#!/usr/bin/env python3
"""
Deployment Management API Routes
Epic: MD-1790 [Platform] Unified Deployment Management GUI

REST API endpoints for deployment management:
- GET /api/v1/deployments/environments - List all environments
- GET /api/v1/deployments/environments/{id} - Get environment details
- GET /api/v1/deployments/environments/{id}/health - Get health status
- POST /api/v1/deployments/environments/{id}/deploy - Trigger deployment
- GET /api/v1/deployments/history - Get deployment history
- GET /api/v1/deployments/{id} - Get deployment details
- GET /api/v1/deployments/{id}/logs - Get deployment logs
- POST /api/v1/deployments/{id}/rollback - Rollback deployment
- POST /api/v1/deployments/{id}/cancel - Cancel deployment
- GET /api/v1/deployments/versions - Get available versions

Acceptance Criteria:
- AC-1: Single dashboard for all environments
- AC-2: Current version per environment
- AC-3: Health status per environment
- AC-4: One-click deploy from versions
- AC-5: Deployment history with status
- AC-6: Basic rollback capability
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# Import deployment services
try:
    from services.deployment_service import (
        get_deployment_service,
        initialize_deployment_service,
        DeploymentService,
        DeploymentStatus,
    )
    from services.deployment_health_monitor import (
        get_deployment_health_monitor,
        DeploymentHealthMonitor,
    )
    HAS_DEPLOYMENT_SERVICE = True
except ImportError:
    HAS_DEPLOYMENT_SERVICE = False

logger = logging.getLogger("deployment_routes")

# Create router
router = APIRouter(prefix="/api/v1/deployments", tags=["deployments"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class TriggerDeploymentRequest(BaseModel):
    """Request to trigger a deployment."""
    version: str = Field(..., description="Version to deploy")
    triggered_by: str = Field(..., description="Username triggering deployment")
    notes: Optional[str] = Field(None, description="Deployment notes")
    git_sha: Optional[str] = Field(None, description="Git commit SHA")
    git_branch: Optional[str] = Field(None, description="Git branch")


class RollbackRequest(BaseModel):
    """Request to rollback a deployment."""
    triggered_by: str = Field(..., description="Username triggering rollback")


class CancelDeploymentRequest(BaseModel):
    """Request to cancel a deployment."""
    cancelled_by: str = Field(..., description="Username cancelling deployment")


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def deployment_api_health():
    """Health check for deployment API."""
    return {
        "status": "healthy" if HAS_DEPLOYMENT_SERVICE else "unavailable",
        "service": "deployment-management",
    }


# ============================================================================
# ENVIRONMENT ENDPOINTS
# ============================================================================

@router.get("/environments")
async def list_environments():
    """
    List all deployment environments.

    AC-1: Single dashboard for all environments
    """
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    service = get_deployment_service()
    await service.initialize()

    environments = await service.get_environments()
    statuses = await service.get_all_environment_statuses()

    return {
        "environments": [s.to_dict() for s in statuses],
        "total": len(environments),
    }


@router.get("/environments/{env_id}")
async def get_environment(env_id: str):
    """
    Get environment details with current deployment status.

    AC-2: Current version per environment
    """
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    service = get_deployment_service()
    await service.initialize()

    status = await service.get_environment_status(env_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Environment not found: {env_id}")

    return status.to_dict()


@router.get("/environments/{env_id}/health")
async def get_environment_health(env_id: str):
    """
    Get current health status for an environment.

    AC-3: Health status per environment
    """
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    monitor = get_deployment_health_monitor()
    result = monitor.get_current_status(env_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"No health data for environment: {env_id}")

    return result.to_dict()


@router.get("/environments/{env_id}/health/history")
async def get_environment_health_history(
    env_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum snapshots"),
):
    """
    Get health history for an environment.

    Returns historical health snapshots for trending visualization.
    """
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    monitor = get_deployment_health_monitor()
    snapshots = await monitor.get_health_history(env_id, hours, limit)

    return {
        "environment_id": env_id,
        "hours": hours,
        "snapshots": [s.to_dict() for s in snapshots],
        "total": len(snapshots),
    }


@router.get("/environments/{env_id}/history")
async def get_environment_deployment_history(
    env_id: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum deployments"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """
    Get deployment history for a specific environment.

    AC-5: Deployment history with status
    """
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    service = get_deployment_service()
    await service.initialize()

    status_filter = None
    if status:
        try:
            status_filter = DeploymentStatus(status)
        except ValueError:
            valid = [s.value for s in DeploymentStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Valid values: {valid}"
            )

    deployments = await service.get_deployment_history(env_id, limit, status_filter)

    return {
        "environment_id": env_id,
        "deployments": [d.to_dict() for d in deployments],
        "total": len(deployments),
    }


@router.post("/environments/{env_id}/deploy")
async def trigger_deployment(env_id: str, request: TriggerDeploymentRequest):
    """
    Trigger a deployment to an environment.

    AC-4: One-click deploy from versions
    """
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    service = get_deployment_service()
    await service.initialize()

    try:
        deployment = await service.trigger_deployment(
            env_id=env_id,
            version=request.version,
            triggered_by=request.triggered_by,
            notes=request.notes,
            git_sha=request.git_sha,
            git_branch=request.git_branch,
        )
        return {
            "status": "triggered",
            "deployment": deployment.to_dict(),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# DEPLOYMENT ENDPOINTS
# ============================================================================

@router.get("/history")
async def get_all_deployment_history(
    limit: int = Query(50, ge=1, le=200, description="Maximum deployments"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """
    Get deployment history across all environments.

    AC-5: Deployment history with status
    """
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    service = get_deployment_service()
    await service.initialize()

    status_filter = None
    if status:
        try:
            status_filter = DeploymentStatus(status)
        except ValueError:
            valid = [s.value for s in DeploymentStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Valid values: {valid}"
            )

    deployments = await service.get_deployment_history(None, limit, status_filter)

    return {
        "deployments": [d.to_dict() for d in deployments],
        "total": len(deployments),
    }


@router.get("/{deployment_id}")
async def get_deployment(deployment_id: str):
    """Get deployment details."""
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    service = get_deployment_service()
    await service.initialize()

    deployment = await service.get_deployment(deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail=f"Deployment not found: {deployment_id}")

    return deployment.to_dict()


@router.get("/{deployment_id}/logs")
async def get_deployment_logs(
    deployment_id: str,
    level: Optional[str] = Query(None, description="Filter by log level"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum log entries"),
):
    """Get logs for a deployment."""
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    service = get_deployment_service()
    await service.initialize()

    logs = await service.get_deployment_logs(deployment_id, level, limit)

    return {
        "deployment_id": deployment_id,
        "logs": [l.to_dict() for l in logs],
        "total": len(logs),
    }


@router.post("/{deployment_id}/rollback")
async def rollback_deployment(deployment_id: str, request: RollbackRequest):
    """
    Rollback to a previous deployment.

    AC-6: Basic rollback capability
    """
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    service = get_deployment_service()
    await service.initialize()

    try:
        rollback = await service.rollback_deployment(
            deployment_id=deployment_id,
            triggered_by=request.triggered_by,
        )
        return {
            "status": "rollback_triggered",
            "deployment": rollback.to_dict(),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{deployment_id}/cancel")
async def cancel_deployment(deployment_id: str, request: CancelDeploymentRequest):
    """Cancel an active deployment."""
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    service = get_deployment_service()
    await service.initialize()

    success = await service.cancel_deployment(
        deployment_id=deployment_id,
        cancelled_by=request.cancelled_by,
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel deployment. It may not exist or is already complete."
        )

    return {"status": "cancelled", "deployment_id": deployment_id}


# ============================================================================
# VERSION ENDPOINTS
# ============================================================================

@router.get("/versions")
async def get_available_versions(
    include_prereleases: bool = Query(False, description="Include pre-release versions"),
    limit: int = Query(20, ge=1, le=50, description="Maximum versions"),
):
    """Get available versions for deployment."""
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    service = get_deployment_service()
    await service.initialize()

    versions = await service.get_available_versions(include_prereleases, limit)

    return {
        "versions": [v.to_dict() for v in versions],
        "total": len(versions),
    }


@router.get("/versions/{version}/environments")
async def get_version_deployments(version: str):
    """Get environments where a specific version is deployed."""
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    service = get_deployment_service()
    await service.initialize()

    statuses = await service.get_all_environment_statuses()

    deployed_envs = [
        {
            "environment_id": s.environment.id,
            "environment_name": s.environment.name,
            "display_name": s.environment.display_name,
            "deployed_at": s.deployed_at.isoformat() if s.deployed_at else None,
        }
        for s in statuses
        if s.current_version == version
    ]

    return {
        "version": version,
        "environments": deployed_envs,
        "total": len(deployed_envs),
    }


# ============================================================================
# HEALTH SUMMARY ENDPOINT
# ============================================================================

@router.get("/health/summary")
async def get_health_summary():
    """Get a summary of all environment health status."""
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    monitor = get_deployment_health_monitor()
    return monitor.get_health_summary()


# ============================================================================
# MD-1861: HEALTH RETRY CONFIGURATION & STATS ENDPOINTS
# ============================================================================

@router.get("/health/retry-config")
async def get_health_retry_config():
    """
    Get current health check retry configuration.

    MD-1861: Returns the retry settings used for health endpoint verification.
    """
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    monitor = get_deployment_health_monitor()
    return {
        "status": "ok",
        "config": monitor.get_retry_config(),
    }


@router.get("/health/retry-stats")
async def get_health_retry_stats(
    env_id: Optional[str] = Query(None, description="Filter by environment ID"),
):
    """
    Get retry statistics for health checks.

    MD-1861: Returns retry counts and statistics for observability.
    Useful for diagnosing flaky endpoints or network issues.
    """
    if not HAS_DEPLOYMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Deployment service not available")

    monitor = get_deployment_health_monitor()
    return {
        "status": "ok",
        "stats": monitor.get_retry_stats(env_id),
    }


# ============================================================================
# HELPER FUNCTION TO REGISTER ROUTER
# ============================================================================

def register_deployment_routes(app):
    """Register deployment routes with a FastAPI app."""
    app.include_router(router)
    logger.info("Deployment routes registered at /api/v1/deployments")
