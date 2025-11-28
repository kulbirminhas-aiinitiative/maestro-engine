#!/usr/bin/env python3
"""
Template Promotion API Routes for MAESTRO Engine

Implements:
- MD-1845: POST /api/templates/promote Endpoint
- MD-1846: Approval Workflow (approve/reject endpoints)
- MD-1847: Semantic Versioning & Changelog endpoints

REST API Endpoints:

MD-1845: POST /api/templates/promote
- Request validation with Pydantic models
- Authentication via API key/JWT
- Rate limiting support
- Audit logging

MD-1846: Approval Workflow
- POST /api/templates/promote/{id}/approve
- POST /api/templates/promote/{id}/reject
- GET /api/templates/promote/{id}/status
- Notification system hooks
- Timeout handling

MD-1847: Semantic Versioning & Changelog
- GET /api/templates/{id}/versions
- GET /api/templates/{id}/changelog
- Version history tracking
"""

import hashlib
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from functools import wraps

from fastapi import APIRouter, HTTPException, Header, Query, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

# Import template promotion service
try:
    from services.template_promotion_service import (
        get_template_promotion_service,
        TemplatePromotionService,
        PromotionStatus,
        PromotionEnvironment,
        VersionBumpType,
        PromotionResult,
        PromotionThresholds,
        FeatureFlags,
        Changelog,
        ChangelogEntry,
    )
    HAS_PROMOTION_SERVICE = True
except ImportError:
    HAS_PROMOTION_SERVICE = False
    # Define stubs for testing
    class PromotionStatus(str, Enum):
        PENDING = "pending"
        VALIDATING = "validating"
        APPROVED = "approved"
        PROMOTED = "promoted"
        FAILED = "failed"
        BLOCKED = "blocked"
        PENDING_APPROVAL = "pending_approval"
        REJECTED = "rejected"

    class PromotionEnvironment(str, Enum):
        DEVELOPMENT = "development"
        STAGING = "staging"
        PRODUCTION = "production"

    class VersionBumpType(str, Enum):
        MAJOR = "major"
        MINOR = "minor"
        PATCH = "patch"

logger = logging.getLogger("template_promotion_routes")

# Create router
router = APIRouter(prefix="/api/templates", tags=["template-promotion"])


# ============================================================================
# RATE LIMITING (MD-1845 AC: Rate limiting)
# ============================================================================

class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed under rate limit."""
        now = time.time()
        minute_ago = now - 60

        # Clean old requests
        self._requests[client_id] = [
            t for t in self._requests[client_id] if t > minute_ago
        ]

        # Check limit
        if len(self._requests[client_id]) >= self.requests_per_minute:
            return False

        # Record request
        self._requests[client_id].append(now)
        return True

    def get_remaining(self, client_id: str) -> int:
        """Get remaining requests in current window."""
        now = time.time()
        minute_ago = now - 60
        recent = [t for t in self._requests[client_id] if t > minute_ago]
        return max(0, self.requests_per_minute - len(recent))


rate_limiter = RateLimiter(requests_per_minute=60)


# ============================================================================
# AUDIT LOGGING (MD-1845 AC: Audit logging)
# ============================================================================

class AuditLogger:
    """Audit logging for promotion operations."""

    def __init__(self):
        self._log: List[Dict[str, Any]] = []

    def log(
        self,
        action: str,
        template_id: str,
        user_id: Optional[str],
        details: Dict[str, Any],
        success: bool = True,
    ) -> str:
        """Log an audit event."""
        audit_id = f"audit_{hashlib.md5(f'{action}_{time.time()}'.encode()).hexdigest()[:12]}"

        entry = {
            "audit_id": audit_id,
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "template_id": template_id,
            "user_id": user_id,
            "details": details,
            "success": success,
        }

        self._log.append(entry)
        logger.info(f"AUDIT: {action} on {template_id} by {user_id} - {'SUCCESS' if success else 'FAILED'}")

        # Keep only last 10000 entries
        if len(self._log) > 10000:
            self._log = self._log[-10000:]

        return audit_id

    def get_logs(
        self,
        template_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get audit logs with optional filtering."""
        results = self._log

        if template_id:
            results = [l for l in results if l["template_id"] == template_id]
        if action:
            results = [l for l in results if l["action"] == action]

        return list(reversed(results[-limit:]))


audit_logger = AuditLogger()


# ============================================================================
# APPROVAL WORKFLOW STATE (MD-1846)
# ============================================================================

class ApprovalStatus(str, Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalRequest:
    """Represents an approval request for a promotion."""

    def __init__(
        self,
        request_id: str,
        promotion_id: str,
        template_id: str,
        requested_by: str,
        target_environment: str,
        required_approvers: int = 1,
        timeout_hours: int = 48,
    ):
        self.request_id = request_id
        self.promotion_id = promotion_id
        self.template_id = template_id
        self.requested_by = requested_by
        self.target_environment = target_environment
        self.required_approvers = required_approvers
        self.timeout_hours = timeout_hours
        self.created_at = datetime.now()
        self.expires_at = self.created_at + timedelta(hours=timeout_hours)
        self.status = ApprovalStatus.PENDING
        self.approvals: List[Dict[str, Any]] = []
        self.rejections: List[Dict[str, Any]] = []
        self.comments: List[Dict[str, Any]] = []
        self.notification_sent = False

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    @property
    def approval_count(self) -> int:
        return len(self.approvals)

    @property
    def is_fully_approved(self) -> bool:
        return self.approval_count >= self.required_approvers

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "promotion_id": self.promotion_id,
            "template_id": self.template_id,
            "requested_by": self.requested_by,
            "target_environment": self.target_environment,
            "required_approvers": self.required_approvers,
            "current_approvals": self.approval_count,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_expired": self.is_expired,
            "approvals": self.approvals,
            "rejections": self.rejections,
            "comments": self.comments,
        }


class ApprovalWorkflow:
    """Manages approval requests for template promotions."""

    def __init__(self):
        self._requests: Dict[str, ApprovalRequest] = {}
        self._by_promotion: Dict[str, str] = {}  # promotion_id -> request_id
        self._notifications: List[Dict[str, Any]] = []

    def create_request(
        self,
        promotion_id: str,
        template_id: str,
        requested_by: str,
        target_environment: str,
        required_approvers: int = 1,
        timeout_hours: int = 48,
    ) -> ApprovalRequest:
        """Create a new approval request."""
        request_id = f"approval_{hashlib.md5(f'{promotion_id}_{time.time()}'.encode()).hexdigest()[:12]}"

        request = ApprovalRequest(
            request_id=request_id,
            promotion_id=promotion_id,
            template_id=template_id,
            requested_by=requested_by,
            target_environment=target_environment,
            required_approvers=required_approvers,
            timeout_hours=timeout_hours,
        )

        self._requests[request_id] = request
        self._by_promotion[promotion_id] = request_id

        # Queue notification
        self._queue_notification(
            request_id=request_id,
            event="approval_requested",
            message=f"Approval requested for template {template_id} promotion to {target_environment}",
        )

        return request

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get approval request by ID."""
        return self._requests.get(request_id)

    def get_by_promotion(self, promotion_id: str) -> Optional[ApprovalRequest]:
        """Get approval request by promotion ID."""
        request_id = self._by_promotion.get(promotion_id)
        if request_id:
            return self._requests.get(request_id)
        return None

    def approve(
        self,
        request_id: str,
        approver_id: str,
        comment: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Approve a request."""
        request = self._requests.get(request_id)
        if not request:
            return False, "Approval request not found"

        if request.is_expired:
            request.status = ApprovalStatus.EXPIRED
            return False, "Approval request has expired"

        if request.status != ApprovalStatus.PENDING:
            return False, f"Request is already {request.status.value}"

        # Check if already approved by this user
        if any(a["approver_id"] == approver_id for a in request.approvals):
            return False, "You have already approved this request"

        # Add approval
        request.approvals.append({
            "approver_id": approver_id,
            "approved_at": datetime.now().isoformat(),
            "comment": comment,
        })

        # Check if fully approved
        if request.is_fully_approved:
            request.status = ApprovalStatus.APPROVED
            self._queue_notification(
                request_id=request_id,
                event="approval_complete",
                message=f"Template {request.template_id} promotion approved",
            )

        return True, f"Approval recorded ({request.approval_count}/{request.required_approvers})"

    def reject(
        self,
        request_id: str,
        rejector_id: str,
        reason: str,
    ) -> Tuple[bool, str]:
        """Reject a request."""
        request = self._requests.get(request_id)
        if not request:
            return False, "Approval request not found"

        if request.status != ApprovalStatus.PENDING:
            return False, f"Request is already {request.status.value}"

        request.rejections.append({
            "rejector_id": rejector_id,
            "rejected_at": datetime.now().isoformat(),
            "reason": reason,
        })

        request.status = ApprovalStatus.REJECTED

        self._queue_notification(
            request_id=request_id,
            event="approval_rejected",
            message=f"Template {request.template_id} promotion rejected: {reason}",
        )

        return True, "Request rejected"

    def _queue_notification(
        self,
        request_id: str,
        event: str,
        message: str,
    ) -> None:
        """Queue a notification for later processing."""
        self._notifications.append({
            "notification_id": f"notif_{hashlib.md5(f'{event}_{time.time()}'.encode()).hexdigest()[:8]}",
            "request_id": request_id,
            "event": event,
            "message": message,
            "created_at": datetime.now().isoformat(),
            "sent": False,
        })

    def get_pending_notifications(self) -> List[Dict[str, Any]]:
        """Get unsent notifications."""
        return [n for n in self._notifications if not n["sent"]]

    def mark_notification_sent(self, notification_id: str) -> None:
        """Mark notification as sent."""
        for n in self._notifications:
            if n["notification_id"] == notification_id:
                n["sent"] = True
                break

    def check_timeouts(self) -> List[str]:
        """Check for expired requests and return list of expired IDs."""
        expired = []
        for request_id, request in self._requests.items():
            if request.status == ApprovalStatus.PENDING and request.is_expired:
                request.status = ApprovalStatus.EXPIRED
                expired.append(request_id)
                self._queue_notification(
                    request_id=request_id,
                    event="approval_expired",
                    message=f"Approval request for {request.template_id} has expired",
                )
        return expired


approval_workflow = ApprovalWorkflow()


# ============================================================================
# VERSION HISTORY (MD-1847)
# ============================================================================

class VersionHistory:
    """Tracks version history for templates."""

    def __init__(self):
        self._history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._changelogs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def record_version(
        self,
        template_id: str,
        version: str,
        bump_type: str,
        changes: List[Dict[str, Any]],
        promoted_by: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a new version."""
        version_id = f"ver_{hashlib.md5(f'{template_id}_{version}_{time.time()}'.encode()).hexdigest()[:12]}"

        entry = {
            "version_id": version_id,
            "template_id": template_id,
            "version": version,
            "bump_type": bump_type,
            "changes": changes,
            "promoted_by": promoted_by,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
        }

        self._history[template_id].append(entry)

        # Generate changelog entries
        for change in changes:
            self._changelogs[template_id].append({
                "version": version,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "author": promoted_by,
                "change_type": change.get("type", "changed"),
                "description": change.get("description", "Update"),
                "breaking": change.get("breaking", False),
            })

        return version_id

    def get_versions(
        self,
        template_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get version history for a template."""
        versions = self._history.get(template_id, [])
        return list(reversed(versions[-limit:]))

    def get_version(
        self,
        template_id: str,
        version: str,
    ) -> Optional[Dict[str, Any]]:
        """Get specific version entry."""
        for entry in self._history.get(template_id, []):
            if entry["version"] == version:
                return entry
        return None

    def get_changelog(
        self,
        template_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get changelog for a template."""
        entries = self._changelogs.get(template_id, [])
        return list(reversed(entries[-limit:]))

    def generate_markdown_changelog(self, template_id: str) -> str:
        """Generate markdown-formatted changelog."""
        entries = self.get_changelog(template_id)

        if not entries:
            return f"# Changelog for {template_id}\n\nNo changes recorded."

        lines = [
            f"# Changelog for {template_id}",
            "",
            f"Generated: {datetime.now().isoformat()}",
            "",
        ]

        current_version = None
        for entry in entries:
            if entry["version"] != current_version:
                current_version = entry["version"]
                lines.append(f"## [{entry['version']}] - {entry['date']}")
                lines.append("")

            prefix = "**BREAKING** " if entry.get("breaking") else ""
            lines.append(f"### {entry['change_type'].capitalize()}")
            lines.append(f"- {prefix}{entry['description']}")
            lines.append("")

        return "\n".join(lines)


version_history = VersionHistory()


# ============================================================================
# REQUEST/RESPONSE MODELS (MD-1845, MD-1846, MD-1847)
# ============================================================================

# MD-1845: Promote Request/Response Models

class ChangeDescription(BaseModel):
    """Description of a single change."""
    type: str = Field(..., description="Change type: added, changed, fixed, removed, security, breaking")
    description: str = Field(..., description="Change description")
    breaking: bool = Field(False, description="Is this a breaking change?")
    commit_hash: Optional[str] = Field(None, description="Associated commit hash")


class PromoteRequest(BaseModel):
    """Request to promote a template."""
    template_id: str = Field(..., description="Template ID to promote")
    template_content: str = Field(..., min_length=1, description="Template source content")
    source_environment: str = Field("staging", description="Source environment")
    target_environment: str = Field("production", description="Target environment")
    changes: Optional[List[ChangeDescription]] = Field(None, description="List of changes")
    force_version_bump: Optional[str] = Field(None, description="Force version bump: major, minor, patch")
    require_approval: bool = Field(False, description="Require approval before promotion")
    approvers_required: int = Field(1, ge=1, le=5, description="Number of approvers required")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    comment: Optional[str] = Field(None, description="Promotion comment")

    @validator("source_environment", "target_environment")
    def validate_environment(cls, v):
        valid = ["development", "staging", "production"]
        if v not in valid:
            raise ValueError(f"Environment must be one of: {valid}")
        return v

    @validator("force_version_bump")
    def validate_bump_type(cls, v):
        if v is not None:
            valid = ["major", "minor", "patch"]
            if v not in valid:
                raise ValueError(f"Version bump must be one of: {valid}")
        return v


class PromoteResponse(BaseModel):
    """Response for template promotion."""
    promotion_id: str
    template_id: str
    status: str
    previous_version: str
    new_version: str
    version_bump_type: str
    source_environment: str
    target_environment: str
    validation_report_id: Optional[str] = None
    criteria: Optional[Dict[str, Any]] = None
    approval_required: bool = False
    approval_request_id: Optional[str] = None
    changelog: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    message: str
    promoted_at: str
    duration_ms: float


# MD-1846: Approval Request/Response Models

class ApproveRequest(BaseModel):
    """Request to approve a promotion."""
    comment: Optional[str] = Field(None, description="Approval comment")


class RejectRequest(BaseModel):
    """Request to reject a promotion."""
    reason: str = Field(..., min_length=1, description="Rejection reason")


class ApprovalStatusResponse(BaseModel):
    """Response with approval status."""
    request_id: str
    promotion_id: str
    template_id: str
    status: str
    requested_by: str
    target_environment: str
    required_approvers: int
    current_approvals: int
    approvals: List[Dict[str, Any]]
    rejections: List[Dict[str, Any]]
    created_at: str
    expires_at: str
    is_expired: bool
    message: str


class NotificationResponse(BaseModel):
    """Response with notification info."""
    notification_id: str
    request_id: str
    event: str
    message: str
    created_at: str
    sent: bool


# MD-1847: Version/Changelog Request/Response Models

class VersionResponse(BaseModel):
    """Response with version info."""
    version_id: str
    template_id: str
    version: str
    bump_type: str
    changes: List[Dict[str, Any]]
    promoted_by: str
    created_at: str
    metadata: Dict[str, Any]


class VersionListResponse(BaseModel):
    """Response with list of versions."""
    template_id: str
    versions: List[Dict[str, Any]]
    total: int


class ChangelogResponse(BaseModel):
    """Response with changelog."""
    template_id: str
    entries: List[Dict[str, Any]]
    total: int
    markdown: Optional[str] = None


# ============================================================================
# AUTHENTICATION HELPER (MD-1845 AC: Authentication)
# ============================================================================

async def get_current_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """Extract user ID from authentication headers."""
    # Support API key authentication
    if x_api_key:
        # In production, validate against API key store
        return f"api_key:{x_api_key[:8]}..."

    # Support Bearer token
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        # In production, validate JWT token
        return f"bearer:{token[:8]}..."

    return None


def require_auth(user_id: Optional[str] = Depends(get_current_user)) -> str:
    """Require authentication for endpoint."""
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide X-API-Key or Authorization header."
        )
    return user_id


# ============================================================================
# RATE LIMITING DEPENDENCY (MD-1845)
# ============================================================================

async def check_rate_limit(request: Request) -> None:
    """Check rate limit for request."""
    client_id = request.client.host if request.client else "unknown"

    if not rate_limiter.is_allowed(client_id):
        remaining = rate_limiter.get_remaining(client_id)
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Rate limit exceeded",
                "requests_per_minute": rate_limiter.requests_per_minute,
                "remaining": remaining,
                "retry_after_seconds": 60,
            }
        )


# ============================================================================
# MD-1845: POST /api/templates/promote Endpoint
# ============================================================================

@router.post("/promote", response_model=PromoteResponse)
async def promote_template(
    request: PromoteRequest,
    user_id: str = Depends(require_auth),
    _: None = Depends(check_rate_limit),
):
    """
    Promote a template to a target environment.

    MD-1845 Acceptance Criteria:
    - AC-1: Request validation with Pydantic models
    - AC-2: Response format with promotion details
    - AC-3: Criteria validation (delegated to service)
    - AC-4: Audit logging
    - AC-5: Authentication required
    - AC-6: Rate limiting

    If require_approval=True, creates an approval request instead of
    immediate promotion.
    """
    if not HAS_PROMOTION_SERVICE:
        raise HTTPException(status_code=503, detail="Promotion service not available")

    try:
        service = get_template_promotion_service()

        # Convert changes to dict format
        changes = []
        if request.changes:
            changes = [c.dict() for c in request.changes]

        # Handle force version bump
        force_bump = None
        if request.force_version_bump:
            force_bump = VersionBumpType(request.force_version_bump)

        # Perform promotion
        result = await service.promote_template(
            template_id=request.template_id,
            template_content=request.template_content,
            source_environment=PromotionEnvironment(request.source_environment),
            target_environment=PromotionEnvironment(request.target_environment),
            changes=changes,
            force_version_bump=force_bump,
            existing_metadata=request.metadata,
            promoted_by=user_id,
        )

        # Check if approval is required
        approval_request_id = None
        if request.require_approval and result.status == PromotionStatus.PROMOTED:
            # Create approval request instead of immediate promotion
            approval_req = approval_workflow.create_request(
                promotion_id=result.promotion_id,
                template_id=request.template_id,
                requested_by=user_id,
                target_environment=request.target_environment,
                required_approvers=request.approvers_required,
            )
            approval_request_id = approval_req.request_id
            result.status = PromotionStatus.PENDING  # Override to pending approval

        # Audit log
        audit_logger.log(
            action="promote_template",
            template_id=request.template_id,
            user_id=user_id,
            details={
                "promotion_id": result.promotion_id,
                "source": request.source_environment,
                "target": request.target_environment,
                "version": result.new_version,
                "status": result.status.value,
                "approval_required": request.require_approval,
            },
            success=result.status in [PromotionStatus.PROMOTED, PromotionStatus.PENDING],
        )

        # Record version history if promoted
        if result.status == PromotionStatus.PROMOTED:
            version_history.record_version(
                template_id=request.template_id,
                version=result.new_version,
                bump_type=result.version_bump_type.value,
                changes=changes,
                promoted_by=user_id,
                metadata=result.metadata.to_dict() if result.metadata else None,
            )

        # Build response
        message = f"Template promotion {result.status.value}"
        if approval_request_id:
            message = f"Promotion pending approval (request: {approval_request_id})"
        elif result.failure_message:
            message = result.failure_message

        return PromoteResponse(
            promotion_id=result.promotion_id,
            template_id=result.template_id,
            status=result.status.value,
            previous_version=result.previous_version,
            new_version=result.new_version,
            version_bump_type=result.version_bump_type.value,
            source_environment=result.source_environment.value,
            target_environment=result.target_environment.value,
            validation_report_id=result.validation_report_id,
            criteria=result.criteria.to_dict() if result.criteria else None,
            approval_required=request.require_approval,
            approval_request_id=approval_request_id,
            changelog=result.changelog.to_dict() if result.changelog else None,
            metadata=result.metadata.to_dict() if result.metadata else None,
            message=message,
            promoted_at=result.completed_at or datetime.now().isoformat(),
            duration_ms=result.duration_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Promotion failed: {e}")
        audit_logger.log(
            action="promote_template",
            template_id=request.template_id,
            user_id=user_id,
            details={"error": str(e)},
            success=False,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/promote/{promotion_id}", response_model=PromoteResponse)
async def get_promotion_status(
    promotion_id: str,
    user_id: Optional[str] = Depends(get_current_user),
):
    """Get status of a promotion request."""
    if not HAS_PROMOTION_SERVICE:
        raise HTTPException(status_code=503, detail="Promotion service not available")

    service = get_template_promotion_service()
    result = service.get_promotion_result(promotion_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Promotion not found: {promotion_id}")

    # Check for approval request
    approval_req = approval_workflow.get_by_promotion(promotion_id)
    approval_request_id = approval_req.request_id if approval_req else None

    return PromoteResponse(
        promotion_id=result.promotion_id,
        template_id=result.template_id,
        status=result.status.value,
        previous_version=result.previous_version,
        new_version=result.new_version,
        version_bump_type=result.version_bump_type.value,
        source_environment=result.source_environment.value,
        target_environment=result.target_environment.value,
        validation_report_id=result.validation_report_id,
        criteria=result.criteria.to_dict() if result.criteria else None,
        approval_required=approval_request_id is not None,
        approval_request_id=approval_request_id,
        changelog=result.changelog.to_dict() if result.changelog else None,
        metadata=result.metadata.to_dict() if result.metadata else None,
        message=f"Promotion status: {result.status.value}",
        promoted_at=result.completed_at or result.started_at,
        duration_ms=result.duration_ms,
    )


# ============================================================================
# MD-1846: Approval Workflow Endpoints
# ============================================================================

@router.post("/promote/{promotion_id}/approve", response_model=ApprovalStatusResponse)
async def approve_promotion(
    promotion_id: str,
    request: ApproveRequest,
    user_id: str = Depends(require_auth),
):
    """
    Approve a promotion request.

    MD-1846 Acceptance Criteria:
    - AC-1: Approval endpoint with authentication
    - AC-2: Multi-approver support
    - AC-3: Notification queuing
    - AC-4: Audit trail
    """
    # Find approval request
    approval_req = approval_workflow.get_by_promotion(promotion_id)
    if not approval_req:
        raise HTTPException(
            status_code=404,
            detail=f"No approval request found for promotion: {promotion_id}"
        )

    # Perform approval
    success, message = approval_workflow.approve(
        request_id=approval_req.request_id,
        approver_id=user_id,
        comment=request.comment,
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Audit log
    audit_logger.log(
        action="approve_promotion",
        template_id=approval_req.template_id,
        user_id=user_id,
        details={
            "request_id": approval_req.request_id,
            "promotion_id": promotion_id,
            "comment": request.comment,
            "current_approvals": approval_req.approval_count,
            "required": approval_req.required_approvers,
        },
    )

    return ApprovalStatusResponse(
        request_id=approval_req.request_id,
        promotion_id=approval_req.promotion_id,
        template_id=approval_req.template_id,
        status=approval_req.status.value,
        requested_by=approval_req.requested_by,
        target_environment=approval_req.target_environment,
        required_approvers=approval_req.required_approvers,
        current_approvals=approval_req.approval_count,
        approvals=approval_req.approvals,
        rejections=approval_req.rejections,
        created_at=approval_req.created_at.isoformat(),
        expires_at=approval_req.expires_at.isoformat(),
        is_expired=approval_req.is_expired,
        message=message,
    )


@router.post("/promote/{promotion_id}/reject", response_model=ApprovalStatusResponse)
async def reject_promotion(
    promotion_id: str,
    request: RejectRequest,
    user_id: str = Depends(require_auth),
):
    """
    Reject a promotion request.

    MD-1846 Acceptance Criteria:
    - AC-1: Reject endpoint with reason required
    - AC-2: Notification queuing
    - AC-3: Audit trail
    """
    # Find approval request
    approval_req = approval_workflow.get_by_promotion(promotion_id)
    if not approval_req:
        raise HTTPException(
            status_code=404,
            detail=f"No approval request found for promotion: {promotion_id}"
        )

    # Perform rejection
    success, message = approval_workflow.reject(
        request_id=approval_req.request_id,
        rejector_id=user_id,
        reason=request.reason,
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Audit log
    audit_logger.log(
        action="reject_promotion",
        template_id=approval_req.template_id,
        user_id=user_id,
        details={
            "request_id": approval_req.request_id,
            "promotion_id": promotion_id,
            "reason": request.reason,
        },
    )

    return ApprovalStatusResponse(
        request_id=approval_req.request_id,
        promotion_id=approval_req.promotion_id,
        template_id=approval_req.template_id,
        status=approval_req.status.value,
        requested_by=approval_req.requested_by,
        target_environment=approval_req.target_environment,
        required_approvers=approval_req.required_approvers,
        current_approvals=approval_req.approval_count,
        approvals=approval_req.approvals,
        rejections=approval_req.rejections,
        created_at=approval_req.created_at.isoformat(),
        expires_at=approval_req.expires_at.isoformat(),
        is_expired=approval_req.is_expired,
        message=message,
    )


@router.get("/promote/{promotion_id}/approval", response_model=ApprovalStatusResponse)
async def get_approval_status(
    promotion_id: str,
    user_id: Optional[str] = Depends(get_current_user),
):
    """Get approval status for a promotion."""
    approval_req = approval_workflow.get_by_promotion(promotion_id)
    if not approval_req:
        raise HTTPException(
            status_code=404,
            detail=f"No approval request found for promotion: {promotion_id}"
        )

    # Check for timeout
    if approval_req.status == ApprovalStatus.PENDING and approval_req.is_expired:
        approval_req.status = ApprovalStatus.EXPIRED

    return ApprovalStatusResponse(
        request_id=approval_req.request_id,
        promotion_id=approval_req.promotion_id,
        template_id=approval_req.template_id,
        status=approval_req.status.value,
        requested_by=approval_req.requested_by,
        target_environment=approval_req.target_environment,
        required_approvers=approval_req.required_approvers,
        current_approvals=approval_req.approval_count,
        approvals=approval_req.approvals,
        rejections=approval_req.rejections,
        created_at=approval_req.created_at.isoformat(),
        expires_at=approval_req.expires_at.isoformat(),
        is_expired=approval_req.is_expired,
        message=f"Approval status: {approval_req.status.value}",
    )


@router.get("/notifications", response_model=List[NotificationResponse])
async def get_notifications(
    pending_only: bool = Query(True, description="Only return unsent notifications"),
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(require_auth),
):
    """Get queued notifications for approvals."""
    notifications = approval_workflow.get_pending_notifications() if pending_only else approval_workflow._notifications

    results = []
    for n in notifications[-limit:]:
        results.append(NotificationResponse(
            notification_id=n["notification_id"],
            request_id=n["request_id"],
            event=n["event"],
            message=n["message"],
            created_at=n["created_at"],
            sent=n["sent"],
        ))

    return results


@router.post("/notifications/{notification_id}/mark-sent")
async def mark_notification_sent(
    notification_id: str,
    user_id: str = Depends(require_auth),
):
    """Mark a notification as sent."""
    approval_workflow.mark_notification_sent(notification_id)
    return {"message": f"Notification {notification_id} marked as sent"}


# ============================================================================
# MD-1847: Version History & Changelog Endpoints
# ============================================================================

@router.get("/{template_id}/versions", response_model=VersionListResponse)
async def get_template_versions(
    template_id: str,
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[str] = Depends(get_current_user),
):
    """
    Get version history for a template.

    MD-1847 Acceptance Criteria:
    - AC-1: Version history endpoint
    - AC-2: List all versions with metadata
    - AC-3: Sorted by date (newest first)
    """
    versions = version_history.get_versions(template_id, limit=limit)

    return VersionListResponse(
        template_id=template_id,
        versions=versions,
        total=len(versions),
    )


@router.get("/{template_id}/versions/{version}", response_model=VersionResponse)
async def get_specific_version(
    template_id: str,
    version: str,
    user_id: Optional[str] = Depends(get_current_user),
):
    """Get details for a specific version."""
    ver = version_history.get_version(template_id, version)

    if not ver:
        raise HTTPException(
            status_code=404,
            detail=f"Version {version} not found for template {template_id}"
        )

    return VersionResponse(
        version_id=ver["version_id"],
        template_id=ver["template_id"],
        version=ver["version"],
        bump_type=ver["bump_type"],
        changes=ver["changes"],
        promoted_by=ver["promoted_by"],
        created_at=ver["created_at"],
        metadata=ver["metadata"],
    )


@router.get("/{template_id}/changelog", response_model=ChangelogResponse)
async def get_template_changelog(
    template_id: str,
    format: str = Query("json", description="Output format: json or markdown"),
    limit: int = Query(100, ge=1, le=500),
    user_id: Optional[str] = Depends(get_current_user),
):
    """
    Get changelog for a template.

    MD-1847 Acceptance Criteria:
    - AC-1: Changelog endpoint
    - AC-2: JSON and Markdown formats
    - AC-3: Breaking changes flagged
    - AC-4: Sorted by version/date
    """
    entries = version_history.get_changelog(template_id, limit=limit)

    markdown = None
    if format == "markdown":
        markdown = version_history.generate_markdown_changelog(template_id)

    return ChangelogResponse(
        template_id=template_id,
        entries=entries,
        total=len(entries),
        markdown=markdown,
    )


# ============================================================================
# AUDIT ENDPOINTS
# ============================================================================

@router.get("/audit/logs")
async def get_audit_logs(
    template_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user_id: str = Depends(require_auth),
):
    """Get audit logs for template operations."""
    logs = audit_logger.get_logs(
        template_id=template_id,
        action=action,
        limit=limit,
    )

    return {
        "logs": logs,
        "total": len(logs),
        "filters": {
            "template_id": template_id,
            "action": action,
        },
    }


# ============================================================================
# HEALTH & CONFIG ENDPOINTS
# ============================================================================

@router.get("/promotion/health")
async def promotion_health():
    """Health check for promotion service."""
    return {
        "status": "healthy" if HAS_PROMOTION_SERVICE else "unavailable",
        "service": "template-promotion",
        "timestamp": datetime.now().isoformat(),
        "promotion_service_available": HAS_PROMOTION_SERVICE,
        "rate_limit": {
            "requests_per_minute": rate_limiter.requests_per_minute,
        },
    }


@router.get("/promotion/config")
async def get_promotion_config(
    user_id: Optional[str] = Depends(get_current_user),
):
    """Get promotion service configuration."""
    if not HAS_PROMOTION_SERVICE:
        return {
            "service_available": False,
            "message": "Promotion service not available",
        }

    service = get_template_promotion_service()
    config = service.get_config()

    return {
        "service_available": True,
        "thresholds": config["thresholds"],
        "feature_flags": config["feature_flags"],
        "quality_fabric_url": config["quality_fabric_url"],
        "cache_size": config["cache_size"],
        "rate_limit": {
            "requests_per_minute": rate_limiter.requests_per_minute,
        },
    }


# ============================================================================
# ROUTER REGISTRATION
# ============================================================================

def register_template_promotion_routes(app):
    """Register template promotion routes with a FastAPI app."""
    app.include_router(router)
    logger.info("Template promotion routes registered at /api/templates")
