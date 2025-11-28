#!/usr/bin/env python3
"""
Team Enhancement API Routes
Implements Epic MD-1819 [ME-800] Team Enhancement Rationale & Override

REST API endpoints for team enhancement management:
- POST /api/teams/{session_id}/enhancements - Propose enhancement
- GET /api/teams/{session_id}/enhancements - Get enhancements with rationale
- POST /api/teams/{session_id}/lock - Lock team
- POST /api/teams/{session_id}/unlock - Unlock team
- GET /api/teams/{session_id}/audit - Get audit trail
- POST /api/teams/{session_id}/enhancements/{id}/accept - Accept enhancement
- POST /api/teams/{session_id}/enhancements/{id}/reject - Reject enhancement
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# Import team enhancement service
try:
    from services.team_enhancement_service import (
        get_team_enhancement_service,
        TeamEnhancementService,
        EnhancementReason,
        AuditEventType,
    )
    HAS_TEAM_SERVICE = True
except ImportError:
    HAS_TEAM_SERVICE = False

logger = logging.getLogger("team_enhancement_routes")

# Create router
router = APIRouter(prefix="/api/teams", tags=["team-enhancement"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ProposeEnhancementRequest(BaseModel):
    """Request to propose a persona enhancement."""
    persona_id: str = Field(..., description="Persona identifier")
    persona_name: str = Field(..., description="Human-readable persona name")
    reason: str = Field(..., description="Enhancement reason category")
    rationale: str = Field(..., description="Detailed rationale for enhancement")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")
    proposed_by: str = Field("system", description="Who proposed this")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class LockTeamRequest(BaseModel):
    """Request to lock a team."""
    locked_by: str = Field(..., description="User locking the team")
    reason: Optional[str] = Field(None, description="Reason for locking")


class UnlockTeamRequest(BaseModel):
    """Request to unlock a team."""
    unlocked_by: str = Field(..., description="User unlocking the team")
    reason: Optional[str] = Field(None, description="Reason for unlocking")


class AcceptEnhancementRequest(BaseModel):
    """Request to accept an enhancement."""
    accepted_by: str = Field(..., description="User accepting the enhancement")


class RejectEnhancementRequest(BaseModel):
    """Request to reject an enhancement."""
    rejected_by: str = Field(..., description="User rejecting the enhancement")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection")


class AddPersonaRequest(BaseModel):
    """Request to add a persona via override."""
    persona_id: str = Field(..., description="Persona identifier")
    persona_name: str = Field(..., description="Human-readable persona name")
    added_by: str = Field(..., description="User adding the persona")
    reason: Optional[str] = Field(None, description="Reason for adding")


class RemovePersonaRequest(BaseModel):
    """Request to remove a persona via override."""
    removed_by: str = Field(..., description="User removing the persona")
    reason: Optional[str] = Field(None, description="Reason for removing")


class CreateReportRequest(BaseModel):
    """Request to create a team enhancement report."""
    base_team: List[str] = Field(..., description="Initial team personas")
    created_by: str = Field("system", description="Who created the report")


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/health")
async def team_enhancement_health():
    """Health check for team enhancement service."""
    return {
        "status": "healthy" if HAS_TEAM_SERVICE else "unavailable",
        "service": "team-enhancement",
    }


@router.post("/{session_id}/report")
async def create_report(session_id: str, request: CreateReportRequest):
    """Create a new team enhancement report."""
    if not HAS_TEAM_SERVICE:
        raise HTTPException(status_code=503, detail="Team enhancement service not available")

    service = get_team_enhancement_service()
    report = service.create_report(
        session_id=session_id,
        base_team=request.base_team,
        created_by=request.created_by,
    )

    return {"status": "created", "report": report.to_dict()}


@router.get("/{session_id}/report")
async def get_report(session_id: str):
    """Get the team enhancement report."""
    if not HAS_TEAM_SERVICE:
        raise HTTPException(status_code=503, detail="Team enhancement service not available")

    service = get_team_enhancement_service()
    report = service.get_report(session_id)

    if not report:
        raise HTTPException(status_code=404, detail=f"Report not found for session: {session_id}")

    return report.to_dict()


@router.post("/{session_id}/enhancements")
async def propose_enhancement(session_id: str, request: ProposeEnhancementRequest):
    """
    Propose a persona enhancement with rationale.
    AC-1: Persona additions include rationale and confidence.
    """
    if not HAS_TEAM_SERVICE:
        raise HTTPException(status_code=503, detail="Team enhancement service not available")

    service = get_team_enhancement_service()

    try:
        reason = EnhancementReason(request.reason)
    except ValueError:
        valid_reasons = [r.value for r in EnhancementReason]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid reason. Valid: {valid_reasons}"
        )

    try:
        enhancement = service.propose_enhancement(
            session_id=session_id,
            persona_id=request.persona_id,
            persona_name=request.persona_name,
            reason=reason,
            rationale=request.rationale,
            confidence=request.confidence,
            proposed_by=request.proposed_by,
            metadata=request.metadata,
        )
        return {"status": "proposed", "enhancement": enhancement.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{session_id}/enhancements")
async def get_enhancements(
    session_id: str,
    persona_id: Optional[str] = Query(None, description="Filter by persona"),
):
    """
    Get enhancements with rationale.
    AC-1: Persona additions include rationale and confidence.
    """
    if not HAS_TEAM_SERVICE:
        raise HTTPException(status_code=503, detail="Team enhancement service not available")

    service = get_team_enhancement_service()
    enhancements = service.get_enhancement_rationale(session_id, persona_id)

    return {
        "session_id": session_id,
        "enhancements": [e.to_dict() for e in enhancements],
        "total": len(enhancements),
    }


@router.post("/{session_id}/lock")
async def lock_team(session_id: str, request: LockTeamRequest):
    """
    Lock the team to prevent further enhancements.
    AC-2: Users can lock base team.
    """
    if not HAS_TEAM_SERVICE:
        raise HTTPException(status_code=503, detail="Team enhancement service not available")

    service = get_team_enhancement_service()
    result = service.lock_team(
        session_id=session_id,
        locked_by=request.locked_by,
        reason=request.reason,
    )

    return {"status": "locked" if result else "failed", "session_id": session_id}


@router.post("/{session_id}/unlock")
async def unlock_team(session_id: str, request: UnlockTeamRequest):
    """
    Unlock the team to allow enhancements.
    AC-2: Users can lock base team.
    """
    if not HAS_TEAM_SERVICE:
        raise HTTPException(status_code=503, detail="Team enhancement service not available")

    service = get_team_enhancement_service()
    result = service.unlock_team(
        session_id=session_id,
        unlocked_by=request.unlocked_by,
        reason=request.reason,
    )

    return {"status": "unlocked" if result else "failed", "session_id": session_id}


@router.get("/{session_id}/lock-status")
async def get_lock_status(session_id: str):
    """Get team lock status."""
    if not HAS_TEAM_SERVICE:
        raise HTTPException(status_code=503, detail="Team enhancement service not available")

    service = get_team_enhancement_service()
    return service.get_team_lock_status(session_id)


@router.get("/{session_id}/audit")
async def get_audit_trail(
    session_id: str,
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    Get audit trail for team changes.
    AC-3: Audit logs include before/after diffs.
    """
    if not HAS_TEAM_SERVICE:
        raise HTTPException(status_code=503, detail="Team enhancement service not available")

    service = get_team_enhancement_service()

    event_type_filter = None
    if event_type:
        try:
            event_type_filter = AuditEventType(event_type)
        except ValueError:
            valid_types = [t.value for t in AuditEventType]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid event_type. Valid: {valid_types}"
            )

    audit_trail = service.get_audit_trail(
        session_id=session_id,
        event_type=event_type_filter,
        limit=limit,
        offset=offset,
    )

    return {
        "session_id": session_id,
        "audit_trail": [a.to_dict() for a in audit_trail],
        "total": len(audit_trail),
    }


@router.get("/{session_id}/audit/{audit_id}/diff")
async def get_audit_diff(session_id: str, audit_id: str):
    """
    Get the diff for a specific audit entry.
    AC-3: Audit logs include before/after diffs.
    """
    if not HAS_TEAM_SERVICE:
        raise HTTPException(status_code=503, detail="Team enhancement service not available")

    service = get_team_enhancement_service()
    diff = service.get_audit_diff(session_id, audit_id)

    if not diff:
        raise HTTPException(status_code=404, detail=f"Audit entry not found: {audit_id}")

    return diff


@router.post("/{session_id}/enhancements/{enhancement_id}/accept")
async def accept_enhancement(
    session_id: str,
    enhancement_id: str,
    request: AcceptEnhancementRequest,
):
    """Accept a proposed enhancement."""
    if not HAS_TEAM_SERVICE:
        raise HTTPException(status_code=503, detail="Team enhancement service not available")

    service = get_team_enhancement_service()
    result = service.accept_enhancement(
        session_id=session_id,
        enhancement_id=enhancement_id,
        accepted_by=request.accepted_by,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Enhancement not found")

    return {"status": "accepted", "enhancement_id": enhancement_id}


@router.post("/{session_id}/enhancements/{enhancement_id}/reject")
async def reject_enhancement(
    session_id: str,
    enhancement_id: str,
    request: RejectEnhancementRequest,
):
    """Reject a proposed enhancement."""
    if not HAS_TEAM_SERVICE:
        raise HTTPException(status_code=503, detail="Team enhancement service not available")

    service = get_team_enhancement_service()
    result = service.reject_enhancement(
        session_id=session_id,
        enhancement_id=enhancement_id,
        rejected_by=request.rejected_by,
        rejection_reason=request.rejection_reason,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Enhancement not found")

    return {"status": "rejected", "enhancement_id": enhancement_id}


@router.post("/{session_id}/personas")
async def add_persona_override(session_id: str, request: AddPersonaRequest):
    """Add a persona via user override."""
    if not HAS_TEAM_SERVICE:
        raise HTTPException(status_code=503, detail="Team enhancement service not available")

    service = get_team_enhancement_service()
    result = service.add_persona_override(
        session_id=session_id,
        persona_id=request.persona_id,
        persona_name=request.persona_name,
        added_by=request.added_by,
        reason=request.reason,
    )

    return {"status": "added" if result else "failed", "persona_id": request.persona_id}


@router.delete("/{session_id}/personas/{persona_id}")
async def remove_persona_override(
    session_id: str,
    persona_id: str,
    request: RemovePersonaRequest,
):
    """Remove a persona via user override."""
    if not HAS_TEAM_SERVICE:
        raise HTTPException(status_code=503, detail="Team enhancement service not available")

    service = get_team_enhancement_service()
    result = service.remove_persona_override(
        session_id=session_id,
        persona_id=persona_id,
        removed_by=request.removed_by,
        reason=request.reason,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Persona not found in team")

    return {"status": "removed", "persona_id": persona_id}


@router.get("/{session_id}/badge")
async def get_ui_badge(session_id: str):
    """Get badge information for UI display."""
    if not HAS_TEAM_SERVICE:
        raise HTTPException(status_code=503, detail="Team enhancement service not available")

    service = get_team_enhancement_service()
    return service.get_ui_badge_info(session_id)


# ============================================================================
# HELPER FUNCTION TO REGISTER ROUTER
# ============================================================================

def register_team_enhancement_routes(app):
    """Register team enhancement routes with a FastAPI app."""
    app.include_router(router)
    logger.info("Team enhancement routes registered")
