"""
Unit tests for AutoRollbackService.

Tests cover:
- Threshold configuration
- Deployment monitoring start/stop
- Health check recording
- Health evaluation logic
- Rollback triggering
- Notification handling
- Statistics and history
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import pytest

from src.services.auto_rollback_service import (
    AutoRollbackService,
    DeploymentMonitor,
    HealthCheckResult,
    HealthStatus,
    RollbackEvent,
    RollbackReason,
    RollbackStatus,
    RollbackThresholds,
    get_auto_rollback_service,
)


@pytest.fixture
def service():
    """Create a fresh AutoRollbackService instance for testing."""
    svc = AutoRollbackService()
    svc.reset()
    return svc


@pytest.fixture
def sample_thresholds():
    """Sample rollback thresholds."""
    return RollbackThresholds(
        consecutive_failures=3,
        failure_window_seconds=60,
        error_rate_threshold=0.05,
        latency_p99_threshold_ms=5000.0,
        memory_threshold_percent=90.0,
        cpu_threshold_percent=85.0,
        health_check_interval_seconds=10,
        stabilization_period_seconds=30,
        rollback_cooldown_seconds=300,
    )


@pytest.fixture
def sample_monitor(service, sample_thresholds):
    """Create a sample deployment monitor."""
    return service.start_monitoring(
        deployment_id="deploy-001",
        service_name="api-service",
        environment="production",
        current_version="2.0.0",
        previous_version="1.9.0",
        thresholds=sample_thresholds,
    )


class TestRollbackThresholds:
    """Tests for RollbackThresholds configuration."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = RollbackThresholds()
        assert thresholds.consecutive_failures == 3
        assert thresholds.failure_window_seconds == 60
        assert thresholds.error_rate_threshold == 0.05
        assert thresholds.latency_p99_threshold_ms == 5000.0
        assert thresholds.memory_threshold_percent == 90.0
        assert thresholds.cpu_threshold_percent == 85.0
        assert thresholds.health_check_interval_seconds == 10
        assert thresholds.stabilization_period_seconds == 60
        assert thresholds.rollback_cooldown_seconds == 300

    def test_custom_thresholds(self, sample_thresholds):
        """Test custom threshold values."""
        assert sample_thresholds.consecutive_failures == 3
        assert sample_thresholds.stabilization_period_seconds == 30


class TestServiceConfiguration:
    """Tests for service configuration."""

    def test_configure_thresholds_with_object(self, service, sample_thresholds):
        """Test configuring thresholds with a RollbackThresholds object."""
        result = service.configure_thresholds(sample_thresholds)
        assert result.consecutive_failures == 3
        assert result.stabilization_period_seconds == 30

    def test_configure_thresholds_with_kwargs(self, service):
        """Test configuring thresholds with keyword arguments."""
        result = service.configure_thresholds(
            consecutive_failures=5,
            error_rate_threshold=0.10,
        )
        assert result.consecutive_failures == 5
        assert result.error_rate_threshold == 0.10

    def test_register_notification_handler(self, service):
        """Test registering a notification handler."""
        handler = MagicMock()
        service.register_notification_handler(handler)
        assert len(service._notification_handlers) == 1

    def test_register_rollback_executor(self, service):
        """Test registering a rollback executor."""
        executor = MagicMock(return_value=True)
        service.register_rollback_executor(executor)
        assert service._rollback_executor == executor

    def test_register_health_checker(self, service):
        """Test registering a health checker."""
        checker = MagicMock()
        service.register_health_checker(checker)
        assert service._health_checker == checker


class TestDeploymentMonitoring:
    """Tests for deployment monitoring."""

    def test_start_monitoring(self, service, sample_thresholds):
        """Test starting deployment monitoring."""
        monitor = service.start_monitoring(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            current_version="2.0.0",
            previous_version="1.9.0",
            thresholds=sample_thresholds,
        )

        assert isinstance(monitor, DeploymentMonitor)
        assert monitor.deployment_id == "deploy-001"
        assert monitor.service_name == "api-service"
        assert monitor.environment == "production"
        assert monitor.current_version == "2.0.0"
        assert monitor.previous_version == "1.9.0"
        assert monitor.is_monitoring is True
        assert monitor.rollback_triggered is False

    def test_start_monitoring_default_thresholds(self, service):
        """Test starting monitoring with default thresholds."""
        monitor = service.start_monitoring(
            deployment_id="deploy-002",
            service_name="api-service",
            environment="staging",
            current_version="2.0.0",
            previous_version="1.9.0",
        )

        assert monitor.thresholds.consecutive_failures == 3

    def test_stop_monitoring(self, service, sample_monitor):
        """Test stopping deployment monitoring."""
        result = service.stop_monitoring("deploy-001")
        assert result is True
        assert sample_monitor.is_monitoring is False

    def test_stop_monitoring_not_found(self, service):
        """Test stopping monitoring for non-existent deployment."""
        result = service.stop_monitoring("nonexistent")
        assert result is False

    def test_get_monitor(self, service, sample_monitor):
        """Test getting a deployment monitor."""
        monitor = service.get_monitor("deploy-001")
        assert monitor == sample_monitor

    def test_get_monitor_not_found(self, service):
        """Test getting a non-existent monitor."""
        monitor = service.get_monitor("nonexistent")
        assert monitor is None

    def test_get_active_monitors(self, service, sample_monitor):
        """Test getting active monitors."""
        service.start_monitoring(
            deployment_id="deploy-002",
            service_name="web-service",
            environment="staging",
            current_version="1.0.0",
            previous_version="0.9.0",
        )

        active = service.get_active_monitors()
        assert len(active) == 2

        service.stop_monitoring("deploy-001")
        active = service.get_active_monitors()
        assert len(active) == 1


class TestHealthCheckRecording:
    """Tests for health check recording."""

    def test_record_health_check_healthy(self, service, sample_monitor):
        """Test recording a healthy check."""
        result = service.record_health_check(
            deployment_id="deploy-001",
            status=HealthStatus.HEALTHY,
            latency_ms=150.0,
            error_rate=0.01,
        )

        assert isinstance(result, HealthCheckResult)
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms == 150.0
        assert result.error_rate == 0.01
        assert len(sample_monitor.health_checks) == 1

    def test_record_health_check_unhealthy(self, service, sample_monitor):
        """Test recording an unhealthy check."""
        result = service.record_health_check(
            deployment_id="deploy-001",
            status=HealthStatus.UNHEALTHY,
            error_rate=0.15,
        )

        assert result.status == HealthStatus.UNHEALTHY
        assert result.is_healthy() is False

    def test_record_health_check_with_resources(self, service, sample_monitor):
        """Test recording a check with resource metrics."""
        result = service.record_health_check(
            deployment_id="deploy-001",
            status=HealthStatus.DEGRADED,
            memory_percent=85.0,
            cpu_percent=70.0,
        )

        assert result.memory_percent == 85.0
        assert result.cpu_percent == 70.0

    def test_record_health_check_with_details(self, service, sample_monitor):
        """Test recording a check with custom details."""
        details = {"endpoint": "/health", "response_code": 200}
        result = service.record_health_check(
            deployment_id="deploy-001",
            status=HealthStatus.HEALTHY,
            details=details,
        )

        assert result.details == details

    def test_record_health_check_not_found(self, service):
        """Test recording for non-existent deployment."""
        result = service.record_health_check(
            deployment_id="nonexistent",
            status=HealthStatus.HEALTHY,
        )
        assert result is None


class TestHealthEvaluation:
    """Tests for health evaluation logic."""

    def test_evaluate_health_not_found(self, service):
        """Test evaluating non-existent deployment."""
        result = service.evaluate_health("nonexistent")
        assert result["status"] == "not_found"
        assert result["should_rollback"] is False

    def test_evaluate_health_no_data(self, service, sample_monitor):
        """Test evaluating with no health checks."""
        result = service.evaluate_health("deploy-001")
        assert result["status"] == "no_data"
        assert result["should_rollback"] is False

    def test_evaluate_health_healthy(self, service, sample_monitor):
        """Test evaluating healthy deployment."""
        # Record several healthy checks
        for _ in range(5):
            service.record_health_check(
                deployment_id="deploy-001",
                status=HealthStatus.HEALTHY,
                latency_ms=100.0,
                error_rate=0.01,
            )

        result = service.evaluate_health("deploy-001")
        assert result["status"] == "healthy"
        assert result["should_rollback"] is False

    def test_evaluate_health_consecutive_failures(self, service, sample_monitor):
        """Test evaluation triggers rollback on consecutive failures."""
        # Record consecutive unhealthy checks
        for _ in range(3):
            service.record_health_check(
                deployment_id="deploy-001",
                status=HealthStatus.UNHEALTHY,
            )

        result = service.evaluate_health("deploy-001")
        assert result["status"] == "unhealthy"
        assert result["should_rollback"] is True
        assert result["reason"] == RollbackReason.HEALTH_CHECK_FAILED
        assert result["consecutive_failures"] == 3

    def test_evaluate_health_error_rate_exceeded(self, service, sample_monitor):
        """Test evaluation triggers rollback on high error rate."""
        # Record checks with high error rate
        for _ in range(5):
            service.record_health_check(
                deployment_id="deploy-001",
                status=HealthStatus.DEGRADED,
                error_rate=0.10,  # 10% error rate
            )

        result = service.evaluate_health("deploy-001")
        assert result["should_rollback"] is True
        assert result["reason"] == RollbackReason.ERROR_RATE_EXCEEDED
        assert result["error_rate"] == 0.10

    def test_evaluate_health_latency_exceeded(self, service, sample_monitor):
        """Test evaluation triggers rollback on high latency."""
        # Record checks with high latency
        for _ in range(10):
            service.record_health_check(
                deployment_id="deploy-001",
                status=HealthStatus.HEALTHY,
                latency_ms=6000.0,  # Above 5000ms threshold
            )

        result = service.evaluate_health("deploy-001")
        assert result["should_rollback"] is True
        assert result["reason"] == RollbackReason.LATENCY_EXCEEDED

    def test_evaluate_health_memory_exceeded(self, service, sample_monitor):
        """Test evaluation triggers rollback on high memory usage."""
        # Record checks with high memory
        for _ in range(5):
            service.record_health_check(
                deployment_id="deploy-001",
                status=HealthStatus.HEALTHY,
                memory_percent=95.0,  # Above 90% threshold
            )

        result = service.evaluate_health("deploy-001")
        assert result["should_rollback"] is True
        assert result["reason"] == RollbackReason.MEMORY_EXCEEDED

    def test_evaluate_health_cpu_exceeded(self, service, sample_monitor):
        """Test evaluation triggers rollback on high CPU usage."""
        # Record checks with high CPU
        for _ in range(5):
            service.record_health_check(
                deployment_id="deploy-001",
                status=HealthStatus.HEALTHY,
                cpu_percent=90.0,  # Above 85% threshold
            )

        result = service.evaluate_health("deploy-001")
        assert result["should_rollback"] is True
        assert result["reason"] == RollbackReason.CPU_EXCEEDED

    def test_evaluate_health_in_cooldown(self, service, sample_monitor):
        """Test evaluation respects cooldown period."""
        # Manually set last rollback time
        sample_monitor.last_rollback_at = datetime.utcnow()

        # Record unhealthy checks
        for _ in range(5):
            service.record_health_check(
                deployment_id="deploy-001",
                status=HealthStatus.UNHEALTHY,
            )

        result = service.evaluate_health("deploy-001")
        assert result["status"] == "cooldown"
        assert result["should_rollback"] is False


class TestRollbackTriggering:
    """Tests for rollback triggering."""

    def test_trigger_rollback_success(self, service, sample_monitor):
        """Test triggering a rollback."""
        executor = MagicMock(return_value=True)
        service.register_rollback_executor(executor)

        event = service.trigger_rollback(
            deployment_id="deploy-001",
            reason=RollbackReason.HEALTH_CHECK_FAILED,
        )

        assert isinstance(event, RollbackEvent)
        assert event.deployment_id == "deploy-001"
        assert event.service_name == "api-service"
        assert event.from_version == "2.0.0"
        assert event.to_version == "1.9.0"
        assert event.reason == RollbackReason.HEALTH_CHECK_FAILED
        assert event.status == RollbackStatus.COMPLETED
        assert event.completed_at is not None
        executor.assert_called_once()

    def test_trigger_rollback_failure(self, service, sample_monitor):
        """Test handling rollback executor failure."""
        executor = MagicMock(return_value=False)
        service.register_rollback_executor(executor)

        event = service.trigger_rollback(
            deployment_id="deploy-001",
            reason=RollbackReason.ERROR_RATE_EXCEEDED,
        )

        assert event.status == RollbackStatus.FAILED
        assert event.error_message is not None

    def test_trigger_rollback_executor_exception(self, service, sample_monitor):
        """Test handling rollback executor exception."""
        executor = MagicMock(side_effect=Exception("Deployment failed"))
        service.register_rollback_executor(executor)

        event = service.trigger_rollback(
            deployment_id="deploy-001",
            reason=RollbackReason.HEALTH_CHECK_FAILED,
        )

        assert event.status == RollbackStatus.FAILED
        assert "Deployment failed" in event.error_message

    def test_trigger_rollback_not_found(self, service):
        """Test triggering rollback for non-existent deployment."""
        event = service.trigger_rollback(
            deployment_id="nonexistent",
            reason=RollbackReason.HEALTH_CHECK_FAILED,
        )
        assert event is None

    def test_trigger_rollback_already_triggered(self, service, sample_monitor):
        """Test preventing duplicate rollbacks."""
        executor = MagicMock(return_value=True)
        service.register_rollback_executor(executor)

        # First rollback
        event1 = service.trigger_rollback(
            deployment_id="deploy-001",
            reason=RollbackReason.HEALTH_CHECK_FAILED,
        )
        assert event1 is not None

        # Second rollback attempt
        event2 = service.trigger_rollback(
            deployment_id="deploy-001",
            reason=RollbackReason.ERROR_RATE_EXCEEDED,
        )
        assert event2 is None

    def test_trigger_rollback_without_executor(self, service, sample_monitor):
        """Test triggering rollback without executor."""
        event = service.trigger_rollback(
            deployment_id="deploy-001",
            reason=RollbackReason.HEALTH_CHECK_FAILED,
        )

        assert event is not None
        assert event.status == RollbackStatus.PENDING


class TestNotifications:
    """Tests for notification handling."""

    def test_notification_sent_on_rollback(self, service, sample_monitor):
        """Test notifications are sent on rollback."""
        handler1 = MagicMock()
        handler1.__name__ = "handler1"
        handler2 = MagicMock()
        handler2.__name__ = "handler2"

        service.register_notification_handler(handler1)
        service.register_notification_handler(handler2)

        event = service.trigger_rollback(
            deployment_id="deploy-001",
            reason=RollbackReason.HEALTH_CHECK_FAILED,
        )

        handler1.assert_called_once_with(event)
        handler2.assert_called_once_with(event)
        assert "handler1" in event.notifications_sent
        assert "handler2" in event.notifications_sent

    def test_notification_handler_failure_doesnt_break_rollback(self, service, sample_monitor):
        """Test that failing notification doesn't break rollback."""
        failing_handler = MagicMock(side_effect=Exception("Notification failed"))
        failing_handler.__name__ = "failing_handler"
        working_handler = MagicMock()
        working_handler.__name__ = "working_handler"

        service.register_notification_handler(failing_handler)
        service.register_notification_handler(working_handler)

        event = service.trigger_rollback(
            deployment_id="deploy-001",
            reason=RollbackReason.HEALTH_CHECK_FAILED,
        )

        assert event is not None
        working_handler.assert_called_once()


class TestRollbackHistory:
    """Tests for rollback history."""

    def test_get_rollback_history(self, service, sample_monitor):
        """Test getting rollback history."""
        service.trigger_rollback("deploy-001", RollbackReason.HEALTH_CHECK_FAILED)

        # Create another monitor and rollback
        service.start_monitoring(
            deployment_id="deploy-002",
            service_name="web-service",
            environment="staging",
            current_version="1.0.0",
            previous_version="0.9.0",
        )
        service.trigger_rollback("deploy-002", RollbackReason.ERROR_RATE_EXCEEDED)

        history = service.get_rollback_history()
        assert len(history) == 2

    def test_get_rollback_history_filter_by_service(self, service, sample_monitor):
        """Test filtering history by service."""
        service.trigger_rollback("deploy-001", RollbackReason.HEALTH_CHECK_FAILED)

        service.start_monitoring(
            deployment_id="deploy-002",
            service_name="web-service",
            environment="production",
            current_version="1.0.0",
            previous_version="0.9.0",
        )
        service.trigger_rollback("deploy-002", RollbackReason.ERROR_RATE_EXCEEDED)

        history = service.get_rollback_history(service_name="api-service")
        assert len(history) == 1
        assert history[0].service_name == "api-service"

    def test_get_rollback_history_filter_by_environment(self, service, sample_monitor):
        """Test filtering history by environment."""
        service.trigger_rollback("deploy-001", RollbackReason.HEALTH_CHECK_FAILED)

        service.start_monitoring(
            deployment_id="deploy-002",
            service_name="web-service",
            environment="staging",
            current_version="1.0.0",
            previous_version="0.9.0",
        )
        service.trigger_rollback("deploy-002", RollbackReason.ERROR_RATE_EXCEEDED)

        history = service.get_rollback_history(environment="production")
        assert len(history) == 1
        assert history[0].environment == "production"

    def test_get_rollback_history_limit(self, service):
        """Test history limit."""
        for i in range(5):
            service.start_monitoring(
                deployment_id=f"deploy-{i:03d}",
                service_name="api-service",
                environment="production",
                current_version="2.0.0",
                previous_version="1.9.0",
            )
            service.trigger_rollback(f"deploy-{i:03d}", RollbackReason.HEALTH_CHECK_FAILED)

        history = service.get_rollback_history(limit=3)
        assert len(history) == 3


class TestStatistics:
    """Tests for rollback statistics."""

    def test_get_statistics_empty(self, service):
        """Test statistics with no rollbacks."""
        stats = service.get_statistics()
        assert stats["total_rollbacks"] == 0
        assert stats["success_rate"] == 0.0

    def test_get_statistics_with_rollbacks(self, service):
        """Test statistics with rollbacks."""
        # Successful rollback
        executor = MagicMock(return_value=True)
        service.register_rollback_executor(executor)

        service.start_monitoring(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            current_version="2.0.0",
            previous_version="1.9.0",
        )
        service.trigger_rollback("deploy-001", RollbackReason.HEALTH_CHECK_FAILED)

        # Failed rollback
        executor.return_value = False
        service.start_monitoring(
            deployment_id="deploy-002",
            service_name="web-service",
            environment="staging",
            current_version="1.0.0",
            previous_version="0.9.0",
        )
        service.trigger_rollback("deploy-002", RollbackReason.ERROR_RATE_EXCEEDED)

        stats = service.get_statistics()
        assert stats["total_rollbacks"] == 2
        assert stats["successful_rollbacks"] == 1
        assert stats["failed_rollbacks"] == 1
        assert stats["success_rate"] == 0.5
        assert "health_check_failed" in stats["by_reason"]
        assert "error_rate_exceeded" in stats["by_reason"]
        assert "api-service" in stats["by_service"]
        assert "web-service" in stats["by_service"]

    def test_get_statistics_filter_by_service(self, service, sample_monitor):
        """Test statistics filtered by service."""
        service.trigger_rollback("deploy-001", RollbackReason.HEALTH_CHECK_FAILED)

        service.start_monitoring(
            deployment_id="deploy-002",
            service_name="web-service",
            environment="production",
            current_version="1.0.0",
            previous_version="0.9.0",
        )
        service.trigger_rollback("deploy-002", RollbackReason.ERROR_RATE_EXCEEDED)

        stats = service.get_statistics(service_name="api-service")
        assert stats["total_rollbacks"] == 1

    def test_get_statistics_filter_by_time(self, service, sample_monitor):
        """Test statistics filtered by time."""
        service.trigger_rollback("deploy-001", RollbackReason.HEALTH_CHECK_FAILED)

        # Stats from future should exclude current rollbacks
        future_time = datetime.utcnow() + timedelta(hours=1)
        stats = service.get_statistics(since=future_time)
        assert stats["total_rollbacks"] == 0


class TestAsyncMonitoring:
    """Tests for async monitoring functionality."""

    @pytest.mark.asyncio
    async def test_monitor_deployment_async_stops_on_rollback(self, service, sample_monitor):
        """Test async monitoring stops when rollback is triggered."""
        # Set up immediate failure
        sample_monitor.thresholds.stabilization_period_seconds = 0
        sample_monitor.thresholds.health_check_interval_seconds = 0.1

        # Set up health checker that always fails
        def failing_checker(deployment_id, service_name):
            return HealthCheckResult(
                check_id="check-1",
                deployment_id=deployment_id,
                timestamp=datetime.utcnow(),
                status=HealthStatus.UNHEALTHY,
            )

        service.register_health_checker(failing_checker)

        # Run monitoring (should trigger rollback quickly)
        task = asyncio.create_task(
            service.monitor_deployment_async("deploy-001", auto_rollback=True)
        )

        # Wait a short time for rollback
        await asyncio.sleep(0.5)

        # Task should complete due to rollback
        assert sample_monitor.rollback_triggered is True
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_monitor_deployment_async_cancelled(self, service, sample_monitor):
        """Test async monitoring can be cancelled."""
        sample_monitor.thresholds.stabilization_period_seconds = 0
        sample_monitor.thresholds.health_check_interval_seconds = 0.1

        task = asyncio.create_task(
            service.monitor_deployment_async("deploy-001", auto_rollback=False)
        )

        await asyncio.sleep(0.1)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_start_async_monitoring(self, service, sample_monitor):
        """Test starting async monitoring task."""
        task = service.start_async_monitoring("deploy-001")
        assert task is not None
        assert "deploy-001" in service._monitoring_tasks

        # Cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def test_start_async_monitoring_not_found(self, service):
        """Test starting async monitoring for non-existent deployment."""
        task = service.start_async_monitoring("nonexistent")
        assert task is None


class TestSingletonPattern:
    """Tests for singleton pattern."""

    def test_singleton_instance(self):
        """Test that service is a singleton."""
        service1 = AutoRollbackService()
        service2 = AutoRollbackService()
        assert service1 is service2

    def test_get_service_function(self):
        """Test get_auto_rollback_service function."""
        service = get_auto_rollback_service()
        assert isinstance(service, AutoRollbackService)


class TestReset:
    """Tests for service reset."""

    def test_reset_clears_all_state(self, service, sample_monitor):
        """Test reset clears all state."""
        handler = MagicMock()
        handler.__name__ = "test_handler"
        service.register_notification_handler(handler)
        service.register_rollback_executor(MagicMock())
        service.trigger_rollback("deploy-001", RollbackReason.HEALTH_CHECK_FAILED)

        service.reset()

        assert len(service._monitors) == 0
        assert len(service._rollback_history) == 0
        assert len(service._notification_handlers) == 0
        assert service._rollback_executor is None
        assert service._health_checker is None


class TestEdgeCases:
    """Tests for edge cases."""

    def test_evaluation_with_mixed_health_checks(self, service, sample_monitor):
        """Test evaluation with mixed healthy/unhealthy checks."""
        # Record mixed checks (healthy, unhealthy, healthy pattern)
        service.record_health_check("deploy-001", HealthStatus.HEALTHY)
        service.record_health_check("deploy-001", HealthStatus.UNHEALTHY)
        service.record_health_check("deploy-001", HealthStatus.HEALTHY)
        service.record_health_check("deploy-001", HealthStatus.UNHEALTHY)
        service.record_health_check("deploy-001", HealthStatus.HEALTHY)

        result = service.evaluate_health("deploy-001")
        # Should not trigger rollback (no 3 consecutive failures)
        assert result["should_rollback"] is False

    def test_evaluation_with_partial_metrics(self, service, sample_monitor):
        """Test evaluation with some metrics missing."""
        # Record checks with only some metrics
        service.record_health_check(
            "deploy-001",
            HealthStatus.HEALTHY,
            latency_ms=100.0,
            # No error_rate, memory, cpu
        )
        service.record_health_check(
            "deploy-001",
            HealthStatus.HEALTHY,
            error_rate=0.01,
            # No latency, memory, cpu
        )

        result = service.evaluate_health("deploy-001")
        assert result["status"] == "healthy"

    def test_rollback_custom_triggered_by(self, service, sample_monitor):
        """Test rollback with custom triggered_by value."""
        event = service.trigger_rollback(
            "deploy-001",
            RollbackReason.MANUAL_TRIGGER,
            triggered_by="ops_team",
        )

        assert event.triggered_by == "ops_team"

    def test_health_check_result_is_healthy_method(self):
        """Test HealthCheckResult.is_healthy method."""
        healthy = HealthCheckResult(
            check_id="1",
            deployment_id="deploy-001",
            timestamp=datetime.utcnow(),
            status=HealthStatus.HEALTHY,
        )
        assert healthy.is_healthy() is True

        unhealthy = HealthCheckResult(
            check_id="2",
            deployment_id="deploy-001",
            timestamp=datetime.utcnow(),
            status=HealthStatus.UNHEALTHY,
        )
        assert unhealthy.is_healthy() is False

        degraded = HealthCheckResult(
            check_id="3",
            deployment_id="deploy-001",
            timestamp=datetime.utcnow(),
            status=HealthStatus.DEGRADED,
        )
        assert degraded.is_healthy() is False
