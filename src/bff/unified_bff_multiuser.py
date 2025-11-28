#!/usr/bin/env python3
"""
Unified BFF Service for MAESTRO Accelerator
Single service for Chat + Preview with Redis state and WebSocket sync
Based on simple_workflow_api.py with Phase 1 enhancements
"""

import asyncio
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Claude Agent SDK (v3.0 - Security Update)
from claude_agent_sdk import ClaudeAgentOptions, query

# Import Shared Libraries
from maestro_core_logging import configure_logging, get_logger
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

# Import configuration
from config import get_settings

# Import Phase 1 infrastructure (absolute imports for standalone execution)
from redis_state_manager import get_redis_state_manager
from websocket_manager import get_websocket_manager

# Get settings
settings = get_settings()

# Initialize structured logging
configure_logging(
    service_name="unified-bff", environment=settings.environment, log_level=settings.log_level
)
logger = get_logger(__name__)

# Initialize Prometheus metrics
REQUEST_COUNT = Counter("unified_bff_requests_total", "Total requests", ["endpoint"])
CHAT_DURATION = Histogram("unified_bff_chat_duration_seconds", "Chat request duration")
WORKFLOW_DURATION = Histogram(
    "unified_bff_workflow_duration_seconds", "Workflow execution duration"
)
AI_CHATS_TOTAL = Counter("unified_bff_ai_chats_total", "Total AI chat requests")
WORKFLOWS_TOTAL = Counter("unified_bff_workflows_total", "Total workflow executions", ["status"])
WEBSOCKET_CONNECTIONS = Gauge("unified_bff_websocket_connections", "Active WebSocket connections")
REDIS_OPERATIONS = Counter(
    "unified_bff_redis_operations_total", "Redis operations", ["operation", "status"]
)


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


# Global instances
redis_state = get_redis_state_manager()
ws_manager = get_websocket_manager()

# Thread pool for CPU-intensive Claude Code execution
executor = ThreadPoolExecutor(max_workers=4)


# ============================================================================
# Multi-User Collaboration Layer
# ============================================================================

from dataclasses import dataclass, field
from typing import Set
import re


@dataclass
class RoomParticipant:
    """Represents a participant in a collaboration room"""
    id: str
    name: str
    type: str  # 'human' or 'ai'
    websocket: Optional[WebSocket] = None


@dataclass
class RoomState:
    """State for a multi-user collaboration room"""
    room_id: str
    participants: List[RoomParticipant] = field(default_factory=list)
    messages: List[Dict] = field(default_factory=list)
    websockets: Set[WebSocket] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)


class RoomManager:
    """Manages multi-user collaboration rooms"""

    def __init__(self):
        self.rooms: Dict[str, RoomState] = {}

    def get_or_create_room(self, room_id: str) -> RoomState:
        """Get existing room or create new one"""
        if room_id not in self.rooms:
            self.rooms[room_id] = RoomState(room_id=room_id)
            logger.info(f"🆕 Room created: {room_id}")
        return self.rooms[room_id]

    async def add_participant(self, room_id: str, participant: RoomParticipant):
        """Add participant to room"""
        room = self.get_or_create_room(room_id)
        room.participants.append(participant)
        if participant.websocket:
            room.websockets.add(participant.websocket)
        logger.info(f"👤 Added {participant.name} to room {room_id}")

    async def remove_participant(self, room_id: str, participant_id: str):
        """Remove participant from room and broadcast to all clients"""
        if room_id in self.rooms:
            room = self.rooms[room_id]

            # Find participant info before removing
            participant = next((p for p in room.participants if p.id == participant_id), None)

            if not participant:
                logger.warning(f"⚠️ Participant {participant_id} not found in room {room_id}")
                return

            # Remove from list
            room.participants = [p for p in room.participants if p.id != participant_id]
            logger.info(f"👋 Removed participant {participant_id} from room {room_id}. Remaining: {len(room.participants)}")

            # Broadcast participant_left event to all remaining clients
            broadcast_msg = {
                "type": "participant_left",
                "roomId": room_id,
                "payload": {
                    "participantId": participant_id,
                    "participantName": participant.name,
                    "participantType": participant.type
                }
            }
            logger.info(f"📢 Broadcasting participant_left for {participant_id} to {len(room.websockets)} websockets")
            await self.broadcast(room_id, broadcast_msg)

    async def broadcast(self, room_id: str, message: Dict):
        """Broadcast message to all participants in room"""
        if room_id not in self.rooms:
            logger.warning(f"⚠️ Room {room_id} not found for broadcast")
            return

        room = self.rooms[room_id]
        disconnected = []
        success_count = 0

        logger.debug(f"📡 Broadcasting {message.get('type')} to {len(room.websockets)} websockets in room {room_id}")

        for ws in room.websockets:
            try:
                await ws.send_json(message)
                success_count += 1
            except Exception as e:
                logger.warning(f"Failed to send to websocket: {e}")
                disconnected.append(ws)

        # Clean up disconnected websockets
        for ws in disconnected:
            room.websockets.discard(ws)

        logger.info(f"✅ Broadcast complete: {success_count} sent, {len(disconnected)} failed for {message.get('type')}")


# Global room manager
room_manager = RoomManager()


def normalize_agent_name(name: str) -> str:
    """
    Normalize agent display name to persona_id format
    Examples:
    - "Requirement Analyst" → "requirement_analyst"
    - "UI/UX Designer" → "ui_ux_designer"
    - "amigo" → "amigo"
    """
    # Convert to lowercase
    normalized = name.lower()
    # Replace slashes and spaces with underscores
    normalized = re.sub(r'[/\s]+', '_', normalized)
    # Remove any characters that aren't alphanumeric or underscore
    normalized = re.sub(r'[^\w]', '', normalized)
    return normalized


def extract_mentions(content: str) -> List[str]:
    """
    Extract @mentions from message content
    Supports multi-word names like "@Requirement Analyst" or "@UI/UX Designer"
    Returns normalized persona_ids

    Strategy: Capture @ followed by capitalized words or lowercase single words
    - "@amigo" → captures "amigo"
    - "@Requirement Analyst" → captures "Requirement Analyst" (stops at lowercase "can")
    - "@UI/UX Designer" → captures "UI/UX Designer"
    """
    # Pattern explanation:
    # @ - literal @
    # ([A-Z][A-Za-z0-9/]*) - Capitalized word (for "Requirement", "UI/UX", etc.)
    # (?:\s+[A-Z][A-Za-z0-9/]*)* - Optional additional capitalized words
    # | - OR
    # ([a-z][a-z0-9]*) - Single lowercase word (for "amigo", "maestro", etc.)
    mentions = re.findall(r'@(?:([A-Z][A-Za-z0-9/]*(?:\s+[A-Z][A-Za-z0-9/]*)*)|([a-z][a-z0-9]*))', content)

    # Normalize each mention to persona_id format
    normalized_mentions = []
    for match_tuple in mentions:
        # match_tuple is (capitalized_match, lowercase_match) - one will be empty
        mention = match_tuple[0] if match_tuple[0] else match_tuple[1]
        if mention:
            # Normalize to persona_id format
            normalized = normalize_agent_name(mention)
            normalized_mentions.append(normalized)

    return normalized_mentions


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    # Startup
    await redis_state.connect()
    logger.info("redis_connected", status="success")

    # Start WebSocket heartbeat monitor
    asyncio.create_task(ws_manager.start_heartbeat_monitor())
    logger.info("websocket_monitor_started")

    logger.info("=" * 60)
    logger.info(
        "unified_bff_service_starting",
        service_name="MAESTRO Unified BFF Service",
        version=settings.version,
        environment=settings.environment,
    )
    logger.info(
        "service_endpoints",
        server=f"http://{settings.bff_host}:{settings.bff_port}",
        docs=f"http://{settings.bff_host}:{settings.bff_port}/docs",
        metrics=f"http://{settings.bff_host}:{settings.bff_port}/metrics",
        websocket=f"ws://{settings.bff_host}:{settings.bff_port}/ws/{{session_id}}",
        engine=settings.engine_url,
    )
    logger.info(
        "service_features",
        claude_agent_sdk="enabled",
        redis_state="connected",
        websocket="ready",
        architecture="Unified BFF (Single connection for Chat + Preview)",
    )
    logger.info("=" * 60)

    yield

    # Shutdown
    await redis_state.disconnect()
    logger.info("unified_bff_shutdown_complete", status="success")


# Initialize FastAPI with lifespan
app = FastAPI(
    title="MAESTRO Unified BFF Service",
    description="Single service for Chat + Preview with Redis state and WebSocket sync",
    version=settings.version,
    lifespan=lifespan,
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "maestro-unified-bff",
        "version": settings.version,
        "environment": settings.environment,
        "timestamp": datetime.now().isoformat(),
        "components": {
            "claude_agent_sdk": True,
            "redis": await redis_state.session_exists("health_check"),  # Redis connectivity
            "websocket_connections": ws_manager.get_connection_count(),
        },
        "architecture": "unified_bff",
        "engine_url": settings.engine_url,
    }


@app.get("/files/tree")
async def get_files_tree(path: Optional[str] = None):
    """
    Get file tree for deployment directory
    Returns hierarchical file structure for file explorer
    """
    import os

    base_path = Path("/home/ec2-user/projects/deployment")
    if path:
        target_path = base_path / path
    else:
        target_path = base_path

    # Ensure path exists
    if not target_path.exists():
        return {"tree": [], "path": str(target_path), "exists": False}

    def build_tree(directory: Path, max_depth: int = 3, current_depth: int = 0):
        """Recursively build file tree"""
        if current_depth >= max_depth:
            return []

        tree = []
        try:
            for item in sorted(directory.iterdir()):
                # Skip hidden files and common ignore patterns
                if item.name.startswith(".") or item.name in [
                    "node_modules",
                    "__pycache__",
                    "venv",
                    ".git",
                ]:
                    continue

                node = {
                    "name": item.name,
                    "path": str(item.relative_to(base_path)),
                    "type": "directory" if item.is_dir() else "file",
                }

                if item.is_dir():
                    node["children"] = build_tree(item, max_depth, current_depth + 1)
                else:
                    node["size"] = item.stat().st_size
                    node["modified"] = datetime.fromtimestamp(item.stat().st_mtime).isoformat()

                tree.append(node)
        except PermissionError:
            pass

        return tree

    return {
        "tree": build_tree(target_path),
        "path": str(target_path.relative_to(base_path)) if path else "/",
        "exists": True,
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

            elif data.get("type") == "trigger_full_workflow":
                # Trigger Guardian Mode - Full SDLC Workflow
                logger.info("guardian_mode_triggered", session_id=session_id)

                # Send acknowledgment
                await ws_manager.send_message(
                    session_id,
                    {
                        "type": "chat_message",
                        "role": "system",
                        "content": "🛡️ GUARDIAN MODE activated! Initiating full SDLC workflow...",
                        "timestamp": datetime.now().isoformat(),
                    },
                )

                # Update workflow state
                await redis_state.update_workflow_state(session_id, "guardian_mode")

                # Start Guardian workflow in background
                asyncio.create_task(execute_guardian_workflow(session_id))

    except (WebSocketDisconnect, RuntimeError) as e:
        # Handle both normal disconnects and runtime errors (closed connections)
        await ws_manager.disconnect(session_id)
        WEBSOCKET_CONNECTIONS.dec()
        logger.info(
            "websocket_client_disconnected",
            session_id=session_id,
            error=str(e) if isinstance(e, RuntimeError) else None,
        )


# ============================================================================
# Multi-User Collaboration WebSocket Endpoint
# ============================================================================


@app.websocket("/ws/collaboration/{room_id}")
async def collaboration_websocket_endpoint(websocket: WebSocket, room_id: str):
    """
    Multi-user collaboration WebSocket endpoint

    Combines:
    - Unified_BFF's powerful capabilities (Claude with full tools)
    - Multi-user collaboration (rooms, participants, @mentions)

    Users in same room see all messages
    Default agent (Amigo) responds automatically
    @mention routes to specialist agents
    """
    # Accept WebSocket connection
    await websocket.accept()

    # Get or create room
    room = room_manager.get_or_create_room(room_id)

    # Generate participant ID (will be set from first message with user info)
    participant_id = f"user_{int(time.time() * 1000)}"
    participant_ws = None

    try:
        # Add websocket to room (participant will be added on first message with user info)
        room.websockets.add(websocket)
        logger.info(f"🔌 WebSocket connected to room {room_id}")

        # Send room state sync (match frontend's expected format)
        await websocket.send_json({
            "type": "room_state",
            "roomId": room_id,
            "payload": {
                "room": {
                    "id": room_id,
                    "participants": [
                        {
                            "id": p.id,
                            "name": p.name,
                            "type": p.type
                        }
                        for p in room.participants
                    ],
                    "messages": room.messages,
                    "currentPreview": None
                }
            }
        })

        # Listen for messages
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "user_message":
                # Extract user info and content
                user_info = data.get("user", {})
                content = data.get("content", "")

                # Add participant if not already added
                if not participant_ws:
                    participant = RoomParticipant(
                        id=user_info.get("id", participant_id),
                        name=user_info.get("name", "User"),
                        type="human",
                        websocket=websocket
                    )
                    await room_manager.add_participant(room_id, participant)
                    participant_ws = participant
                    participant_id = participant.id

                # Create message object
                user_message = {
                    "id": f"msg_{int(time.time() * 1000)}",
                    "type": "user_message",
                    "sender": {
                        "id": participant_id,
                        "name": user_info.get("name", "User"),
                        "type": "human"
                    },
                    "content": content,
                    "timestamp": datetime.now().isoformat()
                }

                # Add to room history
                room.messages.append(user_message)

                # Broadcast user message to all participants
                await room_manager.broadcast(room_id, {
                    "type": "user_message",
                    "roomId": room_id,
                    "payload": user_message
                })

                # Route to AI agents (with @mention detection)
                await handle_collaboration_message(room_id, room, user_message)

            elif data.get("type") == "pong":
                # Handle heartbeat
                pass

            elif data.get("type") == "request_preview":
                # Send current preview if any (for now, previews are room-scoped)
                # Could extend to have room-specific previews
                pass

            elif data.get("type") == "add_participant":
                # Handle adding participant (AI agents) to room
                participant_id = data.get("participantId")
                participant_type = data.get("participantType", "ai")
                participant_data = data.get("participantData", {})

                if participant_id:
                    participant = RoomParticipant(
                        id=participant_id,
                        name=participant_data.get("name", participant_id),
                        type=participant_type,
                        websocket=None  # AI agents don't have their own websocket
                    )
                    await room_manager.add_participant(room_id, participant)
                    logger.info(f"➕ Added {participant_type} participant {participant_id} to room {room_id}")

            elif data.get("type") == "remove_participant":
                # Handle participant removal
                remove_participant_id = data.get("participantId")
                if remove_participant_id:
                    await room_manager.remove_participant(room_id, remove_participant_id)
                    logger.info(f"🗑️ Participant {remove_participant_id} removed from room {room_id} by user request")

    except (WebSocketDisconnect, RuntimeError) as e:
        # Handle disconnection
        room.websockets.discard(websocket)
        if participant_ws:
            await room_manager.remove_participant(room_id, participant_id)
        logger.info(
            f"websocket_disconnected_from_room",
            room_id=room_id,
            participant_id=participant_id,
            error=str(e) if isinstance(e, RuntimeError) else None
        )


# Alias endpoint for gateway path stripping (gateway strips /ws/collaboration prefix)
@app.websocket("/{room_id}")
async def collaboration_websocket_endpoint_alias(websocket: WebSocket, room_id: str):
    """
    Alias endpoint for when gateway strips /ws/collaboration prefix
    Routes to same implementation as main collaboration endpoint
    """
    return await collaboration_websocket_endpoint(websocket, room_id)


async def check_and_send_preview(room_id: str, room: RoomState, agent_name: str, before_files: set):
    """
    Check if HTML files were created and automatically send preview
    Uses before/after snapshot to detect newly created files per session

    Args:
        room_id: The room ID
        room: The room state
        agent_name: Name of the agent that responded
        before_files: Set of HTML files that existed before AI response
    """
    try:
        # Check for HTML files in /tmp directory (including subdirectories)
        import glob
        current_files = set(glob.glob("/tmp/*.html") + glob.glob("/tmp/**/*.html", recursive=True))

        # Find newly created files (files that exist now but didn't exist before)
        new_files = current_files - before_files

        if not new_files:
            logger.debug(f"No new HTML files created for room {room_id}")
            return

        # Use the most recently created file if multiple files were created
        latest_html = max(new_files, key=os.path.getmtime)

        logger.info(f"📁 Detected new HTML file: {latest_html} for room {room_id}")

        with open(latest_html, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Send preview_generated message to all participants
        preview_message = {
            "type": "preview_generated",
            "roomId": room_id,
            "payload": {
                "preview": {
                    "id": f"preview_{int(time.time() * 1000)}",
                    "type": "web",
                    "html_content": html_content,
                    "files": [],
                    "generatedBy": agent_name,
                    "synthesisNotes": "Live view generated by Maestro"
                }
            }
        }

        await room_manager.broadcast(room_id, preview_message)
        logger.info(f"📺 Auto-generated preview from {os.path.basename(latest_html)} for room {room_id}")

    except Exception as e:
        logger.error(f"Error checking/sending preview: {e}")


async def handle_collaboration_message(room_id: str, room: RoomState, user_message: Dict):
    """
    Handle user message in collaboration room
    Routes to default agent (Amigo) or @mentioned specialists
    Uses unified_bff's Claude with full tool access
    """
    content = user_message["content"]

    # Extract @mentions
    mentions = extract_mentions(content)

    if mentions:
        # Route to mentioned agents
        for agent_name in mentions:
            await generate_collaboration_ai_response(room_id, room, agent_name, user_message)
    else:
        # Default: Amigo responds (like unified_bff - no @mention needed)
        await generate_collaboration_ai_response(room_id, room, "amigo", user_message)


async def generate_collaboration_ai_response(
    room_id: str,
    room: RoomState,
    agent_name: str,
    user_message: Dict
):
    """
    Generate AI response in collaboration room
    Uses Claude Agent SDK with full tool access (web browsing, code execution, etc.)
    """
    # Initialize system_prompt with a default value to prevent UnboundLocalError
    system_prompt = f"You are {agent_name.capitalize()}, an AI assistant. Be helpful and conversational."

    try:
        # Load agent persona
        persona_file = Path(f"/home/ec2-user/projects/maestro-engine-new/src/personas/definitions/{agent_name.lower()}.json")

        if not persona_file.exists():
            logger.warning(f"Persona not found: {agent_name}")
            agent_info = {
                "id": agent_name,
                "name": agent_name.capitalize(),
                "role": "AI Assistant"
            }
            # system_prompt already initialized with default value
        else:
            with open(persona_file, "r") as f:
                agent_info = json.load(f)

            # Get system prompt from persona
            system_prompt = agent_info.get("system_prompt") or \
                          agent_info.get("prompts", {}).get("system_prompt") or \
                          f"You are {agent_info.get('name')}, {agent_info.get('role')}. Be helpful and conversational."

        # Build conversation context from room messages
        conversation_history = []
        for msg in room.messages[-10:]:  # Last 10 messages for context
            role = "user" if msg["sender"]["type"] == "human" else "assistant"
            conversation_history.append(f"{role}: {msg['content']}")

        # Create prompt with context
        context = "\n".join(conversation_history) if conversation_history else ""
        prompt = f"""Conversation so far:
{context}

User's latest message: {user_message["content"]}

Respond naturally as {agent_info.get('name')}. Be helpful and conversational."""

        # Capture snapshot of HTML files BEFORE AI response (for auto-preview detection)
        import glob
        files_before = set(glob.glob("/tmp/*.html") + glob.glob("/tmp/**/*.html", recursive=True))

        # Create Claude Agent with FULL tool access (this is what makes unified_bff powerful!)
        options = ClaudeAgentOptions(
            cwd="/tmp",
            permission_mode="bypassPermissions",
            system_prompt=system_prompt,
            continue_conversation=True,
            allowed_tools=["read", "write", "bash", "web_fetch", "grep", "glob", "edit"],
        )

        # Generate response using Claude query() function
        response_parts = []

        async for message in query(prompt=prompt, options=options):
            if hasattr(message, "text") and message.text:
                response_parts.append(message.text)
            elif hasattr(message, "content"):
                content = message.content
                if isinstance(content, str):
                    response_parts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if hasattr(block, "text"):
                            response_parts.append(block.text)

        ai_response_text = "".join(response_parts)

        # Create AI message object with proper fallbacks
        sender_name = agent_info.get("name") or agent_info.get("id", agent_name).capitalize()
        sender_role = agent_info.get("role", "AI Assistant")
        # Ensure role is a string, not an object
        if isinstance(sender_role, dict):
            sender_role = sender_role.get("primary_role", "AI Assistant")

        ai_message = {
            "id": f"msg_{int(time.time() * 1000)}",
            "type": "ai_message",
            "sender": {
                "id": agent_info.get("id", agent_name),
                "name": sender_name,
                "type": "ai",
                "role": str(sender_role)  # Ensure it's a string
            },
            "content": ai_response_text,
            "timestamp": datetime.now().isoformat()
        }

        # Add to room history
        room.messages.append(ai_message)

        # Broadcast AI response to all participants
        await room_manager.broadcast(room_id, {
            "type": "ai_message",
            "roomId": room_id,
            "payload": ai_message
        })

        # Use fallback for agent name display
        agent_display_name = agent_info.get('name') or agent_info.get('id', agent_name).capitalize()
        logger.info(f"🤖 {agent_display_name} responded in room {room_id} ({len(ai_response_text)} chars)")

        # Auto-detect and send preview if HTML files were created (like original unified_bff)
        # Pass the before-snapshot to detect only newly created files
        await check_and_send_preview(room_id, room, agent_name, files_before)

    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        # Send error message to room
        error_message = {
            "id": f"msg_{int(time.time() * 1000)}",
            "type": "ai_message",
            "sender": {
                "id": "system",
                "name": "System",
                "type": "ai"
            },
            "content": f"Sorry, I encountered an error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        await room_manager.broadcast(room_id, {
            "type": "ai_message",
            "roomId": room_id,
            "payload": error_message
        })


async def handle_chat_message_unified(session_id: str, user_message: str):
    """
    Conversational-first handler with parallel building
    Agent has REAL conversation while building happens in background
    """
    # 1. Add user message to conversation (Redis)
    await redis_state.add_message(session_id, "user", user_message)

    # 2. Broadcast user message
    await ws_manager.send_chat_message(session_id, "user", user_message)

    # 3. Get conversation history
    conversation = await redis_state.get_conversation(session_id)

    # 4. Check if there's already a build task running
    active_task = await redis_state.get_active_build_task(session_id)

    if not active_task:
        # FIRST MESSAGE - Spawn builder FIRST, then have conversation in parallel
        task_id = f"build_{session_id}_{int(time.time())}"

        # Start background builder immediately (doesn't wait)
        asyncio.create_task(background_builder(session_id, task_id, conversation))
        await redis_state.set_active_build_task(session_id, task_id)

        # NOW have actual AI conversation (while build runs in background)
        response = await generate_ai_chat_response(user_message, conversation)

        # Send conversational response
        await redis_state.add_message(session_id, "assistant", response)
        await ws_manager.send_chat_message(session_id, "assistant", response)

    else:
        # ADDITIONAL REQUIREMENTS - Queue for existing builder to enhance progressively

        # Have real AI conversation about the enhancement
        response = await generate_ai_chat_response(user_message, conversation, is_enhancement=True)

        # Send response
        await redis_state.add_message(session_id, "assistant", response)
        await ws_manager.send_chat_message(session_id, "assistant", response)

        # Queue new requirement for existing background builder to pick up
        # The builder monitors redis_state.pop_build_requirements() every 2 seconds
        await redis_state.add_build_requirement(session_id, user_message)


async def generate_ai_chat_response(
    user_message: str, conversation: List[Dict[str, Any]], is_enhancement: bool = False
) -> str:
    """
    Generate REAL AI conversational response using Claude
    This runs WHILE the builder is working in the background
    """
    try:
        # Build conversation context
        context_messages = []
        for msg in conversation[-5:]:  # Last 5 messages for context
            context_messages.append(f"{msg['role']}: {msg['content']}")

        context = "\n".join(context_messages) if context_messages else ""

        # System prompt for frontend analyst persona
        if is_enhancement:
            system_prompt = """You are a friendly Frontend Engineer in a rapid prototyping session.
The user is adding requirements to an existing project you're building in the background.

Your role:
- Acknowledge their new requirements naturally
- Ask clarifying questions to better understand their vision
- Suggest improvements or alternatives when relevant
- Keep responses conversational and brief (2-3 sentences)
- Let them know you're incorporating their feedback

You're having a conversation, not just confirming - be helpful and engaging!"""
        else:
            system_prompt = """You are a friendly Frontend Engineer starting a rapid prototyping session.
The user just described what they want to build, and you're already working on it in the background.

Your role:
- Respond naturally to their request
- Ask clarifying questions to improve the result (colors, features, content, etc.)
- Make helpful suggestions based on their requirements
- Keep responses conversational and brief (2-3 sentences)
- Build rapport and be encouraging

You're having a conversation while building - be helpful, curious, and engaging!"""

        # Call Claude for real conversation
        options = ClaudeAgentOptions(
            cwd="/tmp",
            permission_mode="bypassPermissions",
            system_prompt=system_prompt,
            continue_conversation=False,
            allowed_tools=[],  # No tools - just conversation
        )

        prompt = f"""Recent conversation:
{context}

User's latest message: {user_message}

Respond naturally as a frontend engineer. Ask 1-2 clarifying questions to better understand their needs. Keep it brief and conversational."""

        response_parts = []
        async for message in query(prompt=prompt, options=options):
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

        response = "\n".join(response_parts).strip()
        return (
            response
            if response
            else "I'm working on that now! Any specific details you'd like to add?"
        )

    except Exception as e:
        logger.error("ai_chat_error", error=str(e))
        # Fallback to pattern-based response
        return generate_chat_response(user_message, conversation, is_enhancement)


def generate_chat_response(
    user_message: str, conversation: List[Dict[str, Any]], is_enhancement: bool = False
) -> str:
    """
    Generate intelligent conversational response without waiting for build
    Frontend analyst persona: friendly, professional, clarifying
    """
    msg_lower = user_message.lower()

    if is_enhancement:
        # Responses for additional requirements
        if any(word in msg_lower for word in ["dark", "theme", "color"]):
            return "Great idea! I'll add that styling to the page. What specific colors would you like, or should I choose modern defaults?"
        elif any(word in msg_lower for word in ["button", "form", "input"]):
            return "Perfect! I'm adding that component now. Any specific text or labels you'd like on it?"
        elif any(word in msg_lower for word in ["animation", "effect", "transition"]):
            return "Nice! I'll make it more interactive. Should it be subtle or eye-catching?"
        else:
            return (
                "Got it! I'm incorporating that into the design now. Feel free to add more ideas!"
            )

    else:
        # Responses for initial request
        if any(word in msg_lower for word in ["website", "landing", "page"]):
            return "I'll create that website for you! While I build it, what's the main headline or message you want visitors to see? Any color preferences?"
        elif any(word in msg_lower for word in ["app", "calculator", "tool"]):
            return "Starting on that now! Should it have any specific features or styling you'd like? I'll build a clean, modern version as I work."
        elif any(word in msg_lower for word in ["dashboard", "admin", "panel"]):
            return "On it! I'll create a professional dashboard. What data or sections should it show? I'll make it responsive and modern."
        elif any(word in msg_lower for word in ["form", "contact", "signup"]):
            return "Building that form now! What fields do you need? (name, email, etc.) I'll make it clean and user-friendly."
        elif any(word in msg_lower for word in ["blog", "article", "content"]):
            return "Creating that content layout! Should it have a sidebar? Any specific sections? I'll make it readable and elegant."
        elif any(word in msg_lower for word in ["seo", "review", "optimize"]):
            return "I'll analyze and optimize that for you! Do you have a URL or should I fetch the site? I'll check meta tags, semantic HTML, and performance."
        else:
            return "I'm starting on that right now! While I build, feel free to share any specific requirements like colors, features, or layout preferences. I'll keep you updated!"


async def background_builder(
    session_id: str, task_id: str, initial_conversation: List[Dict[str, Any]]
):
    """
    Runs in background, building and updating based on requirements queue
    """
    work_dir = Path(f"/tmp/maestro_projects/accelerator_{session_id}")
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Initial build
        await ws_manager.send_generation_progress(
            session_id, "building", 30, "Creating initial version..."
        )
        await redis_state.update_workflow_state(session_id, "generating")

        # Get initial requirement from conversation
        initial_requirement = initial_conversation[-1]["content"] if initial_conversation else ""

        result = await execute_generation(session_id, initial_requirement, work_dir)

        # Update preview
        if result.get("html_content"):
            preview_data = {
                "type": "web",
                "html_content": result["html_content"],
                "files": result.get("files", []),
            }
            await redis_state.update_preview(session_id, preview_data)
            await ws_manager.send_preview_update(session_id, preview_data)

        # Notify about generated files
        for file_info in result.get("files", []):
            await redis_state.add_generated_file(session_id, file_info)
            await ws_manager.send_file_generated(session_id, file_info)

        # Mark initial build as complete
        await ws_manager.send_generation_progress(
            session_id, "complete", 100, "Initial build complete!"
        )
        await ws_manager.send_workflow_state_change(session_id, "generating", "complete")
        await redis_state.update_workflow_state(session_id, "complete")

        # Monitor for additional requirements with timeout
        idle_cycles = 0
        max_idle_cycles = 30  # 60 seconds of no activity (30 cycles * 2 seconds)

        while True:
            # Check for new requirements every 2 seconds
            await asyncio.sleep(2)

            new_reqs = await redis_state.pop_build_requirements(session_id)
            if new_reqs:
                # Reset idle counter - user is actively adding requirements
                idle_cycles = 0

                # User added more requirements - enhance existing build
                await ws_manager.send_generation_progress(
                    session_id, "enhancing", 50, "Updating with your new requirements..."
                )
                await redis_state.update_workflow_state(session_id, "generating")

                # Get updated conversation
                conversation = await redis_state.get_conversation(session_id)

                # Build enhancement prompt
                enhancement_requirement = (
                    f"Update the existing page with these new requirements: {', '.join(new_reqs)}"
                )

                # Enhance existing work
                result = await execute_generation(
                    session_id, enhancement_requirement, work_dir, existing_files=True
                )

                # Update preview
                if result.get("html_content"):
                    preview_data = {
                        "type": "web",
                        "html_content": result["html_content"],
                        "files": result.get("files", []),
                    }
                    await redis_state.update_preview(session_id, preview_data)
                    await ws_manager.send_preview_update(session_id, preview_data)

                # Notify about updated files
                for file_info in result.get("files", []):
                    await redis_state.add_generated_file(session_id, file_info)
                    await ws_manager.send_file_generated(session_id, file_info)

                # Mark enhancement as complete
                await ws_manager.send_generation_progress(
                    session_id, "complete", 100, "Enhancement complete!"
                )
                await ws_manager.send_workflow_state_change(session_id, "generating", "complete")
                await redis_state.update_workflow_state(session_id, "complete")
            else:
                # No new requirements - increment idle counter
                idle_cycles += 1
                if idle_cycles >= max_idle_cycles:
                    # No activity for 60 seconds - exit monitoring loop
                    logger.info(
                        "background_builder_idle_timeout",
                        session_id=session_id,
                        idle_seconds=idle_cycles * 2,
                    )
                    break

            # Check if task should stop
            should_stop = await redis_state.should_stop_build(session_id, task_id)
            if should_stop:
                break

    except Exception as e:
        logger.error("background_builder_error", session_id=session_id, error=str(e))
        await ws_manager.send_error(session_id, f"Build error: {str(e)}")
        await redis_state.update_workflow_state(session_id, "error")
    finally:
        await redis_state.clear_active_build_task(session_id)
        await ws_manager.send_workflow_state_change(session_id, "generating", "complete")
        await redis_state.update_workflow_state(session_id, "complete")


async def execute_generation_async(
    session_id: str, requirement: str, work_dir: Path, existing_files: bool = False
) -> Dict[str, Any]:
    """
    Async execution of Claude Code SDK
    Runs the actual async generator properly
    """
    try:
        # Define the Core Identity and Environment (Applies to both modes)
        CORE_IDENTITY = f"""You are 'Accelerator', an Elite Frontend Developer AI. Your mission is to rapidly translate user requirements into functional, modern, and responsive web applications (websites, games, UIs, etc.).

**Environment Context:**
- Working Directory (CWD): {work_dir}
- Primary Target File: './index.html' (All operations must be relative to CWD, not /tmp)

**Core Directives:**
1. **Execute, Don't Describe:** Do not explain the code or provide snippets in conversation. Use the appropriate tools (Write, Edit) immediately.
2. **Quality & Standards:** All output must be visually appealing, use modern best practices (Semantic HTML5, Flexbox/Grid for layout, Vanilla JS), and be responsive across devices.
3. **Self-Contained Prototypes:** Prefer inline or internal CSS/JS within './index.html' for rapid delivery, unless complexity demands separate files.
"""

        # Define the mandatory protocol for analyzing referenced websites
        WEBSITE_ANALYSIS_PROTOCOL = """
**MANDATORY PROTOCOL: Design System Extraction**
If the user references a website or domain (e.g., "google.com", "fifth-9.com", "aiinitiative.co.uk", "http://example.com"):

1. **Acknowledge:** Say: "Analyzing [domain] to extract its design system..."
2. **Normalize URL:** Ensure the URL starts with "https://" (e.g., "google.com" → "https://google.com").
3. **Execute WebFetch:** Use the WebFetch tool with the normalized URL and prompt: "Extract the layout, features, color scheme, fonts, typography, spacing, and key functionality"
4. **Analyze & Integrate:** Extract the underlying Design System to inform your build/enhancement:
    - **Visual Identity:** Color palette, typography, spacing, iconography, button/input styles.
    - **Layout & Structure:** Grid system, navigation patterns, responsive behaviors, component organization.
    - **Interactions:** Key functionalities, animations, and JavaScript behaviors.
"""

        # Configure system prompt based on whether we're enhancing existing files
        if existing_files:
            # Enhancement Mode (Iterating on existing work)
            system_prompt = f"""{CORE_IDENTITY}
{WEBSITE_ANALYSIS_PROTOCOL}

---
# Operating Mode: ITERATION (Enhancing Existing Work)

**CRITICAL RULE:** You MUST use the Edit tool for surgical updates. Using Write or replacing the entire file content will result in failure.

**Iteration Workflow:**
1. **Analyze Request:** Determine the desired changes or new features.
2. **Website Analysis (If Applicable):** Execute the 'Design System Extraction Protocol' above.
3. **Read Current State (MANDATORY):** Use the Read tool to examine './index.html'. You must understand the existing code before modifying it.
4. **Execute Changes:** Use the Edit tool exclusively. Apply changes incrementally using precise old_string and new_string parameters. Preserve existing functionality.
5. **Confirm:** Respond: "Update complete. I've integrated [Specific Feature] into the project."
"""
        else:
            # Creation Mode (Rapid Prototyping new projects)
            system_prompt = f"""{CORE_IDENTITY}
{WEBSITE_ANALYSIS_PROTOCOL}

---
# Operating Mode: PROTOTYPING (Rapid Creation)

**CRITICAL RULE:** You MUST use the Write tool to create the initial file. Ensure the output is a complete, runnable application.

**Prototyping Workflow:**
1. **Analyze Request:** Understand the goal (e.g., game, chat UI, website layout).
2. **Website Analysis (If Applicable):** Execute the 'Design System Extraction Protocol' above. Use the extracted system as the foundation for the build.
3. **Execute Build:** IMMEDIATELY use the Write tool to create './index.html'.
4. **Confirm:**
   - If based on a site: "Prototype ready. Inspired by [website], located at './index.html'."
   - If a new idea: "Prototype ready. Your [Project Type] is located at './index.html'."
"""

        # Configure Claude Agent SDK options (v3.0)
        options = ClaudeAgentOptions(
            cwd=str(work_dir),
            permission_mode="bypassPermissions",
            system_prompt=system_prompt,
            continue_conversation=True,
            allowed_tools=[
                "write",
                "read",
                "edit",
                "bash",
                "glob",
                "grep",
                "web_search",
                "web_fetch",
            ],
        )

        # Execute with Claude Code SDK (async generator)
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


async def execute_generation(
    session_id: str, requirement: str, work_dir: Path = None, existing_files: bool = False
) -> Dict[str, Any]:
    """
    Execute generation - now runs async directly
    Background task ensures it doesn't block chat responses
    """
    if work_dir is None:
        work_dir = Path(f"/tmp/maestro_projects/accelerator_{session_id}")
    work_dir.mkdir(parents=True, exist_ok=True)

    # Call async function directly
    result = await execute_generation_async(session_id, requirement, work_dir, existing_files)
    return result


async def execute_guardian_workflow(session_id: str):
    """
    Execute the full SDLC Guardian workflow using real maestro-engine
    Polls MCP cache for real-time progress events
    """
    import httpx

    from .mcp_event_poller import MCPEventPoller

    try:
        # Export full session context (conversation + preview + files)
        session_context = await redis_state.export_session_context(session_id)

        # Get the user's requirement from the session
        conversation = session_context.get("conversation", [])
        if not conversation:
            requirement = "Build a complete web application with best practices"
        else:
            user_messages = [msg for msg in conversation if msg.get("role") == "user"]
            requirement = (
                user_messages[-1].get("content")
                if user_messages
                else "Build a complete web application"
            )

        logger.info(
            f"🛡️ Guardian Mode: Executing maestro-engine workflow for: {requirement[:100]}..."
        )
        logger.info(
            f"📦 Session context: {session_context['metadata']['total_messages']} messages, "
            f"{session_context['metadata']['file_count']} files, "
            f"has_preview={session_context['metadata']['has_preview']}"
        )

        # Create event handler for MCP events
        async def handle_mcp_event(event: Dict[str, Any]):
            """Forward MCP events to frontend via WebSocket"""
            await ws_manager.send_message(session_id, event)

        # Start MCP event poller in background
        poller = MCPEventPoller(session_id=session_id, on_event=handle_mcp_event)
        polling_task = asyncio.create_task(
            poller.start_polling(poll_interval=2.0, max_duration=600)
        )

        # Call maestro-engine API (non-blocking - events will stream via MCP)
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(
                "http://localhost:5000/api/workflow/execute",
                json={
                    "requirement": requirement,
                    "session_id": session_id,
                    "enable_mcp": True,  # Ensure MCP events are enabled
                    "enable_utcp": False,  # Use local execution for now
                    "enable_rag": True,
                    # Pass session context for continuation
                    "mcp_context": {
                        "conversation": conversation,
                        "preview": session_context.get("preview"),
                        "generated_files": session_context.get("generated_files", []),
                        "continuation_mode": len(conversation)
                        > 1,  # True if building on existing work
                    },
                },
            )

            if response.status_code != 200:
                poller.stop_polling()
                raise Exception(
                    f"Maestro-engine API error: {response.status_code} - {response.text}"
                )

            result = response.json()

        logger.info(f"✅ Maestro-engine execution completed: {result.get('session_id')}")

        # Wait a bit for final events to be processed
        await asyncio.sleep(3)
        poller.stop_polling()

        # Wait for polling task to complete
        try:
            await asyncio.wait_for(polling_task, timeout=5)
        except asyncio.TimeoutError:
            pass

        # Get final progress summary
        progress_summary = poller.get_progress_summary()
        logger.info(f"📊 Progress Summary: {progress_summary}")

        # Send workflow complete
        await ws_manager.send_message(
            session_id, {"type": "workflow_complete", "timestamp": datetime.now().isoformat()}
        )

        # Final summary
        if result is None:
            logger.warning("⚠️ Maestro-engine returned None - workflow may have failed")
            await ws_manager.send_message(
                session_id,
                {
                    "type": "chat_message",
                    "role": "system",
                    "content": "⚠️ Guardian workflow encountered an error. Please check the logs for details.",
                    "timestamp": datetime.now().isoformat(),
                },
            )
            await redis_state.update_workflow_state(session_id, "error")
            return

        team_members = result.get("team_members", [])
        execution_time = result.get("total_execution_time", 0)
        files_generated = result.get("files_generated", [])
        quality_score = result.get("quality_validation", {}).get("quality_score", 0.0)

        summary_msg = f"🎉 Guardian Mode completed!\n\n"
        summary_msg += f"📊 **Execution Summary**\n"
        summary_msg += f"  • Total Time: {execution_time:.1f}s\n"
        summary_msg += f"  • Team Size: {len(team_members)} members\n"
        summary_msg += f"  • Files Generated: {len(files_generated)}\n"
        summary_msg += f"  • MCP Events Processed: {progress_summary['total_events']}\n"
        summary_msg += f"  • Quality Score: {quality_score * 100:.1f}%\n"
        summary_msg += f"  • Session ID: {result.get('session_id')}"

        await ws_manager.send_message(
            session_id,
            {
                "type": "chat_message",
                "role": "system",
                "content": summary_msg,
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Update workflow state
        await redis_state.update_workflow_state(session_id, "complete")

    except Exception as e:
        logger.error(f"Guardian workflow error: {e}", exc_info=True)
        await ws_manager.send_message(
            session_id,
            {
                "type": "error",
                "error": f"Guardian workflow failed: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            },
        )
        await redis_state.update_workflow_state(session_id, "error")


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
    logger.info("ai_chat_request", session_id=session_id, prompt_length=len(request.prompt))

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
        # No WebSocket - still use conversational-first approach
        conversation = await redis_state.get_conversation(session_id)
        active_task = await redis_state.get_active_build_task(session_id)

        if not active_task:
            # Spawn builder FIRST (runs in background)
            task_id = f"build_{session_id}_{int(time.time())}"
            asyncio.create_task(background_builder(session_id, task_id, conversation))
            await redis_state.set_active_build_task(session_id, task_id)

            # NOW have REAL AI conversation (while builder runs)
            response = await generate_ai_chat_response(request.prompt, conversation)

            # Save response
            await redis_state.add_message(session_id, "assistant", response)

            duration = time.time() - start_time
            CHAT_DURATION.observe(duration)
            logger.info("ai_chat_conversational_response", session_id=session_id, duration=duration)

            return AIChatResponse(
                response=response,
                session_id=session_id,
                timestamp=datetime.now().isoformat(),
                workflow_state="generating",
                has_preview=False,
            )
        else:
            # Additional requirement - queue and have AI conversation
            await redis_state.add_build_requirement(session_id, request.prompt)

            # REAL AI conversation about enhancement
            response = await generate_ai_chat_response(
                request.prompt, conversation, is_enhancement=True
            )
            await redis_state.add_message(session_id, "assistant", response)

            duration = time.time() - start_time
            CHAT_DURATION.observe(duration)

            return AIChatResponse(
                response=response,
                session_id=session_id,
                timestamp=datetime.now().isoformat(),
                workflow_state="enhancing",
                has_preview=False,
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
    return preview


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
        "project_path": str(settings.get_project_dir(session_id)),
        "timestamp": preview.get("last_updated", datetime.now().isoformat()),
    }


# Mount Prometheus metrics endpoint
app.mount("/metrics", make_asgi_app())


if __name__ == "__main__":
    # Override port to 4003 for multi-user collaboration service
    collaboration_port = 4003

    logger.info(
        "unified_bff_multiuser_starting",
        port=collaboration_port,
        version=settings.version,
        environment=settings.environment,
        mode="multi-user-collaboration",
        features=["claude_with_tools", "room_based", "@mention_routing", "web_browsing", "code_execution"]
    )

    uvicorn.run(
        app,
        host=settings.bff_host,
        port=collaboration_port,  # Port 4003 (replacing V2)
        log_level=settings.log_level.lower(),
        reload=False,  # Disable reload for production use
    )
