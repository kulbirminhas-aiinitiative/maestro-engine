"""
Symphony Observability, Metrics, and SLOs

EPIC: MD-3902 - Maestro Symphony Demo
Story: MD-3912 - Add Observability, Metrics, and SLOs

Provides structured logging, metrics collection, trace context propagation,
and SLO monitoring for Symphony demo components.
"""

import asyncio
import time
import uuid
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from collections import deque
from contextlib import contextmanager
import logging
import json

logger = logging.getLogger(__name__)


# =============================================================================
# SLO Definitions
# =============================================================================

@dataclass
class SLODefinition:
    """Service Level Objective definition"""
    name: str
    description: str
    target: float  # Target value (e.g., 99.0 for 99%)
    unit: str  # "percent", "ms", "count"
    threshold_warning: float  # Warn if below this
    threshold_critical: float  # Critical if below this


# Symphony Demo SLOs
SYMPHONY_SLOS = {
    "message_latency_p50": SLODefinition(
        name="Message Latency P50",
        description="50th percentile message delivery latency including synthetic delays",
        target=2000.0,  # 2 seconds
        unit="ms",
        threshold_warning=3000.0,
        threshold_critical=5000.0,
    ),
    "message_latency_p95": SLODefinition(
        name="Message Latency P95",
        description="95th percentile message delivery latency",
        target=5000.0,  # 5 seconds
        unit="ms",
        threshold_warning=7000.0,
        threshold_critical=10000.0,
    ),
    "persona_selection_time": SLODefinition(
        name="Persona Selection Time",
        description="Time to select responding persona",
        target=50.0,  # 50ms
        unit="ms",
        threshold_warning=100.0,
        threshold_critical=500.0,
    ),
    "artifact_generation_time": SLODefinition(
        name="Artifact Generation Time",
        description="Time to generate and stream artifact",
        target=2000.0,  # 2 seconds
        unit="ms",
        threshold_warning=5000.0,
        threshold_critical=10000.0,
    ),
    "websocket_uptime": SLODefinition(
        name="WebSocket Uptime",
        description="Percentage of time WebSocket is connected",
        target=99.0,  # 99%
        unit="percent",
        threshold_warning=95.0,
        threshold_critical=90.0,
    ),
    "artifact_stream_success": SLODefinition(
        name="Artifact Stream Success Rate",
        description="Percentage of artifacts successfully streamed",
        target=99.0,  # 99%
        unit="percent",
        threshold_warning=95.0,
        threshold_critical=90.0,
    ),
    "typing_indicator_accuracy": SLODefinition(
        name="Typing Indicator Accuracy",
        description="Percentage of AI messages preceded by typing indicator",
        target=95.0,  # 95%
        unit="percent",
        threshold_warning=90.0,
        threshold_critical=80.0,
    ),
    "response_delay_accuracy": SLODefinition(
        name="Response Delay Accuracy",
        description="Percentage of responses within configured delay bounds",
        target=90.0,  # 90%
        unit="percent",
        threshold_warning=80.0,
        threshold_critical=70.0,
    ),
}


class SLOStatus(str, Enum):
    """SLO health status"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# =============================================================================
# Metric Types
# =============================================================================

class MetricType(str, Enum):
    """Types of metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricSample:
    """A single metric sample"""
    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE


@dataclass
class TimerMetric:
    """Timer metric with start/end tracking"""
    name: str
    started_at: float
    labels: Dict[str, str] = field(default_factory=dict)

    def stop(self) -> float:
        """Stop timer and return duration in ms"""
        return (time.perf_counter() - self.started_at) * 1000


# =============================================================================
# Trace Context
# =============================================================================

@dataclass
class TraceContext:
    """
    Trace context for correlating events across Symphony components.

    Propagates through:
    - Teams messages → Router → Persona → Artifact → WebSocket
    """
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    persona_id: Optional[str] = None
    artifact_id: Optional[str] = None
    workflow_phase: Optional[str] = None

    @classmethod
    def new(cls, session_id: Optional[str] = None) -> "TraceContext":
        """Create new trace context"""
        return cls(
            trace_id=uuid.uuid4().hex[:16],
            span_id=uuid.uuid4().hex[:8],
            session_id=session_id,
        )

    def new_span(self) -> "TraceContext":
        """Create child span context"""
        return TraceContext(
            trace_id=self.trace_id,
            span_id=uuid.uuid4().hex[:8],
            parent_span_id=self.span_id,
            session_id=self.session_id,
            conversation_id=self.conversation_id,
            persona_id=self.persona_id,
            artifact_id=self.artifact_id,
            workflow_phase=self.workflow_phase,
        )

    def with_persona(self, persona_id: str) -> "TraceContext":
        """Create context with persona"""
        ctx = self.new_span()
        ctx.persona_id = persona_id
        return ctx

    def with_artifact(self, artifact_id: str) -> "TraceContext":
        """Create context with artifact"""
        ctx = self.new_span()
        ctx.artifact_id = artifact_id
        return ctx

    def with_phase(self, phase: str) -> "TraceContext":
        """Create context with workflow phase"""
        ctx = self.new_span()
        ctx.workflow_phase = phase
        return ctx

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/headers"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "persona_id": self.persona_id,
            "artifact_id": self.artifact_id,
            "workflow_phase": self.workflow_phase,
        }

    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP headers for propagation"""
        return {
            "X-Trace-Id": self.trace_id,
            "X-Span-Id": self.span_id,
            "X-Parent-Span-Id": self.parent_span_id or "",
            "X-Session-Id": self.session_id or "",
        }


# =============================================================================
# Metrics Collector
# =============================================================================

class MetricsCollector:
    """
    Collects and aggregates Symphony metrics for observability.

    Tracks:
    - Message latency (including synthetic delays)
    - Persona selection time
    - Artifact generation time
    - WebSocket connection status
    - Error counts
    """

    def __init__(self, max_samples: int = 1000):
        """Initialize metrics collector"""
        self.max_samples = max_samples

        # Counters
        self.counters: Dict[str, int] = {
            "messages_received": 0,
            "messages_sent": 0,
            "artifacts_generated": 0,
            "artifacts_streamed": 0,
            "typing_indicators_sent": 0,
            "persona_selections": 0,
            "websocket_connects": 0,
            "websocket_disconnects": 0,
            "errors": 0,
            "fallback_switches": 0,
        }

        # Histograms (store recent values for percentile calculation)
        self.histograms: Dict[str, deque] = {
            "message_latency_ms": deque(maxlen=max_samples),
            "persona_selection_ms": deque(maxlen=max_samples),
            "artifact_generation_ms": deque(maxlen=max_samples),
            "response_delay_ms": deque(maxlen=max_samples),
            "typing_duration_ms": deque(maxlen=max_samples),
        }

        # Gauges (current values)
        self.gauges: Dict[str, float] = {
            "active_sessions": 0,
            "active_websockets": 0,
            "current_phase_progress": 0,
            "playback_speed": 1.0,
        }

        # WebSocket uptime tracking
        self._ws_connected_time: float = 0.0
        self._ws_total_time: float = 0.0
        self._ws_connect_start: Optional[float] = None

        # Timing metrics within bounds tracking
        self._delays_within_bounds: int = 0
        self._total_delays: int = 0

        # Started at
        self.started_at = datetime.utcnow()

    # -------------------------------------------------------------------------
    # Counter Operations
    # -------------------------------------------------------------------------

    def increment(self, counter: str, value: int = 1, labels: Optional[Dict[str, str]] = None):
        """Increment a counter"""
        if counter in self.counters:
            self.counters[counter] += value
        else:
            self.counters[counter] = value

        # Log with labels
        self._log_metric(counter, value, MetricType.COUNTER, labels)

    def get_counter(self, counter: str) -> int:
        """Get counter value"""
        return self.counters.get(counter, 0)

    # -------------------------------------------------------------------------
    # Histogram Operations
    # -------------------------------------------------------------------------

    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a histogram value"""
        if name in self.histograms:
            self.histograms[name].append(value)
        else:
            self.histograms[name] = deque([value], maxlen=self.max_samples)

        self._log_metric(name, value, MetricType.HISTOGRAM, labels)

    def get_percentile(self, name: str, percentile: float) -> Optional[float]:
        """Get percentile value from histogram"""
        if name not in self.histograms or len(self.histograms[name]) == 0:
            return None

        sorted_values = sorted(self.histograms[name])
        index = int(len(sorted_values) * percentile / 100)
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]

    def get_histogram_stats(self, name: str) -> Dict[str, Optional[float]]:
        """Get histogram statistics"""
        if name not in self.histograms or len(self.histograms[name]) == 0:
            return {"p50": None, "p95": None, "p99": None, "mean": None, "count": 0}

        values = list(self.histograms[name])
        return {
            "p50": self.get_percentile(name, 50),
            "p95": self.get_percentile(name, 95),
            "p99": self.get_percentile(name, 99),
            "mean": statistics.mean(values),
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }

    # -------------------------------------------------------------------------
    # Gauge Operations
    # -------------------------------------------------------------------------

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge value"""
        self.gauges[name] = value
        self._log_metric(name, value, MetricType.GAUGE, labels)

    def get_gauge(self, name: str) -> float:
        """Get gauge value"""
        return self.gauges.get(name, 0.0)

    # -------------------------------------------------------------------------
    # Timer Operations
    # -------------------------------------------------------------------------

    def start_timer(self, name: str, labels: Optional[Dict[str, str]] = None) -> TimerMetric:
        """Start a timer"""
        return TimerMetric(
            name=name,
            started_at=time.perf_counter(),
            labels=labels or {},
        )

    def stop_timer(self, timer: TimerMetric):
        """Stop a timer and record the duration"""
        duration_ms = timer.stop()
        self.record_histogram(f"{timer.name}_ms", duration_ms, timer.labels)
        return duration_ms

    @contextmanager
    def timer(self, name: str, labels: Optional[Dict[str, str]] = None):
        """Context manager for timing operations"""
        timer = self.start_timer(name, labels)
        try:
            yield timer
        finally:
            self.stop_timer(timer)

    # -------------------------------------------------------------------------
    # WebSocket Tracking
    # -------------------------------------------------------------------------

    def record_websocket_connect(self, session_id: str):
        """Record WebSocket connection"""
        self.increment("websocket_connects")
        self.gauges["active_websockets"] += 1
        self._ws_connect_start = time.perf_counter()

    def record_websocket_disconnect(self, session_id: str):
        """Record WebSocket disconnection"""
        self.increment("websocket_disconnects")
        self.gauges["active_websockets"] = max(0, self.gauges["active_websockets"] - 1)

        if self._ws_connect_start:
            connected_duration = time.perf_counter() - self._ws_connect_start
            self._ws_connected_time += connected_duration
            self._ws_connect_start = None

        self._ws_total_time = (datetime.utcnow() - self.started_at).total_seconds()

    def get_websocket_uptime(self) -> float:
        """Get WebSocket uptime percentage"""
        if self._ws_total_time == 0:
            return 100.0

        current_connected = 0
        if self._ws_connect_start:
            current_connected = time.perf_counter() - self._ws_connect_start

        total_connected = self._ws_connected_time + current_connected
        self._ws_total_time = (datetime.utcnow() - self.started_at).total_seconds()

        return (total_connected / max(self._ws_total_time, 1)) * 100

    # -------------------------------------------------------------------------
    # Response Delay Tracking
    # -------------------------------------------------------------------------

    def record_response_delay(self, actual_ms: float, expected_min_ms: float, expected_max_ms: float):
        """Record a response delay and check if within bounds"""
        self.record_histogram("response_delay_ms", actual_ms)
        self._total_delays += 1

        if expected_min_ms <= actual_ms <= expected_max_ms:
            self._delays_within_bounds += 1

    def get_delay_accuracy(self) -> float:
        """Get percentage of delays within configured bounds"""
        if self._total_delays == 0:
            return 100.0
        return (self._delays_within_bounds / self._total_delays) * 100

    # -------------------------------------------------------------------------
    # Structured Logging
    # -------------------------------------------------------------------------

    def _log_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType,
        labels: Optional[Dict[str, str]] = None
    ):
        """Log metric in structured format"""
        log_data = {
            "metric_name": name,
            "metric_value": value,
            "metric_type": metric_type.value,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if labels:
            log_data["labels"] = labels

        logger.debug(f"METRIC: {json.dumps(log_data)}")

    def log_event(
        self,
        event_name: str,
        data: Dict[str, Any],
        trace_ctx: Optional[TraceContext] = None,
        level: str = "info"
    ):
        """Log structured event"""
        log_data = {
            "event": event_name,
            "timestamp": datetime.utcnow().isoformat(),
            **data,
        }

        if trace_ctx:
            log_data["trace"] = trace_ctx.to_dict()

        log_fn = getattr(logger, level, logger.info)
        log_fn(f"EVENT: {json.dumps(log_data)}")

    # -------------------------------------------------------------------------
    # SLO Evaluation
    # -------------------------------------------------------------------------

    def evaluate_slo(self, slo_name: str) -> Tuple[SLOStatus, float, str]:
        """
        Evaluate a single SLO.

        Returns: (status, current_value, message)
        """
        if slo_name not in SYMPHONY_SLOS:
            return SLOStatus.UNKNOWN, 0.0, f"Unknown SLO: {slo_name}"

        slo = SYMPHONY_SLOS[slo_name]
        current_value = 0.0

        # Calculate current value based on SLO type
        if slo_name == "message_latency_p50":
            current_value = self.get_percentile("message_latency_ms", 50) or 0.0
        elif slo_name == "message_latency_p95":
            current_value = self.get_percentile("message_latency_ms", 95) or 0.0
        elif slo_name == "persona_selection_time":
            current_value = self.get_percentile("persona_selection_ms", 50) or 0.0
        elif slo_name == "artifact_generation_time":
            current_value = self.get_percentile("artifact_generation_ms", 50) or 0.0
        elif slo_name == "websocket_uptime":
            current_value = self.get_websocket_uptime()
        elif slo_name == "artifact_stream_success":
            generated = self.get_counter("artifacts_generated")
            streamed = self.get_counter("artifacts_streamed")
            current_value = (streamed / max(generated, 1)) * 100
        elif slo_name == "typing_indicator_accuracy":
            sent = self.get_counter("typing_indicators_sent")
            messages = self.get_counter("messages_sent")
            current_value = (sent / max(messages, 1)) * 100
        elif slo_name == "response_delay_accuracy":
            current_value = self.get_delay_accuracy()

        # Determine status
        if slo.unit == "percent":
            # Higher is better for percentages
            if current_value >= slo.target:
                status = SLOStatus.HEALTHY
            elif current_value >= slo.threshold_critical:
                status = SLOStatus.WARNING
            else:
                status = SLOStatus.CRITICAL
        else:
            # Lower is better for latencies
            # target < warning < critical
            if current_value <= slo.target:
                status = SLOStatus.HEALTHY
            elif current_value <= slo.threshold_critical:
                status = SLOStatus.WARNING
            else:
                status = SLOStatus.CRITICAL

        message = f"{slo.name}: {current_value:.2f}{slo.unit} (target: {slo.target}{slo.unit})"
        return status, current_value, message

    def evaluate_all_slos(self) -> Dict[str, Any]:
        """Evaluate all SLOs and return status report"""
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": SLOStatus.HEALTHY.value,
            "slos": {},
        }

        critical_count = 0
        warning_count = 0

        for slo_name, slo_def in SYMPHONY_SLOS.items():
            status, value, message = self.evaluate_slo(slo_name)
            results["slos"][slo_name] = {
                "name": slo_def.name,
                "description": slo_def.description,
                "target": slo_def.target,
                "current": value,
                "unit": slo_def.unit,
                "status": status.value,
                "message": message,
            }

            if status == SLOStatus.CRITICAL:
                critical_count += 1
            elif status == SLOStatus.WARNING:
                warning_count += 1

        # Set overall status
        if critical_count > 0:
            results["overall_status"] = SLOStatus.CRITICAL.value
        elif warning_count > 0:
            results["overall_status"] = SLOStatus.WARNING.value

        results["summary"] = {
            "healthy": len(SYMPHONY_SLOS) - critical_count - warning_count,
            "warning": warning_count,
            "critical": critical_count,
        }

        return results

    # -------------------------------------------------------------------------
    # Export / Summary
    # -------------------------------------------------------------------------

    def get_summary(self) -> Dict[str, Any]:
        """Get full metrics summary"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": (datetime.utcnow() - self.started_at).total_seconds(),
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {
                name: self.get_histogram_stats(name)
                for name in self.histograms
            },
            "websocket_uptime_percent": self.get_websocket_uptime(),
            "delay_accuracy_percent": self.get_delay_accuracy(),
        }

    def reset(self):
        """Reset all metrics"""
        for key in self.counters:
            self.counters[key] = 0
        for key in self.histograms:
            self.histograms[key].clear()
        for key in self.gauges:
            self.gauges[key] = 0.0

        self._ws_connected_time = 0.0
        self._ws_total_time = 0.0
        self._ws_connect_start = None
        self._delays_within_bounds = 0
        self._total_delays = 0
        self.started_at = datetime.utcnow()


# =============================================================================
# Convenience Functions
# =============================================================================

# Singleton metrics collector
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get singleton MetricsCollector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def reset_metrics_collector():
    """Reset the metrics collector (for testing)"""
    global _metrics_collector
    _metrics_collector = None


# =============================================================================
# Decorators for Easy Instrumentation
# =============================================================================

def timed(name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to time function execution"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            with collector.timer(name, labels):
                return await func(*args, **kwargs)

        def sync_wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            with collector.timer(name, labels):
                return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def counted(counter_name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to count function calls"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            collector.increment(counter_name, labels=labels)
            return await func(*args, **kwargs)

        def sync_wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            collector.increment(counter_name, labels=labels)
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
