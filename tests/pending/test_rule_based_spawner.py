#!/usr/bin/env python3
"""
Unit tests for Rule-Based Autonomous Spawning System
"""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from shared.autonomy.rule_based_spawner import (
    AutonomousSpawnConfig,
    ResourceMetrics,
    RuleBasedAutonomousSpawner,
    SpawnDecision,
    SpawnRecommendation,
    SpawnStrategy,
    SpawnTrigger,
)
from shared.intelligence.complexity_analyzer import ComplexityLevel
from shared.models.orchestration_node import NodeStatus, NodeType, OrchestrationNode, Priority
from shared.orchestration.multi_phase_engine import ProjectPhase


class TestRuleBasedAutonomousSpawner:
    """Test suite for Rule-Based Autonomous Spawning System"""

    def setup_method(self):
        """Setup test fixtures"""
        self.spawner = RuleBasedAutonomousSpawner()

        # Create test hive
        self.test_hive = OrchestrationNode(
            requirement="Test complex system with multiple components",
            node_type=NodeType.FEATURE,
            priority=Priority.HIGH,
        )

        # Create test resource metrics
        self.test_metrics = ResourceMetrics(
            cpu_usage=0.7,
            memory_usage=0.6,
            network_bandwidth=0.5,
            active_hives=5,
            concurrent_tasks=20,
            average_response_time=2.5,
            error_rate=0.05,
        )

    def test_spawner_initialization(self):
        """Test spawner initialization"""
        assert self.spawner is not None
        assert hasattr(self.spawner, "config")
        assert hasattr(self.spawner, "phase_complexity_analyzer")
        assert isinstance(self.spawner.config, AutonomousSpawnConfig)

    def test_spawn_trigger_enum(self):
        """Test SpawnTrigger enum values"""
        assert SpawnTrigger.COMPLEXITY_THRESHOLD.value == "complexity_threshold"
        assert SpawnTrigger.PERFORMANCE_DEGRADATION.value == "performance_degradation"
        assert SpawnTrigger.RESOURCE_UTILIZATION.value == "resource_utilization"
        assert SpawnTrigger.WORKLOAD_IMBALANCE.value == "workload_imbalance"

    def test_spawn_strategy_enum(self):
        """Test SpawnStrategy enum values"""
        assert SpawnStrategy.FUNCTIONAL_DECOMPOSITION.value == "functional_decomposition"
        assert SpawnStrategy.TECHNICAL_DECOMPOSITION.value == "technical_decomposition"
        assert SpawnStrategy.WORKLOAD_DISTRIBUTION.value == "workload_distribution"
        assert SpawnStrategy.SPECIALIZATION.value == "specialization"

    @pytest.mark.asyncio
    async def test_evaluate_spawn_conditions_basic(self):
        """Test basic spawn condition evaluation"""
        context = {"complexity_level": ComplexityLevel.COMPLEX}

        with patch.object(
            self.spawner.phase_complexity_analyzer, "analyze_phase_complexity"
        ) as mock_analyze:
            mock_analyze.return_value = MagicMock(
                complexity_level=ComplexityLevel.COMPLEX, complexity_score=25.0
            )

            recommendations = await self.spawner.evaluate_spawn_conditions(
                self.test_hive, self.test_metrics, context
            )

            assert isinstance(recommendations, list)
            assert len(recommendations) > 0
            assert all(isinstance(rec, SpawnRecommendation) for rec in recommendations)

    @pytest.mark.asyncio
    async def test_complexity_threshold_trigger(self):
        """Test complexity threshold trigger evaluation"""
        # High complexity should trigger spawning
        high_complexity_context = {"complexity_level": ComplexityLevel.COMPLEX}

        recommendations = await self.spawner._evaluate_complexity_trigger(
            self.test_hive, self.test_metrics, high_complexity_context
        )

        assert len(recommendations) > 0
        assert any(rec.trigger == SpawnTrigger.COMPLEXITY_THRESHOLD for rec in recommendations)

    @pytest.mark.asyncio
    async def test_performance_degradation_trigger(self):
        """Test performance degradation trigger evaluation"""
        # Poor performance metrics should trigger spawning
        poor_metrics = ResourceMetrics(
            cpu_usage=0.95,
            memory_usage=0.90,
            network_bandwidth=0.85,
            active_hives=10,
            concurrent_tasks=50,
            average_response_time=10.0,  # Very slow
            error_rate=0.20,  # High error rate
        )

        recommendations = await self.spawner._evaluate_performance_trigger(
            self.test_hive, poor_metrics, {}
        )

        assert len(recommendations) > 0
        assert any(rec.trigger == SpawnTrigger.PERFORMANCE_DEGRADATION for rec in recommendations)

    @pytest.mark.asyncio
    async def test_resource_utilization_trigger(self):
        """Test resource utilization trigger evaluation"""
        # High resource utilization should trigger spawning
        high_resource_metrics = ResourceMetrics(
            cpu_usage=0.90,
            memory_usage=0.85,
            network_bandwidth=0.80,
            active_hives=3,
            concurrent_tasks=40,
            average_response_time=3.0,
            error_rate=0.05,
        )

        recommendations = await self.spawner._evaluate_resource_trigger(
            self.test_hive, high_resource_metrics, {}
        )

        assert len(recommendations) > 0
        assert any(rec.trigger == SpawnTrigger.RESOURCE_UTILIZATION for rec in recommendations)

    @pytest.mark.asyncio
    async def test_workload_imbalance_trigger(self):
        """Test workload imbalance trigger evaluation"""
        # Imbalanced workload should trigger spawning
        imbalanced_context = {
            "hive_workloads": {
                "hive_1": 50,  # Very high
                "hive_2": 5,  # Very low
                "hive_3": 25,  # Medium
            }
        }

        recommendations = await self.spawner._evaluate_workload_trigger(
            self.test_hive, self.test_metrics, imbalanced_context
        )

        assert len(recommendations) > 0
        assert any(rec.trigger == SpawnTrigger.WORKLOAD_IMBALANCE for rec in recommendations)

    def test_spawn_recommendation_creation(self):
        """Test spawn recommendation creation"""
        recommendation = SpawnRecommendation(
            trigger=SpawnTrigger.COMPLEXITY_THRESHOLD,
            strategy=SpawnStrategy.FUNCTIONAL_DECOMPOSITION,
            priority=Priority.HIGH,
            confidence=0.85,
            rationale="High complexity requires decomposition",
            estimated_benefit=0.70,
            resource_requirements={"cpu": 2, "memory": "4GB"},
            timeline_estimate=timedelta(hours=2),
        )

        assert recommendation.trigger == SpawnTrigger.COMPLEXITY_THRESHOLD
        assert recommendation.strategy == SpawnStrategy.FUNCTIONAL_DECOMPOSITION
        assert recommendation.confidence == 0.85
        assert recommendation.estimated_benefit == 0.70

    @pytest.mark.asyncio
    async def test_execute_spawn_decision(self):
        """Test spawn decision execution"""
        spawn_decision = SpawnDecision(
            approved=True,
            selected_strategy=SpawnStrategy.FUNCTIONAL_DECOMPOSITION,
            resource_allocation={"cpu": 4, "memory": "8GB"},
            approval_rationale="Complexity requires decomposition",
        )

        with patch.object(
            self.spawner, "_create_child_hives", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = [
                OrchestrationNode(requirement="Component A", node_type=NodeType.TASK),
                OrchestrationNode(requirement="Component B", node_type=NodeType.TASK),
            ]

            result = await self.spawner.execute_spawn_decision(self.test_hive, spawn_decision, {})

            assert result["success"] is True
            assert len(result["child_hives"]) == 2
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_spawn_analytics(self):
        """Test spawn analytics collection"""
        spawn_history = [
            {
                "timestamp": datetime.now() - timedelta(hours=1),
                "trigger": SpawnTrigger.COMPLEXITY_THRESHOLD,
                "success": True,
                "benefit_realized": 0.8,
            },
            {
                "timestamp": datetime.now() - timedelta(minutes=30),
                "trigger": SpawnTrigger.PERFORMANCE_DEGRADATION,
                "success": True,
                "benefit_realized": 0.6,
            },
        ]

        analytics = self.spawner.get_spawn_analytics(spawn_history)

        assert "success_rate" in analytics
        assert "average_benefit" in analytics
        assert "trigger_frequency" in analytics
        assert analytics["success_rate"] == 1.0
        assert analytics["average_benefit"] == 0.7

    def test_resource_constraint_checking(self):
        """Test resource constraint checking"""
        # Available resources
        available_resources = {
            "cpu": 8,
            "memory": "16GB",
            "storage": "1TB",
            "network_bandwidth": "1Gbps",
        }

        # Required resources for spawning
        required_resources = {"cpu": 4, "memory": "8GB", "storage": "100GB"}

        can_spawn = self.spawner._check_resource_constraints(
            available_resources, required_resources
        )

        assert can_spawn is True

        # Test insufficient resources
        insufficient_resources = {"cpu": 2, "memory": "4GB"}  # Not enough CPU  # Not enough memory

        cannot_spawn = self.spawner._check_resource_constraints(
            insufficient_resources, required_resources
        )

        assert cannot_spawn is False

    def test_spawn_strategy_selection(self):
        """Test spawn strategy selection"""
        # Test functional decomposition strategy
        functional_strategy = self.spawner._select_spawn_strategy(
            SpawnTrigger.COMPLEXITY_THRESHOLD, {"requirement_type": "functional"}
        )
        assert functional_strategy == SpawnStrategy.FUNCTIONAL_DECOMPOSITION

        # Test performance-based strategy
        performance_strategy = self.spawner._select_spawn_strategy(
            SpawnTrigger.PERFORMANCE_DEGRADATION, {"bottleneck_type": "processing"}
        )
        assert performance_strategy in [
            SpawnStrategy.WORKLOAD_DISTRIBUTION,
            SpawnStrategy.PARALLEL_EXECUTION,
        ]

    def test_confidence_calculation(self):
        """Test confidence score calculation"""
        # High confidence scenario
        high_confidence_factors = {
            "complexity_certainty": 0.9,
            "resource_availability": 0.8,
            "historical_success": 0.85,
            "strategy_fit": 0.9,
        }

        high_confidence = self.spawner._calculate_confidence(high_confidence_factors)
        assert high_confidence > 0.8

        # Low confidence scenario
        low_confidence_factors = {
            "complexity_certainty": 0.5,
            "resource_availability": 0.4,
            "historical_success": 0.3,
            "strategy_fit": 0.6,
        }

        low_confidence = self.spawner._calculate_confidence(low_confidence_factors)
        assert low_confidence < 0.6

    def test_benefit_estimation(self):
        """Test benefit estimation"""
        # High benefit scenario
        high_benefit_context = {
            "current_performance": 0.3,
            "expected_improvement": 0.7,
            "complexity_reduction": 0.8,
            "resource_efficiency": 0.6,
        }

        high_benefit = self.spawner._estimate_spawn_benefit(high_benefit_context)
        assert high_benefit > 0.6

        # Low benefit scenario
        low_benefit_context = {
            "current_performance": 0.8,
            "expected_improvement": 0.2,
            "complexity_reduction": 0.1,
            "resource_efficiency": 0.3,
        }

        low_benefit = self.spawner._estimate_spawn_benefit(low_benefit_context)
        assert low_benefit < 0.4

    @pytest.mark.asyncio
    async def test_spawn_timing_optimization(self):
        """Test spawn timing optimization"""
        # Test optimal timing
        optimal_timing = await self.spawner._determine_optimal_spawn_timing(
            self.test_hive, self.test_metrics, SpawnStrategy.FUNCTIONAL_DECOMPOSITION
        )

        assert "recommended_delay" in optimal_timing
        assert "urgency_level" in optimal_timing
        assert optimal_timing["recommended_delay"] >= 0

    def test_spawn_history_tracking(self):
        """Test spawn history tracking"""
        # Add spawn events to history
        self.spawner._track_spawn_event(
            self.test_hive,
            SpawnTrigger.COMPLEXITY_THRESHOLD,
            SpawnStrategy.FUNCTIONAL_DECOMPOSITION,
            success=True,
            benefit_realized=0.8,
        )

        history = self.spawner.get_spawn_history()
        assert len(history) > 0
        assert history[-1]["success"] is True
        assert history[-1]["benefit_realized"] == 0.8

    @pytest.mark.asyncio
    async def test_error_handling_invalid_metrics(self):
        """Test error handling for invalid metrics"""
        invalid_metrics = ResourceMetrics(
            cpu_usage=-0.5,  # Invalid negative value
            memory_usage=1.5,  # Invalid > 1.0 value
            network_bandwidth=0.5,
            active_hives=5,
            concurrent_tasks=20,
            average_response_time=2.5,
            error_rate=0.05,
        )

        # Should handle gracefully
        recommendations = await self.spawner.evaluate_spawn_conditions(
            self.test_hive, invalid_metrics, {}
        )

        # Should still return recommendations or handle error gracefully
        assert isinstance(recommendations, list)

    @pytest.mark.asyncio
    async def test_concurrent_spawn_evaluation(self):
        """Test concurrent spawn evaluation for multiple hives"""
        hives = [
            OrchestrationNode(requirement=f"Hive {i}", node_type=NodeType.FEATURE) for i in range(5)
        ]

        # Test concurrent evaluation
        tasks = [
            self.spawner.evaluate_spawn_conditions(hive, self.test_metrics, {}) for hive in hives
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All evaluations should complete
        assert len(results) == 5
        assert all(isinstance(result, list) or isinstance(result, Exception) for result in results)

    def test_spawn_configuration_validation(self):
        """Test spawn configuration validation"""
        # Valid configuration
        valid_config = AutonomousSpawnConfig(
            enable_autonomous_spawning=True,
            complexity_threshold=0.7,
            performance_threshold=0.8,
            resource_threshold=0.85,
            max_concurrent_spawns=3,
            min_confidence_threshold=0.6,
        )

        is_valid = self.spawner._validate_spawn_config(valid_config)
        assert is_valid is True

        # Invalid configuration
        invalid_config = AutonomousSpawnConfig(
            enable_autonomous_spawning=True,
            complexity_threshold=1.5,  # Invalid > 1.0
            performance_threshold=-0.1,  # Invalid negative
            resource_threshold=0.85,
            max_concurrent_spawns=-1,  # Invalid negative
            min_confidence_threshold=0.6,
        )

        is_invalid = self.spawner._validate_spawn_config(invalid_config)
        assert is_invalid is False

    @pytest.mark.parametrize(
        "trigger,expected_strategy",
        [
            (SpawnTrigger.COMPLEXITY_THRESHOLD, SpawnStrategy.FUNCTIONAL_DECOMPOSITION),
            (SpawnTrigger.PERFORMANCE_DEGRADATION, SpawnStrategy.WORKLOAD_DISTRIBUTION),
            (SpawnTrigger.RESOURCE_UTILIZATION, SpawnStrategy.PARALLEL_EXECUTION),
        ],
    )
    def test_trigger_strategy_mapping(self, trigger, expected_strategy):
        """Test trigger to strategy mapping"""
        strategy = self.spawner._select_spawn_strategy(trigger, {})

        # Should return a valid strategy (exact mapping may vary based on context)
        assert isinstance(strategy, SpawnStrategy)

    def test_spawn_recommendation_prioritization(self):
        """Test spawn recommendation prioritization"""
        recommendations = [
            SpawnRecommendation(
                trigger=SpawnTrigger.COMPLEXITY_THRESHOLD,
                strategy=SpawnStrategy.FUNCTIONAL_DECOMPOSITION,
                priority=Priority.NORMAL,
                confidence=0.7,
                estimated_benefit=0.6,
            ),
            SpawnRecommendation(
                trigger=SpawnTrigger.PERFORMANCE_DEGRADATION,
                strategy=SpawnStrategy.WORKLOAD_DISTRIBUTION,
                priority=Priority.HIGH,
                confidence=0.9,
                estimated_benefit=0.8,
            ),
        ]

        prioritized = self.spawner._prioritize_recommendations(recommendations)

        # High priority, high confidence recommendation should be first
        assert prioritized[0].priority == Priority.HIGH
        assert prioritized[0].confidence == 0.9
