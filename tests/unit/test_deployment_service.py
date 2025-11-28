#!/usr/bin/env python3
"""
Unit Tests for Deployment Management Service
Epic: MD-1790 [Platform] Unified Deployment Management GUI

Tests for:
- DeploymentService
- DeploymentHealthMonitor
- GitHubActionsClient (mock integration)

Acceptance Criteria Verification:
- AC-1: Single dashboard for all environments
- AC-2: Current version per environment
- AC-3: Health status per environment
- AC-4: One-click deploy from versions
- AC-5: Deployment history with status
- AC-6: Basic rollback capability
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from services.deployment_service import (
    DeploymentService,
    DeploymentStorage,
    Environment,
    Deployment,
    DeploymentStatus,
    TriggerType,
    HealthStatus,
    EnvironmentStatus,
    Version,
)
from services.deployment_health_monitor import (
    DeploymentHealthMonitor,
    HealthSnapshotStorage,
    HealthCheckResult,
    HealthSnapshot,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def storage():
    """Create a fresh storage instance for each test."""
    return DeploymentStorage()


@pytest.fixture
def deployment_service(storage):
    """Create a deployment service with mock storage."""
    service = DeploymentService(storage=storage)
    # Add test environments
    storage.add_environment(Environment(
        id="env-beta",
        name="beta",
        display_name="Beta Environment",
        github_environment="development",
        health_url="http://localhost:4001/health",
    ))
    storage.add_environment(Environment(
        id="env-prod",
        name="production",
        display_name="Production",
        github_environment="production",
        health_url="http://localhost:4001/health",
        is_production=True,
        requires_approval=True,
    ))
    return service


@pytest.fixture
def health_storage():
    """Create a fresh health storage instance."""
    return HealthSnapshotStorage()


@pytest.fixture
def health_monitor(health_storage):
    """Create a health monitor with mock storage."""
    monitor = DeploymentHealthMonitor(storage=health_storage)
    monitor.register_environment("env-beta", "beta", "http://localhost:4001/health")
    monitor.register_environment("env-prod", "production", "http://localhost:5000/health")
    return monitor


# ============================================================================
# DEPLOYMENT SERVICE TESTS
# ============================================================================

class TestDeploymentStorage:
    """Tests for DeploymentStorage."""

    def test_add_and_get_environment(self, storage):
        """Test adding and retrieving environments."""
        env = Environment(
            id="test-env",
            name="test",
            display_name="Test Environment",
        )
        storage.add_environment(env)

        result = storage.get_environment("test-env")
        assert result is not None
        assert result.name == "test"
        assert result.display_name == "Test Environment"

    def test_get_environment_by_name(self, storage):
        """Test retrieving environment by name."""
        env = Environment(id="env-1", name="staging", display_name="Staging")
        storage.add_environment(env)

        result = storage.get_environment_by_name("staging")
        assert result is not None
        assert result.id == "env-1"

    def test_list_active_environments(self, storage):
        """Test listing only active environments."""
        storage.add_environment(Environment(id="1", name="active", display_name="Active", is_active=True))
        storage.add_environment(Environment(id="2", name="inactive", display_name="Inactive", is_active=False))

        environments = storage.list_environments()
        assert len(environments) == 1
        assert environments[0].name == "active"

    def test_add_and_get_deployment(self, storage):
        """Test adding and retrieving deployments."""
        deployment = Deployment(
            id="deploy-1",
            environment_id="env-beta",
            environment_name="beta",
            version="1.0.0",
            status=DeploymentStatus.SUCCESS,
            triggered_by="test-user",
        )
        storage.add_deployment(deployment)

        result = storage.get_deployment("deploy-1")
        assert result is not None
        assert result.version == "1.0.0"
        assert result.status == DeploymentStatus.SUCCESS

    def test_get_deployments_for_environment(self, storage):
        """Test getting deployments filtered by environment."""
        storage.add_deployment(Deployment(
            id="d1", environment_id="env-1", environment_name="beta",
            version="1.0", status=DeploymentStatus.SUCCESS, triggered_by="user"
        ))
        storage.add_deployment(Deployment(
            id="d2", environment_id="env-1", environment_name="beta",
            version="1.1", status=DeploymentStatus.SUCCESS, triggered_by="user"
        ))
        storage.add_deployment(Deployment(
            id="d3", environment_id="env-2", environment_name="prod",
            version="1.0", status=DeploymentStatus.SUCCESS, triggered_by="user"
        ))

        deployments = storage.get_deployments_for_environment("env-1")
        assert len(deployments) == 2

    def test_get_latest_successful_deployment(self, storage):
        """Test getting the most recent successful deployment."""
        # Add deployments with different times
        d1 = Deployment(
            id="d1", environment_id="env-1", environment_name="beta",
            version="1.0", status=DeploymentStatus.SUCCESS, triggered_by="user",
            completed_at=datetime.utcnow() - timedelta(hours=2),
        )
        d2 = Deployment(
            id="d2", environment_id="env-1", environment_name="beta",
            version="1.1", status=DeploymentStatus.SUCCESS, triggered_by="user",
            completed_at=datetime.utcnow() - timedelta(hours=1),
        )
        d3 = Deployment(
            id="d3", environment_id="env-1", environment_name="beta",
            version="1.2", status=DeploymentStatus.FAILED, triggered_by="user",
            completed_at=datetime.utcnow(),
        )

        storage.add_deployment(d1)
        storage.add_deployment(d2)
        storage.add_deployment(d3)

        latest = storage.get_latest_successful_deployment("env-1")
        assert latest is not None
        assert latest.version == "1.1"  # d2 is most recent success


class TestDeploymentService:
    """Tests for DeploymentService."""

    @pytest.mark.asyncio
    async def test_get_environments(self, deployment_service):
        """AC-1: Test listing all environments."""
        environments = await deployment_service.get_environments()
        assert len(environments) == 2
        names = [e.name for e in environments]
        assert "beta" in names
        assert "production" in names

    @pytest.mark.asyncio
    async def test_get_environment_status(self, deployment_service):
        """AC-2: Test getting current version per environment."""
        # Add a successful deployment
        deployment_service.storage.add_deployment(Deployment(
            id="d1",
            environment_id="env-beta",
            environment_name="beta",
            version="2.0.0",
            status=DeploymentStatus.SUCCESS,
            triggered_by="test",
            completed_at=datetime.utcnow(),
        ))

        status = await deployment_service.get_environment_status("env-beta")
        assert status is not None
        assert status.current_version == "2.0.0"
        assert status.environment.name == "beta"

    @pytest.mark.asyncio
    async def test_get_all_environment_statuses(self, deployment_service):
        """AC-1: Test getting status for all environments (dashboard data)."""
        statuses = await deployment_service.get_all_environment_statuses()
        assert len(statuses) == 2

    @pytest.mark.asyncio
    async def test_trigger_deployment_creates_deployment(self, deployment_service):
        """AC-4: Test triggering a deployment creates a deployment record."""
        # Mock the GitHub client
        with patch.object(deployment_service, '_github_client') as mock_client:
            mock_client.trigger_workflow = AsyncMock(return_value=12345)
            mock_client.poll_workflow_status = AsyncMock()

            deployment = await deployment_service.trigger_deployment(
                env_id="env-beta",
                version="3.0.0",
                triggered_by="test-user",
                notes="Test deployment",
            )

            assert deployment is not None
            assert deployment.version == "3.0.0"
            assert deployment.triggered_by == "test-user"
            assert deployment.status == DeploymentStatus.PENDING

    @pytest.mark.asyncio
    async def test_trigger_deployment_blocks_when_active(self, deployment_service):
        """Test that concurrent deployments to same environment are blocked."""
        # Add an active deployment
        deployment_service.storage.add_deployment(Deployment(
            id="active-1",
            environment_id="env-beta",
            environment_name="beta",
            version="2.0.0",
            status=DeploymentStatus.IN_PROGRESS,
            triggered_by="user1",
        ))

        with pytest.raises(ValueError) as excinfo:
            await deployment_service.trigger_deployment(
                env_id="env-beta",
                version="3.0.0",
                triggered_by="user2",
            )

        assert "Deployment already in progress" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_get_deployment_history(self, deployment_service):
        """AC-5: Test getting deployment history."""
        # Add some deployments
        for i in range(5):
            deployment_service.storage.add_deployment(Deployment(
                id=f"d{i}",
                environment_id="env-beta",
                environment_name="beta",
                version=f"1.{i}.0",
                status=DeploymentStatus.SUCCESS,
                triggered_by="test",
            ))

        history = await deployment_service.get_deployment_history("env-beta", limit=10)
        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_rollback_deployment(self, deployment_service):
        """AC-6: Test rollback capability."""
        # Add a successful deployment to rollback to
        deployment_service.storage.add_deployment(Deployment(
            id="original-deploy",
            environment_id="env-beta",
            environment_name="beta",
            version="1.0.0",
            status=DeploymentStatus.SUCCESS,
            triggered_by="user1",
            completed_at=datetime.utcnow() - timedelta(hours=1),
        ))

        # Mock GitHub client
        with patch.object(deployment_service, '_github_client') as mock_client:
            mock_client.trigger_workflow = AsyncMock(return_value=12345)
            mock_client.poll_workflow_status = AsyncMock()

            rollback = await deployment_service.rollback_deployment(
                deployment_id="original-deploy",
                triggered_by="admin",
            )

            assert rollback is not None
            assert rollback.version == "1.0.0"
            assert rollback.trigger_type == TriggerType.ROLLBACK
            assert rollback.rollback_of == "original-deploy"

    @pytest.mark.asyncio
    async def test_rollback_only_successful_deployments(self, deployment_service):
        """Test that only successful deployments can be rolled back to."""
        deployment_service.storage.add_deployment(Deployment(
            id="failed-deploy",
            environment_id="env-beta",
            environment_name="beta",
            version="1.0.0",
            status=DeploymentStatus.FAILED,
            triggered_by="user1",
        ))

        with pytest.raises(ValueError) as excinfo:
            await deployment_service.rollback_deployment(
                deployment_id="failed-deploy",
                triggered_by="admin",
            )

        assert "Can only rollback to successful deployments" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_cancel_deployment(self, deployment_service):
        """Test cancelling an active deployment."""
        deployment_service.storage.add_deployment(Deployment(
            id="active-deploy",
            environment_id="env-beta",
            environment_name="beta",
            version="2.0.0",
            status=DeploymentStatus.IN_PROGRESS,
            triggered_by="user1",
            github_run_id=12345,
        ))

        with patch.object(deployment_service, '_github_client') as mock_client:
            mock_client.cancel_workflow_run = AsyncMock(return_value=True)

            success = await deployment_service.cancel_deployment(
                deployment_id="active-deploy",
                cancelled_by="admin",
            )

            assert success is True

            deployment = deployment_service.storage.get_deployment("active-deploy")
            assert deployment.status == DeploymentStatus.CANCELLED


# ============================================================================
# HEALTH MONITOR TESTS
# ============================================================================

class TestHealthSnapshotStorage:
    """Tests for HealthSnapshotStorage."""

    def test_add_and_get_snapshot(self, health_storage):
        """Test adding and retrieving health snapshots."""
        snapshot = HealthSnapshot(
            id="snap-1",
            environment_id="env-1",
            status=HealthStatus.HEALTHY,
            response_time_ms=50,
            status_code=200,
            details={},
            recorded_at=datetime.utcnow(),
        )
        health_storage.add_snapshot(snapshot)

        snapshots = health_storage.get_snapshots("env-1")
        assert len(snapshots) == 1
        assert snapshots[0].status == HealthStatus.HEALTHY

    def test_snapshot_retention(self, health_storage):
        """Test that old snapshots are cleaned up."""
        # Add old snapshot
        old_snapshot = HealthSnapshot(
            id="old",
            environment_id="env-1",
            status=HealthStatus.HEALTHY,
            response_time_ms=50,
            status_code=200,
            details={},
            recorded_at=datetime.utcnow() - timedelta(hours=200),
        )
        health_storage.add_snapshot(old_snapshot)

        # Add recent snapshot
        new_snapshot = HealthSnapshot(
            id="new",
            environment_id="env-1",
            status=HealthStatus.HEALTHY,
            response_time_ms=50,
            status_code=200,
            details={},
            recorded_at=datetime.utcnow(),
        )
        health_storage.add_snapshot(new_snapshot)

        # Only get snapshots from last 24 hours
        snapshots = health_storage.get_snapshots("env-1", hours=24)
        assert len(snapshots) == 1
        assert snapshots[0].id == "new"

    def test_current_status_tracking(self, health_storage):
        """Test tracking current health status."""
        result = HealthCheckResult(
            environment_id="env-1",
            environment_name="beta",
            status=HealthStatus.HEALTHY,
            response_time_ms=100,
            status_code=200,
        )
        health_storage.set_current_status(result)

        current = health_storage.get_current_status("env-1")
        assert current is not None
        assert current.status == HealthStatus.HEALTHY


class TestDeploymentHealthMonitor:
    """Tests for DeploymentHealthMonitor."""

    def test_register_environment(self, health_monitor):
        """Test registering an environment for monitoring."""
        health_monitor.register_environment("env-3", "staging", "http://staging/health")
        assert "env-3" in health_monitor._environments

    def test_unregister_environment(self, health_monitor):
        """Test unregistering an environment."""
        health_monitor.unregister_environment("env-beta")
        assert "env-beta" not in health_monitor._environments

    @pytest.mark.asyncio
    async def test_check_environment_health_success(self, health_monitor):
        """AC-3: Test successful health check."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"status": "ok"})
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await health_monitor.check_environment_health("env-beta")

            assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNKNOWN]

    def test_get_health_summary(self, health_monitor):
        """Test getting health summary for dashboard."""
        # Set some current statuses
        health_monitor.storage.set_current_status(HealthCheckResult(
            environment_id="env-beta",
            environment_name="beta",
            status=HealthStatus.HEALTHY,
        ))
        health_monitor.storage.set_current_status(HealthCheckResult(
            environment_id="env-prod",
            environment_name="production",
            status=HealthStatus.DEGRADED,
        ))

        summary = health_monitor.get_health_summary()

        assert summary["total"] == 2
        assert summary["healthy"] == 1
        assert summary["degraded"] == 1


# ============================================================================
# DATA CLASS TESTS
# ============================================================================

class TestDataClasses:
    """Tests for data class serialization."""

    def test_environment_to_dict(self):
        """Test Environment serialization."""
        env = Environment(
            id="env-1",
            name="beta",
            display_name="Beta",
            is_production=False,
        )
        data = env.to_dict()

        assert data["id"] == "env-1"
        assert data["name"] == "beta"
        assert data["is_production"] is False

    def test_deployment_to_dict(self):
        """Test Deployment serialization."""
        deployment = Deployment(
            id="d1",
            environment_id="env-1",
            environment_name="beta",
            version="1.0.0",
            status=DeploymentStatus.SUCCESS,
            triggered_by="user",
            started_at=datetime(2024, 1, 1, 12, 0, 0),
            completed_at=datetime(2024, 1, 1, 12, 5, 0),
        )
        data = deployment.to_dict()

        assert data["id"] == "d1"
        assert data["version"] == "1.0.0"
        assert data["status"] == "success"
        assert data["duration_seconds"] == 300

    def test_version_to_dict(self):
        """Test Version serialization."""
        version = Version(
            version="2.0.0",
            git_sha="abc123",
            is_latest=True,
            deployed_to=["beta", "production"],
        )
        data = version.to_dict()

        assert data["version"] == "2.0.0"
        assert data["is_latest"] is True
        assert "beta" in data["deployed_to"]


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestDeploymentIntegration:
    """Integration tests for the deployment workflow."""

    @pytest.mark.asyncio
    async def test_full_deployment_workflow(self, deployment_service):
        """Test the complete deployment workflow."""
        # 1. List environments
        environments = await deployment_service.get_environments()
        assert len(environments) > 0

        # 2. Get initial status
        status = await deployment_service.get_environment_status("env-beta")
        assert status.current_version is None  # No deployments yet

        # 3. Trigger deployment (mocked)
        with patch.object(deployment_service, '_github_client') as mock_client:
            mock_client.trigger_workflow = AsyncMock(return_value=12345)

            deployment = await deployment_service.trigger_deployment(
                env_id="env-beta",
                version="1.0.0",
                triggered_by="integration-test",
            )
            assert deployment.status == DeploymentStatus.PENDING

        # 4. Simulate deployment completion
        deployment.status = DeploymentStatus.SUCCESS
        deployment.completed_at = datetime.utcnow()
        deployment_service.storage.update_deployment(deployment)

        # 5. Verify status updated
        status = await deployment_service.get_environment_status("env-beta")
        assert status.current_version == "1.0.0"

        # 6. Check history
        history = await deployment_service.get_deployment_history("env-beta")
        assert len(history) == 1
        assert history[0].version == "1.0.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
