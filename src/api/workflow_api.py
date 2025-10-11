#!/usr/bin/env python3
"""
MAESTRO Engine - Workflow API
FastAPI routes for Guardian workflow execution from maestro-frontend

Supports both:
- Legacy synchronous execution (/ai/chat)
- New async workflow execution (/api/workflow/execute)
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

# Import Claude Agent SDK (v3.0 - Security Update)
from claude_agent_sdk import ClaudeAgentOptions, query
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

# Import workflow execution infrastructure
try:
    from utils.redis_manager import WorkflowStateManager
    from utils.websocket_manager import WebSocketConnectionManager
    from api.workflow_executor import MaestroWorkflowExecutor, WorkflowExecutionRequest
    ASYNC_WORKFLOW_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Async workflow infrastructure not available: {e}")
    ASYNC_WORKFLOW_AVAILABLE = False
    WorkflowStateManager = None
    WebSocketConnectionManager = None
    MaestroWorkflowExecutor = None
    WorkflowExecutionRequest = None

# Create router
router = APIRouter(prefix="", tags=["workflow"])

# Initialize workflow infrastructure (if available)
redis_manager = None
ws_manager = None
workflow_executor = None

if ASYNC_WORKFLOW_AVAILABLE:
    try:
        redis_manager = WorkflowStateManager(redis_url="redis://localhost:6380", db=0)
        ws_manager = WebSocketConnectionManager(redis_manager=redis_manager)
        workflow_executor = MaestroWorkflowExecutor(
            redis_manager=redis_manager,
            ws_manager=ws_manager
        )
        logging.info("✅ Async workflow infrastructure initialized")
    except Exception as e:
        logging.error(f"Failed to initialize async workflow infrastructure: {e}")
        ASYNC_WORKFLOW_AVAILABLE = False


# Request/Response models
class WorkflowRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="Session ID")
    prompt: str = Field(..., description="User requirement/prompt")
    project_name: Optional[str] = Field(None, description="Project name for deployment folder")
    phase: Optional[str] = Field("requirements", description="Current SDLC phase")


class WorkflowResponse(BaseModel):
    response: str
    session_id: str
    timestamp: str
    workflow_state: str
    has_preview: bool = False


class SessionState(BaseModel):
    session_id: str
    messages: List[Dict[str, str]]
    workflow_state: str
    files: List[Dict[str, Any]]
    created_at: str
    updated_at: str


# In-memory session storage (replace with Redis in production)
sessions: Dict[str, Dict[str, Any]] = {}
ws_connections: Dict[str, WebSocket] = {}


@router.post("/ai/chat", response_model=WorkflowResponse)
async def ai_chat(request: WorkflowRequest):
    """Execute Guardian workflow"""
    session_id = request.session_id or f"session_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    project_name = request.project_name or f"project_{session_id}"
    phase = request.phase or "requirements"

    # Create or get session
    if session_id not in sessions:
        sessions[session_id] = {
            "session_id": session_id,
            "project_name": project_name,
            "messages": [],
            "workflow_state": "idle",
            "files": [],
            "current_phase": phase,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
    else:
        # Update phase if provided
        sessions[session_id]["current_phase"] = phase

    # Add user message
    sessions[session_id]["messages"].append(
        {"role": "user", "content": request.prompt, "timestamp": datetime.now().isoformat()}
    )

    # Update workflow state
    sessions[session_id]["workflow_state"] = "generating"
    sessions[session_id]["updated_at"] = datetime.now().isoformat()

    # Send WebSocket update if connected
    if session_id in ws_connections:
        try:
            await ws_connections[session_id].send_json(
                {
                    "type": "workflow_state",
                    "state": "generating",
                    "message": "Starting workflow execution...",
                    "phase": phase,
                }
            )
        except:
            pass

    # Execute workflow
    result = await execute_generation(session_id, request.prompt, project_name, phase)

    # Add assistant message
    sessions[session_id]["messages"].append(
        {
            "role": "assistant",
            "content": result["ai_response"],
            "timestamp": datetime.now().isoformat(),
        }
    )

    # Update workflow state
    sessions[session_id]["workflow_state"] = "complete" if result["success"] else "error"
    sessions[session_id]["updated_at"] = datetime.now().isoformat()

    # Send WebSocket update if connected
    if session_id in ws_connections:
        try:
            await ws_connections[session_id].send_json(
                {
                    "type": "workflow_state",
                    "state": sessions[session_id]["workflow_state"],
                    "message": result["ai_response"],
                }
            )
        except:
            pass

    return WorkflowResponse(
        response=result["ai_response"],
        session_id=session_id,
        timestamp=datetime.now().isoformat(),
        workflow_state=sessions[session_id]["workflow_state"],
        has_preview=result.get("html_content") is not None,
    )


async def execute_generation(session_id: str, requirement: str, project_name: str, phase: str = "requirements") -> Dict[str, Any]:
    """Execute code generation using Claude Code SDK"""
    # Use deployment folder with phase organization
    deployment_base = Path.home() / "projects" / "deployment"
    deployment_dir = deployment_base / project_name / phase
    deployment_dir.mkdir(parents=True, exist_ok=True)

    # Still use /tmp for working directory during execution
    work_dir = Path(f"/tmp/maestro_projects/accelerator_{session_id}")
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Configure Claude Agent SDK options (v3.0)
        options = ClaudeAgentOptions(
            cwd=str(work_dir),
            permission_mode="bypassPermissions",
            system_prompt=f"""You are an expert software developer creating production-ready applications.

CRITICAL INSTRUCTIONS:
1. Use the Write tool to create actual files - do NOT just describe code!
2. Your current working directory is: {work_dir}
3. Create complete, working applications with all necessary files
4. Include proper error handling, comments, and documentation
5. This is for the {phase} phase of the SDLC workflow

When users describe what they want to build:
1. Analyze the requirement thoroughly
2. Create a complete file structure
3. Use Write tool for each file with proper paths (e.g., './index.html', './src/app.js')
4. Include inline CSS and JavaScript where appropriate
5. Ensure the application is ready to run

Requirement: {requirement}

Create a complete, production-ready implementation for the {phase} phase.
""",
            continue_conversation=False,
            allowed_tools=["read", "write", "bash", "glob", "grep"],
        )

        # Execute with Claude Code SDK
        response_parts = []
        async for message in query(prompt=requirement, options=options):
            if hasattr(message, "text") and message.text:
                response_parts.append(message.text)

                # Send WebSocket progress update
                if session_id in ws_connections:
                    try:
                        await ws_connections[session_id].send_json(
                            {
                                "type": "progress",
                                "message": (
                                    message.text[:100] + "..."
                                    if len(message.text) > 100
                                    else message.text
                                ),
                            }
                        )
                    except:
                        pass

        full_response = "\n".join(response_parts)

        # Find created files and copy to deployment folder
        created_files = []
        import shutil

        for file_path in work_dir.rglob("*"):
            if file_path.is_file():
                rel_path = str(file_path.relative_to(work_dir))
                file_size = file_path.stat().st_size

                # Read file content
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except:
                    content = "[Binary file]"

                # Copy file to deployment folder (preserving structure)
                deployment_file_path = deployment_dir / rel_path
                deployment_file_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, deployment_file_path)

                file_info = {
                    "path": rel_path,
                    "full_path": str(file_path),
                    "deployment_path": str(deployment_file_path),
                    "project_name": project_name,
                    "phase": phase,
                    "size": file_size,
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                }

                created_files.append(file_info)

                # Store in session
                sessions[session_id]["files"].append(file_info)

                # Send WebSocket file update with phase and deployment info
                if session_id in ws_connections:
                    try:
                        await ws_connections[session_id].send_json({
                            "type": "file_created",
                            "file_path": rel_path,
                            "deployment_path": str(deployment_file_path),
                            "phase": phase,
                            "project_name": project_name
                        })
                    except:
                        pass

        # Check for HTML content
        html_content = None
        index_html = work_dir / "index.html"
        if index_html.exists():
            with open(index_html, "r") as f:
                html_content = f.read()

        return {
            "success": True,
            "ai_response": (
                full_response[:500] + "..." if len(full_response) > 500 else full_response
            ),
            "files_created": created_files,
            "html_content": html_content,
        }

    except Exception as e:
        return {
            "success": False,
            "ai_response": f"Error: {str(e)}",
            "files_created": [],
            "html_content": None,
        }


@router.get("/api/session/{session_id}/state")
async def get_session_state(session_id: str):
    """Get session state"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return sessions[session_id]


@router.get("/api/session/{session_id}/files")
async def get_session_files(session_id: str):
    """Get generated files for session"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return sessions[session_id].get("files", [])


@router.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    ws_connections[session_id] = websocket

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        if session_id in ws_connections:
            del ws_connections[session_id]


@router.websocket("/ws/workflow/{session_id}")
async def websocket_workflow(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for workflow updates"""
    await websocket.accept()
    ws_connections[session_id] = websocket

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        if session_id in ws_connections:
            del ws_connections[session_id]


@router.get("/api/workflow/projects")
async def list_projects():
    """List all projects in deployment folder"""
    deployment_base = Path.home() / "projects" / "deployment"

    if not deployment_base.exists():
        return {"projects": []}

    projects = []
    for project_dir in deployment_base.iterdir():
        if project_dir.is_dir():
            # Get phases for this project
            phases = []
            for phase_dir in project_dir.iterdir():
                if phase_dir.is_dir():
                    phases.append(phase_dir.name)

            projects.append({
                "name": project_dir.name,
                "path": str(project_dir),
                "phases": sorted(phases)
            })

    return {"projects": projects}


@router.get("/api/workflow/projects/{project_name}/artifacts/{phase}")
async def get_phase_artifacts(project_name: str, phase: str):
    """Get artifacts for a specific project phase"""
    deployment_base = Path.home() / "projects" / "deployment"
    phase_dir = deployment_base / project_name / phase

    if not phase_dir.exists():
        return {"artifacts": []}

    artifacts = []
    for file_path in phase_dir.rglob("*"):
        if file_path.is_file():
            rel_path = str(file_path.relative_to(phase_dir))

            # Get file info
            stat = file_path.stat()

            # Try to read content for text files
            content = None
            is_text = file_path.suffix.lower() in ['.md', '.txt', '.json', '.yaml', '.yml', '.py', '.js', '.ts', '.html', '.css', '.xml']

            if is_text:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except:
                    pass

            artifacts.append({
                "name": file_path.name,
                "path": rel_path,
                "full_path": str(file_path),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "is_text": is_text,
                "content": content
            })

    return {"phase": phase, "project": project_name, "artifacts": artifacts}


@router.get("/api/workflow/artifacts/content")
async def get_artifact_content(file_path: str):
    """Get content of a specific artifact file"""
    path = Path(file_path)

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # Security check - ensure file is within deployment folder
    deployment_base = Path.home() / "projects" / "deployment"
    try:
        path.relative_to(deployment_base)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    # Try to read as text
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        return {
            "file_path": str(path),
            "content": content,
            "size": path.stat().st_size,
            "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        }
    except:
        raise HTTPException(status_code=400, detail="Cannot read file as text")


# ============================================================================
# ASYNC WORKFLOW EXECUTION ENDPOINTS (NEW)
# ============================================================================

# New request/response models for async workflows
class AsyncWorkflowExecuteRequest(BaseModel):
    requirement: str = Field(..., description="Project requirement/description")
    mode: Literal["batch", "phased", "mixed"] = Field("batch", description="Execution mode")
    project_name: Optional[str] = Field(None, description="Project name")
    checkpoint_phases: Optional[List[str]] = Field(None, description="Phases to checkpoint after (mixed mode)")
    quality_threshold: float = Field(0.70, description="Quality threshold (0.0-1.0)")


class AsyncWorkflowExecuteResponse(BaseModel):
    workflow_id: str
    status: str
    project_name: str
    mode: str
    message: str


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    status: str
    mode: str
    current_phase: Optional[str]
    phases_completed: List[str]
    progress: float
    started_at: str
    updated_at: str
    error: Optional[str]


@router.post("/api/workflow/execute", response_model=AsyncWorkflowExecuteResponse)
async def execute_async_workflow(request: AsyncWorkflowExecuteRequest):
    """
    Execute workflow asynchronously (non-blocking).

    Returns immediately with workflow_id for status tracking.
    """
    if not ASYNC_WORKFLOW_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Async workflow execution not available. Check server logs."
        )

    # Generate workflow ID
    workflow_id = f"wf-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    project_name = request.project_name or f"project_{workflow_id}"

    # Create execution request
    exec_request = WorkflowExecutionRequest(
        workflow_id=workflow_id,
        requirement=request.requirement,
        mode=request.mode,
        project_name=project_name,
        checkpoint_phases=request.checkpoint_phases,
        quality_threshold=request.quality_threshold
    )

    # Start workflow execution (non-blocking)
    result = await workflow_executor.start_workflow(exec_request)

    return AsyncWorkflowExecuteResponse(
        workflow_id=workflow_id,
        status=result["status"],
        project_name=project_name,
        mode=request.mode,
        message=f"Workflow started. Use /api/workflow/{workflow_id}/status to track progress."
    )


@router.get("/api/workflow/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(workflow_id: str):
    """Get current status of async workflow"""

    if not ASYNC_WORKFLOW_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Async workflow execution not available"
        )

    # Get status from executor
    status = await workflow_executor.get_status(workflow_id)

    if not status:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow {workflow_id} not found"
        )

    # Extract phase information
    phases_completed = []
    for phase in ["requirements", "design", "implementation", "testing", "deployment"]:
        if phase in status.get("phases", {}):
            phase_data = status["phases"][phase]
            if phase_data.get("status") == "completed":
                phases_completed.append(phase)

    return WorkflowStatusResponse(
        workflow_id=workflow_id,
        status=status.get("status", "unknown"),
        mode=status.get("mode", "unknown"),
        current_phase=status.get("current_phase"),
        phases_completed=phases_completed,
        progress=float(status.get("progress", 0.0)),
        started_at=status.get("started_at", ""),
        updated_at=status.get("updated_at", ""),
        error=status.get("error")
    )


@router.get("/api/workflow/{workflow_id}/checkpoints")
async def get_workflow_checkpoints(workflow_id: str):
    """List all checkpoints for a workflow"""

    if not ASYNC_WORKFLOW_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Async workflow execution not available"
        )

    checkpoints = await redis_manager.get_checkpoints(workflow_id)

    return {
        "workflow_id": workflow_id,
        "checkpoints": checkpoints
    }


@router.post("/api/workflow/{workflow_id}/pause")
async def pause_workflow(workflow_id: str):
    """Pause running workflow"""

    if not ASYNC_WORKFLOW_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Async workflow execution not available"
        )

    # Check if workflow exists
    workflow = await redis_manager.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow {workflow_id} not found"
        )

    # Pause workflow
    success = await workflow_executor.pause_workflow(workflow_id)

    return {
        "workflow_id": workflow_id,
        "status": "paused" if success else "error",
        "message": "Workflow paused successfully" if success else "Failed to pause workflow"
    }


@router.post("/api/workflow/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """Cancel running workflow"""

    if not ASYNC_WORKFLOW_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Async workflow execution not available"
        )

    # Check if workflow exists
    workflow = await redis_manager.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow {workflow_id} not found"
        )

    # Cancel workflow
    success = await workflow_executor.cancel_workflow(workflow_id)

    return {
        "workflow_id": workflow_id,
        "status": "cancelled" if success else "error",
        "message": "Workflow cancelled successfully" if success else "Failed to cancel workflow"
    }


@router.get("/api/workflow/active")
async def list_active_workflows():
    """List all currently active workflows"""

    if not ASYNC_WORKFLOW_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Async workflow execution not available"
        )

    active_workflows = await workflow_executor.get_active_workflows()

    # Get details for each
    workflows = []
    for workflow_id in active_workflows:
        workflow = await redis_manager.get_workflow(workflow_id)
        if workflow:
            workflows.append({
                "workflow_id": workflow_id,
                "status": workflow.get("status"),
                "mode": workflow.get("mode"),
                "project_name": workflow.get("project_name"),
                "current_phase": workflow.get("current_phase"),
                "progress": float(workflow.get("progress", 0.0)),
                "started_at": workflow.get("started_at")
            })

    return {
        "active_count": len(workflows),
        "workflows": workflows
    }


# Enhanced WebSocket endpoint for async workflows
@router.websocket("/ws/workflow-async/{workflow_id}")
async def websocket_async_workflow(websocket: WebSocket, workflow_id: str):
    """
    Enhanced WebSocket endpoint for async workflow updates.

    Provides real-time progress updates for async workflows.
    """
    if not ASYNC_WORKFLOW_AVAILABLE or not ws_manager:
        await websocket.close(code=1011, reason="Async workflow not available")
        return

    # Connect to WebSocket manager
    await ws_manager.connect(websocket, workflow_id)

    try:
        # Listen for client messages
        await ws_manager.listen(websocket, workflow_id)
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(websocket)


def get_workflow_router() -> APIRouter:
    """Get the workflow router for inclusion in main app"""
    return router
