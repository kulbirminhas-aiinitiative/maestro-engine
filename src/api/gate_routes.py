#!/usr/bin/env python3
"""
Gate Framework API Routes for MAESTRO Engine
Implements EPIC-2: Gate Framework (DDE/BRV/ACC)

REST API endpoints for gate management:
- GET /api/gates - List gates with filters
- GET /api/gates/{gate_id} - Get gate details
- POST /api/gates - Create a new gate
- POST /api/gates/{gate_id}/evaluate - Evaluate a gate
- POST /api/gates/{gate_id}/approve - Approve a gate
- POST /api/gates/{gate_id}/reject - Reject a gate
- POST /api/gates/{gate_id}/evidence - Attach evidence
- GET /api/gates/{gate_id}/audit - Get audit trail

Acceptance Criteria Coverage:
- AC-1: Gates computed and stored per phase with status
- AC-2: Evidence URIs attachable to gates
- AC-4: Override requires explicit X-Gate-Override header with audit
- AC-5: WebSocket ws:gate:update broadcasts state changes
- AC-6: Dry-run mode computes gates without blocking
- AC-7: Audit trail persists all gate decisions
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header, Query, Request
from pydantic import BaseModel, Field

# MD-1876: Import input sanitizer for security hardening
try:
    from utils.input_sanitizer import sanitize_string, sanitize_identifier
    HAS_SANITIZER = True
except ImportError:
    HAS_SANITIZER = False
    def sanitize_string(v, **kwargs): return v
    def sanitize_identifier(v, **kwargs): return v

# Import gate service
try:
    from services.gate_service import (
        get_gate_service,
        GateType,
        GateStatus,
        GateEnforcement,
        EvidenceType,
        Gate,
        Evidence,
        GateEvaluationResult,
        AuditEntry,
    )
    HAS_GATE_SERVICE = True
except ImportError:
    HAS_GATE_SERVICE = False

# Import WebSocket manager for ws:gate:update events (AC-5)
try:
    from bff.websocket_manager import get_websocket_manager
    ws_manager = get_websocket_manager()
    HAS_WEBSOCKET = True
except ImportError:
    ws_manager = None
    HAS_WEBSOCKET = False

logger = logging.getLogger("gate_routes")


async def emit_gate_update(gate: Gate, result: Optional[GateEvaluationResult] = None):
    """
    Emit ws:gate:update WebSocket event (AC-5).
    Only emits if session_id is set and WebSocket is available.
    """
    if not HAS_WEBSOCKET or ws_manager is None or not gate.session_id:
        return

    try:
        await ws_manager.send_gate_update(
            session_id=gate.session_id,
            gate_id=gate.id,
            gate_type=gate.gate_type.value,
            status=gate.status.value,
            phase_id=gate.phase_id,
            workflow_id=gate.workflow_id,
            was_overridden=gate.was_overridden,
            evaluation_result=result.to_dict() if result else None,
        )
        logger.debug(f"Emitted ws:gate:update for gate {gate.id}")
    except Exception as e:
        logger.warning(f"Failed to emit ws:gate:update: {e}")

# Create router
router = APIRouter(prefix="/api/gates", tags=["gates"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class GateCreateRequest(BaseModel):
    """Request to create a new gate."""
    gate_type: str = Field(..., description="Gate type: DDE, BRV, or ACC")
    name: str = Field(..., description="Gate name")
    description: str = Field("", description="Gate description")
    phase_id: str = Field(..., description="Phase ID this gate belongs to")
    workflow_id: str = Field(..., description="Workflow ID")
    session_id: Optional[str] = Field(None, description="Session ID")
    enforcement: str = Field("mandatory", description="Enforcement level: mandatory or advisory")


class GateEvaluateRequest(BaseModel):
    """Request to evaluate a gate."""
    context: Dict[str, Any] = Field(default_factory=dict, description="Evaluation context data")
    dry_run: bool = Field(False, description="If true, don't update gate status")


class GateApproveRequest(BaseModel):
    """Request to approve a gate."""
    approved_by: str = Field(..., description="Approver identifier")
    comment: Optional[str] = Field(None, description="Approval comment")


class GateRejectRequest(BaseModel):
    """Request to reject a gate."""
    rejected_by: str = Field(..., description="Rejector identifier")
    reason: str = Field(..., description="Rejection reason")


class EvidenceAttachRequest(BaseModel):
    """Request to attach evidence to a gate."""
    evidence_type: str = Field(..., description="Evidence type: document, test_result, code_review, approval, metric, artifact")
    uri: str = Field(..., description="Evidence URI/reference")
    description: str = Field(..., description="Evidence description")
    attached_by: Optional[str] = Field(None, description="Who is attaching the evidence")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class CreatePhaseGatesRequest(BaseModel):
    """Request to create gates for a phase."""
    phase_type: str = Field(..., description="Phase type: requirements, design, implementation, testing, deployment")
    phase_id: str = Field(..., description="Phase ID")
    workflow_id: str = Field(..., description="Workflow ID")
    session_id: Optional[str] = Field(None, description="Session ID")
    custom_gates: Optional[List[Dict[str, Any]]] = Field(None, description="Custom gate definitions")


class GateResponse(BaseModel):
    """Gate response model."""
    id: str
    gate_type: str
    name: str
    description: str
    phase_id: str
    workflow_id: str
    session_id: Optional[str]
    status: str
    enforcement: str
    check_items: List[Dict[str, Any]]
    overall_score: Optional[float]
    evidence: List[Dict[str, Any]]
    created_at: Optional[str]
    evaluated_at: Optional[str]
    completed_at: Optional[str]
    was_overridden: bool
    override_reason: Optional[str]
    override_by: Optional[str]
    override_at: Optional[str]


class GateEvaluationResponse(BaseModel):
    """Gate evaluation result response."""
    gate_id: str
    gate_type: str
    status: str
    passed: bool
    blocking: bool
    overall_score: float
    check_items: List[Dict[str, Any]]
    message: str
    remediation: List[str]
    evaluated_at: str
    evaluation_time_ms: float
    dry_run: bool


class GateListResponse(BaseModel):
    """Response for listing gates."""
    gates: List[GateResponse]
    total: int
    filters: Dict[str, Any]


class AuditEntryResponse(BaseModel):
    """Audit entry response."""
    id: str
    gate_id: str
    action: str
    actor: Optional[str]
    timestamp: str
    details: Dict[str, Any]
    previous_status: Optional[str]
    new_status: Optional[str]


class AuditTrailResponse(BaseModel):
    """Audit trail response."""
    gate_id: str
    entries: List[AuditEntryResponse]
    total: int


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/health")
async def gate_service_health():
    """Health check for gate service."""
    return {
        "status": "healthy" if HAS_GATE_SERVICE else "unavailable",
        "service": "gate-framework",
        "timestamp": datetime.now().isoformat(),
        "feature_flag": "FF_GATES_ENFORCEMENT_ENABLED",
    }


@router.get("", response_model=GateListResponse)
async def list_gates(
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    phase: Optional[str] = Query(None, description="Filter by phase ID"),
    workflow_id: Optional[str] = Query(None, description="Filter by workflow ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    gate_type: Optional[str] = Query(None, description="Filter by gate type"),
):
    """
    List gates with optional filters.

    Query parameters:
    - session_id: Filter by session
    - phase: Filter by phase ID
    - workflow_id: Filter by workflow ID
    - status: Filter by gate status (open, pending, passed, failed)
    - gate_type: Filter by gate type (DDE, BRV, ACC)
    """
    if not HAS_GATE_SERVICE:
        raise HTTPException(status_code=503, detail="Gate service not available")

    service = get_gate_service()

    # Get gates based on filters
    if session_id:
        gates = service.get_gates_by_session(session_id, phase)
    elif workflow_id:
        gates = service.storage.get_gates_by_workflow(workflow_id)
    elif phase:
        gates = service.storage.get_gates_by_phase(phase)
    else:
        gates = service.storage.get_all_gates()

    # Apply additional filters
    if status:
        gates = [g for g in gates if g.status.value == status]
    if gate_type:
        gates = [g for g in gates if g.gate_type.value == gate_type]

    return GateListResponse(
        gates=[GateResponse(**g.to_dict()) for g in gates],
        total=len(gates),
        filters={
            "session_id": session_id,
            "phase": phase,
            "workflow_id": workflow_id,
            "status": status,
            "gate_type": gate_type,
        },
    )


@router.get("/{gate_id}", response_model=GateResponse)
async def get_gate(gate_id: str):
    """Get a specific gate by ID."""
    if not HAS_GATE_SERVICE:
        raise HTTPException(status_code=503, detail="Gate service not available")

    service = get_gate_service()
    gate = service.get_gate(gate_id)

    if not gate:
        raise HTTPException(status_code=404, detail=f"Gate not found: {gate_id}")

    return GateResponse(**gate.to_dict())


@router.post("", response_model=GateResponse)
async def create_gate(request: GateCreateRequest):
    """
    Create a new gate.

    Creates a gate of the specified type for a phase/workflow.
    """
    if not HAS_GATE_SERVICE:
        raise HTTPException(status_code=503, detail="Gate service not available")

    try:
        service = get_gate_service()

        # MD-1876: Sanitize input fields
        sanitized_name = sanitize_string(request.name, max_length=200, field_type="name")
        sanitized_description = sanitize_string(
            request.description,
            max_length=5000,
            field_type="description"
        )
        sanitized_phase_id = sanitize_identifier(request.phase_id, max_length=100)
        sanitized_workflow_id = sanitize_identifier(request.workflow_id, max_length=100)
        sanitized_session_id = sanitize_identifier(
            request.session_id,
            max_length=100
        ) if request.session_id else None

        if not sanitized_phase_id or not sanitized_workflow_id:
            raise HTTPException(status_code=400, detail="Invalid phase_id or workflow_id format")

        gate = service.create_gate(
            gate_type=GateType(request.gate_type),
            name=sanitized_name,
            description=sanitized_description,
            phase_id=sanitized_phase_id,
            workflow_id=sanitized_workflow_id,
            session_id=sanitized_session_id,
            enforcement=GateEnforcement(request.enforcement),
        )

        logger.info(f"Gate created via API: {gate.id}")

        return GateResponse(**gate.to_dict())

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating gate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/phase", response_model=GateListResponse)
async def create_phase_gates(request: CreatePhaseGatesRequest):
    """
    Create default gates for a phase type.

    Creates all standard gates for the specified phase type (requirements, design, etc.).
    """
    if not HAS_GATE_SERVICE:
        raise HTTPException(status_code=503, detail="Gate service not available")

    try:
        service = get_gate_service()

        gates = service.create_gates_for_phase(
            phase_type=request.phase_type,
            phase_id=request.phase_id,
            workflow_id=request.workflow_id,
            session_id=request.session_id,
            custom_gates=request.custom_gates,
        )

        logger.info(f"Created {len(gates)} gates for phase {request.phase_id}")

        return GateListResponse(
            gates=[GateResponse(**g.to_dict()) for g in gates],
            total=len(gates),
            filters={"phase_type": request.phase_type, "phase_id": request.phase_id},
        )

    except Exception as e:
        logger.error(f"Error creating phase gates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{gate_id}/evaluate", response_model=GateEvaluationResponse)
async def evaluate_gate(
    gate_id: str,
    request: GateEvaluateRequest,
    http_request: Request,
    x_gate_override: Optional[str] = Header(None, description="Override header with reason"),
):
    """
    Evaluate a gate.

    Evaluates the gate based on the provided context data.
    Supports dry-run mode (doesn't update gate status) and override via X-Gate-Override header.

    Headers:
    - X-Gate-Override: "reason" to force gate to pass with audit
    """
    if not HAS_GATE_SERVICE:
        raise HTTPException(status_code=503, detail="Gate service not available")

    try:
        service = get_gate_service()

        # Check for override
        override = x_gate_override is not None
        override_reason = x_gate_override if override else None
        override_by = http_request.headers.get("X-User-Id", "api_user") if override else None

        result = service.evaluate_gate(
            gate_id=gate_id,
            context=request.context,
            dry_run=request.dry_run,
            override=override,
            override_reason=override_reason,
            override_by=override_by,
        )

        logger.info(
            f"Gate evaluated via API: {gate_id} -> {result.status.value} "
            f"(dry_run={request.dry_run}, override={override})"
        )

        # Emit WebSocket event for non-dry-run evaluations (AC-5)
        if not request.dry_run:
            gate = service.get_gate(gate_id)
            if gate:
                await emit_gate_update(gate, result)

        return GateEvaluationResponse(**result.to_dict())

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error evaluating gate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{gate_id}/approve", response_model=GateResponse)
async def approve_gate(gate_id: str, request: GateApproveRequest):
    """
    Manually approve a gate.

    Marks the gate as passed regardless of check results.
    """
    if not HAS_GATE_SERVICE:
        raise HTTPException(status_code=503, detail="Gate service not available")

    try:
        service = get_gate_service()

        gate = service.approve_gate(
            gate_id=gate_id,
            approved_by=request.approved_by,
            comment=request.comment,
        )

        logger.info(f"Gate approved via API: {gate_id} by {request.approved_by}")

        # Emit WebSocket event (AC-5)
        await emit_gate_update(gate)

        return GateResponse(**gate.to_dict())

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error approving gate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{gate_id}/reject", response_model=GateResponse)
async def reject_gate(gate_id: str, request: GateRejectRequest):
    """
    Manually reject a gate.

    Marks the gate as failed with the provided reason.
    """
    if not HAS_GATE_SERVICE:
        raise HTTPException(status_code=503, detail="Gate service not available")

    try:
        service = get_gate_service()

        gate = service.reject_gate(
            gate_id=gate_id,
            rejected_by=request.rejected_by,
            reason=request.reason,
        )

        logger.info(f"Gate rejected via API: {gate_id} by {request.rejected_by}")

        # Emit WebSocket event (AC-5)
        await emit_gate_update(gate)

        return GateResponse(**gate.to_dict())

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error rejecting gate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{gate_id}/evidence")
async def attach_evidence(gate_id: str, request: EvidenceAttachRequest):
    """
    Attach evidence to a gate.

    Attaches a piece of evidence (document, test result, etc.) to the gate.
    """
    if not HAS_GATE_SERVICE:
        raise HTTPException(status_code=503, detail="Gate service not available")

    try:
        service = get_gate_service()

        evidence = service.attach_evidence(
            gate_id=gate_id,
            evidence_type=EvidenceType(request.evidence_type),
            uri=request.uri,
            description=request.description,
            attached_by=request.attached_by,
            metadata=request.metadata,
        )

        logger.info(f"Evidence attached via API: {evidence.id} to gate {gate_id}")

        return {
            "evidence": evidence.to_dict(),
            "gate_id": gate_id,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error attaching evidence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{gate_id}/audit", response_model=AuditTrailResponse)
async def get_audit_trail(gate_id: str):
    """
    Get the audit trail for a gate.

    Returns all audit entries for the specified gate.
    """
    if not HAS_GATE_SERVICE:
        raise HTTPException(status_code=503, detail="Gate service not available")

    try:
        service = get_gate_service()

        # Verify gate exists
        gate = service.get_gate(gate_id)
        if not gate:
            raise HTTPException(status_code=404, detail=f"Gate not found: {gate_id}")

        entries = service.get_audit_trail(gate_id)

        return AuditTrailResponse(
            gate_id=gate_id,
            entries=[AuditEntryResponse(**e.to_dict()) for e in entries],
            total=len(entries),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting audit trail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HELPER FUNCTION TO REGISTER ROUTER
# ============================================================================

def register_gate_routes(app):
    """Register gate routes with a FastAPI app."""
    app.include_router(router)
    logger.info("Gate routes registered")
