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
    logger.info("Claude Agent SDK loaded successfully")
except ImportError:
    HAS_CLAUDE_SDK = False
    logger.warning("Claude Agent SDK not available - AI responses will be simulated")

# ============================================================================
# AI Agent Personas (Same as frontend)
# ============================================================================

AI_AGENT_PERSONAS = {
    'stephen': {
        'id': 'stephen',
        'name': 'Stephen',
        'role': 'Requirements Analyst',
        'avatar': '📋',
        'color': '#3b82f6',
        'status': 'active',
        'specialization': ['requirements-gathering', 'user-stories', 'acceptance-criteria', 'stakeholder-management'],
        'personality': 'analytical, detail-oriented, methodical, clarifying',
        'response_time': 2.0,
        'system_prompt': """You are Stephen, a Requirements Analyst AI agent in a collaborative team setting.

Your role is to:
- Gather clear, comprehensive requirements through targeted questions
- Create well-defined user stories with acceptance criteria
- Identify edge cases and potential issues early
- Ensure stakeholder needs are properly understood and documented

When responding:
- Ask 1-2 clarifying questions to better understand requirements
- Be concise (2-3 sentences unless detailed analysis is needed)
- Reference specific details from the conversation
- Respond naturally as a team member would

You are part of a multi-agent team. Stay focused on your requirements analysis expertise."""
    },
    'andy': {
        'id': 'andy',
        'name': 'Andy',
        'role': 'Solution Architect',
        'avatar': '🏗️',
        'color': '#8b5cf6',
        'status': 'active',
        'specialization': ['system-design', 'architecture', 'scalability', 'technology-stack', 'api-design'],
        'personality': 'strategic, technical, forward-thinking, pragmatic',
        'response_time': 2.5,
        'system_prompt': """You are Andy, a Solution Architect AI agent in a collaborative team setting.

Your role is to:
- Design scalable, maintainable system architectures
- Recommend appropriate technology stacks and patterns
- Consider non-functional requirements (performance, security, scalability)
- Identify architectural risks and propose mitigations

When responding:
- Provide architectural insights and recommendations
- Be concise (2-3 sentences unless deep technical discussion is needed)
- Reference modern best practices and patterns
- Respond naturally as a senior architect would

You are part of a multi-agent team. Stay focused on your architectural expertise."""
    },
    'sarah': {
        'id': 'sarah',
        'name': 'Sarah',
        'role': 'UX Designer',
        'avatar': '🎨',
        'color': '#ec4899',
        'status': 'active',
        'specialization': ['ux-design', 'user-research', 'wireframing', 'prototyping', 'accessibility'],
        'personality': 'creative, user-focused, empathetic, detail-oriented',
        'response_time': 2.0,
        'system_prompt': """You are Sarah, a UX Designer AI agent in a collaborative team setting.

Your role is to:
- Design intuitive, user-friendly interfaces
- Consider user experience and accessibility
- Create design systems and visual hierarchies
- Advocate for end-user needs

When responding:
- Provide UX insights and design recommendations
- Be concise (2-3 sentences unless detailed design discussion is needed)
- Reference user-centered design principles
- Respond naturally as a designer would

You are part of a multi-agent team. Stay focused on your UX design expertise."""
    },
    'marcus': {
        'id': 'marcus',
        'name': 'Marcus',
        'role': 'Backend Developer',
        'avatar': '⚙️',
        'color': '#f97316',
        'status': 'active',
        'specialization': ['backend-development', 'api-development', 'database-design', 'server-architecture'],
        'personality': 'pragmatic, detail-oriented, performance-focused, thorough',
        'response_time': 2.0,
        'system_prompt': """You are Marcus, a Backend Developer AI agent in a collaborative team setting.

Your role is to:
- Design and implement robust backend services
- Create efficient API endpoints and data models
- Optimize database queries and server performance
- Ensure security and data integrity

When responding:
- Provide backend implementation insights
- Be concise (2-3 sentences unless technical details are needed)
- Reference best practices for APIs, databases, and server architecture
- Respond naturally as a backend developer would

You are part of a multi-agent team. Stay focused on your backend development expertise."""
    },
    'emma': {
        'id': 'emma',
        'name': 'Emma',
        'role': 'Frontend Developer',
        'avatar': '💻',
        'color': '#10b981',
        'status': 'active',
        'specialization': ['frontend-development', 'react', 'typescript', 'responsive-design', 'component-architecture'],
        'personality': 'creative, practical, modern, quality-focused',
        'response_time': 2.0,
        'system_prompt': """You are Emma, a Frontend Developer AI agent in a collaborative team setting.

Your role is to:
- Implement modern, responsive user interfaces
- Build reusable component architectures
- Ensure cross-browser compatibility and accessibility
- Optimize frontend performance

When responding:
- Provide frontend implementation insights
- Be concise (2-3 sentences unless technical details are needed)
- Reference modern frontend best practices (React, TypeScript, etc.)
- Respond naturally as a frontend developer would

You are part of a multi-agent team. Stay focused on your frontend development expertise."""
    },
    'maestro': {
        'id': 'maestro',
        'name': 'Maestro',
        'role': 'Code Synthesis Agent',
        'avatar': '🤖',
        'color': '#6366f1',
        'status': 'active',
        'specialization': ['code-generation', 'full-stack-development', 'synthesis', 'implementation'],
        'personality': 'comprehensive, synthesizing, action-oriented, intelligent',
        'response_time': 5.0,
        'system_prompt': """You are Maestro, the Code Synthesis AI agent - the executor of the team.

Your role is UNIQUE and CRITICAL:
- Analyze the ENTIRE team conversation to extract all requirements
- Synthesize inputs from ALL agents (Stephen's requirements, Andy's architecture, Sarah's UX, Marcus's backend, Emma's frontend)
- Generate COMPLETE, PRODUCTION-READY code that incorporates everyone's expertise
- Create fully functional deliverables (HTML/CSS/JS applications)

When generating code:
- Review the full conversation history carefully
- Incorporate requirements from Stephen
- Follow architectural patterns from Andy
- Implement UX design from Sarah
- Create backend logic as Marcus suggested
- Build frontend components as Emma recommended
- Generate a COMPLETE, SELF-CONTAINED HTML file with inline CSS and JavaScript
- Use modern best practices (Semantic HTML5, Flexbox/Grid, Vanilla JS)

Your output should be:
1. A brief synthesis note (1-2 sentences) explaining what you built
2. The complete, runnable code using the Write tool

You are the synthesis engine that brings the team's discussion to life."""
    }
}


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
        # Build conversation context (last 10 messages)
        context_messages = []
        for msg in conversation[-10:]:
            role = "user" if msg['sender']['type'] == 'human' else msg['sender']['name']
            context_messages.append(f"{role}: {msg['content']}")

        context = "\n".join(context_messages) if context_messages else ""

        # System prompt from persona
        system_prompt = agent['system_prompt']

        # Create prompt for Claude
        prompt = f"""Conversation history:
{context}

Latest message: {user_message}
{'(You were mentioned with @' + agent['name'] + ')' if mentioned_in_message else ''}

Respond naturally as {agent['name']}, the {agent['role']}. Keep your response concise (2-3 sentences unless detailed analysis is needed). Reference the conversation and provide value based on your expertise."""

        # Configure Claude Agent SDK options (same pattern as main BFF)
        options = ClaudeAgentOptions(
            cwd="/tmp",
            permission_mode="bypassPermissions",
            system_prompt=system_prompt,
            continue_conversation=False,
            disallowed_tools=["Write", "Edit", "Bash"]  # Conversational only
        )

        # Call Claude Agent SDK
        response_parts = []
        async for message in query(prompt=prompt, options=options):
            if hasattr(message, 'text') and message.text:
                response_parts.append(message.text)
            elif hasattr(message, 'content'):
                content = message.content
                if isinstance(content, str):
                    response_parts.append(content)
                elif isinstance(content, list):
                    for item in content:
                        if hasattr(item, 'text'):
                            response_parts.append(item.text)

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
    """Generate simulated response when Claude SDK is not available"""
    msg_lower = user_message.lower()
    agent_id = agent['id']

    responses = {
        'stephen': [
            "Let me clarify the requirements. What's the primary user persona for this feature? What are the key success criteria?",
            "Good point! Can you provide more details about the expected user workflow? Are there any edge cases we should consider?",
            "I want to ensure we capture all requirements. What should happen if the user encounters an error in this flow?"
        ],
        'andy': [
            "From an architectural perspective, I'd recommend a modular approach. Should we use microservices or a monolithic architecture for this?",
            "We should consider scalability. How many concurrent users are we expecting? I'll design the system to handle that load.",
            "I suggest we implement this using a RESTful API pattern with proper authentication. What's your preferred tech stack?"
        ],
        'sarah': [
            "From a UX standpoint, we should keep the interface intuitive. Have you considered the user's mental model for this interaction?",
            "I recommend a clean, minimal design with clear visual hierarchy. What's the primary action you want users to take?",
            "Accessibility is important here. Let's ensure we have proper color contrast and keyboard navigation."
        ],
        'marcus': [
            "For the backend, I'll set up efficient API endpoints and database schemas. Are we using SQL or NoSQL for this data?",
            "I can implement that with proper error handling and validation. What's the expected data volume and query patterns?",
            "Let's optimize for performance. I'll add caching and indexing where needed."
        ],
        'emma': [
            "I'll build that with modern React components and TypeScript for type safety. Should it be responsive across all devices?",
            "For the frontend implementation, I recommend using React hooks and context for state management. Any specific styling preferences?",
            "I can create reusable components for this. Let's ensure it's accessible and performs well."
        ],
        'maestro': [
            "I'm analyzing all the team's input to create a complete solution. Generating the code now...",
            "Synthesizing requirements from the team. I'll create a fully functional implementation.",
            "Based on the team discussion, I'll build a complete, production-ready solution."
        ]
    }

    # Return a random response from the agent's pool
    import random
    agent_responses = responses.get(agent_id, ["I'm here to help with your project!"])
    return random.choice(agent_responses)


async def generate_maestro_preview(
    room_id: str,
    conversation: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Generate preview using @Maestro synthesis with claude-agent-sdk"""
    agent = AI_AGENT_PERSONAS['maestro']

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
        # Build comprehensive context from entire conversation
        context_messages = []
        for msg in conversation:
            role = "user" if msg['sender']['type'] == 'human' else msg['sender']['name']
            context_messages.append(f"{role}: {msg['content']}")

        context = "\n".join(context_messages)

        # Maestro's synthesis prompt
        system_prompt = AI_AGENT_PERSONAS['maestro']['system_prompt']

        prompt = f"""Review this team conversation and synthesize a complete solution:

{context}

Create a COMPLETE, SELF-CONTAINED HTML file that implements everything discussed by the team. Include:
- All requirements mentioned by users and Stephen
- Architectural patterns suggested by Andy
- UX design principles from Sarah
- Backend logic (simulated in frontend) as Marcus described
- Modern frontend implementation as Emma would build it

Generate a fully functional, production-ready HTML file with inline CSS and JavaScript."""

        # Create work directory for Maestro
        work_dir = f"/tmp/maestro_collaboration/{room_id}"
        import os
        os.makedirs(work_dir, exist_ok=True)

        # Configure Claude Agent SDK options for Maestro (same pattern as main BFF)
        options = ClaudeAgentOptions(
            cwd=work_dir,
            permission_mode="bypassPermissions",
            system_prompt=system_prompt,
            continue_conversation=False,
            allowed_tools=["write", "read", "edit"]
        )

        # Call Claude Agent SDK with tools enabled for code generation
        response_parts = []
        async for message in query(prompt=prompt, options=options):
            if hasattr(message, 'text') and message.text:
                response_parts.append(message.text)
            elif hasattr(message, 'content'):
                content = message.content
                if isinstance(content, str):
                    response_parts.append(content)
                elif isinstance(content, list):
                    for item in content:
                        if hasattr(item, 'text'):
                            response_parts.append(item.text)

        # Check for generated index.html
        import pathlib
        index_file = pathlib.Path(work_dir) / "index.html"
        html_content = None

        if index_file.exists():
            with open(index_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
        else:
            # If no file was created, use simulated preview
            html_content = generate_simulated_html_preview(conversation)

        synthesis_notes = "\n".join(response_parts).strip() or "Preview generated from team discussion"

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

def should_agent_respond(agent_id: str, message: str, mentions: List[str]) -> bool:
    """Determine if an agent should respond to a message"""
    # Always respond if mentioned
    if agent_id in mentions:
        return True

    # Maestro only responds when mentioned
    if agent_id == 'maestro':
        return False

    # Other agents respond based on keyword relevance (10% chance for natural conversation flow)
    import random
    if random.random() < 0.10:  # 10% chance of spontaneous contribution
        agent = AI_AGENT_PERSONAS.get(agent_id)
        if agent:
            msg_lower = message.lower()
            # Check if message is relevant to agent's specialization
            for keyword in agent['specialization']:
                if keyword.replace('-', ' ') in msg_lower:
                    return True

    return False


# ============================================================================
# FastAPI Application
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    logger.info("=" * 60)
    logger.info(f"🚀 Multi-Agent Collaboration BFF Service Starting")
    logger.info(f"   WebSocket: ws://localhost:4002/ws/collaboration/{{room_id}}")
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


@app.websocket("/ws/collaboration/{room_id}")
async def collaboration_websocket(websocket: WebSocket, room_id: str):
    """WebSocket endpoint for multi-agent collaboration"""
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

            if message_type == 'user_message':
                await handle_user_message(room_id, room, data, websocket)

            elif message_type == 'generate_preview':
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
                    # For human participants (simulated)
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

    # Route to AI agents based on mentions and relevance
    responding_agents = []

    # Always route to mentioned agents
    for agent_id in mentions:
        if agent_id in AI_AGENT_PERSONAS and agent_id != 'maestro':
            responding_agents.append(agent_id)

    # Check if other agents should respond based on relevance
    for agent_id in AI_AGENT_PERSONAS:
        if agent_id not in responding_agents and agent_id != 'maestro':
            if should_agent_respond(agent_id, content, mentions):
                responding_agents.append(agent_id)

    # Generate responses from agents in parallel
    if responding_agents:
        tasks = []
        for agent_id in responding_agents:
            tasks.append(generate_and_broadcast_agent_response(
                room_id, room, agent_id, content, agent_id in mentions
            ))
        await asyncio.gather(*tasks)


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
