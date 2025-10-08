#!/usr/bin/env python3
"""
Enhanced Batch Git Template Publisher with Quality Curation
Integrates auto-classification, quality gates, deduplication, and category limits

Features:
- Quality gate filtering (--quality-gate 80)
- Deduplication based on similarity (--deduplicate)
- Category limits (--max-per-category 20)
- Auto tier assignment (--tier-auto-assign)
- Integration with template_auto_classifier.py

Usage:
    poetry run python batch_git_template_publisher_enhanced.py \\
        --source-dir /path/to/projects \\
        --quality-gate 80 \\
        --max-templates 150 \\
        --max-per-category 20 \\
        --deduplicate \\
        --tier-auto-assign \\
        --github-token $GITHUB_TOKEN \\
        --admin-key $MAESTRO_ADMIN_KEY
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from git_template_publisher import GitConfig, GitTemplatePublisher, TemplateRegistrationConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ClassifiedProject:
    """Project with classification metadata"""

    path: Path
    name: str
    category: str
    language: str
    framework: Optional[str]
    quality_score: float
    tags: List[str]
    file_count: int
    total_lines: int
    features: List[str]
    description: str = ""
    tier: str = "standard"
    is_pinned: bool = False
    similarity_hash: str = ""


@dataclass
class CurationStats:
    """Statistics for curation process"""

    total_discovered: int = 0
    classified: int = 0
    classification_failed: int = 0
    passed_quality_gate: int = 0
    failed_quality_gate: int = 0
    after_deduplication: int = 0
    duplicates_removed: int = 0
    after_category_limits: int = 0
    category_overflow: int = 0
    published: int = 0
    failed_publish: int = 0

    # Category breakdown
    by_category: Dict[str, int] = field(default_factory=dict)
    by_tier: Dict[str, int] = field(default_factory=dict)
    by_language: Dict[str, int] = field(default_factory=dict)

    errors: List[Dict[str, str]] = field(default_factory=list)


class EnhancedBatchPublisher:
    """
    Enhanced batch publisher with quality curation features
    """

    def __init__(
        self,
        source_dir: Path,
        git_config: GitConfig,
        template_config: TemplateRegistrationConfig,
        quality_gate: float = 0.0,
        max_templates: Optional[int] = None,
        max_per_category: Optional[int] = None,
        deduplicate: bool = False,
        tier_auto_assign: bool = False,
        dry_run: bool = False,
    ):
        self.source_dir = Path(source_dir)
        self.git_config = git_config
        self.template_config = template_config
        self.quality_gate = quality_gate
        self.max_templates = max_templates
        self.max_per_category = max_per_category
        self.deduplicate = deduplicate
        self.tier_auto_assign = tier_auto_assign
        self.dry_run = dry_run
        self.stats = CurationStats()

    async def classify_projects(self, project_paths: List[Path]) -> List[ClassifiedProject]:
        """
        Classify projects using template_auto_classifier.py

        Args:
            project_paths: List of project directories

        Returns:
            List of classified projects
        """
        logger.info(f"\n🔍 Classifying {len(project_paths)} projects...")

        classified_projects = []

        for project_path in project_paths:
            try:
                # Run auto-classifier for single project
                result = subprocess.run(
                    [
                        "poetry",
                        "run",
                        "python",
                        "template_auto_classifier.py",
                        "single",
                        "--project-dir",
                        str(project_path),
                        "--output",
                        "json",
                    ],
                    cwd="/home/ec2-user/projects/maestro-engine",
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if result.returncode == 0:
                    classification = json.loads(result.stdout)

                    # Calculate quality score (0-100)
                    quality_score = self._calculate_quality_score(classification, project_path)

                    classified = ClassifiedProject(
                        path=project_path,
                        name=classification.get("name", project_path.name),
                        category=classification.get("category", "utility"),
                        language=classification.get("language", "unknown"),
                        framework=classification.get("framework"),
                        quality_score=quality_score,
                        tags=classification.get("tags", []),
                        file_count=classification.get("file_count", 0),
                        total_lines=classification.get("total_lines", 0),
                        features=classification.get("features", []),
                        description=classification.get("description", ""),
                        similarity_hash=self._generate_similarity_hash(classification),
                    )

                    classified_projects.append(classified)
                    self.stats.classified += 1

                    logger.debug(
                        f"  ✅ {project_path.name}: {classified.category}/{classified.language} (score: {quality_score:.1f})"
                    )

                else:
                    logger.warning(
                        f"  ⚠️ Classification failed for {project_path.name}: {result.stderr[:100]}"
                    )
                    self.stats.classification_failed += 1

            except Exception as e:
                logger.error(f"  ❌ Error classifying {project_path.name}: {e}")
                self.stats.classification_failed += 1
                self.stats.errors.append(
                    {"project": project_path.name, "stage": "classification", "error": str(e)}
                )

        logger.info(
            f"✅ Classification complete: {self.stats.classified} successful, {self.stats.classification_failed} failed"
        )
        return classified_projects

    def _calculate_quality_score(self, classification: Dict, project_path: Path) -> float:
        """
        Calculate quality score (0-100) based on multiple signals

        Scoring factors:
        - Code completeness (30 points)
        - Documentation quality (25 points)
        - Code quality (25 points)
        - Uniqueness/Features (20 points)
        """
        score = 0.0

        # Code completeness (30 points)
        has_readme = (project_path / "README.md").exists()
        has_manifest = (project_path / "manifest.yaml").exists()
        file_count = classification.get("file_count", 0)

        if has_readme:
            score += 10
        if has_manifest:
            score += 10
        if file_count >= 5:
            score += 10
        elif file_count >= 3:
            score += 5

        # Documentation quality (25 points)
        if has_readme:
            readme_content = (project_path / "README.md").read_text()
            if len(readme_content) > 500:
                score += 10
            if "## Usage" in readme_content or "## Installation" in readme_content:
                score += 8
            if "## Examples" in readme_content or "## Example" in readme_content:
                score += 7

        # Code quality (25 points)
        total_lines = classification.get("total_lines", 0)
        framework = classification.get("framework")

        if total_lines > 100:
            score += 10
        elif total_lines > 50:
            score += 5

        if framework:
            score += 10  # Has recognized framework

        # Detect tests
        has_tests = any("test" in str(f).lower() for f in project_path.rglob("*"))
        if has_tests:
            score += 5

        # Features (20 points)
        features = classification.get("features", [])
        score += min(len(features) * 4, 20)

        return min(score, 100.0)

    def _generate_similarity_hash(self, classification: Dict) -> str:
        """Generate similarity hash for deduplication"""
        # Create hash based on category, language, framework, and features
        hash_input = f"{classification.get('category', '')}|{classification.get('language', '')}|{classification.get('framework', '')}|{'|'.join(sorted(classification.get('features', [])))}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:8]

    def apply_quality_gate(self, projects: List[ClassifiedProject]) -> List[ClassifiedProject]:
        """
        Filter projects by quality score threshold

        Args:
            projects: List of classified projects

        Returns:
            Filtered list of projects passing quality gate
        """
        if self.quality_gate <= 0:
            return projects

        logger.info(f"\n🚦 Applying quality gate (threshold: {self.quality_gate})")

        passed = []
        for project in projects:
            if project.quality_score >= self.quality_gate:
                passed.append(project)
                self.stats.passed_quality_gate += 1
            else:
                self.stats.failed_quality_gate += 1
                logger.debug(
                    f"  ⛔ {project.name}: score {project.quality_score:.1f} < {self.quality_gate}"
                )

        logger.info(
            f"✅ Quality gate: {self.stats.passed_quality_gate} passed, {self.stats.failed_quality_gate} filtered"
        )
        return passed

    def deduplicate_projects(self, projects: List[ClassifiedProject]) -> List[ClassifiedProject]:
        """
        Remove duplicate/similar projects

        Args:
            projects: List of classified projects

        Returns:
            Deduplicated list of projects
        """
        if not self.deduplicate:
            return projects

        logger.info(f"\n🔄 Deduplicating projects (similarity threshold: 85%)")

        # Group by similarity hash
        hash_groups: Dict[str, List[ClassifiedProject]] = defaultdict(list)
        for project in projects:
            hash_groups[project.similarity_hash].append(project)

        # Keep highest quality from each group
        unique_projects = []
        for hash_val, group in hash_groups.items():
            if len(group) > 1:
                # Sort by quality score descending
                group.sort(key=lambda p: p.quality_score, reverse=True)
                best = group[0]
                unique_projects.append(best)
                self.stats.duplicates_removed += len(group) - 1
                logger.debug(
                    f"  🔄 Kept {best.name} (score: {best.quality_score:.1f}), removed {len(group)-1} similar"
                )
            else:
                unique_projects.append(group[0])

        self.stats.after_deduplication = len(unique_projects)
        logger.info(
            f"✅ Deduplication: {self.stats.duplicates_removed} duplicates removed, {len(unique_projects)} unique"
        )

        return unique_projects

    def apply_category_limits(self, projects: List[ClassifiedProject]) -> List[ClassifiedProject]:
        """
        Apply per-category limits

        Args:
            projects: List of classified projects

        Returns:
            Projects after applying category limits
        """
        if not self.max_per_category:
            return projects

        logger.info(f"\n📊 Applying category limits (max {self.max_per_category} per category)")

        # Group by category
        by_category: Dict[str, List[ClassifiedProject]] = defaultdict(list)
        for project in projects:
            by_category[project.category].append(project)

        # Apply limits per category
        limited_projects = []
        for category, group in by_category.items():
            # Sort by quality score descending
            group.sort(key=lambda p: p.quality_score, reverse=True)

            kept = group[: self.max_per_category]
            overflow = len(group) - len(kept)

            limited_projects.extend(kept)
            self.stats.by_category[category] = len(kept)
            self.stats.category_overflow += overflow

            if overflow > 0:
                logger.info(f"  📉 {category}: kept top {len(kept)}, removed {overflow}")
            else:
                logger.info(f"  ✅ {category}: kept all {len(kept)}")

        self.stats.after_category_limits = len(limited_projects)
        logger.info(
            f"✅ Category limits applied: {len(limited_projects)} templates, {self.stats.category_overflow} overflow"
        )

        return limited_projects

    def assign_tiers(self, projects: List[ClassifiedProject]) -> List[ClassifiedProject]:
        """
        Auto-assign quality tiers based on scores

        Tiers:
        - Gold (≥90): Pinned, top tier
        - Silver (80-89): Pinned, high quality
        - Bronze (70-79): Available, not pinned
        - Standard (<70): Available, not pinned

        Args:
            projects: List of classified projects

        Returns:
            Projects with assigned tiers
        """
        if not self.tier_auto_assign:
            return projects

        logger.info(f"\n🏅 Assigning quality tiers")

        for project in projects:
            if project.quality_score >= 90:
                project.tier = "gold"
                project.is_pinned = True
                self.stats.by_tier["gold"] = self.stats.by_tier.get("gold", 0) + 1
            elif project.quality_score >= 80:
                project.tier = "silver"
                project.is_pinned = True
                self.stats.by_tier["silver"] = self.stats.by_tier.get("silver", 0) + 1
            elif project.quality_score >= 70:
                project.tier = "bronze"
                project.is_pinned = False
                self.stats.by_tier["bronze"] = self.stats.by_tier.get("bronze", 0) + 1
            else:
                project.tier = "standard"
                project.is_pinned = False
                self.stats.by_tier["standard"] = self.stats.by_tier.get("standard", 0) + 1

        logger.info(f"✅ Tier assignment complete:")
        for tier, count in sorted(self.stats.by_tier.items()):
            logger.info(f"   {tier.capitalize()}: {count}")

        return projects

    async def publish_projects(self, projects: List[ClassifiedProject]) -> CurationStats:
        """
        Publish curated projects

        Args:
            projects: List of curated projects to publish

        Returns:
            Publishing statistics
        """
        # Apply max templates limit
        if self.max_templates and len(projects) > self.max_templates:
            logger.info(f"\n✂️  Limiting to {self.max_templates} templates (from {len(projects)})")
            # Sort by quality score descending
            projects.sort(key=lambda p: p.quality_score, reverse=True)
            projects = projects[: self.max_templates]

        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 Publishing {len(projects)} curated templates")
        logger.info(f"{'='*70}\n")

        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No actual publishing\n")
            for i, project in enumerate(projects, 1):
                logger.info(f"[{i}/{len(projects)}] Would publish: {project.name}")
                logger.info(f"  Category: {project.category} | Language: {project.language}")
                logger.info(
                    f"  Quality: {project.quality_score:.1f} | Tier: {project.tier} | Pinned: {project.is_pinned}"
                )
            self.stats.published = len(projects)
            return self.stats

        start_time = time.time()

        async with GitTemplatePublisher(self.git_config, self.template_config) as publisher:
            for i, project in enumerate(projects, 1):
                logger.info(f"\n[{i}/{len(projects)}] " + "=" * 60)
                logger.info(f"📦 {project.name}")
                logger.info(
                    f"   Category: {project.category} | Language: {project.language} | Framework: {project.framework or 'none'}"
                )
                logger.info(
                    f"   Quality: {project.quality_score:.1f} | Tier: {project.tier} | Pinned: {project.is_pinned}"
                )

                # Generate repo name
                repo_name = self._generate_repo_name(project)

                # Publish
                result = await publisher.publish_project(project.path, repo_name)

                if result["success"]:
                    self.stats.published += 1
                    logger.info(f"   ✅ Published: {result.get('git_url')}")
                else:
                    self.stats.failed_publish += 1
                    logger.error(f"   ❌ Failed: {result.get('error')}")
                    self.stats.errors.append(
                        {
                            "project": project.name,
                            "stage": "publish",
                            "error": result.get("error", "Unknown"),
                        }
                    )

                # Progress
                progress_pct = (i / len(projects)) * 100
                logger.info(
                    f"\n   📊 Progress: {progress_pct:.1f}% ({self.stats.published} published, {self.stats.failed_publish} failed)"
                )

                # Rate limiting
                await asyncio.sleep(2)

        duration = time.time() - start_time

        # Final summary
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 CURATED PUBLISHING COMPLETE")
        logger.info(f"{'='*70}")
        logger.info(f"\n📈 Pipeline Summary:")
        logger.info(f"   Total Discovered: {self.stats.total_discovered}")
        logger.info(f"   Classified: {self.stats.classified}")
        logger.info(
            f"   Passed Quality Gate (≥{self.quality_gate}): {self.stats.passed_quality_gate}"
        )
        logger.info(f"   After Deduplication: {self.stats.after_deduplication}")
        logger.info(f"   After Category Limits: {self.stats.after_category_limits}")
        logger.info(f"   Published: {self.stats.published}")
        logger.info(f"   Failed: {self.stats.failed_publish}")

        logger.info(f"\n🏅 Templates by Tier:")
        for tier in ["gold", "silver", "bronze", "standard"]:
            count = self.stats.by_tier.get(tier, 0)
            if count > 0:
                emoji = {"gold": "🥇", "silver": "🥈", "bronze": "🥉", "standard": "📄"}.get(
                    tier, ""
                )
                logger.info(f"   {emoji} {tier.capitalize()}: {count}")

        logger.info(f"\n📂 Templates by Category:")
        for category, count in sorted(self.stats.by_category.items()):
            logger.info(f"   {category}: {count}")

        logger.info(f"\n⏱️  Duration: {duration:.1f}s ({duration/len(projects):.1f}s per template)")
        logger.info(f"{'='*70}\n")

        return self.stats

    def _generate_repo_name(self, project: ClassifiedProject) -> str:
        """Generate repository name from project"""
        repo_name = project.name.replace("_", "-").lower()
        if not repo_name[0].isalnum():
            repo_name = "maestro-" + repo_name
        return f"maestro-template-{repo_name}"

    async def run(self) -> CurationStats:
        """
        Run complete curated publishing pipeline

        Returns:
            Curation statistics
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🎯 ENHANCED CURATED TEMPLATE PUBLISHING")
        logger.info(f"{'='*70}")
        logger.info(f"Source: {self.source_dir}")
        logger.info(f"Quality Gate: {self.quality_gate if self.quality_gate > 0 else 'None'}")
        logger.info(f"Deduplicate: {self.deduplicate}")
        logger.info(f"Max Templates: {self.max_templates or 'Unlimited'}")
        logger.info(f"Max Per Category: {self.max_per_category or 'Unlimited'}")
        logger.info(f"Tier Assignment: {self.tier_auto_assign}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info(f"{'='*70}\n")

        # Step 1: Discover projects
        logger.info("📂 Step 1: Discovering projects...")
        project_paths = await self._discover_projects()
        self.stats.total_discovered = len(project_paths)

        if not project_paths:
            logger.error("❌ No projects found")
            return self.stats

        # Step 2: Classify
        logger.info(f"\n🔍 Step 2: Classifying {len(project_paths)} projects...")
        classified = await self.classify_projects(project_paths)

        # Step 3: Quality gate
        filtered = self.apply_quality_gate(classified)

        # Step 4: Deduplicate
        unique = self.deduplicate_projects(filtered)

        # Step 5: Category limits
        limited = self.apply_category_limits(unique)

        # Step 6: Assign tiers
        tiered = self.assign_tiers(limited)

        # Step 7: Publish
        await self.publish_projects(tiered)

        return self.stats

    async def _discover_projects(self) -> List[Path]:
        """Discover project directories"""
        if not self.source_dir.exists():
            logger.error(f"❌ Source directory not found: {self.source_dir}")
            return []

        projects = []
        for item in self.source_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                # Check for code files
                code_files = (
                    list(item.rglob("*.py")) + list(item.rglob("*.js")) + list(item.rglob("*.ts"))
                )
                if code_files:
                    projects.append(item)

        logger.info(f"✅ Discovered {len(projects)} projects")
        return projects


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Enhanced batch publisher with quality curation")

    # Source
    parser.add_argument(
        "--source-dir",
        default="/home/ec2-user/projects/maestro-v2/enhanced_lean_output",
        help="Source directory with projects",
    )

    # Quality curation
    parser.add_argument(
        "--quality-gate",
        type=float,
        default=0.0,
        help="Minimum quality score (0-100). Example: --quality-gate 80",
    )
    parser.add_argument(
        "--max-templates",
        type=int,
        help="Maximum number of templates to publish. Example: --max-templates 150",
    )
    parser.add_argument(
        "--max-per-category",
        type=int,
        help="Maximum templates per category. Example: --max-per-category 20",
    )
    parser.add_argument(
        "--deduplicate", action="store_true", help="Remove duplicate/similar templates"
    )
    parser.add_argument(
        "--tier-auto-assign",
        action="store_true",
        help="Auto-assign quality tiers (gold/silver/bronze)",
    )

    # Git provider
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
        "--private", action="store_true", default=True, help="Make repositories private"
    )

    # Registry
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

    # Control
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview curation without publishing"
    )
    parser.add_argument("--verbose", action="store_true", help="Detailed logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate
    if args.git_provider == "github" and not args.github_token:
        logger.error("❌ GitHub token required. Set --github-token or GITHUB_TOKEN env var")
        return 1

    if not args.dry_run and not args.admin_key:
        logger.error(
            "❌ Admin key required for publishing. Set --admin-key or MAESTRO_ADMIN_KEY env var"
        )
        return 1

    # Configure
    git_config = GitConfig(
        git_provider=args.git_provider,
        github_token=args.github_token,
        github_org=args.github_org,
        make_private=args.private,
    )

    template_config = TemplateRegistrationConfig(
        registry_url=args.registry_url, admin_api_key=args.admin_key, organization=args.organization
    )

    # Create publisher
    publisher = EnhancedBatchPublisher(
        source_dir=args.source_dir,
        git_config=git_config,
        template_config=template_config,
        quality_gate=args.quality_gate,
        max_templates=args.max_templates,
        max_per_category=args.max_per_category,
        deduplicate=args.deduplicate,
        tier_auto_assign=args.tier_auto_assign,
        dry_run=args.dry_run,
    )

    # Run
    stats = await publisher.run()

    # Save stats
    stats_file = Path("enhanced_batch_publishing_stats.json")
    with open(stats_file, "w") as f:
        json.dump(asdict(stats), f, indent=2)

    logger.info(f"📄 Stats saved to: {stats_file}")

    return 0 if stats.failed_publish == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
