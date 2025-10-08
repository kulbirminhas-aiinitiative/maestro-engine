#!/usr/bin/env python3
"""
Find unused Python files (not imported anywhere).

This script analyzes Python files to detect modules that are never imported
by other modules, which may indicate dead code that can be safely removed.

Part of ADR-007: Code Organization and Cleanup Policy

Usage:
    python scripts/find_unused_files.py                # Report mode
    python scripts/find_unused_files.py --verbose      # Show import graph
    python scripts/find_unused_files.py --exclude-tests # Exclude test files
"""

import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set


class UnusedFileFinder:
    """Find Python files that are never imported."""

    def __init__(
        self, root_dir: str = "src", exclude_patterns: List[str] = None, exclude_tests: bool = False
    ):
        self.root_dir = Path(root_dir)
        self.exclude_patterns = exclude_patterns or ["_legacy", "_experiments", "archived"]
        self.exclude_tests = exclude_tests

        self.all_files: List[Path] = []
        self.imports: Dict[Path, Set[str]] = defaultdict(set)
        self.module_to_file: Dict[str, Path] = {}

    def should_skip_path(self, path: Path) -> bool:
        """Check if path should be skipped."""
        path_str = str(path)

        # Skip excluded patterns
        if any(pattern in path_str for pattern in self.exclude_patterns):
            return True

        # Skip test files if requested
        if self.exclude_tests and ("test_" in path_str or "/tests/" in path_str):
            return True

        # Always skip __init__.py and __main__.py
        if path.name in ("__init__.py", "__main__.py"):
            return True

        return False

    def find_python_files(self) -> List[Path]:
        """Find all Python files in root directory."""
        files = []
        for py_file in self.root_dir.rglob("*.py"):
            if not self.should_skip_path(py_file):
                files.append(py_file)
        return files

    def extract_imports(self, file_path: Path) -> Set[str]:
        """Extract import statements from a Python file."""
        imports = set()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Match: import module
            for match in re.finditer(r"^\s*import\s+([\w.]+)", content, re.MULTILINE):
                module = match.group(1).split(".")[0]  # Get root module
                imports.add(module)

            # Match: from module import ...
            for match in re.finditer(r"^\s*from\s+([\w.]+)\s+import", content, re.MULTILINE):
                module = match.group(1).split(".")[0]  # Get root module
                imports.add(module)

        except Exception as e:
            print(f"⚠️  Error reading {file_path}: {e}", file=sys.stderr)

        return imports

    def path_to_module(self, file_path: Path) -> str:
        """Convert file path to module name."""
        # Get relative path from root_dir
        try:
            rel_path = file_path.relative_to(self.root_dir)
        except ValueError:
            rel_path = file_path

        # Convert path to module name
        module = str(rel_path).replace("/", ".").replace("\\", ".")

        # Remove .py extension
        if module.endswith(".py"):
            module = module[:-3]

        return module

    def build_module_map(self) -> None:
        """Build mapping of module names to file paths."""
        for file_path in self.all_files:
            module = self.path_to_module(file_path)

            # Store both full module path and variations
            self.module_to_file[module] = file_path

            # Also store each component (for partial imports)
            parts = module.split(".")
            for i in range(len(parts)):
                partial = ".".join(parts[: i + 1])
                self.module_to_file[partial] = file_path

    def find_unused_files(self) -> List[Path]:
        """Find files that are never imported."""
        # Collect all imports across all files
        all_imports = set()
        for file_path in self.all_files:
            imports = self.extract_imports(file_path)
            self.imports[file_path] = imports
            all_imports.update(imports)

        # Find files that are never imported
        unused = []
        for file_path in self.all_files:
            module = self.path_to_module(file_path)

            # Check if this module or any of its components are imported
            is_imported = False
            parts = module.split(".")

            for i in range(len(parts)):
                partial = ".".join(parts[: i + 1])
                if partial in all_imports:
                    is_imported = True
                    break

            # Also check the base name
            base_name = parts[-1] if parts else module
            if base_name in all_imports:
                is_imported = True

            if not is_imported:
                unused.append(file_path)

        return unused

    def print_report(self, unused: List[Path]) -> None:
        """Print formatted report of unused files."""
        if not unused:
            print("✅ No unused files found!")
            return

        print(f"\n🗑️  Found {len(unused)} unused file(s):\n")

        # Group by directory
        by_dir = defaultdict(list)
        for file_path in unused:
            dir_path = file_path.parent
            by_dir[dir_path].append(file_path.name)

        for dir_path in sorted(by_dir.keys()):
            print(f"📁 {dir_path}/")
            for filename in sorted(by_dir[dir_path]):
                print(f"   - {filename}")
            print()

        print("💡 Recommendations:")
        print("   1. Review files to confirm they're truly unused")
        print("   2. Check if files are entry points (scripts, CLI tools)")
        print("   3. Move to _legacy/ if keeping for reference")
        print("   4. Delete if confirmed unused")
        print()

    def print_import_graph(self) -> None:
        """Print import relationships (verbose mode)."""
        print("\n📊 Import Graph:\n")

        for file_path in sorted(self.all_files):
            imports = self.imports.get(file_path, set())
            if imports:
                print(f"📄 {file_path.name}")
                for imp in sorted(imports):
                    print(f"   ↳ {imp}")
                print()

    def run(self, verbose: bool = False) -> int:
        """Run unused file detection."""
        print(f"🔍 Finding unused Python files in {self.root_dir}/")
        print(f"   Excluding: {', '.join(self.exclude_patterns)}")
        if self.exclude_tests:
            print("   Excluding: test files")
        print()

        # Find all Python files
        self.all_files = self.find_python_files()
        print(f"📊 Found {len(self.all_files)} Python files to analyze")

        # Build module mapping
        self.build_module_map()

        # Find unused files
        unused = self.find_unused_files()

        # Print report
        self.print_report(unused)

        # Print import graph if verbose
        if verbose:
            self.print_import_graph()

        # Return count of unused files
        return len(unused)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Find unused Python files (not imported anywhere)")
    parser.add_argument(
        "--root", type=str, default="src", help="Root directory to scan (default: src)"
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="+",
        default=["_legacy", "_experiments", "archived"],
        help="Patterns to exclude (default: _legacy _experiments archived)",
    )
    parser.add_argument(
        "--exclude-tests", action="store_true", help="Exclude test files from analysis"
    )
    parser.add_argument("--verbose", action="store_true", help="Show import graph")

    args = parser.parse_args()

    finder = UnusedFileFinder(
        root_dir=args.root, exclude_patterns=args.exclude, exclude_tests=args.exclude_tests
    )

    unused_count = finder.run(verbose=args.verbose)

    # Exit code is count of unused files (0 = none found)
    sys.exit(min(unused_count, 255))  # Cap at 255 for exit codes


if __name__ == "__main__":
    main()
