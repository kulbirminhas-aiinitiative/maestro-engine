#!/usr/bin/env python3
"""
Enhanced MAESTRO MCP Context Workflow API with Hot Session Support
Direct Claude Code SDK integration with hot session management and MCP context sharing
"""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import Claude Code SDK
from claude_code_sdk import query, ClaudeCodeOptions

# Import MAESTRO Claude Toolkit
from maestro_claude_toolkit import get_toolkit_tools

# Import Hot Session Manager
from hot_mcp_session_manager import get_hot_session_pool, HotMCPSession

# Import Dynamic MCP Service
from dynamic_mcp_service import get_dynamic_mcp_service


# Request/Response Models
class MCPWorkflowRequest(BaseModel):
    session_id: str = Field(..., description="MCP session ID to fetch context from")
    project_name: Optional[str] = Field(None, description="Optional project name")
    mcp_context_dir: Optional[str] = Field("/tmp/mcp_shared_context", description="MCP context directory")
    use_hot_session: Optional[bool] = Field(True, description="Use hot session for faster execution")


class HotSessionRequest(BaseModel):
    session_id: str = Field(..., description="Session ID")
    requirement: str = Field(..., description="User requirement")
    use_mcp_context: Optional[bool] = Field(True, description="Use MCP context if available")


class WorkflowResponse(BaseModel):
    session_id: str
    success: bool
    message: str
    requirement: str
    timestamp: str
    execution_time: float
    files_generated: List[str]
    project_path: str
    mcp_context_used: bool
    hot_session_used: bool
    session_stats: Optional[Dict[str, Any]] = None


# Initialize FastAPI
app = FastAPI(
    title="Enhanced MAESTRO MCP Context Workflow API",
    description="Direct Claude Code SDK integration with hot session management, MCP context sharing and MAESTRO Claude Toolkit",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global hot session pool and dynamic service
hot_session_pool = get_hot_session_pool()
dynamic_mcp_service = get_dynamic_mcp_service()


@app.on_event("startup")
async def startup_event():
    """Initialize API, hot session pool, and dynamic MCP service"""
    print("✅ Enhanced MAESTRO MCP Context Workflow API started")
    print(f"🚀 Server: http://0.0.0.0:4001")
    print(f"📚 Docs: http://0.0.0.0:4001/docs")
    print(f"🔧 Claude Code SDK: Direct integration")
    print(f"📋 MCP Context: Enabled")
    print(f"🛠️  MAESTRO Claude Toolkit: {len(get_toolkit_tools())} specialized tools")

    # Initialize hot session pool and dynamic service
    await hot_session_pool.initialize_pool()

    # Start dynamic MCP service in background task
    asyncio.create_task(dynamic_mcp_service.start())
    print(f"🔥 Hot Sessions: Enabled")
    print(f"📡 Dynamic MCP Service: Monitoring cache for pre-processing")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("🧹 Cleaning up hot sessions...")
    await hot_session_pool.cleanup_old_sessions()


@app.get("/health")
async def health_check():
    """Health check endpoint with hot session status"""
    pool_stats = hot_session_pool.get_pool_stats()

    return {
        "status": "healthy",
        "service": "enhanced-maestro-mcp-workflow-api",
        "timestamp": datetime.now().isoformat(),
        "claude_code_sdk_available": True,
        "mcp_context_enabled": True,
        "maestro_claude_toolkit": {
            "enabled": True,
            "tools_count": len(get_toolkit_tools()),
            "available_tools": get_toolkit_tools()
        },
        "hot_sessions": {
            "enabled": True,
            "pool_stats": pool_stats
        }
    }


def get_mcp_context(session_id: str, mcp_context_dir: str = "/tmp/mcp_shared_context") -> Dict[str, Any]:
    """Retrieve MCP context for a given session"""
    mcp_dir = Path(mcp_context_dir)
    mcp_file = mcp_dir / f"{session_id}.json"

    if not mcp_file.exists():
        return {
            "has_context": False,
            "reason": "mcp_file_not_found",
            "file_path": str(mcp_file)
        }

    try:
        with open(mcp_file, 'r') as f:
            context = json.load(f)

        # Validate context structure
        required_keys = ["conversation", "latest_user_message", "updated_at"]
        if not all(key in context for key in required_keys):
            return {
                "has_context": False,
                "reason": "invalid_context_structure",
                "missing_keys": [key for key in required_keys if key not in context]
            }

        return {
            "has_context": True,
            "conversation": context.get("conversation", []),
            "latest_user_message": context.get("latest_user_message", ""),
            "latest_ai_response": context.get("latest_ai_response", ""),
            "updated_at": context.get("updated_at", ""),
            "message_count": len(context.get("conversation", [])),
            "file_path": str(mcp_file)
        }

    except Exception as e:
        return {
            "has_context": False,
            "reason": "mcp_parse_error",
            "error": str(e)
        }


async def execute_with_hot_session(
    requirement: str,
    hot_session: HotMCPSession,
    use_mcp_context: bool = True
) -> Dict[str, Any]:
    """Execute workflow using hot session with Claude Code SDK"""

    # Create project directory
    hot_session.project_path.mkdir(parents=True, exist_ok=True)

    try:
        # Get MAESTRO Claude Toolkit tools
        toolkit_tools = get_toolkit_tools()

        # Build context-aware prompt
        context_prompt = ""
        if use_mcp_context and hot_session.mcp_context.get("conversation"):
            context_prompt = f"""
Previous conversation context:
{chr(10).join([f"{msg['role'].upper()}: {msg['content']}" for msg in hot_session.mcp_context['conversation'][-3:]])}

"""

        # Configure Claude Code options with enhanced tools
        options = ClaudeCodeOptions(
            cwd=str(hot_session.project_path),
            system_prompt=f"""You are a professional software developer with access to the MAESTRO Claude Toolkit.

{context_prompt}Current requirement: {requirement}

Available specialized tools from MAESTRO Claude Toolkit:
- create_code_file: Create code files with proper syntax highlighting and purpose documentation
- create_documentation: Generate comprehensive documentation files
- create_config_file: Create configuration files with proper formatting
- create_project_structure: Set up complete directory structures
- save_persona_analysis: Save analysis and context for future reference
- get_previous_context: Access work from previous development phases
- list_artifacts: View all created project artifacts

Create complete, working code with proper structure:
1. Use create_code_file for all source code with appropriate language tags
2. Use create_documentation for README.md and other docs
3. Use create_config_file for configuration files
4. Use create_project_structure to organize directories
5. Include proper error handling and comments

Focus on clean, production-ready code with comprehensive documentation.""",
            continue_conversation=len(hot_session.conversation_history) > 0,
            allowed_tools=["read", "write", "bash", "glob", "grep"] + toolkit_tools
        )

        # Execute with Claude Code SDK
        response_parts = []
        async for message in query(prompt=requirement, options=options):
            if hasattr(message, 'text') and message.text:
                response_parts.append(message.text)

        full_response = "\n".join(response_parts)

        # Update hot session
        hot_session.add_conversation("user", requirement)
        hot_session.add_conversation("assistant", full_response)
        hot_session.last_requirement = requirement

        # Find created files
        created_files = []
        for file_path in hot_session.project_path.rglob("*"):
            if file_path.is_file():
                created_files.append(str(file_path))
                hot_session.add_generated_file(str(file_path))

        # Save hot session state
        hot_session.save_mcp_context()

        return {
            "success": True,
            "message": f"Implementation completed successfully - {len(created_files)} files created",
            "files_created": created_files,
            "instructions": f"Project created in {hot_session.project_path}. Check README.md for setup instructions.",
            "claude_response": full_response[:500] + "..." if len(full_response) > 500 else full_response,
            "hot_session_stats": hot_session.to_dict()
        }

    except Exception as e:
        # Return failure with detailed error message
        return {
            "success": False,
            "message": f"Hot session execution failed: {str(e)}",
            "files_created": [],
            "instructions": "Execution failed - check error message for details",
            "claude_response": f"Error: {str(e)}",
            "hot_session_stats": hot_session.to_dict()
        }


@app.post("/api/hot-execute", response_model=WorkflowResponse)
async def execute_hot_session_workflow(request: HotSessionRequest):
    """Execute workflow using hot session for faster response"""

    start_time = time.time()

    try:
        # Acquire hot session from pool
        hot_session = await hot_session_pool.acquire_session(request.session_id)

        # Execute with hot session
        result = await execute_with_hot_session(
            requirement=request.requirement,
            hot_session=hot_session,
            use_mcp_context=request.use_mcp_context
        )

        execution_time = time.time() - start_time

        return WorkflowResponse(
            session_id=request.session_id,
            success=result["success"],
            message=result["message"],
            requirement=request.requirement,
            timestamp=datetime.now().isoformat(),
            execution_time=execution_time,
            files_generated=result.get("files_created", []),
            project_path=str(hot_session.project_path),
            mcp_context_used=request.use_mcp_context,
            hot_session_used=True,
            session_stats=result.get("hot_session_stats")
        )

    except Exception as e:
        execution_time = time.time() - start_time

        raise HTTPException(
            status_code=500,
            detail={
                "error": "Hot session execution failed",
                "message": str(e),
                "session_id": request.session_id,
                "execution_time": execution_time
            }
        )


async def execute_with_claude_code(requirement: str, project_path: Path) -> Dict[str, Any]:
    """Execute workflow using Claude Code SDK directly (legacy method)"""

    # Create project directory
    project_path.mkdir(parents=True, exist_ok=True)

    try:
        # Get MAESTRO Claude Toolkit tools
        toolkit_tools = get_toolkit_tools()

        # Configure Claude Code options with enhanced tools
        options = ClaudeCodeOptions(
            cwd=str(project_path),
            system_prompt=f"""You are a professional software developer with access to the MAESTRO Claude Toolkit.

Implement the following requirement: {requirement}

Available specialized tools from MAESTRO Claude Toolkit:
- create_code_file: Create code files with proper syntax highlighting and purpose documentation
- create_documentation: Generate comprehensive documentation files
- create_config_file: Create configuration files with proper formatting
- create_project_structure: Set up complete directory structures
- save_persona_analysis: Save analysis and context for future reference
- get_previous_context: Access work from previous development phases
- list_artifacts: View all created project artifacts

Create complete, working code with proper structure:
1. Use create_code_file for all source code with appropriate language tags
2. Use create_documentation for README.md and other docs
3. Use create_config_file for configuration files
4. Use create_project_structure to organize directories
5. Include proper error handling and comments

Focus on clean, production-ready code with comprehensive documentation.""",
            continue_conversation=False,
            allowed_tools=["read", "write", "bash", "glob", "grep"] + toolkit_tools
        )

        # Execute with Claude Code SDK
        response_parts = []
        async for message in query(prompt=requirement, options=options):
            if hasattr(message, 'text') and message.text:
                response_parts.append(message.text)

        full_response = "\n".join(response_parts)

        # Find created files
        created_files = []
        for file_path in project_path.rglob("*"):
            if file_path.is_file():
                created_files.append(str(file_path))

        return {
            "success": True,
            "message": f"Implementation completed successfully - {len(created_files)} files created",
            "files_created": created_files,
            "instructions": f"Project created in {project_path}. Check README.md for setup instructions.",
            "claude_response": full_response[:500] + "..." if len(full_response) > 500 else full_response
        }

    except Exception as e:
        # Return failure with detailed error message
        return {
            "success": False,
            "message": f"Claude Code SDK execution failed: {str(e)}",
            "files_created": [],
            "instructions": "Execution failed - check error message for details",
            "claude_response": f"Error: {str(e)}"
        }


@app.post("/api/execute", response_model=WorkflowResponse)
async def execute_mcp_workflow(request: MCPWorkflowRequest):
    """Execute workflow using MCP context (with optional hot session)"""

    start_time = time.time()

    # Get MCP context
    mcp_context = get_mcp_context(request.session_id, request.mcp_context_dir)

    if not mcp_context["has_context"]:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "MCP context not available",
                "reason": mcp_context["reason"],
                "session_id": request.session_id,
                "mcp_context_dir": request.mcp_context_dir
            }
        )

    # Extract requirement from MCP context
    requirement = mcp_context["latest_user_message"]
    if not requirement or not requirement.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "No requirement found in MCP context",
                "latest_user_message": requirement,
                "session_id": request.session_id
            }
        )

    # Generate project name if not provided
    project_name = request.project_name or f"mcp_project_{request.session_id}"

    # Execute with hot session or traditional method
    if request.use_hot_session:
        try:
            hot_session = await hot_session_pool.acquire_session(request.session_id)
            result = await execute_with_hot_session(
                requirement=requirement,
                hot_session=hot_session,
                use_mcp_context=True
            )
            project_path = hot_session.project_path
            hot_session_used = True
            session_stats = result.get("hot_session_stats")

        except Exception as e:
            # Fallback to traditional method
            project_path = Path(f"/tmp/maestro_projects/{project_name}")
            result = await execute_with_claude_code(requirement, project_path)
            hot_session_used = False
            session_stats = None

    else:
        # Traditional method
        project_path = Path(f"/tmp/maestro_projects/{project_name}")
        result = await execute_with_claude_code(requirement, project_path)
        hot_session_used = False
        session_stats = None

    execution_time = time.time() - start_time

    return WorkflowResponse(
        session_id=request.session_id,
        success=result["success"],
        message=result["message"],
        requirement=requirement,
        timestamp=datetime.now().isoformat(),
        execution_time=execution_time,
        files_generated=result.get("files_created", []),
        project_path=str(project_path),
        mcp_context_used=True,
        hot_session_used=hot_session_used,
        session_stats=session_stats
    )


@app.get("/api/hot-sessions")
async def list_hot_sessions():
    """List all active hot sessions"""
    return {
        "pool_stats": hot_session_pool.get_pool_stats(),
        "active_sessions": hot_session_pool.list_active_sessions()
    }


@app.delete("/api/hot-sessions/{session_id}")
async def release_hot_session(session_id: str, save_state: bool = True):
    """Release a hot session"""
    await hot_session_pool.release_session(session_id, save_state=save_state)
    return {
        "message": f"Hot session {session_id} released",
        "state_saved": save_state
    }


@app.post("/api/hot-sessions/cleanup")
async def cleanup_old_hot_sessions():
    """Cleanup old inactive hot sessions"""
    await hot_session_pool.cleanup_old_sessions()
    return {
        "message": "Old hot sessions cleaned up",
        "pool_stats": hot_session_pool.get_pool_stats()
    }


@app.get("/api/mcp-context/{session_id}")
async def get_mcp_context_info(session_id: str, mcp_context_dir: str = "/tmp/mcp_shared_context"):
    """Get MCP context information for debugging"""
    return get_mcp_context(session_id, mcp_context_dir)


@app.get("/api/projects/{project_name}")
async def get_project_files(project_name: str):
    """Get list of files in a project"""
    project_path = Path(f"/tmp/maestro_projects/{project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    files = []
    for file_path in project_path.rglob("*"):
        if file_path.is_file():
            files.append({
                "path": str(file_path.relative_to(project_path)),
                "size": file_path.stat().st_size,
                "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            })

    return {
        "project_name": project_name,
        "project_path": str(project_path),
        "file_count": len(files),
        "files": sorted(files, key=lambda x: x["path"])
    }


@app.get("/api/projects/{project_name}/files/{file_path:path}")
async def get_file_content(project_name: str, file_path: str):
    """Get content of a specific file"""
    full_path = Path(f"/tmp/maestro_projects/{project_name}/{file_path}")

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return {
            "project_name": project_name,
            "file_path": file_path,
            "content": content,
            "size": len(content),
            "lines": len(content.splitlines())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read file: {str(e)}")


# Dynamic MCP Service Endpoints

@app.get("/api/dynamic-service/stats")
async def get_dynamic_service_stats():
    """Get dynamic MCP service statistics"""
    try:
        stats = await dynamic_mcp_service.get_service_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not get service stats: {str(e)}")


@app.get("/api/dynamic-service/cache-entries")
async def list_cache_entries(status_filter: Optional[str] = None):
    """List cache entries with optional status filter"""
    try:
        entries = await dynamic_mcp_service.list_cache_entries(status_filter)
        return {
            "cache_entries": entries,
            "total_count": len(entries),
            "status_filter": status_filter
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not list cache entries: {str(e)}")


class DynamicExecuteRequest(BaseModel):
    session_id: str = Field(..., description="Session ID that was pre-processed")
    frontend_request_data: Optional[Dict[str, Any]] = Field({}, description="Additional frontend request data")


@app.post("/api/dynamic-execute", response_model=WorkflowResponse)
async def execute_with_dynamic_linking(request: DynamicExecuteRequest):
    """Execute workflow using pre-processed cache entry and hot session linking"""
    try:
        # Try to link to a pre-processed entry
        hot_session_id = await dynamic_mcp_service.link_to_frontend_request(
            request.session_id,
            request.frontend_request_data
        )

        if hot_session_id:
            # Use the linked hot session for execution
            hot_session = await hot_session_pool.acquire_session(hot_session_id)

            result = await execute_with_hot_session(
                requirement=hot_session.last_requirement,
                hot_session=hot_session
            )

            # Update cache entry status
            if request.session_id in dynamic_mcp_service.cache_entries:
                dynamic_mcp_service.cache_entries[request.session_id].status = 'processed'

            return result

        else:
            # Fallback to regular hot session execution
            hot_session = await hot_session_pool.acquire_session(request.session_id)

            # Load MCP context if available
            requirement = hot_session.last_requirement or "No requirement found in pre-processed cache"

            result = await execute_with_hot_session(
                requirement=requirement,
                hot_session=hot_session
            )

            return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dynamic execution failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(
        "enhanced_mcp_workflow_api:app",
        host="0.0.0.0",
        port=4001,
        log_level="info",
        reload=False
    )