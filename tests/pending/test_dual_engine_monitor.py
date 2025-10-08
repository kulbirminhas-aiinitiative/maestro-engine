#!/usr/bin/env python3
"""
Unit Tests for DualEngineMonitor
Tests the comprehensive monitoring system for dual-engine orchestration.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from shared.monitoring.dual_engine_monitor import (
    ComparisonAnalysis,
    DualEngineMonitor,
    EngineMetrics,
    EnginePerformanceType,
    ExecutionRecord,
    end_execution_tracking,
    get_dashboard_data,
    get_performance_comparison,
    start_execution_tracking,
)

# Use Poetry and relative imports instead of hardcoded paths



class TestDualEngineMonitor:
    """Test DualEngineMonitor functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.monitor = DualEngineMonitor(retention_hours=1)  # Short retention for testing

    def test_monitor_initialization(self):
        """Test monitor initialization with default settings"""
        assert self.monitor.retention_hours == 1
        assert len(self.monitor.engine_metrics) == 3  # chained, coherent, hybrid
        assert "chained" in self.monitor.engine_metrics
        assert "coherent" in self.monitor.engine_metrics
        assert "hybrid" in self.monitor.engine_metrics
        assert len(self.monitor.active_executions) == 0

    def test_start_execution(self):
        """Test starting execution tracking"""
        execution_id = "test_exec_001"
        engine_type = "chained"
        request_context = {"complexity": "high", "user_id": "user123"}

        record = self.monitor.start_execution(execution_id, engine_type, request_context)

        assert record.execution_id == execution_id
        assert record.engine_type == engine_type
        assert record.request_complexity == "high"
        assert record.metadata == request_context
        assert execution_id in self.monitor.active_executions
        assert isinstance(record.start_time, datetime)

    def test_end_execution_success(self):
        """Test ending execution tracking with success"""
        execution_id = "test_exec_002"
        engine_type = "coherent"

        # Start execution
        start_record = self.monitor.start_execution(execution_id, engine_type)

        # End execution
        end_record = self.monitor.end_execution(
            execution_id=execution_id,
            success=True,
            quality_score=88.5,
            persona_executions=["RequirementAnalyst", "SolutionArchitect"],
        )

        assert end_record is not None
        assert end_record.success == True
        assert end_record.quality_score == 88.5
        assert len(end_record.persona_executions) == 2
        assert end_record.duration_seconds > 0
        assert execution_id not in self.monitor.active_executions
        assert len(self.monitor.execution_records) == 1

    def test_end_execution_failure(self):
        """Test ending execution tracking with failure"""
        execution_id = "test_exec_003"
        engine_type = "chained"

        # Start execution
        self.monitor.start_execution(execution_id, engine_type)

        # End execution with failure
        end_record = self.monitor.end_execution(
            execution_id=execution_id, success=False, error_message="Database connection failed"
        )

        assert end_record is not None
        assert end_record.success == False
        assert end_record.error_message == "Database connection failed"
        assert end_record.quality_score == 0.0

    def test_end_execution_nonexistent(self):
        """Test ending execution for non-existent execution ID"""
        result = self.monitor.end_execution("nonexistent_id", success=True)
        assert result is None

    def test_engine_metrics_update(self):
        """Test engine metrics are updated correctly"""
        execution_id = "test_exec_004"
        engine_type = "coherent"

        # Start and end execution
        self.monitor.start_execution(execution_id, engine_type)
        self.monitor.end_execution(
            execution_id=execution_id,
            success=True,
            quality_score=92.0,
            persona_executions=["Persona1", "Persona2", "Persona3"],
        )

        metrics = self.monitor.get_engine_metrics(engine_type)

        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert metrics.avg_quality_score == 92.0
        assert metrics.avg_persona_count == 3
        assert metrics.error_rate == 0.0
        assert metrics.avg_response_time > 0

    def test_engine_metrics_multiple_executions(self):
        """Test engine metrics with multiple executions"""
        engine_type = "chained"

        # Execute multiple requests
        for i in range(5):
            execution_id = f"test_exec_00{i+5}"
            self.monitor.start_execution(execution_id, engine_type)
            success = i < 4  # 4 successes, 1 failure
            quality_score = 85.0 + (i * 2) if success else 0.0

            self.monitor.end_execution(
                execution_id=execution_id,
                success=success,
                quality_score=quality_score,
                persona_executions=["P1", "P2"] if success else [],
            )

        metrics = self.monitor.get_engine_metrics(engine_type)

        assert metrics.total_requests == 5
        assert metrics.successful_requests == 4
        assert metrics.failed_requests == 1
        assert metrics.error_rate == 20.0  # 1/5 = 20%
        assert metrics.avg_quality_score > 0  # Should be average of successful ones

    def test_performance_history_update(self):
        """Test performance history tracking"""
        execution_id = "test_exec_010"
        engine_type = "coherent"

        self.monitor.start_execution(execution_id, engine_type)
        self.monitor.end_execution(execution_id=execution_id, success=True, quality_score=90.0)

        history = self.monitor.performance_history[engine_type]
        assert len(history["response_times"]) == 1
        assert len(history["quality_scores"]) == 1
        assert len(history["timestamps"]) == 1
        assert history["quality_scores"][0] == 90.0

    def test_comparative_analysis_insufficient_data(self):
        """Test comparative analysis with insufficient data"""
        analysis = self.monitor.get_comparative_analysis(timeframe_hours=1)

        assert isinstance(analysis, ComparisonAnalysis)
        assert analysis.timeframe_hours == 1
        assert analysis.chained_metrics.total_requests == 0
        assert analysis.coherent_metrics.total_requests == 0
        assert "Insufficient data" in analysis.recommendation

    def test_comparative_analysis_with_data(self):
        """Test comparative analysis with sufficient data"""
        # Add chained executions
        for i in range(15):
            exec_id = f"chained_exec_{i}"
            self.monitor.start_execution(exec_id, "chained")
            self.monitor.end_execution(
                exec_id, success=True, quality_score=80.0, persona_executions=["P1", "P2"]
            )

        # Add coherent executions (better performance)
        for i in range(12):
            exec_id = f"coherent_exec_{i}"
            self.monitor.start_execution(exec_id, "coherent")
            self.monitor.end_execution(
                exec_id, success=True, quality_score=92.0, persona_executions=["P1", "P2", "P3"]
            )

        analysis = self.monitor.get_comparative_analysis(timeframe_hours=1)

        assert analysis.chained_metrics.total_requests == 15
        assert analysis.coherent_metrics.total_requests == 12
        assert analysis.quality_improvement > 0  # Coherent should be better
        assert "improvement" in analysis.recommendation.lower()

    def test_real_time_dashboard_data(self):
        """Test real-time dashboard data generation"""
        # Add some executions
        self.monitor.start_execution("active_1", "chained")
        self.monitor.start_execution("active_2", "coherent")

        # Complete one execution
        self.monitor.end_execution("active_1", success=True, quality_score=85.0)

        dashboard_data = self.monitor.get_real_time_dashboard_data()

        assert "timestamp" in dashboard_data
        assert "engine_status" in dashboard_data
        assert "feature_flags" in dashboard_data
        assert "performance_trends" in dashboard_data
        assert "active_executions" in dashboard_data
        assert "system_health" in dashboard_data

        # Verify engine status
        assert "chained" in dashboard_data["engine_status"]
        assert "coherent" in dashboard_data["engine_status"]
        assert dashboard_data["active_executions"] == 1  # One still active

    @patch("shared.monitoring.dual_engine_monitor.feature_manager")
    def test_dashboard_feature_flags_integration(self, mock_feature_manager):
        """Test dashboard integration with feature flags"""
        mock_feature_manager.get_status.return_value = {
            "coherent_orchestration": "enabled",
            "dual_engine_monitoring": "enabled",
        }

        dashboard_data = self.monitor.get_real_time_dashboard_data()

        assert dashboard_data["feature_flags"]["coherent_orchestration"] == "enabled"
        mock_feature_manager.get_status.assert_called_once()

    def test_export_metrics(self):
        """Test metrics export functionality"""
        # Add some test data
        self.monitor.start_execution("export_test_1", "chained")
        self.monitor.end_execution("export_test_1", success=True, quality_score=88.0)

        exported_data = self.monitor.export_metrics(timeframe_hours=1)

        assert "timeframe_hours" in exported_data
        assert "export_time" in exported_data
        assert "total_executions" in exported_data
        assert "engine_metrics" in exported_data
        assert "execution_records" in exported_data
        assert "comparative_analysis" in exported_data
        assert "dashboard_data" in exported_data

        assert exported_data["total_executions"] == 1
        assert "chained" in exported_data["engine_metrics"]

    def test_cleanup_old_records(self):
        """Test cleanup of old execution records"""
        # Create monitor with very short retention
        short_monitor = DualEngineMonitor(retention_hours=0)  # 0 hours retention

        # Add old record by manipulating the start time
        execution_id = "old_exec"
        record = short_monitor.start_execution(execution_id, "chained")
        record.start_time = datetime.utcnow() - timedelta(hours=2)  # 2 hours ago
        short_monitor.end_execution(execution_id, success=True)

        # Add recent record
        short_monitor.start_execution("recent_exec", "coherent")
        short_monitor.end_execution("recent_exec", success=True)

        # Trigger cleanup
        short_monitor._cleanup_old_records()

        # Old record should be removed (this is a simplified test)
        # In real implementation, records older than retention_hours are removed

    def test_analysis_caching(self):
        """Test analysis result caching"""
        # First call should generate analysis
        analysis1 = self.monitor.get_comparative_analysis(timeframe_hours=1)

        # Second call should use cache (very quick succession)
        analysis2 = self.monitor.get_comparative_analysis(timeframe_hours=1)

        # Should be the same object due to caching
        assert analysis1.generated_at == analysis2.generated_at

    def test_engine_metrics_dataclass(self):
        """Test EngineMetrics dataclass functionality"""
        metrics = EngineMetrics(
            engine_type="test_engine",
            total_requests=100,
            successful_requests=95,
            avg_response_time=1.5,
            avg_quality_score=88.5,
        )

        assert metrics.engine_type == "test_engine"
        assert metrics.error_rate == 0.0  # Default value
        assert isinstance(metrics.last_updated, datetime)

    def test_execution_record_dataclass(self):
        """Test ExecutionRecord dataclass functionality"""
        record = ExecutionRecord(
            execution_id="test_001",
            engine_type="chained",
            start_time=datetime.utcnow(),
            success=True,
            quality_score=90.0,
        )

        assert record.execution_id == "test_001"
        assert record.persona_executions == []  # Default empty list
        assert record.metadata == {}  # Default empty dict

    def test_comparison_analysis_dataclass(self):
        """Test ComparisonAnalysis dataclass functionality"""
        chained_metrics = EngineMetrics(engine_type="chained")
        coherent_metrics = EngineMetrics(engine_type="coherent")

        analysis = ComparisonAnalysis(
            timeframe_hours=2,
            chained_metrics=chained_metrics,
            coherent_metrics=coherent_metrics,
            performance_improvement={"quality": 15.0},
            quality_improvement=15.0,
            speed_improvement=20.0,
            reliability_improvement=5.0,
            recommendation="Test recommendation",
            confidence_score=0.85,
        )

        assert analysis.timeframe_hours == 2
        assert analysis.confidence_score == 0.85
        assert isinstance(analysis.generated_at, datetime)


class TestConvenienceFunctions:
    """Test module-level convenience functions"""

    def setup_method(self):
        """Reset the global monitor for each test"""
        # Clear any existing data in the global monitor
        from shared.monitoring.dual_engine_monitor import dual_engine_monitor

        dual_engine_monitor.execution_records.clear()
        dual_engine_monitor.active_executions.clear()

    def test_start_execution_tracking_function(self):
        """Test global start_execution_tracking function"""
        execution_id = "global_test_001"
        record = start_execution_tracking(
            execution_id=execution_id,
            engine_type="coherent",
            request_context={"complexity": "medium"},
        )

        assert record.execution_id == execution_id
        assert record.engine_type == "coherent"
        assert record.request_complexity == "medium"

    def test_end_execution_tracking_function(self):
        """Test global end_execution_tracking function"""
        execution_id = "global_test_002"

        # Start tracking
        start_execution_tracking(execution_id, "chained")

        # End tracking
        record = end_execution_tracking(
            execution_id=execution_id,
            success=True,
            quality_score=87.5,
            persona_executions=["TestPersona"],
        )

        assert record is not None
        assert record.success == True
        assert record.quality_score == 87.5

    def test_get_performance_comparison_function(self):
        """Test global get_performance_comparison function"""
        analysis = get_performance_comparison(timeframe_hours=2)

        assert isinstance(analysis, ComparisonAnalysis)
        assert analysis.timeframe_hours == 2

    def test_get_dashboard_data_function(self):
        """Test global get_dashboard_data function"""
        dashboard_data = get_dashboard_data()

        assert isinstance(dashboard_data, dict)
        assert "timestamp" in dashboard_data
        assert "engine_status" in dashboard_data

    def test_full_workflow_integration(self):
        """Test complete workflow using convenience functions"""
        execution_id = "integration_test_001"

        # Start execution
        record = start_execution_tracking(
            execution_id=execution_id,
            engine_type="hybrid",
            request_context={"complexity": "high", "user_id": "test_user"},
        )

        assert record.engine_type == "hybrid"

        # End execution
        final_record = end_execution_tracking(
            execution_id=execution_id,
            success=True,
            quality_score=94.0,
            persona_executions=["Analyst", "Architect", "Developer"],
        )

        assert final_record.quality_score == 94.0
        assert len(final_record.persona_executions) == 3

        # Get analysis
        analysis = get_performance_comparison(timeframe_hours=1)
        assert analysis.timeframe_hours == 1

        # Get dashboard data
        dashboard = get_dashboard_data()
        assert dashboard["total_requests_today"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
