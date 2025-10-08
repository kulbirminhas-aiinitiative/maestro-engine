#!/usr/bin/env python3
"""
MAESTRO Phase 4.5 Unit Test Suite Runner
Comprehensive test runner for all Phase 4.5 autonomous orchestration components
"""
import asyncio
import sys
import time
from pathlib import Path

import pytest


class Phase45TestSuite:
    """Test suite runner for Phase 4.5 components"""

    def __init__(self):
        self.test_results = {}
        self.start_time = None
        self.end_time = None

    def run_all_phase45_tests(self, verbose=True, coverage=True):
        """Run all Phase 4.5 unit tests"""
        print("🚀 Starting MAESTRO Phase 4.5 Unit Test Suite")
        print("=" * 60)

        self.start_time = time.time()

        # Define test modules and their markers
        test_modules = {
            "Multi-Phase Orchestration Engine": {
                "path": "tests/unit/test_multi_phase_engine.py",
                "markers": ["unit", "phase45", "orchestration"],
                "critical": True,
            },
            "Phase-Aware Complexity Analyzer": {
                "path": "tests/unit/test_phase_complexity_analyzer.py",
                "markers": ["unit", "phase45", "complexity"],
                "critical": True,
            },
            "Rule-Based Autonomous Spawning": {
                "path": "tests/unit/test_rule_based_spawner.py",
                "markers": ["unit", "phase45", "autonomous"],
                "critical": True,
            },
            "Dynamic Boundary Manager": {
                "path": "tests/unit/test_dynamic_boundary_manager.py",
                "markers": ["unit", "phase45", "autonomous"],
                "critical": False,
            },
            "Cross-Hive Communication": {
                "path": "tests/unit/test_hive_communication.py",
                "markers": ["unit", "phase45", "communication"],
                "critical": True,
            },
        }

        # Run tests for each module
        for module_name, config in test_modules.items():
            print(f"\n📋 Testing: {module_name}")
            print("-" * 50)

            result = self._run_module_tests(config, verbose, coverage)
            self.test_results[module_name] = result

            # Print immediate results
            status = "✅ PASSED" if result["success"] else "❌ FAILED"
            print(f"Status: {status}")
            print(f"Tests: {result['passed']}/{result['total']} passed")
            if result["duration"]:
                print(f"Duration: {result['duration']:.2f}s")

        self.end_time = time.time()
        self._print_summary()

        return self._get_overall_success()

    def run_critical_tests_only(self):
        """Run only critical Phase 4.5 tests"""
        print("🎯 Running Critical Phase 4.5 Tests Only")
        print("=" * 50)

        critical_tests = [
            "tests/unit/test_multi_phase_engine.py::TestMultiPhaseOrchestrationEngine::test_orchestrate_single_phase_basic",
            "tests/unit/test_phase_complexity_analyzer.py::TestPhaseComplexityAnalyzer::test_analyze_phase_complexity_requirements",
            "tests/unit/test_rule_based_spawner.py::TestRuleBasedAutonomousSpawner::test_evaluate_spawn_conditions_basic",
            "tests/unit/test_hive_communication.py::TestHiveCommunicationSystem::test_send_direct_message",
        ]

        pytest_args = [
            "-v",
            "--tb=short",
            "-m",
            "phase45 and critical",
            "--disable-warnings",
        ] + critical_tests

        result = pytest.main(pytest_args)

        if result == 0:
            print("✅ All critical Phase 4.5 tests passed!")
        else:
            print("❌ Some critical Phase 4.5 tests failed!")

        return result == 0

    def run_smoke_tests(self):
        """Run quick smoke tests for Phase 4.5 components"""
        print("💨 Running Phase 4.5 Smoke Tests")
        print("=" * 40)

        smoke_tests = [
            "tests/unit/test_multi_phase_engine.py::TestMultiPhaseOrchestrationEngine::test_engine_initialization",
            "tests/unit/test_phase_complexity_analyzer.py::TestPhaseComplexityAnalyzer::test_analyzer_initialization",
            "tests/unit/test_rule_based_spawner.py::TestRuleBasedAutonomousSpawner::test_spawner_initialization",
            "tests/unit/test_dynamic_boundary_manager.py::TestDynamicBoundaryManager::test_boundary_manager_initialization",
            "tests/unit/test_hive_communication.py::TestHiveCommunicationSystem::test_communication_system_initialization",
        ]

        pytest_args = [
            "-v",
            "--tb=line",
            "--disable-warnings",
            "-x",  # Stop on first failure
        ] + smoke_tests

        result = pytest.main(pytest_args)

        if result == 0:
            print("✅ All Phase 4.5 smoke tests passed!")
        else:
            print("❌ Phase 4.5 smoke tests failed!")

        return result == 0

    def _run_module_tests(self, config, verbose=True, coverage=True):
        """Run tests for a specific module"""
        test_path = config["path"]

        if not Path(test_path).exists():
            return {
                "success": False,
                "passed": 0,
                "total": 0,
                "duration": 0,
                "error": f"Test file not found: {test_path}",
            }

        # Build pytest arguments
        pytest_args = [test_path]

        if verbose:
            pytest_args.extend(["-v", "--tb=short"])
        else:
            pytest_args.extend(["-q"])

        if coverage:
            pytest_args.extend(
                [
                    f"--cov={test_path.replace('tests/unit/test_', '').replace('.py', '')}",
                    "--cov-report=term-missing",
                ]
            )

        # Add markers
        if config.get("markers"):
            marker_expr = " and ".join(config["markers"])
            pytest_args.extend(["-m", marker_expr])

        pytest_args.extend(["--disable-warnings", "--tb=short"])

        # Capture start time
        start_time = time.time()

        # Run the tests
        try:
            result = pytest.main(pytest_args)
            duration = time.time() - start_time

            # Parse results (simplified)
            success = result == 0

            return {
                "success": success,
                "passed": "N/A",  # Would need pytest plugin to get exact counts
                "total": "N/A",
                "duration": duration,
                "exit_code": result,
            }

        except Exception as e:
            return {
                "success": False,
                "passed": 0,
                "total": 0,
                "duration": time.time() - start_time,
                "error": str(e),
            }

    def _print_summary(self):
        """Print test execution summary"""
        print("\n" + "=" * 60)
        print("📊 PHASE 4.5 TEST EXECUTION SUMMARY")
        print("=" * 60)

        total_duration = self.end_time - self.start_time if self.end_time and self.start_time else 0

        successful_modules = sum(1 for result in self.test_results.values() if result["success"])
        total_modules = len(self.test_results)

        print(f"📈 Overall Success Rate: {successful_modules}/{total_modules} modules passed")
        print(f"⏱️  Total Execution Time: {total_duration:.2f} seconds")
        print()

        # Module-by-module results
        for module_name, result in self.test_results.items():
            status = "✅" if result["success"] else "❌"
            print(f"{status} {module_name}")

            if "error" in result:
                print(f"   Error: {result['error']}")
            elif result["duration"]:
                print(f"   Duration: {result['duration']:.2f}s")

        print()

        # Overall status
        if self._get_overall_success():
            print("🎉 ALL PHASE 4.5 UNIT TESTS PASSED!")
            print("✅ Phase 4.5 components are ready for integration testing")
        else:
            print("⚠️  SOME PHASE 4.5 TESTS FAILED")
            print("❌ Phase 4.5 components need fixes before integration")

        print("=" * 60)

    def _get_overall_success(self):
        """Check if all tests passed"""
        return all(result["success"] for result in self.test_results.values())

    def run_performance_tests(self):
        """Run performance tests for Phase 4.5 components"""
        print("⚡ Running Phase 4.5 Performance Tests")
        print("=" * 45)

        performance_tests = [
            "tests/unit/test_multi_phase_engine.py::TestMultiPhaseOrchestrationEngine::test_concurrent_phase_orchestration",
            "tests/unit/test_rule_based_spawner.py::TestRuleBasedAutonomousSpawner::test_concurrent_spawn_evaluation",
            "tests/unit/test_dynamic_boundary_manager.py::TestDynamicBoundaryManager::test_concurrent_boundary_monitoring",
            "tests/unit/test_hive_communication.py::TestHiveCommunicationSystem::test_concurrent_message_handling",
        ]

        pytest_args = [
            "-v",
            "--tb=short",
            "-m",
            "phase45",
            "--disable-warnings",
        ] + performance_tests

        result = pytest.main(pytest_args)

        if result == 0:
            print("✅ All Phase 4.5 performance tests passed!")
        else:
            print("❌ Some Phase 4.5 performance tests failed!")

        return result == 0


def main():
    """Main test runner function"""
    suite = Phase45TestSuite()

    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()

        if test_type == "smoke":
            success = suite.run_smoke_tests()
        elif test_type == "critical":
            success = suite.run_critical_tests_only()
        elif test_type == "performance":
            success = suite.run_performance_tests()
        elif test_type == "all":
            success = suite.run_all_phase45_tests()
        else:
            print(f"Unknown test type: {test_type}")
            print("Available options: smoke, critical, performance, all")
            sys.exit(1)
    else:
        # Default to running all tests
        success = suite.run_all_phase45_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
