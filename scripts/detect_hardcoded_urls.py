#!/usr/bin/env python3
"""
Detect hardcoded service URLs in the codebase.

This script scans Python files for hardcoded localhost URLs and service endpoints
that should be externalized to environment variables or configuration files.

Usage:
    python scripts/detect_hardcoded_urls.py              # Report mode
    python scripts/detect_hardcoded_urls.py --strict     # Exit 1 if any found
    python scripts/detect_hardcoded_urls.py --fix        # Auto-fix (future)

Part of ADR-001: Service Discovery and Dynamic Configuration
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class HardcodedURLDetector:
    """Detect hardcoded URLs in Python source files."""

    # Patterns to detect hardcoded URLs
    URL_PATTERNS = [
        # localhost with port
        r'["\']https?://localhost:\d+["\']',
        # localhost without port
        r'["\']https?://localhost[/"\']',
        # 127.0.0.1 with port
        r'["\']https?://127\.0\.0\.1:\d+["\']',
        # Common service hosts (should use env vars)
        r'["\']https?://[a-z-]+:\d+["\']',
        # Direct port references in URLs
        r'["\']https?://[^"\']+:\d{4,5}["\']',
    ]

    # Exclude patterns (legitimate uses)
    EXCLUDE_PATTERNS = [
        r"# Example:",
        r"# URL:",
        r'"""',
        r"'''",
        r"# Sample",
        r"# Test",
        r"http://example\.com",
        r"https://example\.com",
        r"http://api\.example",
    ]

    # Files/directories to skip
    SKIP_PATHS = [
        "_legacy",
        "_experiments",
        "archived",
        "__pycache__",
        ".venv",
        "venv",
        "tests",  # Allow hardcoded URLs in tests
        "docs",  # Allow in documentation
    ]

    def __init__(self, strict: bool = False):
        self.strict = strict
        self.violations: List[Dict] = []

    def should_skip_path(self, path: Path) -> bool:
        """Check if path should be skipped."""
        path_str = str(path)
        return any(skip in path_str for skip in self.SKIP_PATHS)

    def is_excluded_line(self, line: str) -> bool:
        """Check if line should be excluded (comment, docstring, etc)."""
        return any(re.search(pattern, line) for pattern in self.EXCLUDE_PATTERNS)

    def detect_in_file(self, file_path: Path) -> List[Dict]:
        """Detect hardcoded URLs in a single file."""
        violations = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    # Skip excluded lines
                    if self.is_excluded_line(line):
                        continue

                    # Check each pattern
                    for pattern in self.URL_PATTERNS:
                        if match := re.search(pattern, line):
                            violations.append(
                                {
                                    "file": str(file_path),
                                    "line": line_num,
                                    "content": line.strip(),
                                    "match": match.group(),
                                    "pattern": pattern,
                                }
                            )

        except Exception as e:
            print(f"⚠️  Error reading {file_path}: {e}", file=sys.stderr)

        return violations

    def scan_directory(self, root_dir: Path = Path("src")) -> List[Dict]:
        """Scan directory recursively for hardcoded URLs."""
        all_violations = []

        # Find all Python files
        for py_file in root_dir.rglob("*.py"):
            if self.should_skip_path(py_file):
                continue

            violations = self.detect_in_file(py_file)
            all_violations.extend(violations)

        return all_violations

    def print_report(self, violations: List[Dict]) -> None:
        """Print formatted report of violations."""
        if not violations:
            print("✅ No hardcoded service URLs found!")
            return

        print(f"\n❌ Found {len(violations)} hardcoded URL(s):\n")

        # Group by file
        by_file: Dict[str, List[Dict]] = {}
        for v in violations:
            by_file.setdefault(v["file"], []).append(v)

        for file_path, file_violations in sorted(by_file.items()):
            print(f"📄 {file_path}")
            for v in file_violations:
                print(f"   Line {v['line']:4d}: {v['match']}")
                print(f"            {v['content'][:80]}")
            print()

        print("\n💡 Remediation:")
        print("   1. Replace hardcoded URLs with environment variables")
        print("   2. Use dynaconf settings: settings.SERVICE_NAME_URL")
        print("   3. Update config/services.yaml with service definitions")
        print("\n   Example:")
        print('   ❌ url = "http://localhost:9600/api"')
        print("   ✅ url = settings.TEMPLATE_SERVICE_URL")
        print()

    def run(self) -> int:
        """Run detection and return exit code."""
        print("🔍 Scanning for hardcoded service URLs...")
        print(f"   Scope: src/ (excluding {', '.join(self.SKIP_PATHS)})\n")

        violations = self.scan_directory()
        self.violations = violations

        self.print_report(violations)

        if violations and self.strict:
            print("⛔ FAIL: Hardcoded URLs detected (strict mode)")
            return 1

        return 0


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Detect hardcoded service URLs in source code")
    parser.add_argument(
        "--strict", action="store_true", help="Exit with code 1 if any hardcoded URLs are found"
    )
    parser.add_argument(
        "--path", type=Path, default=Path("src"), help="Path to scan (default: src/)"
    )

    args = parser.parse_args()

    detector = HardcodedURLDetector(strict=args.strict)
    exit_code = detector.run()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
