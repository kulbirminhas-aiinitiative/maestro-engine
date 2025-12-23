"""
Test Suite for Block Promotion Pipeline (MD-2510)

Tests for all acceptance criteria:
- AC-1: BlockStatus enum with NEW, SHARABLE, CATALOGUED, TRUSTED levels
- AC-2: Promotion gates with automated criteria checks
- AC-3: Human-in-the-loop approval mechanism
- AC-4: Promotion history and audit trail tracking
- AC-5: Emergency override capability with audit logging

Author: Maestro Platform Team
Created: 2025-12-06
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from orchestration.block_promotion import (
    BlockStatus,
    ApproverRole,
    ApprovalStatus,
    GateResult,
    PromotionCriteria,
    CriteriaResult,
    HumanApproval,
    PromotionLevelConfig,
    GateEvaluation,
    PromotionAttempt,
    BlockInfo,
    PromotionGate,
    NewToSharableGate,
    SharableToCataloguedGate,
    CataloguedToTrustedGate,
    PromotionHistoryTracker,
    BlockPromotionPipeline,
    create_default_criteria_validators,
)


# ============================================================================
# AC-1: BlockStatus Enum Tests
# ============================================================================

class TestBlockStatus:
    """AC-1: BlockStatus enum with 4 levels."""

    def test_all_statuses_defined(self):
        """Verify all 4 status levels are defined."""
        assert BlockStatus.NEW.value == "new"
        assert BlockStatus.SHARABLE.value == "sharable"
        assert BlockStatus.CATALOGUED.value == "catalogued"
        assert BlockStatus.TRUSTED.value == "trusted"

    def test_status_order(self):
        """Verify status progression order."""
        order = [BlockStatus.NEW, BlockStatus.SHARABLE, BlockStatus.CATALOGUED, BlockStatus.TRUSTED]
        assert len(order) == 4

    def test_status_from_string(self):
        """Test creating status from string value."""
        assert BlockStatus("new") == BlockStatus.NEW
        assert BlockStatus("trusted") == BlockStatus.TRUSTED

    def test_status_is_enum(self):
        """Test that BlockStatus is a proper enum."""
        assert isinstance(BlockStatus.NEW, BlockStatus)
        assert BlockStatus.NEW != BlockStatus.SHARABLE


class TestApproverRole:
    """Tests for ApproverRole enum."""

    def test_all_roles_defined(self):
        """Verify all approver roles are defined."""
        assert ApproverRole.DEVELOPER.value == "developer"
        assert ApproverRole.PEER.value == "peer"
        assert ApproverRole.SECURITY_TEAM.value == "security_team"
        assert ApproverRole.PLATFORM_LEAD.value == "platform_lead"
        assert ApproverRole.PLATFORM_TEAM.value == "platform_team"


class TestApprovalStatus:
    """Tests for ApprovalStatus enum."""

    def test_all_statuses_defined(self):
        """Verify all approval statuses are defined."""
        assert ApprovalStatus.PENDING.value == "pending"
        assert ApprovalStatus.APPROVED.value == "approved"
        assert ApprovalStatus.REJECTED.value == "rejected"
        assert ApprovalStatus.EXPIRED.value == "expired"


# ============================================================================
# AC-2: Promotion Gates with Automated Criteria
# ============================================================================

class TestNewToSharableGate:
    """AC-2: NEW -> SHARABLE gate tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gate = NewToSharableGate()

    def test_gate_initialization(self):
        """Test gate is properly initialized."""
        assert self.gate.from_status == BlockStatus.NEW
        assert self.gate.to_status == BlockStatus.SHARABLE
        assert len(self.gate.criteria) > 0
        assert len(self.gate.required_approvers) > 0

    def test_gate_name(self):
        """Test gate name generation."""
        assert self.gate.gate_name == "new_to_sharable"

    def test_required_approvers(self):
        """Test that Developer and Peer are required."""
        assert ApproverRole.DEVELOPER in self.gate.required_approvers
        assert ApproverRole.PEER in self.gate.required_approvers

    def test_evaluate_criteria_passes_with_valid_block(self):
        """Test criteria evaluation passes with valid block."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW,
            projects_used=3,
            interface_abstracted=True,
            metadata={"has_documentation": True}
        )

        results = self.gate.evaluate_criteria(block_info)

        # Check required criteria passed
        projects_result = next(r for r in results if r.criterion_name == "projects_used")
        interface_result = next(r for r in results if r.criterion_name == "interface_abstracted")

        assert projects_result.passed is True
        assert interface_result.passed is True

    def test_evaluate_criteria_fails_with_insufficient_projects(self):
        """Test criteria evaluation fails with insufficient projects."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW,
            projects_used=1,  # Need 2+
            interface_abstracted=True
        )

        results = self.gate.evaluate_criteria(block_info)
        projects_result = next(r for r in results if r.criterion_name == "projects_used")

        assert projects_result.passed is False
        assert "1 projects" in projects_result.details

    def test_evaluate_criteria_fails_without_interface(self):
        """Test criteria fails without abstracted interface."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW,
            projects_used=5,
            interface_abstracted=False
        )

        results = self.gate.evaluate_criteria(block_info)
        interface_result = next(r for r in results if r.criterion_name == "interface_abstracted")

        assert interface_result.passed is False

    def test_full_evaluation_pending_approval(self):
        """Test full evaluation with no approvals yet."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW,
            projects_used=3,
            interface_abstracted=True
        )

        evaluation = self.gate.evaluate(block_info, [])

        assert evaluation.result == GateResult.PENDING_APPROVAL
        assert "developer" in evaluation.notes.lower()

    def test_full_evaluation_passes_with_all_approvals(self):
        """Test full evaluation passes with all approvals."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW,
            projects_used=3,
            interface_abstracted=True
        )

        approvals = [
            HumanApproval(
                role=ApproverRole.DEVELOPER,
                approver_id="dev1",
                approver_name="Developer 1",
                status=ApprovalStatus.APPROVED
            ),
            HumanApproval(
                role=ApproverRole.PEER,
                approver_id="peer1",
                approver_name="Peer 1",
                status=ApprovalStatus.APPROVED
            )
        ]

        evaluation = self.gate.evaluate(block_info, approvals)

        assert evaluation.result == GateResult.PASSED

    def test_full_evaluation_fails_with_rejection(self):
        """Test full evaluation fails when any approver rejects."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW,
            projects_used=3,
            interface_abstracted=True
        )

        approvals = [
            HumanApproval(
                role=ApproverRole.DEVELOPER,
                approver_id="dev1",
                approver_name="Developer 1",
                status=ApprovalStatus.APPROVED
            ),
            HumanApproval(
                role=ApproverRole.PEER,
                approver_id="peer1",
                approver_name="Peer 1",
                status=ApprovalStatus.REJECTED,
                notes="Code quality issues"
            )
        ]

        evaluation = self.gate.evaluate(block_info, approvals)

        assert evaluation.result == GateResult.FAILED
        assert "rejected" in evaluation.notes.lower()


class TestSharableToCataloguedGate:
    """AC-2: SHARABLE -> CATALOGUED gate tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gate = SharableToCataloguedGate()

    def test_gate_initialization(self):
        """Test gate is properly initialized."""
        assert self.gate.from_status == BlockStatus.SHARABLE
        assert self.gate.to_status == BlockStatus.CATALOGUED

    def test_required_approvers(self):
        """Test that Security Team and Platform Lead are required."""
        assert ApproverRole.SECURITY_TEAM in self.gate.required_approvers
        assert ApproverRole.PLATFORM_LEAD in self.gate.required_approvers

    def test_security_review_criterion(self):
        """Test security review is a required criterion."""
        criteria_names = [c.name for c in self.gate.criteria]
        assert "security_review" in criteria_names

    def test_test_coverage_criterion(self):
        """Test coverage requirement (>90%)."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.SHARABLE,
            test_coverage=85.0  # Below 90%
        )

        results = self.gate.evaluate_criteria(block_info)
        coverage_result = next(r for r in results if r.criterion_name == "test_coverage")

        assert coverage_result.passed is False
        assert "85.0%" in coverage_result.details

    def test_contract_tests_criterion(self):
        """Test contract tests requirement."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.SHARABLE,
            contract_tests_defined=False
        )

        results = self.gate.evaluate_criteria(block_info)
        contract_result = next(r for r in results if r.criterion_name == "contract_tests")

        assert contract_result.passed is False


class TestCataloguedToTrustedGate:
    """AC-2: CATALOGUED -> TRUSTED gate tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gate = CataloguedToTrustedGate()

    def test_gate_initialization(self):
        """Test gate is properly initialized."""
        assert self.gate.from_status == BlockStatus.CATALOGUED
        assert self.gate.to_status == BlockStatus.TRUSTED

    def test_production_deployments_criterion(self):
        """Test 5+ production deployments requirement."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.CATALOGUED,
            production_deployments=3  # Need 5+
        )

        results = self.gate.evaluate_criteria(block_info)
        deploy_result = next(r for r in results if r.criterion_name == "production_deployments")

        assert deploy_result.passed is False
        assert "3" in deploy_result.details

    def test_days_without_bugs_criterion(self):
        """Test 30 days without critical bugs requirement."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.CATALOGUED,
            days_without_critical_bugs=15  # Need 30+
        )

        results = self.gate.evaluate_criteria(block_info)
        bugs_result = next(r for r in results if r.criterion_name == "days_without_bugs")

        assert bugs_result.passed is False
        assert "15" in bugs_result.details

    def test_majority_approval_rule(self):
        """Test that majority (not all) platform team approvals needed."""
        # This gate uses require_all_approvers=False
        assert self.gate.require_all_approvers is False


# ============================================================================
# AC-3: Human-in-the-Loop Approval Mechanism
# ============================================================================

class TestHumanApproval:
    """AC-3: Human approval data class tests."""

    def test_create_pending_approval(self):
        """Test creating a pending approval."""
        approval = HumanApproval(role=ApproverRole.DEVELOPER)

        assert approval.status == ApprovalStatus.PENDING
        assert approval.approver_id is None
        assert approval.approved_at is None

    def test_create_approved_approval(self):
        """Test creating an approved approval."""
        now = datetime.utcnow()
        approval = HumanApproval(
            role=ApproverRole.SECURITY_TEAM,
            approver_id="sec-001",
            approver_name="Security Lead",
            status=ApprovalStatus.APPROVED,
            notes="All security checks passed",
            approved_at=now
        )

        assert approval.status == ApprovalStatus.APPROVED
        assert approval.approver_name == "Security Lead"
        assert approval.notes == "All security checks passed"


class TestApprovalChecking:
    """AC-3: Tests for approval checking logic."""

    def test_check_approvals_all_approved(self):
        """Test checking when all approvals are received."""
        gate = NewToSharableGate()

        approvals = [
            HumanApproval(role=ApproverRole.DEVELOPER, status=ApprovalStatus.APPROVED),
            HumanApproval(role=ApproverRole.PEER, status=ApprovalStatus.APPROVED)
        ]

        all_approved, missing, rejected = gate.check_approvals(approvals)

        assert all_approved is True
        assert len(missing) == 0
        assert len(rejected) == 0

    def test_check_approvals_missing_some(self):
        """Test checking when some approvals are missing."""
        gate = NewToSharableGate()

        approvals = [
            HumanApproval(role=ApproverRole.DEVELOPER, status=ApprovalStatus.APPROVED)
            # Missing PEER approval
        ]

        all_approved, missing, rejected = gate.check_approvals(approvals)

        assert all_approved is False
        assert ApproverRole.PEER in missing
        assert len(rejected) == 0

    def test_check_approvals_with_rejection(self):
        """Test checking when one approver rejected."""
        gate = NewToSharableGate()

        approvals = [
            HumanApproval(role=ApproverRole.DEVELOPER, status=ApprovalStatus.APPROVED),
            HumanApproval(role=ApproverRole.PEER, status=ApprovalStatus.REJECTED)
        ]

        all_approved, missing, rejected = gate.check_approvals(approvals)

        assert all_approved is False
        assert ApproverRole.PEER in rejected


# ============================================================================
# AC-4: Promotion History and Audit Trail
# ============================================================================

class TestPromotionHistoryTracker:
    """AC-4: Promotion history and audit trail tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = PromotionHistoryTracker()

    def test_record_attempt(self):
        """Test recording a promotion attempt."""
        attempt = PromotionAttempt(
            block_id="test-block",
            block_version="1.0.0",
            from_status=BlockStatus.NEW,
            to_status=BlockStatus.SHARABLE,
            requester_id="user-001",
            requester_name="Test User",
            success=True
        )

        self.tracker.record_attempt(attempt)

        assert self.tracker.get_by_id(attempt.attempt_id) is not None
        assert len(self.tracker.get_by_block("test-block")) == 1

    def test_get_successful_promotions(self):
        """Test getting successful promotions."""
        successful = PromotionAttempt(
            block_id="test-block",
            success=True
        )
        failed = PromotionAttempt(
            block_id="test-block",
            success=False
        )

        self.tracker.record_attempt(successful)
        self.tracker.record_attempt(failed)

        successful_list = self.tracker.get_successful_promotions("test-block")
        assert len(successful_list) == 1

    def test_get_failed_promotions(self):
        """Test getting failed promotions."""
        successful = PromotionAttempt(
            block_id="test-block",
            success=True
        )
        failed = PromotionAttempt(
            block_id="test-block",
            success=False,
            failure_reason="Criteria not met"
        )

        self.tracker.record_attempt(successful)
        self.tracker.record_attempt(failed)

        failed_list = self.tracker.get_failed_promotions("test-block")
        assert len(failed_list) == 1
        assert failed_list[0].failure_reason == "Criteria not met"

    def test_get_statistics(self):
        """Test getting promotion statistics."""
        for i in range(5):
            attempt = PromotionAttempt(
                block_id="test-block",
                from_status=BlockStatus.NEW,
                to_status=BlockStatus.SHARABLE,
                success=(i < 3)  # 3 successful, 2 failed
            )
            self.tracker.record_attempt(attempt)

        stats = self.tracker.get_statistics("test-block")

        assert stats["total_attempts"] == 5
        assert stats["successful"] == 3
        assert stats["failed"] == 2
        assert stats["success_rate"] == 60.0


# ============================================================================
# AC-5: Emergency Override Capability
# ============================================================================

class TestEmergencyOverride:
    """AC-5: Emergency override capability tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.pipeline = BlockPromotionPipeline()

    def test_emergency_override_success(self):
        """Test successful emergency override to TRUSTED."""
        block_info = BlockInfo(
            block_id="critical-block",
            name="Critical Block",
            version="1.0.0",
            current_status=BlockStatus.NEW
        )

        attempt = self.pipeline.emergency_override(
            block_info=block_info,
            target_status=BlockStatus.TRUSTED,
            platform_lead_id="lead-001",
            platform_lead_name="Platform Lead",
            justification="Critical security fix required for production incident P1-2345"
        )

        assert attempt.success is True
        assert attempt.is_emergency_override is True
        assert attempt.to_status == BlockStatus.TRUSTED
        assert "P1-2345" in attempt.override_justification

    def test_emergency_override_requires_trusted_target(self):
        """Test that emergency override only works for TRUSTED target."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW
        )

        attempt = self.pipeline.emergency_override(
            block_info=block_info,
            target_status=BlockStatus.SHARABLE,  # Not TRUSTED
            platform_lead_id="lead-001",
            platform_lead_name="Platform Lead",
            justification="Need to promote quickly"
        )

        assert attempt.success is False
        assert "only allowed for TRUSTED" in attempt.failure_reason

    def test_emergency_override_requires_justification(self):
        """Test that emergency override requires sufficient justification."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW
        )

        attempt = self.pipeline.emergency_override(
            block_info=block_info,
            target_status=BlockStatus.TRUSTED,
            platform_lead_id="lead-001",
            platform_lead_name="Platform Lead",
            justification="Urgent"  # Too short
        )

        assert attempt.success is False
        assert "20 characters" in attempt.failure_reason

    def test_emergency_override_tracked_in_history(self):
        """Test that emergency overrides are tracked in history."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW
        )

        self.pipeline.emergency_override(
            block_info=block_info,
            target_status=BlockStatus.TRUSTED,
            platform_lead_id="lead-001",
            platform_lead_name="Platform Lead",
            justification="Critical production incident requires immediate deployment"
        )

        stats = self.pipeline.history.get_statistics()
        assert stats["emergency_overrides"] == 1

    def test_quarterly_override_report(self):
        """Test quarterly override report generation."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW
        )

        self.pipeline.emergency_override(
            block_info=block_info,
            target_status=BlockStatus.TRUSTED,
            platform_lead_id="lead-001",
            platform_lead_name="Platform Lead",
            justification="Critical production incident requires immediate deployment"
        )

        quarter_start = datetime.utcnow() - timedelta(days=90)
        quarter_end = datetime.utcnow()

        report = self.pipeline.get_quarterly_override_report(quarter_start, quarter_end)

        assert report["total_overrides"] == 1
        assert len(report["overrides"]) == 1
        assert report["overrides"][0]["requester"] == "Platform Lead"


# ============================================================================
# BlockPromotionPipeline Integration Tests
# ============================================================================

class TestBlockPromotionPipeline:
    """Integration tests for BlockPromotionPipeline."""

    def setup_method(self):
        """Set up test fixtures."""
        self.pipeline = BlockPromotionPipeline()

    def test_promotion_order(self):
        """Test promotion order is correct."""
        assert self.pipeline.PROMOTION_ORDER == [
            BlockStatus.NEW,
            BlockStatus.SHARABLE,
            BlockStatus.CATALOGUED,
            BlockStatus.TRUSTED
        ]

    def test_get_next_status(self):
        """Test getting next status in promotion chain."""
        assert self.pipeline.get_next_status(BlockStatus.NEW) == BlockStatus.SHARABLE
        assert self.pipeline.get_next_status(BlockStatus.SHARABLE) == BlockStatus.CATALOGUED
        assert self.pipeline.get_next_status(BlockStatus.CATALOGUED) == BlockStatus.TRUSTED
        assert self.pipeline.get_next_status(BlockStatus.TRUSTED) is None

    def test_can_promote_valid_transition(self):
        """Test can_promote for valid transition."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW
        )

        can_promote, reason = self.pipeline.can_promote(block_info, BlockStatus.SHARABLE)

        assert can_promote is True

    def test_cannot_skip_levels(self):
        """Test that promotion cannot skip levels."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW
        )

        can_promote, reason = self.pipeline.can_promote(block_info, BlockStatus.CATALOGUED)

        assert can_promote is False
        assert "skip" in reason.lower()

    def test_cannot_promote_backwards(self):
        """Test that promotion cannot go backwards."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.SHARABLE
        )

        can_promote, reason = self.pipeline.can_promote(block_info, BlockStatus.NEW)

        assert can_promote is False

    def test_request_promotion_creates_attempt(self):
        """Test that requesting promotion creates an attempt."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW,
            projects_used=5,
            interface_abstracted=True
        )

        attempt = self.pipeline.request_promotion(
            block_info=block_info,
            requester_id="user-001",
            requester_name="Test User"
        )

        assert attempt.block_id == "test-block"
        assert attempt.from_status == BlockStatus.NEW
        assert attempt.to_status == BlockStatus.SHARABLE
        assert len(attempt.gate_evaluations) > 0

    def test_submit_approval_updates_attempt(self):
        """Test that submitting approval updates the attempt."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW,
            projects_used=5,
            interface_abstracted=True
        )

        # Request promotion
        attempt = self.pipeline.request_promotion(
            block_info=block_info,
            requester_id="user-001",
            requester_name="Test User"
        )

        # Submit first approval
        updated = self.pipeline.submit_approval(
            attempt_id=attempt.attempt_id,
            approver_role=ApproverRole.DEVELOPER,
            approver_id="dev-001",
            approver_name="Developer 1",
            approved=True,
            notes="Looks good"
        )

        assert updated is not None
        # Still pending because peer approval needed
        assert len(updated.gate_evaluations[-1].human_approvals) == 1

    def test_all_approvals_completes_promotion(self):
        """Test that all approvals complete the promotion."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW,
            projects_used=5,
            interface_abstracted=True
        )

        attempt = self.pipeline.request_promotion(
            block_info=block_info,
            requester_id="user-001",
            requester_name="Test User"
        )

        # Submit both approvals
        self.pipeline.submit_approval(
            attempt_id=attempt.attempt_id,
            approver_role=ApproverRole.DEVELOPER,
            approver_id="dev-001",
            approver_name="Developer 1",
            approved=True
        )

        updated = self.pipeline.submit_approval(
            attempt_id=attempt.attempt_id,
            approver_role=ApproverRole.PEER,
            approver_id="peer-001",
            approver_name="Peer 1",
            approved=True
        )

        assert updated.success is True
        assert updated.completed_at is not None

    def test_rejection_fails_promotion(self):
        """Test that a rejection fails the promotion."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW,
            projects_used=5,
            interface_abstracted=True
        )

        attempt = self.pipeline.request_promotion(
            block_info=block_info,
            requester_id="user-001",
            requester_name="Test User"
        )

        # Reject
        updated = self.pipeline.submit_approval(
            attempt_id=attempt.attempt_id,
            approver_role=ApproverRole.DEVELOPER,
            approver_id="dev-001",
            approver_name="Developer 1",
            approved=False,
            notes="Code quality issues found"
        )

        assert updated.success is False
        assert "rejected" in updated.failure_reason.lower()

    def test_get_pending_approvals(self):
        """Test getting list of pending approvals."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW,
            projects_used=5,
            interface_abstracted=True
        )

        self.pipeline.request_promotion(
            block_info=block_info,
            requester_id="user-001",
            requester_name="Test User"
        )

        pending = self.pipeline.get_pending_approvals()
        assert len(pending) == 1

    def test_get_promotion_status(self):
        """Test getting status of a promotion attempt."""
        block_info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW,
            projects_used=5,
            interface_abstracted=True
        )

        attempt = self.pipeline.request_promotion(
            block_info=block_info,
            requester_id="user-001",
            requester_name="Test User"
        )

        status = self.pipeline.get_promotion_status(attempt.attempt_id)
        assert status is not None
        assert status.attempt_id == attempt.attempt_id


# ============================================================================
# Data Class Tests
# ============================================================================

class TestBlockInfo:
    """Tests for BlockInfo data class."""

    def test_create_minimal_block_info(self):
        """Test creating block info with minimal data."""
        info = BlockInfo(
            block_id="test-block",
            name="Test Block",
            version="1.0.0",
            current_status=BlockStatus.NEW
        )

        assert info.block_id == "test-block"
        assert info.projects_used == 0
        assert info.test_coverage == 0.0

    def test_create_full_block_info(self):
        """Test creating block info with all data."""
        info = BlockInfo(
            block_id="full-block",
            name="Full Block",
            version="2.0.0",
            current_status=BlockStatus.CATALOGUED,
            projects_used=10,
            test_coverage=95.5,
            production_deployments=7,
            days_without_critical_bugs=45,
            security_review_passed=True,
            contract_tests_defined=True,
            interface_abstracted=True,
            metadata={"sla_defined": True, "platform_maintained": True}
        )

        assert info.test_coverage == 95.5
        assert info.security_review_passed is True
        assert info.metadata["sla_defined"] is True


class TestPromotionAttempt:
    """Tests for PromotionAttempt data class."""

    def test_create_attempt_with_defaults(self):
        """Test creating attempt with default values."""
        attempt = PromotionAttempt()

        assert attempt.attempt_id is not None  # UUID generated
        assert len(attempt.gate_evaluations) == 0
        assert attempt.success is False

    def test_attempt_id_is_unique(self):
        """Test that each attempt gets unique ID."""
        attempt1 = PromotionAttempt()
        attempt2 = PromotionAttempt()

        assert attempt1.attempt_id != attempt2.attempt_id


class TestGateEvaluation:
    """Tests for GateEvaluation data class."""

    def test_create_evaluation(self):
        """Test creating gate evaluation."""
        evaluation = GateEvaluation(
            gate_name="new_to_sharable",
            from_status=BlockStatus.NEW,
            to_status=BlockStatus.SHARABLE
        )

        assert evaluation.result == GateResult.PENDING_APPROVAL
        assert evaluation.score == 0.0


class TestCriteriaResult:
    """Tests for CriteriaResult data class."""

    def test_create_passed_result(self):
        """Test creating passed criteria result."""
        result = CriteriaResult(
            criterion_name="test_coverage",
            passed=True,
            details="Coverage: 95%",
            score=2.0
        )

        assert result.passed is True
        assert result.score == 2.0

    def test_create_failed_result(self):
        """Test creating failed criteria result."""
        result = CriteriaResult(
            criterion_name="test_coverage",
            passed=False,
            details="Coverage: 70% (need 90%)",
            score=0.0
        )

        assert result.passed is False
        assert result.score == 0.0


# ============================================================================
# Utility Function Tests
# ============================================================================

class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_create_default_criteria_validators(self):
        """Test creating default validators."""
        validators = create_default_criteria_validators()

        assert "projects_used" in validators
        assert "test_coverage" in validators
        assert "production_deployments" in validators
        assert "security_review" in validators

    def test_projects_used_validator(self):
        """Test projects_used validator."""
        validators = create_default_criteria_validators()
        validator = validators["projects_used"]

        passed, details = validator({"projects_used": 5}, 2)
        assert passed is True

        passed, details = validator({"projects_used": 1}, 2)
        assert passed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
