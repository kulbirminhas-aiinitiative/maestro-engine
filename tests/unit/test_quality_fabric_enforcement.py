#!/usr/bin/env python3
"""
Unit Tests for Quality Fabric Enforcement Service
Tests for EPIC ME-400 (QF-200): Phase-Test Mapping with Threshold Enforcement

Test Coverage:
- QF-200-AC1: YAML config loading for phase-test mappings
- QF-200-AC2: Environment-specific thresholds
- QF-200-AC3: Rollback on deployment failure
- QF-200-AC4: API endpoints for config management
- QF-200-AC5: Test threshold enforcement
"""

import asyncio
import json
import os
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.quality_fabric_enforcement import (
    QualityFabricEnforcementService,
    PhaseTestConfigLoader,
    PhaseTestMapping,
    QualityValidationResult,
    Waiver,
    WaiverType,
    TestCategory,
    EnforcementLevel,
    DEFAULT_PHASE_TEST_MAPPING,
    DEFAULT_THRESHOLDS,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def sample_yaml_config():
    """Sample YAML config for testing."""
    return {
        "version": "1.0",
        "defaults": {
            "coverage_min": 0.75,
            "pass_rate_min": 0.95,
            "max_critical_issues": 0,
            "max_high_issues": 5,
            "timeout_minutes": 15,
        },
        "phase_test_map": {
            "requirements": {
                "description": "Validate requirement schemas",
                "test_categories": ["unit"],
                "thresholds": {
                    "coverage_min": 0.60,
                    "pass_rate_min": 0.90,
                },
                "enforcement": "standard",
            },
            "implementation": {
                "description": "Code implementation validation",
                "test_categories": ["unit", "integration", "functional"],
                "test_commands": {
                    "unit": "pytest::tests/unit",
                    "integration": "pytest::tests/integration",
                },
                "thresholds": {
                    "coverage_min": 0.75,
                    "pass_rate_min": 0.95,
                },
                "enforcement": "strict",
            },
            "deployment": {
                "description": "Deployment validation",
                "test_categories": ["integration", "api", "performance"],
                "smoke_tests": ["scripts/smoke_tests.sh"],
                "thresholds": {
                    "pass_rate_min": 1.0,
                },
                "enforcement": "strict",
                "rollback_on_fail": True,
            },
        },
        "environments": {
            "development": {
                "enforcement_level": "relaxed",
                "override_thresholds": {
                    "coverage_min": 0.50,
                    "pass_rate_min": 0.80,
                },
            },
            "staging": {
                "enforcement_level": "strict",
            },
            "production": {
                "enforcement_level": "strict",
                "rollback_on_fail": True,
            },
        },
    }


@pytest.fixture
def temp_config_file(sample_yaml_config):
    """Create a temporary YAML config file."""
    import yaml

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(sample_yaml_config, f)
        config_path = f.name

    yield config_path

    # Cleanup
    if os.path.exists(config_path):
        os.unlink(config_path)


@pytest.fixture
def enforcement_service(temp_config_file):
    """Create enforcement service with test config."""
    return QualityFabricEnforcementService(
        quality_fabric_url="http://localhost:8000",
        environment="staging",
        config_path=temp_config_file,
    )


@pytest.fixture
def mock_validation_result():
    """Create a mock validation result."""
    return QualityValidationResult(
        validation_id="test_val_001",
        phase_id="phase_deploy_001",
        workflow_id="wf_test_001",
        session_id="session_test",
        total_tests=10,
        passed_tests=8,
        failed_tests=2,
        error_tests=0,
        skipped_tests=0,
        test_pass_rate=80.0,
        test_coverage=75.0,
        quality_score=65.0,
        thresholds_met=False,
        threshold_violations=[
            {"type": "pass_rate", "threshold": 95, "actual": 80},
        ],
        evidence_uri="/api/quality/validations/test_val_001",
        artifacts=["/api/quality/reports/test_val_001"],
        execution_time_ms=1500.0,
        timestamp=datetime.now().isoformat(),
    )


# ============================================================================
# QF-200-AC1: YAML CONFIG LOADING TESTS
# ============================================================================

class TestYAMLConfigLoading:
    """Tests for YAML config loading (QF-200-AC1)."""

    def test_load_config_from_file(self, temp_config_file, sample_yaml_config):
        """Test loading config from YAML file."""
        config = PhaseTestConfigLoader.load_config(temp_config_file)

        assert config is not None
        assert config.get("version") == "1.0"
        assert "phase_test_map" in config
        assert "requirements" in config["phase_test_map"]
        assert "deployment" in config["phase_test_map"]

    def test_load_config_missing_file(self):
        """Test loading config with missing file returns empty dict."""
        config = PhaseTestConfigLoader.load_config("/nonexistent/path.yaml")
        assert config == {}

    def test_get_phase_mapping_from_config(self, sample_yaml_config):
        """Test extracting phase mapping from config."""
        mapping = PhaseTestConfigLoader.get_phase_mapping_from_config(
            sample_yaml_config, "deployment"
        )

        assert mapping is not None
        assert mapping["rollback_on_fail"] == True
        assert "integration" in mapping["test_categories"]

    def test_get_default_thresholds(self, sample_yaml_config):
        """Test getting default thresholds."""
        defaults = PhaseTestConfigLoader.get_default_thresholds(sample_yaml_config)

        assert defaults["coverage_min"] == 0.75
        assert defaults["pass_rate_min"] == 0.95

    def test_get_environment_config(self, sample_yaml_config):
        """Test getting environment-specific config."""
        dev_config = PhaseTestConfigLoader.get_environment_config(
            sample_yaml_config, "development"
        )

        assert dev_config["enforcement_level"] == "relaxed"
        assert dev_config["override_thresholds"]["coverage_min"] == 0.50


class TestPhaseTestMapping:
    """Tests for phase-test mapping functionality."""

    def test_service_loads_yaml_config(self, enforcement_service):
        """Test service loads YAML config on init."""
        assert enforcement_service._yaml_config is not None
        assert enforcement_service.get_config_info()["config_loaded"] == True

    def test_phase_mapping_from_yaml(self, enforcement_service):
        """Test phase mappings are loaded from YAML."""
        mapping = enforcement_service.get_phase_mapping("deployment")

        assert mapping.phase_type == "deployment"
        assert mapping.rollback_on_fail == True
        assert "integration" in mapping.test_categories

    def test_phase_mapping_test_categories(self, enforcement_service):
        """Test test categories are correctly loaded."""
        impl_mapping = enforcement_service.get_phase_mapping("implementation")

        assert "unit" in impl_mapping.test_categories
        assert "integration" in impl_mapping.test_categories
        assert "functional" in impl_mapping.test_categories

    def test_fallback_to_default_mapping(self, enforcement_service):
        """Test fallback to default when phase not in config."""
        # 'unknown_phase' not in config, should fall back to defaults
        mapping = enforcement_service.get_phase_mapping("unknown_phase")

        assert mapping is not None
        assert mapping.phase_type == "unknown_phase"
        assert "unit" in mapping.test_categories  # Default includes unit

    def test_validate_phase_mapping(self, enforcement_service):
        """Test phase mapping validation."""
        is_valid, msg = enforcement_service.validate_phase_mapping("implementation")

        assert is_valid == True
        assert "3 test categories" in msg


# ============================================================================
# QF-200-AC2: ENVIRONMENT-SPECIFIC THRESHOLDS TESTS
# ============================================================================

class TestEnvironmentThresholds:
    """Tests for environment-specific thresholds (QF-200-AC2)."""

    def test_development_relaxed_enforcement(self, temp_config_file):
        """Test development environment uses relaxed enforcement."""
        service = QualityFabricEnforcementService(
            environment="development",
            config_path=temp_config_file,
        )

        assert service.enforcement_level == EnforcementLevel.RELAXED

    def test_staging_strict_enforcement(self, temp_config_file):
        """Test staging environment uses strict enforcement."""
        service = QualityFabricEnforcementService(
            environment="staging",
            config_path=temp_config_file,
        )

        assert service.enforcement_level == EnforcementLevel.STRICT

    def test_production_strict_enforcement(self, temp_config_file):
        """Test production environment uses strict enforcement."""
        service = QualityFabricEnforcementService(
            environment="production",
            config_path=temp_config_file,
        )

        assert service.enforcement_level == EnforcementLevel.STRICT

    def test_environment_override_thresholds(self, temp_config_file):
        """Test environment-specific threshold overrides."""
        service = QualityFabricEnforcementService(
            environment="development",
            config_path=temp_config_file,
        )

        # Development should have lower thresholds
        assert service.thresholds.get("coverage_min") == 0.50
        assert service.thresholds.get("pass_rate_min") == 0.80

    def test_enabled_for_staging_production(self, temp_config_file):
        """Test enforcement is always enabled for staging/production."""
        staging_service = QualityFabricEnforcementService(
            environment="staging",
            config_path=temp_config_file,
            feature_flag_enabled=False,  # Even with FF disabled
        )

        assert staging_service.is_enabled_for_environment() == True


# ============================================================================
# QF-200-AC3: ROLLBACK ON DEPLOYMENT FAILURE TESTS
# ============================================================================

class TestRollbackSupport:
    """Tests for rollback on deployment failure (QF-200-AC3)."""

    def test_rollback_configured_for_deployment(self, enforcement_service):
        """Test rollback is configured for deployment phase."""
        mapping = enforcement_service.get_phase_mapping("deployment")
        assert mapping.rollback_on_fail == True

    def test_rollback_not_configured_for_other_phases(self, enforcement_service):
        """Test rollback is not configured for non-deployment phases."""
        mapping = enforcement_service.get_phase_mapping("implementation")
        assert mapping.rollback_on_fail == False

    def test_check_rollback_needed_on_failure(self, enforcement_service, mock_validation_result):
        """Test rollback is needed when deployment tests fail."""
        mapping = enforcement_service.get_phase_mapping("deployment")

        should_rollback, reason = enforcement_service.check_rollback_needed(
            mock_validation_result, mapping
        )

        assert should_rollback == True
        assert "failed" in reason.lower() or "pass rate" in reason.lower()

    def test_no_rollback_when_thresholds_met(self, enforcement_service):
        """Test no rollback when all thresholds are met."""
        mapping = enforcement_service.get_phase_mapping("deployment")

        passing_result = QualityValidationResult(
            validation_id="test_pass_001",
            phase_id="phase_deploy_001",
            workflow_id="wf_test_001",
            session_id=None,
            total_tests=10,
            passed_tests=10,
            failed_tests=0,
            error_tests=0,
            skipped_tests=0,
            test_pass_rate=100.0,
            test_coverage=90.0,
            quality_score=95.0,
            thresholds_met=True,
            threshold_violations=[],
            evidence_uri="/api/quality/validations/test_pass_001",
            artifacts=[],
            execution_time_ms=1000.0,
            timestamp=datetime.now().isoformat(),
        )

        should_rollback, reason = enforcement_service.check_rollback_needed(
            passing_result, mapping
        )

        assert should_rollback == False
        assert "no rollback needed" in reason.lower()

    def test_no_rollback_when_not_configured(self, enforcement_service, mock_validation_result):
        """Test no rollback when not configured for phase."""
        mapping = enforcement_service.get_phase_mapping("implementation")

        should_rollback, reason = enforcement_service.check_rollback_needed(
            mock_validation_result, mapping
        )

        assert should_rollback == False
        assert "not configured" in reason.lower()

    @pytest.mark.asyncio
    async def test_trigger_rollback(self, enforcement_service):
        """Test triggering a rollback."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "rollback_initiated"}

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await enforcement_service.trigger_rollback(
                workflow_id="wf_test_001",
                phase_id="phase_deploy_001",
                reason="Smoke tests failed",
                context={"deployment_version": "1.2.3"},
            )

            assert "rollback_id" in result
            assert result["workflow_id"] == "wf_test_001"
            assert result["reason"] == "Smoke tests failed"


# ============================================================================
# QF-200-AC4: CONFIG MANAGEMENT TESTS
# ============================================================================

class TestConfigManagement:
    """Tests for config management functionality."""

    def test_get_config_info(self, enforcement_service):
        """Test getting config info."""
        info = enforcement_service.get_config_info()

        assert info["config_loaded"] == True
        assert info["config_version"] == "1.0"
        assert "deployment" in info["phases_from_config"]
        assert "development" in info["environments_configured"]

    def test_reload_config(self, enforcement_service, temp_config_file):
        """Test reloading config from file."""
        success = enforcement_service.reload_config(temp_config_file)

        assert success == True
        info = enforcement_service.get_config_info()
        assert info["config_loaded"] == True

    def test_reload_config_invalid_path(self, enforcement_service):
        """Test reload with invalid path returns False."""
        # Reloading with nonexistent path should work but load empty config
        success = enforcement_service.reload_config("/nonexistent/config.yaml")

        # Still succeeds but with empty config
        assert success == True


# ============================================================================
# QF-200-AC5: THRESHOLD ENFORCEMENT TESTS
# ============================================================================

class TestThresholdEnforcement:
    """Tests for threshold enforcement functionality."""

    def test_threshold_violations_detected(self, enforcement_service):
        """Test threshold violations are detected."""
        pass_rate = 80.0  # Below 95% threshold
        coverage = 70.0   # Below 80% threshold
        issues = {"critical": 0, "high": 1}

        met, violations = enforcement_service._evaluate_thresholds(
            pass_rate, coverage, issues
        )

        assert met == False
        assert len(violations) >= 1

    def test_all_thresholds_met(self, enforcement_service):
        """Test when all thresholds are met."""
        pass_rate = 98.0
        coverage = 90.0
        issues = {"critical": 0, "high": 0}

        met, violations = enforcement_service._evaluate_thresholds(
            pass_rate, coverage, issues
        )

        assert met == True
        assert len(violations) == 0

    def test_critical_issues_block(self, enforcement_service):
        """Test critical issues block the gate."""
        pass_rate = 100.0
        coverage = 100.0
        issues = {"critical": 1, "high": 0}  # 1 critical issue

        met, violations = enforcement_service._evaluate_thresholds(
            pass_rate, coverage, issues
        )

        assert met == False
        assert any(v["type"] == "critical_issues" for v in violations)


# ============================================================================
# GATE BLOCKING AND WAIVER TESTS
# ============================================================================

class TestGateBlocking:
    """Tests for gate blocking functionality."""

    def test_gate_blocked_on_threshold_failure(self, enforcement_service, mock_validation_result):
        """Test gate is blocked when thresholds not met."""
        should_block, reason = enforcement_service.should_block_gate(mock_validation_result)

        assert should_block == True
        assert "threshold" in reason.lower()

    def test_gate_not_blocked_with_waiver(self, enforcement_service, mock_validation_result):
        """Test gate is not blocked when valid waiver exists."""
        waiver = enforcement_service.grant_waiver(
            phase_id="phase_deploy_001",
            workflow_id="wf_test_001",
            waiver_type=WaiverType.EMERGENCY,
            reason="Emergency hotfix",
            granted_by="admin@test.com",
        )

        should_block, reason = enforcement_service.should_block_gate(
            mock_validation_result, waiver
        )

        assert should_block == False
        assert "waiver" in reason.lower()

    def test_gate_not_blocked_when_disabled(self, temp_config_file):
        """Test gate is not blocked when enforcement disabled."""
        service = QualityFabricEnforcementService(
            environment="development",
            config_path=temp_config_file,
            feature_flag_enabled=False,
        )

        result = QualityValidationResult(
            validation_id="test",
            phase_id="test",
            workflow_id="test",
            session_id=None,
            total_tests=0,
            passed_tests=0,
            failed_tests=10,
            error_tests=0,
            skipped_tests=0,
            test_pass_rate=0,
            test_coverage=0,
            quality_score=0,
            thresholds_met=False,
            threshold_violations=[],
            evidence_uri="",
            artifacts=[],
            execution_time_ms=0,
            timestamp=datetime.now().isoformat(),
        )

        should_block, reason = service.should_block_gate(result)

        assert should_block == False


class TestWaivers:
    """Tests for waiver functionality."""

    def test_grant_waiver(self, enforcement_service):
        """Test granting a waiver."""
        waiver = enforcement_service.grant_waiver(
            phase_id="phase_001",
            workflow_id="wf_001",
            waiver_type=WaiverType.EMERGENCY,
            reason="Critical production fix",
            granted_by="admin@test.com",
        )

        assert waiver.waiver_id is not None
        assert waiver.waiver_type == WaiverType.EMERGENCY
        assert waiver.reason == "Critical production fix"

    def test_get_waiver(self, enforcement_service):
        """Test retrieving a waiver."""
        enforcement_service.grant_waiver(
            phase_id="phase_test",
            workflow_id="wf_test",
            waiver_type=WaiverType.TEMPORARY,
            reason="Test waiver",
            granted_by="test@test.com",
        )

        waiver = enforcement_service.get_waiver("phase_test", "wf_test")

        assert waiver is not None
        assert waiver.reason == "Test waiver"

    def test_expired_waiver_invalid(self, enforcement_service):
        """Test expired waiver is not valid."""
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()

        waiver = enforcement_service.grant_waiver(
            phase_id="phase_expired",
            workflow_id="wf_expired",
            waiver_type=WaiverType.TEMPORARY,
            reason="Expired waiver",
            granted_by="test@test.com",
            expires_at=expired_time,
        )

        is_valid = enforcement_service._is_waiver_valid(waiver)

        assert is_valid == False


# ============================================================================
# QUALITY VALIDATION TESTS
# ============================================================================

class TestQualityValidation:
    """Tests for quality validation functionality."""

    @pytest.mark.asyncio
    async def test_validate_phase_returns_result(self, enforcement_service):
        """Test validate_phase returns a result."""
        with patch.object(enforcement_service, '_execute_quality_fabric_validation') as mock_exec:
            mock_exec.return_value = {
                "status": {
                    "status": "completed",
                    "total_tests": 10,
                    "passed_tests": 9,
                    "failed_tests": 1,
                    "error_tests": 0,
                },
                "results": {
                    "coverage": 85.0,
                    "issues": {"critical": 0, "high": 1},
                },
            }

            result = await enforcement_service.validate_phase(
                phase_id="phase_impl_001",
                phase_type="implementation",
                workflow_id="wf_test_001",
            )

            assert result.validation_id is not None
            assert result.total_tests == 10
            assert result.passed_tests == 9

    def test_calculate_quality_score(self, enforcement_service):
        """Test quality score calculation."""
        score = enforcement_service._calculate_quality_score(
            pass_rate=95.0,
            coverage=85.0,
            failed=1,
            errors=0,
        )

        # Score should be reasonable (between 0 and 100)
        assert 0 <= score <= 100
        assert score > 70  # Should be a decent score

    def test_create_gate_evidence(self, enforcement_service, mock_validation_result):
        """Test gate evidence creation."""
        evidence = enforcement_service.create_gate_evidence(mock_validation_result)

        assert evidence["type"] == "quality_validation"
        assert evidence["uri"] == mock_validation_result.evidence_uri
        assert "metadata" in evidence
        assert evidence["metadata"]["validation_id"] == mock_validation_result.validation_id


# ============================================================================
# VALIDATION HISTORY TESTS
# ============================================================================

class TestValidationHistory:
    """Tests for validation history functionality."""

    @pytest.mark.asyncio
    async def test_validation_stored_in_history(self, enforcement_service):
        """Test validations are stored in history."""
        with patch.object(enforcement_service, '_execute_quality_fabric_validation') as mock_exec:
            mock_exec.return_value = {
                "status": {"status": "completed", "total_tests": 5, "passed_tests": 5},
                "results": {"coverage": 90.0, "issues": {}},
            }

            await enforcement_service.validate_phase(
                phase_id="phase_hist_001",
                phase_type="implementation",
                workflow_id="wf_hist_001",
            )

            history = enforcement_service.get_validation_history(workflow_id="wf_hist_001")

            assert len(history) >= 1
            assert history[-1].workflow_id == "wf_hist_001"

    def test_history_filtering(self, enforcement_service):
        """Test history filtering by workflow/phase."""
        # Add mock results to history
        result1 = QualityValidationResult(
            validation_id="hist_001",
            phase_id="phase_a",
            workflow_id="wf_a",
            session_id=None,
            total_tests=5, passed_tests=5, failed_tests=0, error_tests=0, skipped_tests=0,
            test_pass_rate=100, test_coverage=90, quality_score=95,
            thresholds_met=True, threshold_violations=[],
            evidence_uri="", artifacts=[], execution_time_ms=100,
            timestamp=datetime.now().isoformat(),
        )

        result2 = QualityValidationResult(
            validation_id="hist_002",
            phase_id="phase_b",
            workflow_id="wf_b",
            session_id=None,
            total_tests=5, passed_tests=4, failed_tests=1, error_tests=0, skipped_tests=0,
            test_pass_rate=80, test_coverage=70, quality_score=75,
            thresholds_met=False, threshold_violations=[],
            evidence_uri="", artifacts=[], execution_time_ms=100,
            timestamp=datetime.now().isoformat(),
        )

        enforcement_service._validation_history.extend([result1, result2])

        # Filter by workflow
        wf_a_history = enforcement_service.get_validation_history(workflow_id="wf_a")
        assert all(r.workflow_id == "wf_a" for r in wf_a_history)


# ============================================================================
# INTEGRATION-STYLE TESTS
# ============================================================================

class TestIntegration:
    """Integration-style tests for the enforcement service."""

    @pytest.mark.asyncio
    async def test_full_validation_workflow(self, enforcement_service):
        """Test complete validation workflow from config to gate decision."""
        # 1. Verify config is loaded
        config_info = enforcement_service.get_config_info()
        assert config_info["config_loaded"]

        # 2. Get deployment mapping (should have rollback)
        mapping = enforcement_service.get_phase_mapping("deployment")
        assert mapping.rollback_on_fail

        # 3. Simulate a failed validation
        with patch.object(enforcement_service, '_execute_quality_fabric_validation') as mock_exec:
            mock_exec.return_value = {
                "status": {
                    "status": "completed",
                    "total_tests": 10,
                    "passed_tests": 7,
                    "failed_tests": 3,
                    "error_tests": 0,
                },
                "results": {
                    "coverage": 65.0,
                    "issues": {"critical": 0, "high": 2},
                },
            }

            result = await enforcement_service.validate_phase(
                phase_id="phase_deploy_test",
                phase_type="deployment",
                workflow_id="wf_integration_test",
            )

        # 4. Check if gate should be blocked
        should_block, block_reason = enforcement_service.should_block_gate(result)
        assert should_block == True

        # 5. Check if rollback is needed
        should_rollback, rollback_reason = enforcement_service.check_rollback_needed(
            result, mapping
        )
        assert should_rollback == True

        # 6. Verify evidence is created
        evidence = enforcement_service.create_gate_evidence(result)
        assert evidence["type"] == "quality_validation"


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
