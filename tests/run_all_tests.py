#!/usr/bin/env python3
"""
Comprehensive Test Runner for DAG Workflow System

Runs all test suites and generates a summary report:
1. Unit tests (DAGCatalogService)
2. Integration tests (WorkflowSuggestionEngine)
3. E2E tests (Workflow Execution)
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime


def print_banner(text: str):
    """Print a formatted banner"""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")


def run_test_suite(test_file: Path, suite_name: str) -> bool:
    """
    Run a test suite and return success status.

    Args:
        test_file: Path to test file
        suite_name: Name of the test suite

    Returns:
        True if all tests passed, False otherwise
    """
    print_banner(f"Running {suite_name}")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short"],
            cwd=test_file.parent.parent.parent,
            capture_output=False,
            text=True
        )

        success = result.returncode == 0

        if success:
            print(f"\n✅ {suite_name} PASSED\n")
        else:
            print(f"\n❌ {suite_name} FAILED\n")

        return success

    except Exception as e:
        print(f"\n❌ Error running {suite_name}: {e}\n")
        return False


def main():
    """Run all test suites and generate report"""
    print_banner("DAG Workflow System - Comprehensive Test Suite")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Define test suites
    tests_dir = Path(__file__).parent
    test_suites = [
        (tests_dir / "unit" / "test_dag_catalog_service.py", "Unit Tests - DAG Catalog Service"),
        (tests_dir / "integration" / "test_workflow_suggestions.py", "Integration Tests - Workflow Suggestions"),
        (tests_dir / "e2e" / "test_workflow_execution.py", "E2E Tests - Workflow Execution"),
    ]

    results = {}

    # Run each test suite
    for test_file, suite_name in test_suites:
        if not test_file.exists():
            print(f"⚠️  Test file not found: {test_file}")
            results[suite_name] = False
            continue

        results[suite_name] = run_test_suite(test_file, suite_name)

    # Generate summary report
    print_banner("Test Summary Report")

    total = len(results)
    passed = sum(1 for success in results.values() if success)
    failed = total - passed

    print(f"Total Test Suites: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print()

    for suite_name, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"  {status}  {suite_name}")

    print()
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")

    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
