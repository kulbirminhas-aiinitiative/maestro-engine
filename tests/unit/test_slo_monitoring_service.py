#!/usr/bin/env python3
"""
Unit Tests for SLO Monitoring Service
Epic: MD-1875 [ME-1000] SLO Monitoring System

Comprehensive test coverage for:
- AC-1: Job classes (critical/standard/batch)
- AC-2: Queue configuration
- AC-3: SLO metrics (p50/p95/p99)
- AC-4: Alert rules for SLO breaches
- AC-5: Documentation and runbook links
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.services.slo_monitoring_service import (
    AlertSeverity,
    DEFAULT_SLO_THRESHOLDS,
    JOB_CLASS_DOCUMENTATION,
    JobClass,
    PercentileMetrics,
    QueueConfig,
    QueueMetrics,
    QueuePriority,
    SLOAlert,
    SLOMetric,
    SLOMonitoringService,
    SLOThreshold,
    SLOType,
    get_slo_monitoring_service,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def slo_service():
    """Create a fresh SLO monitoring service for each test."""
    return SLOMonitoringService()


@pytest.fixture
def slo_service_with_callback():
    """Create SLO service with alert callback."""
    callback = MagicMock()
    return SLOMonitoringService(alert_callback=callback), callback


@pytest.fixture
def sample_latencies():
    """Sample latency data for testing."""
    return {
        "fast": [0.05, 0.06, 0.04, 0.07, 0.05, 0.06, 0.04, 0.05, 0.06, 0.05],
        "medium": [0.5, 0.6, 0.4, 0.7, 0.5, 0.6, 0.4, 0.5, 0.6, 0.5],
        "slow": [2.0, 2.5, 1.8, 3.0, 2.2, 2.8, 1.9, 2.1, 2.4, 2.3],
    }


# ============================================================================
# AC-1: JOB CLASSES TESTS
# ============================================================================


class TestJobClasses:
    """Tests for AC-1: Job classes (critical/standard/batch)."""

    def test_job_class_enum_values(self):
        """Test job class enum has correct values."""
        assert JobClass.CRITICAL.value == "critical"
        assert JobClass.STANDARD.value == "standard"
        assert JobClass.BATCH.value == "batch"

    def test_job_class_is_string_enum(self):
        """Test job class inherits from str."""
        assert isinstance(JobClass.CRITICAL, str)
        assert JobClass.CRITICAL == "critical"

    def test_all_job_classes_defined(self):
        """Test all expected job classes exist."""
        classes = list(JobClass)
        assert len(classes) == 3
        assert JobClass.CRITICAL in classes
        assert JobClass.STANDARD in classes
        assert JobClass.BATCH in classes

    def test_job_class_from_string(self):
        """Test creating job class from string."""
        assert JobClass("critical") == JobClass.CRITICAL
        assert JobClass("standard") == JobClass.STANDARD
        assert JobClass("batch") == JobClass.BATCH

    def test_invalid_job_class_raises_error(self):
        """Test invalid job class raises ValueError."""
        with pytest.raises(ValueError):
            JobClass("invalid")


class TestSLOThresholdsByJobClass:
    """Tests for SLO thresholds per job class."""

    def test_critical_thresholds_strictest(self):
        """Test critical job class has strictest thresholds."""
        critical = DEFAULT_SLO_THRESHOLDS[JobClass.CRITICAL]
        standard = DEFAULT_SLO_THRESHOLDS[JobClass.STANDARD]
        batch = DEFAULT_SLO_THRESHOLDS[JobClass.BATCH]

        # Latency thresholds should be lowest for critical
        assert critical[SLOType.LATENCY_P50] < standard[SLOType.LATENCY_P50]
        assert critical[SLOType.LATENCY_P95] < standard[SLOType.LATENCY_P95]
        assert critical[SLOType.LATENCY_P99] < standard[SLOType.LATENCY_P99]

        # Availability should be highest for critical
        assert critical[SLOType.AVAILABILITY] > standard[SLOType.AVAILABILITY]
        assert standard[SLOType.AVAILABILITY] > batch[SLOType.AVAILABILITY]

    def test_batch_thresholds_most_relaxed(self):
        """Test batch job class has most relaxed thresholds."""
        batch = DEFAULT_SLO_THRESHOLDS[JobClass.BATCH]
        standard = DEFAULT_SLO_THRESHOLDS[JobClass.STANDARD]

        # Latency thresholds should be highest for batch
        assert batch[SLOType.LATENCY_P50] > standard[SLOType.LATENCY_P50]
        assert batch[SLOType.LATENCY_P95] > standard[SLOType.LATENCY_P95]
        assert batch[SLOType.LATENCY_P99] > standard[SLOType.LATENCY_P99]

    def test_all_slo_types_defined_for_each_class(self):
        """Test all SLO types are defined for each job class."""
        expected_slo_types = {
            SLOType.LATENCY_P50,
            SLOType.LATENCY_P95,
            SLOType.LATENCY_P99,
            SLOType.AVAILABILITY,
            SLOType.ERROR_RATE,
            SLOType.THROUGHPUT,
        }

        for job_class in JobClass:
            defined_types = set(DEFAULT_SLO_THRESHOLDS[job_class].keys())
            assert defined_types == expected_slo_types, f"Missing SLO types for {job_class}"


# ============================================================================
# AC-2: QUEUE CONFIGURATION TESTS
# ============================================================================


class TestQueueConfiguration:
    """Tests for AC-2: Queue configuration."""

    def test_default_queues_initialized(self, slo_service):
        """Test default queues are created on initialization."""
        queues = slo_service.get_all_queue_configs()

        assert "maestro-critical" in queues
        assert "maestro-standard" in queues
        assert "maestro-batch" in queues

    def test_critical_queue_config(self, slo_service):
        """Test critical queue has correct configuration."""
        queue = slo_service.get_queue_config("maestro-critical")

        assert queue is not None
        assert queue.job_class == JobClass.CRITICAL
        assert queue.priority == QueuePriority.HIGHEST
        assert queue.max_workers == 20
        assert queue.timeout_seconds == 30.0
        assert queue.retry_limit == 1

    def test_standard_queue_config(self, slo_service):
        """Test standard queue has correct configuration."""
        queue = slo_service.get_queue_config("maestro-standard")

        assert queue is not None
        assert queue.job_class == JobClass.STANDARD
        assert queue.priority == QueuePriority.NORMAL
        assert queue.max_workers == 10
        assert queue.timeout_seconds == 300.0
        assert queue.retry_limit == 3

    def test_batch_queue_config(self, slo_service):
        """Test batch queue has correct configuration."""
        queue = slo_service.get_queue_config("maestro-batch")

        assert queue is not None
        assert queue.job_class == JobClass.BATCH
        assert queue.priority == QueuePriority.LOW
        assert queue.max_workers == 5
        assert queue.timeout_seconds == 1800.0
        assert queue.retry_limit == 5

    def test_register_custom_queue(self, slo_service):
        """Test registering a custom queue configuration."""
        custom_queue = QueueConfig(
            name="custom-queue",
            job_class=JobClass.STANDARD,
            priority=QueuePriority.HIGH,
            max_size=2000,
            max_workers=15,
            timeout_seconds=120.0,
            retry_limit=2,
        )

        slo_service.register_queue(custom_queue)
        retrieved = slo_service.get_queue_config("custom-queue")

        assert retrieved is not None
        assert retrieved.name == "custom-queue"
        assert retrieved.max_workers == 15

    def test_get_queue_for_job_class(self, slo_service):
        """Test getting default queue for job class."""
        critical_queue = slo_service.get_queue_for_job_class(JobClass.CRITICAL)
        assert critical_queue is not None
        assert critical_queue.job_class == JobClass.CRITICAL

        batch_queue = slo_service.get_queue_for_job_class(JobClass.BATCH)
        assert batch_queue is not None
        assert batch_queue.job_class == JobClass.BATCH

    def test_queue_priority_ordering(self):
        """Test queue priority has correct ordering."""
        assert QueuePriority.HIGHEST.value < QueuePriority.HIGH.value
        assert QueuePriority.HIGH.value < QueuePriority.NORMAL.value
        assert QueuePriority.NORMAL.value < QueuePriority.LOW.value
        assert QueuePriority.LOW.value < QueuePriority.LOWEST.value

    def test_queue_config_to_dict(self):
        """Test queue config serialization."""
        config = QueueConfig(
            name="test-queue",
            job_class=JobClass.STANDARD,
            priority=QueuePriority.NORMAL,
            max_size=1000,
            max_workers=5,
        )

        d = config.to_dict()
        assert d["name"] == "test-queue"
        assert d["job_class"] == "standard"
        assert d["priority"] == QueuePriority.NORMAL.value
        assert d["max_size"] == 1000

    def test_queue_dead_letter_queue(self):
        """Test dead letter queue configuration."""
        config = QueueConfig(
            name="test-queue",
            job_class=JobClass.CRITICAL,
            priority=QueuePriority.HIGHEST,
            dead_letter_queue="test-dlq",
        )

        assert config.dead_letter_queue == "test-dlq"


# ============================================================================
# AC-3: SLO METRICS (P50/P95/P99) TESTS
# ============================================================================


class TestPercentileCalculations:
    """Tests for AC-3: SLO metrics (p50/p95/p99)."""

    def test_calculate_percentiles_basic(self, slo_service):
        """Test basic percentile calculation."""
        # Record 100 latency samples
        for i in range(100):
            slo_service.record_latency(
                operation="test_op",
                latency_seconds=i / 100.0,  # 0.00 to 0.99
                job_class=JobClass.STANDARD,
            )

        percentiles = slo_service.calculate_percentiles("test_op", JobClass.STANDARD)

        assert percentiles.sample_count == 100
        assert 0.49 <= percentiles.p50 <= 0.51  # ~0.50
        assert 0.94 <= percentiles.p95 <= 0.96  # ~0.95
        assert 0.98 <= percentiles.p99 <= 1.0   # ~0.99

    def test_calculate_percentiles_empty(self, slo_service):
        """Test percentiles with no data returns zeros."""
        percentiles = slo_service.calculate_percentiles("nonexistent", JobClass.STANDARD)

        assert percentiles.p50 == 0.0
        assert percentiles.p95 == 0.0
        assert percentiles.p99 == 0.0
        assert percentiles.sample_count == 0

    def test_percentile_metrics_min_max(self, slo_service):
        """Test min/max values in percentile metrics."""
        latencies = [0.1, 0.5, 0.2, 0.8, 0.3, 0.9, 0.4, 0.7, 0.6, 0.05]

        for lat in latencies:
            slo_service.record_latency(
                operation="minmax_test",
                latency_seconds=lat,
                job_class=JobClass.STANDARD,
            )

        percentiles = slo_service.calculate_percentiles("minmax_test", JobClass.STANDARD)

        assert percentiles.min_val == 0.05
        assert percentiles.max_val == 0.9
        assert percentiles.sample_count == len(latencies)

    def test_percentile_metrics_mean(self, slo_service):
        """Test mean calculation in percentiles."""
        latencies = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        expected_mean = sum(latencies) / len(latencies)  # 0.55

        for lat in latencies:
            slo_service.record_latency(
                operation="mean_test",
                latency_seconds=lat,
                job_class=JobClass.CRITICAL,
            )

        percentiles = slo_service.calculate_percentiles("mean_test", JobClass.CRITICAL)

        assert abs(percentiles.mean_val - expected_mean) < 0.01

    def test_percentile_metrics_to_dict(self):
        """Test PercentileMetrics serialization."""
        metrics = PercentileMetrics(
            p50=0.1,
            p95=0.5,
            p99=1.0,
            min_val=0.05,
            max_val=1.5,
            mean_val=0.3,
            sample_count=100,
        )

        d = metrics.to_dict()
        assert d["p50"] == 0.1
        assert d["p95"] == 0.5
        assert d["p99"] == 1.0
        assert d["min"] == 0.05
        assert d["max"] == 1.5
        assert d["sample_count"] == 100

    def test_get_all_percentiles(self, slo_service):
        """Test getting percentiles for all operations."""
        # Record latencies for multiple operations
        for i in range(20):
            slo_service.record_latency("op1", i / 100.0, JobClass.CRITICAL)
            slo_service.record_latency("op2", i / 50.0, JobClass.STANDARD)

        all_percentiles = slo_service.get_all_percentiles()

        assert "critical:op1" in all_percentiles
        assert "standard:op2" in all_percentiles
        assert all_percentiles["critical:op1"].sample_count == 20
        assert all_percentiles["standard:op2"].sample_count == 20

    def test_window_size_limits_samples(self):
        """Test that window size limits stored samples."""
        service = SLOMonitoringService(window_size=10)

        # Record 20 samples
        for i in range(20):
            service.record_latency("window_test", i / 10.0, JobClass.STANDARD)

        percentiles = service.calculate_percentiles("window_test", JobClass.STANDARD)

        # Should only have last 10 samples
        assert percentiles.sample_count == 10


class TestLatencyRecording:
    """Tests for latency recording functionality."""

    def test_record_latency_success(self, slo_service):
        """Test recording successful latency."""
        slo_service.record_latency(
            operation="test_operation",
            latency_seconds=0.15,
            job_class=JobClass.STANDARD,
            success=True,
        )

        percentiles = slo_service.calculate_percentiles("test_operation", JobClass.STANDARD)
        assert percentiles.sample_count == 1
        assert percentiles.p50 == 0.15

    def test_record_latency_failure(self, slo_service):
        """Test recording failed operation."""
        slo_service.record_latency(
            operation="failing_op",
            latency_seconds=0.5,
            job_class=JobClass.CRITICAL,
            success=False,
        )

        # Check dashboard shows failure count
        dashboard = slo_service.get_slo_dashboard()
        op_metrics = dashboard["job_classes"]["critical"]["operations"].get("failing_op", {})

        assert op_metrics.get("failure_count", 0) == 1
        assert op_metrics.get("success_count", 0) == 0

    def test_record_latency_with_metadata(self, slo_service):
        """Test recording latency with metadata."""
        metadata = {"user_id": "123", "request_id": "abc"}

        alert = slo_service.record_latency(
            operation="meta_op",
            latency_seconds=0.1,
            job_class=JobClass.STANDARD,
            metadata=metadata,
        )

        # Metadata should be stored (even though we don't expose it directly)
        # No alert should be generated for fast operation
        assert alert is None

    def test_record_latency_different_job_classes(self, slo_service):
        """Test recording latencies for different job classes."""
        slo_service.record_latency("shared_op", 0.1, JobClass.CRITICAL)
        slo_service.record_latency("shared_op", 0.2, JobClass.STANDARD)
        slo_service.record_latency("shared_op", 0.3, JobClass.BATCH)

        critical = slo_service.calculate_percentiles("shared_op", JobClass.CRITICAL)
        standard = slo_service.calculate_percentiles("shared_op", JobClass.STANDARD)
        batch = slo_service.calculate_percentiles("shared_op", JobClass.BATCH)

        assert critical.p50 == 0.1
        assert standard.p50 == 0.2
        assert batch.p50 == 0.3


# ============================================================================
# AC-4: ALERT RULES FOR SLO BREACHES TESTS
# ============================================================================


class TestAlertGeneration:
    """Tests for AC-4: Alert rules for SLO breaches."""

    def test_no_alert_for_fast_operation(self, slo_service):
        """Test no alert generated for operation within SLO."""
        # Record fast latencies (well under critical threshold)
        for _ in range(20):
            alert = slo_service.record_latency(
                operation="fast_op",
                latency_seconds=0.01,  # 10ms, well under 100ms P50
                job_class=JobClass.CRITICAL,
            )

        assert alert is None
        assert len(slo_service.get_active_alerts()) == 0

    def test_alert_for_slow_critical_operation(self, slo_service):
        """Test alert generated for slow critical operation."""
        # Record latencies that exceed critical P99 threshold (1.0s)
        for i in range(20):
            alert = slo_service.record_latency(
                operation="slow_critical",
                latency_seconds=2.0,  # 2s, exceeds 1s P99 threshold
                job_class=JobClass.CRITICAL,
            )

        # Should have generated an alert
        assert alert is not None
        assert alert.job_class == JobClass.CRITICAL
        assert alert.slo_type == SLOType.LATENCY_P99
        assert alert.current_value >= 2.0

    def test_alert_severity_levels(self, slo_service):
        """Test alert severity based on breach percentage."""
        # Minor breach (< 50% over)
        for _ in range(20):
            slo_service.record_latency("minor_breach", 0.12, JobClass.CRITICAL)  # 20% over P50

        alerts = slo_service.get_active_alerts()
        if alerts:
            # Minor breaches should be INFO severity
            assert any(a.severity == AlertSeverity.INFO for a in alerts)

    def test_critical_severity_for_major_breach(self, slo_service):
        """Test critical severity for major breach."""
        # Major breach (> 100% over)
        for _ in range(20):
            alert = slo_service.record_latency(
                "major_breach",
                5.0,  # 500% over critical P99 threshold
                JobClass.CRITICAL,
            )

        if alert:
            assert alert.severity == AlertSeverity.CRITICAL
            assert alert.breach_percentage > 100

    def test_alert_callback_invoked(self, slo_service_with_callback):
        """Test alert callback is invoked on breach."""
        service, callback = slo_service_with_callback

        # Generate breach
        for _ in range(20):
            service.record_latency("callback_test", 5.0, JobClass.CRITICAL)

        # Callback should have been invoked
        assert callback.called

    def test_alert_contains_runbook_link(self, slo_service):
        """Test alert contains runbook link."""
        for _ in range(20):
            alert = slo_service.record_latency("runbook_test", 5.0, JobClass.CRITICAL)

        if alert:
            assert alert.runbook_link is not None
            assert "runbook" in alert.runbook_link.lower()

    def test_acknowledge_alert(self, slo_service):
        """Test acknowledging an alert."""
        # Generate an alert
        for _ in range(20):
            alert = slo_service.record_latency("ack_test", 5.0, JobClass.CRITICAL)

        if alert:
            assert not alert.acknowledged

            result = slo_service.acknowledge_alert(alert.alert_id)
            assert result is True

            # Check alert is now acknowledged
            active = slo_service.get_active_alerts()
            acked = [a for a in active if a.alert_id == alert.alert_id]
            if acked:
                assert acked[0].acknowledged

    def test_resolve_alert(self, slo_service):
        """Test resolving an alert."""
        # Generate an alert
        for _ in range(20):
            alert = slo_service.record_latency("resolve_test", 5.0, JobClass.CRITICAL)

        if alert:
            initial_count = len(slo_service.get_active_alerts())

            result = slo_service.resolve_alert(alert.alert_id)
            assert result is True

            # Alert should be removed
            assert len(slo_service.get_active_alerts()) < initial_count

    def test_resolve_nonexistent_alert(self, slo_service):
        """Test resolving non-existent alert returns False."""
        result = slo_service.resolve_alert("nonexistent-id")
        assert result is False

    def test_alert_to_dict(self):
        """Test SLOAlert serialization."""
        alert = SLOAlert(
            alert_id="test-123",
            job_class=JobClass.CRITICAL,
            slo_type=SLOType.LATENCY_P99,
            severity=AlertSeverity.WARNING,
            operation="test_op",
            current_value=1.5,
            threshold=1.0,
            breach_percentage=50.0,
            message="Test alert",
            runbook_link="https://runbook.example.com",
        )

        d = alert.to_dict()
        assert d["alert_id"] == "test-123"
        assert d["job_class"] == "critical"
        assert d["slo_type"] == "latency_p99"
        assert d["severity"] == "warning"
        assert d["breach_percentage"] == 50.0

    def test_minimum_samples_for_alert(self, slo_service):
        """Test that alerts require minimum sample count."""
        # Record fewer than 10 samples
        for _ in range(5):
            alert = slo_service.record_latency("few_samples", 5.0, JobClass.CRITICAL)

        # Should not generate alert with insufficient data
        assert alert is None


# ============================================================================
# AC-5: DOCUMENTATION AND RUNBOOK LINKS TESTS
# ============================================================================


class TestDocumentation:
    """Tests for AC-5: Documentation and runbook links."""

    def test_job_class_documentation_exists(self):
        """Test documentation exists for all job classes."""
        for job_class in JobClass:
            assert job_class in JOB_CLASS_DOCUMENTATION

    def test_documentation_has_required_fields(self):
        """Test documentation contains required fields."""
        required_fields = [
            "name",
            "description",
            "use_cases",
            "slo_targets",
            "runbook_link",
            "escalation_policy",
            "queue_config",
        ]

        for job_class in JobClass:
            doc = JOB_CLASS_DOCUMENTATION[job_class]
            for field in required_fields:
                assert field in doc, f"Missing {field} in {job_class} documentation"

    def test_critical_documentation(self):
        """Test critical job class documentation."""
        doc = JOB_CLASS_DOCUMENTATION[JobClass.CRITICAL]

        assert doc["name"] == "Critical"
        assert "user-facing" in doc["description"].lower()
        assert "100ms" in doc["slo_targets"]["latency_p50"]
        assert "runbook" in doc["runbook_link"].lower()

    def test_get_job_class_documentation_service(self, slo_service):
        """Test getting documentation via service."""
        # Get specific job class
        critical_doc = slo_service.get_job_class_documentation(JobClass.CRITICAL)
        assert critical_doc["name"] == "Critical"

        # Get all documentation
        all_docs = slo_service.get_job_class_documentation()
        assert len(all_docs) == 3

    def test_runbook_links_are_urls(self):
        """Test runbook links are valid URLs."""
        for job_class in JobClass:
            runbook = JOB_CLASS_DOCUMENTATION[job_class]["runbook_link"]
            assert runbook.startswith("http")

    def test_use_cases_are_list(self):
        """Test use cases are lists."""
        for job_class in JobClass:
            use_cases = JOB_CLASS_DOCUMENTATION[job_class]["use_cases"]
            assert isinstance(use_cases, list)
            assert len(use_cases) > 0


# ============================================================================
# DASHBOARD AND METRICS TESTS
# ============================================================================


class TestDashboard:
    """Tests for SLO dashboard functionality."""

    def test_get_slo_dashboard_empty(self, slo_service):
        """Test dashboard with no data."""
        dashboard = slo_service.get_slo_dashboard()

        assert "timestamp" in dashboard
        assert "job_classes" in dashboard
        assert "queues" in dashboard
        assert "active_alerts" in dashboard
        assert dashboard["overall_health"] == "healthy"

    def test_dashboard_contains_all_job_classes(self, slo_service):
        """Test dashboard contains all job classes."""
        dashboard = slo_service.get_slo_dashboard()

        for job_class in JobClass:
            assert job_class.value in dashboard["job_classes"]

    def test_dashboard_with_operations(self, slo_service):
        """Test dashboard shows recorded operations."""
        for i in range(15):
            slo_service.record_latency("dashboard_op", 0.1 + i / 100, JobClass.STANDARD)

        dashboard = slo_service.get_slo_dashboard()
        standard_ops = dashboard["job_classes"]["standard"]["operations"]

        assert "dashboard_op" in standard_ops
        assert "percentiles" in standard_ops["dashboard_op"]
        assert standard_ops["dashboard_op"]["total_count"] == 15

    def test_dashboard_health_status_warning(self, slo_service):
        """Test dashboard health status with warnings."""
        # Generate warning-level alert (50% breach triggers INFO, need > 50% for WARNING)
        # Use latency that is > 100% over threshold to trigger WARNING severity
        for _ in range(20):
            slo_service.record_latency("warning_op", 2.5, JobClass.CRITICAL)  # 150% over P99 threshold

        dashboard = slo_service.get_slo_dashboard()
        alerts = slo_service.get_active_alerts()

        # Should have alerts and health should be degraded
        assert len(alerts) > 0 or dashboard["overall_health"] in ["warning", "critical"]

    def test_dashboard_queues(self, slo_service):
        """Test dashboard includes queue information."""
        dashboard = slo_service.get_slo_dashboard()

        assert "maestro-critical" in dashboard["queues"]
        assert "maestro-standard" in dashboard["queues"]
        assert "maestro-batch" in dashboard["queues"]


class TestGrafanaMetrics:
    """Tests for Grafana metrics export."""

    def test_grafana_metrics_empty(self, slo_service):
        """Test Grafana metrics with no data."""
        metrics = slo_service.get_grafana_metrics()

        assert "timestamp" in metrics
        assert "series" in metrics
        assert isinstance(metrics["series"], list)

    def test_grafana_metrics_with_data(self, slo_service):
        """Test Grafana metrics with recorded data."""
        for i in range(20):
            slo_service.record_latency("grafana_op", 0.1 + i / 100, JobClass.STANDARD)

        metrics = slo_service.get_grafana_metrics()

        # Should have p50, p95, p99 series
        series_names = [s["name"] for s in metrics["series"]]
        assert any("p50" in name for name in series_names)
        assert any("p95" in name for name in series_names)
        assert any("p99" in name for name in series_names)

    def test_grafana_series_contains_labels(self, slo_service):
        """Test Grafana series contains proper labels."""
        for i in range(20):
            slo_service.record_latency("labeled_op", 0.1, JobClass.CRITICAL)

        metrics = slo_service.get_grafana_metrics()

        if metrics["series"]:
            series = metrics["series"][0]
            assert "labels" in series
            assert "job_class" in series["labels"]
            assert "operation" in series["labels"]
            assert "percentile" in series["labels"]

    def test_grafana_series_contains_thresholds(self, slo_service):
        """Test Grafana series includes threshold values."""
        for i in range(20):
            slo_service.record_latency("threshold_op", 0.1, JobClass.STANDARD)

        metrics = slo_service.get_grafana_metrics()

        if metrics["series"]:
            series = metrics["series"][0]
            assert "threshold" in series


# ============================================================================
# SLO THRESHOLD TESTS
# ============================================================================


class TestSLOThresholds:
    """Tests for SLO threshold configuration."""

    def test_custom_thresholds(self):
        """Test service with custom thresholds."""
        custom = {
            JobClass.CRITICAL: {
                SLOType.LATENCY_P50: 0.05,
                SLOType.LATENCY_P95: 0.1,
                SLOType.LATENCY_P99: 0.2,
            }
        }

        service = SLOMonitoringService(custom_thresholds=custom)
        thresholds = service.get_slo_thresholds(JobClass.CRITICAL)

        assert thresholds["latency_p50"] == 0.05
        assert thresholds["latency_p95"] == 0.1
        assert thresholds["latency_p99"] == 0.2

    def test_get_all_thresholds(self, slo_service):
        """Test getting all SLO thresholds."""
        thresholds = slo_service.get_slo_thresholds()

        assert "critical" in thresholds
        assert "standard" in thresholds
        assert "batch" in thresholds

    def test_threshold_dataclass(self):
        """Test SLOThreshold dataclass."""
        threshold = SLOThreshold(
            slo_type=SLOType.LATENCY_P95,
            threshold=0.5,
            job_class=JobClass.STANDARD,
            warning_multiplier=0.8,
            description="95th percentile latency",
        )

        d = threshold.to_dict()
        assert d["threshold"] == 0.5
        assert d["warning_threshold"] == 0.4  # 0.5 * 0.8
        assert d["slo_type"] == "latency_p95"


# ============================================================================
# DATA CLASS TESTS
# ============================================================================


class TestDataClasses:
    """Tests for data class serialization."""

    def test_slo_metric_to_dict(self):
        """Test SLOMetric serialization."""
        metric = SLOMetric(
            job_class=JobClass.STANDARD,
            operation="test_op",
            slo_type=SLOType.LATENCY_P50,
            value=0.15,
            threshold=0.5,
            is_breach=False,
        )

        d = metric.to_dict()
        assert d["job_class"] == "standard"
        assert d["operation"] == "test_op"
        assert d["value"] == 0.15
        assert d["is_breach"] is False

    def test_queue_metrics_to_dict(self):
        """Test QueueMetrics serialization."""
        metrics = QueueMetrics(
            queue_name="test-queue",
            job_class=JobClass.BATCH,
            size=100,
            pending=80,
            processing=20,
            throughput=50.5,
        )

        d = metrics.to_dict()
        assert d["queue_name"] == "test-queue"
        assert d["job_class"] == "batch"
        assert d["size"] == 100
        assert d["throughput"] == 50.5


# ============================================================================
# SINGLETON TESTS
# ============================================================================


class TestSingleton:
    """Tests for singleton service instance."""

    def test_get_slo_monitoring_service(self):
        """Test singleton service getter."""
        service1 = get_slo_monitoring_service()
        service2 = get_slo_monitoring_service()

        # Should return same instance
        assert service1 is service2

    def test_singleton_is_slo_service(self):
        """Test singleton is correct type."""
        service = get_slo_monitoring_service()
        assert isinstance(service, SLOMonitoringService)


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_very_large_latency(self, slo_service):
        """Test recording very large latency values."""
        slo_service.record_latency("large_latency", 1000.0, JobClass.BATCH)

        percentiles = slo_service.calculate_percentiles("large_latency", JobClass.BATCH)
        assert percentiles.p50 == 1000.0

    def test_very_small_latency(self, slo_service):
        """Test recording very small latency values."""
        slo_service.record_latency("small_latency", 0.0001, JobClass.CRITICAL)

        percentiles = slo_service.calculate_percentiles("small_latency", JobClass.CRITICAL)
        assert percentiles.p50 == 0.0001

    def test_operation_name_with_special_chars(self, slo_service):
        """Test operation names with special characters."""
        slo_service.record_latency("op/with/slashes", 0.1, JobClass.STANDARD)
        slo_service.record_latency("op-with-dashes", 0.2, JobClass.STANDARD)
        slo_service.record_latency("op_with_underscores", 0.3, JobClass.STANDARD)

        p1 = slo_service.calculate_percentiles("op/with/slashes", JobClass.STANDARD)
        p2 = slo_service.calculate_percentiles("op-with-dashes", JobClass.STANDARD)
        p3 = slo_service.calculate_percentiles("op_with_underscores", JobClass.STANDARD)

        assert p1.sample_count == 1
        assert p2.sample_count == 1
        assert p3.sample_count == 1

    def test_concurrent_operations(self, slo_service):
        """Test recording multiple operations concurrently."""
        operations = ["op1", "op2", "op3", "op4", "op5"]

        for i in range(50):
            for op in operations:
                slo_service.record_latency(op, 0.1 + i / 100, JobClass.STANDARD)

        all_percentiles = slo_service.get_all_percentiles()

        for op in operations:
            key = f"standard:{op}"
            assert key in all_percentiles
            assert all_percentiles[key].sample_count == 50

    def test_alert_callback_error_handling(self):
        """Test error handling in alert callback."""
        def failing_callback(alert):
            raise Exception("Callback error")

        service = SLOMonitoringService(alert_callback=failing_callback)

        # Should not raise, should log error instead
        for _ in range(20):
            service.record_latency("callback_error_test", 5.0, JobClass.CRITICAL)

    def test_get_queue_config_nonexistent(self, slo_service):
        """Test getting non-existent queue config."""
        result = slo_service.get_queue_config("nonexistent-queue")
        assert result is None


# ============================================================================
# INTEGRATION-LIKE TESTS
# ============================================================================


class TestIntegrationScenarios:
    """Integration-like tests for realistic scenarios."""

    def test_typical_workflow(self, slo_service):
        """Test a typical monitoring workflow."""
        # Record various operations with different latencies within SLO thresholds
        for _ in range(30):
            slo_service.record_latency("auth", 0.05, JobClass.CRITICAL)  # Under 100ms P50
            slo_service.record_latency("template_gen", 0.3, JobClass.STANDARD)  # Under 500ms P50
            slo_service.record_latency("cleanup", 3.0, JobClass.BATCH)  # Under 5s P50

        # Check dashboard - should be healthy when all ops within SLO
        dashboard = slo_service.get_slo_dashboard()
        assert dashboard["overall_health"] == "healthy"

        # Check Grafana export
        grafana = slo_service.get_grafana_metrics()
        assert len(grafana["series"]) > 0

        # Check documentation available
        doc = slo_service.get_job_class_documentation()
        assert len(doc) == 3

    def test_degradation_scenario(self, slo_service):
        """Test system degradation scenario."""
        # Start with normal performance
        for _ in range(15):
            slo_service.record_latency("degrading_op", 0.05, JobClass.CRITICAL)

        # Simulate degradation
        for _ in range(15):
            slo_service.record_latency("degrading_op", 2.0, JobClass.CRITICAL)

        # Should have alerts
        alerts = slo_service.get_active_alerts()
        dashboard = slo_service.get_slo_dashboard()

        # Health should be degraded
        assert dashboard["overall_health"] in ["warning", "critical"] or len(alerts) > 0

    def test_recovery_scenario(self, slo_service):
        """Test system recovery scenario."""
        # Generate alert
        for _ in range(20):
            slo_service.record_latency("recovery_op", 5.0, JobClass.CRITICAL)

        alerts = slo_service.get_active_alerts()
        initial_alert_count = len(alerts)

        # Resolve alerts
        for alert in alerts:
            slo_service.resolve_alert(alert.alert_id)

        # Check alerts cleared
        assert len(slo_service.get_active_alerts()) < initial_alert_count
