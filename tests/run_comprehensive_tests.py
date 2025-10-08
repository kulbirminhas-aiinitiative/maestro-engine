#!/usr/bin/env python3
"""
MAESTRO Comprehensive Test Runner
Runs all test suites including unit, integration, performance, and regression tests
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

# Use Poetry and relative imports instead of hardcoded paths


def run_test_suite(test_path, suite_name, timeout=120):
    """Run a specific test suite with timeout"""
    print(f"\n🧪 Running {suite_name}")
    print("=" * 60)

    try:
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short", "--no-header"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/data/maestro-services",
        )

        end_time = time.time()
        duration = end_time - start_time

        if result.returncode == 0:
            print(f"✅ {suite_name} - PASSED ({duration:.2f}s)")
            return {"status": "PASSED", "duration": duration, "output": result.stdout}
        else:
            print(f"❌ {suite_name} - FAILED ({duration:.2f}s)")
            print(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                print(f"STDERR:\n{result.stderr}")
            return {
                "status": "FAILED",
                "duration": duration,
                "output": result.stdout,
                "error": result.stderr,
            }

    except subprocess.TimeoutExpired:
        print(f"⏰ {suite_name} - TIMEOUT ({timeout}s)")
        return {"status": "TIMEOUT", "duration": timeout, "output": "", "error": "Test timed out"}
    except Exception as e:
        print(f"💥 {suite_name} - ERROR: {e}")
        return {"status": "ERROR", "duration": 0, "output": "", "error": str(e)}


def main():
    """Main test runner"""
    print("🚀 MAESTRO Comprehensive Test Suite")
    print("=" * 80)
    print("Running all test categories: Unit, Integration, Performance, Regression")
    print()

    # Test suites to run
    test_suites = [
        # Configuration and System Tests (New)
        ("tests/integration/test_configuration_system.py", "Configuration Integration Tests"),
        ("tests/integration/test_import_system.py", "Import System Tests"),
        ("tests/performance/test_coherent_system_performance.py", "Performance Tests"),
        ("tests/regression/test_configuration_regression.py", "Configuration Regression Tests"),
        # Original Unit Tests (Selected Key Ones)
        ("tests/unit/test_multi_phase_engine.py", "Multi-Phase Engine Unit Tests"),
        ("tests/unit/test_phase_complexity_analyzer.py", "Complexity Analyzer Unit Tests"),
        ("tests/unit/test_rule_based_spawner.py", "Rule-Based Spawner Unit Tests"),
        ("tests/unit/test_coherent_domain_system.py", "Coherent Domain System Unit Tests"),
    ]

    results = {}
    total_start_time = time.time()

    # Run each test suite
    for test_path, suite_name in test_suites:
        full_path = Path("/data/maestro-services") / test_path
        if full_path.exists():
            result = run_test_suite(full_path, suite_name)
            results[suite_name] = result
        else:
            print(f"⚠️  {suite_name} - SKIPPED (file not found: {test_path})")
            results[suite_name] = {
                "status": "SKIPPED",
                "duration": 0,
                "output": "",
                "error": "File not found",
            }

    total_end_time = time.time()
    total_duration = total_end_time - total_start_time

    # Summary
    print("\n" + "=" * 80)
    print("🏁 MAESTRO Comprehensive Test Results")
    print("=" * 80)

    passed = sum(1 for r in results.values() if r["status"] == "PASSED")
    failed = sum(1 for r in results.values() if r["status"] == "FAILED")
    errors = sum(1 for r in results.values() if r["status"] in ["ERROR", "TIMEOUT"])
    skipped = sum(1 for r in results.values() if r["status"] == "SKIPPED")

    print(f"📊 Total Test Suites: {len(results)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"💥 Errors/Timeouts: {errors}")
    print(f"⏭️  Skipped: {skipped}")
    print(f"⏱️  Total Time: {total_duration:.2f} seconds")

    # Detailed results
    if failed > 0 or errors > 0:
        print(f"\n❌ Failed/Error Test Suites:")
        for suite_name, result in results.items():
            if result["status"] in ["FAILED", "ERROR", "TIMEOUT"]:
                print(f"   • {suite_name}: {result['status']}")
                if result.get("error"):
                    print(f"     Error: {result['error'][:200]}...")

    if passed > 0:
        print(f"\n✅ Passed Test Suites:")
        for suite_name, result in results.items():
            if result["status"] == "PASSED":
                print(f"   • {suite_name} ({result['duration']:.2f}s)")

    # Success rate
    total_tests = len(results) - skipped
    if total_tests > 0:
        success_rate = (passed / total_tests) * 100
        print(f"\n📈 Success Rate: {success_rate:.1f}%")

        if success_rate >= 80:
            print("🎉 Excellent test coverage!")
        elif success_rate >= 60:
            print("👍 Good test coverage")
        else:
            print("⚠️  Test suite needs attention")

    # Configuration verification
    print(f"\n🔧 Configuration System Status:")
    try:
        from maestro_config import get_config

        config = get_config()
        print(f"   ✅ Configuration loads successfully")
        print(f"   ✅ Orchestration Port: {config.orchestration_gateway.port}")
        print(f"   ✅ Intelligence Port: {config.intelligence_service.port}")
    except Exception as e:
        print(f"   ❌ Configuration error: {e}")

    # Return appropriate exit code
    if failed > 0 or errors > 0:
        return 1
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
