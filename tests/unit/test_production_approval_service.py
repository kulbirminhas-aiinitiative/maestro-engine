"""
Unit tests for ProductionApprovalService.

Tests cover:
- Approval request creation
- Decision submission
- Approval strategies (all required, majority, any one, quorum)
- Timeout handling
- Audit trail
- Statistics
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import pytest

from src.services.production_approval_service import (
    ApprovalConfig,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStrategy,
    Approver,
    ProductionApprovalService,
    get_production_approval_service,
)


@pytest.fixture
def service():
    """Create a fresh ProductionApprovalService instance for testing."""
    svc = ProductionApprovalService()
    svc.reset()
    return svc


@pytest.fixture
def sample_config():
    """Sample approval configuration."""
    return ApprovalConfig(
        required_approvers=["approver1", "approver2", "approver3"],
        strategy=ApprovalStrategy.ALL_REQUIRED,
        timeout_hours=24,
        allow_self_approval=False,
        require_comment_on_reject=True,
    )


@pytest.fixture
def majority_config():
    """Majority approval configuration."""
    return ApprovalConfig(
        required_approvers=["approver1", "approver2", "approver3"],
        strategy=ApprovalStrategy.MAJORITY,
        timeout_hours=24,
    )


@pytest.fixture
def any_one_config():
    """Any one approval configuration."""
    return ApprovalConfig(
        required_approvers=["approver1", "approver2", "approver3"],
        strategy=ApprovalStrategy.ANY_ONE,
        timeout_hours=24,
    )


@pytest.fixture
def quorum_config():
    """Quorum approval configuration."""
    return ApprovalConfig(
        required_approvers=["approver1", "approver2", "approver3", "approver4"],
        strategy=ApprovalStrategy.QUORUM,
        quorum_count=2,
        timeout_hours=24,
    )


@pytest.fixture
def sample_request(service, sample_config):
    """Create a sample approval request."""
    return service.create_request(
        deployment_id="deploy-001",
        service_name="api-service",
        environment="production",
        version="2.0.0",
        requested_by="developer1",
        config=sample_config,
    )


class TestApprovalConfig:
    """Tests for ApprovalConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ApprovalConfig(required_approvers=["user1"])
        assert config.strategy == ApprovalStrategy.ALL_REQUIRED
        assert config.timeout_hours == 24
        assert config.allow_self_approval is False
        assert config.require_comment_on_reject is True

    def test_custom_values(self, sample_config):
        """Test custom configuration values."""
        assert len(sample_config.required_approvers) == 3
        assert sample_config.strategy == ApprovalStrategy.ALL_REQUIRED


class TestRequestCreation:
    """Tests for approval request creation."""

    def test_create_request_success(self, service, sample_config):
        """Test creating an approval request."""
        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=sample_config,
        )

        assert isinstance(request, ApprovalRequest)
        assert request.deployment_id == "deploy-001"
        assert request.service_name == "api-service"
        assert request.environment == "production"
        assert request.version == "2.0.0"
        assert request.requested_by == "developer1"
        assert request.status == ApprovalStatus.PENDING
        assert len(request.approvers) == 3

    def test_create_request_with_default_config(self, service, sample_config):
        """Test creating request with default configuration."""
        service.configure_default(sample_config)

        request = service.create_request(
            deployment_id="deploy-002",
            service_name="web-service",
            environment="production",
            version="1.0.0",
            requested_by="developer2",
        )

        assert request.config.strategy == ApprovalStrategy.ALL_REQUIRED

    def test_create_request_no_config(self, service):
        """Test creating request without configuration raises error."""
        with pytest.raises(ValueError, match="No approval configuration provided"):
            service.create_request(
                deployment_id="deploy-001",
                service_name="api-service",
                environment="production",
                version="2.0.0",
                requested_by="developer1",
            )

    def test_create_request_self_approval_blocked(self, service, sample_config):
        """Test self-approval is blocked when not allowed."""
        with pytest.raises(ValueError, match="Self-approval not allowed"):
            service.create_request(
                deployment_id="deploy-001",
                service_name="api-service",
                environment="production",
                version="2.0.0",
                requested_by="approver1",  # Requester is an approver
                config=sample_config,
            )

    def test_create_request_self_approval_allowed(self, service):
        """Test self-approval when allowed."""
        config = ApprovalConfig(
            required_approvers=["approver1"],
            allow_self_approval=True,
        )

        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="approver1",
            config=config,
        )

        assert request is not None

    def test_create_request_with_metadata(self, service, sample_config):
        """Test creating request with metadata."""
        metadata = {"ticket": "JIRA-123", "reason": "Critical fix"}

        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=sample_config,
            metadata=metadata,
        )

        assert request.metadata == metadata

    def test_create_request_sets_expiration(self, service, sample_config):
        """Test that expiration is set correctly."""
        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=sample_config,
        )

        assert request.expires_at is not None
        expected_expiry = request.requested_at + timedelta(hours=24)
        assert abs((request.expires_at - expected_expiry).total_seconds()) < 1


class TestDecisionSubmission:
    """Tests for decision submission."""

    def test_submit_approval(self, service, sample_request):
        """Test submitting an approval decision."""
        request = service.submit_decision(
            request_id=sample_request.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.APPROVED,
        )

        approver = next(a for a in request.approvers if a.user_id == "approver1")
        assert approver.decision == ApprovalDecision.APPROVED
        assert approver.decided_at is not None

    def test_submit_rejection_with_comment(self, service, sample_request):
        """Test submitting a rejection with comment."""
        request = service.submit_decision(
            request_id=sample_request.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.REJECTED,
            comment="Security concerns",
        )

        approver = next(a for a in request.approvers if a.user_id == "approver1")
        assert approver.decision == ApprovalDecision.REJECTED
        assert approver.comment == "Security concerns"

    def test_submit_rejection_without_comment_fails(self, service, sample_request):
        """Test rejection without required comment fails."""
        with pytest.raises(ValueError, match="Comment is required when rejecting"):
            service.submit_decision(
                request_id=sample_request.request_id,
                approver_id="approver1",
                decision=ApprovalDecision.REJECTED,
            )

    def test_submit_decision_not_found(self, service):
        """Test submitting decision for non-existent request."""
        with pytest.raises(ValueError, match="Approval request not found"):
            service.submit_decision(
                request_id="nonexistent",
                approver_id="approver1",
                decision=ApprovalDecision.APPROVED,
            )

    def test_submit_decision_invalid_approver(self, service, sample_request):
        """Test submitting decision by non-approver fails."""
        with pytest.raises(ValueError, match="is not an approver"):
            service.submit_decision(
                request_id=sample_request.request_id,
                approver_id="random_user",
                decision=ApprovalDecision.APPROVED,
            )

    def test_submit_decision_twice_fails(self, service, sample_request):
        """Test submitting decision twice fails."""
        service.submit_decision(
            request_id=sample_request.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.APPROVED,
        )

        with pytest.raises(ValueError, match="has already submitted a decision"):
            service.submit_decision(
                request_id=sample_request.request_id,
                approver_id="approver1",
                decision=ApprovalDecision.APPROVED,
            )


class TestAllRequiredStrategy:
    """Tests for ALL_REQUIRED approval strategy."""

    def test_all_approved(self, service, sample_config):
        """Test request is approved when all approve."""
        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=sample_config,
        )

        for approver_id in ["approver1", "approver2", "approver3"]:
            request = service.submit_decision(
                request_id=request.request_id,
                approver_id=approver_id,
                decision=ApprovalDecision.APPROVED,
            )

        assert request.status == ApprovalStatus.APPROVED
        assert request.final_decision == ApprovalDecision.APPROVED

    def test_one_rejection_fails(self, service, sample_config):
        """Test request is rejected when any approver rejects."""
        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=sample_config,
        )

        service.submit_decision(
            request_id=request.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.APPROVED,
        )

        request = service.submit_decision(
            request_id=request.request_id,
            approver_id="approver2",
            decision=ApprovalDecision.REJECTED,
            comment="Not ready",
        )

        assert request.status == ApprovalStatus.REJECTED


class TestMajorityStrategy:
    """Tests for MAJORITY approval strategy."""

    def test_majority_approved(self, service, majority_config):
        """Test request is approved when majority approves."""
        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=majority_config,
        )

        # 2 out of 3 approve (majority)
        service.submit_decision(
            request_id=request.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.APPROVED,
        )
        request = service.submit_decision(
            request_id=request.request_id,
            approver_id="approver2",
            decision=ApprovalDecision.APPROVED,
        )

        assert request.status == ApprovalStatus.APPROVED

    def test_majority_rejected(self, service, majority_config):
        """Test request is rejected when majority rejects."""
        majority_config.require_comment_on_reject = False
        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=majority_config,
        )

        # 2 out of 3 reject (majority)
        service.submit_decision(
            request_id=request.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.REJECTED,
        )
        request = service.submit_decision(
            request_id=request.request_id,
            approver_id="approver2",
            decision=ApprovalDecision.REJECTED,
        )

        assert request.status == ApprovalStatus.REJECTED


class TestAnyOneStrategy:
    """Tests for ANY_ONE approval strategy."""

    def test_single_approval_succeeds(self, service, any_one_config):
        """Test request is approved when any one approves."""
        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=any_one_config,
        )

        request = service.submit_decision(
            request_id=request.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.APPROVED,
        )

        assert request.status == ApprovalStatus.APPROVED

    def test_single_rejection_fails(self, service, any_one_config):
        """Test request is rejected when any one rejects."""
        any_one_config.require_comment_on_reject = False
        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=any_one_config,
        )

        request = service.submit_decision(
            request_id=request.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.REJECTED,
        )

        assert request.status == ApprovalStatus.REJECTED


class TestQuorumStrategy:
    """Tests for QUORUM approval strategy."""

    def test_quorum_met(self, service, quorum_config):
        """Test request is approved when quorum is met."""
        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=quorum_config,
        )

        # 2 approvals meet quorum of 2
        service.submit_decision(
            request_id=request.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.APPROVED,
        )
        request = service.submit_decision(
            request_id=request.request_id,
            approver_id="approver2",
            decision=ApprovalDecision.APPROVED,
        )

        assert request.status == ApprovalStatus.APPROVED

    def test_quorum_cannot_be_met_rejects(self, service, quorum_config):
        """Test request is rejected when quorum cannot be met."""
        quorum_config.require_comment_on_reject = False
        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=quorum_config,
        )

        # 3 rejections make quorum impossible (4 - 3 = 1 < 2)
        for approver_id in ["approver1", "approver2", "approver3"]:
            request = service.submit_decision(
                request_id=request.request_id,
                approver_id=approver_id,
                decision=ApprovalDecision.REJECTED,
            )

        assert request.status == ApprovalStatus.REJECTED


class TestTimeoutHandling:
    """Tests for timeout handling."""

    def test_expired_request_cannot_be_decided(self, service, sample_config):
        """Test that expired requests cannot receive decisions."""
        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=sample_config,
        )

        # Manually expire the request
        request.expires_at = datetime.utcnow() - timedelta(hours=1)

        with pytest.raises(ValueError, match="Approval request has expired"):
            service.submit_decision(
                request_id=request.request_id,
                approver_id="approver1",
                decision=ApprovalDecision.APPROVED,
            )

    def test_check_expired_requests(self, service, sample_config):
        """Test checking for expired requests."""
        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=sample_config,
        )

        # Manually expire the request
        request.expires_at = datetime.utcnow() - timedelta(hours=1)

        expired = service.check_expired_requests()

        assert len(expired) == 1
        assert expired[0].status == ApprovalStatus.EXPIRED


class TestCancellation:
    """Tests for request cancellation."""

    def test_cancel_request(self, service, sample_request):
        """Test cancelling a request."""
        request = service.cancel_request(
            request_id=sample_request.request_id,
            cancelled_by="developer1",
            reason="Deployment no longer needed",
        )

        assert request.status == ApprovalStatus.CANCELLED
        assert request.completed_at is not None

    def test_cancel_completed_request_fails(self, service, sample_config):
        """Test cancelling a completed request fails."""
        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=ApprovalConfig(
                required_approvers=["approver1"],
                strategy=ApprovalStrategy.ANY_ONE,
            ),
        )

        # Complete the request
        service.submit_decision(
            request_id=request.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.APPROVED,
        )

        with pytest.raises(ValueError, match="Cannot cancel"):
            service.cancel_request(
                request_id=request.request_id,
                cancelled_by="developer1",
            )


class TestQueryMethods:
    """Tests for query methods."""

    def test_get_request(self, service, sample_request):
        """Test getting a request by ID."""
        request = service.get_request(sample_request.request_id)
        assert request == sample_request

    def test_get_request_not_found(self, service):
        """Test getting non-existent request."""
        request = service.get_request("nonexistent")
        assert request is None

    def test_get_pending_requests(self, service, sample_config):
        """Test getting pending requests."""
        service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=sample_config,
        )
        service.create_request(
            deployment_id="deploy-002",
            service_name="web-service",
            environment="staging",
            version="1.0.0",
            requested_by="developer1",
            config=sample_config,
        )

        pending = service.get_pending_requests()
        assert len(pending) == 2

    def test_get_pending_requests_filter_by_service(self, service, sample_config):
        """Test filtering pending requests by service."""
        service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=sample_config,
        )
        service.create_request(
            deployment_id="deploy-002",
            service_name="web-service",
            environment="production",
            version="1.0.0",
            requested_by="developer1",
            config=sample_config,
        )

        pending = service.get_pending_requests(service_name="api-service")
        assert len(pending) == 1
        assert pending[0].service_name == "api-service"

    def test_get_pending_requests_filter_by_approver(self, service, sample_config):
        """Test filtering pending requests by approver."""
        service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=sample_config,
        )

        pending = service.get_pending_requests(approver_id="approver1")
        assert len(pending) == 1

        # Submit decision
        service.submit_decision(
            request_id=pending[0].request_id,
            approver_id="approver1",
            decision=ApprovalDecision.APPROVED,
        )

        # Now approver1 shouldn't have pending requests
        pending = service.get_pending_requests(approver_id="approver1")
        assert len(pending) == 0

    def test_get_requests_by_status(self, service, sample_config):
        """Test getting requests by status."""
        # Create and approve a request
        config = ApprovalConfig(
            required_approvers=["approver1"],
            strategy=ApprovalStrategy.ANY_ONE,
        )
        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=config,
        )
        service.submit_decision(
            request_id=request.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.APPROVED,
        )

        approved = service.get_requests_by_status(ApprovalStatus.APPROVED)
        assert len(approved) == 1


class TestAuditTrail:
    """Tests for audit trail."""

    def test_audit_trail_on_create(self, service, sample_config):
        """Test audit entry is created on request creation."""
        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=sample_config,
        )

        audit = service.get_audit_trail(request_id=request.request_id)
        assert len(audit) == 1
        assert audit[0].action == "request_created"
        assert audit[0].actor == "developer1"

    def test_audit_trail_on_decision(self, service, sample_request):
        """Test audit entry is created on decision."""
        service.submit_decision(
            request_id=sample_request.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.APPROVED,
        )

        audit = service.get_audit_trail(request_id=sample_request.request_id)
        assert len(audit) == 2  # create + decision
        assert any(e.action == "decision_submitted" for e in audit)

    def test_audit_trail_filter_by_actor(self, service, sample_request):
        """Test filtering audit trail by actor."""
        service.submit_decision(
            request_id=sample_request.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.APPROVED,
        )

        audit = service.get_audit_trail(actor="approver1")
        assert len(audit) == 1
        assert audit[0].actor == "approver1"


class TestStatistics:
    """Tests for statistics."""

    def test_statistics_empty(self, service):
        """Test statistics with no requests."""
        stats = service.get_statistics()
        assert stats["total_requests"] == 0
        assert stats["approval_rate"] == 0.0

    def test_statistics_with_data(self, service):
        """Test statistics with requests."""
        config = ApprovalConfig(
            required_approvers=["approver1"],
            strategy=ApprovalStrategy.ANY_ONE,
        )

        # Create and approve a request
        request1 = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=config,
        )
        service.submit_decision(
            request_id=request1.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.APPROVED,
        )

        # Create and reject a request
        config.require_comment_on_reject = False
        request2 = service.create_request(
            deployment_id="deploy-002",
            service_name="api-service",
            environment="production",
            version="3.0.0",
            requested_by="developer1",
            config=config,
        )
        service.submit_decision(
            request_id=request2.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.REJECTED,
        )

        stats = service.get_statistics()
        assert stats["total_requests"] == 2
        assert stats["approved"] == 1
        assert stats["rejected"] == 1
        assert stats["approval_rate"] == 0.5

    def test_statistics_filter_by_service(self, service):
        """Test statistics filtered by service."""
        config = ApprovalConfig(
            required_approvers=["approver1"],
            strategy=ApprovalStrategy.ANY_ONE,
        )

        for service_name in ["api-service", "web-service"]:
            request = service.create_request(
                deployment_id=f"deploy-{service_name}",
                service_name=service_name,
                environment="production",
                version="1.0.0",
                requested_by="developer1",
                config=config,
            )
            service.submit_decision(
                request_id=request.request_id,
                approver_id="approver1",
                decision=ApprovalDecision.APPROVED,
            )

        stats = service.get_statistics(service_name="api-service")
        assert stats["total_requests"] == 1


class TestNotifications:
    """Tests for notification handling."""

    def test_notification_on_create(self, service, sample_config):
        """Test notification is sent on request creation."""
        handler = MagicMock()
        service.register_notification_handler(handler)

        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=sample_config,
        )

        handler.assert_called_once()
        call_args = handler.call_args
        assert call_args[0][0] == request
        assert call_args[0][1] == "request_created"

    def test_notification_on_decision(self, service, sample_config):
        """Test notification is sent on decision."""
        handler = MagicMock()

        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=sample_config,
        )

        service.register_notification_handler(handler)

        service.submit_decision(
            request_id=request.request_id,
            approver_id="approver1",
            decision=ApprovalDecision.APPROVED,
        )

        assert handler.call_count == 1
        call_args = handler.call_args
        assert call_args[0][1] == "decision_approved"


class TestApproverResolver:
    """Tests for approver resolver."""

    def test_custom_approver_resolver(self, service, sample_config):
        """Test using custom approver resolver."""
        def resolver(user_id):
            return Approver(
                user_id=user_id,
                email=f"{user_id}@company.com",
                display_name=f"User {user_id}",
                role="Engineer",
            )

        service.register_approver_resolver(resolver)

        request = service.create_request(
            deployment_id="deploy-001",
            service_name="api-service",
            environment="production",
            version="2.0.0",
            requested_by="developer1",
            config=sample_config,
        )

        assert request.approvers[0].email == "approver1@company.com"
        assert request.approvers[0].role == "Engineer"


class TestSingletonPattern:
    """Tests for singleton pattern."""

    def test_singleton_instance(self):
        """Test that service is a singleton."""
        service1 = ProductionApprovalService()
        service2 = ProductionApprovalService()
        assert service1 is service2

    def test_get_service_function(self):
        """Test get_production_approval_service function."""
        service = get_production_approval_service()
        assert isinstance(service, ProductionApprovalService)


class TestReset:
    """Tests for service reset."""

    def test_reset_clears_state(self, service, sample_request):
        """Test reset clears all state."""
        handler = MagicMock()
        service.register_notification_handler(handler)

        service.reset()

        assert len(service._requests) == 0
        assert len(service._audit_log) == 0
        assert len(service._notification_handlers) == 0
