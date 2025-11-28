#!/usr/bin/env python3
"""
Unified Deployment Management Service
Epic: MD-1790 [Platform] Unified Deployment Management GUI

Provides backend services for the deployment management platform:

### Environment Management (MD-1878)
- Environment status and health monitoring
- Real-time status updates

### Deployment History (MD-1879)
- Track deployment records
- Query history by environment
- Success rate metrics

### Version Management (MD-1880)
- Available versions listing
- Current version tracking
- Version comparison

### One-Click Deploy (MD-1881)
- Trigger deployments
- Async deployment with status polling
- Pre-deployment validation

### Rollback Capability (MD-1882)
- Rollback to previous versions
- Safety checks and validation

Acceptance Criteria:
- AC-1: Single dashboard showing all environments
- AC-2: Current deployed version per environment
- AC-3: Health status per environment
- AC-4: One-click deploy from versions
- AC-5: Deployment history with status
- AC-6: Basic rollback capability
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

    DEPLOYMENT_REQUESTS = Counter(
        "maestro_deployment_requests_total",
        "Total deployment requests",
        ["environment", "status"]
    )
    DEPLOYMENT_DURATION = Histogram(
        "maestro_deployment_duration_seconds",
        "Deployment duration",
        buckets=[30.0, 60.0, 120.0, 300.0, 600.0, 1200.0]
    )
    ENVIRONMENT_HEALTH = Gauge(
        "maestro_environment_health",
        "Environment health status (1=healthy, 0=unhealthy)",
        ["environment"]
    )
    ROLLBACK_REQUESTS = Counter(
        "maestro_rollback_requests_total",
        "Total rollback requests",
        ["environment", "status"]
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

    DEPLOYMENT_REQUESTS = StubMetric()
    DEPLOYMENT_DURATION = StubMetric()
    ENVIRONMENT_HEALTH = StubMetric()
    ROLLBACK_REQUESTS = StubMetric()

logger = logging.getLogger("deployment_management_service")


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class EnvironmentType(str, Enum):
    """Types of deployment environments."""
    BETA = "beta"
    DEMO = "demo"
    STAGING = "staging"
    PRODUCTION = "production"


class EnvironmentStatus(str, Enum):
    """Status of an environment."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DEPLOYING = "deploying"
    UNKNOWN = "unknown"


class DeploymentStatus(str, Enum):
    """Status of a deployment."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class DeploymentAction(str, Enum):
    """Type of deployment action."""
    DEPLOY = "deploy"
    ROLLBACK = "rollback"
    HOTFIX = "hotfix"
    CANARY = "canary"


# ============================================================================
# DATA CLASSES - Environment Management (MD-1878)
# ============================================================================

@dataclass
class HealthCheck:
    """Health check result."""
    name: str
    status: str  # "pass", "fail", "warn"
    response_time_ms: Optional[int] = None
    message: Optional[str] = None
    last_check: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "response_time_ms": self.response_time_ms,
            "message": self.message,
            "last_check": self.last_check.isoformat() if self.last_check else None,
        }


@dataclass
class EnvironmentConfig:
    """Configuration for a deployment environment."""
    id: str
    name: str
    type: EnvironmentType
    url: str
    health_url: str
    api_url: Optional[str] = None
    description: str = ""
    is_production: bool = False
    auto_deploy_enabled: bool = False
    requires_approval: bool = False
    max_instances: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "url": self.url,
            "health_url": self.health_url,
            "api_url": self.api_url,
            "description": self.description,
            "is_production": self.is_production,
            "auto_deploy_enabled": self.auto_deploy_enabled,
            "requires_approval": self.requires_approval,
            "max_instances": self.max_instances,
        }


@dataclass
class EnvironmentState:
    """
    Current state of an environment.

    AC-1: Single dashboard showing all environments
    AC-2: Current deployed version per environment
    AC-3: Health status per environment
    """
    environment_id: str
    environment_name: str
    environment_type: EnvironmentType
    status: EnvironmentStatus
    current_version: Optional[str] = None
    deployed_at: Optional[datetime] = None
    deployed_by: Optional[str] = None
    health_checks: List[HealthCheck] = field(default_factory=list)
    uptime_percentage: float = 100.0
    last_deployment_id: Optional[str] = None
    pending_deployment_id: Optional[str] = None
    last_health_check: Optional[datetime] = None
    url: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "environment_name": self.environment_name,
            "environment_type": self.environment_type.value,
            "status": self.status.value,
            "current_version": self.current_version,
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
            "deployed_by": self.deployed_by,
            "health_checks": [h.to_dict() for h in self.health_checks],
            "uptime_percentage": self.uptime_percentage,
            "last_deployment_id": self.last_deployment_id,
            "pending_deployment_id": self.pending_deployment_id,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "url": self.url,
            "is_healthy": self.status == EnvironmentStatus.HEALTHY,
        }


# ============================================================================
# DATA CLASSES - Deployment History (MD-1879)
# ============================================================================

@dataclass
class DeploymentRecord:
    """
    Record of a deployment.

    AC-5: Deployment history with status
    """
    deployment_id: str
    environment_id: str
    environment_name: str
    version: str
    previous_version: Optional[str] = None
    action: DeploymentAction = DeploymentAction.DEPLOY
    status: DeploymentStatus = DeploymentStatus.PENDING
    triggered_by: str = "system"
    trigger_source: str = "api"  # "api", "github_actions", "manual", "auto"
    commit_sha: Optional[str] = None
    release_notes: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    rollback_target_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "environment_id": self.environment_id,
            "environment_name": self.environment_name,
            "version": self.version,
            "previous_version": self.previous_version,
            "action": self.action.value,
            "status": self.status.value,
            "triggered_by": self.triggered_by,
            "trigger_source": self.trigger_source,
            "commit_sha": self.commit_sha,
            "release_notes": self.release_notes,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "error_message": self.error_message,
            "rollback_target_id": self.rollback_target_id,
            "duration_seconds": self.get_duration_seconds(),
        }

    def get_duration_seconds(self) -> Optional[float]:
        """Get deployment duration in seconds."""
        if self.started_at:
            end_time = self.completed_at or datetime.utcnow()
            return round((end_time - self.started_at).total_seconds(), 2)
        return None


# ============================================================================
# DATA CLASSES - Version Management (MD-1880)
# ============================================================================

@dataclass
class Version:
    """
    A deployable version.

    AC-4: One-click deploy from versions
    """
    version_id: str
    version_tag: str
    commit_sha: str
    branch: str = "main"
    release_type: str = "release"  # "release", "hotfix", "canary"
    release_notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = "system"
    is_current: Dict[str, bool] = field(default_factory=dict)  # env_id -> is_current
    is_deployable: bool = True
    artifact_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "version_tag": self.version_tag,
            "commit_sha": self.commit_sha,
            "branch": self.branch,
            "release_type": self.release_type,
            "release_notes": self.release_notes,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "is_current": self.is_current,
            "is_deployable": self.is_deployable,
            "artifact_url": self.artifact_url,
        }


# ============================================================================
# DATA CLASSES - One-Click Deploy (MD-1881)
# ============================================================================

@dataclass
class DeploymentRequest:
    """Request to trigger a deployment."""
    environment_id: str
    version_id: str
    triggered_by: str
    trigger_source: str = "api"
    skip_validation: bool = False
    force: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentValidation:
    """Result of deployment validation."""
    is_valid: bool
    checks: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "checks": self.checks,
            "warnings": self.warnings,
            "errors": self.errors,
        }


# ============================================================================
# DATA CLASSES - Rollback (MD-1882)
# ============================================================================

@dataclass
class RollbackRequest:
    """
    Request to rollback a deployment.

    AC-6: Basic rollback capability
    """
    environment_id: str
    target_version_id: Optional[str] = None  # If None, rollback to previous
    triggered_by: str = "system"
    reason: str = ""
    skip_validation: bool = False


# ============================================================================
# IN-MEMORY STORAGE
# ============================================================================

class DeploymentStorage:
    """In-memory storage for deployment data."""

    def __init__(self, max_records: int = 1000):
        self.environments: Dict[str, EnvironmentConfig] = {}
        self.environment_states: Dict[str, EnvironmentState] = {}
        self.deployments: Dict[str, DeploymentRecord] = {}
        self.versions: Dict[str, Version] = {}
        self.max_records = max_records

        # Initialize default environments
        self._init_default_environments()

    def _init_default_environments(self) -> None:
        """Initialize default Maestro environments."""
        default_envs = [
            EnvironmentConfig(
                id="env-beta",
                name="Beta",
                type=EnvironmentType.BETA,
                url="https://beta.maestro.ai",
                health_url="https://beta.maestro.ai/health",
                api_url="https://beta.maestro.ai/api",
                description="Beta testing environment",
                is_production=False,
                auto_deploy_enabled=True,
                requires_approval=False,
            ),
            EnvironmentConfig(
                id="env-demo",
                name="Demo",
                type=EnvironmentType.DEMO,
                url="https://demo.maestro.ai",
                health_url="https://demo.maestro.ai/health",
                api_url="https://demo.maestro.ai/api",
                description="Demo environment for customer showcases",
                is_production=False,
                auto_deploy_enabled=False,
                requires_approval=True,
            ),
            EnvironmentConfig(
                id="env-staging",
                name="Staging",
                type=EnvironmentType.STAGING,
                url="https://staging.maestro.ai",
                health_url="https://staging.maestro.ai/health",
                api_url="https://staging.maestro.ai/api",
                description="Pre-production staging environment",
                is_production=False,
                auto_deploy_enabled=False,
                requires_approval=True,
            ),
            EnvironmentConfig(
                id="env-prod",
                name="Production",
                type=EnvironmentType.PRODUCTION,
                url="https://app.maestro.ai",
                health_url="https://app.maestro.ai/health",
                api_url="https://app.maestro.ai/api",
                description="Production environment",
                is_production=True,
                auto_deploy_enabled=False,
                requires_approval=True,
            ),
        ]

        for env in default_envs:
            self.environments[env.id] = env
            self.environment_states[env.id] = EnvironmentState(
                environment_id=env.id,
                environment_name=env.name,
                environment_type=env.type,
                status=EnvironmentStatus.UNKNOWN,
                url=env.url,
            )

    def add_environment(self, config: EnvironmentConfig) -> None:
        """Add or update an environment."""
        self.environments[config.id] = config
        if config.id not in self.environment_states:
            self.environment_states[config.id] = EnvironmentState(
                environment_id=config.id,
                environment_name=config.name,
                environment_type=config.type,
                status=EnvironmentStatus.UNKNOWN,
                url=config.url,
            )

    def get_environment(self, env_id: str) -> Optional[EnvironmentConfig]:
        """Get environment configuration."""
        return self.environments.get(env_id)

    def get_environment_state(self, env_id: str) -> Optional[EnvironmentState]:
        """Get environment state."""
        return self.environment_states.get(env_id)

    def update_environment_state(self, state: EnvironmentState) -> None:
        """Update environment state."""
        self.environment_states[state.environment_id] = state

    def get_all_environments(self) -> List[EnvironmentConfig]:
        """Get all environment configurations."""
        return list(self.environments.values())

    def get_all_environment_states(self) -> List[EnvironmentState]:
        """Get all environment states."""
        return list(self.environment_states.values())

    def add_deployment(self, deployment: DeploymentRecord) -> None:
        """Add a deployment record."""
        self.deployments[deployment.deployment_id] = deployment

        # Trim old records
        if len(self.deployments) > self.max_records:
            oldest = sorted(
                self.deployments.values(),
                key=lambda d: d.created_at
            )[:len(self.deployments) - self.max_records]
            for d in oldest:
                del self.deployments[d.deployment_id]

    def get_deployment(self, deployment_id: str) -> Optional[DeploymentRecord]:
        """Get deployment by ID."""
        return self.deployments.get(deployment_id)

    def update_deployment(self, deployment: DeploymentRecord) -> None:
        """Update deployment record."""
        self.deployments[deployment.deployment_id] = deployment

    def get_deployments_for_environment(
        self,
        env_id: str,
        limit: int = 50,
        status: Optional[DeploymentStatus] = None,
    ) -> List[DeploymentRecord]:
        """Get deployments for an environment."""
        deployments = [
            d for d in self.deployments.values()
            if d.environment_id == env_id
        ]
        if status:
            deployments = [d for d in deployments if d.status == status]
        deployments.sort(key=lambda d: d.created_at, reverse=True)
        return deployments[:limit]

    def get_all_deployments(
        self,
        limit: int = 50,
        status: Optional[DeploymentStatus] = None,
    ) -> List[DeploymentRecord]:
        """Get all deployments."""
        deployments = list(self.deployments.values())
        if status:
            deployments = [d for d in deployments if d.status == status]
        deployments.sort(key=lambda d: d.created_at, reverse=True)
        return deployments[:limit]

    def add_version(self, version: Version) -> None:
        """Add a version."""
        self.versions[version.version_id] = version

    def get_version(self, version_id: str) -> Optional[Version]:
        """Get version by ID."""
        return self.versions.get(version_id)

    def get_version_by_tag(self, tag: str) -> Optional[Version]:
        """Get version by tag."""
        for v in self.versions.values():
            if v.version_tag == tag:
                return v
        return None

    def get_all_versions(
        self,
        limit: int = 50,
        deployable_only: bool = False,
    ) -> List[Version]:
        """Get all versions."""
        versions = list(self.versions.values())
        if deployable_only:
            versions = [v for v in versions if v.is_deployable]
        versions.sort(key=lambda v: v.created_at, reverse=True)
        return versions[:limit]


# Global storage instance
_storage = DeploymentStorage()


# ============================================================================
# DEPLOYMENT MANAGEMENT SERVICE
# ============================================================================

class DeploymentManagementService:
    """
    Unified Deployment Management Service.

    Provides a single interface for managing all Maestro deployments:
    - Environment status and health
    - Deployment history
    - Version management
    - One-click deploy
    - Rollback capability
    """

    def __init__(
        self,
        storage: Optional[DeploymentStorage] = None,
        github_actions_callback: Optional[Callable] = None,
        notification_callback: Optional[Callable] = None,
    ):
        """
        Initialize deployment management service.

        Args:
            storage: Storage backend
            github_actions_callback: Callback to trigger GitHub Actions
            notification_callback: Callback for notifications
        """
        self.storage = storage or _storage
        self.github_actions_callback = github_actions_callback
        self.notification_callback = notification_callback
        self._session: Optional[aiohttp.ClientSession] = None

        logger.info("DeploymentManagementService initialized")

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

    async def _notify(self, event_type: str, data: Dict[str, Any]) -> None:
        """Send notification."""
        if self.notification_callback:
            try:
                notification = {
                    "type": event_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": data,
                }
                if asyncio.iscoroutinefunction(self.notification_callback):
                    await self.notification_callback(notification)
                else:
                    self.notification_callback(notification)
            except Exception as e:
                logger.error(f"Error sending notification: {e}")

    # =========================================================================
    # Environment Management (MD-1878)
    # =========================================================================

    def get_environments(self) -> List[EnvironmentConfig]:
        """
        Get all environment configurations.

        AC-1: Single dashboard showing all environments
        """
        return self.storage.get_all_environments()

    def get_environment(self, env_id: str) -> Optional[EnvironmentConfig]:
        """Get environment configuration."""
        return self.storage.get_environment(env_id)

    def get_environment_states(self) -> List[EnvironmentState]:
        """
        Get all environment states.

        AC-1: Single dashboard showing all environments
        AC-2: Current deployed version per environment
        AC-3: Health status per environment
        """
        return self.storage.get_all_environment_states()

    def get_environment_state(self, env_id: str) -> Optional[EnvironmentState]:
        """Get environment state."""
        return self.storage.get_environment_state(env_id)

    async def check_environment_health(
        self,
        env_id: str,
        timeout_seconds: float = 30.0,
    ) -> EnvironmentState:
        """
        Check health of an environment.

        AC-3: Health status per environment
        """
        env_config = self.storage.get_environment(env_id)
        if not env_config:
            raise ValueError(f"Environment not found: {env_id}")

        state = self.storage.get_environment_state(env_id)
        if not state:
            state = EnvironmentState(
                environment_id=env_id,
                environment_name=env_config.name,
                environment_type=env_config.type,
                status=EnvironmentStatus.UNKNOWN,
                url=env_config.url,
            )

        session = await self._get_session()
        health_checks = []

        try:
            timeout = aiohttp.ClientTimeout(total=timeout_seconds)
            start_time = asyncio.get_event_loop().time()

            async with session.get(env_config.health_url, timeout=timeout) as response:
                response_time = int(
                    (asyncio.get_event_loop().time() - start_time) * 1000
                )

                if response.status == 200:
                    health_checks.append(HealthCheck(
                        name="health_endpoint",
                        status="pass",
                        response_time_ms=response_time,
                        last_check=datetime.utcnow(),
                    ))
                    state.status = EnvironmentStatus.HEALTHY
                else:
                    health_checks.append(HealthCheck(
                        name="health_endpoint",
                        status="fail",
                        response_time_ms=response_time,
                        message=f"Status code: {response.status}",
                        last_check=datetime.utcnow(),
                    ))
                    state.status = EnvironmentStatus.UNHEALTHY

        except asyncio.TimeoutError:
            health_checks.append(HealthCheck(
                name="health_endpoint",
                status="fail",
                message="Timeout",
                last_check=datetime.utcnow(),
            ))
            state.status = EnvironmentStatus.UNHEALTHY

        except Exception as e:
            health_checks.append(HealthCheck(
                name="health_endpoint",
                status="fail",
                message=str(e),
                last_check=datetime.utcnow(),
            ))
            state.status = EnvironmentStatus.UNHEALTHY

        state.health_checks = health_checks
        state.last_health_check = datetime.utcnow()

        self.storage.update_environment_state(state)

        # Update Prometheus metric
        ENVIRONMENT_HEALTH.labels(
            environment=state.environment_name
        ).set(1 if state.status == EnvironmentStatus.HEALTHY else 0)

        return state

    async def refresh_all_environment_health(self) -> List[EnvironmentState]:
        """Refresh health status of all environments."""
        states = []
        for env in self.storage.get_all_environments():
            try:
                state = await self.check_environment_health(env.id)
                states.append(state)
            except Exception as e:
                logger.error(f"Error checking health for {env.id}: {e}")
        return states

    def add_environment(self, config: EnvironmentConfig) -> None:
        """Add or update an environment."""
        self.storage.add_environment(config)

    # =========================================================================
    # Deployment History (MD-1879)
    # =========================================================================

    def get_deployment_history(
        self,
        env_id: Optional[str] = None,
        limit: int = 50,
        status: Optional[DeploymentStatus] = None,
    ) -> List[DeploymentRecord]:
        """
        Get deployment history.

        AC-5: Deployment history with status
        """
        if env_id:
            return self.storage.get_deployments_for_environment(env_id, limit, status)
        return self.storage.get_all_deployments(limit, status)

    def get_deployment(self, deployment_id: str) -> Optional[DeploymentRecord]:
        """Get deployment by ID."""
        return self.storage.get_deployment(deployment_id)

    def get_deployment_metrics(
        self,
        env_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get deployment metrics."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        if env_id:
            deployments = self.storage.get_deployments_for_environment(env_id, limit=1000)
        else:
            deployments = self.storage.get_all_deployments(limit=1000)

        recent = [d for d in deployments if d.created_at >= cutoff]

        total = len(recent)
        successful = len([d for d in recent if d.status == DeploymentStatus.SUCCESS])
        failed = len([d for d in recent if d.status == DeploymentStatus.FAILED])
        rolled_back = len([d for d in recent if d.status == DeploymentStatus.ROLLED_BACK])

        durations = [
            d.get_duration_seconds()
            for d in recent
            if d.get_duration_seconds() is not None and d.status == DeploymentStatus.SUCCESS
        ]

        return {
            "period_days": days,
            "total_deployments": total,
            "successful": successful,
            "failed": failed,
            "rolled_back": rolled_back,
            "success_rate": round(successful / total * 100, 2) if total > 0 else 0,
            "average_duration_seconds": round(sum(durations) / len(durations), 2) if durations else None,
            "deployments_per_day": round(total / days, 2) if days > 0 else 0,
        }

    # =========================================================================
    # Version Management (MD-1880)
    # =========================================================================

    def get_versions(
        self,
        limit: int = 50,
        deployable_only: bool = False,
    ) -> List[Version]:
        """
        Get available versions.

        AC-4: One-click deploy from versions
        """
        return self.storage.get_all_versions(limit, deployable_only)

    def get_version(self, version_id: str) -> Optional[Version]:
        """Get version by ID."""
        return self.storage.get_version(version_id)

    def get_version_by_tag(self, tag: str) -> Optional[Version]:
        """Get version by tag."""
        return self.storage.get_version_by_tag(tag)

    def add_version(self, version: Version) -> None:
        """Add a new version."""
        self.storage.add_version(version)
        logger.info(f"Added version: {version.version_tag}")

    def get_current_version(self, env_id: str) -> Optional[str]:
        """
        Get current deployed version for an environment.

        AC-2: Current deployed version per environment
        """
        state = self.storage.get_environment_state(env_id)
        return state.current_version if state else None

    def compare_versions(
        self,
        version_a_id: str,
        version_b_id: str,
    ) -> Dict[str, Any]:
        """Compare two versions."""
        v_a = self.storage.get_version(version_a_id)
        v_b = self.storage.get_version(version_b_id)

        if not v_a or not v_b:
            return {"error": "Version not found"}

        return {
            "version_a": v_a.to_dict(),
            "version_b": v_b.to_dict(),
            "same_branch": v_a.branch == v_b.branch,
            "a_is_newer": v_a.created_at > v_b.created_at,
        }

    # =========================================================================
    # One-Click Deploy (MD-1881)
    # =========================================================================

    async def validate_deployment(
        self,
        request: DeploymentRequest,
    ) -> DeploymentValidation:
        """
        Validate a deployment request.

        Pre-deployment validation for one-click deploy.
        """
        checks = []
        warnings = []
        errors = []

        # Check environment exists
        env = self.storage.get_environment(request.environment_id)
        if not env:
            errors.append(f"Environment not found: {request.environment_id}")
            checks.append({"name": "environment_exists", "status": "fail"})
        else:
            checks.append({"name": "environment_exists", "status": "pass"})

        # Check version exists
        version = self.storage.get_version(request.version_id)
        if not version:
            errors.append(f"Version not found: {request.version_id}")
            checks.append({"name": "version_exists", "status": "fail"})
        elif not version.is_deployable:
            errors.append(f"Version is not deployable: {request.version_id}")
            checks.append({"name": "version_deployable", "status": "fail"})
        else:
            checks.append({"name": "version_exists", "status": "pass"})
            checks.append({"name": "version_deployable", "status": "pass"})

        # Check no deployment in progress
        state = self.storage.get_environment_state(request.environment_id)
        if state and state.status == EnvironmentStatus.DEPLOYING:
            if not request.force:
                errors.append("Deployment already in progress")
                checks.append({"name": "no_active_deployment", "status": "fail"})
            else:
                warnings.append("Force deploying while deployment in progress")
                checks.append({"name": "no_active_deployment", "status": "warn"})
        else:
            checks.append({"name": "no_active_deployment", "status": "pass"})

        # Check approval requirement
        if env and env.requires_approval:
            warnings.append("This environment requires approval")
            checks.append({"name": "requires_approval", "status": "warn"})

        # Check if deploying same version
        if state and version and state.current_version == version.version_tag:
            warnings.append("Deploying the same version currently deployed")
            checks.append({"name": "version_change", "status": "warn"})
        else:
            checks.append({"name": "version_change", "status": "pass"})

        return DeploymentValidation(
            is_valid=len(errors) == 0,
            checks=checks,
            warnings=warnings,
            errors=errors,
        )

    async def trigger_deployment(
        self,
        request: DeploymentRequest,
    ) -> DeploymentRecord:
        """
        Trigger a new deployment.

        AC-4: One-click deploy from versions
        """
        # Validate first
        if not request.skip_validation:
            validation = await self.validate_deployment(request)
            if not validation.is_valid:
                raise ValueError(f"Deployment validation failed: {validation.errors}")

        env = self.storage.get_environment(request.environment_id)
        version = self.storage.get_version(request.version_id)
        state = self.storage.get_environment_state(request.environment_id)

        # Create deployment record
        deployment = DeploymentRecord(
            deployment_id=str(uuid.uuid4()),
            environment_id=request.environment_id,
            environment_name=env.name if env else request.environment_id,
            version=version.version_tag if version else request.version_id,
            previous_version=state.current_version if state else None,
            action=DeploymentAction.DEPLOY,
            status=DeploymentStatus.PENDING,
            triggered_by=request.triggered_by,
            trigger_source=request.trigger_source,
            commit_sha=version.commit_sha if version else None,
            release_notes=version.release_notes if version else None,
            metadata=request.metadata,
        )

        self.storage.add_deployment(deployment)

        # Update environment state
        if state:
            state.pending_deployment_id = deployment.deployment_id
            state.status = EnvironmentStatus.DEPLOYING
            self.storage.update_environment_state(state)

        DEPLOYMENT_REQUESTS.labels(
            environment=deployment.environment_name,
            status="pending"
        ).inc()

        # Notify
        await self._notify("deployment_triggered", {
            "deployment_id": deployment.deployment_id,
            "environment": deployment.environment_name,
            "version": deployment.version,
        })

        # If GitHub Actions callback is configured, trigger the workflow
        if self.github_actions_callback:
            try:
                if asyncio.iscoroutinefunction(self.github_actions_callback):
                    await self.github_actions_callback(deployment)
                else:
                    self.github_actions_callback(deployment)
            except Exception as e:
                logger.error(f"Error triggering GitHub Actions: {e}")

        logger.info(
            f"Deployment triggered: {deployment.deployment_id} - "
            f"{deployment.version} to {deployment.environment_name}"
        )

        return deployment

    async def update_deployment_status(
        self,
        deployment_id: str,
        status: DeploymentStatus,
        error_message: Optional[str] = None,
    ) -> Optional[DeploymentRecord]:
        """Update deployment status."""
        deployment = self.storage.get_deployment(deployment_id)
        if not deployment:
            return None

        old_status = deployment.status
        deployment.status = status
        deployment.error_message = error_message

        if status == DeploymentStatus.IN_PROGRESS and not deployment.started_at:
            deployment.started_at = datetime.utcnow()

        if status in [DeploymentStatus.SUCCESS, DeploymentStatus.FAILED,
                      DeploymentStatus.ROLLED_BACK, DeploymentStatus.CANCELLED]:
            deployment.completed_at = datetime.utcnow()

            if deployment.started_at:
                duration = deployment.get_duration_seconds()
                if duration:
                    DEPLOYMENT_DURATION.observe(duration)

        self.storage.update_deployment(deployment)

        # Update environment state
        state = self.storage.get_environment_state(deployment.environment_id)
        if state:
            if status == DeploymentStatus.SUCCESS:
                state.current_version = deployment.version
                state.deployed_at = deployment.completed_at
                state.deployed_by = deployment.triggered_by
                state.last_deployment_id = deployment.deployment_id
                state.status = EnvironmentStatus.HEALTHY
                state.pending_deployment_id = None

                # Update version's is_current
                version = self.storage.get_version_by_tag(deployment.version)
                if version:
                    version.is_current[deployment.environment_id] = True
                    # Clear is_current for other versions in this env
                    for v in self.storage.get_all_versions(limit=1000):
                        if v.version_id != version.version_id:
                            v.is_current[deployment.environment_id] = False

            elif status == DeploymentStatus.FAILED:
                state.status = EnvironmentStatus.DEGRADED
                state.pending_deployment_id = None

            elif status == DeploymentStatus.IN_PROGRESS:
                state.status = EnvironmentStatus.DEPLOYING

            self.storage.update_environment_state(state)

        DEPLOYMENT_REQUESTS.labels(
            environment=deployment.environment_name,
            status=status.value
        ).inc()

        await self._notify("deployment_status_updated", {
            "deployment_id": deployment_id,
            "old_status": old_status.value,
            "new_status": status.value,
        })

        return deployment

    # =========================================================================
    # Rollback Capability (MD-1882)
    # =========================================================================

    async def validate_rollback(
        self,
        request: RollbackRequest,
    ) -> DeploymentValidation:
        """Validate a rollback request."""
        checks = []
        warnings = []
        errors = []

        # Check environment exists
        env = self.storage.get_environment(request.environment_id)
        if not env:
            errors.append(f"Environment not found: {request.environment_id}")
            checks.append({"name": "environment_exists", "status": "fail"})
        else:
            checks.append({"name": "environment_exists", "status": "pass"})

        # Check we have a deployment to rollback to
        state = self.storage.get_environment_state(request.environment_id)

        if request.target_version_id:
            target_version = self.storage.get_version(request.target_version_id)
            if not target_version:
                errors.append(f"Target version not found: {request.target_version_id}")
                checks.append({"name": "target_version_exists", "status": "fail"})
            else:
                checks.append({"name": "target_version_exists", "status": "pass"})
        else:
            # Find previous successful deployment
            history = self.storage.get_deployments_for_environment(
                request.environment_id,
                limit=10,
                status=DeploymentStatus.SUCCESS,
            )
            current = state.current_version if state else None
            previous = next(
                (d for d in history if d.version != current),
                None
            )
            if not previous:
                errors.append("No previous deployment found to rollback to")
                checks.append({"name": "previous_deployment_exists", "status": "fail"})
            else:
                checks.append({"name": "previous_deployment_exists", "status": "pass"})

        # Check no deployment in progress
        if state and state.status == EnvironmentStatus.DEPLOYING:
            errors.append("Cannot rollback while deployment in progress")
            checks.append({"name": "no_active_deployment", "status": "fail"})
        else:
            checks.append({"name": "no_active_deployment", "status": "pass"})

        # Production warning
        if env and env.is_production:
            warnings.append("Rolling back production environment")

        return DeploymentValidation(
            is_valid=len(errors) == 0,
            checks=checks,
            warnings=warnings,
            errors=errors,
        )

    async def trigger_rollback(
        self,
        request: RollbackRequest,
    ) -> DeploymentRecord:
        """
        Trigger a rollback.

        AC-6: Basic rollback capability
        """
        # Validate first
        if not request.skip_validation:
            validation = await self.validate_rollback(request)
            if not validation.is_valid:
                raise ValueError(f"Rollback validation failed: {validation.errors}")

        env = self.storage.get_environment(request.environment_id)
        state = self.storage.get_environment_state(request.environment_id)

        # Determine target version
        target_version_tag: str
        target_deployment_id: Optional[str] = None

        if request.target_version_id:
            version = self.storage.get_version(request.target_version_id)
            if not version:
                raise ValueError(f"Target version not found: {request.target_version_id}")
            target_version_tag = version.version_tag
        else:
            # Find previous successful deployment
            history = self.storage.get_deployments_for_environment(
                request.environment_id,
                limit=10,
                status=DeploymentStatus.SUCCESS,
            )
            current = state.current_version if state else None
            previous = next(
                (d for d in history if d.version != current),
                None
            )
            if not previous:
                raise ValueError("No previous deployment found to rollback to")
            target_version_tag = previous.version
            target_deployment_id = previous.deployment_id

        # Create rollback deployment record
        deployment = DeploymentRecord(
            deployment_id=str(uuid.uuid4()),
            environment_id=request.environment_id,
            environment_name=env.name if env else request.environment_id,
            version=target_version_tag,
            previous_version=state.current_version if state else None,
            action=DeploymentAction.ROLLBACK,
            status=DeploymentStatus.PENDING,
            triggered_by=request.triggered_by,
            trigger_source="rollback",
            release_notes=request.reason,
            rollback_target_id=target_deployment_id,
        )

        self.storage.add_deployment(deployment)

        # Update environment state
        if state:
            state.pending_deployment_id = deployment.deployment_id
            state.status = EnvironmentStatus.DEPLOYING
            self.storage.update_environment_state(state)

        ROLLBACK_REQUESTS.labels(
            environment=deployment.environment_name,
            status="pending"
        ).inc()

        await self._notify("rollback_triggered", {
            "deployment_id": deployment.deployment_id,
            "environment": deployment.environment_name,
            "from_version": deployment.previous_version,
            "to_version": deployment.version,
            "reason": request.reason,
        })

        logger.warning(
            f"Rollback triggered: {deployment.deployment_id} - "
            f"{deployment.previous_version} -> {deployment.version} "
            f"in {deployment.environment_name}"
        )

        return deployment

    # =========================================================================
    # Dashboard Summary
    # =========================================================================

    async def get_dashboard_summary(self) -> Dict[str, Any]:
        """
        Get dashboard summary for the GUI.

        AC-1: Single dashboard showing all environments
        """
        environments = []
        for state in self.storage.get_all_environment_states():
            env_config = self.storage.get_environment(state.environment_id)
            environments.append({
                **state.to_dict(),
                "config": env_config.to_dict() if env_config else None,
            })

        recent_deployments = self.storage.get_all_deployments(limit=10)
        available_versions = self.storage.get_all_versions(limit=10, deployable_only=True)

        metrics = self.get_deployment_metrics(days=7)

        return {
            "environments": environments,
            "recent_deployments": [d.to_dict() for d in recent_deployments],
            "available_versions": [v.to_dict() for v in available_versions],
            "metrics_7_days": metrics,
            "generated_at": datetime.utcnow().isoformat(),
        }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_service: Optional[DeploymentManagementService] = None


def get_deployment_management_service() -> DeploymentManagementService:
    """Get the singleton deployment management service instance."""
    global _service
    if _service is None:
        _service = DeploymentManagementService()
    return _service


# Convenience alias
deployment_service = get_deployment_management_service
