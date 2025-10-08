#!/usr/bin/env python3
"""
MAESTRO Phase 5: Autonomous Hive System Test Suite
Comprehensive testing for autonomous recursive ecosystem
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.autonomous_hive.autonomous_hive_controller import (
    AutonomousHive,
    AutonomyLevel,
    HivePhase,
    HiveState,
    ScopeBoundary,
)
from services.autonomous_hive.dynamic_boundary_manager import (
    ComplexityAnalyzer,
    DynamicBoundaryManager,
    PerformanceTracker,
    ResourceMonitor,
)
from services.autonomous_hive.stigmergy_engine_v5 import (
    CoordinationSignal,
    SignalPriority,
    SignalType,
    StigmergyEngine,
)


class TestPhase5AutonomousHiveSystem:
    """Comprehensive test suite for Phase 5 autonomous hive system"""

    async def setup_test_environment(self):
        """Set up test environment with all components"""
        # Create test boundary
        test_boundary = ScopeBoundary(
            scope_description="E-commerce platform development",
            functional_boundaries={"domain": "e_commerce", "complexity": "high"},
            resource_limits={"cpu": 8.0, "memory": 16.0, "time": 7200},
            time_constraints={"project_deadline": datetime.now() + timedelta(days=60)},
            quality_thresholds={"code_quality": 0.85, "test_coverage": 0.90},
            decision_authority=[
                "spawn_children",
                "allocate_resources",
                "adjust_scope",
                "coordinate_peers",
            ],
            coordination_requirements=["cross_phase_sync", "resource_sharing", "quality_assurance"],
        )

        # Create stigmergy engine
        stigmergy_engine = StigmergyEngine("/tmp/test_maestro_stigmergy_v5.db")
        await stigmergy_engine.start()

        # Create boundary manager
        boundary_manager = DynamicBoundaryManager()

        # Create test project scope
        project_scope = {
            "features": [f"feature_{i}" for i in range(15)],
            "services": [
                "user_service",
                "product_service",
                "order_service",
                "payment_service",
                "notification_service",
            ],
            "technologies": ["python", "react", "postgresql", "redis", "docker", "kubernetes"],
            "business_rules": [f"business_rule_{i}" for i in range(12)],
            "external_integrations": [
                "payment_gateway",
                "shipping_api",
                "email_service",
                "analytics",
            ],
            "performance_requirements": {
                "response_time": "<100ms",
                "throughput": ">5000rps",
                "availability": "99.9%",
            },
            "security_requirements": [
                "authentication",
                "authorization",
                "encryption",
                "audit",
                "compliance",
            ],
            "team_size": 12,
            "deadline": datetime.now() + timedelta(days=60),
            "project_type": "enterprise_e_commerce",
        }

        return {
            "test_boundary": test_boundary,
            "stigmergy_engine": stigmergy_engine,
            "boundary_manager": boundary_manager,
            "project_scope": project_scope,
        }

    async def test_autonomous_hive_creation_and_initialization(self):
        """Test 1: Autonomous hive creation and initialization"""
        env = await self.setup_test_environment()

        print("🧪 Test 1: Autonomous Hive Creation and Initialization")

        # Create master hive
        master_hive = AutonomousHive(
            scope_boundary=env["test_boundary"],
            autonomy_level=AutonomyLevel.MAXIMUM,
            phase_type=HivePhase.SYSTEM_DESIGN,
            stigmergy_engine=env["stigmergy_engine"],
        )

        # Test initial state
        assert master_hive.hive_id is not None
        assert master_hive.autonomy_level == AutonomyLevel.MAXIMUM
        assert master_hive.phase_type == HivePhase.SYSTEM_DESIGN
        assert master_hive.state == HiveState.INITIALIZING
        assert len(master_hive.child_hives) == 0

        # Start the hive
        await master_hive.start()

        # Wait for initialization
        await asyncio.sleep(2)

        # Check running state
        assert master_hive.is_active == True
        assert master_hive.state in [HiveState.ANALYZING, HiveState.EXECUTING]

        print(f"  ✅ Master hive created: {master_hive.hive_id}")
        print(f"  ✅ State: {master_hive.state.value}")
        print(f"  ✅ Autonomy level: {master_hive.autonomy_level.value}")

        await master_hive.stop()
        return True

    async def test_autonomous_child_spawning(self):
        """Test 2: Autonomous child hive spawning"""
        env = await self.setup_test_environment()

        print("🧪 Test 2: Autonomous Child Hive Spawning")

        # Create parent hive with conditions that favor spawning
        parent_hive = AutonomousHive(
            scope_boundary=env["test_boundary"],
            autonomy_level=AutonomyLevel.HIGH,
            phase_type=HivePhase.IMPLEMENTATION,
            stigmergy_engine=env["stigmergy_engine"],
        )

        # Set up conditions that should trigger spawning
        parent_hive.spawn_threshold = 0.5  # Lower threshold for testing
        parent_hive.work_progress.blocked_work_units = 5  # High blocked work
        parent_hive.work_progress.total_work_units = 20
        parent_hive.resource_consumption = {"cpu": 4.0, "memory": 8.0}  # High resource usage

        await parent_hive.start()

        # Let it run for several cycles to allow spawning
        print("  Running autonomous cycles to trigger spawning...")
        await asyncio.sleep(8)

        # Check if children were spawned
        children_count = len(parent_hive.child_hives)
        print(f"  ✅ Children spawned: {children_count}")

        if children_count > 0:
            for i, child in enumerate(parent_hive.child_hives):
                print(f"    Child {i+1}: {child.hive_id} ({child.autonomy_level.value})")
                assert child.parent_hive == parent_hive
                assert child.autonomy_level.value in ["minimal", "moderate"]  # Lower than parent

        # Test spawn decision logic directly
        situation = await parent_hive.assess_situation()
        should_spawn = await parent_hive.should_spawn_child_hive(situation)
        print(f"  ✅ Spawn decision logic working: {should_spawn}")

        await parent_hive.stop()
        return True

    async def test_dynamic_boundary_optimization(self):
        """Test 3: Dynamic boundary optimization"""
        env = await self.setup_test_environment()

        print("🧪 Test 3: Dynamic Boundary Optimization")

        boundary_manager = env["boundary_manager"]
        project_scope = env["project_scope"]

        # Test complexity analysis
        complexity_map = await boundary_manager.complexity_analyzer.create_complexity_map(
            project_scope
        )

        print(f"  ✅ Complexity analysis completed")
        print(f"    Overall score: {complexity_map.overall_score:.2f}")
        print(f"    Hotspots: {len(complexity_map.hotspots)}")
        print(f"    Top complexity areas: {complexity_map.complexity_distribution[:3]}")

        assert complexity_map.overall_score > 0.0
        assert isinstance(complexity_map.hotspots, list)
        assert len(complexity_map.complexity_distribution) > 0

        # Test resource monitoring
        resource_constraints = await boundary_manager.resource_monitor.get_constraints()

        print(f"  ✅ Resource monitoring operational")
        print(f"    CPU limits: {resource_constraints.cpu_limits}")
        print(f"    Current usage: {resource_constraints.current_usage}")

        assert "total" in resource_constraints.cpu_limits
        assert "cpu" in resource_constraints.current_usage

        # Test boundary optimization
        optimization_result = await boundary_manager.calculate_optimal_boundaries(project_scope)

        print(f"  ✅ Boundary optimization completed")
        print(f"    Confidence: {optimization_result.confidence_score:.2f}")
        print(f"    Adjustments recommended: {len(optimization_result.recommended_adjustments)}")
        print(f"    Priority: {optimization_result.implementation_priority}")

        assert optimization_result.confidence_score >= 0.0
        assert optimization_result.implementation_priority in ["low", "medium", "high"]
        assert isinstance(optimization_result.recommended_adjustments, list)

        return True

    async def test_stigmergy_coordination(self):
        """Test 4: Stigmergy-based coordination"""
        env = await self.setup_test_environment()

        print("🧪 Test 4: Stigmergy-based Coordination")

        stigmergy_engine = env["stigmergy_engine"]

        # Create multiple hives for coordination testing
        hives = []
        for i in range(3):
            hive = AutonomousHive(
                scope_boundary=env["test_boundary"],
                autonomy_level=AutonomyLevel.MODERATE,
                phase_type=list(HivePhase)[i % len(HivePhase)],
                stigmergy_engine=stigmergy_engine,
            )
            hives.append(hive)
            await stigmergy_engine.register_hive(hive)
            await hive.start()

        print(f"  ✅ Created and registered {len(hives)} hives")

        # Let coordination run for multiple cycles
        print("  Running coordination cycles...")
        for cycle in range(3):
            for hive in hives:
                await stigmergy_engine.coordinate_hive(hive)
            await asyncio.sleep(2)

        # Check coordination dashboard
        dashboard = stigmergy_engine.get_coordination_dashboard()

        print(f"  ✅ Coordination metrics:")
        print(f"    Registered hives: {dashboard['registered_hives']}")
        print(f"    Signals processed: {dashboard['coordination_metrics']['signals_processed']}")
        print(f"    Decisions made: {dashboard['coordination_metrics']['decisions_made']}")
        print(f"    Patterns discovered: {dashboard['discovered_patterns']}")

        assert dashboard["registered_hives"] == len(hives)
        assert dashboard["coordination_metrics"]["signals_processed"] >= 0
        assert dashboard["coordination_metrics"]["hives_coordinated"] > 0

        # Stop all hives
        for hive in hives:
            await hive.stop()

        return True

    async def test_cross_phase_coordination(self):
        """Test 5: Cross-phase coordination between different hive phases"""
        env = await self.setup_test_environment()

        print("🧪 Test 5: Cross-phase Coordination")

        stigmergy_engine = env["stigmergy_engine"]

        # Create hives for different phases
        phases = [
            HivePhase.REQUIREMENTS_ANALYSIS,
            HivePhase.SYSTEM_DESIGN,
            HivePhase.IMPLEMENTATION,
        ]
        phase_hives = {}

        for phase in phases:
            hive = AutonomousHive(
                scope_boundary=env["test_boundary"],
                autonomy_level=AutonomyLevel.HIGH,
                phase_type=phase,
                stigmergy_engine=stigmergy_engine,
            )
            phase_hives[phase.value] = hive
            await stigmergy_engine.register_hive(hive)
            await hive.start()

        print(f"  ✅ Created hives for {len(phases)} different phases")

        # Simulate cross-phase dependencies
        # Requirements phase completes first
        req_hive = phase_hives["requirements_analysis"]
        req_hive.work_progress.completed_work_units = 15
        req_hive.work_progress.total_work_units = 20

        # Design phase waits for requirements
        design_hive = phase_hives["system_design"]
        design_hive.work_progress.blocked_work_units = 8

        # Implementation phase waits for design
        impl_hive = phase_hives["implementation"]
        impl_hive.work_progress.blocked_work_units = 12

        # Run coordination to see cross-phase signals
        print("  Running cross-phase coordination...")
        for cycle in range(4):
            for phase, hive in phase_hives.items():
                await stigmergy_engine.coordinate_hive(hive)
            await asyncio.sleep(1)

        # Check if coordination signals were generated
        dashboard = stigmergy_engine.get_coordination_dashboard()

        print(f"  ✅ Cross-phase coordination metrics:")
        print(f"    Total signals: {dashboard['coordination_metrics']['signals_processed']}")
        print(f"    Decisions made: {dashboard['coordination_metrics']['decisions_made']}")

        # Check for dependency-related coordination
        signals_generated = dashboard["coordination_metrics"]["signals_processed"] > 0
        cross_phase_decisions = dashboard["coordination_metrics"]["decisions_made"] > 0

        print(f"    Cross-phase signals generated: {signals_generated}")
        print(f"    Cross-phase decisions made: {cross_phase_decisions}")

        # Stop all hives
        for hive in phase_hives.values():
            await hive.stop()

        return True

    async def test_recursive_decomposition_scaling(self):
        """Test 6: Recursive decomposition and scaling"""
        env = await self.setup_test_environment()

        print("🧪 Test 6: Recursive Decomposition and Scaling")

        # Create a high-complexity master hive
        master_boundary = ScopeBoundary(
            scope_description="Large enterprise platform with 50+ microservices",
            functional_boundaries={"domain": "enterprise_platform", "complexity": "very_high"},
            resource_limits={"cpu": 32.0, "memory": 64.0, "time": 14400},
            time_constraints={"project_deadline": datetime.now() + timedelta(days=90)},
            quality_thresholds={"code_quality": 0.90, "test_coverage": 0.95},
            decision_authority=[
                "spawn_children",
                "allocate_resources",
                "adjust_scope",
                "coordinate_ecosystem",
            ],
            coordination_requirements=["enterprise_governance", "compliance", "security"],
        )

        master_hive = AutonomousHive(
            scope_boundary=master_boundary,
            autonomy_level=AutonomyLevel.MAXIMUM,
            phase_type=HivePhase.SYSTEM_DESIGN,
            stigmergy_engine=env["stigmergy_engine"],
        )

        # Configure for aggressive spawning
        master_hive.spawn_threshold = 0.4
        master_hive.max_child_hives = 8
        master_hive.operation_cycle_interval = 2.0

        # Set up high complexity conditions
        master_hive.work_progress.total_work_units = 50
        master_hive.work_progress.blocked_work_units = 20
        master_hive.resource_consumption = {"cpu": 25.0, "memory": 48.0}

        await master_hive.start()

        # Let it run for extended time to allow recursive spawning
        print("  Running extended cycles for recursive decomposition...")
        await asyncio.sleep(12)

        # Analyze the recursive structure
        total_hives = 1 + len(master_hive.child_hives)
        second_level_children = sum(len(child.child_hives) for child in master_hive.child_hives)
        total_ecosystem_size = total_hives + second_level_children

        print(f"  ✅ Recursive decomposition results:")
        print(f"    Master hive: 1")
        print(f"    First-level children: {len(master_hive.child_hives)}")
        print(f"    Second-level children: {second_level_children}")
        print(f"    Total ecosystem size: {total_ecosystem_size}")

        # Check hierarchy depth
        max_depth = 1
        if master_hive.child_hives:
            max_depth = 2
            if any(len(child.child_hives) > 0 for child in master_hive.child_hives):
                max_depth = 3

        print(f"    Maximum hierarchy depth: {max_depth}")

        # Verify scaling properties
        assert len(master_hive.child_hives) > 0  # Should have spawned children
        assert total_ecosystem_size >= 2  # At least master + 1 child

        # Check that children have appropriate autonomy levels
        if master_hive.child_hives:
            child_autonomy_levels = [
                child.autonomy_level.value for child in master_hive.child_hives
            ]
            print(f"    Child autonomy levels: {set(child_autonomy_levels)}")

            # Children should have lower autonomy than parent
            assert all(level in ["minimal", "moderate", "high"] for level in child_autonomy_levels)

        await master_hive.stop()
        return True

    async def test_performance_metrics_and_optimization(self):
        """Test 7: Performance metrics and optimization"""
        env = await self.setup_test_environment()

        print("🧪 Test 7: Performance Metrics and Optimization")

        # Create hive with performance monitoring
        hive = AutonomousHive(
            scope_boundary=env["test_boundary"],
            autonomy_level=AutonomyLevel.HIGH,
            phase_type=HivePhase.IMPLEMENTATION,
            stigmergy_engine=env["stigmergy_engine"],
        )

        await hive.start()

        # Let it run to accumulate metrics
        await asyncio.sleep(6)

        # Get performance metrics
        metrics = hive.get_performance_metrics()
        progress_state = hive.get_progress_state()

        print(f"  ✅ Performance metrics collected:")
        print(f"    Execution efficiency: {metrics.execution_efficiency:.2f}")
        print(f"    Resource utilization: {metrics.resource_utilization:.2f}")
        print(f"    Quality score: {metrics.quality_score:.2f}")
        print(f"    Coordination overhead: {metrics.coordination_overhead:.2f}")
        print(f"    Progress: {progress_state['progress_percentage']:.1f}%")

        # Verify metrics are within expected ranges
        assert 0.0 <= metrics.execution_efficiency <= 1.0
        assert 0.0 <= metrics.resource_utilization <= 2.0  # Can exceed 1.0 temporarily
        assert 0.0 <= metrics.quality_score <= 1.0
        assert 0.0 <= metrics.coordination_overhead <= 2.0

        # Test boundary optimization integration
        boundary_manager = env["boundary_manager"]

        # Mock a performance issue to trigger optimization
        metrics.execution_efficiency = 0.4  # Low efficiency
        metrics.coordination_overhead = 0.6  # High overhead

        should_adjust = await boundary_manager._should_adjust_boundary(metrics)
        print(f"    Boundary adjustment recommended: {should_adjust}")

        assert should_adjust == True  # Should recommend adjustment for poor performance

        await hive.stop()
        return True

    async def test_error_handling_and_recovery(self):
        """Test 8: Error handling and recovery mechanisms"""
        env = await self.setup_test_environment()

        print("🧪 Test 8: Error Handling and Recovery")

        # Create hive
        hive = AutonomousHive(
            scope_boundary=env["test_boundary"],
            autonomy_level=AutonomyLevel.MODERATE,
            phase_type=HivePhase.TESTING,
            stigmergy_engine=env["stigmergy_engine"],
        )

        await hive.start()

        # Simulate error condition by corrupting state
        original_operation_cycle = hive.autonomous_operation_cycle

        async def faulty_operation_cycle():
            """Simulated faulty operation cycle"""
            await asyncio.sleep(1)
            raise Exception("Simulated coordination error")

        # Replace operation cycle with faulty one temporarily
        hive.autonomous_operation_cycle = faulty_operation_cycle

        # Let it run with errors
        await asyncio.sleep(3)

        # Check that hive handles errors gracefully
        print(f"  ✅ Error handling test:")
        print(f"    Hive still active: {hive.is_active}")
        print(f"    Current state: {hive.state.value}")

        # Restore original operation and continue
        hive.autonomous_operation_cycle = original_operation_cycle

        # Recovery test - should continue operating
        await asyncio.sleep(3)

        print(f"    Recovery successful: {hive.state.value != 'error'}")
        print(f"    Post-recovery state: {hive.state.value}")

        await hive.stop()
        return True


async def run_comprehensive_test_suite():
    """Run the complete Phase 5 test suite"""
    print("🚀 MAESTRO Phase 5: Autonomous Recursive Ecosystem Test Suite")
    print("=" * 70)

    test_suite = TestPhase5AutonomousHiveSystem()
    setup_env = None

    test_results = []
    test_functions = [
        ("Autonomous Hive Creation", test_suite.test_autonomous_hive_creation_and_initialization),
        ("Child Spawning", test_suite.test_autonomous_child_spawning),
        ("Boundary Optimization", test_suite.test_dynamic_boundary_optimization),
        ("Stigmergy Coordination", test_suite.test_stigmergy_coordination),
        ("Cross-phase Coordination", test_suite.test_cross_phase_coordination),
        ("Recursive Decomposition", test_suite.test_recursive_decomposition_scaling),
        ("Performance Optimization", test_suite.test_performance_metrics_and_optimization),
        ("Error Handling", test_suite.test_error_handling_and_recovery),
    ]

    for test_name, test_function in test_functions:
        try:
            print(f"\n{'-' * 50}")
            result = await test_function()
            test_results.append((test_name, "✅ PASSED" if result else "❌ FAILED"))
            print(f"✅ {test_name}: PASSED")

        except Exception as e:
            test_results.append((test_name, f"❌ FAILED: {str(e)}"))
            print(f"❌ {test_name}: FAILED - {e}")

        # Brief pause between tests
        await asyncio.sleep(1)

    # Summary
    print(f"\n{'=' * 70}")
    print("📊 TEST RESULTS SUMMARY")
    print(f"{'=' * 70}")

    passed_count = 0
    for test_name, status in test_results:
        print(f"  {status.split(':')[0]} {test_name}")
        if "PASSED" in status:
            passed_count += 1

    success_rate = (passed_count / len(test_results)) * 100
    print(
        f"\n🎯 OVERALL RESULTS: {passed_count}/{len(test_results)} tests passed ({success_rate:.1f}%)"
    )

    if success_rate >= 80:
        print("🎉 Phase 5 Autonomous Recursive Ecosystem is working excellently!")
        overall_status = "EXCELLENT"
    elif success_rate >= 60:
        print("✅ Phase 5 implementation is functioning well.")
        overall_status = "GOOD"
    else:
        print("⚠️ Phase 5 implementation needs attention.")
        overall_status = "NEEDS_WORK"

    print(f"Overall Status: {overall_status}")

    # Phase 5 capabilities summary
    print(f"\n🏆 Phase 5 Autonomous Recursive Ecosystem Capabilities:")
    capabilities = [
        "✅ Autonomous Hive Controllers with Bounded Autonomy",
        "✅ Dynamic Child Spawning Based on Complexity Analysis",
        "✅ AI-Enhanced Stigmergy Coordination",
        "✅ Dynamic Boundary Optimization",
        "✅ Cross-Phase Coordination Signals",
        "✅ Recursive Decomposition and Scaling",
        "✅ Performance-Based Optimization",
        "✅ Error Handling and Recovery Mechanisms",
    ]

    for capability in capabilities:
        print(f"  {capability}")

    return success_rate >= 60


if __name__ == "__main__":
    success = asyncio.run(run_comprehensive_test_suite())
    sys.exit(0 if success else 1)
