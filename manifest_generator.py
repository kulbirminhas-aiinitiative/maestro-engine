#!/usr/bin/env python3
"""
Manifest Generator
Generates manifest.yaml files from ProjectClassification

The manifest.yaml format is required by the Template Registry
for Git-based templates.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import yaml

from template_auto_classifier import ProjectClassification, TemplateAutoClassifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ManifestGenerator:
    """
    Generates manifest.yaml files from classification data
    """

    def __init__(self):
        self.classifier = TemplateAutoClassifier()

    def generate_manifest(
        self, classification: ProjectClassification, engine: str = "jinja2"
    ) -> Dict[str, Any]:
        """
        Generate manifest dictionary from classification

        Args:
            classification: Project classification
            engine: Templating engine (jinja2, cookiecutter, copier)

        Returns:
            Manifest dictionary
        """
        manifest = {
            "manifest_version": "1.0",
            "name": classification.name,
            "description": classification.description,
            "version": classification.version,
            "engine": engine,
            "metadata": {
                "category": classification.category,
                "language": classification.language,
                "framework": classification.framework or "none",
                "tags": classification.tags,
                "architecture": classification.architecture,
                # Additional metadata
                "file_count": classification.file_count,
                "total_lines": classification.total_lines,
                "auto_classified": True,
                "classification_confidence": round(classification.confidence, 2),
                "generated_at": datetime.utcnow().isoformat() + "Z",
            },
            "placeholders": [],  # Can be populated later if template has variables
            "hooks": {"pre_generation": [], "post_generation": []},
            "files": {
                "include": ["**/*"],
                "exclude": [
                    ".git/**",
                    "__pycache__/**",
                    "node_modules/**",
                    ".pytest_cache/**",
                    "*.pyc",
                    ".DS_Store",
                ],
            },
        }

        # Add detected languages as metadata
        if classification.detected_languages:
            manifest["metadata"]["detected_languages"] = classification.detected_languages

        # Add detected frameworks
        if classification.detected_frameworks:
            manifest["metadata"]["detected_frameworks"] = classification.detected_frameworks

        # Add features
        if classification.features:
            manifest["metadata"]["features"] = classification.features[:5]

        return manifest

    def write_manifest(
        self, project_path: Path, classification: ProjectClassification, engine: str = "jinja2"
    ) -> Path:
        """
        Write manifest.yaml to project directory

        Args:
            project_path: Path to project directory
            classification: Project classification
            engine: Templating engine

        Returns:
            Path to written manifest.yaml
        """
        manifest = self.generate_manifest(classification, engine)

        manifest_path = project_path / "manifest.yaml"

        try:
            with open(manifest_path, "w") as f:
                yaml.dump(manifest, f, default_flow_style=False, sort_keys=False, indent=2)

            logger.info(f"✅ Manifest written: {manifest_path}")
            return manifest_path

        except Exception as e:
            logger.error(f"❌ Failed to write manifest: {e}")
            raise

    def classify_and_generate_manifest(
        self, project_path: Path, engine: str = "jinja2"
    ) -> tuple[ProjectClassification, Path]:
        """
        Classify project and generate manifest.yaml in one step

        Args:
            project_path: Path to project directory
            engine: Templating engine

        Returns:
            (classification, manifest_path)
        """
        logger.info(f"Processing: {project_path.name}")

        # Classify project
        classification = self.classifier.classify_project(project_path)

        # Write manifest
        manifest_path = self.write_manifest(project_path, classification, engine)

        return classification, manifest_path


def generate_for_project(project_path: str, engine: str = "jinja2"):
    """
    Generate manifest for a single project (CLI helper)

    Args:
        project_path: Path to project directory
        engine: Templating engine (default: jinja2)
    """
    generator = ManifestGenerator()

    project = Path(project_path)
    if not project.exists():
        print(f"❌ Project not found: {project_path}")
        return

    try:
        classification, manifest_path = generator.classify_and_generate_manifest(project, engine)

        print(f"\n{'='*60}")
        print(f"✅ Manifest generated: {manifest_path}")
        print(f"{'='*60}")
        print(f"Category: {classification.category}")
        print(f"Language: {classification.language}")
        print(f"Framework: {classification.framework or 'None'}")
        print(f"Tags: {', '.join(classification.tags)}")
        print(f"Confidence: {classification.confidence:.2%}")

        # Show manifest preview
        print(f"\nManifest Preview:")
        print(f"{'-'*60}")
        with open(manifest_path, "r") as f:
            print(f.read())

    except Exception as e:
        print(f"❌ Error: {e}")
        raise


def batch_generate_manifests(source_dir: Path, limit: int = None, dry_run: bool = False):
    """
    Generate manifests for multiple projects

    Args:
        source_dir: Directory containing projects
        limit: Maximum number of projects to process
        dry_run: If True, only print what would be done
    """
    generator = ManifestGenerator()

    projects = [p for p in source_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]

    if limit:
        projects = projects[:limit]

    logger.info(f"Found {len(projects)} projects")

    stats = {"total": len(projects), "success": 0, "failed": 0, "skipped": 0}

    for i, project_path in enumerate(projects, 1):
        print(f"\n[{i}/{len(projects)}] {project_path.name}")

        # Skip if manifest already exists
        if (project_path / "manifest.yaml").exists():
            print("  ⏭️  Manifest already exists, skipping")
            stats["skipped"] += 1
            continue

        if dry_run:
            print("  🔍 [DRY RUN] Would generate manifest")
            stats["success"] += 1
            continue

        try:
            classification, manifest_path = generator.classify_and_generate_manifest(project_path)
            print(
                f"  ✅ {classification.category} | {classification.language} | {classification.framework or 'N/A'}"
            )
            stats["success"] += 1

        except Exception as e:
            print(f"  ❌ Error: {e}")
            stats["failed"] += 1

    # Print summary
    print(f"\n{'='*60}")
    print(f"📊 BATCH MANIFEST GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"Total: {stats['total']}")
    print(f"Success: {stats['success']}")
    print(f"Failed: {stats['failed']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Generate manifest.yaml for templates")
    parser.add_argument("--project-dir", help="Single project directory to process")
    parser.add_argument(
        "--source-dir",
        default="/home/ec2-user/projects/maestro-v2/enhanced_lean_output",
        help="Source directory with multiple projects (for batch mode)",
    )
    parser.add_argument(
        "--engine",
        default="jinja2",
        choices=["jinja2", "cookiecutter", "copier"],
        help="Templating engine",
    )
    parser.add_argument(
        "--limit", type=int, help="Limit number of projects to process (batch mode)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run - show what would be done without making changes",
    )
    parser.add_argument(
        "--batch", action="store_true", help="Batch mode - process all projects in source-dir"
    )

    args = parser.parse_args()

    if args.project_dir:
        # Single project mode
        generate_for_project(args.project_dir, args.engine)

    elif args.batch:
        # Batch mode
        source_dir = Path(args.source_dir)
        batch_generate_manifests(source_dir, args.limit, args.dry_run)

    else:
        # No arguments - show help
        parser.print_help()
        print("\n" + "=" * 60)
        print("Examples:")
        print("=" * 60)
        print("\n# Generate manifest for single project:")
        print("python manifest_generator.py --project-dir /path/to/project")
        print("\n# Batch generate manifests (first 10 projects):")
        print("python manifest_generator.py --batch --limit 10")
        print("\n# Dry run (test without creating files):")
        print("python manifest_generator.py --batch --limit 5 --dry-run")
        print("\n# Process all 417 projects:")
        print("python manifest_generator.py --batch")
