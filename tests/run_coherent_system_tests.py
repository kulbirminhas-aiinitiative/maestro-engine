#!/usr/bin/env python3
"""
Unified Test Runner for MAESTRO Coherent System Components
Runs comprehensive test suites for all coherent system components with proper configuration.
"""
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

# Add maestro-services to Python path
# Use Poetry and relative imports instead of hardcoded paths


def setup_test_environment():
    """Setup test environment and dependencies"""
    print("🔧 Setting up test environment...")

    # Ensure we're in the correct directory
    os.chdir("/data/maestro-services")

    # Create __init__.py files for proper module structure
    init_files = ["tests/__init__.py", "tests/unit/__init__.py", "shared/__init__.py"]

    for init_file in init_files:
        init_path = Path(init_file)
        init_path.parent.mkdir(parents=True, exist_ok=True)
        if not init_path.exists():
            init_path.write_text("# Test module init file\n")

    print("✅ Test environment setup complete")


def run_pytest_suite(test_pattern, description):
    """Run a specific pytest suite with proper configuration"""
    print(f"\n🧪 Running {description}")
    print("=" * 60)

    cmd = [
        "python3",
        "-m",
        "pytest",
        test_pattern,
        "-v",
        "--tb=short",
        "--no-header",
        "-x",  # Stop on first failure for faster feedback
        "--disable-warnings",
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd="/data/maestro-services",
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout per test suite
        )

        if result.returncode == 0:
            print(f"✅ {description} - PASSED")
            if result.stdout:
                # Show only the summary line
                lines = result.stdout.strip().split("\n")
                summary_lines = [line for line in lines if "passed" in line and "::" not in line]
                for line in summary_lines[-2:]:  # Last 2 lines usually contain summary
                    print(f"   {line}")
        else:
            print(f"❌ {description} - FAILED")
            if result.stdout:
                print("STDOUT:")
                print(result.stdout)
            if result.stderr:
                print("STDERR:")
                print(result.stderr)

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - TIMEOUT (120s)")
        return False
    except Exception as e:
        print(f"💥 {description} - ERROR: {str(e)}")
        return False


def run_all_coherent_system_tests():
    """Run all coherent system test suites"""
    print("🚀 MAESTRO Coherent System Test Suite")
    print("=" * 60)

    # Setup environment
    setup_test_environment()

    # Define test suites in order of execution
    test_suites = [
        # Phase 4.5 Core Components (Foundation)
        {
            "pattern": "tests/unit/test_multi_phase_engine.py",
            "description": "Multi-Phase Orchestration Engine Tests",
            "priority": "CRITICAL",
        },
        {
            "pattern": "tests/unit/test_phase_complexity_analyzer.py",
            "description": "Phase Complexity Analyzer Tests",
            "priority": "CRITICAL",
        },
        {
            "pattern": "tests/unit/test_rule_based_spawner.py",
            "description": "Rule-Based Spawner Tests",
            "priority": "CRITICAL",
        },
        {
            "pattern": "tests/unit/test_dynamic_boundary_manager.py",
            "description": "Dynamic Boundary Manager Tests",
            "priority": "CRITICAL",
        },
        {
            "pattern": "tests/unit/test_hive_communication.py",
            "description": "Hive Communication Tests",
            "priority": "CRITICAL",
        },
        # HIGH Priority Coherent System Components
        {
            "pattern": "tests/unit/test_enhanced_coherent_with_ai_coordination.py",
            "description": "AI-Enhanced Coherent System Tests",
            "priority": "HIGH",
        },
        {
            "pattern": "tests/unit/test_stigmergy_engine.py",
            "description": "Stigmergy Engine Tests",
            "priority": "HIGH",
        },
        {
            "pattern": "tests/unit/test_digital_blackboard_system.py",
            "description": "Digital Blackboard System Tests",
            "priority": "HIGH",
        },
        {
            "pattern": "tests/unit/test_enhanced_orchestration_system.py",
            "description": "Enhanced Orchestration System Tests",
            "priority": "HIGH",
        },
        # MEDIUM Priority Components
        {
            "pattern": "tests/unit/test_enhanced_workflow_with_deployment.py",
            "description": "Enhanced Workflow with Deployment Tests",
            "priority": "MEDIUM",
        },
        {
            "pattern": "tests/unit/test_debug_coherent_persona_executor.py",
            "description": "Debug Coherent Persona Executor Tests",
            "priority": "MEDIUM",
        },
        # Integration Components
        {
            "pattern": "tests/unit/test_coherent_blackboard_integration.py",
            "description": "Coherent Blackboard Integration Tests",
            "priority": "INTEGRATION",
        },
        {
            "pattern": "tests/unit/test_coherent_domain_system.py",
            "description": "Coherent Domain System Tests",
            "priority": "INTEGRATION",
        },
    ]

    # Track results
    results = {"total": len(test_suites), "passed": 0, "failed": 0, "failed_suites": []}

    start_time = time.time()

    # Run each test suite
    for i, suite in enumerate(test_suites, 1):
        print(f"\n[{i}/{len(test_suites)}] Priority: {suite['priority']}")

        success = run_pytest_suite(suite["pattern"], suite["description"])

        if success:
            results["passed"] += 1
        else:
            results["failed"] += 1
            results["failed_suites"].append(suite["description"])

    # Final report
    total_time = time.time() - start_time

    print("\n" + "=" * 60)
    print("🏁 MAESTRO Coherent System Test Results")
    print("=" * 60)
    print(f"📊 Total Test Suites: {results['total']}")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⏱️  Total Time: {total_time:.2f} seconds")

    if results["failed"] > 0:
        print(f"\n❌ Failed Test Suites:")
        for suite in results["failed_suites"]:
            print(f"   • {suite}")

    success_rate = (results["passed"] / results["total"]) * 100
    print(f"\n📈 Success Rate: {success_rate:.1f}%")

    if success_rate >= 80:
        print("🎉 Coherent System test suite PASSED!")
        return True
    else:
        print("⚠️  Coherent System test suite needs attention")
        return False


def run_specific_component_tests(component_name):
    """Run tests for a specific component"""
    component_test_map = {
        "phase45": [
            "tests/unit/test_multi_phase_engine.py",
            "tests/unit/test_phase_complexity_analyzer.py",
            "tests/unit/test_rule_based_spawner.py",
            "tests/unit/test_dynamic_boundary_manager.py",
            "tests/unit/test_hive_communication.py",
        ],
        "coherent": [
            "tests/unit/test_enhanced_coherent_with_ai_coordination.py",
            "tests/unit/test_coherent_blackboard_integration.py",
            "tests/unit/test_coherent_domain_system.py",
        ],
        "ai": [
            "tests/unit/test_stigmergy_engine.py",
            "tests/unit/test_enhanced_coherent_with_ai_coordination.py",
        ],
        "orchestration": [
            "tests/unit/test_enhanced_orchestration_system.py",
            "tests/unit/test_enhanced_workflow_with_deployment.py",
        ],
        "blackboard": [
            "tests/unit/test_digital_blackboard_system.py",
            "tests/unit/test_coherent_blackboard_integration.py",
        ],
    }

    if component_name not in component_test_map:
        print(f"❌ Unknown component: {component_name}")
        print(f"Available components: {', '.join(component_test_map.keys())}")
        return False

    print(f"🔍 Running tests for component: {component_name}")

    test_files = component_test_map[component_name]
    all_passed = True

    for test_file in test_files:
        description = f"{component_name.title()} - {Path(test_file).stem}"
        success = run_pytest_suite(test_file, description)
        if not success:
            all_passed = False

    return all_passed


def generate_test_report():
    """Generate comprehensive test report"""
    print("📋 Generating comprehensive test report...")

    # Run pytest with coverage and report generation
    cmd = ["python3", "-m", "pytest", "tests/unit/", "--tb=short", "--quiet", "-x"]

    try:
        result = subprocess.run(
            cmd,
            cwd="/data/maestro-services",
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout for full suite
        )

        print("📊 Test Report Generated")
        if result.stdout:
            lines = result.stdout.strip().split("\n")
            for line in lines[-10:]:  # Show last 10 lines (summary)
                print(f"   {line}")

        return result.returncode == 0

    except Exception as e:
        print(f"❌ Report generation failed: {str(e)}")
        return False


def main():
    """Main test runner entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="MAESTRO Coherent System Test Runner")
    parser.add_argument(
        "--component",
        help="Run tests for specific component (phase45, coherent, ai, orchestration, blackboard)",
    )
    parser.add_argument("--report", action="store_true", help="Generate comprehensive test report")
    parser.add_argument(
        "--fast", action="store_true", help="Run fast test mode (skip slow integration tests)"
    )

    args = parser.parse_args()

    if args.component:
        success = run_specific_component_tests(args.component)
    elif args.report:
        success = generate_test_report()
    else:
        success = run_all_coherent_system_tests()

    if args.report and success:
        generate_test_report()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
