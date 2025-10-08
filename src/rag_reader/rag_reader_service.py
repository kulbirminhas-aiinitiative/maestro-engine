#!/usr/bin/env python3
"""
RAG Reader Service - FastAPI Microservice for RAG Queries
Port: 9801
Provides cached, rate-limited access to RAG knowledge base
"""

import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.persona_domains import (
    get_persona_domain,
    get_relevant_templates_for_persona,
    match_template_to_persona,
)
from rag.persona_rag_tools import _load_maestro_templates
from rag_system.pattern_recommender import PatternRecommender
from rag_system.vector_rag_manager import get_rag_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Redis configuration
REDIS_AVAILABLE = False
try:
    import redis

    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=int(os.getenv("REDIS_DB", 2)),
        decode_responses=True,
    )
    redis_client.ping()
    REDIS_AVAILABLE = True
    logger.info("✅ Redis connection established")
except Exception as e:
    logger.warning(f"⚠️  Redis not available: {e}. Caching disabled.")
    redis_client = None

# FastAPI app
app = FastAPI(
    title="MAESTRO RAG Reader Service",
    description="Cached, rate-limited access to RAG knowledge base for persona-level template queries",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Keys (in production, load from environment or secrets manager)
VALID_API_KEYS = {
    os.getenv("RAG_READER_API_KEY", "dev_rag_reader_key_12345"): "maestro_engine",
    os.getenv("FRONTEND_API_KEY", "dev_frontend_key_67890"): "maestro_frontend",
}

# Rate limiting configuration
RATE_LIMIT_REQUESTS = 100  # requests per window
RATE_LIMIT_WINDOW = 60  # seconds
rate_limit_store: Dict[str, List[datetime]] = {}

# Cache TTL (seconds)
CACHE_TTL_SHORT = 300  # 5 minutes for fast-changing data
CACHE_TTL_MEDIUM = 1800  # 30 minutes for templates
CACHE_TTL_LONG = 3600  # 1 hour for personas


# ==============================================================================
# Authentication & Rate Limiting
# ==============================================================================


def verify_api_key(x_api_key: str = Header(...)) -> str:
    """Verify API key from header"""
    if x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return VALID_API_KEYS[x_api_key]


def check_rate_limit(request: Request, client: str = Depends(verify_api_key)):
    """Check rate limit for client"""
    now = datetime.now()

    # Initialize client if not exists
    if client not in rate_limit_store:
        rate_limit_store[client] = []

    # Clean old requests outside window
    cutoff = now - timedelta(seconds=RATE_LIMIT_WINDOW)
    rate_limit_store[client] = [
        req_time for req_time in rate_limit_store[client] if req_time > cutoff
    ]

    # Check limit
    if len(rate_limit_store[client]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s",
        )

    # Record request
    rate_limit_store[client].append(now)

    return client


# ==============================================================================
# Caching Utilities
# ==============================================================================


def get_cache_key(prefix: str, params: Dict[str, Any]) -> str:
    """Generate cache key from prefix and parameters"""
    # Create deterministic key from params
    param_str = json.dumps(params, sort_keys=True)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:12]
    return f"rag_reader:{prefix}:{param_hash}"


def get_cached_response(cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached response if available"""
    if not REDIS_AVAILABLE:
        return None

    try:
        cached = redis_client.get(cache_key)
        if cached:
            logger.info(f"✅ Cache hit: {cache_key}")
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")

    return None


def set_cached_response(cache_key: str, response: Dict[str, Any], ttl: int):
    """Set cached response with TTL"""
    if not REDIS_AVAILABLE:
        return

    try:
        redis_client.setex(cache_key, ttl, json.dumps(response))
        logger.info(f"✅ Cached response: {cache_key} (TTL: {ttl}s)")
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")


# ==============================================================================
# Request/Response Models
# ==============================================================================


class TemplateQueryRequest(BaseModel):
    """Request model for template queries"""

    persona_id: str = Field(..., description="Persona identifier")
    requirement: str = Field(..., description="Requirement or task description")
    top_k: int = Field(5, description="Number of templates to return", ge=1, le=50)
    min_quality_score: float = Field(0.0, description="Minimum quality score", ge=0.0, le=100.0)


class SimilarExecutionsRequest(BaseModel):
    """Request model for similar executions query"""

    requirement: str = Field(..., description="Requirement to find similar executions for")
    top_k: int = Field(3, description="Number of executions to return", ge=1, le=20)
    min_quality: float = Field(0.0, description="Minimum quality score", ge=0.0, le=1.0)
    persona_filter: Optional[str] = Field(None, description="Filter by persona involvement")


class TeamRecommendationRequest(BaseModel):
    """Request model for team recommendation"""

    requirement: str = Field(..., description="Requirement to get team recommendation for")
    max_team_size: int = Field(10, description="Maximum team size", ge=1, le=20)


class BestPracticesRequest(BaseModel):
    """Request model for best practices"""

    persona_id: str = Field(..., description="Persona identifier")
    task_type: Optional[str] = Field(None, description="Specific task type (optional)")


# ==============================================================================
# API Endpoints
# ==============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "rag_reader",
        "version": "1.0.0",
        "port": 9801,
        "redis_available": REDIS_AVAILABLE,
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/v1/query/templates")
async def query_templates(request: TemplateQueryRequest, client: str = Depends(check_rate_limit)):
    """
    Query templates relevant to a persona's domain

    Returns templates from maestro-templates filtered and ranked by persona relevance
    """
    try:
        # Check cache
        cache_key = get_cache_key(
            "templates",
            {
                "persona_id": request.persona_id,
                "requirement": request.requirement,
                "top_k": request.top_k,
                "min_quality": request.min_quality_score,
            },
        )

        cached = get_cached_response(cache_key)
        if cached:
            cached["_cache_hit"] = True
            return JSONResponse(content=cached)

        # Load templates
        all_templates = _load_maestro_templates()

        if not all_templates:
            return JSONResponse(
                content={
                    "persona_id": request.persona_id,
                    "templates_found": 0,
                    "templates": [],
                    "message": "No templates available",
                    "cached": False,
                }
            )

        # Get persona domain
        domain = get_persona_domain(request.persona_id)

        # Filter relevant templates
        relevant_templates = get_relevant_templates_for_persona(request.persona_id, all_templates)

        # Filter by quality score
        quality_filtered = [
            t for t in relevant_templates if t.get("quality_score", 0) >= request.min_quality_score
        ]

        # Take top K
        top_templates = quality_filtered[: request.top_k]

        # Format response
        response = {
            "persona_id": request.persona_id,
            "requirement": request.requirement,
            "persona_domain": {
                "categories": domain.get("template_categories", []),
                "languages": domain.get("languages", []),
                "frameworks": domain.get("frameworks", []),
            },
            "templates_found": len(top_templates),
            "total_available": len(all_templates),
            "templates": [
                {
                    "id": t.get("id", "unknown"),
                    "name": t.get("name", "Unnamed"),
                    "category": t.get("category", "general"),
                    "language": t.get("language", "unknown"),
                    "framework": t.get("framework", "none"),
                    "description": t.get("description", ""),
                    "quality_score": t.get("quality_score", 0),
                    "security_score": t.get("security_score", 0),
                    "performance_score": t.get("performance_score", 0),
                    "maintainability_score": t.get("maintainability_score", 0),
                    "tags": t.get("tags", []),
                    "relevance_score": t.get("_relevance_score", 0),
                    "file_path": t.get("file_path", ""),
                }
                for t in top_templates
            ],
            "cached": False,
            "timestamp": datetime.now().isoformat(),
        }

        # Cache response
        set_cached_response(cache_key, response, CACHE_TTL_MEDIUM)

        logger.info(f"✅ Template query: {request.persona_id} → {len(top_templates)} templates")

        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Template query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/query/similar-executions")
async def query_similar_executions(
    request: SimilarExecutionsRequest, client: str = Depends(check_rate_limit)
):
    """
    Query similar historical executions

    Returns executions with similar requirements, optionally filtered by persona
    """
    try:
        # Check cache
        cache_key = get_cache_key(
            "similar_executions",
            {
                "requirement": request.requirement,
                "top_k": request.top_k,
                "min_quality": request.min_quality,
                "persona": request.persona_filter,
            },
        )

        cached = get_cached_response(cache_key)
        if cached:
            cached["_cache_hit"] = True
            return JSONResponse(content=cached)

        # Query RAG manager
        rag_manager = get_rag_manager()

        if not rag_manager.enabled:
            return JSONResponse(
                content={
                    "similar_executions_found": 0,
                    "executions": [],
                    "message": "RAG system not available",
                    "cached": False,
                }
            )

        similar_executions = rag_manager.search_similar_executions(
            requirement=request.requirement,
            top_k=request.top_k * 2,  # Get extra for filtering
            min_quality=request.min_quality,
        )

        # Filter by persona if specified
        if request.persona_filter:
            filtered = []
            for execution in similar_executions:
                team_members = execution["metadata"].get("team_members", "")
                if isinstance(team_members, list):
                    team_list = team_members
                else:
                    team_list = team_members.split(",")

                if (
                    request.persona_filter in team_list
                    or f"ai_{request.persona_filter}" in team_list
                ):
                    filtered.append(execution)

            similar_executions = filtered[: request.top_k]

        # Format results
        results = []
        for execution in similar_executions:
            results.append(
                {
                    "requirement": execution["metadata"].get("requirement", "Unknown"),
                    "similarity": execution["similarity"],
                    "team_used": execution["metadata"].get("team_members", []),
                    "files_generated": execution["metadata"].get("total_files", 0),
                    "success": execution["metadata"].get("success", False),
                    "quality_score": execution["metadata"].get("quality_score", 0),
                    "session_id": execution["execution_id"],
                }
            )

        response = {
            "requirement": request.requirement,
            "persona_filter": request.persona_filter,
            "similar_executions_found": len(results),
            "executions": results,
            "cached": False,
            "timestamp": datetime.now().isoformat(),
        }

        # Cache response
        set_cached_response(cache_key, response, CACHE_TTL_SHORT)

        logger.info(f"✅ Similar executions query: {len(results)} found")

        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Similar executions query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/query/team-recommendation")
async def query_team_recommendation(
    request: TeamRecommendationRequest, client: str = Depends(check_rate_limit)
):
    """
    Get recommended team composition based on historical data
    """
    try:
        # Check cache
        cache_key = get_cache_key(
            "team_recommendation",
            {"requirement": request.requirement, "max_team_size": request.max_team_size},
        )

        cached = get_cached_response(cache_key)
        if cached:
            cached["_cache_hit"] = True
            return JSONResponse(content=cached)

        # Get recommendation
        recommender = PatternRecommender()
        recommendation = recommender.recommend_team_composition(
            requirement=request.requirement, max_team_size=request.max_team_size
        )

        response = {**recommendation, "cached": False, "timestamp": datetime.now().isoformat()}

        # Cache response
        set_cached_response(cache_key, response, CACHE_TTL_MEDIUM)

        logger.info(
            f"✅ Team recommendation: {len(recommendation.get('recommended_team', []))} members"
        )

        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Team recommendation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/query/best-practices")
async def query_best_practices(
    request: BestPracticesRequest, client: str = Depends(check_rate_limit)
):
    """
    Get best practices for a persona based on high-quality templates
    """
    try:
        # Check cache
        cache_key = get_cache_key(
            "best_practices",
            {"persona_id": request.persona_id, "task_type": request.task_type or ""},
        )

        cached = get_cached_response(cache_key)
        if cached:
            cached["_cache_hit"] = True
            return JSONResponse(content=cached)

        # Get persona domain
        domain = get_persona_domain(request.persona_id)

        # Load templates
        all_templates = _load_maestro_templates()
        relevant_templates = get_relevant_templates_for_persona(request.persona_id, all_templates)

        # Filter high-quality templates
        high_quality = [t for t in relevant_templates if t.get("quality_score", 0) >= 80]

        # Analyze patterns
        common_frameworks = {}
        common_tags = {}

        for template in high_quality:
            framework = template.get("framework", "")
            if framework:
                common_frameworks[framework] = common_frameworks.get(framework, 0) + 1

            for tag in template.get("tags", []):
                common_tags[tag] = common_tags.get(tag, 0) + 1

        # Sort by frequency
        top_frameworks = sorted(common_frameworks.items(), key=lambda x: x[1], reverse=True)[:5]
        top_tags = sorted(common_tags.items(), key=lambda x: x[1], reverse=True)[:10]

        response = {
            "persona_id": request.persona_id,
            "task_type": request.task_type,
            "domain_expertise": {
                "primary_languages": domain.get("languages", []),
                "primary_frameworks": domain.get("frameworks", []),
                "template_categories": domain.get("template_categories", []),
            },
            "proven_patterns": {
                "most_used_frameworks": [f[0] for f in top_frameworks],
                "framework_usage": dict(top_frameworks),
                "common_tags": [t[0] for t in top_tags],
                "tag_frequency": dict(top_tags),
            },
            "high_quality_templates_available": len(high_quality),
            "best_practices": [
                f"Use {framework} (used in {count} high-quality templates)"
                for framework, count in top_frameworks
            ],
            "git_search_keywords": domain.get("git_search_keywords", []),
            "cached": False,
            "timestamp": datetime.now().isoformat(),
        }

        # Cache response
        set_cached_response(cache_key, response, CACHE_TTL_LONG)

        logger.info(
            f"✅ Best practices query: {request.persona_id} → {len(high_quality)} templates"
        )

        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Best practices query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stats")
async def get_stats(client: str = Depends(check_rate_limit)):
    """Get RAG system statistics"""
    try:
        rag_manager = get_rag_manager()

        if not rag_manager.enabled:
            return JSONResponse(content={"enabled": False, "message": "RAG system not available"})

        stats = rag_manager.get_collection_stats()

        # Add template stats
        all_templates = _load_maestro_templates()

        response = {
            "enabled": True,
            "executions": stats.get("executions", {}),
            "collaterals": stats.get("collaterals", {}),
            "patterns": stats.get("patterns", {}),
            "templates_available": len(all_templates),
            "redis_available": REDIS_AVAILABLE,
            "rate_limit": {
                "requests_per_window": RATE_LIMIT_REQUESTS,
                "window_seconds": RATE_LIMIT_WINDOW,
            },
            "timestamp": datetime.now().isoformat(),
        }

        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Stats query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# Startup / Shutdown
# ==============================================================================


@app.on_event("startup")
async def startup_event():
    """Startup tasks"""
    logger.info("=" * 80)
    logger.info("🚀 MAESTRO RAG Reader Service Starting")
    logger.info("=" * 80)
    logger.info(f"📡 Port: 9801")
    logger.info(f"🔄 Redis: {'✅ Available' if REDIS_AVAILABLE else '❌ Not available'}")
    logger.info(f"⏱️  Rate Limit: {RATE_LIMIT_REQUESTS} req/{RATE_LIMIT_WINDOW}s")
    logger.info(f"📚 Docs: http://0.0.0.0:9801/docs")
    logger.info("=" * 80)


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown tasks"""
    logger.info("👋 MAESTRO RAG Reader Service Shutting Down")


# ==============================================================================
# Main
# ==============================================================================

if __name__ == "__main__":
    uvicorn.run("rag_reader_service:app", host="0.0.0.0", port=9801, reload=True, log_level="info")
