#!/usr/bin/env python3
"""
Deployment Health Monitor Service
Epic: MD-1790 [Platform] Unified Deployment Management GUI

Monitors health of deployed environments and provides:
- Periodic health checks
- Health status history for trending
- Real-time health status updates via WebSocket
- Configurable check intervals and thresholds

Implements AC-3: Health status per environment
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import aiohttp
import yaml

# Try to import Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, Gauge

    HEALTH_CHECKS = Counter(
        "maestro_deployment_health_checks_total",
        "Total health checks performed",
        ["environment", "status"]
    )
    HEALTH_CHECK_LATENCY = Histogram(
        "maestro_deployment_health_check_latency_seconds",
        "Health check latency",
        buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    )
    ENVIRONMENT_HEALTH = Gauge(
        "maestro_environment_health_status",
        "Current environment health status (1=healthy, 0.5=degraded, 0=unhealthy)",
        ["environment"]
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

    HEALTH_CHECKS = StubMetric()
    HEALTH_CHECK_LATENCY = StubMetric()
    ENVIRONMENT_HEALTH = StubMetric()

logger = logging.getLogger("deployment_health_monitor")


class HealthStatus(str, Enum):
    """Health status of an environment."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    environment_id: str
    environment_name: str
    status: HealthStatus
    response_time_ms: Optional[int] = None
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "environment_name": self.environment_name,
            "status": self.status.value,
            "response_time_ms": self.response_time_ms,
            "status_code": self.status_code,
            "error_message": self.error_message,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass
class HealthSnapshot:
    """A point-in-time health snapshot for history."""
    id: str
    environment_id: str
    status: HealthStatus
    response_time_ms: Optional[int]
    status_code: Optional[int]
    details: Dict[str, Any]
    recorded_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "environment_id": self.environment_id,
            "status": self.status.value,
            "response_time_ms": self.response_time_ms,
            "status_code": self.status_code,
            "recorded_at": self.recorded_at.isoformat(),
        }


class HealthSnapshotStorage:
    """
    In-memory storage for health snapshots.
    In production, this would be PostgreSQL.
    """

    def __init__(self, max_snapshots_per_env: int = 1000):
        self.snapshots: Dict[str, List[HealthSnapshot]] = {}
        self.max_snapshots_per_env = max_snapshots_per_env
        self.current_status: Dict[str, HealthCheckResult] = {}

    def add_snapshot(self, snapshot: HealthSnapshot) -> None:
        """Add a health snapshot."""
        env_id = snapshot.environment_id
        if env_id not in self.snapshots:
            self.snapshots[env_id] = []

        self.snapshots[env_id].append(snapshot)

        # Trim old snapshots
        if len(self.snapshots[env_id]) > self.max_snapshots_per_env:
            self.snapshots[env_id] = self.snapshots[env_id][-self.max_snapshots_per_env:]

    def get_snapshots(
        self,
        env_id: str,
        hours: int = 24,
        limit: int = 100,
    ) -> List[HealthSnapshot]:
        """Get health snapshots for an environment."""
        if env_id not in self.snapshots:
            return []

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        snapshots = [
            s for s in self.snapshots[env_id]
            if s.recorded_at >= cutoff
        ]
        return snapshots[-limit:]

    def set_current_status(self, result: HealthCheckResult) -> None:
        """Update current status for an environment."""
        self.current_status[result.environment_id] = result

    def get_current_status(self, env_id: str) -> Optional[HealthCheckResult]:
        """Get current status for an environment."""
        return self.current_status.get(env_id)

    def get_all_current_statuses(self) -> Dict[str, HealthCheckResult]:
        """Get current status for all environments."""
        return self.current_status.copy()

    def cleanup_old_snapshots(self, retention_hours: int = 168) -> int:
        """Remove snapshots older than retention period."""
        cutoff = datetime.utcnow() - timedelta(hours=retention_hours)
        removed_count = 0

        for env_id in self.snapshots:
            original_count = len(self.snapshots[env_id])
            self.snapshots[env_id] = [
                s for s in self.snapshots[env_id]
                if s.recorded_at >= cutoff
            ]
            removed_count += original_count - len(self.snapshots[env_id])

        return removed_count


class DeploymentHealthMonitor:
    """
    Monitors health of deployed environments.

    Performs periodic health checks, tracks status history,
    and broadcasts status changes via WebSocket.

    MD-1861: Enhanced with configurable timeout and retry logic
    for robust health endpoint verification.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        storage: Optional[HealthSnapshotStorage] = None,
        event_callback: Optional[Callable] = None,
    ):
        """
        Initialize health monitor.

        Args:
            config_path: Path to deployment configuration
            storage: Storage backend for snapshots
            event_callback: Callback for health events (WebSocket)
        """
        self.storage = storage or HealthSnapshotStorage()
        self.event_callback = event_callback
        self.config = self._load_config(config_path)
        self._monitoring_task: Optional[asyncio.Task] = None
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None

        # Track consecutive failures for threshold detection
        self._failure_counts: Dict[str, int] = {}
        self._success_counts: Dict[str, int] = {}

        # Environment configurations (will be populated from deployment service)
        self._environments: Dict[str, Dict[str, Any]] = {}

        # MD-1861: Track retry attempts per check
        self._last_retry_counts: Dict[str, int] = {}

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load health monitoring configuration."""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config",
                "deployment_config.yaml",
            )

        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f) or {}
                return config.get("health_monitor", {})
        except FileNotFoundError:
            logger.warning(f"Config file not found: {config_path}")
            return {}
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}

    @property
    def check_interval(self) -> int:
        """Get health check interval in seconds."""
        return self.config.get("interval_seconds", 30)

    @property
    def check_timeout(self) -> int:
        """Get health check timeout in seconds."""
        return self.config.get("timeout_seconds", 10)

    @property
    def unhealthy_threshold(self) -> int:
        """Number of consecutive failures before marking unhealthy."""
        return self.config.get("unhealthy_threshold", 3)

    @property
    def healthy_threshold(self) -> int:
        """Number of consecutive successes before marking healthy."""
        return self.config.get("healthy_threshold", 2)

    @property
    def max_retries(self) -> int:
        """Maximum retry attempts for failed health checks (MD-1861)."""
        return self.config.get("max_retries", 3)

    @property
    def retry_delay(self) -> float:
        """Delay between retry attempts in seconds (MD-1861)."""
        return self.config.get("retry_delay_seconds", 1.0)

    @property
    def retry_backoff_multiplier(self) -> float:
        """Exponential backoff multiplier for retries (MD-1861)."""
        return self.config.get("retry_backoff_multiplier", 2.0)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.check_timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def register_environment(
        self,
        env_id: str,
        name: str,
        health_url: str,
    ) -> None:
        """Register an environment for health monitoring."""
        self._environments[env_id] = {
            "id": env_id,
            "name": name,
            "health_url": health_url,
        }
        self._failure_counts[env_id] = 0
        self._success_counts[env_id] = 0
        logger.info(f"Registered environment for health monitoring: {name}")

    def unregister_environment(self, env_id: str) -> None:
        """Unregister an environment from health monitoring."""
        if env_id in self._environments:
            del self._environments[env_id]
        if env_id in self._failure_counts:
            del self._failure_counts[env_id]
        if env_id in self._success_counts:
            del self._success_counts[env_id]

    async def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit a health event."""
        if self.event_callback:
            try:
                event = {
                    "type": event_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": data,
                }
                if asyncio.iscoroutinefunction(self.event_callback):
                    await self.event_callback(event)
                else:
                    self.event_callback(event)
            except Exception as e:
                logger.error(f"Error emitting event: {e}")

    async def _single_health_check(
        self,
        env_id: str,
        env_config: Dict[str, Any],
        health_url: str,
    ) -> HealthCheckResult:
        """
        Perform a single health check attempt (internal method).

        MD-1861: Extracted for retry logic support.

        Args:
            env_id: Environment ID
            env_config: Environment configuration
            health_url: Health endpoint URL

        Returns:
            HealthCheckResult from single attempt
        """
        session = await self._get_session()
        start_time = asyncio.get_event_loop().time()

        async with session.get(health_url) as response:
            response_time_ms = int(
                (asyncio.get_event_loop().time() - start_time) * 1000
            )

            # Parse response
            details = {}
            try:
                details = await response.json()
            except Exception:
                details = {"raw": await response.text()[:500]}

            # Determine status based on response code
            expected_codes = self.config.get("expected_status_codes", [200, 204])
            if response.status in expected_codes:
                raw_status = HealthStatus.HEALTHY
                self._success_counts[env_id] = self._success_counts.get(env_id, 0) + 1
                self._failure_counts[env_id] = 0
            else:
                raw_status = HealthStatus.UNHEALTHY
                self._failure_counts[env_id] = self._failure_counts.get(env_id, 0) + 1
                self._success_counts[env_id] = 0

            # Apply threshold logic
            status = self._apply_threshold(env_id, raw_status)

            result = HealthCheckResult(
                environment_id=env_id,
                environment_name=env_config.get("name", "Unknown"),
                status=status,
                response_time_ms=response_time_ms,
                status_code=response.status,
                details=details,
            )

            HEALTH_CHECKS.labels(
                environment=env_config.get("name"),
                status=status.value
            ).inc()
            HEALTH_CHECK_LATENCY.observe(response_time_ms / 1000.0)

            # Update Prometheus gauge
            gauge_value = 1.0 if status == HealthStatus.HEALTHY else (
                0.5 if status == HealthStatus.DEGRADED else 0.0
            )
            ENVIRONMENT_HEALTH.labels(
                environment=env_config.get("name")
            ).set(gauge_value)

            return result

    async def check_environment_health(
        self,
        env_id: str,
    ) -> HealthCheckResult:
        """
        Perform health check for a single environment with retry logic.

        MD-1861: Enhanced with configurable timeout and retry mechanism.
        Implements exponential backoff for transient failures.

        Args:
            env_id: Environment ID

        Returns:
            HealthCheckResult with status and metrics
        """
        env_config = self._environments.get(env_id)
        if not env_config:
            return HealthCheckResult(
                environment_id=env_id,
                environment_name="Unknown",
                status=HealthStatus.UNKNOWN,
                error_message="Environment not registered",
            )

        health_url = env_config.get("health_url")
        if not health_url:
            return HealthCheckResult(
                environment_id=env_id,
                environment_name=env_config.get("name", "Unknown"),
                status=HealthStatus.UNKNOWN,
                error_message="No health URL configured",
            )

        # MD-1861: Retry logic with exponential backoff
        last_error: Optional[str] = None
        delay = self.retry_delay

        for attempt in range(self.max_retries + 1):
            try:
                result = await self._single_health_check(env_id, env_config, health_url)
                # MD-1861: Track retry count for observability
                # attempt is 0-indexed, so attempt > 0 means we retried
                self._last_retry_counts[env_id] = attempt
                if attempt > 0:
                    result.details["retry_count"] = attempt
                    logger.info(
                        f"Health check for {env_config.get('name')} succeeded "
                        f"after {attempt} retries"
                    )
                return result

            except asyncio.TimeoutError:
                last_error = "Health check timed out"
                if attempt < self.max_retries:
                    logger.warning(
                        f"Health check timeout for {env_config.get('name')}, "
                        f"retry {attempt + 1}/{self.max_retries} in {delay}s"
                    )
                    await asyncio.sleep(delay)
                    delay *= self.retry_backoff_multiplier

            except aiohttp.ClientError as e:
                last_error = f"Connection error: {str(e)}"
                if attempt < self.max_retries:
                    logger.warning(
                        f"Health check connection error for {env_config.get('name')}: {e}, "
                        f"retry {attempt + 1}/{self.max_retries} in {delay}s"
                    )
                    await asyncio.sleep(delay)
                    delay *= self.retry_backoff_multiplier

            except Exception as e:
                # Non-retryable errors
                logger.error(f"Unexpected error checking health for {env_id}: {e}")
                self._last_retry_counts[env_id] = attempt
                return HealthCheckResult(
                    environment_id=env_id,
                    environment_name=env_config.get("name", "Unknown"),
                    status=HealthStatus.UNKNOWN,
                    error_message=f"Unexpected error: {str(e)}",
                    details={"retry_count": attempt},
                )

        # All retries exhausted (max_retries attempts were made after initial)
        self._failure_counts[env_id] = self._failure_counts.get(env_id, 0) + 1
        self._success_counts[env_id] = 0
        status = self._apply_threshold(env_id, HealthStatus.UNHEALTHY)
        self._last_retry_counts[env_id] = self.max_retries

        logger.error(
            f"Health check for {env_config.get('name')} failed after "
            f"{self.max_retries} retries: {last_error}"
        )

        return HealthCheckResult(
            environment_id=env_id,
            environment_name=env_config.get("name", "Unknown"),
            status=status,
            error_message=f"{last_error} (after {self.max_retries} retries)",
            details={"retry_count": self.max_retries, "max_retries": self.max_retries},
        )

    def _apply_threshold(
        self,
        env_id: str,
        raw_status: HealthStatus,
    ) -> HealthStatus:
        """
        Apply threshold logic to determine final status.

        Uses consecutive success/failure counts to prevent flapping.
        """
        current = self.storage.get_current_status(env_id)
        current_status = current.status if current else HealthStatus.UNKNOWN

        failures = self._failure_counts.get(env_id, 0)
        successes = self._success_counts.get(env_id, 0)

        if raw_status == HealthStatus.HEALTHY:
            if successes >= self.healthy_threshold:
                return HealthStatus.HEALTHY
            elif current_status == HealthStatus.UNHEALTHY:
                return HealthStatus.DEGRADED
            else:
                return current_status or HealthStatus.HEALTHY

        else:  # UNHEALTHY
            if failures >= self.unhealthy_threshold:
                return HealthStatus.UNHEALTHY
            elif current_status == HealthStatus.HEALTHY:
                return HealthStatus.DEGRADED
            else:
                return current_status or HealthStatus.UNHEALTHY

    async def check_all_environments(self) -> Dict[str, HealthCheckResult]:
        """
        Check health of all registered environments.

        Returns:
            Dictionary mapping environment ID to health result
        """
        results = {}

        tasks = [
            self.check_environment_health(env_id)
            for env_id in self._environments
        ]

        if tasks:
            completed = await asyncio.gather(*tasks, return_exceptions=True)

            for result in completed:
                if isinstance(result, HealthCheckResult):
                    results[result.environment_id] = result
                    await self._process_result(result)

        return results

    async def _process_result(self, result: HealthCheckResult) -> None:
        """Process a health check result."""
        previous = self.storage.get_current_status(result.environment_id)
        self.storage.set_current_status(result)

        # Record snapshot
        import uuid
        snapshot = HealthSnapshot(
            id=str(uuid.uuid4()),
            environment_id=result.environment_id,
            status=result.status,
            response_time_ms=result.response_time_ms,
            status_code=result.status_code,
            details=result.details,
            recorded_at=result.checked_at,
        )
        self.storage.add_snapshot(snapshot)

        # Emit event if status changed
        if previous is None or previous.status != result.status:
            await self._emit_event("health_status_changed", {
                "environment_id": result.environment_id,
                "environment_name": result.environment_name,
                "previous_status": previous.status.value if previous else None,
                "current_status": result.status.value,
                "response_time_ms": result.response_time_ms,
                "error_message": result.error_message,
            })

    async def start_monitoring(
        self,
        interval_override: Optional[int] = None,
    ) -> None:
        """
        Start background health monitoring.

        Args:
            interval_override: Override check interval from config
        """
        if self._running:
            logger.warning("Health monitoring already running")
            return

        self._running = True
        interval = interval_override or self.check_interval

        logger.info(
            f"Starting health monitoring for {len(self._environments)} environments "
            f"(interval: {interval}s)"
        )

        async def monitoring_loop():
            while self._running:
                try:
                    await self.check_all_environments()
                except Exception as e:
                    logger.error(f"Error in health monitoring loop: {e}")

                await asyncio.sleep(interval)

        self._monitoring_task = asyncio.create_task(monitoring_loop())

    async def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        self._running = False

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

        await self.close()
        logger.info("Health monitoring stopped")

    def get_current_status(
        self,
        env_id: str,
    ) -> Optional[HealthCheckResult]:
        """Get current health status for an environment."""
        return self.storage.get_current_status(env_id)

    def get_all_current_statuses(self) -> Dict[str, HealthCheckResult]:
        """Get current health status for all environments."""
        return self.storage.get_all_current_statuses()

    async def get_health_history(
        self,
        env_id: str,
        hours: int = 24,
        limit: int = 100,
    ) -> List[HealthSnapshot]:
        """
        Get health history for an environment.

        Args:
            env_id: Environment ID
            hours: How many hours of history to retrieve
            limit: Maximum snapshots to return

        Returns:
            List of health snapshots
        """
        return self.storage.get_snapshots(env_id, hours, limit)

    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all environment health.

        Returns:
            Summary with counts by status
        """
        statuses = self.storage.get_all_current_statuses()

        summary = {
            "total": len(statuses),
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "unknown": 0,
            "environments": {},
        }

        for env_id, result in statuses.items():
            status_key = result.status.value
            summary[status_key] = summary.get(status_key, 0) + 1
            summary["environments"][env_id] = {
                "name": result.environment_name,
                "status": result.status.value,
                "response_time_ms": result.response_time_ms,
                "last_check": result.checked_at.isoformat(),
                # MD-1861: Include retry info
                "last_retry_count": self._last_retry_counts.get(env_id, 0),
            }

        return summary

    def get_retry_config(self) -> Dict[str, Any]:
        """
        Get current retry configuration (MD-1861).

        Returns:
            Dictionary with retry settings
        """
        return {
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay,
            "retry_backoff_multiplier": self.retry_backoff_multiplier,
            "timeout_seconds": self.check_timeout,
        }

    def get_retry_stats(self, env_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get retry statistics for health checks (MD-1861).

        Args:
            env_id: Optional environment ID (None = all environments)

        Returns:
            Dictionary with retry statistics
        """
        if env_id:
            return {
                "environment_id": env_id,
                "last_retry_count": self._last_retry_counts.get(env_id, 0),
                "max_retries": self.max_retries,
            }

        return {
            "config": self.get_retry_config(),
            "environments": {
                eid: {
                    "last_retry_count": count,
                    "environment_name": self._environments.get(eid, {}).get("name", "Unknown"),
                }
                for eid, count in self._last_retry_counts.items()
            },
        }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_monitor: Optional[DeploymentHealthMonitor] = None


def get_deployment_health_monitor() -> DeploymentHealthMonitor:
    """Get the singleton health monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = DeploymentHealthMonitor()
    return _monitor


async def cleanup_health_monitor() -> None:
    """Cleanup the singleton monitor."""
    global _monitor
    if _monitor:
        await _monitor.stop_monitoring()
        _monitor = None
