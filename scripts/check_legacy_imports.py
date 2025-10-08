#!/usr/bin/env python3
"""
Check for imports from _legacy or _experiments directories.

Production code (src/) should never import from _legacy/ or _experiments/
directories, as these contain archived or experimental code.

Part of ADR-007: Code Organization and Cleanup Policy

Usage:
    python scripts/check_legacy_imports.py                    # Check all src/
    python scripts/check_legacy_imports.py file1.py file2.py  # Check specific files
    python scripts/check_legacy_imports.py --strict           # Exit 1 if any found

This script is designed to be used as a pre-commit hook.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class LegacyImportChecker:
    """Check for imports from legacy or experimental code."""

    # Patterns to detect legacy/experimental imports
    FORBIDDEN_PATTERNS = [
        (r"from\s+_legacy", "_legacy"),
        (r"import\s+_legacy", "_legacy"),
        (r"from\s+_experiments", "_experiments"),
        (r"import\s+_experiments", "_experiments"),
        (r"from\s+archived", "archived"),
        (r"import\s+archived", "archived"),
        (r"from\s+src\.archived", "src.archived"),
        (r"import\s+src\.archived", "src.archived"),
    ]

    def __init__(self, strict: bool = False):
        self.strict = strict
        self.violations: List[Dict] = []

    def check_file(self, file_path: Path) -> List[Tuple[int, str, str]]:
        """
        Check a single file for legacy imports.

        Returns:
            List of (line_number, line_content, forbidden_pattern) tuples
        """
        violations = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    # Skip comments and docstrings
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if stripped.startswith('"""') or stripped.startswith("'''"):
                        continue

                    # Check each forbidden pattern
                    for pattern, name in self.FORBIDDEN_PATTERNS:
                        if re.search(pattern, line):
                            violations.append((line_num, line.strip(), name))

        except Exception as e:
            print(f"⚠️  Error reading {file_path}: {e}", file=sys.stderr)

        return violations

    def check_files(self, file_paths: List[Path]) -> Dict[Path, List]:
        """Check multiple files for legacy imports."""
        all_violations = {}

        for file_path in file_paths:
            violations = self.check_file(file_path)
            if violations:
                all_violations[file_path] = violations

        return all_violations

    def find_python_files(self, root_dir: Path = Path("src")) -> List[Path]:
        """Find all Python files in directory (excluding legacy/experiments)."""
        files = []

        for py_file in root_dir.rglob("*.py"):
            # Skip _legacy and _experiments directories
            path_str = str(py_file)
            if "_legacy" in path_str or "_experiments" in path_str or "archived" in path_str:
                continue

            files.append(py_file)

        return files

    def print_report(self, violations: Dict[Path, List]) -> None:
        """Print formatted report of violations."""
        if not violations:
            print("✅ No legacy/experimental imports found in production code!")
            return

        total = sum(len(v) for v in violations.values())
        print(f"\n❌ Found {total} legacy/experimental import(s) in {len(violations)} file(s):\n")

        for file_path, file_violations in sorted(violations.items()):
            print(f"📄 {file_path}")
            for line_num, content, pattern in file_violations:
                print(f"   Line {line_num:4d}: {content[:80]}")
                print(f"            ↳ Imports from: {pattern}")
            print()

        print("⛔ POLICY VIOLATION:")
        print("   Production code (src/) cannot import from:")
        print("   - _legacy/       (archived code)")
        print("   - _experiments/  (experimental code)")
        print("   - archived/      (old archived code)")
        print()
        print("💡 Remediation:")
        print("   1. Move required code from _legacy/_experiments to src/")
        print("   2. Or refactor to remove the dependency")
        print("   3. Update imports to use production code paths")
        print()

    def run(self, files: List[Path] = None) -> int:
        """Run legacy import checks."""
        if files:
            # Check specific files (pre-commit mode)
            print(f"🔍 Checking {len(files)} file(s) for legacy imports...")
            violations = self.check_files(files)
        else:
            # Check all src/ files
            print("🔍 Checking all src/ files for legacy imports...")
            python_files = self.find_python_files()
            print(f"   Found {len(python_files)} Python files\n")
            violations = self.check_files(python_files)

        self.violations = violations
        self.print_report(violations)

        if violations:
            return 1 if self.strict else 1  # Always return 1 if violations found

        return 0


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Check for imports from _legacy or _experiments directories"
    )
    parser.add_argument(
        "files", nargs="*", type=Path, help="Specific files to check (default: all src/ files)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if any violations found (always enabled)",
    )

    args = parser.parse_args()

    checker = LegacyImportChecker(strict=True)  # Always strict
    exit_code = checker.run(files=args.files if args.files else None)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
