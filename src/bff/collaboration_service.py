#!/usr/bin/env python3
"""
Multi-Agent Collaboration BFF Service
WebSocket-based service for real-time collaboration with AI agents

Features:
- Real-time multi-agent chat
- AI agent personas with Claude Code SDK
- @mention routing to specific agents
- @Maestro preview generation
- Room-based collaboration
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List, Set
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Try to import shared libraries (graceful fallback if not available)
try:
    from maestro_core_logging import get_logger, configure_logging
    configure_logging(
        service_name="collaboration-bff",
        environment="production",
        log_level="INFO"
    )
    logger = get_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

# Import Claude Agent SDK directly (same as main BFF service)
try:
    from claude_agent_sdk import ClaudeAgentOptions, query
    HAS_CLAUDE_SDK = True
    logger.info("✅ Claude Agent SDK loaded successfully")
except ImportError:
    HAS_CLAUDE_SDK = False
    logger.warning("Claude Agent SDK not available - AI responses will be simulated")

# ============================================================================
# AI Agent Personas (Loaded from real backend persona definitions)
# ============================================================================

# Add current directory to path for persona_loader import
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# Import real personas from persona_loader.py
from persona_loader import AI_AGENT_PERSONAS

logger.info(f"✅ Loaded {len(AI_AGENT_PERSONAS)} real AI agent personas from backend")


# ============================================================================
# In-Memory Room State (Redis would be used in production)
# ============================================================================

class RoomState:
    """Manages state for a collaboration room"""
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.participants: List[Dict[str, Any]] = []
        self.messages: List[Dict[str, Any]] = []
        self.current_preview: Optional[Dict[str, Any]] = None
        self.typing_users: Set[str] = set()
        self.created_at = datetime.now()
        self.last_activity = datetime.now()

    def add_participant(self, participant: Dict[str, Any]):
        """Add participant to room"""
        if not any(p['id'] == participant['id'] for p in self.participants):
            self.participants.append(participant)
            self.last_activity = datetime.now()

    def remove_participant(self, participant_id: str):
        """Remove participant from room"""
        self.participants = [p for p in self.participants if p['id'] != participant_id]
        self.last_activity = datetime.now()

    def add_message(self, message: Dict[str, Any]):
        """Add message to room history"""
        self.messages.append(message)
        self.last_activity = datetime.now()

    def set_typing(self, user_id: str, is_typing: bool):
        """Set typing status for user"""
        if is_typing:
            self.typing_users.add(user_id)
        else:
            self.typing_users.discard(user_id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert room state to dict"""
        return {
            'id': self.room_id,
            'name': f'Collaboration Room {self.room_id[:8]}',
            'participants': self.participants,
            'messages': self.messages,
            'current_preview': self.current_preview
        }


class CollaborationRoomManager:
    """Manages all collaboration rooms"""
    def __init__(self):
        self.rooms: Dict[str, RoomState] = {}
        self.connections: Dict[str, Set[WebSocket]] = {}  # room_id -> set of websockets

    async def get_or_create_room(self, room_id: str) -> RoomState:
        """Get existing room or create new one"""
        if room_id not in self.rooms:
            self.rooms[room_id] = RoomState(room_id)
            self.connections[room_id] = set()
            logger.info(f"Created new room: {room_id}")
        return self.rooms[room_id]

    async def connect_to_room(self, room_id: str, websocket: WebSocket):
        """Connect websocket to room"""
        if room_id not in self.connections:
            self.connections[room_id] = set()
        self.connections[room_id].add(websocket)
        logger.info(f"WebSocket connected to room {room_id}. Total connections: {len(self.connections[room_id])}")

    async def disconnect_from_room(self, room_id: str, websocket: WebSocket):
        """Disconnect websocket from room"""
        if room_id in self.connections:
            self.connections[room_id].discard(websocket)
            logger.info(f"WebSocket disconnected from room {room_id}. Remaining connections: {len(self.connections[room_id])}")

    async def broadcast_to_room(self, room_id: str, message: Dict[str, Any], exclude_ws: Optional[WebSocket] = None):
        """Broadcast message to all connections in room"""
        if room_id not in self.connections:
            return

        dead_connections = set()
        for websocket in self.connections[room_id]:
            if websocket == exclude_ws:
                continue
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to websocket: {e}")
                dead_connections.add(websocket)

        # Clean up dead connections
        for ws in dead_connections:
            self.connections[room_id].discard(ws)


# Global room manager
room_manager = CollaborationRoomManager()

# Global SDK lock to serialize claude_agent_sdk access (prevents concurrent execution issues)
sdk_lock = asyncio.Lock()


# ============================================================================
# AI Agent Response Generation
# ============================================================================

async def generate_ai_response(
    agent_id: str,
    conversation: List[Dict[str, Any]],
    user_message: str,
    mentioned_in_message: bool = False
) -> str:
    """Generate AI response for specific agent using claude-agent-sdk"""
    agent = AI_AGENT_PERSONAS.get(agent_id)
    if not agent:
        return f"Unknown agent: {agent_id}"

    # Simulate thinking time
    await asyncio.sleep(agent['response_time'])

    if not HAS_CLAUDE_SDK:
        # Simulated response if SDK not available
        return generate_simulated_response(agent, user_message, mentioned_in_message)

    try:
        # Build conversation context (MINIMIZED: last 3 messages only to reduce prompt size)
        context_messages = []
        for msg in conversation[-3:]:
            role = "user" if msg['sender']['type'] == 'human' else msg['sender']['name']
            # Truncate long messages to max 200 chars
            content = msg['content'][:200] + ('...' if len(msg['content']) > 200 else '')
            context_messages.append(f"{role}: {content}")

        context = "\n".join(context_messages) if context_messages else ""

        # MINIMIZED system prompt (instead of full persona)
        minimal_system_prompt = f"You are {agent['name']}, a {agent['role']}. Be concise and helpful."

        # Create MINIMIZED prompt for Claude
        prompt = f"""Context (last 3 messages):
{context}

Message: {user_message}
{'(You were @mentioned)' if mentioned_in_message else ''}

Respond briefly (1-2 sentences) as {agent['role']}."""

        # Configure Claude Agent SDK options (matching working main BFF)
        options = ClaudeAgentOptions(
            cwd="/tmp",
            permission_mode="bypassPermissions",
            system_prompt=minimal_system_prompt,
            continue_conversation=False,
            allowed_tools=["write", "read", "bash", "glob", "grep", "webfetch"]
        )

        # Call Claude Agent SDK with serialization lock
        response_parts = []
        async with sdk_lock:
            logger.info(f"🔒 Acquired SDK lock for {agent_id}")
            async for message in query(prompt=prompt, options=options):
                # Check .content FIRST (AssistantMessage uses this)
                if hasattr(message, 'content'):
                    content = message.content
                    if isinstance(content, str):
                        response_parts.append(content)
                    elif isinstance(content, list):
                        for item in content:
                            if hasattr(item, 'text'):
                                response_parts.append(item.text)
                elif hasattr(message, 'text') and message.text:
                    response_parts.append(message.text)
            logger.info(f"🔓 Released SDK lock for {agent_id}")

        response = "\n".join(response_parts).strip()
        response_dict = {'success': bool(response), 'output': response}

        if response_dict.get('success'):
            response = response_dict.get('output', '').strip()
            return response if response else generate_simulated_response(agent, user_message, mentioned_in_message)
        else:
            logger.error(f"Error from Claude SDK for {agent_id}: {response_dict.get('error')}")
            return generate_simulated_response(agent, user_message, mentioned_in_message)

    except Exception as e:
        logger.error(f"Error generating AI response for {agent_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return generate_simulated_response(agent, user_message, mentioned_in_message)


def generate_simulated_response(agent: Dict[str, Any], user_message: str, mentioned: bool) -> str:
    """Generate simulated response when Claude SDK is not available - dynamically based on agent role"""
    import random

    agent_name = agent['name']
    agent_role = agent['role']
    specializations = agent.get('specialization', [])
    spec_text = specializations[0] if specializations else agent_role

    # Generic response templates based on role
    templates = [
        f"As a {agent_role}, I can help with {spec_text}. What specific aspects would you like me to focus on?",
        f"That's an interesting point! From my {agent_role} perspective, I'd recommend considering {spec_text}.",
        f"I can assist with {spec_text}. What are your priorities for this requirement?"
    ]

    # Special handling for Maestro and Amigo
    if agent['id'] == 'maestro':
        templates = [
            "I'm analyzing all the team's input to create a complete solution. Generating the code now...",
            "Synthesizing requirements from the team. I'll create a fully functional implementation.",
            "Based on the team discussion, I'll build a complete, production-ready solution."
        ]
    elif agent['id'] == 'amigo':
        templates = [
            "Hi! I'm here to help you. I'm learning from our interactions to provide better assistance.",
            "I've noticed you're working on this - would you like me to provide personalized recommendations?",
            "As your personal AI assistant, I'm adapting to your preferences. How can I support you best?"
        ]

    return random.choice(templates)


async def generate_maestro_preview(
    room_id: str,
    conversation: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Generate preview using @Maestro synthesis with claude-agent-sdk"""
    agent = AI_AGENT_PERSONAS['maestro']

    logger.info(f"🔍 HAS_CLAUDE_SDK = {HAS_CLAUDE_SDK}")
    logger.info(f"📊 Conversation has {len(conversation)} messages")

    # Simulate Maestro's longer processing time
    await asyncio.sleep(agent['response_time'])

    if not HAS_CLAUDE_SDK:
        # Return simulated preview
        return {
            'id': f'preview_{int(time.time())}',
            'type': 'web',
            'html_content': generate_simulated_html_preview(conversation),
            'generated_by': 'maestro',
            'synthesis_notes': 'Preview generated based on team discussion (simulated mode)'
        }

    try:
        # Build MINIMIZED context from last 5 messages only (not entire conversation)
        context_messages = []
        for msg in conversation[-5:]:
            role = "user" if msg['sender']['type'] == 'human' else msg['sender']['name']
            # Truncate to max 200 chars per message
            content = msg['content'][:200] + ('...' if len(msg['content']) > 200 else '')
            context_messages.append(f"{role}: {content}")

        context = "\n".join(context_messages)

        # MINIMIZED Maestro system prompt
        minimal_system_prompt = "You are Maestro, a code synthesis AI. Create complete HTML files."

        # MINIMIZED Maestro prompt
        prompt = f"""Team discussion (last 5 messages):
{context}

Use Write tool to create './index.html' with complete self-contained HTML (inline CSS/JS).
Be concise."""

        # Create work directory for Maestro
        work_dir = f"/tmp/maestro_collaboration/{room_id}"
        import os
        os.makedirs(work_dir, exist_ok=True)

        # Configure Claude Agent SDK options for Maestro (matching working main BFF)
        options = ClaudeAgentOptions(
            cwd=work_dir,
            permission_mode="bypassPermissions",
            system_prompt=minimal_system_prompt,
            continue_conversation=False,
            allowed_tools=["write", "read", "bash", "glob", "grep", "webfetch"]
        )

        # Call Claude Agent SDK with serialization lock
        response_parts = []
        async with sdk_lock:
            logger.info(f"🔒 Acquired SDK lock for Maestro preview")
            async for message in query(prompt=prompt, options=options):
                # Check .content FIRST (AssistantMessage uses this)
                if hasattr(message, 'content'):
                    content = message.content
                    if isinstance(content, str):
                        response_parts.append(content)
                    elif isinstance(content, list):
                        for item in content:
                            if hasattr(item, 'text'):
                                response_parts.append(item.text)
                elif hasattr(message, 'text') and message.text:
                    response_parts.append(message.text)
            logger.info(f"🔓 Released SDK lock for Maestro preview")

        # Check if index.html was created by Write tool
        import pathlib
        index_file = pathlib.Path(work_dir) / "index.html"
        html_content = None

        if index_file.exists():
            with open(index_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            synthesis_notes = "Preview generated using Claude AI with Write tool"
        else:
            # Fallback: try to extract HTML from response text
            full_response = "\n".join(response_parts).strip()
            if '```html' in full_response:
                html_start = full_response.find('```html') + 7
                html_end = full_response.find('```', html_start)
                if html_end > html_start:
                    html_content = full_response[html_start:html_end].strip()
            elif '<!DOCTYPE' in full_response or '<html' in full_response:
                html_content = full_response

            if not html_content:
                # No HTML found, use simulated preview
                logger.warning(f"No HTML file created and no HTML in response, using simulated preview")
                html_content = generate_simulated_html_preview(conversation)

            synthesis_notes = "Preview generated from team discussion"

        return {
            'id': f'preview_{int(time.time())}',
            'type': 'web',
            'html_content': html_content,
            'generated_by': 'maestro',
            'synthesis_notes': synthesis_notes[:200]  # Truncate for display
        }

    except Exception as e:
        logger.error(f"Error generating Maestro preview: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'id': f'preview_{int(time.time())}',
            'type': 'web',
            'html_content': generate_simulated_html_preview(conversation),
            'generated_by': 'maestro',
            'synthesis_notes': f'Preview generated (error: {str(e)[:100]})'
        }


def generate_simulated_html_preview(conversation: List[Dict[str, Any]]) -> str:
    """Generate simulated HTML preview when Claude SDK is not available"""
    # Extract key points from conversation
    messages = [msg['content'] for msg in conversation[-5:]]
    conversation_summary = " ".join(messages)[:200]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Maestro Preview</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: white;
            padding: 60px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 800px;
            text-align: center;
        }}
        h1 {{
            font-size: 48px;
            color: #333;
            margin-bottom: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        p {{
            font-size: 18px;
            color: #666;
            line-height: 1.6;
            margin-bottom: 30px;
        }}
        .team-badge {{
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background: #f0f4ff;
            padding: 10px 20px;
            border-radius: 50px;
            font-size: 14px;
            color: #667eea;
            font-weight: 600;
            margin-top: 20px;
        }}
        .generated-note {{
            margin-top: 40px;
            padding: 20px;
            background: #f9fafb;
            border-radius: 10px;
            font-size: 14px;
            color: #6b7280;
            border-left: 4px solid #667eea;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Maestro Preview</h1>
        <p>This is a synthesized preview based on the team's collaborative discussion.</p>
        <p><strong>Conversation Context:</strong> {conversation_summary}...</p>
        <div class="team-badge">
            <span>📋 Stephen</span>
            <span>🏗️ Andy</span>
            <span>🎨 Sarah</span>
            <span>⚙️ Marcus</span>
            <span>💻 Emma</span>
            <span>🤖 Maestro</span>
        </div>
        <div class="generated-note">
            <strong>Note:</strong> This is a simulated preview. Connect Claude Code SDK for full AI-powered code generation.
        </div>
    </div>
</body>
</html>"""


# ============================================================================
# Agent Invocation Logic
# ============================================================================

async def should_agent_respond_ai(
    agent_id: str,
    message: str,
    mentions: List[str],
    conversation: List[Dict[str, Any]]
) -> bool:
    """
    Use Claude AI to intelligently decide if agent should respond.
    This is NOT scripted/random - the AI decides based on context and relevance.
    """
    # Always respond if directly mentioned
    if agent_id in mentions:
        return True

    # Maestro only responds when mentioned (specialized code generation agent)
    if agent_id == 'maestro':
        return False

    # For all other agents: Let Claude AI decide based on conversation context
    if not HAS_CLAUDE_SDK:
        # Fallback only if SDK unavailable: basic relevance check
        agent = AI_AGENT_PERSONAS.get(agent_id)
        if agent:
            msg_lower = message.lower()
            for keyword in agent['specialization']:
                if keyword.replace('-', ' ') in msg_lower:
                    return True
        return False

    try:
        agent = AI_AGENT_PERSONAS.get(agent_id)
        if not agent:
            return False

        # Build conversation context
        context_messages = []
        for msg in conversation[-5:]:  # Last 5 messages for context
            role = "user" if msg['sender']['type'] == 'human' else msg['sender']['name']
            context_messages.append(f"{role}: {msg['content']}")
        context = "\n".join(context_messages) if context_messages else ""

        # Ask Claude AI: "Should I respond to this?"
        decision_prompt = f"""You are {agent['name']}, a {agent['role']} in a collaborative team.

Recent conversation:
{context}

Latest message: {message}

Question: Based on your role as {agent['role']} and your expertise in {', '.join(agent['specialization'])}, should you respond to this message?

Respond with ONLY one word:
- "YES" if this message is relevant to your expertise and you can add value
- "NO" if this message is not relevant to your role or others can handle it better

Do not explain. Just answer YES or NO."""

        # Use Claude SDK for intelligent decision
        # NO LOCK for decisions - these are fast and work fine concurrently
        options = ClaudeAgentOptions(
            cwd="/tmp",
            permission_mode="bypassPermissions",
            system_prompt=f"You are {agent['name']}, deciding if you should contribute based on your {agent['role']} expertise.",
            continue_conversation=False,
            allowed_tools=["write", "read", "bash", "glob", "grep", "webfetch"]
        )

        response_parts = []
        async for msg in query(prompt=decision_prompt, options=options):
            # Check .content FIRST (AssistantMessage uses this)
            if hasattr(msg, 'content'):
                content = msg.content
                if isinstance(content, str):
                    response_parts.append(content)
                elif isinstance(content, list):
                    for item in content:
                        if hasattr(item, 'text'):
                            response_parts.append(item.text)
            elif hasattr(msg, 'text') and msg.text:
                response_parts.append(msg.text)

        decision = "\n".join(response_parts).strip().upper()

        # Log the AI's decision
        logger.info(f"{agent['name']} AI decision for message '{message[:50]}...': {decision}")

        return "YES" in decision

    except Exception as e:
        logger.error(f"Error in AI decision for {agent_id}: {e}")
        # Fallback: don't respond if AI decision fails
        return False


# ============================================================================
# FastAPI Application
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    logger.info("=" * 60)
    logger.info(f"🚀 Multi-Agent Collaboration BFF Service Starting")
    logger.info(f"   WebSocket: ws://localhost:4002/ws/{{room_id}} (via gateway: /ws/collaboration/*)")
    logger.info(f"   Humans API: http://localhost:4002/humans (via gateway: /api/collaboration/humans)")
    logger.info(f"   Health: http://localhost:4002/health")
    logger.info(f"   Claude SDK: {'✅ Enabled' if HAS_CLAUDE_SDK else '⚠️  Simulated Mode'}")
    logger.info("=" * 60)
    yield
    logger.info("🛑 Multi-Agent Collaboration BFF Service Shutting Down")


app = FastAPI(
    title="Multi-Agent Collaboration BFF Service",
    description="Real-time collaboration with AI agents",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "collaboration-bff",
        "timestamp": datetime.now().isoformat(),
        "claude_sdk": HAS_CLAUDE_SDK,
        "active_rooms": len(room_manager.rooms)
    }


@app.get("/api/personas")
async def get_personas():
    """Get all available AI agent personas from backend definitions"""
    return {
        "personas": [
            {
                "id": p["id"],
                "name": p["name"],
                "role": p["role"],
                "avatar": p["avatar"],
                "color": p["color"],
                "description": p.get("description", ""),
                "specialization": p.get("specialization", []),
                "status": p.get("status", "active")
            }
            for p in AI_AGENT_PERSONAS.values()
        ]
    }


@app.get("/humans")
async def get_humans():
    """Get all available human team members (simulated for now)"""
    # TODO: In production, fetch from backend /api/v1/auth/users endpoint with auth
    # For now, return simulated team members for collaboration testing
    return {
        "humans": [
            {
                "id": "kulbir-minhas",
                "name": "Kulbir Minhas",
                "email": "kulbir@maestro.com",
                "role": "Product Manager",
                "avatar": "KM",
                "status": "online",
                "department": "Product",
                "expertise": ["Product Strategy", "User Research", "Roadmap Planning"]
            },
            {
                "id": "sarah-chen",
                "name": "Sarah Chen",
                "email": "sarah.chen@maestro.com",
                "role": "Senior Engineer",
                "avatar": "SC",
                "status": "online",
                "department": "Engineering",
                "expertise": ["Backend Development", "System Design", "API Design"]
            },
            {
                "id": "james-williams",
                "name": "James Williams",
                "email": "james.w@maestro.com",
                "role": "UX Designer",
                "avatar": "JW",
                "status": "away",
                "department": "Design",
                "expertise": ["UI/UX Design", "User Research", "Prototyping"]
            }
        ]
    }


@app.websocket("/ws/{room_id}")
async def collaboration_websocket(websocket: WebSocket, room_id: str):
    """WebSocket endpoint for multi-agent collaboration (via gateway: /ws/collaboration/*)"""
    await websocket.accept()
    room = await room_manager.get_or_create_room(room_id)
    await room_manager.connect_to_room(room_id, websocket)

    try:
        # Send initial room state
        await websocket.send_json({
            'type': 'room_state',
            'roomId': room_id,
            'payload': {
                'room': room.to_dict()
            },
            'timestamp': datetime.now().isoformat()
        })

        # Listen for messages
        while True:
            data = await websocket.receive_json()
            message_type = data.get('type')

            logger.info(f"📩 Received WS message type: {message_type}")

            if message_type == 'user_message':
                await handle_user_message(room_id, room, data, websocket)

            elif message_type == 'generate_preview':
                logger.info(f"🎨 Generating Maestro preview for room {room_id}")
                await handle_preview_generation(room_id, room, websocket)

            elif message_type == 'typing_start':
                room.set_typing(data.get('userId'), True)
                await room_manager.broadcast_to_room(room_id, {
                    'type': 'user_typing',
                    'roomId': room_id,
                    'payload': {
                        'userId': data.get('userId'),
                        'userName': data.get('userName')
                    },
                    'timestamp': datetime.now().isoformat()
                }, exclude_ws=websocket)

            elif message_type == 'typing_stop':
                room.set_typing(data.get('userId'), False)
                await room_manager.broadcast_to_room(room_id, {
                    'type': 'user_stopped_typing',
                    'roomId': room_id,
                    'payload': {
                        'userId': data.get('userId')
                    },
                    'timestamp': datetime.now().isoformat()
                }, exclude_ws=websocket)

            elif message_type == 'add_participant':
                # Add participant to room
                participant_id = data.get('participantId')
                participant_type = data.get('participantType')

                if participant_type == 'ai' and participant_id in AI_AGENT_PERSONAS:
                    agent = AI_AGENT_PERSONAS[participant_id]
                    participant = {
                        'id': agent['id'],
                        'name': agent['name'],
                        'type': 'ai',
                        'role': agent['role'],
                        'avatar': agent['avatar'],
                        'color': agent['color'],
                        'status': agent['status']
                    }
                    room.add_participant(participant)

                    # Broadcast participant joined
                    await room_manager.broadcast_to_room(room_id, {
                        'type': 'participant_joined',
                        'roomId': room_id,
                        'payload': {
                            'participant': participant
                        },
                        'timestamp': datetime.now().isoformat()
                    })

                elif participant_type == 'human':
                    # Look up human participant data from /humans endpoint
                    humans_response = await get_humans()
                    human_data = next((h for h in humans_response['humans'] if h['id'] == participant_id), None)

                    if human_data:
                        participant = {
                            'id': human_data['id'],
                            'name': human_data['name'],
                            'type': 'human',
                            'role': human_data.get('role', 'Team Member'),
                            'avatar': human_data.get('avatar', participant_id[:2].upper()),
                            'status': human_data.get('status', 'online')
                        }
                    else:
                        # Fallback if human not found in /humans endpoint
                        participant = {
                            'id': participant_id,
                            'name': participant_id.replace('-', ' ').title(),
                            'type': 'human',
                            'role': 'Team Member',
                            'avatar': participant_id[:2].upper(),
                            'status': 'online'
                        }
                    room.add_participant(participant)

                    # Broadcast participant joined
                    await room_manager.broadcast_to_room(room_id, {
                        'type': 'participant_joined',
                        'roomId': room_id,
                        'payload': {
                            'participant': participant
                        },
                        'timestamp': datetime.now().isoformat()
                    })

            elif message_type == 'remove_participant':
                # Remove participant from room
                participant_id = data.get('participantId')
                room.remove_participant(participant_id)

                # Broadcast participant left
                await room_manager.broadcast_to_room(room_id, {
                    'type': 'participant_left',
                    'roomId': room_id,
                    'payload': {
                        'participantId': participant_id
                    },
                    'timestamp': datetime.now().isoformat()
                })

    except WebSocketDisconnect:
        await room_manager.disconnect_from_room(room_id, websocket)
        logger.info(f"Client disconnected from room {room_id}")
    except Exception as e:
        logger.error(f"WebSocket error in room {room_id}: {e}")
        await room_manager.disconnect_from_room(room_id, websocket)


async def handle_user_message(room_id: str, room: RoomState, data: Dict[str, Any], websocket: WebSocket):
    """Handle user message and route to AI agents"""
    sender = data.get('sender', {})
    content = data.get('content', '')
    mentions = data.get('mentions', [])

    logger.info(f"📨 Received user message in room {room_id}: '{content[:50]}...' from {sender.get('name', 'Unknown')}")
    logger.info(f"   Mentions: {mentions}")

    # Create message
    message = {
        'id': f'msg_{int(time.time())}_{uuid.uuid4().hex[:8]}',
        'sender': sender,
        'content': content,
        'timestamp': datetime.now().isoformat(),
        'mentions': mentions
    }

    # Add to room history
    room.add_message(message)

    # Broadcast user message to all participants
    await room_manager.broadcast_to_room(room_id, {
        'type': 'user_message',
        'roomId': room_id,
        'payload': message,
        'timestamp': message['timestamp']
    })

    # Route message to ALL AI agents - let each agent's AI decide if they should respond
    # This is TRUE AI collaboration, not scripted/random behavior

    # Get all agents in the room
    agent_ids_in_room = [p['id'] for p in room.participants if p['type'] == 'ai' and p['id'] != 'maestro']

    # If no agents in room yet, check all available agents (for initial messages)
    if not agent_ids_in_room:
        agent_ids_in_room = [aid for aid in AI_AGENT_PERSONAS.keys() if aid != 'maestro']

    logger.info(f"🤖 Checking {len(agent_ids_in_room)} agents for responses: {agent_ids_in_room}")

    # Let each agent's AI decide if they should respond
    decision_tasks = []
    for agent_id in agent_ids_in_room:
        # Skip the sender if they're an agent (agents don't respond to themselves)
        if sender.get('id') == agent_id:
            continue
        decision_tasks.append(check_and_respond_if_relevant(
            room_id, room, agent_id, content, mentions
        ))

    # Execute all AI decisions in parallel (fast)
    if decision_tasks:
        await asyncio.gather(*decision_tasks)


async def check_and_respond_if_relevant(
    room_id: str,
    room: RoomState,
    agent_id: str,
    content: str,
    mentions: List[str]
):
    """
    Let the agent's AI decide if the message is relevant, then respond if yes.
    This is the TRUE AI collaboration approach.
    """
    # Ask the AI if this agent should respond
    should_respond = await should_agent_respond_ai(agent_id, content, mentions, room.messages)

    logger.info(f"   {agent_id}: should_respond = {should_respond}")

    if should_respond:
        # Generate and broadcast response
        await generate_and_broadcast_agent_response(
            room_id, room, agent_id, content, agent_id in mentions
        )


async def generate_and_broadcast_agent_response(
    room_id: str,
    room: RoomState,
    agent_id: str,
    user_message: str,
    mentioned: bool
):
    """Generate AI response and broadcast to room"""
    agent = AI_AGENT_PERSONAS[agent_id]

    # Send typing indicator
    await room_manager.broadcast_to_room(room_id, {
        'type': 'agent_typing',
        'roomId': room_id,
        'payload': {
            'agentId': agent_id,
            'agentName': agent['name'],
            'agentRole': agent['role']
        },
        'timestamp': datetime.now().isoformat()
    })

    # Generate response
    response_content = await generate_ai_response(
        agent_id, room.messages, user_message, mentioned
    )

    # Create AI message
    ai_message = {
        'id': f'msg_{int(time.time())}_{uuid.uuid4().hex[:8]}',
        'sender': {
            'id': agent_id,
            'name': agent['name'],
            'type': 'ai',
            'role': agent['role'],
            'avatar': agent['avatar'],
            'color': agent['color']
        },
        'content': response_content,
        'timestamp': datetime.now().isoformat()
    }

    # Add to room history
    room.add_message(ai_message)

    # Send stopped typing
    await room_manager.broadcast_to_room(room_id, {
        'type': 'agent_stopped_typing',
        'roomId': room_id,
        'payload': {
            'agentId': agent_id
        },
        'timestamp': datetime.now().isoformat()
    })

    # Broadcast AI message
    await room_manager.broadcast_to_room(room_id, {
        'type': 'ai_message',
        'roomId': room_id,
        'payload': ai_message,
        'timestamp': ai_message['timestamp']
    })


async def handle_preview_generation(room_id: str, room: RoomState, websocket: WebSocket):
    """Handle @Maestro preview generation"""
    # Send Maestro typing
    await room_manager.broadcast_to_room(room_id, {
        'type': 'agent_typing',
        'roomId': room_id,
        'payload': {
            'agentId': 'maestro',
            'agentName': 'Maestro',
            'agentRole': 'Code Synthesis Agent'
        },
        'timestamp': datetime.now().isoformat()
    })

    # Generate preview
    preview = await generate_maestro_preview(room_id, room.messages)

    # Update room state
    room.current_preview = preview

    # Send stopped typing
    await room_manager.broadcast_to_room(room_id, {
        'type': 'agent_stopped_typing',
        'roomId': room_id,
        'payload': {
            'agentId': 'maestro'
        },
        'timestamp': datetime.now().isoformat()
    })

    # Broadcast preview
    await room_manager.broadcast_to_room(room_id, {
        'type': 'preview_generated',
        'roomId': room_id,
        'payload': {
            'preview': preview
        },
        'timestamp': datetime.now().isoformat()
    })


if __name__ == "__main__":
    logger.info("Starting Multi-Agent Collaboration BFF Service on port 4002")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=4002,
        log_level="info"
    )
