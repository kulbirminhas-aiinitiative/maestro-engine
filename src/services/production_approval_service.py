"""
Production Approval Workflow Service.

This service manages approval workflows for production deployments,
supporting multiple approvers, timeout handling, and audit trails.

Implements MD-1810: Production Approval Workflow
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

try:
    from prometheus_client import Counter, Gauge, Histogram
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalDecision(Enum):
    """Individual approver decision."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ABSTAINED = "abstained"


class ApprovalStrategy(Enum):
    """Strategy for determining approval outcome."""
    ALL_REQUIRED = "all_required"  # All approvers must approve
    MAJORITY = "majority"  # Majority must approve
    ANY_ONE = "any_one"  # Any single approver can approve
    QUORUM = "quorum"  # Minimum number required


@dataclass
class Approver:
    """An individual approver."""
    user_id: str
    email: str
    display_name: str
    role: Optional[str] = None
    decision: ApprovalDecision = ApprovalDecision.PENDING
    decided_at: Optional[datetime] = None
    comment: Optional[str] = None


@dataclass
class ApprovalConfig:
    """Configuration for approval workflow."""
    required_approvers: List[str]  # User IDs of required approvers
    strategy: ApprovalStrategy = ApprovalStrategy.ALL_REQUIRED
    quorum_count: int = 1  # For QUORUM strategy
    timeout_hours: int = 24
    allow_self_approval: bool = False
    auto_expire_on_timeout: bool = True
    require_comment_on_reject: bool = True
    notification_channels: List[str] = field(default_factory=list)


@dataclass
class ApprovalRequest:
    """A production deployment approval request."""
    request_id: str
    deployment_id: str
    service_name: str
    environment: str
    version: str
    requested_by: str
    requested_at: datetime
    config: ApprovalConfig
    status: ApprovalStatus = ApprovalStatus.PENDING
    approvers: List[Approver] = field(default_factory=list)
    expires_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    final_decision: Optional[ApprovalDecision] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalAuditEntry:
    """Audit entry for approval actions."""
    entry_id: str
    request_id: str
    action: str
    actor: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)


class ProductionApprovalService:
    """
    Service for managing production deployment approval workflows.

    Features:
    - Create approval request flow
    - Support multiple approvers
    - Handle approval timeout
    - Maintain audit trail for approvals
    """

    _instance: Optional["ProductionApprovalService"] = None

    def __new__(cls) -> "ProductionApprovalService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._requests: Dict[str, ApprovalRequest] = {}
        self._audit_log: List[ApprovalAuditEntry] = []
        self._notification_handlers: List[Callable[[ApprovalRequest, str], None]] = []
        self._approver_resolver: Optional[Callable[[str], Approver]] = None
        self._default_config: Optional[ApprovalConfig] = None

        # Prometheus metrics
        if PROMETHEUS_AVAILABLE:
            self._approval_requests_counter = Counter(
                "approval_requests_total",
                "Total number of approval requests",
                ["service", "environment", "status"]
            )
            self._approval_time_histogram = Histogram(
                "approval_time_seconds",
                "Time taken for approval decisions",
                ["service", "environment", "decision"]
            )
            self._pending_approvals_gauge = Gauge(
                "pending_approvals",
                "Number of pending approval requests",
                ["service", "environment"]
            )

        self._initialized = True
        logger.info("ProductionApprovalService initialized")

    def configure_default(self, config: ApprovalConfig) -> None:
        """
        Set default approval configuration.

        Args:
            config: Default configuration to use
        """
        self._default_config = config
        logger.info(f"Default approval config set: strategy={config.strategy.value}")

    def register_notification_handler(
        self,
        handler: Callable[[ApprovalRequest, str], None]
    ) -> None:
        """
        Register a handler for approval notifications.

        Args:
            handler: Callback function(request, action) for notifications
        """
        self._notification_handlers.append(handler)
        logger.info(f"Notification handler registered. Total: {len(self._notification_handlers)}")

    def register_approver_resolver(
        self,
        resolver: Callable[[str], Approver]
    ) -> None:
        """
        Register a function to resolve approver details from user ID.

        Args:
            resolver: Function(user_id) -> Approver
        """
        self._approver_resolver = resolver
        logger.info("Approver resolver registered")

    def create_request(
        self,
        deployment_id: str,
        service_name: str,
        environment: str,
        version: str,
        requested_by: str,
        config: Optional[ApprovalConfig] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ApprovalRequest:
        """
        Create a new approval request.

        Args:
            deployment_id: ID of the deployment requiring approval
            service_name: Name of the service being deployed
            environment: Target environment (should be production)
            version: Version being deployed
            requested_by: User ID of requester
            config: Approval configuration (uses default if not provided)
            metadata: Additional metadata

        Returns:
            Created ApprovalRequest
        """
        effective_config = config or self._default_config
        if not effective_config:
            raise ValueError("No approval configuration provided and no default set")

        # Check self-approval
        if not effective_config.allow_self_approval:
            if requested_by in effective_config.required_approvers:
                raise ValueError(
                    f"Self-approval not allowed: {requested_by} cannot approve their own deployment"
                )

        # Resolve approvers
        approvers = []
        for user_id in effective_config.required_approvers:
            if self._approver_resolver:
                approver = self._approver_resolver(user_id)
            else:
                approver = Approver(
                    user_id=user_id,
                    email=f"{user_id}@example.com",
                    display_name=user_id,
                )
            approvers.append(approver)

        request = ApprovalRequest(
            request_id=str(uuid4()),
            deployment_id=deployment_id,
            service_name=service_name,
            environment=environment,
            version=version,
            requested_by=requested_by,
            requested_at=datetime.utcnow(),
            config=effective_config,
            approvers=approvers,
            expires_at=datetime.utcnow() + timedelta(hours=effective_config.timeout_hours),
            metadata=metadata or {},
        )

        self._requests[request.request_id] = request

        # Log audit entry
        self._log_audit(
            request_id=request.request_id,
            action="request_created",
            actor=requested_by,
            details={
                "deployment_id": deployment_id,
                "service": service_name,
                "environment": environment,
                "version": version,
                "approvers": [a.user_id for a in approvers],
            },
        )

        # Update metrics
        if PROMETHEUS_AVAILABLE:
            self._approval_requests_counter.labels(
                service=service_name,
                environment=environment,
                status="pending"
            ).inc()
            self._pending_approvals_gauge.labels(
                service=service_name,
                environment=environment
            ).inc()

        # Send notifications
        self._send_notifications(request, "request_created")

        logger.info(
            f"Approval request created: {request.request_id} for "
            f"{service_name} v{version} to {environment}"
        )

        return request

    def submit_decision(
        self,
        request_id: str,
        approver_id: str,
        decision: ApprovalDecision,
        comment: Optional[str] = None,
    ) -> ApprovalRequest:
        """
        Submit an approval decision.

        Args:
            request_id: ID of the approval request
            approver_id: User ID of the approver
            decision: The decision (approved, rejected, abstained)
            comment: Optional comment (required for rejection if configured)

        Returns:
            Updated ApprovalRequest

        Raises:
            ValueError: If request not found, approver not valid, or invalid state
        """
        if request_id not in self._requests:
            raise ValueError(f"Approval request not found: {request_id}")

        request = self._requests[request_id]

        # Check request status
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(
                f"Cannot submit decision: request status is {request.status.value}"
            )

        # Check expiration
        if request.expires_at and datetime.utcnow() > request.expires_at:
            self._handle_expiration(request)
            raise ValueError("Approval request has expired")

        # Find approver
        approver = None
        for a in request.approvers:
            if a.user_id == approver_id:
                approver = a
                break

        if not approver:
            raise ValueError(f"User {approver_id} is not an approver for this request")

        if approver.decision != ApprovalDecision.PENDING:
            raise ValueError(f"User {approver_id} has already submitted a decision")

        # Check comment requirement
        if (
            decision == ApprovalDecision.REJECTED
            and request.config.require_comment_on_reject
            and not comment
        ):
            raise ValueError("Comment is required when rejecting")

        # Record decision
        approver.decision = decision
        approver.decided_at = datetime.utcnow()
        approver.comment = comment

        # Log audit entry
        self._log_audit(
            request_id=request_id,
            action="decision_submitted",
            actor=approver_id,
            details={
                "decision": decision.value,
                "comment": comment,
            },
        )

        # Evaluate overall status
        self._evaluate_request(request)

        # Send notifications
        self._send_notifications(request, f"decision_{decision.value}")

        logger.info(
            f"Decision submitted for {request_id}: {approver_id} -> {decision.value}"
        )

        return request

    def _evaluate_request(self, request: ApprovalRequest) -> None:
        """Evaluate the overall status of a request based on decisions."""
        strategy = request.config.strategy
        approvers = request.approvers

        approved_count = sum(1 for a in approvers if a.decision == ApprovalDecision.APPROVED)
        rejected_count = sum(1 for a in approvers if a.decision == ApprovalDecision.REJECTED)
        pending_count = sum(1 for a in approvers if a.decision == ApprovalDecision.PENDING)
        total_count = len(approvers)

        if strategy == ApprovalStrategy.ALL_REQUIRED:
            # All must approve, any rejection fails
            if rejected_count > 0:
                self._complete_request(request, ApprovalStatus.REJECTED)
            elif approved_count == total_count:
                self._complete_request(request, ApprovalStatus.APPROVED)

        elif strategy == ApprovalStrategy.MAJORITY:
            # Majority must approve
            majority = total_count // 2 + 1
            if approved_count >= majority:
                self._complete_request(request, ApprovalStatus.APPROVED)
            elif rejected_count > total_count - majority:
                self._complete_request(request, ApprovalStatus.REJECTED)

        elif strategy == ApprovalStrategy.ANY_ONE:
            # Any single approval or rejection
            if approved_count > 0:
                self._complete_request(request, ApprovalStatus.APPROVED)
            elif rejected_count > 0:
                self._complete_request(request, ApprovalStatus.REJECTED)

        elif strategy == ApprovalStrategy.QUORUM:
            # Need quorum_count approvals
            quorum = request.config.quorum_count
            if approved_count >= quorum:
                self._complete_request(request, ApprovalStatus.APPROVED)
            elif rejected_count > total_count - quorum:
                self._complete_request(request, ApprovalStatus.REJECTED)

    def _complete_request(
        self,
        request: ApprovalRequest,
        status: ApprovalStatus,
    ) -> None:
        """Mark a request as completed."""
        request.status = status
        request.completed_at = datetime.utcnow()
        request.final_decision = (
            ApprovalDecision.APPROVED if status == ApprovalStatus.APPROVED
            else ApprovalDecision.REJECTED
        )

        # Log audit entry
        self._log_audit(
            request_id=request.request_id,
            action="request_completed",
            actor="system",
            details={
                "status": status.value,
                "final_decision": request.final_decision.value if request.final_decision else None,
            },
        )

        # Update metrics
        if PROMETHEUS_AVAILABLE:
            self._approval_requests_counter.labels(
                service=request.service_name,
                environment=request.environment,
                status=status.value
            ).inc()
            self._pending_approvals_gauge.labels(
                service=request.service_name,
                environment=request.environment
            ).dec()

            duration = (request.completed_at - request.requested_at).total_seconds()
            self._approval_time_histogram.labels(
                service=request.service_name,
                environment=request.environment,
                decision=status.value
            ).observe(duration)

        # Send notifications
        self._send_notifications(request, f"request_{status.value}")

        logger.info(f"Request {request.request_id} completed with status: {status.value}")

    def _handle_expiration(self, request: ApprovalRequest) -> None:
        """Handle an expired request."""
        if request.config.auto_expire_on_timeout:
            request.status = ApprovalStatus.EXPIRED
            request.completed_at = datetime.utcnow()

            self._log_audit(
                request_id=request.request_id,
                action="request_expired",
                actor="system",
                details={"expires_at": request.expires_at.isoformat() if request.expires_at else None},
            )

            # Update metrics
            if PROMETHEUS_AVAILABLE:
                self._pending_approvals_gauge.labels(
                    service=request.service_name,
                    environment=request.environment
                ).dec()

            self._send_notifications(request, "request_expired")
            logger.warning(f"Request {request.request_id} expired")

    def cancel_request(
        self,
        request_id: str,
        cancelled_by: str,
        reason: Optional[str] = None,
    ) -> ApprovalRequest:
        """
        Cancel an approval request.

        Args:
            request_id: ID of the request to cancel
            cancelled_by: User ID of person cancelling
            reason: Optional reason for cancellation

        Returns:
            Updated ApprovalRequest
        """
        if request_id not in self._requests:
            raise ValueError(f"Approval request not found: {request_id}")

        request = self._requests[request_id]

        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot cancel: request status is {request.status.value}")

        request.status = ApprovalStatus.CANCELLED
        request.completed_at = datetime.utcnow()

        self._log_audit(
            request_id=request_id,
            action="request_cancelled",
            actor=cancelled_by,
            details={"reason": reason},
        )

        # Update metrics
        if PROMETHEUS_AVAILABLE:
            self._pending_approvals_gauge.labels(
                service=request.service_name,
                environment=request.environment
            ).dec()

        self._send_notifications(request, "request_cancelled")
        logger.info(f"Request {request_id} cancelled by {cancelled_by}")

        return request

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID."""
        return self._requests.get(request_id)

    def get_pending_requests(
        self,
        service_name: Optional[str] = None,
        environment: Optional[str] = None,
        approver_id: Optional[str] = None,
    ) -> List[ApprovalRequest]:
        """
        Get pending approval requests with optional filters.

        Args:
            service_name: Filter by service name
            environment: Filter by environment
            approver_id: Filter by approver user ID

        Returns:
            List of pending ApprovalRequests
        """
        requests = [r for r in self._requests.values() if r.status == ApprovalStatus.PENDING]

        if service_name:
            requests = [r for r in requests if r.service_name == service_name]

        if environment:
            requests = [r for r in requests if r.environment == environment]

        if approver_id:
            requests = [
                r for r in requests
                if any(a.user_id == approver_id and a.decision == ApprovalDecision.PENDING
                       for a in r.approvers)
            ]

        return sorted(requests, key=lambda r: r.requested_at, reverse=True)

    def get_requests_by_status(
        self,
        status: ApprovalStatus,
        limit: int = 100,
    ) -> List[ApprovalRequest]:
        """Get requests by status."""
        requests = [r for r in self._requests.values() if r.status == status]
        return sorted(requests, key=lambda r: r.requested_at, reverse=True)[:limit]

    def check_expired_requests(self) -> List[ApprovalRequest]:
        """
        Check for and handle expired requests.

        Returns:
            List of requests that were expired
        """
        now = datetime.utcnow()
        expired = []

        for request in list(self._requests.values()):
            if request.status == ApprovalStatus.PENDING:
                if request.expires_at and now > request.expires_at:
                    self._handle_expiration(request)
                    expired.append(request)

        return expired

    def get_audit_trail(
        self,
        request_id: Optional[str] = None,
        actor: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[ApprovalAuditEntry]:
        """
        Get audit trail entries with optional filters.

        Args:
            request_id: Filter by request ID
            actor: Filter by actor
            since: Only entries after this time
            limit: Maximum entries to return

        Returns:
            List of audit entries
        """
        entries = self._audit_log

        if request_id:
            entries = [e for e in entries if e.request_id == request_id]

        if actor:
            entries = [e for e in entries if e.actor == actor]

        if since:
            entries = [e for e in entries if e.timestamp >= since]

        return sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_statistics(
        self,
        service_name: Optional[str] = None,
        environment: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get approval workflow statistics.

        Args:
            service_name: Filter by service name
            environment: Filter by environment
            since: Only include requests after this time

        Returns:
            Statistics dictionary
        """
        requests = list(self._requests.values())

        if service_name:
            requests = [r for r in requests if r.service_name == service_name]

        if environment:
            requests = [r for r in requests if r.environment == environment]

        if since:
            requests = [r for r in requests if r.requested_at >= since]

        if not requests:
            return {
                "total_requests": 0,
                "pending": 0,
                "approved": 0,
                "rejected": 0,
                "expired": 0,
                "cancelled": 0,
                "approval_rate": 0.0,
                "avg_time_to_decision_hours": None,
            }

        by_status = {}
        for r in requests:
            status = r.status.value
            by_status[status] = by_status.get(status, 0) + 1

        # Calculate average time to decision
        completed = [r for r in requests if r.completed_at]
        if completed:
            durations = [
                (r.completed_at - r.requested_at).total_seconds() / 3600
                for r in completed
            ]
            avg_time = sum(durations) / len(durations)
        else:
            avg_time = None

        approved = by_status.get("approved", 0)
        rejected = by_status.get("rejected", 0)
        decided = approved + rejected

        return {
            "total_requests": len(requests),
            "pending": by_status.get("pending", 0),
            "approved": approved,
            "rejected": rejected,
            "expired": by_status.get("expired", 0),
            "cancelled": by_status.get("cancelled", 0),
            "approval_rate": approved / decided if decided > 0 else 0.0,
            "avg_time_to_decision_hours": avg_time,
        }

    def _log_audit(
        self,
        request_id: str,
        action: str,
        actor: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> ApprovalAuditEntry:
        """Log an audit entry."""
        entry = ApprovalAuditEntry(
            entry_id=str(uuid4()),
            request_id=request_id,
            action=action,
            actor=actor,
            timestamp=datetime.utcnow(),
            details=details or {},
        )
        self._audit_log.append(entry)
        return entry

    def _send_notifications(self, request: ApprovalRequest, action: str) -> None:
        """Send notifications to all registered handlers."""
        for handler in self._notification_handlers:
            try:
                handler(request, action)
            except Exception as e:
                logger.exception(f"Notification handler failed: {e}")

    def reset(self) -> None:
        """Reset the service state (for testing)."""
        self._requests.clear()
        self._audit_log.clear()
        self._notification_handlers.clear()
        self._approver_resolver = None
        self._default_config = None
        logger.info("ProductionApprovalService reset")


# Singleton instance
_production_approval_service: Optional[ProductionApprovalService] = None


def get_production_approval_service() -> ProductionApprovalService:
    """Get the singleton ProductionApprovalService instance."""
    global _production_approval_service
    if _production_approval_service is None:
        _production_approval_service = ProductionApprovalService()
    return _production_approval_service
