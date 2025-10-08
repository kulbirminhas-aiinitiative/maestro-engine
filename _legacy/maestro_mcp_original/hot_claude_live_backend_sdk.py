#!/usr/bin/env python3
"""
Hot Claude Live Backend - Real-time Code Generation & Preview
Using Claude SDK Hot Agents
Port: 9801
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from enum import Enum
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from claude_code_sdk import ClaudeCodeOptions, query
import uvicorn

# Import unified session manager
from unified_session_manager import (
    unified_session_manager,
    SessionType,
    SessionStatus,
    WSState,
    create_user,
    get_user
)

app = FastAPI(title="Hot Claude Live Backend SDK")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
LIVE_PREVIEW_DIR = Path("/tmp/maestro_live_preview")
LIVE_PREVIEW_DIR.mkdir(exist_ok=True)

# Connection locks for thread-safe WebSocket operations
connection_locks: Dict[str, asyncio.Lock] = {}

# Pydantic models for API requests
class SessionCreateRequest(BaseModel):
    user_id: str
    email: str
    session_type: str = "live_preview"

class UserCreateRequest(BaseModel):
    user_id: str
    email: str

async def safe_websocket_send(websocket: WebSocket, session_id: str, message: dict) -> bool:
    """Safely send WebSocket message with connection state checking"""
    session = unified_session_manager.get_session(session_id)
    if not session or session.websocket_state == WSState.CLOSED:
        return False

    # Get connection lock for this session
    if session_id not in connection_locks:
        connection_locks[session_id] = asyncio.Lock()

    async with connection_locks[session_id]:
        try:
            await websocket.send_json(message)
            unified_session_manager.update_session_activity(session_id)
            return True
        except Exception as e:
            print(f"[WEBSOCKET] Failed to send message to {session_id}: {e}")
            unified_session_manager.set_websocket_state(session_id, WSState.CLOSED)
            return False

async def keep_websocket_alive(websocket: WebSocket, session_id: str):
    """Keep WebSocket connection alive with periodic pings"""
    try:
        session = unified_session_manager.get_session(session_id)
        if not session:
            print(f"[KEEPALIVE] Session {session_id} not found")
            return

        while session.status == SessionStatus.ACTIVE and session.websocket_state in [WSState.OPEN, WSState.CONNECTING]:
            await asyncio.sleep(30)  # Ping every 30 seconds

            # Check if session still exists and is active
            session = unified_session_manager.get_session(session_id)
            if not session or session.status != SessionStatus.ACTIVE:
                break

            success = await safe_websocket_send(websocket, session_id, {
                "type": "ping",
                "timestamp": datetime.now().isoformat()
            })

            if not success:
                print(f"[KEEPALIVE] Ping failed for session {session_id}, stopping keep-alive")
                break

    except Exception as e:
        print(f"[KEEPALIVE] Keep-alive task failed for {session_id}: {e}")
    finally:
        unified_session_manager.set_websocket_state(session_id, WSState.CLOSED)

async def cleanup_stale_sessions():
    """Clean up sessions using unified session manager"""
    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes
            unified_session_manager.cleanup_expired_sessions()

            # Clean up orphaned connection locks
            active_session_ids = {s.session_id for s in unified_session_manager.get_active_sessions()}
            orphaned_locks = set(connection_locks.keys()) - active_session_ids

            for session_id in orphaned_locks:
                print(f"[CLEANUP] Removing orphaned connection lock: {session_id}")
                del connection_locks[session_id]

        except Exception as e:
            print(f"[CLEANUP] Session cleanup failed: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying


class LiveCodeGenerator:
    """Hot Claude SDK agent for real-time code generation"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.conversation_history = []
        # Use unified session manager paths
        self.project_dir = Path(unified_session_manager.get_live_preview_path(session_id))
        self.project_dir.mkdir(parents=True, exist_ok=True)

    async def generate_code(self, requirement: str) -> str:
        """Generate code using Claude SDK hot agent with MCP context"""

        # Try to read from MCP shared context first using unified session manager
        import json
        from pathlib import Path
        mcp_context = None
        mcp_cache_file = Path(unified_session_manager.get_mcp_cache_path(self.session_id))

        if mcp_cache_file.exists():
            try:
                with open(mcp_cache_file) as f:
                    mcp_context = json.load(f)
                    print(f"[MCP] Loaded shared context from chat agent")
            except Exception as e:
                print(f"[MCP] Failed to load context: {e}")

        # Check for existing website files
        existing_website = ""
        index_path = self.project_dir / "index.html"

        if index_path.exists():
            try:
                existing_content = index_path.read_text()
                # Get first 500 chars to understand current state
                preview = existing_content[:500] + "..." if len(existing_content) > 500 else existing_content
                existing_website = f"""
EXISTING WEBSITE FOUND:
Current website preview (first 500 chars):
{preview}

IMPORTANT: You have an existing website! This request should IMPROVE/ENHANCE it, not replace it entirely.
Analyze the current content and apply the requested changes while maintaining consistency.
"""
                print(f"[EXISTING] Found existing website: {len(existing_content)} chars")
            except Exception as e:
                print(f"[EXISTING] Failed to read existing website: {e}")

        # Build enhanced prompt with MCP context and website info
        context_info = ""
        website_context = ""

        if mcp_context:
            if mcp_context.get("conversation"):
                context_info = f"""
CONVERSATION CONTEXT (from chat agent):
{chr(10).join([f"{msg['role'].upper()}: {msg['content']}" for msg in mcp_context['conversation']])}
"""

            # Check if chat assistant analyzed a website
            if mcp_context.get("website_info") and mcp_context["website_info"].get("website_mentioned"):
                website = mcp_context["website_info"]["website_mentioned"]
                website_context = f"""
IMPORTANT - WEBSITE ANALYSIS:
The user mentioned website: {website}
The chat assistant may have analyzed it - check conversation context above for industry/design insights.
Use web_search to visit {website} if needed to understand:
- Industry type (retail, food, entertainment, corporate, etc.)
- Current design style and branding
- What needs improvement

CRITICAL: Match your design to the actual industry/business type, not a generic template!
"""

        prompt = f"""You are a fullstack developer creating and improving a SINGLE live web application.

{existing_website}{context_info}{website_context}
USER REQUEST: {requirement}

CRITICAL - SINGLE WEBSITE APPROACH:
- You are working on ONE continuous website project, not creating multiple separate websites
- FIRST: Check if you already have an existing website file from previous interactions
- If existing website exists: IMPROVE and ENHANCE it based on the new requirement
- If no existing website: Create the initial version, then future requests will improve it
- Maintain visual consistency and continuity across all improvements
- Keep the same overall theme/brand while adding new features or content

INSTRUCTIONS:
1. If website URL mentioned → Use web_search to analyze it FIRST (understand industry, style, tech)
2. Check conversation context for chat assistant's website analysis and insights
3. If existing website exists → Load it, understand its current state, then improve it
4. If no existing website → Create initial version matching the business type
5. Generate a COMPLETE, WORKING HTML file with embedded CSS and JavaScript
6. NO external dependencies - everything must be inline
7. Make it visually beautiful with modern design appropriate for the industry
8. Focus on ITERATIVE IMPROVEMENTS rather than complete redesigns
9. Your final output MUST be valid HTML code (you can use markdown code blocks if needed)

APPROACH FOR THIS REQUEST:
- Check existing website state first
- Determine if this is an improvement request or initial creation
- Apply the change/enhancement while maintaining overall website integrity

Generate the enhanced/improved solution now:"""

        # Use Claude SDK with hot agent - allow tools for research/fetching
        options = ClaudeCodeOptions(
            max_turns=3,  # Allow a few turns for research + generation
            # allowed_tools enabled by default - can fetch websites, analyze, etc.
        )

        try:
            # Query returns an async iterator, we need to collect it
            result_parts = []
            async for message in query(prompt=prompt, options=options):
                print(f"[DEBUG] Message type: {type(message).__name__}")
                print(f"[DEBUG] Message attrs: {dir(message)}")

                # Check different message types
                if hasattr(message, 'text') and message.text:
                    print(f"[DEBUG] Got text: {message.text[:100]}")
                    result_parts.append(message.text)
                elif hasattr(message, 'content'):
                    if isinstance(message.content, str):
                        print(f"[DEBUG] Got content string: {message.content[:100]}")
                        result_parts.append(message.content)
                    elif isinstance(message.content, list):
                        for item in message.content:
                            if hasattr(item, 'text'):
                                print(f"[DEBUG] Got list item text: {item.text[:100]}")
                                result_parts.append(item.text)

            code = ''.join(result_parts).strip()
            print(f"[DEBUG] Final code length: {len(code)}")

            # Extract HTML if wrapped in markdown
            if "```html" in code:
                code = code.split("```html")[1].split("```")[0].strip()
            elif "```" in code:
                code = code.split("```")[1].split("```")[0].strip()

            # If no HTML tags, wrap in basic structure
            if not code.startswith("<!DOCTYPE") and not code.startswith("<html"):
                code = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Preview</title>
</head>
<body>
{code}
</body>
</html>"""

            return code

        except Exception as e:
            # Fallback simple HTML
            return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .container {{
            text-align: center;
            padding: 40px;
            background: rgba(0,0,0,0.3);
            border-radius: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{requirement}</h1>
        <p>Working on it... (Error: {str(e)})</p>
    </div>
</body>
</html>"""

    async def save_and_serve(self, code: str) -> str:
        """Save generated code and return file path"""
        index_path = self.project_dir / "index.html"
        index_path.write_text(code)
        
        # Also save to MCP context for Enhanced Ultimate backend coordination
        await self.save_to_mcp_context(code)
        
        return f"/preview/{self.session_id}/index.html"
    
    async def save_to_mcp_context(self, html_code: str):
        """Save live preview results to MCP context for backend coordination"""
        import json
        from datetime import datetime

        mcp_cache_file = Path(unified_session_manager.get_mcp_cache_path(self.session_id))
        mcp_cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Load existing MCP context or create new one
            mcp_context = {}
            if mcp_cache_file.exists():
                with open(mcp_cache_file) as f:
                    mcp_context = json.load(f)
            
            # Add live preview information
            mcp_context["live_preview"] = {
                "generated_html": html_code,
                "session_id": self.session_id,
                "generated_at": datetime.now().isoformat(),
                "preview_url": f"/preview/{self.session_id}/index.html",
                "status": "generated",
                "file_path": str(self.project_dir / "index.html")
            }
            
            # Update timestamp
            mcp_context["updated_at"] = datetime.now().isoformat()
            mcp_context["updated_by"] = "live_preview_generator"
            
            # Save back to MCP cache
            with open(mcp_cache_file, "w") as f:
                json.dump(mcp_context, f, indent=2)
                
            print(f"[MCP] Live preview saved to context for session: {self.session_id}")
                
        except Exception as e:
            print(f"[MCP] Failed to save live preview to context: {e}")


@app.get("/")
async def root():
    stats = unified_session_manager.get_stats()
    return {
        "status": "Hot Claude Live Backend (SDK)",
        "port": 9801,
        "sessions": stats["active_sessions"],
        "total_users": stats["total_users"],
        "connected_websockets": stats["connected_websockets"],
        "using": "Claude SDK Hot Agents + Unified Session Manager"
    }


@app.get("/health")
async def health():
    stats = unified_session_manager.get_stats()
    return {
        "status": "healthy",
        "active_sessions": stats["active_sessions"],
        "websocket_connections": stats["connected_websockets"],
        "total_users": stats["total_users"],
        "websocket_states": stats["websocket_states"]
    }


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    # Validate session exists in unified session manager
    session = unified_session_manager.get_session(session_id)
    if not session:
        await websocket.close(code=1008, reason="Session not found")
        return

    await websocket.accept()
    print(f"[WEBSOCKET] Connected: {session_id} for user: {session.user_id}")

    # Update session manager with WebSocket connection
    unified_session_manager.set_websocket_state(session_id, WSState.OPEN, websocket)

    # Create live code generator
    generator = LiveCodeGenerator(session_id)

    # Start keep-alive task
    keep_alive_task = asyncio.create_task(keep_websocket_alive(websocket, session_id))

    try:
        # Send connection confirmation
        success = await safe_websocket_send(websocket, session_id, {
            "type": "connected",
            "session_id": session_id,
            "user_id": session.user_id,
            "message": "Hot Claude Live Backend (SDK) connected"
        })

        if not success:
            print(f"[WEBSOCKET] Failed to send connection confirmation to {session_id}")
            return

        while True:
            data = await websocket.receive_json()

            if data.get("type") == "generate":
                requirement = data.get("requirement", "")

                # Send enhanced typing indicator with estimated time
                success = await safe_websocket_send(websocket, session_id, {
                    "type": "generating",
                    "message": "Generating code...",
                    "status": "processing",
                    "estimated_time": "30-60 seconds",
                    "stage": "Analyzing existing website and requirements"
                })

                if not success:
                    print(f"[WEBSOCKET] Failed to send generating message to {session_id}")
                    break  # Exit the WebSocket loop

                # Send progress update
                success = await safe_websocket_send(websocket, session_id, {
                    "type": "generating",
                    "message": "Starting code generation...",
                    "stage": "Initializing Claude SDK"
                })

                if not success:
                    print(f"[WEBSOCKET] Failed to send progress update to {session_id}")
                    break

                try:
                    # Generate code
                    print(f"[DEBUG] Generating code for: {requirement}")
                    code = await generator.generate_code(requirement)
                    print(f"[DEBUG] Generated {len(code)} chars of code")

                    # Send completion progress
                    success = await safe_websocket_send(websocket, session_id, {
                        "type": "generating",
                        "message": "Code generated! Preparing preview...",
                        "stage": "Finalizing"
                    })

                    if not success:
                        print(f"[WEBSOCKET] Failed to send completion progress to {session_id}")
                        break

                    # Save and get preview URL
                    preview_url = await generator.save_and_serve(code)
                    print(f"[DEBUG] Saved to: {preview_url}")

                    # Send success with preview URL
                    success = await safe_websocket_send(websocket, session_id, {
                        "type": "generated",
                        "preview_url": preview_url,
                        "code": code[:200] + "..." if len(code) > 200 else code,
                        "message": "Code generated successfully"
                    })

                    if not success:
                        print(f"[WEBSOCKET] Failed to send success message to {session_id}")

                except Exception as e:
                    print(f"[ERROR] Generation failed: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    await safe_websocket_send(websocket, session_id, {
                        "type": "error",
                        "error": str(e)
                    })

    except WebSocketDisconnect:
        print(f"[WEBSOCKET] Client disconnected: {session_id}")
    except Exception as e:
        print(f"[WEBSOCKET] Connection error for {session_id}: {e}")
    finally:
        # Cleanup: Cancel keep-alive task and update session manager
        if keep_alive_task:
            keep_alive_task.cancel()

        unified_session_manager.set_websocket_state(session_id, WSState.CLOSED)

        # Clean up connection lock
        if session_id in connection_locks:
            del connection_locks[session_id]

        print(f"[WEBSOCKET] Cleaned up connection for: {session_id}")


@app.get("/preview/{session_id}/{file_path:path}")
async def serve_preview(session_id: str, file_path: str):
    """Serve generated preview files"""
    # Validate session exists
    session = unified_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    preview_dir = Path(unified_session_manager.get_live_preview_path(session_id))
    file_full_path = preview_dir / file_path

    if file_full_path.exists():
        return FileResponse(file_full_path)
    else:
        return HTMLResponse(
            content="<h1>Preview not ready</h1><p>Waiting for code generation...</p>",
            status_code=200
        )


@app.get("/sessions")
async def list_sessions():
    """List active sessions"""
    active_sessions = unified_session_manager.get_active_sessions()
    return {
        "active_sessions": len(active_sessions),
        "sessions": [
            {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "session_type": session.session_type.value,
                "websocket_state": session.websocket_state.value,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat()
            }
            for session in active_sessions
        ],
        "stats": unified_session_manager.get_stats()
    }


@app.post("/api/users/create")
async def create_user_endpoint(request: UserCreateRequest):
    """Create a new user in the system"""
    try:
        user = unified_session_manager.create_user(request.user_id, request.email)
        return {
            "success": True,
            "user": user.to_dict(),
            "message": f"User {request.user_id} created successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail={
            "error": str(e),
            "user_id": request.user_id
        })


@app.post("/api/sessions/create")
async def create_session_endpoint(request: SessionCreateRequest):
    """Create a new session for a user"""
    try:
        # Ensure user exists first
        user = unified_session_manager.get_user(request.user_id)
        if not user:
            # Auto-create user if not exists
            user = unified_session_manager.create_user(request.user_id, request.email)

        # Map session type string to enum
        session_type_map = {
            "live_preview": SessionType.LIVE_PREVIEW,
            "backend_workflow": SessionType.BACKEND_WORKFLOW,
            "chat": SessionType.CHAT
        }

        session_type_enum = session_type_map.get(request.session_type, SessionType.LIVE_PREVIEW)

        # Create session
        session = unified_session_manager.create_session(
            request.user_id,
            session_type_enum,
            metadata={"created_via": "api"}
        )

        return {
            "success": True,
            "session": session.to_dict(),
            "urls": unified_session_manager.get_session_urls(session.session_id),
            "message": f"Session {session.session_id} created successfully"
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail={
            "error": str(e),
            "user_id": request.user_id
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": f"Failed to create session: {str(e)}",
            "user_id": request.user_id
        })


@app.get("/api/users/{user_id}")
async def get_user_endpoint(user_id: str):
    """Get user information and sessions"""
    user = unified_session_manager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    user_sessions = unified_session_manager.get_user_sessions(user_id)

    return {
        "user": user.to_dict(),
        "sessions": [
            {
                "session_id": session.session_id,
                "session_type": session.session_type.value,
                "status": session.status.value,
                "websocket_state": session.websocket_state.value,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "urls": unified_session_manager.get_session_urls(session.session_id)
            }
            for session in user_sessions
        ],
        "active_session_count": len([s for s in user_sessions if s.status == SessionStatus.ACTIVE])
    }

@app.get("/api/sessions/admin")
async def get_admin_sessions():
    """Get admin sessions - compatibility endpoint for frontend"""
    # Get all sessions for admin user
    admin_sessions = unified_session_manager.get_user_sessions("admin")
    return {
        "success": True,
        "sessions": [
            {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "status": session.status.value,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat()
            }
            for session in admin_sessions
        ],
        "count": len(admin_sessions)
    }

@app.get("/api/users/{user_id}/sessions")
async def get_user_sessions(user_id: str):
    """Get sessions for a specific user"""
    try:
        user_sessions = unified_session_manager.get_user_sessions(user_id)
        return {
            "success": True,
            "sessions": [
                {
                    "session_id": session.session_id,
                    "user_id": session.user_id,
                    "session_type": session.session_type.value,
                    "websocket_state": session.websocket_state.value,
                    "created_at": session.created_at.isoformat(),
                    "last_activity": session.last_activity.isoformat(),
                    "status": session.status.value,
                    "metadata": session.metadata
                }
                for session in user_sessions
            ],
            "count": len(user_sessions)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "sessions": [],
            "count": 0
        }

@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get a specific session by ID"""
    try:
        session = unified_session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "success": True,
            "session": {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "session_type": session.session_type.value,
                "websocket_state": session.websocket_state.value,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "status": session.status.value,
                "metadata": session.metadata
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session by ID"""
    try:
        result = unified_session_manager.cleanup_session(session_id)
        if result:
            return {
                "success": True,
                "message": f"Session {session_id} deleted successfully"
            }
        else:
            raise HTTPException(status_code=404, detail="Session not found or already deleted")
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.on_event("startup")
async def startup_event():
    """Start background tasks when the app starts"""
    # Start both cleanup tasks
    asyncio.create_task(cleanup_stale_sessions())
    await unified_session_manager.start_cleanup_task()

    print("🧹 Session cleanup tasks started")
    print("🔧 Unified Session Manager initialized")

    # Print configuration
    stats = unified_session_manager.get_stats()
    print(f"👥 Users: {stats['total_users']}")
    print(f"📋 Sessions: {stats['total_sessions']}")
    print(f"🔌 Active WebSocket connections: {stats['connected_websockets']}")

if __name__ == "__main__":
    print("🔥 Hot Claude Live Backend (SDK) Starting...")
    print(f"📍 Port: 9801")
    print(f"🔌 WebSocket: ws://localhost:9801/ws/{{session_id}}")
    print(f"👁️  Preview: http://localhost:9801/preview/{{session_id}}/index.html")
    print(f"📁 Live Preview Dir: {LIVE_PREVIEW_DIR}")
    print(f"⚡ Using: Claude SDK Hot Agents")
    print(f"🔧 Features: Progress indicators, Keep-alive, Auto-cleanup")

    uvicorn.run(app, host="0.0.0.0", port=9801, log_level="info")