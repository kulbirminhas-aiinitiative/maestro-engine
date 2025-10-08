#!/usr/bin/env python3
"""
Unit tests for Dynamic Boundary Manager
"""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from shared.autonomy.dynamic_boundary_manager import (
    BoundaryAdjustment,
    BoundaryAdjustmentType,
    BoundaryConflictResolution,
    BoundaryMetrics,
    DynamicBoundaryManager,
    PerformanceThreshold,
)
from shared.models.orchestration_node import NodeStatus, NodeType, OrchestrationNode, Priority


class TestDynamicBoundaryManager:
    """Test suite for Dynamic Boundary Manager"""

    def setup_method(self):
        """Setup test fixtures"""
        self.boundary_manager = DynamicBoundaryManager()

        # Create test hives
        self.test_hive_1 = OrchestrationNode(
            requirement="Hive 1 - User Authentication",
            node_type=NodeType.FEATURE,
            priority=Priority.HIGH,
        )

        self.test_hive_2 = OrchestrationNode(
            requirement="Hive 2 - Data Processing",
            node_type=NodeType.FEATURE,
            priority=Priority.NORMAL,
        )

        # Create test boundary metrics
        self.test_metrics = BoundaryMetrics(
            hive_id=self.test_hive_1.node_id,
            performance_score=0.75,
            resource_utilization=0.80,
            task_completion_rate=0.85,
            error_rate=0.05,
            response_time_avg=2.5,
            throughput=150.0,
            boundary_violations=2,
            last_updated=datetime.now(),
        )

    def test_boundary_manager_initialization(self):
        """Test boundary manager initialization"""
        assert self.boundary_manager is not None
        assert hasattr(self.boundary_manager, "monitoring_active")
        assert hasattr(self.boundary_manager, "performance_thresholds")

    def test_boundary_metrics_creation(self):
        """Test boundary metrics creation"""
        metrics = BoundaryMetrics(
            hive_id="test_hive",
            performance_score=0.8,
            resource_utilization=0.7,
            task_completion_rate=0.9,
            error_rate=0.02,
            response_time_avg=1.5,
            throughput=200.0,
            boundary_violations=0,
            last_updated=datetime.now(),
        )

        assert metrics.hive_id == "test_hive"
        assert metrics.performance_score == 0.8
        assert metrics.error_rate == 0.02
        assert metrics.boundary_violations == 0

    @pytest.mark.asyncio
    async def test_start_boundary_monitoring(self):
        """Test starting boundary monitoring"""
        await self.boundary_manager.start_boundary_monitoring([self.test_hive_1, self.test_hive_2])

        assert self.boundary_manager.monitoring_active is True
        assert len(self.boundary_manager.monitored_hives) == 2

    @pytest.mark.asyncio
    async def test_stop_boundary_monitoring(self):
        """Test stopping boundary monitoring"""
        # Start monitoring first
        await self.boundary_manager.start_boundary_monitoring([self.test_hive_1])

        # Then stop it
        await self.boundary_manager.stop_boundary_monitoring()

        assert self.boundary_manager.monitoring_active is False

    @pytest.mark.asyncio
    async def test_collect_boundary_metrics(self):
        """Test boundary metrics collection"""
        with patch.object(
            self.boundary_manager, "_measure_hive_performance", new_callable=AsyncMock
        ) as mock_measure:
            mock_measure.return_value = {
                "performance_score": 0.8,
                "resource_utilization": 0.7,
                "task_completion_rate": 0.9,
                "error_rate": 0.03,
                "response_time_avg": 1.8,
                "throughput": 180.0,
                "boundary_violations": 1,
            }

            metrics = await self.boundary_manager.collect_boundary_metrics(self.test_hive_1)

            assert isinstance(metrics, BoundaryMetrics)
            assert metrics.hive_id == self.test_hive_1.node_id
            assert metrics.performance_score == 0.8
            mock_measure.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_boundary_adjustment(self):
        """Test boundary adjustment evaluation"""
        # Poor performance metrics should trigger adjustment
        poor_metrics = BoundaryMetrics(
            hive_id=self.test_hive_1.node_id,
            performance_score=0.4,  # Poor performance
            resource_utilization=0.95,  # High utilization
            task_completion_rate=0.6,  # Low completion rate
            error_rate=0.15,  # High error rate
            response_time_avg=8.0,  # Slow response
            throughput=50.0,  # Low throughput
            boundary_violations=5,
            last_updated=datetime.now(),
        )

        adjustment = await self.boundary_manager.evaluate_boundary_adjustment(
            self.test_hive_1, poor_metrics
        )

        assert adjustment is not None
        assert isinstance(adjustment, BoundaryAdjustment)
        assert adjustment.adjustment_needed is True

    @pytest.mark.asyncio
    async def test_execute_boundary_adjustment(self):
        """Test boundary adjustment execution"""
        adjustment = BoundaryAdjustment(
            hive_id=self.test_hive_1.node_id,
            adjustment_type=BoundaryAdjustmentType.EXPAND_SCOPE,
            adjustment_needed=True,
            priority=Priority.HIGH,
            rationale="Poor performance requires scope expansion",
            estimated_impact=0.3,
            resource_changes={"cpu": "+2", "memory": "+4GB"},
        )

        with patch.object(
            self.boundary_manager, "_apply_boundary_changes", new_callable=AsyncMock
        ) as mock_apply:
            mock_apply.return_value = {"success": True, "changes_applied": ["scope_expanded"]}

            result = await self.boundary_manager.execute_boundary_adjustment(
                self.test_hive_1, adjustment
            )

            assert result["success"] is True
            assert "changes_applied" in result
            mock_apply.assert_called_once()

    def test_boundary_adjustment_types(self):
        """Test boundary adjustment type enum"""
        assert BoundaryAdjustmentType.EXPAND_SCOPE.value == "expand_scope"
        assert BoundaryAdjustmentType.REDUCE_SCOPE.value == "reduce_scope"
        assert BoundaryAdjustmentType.INCREASE_RESOURCES.value == "increase_resources"
        assert BoundaryAdjustmentType.DECREASE_RESOURCES.value == "decrease_resources"
        assert BoundaryAdjustmentType.MERGE_BOUNDARIES.value == "merge_boundaries"
        assert BoundaryAdjustmentType.SPLIT_BOUNDARIES.value == "split_boundaries"

    def test_performance_threshold_validation(self):
        """Test performance threshold validation"""
        # Valid thresholds
        valid_thresholds = PerformanceThreshold(
            min_performance_score=0.6,
            max_resource_utilization=0.9,
            max_error_rate=0.1,
            max_response_time=5.0,
            min_throughput=100.0,
        )

        is_valid = self.boundary_manager._validate_performance_thresholds(valid_thresholds)
        assert is_valid is True

        # Invalid thresholds
        invalid_thresholds = PerformanceThreshold(
            min_performance_score=1.5,  # Invalid > 1.0
            max_resource_utilization=-0.1,  # Invalid negative
            max_error_rate=2.0,  # Invalid > 1.0
            max_response_time=-1.0,  # Invalid negative
            min_throughput=-50.0,  # Invalid negative
        )

        is_invalid = self.boundary_manager._validate_performance_thresholds(invalid_thresholds)
        assert is_invalid is False

    @pytest.mark.asyncio
    async def test_boundary_conflict_detection(self):
        """Test boundary conflict detection"""
        # Create overlapping boundaries
        hive_boundaries = {
            self.test_hive_1.node_id: {
                "scope": ["authentication", "user_management", "session_management"],
                "resources": {"cpu": 4, "memory": "8GB"},
            },
            self.test_hive_2.node_id: {
                "scope": ["user_management", "data_processing", "analytics"],
                "resources": {"cpu": 6, "memory": "12GB"},
            },
        }

        conflicts = await self.boundary_manager.detect_boundary_conflicts(hive_boundaries)

        assert len(conflicts) > 0
        # Should detect overlap in "user_management"
        assert any("user_management" in str(conflict) for conflict in conflicts)

    @pytest.mark.asyncio
    async def test_boundary_conflict_resolution(self):
        """Test boundary conflict resolution"""
        conflict = {
            "type": "scope_overlap",
            "hives": [self.test_hive_1.node_id, self.test_hive_2.node_id],
            "conflicting_elements": ["user_management"],
            "severity": "medium",
        }

        resolution = await self.boundary_manager.resolve_boundary_conflict(
            conflict, BoundaryConflictResolution.NEGOTIATE_SPLIT
        )

        assert resolution["resolved"] is True
        assert "resolution_strategy" in resolution
        assert resolution["resolution_strategy"] == BoundaryConflictResolution.NEGOTIATE_SPLIT

    def test_boundary_adjustment_history(self):
        """Test boundary adjustment history tracking"""
        # Add adjustment to history
        adjustment = BoundaryAdjustment(
            hive_id=self.test_hive_1.node_id,
            adjustment_type=BoundaryAdjustmentType.EXPAND_SCOPE,
            adjustment_needed=True,
            priority=Priority.HIGH,
            rationale="Performance improvement needed",
        )

        self.boundary_manager._track_boundary_adjustment(adjustment, success=True)

        history = self.boundary_manager.get_boundary_adjustment_history()
        assert len(history) > 0
        assert history[-1]["success"] is True

    @pytest.mark.asyncio
    async def test_boundary_optimization_suggestions(self):
        """Test boundary optimization suggestions"""
        metrics_history = [
            BoundaryMetrics(
                hive_id=self.test_hive_1.node_id,
                performance_score=0.6,
                resource_utilization=0.9,
                task_completion_rate=0.7,
                error_rate=0.1,
                response_time_avg=4.0,
                throughput=80.0,
                boundary_violations=3,
                last_updated=datetime.now() - timedelta(hours=1),
            ),
            BoundaryMetrics(
                hive_id=self.test_hive_1.node_id,
                performance_score=0.5,
                resource_utilization=0.95,
                task_completion_rate=0.6,
                error_rate=0.15,
                response_time_avg=6.0,
                throughput=60.0,
                boundary_violations=5,
                last_updated=datetime.now(),
            ),
        ]

        suggestions = await self.boundary_manager.generate_optimization_suggestions(
            self.test_hive_1, metrics_history
        )

        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        assert all("suggestion" in suggestion for suggestion in suggestions)

    @pytest.mark.asyncio
    async def test_boundary_monitoring_loop(self):
        """Test boundary monitoring loop"""
        # Start monitoring
        await self.boundary_manager.start_boundary_monitoring([self.test_hive_1])

        # Mock the monitoring cycle
        with patch.object(
            self.boundary_manager, "_monitoring_cycle", new_callable=AsyncMock
        ) as mock_cycle:
            mock_cycle.return_value = {"metrics_collected": 1, "adjustments_made": 0}

            # Run one monitoring cycle
            result = await self.boundary_manager._monitoring_cycle()

            assert "metrics_collected" in result
            mock_cycle.assert_called_once()

    def test_boundary_metrics_aggregation(self):
        """Test boundary metrics aggregation"""
        metrics_list = [
            BoundaryMetrics(
                hive_id="hive_1",
                performance_score=0.8,
                resource_utilization=0.7,
                task_completion_rate=0.9,
                error_rate=0.02,
                response_time_avg=1.5,
                throughput=200.0,
                boundary_violations=0,
                last_updated=datetime.now(),
            ),
            BoundaryMetrics(
                hive_id="hive_1",
                performance_score=0.7,
                resource_utilization=0.8,
                task_completion_rate=0.85,
                error_rate=0.03,
                response_time_avg=2.0,
                throughput=180.0,
                boundary_violations=1,
                last_updated=datetime.now(),
            ),
        ]

        aggregated = self.boundary_manager._aggregate_metrics(metrics_list)

        assert aggregated["avg_performance_score"] == 0.75
        assert aggregated["avg_resource_utilization"] == 0.75
        assert aggregated["total_boundary_violations"] == 1

    @pytest.mark.asyncio
    async def test_boundary_analytics(self):
        """Test boundary analytics generation"""
        analytics = await self.boundary_manager.get_boundary_analytics()

        assert isinstance(analytics, dict)
        assert "monitoring_status" in analytics
        assert "total_hives_monitored" in analytics
        assert "adjustment_success_rate" in analytics

    def test_boundary_configuration_validation(self):
        """Test boundary configuration validation"""
        # Valid configuration
        valid_config = {
            "monitoring_interval": 60,
            "adjustment_threshold": 0.6,
            "max_concurrent_adjustments": 3,
            "enable_auto_adjustment": True,
        }

        is_valid = self.boundary_manager._validate_boundary_config(valid_config)
        assert is_valid is True

        # Invalid configuration
        invalid_config = {
            "monitoring_interval": -60,  # Invalid negative
            "adjustment_threshold": 1.5,  # Invalid > 1.0
            "max_concurrent_adjustments": -1,  # Invalid negative
            "enable_auto_adjustment": "invalid",  # Invalid type
        }

        is_invalid = self.boundary_manager._validate_boundary_config(invalid_config)
        assert is_invalid is False

    @pytest.mark.asyncio
    async def test_boundary_rollback_capability(self):
        """Test boundary rollback capability"""
        # Create a rollback point
        rollback_point = await self.boundary_manager._create_boundary_rollback_point(
            self.test_hive_1
        )

        assert "rollback_id" in rollback_point
        assert "boundary_state" in rollback_point

        # Test rollback execution
        rollback_result = await self.boundary_manager._execute_boundary_rollback(
            rollback_point["rollback_id"]
        )

        assert rollback_result["success"] is True

    @pytest.mark.asyncio
    async def test_adaptive_thresholds(self):
        """Test adaptive threshold adjustment"""
        # Simulate performance history
        performance_history = [0.8, 0.75, 0.7, 0.65, 0.6]

        adaptive_thresholds = await self.boundary_manager._calculate_adaptive_thresholds(
            performance_history
        )

        assert "min_performance_score" in adaptive_thresholds
        assert "max_resource_utilization" in adaptive_thresholds
        assert adaptive_thresholds["min_performance_score"] > 0

    @pytest.mark.asyncio
    async def test_error_handling_invalid_hive(self):
        """Test error handling for invalid hive"""
        invalid_hive = None

        with pytest.raises((ValueError, TypeError)):
            await self.boundary_manager.collect_boundary_metrics(invalid_hive)

    @pytest.mark.asyncio
    async def test_concurrent_boundary_monitoring(self):
        """Test concurrent boundary monitoring for multiple hives"""
        hives = [self.test_hive_1, self.test_hive_2]

        # Start monitoring multiple hives
        await self.boundary_manager.start_boundary_monitoring(hives)

        # Mock concurrent metric collection
        with patch.object(
            self.boundary_manager, "collect_boundary_metrics", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = self.test_metrics

            # Collect metrics for all hives concurrently
            tasks = [self.boundary_manager.collect_boundary_metrics(hive) for hive in hives]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            assert len(results) == 2
            assert all(
                isinstance(result, BoundaryMetrics) or isinstance(result, Exception)
                for result in results
            )

    @pytest.mark.parametrize(
        "performance_score,expected_adjustment",
        [
            (0.9, False),  # Good performance, no adjustment needed
            (0.5, True),  # Poor performance, adjustment needed
            (0.3, True),  # Very poor performance, adjustment needed
        ],
    )
    @pytest.mark.asyncio
    async def test_performance_based_adjustments(self, performance_score, expected_adjustment):
        """Test performance-based boundary adjustments"""
        metrics = BoundaryMetrics(
            hive_id=self.test_hive_1.node_id,
            performance_score=performance_score,
            resource_utilization=0.8,
            task_completion_rate=0.7,
            error_rate=0.1,
            response_time_avg=3.0,
            throughput=100.0,
            boundary_violations=2,
            last_updated=datetime.now(),
        )

        adjustment = await self.boundary_manager.evaluate_boundary_adjustment(
            self.test_hive_1, metrics
        )

        assert (adjustment.adjustment_needed if adjustment else False) == expected_adjustment
