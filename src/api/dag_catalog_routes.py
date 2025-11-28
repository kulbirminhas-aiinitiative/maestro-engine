#!/usr/bin/env python3
"""
DAG Catalog Routes for MAESTRO Backend API
Manages DAG definitions, templates, and frontend DAG submissions
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.models import (
    DAGCategoriesResponse,
    DAGListResponse,
    DAGMetadataResponse,
    DAGNodeResponse,
    DAGResponse,
    DAGSearchRequest,
    DAGSubmitRequest,
    DAGSubmitResponse,
)
from services.dag_catalog import DAGCatalogService
from utils.redis_manager import RedisManager
from workflow.dag import DAG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dag-catalog", tags=["DAG Catalog"])

# Initialize service
redis_mgr = RedisManager()
catalog_service = DAGCatalogService(redis_manager=redis_mgr)


@router.on_event("startup")
async def startup_event():
    """Initialize DAG templates on startup"""
    try:
        logger.info("🔧 Initializing DAG catalog templates...")
        await catalog_service.initialize_templates()
        logger.info("✅ DAG catalog templates initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize DAG templates: {e}")


@router.post("/submit", response_model=DAGSubmitResponse)
async def submit_dag(request: DAGSubmitRequest):
    """
    Submit/store a DAG definition from frontend

    This endpoint receives DAG JSON from the frontend DAG designer,
    validates it, and stores it in the catalog for future execution.

    Args:
        request: DAG submission request with dag_json and metadata

    Returns:
        DAGSubmitResponse with success status and assigned dag_id
    """
    try:
        logger.info(f"📥 Receiving DAG submission from user: {request.user_id or 'anonymous'}")

        # Validate DAG structure
        if not request.dag_json:
            raise HTTPException(status_code=400, detail="dag_json is required")

        # Convert dict to DAG object
        try:
            dag = DAG.from_dict(request.dag_json)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid DAG structure: {str(e)}"
            )

        # Store DAG in catalog
        dag_id = await catalog_service.store_dag(
            dag=dag,
            metadata=request.metadata,
            user_id=request.user_id,
        )

        logger.info(f"✅ DAG stored successfully with ID: {dag_id}")

        return DAGSubmitResponse(
            success=True,
            dag_id=dag_id,
            message="DAG stored successfully in catalog",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ DAG submission failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": "DAG submission failed", "message": str(e)},
        )


@router.get("/templates", response_model=DAGListResponse)
async def list_templates(category: Optional[str] = None, limit: int = 100):
    """
    List all available DAG templates

    Templates are pre-built DAG workflows that match the frontend
    workflow templates (SaaS, Microservice, Mobile, Enterprise).

    Args:
        category: Optional category filter (saas, microservice, mobile, enterprise)
        limit: Maximum number of results (default: 100)

    Returns:
        DAGListResponse with list of template metadata
    """
    try:
        logger.info(f"📋 Listing DAG templates (category={category}, limit={limit})")

        # Get DAGs from catalog
        dags = await catalog_service.list_dags(category=category, limit=limit)

        # Filter to only templates
        templates = [d for d in dags if d.get("is_template", False)]

        # Convert to response format
        metadata_list = [
            DAGMetadataResponse(
                dag_id=dag.get("dag_id", ""),
                name=dag.get("name", "Unknown"),
                description=dag.get("description"),
                category=dag.get("category"),
                complexity=dag.get("complexity"),
                node_count=dag.get("node_count"),
                created_at=dag.get("created_at"),
                is_template=True,
            )
            for dag in templates
        ]

        return DAGListResponse(
            dags=metadata_list,
            total=len(metadata_list),
            category=category,
        )

    except Exception as e:
        logger.error(f"❌ Failed to list templates: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to list templates", "message": str(e)},
        )


@router.get("/dags", response_model=DAGListResponse)
async def list_dags(
    category: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 100,
):
    """
    List all DAGs (templates + user-created)

    Args:
        category: Optional category filter
        user_id: Optional filter by user who created the DAG
        limit: Maximum number of results (default: 100)

    Returns:
        DAGListResponse with list of DAG metadata
    """
    try:
        logger.info(
            f"📋 Listing DAGs (category={category}, user={user_id}, limit={limit})"
        )

        # Get DAGs from catalog
        dags = await catalog_service.list_dags(
            category=category, user_id=user_id, limit=limit
        )

        # Convert to response format
        metadata_list = [
            DAGMetadataResponse(
                dag_id=dag.get("dag_id", ""),
                name=dag.get("name", "Unknown"),
                description=dag.get("description"),
                category=dag.get("category"),
                complexity=dag.get("complexity"),
                node_count=dag.get("node_count"),
                created_at=dag.get("created_at"),
                is_template=dag.get("is_template", False),
            )
            for dag in dags
        ]

        return DAGListResponse(
            dags=metadata_list,
            total=len(metadata_list),
            category=category,
        )

    except Exception as e:
        logger.error(f"❌ Failed to list DAGs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to list DAGs", "message": str(e)},
        )


@router.get("/{dag_id}", response_model=DAGResponse)
async def get_dag(dag_id: str):
    """
    Get a specific DAG by ID

    Returns the complete DAG definition including all nodes and metadata.
    This is used by the frontend to load a DAG for visualization or execution.

    Args:
        dag_id: DAG identifier

    Returns:
        DAGResponse with complete DAG data
    """
    try:
        logger.info(f"🔍 Fetching DAG: {dag_id}")

        # Get DAG from catalog
        dag = await catalog_service.get_dag(dag_id)

        if not dag:
            raise HTTPException(status_code=404, detail=f"DAG not found: {dag_id}")

        # Get metadata
        metadata = await catalog_service.get_dag_metadata(dag_id)

        # Convert nodes to response format
        nodes = [
            DAGNodeResponse(
                id=node.id,
                name=node.name,
                task_type=node.task_type.value if hasattr(node.task_type, "value") else str(node.task_type),
                description=node.description,
                depends_on=node.depends_on,
                priority=node.priority,
                metadata=node.metadata,
            )
            for node in dag.nodes.values()
        ]

        return DAGResponse(
            dag_id=dag_id,
            name=dag.name,
            description=dag.description,
            nodes=nodes,
            metadata=metadata,
            created_at=metadata.get("created_at") if metadata else None,
            is_template=metadata.get("is_template", False) if metadata else False,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get DAG: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to retrieve DAG", "message": str(e)},
        )


@router.post("/search", response_model=DAGListResponse)
async def search_dags(request: DAGSearchRequest):
    """
    Search DAGs by name or description

    Uses fuzzy matching to find DAGs that match the search query.
    Useful for @workflow suggestions in collaboration chat.

    Args:
        request: Search request with query string and limit

    Returns:
        DAGListResponse with matching DAGs
    """
    try:
        logger.info(f"🔎 Searching DAGs: query='{request.query}', limit={request.limit}")

        # Search in catalog
        results = await catalog_service.search_dags(
            query=request.query, limit=request.limit
        )

        # Convert to response format
        metadata_list = [
            DAGMetadataResponse(
                dag_id=dag.get("dag_id", ""),
                name=dag.get("name", "Unknown"),
                description=dag.get("description"),
                category=dag.get("category"),
                complexity=dag.get("complexity"),
                node_count=dag.get("node_count"),
                created_at=dag.get("created_at"),
                is_template=dag.get("is_template", False),
            )
            for dag in results
        ]

        return DAGListResponse(
            dags=metadata_list,
            total=len(metadata_list),
            category=None,
        )

    except Exception as e:
        logger.error(f"❌ Search failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Search failed", "message": str(e)},
        )


@router.get("/categories/list", response_model=DAGCategoriesResponse)
async def list_categories():
    """
    List all available DAG categories

    Returns:
        DAGCategoriesResponse with list of categories
    """
    try:
        # Hardcoded categories matching the 4 frontend templates
        categories = ["saas", "microservice", "mobile", "enterprise"]

        return DAGCategoriesResponse(
            categories=categories,
            total=len(categories),
        )

    except Exception as e:
        logger.error(f"❌ Failed to list categories: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to list categories", "message": str(e)},
        )


@router.delete("/{dag_id}")
async def delete_dag(dag_id: str):
    """
    Delete a DAG from the catalog

    Only allows deleting custom user DAGs, not templates.

    Args:
        dag_id: DAG identifier to delete

    Returns:
        Success message
    """
    try:
        logger.info(f"🗑️  Deleting DAG: {dag_id}")

        # Check if it's a template
        metadata = await catalog_service.get_dag_metadata(dag_id)
        if metadata and metadata.get("is_template", False):
            raise HTTPException(
                status_code=403, detail="Cannot delete template DAGs"
            )

        # Delete DAG
        deleted = await catalog_service.delete_dag(dag_id)

        if not deleted:
            raise HTTPException(status_code=404, detail=f"DAG not found: {dag_id}")

        logger.info(f"✅ DAG deleted successfully: {dag_id}")

        return {"success": True, "message": f"DAG {dag_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete DAG: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to delete DAG", "message": str(e)},
        )


@router.get("/health/check")
async def health_check():
    """
    Health check for DAG catalog service

    Returns:
        Health status
    """
    try:
        # Try to get templates count
        templates = await catalog_service.list_dags(limit=1)

        return {
            "status": "healthy",
            "service": "dag-catalog",
            "templates_initialized": len(templates) > 0,
        }

    except Exception as e:
        logger.error(f"❌ Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "service": "dag-catalog",
            "error": str(e),
        }
