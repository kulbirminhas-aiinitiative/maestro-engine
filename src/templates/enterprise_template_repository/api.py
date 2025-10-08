"""
MAESTRO Enterprise Template Repository API
Version: 1.0
Purpose: Unified API for enterprise template repository with all features integrated
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from governance_dashboard import GovernanceDashboard
from multi_tenancy import MultiTenancyManager, TenantContext, TenantPlan, TenantStatus
from performance_monitor import PerformanceMonitor
from pydantic import BaseModel, Field
from quality_integration import QualityAnalysisResult, TemplateExtractor
from rbac_security import RBACSecurityManager
from semantic_search import TemplateSemanticSearch
from template_manager import (
    ComplexityLevel,
    EnterpriseTemplateRepository,
    TemplateMetadata,
    TemplateSearchQuery,
    TemplateStatus,
)
from workflow_engine import EnterpriseWorkflowEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MAESTRO Enterprise Template Repository API",
    description="AI-powered template management with semantic search and quality analysis",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
repository: Optional[EnterpriseTemplateRepository] = None
semantic_search: Optional[TemplateSemanticSearch] = None
template_extractor: Optional[TemplateExtractor] = None
workflow_engine: Optional[EnterpriseWorkflowEngine] = None
rbac_manager: Optional[RBACSecurityManager] = None
governance_dashboard: Optional[GovernanceDashboard] = None
performance_monitor: Optional[PerformanceMonitor] = None
multi_tenancy_manager: Optional[MultiTenancyManager] = None


# Pydantic models for API
class TemplateCreateRequest(BaseModel):
    name: str = Field(..., description="Template name")
    category: str = Field(..., description="Template category")
    language: str = Field(..., description="Programming language")
    description: str = Field(..., description="Template description")
    content: str = Field(..., description="Template source code")
    framework: Optional[str] = Field(None, description="Framework name")
    domain: Optional[str] = Field(None, description="Business domain")
    pattern: Optional[str] = Field(None, description="Design pattern")
    tags: List[str] = Field(default_factory=list, description="Template tags")
    complexity: str = Field("intermediate", description="Complexity level")
    test_content: Optional[str] = Field(None, description="Test code")
    examples: Optional[Dict[str, str]] = Field(None, description="Usage examples")
    created_by: str = Field("API_User", description="Creator identifier")
    organization: Optional[str] = Field(None, description="Organization name")


class TemplateSearchRequest(BaseModel):
    query: Optional[str] = Field(None, description="Search query")
    language: Optional[List[str]] = Field(None, description="Programming languages")
    framework: Optional[List[str]] = Field(None, description="Frameworks")
    domain: Optional[List[str]] = Field(None, description="Business domains")
    category: Optional[List[str]] = Field(None, description="Categories")
    tags: Optional[List[str]] = Field(None, description="Tags")
    quality_min: float = Field(0.0, description="Minimum quality score")
    complexity: Optional[List[str]] = Field(None, description="Complexity levels")
    status: Optional[List[str]] = Field(None, description="Template status")
    semantic_search: bool = Field(True, description="Enable semantic search")
    limit: int = Field(10, description="Maximum results")
    offset: int = Field(0, description="Result offset")


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., description="Natural language search query")
    filters: Optional[Dict[str, Any]] = Field(None, description="Metadata filters")
    limit: int = Field(10, description="Maximum results")
    min_similarity: float = Field(0.0, description="Minimum similarity threshold")


class RecommendationRequest(BaseModel):
    preferred_language: Optional[str] = Field(None, description="Preferred programming language")
    preferred_framework: Optional[str] = Field(None, description="Preferred framework")
    current_project_type: Optional[str] = Field(None, description="Current project type")
    working_domain: Optional[str] = Field(None, description="Working domain")
    recent_searches: Optional[List[str]] = Field(None, description="Recent search queries")
    limit: int = Field(10, description="Maximum recommendations")


class QualityAnalysisRequest(BaseModel):
    file_path: str = Field(..., description="Source file path")
    language: str = Field(..., description="Programming language")
    code_content: str = Field(..., description="Source code content")
    quality_score: float = Field(..., description="Quality score (0-100)")
    security_score: int = Field(85, description="Security score (0-100)")
    performance_score: int = Field(85, description="Performance score (0-100)")
    maintainability_score: int = Field(85, description="Maintainability score (0-100)")
    test_coverage: float = Field(0.0, description="Test coverage percentage")
    issues: List[Dict[str, Any]] = Field(default_factory=list, description="Code issues")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Code metrics")


class TemplateUsageRequest(BaseModel):
    template_id: str = Field(..., description="Template ID")
    session_id: str = Field(..., description="User session ID")
    success: bool = Field(..., description="Usage success status")
    feedback_score: Optional[int] = Field(None, description="User feedback score (1-5)")
    modifications_made: Optional[str] = Field(None, description="Modifications description")
    user_id: Optional[str] = Field(None, description="User identifier")
    organization: Optional[str] = Field(None, description="Organization name")
    project_type: Optional[str] = Field(None, description="Project type")
    generation_time_ms: Optional[int] = Field(None, description="Generation time in milliseconds")


@app.on_event("startup")
async def startup_event():
    """Initialize all components on startup"""
    global repository, semantic_search, template_extractor, workflow_engine, rbac_manager, governance_dashboard, performance_monitor, multi_tenancy_manager

    try:
        logger.info("🚀 Initializing MAESTRO Enterprise Template Repository API...")

        # Initialize repository
        repository = EnterpriseTemplateRepository()
        await repository.initialize()

        # Initialize semantic search
        semantic_search = TemplateSemanticSearch(repository)
        await semantic_search.initialize()

        # Initialize template extractor
        template_extractor = TemplateExtractor(repository)

        # Initialize enterprise components
        workflow_engine = EnterpriseWorkflowEngine(repository.db_config)
        await workflow_engine.initialize()

        rbac_manager = RBACSecurityManager(repository.db_config)
        await rbac_manager.initialize()

        governance_dashboard = GovernanceDashboard(repository.db_config)
        await governance_dashboard.initialize()

        performance_monitor = PerformanceMonitor(repository.db_config)
        await performance_monitor.initialize()

        multi_tenancy_manager = MultiTenancyManager(repository.db_config)
        await multi_tenancy_manager.initialize()

        # Update embeddings for existing templates
        await semantic_search.update_embeddings_batch(batch_size=50)

        # Start performance monitoring in background
        asyncio.create_task(performance_monitor.start_monitoring())

        logger.info(
            "✅ MAESTRO Enterprise Template Repository API ready with full enterprise features including multi-tenancy!"
        )

    except Exception as e:
        logger.error(f"❌ Failed to initialize API: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    if multi_tenancy_manager:
        await multi_tenancy_manager.cleanup()
    if performance_monitor:
        await performance_monitor.cleanup()
    if governance_dashboard:
        await governance_dashboard.cleanup()
    if rbac_manager:
        await rbac_manager.cleanup()
    if workflow_engine:
        await workflow_engine.cleanup()
    if semantic_search:
        await semantic_search.close()
    if repository:
        await repository.close()
    logger.info("✅ API shutdown completed")


# Health check endpoints
@app.get("/health")
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "service": "MAESTRO Enterprise Template Repository API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with component status"""
    try:
        health_status = {
            "status": "healthy",
            "service": "MAESTRO Enterprise Template Repository API",
            "version": "1.0.0",
            "components": {},
        }

        # Check repository
        if repository:
            try:
                async with repository.db_pool.acquire() as conn:
                    await conn.execute("SELECT 1")
                health_status["components"]["repository"] = {"status": "healthy"}
            except Exception as e:
                health_status["components"]["repository"] = {"status": "unhealthy", "error": str(e)}
                health_status["status"] = "degraded"

        # Check semantic search
        if semantic_search:
            try:
                collection_count = semantic_search.collection.count()
                health_status["components"]["semantic_search"] = {
                    "status": "healthy",
                    "embeddings_count": collection_count,
                }
            except Exception as e:
                health_status["components"]["semantic_search"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                health_status["status"] = "degraded"

        # Check performance monitor
        if performance_monitor:
            try:
                dashboard = await performance_monitor.get_performance_dashboard()
                health_status["components"]["performance_monitor"] = {"status": "healthy"}
            except Exception as e:
                health_status["components"]["performance_monitor"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                health_status["status"] = "degraded"
        else:
            health_status["components"]["performance_monitor"] = {"status": "not_initialized"}
            health_status["status"] = "degraded"

        return health_status

    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()}


# Template management endpoints
@app.post("/templates", response_model=Dict[str, str])
async def create_template(request: TemplateCreateRequest):
    """Create a new template"""
    try:
        # Convert complexity string to enum
        complexity_mapping = {
            "simple": ComplexityLevel.SIMPLE,
            "intermediate": ComplexityLevel.INTERMEDIATE,
            "advanced": ComplexityLevel.ADVANCED,
            "expert": ComplexityLevel.EXPERT,
        }
        complexity = complexity_mapping.get(
            request.complexity.lower(), ComplexityLevel.INTERMEDIATE
        )

        # Create metadata
        metadata = TemplateMetadata(
            name=request.name,
            category=request.category,
            language=request.language,
            framework=request.framework,
            domain=request.domain,
            pattern=request.pattern,
            description=request.description,
            tags=request.tags,
            complexity=complexity,
            created_by=request.created_by,
            organization=request.organization,
        )

        # Create template
        template_id = await repository.create_template(
            request.content, metadata, request.test_content, request.examples
        )

        # Add embedding for semantic search
        if semantic_search:
            try:
                vector_id = await semantic_search.add_template_embedding(
                    template_id, metadata.to_dict(), request.content
                )
                logger.info(f"✅ Added embedding for new template: {vector_id}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to add embedding: {e}")

        return {
            "template_id": template_id,
            "message": "Template created successfully",
            "status": "success",
        }

    except Exception as e:
        logger.error(f"❌ Failed to create template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/templates/{template_id}")
async def get_template(template_id: str, version: Optional[str] = None):
    """Get template by ID"""
    try:
        template = await repository.get_template(template_id, version)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        return template

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/templates/search")
async def search_templates(request: TemplateSearchRequest):
    """Search templates with metadata and semantic search"""
    try:
        # Convert to internal search query
        complexity_enums = []
        if request.complexity:
            complexity_mapping = {
                "simple": ComplexityLevel.SIMPLE,
                "intermediate": ComplexityLevel.INTERMEDIATE,
                "advanced": ComplexityLevel.ADVANCED,
                "expert": ComplexityLevel.EXPERT,
            }
            complexity_enums = [
                complexity_mapping.get(c.lower())
                for c in request.complexity
                if complexity_mapping.get(c.lower())
            ]

        status_enums = []
        if request.status:
            status_mapping = {
                "draft": TemplateStatus.DRAFT,
                "review": TemplateStatus.REVIEW,
                "approved": TemplateStatus.APPROVED,
                "deprecated": TemplateStatus.DEPRECATED,
            }
            status_enums = [
                status_mapping.get(s.lower())
                for s in request.status
                if status_mapping.get(s.lower())
            ]

        search_query = TemplateSearchQuery(
            query=request.query,
            language=request.language,
            framework=request.framework,
            domain=request.domain,
            category=request.category,
            tags=request.tags,
            quality_min=request.quality_min,
            complexity=complexity_enums,
            status=status_enums or [TemplateStatus.APPROVED],
            semantic_search=request.semantic_search,
            limit=request.limit,
            offset=request.offset,
        )

        # Perform search
        if request.semantic_search and request.query and semantic_search:
            results = await semantic_search.hybrid_search(search_query)
        else:
            results = await repository.search_templates(search_query)

        return {
            "templates": results,
            "total": len(results),
            "query": request.query,
            "filters_applied": {
                "language": request.language,
                "framework": request.framework,
                "domain": request.domain,
                "semantic_search": request.semantic_search,
            },
        }

    except Exception as e:
        logger.error(f"❌ Template search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/templates/semantic-search")
async def semantic_search_templates(request: SemanticSearchRequest):
    """Perform semantic search on templates"""
    try:
        if not semantic_search:
            raise HTTPException(status_code=503, detail="Semantic search not available")

        results = await semantic_search.semantic_search(
            request.query, request.filters, request.limit, request.min_similarity
        )

        return {
            "results": [
                {
                    "template_id": r.template_id,
                    "template_name": r.template_name,
                    "similarity_score": r.similarity_score,
                    "metadata": r.metadata,
                    "content_snippet": r.content_snippet,
                }
                for r in results
            ],
            "total": len(results),
            "query": request.query,
            "min_similarity": request.min_similarity,
        }

    except Exception as e:
        logger.error(f"❌ Semantic search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/templates/recommendations")
async def get_recommendations(request: RecommendationRequest):
    """Get template recommendations based on user context"""
    try:
        if not semantic_search:
            raise HTTPException(status_code=503, detail="Recommendation service not available")

        user_context = {
            "preferred_language": request.preferred_language,
            "preferred_framework": request.preferred_framework,
            "current_project_type": request.current_project_type,
            "working_domain": request.working_domain,
            "recent_searches": request.recent_searches or [],
        }

        recommendations = await semantic_search.get_recommendations(user_context, request.limit)

        return {
            "recommendations": recommendations,
            "total": len(recommendations),
            "context": user_context,
        }

    except Exception as e:
        logger.error(f"❌ Failed to get recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/templates/{template_id}/similar")
async def get_similar_templates(template_id: str, limit: int = Query(5, ge=1, le=20)):
    """Find templates similar to the given template"""
    try:
        if not semantic_search:
            raise HTTPException(status_code=503, detail="Semantic search not available")

        similar_templates = await semantic_search.find_similar_templates(template_id, limit)

        return {
            "similar_templates": [
                {
                    "template_id": r.template_id,
                    "template_name": r.template_name,
                    "similarity_score": r.similarity_score,
                    "metadata": r.metadata,
                }
                for r in similar_templates
            ],
            "reference_template_id": template_id,
            "total": len(similar_templates),
        }

    except Exception as e:
        logger.error(f"❌ Failed to find similar templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Quality analysis integration
@app.post("/quality-analysis/extract-templates")
async def extract_templates_from_quality_analysis(request: QualityAnalysisRequest):
    """Extract templates from quality analysis results"""
    try:
        if not template_extractor:
            raise HTTPException(status_code=503, detail="Template extraction not available")

        # Convert request to QualityAnalysisResult
        analysis_result = QualityAnalysisResult(
            file_path=request.file_path,
            language=request.language,
            quality_score=request.quality_score,
            security_score=request.security_score,
            performance_score=request.performance_score,
            maintainability_score=request.maintainability_score,
            test_coverage=request.test_coverage,
            issues=request.issues,
            metrics=request.metrics,
            code_content=request.code_content,
        )

        # Extract templates
        created_templates = await template_extractor.process_quality_analysis_result(
            analysis_result
        )

        return {
            "extracted_templates": created_templates,
            "total_extracted": len(created_templates),
            "source_file": request.file_path,
            "quality_score": request.quality_score,
        }

    except Exception as e:
        logger.error(f"❌ Template extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Usage tracking
@app.post("/templates/usage")
async def track_template_usage(request: TemplateUsageRequest):
    """Track template usage for analytics"""
    try:
        context = {
            "user_id": request.user_id,
            "organization": request.organization,
            "project_type": request.project_type,
            "generation_time_ms": request.generation_time_ms,
        }

        await repository.track_template_usage(
            request.template_id,
            request.session_id,
            request.success,
            request.feedback_score,
            request.modifications_made,
            context,
        )

        return {
            "message": "Usage tracked successfully",
            "template_id": request.template_id,
            "success": request.success,
        }

    except Exception as e:
        logger.error(f"❌ Failed to track usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Analytics endpoints
@app.get("/analytics/templates/{template_id}")
async def get_template_analytics(template_id: str):
    """Get analytics for a specific template"""
    try:
        analytics = await repository.get_template_analytics(template_id)
        return analytics

    except Exception as e:
        logger.error(f"❌ Failed to get template analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/repository")
async def get_repository_analytics():
    """Get repository-wide analytics"""
    try:
        analytics = {}

        # Repository stats
        async with repository.db_pool.acquire() as conn:
            # Template counts by status
            status_counts = await conn.fetch(
                """
                SELECT status, COUNT(*) as count
                FROM templates
                GROUP BY status
            """
            )

            # Language distribution
            language_counts = await conn.fetch(
                """
                SELECT language, COUNT(*) as count
                FROM templates
                WHERE status = 'approved'
                GROUP BY language
                ORDER BY count DESC
                LIMIT 10
            """
            )

            # Quality distribution
            quality_stats = await conn.fetchrow(
                """
                SELECT
                    AVG(quality_score) as avg_quality,
                    MIN(quality_score) as min_quality,
                    MAX(quality_score) as max_quality,
                    COUNT(CASE WHEN quality_score >= 90 THEN 1 END) as high_quality_count
                FROM templates
                WHERE status = 'approved'
            """
            )

        analytics = {
            "repository_stats": {
                "status_distribution": {row["status"]: row["count"] for row in status_counts},
                "language_distribution": {row["language"]: row["count"] for row in language_counts},
                "quality_metrics": dict(quality_stats) if quality_stats else {},
            }
        }

        # Semantic search stats
        if semantic_search:
            search_analytics = await semantic_search.get_search_analytics()
            analytics["search_stats"] = search_analytics

        analytics["generated_at"] = datetime.now().isoformat()

        return analytics

    except Exception as e:
        logger.error(f"❌ Failed to get repository analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Admin endpoints
@app.post("/admin/update-embeddings")
async def update_embeddings(batch_size: int = Query(100, ge=1, le=500)):
    """Update embeddings for templates missing them"""
    try:
        if not semantic_search:
            raise HTTPException(status_code=503, detail="Semantic search not available")

        await semantic_search.update_embeddings_batch(batch_size)

        return {
            "message": f"Embedding update completed for batch size {batch_size}",
            "status": "success",
        }

    except Exception as e:
        logger.error(f"❌ Failed to update embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Root endpoint
@app.get("/")
async def root():
    """API information"""
    return {
        "service": "MAESTRO Enterprise Template Repository API",
        "version": "1.0.0",
        "description": "AI-powered template management with semantic search and quality analysis",
        "features": [
            "Template CRUD operations",
            "AI-powered semantic search",
            "Quality analysis integration",
            "Usage analytics",
            "Template recommendations",
            "Enterprise governance",
        ],
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "templates": "/templates",
            "search": "/templates/search",
            "semantic_search": "/templates/semantic-search",
            "recommendations": "/templates/recommendations",
        },
        "timestamp": datetime.now().isoformat(),
    }


# Performance monitoring API endpoints
@app.get("/performance/dashboard")
async def get_performance_dashboard():
    """Get real-time performance dashboard"""
    if not performance_monitor:
        raise HTTPException(status_code=503, detail="Performance monitor not available")

    try:
        dashboard_data = await performance_monitor.get_performance_dashboard()
        return dashboard_data
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get performance dashboard: {str(e)}"
        )


@app.get("/performance/recommendations")
async def get_performance_recommendations():
    """Get performance optimization recommendations"""
    if not performance_monitor:
        raise HTTPException(status_code=503, detail="Performance monitor not available")

    try:
        recommendations = await performance_monitor.get_optimization_recommendations()
        return recommendations
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@app.get("/governance/dashboard")
async def get_governance_dashboard():
    """Get governance dashboard"""
    if not governance_dashboard:
        raise HTTPException(status_code=503, detail="Governance dashboard not available")

    try:
        dashboard_data = await governance_dashboard.get_governance_overview()
        return dashboard_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get governance dashboard: {str(e)}")


@app.get("/governance/compliance")
async def get_compliance_report():
    """Get compliance report"""
    if not governance_dashboard:
        raise HTTPException(status_code=503, detail="Governance dashboard not available")

    try:
        compliance_data = await governance_dashboard.get_compliance_report()
        return compliance_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get compliance report: {str(e)}")


# Multi-tenancy API endpoints
@app.post("/tenants")
async def create_tenant(
    organization_name: str = Body(...),
    display_name: str = Body(...),
    plan: str = Body(...),
    created_by: str = Body(...),
    custom_config: Optional[Dict[str, Any]] = Body(None),
):
    """Create new tenant"""
    if not multi_tenancy_manager:
        raise HTTPException(status_code=503, detail="Multi-tenancy not available")

    try:
        tenant_plan = TenantPlan(plan)
        tenant_id = await multi_tenancy_manager.create_tenant(
            organization_name, display_name, tenant_plan, created_by, custom_config
        )
        return {"tenant_id": tenant_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create tenant: {str(e)}")


@app.get("/tenants")
async def list_tenants(
    status: Optional[str] = Query(None),
    plan: Optional[str] = Query(None),
    parent_tenant: Optional[str] = Query(None),
):
    """List tenants with filters"""
    if not multi_tenancy_manager:
        raise HTTPException(status_code=503, detail="Multi-tenancy not available")

    try:
        status_filter = TenantStatus(status) if status else None
        plan_filter = TenantPlan(plan) if plan else None

        tenants = await multi_tenancy_manager.list_tenants(
            status_filter, plan_filter, parent_tenant
        )

        return [
            {
                "tenant_id": t.tenant_id,
                "organization_name": t.organization_name,
                "display_name": t.display_name,
                "status": t.status.value,
                "plan": t.plan.value,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tenants
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tenants: {str(e)}")


@app.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: str):
    """Get tenant details"""
    if not multi_tenancy_manager:
        raise HTTPException(status_code=503, detail="Multi-tenancy not available")

    try:
        tenant = await multi_tenancy_manager.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        return {
            "tenant_id": tenant.tenant_id,
            "organization_name": tenant.organization_name,
            "display_name": tenant.display_name,
            "status": tenant.status.value,
            "plan": tenant.plan.value,
            "custom_domain": tenant.custom_domain,
            "features": tenant.features,
            "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tenant: {str(e)}")


@app.get("/tenants/{tenant_id}/quotas")
async def get_tenant_quotas(tenant_id: str):
    """Get tenant resource quotas"""
    if not multi_tenancy_manager:
        raise HTTPException(status_code=503, detail="Multi-tenancy not available")

    try:
        quotas = await multi_tenancy_manager.get_tenant_quotas(tenant_id)
        return [
            {
                "resource_type": q.resource_type.value,
                "quota_limit": q.quota_limit,
                "current_usage": q.current_usage,
                "usage_percent": (
                    round((q.current_usage / q.quota_limit) * 100, 2) if q.quota_limit > 0 else 0
                ),
                "warning_threshold": q.warning_threshold,
                "hard_limit_reached": q.hard_limit_reached,
            }
            for q in quotas
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get quotas: {str(e)}")


@app.get("/tenants/{tenant_id}/usage")
async def get_tenant_usage(tenant_id: str, days: int = Query(30)):
    """Get tenant usage metrics"""
    if not multi_tenancy_manager:
        raise HTTPException(status_code=503, detail="Multi-tenancy not available")

    try:
        start_date = datetime.now() - timedelta(days=days)
        metrics = await multi_tenancy_manager.get_tenant_usage_metrics(tenant_id, start_date)

        return [
            {
                "date": m.period_start.date().isoformat(),
                "templates_created": m.templates_created,
                "templates_accessed": m.templates_accessed,
                "api_requests": m.api_requests,
                "unique_users": m.unique_users,
                "storage_used_gb": float(m.storage_used_gb),
                "search_queries": m.search_queries,
            }
            for m in metrics
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get usage: {str(e)}")


@app.get("/analytics/multi-tenant")
async def get_multi_tenant_analytics():
    """Get multi-tenant analytics overview"""
    if not multi_tenancy_manager:
        raise HTTPException(status_code=503, detail="Multi-tenancy not available")

    try:
        analytics = await multi_tenancy_manager.get_multi_tenant_analytics()
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.environ.get("PORT", 4006))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True, log_level="info")
