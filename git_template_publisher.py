#!/usr/bin/env python3
"""
Git Template Publisher
Converts generated projects into Git repositories and registers them as templates

This script:
1. Creates a Git repository for each generated project
2. Pushes to GitHub/GitLab/Local Git server
3. Registers template via maestro-templates admin API

Usage:
    poetry run python git_template_publisher.py --project-dir PATH [options]
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class GitConfig:
    """Git configuration"""

    git_provider: str = "github"  # github, gitlab, local
    github_token: str = ""
    github_org: str = ""
    gitlab_token: str = ""
    gitlab_group: str = ""
    local_git_url: str = ""
    auto_create_repo: bool = True
    make_private: bool = True


@dataclass
class TemplateRegistrationConfig:
    """Template registration configuration"""

    registry_url: str = "http://localhost:9600"
    admin_api_key: str = ""
    organization: str = "maestro-generated"
    auto_validate: bool = True


class GitTemplatePublisher:
    """
    Publishes generated projects as Git-based templates
    """

    def __init__(self, git_config: GitConfig, template_config: TemplateRegistrationConfig):
        self.git_config = git_config
        self.template_config = template_config
        self.http_client = httpx.AsyncClient(timeout=300.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()

    def _run_git_command(self, cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
        """Run a git command"""
        try:
            result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=True)
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: {' '.join(cmd)}")
            logger.error(f"Error: {e.stderr}")
            raise

    async def initialize_git_repo(self, project_path: Path) -> bool:
        """
        Initialize a Git repository in the project directory

        Args:
            project_path: Path to project directory

        Returns:
            True if successful
        """
        try:
            logger.info(f"  📦 Initializing Git repository in {project_path.name}")

            # Check if already a git repo
            if (project_path / ".git").exists():
                logger.info(f"  ✅ Git repository already initialized")
                return True

            # Initialize git
            self._run_git_command(["git", "init"], project_path)
            logger.info(f"  ✅ Git initialized")

            # Configure git user (for commits)
            self._run_git_command(["git", "config", "user.name", "MAESTRO Bot"], project_path)
            self._run_git_command(
                ["git", "config", "user.email", "maestro-bot@example.com"], project_path
            )

            # Add all files
            self._run_git_command(["git", "add", "."], project_path)
            logger.info(f"  ✅ Files added to Git")

            # Create initial commit
            commit_message = f"Initial commit: MAESTRO generated project\n\nGenerated: {datetime.now().isoformat()}"
            self._run_git_command(["git", "commit", "-m", commit_message], project_path)
            logger.info(f"  ✅ Initial commit created")

            return True

        except Exception as e:
            logger.error(f"  ❌ Failed to initialize Git: {e}")
            return False

    async def create_github_repo(self, repo_name: str) -> Optional[str]:
        """
        Create a GitHub repository

        Args:
            repo_name: Repository name

        Returns:
            Repository URL if successful, None otherwise
        """
        try:
            logger.info(f"  🐙 Creating GitHub repository: {repo_name}")

            headers = {
                "Authorization": f"token {self.git_config.github_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            # Determine endpoint (user or org)
            if self.git_config.github_org:
                url = f"https://api.github.com/orgs/{self.git_config.github_org}/repos"
            else:
                url = "https://api.github.com/user/repos"

            data = {
                "name": repo_name,
                "private": self.git_config.make_private,
                "description": f"MAESTRO generated template - {repo_name}",
                "auto_init": False,
            }

            response = await self.http_client.post(url, json=data, headers=headers)

            if response.status_code == 201:
                repo_data = response.json()
                clone_url = repo_data["clone_url"]
                logger.info(f"  ✅ GitHub repository created: {clone_url}")
                return clone_url
            elif response.status_code == 422:
                # Repository already exists
                logger.warning(f"  ⚠️ Repository {repo_name} already exists")
                if self.git_config.github_org:
                    return f"https://github.com/{self.git_config.github_org}/{repo_name}.git"
                else:
                    # Get username
                    user_response = await self.http_client.get(
                        "https://api.github.com/user", headers=headers
                    )
                    username = user_response.json()["login"]
                    return f"https://github.com/{username}/{repo_name}.git"
            else:
                logger.error(f"  ❌ Failed to create GitHub repo: {response.status_code}")
                logger.error(f"  Response: {response.text}")
                return None

        except Exception as e:
            logger.error(f"  ❌ Failed to create GitHub repository: {e}")
            return None

    async def create_gitlab_repo(self, repo_name: str) -> Optional[str]:
        """
        Create a GitLab repository

        Args:
            repo_name: Repository name

        Returns:
            Repository URL if successful, None otherwise
        """
        try:
            logger.info(f"  🦊 Creating GitLab repository: {repo_name}")

            headers = {
                "PRIVATE-TOKEN": self.git_config.gitlab_token,
                "Content-Type": "application/json",
            }

            data = {
                "name": repo_name,
                "visibility": "private" if self.git_config.make_private else "public",
                "description": f"MAESTRO generated template - {repo_name}",
            }

            if self.git_config.gitlab_group:
                # Create in group
                url = f"https://gitlab.com/api/v4/projects"
                data["namespace_id"] = self.git_config.gitlab_group
            else:
                # Create in user namespace
                url = "https://gitlab.com/api/v4/projects"

            response = await self.http_client.post(url, json=data, headers=headers)

            if response.status_code == 201:
                repo_data = response.json()
                http_url = repo_data["http_url_to_repo"]
                logger.info(f"  ✅ GitLab repository created: {http_url}")
                return http_url
            else:
                logger.error(f"  ❌ Failed to create GitLab repo: {response.status_code}")
                logger.error(f"  Response: {response.text}")
                return None

        except Exception as e:
            logger.error(f"  ❌ Failed to create GitLab repository: {e}")
            return None

    async def push_to_remote(self, project_path: Path, remote_url: str) -> bool:
        """
        Push repository to remote

        Args:
            project_path: Path to project directory
            remote_url: Remote repository URL

        Returns:
            True if successful
        """
        try:
            logger.info(f"  🚀 Pushing to remote: {remote_url}")

            # Configure authentication for HTTPS
            if self.git_config.git_provider == "github" and self.git_config.github_token:
                # Use token in URL
                auth_url = remote_url.replace(
                    "https://", f"https://{self.git_config.github_token}@"
                )
            elif self.git_config.git_provider == "gitlab" and self.git_config.gitlab_token:
                # Use token in URL
                auth_url = remote_url.replace(
                    "https://", f"https://oauth2:{self.git_config.gitlab_token}@"
                )
            else:
                auth_url = remote_url

            # Add remote
            try:
                self._run_git_command(["git", "remote", "add", "origin", auth_url], project_path)
            except subprocess.CalledProcessError:
                # Remote might already exist, update it
                self._run_git_command(
                    ["git", "remote", "set-url", "origin", auth_url], project_path
                )

            # Set default branch to main
            self._run_git_command(["git", "branch", "-M", "main"], project_path)

            # Push to remote
            self._run_git_command(["git", "push", "-u", "origin", "main"], project_path)
            logger.info(f"  ✅ Pushed to remote successfully")

            return True

        except Exception as e:
            logger.error(f"  ❌ Failed to push to remote: {e}")
            return False

    async def register_template(
        self, git_url: str, project_name: str, metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Register template with maestro-templates service

        Args:
            git_url: Git repository URL
            project_name: Project name
            metadata: Optional metadata

        Returns:
            Template ID if successful, None otherwise
        """
        try:
            logger.info(f"  📋 Registering template with maestro-templates")

            url = f"{self.template_config.registry_url}/api/v1/admin/templates"

            headers = {
                "X-Admin-Key": self.template_config.admin_api_key,
                "Content-Type": "application/json",
            }

            data = {
                "git_url": git_url,
                "git_branch": "main",
                "organization": self.template_config.organization,
                "auto_validate": self.template_config.auto_validate,
            }

            response = await self.http_client.post(url, json=data, headers=headers)

            if response.status_code == 201:
                result = response.json()
                template_id = result.get("template_id") or result.get("id")
                logger.info(f"  ✅ Template registered: {template_id}")
                return template_id
            elif response.status_code == 409:
                logger.warning(f"  ⚠️ Template already exists")
                return None
            else:
                logger.error(f"  ❌ Failed to register template: {response.status_code}")
                logger.error(f"  Response: {response.text}")
                return None

        except Exception as e:
            logger.error(f"  ❌ Failed to register template: {e}")
            return None

    async def publish_project(
        self, project_path: Path, repo_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publish a project as a Git-based template

        Args:
            project_path: Path to project directory
            repo_name: Optional repository name (defaults to project directory name)

        Returns:
            Result dictionary with status and details
        """
        result = {
            "project": project_path.name,
            "success": False,
            "git_url": None,
            "template_id": None,
            "error": None,
        }

        try:
            repo_name = repo_name or project_path.name

            logger.info(f"\n{'='*60}")
            logger.info(f"📦 Publishing: {project_path.name}")
            logger.info(f"{'='*60}")

            # Step 0: Classify project and generate manifest.yaml (if not exists)
            manifest_path = project_path / "manifest.yaml"
            if not manifest_path.exists():
                logger.info("  🔍 Classifying project and generating manifest...")
                try:
                    from manifest_generator import ManifestGenerator

                    generator = ManifestGenerator()
                    classification, manifest_path = generator.classify_and_generate_manifest(
                        project_path
                    )

                    logger.info(
                        f"  ✅ Classified as: {classification.category} | {classification.language} | {classification.framework or 'N/A'}"
                    )
                    result["classification"] = {
                        "category": classification.category,
                        "language": classification.language,
                        "framework": classification.framework,
                        "tags": classification.tags,
                        "confidence": classification.confidence,
                    }
                except Exception as e:
                    logger.warning(f"  ⚠️ Classification failed: {e} - continuing without manifest")
            else:
                logger.info("  ✅ Manifest already exists, skipping classification")

            # Step 1: Initialize Git repository
            if not await self.initialize_git_repo(project_path):
                result["error"] = "Failed to initialize Git repository"
                return result

            # Step 2: Create remote repository
            if self.git_config.git_provider == "github":
                git_url = await self.create_github_repo(repo_name)
            elif self.git_config.git_provider == "gitlab":
                git_url = await self.create_gitlab_repo(repo_name)
            elif self.git_config.git_provider == "local":
                git_url = f"{self.git_config.local_git_url}/{repo_name}.git"
            else:
                result["error"] = f"Unknown git provider: {self.git_config.git_provider}"
                return result

            if not git_url:
                result["error"] = "Failed to create remote repository"
                return result

            result["git_url"] = git_url

            # Step 3: Push to remote
            if not await self.push_to_remote(project_path, git_url):
                result["error"] = "Failed to push to remote"
                return result

            # Step 4: Register template
            template_id = await self.register_template(git_url, repo_name)
            result["template_id"] = template_id
            result["success"] = template_id is not None

            if result["success"]:
                logger.info(f"\n✅ Successfully published: {repo_name}")
                logger.info(f"   Git URL: {git_url}")
                logger.info(f"   Template ID: {template_id}")
            else:
                logger.warning(
                    f"\n⚠️ Partially published (Git OK, template registration failed): {repo_name}"
                )

            return result

        except Exception as e:
            logger.error(f"\n❌ Failed to publish {project_path.name}: {e}")
            result["error"] = str(e)
            return result


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Publish MAESTRO projects as Git-based templates")
    parser.add_argument("--project-dir", required=True, help="Project directory to publish")
    parser.add_argument("--repo-name", help="Repository name (defaults to project directory name)")
    parser.add_argument(
        "--git-provider",
        default="github",
        choices=["github", "gitlab", "local"],
        help="Git hosting provider",
    )
    parser.add_argument(
        "--github-token",
        default=os.getenv("GITHUB_TOKEN", ""),
        help="GitHub personal access token (or set GITHUB_TOKEN env var)",
    )
    parser.add_argument(
        "--github-org",
        default=os.getenv("GITHUB_ORG", ""),
        help="GitHub organization (optional, defaults to personal)",
    )
    parser.add_argument(
        "--gitlab-token", default=os.getenv("GITLAB_TOKEN", ""), help="GitLab personal access token"
    )
    parser.add_argument("--private", action="store_true", help="Make repository private")
    parser.add_argument(
        "--registry-url", default="http://localhost:9600", help="Template registry URL"
    )
    parser.add_argument(
        "--admin-key",
        default=os.getenv("MAESTRO_ADMIN_KEY", ""),
        help="Admin API key for template registry",
    )
    parser.add_argument(
        "--organization", default="maestro-generated", help="Template organization name"
    )

    args = parser.parse_args()

    # Validate inputs
    project_path = Path(args.project_dir)
    if not project_path.exists():
        logger.error(f"❌ Project directory does not exist: {project_path}")
        return 1

    if not project_path.is_dir():
        logger.error(f"❌ Path is not a directory: {project_path}")
        return 1

    # Validate authentication
    if args.git_provider == "github" and not args.github_token:
        logger.error("❌ GitHub token required. Set --github-token or GITHUB_TOKEN env var")
        return 1

    if args.git_provider == "gitlab" and not args.gitlab_token:
        logger.error("❌ GitLab token required. Set --gitlab-token or GITLAB_TOKEN env var")
        return 1

    if not args.admin_key:
        logger.error("❌ Admin key required. Set --admin-key or MAESTRO_ADMIN_KEY env var")
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

    # Publish
    async with GitTemplatePublisher(git_config, template_config) as publisher:
        result = await publisher.publish_project(project_path, args.repo_name)

        if result["success"]:
            logger.info(f"\n🎉 Template published successfully!")
            return 0
        else:
            logger.error(f"\n❌ Template publishing failed: {result.get('error')}")
            return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
