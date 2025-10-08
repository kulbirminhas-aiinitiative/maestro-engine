#!/usr/bin/env python3
"""
MAESTRO Engine - Workflow API
FastAPI routes for Guardian workflow execution from maestro-frontend
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import Claude Code SDK
from claude_code_sdk import ClaudeCodeOptions, query
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

# Create router
router = APIRouter(prefix="", tags=["workflow"])


# Request/Response models
class WorkflowRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="Session ID")
    prompt: str = Field(..., description="User requirement/prompt")


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

    # Create or get session
    if session_id not in sessions:
        sessions[session_id] = {
            "session_id": session_id,
            "messages": [],
            "workflow_state": "idle",
            "files": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

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
                }
            )
        except:
            pass

    # Execute workflow
    result = await execute_generation(session_id, request.prompt)

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


async def execute_generation(session_id: str, requirement: str) -> Dict[str, Any]:
    """Execute code generation using Claude Code SDK"""
    work_dir = Path(f"/tmp/maestro_projects/accelerator_{session_id}")
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Configure Claude Code options
        options = ClaudeCodeOptions(
            cwd=str(work_dir),
            permission_mode="bypassPermissions",
            system_prompt=f"""You are an expert software developer creating production-ready applications.

CRITICAL INSTRUCTIONS:
1. Use the Write tool to create actual files - do NOT just describe code!
2. Your current working directory is: {work_dir}
3. Create complete, working applications with all necessary files
4. Include proper error handling, comments, and documentation

When users describe what they want to build:
1. Analyze the requirement thoroughly
2. Create a complete file structure
3. Use Write tool for each file with proper paths (e.g., './index.html', './src/app.js')
4. Include inline CSS and JavaScript where appropriate
5. Ensure the application is ready to run

Requirement: {requirement}

Create a complete, production-ready implementation.
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

        # Find created files
        created_files = []
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

                file_info = {
                    "path": rel_path,
                    "full_path": str(file_path),
                    "size": file_size,
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                }

                created_files.append(file_info)

                # Store in session
                sessions[session_id]["files"].append(file_info)

                # Send WebSocket file update
                if session_id in ws_connections:
                    try:
                        await ws_connections[session_id].send_json(
                            {"type": "file_created", "file_path": rel_path}
                        )
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


def get_workflow_router() -> APIRouter:
    """Get the workflow router for inclusion in main app"""
    return router
