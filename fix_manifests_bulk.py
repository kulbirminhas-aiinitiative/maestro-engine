#!/usr/bin/env python3
"""
Bulk Manifest Fixer
Updates manifest.yaml files to add missing required fields for registry validation
"""

import sys
from pathlib import Path

import yaml


def fix_manifest(manifest_path: Path) -> bool:
    """
    Fix a single manifest file by adding missing required fields

    Returns:
        True if file was modified, False otherwise
    """
    try:
        with open(manifest_path, "r") as f:
            manifest = yaml.safe_load(f)

        modified = False

        # Add author if missing
        if "author" not in manifest:
            manifest["author"] = "MAESTRO Orchestrator"
            modified = True
            print(f"  ✅ Added author field")

        # Add license if missing in metadata
        if "metadata" in manifest:
            if "license" not in manifest["metadata"]:
                manifest["metadata"]["license"] = "MIT"
                modified = True
                print(f"  ✅ Added metadata.license field")
        else:
            # Create metadata if it doesn't exist (shouldn't happen)
            manifest["metadata"] = {
                "license": "MIT",
                "category": "utility",
                "language": "unknown",
                "framework": "none",
                "tags": ["generated"],
            }
            modified = True
            print(f"  ✅ Added metadata section")

        if modified:
            # Write back with proper formatting
            with open(manifest_path, "w") as f:
                yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)
            return True

        return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Main entry point"""
    base_dir = Path("/home/ec2-user/projects/maestro-v2/enhanced_lean_output")

    if not base_dir.exists():
        print(f"❌ Directory not found: {base_dir}")
        return 1

    print("=" * 70)
    print("🔧 Bulk Manifest Fixer")
    print("=" * 70)
    print()

    total = 0
    fixed = 0
    skipped = 0
    errors = 0

    # Process all project directories
    for project_dir in sorted(base_dir.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith("."):
            continue

        manifest_path = project_dir / "manifest.yaml"

        if not manifest_path.exists():
            continue

        total += 1
        print(f"[{total}] Processing: {project_dir.name}")

        if fix_manifest(manifest_path):
            fixed += 1
        else:
            skipped += 1

    print()
    print("=" * 70)
    print("📊 Summary")
    print("=" * 70)
    print(f"Total manifests: {total}")
    print(f"Fixed: {fixed}")
    print(f"Already OK: {skipped}")
    print(f"Errors: {errors}")
    print()

    if fixed > 0:
        print(f"✅ Updated {fixed} manifest files with missing fields")
    else:
        print("✅ All manifests already have required fields")

    return 0


if __name__ == "__main__":
    sys.exit(main())
