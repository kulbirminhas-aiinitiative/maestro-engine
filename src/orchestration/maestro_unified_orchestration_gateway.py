#!/usr/bin/env python3
"""
MAESTRO Unified Orchestration Gateway
Port: 8004
Workflow coordination, team orchestration, and task distribution
"""

import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MAESTRO Orchestration Gateway",
    description="Workflow coordination, team orchestration, and task distribution",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory workflow storage
workflows: Dict[str, Dict[str, Any]] = {}


# Pydantic models
class WorkflowRequest(BaseModel):
    requirement: str = Field(..., description="User requirement description")
    project_name: Optional[str] = Field(None, description="Project name")
    personas: Optional[List[str]] = Field(
        default_factory=list, description="List of persona IDs to use"
    )


class WorkflowResponse(BaseModel):
    workflow_id: str
    status: str
    requirement: str
    created_at: str
    personas: List[str]


class WorkflowStatus(BaseModel):
    workflow_id: str
    status: str
    progress: float
    current_step: Optional[str]
    results: Optional[Dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    total_workflows: int
    active_workflows: int


# API Endpoints


@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info("=" * 80)
    logger.info("🚀 MAESTRO Orchestration Gateway Starting on port 8004...")
    logger.info("=" * 80)

    # Check for MCP service connection
    mcp_url = os.getenv("MAESTRO_MCP_SERVICE_URL", "http://mcp:9800")
    logger.info(f"🔗 MCP Service URL: {mcp_url}")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "service": "MAESTRO Orchestration Gateway",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "execute": "POST /workflows/execute",
            "status": "GET /workflows/{workflow_id}/status",
            "list": "GET /workflows",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    active_workflows = len([w for w in workflows.values() if w["status"] == "running"])

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0",
        total_workflows=len(workflows),
        active_workflows=active_workflows,
    )


@app.post("/workflows/execute", response_model=WorkflowResponse, tags=["Workflows"])
async def execute_workflow(request: WorkflowRequest, background_tasks: BackgroundTasks):
    """Execute a new workflow"""
    workflow_id = str(uuid.uuid4())

    workflow_data = {
        "workflow_id": workflow_id,
        "status": "queued",
        "requirement": request.requirement,
        "project_name": request.project_name or f"project_{workflow_id[:8]}",
        "personas": request.personas or [],
        "created_at": datetime.now().isoformat(),
        "progress": 0.0,
        "current_step": None,
        "results": None,
    }

    workflows[workflow_id] = workflow_data

    # Schedule workflow execution in background
    background_tasks.add_task(run_workflow, workflow_id)

    logger.info(f"✅ Created workflow: {workflow_id}")

    return WorkflowResponse(
        workflow_id=workflow_id,
        status="queued",
        requirement=request.requirement,
        created_at=workflow_data["created_at"],
        personas=workflow_data["personas"],
    )


@app.get("/workflows/{workflow_id}/status", response_model=WorkflowStatus, tags=["Workflows"])
async def get_workflow_status(workflow_id: str):
    """Get workflow status"""
    if workflow_id not in workflows:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    workflow = workflows[workflow_id]

    return WorkflowStatus(
        workflow_id=workflow_id,
        status=workflow["status"],
        progress=workflow["progress"],
        current_step=workflow["current_step"],
        results=workflow["results"],
    )


@app.get("/workflows", tags=["Workflows"])
async def list_workflows():
    """List all workflows"""
    return {
        "total": len(workflows),
        "workflows": [
            {
                "workflow_id": wf_id,
                "status": wf["status"],
                "requirement": wf["requirement"],
                "created_at": wf["created_at"],
            }
            for wf_id, wf in workflows.items()
        ],
    }


@app.delete("/workflows/{workflow_id}", tags=["Workflows"])
async def delete_workflow(workflow_id: str):
    """Delete a workflow"""
    if workflow_id not in workflows:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    del workflows[workflow_id]
    logger.info(f"🗑️  Deleted workflow: {workflow_id}")

    return {"message": f"Workflow {workflow_id} deleted successfully"}


# Background workflow execution
async def run_workflow(workflow_id: str):
    """Execute workflow in background"""
    try:
        workflow = workflows[workflow_id]
        workflow["status"] = "running"
        workflow["progress"] = 0.1
        workflow["current_step"] = "Initializing"

        logger.info(f"🚀 Starting workflow: {workflow_id}")

        # Simulate workflow execution
        # In production, this would call the actual orchestration logic
        import time

        time.sleep(2)

        workflow["progress"] = 0.5
        workflow["current_step"] = "Executing personas"

        time.sleep(2)

        workflow["progress"] = 1.0
        workflow["current_step"] = "Completed"
        workflow["status"] = "completed"
        workflow["results"] = {"message": "Workflow executed successfully", "files_generated": []}

        logger.info(f"✅ Completed workflow: {workflow_id}")

    except Exception as e:
        logger.error(f"❌ Workflow {workflow_id} failed: {e}")
        workflow["status"] = "failed"
        workflow["results"] = {"error": str(e)}


if __name__ == "__main__":
    uvicorn.run(
        "maestro_unified_orchestration_gateway:app",
        host="0.0.0.0",
        port=8004,
        reload=False,
        log_level="info",
    )
