#!/usr/bin/env python3
"""
Unit Tests for Template Promotion API Routes

Tests for:
- MD-1845: POST /api/templates/promote Endpoint
- MD-1846: Approval Workflow (approve/reject endpoints)
- MD-1847: Semantic Versioning & Changelog endpoints

Test coverage includes:
- Request validation
- Response format validation
- Authentication checks
- Rate limiting
- Audit logging
- Approval workflow states
- Version history tracking
- Changelog generation
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Import the routes module components
from api.template_promotion_routes import (
    RateLimiter,
    AuditLogger,
    ApprovalStatus,
    ApprovalRequest,
    ApprovalWorkflow,
    VersionHistory,
    PromoteRequest,
    PromoteResponse,
    ApproveRequest,
    RejectRequest,
    ApprovalStatusResponse,
    VersionListResponse,
    ChangelogResponse,
    ChangeDescription,
    rate_limiter,
    audit_logger,
    approval_workflow,
    version_history,
)


# ============================================================================
# TEST: RATE LIMITER (MD-1845)
# ============================================================================

class TestRateLimiter:
    """Tests for rate limiting functionality."""

    def test_rate_limiter_allows_initial_request(self):
        """Test that initial requests are allowed."""
        limiter = RateLimiter(requests_per_minute=10)
        assert limiter.is_allowed("client1") is True

    def test_rate_limiter_tracks_multiple_requests(self):
        """Test that multiple requests are tracked."""
        limiter = RateLimiter(requests_per_minute=5)

        for _ in range(5):
            assert limiter.is_allowed("client1") is True

        # 6th request should be blocked
        assert limiter.is_allowed("client1") is False

    def test_rate_limiter_separate_clients(self):
        """Test that different clients have separate limits."""
        limiter = RateLimiter(requests_per_minute=2)

        assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is False

        # Client2 should still be allowed
        assert limiter.is_allowed("client2") is True

    def test_rate_limiter_get_remaining(self):
        """Test remaining request count."""
        limiter = RateLimiter(requests_per_minute=5)

        assert limiter.get_remaining("client1") == 5
        limiter.is_allowed("client1")
        assert limiter.get_remaining("client1") == 4


# ============================================================================
# TEST: AUDIT LOGGER (MD-1845)
# ============================================================================

class TestAuditLogger:
    """Tests for audit logging functionality."""

    def test_audit_log_creates_entry(self):
        """Test that logging creates an entry."""
        logger = AuditLogger()

        audit_id = logger.log(
            action="test_action",
            template_id="tpl_123",
            user_id="user_456",
            details={"key": "value"},
        )

        assert audit_id.startswith("audit_")
        logs = logger.get_logs(template_id="tpl_123")
        assert len(logs) == 1
        assert logs[0]["action"] == "test_action"

    def test_audit_log_filters_by_template(self):
        """Test filtering logs by template ID."""
        logger = AuditLogger()

        logger.log("action1", "tpl_1", "user_1", {})
        logger.log("action2", "tpl_2", "user_1", {})
        logger.log("action3", "tpl_1", "user_2", {})

        logs_tpl1 = logger.get_logs(template_id="tpl_1")
        assert len(logs_tpl1) == 2

        logs_tpl2 = logger.get_logs(template_id="tpl_2")
        assert len(logs_tpl2) == 1

    def test_audit_log_filters_by_action(self):
        """Test filtering logs by action."""
        logger = AuditLogger()

        logger.log("promote", "tpl_1", "user_1", {})
        logger.log("approve", "tpl_1", "user_2", {})
        logger.log("promote", "tpl_2", "user_1", {})

        logs = logger.get_logs(action="promote")
        assert len(logs) == 2

    def test_audit_log_respects_limit(self):
        """Test that log retrieval respects limit."""
        logger = AuditLogger()

        for i in range(20):
            logger.log(f"action_{i}", f"tpl_{i}", "user_1", {})

        logs = logger.get_logs(limit=5)
        assert len(logs) == 5

    def test_audit_log_tracks_success_failure(self):
        """Test success/failure tracking."""
        logger = AuditLogger()

        logger.log("action1", "tpl_1", "user_1", {}, success=True)
        logger.log("action2", "tpl_2", "user_1", {}, success=False)

        logs = logger.get_logs()
        assert logs[0]["success"] is False
        assert logs[1]["success"] is True


# ============================================================================
# TEST: APPROVAL REQUEST (MD-1846)
# ============================================================================

class TestApprovalRequest:
    """Tests for approval request model."""

    def test_approval_request_creation(self):
        """Test creating an approval request."""
        request = ApprovalRequest(
            request_id="req_123",
            promotion_id="promo_456",
            template_id="tpl_789",
            requested_by="user_abc",
            target_environment="production",
            required_approvers=2,
            timeout_hours=24,
        )

        assert request.request_id == "req_123"
        assert request.status == ApprovalStatus.PENDING
        assert request.required_approvers == 2
        assert not request.is_expired

    def test_approval_request_expiration(self):
        """Test approval request expiration."""
        request = ApprovalRequest(
            request_id="req_123",
            promotion_id="promo_456",
            template_id="tpl_789",
            requested_by="user_abc",
            target_environment="production",
            timeout_hours=0,  # Expire immediately
        )

        # Force expiration
        request.expires_at = datetime.now() - timedelta(hours=1)
        assert request.is_expired is True

    def test_approval_request_approval_count(self):
        """Test tracking approval count."""
        request = ApprovalRequest(
            request_id="req_123",
            promotion_id="promo_456",
            template_id="tpl_789",
            requested_by="user_abc",
            target_environment="production",
            required_approvers=2,
        )

        assert request.approval_count == 0
        assert request.is_fully_approved is False

        request.approvals.append({"approver_id": "user_1", "approved_at": datetime.now().isoformat()})
        assert request.approval_count == 1
        assert request.is_fully_approved is False

        request.approvals.append({"approver_id": "user_2", "approved_at": datetime.now().isoformat()})
        assert request.approval_count == 2
        assert request.is_fully_approved is True

    def test_approval_request_to_dict(self):
        """Test serialization to dictionary."""
        request = ApprovalRequest(
            request_id="req_123",
            promotion_id="promo_456",
            template_id="tpl_789",
            requested_by="user_abc",
            target_environment="production",
        )

        data = request.to_dict()

        assert data["request_id"] == "req_123"
        assert data["promotion_id"] == "promo_456"
        assert data["template_id"] == "tpl_789"
        assert data["status"] == "pending"
        assert "created_at" in data
        assert "expires_at" in data


# ============================================================================
# TEST: APPROVAL WORKFLOW (MD-1846)
# ============================================================================

class TestApprovalWorkflow:
    """Tests for approval workflow management."""

    def test_create_request(self):
        """Test creating an approval request."""
        workflow = ApprovalWorkflow()

        request = workflow.create_request(
            promotion_id="promo_123",
            template_id="tpl_456",
            requested_by="user_789",
            target_environment="production",
            required_approvers=2,
        )

        assert request.request_id.startswith("approval_")
        assert request.promotion_id == "promo_123"
        assert request.required_approvers == 2

    def test_get_request_by_id(self):
        """Test retrieving request by ID."""
        workflow = ApprovalWorkflow()

        created = workflow.create_request(
            promotion_id="promo_1",
            template_id="tpl_1",
            requested_by="user_1",
            target_environment="staging",
        )

        retrieved = workflow.get_request(created.request_id)
        assert retrieved is not None
        assert retrieved.request_id == created.request_id

    def test_get_request_by_promotion(self):
        """Test retrieving request by promotion ID."""
        workflow = ApprovalWorkflow()

        workflow.create_request(
            promotion_id="promo_unique",
            template_id="tpl_1",
            requested_by="user_1",
            target_environment="staging",
        )

        retrieved = workflow.get_by_promotion("promo_unique")
        assert retrieved is not None
        assert retrieved.promotion_id == "promo_unique"

    def test_approve_request(self):
        """Test approving a request."""
        workflow = ApprovalWorkflow()

        request = workflow.create_request(
            promotion_id="promo_1",
            template_id="tpl_1",
            requested_by="user_1",
            target_environment="production",
            required_approvers=1,
        )

        success, message = workflow.approve(
            request_id=request.request_id,
            approver_id="approver_1",
            comment="Looks good!",
        )

        assert success is True
        assert request.status == ApprovalStatus.APPROVED
        assert request.approval_count == 1

    def test_approve_multi_approver(self):
        """Test multi-approver workflow."""
        workflow = ApprovalWorkflow()

        request = workflow.create_request(
            promotion_id="promo_1",
            template_id="tpl_1",
            requested_by="user_1",
            target_environment="production",
            required_approvers=2,
        )

        # First approval
        success1, _ = workflow.approve(request.request_id, "approver_1")
        assert success1 is True
        assert request.status == ApprovalStatus.PENDING  # Still pending

        # Second approval
        success2, _ = workflow.approve(request.request_id, "approver_2")
        assert success2 is True
        assert request.status == ApprovalStatus.APPROVED  # Now approved

    def test_approve_duplicate_prevented(self):
        """Test that same user cannot approve twice."""
        workflow = ApprovalWorkflow()

        request = workflow.create_request(
            promotion_id="promo_1",
            template_id="tpl_1",
            requested_by="user_1",
            target_environment="production",
            required_approvers=2,
        )

        workflow.approve(request.request_id, "approver_1")
        success, message = workflow.approve(request.request_id, "approver_1")

        assert success is False
        assert "already approved" in message

    def test_approve_expired_request(self):
        """Test approving an expired request fails."""
        workflow = ApprovalWorkflow()

        request = workflow.create_request(
            promotion_id="promo_1",
            template_id="tpl_1",
            requested_by="user_1",
            target_environment="production",
        )

        # Force expiration
        request.expires_at = datetime.now() - timedelta(hours=1)

        success, message = workflow.approve(request.request_id, "approver_1")

        assert success is False
        assert "expired" in message

    def test_reject_request(self):
        """Test rejecting a request."""
        workflow = ApprovalWorkflow()

        request = workflow.create_request(
            promotion_id="promo_1",
            template_id="tpl_1",
            requested_by="user_1",
            target_environment="production",
        )

        success, message = workflow.reject(
            request_id=request.request_id,
            rejector_id="reviewer_1",
            reason="Security concerns",
        )

        assert success is True
        assert request.status == ApprovalStatus.REJECTED
        assert len(request.rejections) == 1
        assert request.rejections[0]["reason"] == "Security concerns"

    def test_notifications_queued(self):
        """Test that notifications are queued on events."""
        workflow = ApprovalWorkflow()

        # Create request should queue notification
        request = workflow.create_request(
            promotion_id="promo_1",
            template_id="tpl_1",
            requested_by="user_1",
            target_environment="production",
            required_approvers=1,
        )

        notifications = workflow.get_pending_notifications()
        assert len(notifications) >= 1
        assert notifications[0]["event"] == "approval_requested"

        # Approval should queue notification
        workflow.approve(request.request_id, "approver_1")
        notifications = workflow.get_pending_notifications()
        assert any(n["event"] == "approval_complete" for n in notifications)

    def test_mark_notification_sent(self):
        """Test marking notification as sent."""
        workflow = ApprovalWorkflow()

        workflow.create_request(
            promotion_id="promo_1",
            template_id="tpl_1",
            requested_by="user_1",
            target_environment="production",
        )

        notifications = workflow.get_pending_notifications()
        assert len(notifications) > 0

        notif_id = notifications[0]["notification_id"]
        workflow.mark_notification_sent(notif_id)

        pending = workflow.get_pending_notifications()
        assert not any(n["notification_id"] == notif_id for n in pending)

    def test_check_timeouts(self):
        """Test timeout checking for expired requests."""
        workflow = ApprovalWorkflow()

        request = workflow.create_request(
            promotion_id="promo_1",
            template_id="tpl_1",
            requested_by="user_1",
            target_environment="production",
        )

        # Force expiration
        request.expires_at = datetime.now() - timedelta(hours=1)

        expired = workflow.check_timeouts()
        assert request.request_id in expired
        assert request.status == ApprovalStatus.EXPIRED


# ============================================================================
# TEST: VERSION HISTORY (MD-1847)
# ============================================================================

class TestVersionHistory:
    """Tests for version history tracking."""

    def test_record_version(self):
        """Test recording a new version."""
        history = VersionHistory()

        version_id = history.record_version(
            template_id="tpl_123",
            version="1.2.0",
            bump_type="minor",
            changes=[{"type": "added", "description": "New feature"}],
            promoted_by="user_abc",
        )

        assert version_id.startswith("ver_")

        versions = history.get_versions("tpl_123")
        assert len(versions) == 1
        assert versions[0]["version"] == "1.2.0"

    def test_get_versions_ordered(self):
        """Test versions are returned in order (newest first)."""
        history = VersionHistory()

        history.record_version("tpl_1", "1.0.0", "patch", [], "user_1")
        history.record_version("tpl_1", "1.1.0", "minor", [], "user_1")
        history.record_version("tpl_1", "2.0.0", "major", [], "user_1")

        versions = history.get_versions("tpl_1")
        assert len(versions) == 3
        assert versions[0]["version"] == "2.0.0"  # Newest first

    def test_get_specific_version(self):
        """Test retrieving a specific version."""
        history = VersionHistory()

        history.record_version("tpl_1", "1.0.0", "patch", [], "user_1")
        history.record_version("tpl_1", "1.1.0", "minor", [], "user_1")

        ver = history.get_version("tpl_1", "1.0.0")
        assert ver is not None
        assert ver["version"] == "1.0.0"

        ver_none = history.get_version("tpl_1", "9.9.9")
        assert ver_none is None

    def test_get_changelog(self):
        """Test generating changelog."""
        history = VersionHistory()

        history.record_version(
            template_id="tpl_1",
            version="1.0.0",
            bump_type="patch",
            changes=[
                {"type": "fixed", "description": "Bug fix 1"},
                {"type": "fixed", "description": "Bug fix 2"},
            ],
            promoted_by="user_1",
        )

        changelog = history.get_changelog("tpl_1")
        assert len(changelog) == 2

    def test_changelog_markdown_generation(self):
        """Test markdown changelog generation."""
        history = VersionHistory()

        history.record_version(
            template_id="tpl_test",
            version="1.0.0",
            bump_type="minor",
            changes=[
                {"type": "added", "description": "New feature", "breaking": False},
                {"type": "breaking", "description": "API change", "breaking": True},
            ],
            promoted_by="developer_1",
        )

        markdown = history.generate_markdown_changelog("tpl_test")

        assert "# Changelog for tpl_test" in markdown
        assert "[1.0.0]" in markdown
        assert "New feature" in markdown
        assert "**BREAKING**" in markdown

    def test_version_history_respects_limit(self):
        """Test that version retrieval respects limit."""
        history = VersionHistory()

        for i in range(20):
            history.record_version(f"tpl_1", f"1.0.{i}", "patch", [], "user_1")

        versions = history.get_versions("tpl_1", limit=5)
        assert len(versions) == 5

    def test_empty_changelog(self):
        """Test changelog for non-existent template."""
        history = VersionHistory()

        markdown = history.generate_markdown_changelog("nonexistent_tpl")
        assert "No changes recorded" in markdown


# ============================================================================
# TEST: REQUEST MODELS (MD-1845)
# ============================================================================

class TestRequestModels:
    """Tests for Pydantic request models."""

    def test_promote_request_valid(self):
        """Test valid promote request."""
        request = PromoteRequest(
            template_id="tpl_123",
            template_content="def hello(): pass",
            source_environment="staging",
            target_environment="production",
        )

        assert request.template_id == "tpl_123"
        assert request.source_environment == "staging"
        assert request.target_environment == "production"

    def test_promote_request_invalid_environment(self):
        """Test promote request with invalid environment."""
        with pytest.raises(ValueError) as exc:
            PromoteRequest(
                template_id="tpl_123",
                template_content="def hello(): pass",
                source_environment="invalid",
                target_environment="production",
            )
        assert "Environment must be one of" in str(exc.value)

    def test_promote_request_invalid_bump_type(self):
        """Test promote request with invalid version bump."""
        with pytest.raises(ValueError) as exc:
            PromoteRequest(
                template_id="tpl_123",
                template_content="def hello(): pass",
                force_version_bump="invalid",
            )
        assert "Version bump must be one of" in str(exc.value)

    def test_promote_request_with_changes(self):
        """Test promote request with changes."""
        request = PromoteRequest(
            template_id="tpl_123",
            template_content="def hello(): pass",
            changes=[
                ChangeDescription(
                    type="added",
                    description="New feature",
                    breaking=False,
                ),
                ChangeDescription(
                    type="breaking",
                    description="API changed",
                    breaking=True,
                ),
            ],
        )

        assert len(request.changes) == 2
        assert request.changes[0].type == "added"
        assert request.changes[1].breaking is True

    def test_approve_request_valid(self):
        """Test valid approve request."""
        request = ApproveRequest(comment="LGTM")
        assert request.comment == "LGTM"

    def test_reject_request_requires_reason(self):
        """Test reject request requires reason."""
        with pytest.raises(ValueError):
            RejectRequest(reason="")

    def test_reject_request_valid(self):
        """Test valid reject request."""
        request = RejectRequest(reason="Security vulnerability found")
        assert request.reason == "Security vulnerability found"


# ============================================================================
# TEST: RESPONSE MODELS (MD-1845, MD-1846, MD-1847)
# ============================================================================

class TestResponseModels:
    """Tests for Pydantic response models."""

    def test_promote_response(self):
        """Test promote response model."""
        response = PromoteResponse(
            promotion_id="promo_123",
            template_id="tpl_456",
            status="promoted",
            previous_version="1.0.0",
            new_version="1.1.0",
            version_bump_type="minor",
            source_environment="staging",
            target_environment="production",
            message="Success",
            promoted_at="2025-01-01T00:00:00",
            duration_ms=150.5,
        )

        assert response.promotion_id == "promo_123"
        assert response.new_version == "1.1.0"

    def test_approval_status_response(self):
        """Test approval status response model."""
        response = ApprovalStatusResponse(
            request_id="req_123",
            promotion_id="promo_456",
            template_id="tpl_789",
            status="pending",
            requested_by="user_abc",
            target_environment="production",
            required_approvers=2,
            current_approvals=1,
            approvals=[{"approver_id": "user_1"}],
            rejections=[],
            created_at="2025-01-01T00:00:00",
            expires_at="2025-01-03T00:00:00",
            is_expired=False,
            message="Pending approval",
        )

        assert response.required_approvers == 2
        assert response.current_approvals == 1

    def test_version_list_response(self):
        """Test version list response model."""
        response = VersionListResponse(
            template_id="tpl_123",
            versions=[
                {"version": "2.0.0", "bump_type": "major"},
                {"version": "1.0.0", "bump_type": "patch"},
            ],
            total=2,
        )

        assert response.total == 2
        assert len(response.versions) == 2

    def test_changelog_response(self):
        """Test changelog response model."""
        response = ChangelogResponse(
            template_id="tpl_123",
            entries=[
                {"version": "1.0.0", "change_type": "added", "description": "Feature"},
            ],
            total=1,
            markdown="# Changelog\n...",
        )

        assert response.total == 1
        assert response.markdown is not None


# ============================================================================
# TEST: INTEGRATION SCENARIOS
# ============================================================================

class TestIntegrationScenarios:
    """Integration tests for complete workflows."""

    def test_full_promotion_with_approval(self):
        """Test complete promotion flow with approval."""
        workflow = ApprovalWorkflow()
        history = VersionHistory()
        audit = AuditLogger()

        # Step 1: Create approval request
        request = workflow.create_request(
            promotion_id="promo_int_1",
            template_id="tpl_int_1",
            requested_by="developer_1",
            target_environment="production",
            required_approvers=2,
        )

        audit.log("request_approval", "tpl_int_1", "developer_1", {
            "request_id": request.request_id,
        })

        assert request.status == ApprovalStatus.PENDING

        # Step 2: First approval
        workflow.approve(request.request_id, "reviewer_1", "LGTM")
        audit.log("approve", "tpl_int_1", "reviewer_1", {})

        assert request.status == ApprovalStatus.PENDING

        # Step 3: Second approval
        workflow.approve(request.request_id, "reviewer_2", "Approved")
        audit.log("approve", "tpl_int_1", "reviewer_2", {})

        assert request.status == ApprovalStatus.APPROVED

        # Step 4: Record version
        history.record_version(
            template_id="tpl_int_1",
            version="2.0.0",
            bump_type="major",
            changes=[{"type": "breaking", "description": "API v2"}],
            promoted_by="developer_1",
        )

        # Verify
        versions = history.get_versions("tpl_int_1")
        assert len(versions) == 1
        assert versions[0]["version"] == "2.0.0"

        logs = audit.get_logs(template_id="tpl_int_1")
        assert len(logs) == 3

    def test_promotion_rejection_flow(self):
        """Test promotion rejection flow."""
        workflow = ApprovalWorkflow()
        audit = AuditLogger()

        # Create request
        request = workflow.create_request(
            promotion_id="promo_rej_1",
            template_id="tpl_rej_1",
            requested_by="developer_1",
            target_environment="production",
        )

        # Reject
        success, message = workflow.reject(
            request.request_id,
            "security_reviewer",
            "Vulnerability CVE-2025-XXXX found",
        )

        audit.log("reject", "tpl_rej_1", "security_reviewer", {
            "reason": "Vulnerability CVE-2025-XXXX found",
        })

        assert success is True
        assert request.status == ApprovalStatus.REJECTED
        assert len(request.rejections) == 1

    def test_timeout_handling(self):
        """Test request timeout handling."""
        workflow = ApprovalWorkflow()

        # Create request with short timeout
        request = workflow.create_request(
            promotion_id="promo_timeout_1",
            template_id="tpl_timeout_1",
            requested_by="developer_1",
            target_environment="production",
            timeout_hours=0,  # Immediate timeout
        )

        # Force expiration
        request.expires_at = datetime.now() - timedelta(minutes=1)

        # Check timeouts
        expired_ids = workflow.check_timeouts()

        assert request.request_id in expired_ids
        assert request.status == ApprovalStatus.EXPIRED

        # Verify notification was queued
        notifications = workflow.get_pending_notifications()
        assert any(n["event"] == "approval_expired" for n in notifications)


# ============================================================================
# TEST: EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_template_content_rejected(self):
        """Test that empty template content is rejected."""
        with pytest.raises(ValueError):
            PromoteRequest(
                template_id="tpl_123",
                template_content="",  # Empty content
                target_environment="production",
            )

    def test_approver_count_bounds(self):
        """Test approver count validation."""
        # Valid range
        request = PromoteRequest(
            template_id="tpl_123",
            template_content="def test(): pass",
            require_approval=True,
            approvers_required=3,
        )
        assert request.approvers_required == 3

        # Below minimum
        with pytest.raises(ValueError):
            PromoteRequest(
                template_id="tpl_123",
                template_content="def test(): pass",
                require_approval=True,
                approvers_required=0,
            )

        # Above maximum
        with pytest.raises(ValueError):
            PromoteRequest(
                template_id="tpl_123",
                template_content="def test(): pass",
                require_approval=True,
                approvers_required=10,
            )

    def test_approve_non_existent_request(self):
        """Test approving non-existent request."""
        workflow = ApprovalWorkflow()

        success, message = workflow.approve("non_existent_id", "user_1")

        assert success is False
        assert "not found" in message

    def test_reject_non_existent_request(self):
        """Test rejecting non-existent request."""
        workflow = ApprovalWorkflow()

        success, message = workflow.reject("non_existent_id", "user_1", "reason")

        assert success is False
        assert "not found" in message

    def test_version_history_empty_changes(self):
        """Test version history with empty changes."""
        history = VersionHistory()

        version_id = history.record_version(
            template_id="tpl_empty",
            version="1.0.0",
            bump_type="patch",
            changes=[],  # Empty changes
            promoted_by="user_1",
        )

        assert version_id is not None
        versions = history.get_versions("tpl_empty")
        assert len(versions) == 1

    def test_audit_log_capacity(self):
        """Test audit log capacity handling."""
        logger = AuditLogger()

        # Add many entries
        for i in range(15000):
            logger.log(f"action_{i}", f"tpl_{i % 100}", "user_1", {})

        # Should be capped at 10000
        all_logs = logger.get_logs(limit=20000)
        assert len(all_logs) <= 10000


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
