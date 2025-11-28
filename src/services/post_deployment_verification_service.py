#!/usr/bin/env python3
"""
Post-Deployment Verification & Rollback Service
Epic: MD-1873 [Deploy] Post-Deployment Verification & Rollback

Automated deployment verification system including:

### Verification
- Post-deploy smoke checks
- Health endpoint verification
- Evidence recording

### Rollback
- Automatic rollback trigger
- ACC gate status updates

### Integration
- Quality-Fabric ACC gate integration

Acceptance Criteria:
- AC-1: Post-deploy smoke checks run automatically after deployment
- AC-2: Health endpoint verification with configurable checks
- AC-3: Evidence recording for audit trail
- AC-4: Automatic rollback trigger on verification failure
- AC-5: ACC gate status updates for Quality-Fabric integration
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import aiohttp

# Try to import Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, Gauge

    VERIFICATION_RUNS = Counter(
        "maestro_post_deploy_verifications_total",
        "Total post-deployment verifications",
        ["environment", "status"]
    )
    VERIFICATION_DURATION = Histogram(
        "maestro_post_deploy_verification_seconds",
        "Post-deployment verification duration",
        buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
    )
    SMOKE_CHECK_COUNTER = Counter(
        "maestro_smoke_checks_total",
        "Total smoke checks executed",
        ["check_name", "status"]
    )
    ROLLBACK_TRIGGERS = Counter(
        "maestro_rollback_triggers_total",
        "Total automatic rollback triggers",
        ["environment", "reason"]
    )
    ACC_GATE_UPDATES = Counter(
        "maestro_acc_gate_updates_total",
        "Total ACC gate status updates",
        ["gate_name", "status"]
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

    VERIFICATION_RUNS = StubMetric()
    VERIFICATION_DURATION = StubMetric()
    SMOKE_CHECK_COUNTER = StubMetric()
    ROLLBACK_TRIGGERS = StubMetric()
    ACC_GATE_UPDATES = StubMetric()

logger = logging.getLogger("post_deployment_verification_service")


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class VerificationStatus(str, Enum):
    """Status of a post-deployment verification."""
    PENDING = "pending"           # Verification not started
    IN_PROGRESS = "in_progress"   # Verification running
    PASSED = "passed"             # All checks passed
    FAILED = "failed"             # One or more checks failed
    ROLLED_BACK = "rolled_back"   # Failed and rollback triggered
    SKIPPED = "skipped"           # Verification skipped


class SmokeCheckType(str, Enum):
    """Types of smoke checks."""
    HEALTH = "health"           # Health endpoint check
    API = "api"                 # API endpoint check
    DATABASE = "database"       # Database connectivity
    CACHE = "cache"             # Cache connectivity (Redis)
    EXTERNAL = "external"       # External service check
    CUSTOM = "custom"           # Custom check function


class SmokeCheckStatus(str, Enum):
    """Status of individual smoke check."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


class ACCGateStatus(str, Enum):
    """ACC gate status for Quality-Fabric integration."""
    OPEN = "open"       # Gate is open, deployment can proceed
    CLOSED = "closed"   # Gate is closed, deployment blocked
    PENDING = "pending" # Gate status pending verification


class RollbackReason(str, Enum):
    """Reason for triggering rollback."""
    HEALTH_CHECK_FAILED = "health_check_failed"
    SMOKE_CHECK_FAILED = "smoke_check_failed"
    TIMEOUT = "timeout"
    MANUAL = "manual"
    ACC_GATE_CLOSED = "acc_gate_closed"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class SmokeCheckConfig:
    """Configuration for a smoke check."""
    name: str
    check_type: SmokeCheckType
    endpoint: Optional[str] = None
    method: str = "GET"
    expected_status: int = 200
    timeout_seconds: float = 10.0
    retry_count: int = 3
    retry_delay_seconds: float = 2.0
    required: bool = True
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None
    validation_fn: Optional[str] = None  # Name of validation function
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "check_type": self.check_type.value,
            "endpoint": self.endpoint,
            "method": self.method,
            "expected_status": self.expected_status,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "required": self.required,
            "description": self.description,
        }


@dataclass
class SmokeCheckResult:
    """Result of a smoke check."""
    check_id: str
    config: SmokeCheckConfig
    status: SmokeCheckStatus
    response_time_ms: Optional[int] = None
    actual_status_code: Optional[int] = None
    error_message: Optional[str] = None
    response_body: Optional[str] = None
    retries_attempted: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.config.name,
            "check_type": self.config.check_type.value,
            "status": self.status.value,
            "response_time_ms": self.response_time_ms,
            "actual_status_code": self.actual_status_code,
            "error_message": self.error_message,
            "retries_attempted": self.retries_attempted,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "required": self.config.required,
        }


@dataclass
class VerificationEvidence:
    """
    Evidence record for audit trail.

    AC-3: Evidence recording for audit trail
    """
    evidence_id: str
    verification_id: str
    deployment_id: str
    environment: str
    evidence_type: str  # "smoke_check", "health_check", "rollback", "acc_gate"
    timestamp: datetime
    status: str
    details: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "verification_id": self.verification_id,
            "deployment_id": self.deployment_id,
            "environment": self.environment,
            "evidence_type": self.evidence_type,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "details": self.details,
            "metadata": self.metadata,
        }


@dataclass
class VerificationRun:
    """A post-deployment verification run."""
    verification_id: str
    deployment_id: str
    environment_id: str
    environment_name: str
    version: str
    status: VerificationStatus
    triggered_by: str
    smoke_check_results: List[SmokeCheckResult] = field(default_factory=list)
    health_check_passed: bool = False
    acc_gate_status: ACCGateStatus = ACCGateStatus.PENDING
    rollback_triggered: bool = False
    rollback_reason: Optional[RollbackReason] = None
    rollback_deployment_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        passed_checks = len([r for r in self.smoke_check_results if r.status == SmokeCheckStatus.PASSED])
        failed_checks = len([r for r in self.smoke_check_results if r.status == SmokeCheckStatus.FAILED])

        return {
            "verification_id": self.verification_id,
            "deployment_id": self.deployment_id,
            "environment_id": self.environment_id,
            "environment_name": self.environment_name,
            "version": self.version,
            "status": self.status.value,
            "triggered_by": self.triggered_by,
            "smoke_checks": {
                "total": len(self.smoke_check_results),
                "passed": passed_checks,
                "failed": failed_checks,
                "results": [r.to_dict() for r in self.smoke_check_results],
            },
            "health_check_passed": self.health_check_passed,
            "acc_gate_status": self.acc_gate_status.value,
            "rollback_triggered": self.rollback_triggered,
            "rollback_reason": self.rollback_reason.value if self.rollback_reason else None,
            "rollback_deployment_id": self.rollback_deployment_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "duration_seconds": self.get_duration_seconds(),
        }

    def get_duration_seconds(self) -> Optional[float]:
        """Get verification duration in seconds."""
        if self.started_at:
            end_time = self.completed_at or datetime.utcnow()
            return round((end_time - self.started_at).total_seconds(), 2)
        return None


@dataclass
class ACCGateConfig:
    """
    ACC gate configuration for Quality-Fabric integration.

    AC-5: ACC gate status updates for Quality-Fabric integration
    """
    gate_name: str
    gate_id: str
    quality_fabric_url: str = "http://localhost:8000"
    required_checks: List[str] = field(default_factory=list)
    auto_close_on_failure: bool = True
    timeout_seconds: float = 30.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "gate_id": self.gate_id,
            "quality_fabric_url": self.quality_fabric_url,
            "required_checks": self.required_checks,
            "auto_close_on_failure": self.auto_close_on_failure,
            "timeout_seconds": self.timeout_seconds,
        }


# ============================================================================
# IN-MEMORY STORAGE
# ============================================================================

class VerificationStorage:
    """In-memory storage for verification records."""

    def __init__(self, max_records: int = 1000):
        self.verifications: Dict[str, VerificationRun] = {}
        self.evidence: Dict[str, List[VerificationEvidence]] = {}
        self.max_records = max_records

    def add_verification(self, run: VerificationRun) -> None:
        """Add a verification run."""
        self.verifications[run.verification_id] = run
        if run.verification_id not in self.evidence:
            self.evidence[run.verification_id] = []

        # Trim old records
        if len(self.verifications) > self.max_records:
            oldest = sorted(
                self.verifications.values(),
                key=lambda v: v.created_at
            )[:len(self.verifications) - self.max_records]
            for v in oldest:
                del self.verifications[v.verification_id]
                if v.verification_id in self.evidence:
                    del self.evidence[v.verification_id]

    def get_verification(self, verification_id: str) -> Optional[VerificationRun]:
        """Get verification by ID."""
        return self.verifications.get(verification_id)

    def update_verification(self, run: VerificationRun) -> None:
        """Update verification run."""
        self.verifications[run.verification_id] = run

    def get_verifications_for_deployment(
        self,
        deployment_id: str,
    ) -> List[VerificationRun]:
        """Get verifications for a deployment."""
        return [
            v for v in self.verifications.values()
            if v.deployment_id == deployment_id
        ]

    def get_latest_verification(
        self,
        environment_id: str,
    ) -> Optional[VerificationRun]:
        """Get latest verification for an environment."""
        verifications = [
            v for v in self.verifications.values()
            if v.environment_id == environment_id
        ]
        if not verifications:
            return None
        return max(verifications, key=lambda v: v.created_at)

    def add_evidence(self, evidence: VerificationEvidence) -> None:
        """Add evidence record."""
        if evidence.verification_id not in self.evidence:
            self.evidence[evidence.verification_id] = []
        self.evidence[evidence.verification_id].append(evidence)

    def get_evidence(
        self,
        verification_id: str,
    ) -> List[VerificationEvidence]:
        """Get evidence for a verification."""
        return self.evidence.get(verification_id, [])

    def get_all_verifications(
        self,
        limit: int = 50,
        status: Optional[VerificationStatus] = None,
    ) -> List[VerificationRun]:
        """Get all verifications."""
        verifications = list(self.verifications.values())
        if status:
            verifications = [v for v in verifications if v.status == status]
        verifications.sort(key=lambda v: v.created_at, reverse=True)
        return verifications[:limit]


# Global storage instance
_storage = VerificationStorage()


# ============================================================================
# POST-DEPLOYMENT VERIFICATION SERVICE
# ============================================================================

class PostDeploymentVerificationService:
    """
    Post-Deployment Verification & Rollback Service.

    Provides automated verification after deployments with:
    - Smoke check execution
    - Health endpoint verification
    - Evidence recording
    - Automatic rollback triggers
    - ACC gate integration
    """

    def __init__(
        self,
        storage: Optional[VerificationStorage] = None,
        deployment_service: Optional[Any] = None,
        health_monitor: Optional[Any] = None,
        event_callback: Optional[Callable] = None,
        acc_gate_config: Optional[ACCGateConfig] = None,
    ):
        """
        Initialize verification service.

        Args:
            storage: Storage backend
            deployment_service: Reference to deployment service for rollbacks
            health_monitor: Reference to health monitor
            event_callback: Callback for verification events
            acc_gate_config: ACC gate configuration
        """
        self.storage = storage or _storage
        self.deployment_service = deployment_service
        self.health_monitor = health_monitor
        self.event_callback = event_callback
        self.acc_gate_config = acc_gate_config

        self._session: Optional[aiohttp.ClientSession] = None

        # Default smoke checks
        self._default_smoke_checks: List[SmokeCheckConfig] = [
            SmokeCheckConfig(
                name="health_endpoint",
                check_type=SmokeCheckType.HEALTH,
                endpoint="/health",
                expected_status=200,
                timeout_seconds=10.0,
                required=True,
                description="Basic health endpoint check",
            ),
            SmokeCheckConfig(
                name="api_status",
                check_type=SmokeCheckType.API,
                endpoint="/api/status",
                expected_status=200,
                timeout_seconds=15.0,
                required=True,
                description="API status endpoint check",
            ),
        ]

        # Custom validation functions
        self._validation_functions: Dict[str, Callable] = {}

        logger.info("PostDeploymentVerificationService initialized")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=60)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit verification event."""
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

    def register_validation_function(
        self,
        name: str,
        fn: Callable[[Dict[str, Any]], bool],
    ) -> None:
        """Register a custom validation function."""
        self._validation_functions[name] = fn

    def set_smoke_checks(self, checks: List[SmokeCheckConfig]) -> None:
        """Set custom smoke checks."""
        self._default_smoke_checks = checks

    def add_smoke_check(self, check: SmokeCheckConfig) -> None:
        """Add a smoke check configuration."""
        self._default_smoke_checks.append(check)

    # =========================================================================
    # AC-1: Post-deploy smoke checks
    # =========================================================================

    async def run_smoke_check(
        self,
        base_url: str,
        config: SmokeCheckConfig,
    ) -> SmokeCheckResult:
        """
        Run a single smoke check.

        AC-1: Post-deploy smoke checks run automatically after deployment

        Args:
            base_url: Base URL for the environment
            config: Smoke check configuration

        Returns:
            SmokeCheckResult with status and details
        """
        check_id = str(uuid.uuid4())[:8]
        result = SmokeCheckResult(
            check_id=check_id,
            config=config,
            status=SmokeCheckStatus.RUNNING,
            started_at=datetime.utcnow(),
        )

        if not config.endpoint:
            result.status = SmokeCheckStatus.SKIPPED
            result.error_message = "No endpoint configured"
            result.completed_at = datetime.utcnow()
            return result

        url = f"{base_url.rstrip('/')}{config.endpoint}"
        session = await self._get_session()

        last_error: Optional[str] = None

        for attempt in range(config.retry_count + 1):
            result.retries_attempted = attempt

            try:
                timeout = aiohttp.ClientTimeout(total=config.timeout_seconds)
                start_time = asyncio.get_event_loop().time()

                async with session.request(
                    method=config.method,
                    url=url,
                    headers=config.headers,
                    json=config.body if config.body else None,
                    timeout=timeout,
                ) as response:
                    response_time = int(
                        (asyncio.get_event_loop().time() - start_time) * 1000
                    )

                    result.response_time_ms = response_time
                    result.actual_status_code = response.status

                    try:
                        body = await response.text()
                        result.response_body = body[:1000]  # Limit size
                    except Exception:
                        result.response_body = None

                    # Check status code
                    if response.status == config.expected_status:
                        # Run custom validation if configured
                        if config.validation_fn and config.validation_fn in self._validation_functions:
                            try:
                                validation_data = {
                                    "status_code": response.status,
                                    "body": result.response_body,
                                    "response_time_ms": response_time,
                                }
                                is_valid = self._validation_functions[config.validation_fn](validation_data)
                                if not is_valid:
                                    result.status = SmokeCheckStatus.FAILED
                                    result.error_message = "Custom validation failed"
                                else:
                                    result.status = SmokeCheckStatus.PASSED
                            except Exception as e:
                                result.status = SmokeCheckStatus.FAILED
                                result.error_message = f"Validation error: {str(e)}"
                        else:
                            result.status = SmokeCheckStatus.PASSED

                        result.completed_at = datetime.utcnow()
                        SMOKE_CHECK_COUNTER.labels(
                            check_name=config.name,
                            status="passed"
                        ).inc()
                        return result
                    else:
                        last_error = f"Expected {config.expected_status}, got {response.status}"

            except asyncio.TimeoutError:
                last_error = f"Timeout after {config.timeout_seconds}s"

            except aiohttp.ClientError as e:
                last_error = f"Connection error: {str(e)}"

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"

            # Wait before retry
            if attempt < config.retry_count:
                await asyncio.sleep(config.retry_delay_seconds)

        # All retries exhausted
        result.status = SmokeCheckStatus.FAILED
        result.error_message = f"{last_error} (after {config.retry_count} retries)"
        result.completed_at = datetime.utcnow()

        SMOKE_CHECK_COUNTER.labels(
            check_name=config.name,
            status="failed"
        ).inc()

        return result

    async def run_smoke_checks(
        self,
        base_url: str,
        checks: Optional[List[SmokeCheckConfig]] = None,
    ) -> List[SmokeCheckResult]:
        """
        Run all smoke checks.

        Args:
            base_url: Base URL for the environment
            checks: Optional custom checks (uses defaults if not provided)

        Returns:
            List of SmokeCheckResult
        """
        checks_to_run = checks or self._default_smoke_checks
        results = []

        for config in checks_to_run:
            result = await self.run_smoke_check(base_url, config)
            results.append(result)

            # Stop on required check failure if configured
            if result.status == SmokeCheckStatus.FAILED and config.required:
                logger.warning(f"Required smoke check failed: {config.name}")
                # Continue running other checks for full picture

        return results

    # =========================================================================
    # AC-2: Health endpoint verification
    # =========================================================================

    async def verify_health_endpoint(
        self,
        health_url: str,
        timeout_seconds: float = 30.0,
        retry_count: int = 5,
        retry_delay: float = 2.0,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify health endpoint is responding correctly.

        AC-2: Health endpoint verification with configurable checks

        Args:
            health_url: Health endpoint URL
            timeout_seconds: Request timeout
            retry_count: Number of retries
            retry_delay: Delay between retries

        Returns:
            Tuple of (is_healthy, details)
        """
        session = await self._get_session()
        last_error: Optional[str] = None

        for attempt in range(retry_count + 1):
            try:
                timeout = aiohttp.ClientTimeout(total=timeout_seconds)
                start_time = asyncio.get_event_loop().time()

                async with session.get(health_url, timeout=timeout) as response:
                    response_time = int(
                        (asyncio.get_event_loop().time() - start_time) * 1000
                    )

                    try:
                        body = await response.json()
                    except Exception:
                        body = {"raw": await response.text()[:500]}

                    if response.status in [200, 204]:
                        return True, {
                            "status_code": response.status,
                            "response_time_ms": response_time,
                            "body": body,
                            "attempts": attempt + 1,
                        }
                    else:
                        last_error = f"Unhealthy status: {response.status}"

            except asyncio.TimeoutError:
                last_error = "Health check timeout"

            except aiohttp.ClientError as e:
                last_error = f"Connection error: {str(e)}"

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"

            if attempt < retry_count:
                await asyncio.sleep(retry_delay)

        return False, {
            "error": last_error,
            "attempts": retry_count + 1,
        }

    # =========================================================================
    # AC-3: Evidence recording
    # =========================================================================

    async def record_evidence(
        self,
        verification_id: str,
        deployment_id: str,
        environment: str,
        evidence_type: str,
        status: str,
        details: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VerificationEvidence:
        """
        Record evidence for audit trail.

        AC-3: Evidence recording for audit trail

        Args:
            verification_id: Verification run ID
            deployment_id: Deployment ID
            environment: Environment name
            evidence_type: Type of evidence
            status: Status of the check
            details: Detailed information
            metadata: Additional metadata

        Returns:
            VerificationEvidence record
        """
        evidence = VerificationEvidence(
            evidence_id=str(uuid.uuid4()),
            verification_id=verification_id,
            deployment_id=deployment_id,
            environment=environment,
            evidence_type=evidence_type,
            timestamp=datetime.utcnow(),
            status=status,
            details=details,
            metadata=metadata or {},
        )

        self.storage.add_evidence(evidence)

        logger.info(
            f"Evidence recorded: {evidence_type} - {status} "
            f"(verification: {verification_id[:8]})"
        )

        return evidence

    # =========================================================================
    # AC-4: Automatic rollback trigger
    # =========================================================================

    async def trigger_automatic_rollback(
        self,
        verification: VerificationRun,
        reason: RollbackReason,
        previous_deployment_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Trigger automatic rollback on verification failure.

        AC-4: Automatic rollback trigger on verification failure

        Args:
            verification: Failed verification run
            reason: Reason for rollback
            previous_deployment_id: ID of deployment to rollback to

        Returns:
            Rollback deployment ID if triggered, None otherwise
        """
        if not self.deployment_service:
            logger.warning("Deployment service not configured, cannot rollback")
            return None

        if not previous_deployment_id:
            # Find previous successful deployment
            try:
                history = await self.deployment_service.get_deployment_history(
                    env_id=verification.environment_id,
                    limit=10,
                )
                previous = next(
                    (d for d in history
                     if d.status.value == "success"
                     and d.id != verification.deployment_id),
                    None
                )
                if previous:
                    previous_deployment_id = previous.id
            except Exception as e:
                logger.error(f"Error finding previous deployment: {e}")

        if not previous_deployment_id:
            logger.error("No previous deployment found for rollback")
            return None

        try:
            rollback = await self.deployment_service.rollback_deployment(
                deployment_id=previous_deployment_id,
                triggered_by="post_deployment_verification_service",
            )

            verification.rollback_triggered = True
            verification.rollback_reason = reason
            verification.rollback_deployment_id = rollback.id
            verification.status = VerificationStatus.ROLLED_BACK
            self.storage.update_verification(verification)

            # Record evidence
            await self.record_evidence(
                verification_id=verification.verification_id,
                deployment_id=verification.deployment_id,
                environment=verification.environment_name,
                evidence_type="rollback",
                status="triggered",
                details={
                    "reason": reason.value,
                    "rollback_to_deployment": previous_deployment_id,
                    "rollback_deployment_id": rollback.id,
                },
            )

            ROLLBACK_TRIGGERS.labels(
                environment=verification.environment_name,
                reason=reason.value
            ).inc()

            await self._emit_event("rollback_triggered", {
                "verification_id": verification.verification_id,
                "deployment_id": verification.deployment_id,
                "environment": verification.environment_name,
                "reason": reason.value,
                "rollback_deployment_id": rollback.id,
            })

            logger.warning(
                f"Automatic rollback triggered for {verification.environment_name}: "
                f"{reason.value}"
            )

            return rollback.id

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            await self.record_evidence(
                verification_id=verification.verification_id,
                deployment_id=verification.deployment_id,
                environment=verification.environment_name,
                evidence_type="rollback",
                status="failed",
                details={"error": str(e)},
            )
            return None

    # =========================================================================
    # AC-5: ACC gate status updates
    # =========================================================================

    async def update_acc_gate_status(
        self,
        verification: VerificationRun,
        status: ACCGateStatus,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update ACC gate status for Quality-Fabric integration.

        AC-5: ACC gate status updates for Quality-Fabric integration

        Args:
            verification: Verification run
            status: New gate status
            details: Additional details

        Returns:
            True if update successful
        """
        if not self.acc_gate_config:
            logger.debug("ACC gate not configured")
            return False

        verification.acc_gate_status = status
        self.storage.update_verification(verification)

        try:
            session = await self._get_session()

            payload = {
                "gate_id": self.acc_gate_config.gate_id,
                "gate_name": self.acc_gate_config.gate_name,
                "status": status.value,
                "deployment_id": verification.deployment_id,
                "environment": verification.environment_name,
                "version": verification.version,
                "verification_id": verification.verification_id,
                "timestamp": datetime.utcnow().isoformat(),
                "details": details or {},
            }

            url = f"{self.acc_gate_config.quality_fabric_url}/api/gates/{self.acc_gate_config.gate_id}/status"

            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.acc_gate_config.timeout_seconds),
            ) as response:
                if response.status in [200, 201, 204]:
                    ACC_GATE_UPDATES.labels(
                        gate_name=self.acc_gate_config.gate_name,
                        status=status.value
                    ).inc()

                    logger.info(
                        f"ACC gate {self.acc_gate_config.gate_name} updated to {status.value}"
                    )

                    # Record evidence
                    await self.record_evidence(
                        verification_id=verification.verification_id,
                        deployment_id=verification.deployment_id,
                        environment=verification.environment_name,
                        evidence_type="acc_gate",
                        status=status.value,
                        details={
                            "gate_id": self.acc_gate_config.gate_id,
                            "gate_name": self.acc_gate_config.gate_name,
                            "response_status": response.status,
                        },
                    )

                    return True
                else:
                    logger.error(f"ACC gate update failed: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"ACC gate update error: {e}")
            return False

    # =========================================================================
    # Main Verification Flow
    # =========================================================================

    async def verify_deployment(
        self,
        deployment_id: str,
        environment_id: str,
        environment_name: str,
        version: str,
        base_url: str,
        health_url: str,
        triggered_by: str = "system",
        smoke_checks: Optional[List[SmokeCheckConfig]] = None,
        auto_rollback: bool = True,
    ) -> VerificationRun:
        """
        Run full post-deployment verification.

        Args:
            deployment_id: Deployment ID
            environment_id: Environment ID
            environment_name: Environment name
            version: Deployed version
            base_url: Base URL for smoke checks
            health_url: Health endpoint URL
            triggered_by: Who triggered verification
            smoke_checks: Optional custom smoke checks
            auto_rollback: Whether to trigger automatic rollback on failure

        Returns:
            VerificationRun with results
        """
        verification = VerificationRun(
            verification_id=str(uuid.uuid4()),
            deployment_id=deployment_id,
            environment_id=environment_id,
            environment_name=environment_name,
            version=version,
            status=VerificationStatus.IN_PROGRESS,
            triggered_by=triggered_by,
            started_at=datetime.utcnow(),
        )

        self.storage.add_verification(verification)

        await self._emit_event("verification_started", {
            "verification_id": verification.verification_id,
            "deployment_id": deployment_id,
            "environment": environment_name,
            "version": version,
        })

        start_time = time.time()

        try:
            # Step 1: Health endpoint verification
            logger.info(f"Running health check for {environment_name}")
            health_passed, health_details = await self.verify_health_endpoint(health_url)
            verification.health_check_passed = health_passed

            await self.record_evidence(
                verification_id=verification.verification_id,
                deployment_id=deployment_id,
                environment=environment_name,
                evidence_type="health_check",
                status="passed" if health_passed else "failed",
                details=health_details,
            )

            if not health_passed:
                verification.status = VerificationStatus.FAILED
                verification.completed_at = datetime.utcnow()

                if auto_rollback:
                    await self.trigger_automatic_rollback(
                        verification,
                        RollbackReason.HEALTH_CHECK_FAILED,
                    )

                if self.acc_gate_config:
                    await self.update_acc_gate_status(
                        verification,
                        ACCGateStatus.CLOSED,
                        {"reason": "health_check_failed"},
                    )

                self.storage.update_verification(verification)
                return verification

            # Step 2: Run smoke checks
            logger.info(f"Running smoke checks for {environment_name}")
            smoke_results = await self.run_smoke_checks(base_url, smoke_checks)
            verification.smoke_check_results = smoke_results

            # Record smoke check evidence
            for result in smoke_results:
                await self.record_evidence(
                    verification_id=verification.verification_id,
                    deployment_id=deployment_id,
                    environment=environment_name,
                    evidence_type="smoke_check",
                    status=result.status.value,
                    details=result.to_dict(),
                )

            # Check for failures in required checks
            required_failures = [
                r for r in smoke_results
                if r.status == SmokeCheckStatus.FAILED and r.config.required
            ]

            if required_failures:
                verification.status = VerificationStatus.FAILED
                verification.completed_at = datetime.utcnow()

                if auto_rollback:
                    await self.trigger_automatic_rollback(
                        verification,
                        RollbackReason.SMOKE_CHECK_FAILED,
                    )

                if self.acc_gate_config:
                    await self.update_acc_gate_status(
                        verification,
                        ACCGateStatus.CLOSED,
                        {"reason": "smoke_check_failed", "failed_checks": [r.config.name for r in required_failures]},
                    )

                self.storage.update_verification(verification)
                return verification

            # Step 3: All checks passed
            verification.status = VerificationStatus.PASSED
            verification.completed_at = datetime.utcnow()

            if self.acc_gate_config:
                await self.update_acc_gate_status(
                    verification,
                    ACCGateStatus.OPEN,
                    {"passed_checks": [r.config.name for r in smoke_results if r.status == SmokeCheckStatus.PASSED]},
                )

            self.storage.update_verification(verification)

            duration = time.time() - start_time
            VERIFICATION_DURATION.observe(duration)
            VERIFICATION_RUNS.labels(
                environment=environment_name,
                status="passed"
            ).inc()

            await self._emit_event("verification_completed", {
                "verification_id": verification.verification_id,
                "deployment_id": deployment_id,
                "environment": environment_name,
                "status": "passed",
                "duration_seconds": round(duration, 2),
            })

            logger.info(
                f"Verification passed for {environment_name} v{version} "
                f"in {duration:.2f}s"
            )

            return verification

        except Exception as e:
            logger.error(f"Verification error: {e}")

            verification.status = VerificationStatus.FAILED
            verification.completed_at = datetime.utcnow()
            self.storage.update_verification(verification)

            await self.record_evidence(
                verification_id=verification.verification_id,
                deployment_id=deployment_id,
                environment=environment_name,
                evidence_type="error",
                status="failed",
                details={"error": str(e)},
            )

            VERIFICATION_RUNS.labels(
                environment=environment_name,
                status="failed"
            ).inc()

            return verification

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_verification(self, verification_id: str) -> Optional[VerificationRun]:
        """Get verification by ID."""
        return self.storage.get_verification(verification_id)

    def get_verification_history(
        self,
        limit: int = 50,
        status: Optional[VerificationStatus] = None,
    ) -> List[VerificationRun]:
        """Get verification history."""
        return self.storage.get_all_verifications(limit, status)

    def get_evidence(self, verification_id: str) -> List[VerificationEvidence]:
        """Get evidence for a verification."""
        return self.storage.get_evidence(verification_id)

    def get_latest_verification(
        self,
        environment_id: str,
    ) -> Optional[VerificationRun]:
        """Get latest verification for an environment."""
        return self.storage.get_latest_verification(environment_id)

    def get_verification_summary(self) -> Dict[str, Any]:
        """Get summary of all verifications."""
        verifications = self.storage.get_all_verifications(limit=100)

        summary = {
            "total": len(verifications),
            "passed": len([v for v in verifications if v.status == VerificationStatus.PASSED]),
            "failed": len([v for v in verifications if v.status == VerificationStatus.FAILED]),
            "rolled_back": len([v for v in verifications if v.status == VerificationStatus.ROLLED_BACK]),
            "in_progress": len([v for v in verifications if v.status == VerificationStatus.IN_PROGRESS]),
            "recent": [v.to_dict() for v in verifications[:5]],
        }

        return summary


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_service: Optional[PostDeploymentVerificationService] = None


def get_post_deployment_verification_service() -> PostDeploymentVerificationService:
    """Get the singleton verification service instance."""
    global _service
    if _service is None:
        _service = PostDeploymentVerificationService()
    return _service


# Convenience alias
verification_service = get_post_deployment_verification_service
