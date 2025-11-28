"""
MT-400: Template Versions & Recommendation APIs Implementation
FastAPI endpoints for template version history and intelligent recommendations
"""

from fastapi import APIRouter, Query, HTTPException, Path
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


# Models
class TemplateVersion(BaseModel):
    """Single version in template history"""
    version: str = Field(..., description="Version identifier (e.g., '1.0.0', '2.1.3')")
    changes: str = Field(..., description="Changelog or description of changes")
    date: datetime = Field(..., description="Release date of this version")
    author: Optional[str] = Field(None, description="Author of this version")
    commit_sha: Optional[str] = Field(None, description="Git commit SHA if applicable")


class TemplateVersionsResponse(BaseModel):
    """Response for version history"""
    template_id: str
    current_version: str
    versions: List[TemplateVersion]
    total: int


class UsageStats(BaseModel):
    """Template usage statistics"""
    applied_count: int = Field(..., description="Number of times template was applied")
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Success rate (0.0 to 1.0)")
    avg_execution_time_ms: Optional[float] = Field(None, description="Average execution time")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")


class TemplateRecommendation(BaseModel):
    """Single template recommendation"""
    template_id: str
    name: str
    description: str
    score: int = Field(..., ge=0, le=100, description="Composite recommendation score (0-100)")
    usage_stats: UsageStats
    citations: List[str] = Field(..., description="Reference projects or golden examples")
    tags: List[str] = Field(default_factory=list)
    persona: Optional[str] = Field(None, description="Recommended for persona")


class RecommendationsResponse(BaseModel):
    """Response for template recommendations"""
    recommendations: List[TemplateRecommendation]
    total: int
    filters_applied: dict
    page: int = 1
    page_size: int = 10


# Router
router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.get("/{template_id}/versions", response_model=TemplateVersionsResponse)
async def get_template_versions(
    template_id: str = Path(..., description="Template identifier"),
    limit: int = Query(10, ge=1, le=100, description="Maximum versions to return")
):
    """
    Get version history for a template with changelog.
    
    Returns array of versions ordered from newest to oldest, including:
    - Version identifier
    - Changes/changelog
    - Release date
    - Author information
    - Git commit SHA if tracked
    
    **Example Response:**
    ```json
    {
      "template_id": "api_auth_v3",
      "current_version": "3.2.1",
      "versions": [
        {
          "version": "3.2.1",
          "changes": "Fixed OAuth2 token refresh logic",
          "date": "2025-11-27T10:00:00Z",
          "author": "john.doe",
          "commit_sha": "abc123def456"
        },
        {
          "version": "3.2.0",
          "changes": "Added support for JWT tokens",
          "date": "2025-11-15T14:30:00Z",
          "author": "jane.smith",
          "commit_sha": "def789ghi012"
        }
      ],
      "total": 12
    }
    ```
    """
    # TODO: Implementation - fetch from database/git
    # For now, return mock data based on acceptance criteria
    
    mock_versions = [
        TemplateVersion(
            version="3.2.1",
            changes="Fixed OAuth2 token refresh logic; improved error handling",
            date=datetime(2025, 11, 27, 10, 0, 0),
            author="john.doe",
            commit_sha="abc123def456"
        ),
        TemplateVersion(
            version="3.2.0",
            changes="Added support for JWT tokens; enhanced security",
            date=datetime(2025, 11, 15, 14, 30, 0),
            author="jane.smith",
            commit_sha="def789ghi012"
        ),
        TemplateVersion(
            version="3.1.0",
            changes="Initial OAuth2 implementation",
            date=datetime(2025, 10, 1, 9, 0, 0),
            author="bob.johnson",
            commit_sha="ghi345jkl678"
        )
    ]
    
    return TemplateVersionsResponse(
        template_id=template_id,
        current_version="3.2.1",
        versions=mock_versions[:limit],
        total=len(mock_versions)
    )


@router.get("/recommend", response_model=RecommendationsResponse)
async def get_template_recommendations(
    persona: Optional[str] = Query(None, description="Filter by persona (e.g., 'backend_developer', 'frontend_developer')"),
    tag: Optional[str] = Query(None, description="Filter by tag (e.g., 'auth', 'database', 'api')"),
    min_score: int = Query(0, ge=0, le=100, description="Minimum recommendation score"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    page_size: int = Query(10, ge=1, le=50, description="Results per page")
):
    """
    Get context-aware template recommendations ranked by composite score.
    
    Ranking algorithm considers:
    - Quality-Fabric (QF) test scores
    - Engine success rate metrics
    - Usage frequency and recency
    - Persona/tag relevance
    
    **Query Parameters:**
    - `persona`: Filter by target persona (backend_developer, frontend_developer, etc.)
    - `tag`: Filter by specific tag (auth, database, api, etc.)
    - `min_score`: Minimum composite score (0-100)
    - `page`: Page number for pagination
    - `page_size`: Results per page (max 50)
    
    **Composite Score Calculation:**
    - QF Score: 40% weight
    - Success Rate: 30% weight
    - Usage Frequency: 20% weight
    - Recency: 10% weight
    
    **Example Request:**
    ```
    GET /api/v1/templates/recommend?persona=backend_developer&tag=auth&min_score=85
    ```
    
    **Example Response:**
    ```json
    {
      "recommendations": [
        {
          "template_id": "api_auth_v3",
          "name": "API Authentication Template v3",
          "description": "OAuth2 + JWT authentication for REST APIs",
          "score": 92,
          "usage_stats": {
            "applied_count": 47,
            "success_rate": 0.89,
            "avg_execution_time_ms": 1234.5,
            "last_used": "2025-11-26T15:30:00Z"
          },
          "citations": ["golden-projects/api-auth", "example-apps/secure-api"],
          "tags": ["auth", "oauth2", "jwt", "api"],
          "persona": "backend_developer"
        }
      ],
      "total": 1,
      "filters_applied": {
        "persona": "backend_developer",
        "tag": "auth",
        "min_score": 85
      },
      "page": 1,
      "page_size": 10
    }
    ```
    """
    # TODO: Implementation - fetch from database with scoring algorithm
    # For now, return mock data based on acceptance criteria
    
    # Mock recommendations
    mock_recommendations = [
        TemplateRecommendation(
            template_id="api_auth_v3",
            name="API Authentication Template v3",
            description="OAuth2 + JWT authentication for REST APIs with refresh token support",
            score=92,
            usage_stats=UsageStats(
                applied_count=47,
                success_rate=0.89,
                avg_execution_time_ms=1234.5,
                last_used=datetime(2025, 11, 26, 15, 30, 0)
            ),
            citations=["golden-projects/api-auth", "example-apps/secure-api"],
            tags=["auth", "oauth2", "jwt", "api"],
            persona="backend_developer"
        ),
        TemplateRecommendation(
            template_id="rest_crud_v2",
            name="REST CRUD Operations Template",
            description="Complete CRUD operations with pagination, filtering, and validation",
            score=88,
            usage_stats=UsageStats(
                applied_count=63,
                success_rate=0.92,
                avg_execution_time_ms=890.2,
                last_used=datetime(2025, 11, 27, 10, 15, 0)
            ),
            citations=["golden-projects/rest-api", "best-practices/crud"],
            tags=["api", "rest", "crud", "database"],
            persona="backend_developer"
        ),
        TemplateRecommendation(
            template_id="react_dashboard_v1",
            name="React Dashboard Template",
            description="Modern dashboard with charts, tables, and real-time updates",
            score=85,
            usage_stats=UsageStats(
                applied_count=31,
                success_rate=0.87,
                avg_execution_time_ms=2100.8,
                last_used=datetime(2025, 11, 25, 9, 45, 0)
            ),
            citations=["golden-projects/admin-dashboard"],
            tags=["react", "dashboard", "frontend", "charts"],
            persona="frontend_developer"
        )
    ]
    
    # Apply filters
    filtered = mock_recommendations
    
    if persona:
        filtered = [r for r in filtered if r.persona == persona]
    
    if tag:
        filtered = [r for r in filtered if tag in r.tags]
    
    if min_score > 0:
        filtered = [r for r in filtered if r.score >= min_score]
    
    # Apply pagination
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated = filtered[start_idx:end_idx]
    
    return RecommendationsResponse(
        recommendations=paginated,
        total=len(filtered),
        filters_applied={
            "persona": persona,
            "tag": tag,
            "min_score": min_score
        },
        page=page,
        page_size=page_size
    )


# Health check for this module
@router.get("/health")
async def templates_health():
    """Health check for templates API"""
    return {
        "status": "healthy",
        "service": "templates-api",
        "endpoints": {
            "versions": "GET /api/v1/templates/{template_id}/versions",
            "recommendations": "GET /api/v1/templates/recommend"
        }
    }
