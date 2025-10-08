#!/usr/bin/env python3
"""
Maestro Engine - Workflow BFF (Backend for Frontend)
Minimal API for Guardian workflow execution from maestro-frontend
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn

# Import Claude Code SDK
from claude_code_sdk import ClaudeCodeOptions, query
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# FastAPI app
app = FastAPI(
    title="Maestro Engine - Workflow BFF",
    description="Backend for Frontend API for Guardian workflow execution",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class WorkflowRequest(BaseModel):
    session_id: str = Field(..., description="Session ID")
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
    created_at: str
    updated_at: str


# In-memory session storage (replace with Redis in production)
sessions: Dict[str, Dict[str, Any]] = {}
ws_connections: Dict[str, WebSocket] = {}


@app.on_event("startup")
async def startup_event():
    print("✅ Maestro Engine - Workflow BFF started")
    print(f"🚀 Server: http://0.0.0.0:4001")
    print(f"📚 Docs: http://0.0.0.0:4001/docs")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "maestro-workflow-bff",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "claude_code_sdk": True,
            "redis": False,
            "websocket_connections": len(ws_connections),
        },
    }


@app.post("/ai/chat", response_model=WorkflowResponse)
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
        await ws_connections[session_id].send_json(
            {
                "type": "workflow_state",
                "state": "generating",
                "message": "Starting workflow execution...",
            }
        )

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
        await ws_connections[session_id].send_json(
            {
                "type": "workflow_state",
                "state": sessions[session_id]["workflow_state"],
                "message": result["ai_response"],
            }
        )

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
            system_prompt=f"""You are an expert Frontend Engineer in Accelerator mode.

CRITICAL INSTRUCTIONS:
1. Use the Write tool to create files - do NOT just describe code!
2. Your current working directory is: {work_dir}
3. Create the file as './index.html' (in the current directory)

When users describe what they want to build:
1. Respond briefly: "I'll create that for you!"
2. IMMEDIATELY use Write tool with file_path='./index.html'
3. Include complete HTML with inline CSS and JavaScript
4. Say: "Done! Your [project] is ready!"

Requirement: {requirement}
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

        full_response = "\n".join(response_parts)

        # Find created files
        created_files = []
        for file_path in work_dir.rglob("*"):
            if file_path.is_file():
                rel_path = str(file_path.relative_to(work_dir))
                created_files.append(
                    {
                        "path": rel_path,
                        "full_path": str(file_path),
                        "size": file_path.stat().st_size,
                    }
                )

                # Store in session
                sessions[session_id]["files"].append(
                    {
                        "path": rel_path,
                        "full_path": str(file_path),
                        "size": file_path.stat().st_size,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                # Send WebSocket file update
                if session_id in ws_connections:
                    await ws_connections[session_id].send_json(
                        {"type": "file_created", "file_path": rel_path}
                    )

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


@app.get("/api/session/{session_id}/state")
async def get_session_state(session_id: str):
    """Get session state"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return sessions[session_id]


@app.get("/api/session/{session_id}/files")
async def get_session_files(session_id: str):
    """Get generated files for session"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    files = []
    for file_info in sessions[session_id].get("files", []):
        try:
            with open(file_info["full_path"], "r") as f:
                content = f.read()
            files.append({"path": file_info["path"], "content": content, "size": file_info["size"]})
        except Exception as e:
            print(f"Error reading file {file_info['path']}: {e}")

    return files


@app.websocket("/ws/chat/{session_id}")
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


@app.websocket("/ws/workflow/{session_id}")
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


if __name__ == "__main__":
    uvicorn.run("workflow_bff:app", host="0.0.0.0", port=4001, log_level="info", reload=False)
