#!/usr/bin/env python3
"""
SLO Monitoring Service for MAESTRO Engine
Epic: MD-1875 [ME-1000] SLO Monitoring System

Job class-based SLO monitoring including:
- Job classes (critical/standard/batch)
- Queue configuration
- Grafana dashboards (p50/p95/p99)
- Alert rules for SLO breaches
- Job class documentation
- Runbook links

Acceptance Criteria:
- AC-1: Job classes defined (critical/standard/batch)
- AC-2: Queue configuration with priority support
- AC-3: SLO metrics (p50/p95/p99 latency percentiles)
- AC-4: Alert rules for SLO breaches
- AC-5: Documentation and runbook links
"""

import asyncio
import hashlib
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from statistics import mean, median, stdev
from typing import Any, Callable, Dict, List, Optional, Tuple

# Try to import Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, Gauge, Summary

    SLO_OPERATIONS = Counter(
        "maestro_slo_operations_total",
        "Total SLO-tracked operations",
        ["job_class", "operation", "status"]
    )
    SLO_LATENCY = Histogram(
        "maestro_slo_latency_seconds",
        "Operation latency by job class",
        ["job_class", "operation"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
    )
    SLO_BREACH_COUNTER = Counter(
        "maestro_slo_breaches_total",
        "Total SLO breaches",
        ["job_class", "slo_type", "severity"]
    )
    QUEUE_SIZE_GAUGE = Gauge(
        "maestro_queue_size",
        "Current queue size",
        ["queue_name", "job_class"]
    )
    QUEUE_WAIT_TIME = Histogram(
        "maestro_queue_wait_seconds",
        "Queue wait time",
        ["queue_name", "job_class"],
        buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0]
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

    class StubMetric:
        def inc(self): pass
        def dec(self): pass
        def observe(self, value): pass
        def labels(self, **kwargs): return self
        def set(self, value): pass

    SLO_OPERATIONS = StubMetric()
    SLO_LATENCY = StubMetric()
    SLO_BREACH_COUNTER = StubMetric()
    QUEUE_SIZE_GAUGE = StubMetric()
    QUEUE_WAIT_TIME = StubMetric()

logger = logging.getLogger("slo_monitoring_service")


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class JobClass(str, Enum):
    """
    Job classification for SLO monitoring.

    AC-1: Job classes (critical/standard/batch)

    - CRITICAL: Real-time user-facing operations, strictest SLOs
    - STANDARD: Normal priority operations, standard SLOs
    - BATCH: Background processing, relaxed SLOs
    """
    CRITICAL = "critical"    # User-facing, low latency required
    STANDARD = "standard"    # Normal operations
    BATCH = "batch"          # Background jobs, can tolerate delays


class SLOType(str, Enum):
    """Types of SLO measurements."""
    LATENCY_P50 = "latency_p50"
    LATENCY_P95 = "latency_p95"
    LATENCY_P99 = "latency_p99"
    AVAILABILITY = "availability"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class QueuePriority(int, Enum):
    """Queue priority levels."""
    HIGHEST = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    LOWEST = 5


# ============================================================================
# SLO THRESHOLDS BY JOB CLASS
# ============================================================================

# AC-3: SLO metrics (p50/p95/p99)
DEFAULT_SLO_THRESHOLDS = {
    JobClass.CRITICAL: {
        SLOType.LATENCY_P50: 0.1,      # 100ms
        SLOType.LATENCY_P95: 0.5,      # 500ms
        SLOType.LATENCY_P99: 1.0,      # 1s
        SLOType.AVAILABILITY: 0.999,   # 99.9%
        SLOType.ERROR_RATE: 0.001,     # 0.1%
        SLOType.THROUGHPUT: 1000,      # 1000 ops/sec
    },
    JobClass.STANDARD: {
        SLOType.LATENCY_P50: 0.5,      # 500ms
        SLOType.LATENCY_P95: 2.0,      # 2s
        SLOType.LATENCY_P99: 5.0,      # 5s
        SLOType.AVAILABILITY: 0.99,    # 99%
        SLOType.ERROR_RATE: 0.01,      # 1%
        SLOType.THROUGHPUT: 500,       # 500 ops/sec
    },
    JobClass.BATCH: {
        SLOType.LATENCY_P50: 5.0,      # 5s
        SLOType.LATENCY_P95: 30.0,     # 30s
        SLOType.LATENCY_P99: 60.0,     # 1min
        SLOType.AVAILABILITY: 0.95,    # 95%
        SLOType.ERROR_RATE: 0.05,      # 5%
        SLOType.THROUGHPUT: 100,       # 100 ops/sec
    },
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class SLOThreshold:
    """SLO threshold configuration."""
    slo_type: SLOType
    threshold: float
    job_class: JobClass
    warning_multiplier: float = 0.8  # Alert at 80% of threshold
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slo_type": self.slo_type.value,
            "threshold": self.threshold,
            "job_class": self.job_class.value,
            "warning_multiplier": self.warning_multiplier,
            "warning_threshold": self.threshold * self.warning_multiplier,
            "description": self.description,
        }


@dataclass
class SLOMetric:
    """Individual SLO metric measurement."""
    job_class: JobClass
    operation: str
    slo_type: SLOType
    value: float
    threshold: float
    is_breach: bool
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_class": self.job_class.value,
            "operation": self.operation,
            "slo_type": self.slo_type.value,
            "value": round(self.value, 4),
            "threshold": self.threshold,
            "is_breach": self.is_breach,
            "recorded_at": self.recorded_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class SLOAlert:
    """SLO breach alert."""
    alert_id: str
    job_class: JobClass
    slo_type: SLOType
    severity: AlertSeverity
    operation: str
    current_value: float
    threshold: float
    breach_percentage: float
    message: str
    runbook_link: str
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "job_class": self.job_class.value,
            "slo_type": self.slo_type.value,
            "severity": self.severity.value,
            "operation": self.operation,
            "current_value": round(self.current_value, 4),
            "threshold": self.threshold,
            "breach_percentage": round(self.breach_percentage, 2),
            "message": self.message,
            "runbook_link": self.runbook_link,
            "triggered_at": self.triggered_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged": self.acknowledged,
        }


@dataclass
class QueueConfig:
    """
    Queue configuration for job class.

    AC-2: Queue configuration
    """
    name: str
    job_class: JobClass
    priority: QueuePriority
    max_size: int = 10000
    max_workers: int = 10
    timeout_seconds: float = 300.0
    retry_limit: int = 3
    retry_delay_seconds: float = 1.0
    dead_letter_queue: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "job_class": self.job_class.value,
            "priority": self.priority.value,
            "max_size": self.max_size,
            "max_workers": self.max_workers,
            "timeout_seconds": self.timeout_seconds,
            "retry_limit": self.retry_limit,
            "retry_delay_seconds": self.retry_delay_seconds,
            "dead_letter_queue": self.dead_letter_queue,
        }


@dataclass
class PercentileMetrics:
    """Percentile metrics for latency measurements."""
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    mean_val: float = 0.0
    sample_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "p50": round(self.p50, 4),
            "p95": round(self.p95, 4),
            "p99": round(self.p99, 4),
            "min": round(self.min_val, 4),
            "max": round(self.max_val, 4),
            "mean": round(self.mean_val, 4),
            "sample_count": self.sample_count,
        }


@dataclass
class QueueMetrics:
    """Queue metrics snapshot."""
    queue_name: str
    job_class: JobClass
    size: int = 0
    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    avg_wait_time: float = 0.0
    avg_process_time: float = 0.0
    throughput: float = 0.0  # ops/sec
    recorded_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "queue_name": self.queue_name,
            "job_class": self.job_class.value,
            "size": self.size,
            "pending": self.pending,
            "processing": self.processing,
            "completed": self.completed,
            "failed": self.failed,
            "avg_wait_time": round(self.avg_wait_time, 4),
            "avg_process_time": round(self.avg_process_time, 4),
            "throughput": round(self.throughput, 2),
            "recorded_at": self.recorded_at.isoformat(),
        }


# ============================================================================
# JOB CLASS DOCUMENTATION
# ============================================================================

# AC-5: Documentation and runbook links
JOB_CLASS_DOCUMENTATION = {
    JobClass.CRITICAL: {
        "name": "Critical",
        "description": "Real-time user-facing operations requiring strictest SLOs",
        "use_cases": [
            "User authentication/authorization",
            "Real-time API responses",
            "Interactive workflow operations",
            "Payment processing",
        ],
        "slo_targets": {
            "latency_p50": "100ms",
            "latency_p95": "500ms",
            "latency_p99": "1s",
            "availability": "99.9%",
            "error_rate": "< 0.1%",
        },
        "runbook_link": "https://docs.maestro.ai/runbooks/slo/critical-jobs",
        "escalation_policy": "PagerDuty - Critical tier (5 min response)",
        "queue_config": {
            "priority": "highest",
            "max_workers": 20,
            "timeout": "30s",
            "retries": 1,
        },
    },
    JobClass.STANDARD: {
        "name": "Standard",
        "description": "Normal priority operations with standard SLOs",
        "use_cases": [
            "Template generation",
            "Code analysis",
            "Quality validation",
            "Report generation",
        ],
        "slo_targets": {
            "latency_p50": "500ms",
            "latency_p95": "2s",
            "latency_p99": "5s",
            "availability": "99%",
            "error_rate": "< 1%",
        },
        "runbook_link": "https://docs.maestro.ai/runbooks/slo/standard-jobs",
        "escalation_policy": "PagerDuty - Standard tier (15 min response)",
        "queue_config": {
            "priority": "normal",
            "max_workers": 10,
            "timeout": "5min",
            "retries": 3,
        },
    },
    JobClass.BATCH: {
        "name": "Batch",
        "description": "Background processing with relaxed SLOs",
        "use_cases": [
            "Bulk template migration",
            "Analytics aggregation",
            "Cleanup tasks",
            "Scheduled reports",
        ],
        "slo_targets": {
            "latency_p50": "5s",
            "latency_p95": "30s",
            "latency_p99": "1min",
            "availability": "95%",
            "error_rate": "< 5%",
        },
        "runbook_link": "https://docs.maestro.ai/runbooks/slo/batch-jobs",
        "escalation_policy": "Email notification (1 hour response)",
        "queue_config": {
            "priority": "low",
            "max_workers": 5,
            "timeout": "30min",
            "retries": 5,
        },
    },
}


# ============================================================================
# SLO MONITORING SERVICE
# ============================================================================

class SLOMonitoringService:
    """
    SLO Monitoring Service for MAESTRO Engine.

    Provides job class-based SLO monitoring with:
    - Job classification (critical/standard/batch)
    - Latency percentile tracking (p50/p95/p99)
    - Alert generation on SLO breaches
    - Queue metrics and configuration
    - Documentation and runbook links
    """

    def __init__(
        self,
        custom_thresholds: Optional[Dict[JobClass, Dict[SLOType, float]]] = None,
        window_size: int = 1000,
        alert_callback: Optional[Callable] = None,
    ):
        """
        Initialize SLO Monitoring Service.

        Args:
            custom_thresholds: Optional custom SLO thresholds
            window_size: Number of samples to keep for percentile calculations
            alert_callback: Callback function for alerts
        """
        self.thresholds = custom_thresholds or DEFAULT_SLO_THRESHOLDS
        self.window_size = window_size
        self.alert_callback = alert_callback

        # Latency samples per operation/job class
        self._latency_samples: Dict[str, deque] = {}

        # Queue configurations
        self._queue_configs: Dict[str, QueueConfig] = {}

        # Queue metrics
        self._queue_metrics: Dict[str, QueueMetrics] = {}

        # Active alerts
        self._active_alerts: Dict[str, SLOAlert] = {}

        # Operation counters
        self._operation_counts: Dict[str, Dict[str, int]] = {}

        # Initialize default queues
        self._initialize_default_queues()

        logger.info("SLOMonitoringService initialized")

    def _initialize_default_queues(self):
        """Initialize default queue configurations."""
        # Critical queue
        self.register_queue(QueueConfig(
            name="maestro-critical",
            job_class=JobClass.CRITICAL,
            priority=QueuePriority.HIGHEST,
            max_size=1000,
            max_workers=20,
            timeout_seconds=30.0,
            retry_limit=1,
            retry_delay_seconds=0.5,
            dead_letter_queue="maestro-critical-dlq",
        ))

        # Standard queue
        self.register_queue(QueueConfig(
            name="maestro-standard",
            job_class=JobClass.STANDARD,
            priority=QueuePriority.NORMAL,
            max_size=5000,
            max_workers=10,
            timeout_seconds=300.0,
            retry_limit=3,
            retry_delay_seconds=1.0,
            dead_letter_queue="maestro-standard-dlq",
        ))

        # Batch queue
        self.register_queue(QueueConfig(
            name="maestro-batch",
            job_class=JobClass.BATCH,
            priority=QueuePriority.LOW,
            max_size=10000,
            max_workers=5,
            timeout_seconds=1800.0,
            retry_limit=5,
            retry_delay_seconds=5.0,
            dead_letter_queue="maestro-batch-dlq",
        ))

    # ========================================================================
    # QUEUE MANAGEMENT (AC-2)
    # ========================================================================

    def register_queue(self, config: QueueConfig) -> None:
        """Register a queue configuration."""
        self._queue_configs[config.name] = config
        self._queue_metrics[config.name] = QueueMetrics(
            queue_name=config.name,
            job_class=config.job_class,
        )
        logger.info(f"Registered queue: {config.name} ({config.job_class.value})")

    def get_queue_config(self, queue_name: str) -> Optional[QueueConfig]:
        """Get queue configuration."""
        return self._queue_configs.get(queue_name)

    def get_all_queue_configs(self) -> Dict[str, QueueConfig]:
        """Get all queue configurations."""
        return self._queue_configs.copy()

    def get_queue_for_job_class(self, job_class: JobClass) -> Optional[QueueConfig]:
        """Get the default queue for a job class."""
        for config in self._queue_configs.values():
            if config.job_class == job_class:
                return config
        return None

    # ========================================================================
    # LATENCY RECORDING
    # ========================================================================

    def record_latency(
        self,
        operation: str,
        latency_seconds: float,
        job_class: JobClass = JobClass.STANDARD,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[SLOAlert]:
        """
        Record operation latency.

        Args:
            operation: Operation name
            latency_seconds: Latency in seconds
            job_class: Job classification
            success: Whether operation succeeded
            metadata: Additional metadata

        Returns:
            SLOAlert if SLO breach detected, None otherwise
        """
        key = f"{job_class.value}:{operation}"

        # Initialize samples deque if needed
        if key not in self._latency_samples:
            self._latency_samples[key] = deque(maxlen=self.window_size)

        # Record sample
        self._latency_samples[key].append({
            "latency": latency_seconds,
            "timestamp": datetime.utcnow(),
            "success": success,
        })

        # Update counters
        if key not in self._operation_counts:
            self._operation_counts[key] = {"total": 0, "success": 0, "failure": 0}
        self._operation_counts[key]["total"] += 1
        if success:
            self._operation_counts[key]["success"] += 1
        else:
            self._operation_counts[key]["failure"] += 1

        # Record Prometheus metrics
        status = "success" if success else "failure"
        SLO_OPERATIONS.labels(
            job_class=job_class.value,
            operation=operation,
            status=status
        ).inc()
        SLO_LATENCY.labels(
            job_class=job_class.value,
            operation=operation
        ).observe(latency_seconds)

        # Check SLOs and generate alert if needed
        alert = self._check_slos(operation, job_class)
        if alert:
            self._active_alerts[alert.alert_id] = alert
            if self.alert_callback:
                try:
                    self.alert_callback(alert)
                except Exception as e:
                    logger.error(f"Alert callback failed: {e}")

        return alert

    # ========================================================================
    # PERCENTILE CALCULATIONS (AC-3)
    # ========================================================================

    def calculate_percentiles(
        self,
        operation: str,
        job_class: JobClass,
    ) -> PercentileMetrics:
        """
        Calculate latency percentiles for an operation.

        AC-3: SLO metrics (p50/p95/p99)

        Args:
            operation: Operation name
            job_class: Job classification

        Returns:
            PercentileMetrics with p50, p95, p99
        """
        key = f"{job_class.value}:{operation}"

        if key not in self._latency_samples or not self._latency_samples[key]:
            return PercentileMetrics()

        latencies = [s["latency"] for s in self._latency_samples[key]]
        sorted_latencies = sorted(latencies)
        count = len(sorted_latencies)

        return PercentileMetrics(
            p50=sorted_latencies[int(count * 0.50)],
            p95=sorted_latencies[int(count * 0.95)] if count > 20 else sorted_latencies[-1],
            p99=sorted_latencies[int(count * 0.99)] if count > 100 else sorted_latencies[-1],
            min_val=min(sorted_latencies),
            max_val=max(sorted_latencies),
            mean_val=mean(sorted_latencies),
            sample_count=count,
        )

    def get_all_percentiles(self) -> Dict[str, PercentileMetrics]:
        """Get percentiles for all operations."""
        result = {}
        for key in self._latency_samples.keys():
            parts = key.split(":", 1)
            if len(parts) == 2:
                job_class = JobClass(parts[0])
                operation = parts[1]
                result[key] = self.calculate_percentiles(operation, job_class)
        return result

    # ========================================================================
    # SLO CHECKING (AC-4)
    # ========================================================================

    def _check_slos(
        self,
        operation: str,
        job_class: JobClass,
    ) -> Optional[SLOAlert]:
        """
        Check SLOs and generate alert if breach detected.

        AC-4: Alert rules for SLO breaches
        """
        percentiles = self.calculate_percentiles(operation, job_class)

        if percentiles.sample_count < 10:
            return None  # Not enough data

        thresholds = self.thresholds.get(job_class, {})

        # Check P99 first (most severe)
        p99_threshold = thresholds.get(SLOType.LATENCY_P99, float('inf'))
        if percentiles.p99 > p99_threshold:
            return self._create_alert(
                job_class=job_class,
                slo_type=SLOType.LATENCY_P99,
                operation=operation,
                current_value=percentiles.p99,
                threshold=p99_threshold,
            )

        # Check P95
        p95_threshold = thresholds.get(SLOType.LATENCY_P95, float('inf'))
        if percentiles.p95 > p95_threshold:
            return self._create_alert(
                job_class=job_class,
                slo_type=SLOType.LATENCY_P95,
                operation=operation,
                current_value=percentiles.p95,
                threshold=p95_threshold,
            )

        # Check P50
        p50_threshold = thresholds.get(SLOType.LATENCY_P50, float('inf'))
        if percentiles.p50 > p50_threshold:
            return self._create_alert(
                job_class=job_class,
                slo_type=SLOType.LATENCY_P50,
                operation=operation,
                current_value=percentiles.p50,
                threshold=p50_threshold,
            )

        return None

    def _create_alert(
        self,
        job_class: JobClass,
        slo_type: SLOType,
        operation: str,
        current_value: float,
        threshold: float,
    ) -> SLOAlert:
        """Create an SLO breach alert."""
        breach_percentage = ((current_value - threshold) / threshold) * 100

        # Determine severity
        if breach_percentage > 100:
            severity = AlertSeverity.CRITICAL
        elif breach_percentage > 50:
            severity = AlertSeverity.WARNING
        else:
            severity = AlertSeverity.INFO

        alert_id = hashlib.md5(
            f"{job_class.value}:{slo_type.value}:{operation}:{time.time()}".encode()
        ).hexdigest()[:16]

        # Get runbook link
        doc = JOB_CLASS_DOCUMENTATION.get(job_class, {})
        runbook_link = doc.get("runbook_link", "https://docs.maestro.ai/runbooks/slo")

        alert = SLOAlert(
            alert_id=alert_id,
            job_class=job_class,
            slo_type=slo_type,
            severity=severity,
            operation=operation,
            current_value=current_value,
            threshold=threshold,
            breach_percentage=breach_percentage,
            message=f"SLO breach: {operation} {slo_type.value} is {current_value:.3f}s "
                   f"(threshold: {threshold}s, {breach_percentage:.1f}% over)",
            runbook_link=runbook_link,
        )

        # Record Prometheus metric
        SLO_BREACH_COUNTER.labels(
            job_class=job_class.value,
            slo_type=slo_type.value,
            severity=severity.value
        ).inc()

        logger.warning(f"SLO breach detected: {alert.message}")

        return alert

    # ========================================================================
    # ALERT MANAGEMENT
    # ========================================================================

    def get_active_alerts(self) -> List[SLOAlert]:
        """Get all active alerts."""
        return list(self._active_alerts.values())

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        if alert_id in self._active_alerts:
            self._active_alerts[alert_id].acknowledged = True
            return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        if alert_id in self._active_alerts:
            self._active_alerts[alert_id].resolved_at = datetime.utcnow()
            del self._active_alerts[alert_id]
            return True
        return False

    # ========================================================================
    # DOCUMENTATION (AC-5)
    # ========================================================================

    def get_job_class_documentation(
        self,
        job_class: Optional[JobClass] = None,
    ) -> Dict[str, Any]:
        """
        Get job class documentation.

        AC-5: Documentation and runbook links
        """
        if job_class:
            return JOB_CLASS_DOCUMENTATION.get(job_class, {})
        return JOB_CLASS_DOCUMENTATION

    def get_slo_thresholds(
        self,
        job_class: Optional[JobClass] = None,
    ) -> Dict[str, Any]:
        """Get SLO thresholds."""
        if job_class:
            thresholds = self.thresholds.get(job_class, {})
            return {k.value: v for k, v in thresholds.items()}

        return {
            jc.value: {k.value: v for k, v in thresholds.items()}
            for jc, thresholds in self.thresholds.items()
        }

    # ========================================================================
    # METRICS DASHBOARD
    # ========================================================================

    def get_slo_dashboard(self) -> Dict[str, Any]:
        """Get SLO monitoring dashboard data."""
        dashboard = {
            "timestamp": datetime.utcnow().isoformat(),
            "job_classes": {},
            "queues": {},
            "active_alerts": [a.to_dict() for a in self._active_alerts.values()],
            "overall_health": "healthy",
        }

        # Calculate health status
        critical_alerts = len([
            a for a in self._active_alerts.values()
            if a.severity == AlertSeverity.CRITICAL
        ])
        warning_alerts = len([
            a for a in self._active_alerts.values()
            if a.severity == AlertSeverity.WARNING
        ])

        if critical_alerts > 0:
            dashboard["overall_health"] = "critical"
        elif warning_alerts > 0:
            dashboard["overall_health"] = "warning"

        # Per job class metrics
        for job_class in JobClass:
            class_metrics = {
                "documentation": JOB_CLASS_DOCUMENTATION.get(job_class, {}),
                "thresholds": {k.value: v for k, v in self.thresholds.get(job_class, {}).items()},
                "operations": {},
            }

            # Get operations for this job class
            for key in self._latency_samples.keys():
                if key.startswith(f"{job_class.value}:"):
                    operation = key.split(":", 1)[1]
                    percentiles = self.calculate_percentiles(operation, job_class)
                    counts = self._operation_counts.get(key, {})

                    class_metrics["operations"][operation] = {
                        "percentiles": percentiles.to_dict(),
                        "total_count": counts.get("total", 0),
                        "success_count": counts.get("success", 0),
                        "failure_count": counts.get("failure", 0),
                        "error_rate": (
                            counts.get("failure", 0) / counts.get("total", 1)
                            if counts.get("total", 0) > 0 else 0
                        ),
                    }

            dashboard["job_classes"][job_class.value] = class_metrics

        # Queue metrics
        for queue_name, metrics in self._queue_metrics.items():
            dashboard["queues"][queue_name] = metrics.to_dict()

        return dashboard

    def get_grafana_metrics(self) -> Dict[str, Any]:
        """
        Get metrics formatted for Grafana dashboards.

        AC-3: Grafana dashboards (p50/p95/p99)
        """
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "series": [],
        }

        for key in self._latency_samples.keys():
            parts = key.split(":", 1)
            if len(parts) != 2:
                continue

            job_class = JobClass(parts[0])
            operation = parts[1]
            percentiles = self.calculate_percentiles(operation, job_class)
            thresholds = self.thresholds.get(job_class, {})

            # Create time series data
            metrics["series"].append({
                "name": f"latency_p50_{job_class.value}_{operation}",
                "value": percentiles.p50,
                "threshold": thresholds.get(SLOType.LATENCY_P50, 0),
                "labels": {
                    "job_class": job_class.value,
                    "operation": operation,
                    "percentile": "p50",
                },
            })
            metrics["series"].append({
                "name": f"latency_p95_{job_class.value}_{operation}",
                "value": percentiles.p95,
                "threshold": thresholds.get(SLOType.LATENCY_P95, 0),
                "labels": {
                    "job_class": job_class.value,
                    "operation": operation,
                    "percentile": "p95",
                },
            })
            metrics["series"].append({
                "name": f"latency_p99_{job_class.value}_{operation}",
                "value": percentiles.p99,
                "threshold": thresholds.get(SLOType.LATENCY_P99, 0),
                "labels": {
                    "job_class": job_class.value,
                    "operation": operation,
                    "percentile": "p99",
                },
            })

        return metrics


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_slo_service: Optional[SLOMonitoringService] = None


def get_slo_monitoring_service() -> SLOMonitoringService:
    """Get the singleton SLO monitoring service instance."""
    global _slo_service
    if _slo_service is None:
        _slo_service = SLOMonitoringService()
    return _slo_service


# Convenience alias
slo_service = get_slo_monitoring_service
