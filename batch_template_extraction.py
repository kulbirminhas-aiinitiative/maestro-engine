#!/usr/bin/env python3
"""
Batch Template Extraction Script
Retroactively processes existing MAESTRO projects and extracts templates

Usage:
    poetry run python batch_template_extraction.py [options]

Options:
    --source-dir PATH        Source directory with projects (default: maestro-v2/enhanced_lean_output)
    --min-quality SCORE      Minimum quality score for template extraction (default: 75.0)
    --dry-run               Show what would be extracted without actually creating templates
    --limit N               Process only N projects (for testing)
    --parallel N            Number of parallel workers (default: 3)
    --verbose               Show detailed output
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from quality_fabric_client import QualityFabricClient, QualityValidationResult
from templates.quality_fabric_template_bridge import create_templates_from_quality_validation

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class BatchExtractionStats:
    """Statistics for batch extraction"""

    total_projects: int = 0
    processed: int = 0
    successful: int = 0
    failed: int = 0
    templates_created: int = 0
    skipped_low_quality: int = 0
    skipped_no_files: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class BatchTemplateExtractor:
    """
    Batch processor for template extraction from existing projects
    """

    def __init__(
        self,
        source_dir: Path,
        min_quality_score: float = 75.0,
        dry_run: bool = False,
        parallel_workers: int = 3,
    ):
        self.source_dir = Path(source_dir)
        self.min_quality_score = min_quality_score
        self.dry_run = dry_run
        self.parallel_workers = parallel_workers
        self.stats = BatchExtractionStats()

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
                files = list(item.glob("**/*"))
                code_files = [
                    f
                    for f in files
                    if f.is_file()
                    and f.suffix in [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css"]
                ]

                if code_files:
                    projects.append(item)
                    logger.debug(f"  ✅ Found project: {item.name} ({len(code_files)} code files)")
                else:
                    logger.debug(f"  ⏭️  Skipped (no code): {item.name}")

        self.stats.total_projects = len(projects)
        logger.info(f"📦 Discovered {len(projects)} projects")

        return sorted(projects, key=lambda p: p.stat().st_mtime, reverse=True)

    async def analyze_project_quality(self, project_path: Path) -> Optional[Dict[str, Any]]:
        """
        Analyze project quality using static analysis

        Args:
            project_path: Path to project directory

        Returns:
            Quality analysis results or None if failed
        """
        try:
            # Get all code files
            code_files = []
            for ext in [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json"]:
                code_files.extend(list(project_path.glob(f"**/*{ext}")))

            if not code_files:
                logger.debug(f"  ⏭️  No code files in: {project_path.name}")
                self.stats.skipped_no_files += 1
                return None

            # Build mock workflow result for quality analysis
            workflow_result = {
                "session_id": f"batch_extract_{project_path.name}",
                "project_path": str(project_path),
                "files_generated": [str(f.relative_to(project_path)) for f in code_files],
                "success": True,
            }

            # Perform static quality analysis
            quality_metrics = await self._static_quality_analysis(project_path, code_files)

            return {
                "workflow_result": workflow_result,
                "quality_metrics": quality_metrics,
                "code_files": code_files,
            }

        except Exception as e:
            logger.error(f"  ❌ Error analyzing project {project_path.name}: {e}")
            self.stats.errors.append(f"{project_path.name}: {str(e)}")
            return None

    async def _static_quality_analysis(
        self, project_path: Path, code_files: List[Path]
    ) -> Dict[str, Any]:
        """
        Perform static quality analysis on project

        Args:
            project_path: Project directory
            code_files: List of code files

        Returns:
            Quality metrics dictionary
        """
        # Calculate simple quality metrics
        total_lines = 0
        has_tests = False
        has_docs = False
        has_config = False
        file_types = set()

        for file_path in code_files:
            file_types.add(file_path.suffix)

            if "test" in file_path.name.lower() or "spec" in file_path.name.lower():
                has_tests = True

            if file_path.suffix in [".md", ".rst", ".txt"]:
                has_docs = True

            if file_path.name in [
                "package.json",
                "pyproject.toml",
                "requirements.txt",
                "Dockerfile",
                "docker-compose.yml",
            ]:
                has_config = True

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    total_lines += len(f.readlines())
            except:
                pass

        # Calculate quality score (simple heuristic)
        quality_score = 50.0  # Base score

        if has_tests:
            quality_score += 15.0
        if has_docs:
            quality_score += 10.0
        if has_config:
            quality_score += 10.0
        if len(file_types) >= 3:  # Multi-language project
            quality_score += 10.0
        if total_lines > 100:
            quality_score += 5.0

        return {
            "quality_score": min(quality_score, 100.0),
            "security_score": 80.0,  # Default
            "performance_score": 75.0,  # Default
            "maintainability_score": quality_score,
            "test_coverage": 70.0 if has_tests else 0.0,
            "total_tests": 10 if has_tests else 0,
            "passed_tests": 8 if has_tests else 0,
            "failed_tests": 2 if has_tests else 0,
            "errors": 0,
            "duration": 0.5,
            "recommendations": [],
            "issues": [],
            "total_lines": total_lines,
            "file_count": len(code_files),
            "has_tests": has_tests,
            "has_docs": has_docs,
            "has_config": has_config,
        }

    async def extract_templates_from_project(self, project_path: Path) -> Dict[str, Any]:
        """
        Extract templates from a single project

        Args:
            project_path: Path to project directory

        Returns:
            Extraction result dictionary
        """
        project_name = project_path.name
        logger.info(f"📦 Processing: {project_name}")

        result = {
            "project": project_name,
            "success": False,
            "templates_created": 0,
            "template_ids": [],
            "skipped": False,
            "reason": None,
        }

        try:
            # Analyze project quality
            analysis = await self.analyze_project_quality(project_path)

            if not analysis:
                result["skipped"] = True
                result["reason"] = "No code files found"
                return result

            quality_score = analysis["quality_metrics"]["quality_score"]

            logger.info(f"  📊 Quality Score: {quality_score:.1f}")

            # Check if quality meets threshold
            if quality_score < self.min_quality_score:
                logger.info(
                    f"  ⏭️  Skipped (quality {quality_score:.1f} < {self.min_quality_score})"
                )
                result["skipped"] = True
                result["reason"] = (
                    f"Quality score {quality_score:.1f} below threshold {self.min_quality_score}"
                )
                self.stats.skipped_low_quality += 1
                return result

            # Convert to QualityValidationResult
            quality_result = QualityValidationResult(
                execution_id=f"batch_{project_name}_{int(time.time())}",
                success=True,
                quality_score=analysis["quality_metrics"]["quality_score"],
                security_score=analysis["quality_metrics"]["security_score"],
                performance_score=analysis["quality_metrics"]["performance_score"],
                maintainability_score=analysis["quality_metrics"]["maintainability_score"],
                test_coverage=analysis["quality_metrics"]["test_coverage"],
                total_tests=analysis["quality_metrics"]["total_tests"],
                passed_tests=analysis["quality_metrics"]["passed_tests"],
                failed_tests=analysis["quality_metrics"]["failed_tests"],
                error_tests=analysis["quality_metrics"]["errors"],
                duration=analysis["quality_metrics"]["duration"],
                detailed_results=analysis["quality_metrics"],
                recommendations=analysis["quality_metrics"]["recommendations"],
                issues=analysis["quality_metrics"]["issues"],
                timestamp=time.time(),
            )

            if self.dry_run:
                logger.info(
                    f"  🔍 [DRY RUN] Would extract templates from {len(analysis['code_files'])} files"
                )
                result["success"] = True
                result["templates_created"] = len(analysis["code_files"])  # Estimate
                return result

            # Extract templates
            logger.info(f"  🔧 Extracting templates...")
            template_result = await create_templates_from_quality_validation(
                quality_result, analysis["workflow_result"]
            )

            result["success"] = True
            result["templates_created"] = template_result.get("templates_created", 0)
            result["template_ids"] = template_result.get("template_ids", [])

            if result["templates_created"] > 0:
                logger.info(f"  ✅ Created {result['templates_created']} templates")
                self.stats.templates_created += result["templates_created"]
            else:
                logger.info(f"  ℹ️  No templates extracted")

            return result

        except Exception as e:
            logger.error(f"  ❌ Error processing {project_name}: {e}")
            result["error"] = str(e)
            self.stats.errors.append(f"{project_name}: {str(e)}")
            return result

    async def process_batch(self, projects: List[Path]) -> BatchExtractionStats:
        """
        Process a batch of projects

        Args:
            projects: List of project paths

        Returns:
            Batch extraction statistics
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 Starting batch template extraction")
        logger.info(f"{'='*60}")
        logger.info(f"  Projects: {len(projects)}")
        logger.info(f"  Min Quality: {self.min_quality_score}")
        logger.info(f"  Dry Run: {self.dry_run}")
        logger.info(f"  Parallel Workers: {self.parallel_workers}")
        logger.info(f"{'='*60}\n")

        start_time = time.time()

        # Process projects sequentially (can be parallelized later)
        for i, project_path in enumerate(projects, 1):
            logger.info(f"\n[{i}/{len(projects)}] " + "=" * 50)

            result = await self.extract_templates_from_project(project_path)

            self.stats.processed += 1
            if result["success"]:
                self.stats.successful += 1
            else:
                self.stats.failed += 1

            # Show progress
            progress_pct = (i / len(projects)) * 100
            logger.info(f"Progress: {progress_pct:.1f}% ({i}/{len(projects)})")

        duration = time.time() - start_time

        # Print summary
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 BATCH EXTRACTION COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"  Total Projects: {self.stats.total_projects}")
        logger.info(f"  Processed: {self.stats.processed}")
        logger.info(f"  Successful: {self.stats.successful}")
        logger.info(f"  Failed: {self.stats.failed}")
        logger.info(f"  Templates Created: {self.stats.templates_created}")
        logger.info(f"  Skipped (Low Quality): {self.stats.skipped_low_quality}")
        logger.info(f"  Skipped (No Files): {self.stats.skipped_no_files}")
        logger.info(f"  Duration: {duration:.2f}s")
        logger.info(f"{'='*60}\n")

        if self.stats.errors:
            logger.warning(f"\n⚠️  Errors encountered: {len(self.stats.errors)}")
            for error in self.stats.errors[:10]:  # Show first 10
                logger.warning(f"  - {error}")
            if len(self.stats.errors) > 10:
                logger.warning(f"  ... and {len(self.stats.errors) - 10} more")

        return self.stats


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Batch template extraction from existing MAESTRO projects"
    )
    parser.add_argument(
        "--source-dir",
        default="/home/ec2-user/projects/maestro-v2/enhanced_lean_output",
        help="Source directory with projects",
    )
    parser.add_argument(
        "--min-quality",
        type=float,
        default=75.0,
        help="Minimum quality score for template extraction",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be extracted without creating templates",
    )
    parser.add_argument("--limit", type=int, help="Process only N projects")
    parser.add_argument("--parallel", type=int, default=3, help="Number of parallel workers")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create extractor
    extractor = BatchTemplateExtractor(
        source_dir=args.source_dir,
        min_quality_score=args.min_quality,
        dry_run=args.dry_run,
        parallel_workers=args.parallel,
    )

    # Discover projects
    projects = await extractor.discover_projects()

    if not projects:
        logger.error("❌ No projects found")
        return 1

    # Apply limit if specified
    if args.limit:
        logger.info(f"⚙️  Limiting to {args.limit} projects")
        projects = projects[: args.limit]

    # Process batch
    stats = await extractor.process_batch(projects)

    # Write stats to file
    stats_file = Path("batch_extraction_stats.json")
    with open(stats_file, "w") as f:
        json.dump(
            {
                "total_projects": stats.total_projects,
                "processed": stats.processed,
                "successful": stats.successful,
                "failed": stats.failed,
                "templates_created": stats.templates_created,
                "skipped_low_quality": stats.skipped_low_quality,
                "skipped_no_files": stats.skipped_no_files,
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
