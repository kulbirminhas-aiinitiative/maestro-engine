#!/usr/bin/env python3
"""
Unit tests for Governance Service
Tests MD-2107: Governance Protocol Integration

Acceptance Criteria Tested:
- AC-1: Governance Protocol schema defines required docs per phase
- AC-2: GovernanceService validates phases have required documentation
- AC-3: Phase transitions blocked if governance fails
- AC-4: Governance decisions logged for audit trail
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.governance_service import (
    GovernanceService,
    GovernancePhaseHook,
    GovernanceResult,
    GovernanceValidationResult,
    DocumentStatus,
    DocumentRequirement,
    DocumentValidationResult,
    EnforcementLevel,
    GateValidationResult,
    PhaseGovernance,
    QualityGateRequirement,
    AuditEntry,
    ApprovalWorkflow,
    get_governance_service,
    reset_governance_service,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_governance_config():
    """Create a sample governance protocol YAML."""
    return {
        "version": "1.0.0",
        "name": "Test Governance Protocol",
        "phases": {
            "requirements": {
                "display_name": "Requirements Phase",
                "required_documents": [
                    {
                        "name": "Business Requirements Document",
                        "template": "brd_template",
                        "validation": {
                            "min_sections": 3,
                            "required_sections": ["overview", "objectives", "scope"],
                        },
                    },
                    {
                        "name": "Optional Stakeholder Doc",
                        "template": "stakeholder_template",
                        "optional": True,
                    },
                ],
                "quality_gates": [
                    {
                        "gate_type": "BRV",
                        "name": "Business Approval",
                        "enforcement": "mandatory",
                        "approvers": {"min_count": 1},
                    },
                ],
                "audit_requirements": {
                    "log_all_changes": True,
                },
            },
            "implementation": {
                "display_name": "Implementation Phase",
                "required_documents": [
                    {
                        "name": "Implementation Plan",
                        "template": "impl_template",
                        "validation": {
                            "min_sections": 2,
                            "required_sections": ["tasks", "dependencies"],
                        },
                    },
                ],
                "quality_gates": [
                    {
                        "gate_type": "DDE",
                        "name": "Code Standards Met",
                        "enforcement": "mandatory",
                        "metrics": {
                            "linting_passed": True,
                            "coverage_min": 80,
                        },
                    },
                    {
                        "gate_type": "ACC",
                        "name": "Unit Tests Advisory",
                        "enforcement": "advisory",
                        "metrics": {
                            "all_tests_pass": True,
                        },
                    },
                ],
            },
        },
        "global_settings": {
            "enforcement": {
                "strict_mode": False,
                "allow_overrides": True,
            },
        },
        "roles": {
            "developer": {
                "display_name": "Developer",
                "permissions": ["submit_documents"],
            },
        },
    }


@pytest.fixture
def temp_config_file(sample_governance_config):
    """Create a temporary config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(sample_governance_config, f)
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def governance_service(temp_config_file):
    """Create a governance service with test config."""
    reset_governance_service()
    return GovernanceService(config_path=temp_config_file)


@pytest.fixture
def governance_service_default():
    """Create a governance service with default config."""
    reset_governance_service()
    return GovernanceService(config_path="/nonexistent/path.yaml")


# ============================================================================
# DATA CLASS TESTS
# ============================================================================

class TestDocumentRequirement:
    """Tests for DocumentRequirement dataclass."""

    def test_creation(self):
        doc = DocumentRequirement(
            name="Test Doc",
            template="test_template",
            validation={"min_sections": 3},
            optional=False,
        )
        assert doc.name == "Test Doc"
        assert doc.template == "test_template"
        assert doc.validation == {"min_sections": 3}
        assert doc.optional is False

    def test_to_dict(self):
        doc = DocumentRequirement(name="Test", template="tpl")
        result = doc.to_dict()
        assert result["name"] == "Test"
        assert result["template"] == "tpl"
        assert result["optional"] is False


class TestQualityGateRequirement:
    """Tests for QualityGateRequirement dataclass."""

    def test_creation(self):
        gate = QualityGateRequirement(
            gate_type="DDE",
            name="Test Gate",
            enforcement=EnforcementLevel.MANDATORY,
            metrics={"coverage": 80},
        )
        assert gate.gate_type == "DDE"
        assert gate.name == "Test Gate"
        assert gate.enforcement == EnforcementLevel.MANDATORY

    def test_to_dict(self):
        gate = QualityGateRequirement(
            gate_type="BRV",
            name="Approval",
            enforcement=EnforcementLevel.ADVISORY,
        )
        result = gate.to_dict()
        assert result["gate_type"] == "BRV"
        assert result["enforcement"] == "advisory"


class TestPhaseGovernance:
    """Tests for PhaseGovernance dataclass."""

    def test_creation(self):
        phase = PhaseGovernance(
            phase_id="test",
            display_name="Test Phase",
            required_documents=[DocumentRequirement(name="Doc", template="tpl")],
            quality_gates=[],
        )
        assert phase.phase_id == "test"
        assert len(phase.required_documents) == 1

    def test_to_dict(self):
        phase = PhaseGovernance(
            phase_id="impl",
            display_name="Implementation",
        )
        result = phase.to_dict()
        assert result["phase_id"] == "impl"
        assert result["display_name"] == "Implementation"
        assert result["required_documents"] == []


class TestDocumentValidationResult:
    """Tests for DocumentValidationResult dataclass."""

    def test_passed_result(self):
        result = DocumentValidationResult(
            document_name="Test Doc",
            status=DocumentStatus.APPROVED,
            passed=True,
            hash="abc123",
        )
        assert result.passed is True
        assert result.status == DocumentStatus.APPROVED

    def test_failed_result(self):
        result = DocumentValidationResult(
            document_name="Test Doc",
            status=DocumentStatus.REJECTED,
            passed=False,
            issues=["Missing section: overview"],
        )
        assert result.passed is False
        assert len(result.issues) == 1


class TestGateValidationResult:
    """Tests for GateValidationResult dataclass."""

    def test_creation(self):
        result = GateValidationResult(
            gate_name="Test Gate",
            gate_type="DDE",
            enforcement="mandatory",
            passed=True,
            score=100.0,
        )
        assert result.passed is True
        assert result.score == 100.0


class TestGovernanceValidationResult:
    """Tests for GovernanceValidationResult dataclass."""

    def test_passed_result(self):
        result = GovernanceValidationResult(
            phase_id="requirements",
            result=GovernanceResult.PASSED,
            can_proceed=True,
        )
        assert result.can_proceed is True
        assert result.result == GovernanceResult.PASSED

    def test_failed_result(self):
        result = GovernanceValidationResult(
            phase_id="design",
            result=GovernanceResult.FAILED,
            blocking_issues=["Missing document"],
            can_proceed=False,
        )
        assert result.can_proceed is False
        assert len(result.blocking_issues) == 1


class TestAuditEntry:
    """Tests for AuditEntry dataclass."""

    def test_creation(self):
        entry = AuditEntry(
            id="test123",
            timestamp=datetime.utcnow().isoformat(),
            action="validation",
            phase_id="requirements",
            workflow_id="wf1",
            actor="user1",
            result="passed",
            details={"key": "value"},
        )
        assert entry.action == "validation"
        assert entry.result == "passed"


# ============================================================================
# GOVERNANCE SERVICE TESTS
# ============================================================================

class TestGovernanceServiceInit:
    """Tests for GovernanceService initialization."""

    def test_init_with_config(self, governance_service):
        assert governance_service.config_path.exists()
        assert "requirements" in governance_service.list_phases()
        assert "implementation" in governance_service.list_phases()

    def test_init_without_config(self, governance_service_default):
        # Should load defaults
        phases = governance_service_default.list_phases()
        assert len(phases) >= 1  # At least default phases

    def test_strict_mode_setting(self, temp_config_file):
        service = GovernanceService(config_path=temp_config_file, strict_mode=True)
        assert service.strict_mode is False  # Config overrides constructor

    def test_allow_overrides_setting(self, temp_config_file):
        service = GovernanceService(config_path=temp_config_file, allow_overrides=False)
        assert service.allow_overrides is True  # Config overrides


class TestGetPhaseRequirements:
    """Tests for get_phase_requirements method."""

    def test_get_existing_phase(self, governance_service):
        reqs = governance_service.get_phase_requirements("requirements")
        assert reqs is not None
        assert reqs.phase_id == "requirements"
        assert len(reqs.required_documents) == 2

    def test_get_nonexistent_phase(self, governance_service):
        reqs = governance_service.get_phase_requirements("nonexistent")
        assert reqs is None


class TestDocumentRegistration:
    """Tests for document registration."""

    def test_register_document(self, governance_service):
        doc_id = governance_service.register_document(
            phase_id="requirements",
            document_name="Test Doc",
            content="Test content",
            document_type="markdown",
            metadata={"author": "test"},
        )
        assert doc_id is not None
        assert len(doc_id) == 16  # SHA256 prefix

    def test_register_creates_audit_entry(self, governance_service):
        governance_service.register_document(
            phase_id="requirements",
            document_name="Audit Test",
            content="Content",
            document_type="text",
        )
        audit = governance_service.get_audit_trail(phase_id="requirements")
        assert len(audit) > 0
        assert audit[0]["action"] == "document_registered"


class TestDocumentValidation:
    """Tests for document validation."""

    def test_validate_document_with_valid_content(self, governance_service):
        result = governance_service.validate_document(
            phase_id="requirements",
            document_name="Business Requirements Document",
            content="Long enough content for validation",
            sections=["overview", "objectives", "scope", "extra"],
        )
        assert result.passed is True
        assert result.status == DocumentStatus.APPROVED

    def test_validate_document_missing_sections(self, governance_service):
        result = governance_service.validate_document(
            phase_id="requirements",
            document_name="Business Requirements Document",
            content="Short content",
            sections=["overview"],  # Missing objectives and scope
        )
        assert result.passed is False
        assert result.status == DocumentStatus.REJECTED
        assert any("Missing required sections" in issue for issue in result.issues)

    def test_validate_document_insufficient_sections(self, governance_service):
        result = governance_service.validate_document(
            phase_id="requirements",
            document_name="Business Requirements Document",
            content="Content",
            sections=["overview", "objectives"],  # Only 2, need 3
        )
        assert result.passed is False
        assert any("Insufficient sections" in issue for issue in result.issues)

    def test_validate_unknown_document_passes(self, governance_service):
        # Documents not in requirements list should pass
        result = governance_service.validate_document(
            phase_id="requirements",
            document_name="Unknown Document",
            content="Any content",
        )
        assert result.passed is True

    def test_validate_document_unknown_phase(self, governance_service):
        result = governance_service.validate_document(
            phase_id="nonexistent",
            document_name="Any Doc",
            content="Content",
        )
        assert result.passed is False
        assert "Unknown phase" in result.issues[0]


class TestQualityGateValidation:
    """Tests for quality gate validation."""

    def test_validate_gate_passing_metrics(self, governance_service):
        result = governance_service.validate_quality_gate(
            phase_id="implementation",
            gate_name="Code Standards Met",
            metrics={
                "linting_passed": True,
                "coverage_min": 85,
            },
        )
        assert result.passed is True
        assert result.score == 100.0

    def test_validate_gate_failing_metrics(self, governance_service):
        result = governance_service.validate_quality_gate(
            phase_id="implementation",
            gate_name="Code Standards Met",
            metrics={
                "linting_passed": False,  # Should be True
                "coverage_min": 70,  # Below 80
            },
        )
        assert result.passed is False
        assert len(result.issues) == 2

    def test_validate_gate_missing_metrics(self, governance_service):
        result = governance_service.validate_quality_gate(
            phase_id="implementation",
            gate_name="Code Standards Met",
            metrics={},  # No metrics provided
        )
        assert result.passed is False
        assert any("Missing metric" in issue for issue in result.issues)

    def test_validate_unknown_gate(self, governance_service):
        result = governance_service.validate_quality_gate(
            phase_id="implementation",
            gate_name="Unknown Gate",
            metrics={},
        )
        # Unknown gates pass by default
        assert result.passed is True


class TestPhaseTransitionValidation:
    """Tests for phase transition validation."""

    def test_validate_transition_all_passed(self, governance_service):
        result = governance_service.validate_phase_transition(
            phase_id="requirements",
            workflow_id="wf1",
            documents={
                "Business Requirements Document": {
                    "content": "Full content here",
                    "sections": ["overview", "objectives", "scope"],
                },
            },
            gate_metrics={
                "Business Approval": {
                    "approvals": ["approver1"],
                },
            },
            actor="test_user",
        )
        assert result.result == GovernanceResult.PASSED
        assert result.can_proceed is True
        assert len(result.blocking_issues) == 0

    def test_validate_transition_missing_document(self, governance_service):
        result = governance_service.validate_phase_transition(
            phase_id="requirements",
            workflow_id="wf1",
            documents={},  # No documents
            gate_metrics={},
            actor="test_user",
        )
        assert result.result == GovernanceResult.FAILED
        assert result.can_proceed is False
        assert any("Missing required document" in issue for issue in result.blocking_issues)

    def test_validate_transition_with_warnings(self, governance_service):
        # Advisory gate fails but mandatory passes
        result = governance_service.validate_phase_transition(
            phase_id="implementation",
            documents={
                "Implementation Plan": {
                    "content": "Content",
                    "sections": ["tasks", "dependencies"],
                },
            },
            gate_metrics={
                "Code Standards Met": {
                    "linting_passed": True,
                    "coverage_min": 90,
                },
                "Unit Tests Advisory": {
                    "all_tests_pass": False,  # Advisory gate fails
                },
            },
        )
        assert result.result == GovernanceResult.WARNING
        assert result.can_proceed is True
        assert len(result.warnings) > 0

    def test_validate_transition_with_override(self, governance_service):
        result = governance_service.validate_phase_transition(
            phase_id="requirements",
            documents={},  # Missing required docs
            gate_metrics={},
            actor="admin_user",
            override=True,
            override_reason="Emergency deployment required",
        )
        assert result.result == GovernanceResult.SKIPPED
        assert result.can_proceed is True
        assert result.override_applied is True

    def test_validate_transition_override_without_reason(self, governance_service):
        result = governance_service.validate_phase_transition(
            phase_id="requirements",
            documents={},
            gate_metrics={},
            override=True,
            override_reason=None,  # No reason
        )
        assert result.can_proceed is False  # Override not applied
        assert result.override_applied is False

    def test_validate_transition_unknown_phase(self, governance_service):
        result = governance_service.validate_phase_transition(
            phase_id="nonexistent",
        )
        assert result.result == GovernanceResult.FAILED
        assert "Unknown phase" in result.blocking_issues[0]


class TestAuditTrail:
    """Tests for audit trail functionality."""

    def test_audit_trail_logging(self, governance_service):
        governance_service.validate_phase_transition(
            phase_id="requirements",
            workflow_id="test_workflow",
            actor="test_user",
        )

        audit = governance_service.get_audit_trail()
        assert len(audit) > 0
        assert audit[0]["action"] == "phase_validation"
        assert audit[0]["phase_id"] == "requirements"

    def test_audit_trail_filter_by_phase(self, governance_service):
        governance_service.validate_phase_transition(phase_id="requirements")
        governance_service.validate_phase_transition(phase_id="implementation")

        audit = governance_service.get_audit_trail(phase_id="requirements")
        assert all(e["phase_id"] == "requirements" for e in audit)

    def test_audit_trail_filter_by_workflow(self, governance_service):
        governance_service.validate_phase_transition(phase_id="requirements", workflow_id="wf1")
        governance_service.validate_phase_transition(phase_id="requirements", workflow_id="wf2")

        audit = governance_service.get_audit_trail(workflow_id="wf1")
        assert all(e["workflow_id"] == "wf1" for e in audit)

    def test_audit_trail_limit(self, governance_service):
        for i in range(10):
            governance_service.validate_phase_transition(phase_id="requirements")

        audit = governance_service.get_audit_trail(limit=5)
        assert len(audit) == 5


class TestGovernanceServiceSerialization:
    """Tests for service serialization."""

    def test_to_dict(self, governance_service):
        result = governance_service.to_dict()
        assert "config_path" in result
        assert "strict_mode" in result
        assert "phases" in result
        assert "roles" in result


# ============================================================================
# GOVERNANCE PHASE HOOK TESTS
# ============================================================================

class TestGovernancePhaseHook:
    """Tests for GovernancePhaseHook integration."""

    def test_hook_initialization(self, governance_service):
        hook = GovernancePhaseHook(governance_service)
        assert hook.governance_service is governance_service

    def test_set_phase_documents(self, governance_service):
        hook = GovernancePhaseHook(governance_service)
        hook.set_phase_documents("requirements", {
            "Business Requirements Document": {"content": "Test"},
        })
        assert "requirements" in hook._document_cache

    def test_set_gate_metrics(self, governance_service):
        hook = GovernancePhaseHook(governance_service)
        hook.set_gate_metrics("implementation", {
            "Code Standards Met": {"linting_passed": True},
        })
        assert "implementation" in hook._gate_metrics_cache

    def test_validate_transition_with_cached_data(self, governance_service):
        hook = GovernancePhaseHook(governance_service)
        hook.set_phase_documents("requirements", {
            "Business Requirements Document": {
                "content": "Content",
                "sections": ["overview", "objectives", "scope"],
            },
        })
        hook.set_gate_metrics("requirements", {
            "Business Approval": {"approvals": ["user1"]},
        })

        can_proceed, result = hook.validate_transition(
            from_phase="requirements",
            to_phase="design",
            actor="test_user",
        )
        assert can_proceed is True
        assert result.result == GovernanceResult.PASSED

    def test_validate_transition_blocked(self, governance_service):
        hook = GovernancePhaseHook(governance_service)
        # No documents cached

        can_proceed, result = hook.validate_transition(
            from_phase="requirements",
            to_phase="design",
        )
        assert can_proceed is False
        assert result.result == GovernanceResult.FAILED

    def test_validate_transition_with_override(self, governance_service):
        hook = GovernancePhaseHook(governance_service)
        # No documents cached, but override

        can_proceed, result = hook.validate_transition(
            from_phase="requirements",
            to_phase="design",
            override=True,
            override_reason="Test override",
        )
        assert can_proceed is True
        assert result.override_applied is True

    def test_clear_cache_specific_phase(self, governance_service):
        hook = GovernancePhaseHook(governance_service)
        hook.set_phase_documents("requirements", {"doc": {}})
        hook.set_phase_documents("design", {"doc": {}})

        hook.clear_cache("requirements")
        assert "requirements" not in hook._document_cache
        assert "design" in hook._document_cache

    def test_clear_cache_all(self, governance_service):
        hook = GovernancePhaseHook(governance_service)
        hook.set_phase_documents("requirements", {"doc": {}})
        hook.set_phase_documents("design", {"doc": {}})

        hook.clear_cache()
        assert len(hook._document_cache) == 0


# ============================================================================
# SINGLETON TESTS
# ============================================================================

class TestSingleton:
    """Tests for singleton accessor."""

    def test_get_governance_service_singleton(self, temp_config_file):
        reset_governance_service()
        service1 = get_governance_service(config_path=temp_config_file)
        service2 = get_governance_service()
        assert service1 is service2

    def test_reset_governance_service(self, temp_config_file):
        reset_governance_service()
        service1 = get_governance_service(config_path=temp_config_file)
        reset_governance_service()
        service2 = get_governance_service(config_path=temp_config_file)
        assert service1 is not service2


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestGovernanceIntegration:
    """Integration tests for complete governance workflow."""

    def test_full_phase_workflow(self, governance_service):
        """Test complete workflow through multiple phases."""
        # Requirements phase
        result = governance_service.validate_phase_transition(
            phase_id="requirements",
            workflow_id="integration_test",
            documents={
                "Business Requirements Document": {
                    "content": "Full requirements document content",
                    "sections": ["overview", "objectives", "scope", "timeline"],
                },
            },
            gate_metrics={
                "Business Approval": {"approvals": ["product_owner"]},
            },
            actor="developer",
        )
        assert result.can_proceed is True

        # Implementation phase
        result = governance_service.validate_phase_transition(
            phase_id="implementation",
            workflow_id="integration_test",
            documents={
                "Implementation Plan": {
                    "content": "Implementation plan content",
                    "sections": ["tasks", "dependencies", "timeline"],
                },
            },
            gate_metrics={
                "Code Standards Met": {
                    "linting_passed": True,
                    "coverage_min": 85,
                },
                "Unit Tests Advisory": {
                    "all_tests_pass": True,
                },
            },
            actor="developer",
        )
        assert result.can_proceed is True

    def test_governance_with_optional_docs(self, governance_service):
        """Test that optional documents don't block transitions."""
        result = governance_service.validate_phase_transition(
            phase_id="requirements",
            documents={
                "Business Requirements Document": {
                    "content": "Content",
                    "sections": ["overview", "objectives", "scope"],
                },
                # "Optional Stakeholder Doc" not provided
            },
            gate_metrics={
                "Business Approval": {"approvals": ["approver"]},
            },
        )
        assert result.can_proceed is True
        # Optional doc missing should be in warnings, not blocking
        assert all("Optional Stakeholder" not in issue for issue in result.blocking_issues)

    def test_audit_trail_complete_workflow(self, governance_service):
        """Test that audit trail captures complete workflow."""
        workflow_id = "audit_test_workflow"

        # Multiple operations
        governance_service.register_document(
            phase_id="requirements",
            document_name="Test Doc",
            content="Content",
            document_type="text",
        )
        governance_service.validate_phase_transition(
            phase_id="requirements",
            workflow_id=workflow_id,
        )

        audit = governance_service.get_audit_trail(workflow_id=workflow_id)
        actions = [e["action"] for e in audit]
        assert "phase_validation" in actions
