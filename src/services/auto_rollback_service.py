"""
Auto-Rollback Service for Health Failures.

This service monitors deployment health and automatically triggers rollbacks
when health checks fail, ensuring system stability and minimizing downtime.

Implements MD-1809: Auto-Rollback on Health Failures
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

try:
    from prometheus_client import Counter, Gauge, Histogram
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class RollbackReason(Enum):
    """Reasons for triggering a rollback."""
    HEALTH_CHECK_FAILED = "health_check_failed"
    ERROR_RATE_EXCEEDED = "error_rate_exceeded"
    LATENCY_EXCEEDED = "latency_exceeded"
    MEMORY_EXCEEDED = "memory_exceeded"
    CPU_EXCEEDED = "cpu_exceeded"
    CUSTOM_METRIC_FAILED = "custom_metric_failed"
    MANUAL_TRIGGER = "manual_trigger"


class RollbackStatus(Enum):
    """Status of a rollback operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RollbackThresholds:
    """Configuration for rollback thresholds."""
    # Health check thresholds
    consecutive_failures: int = 3
    failure_window_seconds: int = 60

    # Error rate thresholds
    error_rate_threshold: float = 0.05  # 5% error rate
    error_rate_window_seconds: int = 300

    # Latency thresholds
    latency_p99_threshold_ms: float = 5000.0
    latency_p95_threshold_ms: float = 3000.0

    # Resource thresholds
    memory_threshold_percent: float = 90.0
    cpu_threshold_percent: float = 85.0

    # Timing
    health_check_interval_seconds: int = 10
    stabilization_period_seconds: int = 60
    rollback_cooldown_seconds: int = 300


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    check_id: str
    deployment_id: str
    timestamp: datetime
    status: HealthStatus
    latency_ms: Optional[float] = None
    error_rate: Optional[float] = None
    memory_percent: Optional[float] = None
    cpu_percent: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def is_healthy(self) -> bool:
        """Check if this result indicates healthy status."""
        return self.status == HealthStatus.HEALTHY


@dataclass
class RollbackEvent:
    """Record of a rollback event."""
    rollback_id: str
    deployment_id: str
    service_name: str
    environment: str
    from_version: str
    to_version: str
    reason: RollbackReason
    status: RollbackStatus
    triggered_at: datetime
    completed_at: Optional[datetime] = None
    triggered_by: str = "auto_rollback_service"
    health_checks: List[HealthCheckResult] = field(default_factory=list)
    error_message: Optional[str] = None
    notifications_sent: List[str] = field(default_factory=list)


@dataclass
class DeploymentMonitor:
    """Monitor state for a deployment."""
    deployment_id: str
    service_name: str
    environment: str
    current_version: str
    previous_version: str
    started_at: datetime
    thresholds: RollbackThresholds
    health_checks: List[HealthCheckResult] = field(default_factory=list)
    is_monitoring: bool = True
    rollback_triggered: bool = False
    last_rollback_at: Optional[datetime] = None


class AutoRollbackService:
    """
    Service for automatic rollback on health failures.

    Features:
    - Configurable rollback thresholds
    - Health monitoring after deployments
    - Automatic rollback trigger on failures
    - Team notifications on auto-rollback
    """

    _instance: Optional["AutoRollbackService"] = None

    def __new__(cls) -> "AutoRollbackService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._monitors: Dict[str, DeploymentMonitor] = {}
        self._rollback_history: List[RollbackEvent] = []
        self._notification_handlers: List[Callable[[RollbackEvent], None]] = []
        self._rollback_executor: Optional[Callable[[str, str, str], bool]] = None
        self._health_checker: Optional[Callable[[str, str], HealthCheckResult]] = None
        self._default_thresholds = RollbackThresholds()
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}

        # Prometheus metrics
        if PROMETHEUS_AVAILABLE:
            self._rollback_counter = Counter(
                "auto_rollback_total",
                "Total number of auto-rollbacks triggered",
                ["service", "environment", "reason"]
            )
            self._rollback_success_counter = Counter(
                "auto_rollback_success_total",
                "Total number of successful auto-rollbacks",
                ["service", "environment"]
            )
            self._rollback_failure_counter = Counter(
                "auto_rollback_failure_total",
                "Total number of failed auto-rollbacks",
                ["service", "environment"]
            )
            self._health_check_gauge = Gauge(
                "deployment_health_status",
                "Current health status of deployments",
                ["deployment_id", "service", "environment"]
            )
            self._rollback_duration_histogram = Histogram(
                "auto_rollback_duration_seconds",
                "Duration of auto-rollback operations",
                ["service", "environment"]
            )

        self._initialized = True
        logger.info("AutoRollbackService initialized")

    def configure_thresholds(
        self,
        thresholds: Optional[RollbackThresholds] = None,
        **kwargs
    ) -> RollbackThresholds:
        """
        Configure default rollback thresholds.

        Args:
            thresholds: Complete threshold configuration
            **kwargs: Individual threshold overrides

        Returns:
            Updated thresholds configuration
        """
        if thresholds:
            self._default_thresholds = thresholds
        else:
            for key, value in kwargs.items():
                if hasattr(self._default_thresholds, key):
                    setattr(self._default_thresholds, key, value)

        logger.info(f"Thresholds configured: {self._default_thresholds}")
        return self._default_thresholds

    def register_notification_handler(
        self,
        handler: Callable[[RollbackEvent], None]
    ) -> None:
        """
        Register a handler for rollback notifications.

        Args:
            handler: Callback function to handle notifications
        """
        self._notification_handlers.append(handler)
        logger.info(f"Notification handler registered. Total handlers: {len(self._notification_handlers)}")

    def register_rollback_executor(
        self,
        executor: Callable[[str, str, str], bool]
    ) -> None:
        """
        Register the rollback executor function.

        Args:
            executor: Function(deployment_id, service_name, target_version) -> success
        """
        self._rollback_executor = executor
        logger.info("Rollback executor registered")

    def register_health_checker(
        self,
        checker: Callable[[str, str], HealthCheckResult]
    ) -> None:
        """
        Register the health check function.

        Args:
            checker: Function(deployment_id, service_name) -> HealthCheckResult
        """
        self._health_checker = checker
        logger.info("Health checker registered")

    def start_monitoring(
        self,
        deployment_id: str,
        service_name: str,
        environment: str,
        current_version: str,
        previous_version: str,
        thresholds: Optional[RollbackThresholds] = None,
    ) -> DeploymentMonitor:
        """
        Start monitoring a deployment for health failures.

        Args:
            deployment_id: Unique deployment identifier
            service_name: Name of the deployed service
            environment: Deployment environment (dev, staging, prod)
            current_version: Currently deployed version
            previous_version: Version to rollback to if needed
            thresholds: Optional custom thresholds for this deployment

        Returns:
            DeploymentMonitor instance
        """
        monitor = DeploymentMonitor(
            deployment_id=deployment_id,
            service_name=service_name,
            environment=environment,
            current_version=current_version,
            previous_version=previous_version,
            started_at=datetime.utcnow(),
            thresholds=thresholds or self._default_thresholds,
        )

        self._monitors[deployment_id] = monitor

        logger.info(
            f"Started monitoring deployment {deployment_id} "
            f"({service_name} v{current_version} in {environment})"
        )

        return monitor

    def stop_monitoring(self, deployment_id: str) -> bool:
        """
        Stop monitoring a deployment.

        Args:
            deployment_id: Deployment to stop monitoring

        Returns:
            True if monitoring was stopped, False if not found
        """
        if deployment_id not in self._monitors:
            return False

        monitor = self._monitors[deployment_id]
        monitor.is_monitoring = False

        # Cancel any running monitoring task
        if deployment_id in self._monitoring_tasks:
            self._monitoring_tasks[deployment_id].cancel()
            del self._monitoring_tasks[deployment_id]

        logger.info(f"Stopped monitoring deployment {deployment_id}")
        return True

    def record_health_check(
        self,
        deployment_id: str,
        status: HealthStatus,
        latency_ms: Optional[float] = None,
        error_rate: Optional[float] = None,
        memory_percent: Optional[float] = None,
        cpu_percent: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[HealthCheckResult]:
        """
        Record a health check result for a deployment.

        Args:
            deployment_id: Deployment being checked
            status: Health status result
            latency_ms: Response latency in milliseconds
            error_rate: Error rate (0.0 to 1.0)
            memory_percent: Memory usage percentage
            cpu_percent: CPU usage percentage
            details: Additional details

        Returns:
            HealthCheckResult or None if deployment not found
        """
        if deployment_id not in self._monitors:
            logger.warning(f"Cannot record health check: deployment {deployment_id} not found")
            return None

        monitor = self._monitors[deployment_id]

        result = HealthCheckResult(
            check_id=str(uuid4()),
            deployment_id=deployment_id,
            timestamp=datetime.utcnow(),
            status=status,
            latency_ms=latency_ms,
            error_rate=error_rate,
            memory_percent=memory_percent,
            cpu_percent=cpu_percent,
            details=details or {},
        )

        monitor.health_checks.append(result)

        # Update Prometheus gauge
        if PROMETHEUS_AVAILABLE:
            status_value = {
                HealthStatus.HEALTHY: 1,
                HealthStatus.DEGRADED: 0.5,
                HealthStatus.UNHEALTHY: 0,
                HealthStatus.UNKNOWN: -1,
            }.get(status, -1)
            self._health_check_gauge.labels(
                deployment_id=deployment_id,
                service=monitor.service_name,
                environment=monitor.environment
            ).set(status_value)

        logger.debug(
            f"Health check recorded for {deployment_id}: {status.value} "
            f"(latency={latency_ms}ms, error_rate={error_rate})"
        )

        return result

    def evaluate_health(self, deployment_id: str) -> Dict[str, Any]:
        """
        Evaluate the overall health of a deployment.

        Args:
            deployment_id: Deployment to evaluate

        Returns:
            Evaluation result with recommendation
        """
        if deployment_id not in self._monitors:
            return {
                "deployment_id": deployment_id,
                "status": "not_found",
                "should_rollback": False,
                "reason": None,
            }

        monitor = self._monitors[deployment_id]
        thresholds = monitor.thresholds

        # Check if in cooldown period
        if monitor.last_rollback_at:
            cooldown_end = monitor.last_rollback_at + timedelta(
                seconds=thresholds.rollback_cooldown_seconds
            )
            if datetime.utcnow() < cooldown_end:
                return {
                    "deployment_id": deployment_id,
                    "status": "cooldown",
                    "should_rollback": False,
                    "reason": "In rollback cooldown period",
                    "cooldown_ends_at": cooldown_end.isoformat(),
                }

        # Get recent health checks within the failure window
        window_start = datetime.utcnow() - timedelta(
            seconds=thresholds.failure_window_seconds
        )
        recent_checks = [
            hc for hc in monitor.health_checks
            if hc.timestamp >= window_start
        ]

        if not recent_checks:
            return {
                "deployment_id": deployment_id,
                "status": "no_data",
                "should_rollback": False,
                "reason": "No health checks in window",
            }

        # Check consecutive failures
        consecutive_failures = 0
        for check in reversed(recent_checks):
            if check.status == HealthStatus.UNHEALTHY:
                consecutive_failures += 1
            else:
                break

        if consecutive_failures >= thresholds.consecutive_failures:
            return {
                "deployment_id": deployment_id,
                "status": "unhealthy",
                "should_rollback": True,
                "reason": RollbackReason.HEALTH_CHECK_FAILED,
                "consecutive_failures": consecutive_failures,
            }

        # Check error rate
        error_rates = [hc.error_rate for hc in recent_checks if hc.error_rate is not None]
        if error_rates:
            avg_error_rate = sum(error_rates) / len(error_rates)
            if avg_error_rate > thresholds.error_rate_threshold:
                return {
                    "deployment_id": deployment_id,
                    "status": "unhealthy",
                    "should_rollback": True,
                    "reason": RollbackReason.ERROR_RATE_EXCEEDED,
                    "error_rate": avg_error_rate,
                    "threshold": thresholds.error_rate_threshold,
                }

        # Check latency
        latencies = [hc.latency_ms for hc in recent_checks if hc.latency_ms is not None]
        if latencies:
            sorted_latencies = sorted(latencies)
            p99_idx = int(len(sorted_latencies) * 0.99)
            p99_latency = sorted_latencies[min(p99_idx, len(sorted_latencies) - 1)]
            if p99_latency > thresholds.latency_p99_threshold_ms:
                return {
                    "deployment_id": deployment_id,
                    "status": "unhealthy",
                    "should_rollback": True,
                    "reason": RollbackReason.LATENCY_EXCEEDED,
                    "p99_latency_ms": p99_latency,
                    "threshold_ms": thresholds.latency_p99_threshold_ms,
                }

        # Check memory usage
        memory_usages = [hc.memory_percent for hc in recent_checks if hc.memory_percent is not None]
        if memory_usages:
            avg_memory = sum(memory_usages) / len(memory_usages)
            if avg_memory > thresholds.memory_threshold_percent:
                return {
                    "deployment_id": deployment_id,
                    "status": "unhealthy",
                    "should_rollback": True,
                    "reason": RollbackReason.MEMORY_EXCEEDED,
                    "memory_percent": avg_memory,
                    "threshold_percent": thresholds.memory_threshold_percent,
                }

        # Check CPU usage
        cpu_usages = [hc.cpu_percent for hc in recent_checks if hc.cpu_percent is not None]
        if cpu_usages:
            avg_cpu = sum(cpu_usages) / len(cpu_usages)
            if avg_cpu > thresholds.cpu_threshold_percent:
                return {
                    "deployment_id": deployment_id,
                    "status": "unhealthy",
                    "should_rollback": True,
                    "reason": RollbackReason.CPU_EXCEEDED,
                    "cpu_percent": avg_cpu,
                    "threshold_percent": thresholds.cpu_threshold_percent,
                }

        # All checks passed
        return {
            "deployment_id": deployment_id,
            "status": "healthy",
            "should_rollback": False,
            "reason": None,
            "checks_evaluated": len(recent_checks),
        }

    def trigger_rollback(
        self,
        deployment_id: str,
        reason: RollbackReason,
        triggered_by: str = "auto_rollback_service",
    ) -> Optional[RollbackEvent]:
        """
        Trigger a rollback for a deployment.

        Args:
            deployment_id: Deployment to rollback
            reason: Reason for the rollback
            triggered_by: Who/what triggered the rollback

        Returns:
            RollbackEvent or None if deployment not found
        """
        if deployment_id not in self._monitors:
            logger.error(f"Cannot trigger rollback: deployment {deployment_id} not found")
            return None

        monitor = self._monitors[deployment_id]

        if monitor.rollback_triggered:
            logger.warning(f"Rollback already triggered for deployment {deployment_id}")
            return None

        # Create rollback event
        rollback_event = RollbackEvent(
            rollback_id=str(uuid4()),
            deployment_id=deployment_id,
            service_name=monitor.service_name,
            environment=monitor.environment,
            from_version=monitor.current_version,
            to_version=monitor.previous_version,
            reason=reason,
            status=RollbackStatus.PENDING,
            triggered_at=datetime.utcnow(),
            triggered_by=triggered_by,
            health_checks=list(monitor.health_checks),
        )

        monitor.rollback_triggered = True
        monitor.last_rollback_at = datetime.utcnow()

        # Update Prometheus metrics
        if PROMETHEUS_AVAILABLE:
            self._rollback_counter.labels(
                service=monitor.service_name,
                environment=monitor.environment,
                reason=reason.value
            ).inc()

        logger.warning(
            f"Rollback triggered for {deployment_id}: {reason.value} "
            f"(from v{monitor.current_version} to v{monitor.previous_version})"
        )

        # Execute rollback if executor is registered
        if self._rollback_executor:
            rollback_event.status = RollbackStatus.IN_PROGRESS
            try:
                success = self._rollback_executor(
                    deployment_id,
                    monitor.service_name,
                    monitor.previous_version
                )
                if success:
                    rollback_event.status = RollbackStatus.COMPLETED
                    rollback_event.completed_at = datetime.utcnow()
                    if PROMETHEUS_AVAILABLE:
                        self._rollback_success_counter.labels(
                            service=monitor.service_name,
                            environment=monitor.environment
                        ).inc()
                        duration = (rollback_event.completed_at - rollback_event.triggered_at).total_seconds()
                        self._rollback_duration_histogram.labels(
                            service=monitor.service_name,
                            environment=monitor.environment
                        ).observe(duration)
                else:
                    rollback_event.status = RollbackStatus.FAILED
                    rollback_event.error_message = "Rollback executor returned failure"
                    if PROMETHEUS_AVAILABLE:
                        self._rollback_failure_counter.labels(
                            service=monitor.service_name,
                            environment=monitor.environment
                        ).inc()
            except Exception as e:
                rollback_event.status = RollbackStatus.FAILED
                rollback_event.error_message = str(e)
                if PROMETHEUS_AVAILABLE:
                    self._rollback_failure_counter.labels(
                        service=monitor.service_name,
                        environment=monitor.environment
                    ).inc()
                logger.exception(f"Rollback executor failed for {deployment_id}: {e}")

        # Store in history
        self._rollback_history.append(rollback_event)

        # Send notifications
        self._send_notifications(rollback_event)

        return rollback_event

    def _send_notifications(self, event: RollbackEvent) -> None:
        """Send notifications to all registered handlers."""
        for handler in self._notification_handlers:
            try:
                handler(event)
                event.notifications_sent.append(handler.__name__)
                logger.info(f"Notification sent via {handler.__name__}")
            except Exception as e:
                logger.exception(f"Notification handler {handler.__name__} failed: {e}")

    def get_monitor(self, deployment_id: str) -> Optional[DeploymentMonitor]:
        """Get the monitor for a deployment."""
        return self._monitors.get(deployment_id)

    def get_active_monitors(self) -> List[DeploymentMonitor]:
        """Get all active deployment monitors."""
        return [m for m in self._monitors.values() if m.is_monitoring]

    def get_rollback_history(
        self,
        service_name: Optional[str] = None,
        environment: Optional[str] = None,
        status: Optional[RollbackStatus] = None,
        limit: int = 100,
    ) -> List[RollbackEvent]:
        """
        Get rollback history with optional filters.

        Args:
            service_name: Filter by service name
            environment: Filter by environment
            status: Filter by rollback status
            limit: Maximum number of events to return

        Returns:
            List of rollback events
        """
        events = self._rollback_history

        if service_name:
            events = [e for e in events if e.service_name == service_name]

        if environment:
            events = [e for e in events if e.environment == environment]

        if status:
            events = [e for e in events if e.status == status]

        # Sort by triggered_at descending and limit
        events = sorted(events, key=lambda e: e.triggered_at, reverse=True)
        return events[:limit]

    def get_statistics(
        self,
        service_name: Optional[str] = None,
        environment: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get rollback statistics.

        Args:
            service_name: Filter by service name
            environment: Filter by environment
            since: Only include events after this time

        Returns:
            Statistics dictionary
        """
        events = self._rollback_history

        if service_name:
            events = [e for e in events if e.service_name == service_name]

        if environment:
            events = [e for e in events if e.environment == environment]

        if since:
            events = [e for e in events if e.triggered_at >= since]

        if not events:
            return {
                "total_rollbacks": 0,
                "successful_rollbacks": 0,
                "failed_rollbacks": 0,
                "success_rate": 0.0,
                "by_reason": {},
                "by_service": {},
                "avg_duration_seconds": None,
            }

        successful = [e for e in events if e.status == RollbackStatus.COMPLETED]
        failed = [e for e in events if e.status == RollbackStatus.FAILED]

        # Group by reason
        by_reason: Dict[str, int] = {}
        for event in events:
            reason_key = event.reason.value
            by_reason[reason_key] = by_reason.get(reason_key, 0) + 1

        # Group by service
        by_service: Dict[str, int] = {}
        for event in events:
            by_service[event.service_name] = by_service.get(event.service_name, 0) + 1

        # Calculate average duration
        durations = []
        for event in successful:
            if event.completed_at:
                duration = (event.completed_at - event.triggered_at).total_seconds()
                durations.append(duration)

        avg_duration = sum(durations) / len(durations) if durations else None

        return {
            "total_rollbacks": len(events),
            "successful_rollbacks": len(successful),
            "failed_rollbacks": len(failed),
            "success_rate": len(successful) / len(events) if events else 0.0,
            "by_reason": by_reason,
            "by_service": by_service,
            "avg_duration_seconds": avg_duration,
        }

    async def monitor_deployment_async(
        self,
        deployment_id: str,
        auto_rollback: bool = True,
    ) -> None:
        """
        Asynchronously monitor a deployment and trigger rollback if needed.

        Args:
            deployment_id: Deployment to monitor
            auto_rollback: Whether to automatically trigger rollback
        """
        if deployment_id not in self._monitors:
            logger.error(f"Cannot monitor: deployment {deployment_id} not found")
            return

        monitor = self._monitors[deployment_id]
        thresholds = monitor.thresholds

        logger.info(f"Starting async monitoring for {deployment_id}")

        # Wait for stabilization period
        await asyncio.sleep(thresholds.stabilization_period_seconds)

        while monitor.is_monitoring and not monitor.rollback_triggered:
            try:
                # Run health check if checker is registered
                if self._health_checker:
                    result = self._health_checker(deployment_id, monitor.service_name)
                    self.record_health_check(
                        deployment_id=deployment_id,
                        status=result.status,
                        latency_ms=result.latency_ms,
                        error_rate=result.error_rate,
                        memory_percent=result.memory_percent,
                        cpu_percent=result.cpu_percent,
                        details=result.details,
                    )

                # Evaluate health
                evaluation = self.evaluate_health(deployment_id)

                if evaluation.get("should_rollback") and auto_rollback:
                    reason = evaluation.get("reason")
                    if isinstance(reason, RollbackReason):
                        self.trigger_rollback(deployment_id, reason)
                        break

                await asyncio.sleep(thresholds.health_check_interval_seconds)

            except asyncio.CancelledError:
                logger.info(f"Monitoring cancelled for {deployment_id}")
                break
            except Exception as e:
                logger.exception(f"Error during monitoring {deployment_id}: {e}")
                await asyncio.sleep(thresholds.health_check_interval_seconds)

        logger.info(f"Monitoring ended for {deployment_id}")

    def start_async_monitoring(
        self,
        deployment_id: str,
        auto_rollback: bool = True,
    ) -> Optional[asyncio.Task]:
        """
        Start asynchronous monitoring for a deployment.

        Args:
            deployment_id: Deployment to monitor
            auto_rollback: Whether to automatically trigger rollback

        Returns:
            Monitoring task or None if deployment not found
        """
        if deployment_id not in self._monitors:
            return None

        task = asyncio.create_task(
            self.monitor_deployment_async(deployment_id, auto_rollback)
        )
        self._monitoring_tasks[deployment_id] = task
        return task

    def reset(self) -> None:
        """Reset the service state (for testing)."""
        self._monitors.clear()
        self._rollback_history.clear()
        self._notification_handlers.clear()
        self._rollback_executor = None
        self._health_checker = None
        self._default_thresholds = RollbackThresholds()

        # Cancel all monitoring tasks
        for task in self._monitoring_tasks.values():
            task.cancel()
        self._monitoring_tasks.clear()

        logger.info("AutoRollbackService reset")


# Singleton instance
_auto_rollback_service: Optional[AutoRollbackService] = None


def get_auto_rollback_service() -> AutoRollbackService:
    """Get the singleton AutoRollbackService instance."""
    global _auto_rollback_service
    if _auto_rollback_service is None:
        _auto_rollback_service = AutoRollbackService()
    return _auto_rollback_service
