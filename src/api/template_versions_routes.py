#!/usr/bin/env python3
"""
Template Versions & Recommendation API Routes for MAESTRO Engine
Implements Epic MD-1831: [MT-400] Template Versions & Recommendation APIs

REST API endpoints for template versions and recommendations:
- GET /api/templates/{id}/versions - Get version history
- GET /api/templates/{id}/versions/{version} - Get specific version details
- POST /api/templates/{id}/versions - Create new version
- GET /api/templates/recommend - Get template recommendations
- POST /api/templates/{id}/usage - Record template usage

Acceptance Criteria Coverage:
- AC-1: Versions API returns array with version, changes, date
- AC-2: Recommend API accepts persona, tag, min_score params
- AC-3: Recommendations ranked by composite score
- AC-4: Response includes usage_stats and citations
- AC-5: Pagination support for large result sets
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, validator

# Import versions service
try:
    from services.template_versions_service import (
        get_template_versions_service,
        TemplateVersion,
        UsageStats,
        TemplateRecommendation,
        RecommendationRequest,
        RecommendationResponse,
        VersionChangeType,
        RecommendationStrategy,
    )
    HAS_VERSIONS_SERVICE = True
except ImportError:
    HAS_VERSIONS_SERVICE = False

logger = logging.getLogger("template_versions_routes")

# Create router
router = APIRouter(prefix="/api/templates", tags=["template-versions"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CreateVersionRequest(BaseModel):
    """Request to create a new template version."""
    version: str = Field(..., description="Semantic version (e.g., '1.2.0')")
    changes: List[str] = Field(..., description="List of change descriptions")
    changelog: str = Field(..., description="Full changelog entry")
    created_by: str = Field(..., description="User/agent creating the version")
    change_type: str = Field("minor", description="Type: major, minor, patch, initial")
    commit_hash: Optional[str] = Field(None, description="Git commit hash")
    validation_report_id: Optional[str] = Field(None, description="QF validation report ID")
    quality_score: Optional[float] = Field(None, ge=0, le=100, description="Quality score")

    @validator("change_type")
    def validate_change_type(cls, v):
        valid_types = ["major", "minor", "patch", "initial"]
        if v not in valid_types:
            raise ValueError(f"change_type must be one of {valid_types}")
        return v


class VersionResponse(BaseModel):
    """Response for a single version."""
    version: str
    template_id: str
    created_at: str
    created_by: str
    change_type: str
    changes: List[str]
    changelog: str
    parent_version: Optional[str]
    commit_hash: Optional[str]
    validation_report_id: Optional[str]
    quality_score: Optional[float]


class VersionListResponse(BaseModel):
    """
    Response for version history.

    AC-1: Returns array with version, changes, date
    """
    versions: List[VersionResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class UsageStatsResponse(BaseModel):
    """Usage statistics response."""
    applied_count: int
    success_rate: float
    avg_quality_score: float
    last_used_at: Optional[str]
    unique_users: int
    unique_projects: int


class RecommendationItemResponse(BaseModel):
    """Single recommendation item response."""
    template_id: str
    template_name: str
    version: str
    score: float
    quality_score: float
    usage_stats: UsageStatsResponse
    citations: List[str]
    match_reasons: List[str]
    persona_match: bool
    tag_match: bool
    metadata: Dict[str, Any]


class RecommendationsResponse(BaseModel):
    """
    Response for recommendations.

    AC-3: Recommendations ranked by composite score
    AC-4: Response includes usage_stats and citations
    AC-5: Pagination support
    """
    recommendations: List[RecommendationItemResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
    filters_applied: Dict[str, Any]
    strategy_used: str


class RecordUsageRequest(BaseModel):
    """Request to record template usage."""
    success: bool = Field(..., description="Whether the usage was successful")
    quality_score: Optional[float] = Field(None, description="Quality score if available")
    user_id: Optional[str] = Field(None, description="User ID")
    project_id: Optional[str] = Field(None, description="Project ID")


class VersionServiceConfigResponse(BaseModel):
    """Version service configuration response."""
    feature_flag_enabled: bool
    scoring_weights: Dict[str, float]
    supported_strategies: List[str]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _format_version_response(version: TemplateVersion) -> VersionResponse:
    """Convert TemplateVersion to API response."""
    return VersionResponse(
        version=version.version,
        template_id=version.template_id,
        created_at=version.created_at.isoformat(),
        created_by=version.created_by,
        change_type=version.change_type.value,
        changes=version.changes,
        changelog=version.changelog,
        parent_version=version.parent_version,
        commit_hash=version.commit_hash,
        validation_report_id=version.validation_report_id,
        quality_score=version.quality_score,
    )


def _format_usage_stats_response(stats: UsageStats) -> UsageStatsResponse:
    """Convert UsageStats to API response."""
    return UsageStatsResponse(
        applied_count=stats.applied_count,
        success_rate=round(stats.success_rate, 3),
        avg_quality_score=round(stats.avg_quality_score, 2),
        last_used_at=stats.last_used_at.isoformat() if stats.last_used_at else None,
        unique_users=stats.unique_users,
        unique_projects=stats.unique_projects,
    )


def _format_recommendation_response(rec: TemplateRecommendation) -> RecommendationItemResponse:
    """Convert TemplateRecommendation to API response."""
    return RecommendationItemResponse(
        template_id=rec.template_id,
        template_name=rec.template_name,
        version=rec.version,
        score=round(rec.score, 2),
        quality_score=round(rec.quality_score, 2),
        usage_stats=_format_usage_stats_response(rec.usage_stats),
        citations=rec.citations,
        match_reasons=rec.match_reasons,
        persona_match=rec.persona_match,
        tag_match=rec.tag_match,
        metadata=rec.metadata,
    )


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/versions/health")
async def versions_service_health():
    """Health check for versions service."""
    return {
        "status": "healthy" if HAS_VERSIONS_SERVICE else "unavailable",
        "service": "template-versions",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/versions/config", response_model=VersionServiceConfigResponse)
async def get_versions_config():
    """Get version service configuration."""
    if not HAS_VERSIONS_SERVICE:
        raise HTTPException(status_code=503, detail="Versions service not available")

    service = get_template_versions_service()

    return VersionServiceConfigResponse(
        feature_flag_enabled=service.feature_flag_enabled,
        scoring_weights=service.scoring_weights,
        supported_strategies=[s.value for s in RecommendationStrategy],
    )


@router.get("/{template_id}/versions", response_model=VersionListResponse)
async def get_template_versions(
    template_id: str,
    limit: int = Query(20, ge=1, le=100, description="Maximum versions to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Get version history for a template.

    AC-1: Returns array with version, changes, date
    """
    if not HAS_VERSIONS_SERVICE:
        raise HTTPException(status_code=503, detail="Versions service not available")

    service = get_template_versions_service()
    versions, total = service.get_template_versions(template_id, limit=limit, offset=offset)

    if not versions and total == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No versions found for template: {template_id}"
        )

    return VersionListResponse(
        versions=[_format_version_response(v) for v in versions],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get("/{template_id}/versions/{version}", response_model=VersionResponse)
async def get_version_details(template_id: str, version: str):
    """Get details for a specific version."""
    if not HAS_VERSIONS_SERVICE:
        raise HTTPException(status_code=503, detail="Versions service not available")

    service = get_template_versions_service()
    version_obj = service.get_version_details(template_id, version)

    if not version_obj:
        raise HTTPException(
            status_code=404,
            detail=f"Version {version} not found for template: {template_id}"
        )

    return _format_version_response(version_obj)


@router.post("/{template_id}/versions", response_model=VersionResponse)
async def create_template_version(
    template_id: str,
    request: CreateVersionRequest,
):
    """
    Create a new version for a template.

    Supports semantic versioning with change tracking.
    """
    if not HAS_VERSIONS_SERVICE:
        raise HTTPException(status_code=503, detail="Versions service not available")

    try:
        service = get_template_versions_service()

        # Convert change_type string to enum
        change_type = VersionChangeType(request.change_type)

        version = service.create_version(
            template_id=template_id,
            version=request.version,
            changes=request.changes,
            changelog=request.changelog,
            created_by=request.created_by,
            change_type=change_type,
            commit_hash=request.commit_hash,
            validation_report_id=request.validation_report_id,
            quality_score=request.quality_score,
        )

        return _format_version_response(version)

    except Exception as e:
        logger.error(f"Failed to create version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommend", response_model=RecommendationsResponse)
async def get_recommendations(
    persona: Optional[str] = Query(None, description="Filter by persona (AC-2)"),
    tags: Optional[str] = Query(None, description="Comma-separated tags (AC-2)"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum quality score (AC-2)"),
    language: Optional[str] = Query(None, description="Filter by programming language"),
    framework: Optional[str] = Query(None, description="Filter by framework"),
    category: Optional[str] = Query(None, description="Filter by category"),
    strategy: str = Query("composite", description="Ranking strategy: composite, quality_first, usage_first, recent_first"),
    include_usage_stats: bool = Query(True, description="Include usage statistics (AC-4)"),
    include_citations: bool = Query(True, description="Include citations (AC-4)"),
    limit: int = Query(10, ge=1, le=50, description="Page size (AC-5)"),
    offset: int = Query(0, ge=0, description="Offset for pagination (AC-5)"),
):
    """
    Get template recommendations based on context.

    AC-2: Accepts persona, tag, min_score params
    AC-3: Recommendations ranked by composite score
    AC-4: Response includes usage_stats and citations
    AC-5: Pagination support for large result sets
    """
    if not HAS_VERSIONS_SERVICE:
        raise HTTPException(status_code=503, detail="Versions service not available")

    try:
        service = get_template_versions_service()

        # Parse tags from comma-separated string
        tag_list = [t.strip() for t in tags.split(",")] if tags else None

        # Convert strategy string to enum
        try:
            strategy_enum = RecommendationStrategy(strategy)
        except ValueError:
            strategy_enum = RecommendationStrategy.COMPOSITE

        # Build request
        request = RecommendationRequest(
            persona=persona,
            tags=tag_list,
            min_score=min_score,
            language=language,
            framework=framework,
            category=category,
            limit=limit,
            offset=offset,
            strategy=strategy_enum,
            include_usage_stats=include_usage_stats,
            include_citations=include_citations,
        )

        response = service.get_recommendations(request)

        return RecommendationsResponse(
            recommendations=[_format_recommendation_response(r) for r in response.recommendations],
            total=response.total,
            page=response.page,
            page_size=response.page_size,
            has_more=response.has_more,
            filters_applied=response.filters_applied,
            strategy_used=response.strategy_used,
        )

    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/usage")
async def record_template_usage(
    template_id: str,
    request: RecordUsageRequest,
):
    """Record template usage for statistics tracking."""
    if not HAS_VERSIONS_SERVICE:
        raise HTTPException(status_code=503, detail="Versions service not available")

    try:
        service = get_template_versions_service()

        service.record_template_usage(
            template_id=template_id,
            success=request.success,
            quality_score=request.quality_score,
            user_id=request.user_id,
            project_id=request.project_id,
        )

        return {
            "message": "Usage recorded successfully",
            "template_id": template_id,
            "success": request.success,
            "recorded_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to record usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}/usage-stats", response_model=UsageStatsResponse)
async def get_template_usage_stats(template_id: str):
    """Get usage statistics for a template."""
    if not HAS_VERSIONS_SERVICE:
        raise HTTPException(status_code=503, detail="Versions service not available")

    service = get_template_versions_service()
    stats = service.get_usage_stats(template_id)

    if not stats:
        raise HTTPException(
            status_code=404,
            detail=f"No usage stats found for template: {template_id}"
        )

    return _format_usage_stats_response(stats)


# ============================================================================
# HELPER FUNCTION TO REGISTER ROUTER
# ============================================================================

def register_template_versions_routes(app):
    """Register template versions routes with a FastAPI app."""
    app.include_router(router)
    logger.info("Template versions routes registered at /api/templates")
