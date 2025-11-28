#!/usr/bin/env python3
"""
Deployment Management Service
Epic: MD-1790 [Platform] Unified Deployment Management GUI

Core service for deployment management providing:
- Environment management
- Deployment triggering via GitHub Actions
- Deployment history and tracking
- Rollback capability
- Version discovery

Acceptance Criteria:
- AC-1: Single dashboard for all environments
- AC-2: Current version per environment
- AC-3: Health status per environment
- AC-4: One-click deploy from versions
- AC-5: Deployment history with status
- AC-6: Basic rollback capability
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

# Try to import Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, Gauge

    DEPLOYMENT_TRIGGERS = Counter(
        "maestro_deployment_triggers_total",
        "Total deployment triggers",
        ["environment", "status"]
    )
    DEPLOYMENT_DURATION = Histogram(
        "maestro_deployment_duration_seconds",
        "Deployment duration",
        buckets=[30, 60, 120, 180, 300, 600, 900, 1200]
    )
    ACTIVE_DEPLOYMENTS = Gauge(
        "maestro_active_deployments",
        "Number of active deployments",
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

    DEPLOYMENT_TRIGGERS = StubMetric()
    DEPLOYMENT_DURATION = StubMetric()
    ACTIVE_DEPLOYMENTS = StubMetric()

logger = logging.getLogger("deployment_service")


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class DeploymentStatus(str, Enum):
    """Status of a deployment."""
    PENDING = "pending"           # Deployment requested, not started
    QUEUED = "queued"             # Waiting in queue
    IN_PROGRESS = "in_progress"   # Deployment running
    SUCCESS = "success"           # Deployment completed successfully
    FAILED = "failed"             # Deployment failed
    CANCELLED = "cancelled"       # Deployment cancelled
    ROLLED_BACK = "rolled_back"   # Deployment was rolled back
    ROLLBACK_FAILED = "rollback_failed"  # Rollback attempt failed


class TriggerType(str, Enum):
    """How the deployment was triggered."""
    MANUAL = "manual"       # User-initiated
    AUTOMATIC = "automatic" # System-initiated (e.g., on merge)
    ROLLBACK = "rollback"   # Triggered as a rollback


class HealthStatus(str, Enum):
    """Health status of an environment."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Environment:
    """Deployment environment configuration."""
    id: str
    name: str
    display_name: str
    description: str = ""
    github_environment: str = ""
    health_url: str = ""
    portainer_stack: str = ""
    is_production: bool = False
    requires_approval: bool = False
    is_active: bool = True
    deploy_timeout_seconds: int = 300
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "github_environment": self.github_environment,
            "health_url": self.health_url,
            "is_production": self.is_production,
            "requires_approval": self.requires_approval,
            "is_active": self.is_active,
        }


@dataclass
class EnvironmentStatus:
    """Current status of an environment."""
    environment: Environment
    current_version: Optional[str] = None
    current_deployment_id: Optional[str] = None
    deployed_at: Optional[datetime] = None
    deployed_by: Optional[str] = None
    health_status: HealthStatus = HealthStatus.UNKNOWN
    health_response_time_ms: Optional[int] = None
    last_health_check: Optional[datetime] = None
    active_deployment: Optional["Deployment"] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment": self.environment.to_dict(),
            "current_version": self.current_version,
            "current_deployment_id": self.current_deployment_id,
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
            "deployed_by": self.deployed_by,
            "health_status": self.health_status.value,
            "health_response_time_ms": self.health_response_time_ms,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "has_active_deployment": self.active_deployment is not None,
        }


@dataclass
class Deployment:
    """A deployment record."""
    id: str
    environment_id: str
    environment_name: str
    version: str
    status: DeploymentStatus
    triggered_by: str
    trigger_type: TriggerType = TriggerType.MANUAL
    git_sha: Optional[str] = None
    git_branch: Optional[str] = None
    github_run_id: Optional[int] = None
    github_run_url: Optional[str] = None
    notes: Optional[str] = None
    error_message: Optional[str] = None
    rollback_of: Optional[str] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "environment_id": self.environment_id,
            "environment_name": self.environment_name,
            "version": self.version,
            "status": self.status.value,
            "triggered_by": self.triggered_by,
            "trigger_type": self.trigger_type.value,
            "git_sha": self.git_sha,
            "git_branch": self.git_branch,
            "github_run_id": self.github_run_id,
            "github_run_url": self.github_run_url,
            "notes": self.notes,
            "error_message": self.error_message,
            "rollback_of": self.rollback_of,
            "queued_at": self.queued_at.isoformat() if self.queued_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "duration_seconds": self.get_duration_seconds(),
        }

    def get_duration_seconds(self) -> Optional[int]:
        """Get deployment duration in seconds."""
        if self.started_at:
            end_time = self.completed_at or datetime.utcnow()
            return int((end_time - self.started_at).total_seconds())
        return None


@dataclass
class DeploymentLog:
    """A log entry for a deployment."""
    id: str
    deployment_id: str
    timestamp: datetime
    level: str  # debug, info, warning, error
    message: str
    stage: Optional[str] = None  # build, test, deploy, verify
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "deployment_id": self.deployment_id,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "message": self.message,
            "stage": self.stage,
            "source": self.source,
        }


@dataclass
class Version:
    """An available version for deployment."""
    version: str
    git_sha: Optional[str] = None
    git_tag: Optional[str] = None
    release_notes: Optional[str] = None
    is_prerelease: bool = False
    is_latest: bool = False
    published_at: Optional[datetime] = None
    deployed_to: List[str] = field(default_factory=list)  # Environment names

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "git_sha": self.git_sha,
            "git_tag": self.git_tag,
            "release_notes": self.release_notes,
            "is_prerelease": self.is_prerelease,
            "is_latest": self.is_latest,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "deployed_to": self.deployed_to,
        }


# ============================================================================
# IN-MEMORY STORAGE (Replace with PostgreSQL in production)
# ============================================================================

class DeploymentStorage:
    """
    In-memory storage for deployments.
    In production, this would be replaced with PostgreSQL.
    """

    def __init__(self):
        self.environments: Dict[str, Environment] = {}
        self.deployments: Dict[str, Deployment] = {}
        self.deployment_logs: Dict[str, List[DeploymentLog]] = {}
        self.versions: Dict[str, Version] = {}
        self.health_snapshots: List[Dict[str, Any]] = []

    def add_environment(self, env: Environment) -> None:
        self.environments[env.id] = env

    def get_environment(self, env_id: str) -> Optional[Environment]:
        return self.environments.get(env_id)

    def get_environment_by_name(self, name: str) -> Optional[Environment]:
        for env in self.environments.values():
            if env.name == name:
                return env
        return None

    def list_environments(self) -> List[Environment]:
        return [e for e in self.environments.values() if e.is_active]

    def add_deployment(self, deployment: Deployment) -> None:
        self.deployments[deployment.id] = deployment
        if deployment.id not in self.deployment_logs:
            self.deployment_logs[deployment.id] = []

    def get_deployment(self, deployment_id: str) -> Optional[Deployment]:
        return self.deployments.get(deployment_id)

    def update_deployment(self, deployment: Deployment) -> None:
        self.deployments[deployment.id] = deployment

    def get_deployments_for_environment(
        self,
        env_id: str,
        limit: int = 50,
        status: Optional[DeploymentStatus] = None,
    ) -> List[Deployment]:
        deployments = [
            d for d in self.deployments.values()
            if d.environment_id == env_id
            and (status is None or d.status == status)
        ]
        deployments.sort(key=lambda d: d.created_at, reverse=True)
        return deployments[:limit]

    def get_latest_successful_deployment(
        self,
        env_id: str,
    ) -> Optional[Deployment]:
        deployments = self.get_deployments_for_environment(
            env_id, limit=1, status=DeploymentStatus.SUCCESS
        )
        return deployments[0] if deployments else None

    def get_active_deployment(self, env_id: str) -> Optional[Deployment]:
        for d in self.deployments.values():
            if d.environment_id == env_id and d.status in [
                DeploymentStatus.PENDING,
                DeploymentStatus.QUEUED,
                DeploymentStatus.IN_PROGRESS,
            ]:
                return d
        return None

    def add_deployment_log(self, log: DeploymentLog) -> None:
        if log.deployment_id not in self.deployment_logs:
            self.deployment_logs[log.deployment_id] = []
        self.deployment_logs[log.deployment_id].append(log)

    def get_deployment_logs(
        self,
        deployment_id: str,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> List[DeploymentLog]:
        logs = self.deployment_logs.get(deployment_id, [])
        if level:
            logs = [l for l in logs if l.level == level]
        return logs[-limit:]

    def get_all_deployments(self, limit: int = 100) -> List[Deployment]:
        deployments = list(self.deployments.values())
        deployments.sort(key=lambda d: d.created_at, reverse=True)
        return deployments[:limit]


# Global storage instance
_storage = DeploymentStorage()


# ============================================================================
# DEPLOYMENT SERVICE
# ============================================================================

class DeploymentService:
    """
    Core deployment management service.

    Manages environments, triggers deployments via GitHub Actions,
    tracks deployment history, and provides rollback capability.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        storage: Optional[DeploymentStorage] = None,
        event_callback: Optional[Callable] = None,
    ):
        """
        Initialize deployment service.

        Args:
            config_path: Path to deployment configuration file
            storage: Storage backend (defaults to in-memory)
            event_callback: Callback for deployment events (for WebSocket)
        """
        self.storage = storage or _storage
        self.event_callback = event_callback
        self.config = self._load_config(config_path)
        self._github_client = None
        self._initialized = False

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config",
                "deployment_config.yaml",
            )

        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"Config file not found: {config_path}")
            return {}
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}

    async def initialize(self) -> None:
        """Initialize service and load environments."""
        if self._initialized:
            return

        # Initialize environments from config
        for env_config in self.config.get("environments", []):
            env = Environment(
                id=str(uuid.uuid4()),
                name=env_config["name"],
                display_name=env_config.get("display_name", env_config["name"]),
                description=env_config.get("description", ""),
                github_environment=env_config.get("github_environment", ""),
                health_url=env_config.get("health_url", ""),
                portainer_stack=env_config.get("portainer_stack", ""),
                is_production=env_config.get("is_production", False),
                requires_approval=env_config.get("requires_approval", False),
                deploy_timeout_seconds=env_config.get("deploy_timeout_seconds", 300),
            )
            self.storage.add_environment(env)

        # Initialize GitHub client
        from services.github_actions_client import GitHubActionsClient
        github_config = self.config.get("github", {})
        self._github_client = GitHubActionsClient(
            repository=github_config.get("repository"),
            timeout=github_config.get("timeout_seconds", 30),
            max_retries=github_config.get("max_retries", 3),
        )

        self._initialized = True
        logger.info(f"Deployment service initialized with {len(self.storage.environments)} environments")

    async def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit a deployment event."""
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

    # =========================================================================
    # Environment Operations
    # =========================================================================

    async def get_environments(self) -> List[Environment]:
        """Get all active environments."""
        return self.storage.list_environments()

    async def get_environment(self, env_id: str) -> Optional[Environment]:
        """Get environment by ID."""
        return self.storage.get_environment(env_id)

    async def get_environment_by_name(self, name: str) -> Optional[Environment]:
        """Get environment by name."""
        return self.storage.get_environment_by_name(name)

    async def get_environment_status(self, env_id: str) -> Optional[EnvironmentStatus]:
        """
        Get current status of an environment.

        Implements AC-2: Current version per environment
        """
        env = self.storage.get_environment(env_id)
        if not env:
            return None

        latest = self.storage.get_latest_successful_deployment(env_id)
        active = self.storage.get_active_deployment(env_id)

        return EnvironmentStatus(
            environment=env,
            current_version=latest.version if latest else None,
            current_deployment_id=latest.id if latest else None,
            deployed_at=latest.completed_at if latest else None,
            deployed_by=latest.triggered_by if latest else None,
            health_status=HealthStatus.UNKNOWN,  # Will be updated by health monitor
            active_deployment=active,
        )

    async def get_all_environment_statuses(self) -> List[EnvironmentStatus]:
        """
        Get status of all environments.

        Implements AC-1: Single dashboard for all environments
        """
        statuses = []
        for env in self.storage.list_environments():
            status = await self.get_environment_status(env.id)
            if status:
                statuses.append(status)
        return statuses

    # =========================================================================
    # Deployment Operations
    # =========================================================================

    async def trigger_deployment(
        self,
        env_id: str,
        version: str,
        triggered_by: str,
        notes: Optional[str] = None,
        git_sha: Optional[str] = None,
        git_branch: Optional[str] = None,
    ) -> Deployment:
        """
        Trigger a deployment to an environment.

        Implements AC-4: One-click deploy from versions

        Args:
            env_id: Environment ID
            version: Version to deploy
            triggered_by: Username triggering deployment
            notes: Optional deployment notes
            git_sha: Optional git commit SHA
            git_branch: Optional git branch

        Returns:
            The created Deployment

        Raises:
            ValueError: If environment not found or deployment blocked
        """
        env = self.storage.get_environment(env_id)
        if not env:
            raise ValueError(f"Environment not found: {env_id}")

        # Check for active deployment
        active = self.storage.get_active_deployment(env_id)
        if active:
            raise ValueError(
                f"Deployment already in progress: {active.id}. "
                f"Wait for completion or cancel it first."
            )

        # Check cooldown
        latest = self.storage.get_latest_successful_deployment(env_id)
        if latest and latest.completed_at:
            cooldown = self.config.get("deployment", {}).get("cooldown_seconds", 60)
            elapsed = (datetime.utcnow() - latest.completed_at).total_seconds()
            if elapsed < cooldown:
                raise ValueError(
                    f"Cooldown period active. Wait {int(cooldown - elapsed)} more seconds."
                )

        # Create deployment record
        deployment = Deployment(
            id=str(uuid.uuid4()),
            environment_id=env_id,
            environment_name=env.name,
            version=version,
            status=DeploymentStatus.PENDING,
            triggered_by=triggered_by,
            trigger_type=TriggerType.MANUAL,
            git_sha=git_sha,
            git_branch=git_branch or self.config.get("github", {}).get("default_ref", "main"),
            notes=notes,
            queued_at=datetime.utcnow(),
        )

        self.storage.add_deployment(deployment)
        DEPLOYMENT_TRIGGERS.labels(environment=env.name, status="pending").inc()
        ACTIVE_DEPLOYMENTS.labels(environment=env.name).inc()

        # Log the start
        await self._add_log(deployment.id, "info", f"Deployment triggered by {triggered_by}", "deploy")

        # Emit event
        await self._emit_event("deployment_started", {
            "deployment_id": deployment.id,
            "environment": env.name,
            "version": version,
            "triggered_by": triggered_by,
        })

        # Trigger GitHub Actions workflow in background
        asyncio.create_task(self._execute_deployment(deployment, env))

        return deployment

    async def _execute_deployment(
        self,
        deployment: Deployment,
        env: Environment,
    ) -> None:
        """Execute the deployment via GitHub Actions."""
        try:
            # Update status to in_progress
            deployment.status = DeploymentStatus.IN_PROGRESS
            deployment.started_at = datetime.utcnow()
            self.storage.update_deployment(deployment)

            await self._add_log(
                deployment.id, "info",
                f"Starting GitHub Actions workflow for {env.github_environment}",
                "deploy"
            )

            # Trigger GitHub workflow
            github_config = self.config.get("github", {})
            workflow_id = github_config.get("workflow_id", "deploy.yml")

            try:
                run_id = await self._github_client.trigger_workflow(
                    workflow_id=workflow_id,
                    ref=deployment.git_branch or "main",
                    inputs={
                        "environment": env.github_environment or env.name,
                        "version": deployment.version,
                    },
                )

                deployment.github_run_id = run_id
                deployment.github_run_url = (
                    f"https://github.com/{github_config.get('repository')}"
                    f"/actions/runs/{run_id}"
                )
                self.storage.update_deployment(deployment)

                await self._add_log(
                    deployment.id, "info",
                    f"GitHub Actions workflow started: {deployment.github_run_url}",
                    "deploy"
                )

                # Poll for completion
                poll_interval = github_config.get("poll_interval_seconds", 10)
                poll_timeout = env.deploy_timeout_seconds

                async def status_callback(run):
                    await self._add_log(
                        deployment.id, "info",
                        f"Workflow status: {run.status.value}",
                        "deploy"
                    )
                    await self._emit_event("deployment_progress", {
                        "deployment_id": deployment.id,
                        "status": run.status.value,
                        "github_run_id": run_id,
                    })

                final_run = await self._github_client.poll_workflow_status(
                    run_id=run_id,
                    poll_interval=poll_interval,
                    timeout=poll_timeout,
                    callback=status_callback,
                )

                if final_run.is_successful():
                    deployment.status = DeploymentStatus.SUCCESS
                    deployment.completed_at = datetime.utcnow()
                    await self._add_log(
                        deployment.id, "info",
                        "Deployment completed successfully",
                        "deploy"
                    )
                else:
                    deployment.status = DeploymentStatus.FAILED
                    deployment.completed_at = datetime.utcnow()
                    deployment.error_message = f"Workflow failed: {final_run.conclusion.value if final_run.conclusion else 'unknown'}"
                    await self._add_log(
                        deployment.id, "error",
                        deployment.error_message,
                        "deploy"
                    )

            except asyncio.TimeoutError:
                deployment.status = DeploymentStatus.FAILED
                deployment.completed_at = datetime.utcnow()
                deployment.error_message = "Deployment timed out"
                await self._add_log(deployment.id, "error", "Deployment timed out", "deploy")

            except Exception as e:
                deployment.status = DeploymentStatus.FAILED
                deployment.completed_at = datetime.utcnow()
                deployment.error_message = str(e)
                await self._add_log(deployment.id, "error", f"GitHub Actions error: {e}", "deploy")

        except Exception as e:
            deployment.status = DeploymentStatus.FAILED
            deployment.completed_at = datetime.utcnow()
            deployment.error_message = str(e)
            logger.error(f"Deployment execution error: {e}")

        finally:
            self.storage.update_deployment(deployment)
            ACTIVE_DEPLOYMENTS.labels(environment=env.name).dec()

            if deployment.status == DeploymentStatus.SUCCESS:
                DEPLOYMENT_TRIGGERS.labels(environment=env.name, status="success").inc()
            else:
                DEPLOYMENT_TRIGGERS.labels(environment=env.name, status="failed").inc()

            if deployment.started_at:
                duration = (datetime.utcnow() - deployment.started_at).total_seconds()
                DEPLOYMENT_DURATION.observe(duration)

            # Emit completion event
            event_type = "deployment_completed" if deployment.status == DeploymentStatus.SUCCESS else "deployment_failed"
            await self._emit_event(event_type, {
                "deployment_id": deployment.id,
                "environment": env.name,
                "version": deployment.version,
                "status": deployment.status.value,
                "error": deployment.error_message,
            })

    async def cancel_deployment(
        self,
        deployment_id: str,
        cancelled_by: str,
    ) -> bool:
        """
        Cancel an active deployment.

        Args:
            deployment_id: Deployment ID
            cancelled_by: Username cancelling deployment

        Returns:
            True if cancelled successfully
        """
        deployment = self.storage.get_deployment(deployment_id)
        if not deployment:
            return False

        if deployment.status not in [
            DeploymentStatus.PENDING,
            DeploymentStatus.QUEUED,
            DeploymentStatus.IN_PROGRESS,
        ]:
            return False

        # Cancel GitHub workflow if running
        if deployment.github_run_id and self._github_client:
            await self._github_client.cancel_workflow_run(deployment.github_run_id)

        deployment.status = DeploymentStatus.CANCELLED
        deployment.completed_at = datetime.utcnow()
        deployment.error_message = f"Cancelled by {cancelled_by}"
        self.storage.update_deployment(deployment)

        await self._add_log(
            deployment_id, "warning",
            f"Deployment cancelled by {cancelled_by}",
            "deploy"
        )

        await self._emit_event("deployment_cancelled", {
            "deployment_id": deployment_id,
            "cancelled_by": cancelled_by,
        })

        return True

    async def rollback_deployment(
        self,
        deployment_id: str,
        triggered_by: str,
    ) -> Deployment:
        """
        Rollback to a previous deployment.

        Implements AC-6: Basic rollback capability

        Args:
            deployment_id: ID of the deployment to rollback to
            triggered_by: Username triggering rollback

        Returns:
            New rollback deployment
        """
        original = self.storage.get_deployment(deployment_id)
        if not original:
            raise ValueError(f"Deployment not found: {deployment_id}")

        if original.status != DeploymentStatus.SUCCESS:
            raise ValueError("Can only rollback to successful deployments")

        env = self.storage.get_environment(original.environment_id)
        if not env:
            raise ValueError(f"Environment not found: {original.environment_id}")

        # Create rollback deployment
        rollback = Deployment(
            id=str(uuid.uuid4()),
            environment_id=original.environment_id,
            environment_name=original.environment_name,
            version=original.version,
            status=DeploymentStatus.PENDING,
            triggered_by=triggered_by,
            trigger_type=TriggerType.ROLLBACK,
            git_sha=original.git_sha,
            git_branch=original.git_branch,
            notes=f"Rollback to deployment {deployment_id}",
            rollback_of=deployment_id,
            queued_at=datetime.utcnow(),
        )

        self.storage.add_deployment(rollback)

        await self._emit_event("rollback_started", {
            "deployment_id": rollback.id,
            "original_deployment_id": deployment_id,
            "environment": env.name,
            "version": original.version,
            "triggered_by": triggered_by,
        })

        # Execute rollback in background
        asyncio.create_task(self._execute_deployment(rollback, env))

        return rollback

    # =========================================================================
    # History Operations
    # =========================================================================

    async def get_deployment(self, deployment_id: str) -> Optional[Deployment]:
        """Get deployment by ID."""
        return self.storage.get_deployment(deployment_id)

    async def get_deployment_history(
        self,
        env_id: Optional[str] = None,
        limit: int = 50,
        status: Optional[DeploymentStatus] = None,
    ) -> List[Deployment]:
        """
        Get deployment history.

        Implements AC-5: Deployment history with status

        Args:
            env_id: Optional environment ID filter
            limit: Maximum deployments to return
            status: Optional status filter

        Returns:
            List of deployments
        """
        if env_id:
            return self.storage.get_deployments_for_environment(env_id, limit, status)
        return self.storage.get_all_deployments(limit)

    async def get_deployment_logs(
        self,
        deployment_id: str,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> List[DeploymentLog]:
        """Get logs for a deployment."""
        return self.storage.get_deployment_logs(deployment_id, level, limit)

    async def _add_log(
        self,
        deployment_id: str,
        level: str,
        message: str,
        stage: Optional[str] = None,
        source: str = "deployment_service",
    ) -> None:
        """Add a log entry for a deployment."""
        log = DeploymentLog(
            id=str(uuid.uuid4()),
            deployment_id=deployment_id,
            timestamp=datetime.utcnow(),
            level=level,
            message=message,
            stage=stage,
            source=source,
        )
        self.storage.add_deployment_log(log)
        logger.log(
            getattr(logging, level.upper(), logging.INFO),
            f"[{deployment_id[:8]}] {message}"
        )

    # =========================================================================
    # Version Operations
    # =========================================================================

    async def get_available_versions(
        self,
        include_prereleases: bool = False,
        limit: int = 20,
    ) -> List[Version]:
        """
        Get available versions for deployment.

        Args:
            include_prereleases: Include pre-release versions
            limit: Maximum versions to return

        Returns:
            List of available versions
        """
        try:
            releases = await self._github_client.list_releases(
                per_page=limit,
                include_prereleases=include_prereleases,
            )

            versions = []
            for i, release in enumerate(releases):
                version = Version(
                    version=release["tag_name"],
                    git_tag=release["tag_name"],
                    release_notes=release.get("body"),
                    is_prerelease=release.get("prerelease", False),
                    is_latest=(i == 0),
                    published_at=datetime.fromisoformat(
                        release["published_at"].replace("Z", "+00:00")
                    ) if release.get("published_at") else None,
                )
                versions.append(version)

            return versions

        except Exception as e:
            logger.error(f"Error fetching versions: {e}")
            return []


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_service: Optional[DeploymentService] = None


def get_deployment_service() -> DeploymentService:
    """Get the singleton deployment service instance."""
    global _service
    if _service is None:
        _service = DeploymentService()
    return _service


async def initialize_deployment_service() -> DeploymentService:
    """Initialize and return the deployment service."""
    service = get_deployment_service()
    await service.initialize()
    return service
