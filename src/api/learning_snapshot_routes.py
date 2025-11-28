#!/usr/bin/env python3
"""
Learning Snapshot API Routes
Implements EPIC QF-400: Learning Snapshots with RAG Ingestion & Provenance

REST API endpoints for learning snapshots:
- POST /api/snapshots - Generate and index a snapshot
- GET /api/snapshots - List snapshots
- GET /api/snapshots/{id} - Get snapshot by ID
- DELETE /api/snapshots/{id} - Delete a snapshot
- GET /api/snapshots/stats - Get collection statistics
- POST /api/snapshots/query - RAG query for similar snapshots
- GET /api/snapshots/{id}/provenance - Validate and resolve provenance
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# Import snapshot service
try:
    from services.learning_snapshot_service import (
        get_snapshot_service,
        LearningSnapshotService,
        LearningSnapshot,
        SnapshotStatus,
        ProvenanceType,
    )
    HAS_SNAPSHOT_SERVICE = True
except ImportError:
    HAS_SNAPSHOT_SERVICE = False

logger = logging.getLogger("learning_snapshot_routes")

# Create router
router = APIRouter(prefix="/api/snapshots", tags=["learning-snapshots"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class PhaseResultRequest(BaseModel):
    """Phase result in snapshot request."""
    id: str = Field(..., description="Phase ID")
    name: str = Field(None, description="Phase name")
    score: float = Field(0.0, description="Phase score (0-1)")
    gates: Dict[str, str] = Field(default_factory=dict, description="Gate results")
    artifacts: List[str] = Field(default_factory=list, description="Artifact URIs")
    duration_ms: float = Field(0, description="Duration in milliseconds")
    test_results: Optional[Dict[str, Any]] = Field(None, description="Test results")


class DefectRequest(BaseModel):
    """Defect in snapshot request."""
    id: str = Field(..., description="Defect ID")
    severity: str = Field("medium", description="Severity: critical, high, medium, low")
    phase: str = Field("", description="Phase where found")
    description: str = Field("", description="Defect description")
    resolution: Optional[str] = Field(None, description="Resolution if fixed")


class CitationRequest(BaseModel):
    """Citation in snapshot request."""
    source: str = Field(..., description="Source identifier")
    ref: str = Field(..., description="Reference (commit, version, etc.)")
    type: str = Field("source_repo", description="Citation type")
    description: Optional[str] = Field(None, description="Description")


class ProvenanceRequest(BaseModel):
    """Provenance information."""
    source_repo: Optional[str] = Field(None, description="Source repository URI")
    commit: Optional[str] = Field(None, description="Commit hash")
    tool_chain: str = Field("maestro+quality-fabric", description="Tool chain used")
    validation_report_id: Optional[str] = Field(None, description="QF validation report ID")
    created_by: Optional[str] = Field(None, description="Creator identifier")


class SnapshotCreateRequest(BaseModel):
    """Request to create a learning snapshot."""
    session_id: str = Field(..., description="Workflow session ID")
    execution_id: str = Field(..., description="Execution ID")
    requirement: str = Field(..., description="Original requirement text")
    phases: List[PhaseResultRequest] = Field(default_factory=list, description="Phase results")
    quality_score: float = Field(0.0, description="Overall quality score (0-1)")
    templates_used: List[str] = Field(default_factory=list, description="Template IDs used")
    defects: List[DefectRequest] = Field(default_factory=list, description="Defects found")
    citations: List[CitationRequest] = Field(default_factory=list, description="Citations")
    provenance: Optional[ProvenanceRequest] = Field(None, description="Provenance info")
    personas: List[str] = Field(default_factory=list, description="Personas involved")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    environment: str = Field("development", description="Environment")
    execution_time_ms: float = Field(0, description="Execution time in ms")
    success: bool = Field(True, description="Whether execution succeeded")
    workflow_id: Optional[str] = Field(None, description="Workflow ID")
    auto_index: bool = Field(True, description="Automatically index after creation")


class RAGQueryRequest(BaseModel):
    """Request for RAG query."""
    query_text: str = Field(..., description="Query text to search for")
    top_k: int = Field(5, description="Number of results to return", ge=1, le=100)
    min_score: float = Field(0.0, description="Minimum similarity score (0-1)")
    min_quality: float = Field(0.0, description="Minimum quality score filter")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters")


class SnapshotResponse(BaseModel):
    """Snapshot response."""
    snapshot_id: str
    session_id: str
    execution_id: str
    workflow_id: Optional[str]
    requirement_summary: str
    overall_score: float
    quality_score: float
    phases: List[Dict[str, Any]]
    templates_used: List[str]
    defect_count: int
    citation_count: int
    personas: List[str]
    tags: List[str]
    environment: str
    status: str
    success: bool
    created_at: str
    indexed_at: Optional[str]


class RAGQueryResultResponse(BaseModel):
    """RAG query result."""
    snapshot_id: str
    similarity: float
    snapshot: SnapshotResponse
    highlights: List[str]


class ProvenanceValidationResponse(BaseModel):
    """Provenance validation response."""
    is_valid: bool
    issues: List[str]
    provenance: Optional[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    resolved_citations: List[Dict[str, Any]]


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/health")
async def learning_snapshot_health():
    """Health check for learning snapshot service."""
    return {
        "status": "healthy" if HAS_SNAPSHOT_SERVICE else "unavailable",
        "service": "learning-snapshots",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/stats")
async def get_snapshot_stats():
    """
    Get statistics about the snapshot collection.

    Returns vector store stats and cached snapshot count.
    """
    if not HAS_SNAPSHOT_SERVICE:
        raise HTTPException(status_code=503, detail="Learning snapshot service not available")

    service = get_snapshot_service()
    info = service.get_service_info()
    stats = service.get_collection_stats()

    return {
        "service_enabled": info.get("enabled", False),
        "collection": info.get("collection"),
        "indexed_count": stats.get("count", 0),
        "cached_count": info.get("cached_snapshots", 0),
        "chromadb_available": info.get("chromadb_available", False),
    }


@router.post("", response_model=SnapshotResponse)
async def create_snapshot(request: SnapshotCreateRequest):
    """
    Create a learning snapshot from execution results.

    Generates a snapshot and optionally indexes it to the vector store.
    Part of QF-400: Learning Snapshots with RAG Ingestion.
    """
    if not HAS_SNAPSHOT_SERVICE:
        raise HTTPException(status_code=503, detail="Learning snapshot service not available")

    service = get_snapshot_service()

    # Convert request models to dicts
    phases = [p.model_dump() for p in request.phases]
    defects = [d.model_dump() for d in request.defects]
    citations = [c.model_dump() for c in request.citations]
    provenance = request.provenance.model_dump() if request.provenance else None

    # Generate snapshot
    snapshot = service.generate_snapshot(
        session_id=request.session_id,
        execution_id=request.execution_id,
        requirement=request.requirement,
        phases=phases,
        quality_score=request.quality_score,
        templates_used=request.templates_used,
        defects=defects,
        citations=citations,
        provenance=provenance,
        personas=request.personas,
        tags=request.tags,
        environment=request.environment,
        execution_time_ms=request.execution_time_ms,
        success=request.success,
        workflow_id=request.workflow_id,
    )

    # Auto-index if requested
    if request.auto_index:
        service.index_snapshot(snapshot)

    return _snapshot_to_response(snapshot)


@router.get("", response_model=List[SnapshotResponse])
async def list_snapshots(
    limit: int = Query(100, description="Maximum results", ge=1, le=1000),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """
    List cached learning snapshots.

    Query parameters:
    - limit: Maximum number of results
    - status: Filter by status (pending, processing, indexed, failed)
    """
    if not HAS_SNAPSHOT_SERVICE:
        raise HTTPException(status_code=503, detail="Learning snapshot service not available")

    service = get_snapshot_service()

    status_filter = None
    if status:
        try:
            status_filter = SnapshotStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Valid: {[s.value for s in SnapshotStatus]}"
            )

    snapshots = service.list_snapshots(limit=limit, status=status_filter)

    return [_snapshot_to_response(s) for s in snapshots]


@router.get("/{snapshot_id}", response_model=SnapshotResponse)
async def get_snapshot(snapshot_id: str):
    """
    Get a specific snapshot by ID.
    """
    if not HAS_SNAPSHOT_SERVICE:
        raise HTTPException(status_code=503, detail="Learning snapshot service not available")

    service = get_snapshot_service()
    snapshot = service.get_snapshot(snapshot_id)

    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {snapshot_id}")

    return _snapshot_to_response(snapshot)


@router.delete("/{snapshot_id}")
async def delete_snapshot(snapshot_id: str):
    """
    Delete a snapshot from cache and vector store.
    """
    if not HAS_SNAPSHOT_SERVICE:
        raise HTTPException(status_code=503, detail="Learning snapshot service not available")

    service = get_snapshot_service()
    deleted = service.delete_snapshot(snapshot_id)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Snapshot not found or delete failed: {snapshot_id}")

    return {"status": "deleted", "snapshot_id": snapshot_id}


@router.post("/query", response_model=List[RAGQueryResultResponse])
async def query_snapshots(request: RAGQueryRequest):
    """
    Query for similar learning snapshots using RAG.

    Searches the vector store for snapshots matching the query text.
    Part of QF-400: RAG queries return relevant snapshots (AC-5).
    """
    if not HAS_SNAPSHOT_SERVICE:
        raise HTTPException(status_code=503, detail="Learning snapshot service not available")

    service = get_snapshot_service()

    # Build filters
    filters = request.filters or {}
    if request.min_quality > 0:
        filters["quality_score"] = request.min_quality

    results = service.query_similar(
        query_text=request.query_text,
        top_k=request.top_k,
        min_score=request.min_score,
        filters=filters if filters else None,
    )

    return [
        RAGQueryResultResponse(
            snapshot_id=r.snapshot_id,
            similarity=r.similarity,
            snapshot=_snapshot_to_response(r.snapshot),
            highlights=r.highlights,
        )
        for r in results
    ]


@router.get("/query/by-requirement")
async def query_by_requirement(
    requirement: str = Query(..., description="Requirement text to search"),
    top_k: int = Query(5, description="Number of results"),
    min_quality: float = Query(0.0, description="Minimum quality score"),
):
    """
    Query for snapshots with similar requirements.

    Convenience endpoint for requirement-based search.
    """
    if not HAS_SNAPSHOT_SERVICE:
        raise HTTPException(status_code=503, detail="Learning snapshot service not available")

    service = get_snapshot_service()
    results = service.query_by_requirement(
        requirement=requirement,
        top_k=top_k,
        min_quality=min_quality,
    )

    return {
        "query": requirement,
        "results": [
            {
                "snapshot_id": r.snapshot_id,
                "similarity": r.similarity,
                "requirement_summary": r.snapshot.requirement_summary,
                "quality_score": r.snapshot.quality_score,
                "success": r.snapshot.success,
            }
            for r in results
        ],
        "total": len(results),
    }


@router.get("/query/by-template/{template_id}")
async def query_by_template(
    template_id: str,
    top_k: int = Query(10, description="Number of results"),
):
    """
    Query for snapshots that used a specific template.
    """
    if not HAS_SNAPSHOT_SERVICE:
        raise HTTPException(status_code=503, detail="Learning snapshot service not available")

    service = get_snapshot_service()
    results = service.query_by_template(template_id=template_id, top_k=top_k)

    return {
        "template_id": template_id,
        "results": [
            {
                "snapshot_id": r.snapshot_id,
                "similarity": r.similarity,
                "session_id": r.snapshot.session_id,
                "quality_score": r.snapshot.quality_score,
            }
            for r in results
        ],
        "total": len(results),
    }


@router.get("/{snapshot_id}/provenance", response_model=ProvenanceValidationResponse)
async def validate_provenance(snapshot_id: str):
    """
    Validate and resolve provenance for a snapshot.

    Checks provenance links and resolves citations to URIs.
    Part of QF-400: Provenance links valid and resolvable (AC-4).
    """
    if not HAS_SNAPSHOT_SERVICE:
        raise HTTPException(status_code=503, detail="Learning snapshot service not available")

    service = get_snapshot_service()
    snapshot = service.get_snapshot(snapshot_id)

    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {snapshot_id}")

    # Validate provenance
    is_valid, issues = service.validate_provenance(snapshot)

    # Resolve citations
    resolved_citations = []
    for citation in snapshot.citations:
        resolved = service.resolve_citation(citation)
        resolved_citations.append(resolved)

    return ProvenanceValidationResponse(
        is_valid=is_valid,
        issues=issues,
        provenance=snapshot.provenance.to_dict() if snapshot.provenance else None,
        citations=[c.to_dict() for c in snapshot.citations],
        resolved_citations=resolved_citations,
    )


@router.post("/{snapshot_id}/index")
async def index_snapshot(snapshot_id: str):
    """
    Index an existing snapshot to the vector store.

    Useful for re-indexing or manually triggering indexing.
    """
    if not HAS_SNAPSHOT_SERVICE:
        raise HTTPException(status_code=503, detail="Learning snapshot service not available")

    service = get_snapshot_service()
    snapshot = service.get_snapshot(snapshot_id)

    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {snapshot_id}")

    indexed = service.index_snapshot(snapshot)

    return {
        "snapshot_id": snapshot_id,
        "indexed": indexed,
        "status": snapshot.status.value,
        "indexed_at": snapshot.indexed_at,
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _snapshot_to_response(snapshot: LearningSnapshot) -> SnapshotResponse:
    """Convert LearningSnapshot to API response."""
    return SnapshotResponse(
        snapshot_id=snapshot.snapshot_id,
        session_id=snapshot.session_id,
        execution_id=snapshot.execution_id,
        workflow_id=snapshot.workflow_id,
        requirement_summary=snapshot.requirement_summary,
        overall_score=snapshot.overall_score,
        quality_score=snapshot.quality_score,
        phases=[p.to_dict() for p in snapshot.phases],
        templates_used=snapshot.templates_used,
        defect_count=len(snapshot.defects),
        citation_count=len(snapshot.citations),
        personas=snapshot.personas,
        tags=snapshot.tags,
        environment=snapshot.environment,
        status=snapshot.status.value,
        success=snapshot.success,
        created_at=snapshot.created_at,
        indexed_at=snapshot.indexed_at,
    )


# ============================================================================
# HELPER FUNCTION TO REGISTER ROUTER
# ============================================================================

def register_learning_snapshot_routes(app):
    """Register learning snapshot routes with a FastAPI app."""
    app.include_router(router)
    logger.info("Learning snapshot routes registered")
