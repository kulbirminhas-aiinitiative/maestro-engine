#!/usr/bin/env python3
"""
Unified BFF Service for MAESTRO Accelerator
Single service for Chat + Preview with Redis state and WebSocket sync
Based on simple_workflow_api.py with Phase 1 enhancements
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn

# Import Claude Agent SDK (v3.0 - Security Update)
from claude_agent_sdk import ClaudeAgentOptions, query
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import local BFF modules
from bff.redis_state_manager import get_redis_state_manager
from bff.websocket_manager import get_websocket_manager

# Try to import shared logging, fall back to standard logging
try:
    from maestro_core_logging import configure_logging, get_logger

    configure_logging(service_name="unified-bff", environment="production", log_level="INFO")
    logger = get_logger(__name__)
    HAS_SHARED_LOGGING = True
except ImportError:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    HAS_SHARED_LOGGING = False

# Try to import Prometheus metrics
try:
    from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

    REQUEST_COUNT = Counter("unified_bff_requests_total", "Total requests", ["endpoint"])
    CHAT_DURATION = Histogram("unified_bff_chat_duration_seconds", "Chat request duration")
    WORKFLOW_DURATION = Histogram(
        "unified_bff_workflow_duration_seconds", "Workflow execution duration"
    )
    AI_CHATS_TOTAL = Counter("unified_bff_ai_chats_total", "Total AI chat requests")
    WORKFLOWS_TOTAL = Counter(
        "unified_bff_workflows_total", "Total workflow executions", ["status"]
    )
    WEBSOCKET_CONNECTIONS = Gauge(
        "unified_bff_websocket_connections", "Active WebSocket connections"
    )
    REDIS_OPERATIONS = Counter(
        "unified_bff_redis_operations_total", "Redis operations", ["operation", "status"]
    )
    HAS_PROMETHEUS = True
except ImportError:
    logger.warning("Prometheus client not available - metrics disabled")
    HAS_PROMETHEUS = False

    # Create stub metrics that do nothing
    class StubMetric:
        def inc(self):
            pass

        def dec(self):
            pass

        def observe(self, value):
            pass

        def labels(self, **kwargs):
            return self

    REQUEST_COUNT = StubMetric()
    CHAT_DURATION = StubMetric()
    WORKFLOW_DURATION = StubMetric()
    AI_CHATS_TOTAL = StubMetric()
    WORKFLOWS_TOTAL = StubMetric()
    WEBSOCKET_CONNECTIONS = StubMetric()
    REDIS_OPERATIONS = StubMetric()


# Request/Response Models
class AIChat(BaseModel):
    prompt: str = Field(..., description="The chat prompt/message")
    session_id: Optional[str] = Field(None, description="Session ID for state continuity")


class AIChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: str
    workflow_state: str
    has_preview: bool


class WorkflowRequest(BaseModel):
    requirement: str = Field(..., description="The project requirement to execute")
    session_id: Optional[str] = Field(None, description="Optional session ID")


class WorkflowResponse(BaseModel):
    session_id: str
    success: bool
    message: str
    requirement: str
    timestamp: str
    execution_time: float
    files_generated: List[str]
    project_path: str


# Initialize FastAPI
app = FastAPI(
    title="MAESTRO Unified BFF Service",
    description="Single service for Chat + Preview with Redis state and WebSocket sync",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
redis_state = get_redis_state_manager()
ws_manager = get_websocket_manager()


@app.on_event("startup")
async def startup_event():
    """Initialize unified BFF service"""
    # Connect to Redis
    try:
        await redis_state.connect()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")

    # Start WebSocket heartbeat monitor
    asyncio.create_task(ws_manager.start_heartbeat_monitor())
    logger.info("✅ WebSocket monitor started")

    logger.info("=" * 60)
    logger.info("🚀 MAESTRO Unified BFF Service Starting...")
    logger.info("=" * 60)
    logger.info(f"📡 Server: http://0.0.0.0:4001")
    logger.info(f"📚 Docs: http://0.0.0.0:4001/docs")
    if HAS_PROMETHEUS:
        logger.info(f"📊 Metrics: http://0.0.0.0:4001/metrics")
    logger.info(f"🔌 WebSocket: ws://localhost:4001/ws/{{session_id}}")
    logger.info("=" * 60)
    logger.info("✅ Features:")
    logger.info(f"  - Claude Agent SDK (v3.0): enabled")
    logger.info(f"  - Redis State: connected")
    logger.info(f"  - WebSocket: ready")
    logger.info(f"  - Prometheus: {'enabled' if HAS_PROMETHEUS else 'disabled'}")
    logger.info(f"  - Shared Logging: {'enabled' if HAS_SHARED_LOGGING else 'disabled'}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await redis_state.disconnect()
    logger.info("🛑 Unified BFF shutdown complete")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "maestro-unified-bff",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "claude_agent_sdk": True,
            "redis": await redis_state.session_exists("health_check"),
            "websocket_connections": ws_manager.get_connection_count(),
        },
        "architecture": "unified_bff",
    }


# ============================================================================
# WebSocket Endpoint - Single connection for Chat + Preview
# ============================================================================


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    Unified WebSocket endpoint
    Single connection handles both Chat and Preview updates
    """
    await ws_manager.connect(session_id, websocket)
    WEBSOCKET_CONNECTIONS.inc()

    try:
        # Initialize or retrieve session state
        state = await redis_state.get_session_state(session_id)
        if not state:
            state = await redis_state.create_session(session_id)

        # Send initial state sync
        await ws_manager.send_message(session_id, {"type": "state_sync", "state": state})

        # Listen for messages
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "pong":
                await ws_manager.handle_pong(session_id)

            elif data.get("type") == "chat_message":
                # Handle chat message via unified flow
                await handle_chat_message_unified(session_id, data.get("content", ""))

            elif data.get("type") == "request_preview":
                # Send current preview state
                preview = await redis_state.get_preview(session_id)
                await ws_manager.send_preview_update(session_id, preview or {})

    except WebSocketDisconnect:
        await ws_manager.disconnect(session_id)
        WEBSOCKET_CONNECTIONS.dec()
        logger.info(f"WebSocket disconnected: {session_id}")


async def handle_chat_message_unified(session_id: str, user_message: str):
    """
    Unified chat message handler
    Updates both Chat and Preview via single WebSocket broadcast
    """
    # 1. Add user message to conversation (Redis)
    await redis_state.add_message(session_id, "user", user_message)

    # 2. Broadcast user message
    await ws_manager.send_chat_message(session_id, "user", user_message)

    # 3. Update workflow state to "generating"
    await redis_state.update_workflow_state(session_id, "generating")
    await ws_manager.send_workflow_state_change(session_id, "idle", "generating")

    # 4. Send progress indicator
    await ws_manager.send_generation_progress(
        session_id,
        stage="initializing",
        progress=10,
        message="Frontend Engineer Persona is analyzing your request...",
    )

    # 5. Execute generation (inline for now, will move to agent in Phase 3)
    try:
        result = await execute_generation(session_id, user_message)

        if result["success"]:
            # 6a. Success: Update conversation
            await redis_state.add_message(session_id, "assistant", result["ai_response"])
            await ws_manager.send_chat_message(session_id, "assistant", result["ai_response"])

            # 6b. Update preview if HTML was generated
            if result.get("html_content"):
                preview_data = {
                    "type": "web",
                    "html_content": result["html_content"],
                    "files": result.get("files", []),
                }
                await redis_state.update_preview(session_id, preview_data)
                await ws_manager.send_preview_update(session_id, preview_data)

            # 6c. Notify about generated files
            for file_info in result.get("files", []):
                await redis_state.add_generated_file(session_id, file_info)
                await ws_manager.send_file_generated(session_id, file_info)

            # 6d. Update workflow state to "complete"
            await redis_state.update_workflow_state(session_id, "complete")
            await ws_manager.send_workflow_state_change(session_id, "generating", "complete")

        else:
            # Error handling
            error_msg = f"Generation failed: {result.get('error', 'Unknown error')}"
            await redis_state.add_message(session_id, "assistant", error_msg)
            await ws_manager.send_error(session_id, error_msg)
            await redis_state.update_workflow_state(session_id, "error")

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        await redis_state.add_message(session_id, "assistant", error_msg)
        await ws_manager.send_error(session_id, error_msg)
        await redis_state.update_workflow_state(session_id, "error")


async def execute_generation(session_id: str, requirement: str) -> Dict[str, Any]:
    """
    Execute code generation using Claude Code SDK
    Phase 1: Inline execution
    Phase 3: Will dispatch to agent via message broker
    """
    work_dir = Path(f"/tmp/maestro_projects/accelerator_{session_id}")
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Configure Claude Agent SDK options (v3.0) for Frontend Engineer persona
        options = ClaudeAgentOptions(
            cwd=str(work_dir),
            permission_mode="bypassPermissions",
            system_prompt=f"""You are an expert Frontend Engineer in Accelerator mode - a rapid prototyping AI assistant.

CRITICAL INSTRUCTIONS:
1. You MUST use the Write tool to create files - do NOT just describe code!
2. Your current working directory is: {work_dir}
3. Create the file as './index.html' (in the current directory)
4. The file MUST be created in the working directory, not /tmp

When users describe what they want to build:
1. Respond briefly: "I'll create that for you!"
2. IMMEDIATELY use Write tool with file_path='./index.html'
3. Include complete HTML with inline CSS and JavaScript
4. Say: "Done! Your [project] is ready!"

Example:
User: "build a button"
You: Use Write tool NOW with:
  file_path: './index.html'
  content: <full HTML>
Then say: "Done! Your button is ready!"

DO NOT write to /tmp/index.html - write to ./index.html in your working directory!""",
            continue_conversation=True,
            allowed_tools=["write", "read", "bash", "glob", "grep"],
        )

        # Execute with Claude Code SDK
        response_parts = []
        async for message in query(prompt=requirement, options=options):
            if hasattr(message, "text") and message.text:
                response_parts.append(message.text)
            elif hasattr(message, "content"):
                content = message.content
                if isinstance(content, str):
                    response_parts.append(content)
                elif isinstance(content, list):
                    for item in content:
                        if hasattr(item, "text"):
                            response_parts.append(item.text)

        full_response = (
            "\n".join(response_parts) if response_parts else "I'm working on your request!"
        )

        # Check if index.html was created
        index_file = work_dir / "index.html"
        html_content = None
        if index_file.exists():
            with open(index_file, "r", encoding="utf-8") as f:
                html_content = f.read()

        # Find all generated files
        files = []
        for file_path in work_dir.rglob("*"):
            if file_path.is_file():
                files.append(
                    {
                        "path": str(file_path.relative_to(work_dir)),
                        "full_path": str(file_path),
                        "size": file_path.stat().st_size,
                    }
                )

        return {
            "success": True,
            "ai_response": full_response,
            "html_content": html_content,
            "files": files,
            "work_dir": str(work_dir),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "ai_response": f"Sorry, I encountered an error: {str(e)}",
        }


# ============================================================================
# REST API Endpoints (for compatibility)
# ============================================================================


@app.post("/ai/chat", response_model=AIChatResponse)
async def ai_chat(request: AIChat):
    """
    Chat endpoint (REST fallback)
    Recommended: Use WebSocket for real-time updates
    """
    REQUEST_COUNT.labels(endpoint="/ai/chat").inc()
    AI_CHATS_TOTAL.inc()
    start_time = time.time()

    session_id = request.session_id or f"session_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    logger.info(f"AI chat request - session: {session_id}, prompt length: {len(request.prompt)}")

    # Get or create session
    state = await redis_state.get_session_state(session_id)
    if not state:
        state = await redis_state.create_session(session_id)

    # Add user message
    await redis_state.add_message(session_id, "user", request.prompt)

    # If WebSocket connected, send via WebSocket
    if ws_manager.is_connected(session_id):
        await handle_chat_message_unified(session_id, request.prompt)

        # Return immediate response
        return AIChatResponse(
            response="Processing your request via WebSocket...",
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            workflow_state="generating",
            has_preview=False,
        )
    else:
        # No WebSocket, execute inline and return result
        result = await execute_generation(session_id, request.prompt)

        await redis_state.add_message(session_id, "assistant", result["ai_response"])

        if result.get("html_content"):
            await redis_state.update_preview(
                session_id, {"type": "web", "html_content": result["html_content"]}
            )

        duration = time.time() - start_time
        CHAT_DURATION.observe(duration)
        logger.info(
            f"AI chat complete - session: {session_id}, duration: {duration:.2f}s, success: {result['success']}"
        )

        return AIChatResponse(
            response=result["ai_response"],
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            workflow_state="complete" if result["success"] else "error",
            has_preview=result.get("html_content") is not None,
        )


@app.get("/api/session/{session_id}/state")
async def get_session_state(session_id: str):
    """Get current session state"""
    state = await redis_state.get_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    return state


@app.get("/api/session/{session_id}/preview")
async def get_preview(session_id: str):
    """Get current preview content"""
    preview = await redis_state.get_preview(session_id)
    if not preview:
        raise HTTPException(status_code=404, detail="No preview available")

    # Frontend expects { html_content: string }
    return {"html_content": preview.get("html_content", "")}


@app.get("/api/session/{session_id}/files")
async def get_files(session_id: str):
    """Get generated files"""
    files = await redis_state.get_generated_files(session_id)
    return {"files": files}


@app.get("/api/stats")
async def get_stats():
    """Get service statistics"""
    return {
        "active_sessions": await redis_state.get_active_sessions_count(),
        "websocket_connections": ws_manager.get_connection_count(),
        "websocket_stats": ws_manager.get_all_connection_stats(),
    }


# ============================================================================
# SDLC Document Endpoints (for historical project viewing)
# ============================================================================


@app.get("/api/sdlc/projects")
async def list_sdlc_projects():
    """List available SDLC projects from examples"""
    projects_base = Path("/home/ec2-user/projects/shared/claude_team_sdk/examples/sdlc_team")

    if not projects_base.exists():
        return {"projects": []}

    projects = []
    for project_dir in projects_base.iterdir():
        if project_dir.is_dir():
            # Check for nested structure (e.g., sunday_com/sunday_com)
            nested_dir = project_dir / project_dir.name
            if nested_dir.exists() and nested_dir.is_dir():
                projects.append(
                    {
                        "id": project_dir.name,
                        "name": project_dir.name.replace("_", ".").title(),
                        "path": str(nested_dir),
                        "status": "completed",
                    }
                )

    return {"projects": projects}


@app.get("/api/sdlc/documents/{project_id}")
async def get_sdlc_documents(project_id: str):
    """Get SDLC documents for a specific project"""
    project_base = Path(
        f"/home/ec2-user/projects/shared/claude_team_sdk/examples/sdlc_team/{project_id}/{project_id}"
    )

    if not project_base.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Map files to SDLC phases
    phase_mapping = {
        "requirements": [
            "requirements_document.md",
            "user_stories.md",
            "acceptance_criteria.md",
            "requirement_backlog.md",
        ],
        "design": [
            "architecture_document.md",
            "tech_stack.md",
            "database_design.md",
            "api_specifications.md",
            "system_design.md",
            "design/",
        ],
        "implementation": ["backend/", "frontend/", "README.md", "DevOps-README.md"],
        "testing": [
            "security_review.md",
            "threat_model.md",
            "security_requirements.md",
            "penetration_test_results.md",
            "testing/",
        ],
    }

    documents_by_phase = {}

    for phase, file_patterns in phase_mapping.items():
        documents = []

        for pattern in file_patterns:
            if pattern.endswith("/"):
                # Handle directories
                dir_path = project_base / pattern.rstrip("/")
                if dir_path.exists() and dir_path.is_dir():
                    for file_path in dir_path.glob("*.md"):
                        content = file_path.read_text()
                        documents.append(
                            {
                                "id": f"{project_id}_{phase}_{file_path.stem}",
                                "title": file_path.stem.replace("_", " ").title(),
                                "phase": phase,
                                "artifactType": "document",
                                "renderType": "markdown",
                                "rawContent": content,
                                "generatedAt": datetime.fromtimestamp(
                                    file_path.stat().st_mtime
                                ).isoformat(),
                                "status": "generated",
                                "version": "1.0",
                            }
                        )
            else:
                # Handle individual files
                file_path = project_base / pattern
                if file_path.exists():
                    content = file_path.read_text()
                    documents.append(
                        {
                            "id": f"{project_id}_{phase}_{file_path.stem}",
                            "title": file_path.stem.replace("_", " ").title(),
                            "phase": phase,
                            "artifactType": "document",
                            "renderType": "markdown",
                            "rawContent": content,
                            "generatedAt": datetime.fromtimestamp(
                                file_path.stat().st_mtime
                            ).isoformat(),
                            "status": "generated",
                            "version": "1.0",
                        }
                    )

        documents_by_phase[phase] = documents

    return documents_by_phase


@app.get("/api/sdlc/execution/{project_id}")
async def get_execution_history(project_id: str):
    """Get execution history and metadata for a completed SDLC project"""
    # For now, return static data for sunday_com
    # TODO: Parse actual execution logs from maestro engine
    if project_id == "sunday_com":
        return {
            "projectId": project_id,
            "status": "completed",
            "startTime": "2025-10-04T12:32:19Z",
            "endTime": "2025-10-04T15:02:19Z",
            "duration": 8829,  # seconds (2.5 hours)
            "personas": [
                {"name": "requirement_analyst", "status": "completed", "order": 1},
                {"name": "solution_architect", "status": "completed", "order": 2},
                {"name": "backend_developer", "status": "completed", "order": 3},
                {"name": "frontend_developer", "status": "completed", "order": 4},
                {"name": "ui_ux_designer", "status": "completed", "order": 5},
                {"name": "database_administrator", "status": "completed", "order": 6},
                {"name": "security_specialist", "status": "completed", "order": 7},
                {"name": "qa_engineer", "status": "completed", "order": 8},
                {"name": "devops_engineer", "status": "completed", "order": 9},
                {"name": "deployment_specialist", "status": "completed", "order": 10},
                {"name": "technical_writer", "status": "completed", "order": 11},
                {"name": "deployment_integration_tester", "status": "completed", "order": 12},
            ],
            "activityLog": [
                {
                    "timestamp": "2025-10-04T12:32:19Z",
                    "agent": "System",
                    "message": "Monday.com Workflow (sunday_com) initiated",
                    "type": "info",
                    "phase": "requirements",
                },
                {
                    "timestamp": "2025-10-04T12:36:00Z",
                    "agent": "Requirement Analyst",
                    "message": "Generated requirements_document.md",
                    "type": "success",
                    "phase": "requirements",
                },
                {
                    "timestamp": "2025-10-04T12:37:00Z",
                    "agent": "Requirement Analyst",
                    "message": "Generated user_stories.md",
                    "type": "success",
                    "phase": "requirements",
                },
                {
                    "timestamp": "2025-10-04T12:38:00Z",
                    "agent": "Requirement Analyst",
                    "message": "Generated acceptance_criteria.md",
                    "type": "success",
                    "phase": "requirements",
                },
                {
                    "timestamp": "2025-10-04T12:39:00Z",
                    "agent": "Requirement Analyst",
                    "message": "Generated requirement_backlog.md",
                    "type": "success",
                    "phase": "requirements",
                },
                {
                    "timestamp": "2025-10-04T12:42:00Z",
                    "agent": "Solution Architect",
                    "message": "Generated architecture_document.md",
                    "type": "success",
                    "phase": "design",
                },
                {
                    "timestamp": "2025-10-04T12:44:00Z",
                    "agent": "Solution Architect",
                    "message": "Generated tech_stack.md",
                    "type": "success",
                    "phase": "design",
                },
                {
                    "timestamp": "2025-10-04T12:47:00Z",
                    "agent": "Database Administrator",
                    "message": "Generated database_design.md",
                    "type": "success",
                    "phase": "design",
                },
                {
                    "timestamp": "2025-10-04T12:49:00Z",
                    "agent": "Solution Architect",
                    "message": "Generated api_specifications.md",
                    "type": "success",
                    "phase": "design",
                },
                {
                    "timestamp": "2025-10-04T12:53:00Z",
                    "agent": "Solution Architect",
                    "message": "Generated system_design.md",
                    "type": "success",
                    "phase": "design",
                },
                {
                    "timestamp": "2025-10-04T12:58:00Z",
                    "agent": "Security Specialist",
                    "message": "Generated security_review.md",
                    "type": "success",
                    "phase": "testing",
                },
                {
                    "timestamp": "2025-10-04T13:02:00Z",
                    "agent": "Security Specialist",
                    "message": "Generated threat_model.md",
                    "type": "success",
                    "phase": "testing",
                },
                {
                    "timestamp": "2025-10-04T13:08:00Z",
                    "agent": "Security Specialist",
                    "message": "Generated security_requirements.md",
                    "type": "success",
                    "phase": "testing",
                },
                {
                    "timestamp": "2025-10-04T13:12:00Z",
                    "agent": "Security Specialist",
                    "message": "Generated penetration_test_results.md",
                    "type": "success",
                    "phase": "testing",
                },
                {
                    "timestamp": "2025-10-04T13:50:00Z",
                    "agent": "Backend Developer",
                    "message": "Generated backend application code",
                    "type": "success",
                    "phase": "implementation",
                },
                {
                    "timestamp": "2025-10-04T13:50:00Z",
                    "agent": "Frontend Developer",
                    "message": "Generated frontend application code",
                    "type": "success",
                    "phase": "implementation",
                },
                {
                    "timestamp": "2025-10-04T14:01:00Z",
                    "agent": "Technical Writer",
                    "message": "Generated README.md",
                    "type": "success",
                    "phase": "implementation",
                },
                {
                    "timestamp": "2025-10-04T14:42:00Z",
                    "agent": "Deployment Specialist",
                    "message": "Generated deployment_guide.md",
                    "type": "success",
                    "phase": "deployment",
                },
                {
                    "timestamp": "2025-10-04T14:46:00Z",
                    "agent": "DevOps Engineer",
                    "message": "Generated monitoring_setup.md",
                    "type": "success",
                    "phase": "deployment",
                },
                {
                    "timestamp": "2025-10-04T15:01:00Z",
                    "agent": "Deployment Integration Tester",
                    "message": "Generated production_deployment_checklist.md",
                    "type": "success",
                    "phase": "deployment",
                },
                {
                    "timestamp": "2025-10-04T15:02:19Z",
                    "agent": "System",
                    "message": "Monday.com Workflow (sunday_com) completed successfully!",
                    "type": "success",
                    "phase": "deployment",
                },
            ],
        }
    else:
        raise HTTPException(status_code=404, detail=f"Execution history for {project_id} not found")


# ============================================================================
# Legacy Endpoints (for compatibility with existing frontend)
# ============================================================================


@app.get("/accelerator/preview/{project_name}")
async def get_accelerator_preview(project_name: str):
    """
    Legacy endpoint for preview fetching
    Extracts session_id from project_name (format: accelerator_{session_id})
    """
    # Extract session_id from project_name
    if project_name.startswith("accelerator_"):
        session_id = project_name.replace("accelerator_", "")
    else:
        session_id = project_name

    # Get preview from Redis
    preview = await redis_state.get_preview(session_id)
    if not preview:
        raise HTTPException(status_code=404, detail="Preview not found")

    return {
        "content": preview.get("html_content", ""),
        "project_path": f"/tmp/maestro_projects/accelerator_{session_id}",
        "timestamp": preview.get("last_updated", datetime.now().isoformat()),
    }


# ============================================================================
# Deployment File Reading Endpoints
# ============================================================================

import os
from pathlib import Path


@app.get("/files/list")
async def list_deployment_files(path: str):
    """List files in deployment directory"""
    try:
        full_path = Path(path)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Path not found")

        if not full_path.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")

        files = []
        for item in full_path.iterdir():
            files.append(
                {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                }
            )

        return {"files": files, "path": str(full_path)}
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/read")
async def read_deployment_file(path: str):
    """Read a file from deployment directory"""
    try:
        full_path = Path(path)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        if not full_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")

        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        return {"content": content, "path": str(full_path), "size": full_path.stat().st_size}
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not a text file")
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Mount Prometheus metrics endpoint if available
if HAS_PROMETHEUS:
    app.mount("/metrics", make_asgi_app())


if __name__ == "__main__":
    logger.info("🚀 Starting Unified BFF Service on port 4001...")

    uvicorn.run(app, host="0.0.0.0", port=4001, log_level="info")
