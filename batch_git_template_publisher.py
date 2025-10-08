#!/usr/bin/env python3
"""
Batch Git Template Publisher
Processes multiple MAESTRO projects and publishes them as Git-based templates

Usage:
    poetry run python batch_git_template_publisher.py --source-dir PATH [options]
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from git_template_publisher import GitConfig, GitTemplatePublisher, TemplateRegistrationConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class BatchStats:
    """Batch processing statistics"""

    total_projects: int = 0
    processed: int = 0
    successful: int = 0
    failed: int = 0
    templates_registered: int = 0
    git_only: int = 0  # Pushed to Git but template registration failed
    errors: List[Dict[str, str]] = field(default_factory=list)


class BatchGitTemplatePublisher:
    """
    Batch processor for publishing multiple projects as Git-based templates
    """

    def __init__(
        self,
        source_dir: Path,
        git_config: GitConfig,
        template_config: TemplateRegistrationConfig,
        dry_run: bool = False,
        limit: Optional[int] = None,
    ):
        self.source_dir = Path(source_dir)
        self.git_config = git_config
        self.template_config = template_config
        self.dry_run = dry_run
        self.limit = limit
        self.stats = BatchStats()

    async def discover_projects(self) -> List[Path]:
        """
        Discover all project directories in source directory

        Returns:
            List of project directory paths
        """
        logger.info(f"🔍 Discovering projects in: {self.source_dir}")

        if not self.source_dir.exists():
            logger.error(f"❌ Source directory does not exist: {self.source_dir}")
            return []

        # Find all subdirectories that look like projects
        projects = []
        for item in self.source_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                # Check if it has actual files
                files = list(item.rglob("*"))
                code_files = [
                    f
                    for f in files
                    if f.is_file()
                    and f.suffix
                    in [
                        ".py",
                        ".js",
                        ".ts",
                        ".jsx",
                        ".tsx",
                        ".html",
                        ".css",
                        ".json",
                        ".md",
                        ".java",
                        ".go",
                        ".rs",
                        ".rb",
                    ]
                ]

                if code_files:
                    projects.append(item)
                    logger.debug(f"  ✅ Found project: {item.name} ({len(code_files)} files)")
                else:
                    logger.debug(f"  ⏭️  Skipped (no code): {item.name}")

        self.stats.total_projects = len(projects)
        logger.info(f"📦 Discovered {len(projects)} projects")

        # Sort by modification time (oldest first, or newest first based on preference)
        projects = sorted(projects, key=lambda p: p.stat().st_mtime, reverse=True)

        # Apply limit if specified
        if self.limit:
            projects = projects[: self.limit]
            logger.info(f"⚙️  Limited to {self.limit} projects")

        return projects

    def generate_repo_name(self, project_path: Path) -> str:
        """
        Generate a repository name from project path

        Args:
            project_path: Project directory path

        Returns:
            Repository name
        """
        # Use project directory name
        repo_name = project_path.name

        # Clean up name (GitHub/GitLab requirements)
        repo_name = repo_name.replace("_", "-")
        repo_name = repo_name.lower()

        # Ensure it starts with alphanumeric
        if not repo_name[0].isalnum():
            repo_name = "maestro-" + repo_name

        # Add prefix to avoid conflicts
        repo_name = f"maestro-template-{repo_name}"

        return repo_name

    async def process_batch(self, projects: List[Path]) -> BatchStats:
        """
        Process a batch of projects

        Args:
            projects: List of project paths

        Returns:
            Batch processing statistics
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 Starting batch Git template publishing")
        logger.info(f"{'='*60}")
        logger.info(f"  Projects: {len(projects)}")
        logger.info(f"  Git Provider: {self.git_config.git_provider}")
        logger.info(f"  Registry: {self.template_config.registry_url}")
        logger.info(f"  Organization: {self.template_config.organization}")
        logger.info(f"  Dry Run: {self.dry_run}")
        logger.info(f"{'='*60}\n")

        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No actual changes will be made\n")

        start_time = time.time()

        async with GitTemplatePublisher(self.git_config, self.template_config) as publisher:
            for i, project_path in enumerate(projects, 1):
                logger.info(f"\n[{i}/{len(projects)}] " + "=" * 50)

                repo_name = self.generate_repo_name(project_path)
                logger.info(f"📦 Project: {project_path.name}")
                logger.info(f"🏷️  Repo Name: {repo_name}")

                if self.dry_run:
                    logger.info(f"  🔍 [DRY RUN] Would publish as: {repo_name}")
                    self.stats.processed += 1
                    self.stats.successful += 1
                    continue

                # Publish project
                result = await publisher.publish_project(project_path, repo_name)

                self.stats.processed += 1

                if result["success"]:
                    self.stats.successful += 1
                    self.stats.templates_registered += 1
                elif result.get("git_url"):
                    # Git push succeeded but template registration failed
                    self.stats.git_only += 1
                    self.stats.errors.append(
                        {
                            "project": project_path.name,
                            "error": result.get("error", "Template registration failed"),
                            "git_url": result["git_url"],
                        }
                    )
                else:
                    self.stats.failed += 1
                    self.stats.errors.append(
                        {
                            "project": project_path.name,
                            "error": result.get("error", "Unknown error"),
                        }
                    )

                # Show progress
                progress_pct = (i / len(projects)) * 100
                logger.info(f"\n📊 Progress: {progress_pct:.1f}% ({i}/{len(projects)})")
                logger.info(f"   Successful: {self.stats.successful}")
                logger.info(f"   Failed: {self.stats.failed}")
                logger.info(f"   Templates Registered: {self.stats.templates_registered}")

                # Small delay to avoid rate limiting
                await asyncio.sleep(2)

        duration = time.time() - start_time

        # Print final summary
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 BATCH PUBLISHING COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"  Total Projects: {self.stats.total_projects}")
        logger.info(f"  Processed: {self.stats.processed}")
        logger.info(f"  Successful: {self.stats.successful}")
        logger.info(f"  Failed: {self.stats.failed}")
        logger.info(f"  Templates Registered: {self.stats.templates_registered}")
        logger.info(f"  Git Only (no template): {self.stats.git_only}")
        logger.info(f"  Duration: {duration:.2f}s")
        logger.info(f"  Avg Time/Project: {duration/len(projects):.2f}s")
        logger.info(f"{'='*60}\n")

        if self.stats.errors:
            logger.warning(f"\n⚠️  Errors encountered: {len(self.stats.errors)}")
            for error in self.stats.errors[:10]:  # Show first 10
                logger.warning(f"  - {error['project']}: {error['error']}")
            if len(self.stats.errors) > 10:
                logger.warning(f"  ... and {len(self.stats.errors) - 10} more")

        return self.stats


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Batch publish MAESTRO projects as Git-based templates"
    )
    parser.add_argument(
        "--source-dir",
        default="/home/ec2-user/projects/maestro-v2/enhanced_lean_output",
        help="Source directory with projects",
    )
    parser.add_argument(
        "--git-provider",
        default="github",
        choices=["github", "gitlab", "local"],
        help="Git hosting provider",
    )
    parser.add_argument(
        "--github-token", default=os.getenv("GITHUB_TOKEN", ""), help="GitHub personal access token"
    )
    parser.add_argument(
        "--github-org", default=os.getenv("GITHUB_ORG", ""), help="GitHub organization (optional)"
    )
    parser.add_argument(
        "--gitlab-token", default=os.getenv("GITLAB_TOKEN", ""), help="GitLab personal access token"
    )
    parser.add_argument(
        "--private",
        action="store_true",
        default=True,
        help="Make repositories private (default: True)",
    )
    parser.add_argument(
        "--registry-url", default="http://localhost:9600", help="Template registry URL"
    )
    parser.add_argument(
        "--admin-key",
        default=os.getenv("ADMIN_KEY", os.getenv("MAESTRO_ADMIN_KEY", "")),
        help="Admin API key for template registry",
    )
    parser.add_argument(
        "--organization", default="maestro-generated", help="Template organization name"
    )
    parser.add_argument("--limit", type=int, help="Process only N projects")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be published without making changes"
    )
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate authentication
    if args.git_provider == "github" and not args.github_token:
        logger.error("❌ GitHub token required. Set --github-token or GITHUB_TOKEN env var")
        logger.info("\n💡 To create a GitHub token:")
        logger.info("   1. Go to https://github.com/settings/tokens")
        logger.info("   2. Click 'Generate new token (classic)'")
        logger.info("   3. Select scopes: 'repo' (full control)")
        logger.info("   4. Generate and copy the token")
        logger.info("   5. Export: export GITHUB_TOKEN=your_token_here")
        return 1

    if args.git_provider == "gitlab" and not args.gitlab_token:
        logger.error("❌ GitLab token required. Set --gitlab-token or GITLAB_TOKEN env var")
        return 1

    if not args.admin_key:
        logger.error("❌ Admin key required. Set --admin-key or MAESTRO_ADMIN_KEY env var")
        logger.info("\n💡 To get the admin key:")
        logger.info("   Check maestro-templates configuration or .env file")
        return 1

    # Configure
    git_config = GitConfig(
        git_provider=args.git_provider,
        github_token=args.github_token,
        github_org=args.github_org,
        gitlab_token=args.gitlab_token,
        make_private=args.private,
    )

    template_config = TemplateRegistrationConfig(
        registry_url=args.registry_url, admin_api_key=args.admin_key, organization=args.organization
    )

    # Create batch publisher
    publisher = BatchGitTemplatePublisher(
        source_dir=args.source_dir,
        git_config=git_config,
        template_config=template_config,
        dry_run=args.dry_run,
        limit=args.limit,
    )

    # Discover projects
    projects = await publisher.discover_projects()

    if not projects:
        logger.error("❌ No projects found")
        return 1

    # Process batch
    stats = await publisher.process_batch(projects)

    # Write stats to file
    stats_file = Path("batch_git_publishing_stats.json")
    with open(stats_file, "w") as f:
        json.dump(
            {
                "total_projects": stats.total_projects,
                "processed": stats.processed,
                "successful": stats.successful,
                "failed": stats.failed,
                "templates_registered": stats.templates_registered,
                "git_only": stats.git_only,
                "error_count": len(stats.errors),
                "errors": stats.errors,
            },
            f,
            indent=2,
        )

    logger.info(f"📄 Stats written to: {stats_file}")

    return 0 if stats.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
