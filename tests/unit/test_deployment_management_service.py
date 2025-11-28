#!/usr/bin/env python3
"""
Unit tests for Deployment Management Service
Epic: MD-1790 [Platform] Unified Deployment Management GUI

Tests cover:
- MD-1878: Environment Status API
- MD-1879: Deployment History Service
- MD-1880: Version Management Service
- MD-1881: One-Click Deploy API
- MD-1882: Rollback Capability API
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.deployment_management_service import (
    DeploymentManagementService,
    DeploymentStorage,
    EnvironmentConfig,
    EnvironmentState,
    EnvironmentType,
    EnvironmentStatus,
    DeploymentRecord,
    DeploymentStatus,
    DeploymentAction,
    DeploymentRequest,
    DeploymentValidation,
    Version,
    RollbackRequest,
    HealthCheck,
    get_deployment_management_service,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def storage():
    """Create a fresh storage instance."""
    return DeploymentStorage()


@pytest.fixture
def service(storage):
    """Create a service with fresh storage."""
    return DeploymentManagementService(storage=storage)


@pytest.fixture
def sample_environment():
    """Create a sample environment config."""
    return EnvironmentConfig(
        id="env-test",
        name="Test",
        type=EnvironmentType.BETA,
        url="https://test.example.com",
        health_url="https://test.example.com/health",
        description="Test environment",
    )


@pytest.fixture
def sample_version():
    """Create a sample version."""
    return Version(
        version_id="v-001",
        version_tag="v1.0.0",
        commit_sha="abc123",
        branch="main",
        release_type="release",
        release_notes="Initial release",
        is_deployable=True,
    )


@pytest.fixture
def sample_deployment():
    """Create a sample deployment record."""
    return DeploymentRecord(
        deployment_id="dep-001",
        environment_id="env-test",
        environment_name="Test",
        version="v1.0.0",
        action=DeploymentAction.DEPLOY,
        status=DeploymentStatus.SUCCESS,
        triggered_by="test-user",
        started_at=datetime.utcnow() - timedelta(minutes=5),
        completed_at=datetime.utcnow(),
    )


# ============================================================================
# MD-1878: Environment Status API Tests
# ============================================================================

class TestEnvironmentConfig:
    """Test EnvironmentConfig dataclass."""

    def test_environment_config_defaults(self):
        """Test default values for EnvironmentConfig."""
        config = EnvironmentConfig(
            id="env-1",
            name="Test",
            type=EnvironmentType.BETA,
            url="https://test.com",
            health_url="https://test.com/health",
        )
        assert config.is_production is False
        assert config.auto_deploy_enabled is False
        assert config.requires_approval is False
        assert config.max_instances == 1

    def test_environment_config_to_dict(self, sample_environment):
        """Test EnvironmentConfig serialization."""
        data = sample_environment.to_dict()
        assert data["id"] == "env-test"
        assert data["name"] == "Test"
        assert data["type"] == "beta"
        assert "url" in data


class TestEnvironmentState:
    """Test EnvironmentState dataclass."""

    def test_environment_state_defaults(self):
        """Test default values for EnvironmentState."""
        state = EnvironmentState(
            environment_id="env-1",
            environment_name="Test",
            environment_type=EnvironmentType.BETA,
            status=EnvironmentStatus.HEALTHY,
        )
        assert state.current_version is None
        assert state.uptime_percentage == 100.0
        assert state.health_checks == []

    def test_environment_state_to_dict(self):
        """Test EnvironmentState serialization."""
        state = EnvironmentState(
            environment_id="env-1",
            environment_name="Test",
            environment_type=EnvironmentType.BETA,
            status=EnvironmentStatus.HEALTHY,
            current_version="v1.0.0",
            deployed_at=datetime.utcnow(),
        )
        data = state.to_dict()
        assert data["environment_id"] == "env-1"
        assert data["status"] == "healthy"
        assert data["is_healthy"] is True
        assert data["current_version"] == "v1.0.0"


class TestEnvironmentManagement:
    """Test environment management functionality."""

    def test_get_environments(self, service):
        """Test getting all environments."""
        envs = service.get_environments()
        # Default environments are initialized
        assert len(envs) >= 4
        env_names = [e.name for e in envs]
        assert "Beta" in env_names
        assert "Demo" in env_names
        assert "Production" in env_names

    def test_get_environment(self, service):
        """Test getting specific environment."""
        env = service.get_environment("env-beta")
        assert env is not None
        assert env.name == "Beta"
        assert env.type == EnvironmentType.BETA

    def test_get_environment_not_found(self, service):
        """Test getting non-existent environment."""
        env = service.get_environment("env-nonexistent")
        assert env is None

    def test_get_environment_states(self, service):
        """Test getting all environment states."""
        states = service.get_environment_states()
        assert len(states) >= 4
        state_names = [s.environment_name for s in states]
        assert "Beta" in state_names

    def test_add_environment(self, service, sample_environment):
        """Test adding a new environment."""
        service.add_environment(sample_environment)
        env = service.get_environment("env-test")
        assert env is not None
        assert env.name == "Test"

    @pytest.mark.asyncio
    async def test_check_environment_health_success(self, service, sample_environment):
        """Test successful health check."""
        service.add_environment(sample_environment)

        with patch.object(service, '_get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status = 200

            # Create a proper async context manager
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session.get = MagicMock(return_value=mock_cm)
            mock_get_session.return_value = mock_session

            state = await service.check_environment_health("env-test")

            assert state.status == EnvironmentStatus.HEALTHY
            assert len(state.health_checks) > 0
            assert state.health_checks[0].status == "pass"

    @pytest.mark.asyncio
    async def test_check_environment_health_failure(self, service, sample_environment):
        """Test failed health check."""
        service.add_environment(sample_environment)

        with patch.object(service, '_get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status = 500

            # Create a proper async context manager
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session.get = MagicMock(return_value=mock_cm)
            mock_get_session.return_value = mock_session

            state = await service.check_environment_health("env-test")

            assert state.status == EnvironmentStatus.UNHEALTHY
            assert state.health_checks[0].status == "fail"

    @pytest.mark.asyncio
    async def test_check_environment_health_timeout(self, service, sample_environment):
        """Test health check timeout."""
        service.add_environment(sample_environment)

        with patch.object(service, '_get_session') as mock_get_session:
            mock_session = MagicMock()

            # Create an async context manager that raises TimeoutError
            async def raise_timeout(*args, **kwargs):
                raise asyncio.TimeoutError()

            mock_cm = MagicMock()
            mock_cm.__aenter__ = raise_timeout
            mock_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session.get = MagicMock(return_value=mock_cm)
            mock_get_session.return_value = mock_session

            state = await service.check_environment_health("env-test")

            assert state.status == EnvironmentStatus.UNHEALTHY
            assert state.health_checks[0].status == "fail"
            assert "Timeout" in state.health_checks[0].message


# ============================================================================
# MD-1879: Deployment History Service Tests
# ============================================================================

class TestDeploymentRecord:
    """Test DeploymentRecord dataclass."""

    def test_deployment_record_defaults(self):
        """Test default values for DeploymentRecord."""
        record = DeploymentRecord(
            deployment_id="dep-1",
            environment_id="env-1",
            environment_name="Test",
            version="v1.0.0",
        )
        assert record.status == DeploymentStatus.PENDING
        assert record.action == DeploymentAction.DEPLOY
        assert record.triggered_by == "system"

    def test_deployment_record_to_dict(self, sample_deployment):
        """Test DeploymentRecord serialization."""
        data = sample_deployment.to_dict()
        assert data["deployment_id"] == "dep-001"
        assert data["version"] == "v1.0.0"
        assert data["status"] == "success"
        assert "duration_seconds" in data

    def test_deployment_duration_calculation(self, sample_deployment):
        """Test deployment duration calculation."""
        duration = sample_deployment.get_duration_seconds()
        assert duration is not None
        assert duration > 0


class TestDeploymentHistory:
    """Test deployment history functionality."""

    def test_get_deployment_history_empty(self, service):
        """Test getting empty deployment history."""
        history = service.get_deployment_history()
        assert isinstance(history, list)

    def test_get_deployment_history_with_records(self, service, storage, sample_deployment):
        """Test getting deployment history with records."""
        storage.add_deployment(sample_deployment)
        history = service.get_deployment_history()
        assert len(history) == 1
        assert history[0].deployment_id == "dep-001"

    def test_get_deployment_history_by_environment(self, service, storage, sample_deployment):
        """Test filtering deployment history by environment."""
        storage.add_deployment(sample_deployment)

        # Add another deployment for different environment
        other_deployment = DeploymentRecord(
            deployment_id="dep-002",
            environment_id="env-other",
            environment_name="Other",
            version="v2.0.0",
        )
        storage.add_deployment(other_deployment)

        history = service.get_deployment_history(env_id="env-test")
        assert len(history) == 1
        assert history[0].environment_id == "env-test"

    def test_get_deployment_history_by_status(self, service, storage):
        """Test filtering deployment history by status."""
        success_dep = DeploymentRecord(
            deployment_id="dep-s",
            environment_id="env-1",
            environment_name="Test",
            version="v1.0.0",
            status=DeploymentStatus.SUCCESS,
        )
        failed_dep = DeploymentRecord(
            deployment_id="dep-f",
            environment_id="env-1",
            environment_name="Test",
            version="v2.0.0",
            status=DeploymentStatus.FAILED,
        )
        storage.add_deployment(success_dep)
        storage.add_deployment(failed_dep)

        success_history = service.get_deployment_history(status=DeploymentStatus.SUCCESS)
        assert len(success_history) == 1
        assert success_history[0].status == DeploymentStatus.SUCCESS

    def test_get_deployment(self, service, storage, sample_deployment):
        """Test getting specific deployment."""
        storage.add_deployment(sample_deployment)
        deployment = service.get_deployment("dep-001")
        assert deployment is not None
        assert deployment.version == "v1.0.0"

    def test_get_deployment_not_found(self, service):
        """Test getting non-existent deployment."""
        deployment = service.get_deployment("dep-nonexistent")
        assert deployment is None


class TestDeploymentMetrics:
    """Test deployment metrics functionality."""

    def test_get_deployment_metrics_empty(self, service):
        """Test metrics with no deployments."""
        metrics = service.get_deployment_metrics()
        assert metrics["total_deployments"] == 0
        assert metrics["success_rate"] == 0

    def test_get_deployment_metrics_with_data(self, service, storage):
        """Test metrics with deployment data."""
        # Add some deployments
        for i in range(5):
            dep = DeploymentRecord(
                deployment_id=f"dep-{i}",
                environment_id="env-1",
                environment_name="Test",
                version=f"v{i}.0.0",
                status=DeploymentStatus.SUCCESS if i < 4 else DeploymentStatus.FAILED,
                started_at=datetime.utcnow() - timedelta(minutes=10),
                completed_at=datetime.utcnow(),
            )
            storage.add_deployment(dep)

        metrics = service.get_deployment_metrics(days=30)
        assert metrics["total_deployments"] == 5
        assert metrics["successful"] == 4
        assert metrics["failed"] == 1
        assert metrics["success_rate"] == 80.0


# ============================================================================
# MD-1880: Version Management Service Tests
# ============================================================================

class TestVersion:
    """Test Version dataclass."""

    def test_version_defaults(self):
        """Test default values for Version."""
        version = Version(
            version_id="v-1",
            version_tag="v1.0.0",
            commit_sha="abc123",
        )
        assert version.branch == "main"
        assert version.release_type == "release"
        assert version.is_deployable is True

    def test_version_to_dict(self, sample_version):
        """Test Version serialization."""
        data = sample_version.to_dict()
        assert data["version_tag"] == "v1.0.0"
        assert data["commit_sha"] == "abc123"
        assert data["is_deployable"] is True


class TestVersionManagement:
    """Test version management functionality."""

    def test_get_versions_empty(self, service):
        """Test getting versions when none exist."""
        versions = service.get_versions()
        assert isinstance(versions, list)

    def test_add_and_get_version(self, service, sample_version):
        """Test adding and retrieving a version."""
        service.add_version(sample_version)
        version = service.get_version("v-001")
        assert version is not None
        assert version.version_tag == "v1.0.0"

    def test_get_version_by_tag(self, service, sample_version):
        """Test getting version by tag."""
        service.add_version(sample_version)
        version = service.get_version_by_tag("v1.0.0")
        assert version is not None
        assert version.version_id == "v-001"

    def test_get_versions_deployable_only(self, service, storage):
        """Test filtering deployable versions."""
        deployable = Version(
            version_id="v-d",
            version_tag="v1.0.0",
            commit_sha="abc",
            is_deployable=True,
        )
        not_deployable = Version(
            version_id="v-nd",
            version_tag="v0.9.0",
            commit_sha="xyz",
            is_deployable=False,
        )
        storage.add_version(deployable)
        storage.add_version(not_deployable)

        versions = service.get_versions(deployable_only=True)
        assert len(versions) == 1
        assert versions[0].is_deployable is True

    def test_get_current_version(self, service, storage):
        """Test getting current version for environment."""
        state = storage.get_environment_state("env-beta")
        state.current_version = "v1.0.0"
        storage.update_environment_state(state)

        current = service.get_current_version("env-beta")
        assert current == "v1.0.0"

    def test_compare_versions(self, service, storage):
        """Test version comparison."""
        v1 = Version(
            version_id="v-1",
            version_tag="v1.0.0",
            commit_sha="abc",
            branch="main",
            created_at=datetime.utcnow() - timedelta(days=1),
        )
        v2 = Version(
            version_id="v-2",
            version_tag="v2.0.0",
            commit_sha="xyz",
            branch="main",
            created_at=datetime.utcnow(),
        )
        storage.add_version(v1)
        storage.add_version(v2)

        comparison = service.compare_versions("v-1", "v-2")
        assert comparison["same_branch"] is True
        assert comparison["a_is_newer"] is False


# ============================================================================
# MD-1881: One-Click Deploy API Tests
# ============================================================================

class TestDeploymentValidation:
    """Test DeploymentValidation dataclass."""

    def test_deployment_validation_to_dict(self):
        """Test DeploymentValidation serialization."""
        validation = DeploymentValidation(
            is_valid=True,
            checks=[{"name": "test", "status": "pass"}],
            warnings=["warning1"],
            errors=[],
        )
        data = validation.to_dict()
        assert data["is_valid"] is True
        assert len(data["checks"]) == 1
        assert len(data["warnings"]) == 1


class TestDeploymentValidationLogic:
    """Test deployment validation logic."""

    @pytest.mark.asyncio
    async def test_validate_deployment_success(self, service, storage, sample_version):
        """Test successful deployment validation."""
        storage.add_version(sample_version)

        request = DeploymentRequest(
            environment_id="env-beta",
            version_id="v-001",
            triggered_by="test-user",
        )

        validation = await service.validate_deployment(request)
        assert validation.is_valid is True
        assert len(validation.errors) == 0

    @pytest.mark.asyncio
    async def test_validate_deployment_env_not_found(self, service, sample_version):
        """Test validation with non-existent environment."""
        service.storage.add_version(sample_version)

        request = DeploymentRequest(
            environment_id="env-nonexistent",
            version_id="v-001",
            triggered_by="test-user",
        )

        validation = await service.validate_deployment(request)
        assert validation.is_valid is False
        assert any("Environment not found" in e for e in validation.errors)

    @pytest.mark.asyncio
    async def test_validate_deployment_version_not_found(self, service):
        """Test validation with non-existent version."""
        request = DeploymentRequest(
            environment_id="env-beta",
            version_id="v-nonexistent",
            triggered_by="test-user",
        )

        validation = await service.validate_deployment(request)
        assert validation.is_valid is False
        assert any("Version not found" in e for e in validation.errors)

    @pytest.mark.asyncio
    async def test_validate_deployment_already_deploying(self, service, storage, sample_version):
        """Test validation when deployment already in progress."""
        storage.add_version(sample_version)

        # Set environment to deploying state
        state = storage.get_environment_state("env-beta")
        state.status = EnvironmentStatus.DEPLOYING
        storage.update_environment_state(state)

        request = DeploymentRequest(
            environment_id="env-beta",
            version_id="v-001",
            triggered_by="test-user",
        )

        validation = await service.validate_deployment(request)
        assert validation.is_valid is False
        assert any("already in progress" in e for e in validation.errors)


class TestTriggerDeployment:
    """Test deployment triggering."""

    @pytest.mark.asyncio
    async def test_trigger_deployment_success(self, service, storage, sample_version):
        """Test successful deployment trigger."""
        storage.add_version(sample_version)

        request = DeploymentRequest(
            environment_id="env-beta",
            version_id="v-001",
            triggered_by="test-user",
        )

        deployment = await service.trigger_deployment(request)

        assert deployment is not None
        assert deployment.status == DeploymentStatus.PENDING
        assert deployment.version == "v1.0.0"
        assert deployment.triggered_by == "test-user"

        # Check environment state was updated
        state = storage.get_environment_state("env-beta")
        assert state.status == EnvironmentStatus.DEPLOYING
        assert state.pending_deployment_id == deployment.deployment_id

    @pytest.mark.asyncio
    async def test_trigger_deployment_validation_failure(self, service):
        """Test deployment trigger with validation failure."""
        request = DeploymentRequest(
            environment_id="env-beta",
            version_id="v-nonexistent",
            triggered_by="test-user",
        )

        with pytest.raises(ValueError) as exc_info:
            await service.trigger_deployment(request)
        assert "validation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_trigger_deployment_skip_validation(self, service, storage, sample_version):
        """Test deployment trigger with skip validation."""
        storage.add_version(sample_version)

        # Set environment to deploying state
        state = storage.get_environment_state("env-beta")
        state.status = EnvironmentStatus.DEPLOYING
        storage.update_environment_state(state)

        request = DeploymentRequest(
            environment_id="env-beta",
            version_id="v-001",
            triggered_by="test-user",
            skip_validation=True,
        )

        # Should succeed even though env is deploying
        deployment = await service.trigger_deployment(request)
        assert deployment is not None

    @pytest.mark.asyncio
    async def test_trigger_deployment_with_callback(self, service, storage, sample_version):
        """Test deployment trigger with GitHub Actions callback."""
        storage.add_version(sample_version)

        callback_called = False

        async def mock_callback(deployment):
            nonlocal callback_called
            callback_called = True

        service.github_actions_callback = mock_callback

        request = DeploymentRequest(
            environment_id="env-beta",
            version_id="v-001",
            triggered_by="test-user",
        )

        await service.trigger_deployment(request)
        assert callback_called is True


class TestUpdateDeploymentStatus:
    """Test deployment status updates."""

    @pytest.mark.asyncio
    async def test_update_deployment_status_success(self, service, storage, sample_version):
        """Test updating deployment status to success."""
        storage.add_version(sample_version)

        request = DeploymentRequest(
            environment_id="env-beta",
            version_id="v-001",
            triggered_by="test-user",
        )
        deployment = await service.trigger_deployment(request)

        # Update to in progress
        await service.update_deployment_status(
            deployment.deployment_id,
            DeploymentStatus.IN_PROGRESS
        )
        updated = service.get_deployment(deployment.deployment_id)
        assert updated.status == DeploymentStatus.IN_PROGRESS
        assert updated.started_at is not None

        # Update to success
        await service.update_deployment_status(
            deployment.deployment_id,
            DeploymentStatus.SUCCESS
        )
        updated = service.get_deployment(deployment.deployment_id)
        assert updated.status == DeploymentStatus.SUCCESS
        assert updated.completed_at is not None

        # Check environment state was updated
        state = storage.get_environment_state("env-beta")
        assert state.current_version == "v1.0.0"
        assert state.status == EnvironmentStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_update_deployment_status_failed(self, service, storage, sample_version):
        """Test updating deployment status to failed."""
        storage.add_version(sample_version)

        request = DeploymentRequest(
            environment_id="env-beta",
            version_id="v-001",
            triggered_by="test-user",
        )
        deployment = await service.trigger_deployment(request)

        await service.update_deployment_status(
            deployment.deployment_id,
            DeploymentStatus.FAILED,
            error_message="Deployment failed"
        )

        updated = service.get_deployment(deployment.deployment_id)
        assert updated.status == DeploymentStatus.FAILED
        assert updated.error_message == "Deployment failed"

        state = storage.get_environment_state("env-beta")
        assert state.status == EnvironmentStatus.DEGRADED


# ============================================================================
# MD-1882: Rollback Capability API Tests
# ============================================================================

class TestRollbackValidation:
    """Test rollback validation logic."""

    @pytest.mark.asyncio
    async def test_validate_rollback_success(self, service, storage, sample_deployment):
        """Test successful rollback validation."""
        storage.add_deployment(sample_deployment)

        # Add a current deployment
        current_dep = DeploymentRecord(
            deployment_id="dep-current",
            environment_id="env-test",
            environment_name="Test",
            version="v2.0.0",
            status=DeploymentStatus.SUCCESS,
        )
        storage.add_deployment(current_dep)

        # Add environment
        service.add_environment(EnvironmentConfig(
            id="env-test",
            name="Test",
            type=EnvironmentType.BETA,
            url="https://test.com",
            health_url="https://test.com/health",
        ))

        state = storage.get_environment_state("env-test")
        state.current_version = "v2.0.0"
        storage.update_environment_state(state)

        request = RollbackRequest(
            environment_id="env-test",
            triggered_by="test-user",
        )

        validation = await service.validate_rollback(request)
        assert validation.is_valid is True

    @pytest.mark.asyncio
    async def test_validate_rollback_no_previous_deployment(self, service, storage):
        """Test rollback validation with no previous deployment."""
        request = RollbackRequest(
            environment_id="env-beta",
            triggered_by="test-user",
        )

        validation = await service.validate_rollback(request)
        assert validation.is_valid is False
        assert any("No previous deployment" in e for e in validation.errors)

    @pytest.mark.asyncio
    async def test_validate_rollback_deploying(self, service, storage, sample_deployment):
        """Test rollback validation when deployment in progress."""
        storage.add_deployment(sample_deployment)

        service.add_environment(EnvironmentConfig(
            id="env-test",
            name="Test",
            type=EnvironmentType.BETA,
            url="https://test.com",
            health_url="https://test.com/health",
        ))

        state = storage.get_environment_state("env-test")
        state.status = EnvironmentStatus.DEPLOYING
        storage.update_environment_state(state)

        request = RollbackRequest(
            environment_id="env-test",
            triggered_by="test-user",
        )

        validation = await service.validate_rollback(request)
        assert validation.is_valid is False
        assert any("Cannot rollback while deployment in progress" in e for e in validation.errors)


class TestTriggerRollback:
    """Test rollback triggering."""

    @pytest.mark.asyncio
    async def test_trigger_rollback_to_previous(self, service, storage):
        """Test triggering rollback to previous version."""
        # Setup environment
        service.add_environment(EnvironmentConfig(
            id="env-test",
            name="Test",
            type=EnvironmentType.BETA,
            url="https://test.com",
            health_url="https://test.com/health",
        ))

        # Add two deployments
        old_dep = DeploymentRecord(
            deployment_id="dep-old",
            environment_id="env-test",
            environment_name="Test",
            version="v1.0.0",
            status=DeploymentStatus.SUCCESS,
            created_at=datetime.utcnow() - timedelta(hours=1),
        )
        current_dep = DeploymentRecord(
            deployment_id="dep-current",
            environment_id="env-test",
            environment_name="Test",
            version="v2.0.0",
            status=DeploymentStatus.SUCCESS,
        )
        storage.add_deployment(old_dep)
        storage.add_deployment(current_dep)

        state = storage.get_environment_state("env-test")
        state.current_version = "v2.0.0"
        storage.update_environment_state(state)

        request = RollbackRequest(
            environment_id="env-test",
            triggered_by="test-user",
            reason="Testing rollback",
        )

        deployment = await service.trigger_rollback(request)

        assert deployment is not None
        assert deployment.action == DeploymentAction.ROLLBACK
        assert deployment.version == "v1.0.0"
        assert deployment.previous_version == "v2.0.0"
        assert deployment.status == DeploymentStatus.PENDING

    @pytest.mark.asyncio
    async def test_trigger_rollback_to_specific_version(self, service, storage, sample_version):
        """Test triggering rollback to specific version."""
        service.add_environment(EnvironmentConfig(
            id="env-test",
            name="Test",
            type=EnvironmentType.BETA,
            url="https://test.com",
            health_url="https://test.com/health",
        ))

        storage.add_version(sample_version)

        # Add a deployment
        dep = DeploymentRecord(
            deployment_id="dep-1",
            environment_id="env-test",
            environment_name="Test",
            version="v2.0.0",
            status=DeploymentStatus.SUCCESS,
        )
        storage.add_deployment(dep)

        state = storage.get_environment_state("env-test")
        state.current_version = "v2.0.0"
        storage.update_environment_state(state)

        request = RollbackRequest(
            environment_id="env-test",
            target_version_id="v-001",
            triggered_by="test-user",
        )

        deployment = await service.trigger_rollback(request)

        assert deployment is not None
        assert deployment.version == "v1.0.0"


# ============================================================================
# Dashboard Summary Tests
# ============================================================================

class TestDashboardSummary:
    """Test dashboard summary functionality."""

    @pytest.mark.asyncio
    async def test_get_dashboard_summary(self, service, storage, sample_deployment, sample_version):
        """Test getting dashboard summary."""
        storage.add_deployment(sample_deployment)
        storage.add_version(sample_version)

        summary = await service.get_dashboard_summary()

        assert "environments" in summary
        assert "recent_deployments" in summary
        assert "available_versions" in summary
        assert "metrics_7_days" in summary
        assert "generated_at" in summary

        assert len(summary["environments"]) >= 4


# ============================================================================
# Storage Tests
# ============================================================================

class TestDeploymentStorage:
    """Test DeploymentStorage functionality."""

    def test_storage_initialization(self, storage):
        """Test storage initializes with default environments."""
        envs = storage.get_all_environments()
        assert len(envs) >= 4

    def test_storage_max_records_deployment(self):
        """Test storage enforces max records limit."""
        storage = DeploymentStorage(max_records=5)

        for i in range(10):
            dep = DeploymentRecord(
                deployment_id=f"dep-{i}",
                environment_id="env-1",
                environment_name="Test",
                version=f"v{i}.0.0",
                created_at=datetime.utcnow() + timedelta(seconds=i),
            )
            storage.add_deployment(dep)

        deployments = storage.get_all_deployments(limit=100)
        assert len(deployments) == 5

    def test_get_latest_deployment_for_environment(self, storage):
        """Test getting deployments for specific environment."""
        dep1 = DeploymentRecord(
            deployment_id="dep-1",
            environment_id="env-a",
            environment_name="A",
            version="v1.0.0",
        )
        dep2 = DeploymentRecord(
            deployment_id="dep-2",
            environment_id="env-b",
            environment_name="B",
            version="v2.0.0",
        )
        storage.add_deployment(dep1)
        storage.add_deployment(dep2)

        a_deployments = storage.get_deployments_for_environment("env-a")
        assert len(a_deployments) == 1
        assert a_deployments[0].environment_id == "env-a"


# ============================================================================
# Singleton Tests
# ============================================================================

class TestSingleton:
    """Test singleton functionality."""

    def test_get_singleton_service(self):
        """Test getting singleton service instance."""
        service = get_deployment_management_service()
        assert service is not None
        assert isinstance(service, DeploymentManagementService)

    def test_singleton_is_same_instance(self):
        """Test singleton returns same instance."""
        service1 = get_deployment_management_service()
        service2 = get_deployment_management_service()
        assert service1 is service2


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_close_session(self, service):
        """Test closing HTTP session."""
        await service.close()
        # Should not raise

    @pytest.mark.asyncio
    async def test_notify_callback_error_handled(self, service, storage, sample_version):
        """Test notification callback errors are handled."""
        storage.add_version(sample_version)

        def bad_callback(notification):
            raise Exception("Callback error")

        service.notification_callback = bad_callback

        request = DeploymentRequest(
            environment_id="env-beta",
            version_id="v-001",
            triggered_by="test-user",
        )

        # Should not raise despite callback error
        deployment = await service.trigger_deployment(request)
        assert deployment is not None

    def test_get_deployment_metrics_zero_days(self, service):
        """Test metrics with zero days."""
        metrics = service.get_deployment_metrics(days=0)
        assert metrics["deployments_per_day"] == 0

    @pytest.mark.asyncio
    async def test_check_health_env_not_found(self, service):
        """Test health check for non-existent environment."""
        with pytest.raises(ValueError) as exc_info:
            await service.check_environment_health("env-nonexistent")
        assert "not found" in str(exc_info.value)
