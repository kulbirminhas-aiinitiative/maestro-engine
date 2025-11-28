#!/usr/bin/env python3
"""
Template Provenance API Routes for MAESTRO Engine
Implements Epic MD-1824: [MT-200] Template Provenance & Citations System

REST API endpoints for template provenance:
- POST /api/templates/{id}/provenance - Create/update provenance
- GET /api/templates/{id}/provenance - Get full provenance
- POST /api/templates/{id}/citations - Add citation
- GET /api/templates/{id}/citations - Get citations
- GET /api/templates/{id}/lineage - Get lineage chain
- POST /api/templates/{id}/citations/{citation_id}/verify - Verify citation

Acceptance Criteria Coverage:
- AC-1: Provenance fields added to template metadata schema
- AC-2: Create/promote APIs require provenance payload
- AC-3: GET /templates/{id} returns full provenance
- AC-4: Search results include provenance summary
- AC-5: Citations link to source artifacts with valid URIs
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, validator

# Import provenance service
try:
    from services.template_provenance_service import (
        get_template_provenance_service,
        TemplateProvenance,
        Citation,
        ProvenanceSource,
        ToolChain,
        ProvenanceType,
        CitationType,
        ProvenanceValidationStatus,
        ProvenanceValidationResult,
        LineageNode,
    )
    HAS_PROVENANCE_SERVICE = True
except ImportError:
    HAS_PROVENANCE_SERVICE = False

logger = logging.getLogger("template_provenance_routes")

# Create router
router = APIRouter(prefix="/api/templates", tags=["template-provenance"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ProvenanceSourceRequest(BaseModel):
    """Source repository information."""
    source_repo: str = Field(..., description="Source repository URI (e.g., github://org/repo)")
    commit: Optional[str] = Field(None, description="Commit hash")
    branch: Optional[str] = Field(None, description="Branch name")
    tag: Optional[str] = Field(None, description="Tag if applicable")
    path: Optional[str] = Field(None, description="Path within repo")


class ToolChainRequest(BaseModel):
    """Tool chain information."""
    name: str = Field("maestro+quality-fabric", description="Tool chain name")
    version: str = Field("1.0.0", description="Tool chain version")
    components: List[str] = Field(default=[], description="Individual tools")


class CitationRequest(BaseModel):
    """Citation to a source artifact."""
    type: str = Field("derived_from", description="Citation type")
    source_uri: str = Field(..., description="URI to source artifact")
    title: Optional[str] = Field(None, description="Human-readable title")
    description: Optional[str] = Field(None, description="Why this was cited")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @validator("type")
    def validate_type(cls, v):
        valid_types = ["derived_from", "inspired_by", "transformed_from",
                       "validated_by", "golden_project", "successful_run"]
        if v not in valid_types:
            raise ValueError(f"type must be one of {valid_types}")
        return v


class CreateProvenanceRequest(BaseModel):
    """
    Request to create template provenance.

    AC-2: Create/promote APIs require provenance payload
    """
    source_repo: str = Field(..., description="Source repository URI")
    commit: Optional[str] = Field(None, description="Commit hash")
    tool_chain: Optional[str] = Field("maestro+quality-fabric", description="Tool chain name")
    validation_report_id: Optional[str] = Field(None, description="QF validation report ID")
    parent_template_id: Optional[str] = Field(None, description="Parent template for derivation")
    citations: Optional[List[CitationRequest]] = Field(None, description="Initial citations")
    created_by: Optional[str] = Field(None, description="Creator identifier")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class ProvenanceSourceResponse(BaseModel):
    """Source repository response."""
    source_repo: str
    commit: Optional[str]
    branch: Optional[str]
    tag: Optional[str]
    path: Optional[str]


class ToolChainResponse(BaseModel):
    """Tool chain response."""
    name: str
    version: str
    components: List[str]


class CitationResponse(BaseModel):
    """Citation response."""
    citation_id: str
    citation_type: str
    source_uri: str
    title: Optional[str]
    description: Optional[str]
    verified: bool
    verified_at: Optional[str]
    metadata: Dict[str, Any]
    created_at: str


class ProvenanceResponse(BaseModel):
    """
    Full provenance response.

    AC-3: GET /templates/{id} returns full provenance
    """
    provenance_id: str
    template_id: str
    source: ProvenanceSourceResponse
    tool_chain: ToolChainResponse
    validation_report_id: Optional[str]
    parent_template_id: Optional[str]
    parent_version: Optional[str]
    citations: List[CitationResponse]
    provenance_type: str
    validation_status: str
    created_by: Optional[str]
    created_at: str
    updated_at: str
    context: Dict[str, Any]


class ProvenanceSummaryResponse(BaseModel):
    """
    Provenance summary for search results.

    AC-4: Search results include provenance summary
    """
    source_repo: str
    commit: Optional[str]
    tool_chain: str
    validation_report_id: Optional[str]
    citation_count: int
    provenance_type: str


class LineageNodeResponse(BaseModel):
    """Lineage node response."""
    template_id: str
    version: str
    provenance_id: str
    source_repo: str
    created_at: str
    depth: int


class ValidationResultResponse(BaseModel):
    """Provenance validation result response."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    validated_uris: List[str]
    validation_time_ms: float


class ProvenanceConfigResponse(BaseModel):
    """Provenance service configuration."""
    supported_uri_schemes: List[str]
    provenance_types: List[str]
    citation_types: List[str]
    cache_size: int
    citation_count: int


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _format_provenance_response(prov: TemplateProvenance) -> ProvenanceResponse:
    """Convert TemplateProvenance to API response."""
    return ProvenanceResponse(
        provenance_id=prov.provenance_id,
        template_id=prov.template_id,
        source=ProvenanceSourceResponse(
            source_repo=prov.source.source_repo,
            commit=prov.source.commit,
            branch=prov.source.branch,
            tag=prov.source.tag,
            path=prov.source.path,
        ),
        tool_chain=ToolChainResponse(
            name=prov.tool_chain.name,
            version=prov.tool_chain.version,
            components=prov.tool_chain.components,
        ),
        validation_report_id=prov.validation_report_id,
        parent_template_id=prov.parent_template_id,
        parent_version=prov.parent_version,
        citations=[
            CitationResponse(
                citation_id=c.citation_id,
                citation_type=c.citation_type.value,
                source_uri=c.source_uri,
                title=c.title,
                description=c.description,
                verified=c.verified,
                verified_at=c.verified_at,
                metadata=c.metadata,
                created_at=c.created_at,
            )
            for c in prov.citations
        ],
        provenance_type=prov.provenance_type.value,
        validation_status=prov.validation_status.value,
        created_by=prov.created_by,
        created_at=prov.created_at,
        updated_at=prov.updated_at,
        context=prov.context,
    )


def _format_citation_response(citation: Citation) -> CitationResponse:
    """Convert Citation to API response."""
    return CitationResponse(
        citation_id=citation.citation_id,
        citation_type=citation.citation_type.value,
        source_uri=citation.source_uri,
        title=citation.title,
        description=citation.description,
        verified=citation.verified,
        verified_at=citation.verified_at,
        metadata=citation.metadata,
        created_at=citation.created_at,
    )


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/provenance/health")
async def provenance_service_health():
    """Health check for provenance service."""
    return {
        "status": "healthy" if HAS_PROVENANCE_SERVICE else "unavailable",
        "service": "template-provenance",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/provenance/config", response_model=ProvenanceConfigResponse)
async def get_provenance_config():
    """Get provenance service configuration."""
    if not HAS_PROVENANCE_SERVICE:
        raise HTTPException(status_code=503, detail="Provenance service not available")

    service = get_template_provenance_service()
    config = service.get_config()

    return ProvenanceConfigResponse(**config)


@router.post("/{template_id}/provenance", response_model=ProvenanceResponse)
async def create_template_provenance(
    template_id: str,
    request: CreateProvenanceRequest,
):
    """
    Create or update provenance for a template.

    AC-1: Provenance fields added to template metadata schema
    AC-2: Create/promote APIs require provenance payload
    """
    if not HAS_PROVENANCE_SERVICE:
        raise HTTPException(status_code=503, detail="Provenance service not available")

    try:
        service = get_template_provenance_service()

        # Convert citations to dict format
        citations_data = None
        if request.citations:
            citations_data = [
                {
                    "type": c.type,
                    "source_uri": c.source_uri,
                    "title": c.title,
                    "description": c.description,
                    "metadata": c.metadata or {},
                }
                for c in request.citations
            ]

        provenance = service.create_provenance(
            template_id=template_id,
            source_repo=request.source_repo,
            commit=request.commit,
            tool_chain=request.tool_chain,
            validation_report_id=request.validation_report_id,
            parent_template_id=request.parent_template_id,
            citations=citations_data,
            created_by=request.created_by,
            context=request.context,
        )

        # Check validation status
        if provenance.validation_status == ProvenanceValidationStatus.INVALID:
            validation = service.validate_provenance(provenance)
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Provenance validation failed",
                    "errors": validation.errors,
                    "warnings": validation.warnings,
                }
            )

        return _format_provenance_response(provenance)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create provenance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}/provenance", response_model=ProvenanceResponse)
async def get_template_provenance(template_id: str):
    """
    Get full provenance for a template.

    AC-3: GET /templates/{id} returns full provenance
    """
    if not HAS_PROVENANCE_SERVICE:
        raise HTTPException(status_code=503, detail="Provenance service not available")

    service = get_template_provenance_service()
    provenance = service.get_provenance(template_id)

    if not provenance:
        raise HTTPException(
            status_code=404,
            detail=f"No provenance found for template: {template_id}"
        )

    return _format_provenance_response(provenance)


@router.get("/{template_id}/provenance/summary", response_model=ProvenanceSummaryResponse)
async def get_provenance_summary(template_id: str):
    """
    Get provenance summary for search results.

    AC-4: Search results include provenance summary
    """
    if not HAS_PROVENANCE_SERVICE:
        raise HTTPException(status_code=503, detail="Provenance service not available")

    service = get_template_provenance_service()
    provenance = service.get_provenance(template_id)

    if not provenance:
        raise HTTPException(
            status_code=404,
            detail=f"No provenance found for template: {template_id}"
        )

    summary = provenance.get_summary()
    return ProvenanceSummaryResponse(**summary)


@router.post("/{template_id}/provenance/validate", response_model=ValidationResultResponse)
async def validate_template_provenance(
    template_id: str,
    require_commit: bool = Query(False, description="Require commit hash"),
):
    """Validate existing provenance for a template."""
    if not HAS_PROVENANCE_SERVICE:
        raise HTTPException(status_code=503, detail="Provenance service not available")

    service = get_template_provenance_service()
    provenance = service.get_provenance(template_id)

    if not provenance:
        raise HTTPException(
            status_code=404,
            detail=f"No provenance found for template: {template_id}"
        )

    result = service.validate_provenance(provenance, require_commit=require_commit)

    return ValidationResultResponse(
        is_valid=result.is_valid,
        errors=result.errors,
        warnings=result.warnings,
        validated_uris=result.validated_uris,
        validation_time_ms=result.validation_time_ms,
    )


@router.post("/{template_id}/citations", response_model=CitationResponse)
async def add_template_citation(
    template_id: str,
    request: CitationRequest,
):
    """
    Add a citation to a template.

    AC-5: Citations link to source artifacts with valid URIs
    """
    if not HAS_PROVENANCE_SERVICE:
        raise HTTPException(status_code=503, detail="Provenance service not available")

    try:
        service = get_template_provenance_service()

        citation = service.add_citation(
            template_id=template_id,
            citation_type=request.type,
            source_uri=request.source_uri,
            title=request.title,
            description=request.description,
            metadata=request.metadata,
        )

        if not citation:
            raise HTTPException(
                status_code=404,
                detail=f"No provenance found for template: {template_id}. "
                       f"Create provenance first."
            )

        return _format_citation_response(citation)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add citation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}/citations", response_model=List[CitationResponse])
async def get_template_citations(template_id: str):
    """Get all citations for a template."""
    if not HAS_PROVENANCE_SERVICE:
        raise HTTPException(status_code=503, detail="Provenance service not available")

    service = get_template_provenance_service()
    citations = service.get_citations(template_id)

    return [_format_citation_response(c) for c in citations]


@router.post("/{template_id}/citations/{citation_id}/verify")
async def verify_citation(template_id: str, citation_id: str):
    """
    Verify a citation URI is valid and accessible.

    AC-5: Citations link to source artifacts with valid URIs
    """
    if not HAS_PROVENANCE_SERVICE:
        raise HTTPException(status_code=503, detail="Provenance service not available")

    service = get_template_provenance_service()
    verified = service.verify_citation(template_id, citation_id)

    if not verified:
        raise HTTPException(
            status_code=404,
            detail=f"Citation not found or verification failed: {citation_id}"
        )

    return {
        "message": "Citation verified successfully",
        "citation_id": citation_id,
        "verified_at": datetime.now().isoformat(),
    }


@router.get("/{template_id}/lineage", response_model=List[LineageNodeResponse])
async def get_template_lineage(
    template_id: str,
    max_depth: int = Query(10, ge=1, le=50, description="Maximum lineage depth"),
):
    """Get lineage chain for a template."""
    if not HAS_PROVENANCE_SERVICE:
        raise HTTPException(status_code=503, detail="Provenance service not available")

    service = get_template_provenance_service()
    lineage = service.get_lineage(template_id, max_depth=max_depth)

    if not lineage:
        raise HTTPException(
            status_code=404,
            detail=f"No lineage found for template: {template_id}"
        )

    return [
        LineageNodeResponse(
            template_id=node.template_id,
            version=node.version,
            provenance_id=node.provenance_id,
            source_repo=node.source_repo,
            created_at=node.created_at,
            depth=node.depth,
        )
        for node in lineage
    ]


@router.get("/{template_id}/derived")
async def get_derived_templates(template_id: str):
    """Get templates derived from this template."""
    if not HAS_PROVENANCE_SERVICE:
        raise HTTPException(status_code=503, detail="Provenance service not available")

    service = get_template_provenance_service()
    derived = service.get_derived_templates(template_id)

    return {
        "template_id": template_id,
        "derived_templates": derived,
        "count": len(derived),
    }


@router.get("/provenance/search")
async def search_by_source(
    source_pattern: str = Query(..., description="Source pattern to search"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
):
    """Search templates by source repository pattern."""
    if not HAS_PROVENANCE_SERVICE:
        raise HTTPException(status_code=503, detail="Provenance service not available")

    service = get_template_provenance_service()
    results = service.search_by_source(source_pattern, limit=limit)

    return {
        "pattern": source_pattern,
        "results": [
            {
                "template_id": p.template_id,
                "provenance_id": p.provenance_id,
                "source": p.source.to_dict(),
                "provenance_type": p.provenance_type.value,
            }
            for p in results
        ],
        "count": len(results),
    }


@router.put("/{template_id}/provenance/validation-report")
async def update_validation_report(
    template_id: str,
    validation_report_id: str = Query(..., description="QF validation report ID"),
):
    """Update provenance with validation report ID."""
    if not HAS_PROVENANCE_SERVICE:
        raise HTTPException(status_code=503, detail="Provenance service not available")

    service = get_template_provenance_service()
    updated = service.update_validation_report(template_id, validation_report_id)

    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"No provenance found for template: {template_id}"
        )

    return {
        "message": "Validation report updated",
        "template_id": template_id,
        "validation_report_id": validation_report_id,
    }


# ============================================================================
# HELPER FUNCTION TO REGISTER ROUTER
# ============================================================================

def register_template_provenance_routes(app):
    """Register template provenance routes with a FastAPI app."""
    app.include_router(router)
    logger.info("Template provenance routes registered at /api/templates")
