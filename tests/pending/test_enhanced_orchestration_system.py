#!/usr/bin/env python3
"""
Unit tests for Enhanced Orchestration System
"""
import asyncio
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from enhanced_orchestration_system import (
    AdaptationStrategy,
    AdaptiveWorkflowPlan,
    ConsensusMethod,
    ConsensusResult,
    EnhancedOrchestrationSystem,
    OrchestrationMode,
    PersonaPerformanceMetrics,
    ResourceAllocation,
    ResourceAllocationStrategy,
)

# Fix import path for enhanced orchestration system
# Use Poetry and relative imports instead of hardcoded paths



class TestPersonaPerformanceMetrics:
    """Test suite for Persona Performance Metrics"""

    def test_metrics_initialization(self):
        """Test persona performance metrics initialization"""
        metrics = PersonaPerformanceMetrics(persona_id="test_persona")

        assert metrics.persona_id == "test_persona"
        assert metrics.success_rate == 0.0
        assert metrics.average_response_time == 0.0
        assert metrics.quality_score == 0.0
        assert metrics.resource_efficiency == 0.0
        assert metrics.specialization_areas == []
        assert metrics.recent_executions == 0
        assert metrics.total_executions == 0
        assert metrics.confidence_level == 0.0

    def test_metrics_with_values(self):
        """Test persona performance metrics with specific values"""
        metrics = PersonaPerformanceMetrics(
            persona_id="experienced_persona",
            success_rate=0.85,
            average_response_time=1.2,
            quality_score=0.90,
            resource_efficiency=0.75,
            specialization_areas=["backend", "api_design"],
            recent_executions=15,
            total_executions=100,
            confidence_level=0.88,
        )

        assert metrics.persona_id == "experienced_persona"
        assert metrics.success_rate == 0.85
        assert metrics.quality_score == 0.90
        assert len(metrics.specialization_areas) == 2
        assert metrics.total_executions == 100


class TestAdaptiveWorkflowPlan:
    """Test suite for Adaptive Workflow Plan"""

    def test_plan_creation(self):
        """Test adaptive workflow plan creation"""
        plan = AdaptiveWorkflowPlan(
            plan_id="test_plan_001",
            requirement="Create web application",
            personas=["backend_dev", "frontend_dev"],
            execution_order=["backend_dev", "frontend_dev"],
            resource_allocation={"backend_dev": 50.0, "frontend_dev": 30.0},
            adaptation_rules=["performance_based"],
            expected_duration=120.0,
            confidence_score=0.85,
        )

        assert plan.plan_id == "test_plan_001"
        assert plan.requirement == "Create web application"
        assert len(plan.personas) == 2
        assert len(plan.execution_order) == 2
        assert plan.confidence_score == 0.85
        assert plan.fallback_plans == []  # Default empty list


class TestEnhancedOrchestrationSystem:
    """Test suite for Enhanced Orchestration System"""

    def setup_method(self):
        """Setup test fixtures"""
        self.orchestrator = EnhancedOrchestrationSystem()

    def test_orchestrator_initialization(self):
        """Test orchestrator initialization"""
        assert hasattr(self.orchestrator, "persona_metrics")
        assert hasattr(self.orchestrator, "adaptation_strategies")
        assert hasattr(self.orchestrator, "consensus_methods")
        assert hasattr(self.orchestrator, "resource_pools")
        assert hasattr(self.orchestrator, "execution_history")

        # Check resource pools initialization
        assert "cpu" in self.orchestrator.resource_pools
        assert "memory" in self.orchestrator.resource_pools
        assert self.orchestrator.resource_pools["cpu"] == 100.0

        # Check adaptation strategies
        assert len(self.orchestrator.adaptation_strategies) == 5
        assert AdaptationStrategy.PERFORMANCE_BASED in self.orchestrator.adaptation_strategies

        # Check consensus methods
        assert len(self.orchestrator.consensus_methods) == 5
        assert ConsensusMethod.MAJORITY_VOTE in self.orchestrator.consensus_methods

    @pytest.mark.asyncio
    async def test_create_adaptive_workflow_plan(self):
        """Test creation of adaptive workflow plan"""
        test_personas = ["backend_developer", "frontend_developer", "qa_engineer"]
        requirement = "Create user authentication system"

        # Add some test metrics
        for persona_id in test_personas:
            self.orchestrator.persona_metrics[persona_id] = PersonaPerformanceMetrics(
                persona_id=persona_id, success_rate=0.8, quality_score=0.75, resource_efficiency=0.7
            )

        plan = await self.orchestrator.create_adaptive_workflow_plan(
            requirement=requirement,
            personas=test_personas,
            adaptation_strategy=AdaptationStrategy.PERFORMANCE_BASED,
        )

        assert plan is not None
        assert plan.requirement == requirement
        assert len(plan.personas) == len(test_personas)
        assert plan.confidence_score >= 0.0
        assert plan.expected_duration >= 0.0
        assert len(plan.adaptation_rules) > 0

    @pytest.mark.asyncio
    async def test_persona_success_probability(self):
        """Test persona success probability calculation"""
        # Test with existing metrics
        self.orchestrator.persona_metrics["good_persona"] = PersonaPerformanceMetrics(
            persona_id="good_persona", success_rate=0.9
        )

        good_probability = self.orchestrator._get_persona_success_probability("good_persona")
        assert good_probability == 0.9

        # Test with low success rate (should be capped at minimum)
        self.orchestrator.persona_metrics["poor_persona"] = PersonaPerformanceMetrics(
            persona_id="poor_persona", success_rate=0.1
        )

        poor_probability = self.orchestrator._get_persona_success_probability("poor_persona")
        assert poor_probability == 0.3  # Minimum threshold

        # Test with new persona (no metrics)
        new_probability = self.orchestrator._get_persona_success_probability("new_persona")
        assert new_probability == 0.7  # Default for new personas

    @pytest.mark.asyncio
    async def test_execute_persona_batch(self):
        """Test execution of persona batch"""
        test_personas = ["test_persona_1", "test_persona_2"]
        requirement = "Test requirement"

        # Set up test metrics
        for persona_id in test_personas:
            self.orchestrator.persona_metrics[persona_id] = PersonaPerformanceMetrics(
                persona_id=persona_id, success_rate=0.8
            )

        # Mock asyncio.sleep to speed up test
        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await self.orchestrator._execute_persona_batch(test_personas, requirement)

            assert len(results) == len(test_personas)
            for result in results:
                assert "persona_id" in result
                assert "success" in result
                assert "execution_time" in result
                assert "quality_score" in result
                assert "output" in result
                assert "timestamp" in result
                assert "resource_usage" in result

    @pytest.mark.asyncio
    async def test_select_adaptive_batch(self):
        """Test adaptive batch selection"""
        test_personas = ["high_performer", "medium_performer", "low_performer", "new_persona"]

        # Set up performance metrics
        self.orchestrator.persona_metrics["high_performer"] = PersonaPerformanceMetrics(
            persona_id="high_performer",
            success_rate=0.95,
            quality_score=0.90,
            resource_efficiency=0.85,
            confidence_level=0.90,
        )

        self.orchestrator.persona_metrics["medium_performer"] = PersonaPerformanceMetrics(
            persona_id="medium_performer",
            success_rate=0.75,
            quality_score=0.70,
            resource_efficiency=0.65,
            confidence_level=0.70,
        )

        self.orchestrator.persona_metrics["low_performer"] = PersonaPerformanceMetrics(
            persona_id="low_performer",
            success_rate=0.60,
            quality_score=0.55,
            resource_efficiency=0.50,
            confidence_level=0.50,
        )

        batch = await self.orchestrator._select_adaptive_batch(test_personas, "test requirement")

        assert len(batch) <= 3  # Max batch size
        assert "high_performer" in batch  # Should be selected first
        # Order should be based on performance scores

    @pytest.mark.asyncio
    async def test_analyze_and_adapt(self):
        """Test performance analysis and adaptation logic"""
        test_plan = AdaptiveWorkflowPlan(
            plan_id="test_plan",
            requirement="test requirement",
            personas=["persona1", "persona2"],
            execution_order=["persona1", "persona2"],
            resource_allocation={},
            adaptation_rules=[],
            expected_duration=60.0,
            confidence_score=0.8,
        )

        # Test low performance triggering adaptation
        low_performance_results = [
            {"persona_id": "persona1", "success": False, "quality_score": 0.3},
            {"persona_id": "persona2", "success": False, "quality_score": 0.4},
        ]

        remaining_personas = ["persona3", "persona4"]

        # Add metrics for remaining personas
        self.orchestrator.persona_metrics["persona3"] = PersonaPerformanceMetrics(
            persona_id="persona3", success_rate=0.9, quality_score=0.85
        )

        adaptation = await self.orchestrator._analyze_and_adapt(
            low_performance_results, remaining_personas, test_plan
        )

        assert adaptation is not None
        assert adaptation["type"] == "add_persona"
        assert "persona3" in adaptation["persona_id"]

        # Test high performance (should consider scope reduction)
        high_performance_results = [
            {"persona_id": "persona1", "success": True, "quality_score": 0.95},
            {"persona_id": "persona2", "success": True, "quality_score": 0.92},
        ]

        remaining_personas_large = ["persona3", "persona4", "persona5", "persona6"]

        adaptation = await self.orchestrator._analyze_and_adapt(
            high_performance_results, remaining_personas_large, test_plan
        )

        assert adaptation is not None
        assert adaptation["type"] == "reduce_scope"

    @pytest.mark.asyncio
    async def test_check_early_termination(self):
        """Test early termination logic"""
        test_plan = AdaptiveWorkflowPlan(
            plan_id="test_plan",
            requirement="test requirement",
            personas=["persona1", "persona2"],
            execution_order=["persona1", "persona2"],
            resource_allocation={},
            adaptation_rules=[],
            expected_duration=60.0,
            confidence_score=0.8,
        )

        # Test insufficient results (should not terminate)
        insufficient_results = [{"persona_id": "persona1", "success": True, "quality_score": 0.95}]

        should_terminate = await self.orchestrator._check_early_termination(
            insufficient_results, test_plan
        )
        assert not should_terminate

        # Test high quality results (should terminate)
        high_quality_results = [
            {"persona_id": "persona1", "success": True, "quality_score": 0.95},
            {"persona_id": "persona2", "success": True, "quality_score": 0.92},
            {"persona_id": "persona3", "success": True, "quality_score": 0.91},
        ]

        should_terminate = await self.orchestrator._check_early_termination(
            high_quality_results, test_plan
        )
        assert should_terminate

        # Test mixed quality results (should not terminate)
        mixed_results = [
            {"persona_id": "persona1", "success": True, "quality_score": 0.95},
            {"persona_id": "persona2", "success": False, "quality_score": 0.60},
        ]

        should_terminate = await self.orchestrator._check_early_termination(
            mixed_results, test_plan
        )
        assert not should_terminate

    @pytest.mark.asyncio
    async def test_create_persona_consensus(self):
        """Test persona consensus creation"""
        test_responses = [
            {
                "persona_id": "backend_dev",
                "success": True,
                "quality_score": 0.85,
                "output": "Backend implementation approach A",
            },
            {
                "persona_id": "frontend_dev",
                "success": True,
                "quality_score": 0.90,
                "output": "Frontend implementation approach B",
            },
            {
                "persona_id": "architect",
                "success": True,
                "quality_score": 0.88,
                "output": "System architecture approach C",
            },
        ]

        # Test weighted average consensus
        consensus = await self.orchestrator.create_persona_consensus(
            requirement="System design approach",
            persona_responses=test_responses,
            method=ConsensusMethod.WEIGHTED_AVERAGE,
        )

        assert consensus is not None
        assert consensus.method == ConsensusMethod.WEIGHTED_AVERAGE
        assert len(consensus.participating_personas) == 3
        assert consensus.confidence > 0.0
        assert consensus.consensus_value is not None

        # Test majority vote consensus
        consensus_majority = await self.orchestrator.create_persona_consensus(
            requirement="System design approach",
            persona_responses=test_responses,
            method=ConsensusMethod.MAJORITY_VOTE,
        )

        assert consensus_majority.method == ConsensusMethod.MAJORITY_VOTE

    @pytest.mark.asyncio
    async def test_consensus_methods(self):
        """Test different consensus methods"""
        test_responses = [
            {"persona_id": "p1", "success": True, "quality_score": 0.8, "output": "Option A"},
            {"persona_id": "p2", "success": True, "quality_score": 0.9, "output": "Option B"},
            {"persona_id": "p3", "success": False, "quality_score": 0.6, "output": "Option C"},
        ]

        # Test weighted average
        result, confidence = await self.orchestrator._consensus_weighted_average(test_responses)
        assert result is not None
        assert 0.0 <= confidence <= 1.0

        # Test majority vote
        result, confidence = await self.orchestrator._consensus_majority_vote(test_responses)
        assert result is not None
        assert 0.0 <= confidence <= 1.0

        # Test confidence threshold
        result, confidence = await self.orchestrator._consensus_confidence_threshold(test_responses)
        assert result is not None
        assert 0.0 <= confidence <= 1.0

        # Test expert override
        result, confidence = await self.orchestrator._consensus_expert_override(test_responses)
        assert result is not None
        assert confidence == 0.9  # Should pick the highest quality response

        # Test collaborative filtering
        result, confidence = await self.orchestrator._consensus_collaborative_filtering(
            test_responses
        )
        assert result is not None
        assert 0.0 <= confidence <= 1.0

    @pytest.mark.asyncio
    async def test_calculate_disagreement(self):
        """Test disagreement calculation"""
        # Test high agreement
        high_agreement = [
            {"persona_id": "p1", "success": True, "quality_score": 0.85},
            {"persona_id": "p2", "success": True, "quality_score": 0.87},
            {"persona_id": "p3", "success": True, "quality_score": 0.86},
        ]

        disagreement = await self.orchestrator._calculate_disagreement(high_agreement)
        assert disagreement < 0.1  # Low disagreement

        # Test high disagreement
        high_disagreement = [
            {"persona_id": "p1", "success": True, "quality_score": 0.9},
            {"persona_id": "p2", "success": False, "quality_score": 0.3},
            {"persona_id": "p3", "success": True, "quality_score": 0.8},
        ]

        disagreement = await self.orchestrator._calculate_disagreement(high_disagreement)
        assert disagreement > 0.1  # Higher disagreement

        # Test single response (should be zero disagreement)
        single_response = [{"persona_id": "p1", "success": True, "quality_score": 0.8}]
        disagreement = await self.orchestrator._calculate_disagreement(single_response)
        assert disagreement == 0.0

    @pytest.mark.asyncio
    async def test_resource_allocation(self):
        """Test resource allocation to personas"""
        test_personas = ["persona1", "persona2", "persona3"]

        # Set up performance metrics
        self.orchestrator.persona_metrics["persona1"] = PersonaPerformanceMetrics(
            persona_id="persona1", success_rate=0.9, quality_score=0.85, resource_efficiency=0.8
        )

        self.orchestrator.persona_metrics["persona2"] = PersonaPerformanceMetrics(
            persona_id="persona2", success_rate=0.7, quality_score=0.7, resource_efficiency=0.6
        )

        allocation = await self.orchestrator._allocate_resources(
            test_personas, ResourceAllocationStrategy.PERFORMANCE_OPTIMIZED
        )

        assert allocation is not None
        assert len(allocation.persona_allocations) == len(test_personas)
        assert allocation.allocation_strategy == ResourceAllocationStrategy.PERFORMANCE_OPTIMIZED

        # Check that high-performing persona gets more resources
        persona1_cpu = allocation.persona_allocations["persona1"]["cpu"]
        persona2_cpu = allocation.persona_allocations["persona2"]["cpu"]
        assert persona1_cpu > persona2_cpu

    @pytest.mark.asyncio
    async def test_update_persona_metrics(self):
        """Test updating persona metrics from execution results"""
        initial_metrics = PersonaPerformanceMetrics(
            persona_id="test_persona",
            success_rate=0.5,
            quality_score=0.6,
            average_response_time=1.0,
            resource_efficiency=0.5,
        )

        self.orchestrator.persona_metrics["test_persona"] = initial_metrics

        # Simulate successful execution
        execution_results = [
            {
                "persona_id": "test_persona",
                "success": True,
                "quality_score": 0.8,
                "execution_time": 0.5,
                "resource_usage": {"cpu": 20.0},
            }
        ]

        await self.orchestrator._update_persona_metrics(execution_results)

        updated_metrics = self.orchestrator.persona_metrics["test_persona"]

        # Metrics should improve (moving average)
        assert updated_metrics.success_rate > initial_metrics.success_rate
        assert updated_metrics.quality_score > initial_metrics.quality_score
        assert updated_metrics.total_executions == 1
        assert updated_metrics.recent_executions == 1

    @pytest.mark.asyncio
    async def test_execute_sequential_mode(self):
        """Test sequential execution mode"""
        test_plan = AdaptiveWorkflowPlan(
            plan_id="seq_plan",
            requirement="Sequential test",
            personas=["persona1", "persona2"],
            execution_order=["persona1", "persona2"],
            resource_allocation={},
            adaptation_rules=[],
            expected_duration=60.0,
            confidence_score=0.8,
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await self.orchestrator._execute_sequential(test_plan)

            assert len(results) == 2
            assert results[0]["persona_id"] == "persona1"
            assert results[1]["persona_id"] == "persona2"

    @pytest.mark.asyncio
    async def test_execute_parallel_mode(self):
        """Test parallel execution mode"""
        test_plan = AdaptiveWorkflowPlan(
            plan_id="par_plan",
            requirement="Parallel test",
            personas=["persona1", "persona2", "persona3"],
            execution_order=["persona1", "persona2", "persona3"],
            resource_allocation={},
            adaptation_rules=[],
            expected_duration=60.0,
            confidence_score=0.8,
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await self.orchestrator._execute_parallel(test_plan)

            assert len(results) == 3
            # All personas should be executed (parallel doesn't guarantee order)
            persona_ids = {r["persona_id"] for r in results}
            assert persona_ids == {"persona1", "persona2", "persona3"}

    @pytest.mark.asyncio
    async def test_execute_hybrid_mode(self):
        """Test hybrid execution mode"""
        test_plan = AdaptiveWorkflowPlan(
            plan_id="hybrid_plan",
            requirement="Hybrid test",
            personas=["persona1", "persona2", "persona3", "persona4"],
            execution_order=["persona1", "persona2", "persona3", "persona4"],
            resource_allocation={},
            adaptation_rules=[],
            expected_duration=60.0,
            confidence_score=0.8,
        )

        execution_result = {"adaptations": []}

        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await self.orchestrator._execute_hybrid(test_plan, execution_result)

            assert len(results) == 4
            # Should have all personas executed
            persona_ids = {r["persona_id"] for r in results}
            assert persona_ids == {"persona1", "persona2", "persona3", "persona4"}

    @pytest.mark.asyncio
    async def test_orchestration_analytics(self):
        """Test orchestration analytics generation"""
        # Add some execution history
        test_execution = {
            "execution_id": "test_exec_1",
            "start_time": datetime.now().isoformat(),
            "success": True,
            "total_duration": 30.0,
        }

        self.orchestrator.execution_history.append(test_execution)

        # Add some adaptation history
        test_adaptation = {
            "type": "add_persona",
            "timestamp": datetime.now().isoformat(),
            "persona_id": "backup_persona",
        }

        self.orchestrator.adaptation_history.append(test_adaptation)

        # Add persona metrics
        self.orchestrator.persona_metrics["test_persona"] = PersonaPerformanceMetrics(
            persona_id="test_persona",
            success_rate=0.85,
            quality_score=0.80,
            average_response_time=1.2,
            resource_efficiency=0.75,
            confidence_level=0.70,
            recent_executions=5,
        )

        analytics = await self.orchestrator.get_orchestration_analytics(days=7)

        assert "total_executions" in analytics
        assert "success_rate" in analytics
        assert "adaptations" in analytics
        assert "persona_performance" in analytics
        assert "resource_utilization" in analytics
        assert analytics["total_executions"] == 1
        assert analytics["success_rate"] == 1.0  # 100% success rate
        assert analytics["adaptations"]["total"] == 1

    @pytest.mark.asyncio
    async def test_adaptation_strategies(self):
        """Test different adaptation strategies"""
        test_personas = ["persona1", "persona2", "persona3"]
        requirement = "Test adaptation strategies"

        # Set up different performance levels
        self.orchestrator.persona_metrics["persona1"] = PersonaPerformanceMetrics(
            persona_id="persona1", success_rate=0.9, quality_score=0.85, resource_efficiency=0.8
        )

        self.orchestrator.persona_metrics["persona2"] = PersonaPerformanceMetrics(
            persona_id="persona2", success_rate=0.7, quality_score=0.75, resource_efficiency=0.6
        )

        self.orchestrator.persona_metrics["persona3"] = PersonaPerformanceMetrics(
            persona_id="persona3", success_rate=0.8, quality_score=0.70, resource_efficiency=0.9
        )

        # Test performance-based adaptation
        adapted_personas, order = await self.orchestrator._adapt_by_performance(
            requirement, test_personas
        )
        assert len(adapted_personas) == len(test_personas)
        assert adapted_personas[0] == "persona1"  # Highest success rate

        # Test resource-based adaptation
        adapted_personas, order = await self.orchestrator._adapt_by_resources(
            requirement, test_personas
        )
        assert len(adapted_personas) == len(test_personas)
        assert adapted_personas[0] == "persona3"  # Highest resource efficiency

        # Test quality-based adaptation
        adapted_personas, order = await self.orchestrator._adapt_by_quality(
            requirement, test_personas
        )
        assert len(adapted_personas) == len(test_personas)
        assert adapted_personas[0] == "persona1"  # Highest quality score

    @pytest.mark.asyncio
    async def test_estimate_execution_duration(self):
        """Test execution duration estimation"""
        test_personas = ["persona1", "persona2"]

        # Set up metrics with known response times
        self.orchestrator.persona_metrics["persona1"] = PersonaPerformanceMetrics(
            persona_id="persona1", average_response_time=1.5
        )

        self.orchestrator.persona_metrics["persona2"] = PersonaPerformanceMetrics(
            persona_id="persona2", average_response_time=2.0
        )

        duration = await self.orchestrator._estimate_execution_duration(
            test_personas, test_personas
        )

        assert duration == 3.5  # 1.5 + 2.0

        # Test with unknown persona
        duration_with_unknown = await self.orchestrator._estimate_execution_duration(
            ["unknown_persona"], ["unknown_persona"]
        )

        assert duration_with_unknown == 1.0  # Default estimate

    @pytest.mark.asyncio
    async def test_calculate_plan_confidence(self):
        """Test plan confidence calculation"""
        test_personas = ["persona1", "persona2"]

        # Set up confidence levels
        self.orchestrator.persona_metrics["persona1"] = PersonaPerformanceMetrics(
            persona_id="persona1", confidence_level=0.8
        )

        self.orchestrator.persona_metrics["persona2"] = PersonaPerformanceMetrics(
            persona_id="persona2", confidence_level=0.6
        )

        confidence = await self.orchestrator._calculate_plan_confidence(
            test_personas, "test requirement"
        )

        assert confidence == 0.7  # Average of 0.8 and 0.6

        # Test with unknown persona
        confidence_with_unknown = await self.orchestrator._calculate_plan_confidence(
            ["unknown_persona"], "test requirement"
        )

        assert confidence_with_unknown == 0.5  # Default confidence

    @pytest.mark.asyncio
    async def test_select_best_persona(self):
        """Test best persona selection"""
        available_personas = ["persona1", "persona2", "persona3"]

        # Set up different performance levels
        self.orchestrator.persona_metrics["persona1"] = PersonaPerformanceMetrics(
            persona_id="persona1", success_rate=0.9, quality_score=0.85
        )

        self.orchestrator.persona_metrics["persona2"] = PersonaPerformanceMetrics(
            persona_id="persona2", success_rate=0.7, quality_score=0.80
        )

        self.orchestrator.persona_metrics["persona3"] = PersonaPerformanceMetrics(
            persona_id="persona3", success_rate=0.8, quality_score=0.70
        )

        best_persona = await self.orchestrator._select_best_persona(available_personas)
        assert best_persona == "persona1"  # Highest combined score

        # Test with empty list
        best_from_empty = await self.orchestrator._select_best_persona([])
        assert best_from_empty is None

    @pytest.mark.asyncio
    async def test_get_resource_utilization(self):
        """Test resource utilization calculation"""
        # Test with no allocations
        utilization_empty = await self.orchestrator._get_resource_utilization()
        assert all(util == 0.0 for util in utilization_empty.values())

        # Add test allocation
        test_allocation = ResourceAllocation(
            allocation_id="test_alloc",
            persona_allocations={},
            total_resources={"cpu": 50.0, "memory": 2000.0},
            utilization_rate=0.5,
            allocation_strategy=ResourceAllocationStrategy.PERFORMANCE_OPTIMIZED,
            timestamp=datetime.now(),
        )

        self.orchestrator.current_allocations.append(test_allocation)

        utilization = await self.orchestrator._get_resource_utilization()
        assert utilization["cpu"] == 50.0  # 50/100 * 100%
        assert utilization["memory"] == pytest.approx(24.414, rel=1e-2)  # 2000/8192 * 100%


class TestIntegrationScenarios:
    """Test integration scenarios for Enhanced Orchestration System"""

    @pytest.mark.asyncio
    async def test_full_adaptive_workflow_execution(self):
        """Test complete adaptive workflow from planning to execution"""
        orchestrator = EnhancedOrchestrationSystem()

        # Set up test personas with metrics
        test_personas = ["backend_dev", "frontend_dev", "qa_engineer"]
        for persona_id in test_personas:
            orchestrator.persona_metrics[persona_id] = PersonaPerformanceMetrics(
                persona_id=persona_id,
                success_rate=0.8,
                quality_score=0.75,
                average_response_time=1.0,
                resource_efficiency=0.7,
                confidence_level=0.6,
            )

        # Create and execute workflow plan
        plan = await orchestrator.create_adaptive_workflow_plan(
            requirement="Build user authentication system",
            personas=test_personas,
            adaptation_strategy=AdaptationStrategy.PERFORMANCE_BASED,
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await orchestrator.execute_adaptive_workflow(plan, OrchestrationMode.ADAPTIVE)

            assert result["success"] is not None
            assert "execution_id" in result
            assert "total_duration" in result
            assert len(result["results"]) > 0

    @pytest.mark.asyncio
    async def test_consensus_with_disagreement(self):
        """Test consensus mechanism with high disagreement"""
        orchestrator = EnhancedOrchestrationSystem()

        # Create responses with high disagreement
        disagreeing_responses = [
            {"persona_id": "p1", "success": True, "quality_score": 0.9, "output": "Approach A"},
            {"persona_id": "p2", "success": False, "quality_score": 0.3, "output": "Approach B"},
            {"persona_id": "p3", "success": True, "quality_score": 0.5, "output": "Approach C"},
        ]

        consensus = await orchestrator.create_persona_consensus(
            "System architecture approach",
            disagreeing_responses,
            ConsensusMethod.CONFIDENCE_THRESHOLD,
        )

        assert consensus.disagreement_level > 0.3  # High disagreement
        assert consensus.confidence < 0.8  # Lower confidence due to disagreement

    @pytest.mark.asyncio
    async def test_resource_exhaustion_scenario(self):
        """Test behavior when resources are exhausted"""
        orchestrator = EnhancedOrchestrationSystem()

        # Reduce available resources
        orchestrator.resource_pools = {
            "cpu": 10.0,  # Very limited
            "memory": 100.0,  # Very limited
            "network": 10.0,
            "storage": 100.0,
        }

        many_personas = [f"persona_{i}" for i in range(10)]

        allocation = await orchestrator._allocate_resources(
            many_personas, ResourceAllocationStrategy.PERFORMANCE_OPTIMIZED
        )

        assert allocation is not None
        assert allocation.utilization_rate <= 1.0  # Should not exceed 100%

        # Verify no single persona gets more than available
        for persona_allocation in allocation.persona_allocations.values():
            assert persona_allocation["cpu"] <= orchestrator.resource_pools["cpu"]

    @pytest.mark.asyncio
    async def test_adaptation_learning_over_time(self):
        """Test that adaptation improves over multiple executions"""
        orchestrator = EnhancedOrchestrationSystem()

        test_personas = ["learner_persona"]
        requirement = "Learning test"

        # Start with poor performance
        orchestrator.persona_metrics["learner_persona"] = PersonaPerformanceMetrics(
            persona_id="learner_persona",
            success_rate=0.3,
            quality_score=0.4,
            average_response_time=2.0,
            resource_efficiency=0.3,
        )

        initial_metrics = orchestrator.persona_metrics["learner_persona"]

        # Simulate multiple successful executions
        for _ in range(5):
            good_results = [
                {
                    "persona_id": "learner_persona",
                    "success": True,
                    "quality_score": 0.9,
                    "execution_time": 0.8,
                    "resource_usage": {"cpu": 15.0},
                }
            ]

            await orchestrator._update_persona_metrics(good_results)

        final_metrics = orchestrator.persona_metrics["learner_persona"]

        # Metrics should improve over time
        assert final_metrics.success_rate > initial_metrics.success_rate
        assert final_metrics.quality_score > initial_metrics.quality_score
        assert final_metrics.total_executions == 5
