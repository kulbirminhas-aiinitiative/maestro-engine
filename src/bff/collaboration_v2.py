#!/usr/bin/env python3
"""
Multi-Agent Collaboration BFF Service V2
Clean, tool-based architecture for flexible N-human + M-AI collaboration

Design Principles:
1. Flexible participant model (any combination of humans and AI agents)
2. Tool-based execution (#preview, #workflow) - not delegation
3. Simple message flow: Store → Broadcast → Detect → Execute
4. Full conversation context always available
5. No fake delegation messages
6. Clean separation: Tools vs Chat routing

Architecture:
    User Message → room.messages → Broadcast → Tool Detection
                                                     ↓
                                            [Tool Execute] OR [Agent Route]
                                                     ↓
                                                 Response
"""

import asyncio
import json
import time
import uuid
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List, Set
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# ============================================================================
# Logging Setup
# ============================================================================
try:
    from maestro_core_logging import get_logger, configure_logging
    configure_logging(
        service_name="collaboration-bff-v2",
        environment="production",
        log_level="DEBUG"  # Changed to DEBUG to see chunk details
    )
    logger = get_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.DEBUG)  # Changed to DEBUG
    logger = logging.getLogger(__name__)

# ============================================================================
# AI Provider Setup (Multi-provider support)
# ============================================================================
try:
    import sys
    import os
    from dotenv import load_dotenv

    execution_platform_path = Path("/home/ec2-user/projects/maestro-platform/execution-platform")
    if execution_platform_path.exists():
        sys.path.insert(0, str(execution_platform_path))

        # CRITICAL: Load .env file BEFORE importing config
        # This ensures EP_PROVIDER and API keys are loaded
        env_file = execution_platform_path / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            logger.info(f"✅ Loaded environment from {env_file}")
            logger.info(f"   EP_PROVIDER={os.getenv('EP_PROVIDER', 'not set')}")
            logger.info(f"   EP_OPENAI_API_KEY={'set' if os.getenv('EP_OPENAI_API_KEY') else 'not set'}")
        else:
            logger.warning(f"⚠️ .env file not found at {env_file}")

    from execution_platform.maestro_sdk.router import get_adapter
    from execution_platform.maestro_sdk.types import ChatRequest, Message
    from execution_platform.config import settings

    # Debug: Check what settings actually has
    logger.info(f"🔍 Settings debug:")
    logger.info(f"   settings.provider = {settings.provider}")
    logger.info(f"   settings.openai_api_key = {'SET' if settings.openai_api_key else 'NOT SET'}")
    logger.info(f"   settings.anthropic_api_key = {'SET' if settings.anthropic_api_key else 'NOT SET'}")
    logger.info(f"   settings.gemini_api_key = {'SET' if settings.gemini_api_key else 'NOT SET'}")

    ai_provider = get_adapter("auto")
    HAS_AI_PROVIDER = True
    logger.info(f"✅ AI Provider loaded: {settings.provider}")
    logger.info(f"   Actual adapter: {type(ai_provider).__name__}")
    logger.info(f"   Using model: {getattr(settings, f'{settings.provider}_model', 'unknown')}")
except ImportError as e:
    HAS_AI_PROVIDER = False
    ai_provider = None
    logger.warning(f"⚠️ AI Provider unavailable - simulated mode: {e}")

# ============================================================================
# Persona Loader
# ============================================================================
sys.path.insert(0, str(Path(__file__).parent))
from persona_loader import AI_AGENT_PERSONAS
logger.info(f"✅ Loaded {len(AI_AGENT_PERSONAS)} AI personas")

# ============================================================================
# Room State Model
# ============================================================================

class RoomState:
    """
    Manages state for a collaboration room
    Supports N humans + M AI agents
    """
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.participants = []  # Mix of humans and AI
        self.messages = []  # Full conversation history
        self.created_at = datetime.now().isoformat()

    def add_participant(self, participant: Dict):
        """Add human or AI participant"""
        if not any(p['id'] == participant['id'] for p in self.participants):
            self.participants.append(participant)
            logger.info(f"➕ Participant added to {self.room_id}: {participant['name']} ({participant['type']})")

    def remove_participant(self, participant_id: str):
        """Remove participant"""
        self.participants = [p for p in self.participants if p['id'] != participant_id]
        logger.info(f"➖ Participant removed from {self.room_id}: {participant_id}")

    def add_message(self, message: Dict):
        """Add message to conversation history"""
        self.messages.append(message)

    def get_ai_participants(self) -> List[Dict]:
        """Get all AI agent participants"""
        return [p for p in self.participants if p['type'] == 'ai']

    def get_human_participants(self) -> List[Dict]:
        """Get all human participants"""
        return [p for p in self.participants if p['type'] == 'human']

# ============================================================================
# Room Manager
# ============================================================================

class RoomManager:
    """Manages multiple collaboration rooms and WebSocket connections"""

    def __init__(self):
        self.rooms: Dict[str, RoomState] = {}
        self.connections: Dict[str, Set[WebSocket]] = {}  # room_id → websockets

    def get_or_create_room(self, room_id: str) -> RoomState:
        """Get existing room or create new one"""
        if room_id not in self.rooms:
            self.rooms[room_id] = RoomState(room_id)
            self.connections[room_id] = set()
            logger.info(f"🆕 Room created: {room_id}")
        return self.rooms[room_id]

    async def connect(self, room_id: str, websocket: WebSocket):
        """Connect WebSocket to room"""
        await websocket.accept()
        if room_id not in self.connections:
            self.connections[room_id] = set()
        self.connections[room_id].add(websocket)
        logger.info(f"🔌 WebSocket connected to room {room_id} (total: {len(self.connections[room_id])})")

    async def disconnect(self, room_id: str, websocket: WebSocket):
        """Disconnect WebSocket from room"""
        if room_id in self.connections:
            self.connections[room_id].discard(websocket)
            logger.info(f"🔌 WebSocket disconnected from room {room_id}")

    async def broadcast(self, room_id: str, message: Dict):
        """Broadcast message to all connections in room"""
        if room_id not in self.connections:
            return

        disconnected = set()
        for ws in self.connections[room_id]:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
                disconnected.add(ws)

        # Clean up disconnected websockets
        for ws in disconnected:
            self.connections[room_id].discard(ws)

# Global room manager
room_manager = RoomManager()

# ============================================================================
# Tool Execution Functions
# ============================================================================

async def execute_preview_tool(room_id: str, room: RoomState, user_content: str) -> Dict:
    """
    Execute #preview tool
    Generates HTML preview using FULL conversation context
    The #preview tag is just a trigger - the requirement comes from the discussion
    """
    logger.info(f"🎨 Executing preview tool in {room_id}")
    logger.info(f"   Using full conversation context ({len(room.messages)} messages)")

    # Show Amigo is working
    await room_manager.broadcast(room_id, {
        'type': 'typing_indicator',
        'roomId': room_id,
        'payload': {'agentId': 'amigo', 'isTyping': True},
        'timestamp': datetime.now().isoformat()
    })

    # Generate preview using FULL conversation context
    # The AI will analyze the entire discussion to understand what to build
    try:
        preview_html = await generate_preview_with_context(room.messages)

        # Create Amigo's response
        amigo = AI_AGENT_PERSONAS.get('amigo')
        amigo_message = {
            'id': f'msg_{int(time.time())}_{uuid.uuid4().hex[:8]}',
            'sender': {
                'id': 'amigo',
                'name': amigo['name'],
                'type': 'ai',
                'role': amigo['role'],
                'avatar': amigo['avatar'],
                'color': amigo['color']
            },
            'content': "I've created a preview based on our discussion!",
            'timestamp': datetime.now().isoformat(),
            'attachments': {'preview': preview_html}
        }

        # Add to room history
        room.add_message(amigo_message)

        # Broadcast response
        await room_manager.broadcast(room_id, {
            'type': 'ai_message',
            'roomId': room_id,
            'payload': amigo_message,
            'timestamp': amigo_message['timestamp']
        })

        # Broadcast preview (match frontend's expected format: preview_generated)
        logger.info(f"📤 Broadcasting preview_generated ({len(preview_html)} chars of HTML)")
        await room_manager.broadcast(room_id, {
            'type': 'preview_generated',
            'roomId': room_id,
            'payload': {
                'preview': {
                    'id': f'preview_{int(time.time())}',
                    'type': 'html_component',
                    'html_content': preview_html,  # Note: html_content (underscore) to match frontend
                    'files': [],
                    'generatedBy': 'amigo',
                    'synthesisNotes': 'Interactive preview generated from conversation'
                }
            },
            'timestamp': datetime.now().isoformat()
        })

        logger.info(f"✅ Preview tool executed successfully in {room_id}")
        return {'success': True}

    except Exception as e:
        logger.error(f"❌ Preview tool failed: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


async def execute_workflow_tool(room_id: str, room: RoomState, user_content: str) -> Dict:
    """
    Execute #workflow tool
    Generates maestro-dag workflow using FULL conversation context
    The #workflow tag is just a trigger - the requirement comes from the discussion
    """
    logger.info(f"🏗️ Executing workflow tool in {room_id}")
    logger.info(f"   Using full conversation context ({len(room.messages)} messages)")

    # Show Amigo is working
    await room_manager.broadcast(room_id, {
        'type': 'typing_indicator',
        'roomId': room_id,
        'payload': {'agentId': 'amigo', 'isTyping': True},
        'timestamp': datetime.now().isoformat()
    })

    # Generate workflow using FULL conversation context
    # The AI will analyze the entire discussion to understand requirements
    try:
        workflow_dag = await generate_workflow_with_context(room.messages)

        # Create Amigo's response
        amigo = AI_AGENT_PERSONAS.get('amigo')
        amigo_message = {
            'id': f'msg_{int(time.time())}_{uuid.uuid4().hex[:8]}',
            'sender': {
                'id': 'amigo',
                'name': amigo['name'],
                'type': 'ai',
                'role': amigo['role'],
                'avatar': amigo['avatar'],
                'color': amigo['color']
            },
            'content': workflow_dag,  # DAG is in the message content
            'timestamp': datetime.now().isoformat()
        }

        # Add to room history
        room.add_message(amigo_message)

        # Broadcast response
        await room_manager.broadcast(room_id, {
            'type': 'ai_message',
            'roomId': room_id,
            'payload': amigo_message,
            'timestamp': amigo_message['timestamp']
        })

        logger.info(f"✅ Workflow tool executed successfully in {room_id}")
        return {'success': True}

    except Exception as e:
        logger.error(f"❌ Workflow tool failed: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

# ============================================================================
# Tool Generation Functions (Using AI Provider)
# ============================================================================

async def generate_preview_with_context(conversation: List[Dict]) -> str:
    """
    Generate HTML preview using FULL conversation context
    Analyzes the entire discussion to understand what to build
    """
    if not HAS_AI_PROVIDER or ai_provider is None:
        # Simulated response
        return """
        <html>
        <body style="font-family: sans-serif; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
            <h1 style="color: white;">Preview Generated</h1>
            <p style="color: white;">This is a simulated preview (AI provider not available)</p>
            <p style="color: white;">In production, this would analyze the conversation to understand requirements.</p>
        </body>
        </html>
        """

    # Build conversation context - use MORE messages for better understanding
    messages = []
    for msg in conversation[-20:]:  # Last 20 messages for full context
        # Defensive check
        if 'sender' not in msg or 'type' not in msg.get('sender', {}):
            continue
        role = "user" if msg['sender']['type'] == 'human' else "assistant"
        messages.append(Message(role=role, content=msg['content']))

    # Add preview generation request
    messages.append(Message(role="user", content="""Based on our conversation above, generate a complete HTML preview.

CRITICAL INSTRUCTIONS:
1. Analyze the ENTIRE conversation to understand what to build
2. Return ONLY the complete HTML code
3. Include inline CSS and JavaScript
4. Make it beautiful and functional
5. NO explanations, NO markdown, ONLY HTML
6. Start with <!DOCTYPE html>

Generate the preview now based on what we discussed:"""))

    # Call AI provider
    try:
        request = ChatRequest(
            messages=messages,
            temperature=0.7,
            max_tokens=4000
        )

        response_parts = []
        chunk_count = 0
        async for chunk in ai_provider.chat(request):
            chunk_count += 1
            # Handle different chunk types (same as generate_ai_response)
            if hasattr(chunk, 'delta_text') and chunk.delta_text:
                response_parts.append(chunk.delta_text)
            elif hasattr(chunk, 'content') and chunk.content:
                response_parts.append(chunk.content)
            elif hasattr(chunk, 'text') and chunk.text:
                response_parts.append(chunk.text)
            elif isinstance(chunk, str):
                response_parts.append(chunk)
            elif isinstance(chunk, dict) and 'content' in chunk:
                response_parts.append(chunk['content'])

        html = ''.join(response_parts)
        logger.info(f"📊 Preview HTML generated ({chunk_count} chunks, {len(html)} chars)")

        # Extract HTML if wrapped in markdown
        if '```html' in html:
            html = html.split('```html')[1].split('```')[0].strip()
        elif '```' in html:
            html = html.split('```')[1].split('```')[0].strip()

        return html

    except Exception as e:
        logger.error(f"Preview generation error: {e}")
        return f"<html><body><h1>Error generating preview: {str(e)}</h1></body></html>"


async def generate_workflow_with_context(conversation: List[Dict]) -> str:
    """
    Generate maestro-dag workflow using FULL conversation context
    Analyzes the entire discussion to understand requirements
    """
    # Call backend WorkflowDAG service
    backend_url = "http://host.docker.internal:3100/api/v1/workflow-dag/generate"

    # Build conversation context - use MORE messages for better understanding
    conversation_context = []
    for msg in conversation[-20:]:  # Last 20 messages for full context
        if 'sender' not in msg or 'type' not in msg.get('sender', {}):
            continue
        role = "user" if msg['sender']['type'] == 'human' else "assistant"
        conversation_context.append({
            "role": role,
            "content": msg['content']
        })

    # Extract requirement from conversation context
    # The backend will analyze the conversation to understand what workflow to generate
    requirement = "Generate workflow based on our discussion"

    try:
        response = requests.post(
            backend_url,
            json={
                "requirement": requirement,
                "project_type": "web_app",
                "conversation": conversation_context  # Full context for analysis
            },
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            return data.get('dag', data.get('workflow', '# Workflow generation failed'))
        else:
            logger.error(f"Workflow generation failed: {response.status_code}")
            return f"# Error: Failed to generate workflow (status {response.status_code})"

    except Exception as e:
        logger.error(f"Workflow generation error: {e}")
        return f"# Error: {str(e)}"

# ============================================================================
# Agent Chat Routing
# ============================================================================

async def route_to_agents(room_id: str, room: RoomState, user_message: Dict):
    """
    Route message to AI agents for natural participation
    This handles normal multi-agent chat (not tool execution)

    UNIFIED_BFF BEHAVIOR: Amigo ALWAYS responds (default agent), no @mention needed
    """
    content = user_message['content']

    # Extract @mentions
    mentioned_agents = extract_mentions(content)

    if mentioned_agents:
        # Route to specifically mentioned agents
        for agent_id in mentioned_agents:
            if agent_id in AI_AGENT_PERSONAS:
                await generate_and_send_agent_response(room_id, room, agent_id, user_message)
    else:
        # ALWAYS respond with Amigo (like unified_bff - no @mention required)
        # This matches the elegant conversational UX of V1
        await generate_and_send_agent_response(room_id, room, 'amigo', user_message)


def extract_mentions(content: str) -> List[str]:
    """Extract @mentions from message content"""
    import re
    # Find all @mentions (e.g., @Maestro, @Amigo)
    mentions = re.findall(r'@(\w+)', content)
    # Convert to lowercase IDs
    return [m.lower() for m in mentions]


async def generate_and_send_agent_response(room_id: str, room: RoomState, agent_id: str, user_message: Dict):
    """Generate and send AI agent response"""
    agent = AI_AGENT_PERSONAS.get(agent_id)
    if not agent:
        return

    # Show typing indicator
    await room_manager.broadcast(room_id, {
        'type': 'typing_indicator',
        'roomId': room_id,
        'payload': {'agentId': agent_id, 'isTyping': True},
        'timestamp': datetime.now().isoformat()
    })

    # Simulate thinking time
    await asyncio.sleep(1.0)

    # Generate response
    if HAS_AI_PROVIDER and ai_provider:
        logger.info(f"🤖 Calling AI provider for {agent['name']}")
        response_content = await generate_ai_response(agent, room.messages, user_message['content'])
        logger.info(f"💬 {agent['name']} response: {response_content[:100]}...")
    else:
        logger.warning(f"⚠️ No AI provider - using simulated response")
        response_content = f"[Simulated {agent['name']}] I understand you're asking about: {user_message['content'][:100]}"

    # Create agent message
    agent_message = {
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
    room.add_message(agent_message)

    # Broadcast
    await room_manager.broadcast(room_id, {
        'type': 'ai_message',
        'roomId': room_id,
        'payload': agent_message,
        'timestamp': agent_message['timestamp']
    })


async def generate_ai_response(agent: Dict, conversation: List[Dict], user_message: str) -> str:
    """Generate AI response using conversation context"""
    try:
        # Build conversation context
        messages = []
        for msg in conversation[-20:]:
            if 'sender' not in msg or 'type' not in msg.get('sender', {}):
                continue
            role = "user" if msg['sender']['type'] == 'human' else "assistant"
            messages.append(Message(role=role, content=msg['content']))

        # Add current user message
        messages.append(Message(role="user", content=user_message))

        # Use the persona's actual system_prompt (from persona JSON file)
        # This provides the best conversational quality and context
        system_prompt = agent.get('system_prompt') or agent.get('prompts', {}).get('system_prompt') or f"""You are {agent['name']}, {agent['role']}.

{agent.get('description', '')}

Respond naturally as this persona. Keep responses concise and helpful (2-3 sentences)."""

        # Call AI provider
        request = ChatRequest(
            messages=messages,
            temperature=0.7,
            max_tokens=500,
            system=system_prompt
        )

        logger.info(f"🤖 Generating response for {agent['name']} (context: {len(messages)} messages)")

        response_parts = []
        chunk_count = 0
        async for chunk in ai_provider.chat(request):
            chunk_count += 1

            # DEBUG: Log chunk structure
            logger.debug(f"[DEBUG] Chunk #{chunk_count}: type={type(chunk).__name__}, repr={repr(chunk)[:200]}")

            # Handle different chunk types
            if hasattr(chunk, 'delta_text') and chunk.delta_text:
                response_parts.append(chunk.delta_text)
                logger.debug(f"[DEBUG] → Extracted from .delta_text: {len(chunk.delta_text)} chars")
            elif hasattr(chunk, 'content') and chunk.content:
                response_parts.append(chunk.content)
                logger.debug(f"[DEBUG] → Extracted from .content: {len(chunk.content)} chars")
            elif hasattr(chunk, 'text') and chunk.text:
                response_parts.append(chunk.text)
                logger.debug(f"[DEBUG] → Extracted from .text: {len(chunk.text)} chars")
            elif isinstance(chunk, str):
                response_parts.append(chunk)
                logger.debug(f"[DEBUG] → Extracted string: {len(chunk)} chars")
            elif isinstance(chunk, dict) and 'content' in chunk:
                response_parts.append(chunk['content'])
                logger.debug(f"[DEBUG] → Extracted from dict['content']: {len(chunk['content'])} chars")
            else:
                logger.debug(f"[DEBUG] → No content extracted! Available attrs: {dir(chunk) if hasattr(chunk, '__dir__') else 'N/A'}")

        full_response = ''.join(response_parts).strip()
        logger.info(f"💬 {agent['name']} response ({chunk_count} chunks, {len(full_response)} chars): {full_response[:100]}...")

        if not full_response:
            logger.warning(f"⚠️ Empty response from AI provider! Falling back to default message.")
            return f"I'm thinking about: {user_message}"

        return full_response

    except Exception as e:
        logger.error(f"AI response generation error: {e}", exc_info=True)
        return f"I'm experiencing some difficulties. Let me get back to you on that."

# ============================================================================
# Main Message Handler
# ============================================================================

async def handle_user_message(room_id: str, room: RoomState, data: Dict):
    """
    Main message handler
    Clean flow: Store → Broadcast → Detect → Execute
    """
    sender = data.get('sender', {})
    content = data.get('content', '')
    mentions = data.get('mentions', [])

    logger.info(f"📨 [{room_id}] Message from {sender.get('name', 'Unknown')}: {content[:50]}...")

    # ========================================
    # STEP 1: Create and store user message
    # ========================================
    message = {
        'id': f'msg_{int(time.time())}_{uuid.uuid4().hex[:8]}',
        'sender': sender,
        'content': content,
        'timestamp': datetime.now().isoformat(),
        'mentions': mentions
    }

    # Add to room history FIRST (critical for context)
    room.add_message(message)

    # ========================================
    # STEP 2: Broadcast user message
    # ========================================
    await room_manager.broadcast(room_id, {
        'type': 'user_message',
        'roomId': room_id,
        'payload': message,
        'timestamp': message['timestamp']
    })

    # ========================================
    # STEP 3: Tool detection and execution
    # ========================================

    # Check for #preview tool
    if '#preview' in content.lower():
        logger.info(f"🎨 [{room_id}] #preview tool detected")
        await execute_preview_tool(room_id, room, content)
        return  # Tool executed, done

    # Check for #workflow tool
    if '#workflow' in content.lower():
        logger.info(f"🏗️ [{room_id}] #workflow tool detected")
        await execute_workflow_tool(room_id, room, content)
        return  # Tool executed, done

    # ========================================
    # STEP 4: Normal agent routing
    # ========================================
    await route_to_agents(room_id, room, message)

# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="MAESTRO Multi-Agent Collaboration BFF V2",
    description="Clean, tool-based multi-agent collaboration",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "collaboration-bff-v2",
        "version": "2.0.0",
        "ai_provider": "enabled" if HAS_AI_PROVIDER else "simulated",
        "rooms": len(room_manager.rooms),
        "connections": sum(len(conns) for conns in room_manager.connections.values())
    }

@app.websocket("/ws/collaboration/{room_id}")
@app.websocket("/room_{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    """
    WebSocket endpoint for room-based collaboration

    Supports both:
    - Direct: /ws/collaboration/{room_id}
    - Gateway (strips prefix): /room_{room_id}

    Gateway receives: /ws/collaboration/room_123
    Gateway forwards: /room_123 (strips /ws/collaboration/ prefix)
    """

    # Get or create room
    room = room_manager.get_or_create_room(room_id)

    # Connect websocket
    await room_manager.connect(room_id, websocket)

    try:
        # Send initial room state
        await websocket.send_json({
            'type': 'room_state',
            'roomId': room_id,
            'payload': {
                'participants': room.participants,
                'messageCount': len(room.messages)
            },
            'timestamp': datetime.now().isoformat()
        })

        # Listen for messages
        while True:
            data = await websocket.receive_json()
            message_type = data.get('type')

            if message_type == 'join':
                # Participant joining room
                participant = data.get('participant', {})
                room.add_participant(participant)

                # Broadcast participant joined
                await room_manager.broadcast(room_id, {
                    'type': 'participant_joined',
                    'roomId': room_id,
                    'payload': {'participant': participant},
                    'timestamp': datetime.now().isoformat()
                })

            elif message_type == 'leave':
                # Participant leaving room
                participant_id = data.get('participantId')
                room.remove_participant(participant_id)

                await room_manager.broadcast(room_id, {
                    'type': 'participant_left',
                    'roomId': room_id,
                    'payload': {'participantId': participant_id},
                    'timestamp': datetime.now().isoformat()
                })

            elif message_type == 'user_message':
                # Handle user message
                await handle_user_message(room_id, room, data)

            elif message_type == 'ping':
                # Heartbeat
                await websocket.send_json({'type': 'pong'})

    except WebSocketDisconnect:
        await room_manager.disconnect(room_id, websocket)
        logger.info(f"🔌 Client disconnected from {room_id}")

    except Exception as e:
        logger.error(f"WebSocket error in {room_id}: {e}", exc_info=True)
        await room_manager.disconnect(room_id, websocket)

# ============================================================================
# Startup
# ============================================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 MAESTRO Collaboration BFF V2 Starting...")
    logger.info("=" * 60)
    logger.info(f"📡 Port: 4003 (v2 - testing)")
    logger.info(f"🤖 AI Provider: {'enabled' if HAS_AI_PROVIDER else 'simulated'}")
    logger.info(f"👥 Personas: {len(AI_AGENT_PERSONAS)}")
    logger.info("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=4003)
