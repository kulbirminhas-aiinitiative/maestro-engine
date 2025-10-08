#!/usr/bin/env python3
"""
Persona Workflow API for MAESTRO Engine

FastAPI routes for executing workflows with the new Schema v3.0 persona system.
Called by the unified BFF for Guardian workflow execution.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from celery.result import AsyncResult

from celery_config import celery_app, get_redis_client

# Import Celery tasks
from celery_tasks import execute_workflow_task, get_job_status

# Import maestro-engine configuration
from config import get_settings, get_workflow_config

# Get configuration
settings = get_settings()
workflow_config = get_workflow_config()

# Create router
router = APIRouter(prefix="/api/workflow", tags=["persona-workflow"])


# Request/Response models
class PersonaWorkflowRequest(BaseModel):
    """Request to execute a persona workflow"""

    requirement: str = Field(..., description="User requirement")
    session_id: str = Field(..., description="Session ID")
    persona_ids: Optional[List[str]] = Field(
        None, description="Personas to execute (None = default SDLC workflow)"
    )
    enable_mcp: bool = Field(default=True, description="Enable MCP event emission")
    enable_rag: bool = Field(default=True, description="Enable RAG context")
    mcp_context: Optional[Dict[str, Any]] = Field(
        None, description="MCP context from previous session"
    )


class PersonaWorkflowResponse(BaseModel):
    """Response from persona workflow execution"""

    session_id: str
    success: bool
    message: str
    total_personas: int
    successful: int
    failed: int
    total_time: float
    total_files: int
    work_dir: str
    team_members: List[str]
    results: List[Dict[str, Any]]


@router.post("/execute")
async def execute_persona_workflow(request: PersonaWorkflowRequest):
    """
    Execute a complete SDLC workflow using Schema v3.0 personas via Celery Queue

    This endpoint queues the workflow in RabbitMQ and returns immediately.
    Use GET /status/{job_id} to check progress and results.

    Features:
    - Non-blocking: Returns immediately with job ID
    - Scalable: Multiple workers can process jobs in parallel
    - Fault-tolerant: Job survives worker crashes
    - Real-time tracking: Progress updates via Redis

    Args:
        request: Workflow execution request

    Returns:
        Job information with tracking ID
    """
    # Determine personas to execute
    personas = request.persona_ids or workflow_config.GUARDIAN_WORKFLOW.personas

    # Prepare task data
    task_data = {
        "requirement": request.requirement,
        "session_id": request.session_id,
        "persona_ids": personas,
        "enable_rag": request.enable_rag,
        "enable_mcp": request.enable_mcp,
    }

    # Queue the workflow execution task in Celery
    task = execute_workflow_task.delay(task_data)

    # Get work directory for reference
    work_dir = settings.get_project_dir(request.session_id)

    # Return immediately with job ID
    return {
        "job_id": task.id,
        "session_id": request.session_id,
        "status": "QUEUED",
        "message": "Workflow queued successfully. Use job_id to track progress.",
        "total_personas": len(personas),
        "team_members": personas,
        "work_dir": str(work_dir),
        "status_endpoint": f"/api/workflow/status/{task.id}",
        "queue": "maestro_long_running",
    }


@router.get("/status/{job_id}")
async def get_workflow_status(job_id: str):
    """
    Get workflow execution status and progress

    Args:
        job_id: Celery task ID from /execute response

    Returns:
        Job status with progress information
    """
    # Get Celery task result
    task_result = AsyncResult(job_id, app=celery_app)

    # Get detailed status from Redis
    redis_client = get_redis_client()
    redis_status = redis_client.hgetall(f"job:{job_id}")

    # Build response
    response = {
        "job_id": job_id,
        "celery_state": task_result.state,  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
        "ready": task_result.ready(),
        "successful": task_result.successful() if task_result.ready() else None,
    }

    # Add Redis tracking data if available
    if redis_status:
        response.update(
            {
                "status": redis_status.get("status", task_result.state),
                "session_id": redis_status.get("session_id"),
                "current_persona": redis_status.get("current_persona"),
                "progress_percent": (
                    float(redis_status.get("progress_percent", 0))
                    if redis_status.get("progress_percent")
                    else 0
                ),
                "personas_completed": (
                    int(redis_status.get("personas_completed", 0))
                    if redis_status.get("personas_completed")
                    else 0
                ),
                "personas_total": (
                    int(redis_status.get("personas_total", 0))
                    if redis_status.get("personas_total")
                    else 0
                ),
                "started_at": redis_status.get("started_at"),
                "updated_at": redis_status.get("updated_at"),
            }
        )

        # Add completion info if finished
        if redis_status.get("status") == "SUCCESS":
            response.update(
                {
                    "completed_at": redis_status.get("completed_at"),
                    "total_files": (
                        int(redis_status.get("total_files", 0))
                        if redis_status.get("total_files")
                        else 0
                    ),
                    "total_time": (
                        float(redis_status.get("total_time", 0))
                        if redis_status.get("total_time")
                        else 0
                    ),
                    "work_dir": redis_status.get("work_dir"),
                }
            )

        # Add error info if failed
        if redis_status.get("status") == "FAILURE":
            response.update(
                {
                    "failed_at": redis_status.get("failed_at"),
                    "error": redis_status.get("error"),
                }
            )

    # Get result if task is complete
    if task_result.ready() and task_result.successful():
        try:
            response["result"] = task_result.result
        except Exception as e:
            response["result_error"] = str(e)

    return response


@router.get("/jobs")
async def list_active_jobs():
    """
    List all active workflow jobs

    Returns:
        List of active jobs with their statuses
    """
    redis_client = get_redis_client()

    # Get all job keys from Redis
    job_keys = redis_client.keys("job:*")

    jobs = []
    for key in job_keys:
        job_id = key.split(":", 1)[1]
        status_data = redis_client.hgetall(key)

        if status_data:
            jobs.append(
                {
                    "job_id": job_id,
                    "session_id": status_data.get("session_id"),
                    "status": status_data.get("status"),
                    "progress_percent": (
                        float(status_data.get("progress_percent", 0))
                        if status_data.get("progress_percent")
                        else 0
                    ),
                    "started_at": status_data.get("started_at"),
                    "updated_at": status_data.get("updated_at"),
                }
            )

    # Sort by started_at desc
    jobs.sort(key=lambda x: x.get("started_at", ""), reverse=True)

    return {"total_jobs": len(jobs), "jobs": jobs}


@router.get("/personas")
async def list_available_personas():
    """
    List all available personas

    Returns:
        Dictionary of available personas with metadata
    """
    from personas import get_adapter

    adapter = get_adapter()
    personas = adapter.get_all_personas()

    return {
        "total": len(personas),
        "personas": {
            persona_id: {
                "name": persona["name"],
                "phase": persona["phase"],
                "role_id": persona["role_id"],
                "collaboration_style": persona["collaboration_style"],
            }
            for persona_id, persona in personas.items()
        },
    }


@router.get("/personas/{persona_id}")
async def get_persona_details(persona_id: str):
    """
    Get detailed information about a specific persona

    Args:
        persona_id: Persona identifier

    Returns:
        Detailed persona information
    """
    from personas import get_adapter

    adapter = get_adapter()
    persona = adapter.get_persona(persona_id)

    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona not found: {persona_id}")

    return {
        "persona_id": persona_id,
        "name": persona["name"],
        "phase": persona["phase"],
        "role_id": persona["role_id"],
        "expertise": persona["expertise"],
        "responsibilities": persona["responsibilities"],
        "collaboration_style": persona["collaboration_style"],
        "system_prompt_length": len(persona["system_prompt"]),
    }


@router.post("/execution-order")
async def get_execution_order(persona_ids: List[str]):
    """
    Get optimal execution order for given personas

    Args:
        persona_ids: List of persona IDs

    Returns:
        Ordered list of persona IDs based on dependencies
    """
    from personas import get_adapter

    adapter = get_adapter()

    try:
        ordered = adapter.get_execution_order(persona_ids)
        return {"requested": persona_ids, "ordered": ordered, "total": len(ordered)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check for persona workflow API"""
    from personas import get_adapter

    adapter = get_adapter()

    try:
        personas = adapter.get_all_personas()
        persona_count = len(personas)
        is_healthy = persona_count > 0
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()}

    return {
        "status": "healthy" if is_healthy else "degraded",
        "persona_system": {"total_personas": persona_count, "schema_version": "3.0"},
        "timestamp": datetime.now().isoformat(),
    }
