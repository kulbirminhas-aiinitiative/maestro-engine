#!/usr/bin/env python3
"""
Unit Tests for Post-Deployment Verification & Rollback Service
Epic: MD-1873 [Deploy] Post-Deployment Verification & Rollback

Test coverage for:
- MD-1860: Post-Deploy Smoke Checks
- MD-1862: Automatic Rollback Trigger
- MD-1863: Evidence Recording
- MD-1864: ACC Gate Status Updates
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.post_deployment_verification_service import (
    ACCGateConfig,
    ACCGateStatus,
    PostDeploymentVerificationService,
    RollbackReason,
    SmokeCheckConfig,
    SmokeCheckResult,
    SmokeCheckStatus,
    SmokeCheckType,
    VerificationEvidence,
    VerificationRun,
    VerificationStatus,
    VerificationStorage,
    get_post_deployment_verification_service,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def verification_service():
    """Create a fresh verification service for each test."""
    storage = VerificationStorage()
    return PostDeploymentVerificationService(storage=storage)


@pytest.fixture
def verification_service_with_mocks():
    """Create verification service with mocked dependencies."""
    storage = VerificationStorage()
    deployment_service = MagicMock()
    health_monitor = MagicMock()
    event_callback = AsyncMock()

    acc_config = ACCGateConfig(
        gate_name="test-gate",
        gate_id="gate-123",
        quality_fabric_url="http://localhost:8000",
    )

    return PostDeploymentVerificationService(
        storage=storage,
        deployment_service=deployment_service,
        health_monitor=health_monitor,
        event_callback=event_callback,
        acc_gate_config=acc_config,
    )


@pytest.fixture
def sample_smoke_check_config():
    """Sample smoke check configuration."""
    return SmokeCheckConfig(
        name="test_health",
        check_type=SmokeCheckType.HEALTH,
        endpoint="/health",
        expected_status=200,
        timeout_seconds=5.0,
        retry_count=2,
        retry_delay_seconds=1.0,
        required=True,
        description="Test health check",
    )


@pytest.fixture
def sample_verification_run():
    """Sample verification run."""
    return VerificationRun(
        verification_id="ver-123",
        deployment_id="dep-456",
        environment_id="env-789",
        environment_name="staging",
        version="1.0.0",
        status=VerificationStatus.IN_PROGRESS,
        triggered_by="test_user",
    )


# ============================================================================
# MD-1860: POST-DEPLOY SMOKE CHECKS TESTS
# ============================================================================


class TestSmokeCheckConfig:
    """Tests for SmokeCheckConfig dataclass."""

    def test_smoke_check_config_defaults(self):
        """Test smoke check config has correct defaults."""
        config = SmokeCheckConfig(
            name="test",
            check_type=SmokeCheckType.HEALTH,
        )

        assert config.method == "GET"
        assert config.expected_status == 200
        assert config.timeout_seconds == 10.0
        assert config.retry_count == 3
        assert config.required is True

    def test_smoke_check_config_to_dict(self, sample_smoke_check_config):
        """Test smoke check config serialization."""
        d = sample_smoke_check_config.to_dict()

        assert d["name"] == "test_health"
        assert d["check_type"] == "health"
        assert d["endpoint"] == "/health"
        assert d["expected_status"] == 200
        assert d["required"] is True


class TestSmokeCheckTypes:
    """Tests for smoke check type enum."""

    def test_all_smoke_check_types_defined(self):
        """Test all expected smoke check types exist."""
        types = list(SmokeCheckType)
        assert SmokeCheckType.HEALTH in types
        assert SmokeCheckType.API in types
        assert SmokeCheckType.DATABASE in types
        assert SmokeCheckType.CACHE in types
        assert SmokeCheckType.EXTERNAL in types
        assert SmokeCheckType.CUSTOM in types

    def test_smoke_check_type_values(self):
        """Test smoke check type string values."""
        assert SmokeCheckType.HEALTH.value == "health"
        assert SmokeCheckType.API.value == "api"
        assert SmokeCheckType.DATABASE.value == "database"


class TestSmokeCheckResult:
    """Tests for SmokeCheckResult dataclass."""

    def test_smoke_check_result_to_dict(self, sample_smoke_check_config):
        """Test smoke check result serialization."""
        result = SmokeCheckResult(
            check_id="check-123",
            config=sample_smoke_check_config,
            status=SmokeCheckStatus.PASSED,
            response_time_ms=150,
            actual_status_code=200,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )

        d = result.to_dict()
        assert d["check_id"] == "check-123"
        assert d["status"] == "passed"
        assert d["response_time_ms"] == 150
        assert d["required"] is True


class TestRunSmokeCheck:
    """Tests for running individual smoke checks."""

    @pytest.mark.asyncio
    async def test_smoke_check_skipped_no_endpoint(self, verification_service):
        """Test smoke check skipped when no endpoint configured."""
        config = SmokeCheckConfig(
            name="no_endpoint",
            check_type=SmokeCheckType.HEALTH,
            endpoint=None,
        )

        result = await verification_service.run_smoke_check(
            base_url="http://localhost:8000",
            config=config,
        )

        assert result.status == SmokeCheckStatus.SKIPPED
        assert "No endpoint" in result.error_message

    @pytest.mark.asyncio
    async def test_smoke_check_success(self, verification_service):
        """Test successful smoke check."""
        config = SmokeCheckConfig(
            name="health_check",
            check_type=SmokeCheckType.HEALTH,
            endpoint="/health",
            expected_status=200,
            timeout_seconds=5.0,
            retry_count=1,
        )

        with patch.object(verification_service, '_get_session') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value='{"status": "ok"}')
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            session = AsyncMock()
            session.request = MagicMock(return_value=mock_response)
            mock_session.return_value = session

            result = await verification_service.run_smoke_check(
                base_url="http://localhost:8000",
                config=config,
            )

            assert result.status == SmokeCheckStatus.PASSED
            assert result.actual_status_code == 200

    @pytest.mark.asyncio
    async def test_smoke_check_failure_wrong_status(self, verification_service):
        """Test smoke check failure on wrong status code."""
        config = SmokeCheckConfig(
            name="failing_check",
            check_type=SmokeCheckType.API,
            endpoint="/api/test",
            expected_status=200,
            timeout_seconds=2.0,
            retry_count=0,  # No retries for faster test
        )

        with patch.object(verification_service, '_get_session') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value='Internal Server Error')
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            session = AsyncMock()
            session.request = MagicMock(return_value=mock_response)
            mock_session.return_value = session

            result = await verification_service.run_smoke_check(
                base_url="http://localhost:8000",
                config=config,
            )

            assert result.status == SmokeCheckStatus.FAILED
            assert result.actual_status_code == 500


class TestRunMultipleSmokeChecks:
    """Tests for running multiple smoke checks."""

    @pytest.mark.asyncio
    async def test_run_smoke_checks_uses_defaults(self, verification_service):
        """Test run_smoke_checks uses default checks when none provided."""
        # Mock the run_smoke_check method
        with patch.object(
            verification_service,
            'run_smoke_check',
            new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = SmokeCheckResult(
                check_id="test",
                config=SmokeCheckConfig(name="test", check_type=SmokeCheckType.HEALTH),
                status=SmokeCheckStatus.PASSED,
            )

            results = await verification_service.run_smoke_checks(
                base_url="http://localhost:8000",
            )

            # Should have called run_smoke_check for each default check
            assert mock_check.call_count == len(verification_service._default_smoke_checks)


class TestCustomValidationFunctions:
    """Tests for custom validation function support."""

    def test_register_validation_function(self, verification_service):
        """Test registering a custom validation function."""
        def my_validator(data):
            return data.get("status_code") == 200

        verification_service.register_validation_function("my_validator", my_validator)

        assert "my_validator" in verification_service._validation_functions


# ============================================================================
# MD-1862: AUTOMATIC ROLLBACK TRIGGER TESTS
# ============================================================================


class TestAutomaticRollback:
    """Tests for automatic rollback trigger functionality."""

    def test_rollback_reason_enum(self):
        """Test rollback reason enum values."""
        assert RollbackReason.HEALTH_CHECK_FAILED.value == "health_check_failed"
        assert RollbackReason.SMOKE_CHECK_FAILED.value == "smoke_check_failed"
        assert RollbackReason.TIMEOUT.value == "timeout"
        assert RollbackReason.MANUAL.value == "manual"
        assert RollbackReason.ACC_GATE_CLOSED.value == "acc_gate_closed"

    @pytest.mark.asyncio
    async def test_trigger_rollback_no_deployment_service(self, verification_service, sample_verification_run):
        """Test rollback returns None when deployment service not configured."""
        result = await verification_service.trigger_automatic_rollback(
            verification=sample_verification_run,
            reason=RollbackReason.HEALTH_CHECK_FAILED,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_trigger_rollback_success(self, verification_service_with_mocks, sample_verification_run):
        """Test successful rollback trigger."""
        service = verification_service_with_mocks

        # Mock deployment history
        mock_deployment = MagicMock()
        mock_deployment.status.value = "success"
        mock_deployment.id = "prev-dep-123"

        service.deployment_service.get_deployment_history = AsyncMock(
            return_value=[mock_deployment]
        )

        # Mock rollback
        mock_rollback = MagicMock()
        mock_rollback.id = "rollback-dep-456"
        service.deployment_service.rollback_deployment = AsyncMock(
            return_value=mock_rollback
        )

        result = await service.trigger_automatic_rollback(
            verification=sample_verification_run,
            reason=RollbackReason.SMOKE_CHECK_FAILED,
        )

        assert result == "rollback-dep-456"
        assert sample_verification_run.rollback_triggered is True
        assert sample_verification_run.rollback_reason == RollbackReason.SMOKE_CHECK_FAILED

    @pytest.mark.asyncio
    async def test_trigger_rollback_with_specific_deployment(self, verification_service_with_mocks, sample_verification_run):
        """Test rollback to specific deployment."""
        service = verification_service_with_mocks

        mock_rollback = MagicMock()
        mock_rollback.id = "rollback-789"
        service.deployment_service.rollback_deployment = AsyncMock(
            return_value=mock_rollback
        )

        result = await service.trigger_automatic_rollback(
            verification=sample_verification_run,
            reason=RollbackReason.MANUAL,
            previous_deployment_id="specific-dep-id",
        )

        assert result == "rollback-789"
        service.deployment_service.rollback_deployment.assert_called_once_with(
            deployment_id="specific-dep-id",
            triggered_by="post_deployment_verification_service",
        )


# ============================================================================
# MD-1863: EVIDENCE RECORDING TESTS
# ============================================================================


class TestEvidenceRecording:
    """Tests for evidence recording functionality."""

    def test_verification_evidence_dataclass(self):
        """Test VerificationEvidence dataclass."""
        evidence = VerificationEvidence(
            evidence_id="ev-123",
            verification_id="ver-456",
            deployment_id="dep-789",
            environment="staging",
            evidence_type="smoke_check",
            timestamp=datetime.utcnow(),
            status="passed",
            details={"check_name": "health"},
        )

        d = evidence.to_dict()
        assert d["evidence_id"] == "ev-123"
        assert d["verification_id"] == "ver-456"
        assert d["evidence_type"] == "smoke_check"
        assert d["status"] == "passed"

    @pytest.mark.asyncio
    async def test_record_evidence(self, verification_service):
        """Test recording evidence."""
        evidence = await verification_service.record_evidence(
            verification_id="ver-123",
            deployment_id="dep-456",
            environment="staging",
            evidence_type="health_check",
            status="passed",
            details={"response_time_ms": 150},
            metadata={"source": "test"},
        )

        assert evidence.evidence_id is not None
        assert evidence.verification_id == "ver-123"
        assert evidence.evidence_type == "health_check"
        assert evidence.status == "passed"

    @pytest.mark.asyncio
    async def test_get_evidence_for_verification(self, verification_service):
        """Test retrieving evidence for a verification."""
        # Record multiple evidence entries
        await verification_service.record_evidence(
            verification_id="ver-123",
            deployment_id="dep-456",
            environment="staging",
            evidence_type="health_check",
            status="passed",
            details={},
        )
        await verification_service.record_evidence(
            verification_id="ver-123",
            deployment_id="dep-456",
            environment="staging",
            evidence_type="smoke_check",
            status="passed",
            details={},
        )

        evidence_list = verification_service.get_evidence("ver-123")

        assert len(evidence_list) == 2
        assert evidence_list[0].evidence_type == "health_check"
        assert evidence_list[1].evidence_type == "smoke_check"


# ============================================================================
# MD-1864: ACC GATE STATUS UPDATES TESTS
# ============================================================================


class TestACCGateStatus:
    """Tests for ACC gate status updates."""

    def test_acc_gate_status_enum(self):
        """Test ACC gate status enum values."""
        assert ACCGateStatus.OPEN.value == "open"
        assert ACCGateStatus.CLOSED.value == "closed"
        assert ACCGateStatus.PENDING.value == "pending"

    def test_acc_gate_config_dataclass(self):
        """Test ACCGateConfig dataclass."""
        config = ACCGateConfig(
            gate_name="deploy-gate",
            gate_id="gate-123",
            quality_fabric_url="http://localhost:8000",
            required_checks=["health", "api"],
            auto_close_on_failure=True,
        )

        d = config.to_dict()
        assert d["gate_name"] == "deploy-gate"
        assert d["gate_id"] == "gate-123"
        assert len(d["required_checks"]) == 2

    @pytest.mark.asyncio
    async def test_update_acc_gate_no_config(self, verification_service, sample_verification_run):
        """Test ACC gate update returns False when not configured."""
        result = await verification_service.update_acc_gate_status(
            verification=sample_verification_run,
            status=ACCGateStatus.OPEN,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_acc_gate_success(self, verification_service_with_mocks, sample_verification_run):
        """Test successful ACC gate status update."""
        service = verification_service_with_mocks

        with patch.object(service, '_get_session') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            session = AsyncMock()
            session.post = MagicMock(return_value=mock_response)
            mock_session.return_value = session

            result = await service.update_acc_gate_status(
                verification=sample_verification_run,
                status=ACCGateStatus.OPEN,
                details={"passed_checks": ["health"]},
            )

            assert result is True
            assert sample_verification_run.acc_gate_status == ACCGateStatus.OPEN


# ============================================================================
# VERIFICATION RUN TESTS
# ============================================================================


class TestVerificationRun:
    """Tests for VerificationRun dataclass."""

    def test_verification_run_to_dict(self, sample_verification_run):
        """Test verification run serialization."""
        d = sample_verification_run.to_dict()

        assert d["verification_id"] == "ver-123"
        assert d["deployment_id"] == "dep-456"
        assert d["environment_name"] == "staging"
        assert d["version"] == "1.0.0"
        assert d["status"] == "in_progress"

    def test_verification_run_duration(self, sample_verification_run):
        """Test verification run duration calculation."""
        sample_verification_run.started_at = datetime.utcnow()

        duration = sample_verification_run.get_duration_seconds()
        assert duration is not None
        assert duration >= 0

    def test_verification_status_enum(self):
        """Test verification status enum values."""
        assert VerificationStatus.PENDING.value == "pending"
        assert VerificationStatus.IN_PROGRESS.value == "in_progress"
        assert VerificationStatus.PASSED.value == "passed"
        assert VerificationStatus.FAILED.value == "failed"
        assert VerificationStatus.ROLLED_BACK.value == "rolled_back"


# ============================================================================
# VERIFICATION STORAGE TESTS
# ============================================================================


class TestVerificationStorage:
    """Tests for VerificationStorage."""

    def test_add_and_get_verification(self):
        """Test adding and retrieving verification."""
        storage = VerificationStorage()

        run = VerificationRun(
            verification_id="ver-123",
            deployment_id="dep-456",
            environment_id="env-789",
            environment_name="staging",
            version="1.0.0",
            status=VerificationStatus.PASSED,
            triggered_by="test",
        )

        storage.add_verification(run)
        retrieved = storage.get_verification("ver-123")

        assert retrieved is not None
        assert retrieved.verification_id == "ver-123"

    def test_get_verifications_for_deployment(self):
        """Test getting verifications for a deployment."""
        storage = VerificationStorage()

        for i in range(3):
            run = VerificationRun(
                verification_id=f"ver-{i}",
                deployment_id="dep-456",
                environment_id="env-789",
                environment_name="staging",
                version="1.0.0",
                status=VerificationStatus.PASSED,
                triggered_by="test",
            )
            storage.add_verification(run)

        verifications = storage.get_verifications_for_deployment("dep-456")
        assert len(verifications) == 3

    def test_get_latest_verification(self):
        """Test getting latest verification for environment."""
        storage = VerificationStorage()

        for i in range(3):
            run = VerificationRun(
                verification_id=f"ver-{i}",
                deployment_id=f"dep-{i}",
                environment_id="env-789",
                environment_name="staging",
                version=f"1.0.{i}",
                status=VerificationStatus.PASSED,
                triggered_by="test",
            )
            storage.add_verification(run)

        latest = storage.get_latest_verification("env-789")
        assert latest is not None
        assert latest.version == "1.0.2"

    def test_storage_max_records_limit(self):
        """Test storage respects max records limit."""
        storage = VerificationStorage(max_records=5)

        for i in range(10):
            run = VerificationRun(
                verification_id=f"ver-{i}",
                deployment_id="dep-456",
                environment_id="env-789",
                environment_name="staging",
                version="1.0.0",
                status=VerificationStatus.PASSED,
                triggered_by="test",
            )
            storage.add_verification(run)

        assert len(storage.verifications) == 5


# ============================================================================
# HEALTH ENDPOINT VERIFICATION TESTS
# ============================================================================


class TestHealthEndpointVerification:
    """Tests for health endpoint verification."""

    @pytest.mark.asyncio
    async def test_verify_health_endpoint_success(self, verification_service):
        """Test successful health endpoint verification."""
        with patch.object(verification_service, '_get_session') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"status": "healthy"})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            session = AsyncMock()
            session.get = MagicMock(return_value=mock_response)
            mock_session.return_value = session

            is_healthy, details = await verification_service.verify_health_endpoint(
                health_url="http://localhost:8000/health",
                timeout_seconds=5.0,
                retry_count=1,
            )

            assert is_healthy is True
            assert details["status_code"] == 200

    @pytest.mark.asyncio
    async def test_verify_health_endpoint_failure(self, verification_service):
        """Test failed health endpoint verification."""
        with patch.object(verification_service, '_get_session') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.json = AsyncMock(return_value={"error": "internal"})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            session = AsyncMock()
            session.get = MagicMock(return_value=mock_response)
            mock_session.return_value = session

            is_healthy, details = await verification_service.verify_health_endpoint(
                health_url="http://localhost:8000/health",
                timeout_seconds=2.0,
                retry_count=0,
            )

            assert is_healthy is False
            assert "Unhealthy status" in details.get("error", "")


# ============================================================================
# FULL VERIFICATION FLOW TESTS
# ============================================================================


class TestFullVerificationFlow:
    """Tests for the complete verification flow."""

    @pytest.mark.asyncio
    async def test_verify_deployment_all_pass(self, verification_service):
        """Test full verification flow when all checks pass."""
        with patch.object(verification_service, 'verify_health_endpoint') as mock_health:
            with patch.object(verification_service, 'run_smoke_checks') as mock_smoke:
                mock_health.return_value = (True, {"status_code": 200})
                mock_smoke.return_value = [
                    SmokeCheckResult(
                        check_id="check-1",
                        config=SmokeCheckConfig(name="health", check_type=SmokeCheckType.HEALTH, required=True),
                        status=SmokeCheckStatus.PASSED,
                    )
                ]

                result = await verification_service.verify_deployment(
                    deployment_id="dep-123",
                    environment_id="env-456",
                    environment_name="staging",
                    version="1.0.0",
                    base_url="http://localhost:8000",
                    health_url="http://localhost:8000/health",
                    triggered_by="test",
                    auto_rollback=False,
                )

                assert result.status == VerificationStatus.PASSED
                assert result.health_check_passed is True

    @pytest.mark.asyncio
    async def test_verify_deployment_health_fails(self, verification_service):
        """Test verification flow when health check fails."""
        with patch.object(verification_service, 'verify_health_endpoint') as mock_health:
            mock_health.return_value = (False, {"error": "timeout"})

            result = await verification_service.verify_deployment(
                deployment_id="dep-123",
                environment_id="env-456",
                environment_name="staging",
                version="1.0.0",
                base_url="http://localhost:8000",
                health_url="http://localhost:8000/health",
                triggered_by="test",
                auto_rollback=False,
            )

            assert result.status == VerificationStatus.FAILED
            assert result.health_check_passed is False

    @pytest.mark.asyncio
    async def test_verify_deployment_smoke_fails_triggers_rollback(self, verification_service_with_mocks):
        """Test verification triggers rollback on smoke check failure."""
        service = verification_service_with_mocks

        with patch.object(service, 'verify_health_endpoint') as mock_health:
            with patch.object(service, 'run_smoke_checks') as mock_smoke:
                with patch.object(service, 'trigger_automatic_rollback') as mock_rollback:
                    mock_health.return_value = (True, {"status_code": 200})
                    mock_smoke.return_value = [
                        SmokeCheckResult(
                            check_id="check-1",
                            config=SmokeCheckConfig(name="api", check_type=SmokeCheckType.API, required=True),
                            status=SmokeCheckStatus.FAILED,
                            error_message="API returned 500",
                        )
                    ]
                    mock_rollback.return_value = "rollback-123"

                    result = await service.verify_deployment(
                        deployment_id="dep-123",
                        environment_id="env-456",
                        environment_name="staging",
                        version="1.0.0",
                        base_url="http://localhost:8000",
                        health_url="http://localhost:8000/health",
                        triggered_by="test",
                        auto_rollback=True,
                    )

                    assert result.status == VerificationStatus.FAILED
                    mock_rollback.assert_called_once()


# ============================================================================
# QUERY METHODS TESTS
# ============================================================================


class TestQueryMethods:
    """Tests for query methods."""

    def test_get_verification(self, verification_service, sample_verification_run):
        """Test getting verification by ID."""
        verification_service.storage.add_verification(sample_verification_run)

        result = verification_service.get_verification("ver-123")
        assert result is not None
        assert result.verification_id == "ver-123"

    def test_get_verification_not_found(self, verification_service):
        """Test getting non-existent verification."""
        result = verification_service.get_verification("nonexistent")
        assert result is None

    def test_get_verification_history(self, verification_service):
        """Test getting verification history."""
        for i in range(5):
            run = VerificationRun(
                verification_id=f"ver-{i}",
                deployment_id="dep-456",
                environment_id="env-789",
                environment_name="staging",
                version="1.0.0",
                status=VerificationStatus.PASSED if i % 2 == 0 else VerificationStatus.FAILED,
                triggered_by="test",
            )
            verification_service.storage.add_verification(run)

        all_history = verification_service.get_verification_history(limit=10)
        assert len(all_history) == 5

        passed_only = verification_service.get_verification_history(
            status=VerificationStatus.PASSED
        )
        assert len(passed_only) == 3

    def test_get_verification_summary(self, verification_service):
        """Test getting verification summary."""
        for i in range(3):
            run = VerificationRun(
                verification_id=f"ver-{i}",
                deployment_id="dep-456",
                environment_id="env-789",
                environment_name="staging",
                version="1.0.0",
                status=VerificationStatus.PASSED,
                triggered_by="test",
            )
            verification_service.storage.add_verification(run)

        summary = verification_service.get_verification_summary()

        assert summary["total"] == 3
        assert summary["passed"] == 3
        assert summary["failed"] == 0


# ============================================================================
# SINGLETON TESTS
# ============================================================================


class TestSingleton:
    """Tests for singleton service instance."""

    def test_get_singleton_service(self):
        """Test singleton service getter."""
        service1 = get_post_deployment_verification_service()
        service2 = get_post_deployment_verification_service()

        assert service1 is service2

    def test_singleton_is_correct_type(self):
        """Test singleton is correct type."""
        service = get_post_deployment_verification_service()
        assert isinstance(service, PostDeploymentVerificationService)


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_set_smoke_checks(self, verification_service):
        """Test setting custom smoke checks."""
        custom_checks = [
            SmokeCheckConfig(name="custom1", check_type=SmokeCheckType.CUSTOM),
            SmokeCheckConfig(name="custom2", check_type=SmokeCheckType.CUSTOM),
        ]

        verification_service.set_smoke_checks(custom_checks)
        assert len(verification_service._default_smoke_checks) == 2

    def test_add_smoke_check(self, verification_service):
        """Test adding a smoke check."""
        initial_count = len(verification_service._default_smoke_checks)

        verification_service.add_smoke_check(
            SmokeCheckConfig(name="new_check", check_type=SmokeCheckType.API)
        )

        assert len(verification_service._default_smoke_checks) == initial_count + 1

    @pytest.mark.asyncio
    async def test_close_session(self, verification_service):
        """Test closing HTTP session."""
        # Create a session
        verification_service._session = AsyncMock()
        verification_service._session.closed = False

        await verification_service.close()

        verification_service._session.close.assert_called_once()
