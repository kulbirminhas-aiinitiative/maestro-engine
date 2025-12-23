"""
Symphony WebSocket Router

EPIC: MD-3902 - Maestro Symphony Demo
Story: MD-3908 - Wire Artifact Streaming via WebSocket

FastAPI router for Symphony WebSocket connections and REST endpoints.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse

from symphony.artifact_streamer import get_artifact_streamer

# MD-4123: Import LLM client and persona prompts for real workflow
from symphony.llm_client import get_llm_client, LLMConnectionError, LLMTimeoutError
from symphony.persona_prompts import (
    get_persona_prompt,
    get_persona_prompt_by_mode,
    get_persona_info,
    PERSONA_EXECUTION_ORDER,
)
from symphony.agent_modes import (
    AgentMode,
    WorkflowModeConfig,
    get_effective_mode,
    is_rag_enabled,
    load_default_modes,
    get_mode_descriptions,
    get_rag_defaults,
)
from symphony.artifact_extractor import get_artifact_extractor
from symphony.models import (
    ArtifactEvent,
    KickstartRequest,
    KickstartResponse,
    SymphonySession,
)
from symphony.personas import (
    get_all_personas,
    get_ai_personas,
    get_persona,
    format_personas_for_frontend,
    select_responding_persona,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/symphony", tags=["symphony"])


# WebSocket connection manager for Symphony
class SymphonyWebSocketManager:
    """Manages WebSocket connections for Symphony artifact streaming"""

    def __init__(self):
        # session_id -> WebSocket
        self.connections: Dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        """Accept and register WebSocket connection"""
        await websocket.accept()
        self.connections[session_id] = websocket
        logger.info(f"Symphony WebSocket connected: {session_id}")

    async def disconnect(self, session_id: str):
        """Disconnect and cleanup"""
        if session_id in self.connections:
            del self.connections[session_id]
        logger.info(f"Symphony WebSocket disconnected: {session_id}")

    async def send_event(self, session_id: str, event: dict):
        """Send event to connected client"""
        if session_id in self.connections:
            try:
                await self.connections[session_id].send_json(event)
                return True
            except Exception as e:
                logger.error(f"Error sending to {session_id}: {e}")
                await self.disconnect(session_id)
                return False
        return False

    def is_connected(self, session_id: str) -> bool:
        """Check if session has active connection"""
        return session_id in self.connections


# Singleton WebSocket manager
ws_manager = SymphonyWebSocketManager()


@router.websocket("/ws/{session_id}")
async def symphony_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for Symphony artifact streaming.

    Clients connect to receive real-time artifact events as conversation
    generates user stories, architecture diagrams, code, and tests.
    """
    await ws_manager.connect(session_id, websocket)
    streamer = get_artifact_streamer()

    # Create or get session
    session = streamer.get_session(session_id)
    if not session:
        session = streamer.create_session(session_id, f"channel_{session_id[:8]}")

    # Define artifact event callback
    async def on_artifact(event: ArtifactEvent):
        """Forward artifact events to WebSocket"""
        event_dict = {
            "type": event.event_type,
            "artifactType": event.artifact_type.value,
            "artifact": event.artifact,
            "timestamp": event.timestamp
        }
        await ws_manager.send_event(session_id, event_dict)

    # Register listener
    streamer.add_listener(session_id, on_artifact)

    try:
        # Send initial state
        await websocket.send_json({
            "type": "connected",
            "sessionId": session_id,
            "channelId": session.channel_id,
            "artifacts": session.artifacts,
            "timestamp": datetime.now().isoformat()
        })

        # Listen for messages
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })

            elif data.get("type") == "message":
                # Process incoming message for artifact extraction
                persona_id = data.get("personaId", "unknown")
                persona_role = data.get("personaRole", "unknown")
                content = data.get("content", "")

                await streamer.process_message(
                    session_id,
                    persona_id,
                    persona_role,
                    content
                )

            elif data.get("type") == "clear_artifacts":
                # Clear all artifacts
                session.artifacts = {
                    "stories": [],
                    "architecture": [],
                    "code": [],
                    "tests": []
                }
                await websocket.send_json({
                    "type": "artifacts_cleared",
                    "timestamp": datetime.now().isoformat()
                })

    except WebSocketDisconnect:
        logger.info(f"Symphony client disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Symphony WebSocket error: {e}")
    finally:
        streamer.remove_listener(session_id, on_artifact)
        await ws_manager.disconnect(session_id)


# REST API endpoints

@router.post("/sessions", response_model=dict)
async def create_session(channel_id: Optional[str] = None):
    """Create a new Symphony session"""
    session_id = f"symphony_{uuid.uuid4().hex[:12]}"
    channel = channel_id or f"channel_{session_id[:8]}"

    streamer = get_artifact_streamer()
    session = streamer.create_session(session_id, channel)

    return {
        "sessionId": session_id,
        "channelId": channel,
        "status": "created",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session state"""
    streamer = get_artifact_streamer()
    session = streamer.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "sessionId": session.session_id,
        "channelId": session.channel_id,
        "workflowStatus": session.workflow_status,
        "artifacts": session.artifacts,
        "workflowProgress": session.workflow_progress.model_dump(by_alias=True) if session.workflow_progress else None,
        "createdAt": session.created_at
    }


@router.get("/sessions/{session_id}/artifacts")
async def get_artifacts(session_id: str):
    """Get all artifacts for a session"""
    streamer = get_artifact_streamer()
    session = streamer.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.artifacts


@router.post("/sessions/{session_id}/kickstart")
async def kickstart_workflow(session_id: str, request: KickstartRequest):
    """
    Kickstart the Symphony SDLC workflow with configurable agent modes.

    This triggers the AI personas to start their conversation
    about the given requirement, generating artifacts in real-time.

    Agent modes:
    - simple: Basic prompt, fast execution, minimal context
    - full: Comprehensive prompt with full schema and guidelines
    - full_rag: Full prompt enhanced with RAG-retrieved context
    """
    streamer = get_artifact_streamer()
    session = streamer.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Update workflow status
    session.workflow_status = "running"

    # Build mode configuration from request
    rag_config = request.rag_config or {}
    mode_config = WorkflowModeConfig(
        global_mode=request.global_mode,
        persona_modes=request.persona_modes or {},
        rag_enabled=request.rag_enabled,
        rag_top_k=rag_config.get("top_k", 5),
        rag_min_score=rag_config.get("min_score", 0.7),
    )

    # MD-4123: Real LLM mode enabled by default
    use_real_llm = os.getenv("SYMPHONY_USE_REAL_LLM", "true").lower() == "true"

    if use_real_llm:
        # Start real LLM workflow via claude_code_api_layer
        asyncio.create_task(
            _run_real_workflow(session_id, request.requirement, mode_config)
        )
    else:
        # Start demo workflow (simulated artifacts)
        asyncio.create_task(
            _run_demo_workflow(session_id, request.requirement)
        )

    # Determine mode description for response
    mode_desc = "per-persona defaults"
    if mode_config.global_mode:
        mode_desc = mode_config.global_mode.value
    elif mode_config.persona_modes:
        mode_desc = "custom per-persona"

    return KickstartResponse(
        sessionId=session_id,
        status="started",
        message=f"Workflow started (mode: {mode_desc}): {request.requirement[:50]}..."
    )


async def _run_demo_workflow(session_id: str, requirement: str):
    """
    Run demo workflow - simulates AI persona conversation.

    In production, this would connect to the actual AI personas.
    For demo purposes, we generate sample artifacts.
    """
    streamer = get_artifact_streamer()
    session = streamer.get_session(session_id)
    if not session:
        return

    try:
        # Phase 1: Requirements
        await streamer.update_workflow_progress(
            session_id, "requirements", "running", 0,
            "Product Manager analyzing requirements..."
        )

        # Simulate PM generating stories
        await asyncio.sleep(2)
        await streamer.process_message(
            session_id,
            "sarah_pm",
            "Product Manager",
            f"Based on the requirement '{requirement}', I see three key user stories:\n"
            f"- As a user, I need to {requirement.lower()}\n"
            f"- As an admin, I need to configure the system\n"
            f"- As a system, I should validate all inputs"
        )

        await streamer.update_workflow_progress(
            session_id, "requirements", "completed", 100,
            "Requirements analysis complete"
        )

        # Phase 2: Design
        await streamer.update_workflow_progress(
            session_id, "design", "running", 0,
            "Architect designing system..."
        )

        await asyncio.sleep(2)
        await streamer.process_message(
            session_id,
            "marcus_arch",
            "Architect",
            "I recommend a microservices architecture with:\n"
            "- API Gateway for routing\n"
            "- Backend service for business logic\n"
            "- Database for persistence\n"
            "- Frontend React application"
        )

        await streamer.update_workflow_progress(
            session_id, "design", "completed", 100,
            "Architecture design complete"
        )

        # Phase 3: Implementation
        await streamer.update_workflow_progress(
            session_id, "implementation", "running", 0,
            "Developer writing code..."
        )

        await asyncio.sleep(2)
        code_content = '''```python
class FeatureService:
    """Main service for handling feature requests"""

    def __init__(self, db_client):
        self.db = db_client

    async def create(self, data: dict) -> dict:
        """Create new feature entry"""
        result = await self.db.insert(data)
        return {"id": result.id, "status": "created"}

    async def get(self, feature_id: str) -> dict:
        """Retrieve feature by ID"""
        return await self.db.find_by_id(feature_id)
```'''
        await streamer.process_message(
            session_id,
            "alex_dev",
            "Developer",
            f"Here's the initial implementation:\n\n{code_content}"
        )

        await streamer.update_workflow_progress(
            session_id, "implementation", "completed", 100,
            "Implementation complete"
        )

        # Phase 4: Testing
        await streamer.update_workflow_progress(
            session_id, "testing", "running", 0,
            "QA defining test cases..."
        )

        await asyncio.sleep(2)
        await streamer.process_message(
            session_id,
            "priya_qa",
            "QA Lead",
            "I've defined the following test cases:\n"
            "- Test: Verify user can create new entries\n"
            "- Test: Validate input sanitization\n"
            "- Test: Check API response format matches contract\n"
            "- Test: Ensure error handling for invalid data"
        )

        await streamer.update_workflow_progress(
            session_id, "testing", "completed", 100,
            "Test planning complete"
        )

        # Workflow complete
        session.workflow_status = "completed"

        # Notify via WebSocket if connected
        if ws_manager.is_connected(session_id):
            await ws_manager.send_event(session_id, {
                "type": "workflow_completed",
                "sessionId": session_id,
                "timestamp": datetime.now().isoformat()
            })

    except Exception as e:
        logger.error(f"Demo workflow error: {e}")
        session.workflow_status = "error"

        if ws_manager.is_connected(session_id):
            await ws_manager.send_event(session_id, {
                "type": "workflow_error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })


# ============================================================
# MD-4123: Real LLM Workflow Implementation
# ============================================================

async def _run_real_workflow(
    session_id: str,
    requirement: str,
    mode_config: Optional[WorkflowModeConfig] = None,
):
    """
    Run real LLM workflow - routes requests through claude_code_api_layer.

    MD-4123: Symphony Real LLM Integration
    Story: MD-4134 - Implement _run_real_workflow with sequential persona execution

    This executes personas sequentially (Sarah → Marcus → Alex → Priya),
    passing context from each persona to the next.

    Args:
        session_id: Symphony session identifier
        requirement: Project requirement to build
        mode_config: Optional mode configuration for agent execution
    """
    streamer = get_artifact_streamer()
    session = streamer.get_session(session_id)
    if not session:
        return

    llm_client = get_llm_client()
    extractor = get_artifact_extractor()

    # Build initial context
    context = {
        "project_brief": requirement,
    }

    # Track total tokens
    total_tokens = 0

    # Initialize RAG connector if any persona might use FULL_RAG mode
    rag_connector = None
    if mode_config:
        # Check if any persona will use FULL_RAG mode
        for persona_id in PERSONA_EXECUTION_ORDER:
            effective_mode = get_effective_mode(persona_id, mode_config)
            if is_rag_enabled(effective_mode, mode_config):
                try:
                    # Lazy import to avoid circular dependency
                    from maestro_hive.personas.rag_connector import get_rag_connector
                    rag_connector = get_rag_connector()
                    logger.info("RAG connector initialized for FULL_RAG mode")
                except ImportError:
                    logger.warning("RAG connector not available - FULL_RAG will use FULL mode prompts")
                except Exception as e:
                    logger.warning(f"Failed to initialize RAG connector: {e}")
                break

    try:
        # Execute each persona in sequence
        for persona_id in PERSONA_EXECUTION_ORDER:
            persona_info = get_persona_info(persona_id)
            phase_name = _persona_to_phase(persona_id)

            # Determine effective mode for this persona
            effective_mode = get_effective_mode(persona_id, mode_config)

            # Update progress with mode info
            await streamer.update_workflow_progress(
                session_id, phase_name, "running", 0,
                f"{persona_info.name} ({persona_info.role}) is working... [mode: {effective_mode.value}]"
            )

            # Notify via WebSocket
            if ws_manager.is_connected(session_id):
                await ws_manager.send_event(session_id, {
                    "type": "persona_started",
                    "personaId": persona_id,
                    "personaName": persona_info.name,
                    "role": persona_info.role,
                    "mode": effective_mode.value,
                    "timestamp": datetime.now().isoformat()
                })

            # Get RAG context if FULL_RAG mode and RAG is enabled
            rag_context = None
            if is_rag_enabled(effective_mode, mode_config) and rag_connector:
                rag_context = await _get_rag_context(
                    rag_connector,
                    requirement,
                    persona_id,
                    mode_config,
                )

            # Build persona-specific prompt
            task_prompt = _build_task_prompt(persona_id, requirement, context)

            # Get mode-specific system prompt with optional RAG context
            system_prompt = get_persona_prompt_by_mode(
                persona_id,
                effective_mode,
                rag_context=rag_context,
            )

            try:
                # Call LLM via claude_code_api_layer
                response = await llm_client.generate(
                    prompt=task_prompt,
                    system_prompt=system_prompt,
                    context=context,
                )

                total_tokens += response.tokens_total
                logger.info(
                    f"Persona {persona_id} completed: "
                    f"{response.tokens_total} tokens, {response.latency_ms:.0f}ms"
                )

                # Extract artifacts from response
                artifacts = extractor.extract_all(response.content, persona_id)

                # Store in context for next persona
                context[persona_info.output_format] = artifacts

                # Process message to extract and stream artifacts
                await streamer.process_message(
                    session_id,
                    persona_id,
                    persona_info.role,
                    response.content
                )

                # Update progress
                await streamer.update_workflow_progress(
                    session_id, phase_name, "completed", 100,
                    f"{persona_info.name} completed"
                )

                # Notify completion
                if ws_manager.is_connected(session_id):
                    await ws_manager.send_event(session_id, {
                        "type": "persona_completed",
                        "personaId": persona_id,
                        "personaName": persona_info.name,
                        "tokensUsed": response.tokens_total,
                        "latencyMs": response.latency_ms,
                        "artifactCount": artifacts.get("count", 0),
                        "timestamp": datetime.now().isoformat()
                    })

            except (LLMConnectionError, LLMTimeoutError) as e:
                logger.error(f"LLM error for persona {persona_id}: {e}")

                # Notify error but continue if possible
                if ws_manager.is_connected(session_id):
                    await ws_manager.send_event(session_id, {
                        "type": "persona_error",
                        "personaId": persona_id,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })

                # Mark phase as failed
                await streamer.update_workflow_progress(
                    session_id, phase_name, "error", 0,
                    f"LLM error: {str(e)[:100]}"
                )

                # Continue to next persona (fail-forward)
                continue

        # Workflow complete
        session.workflow_status = "completed"

        # Notify completion
        if ws_manager.is_connected(session_id):
            await ws_manager.send_event(session_id, {
                "type": "workflow_completed",
                "sessionId": session_id,
                "totalTokens": total_tokens,
                "mode": "real_llm",
                "timestamp": datetime.now().isoformat()
            })

        logger.info(f"Real workflow completed: session={session_id}, tokens={total_tokens}")

    except Exception as e:
        logger.error(f"Real workflow error: {e}")
        session.workflow_status = "error"

        if ws_manager.is_connected(session_id):
            await ws_manager.send_event(session_id, {
                "type": "workflow_error",
                "error": str(e),
                "mode": "real_llm",
                "timestamp": datetime.now().isoformat()
            })


def _persona_to_phase(persona_id: str) -> str:
    """Map persona ID to workflow phase name"""
    mapping = {
        "sarah": "requirements",
        "marcus": "design",
        "alex": "implementation",
        "priya": "testing",
    }
    return mapping.get(persona_id, persona_id)


def _build_task_prompt(persona_id: str, requirement: str, context: Dict[str, Any]) -> str:
    """Build task-specific prompt for persona"""
    if persona_id == "sarah":
        return f"""Analyze the following project requirement and create detailed user stories with acceptance criteria.

## Project Requirement
{requirement}

Please provide:
1. 3-5 user stories in standard format
2. Clear acceptance criteria for each
3. Priority and story point estimates
4. Any risks or dependencies identified"""

    elif persona_id == "marcus":
        stories = context.get("user_stories", {})
        stories_text = json.dumps(stories, indent=2) if stories else "See previous context"

        return f"""Based on the user stories below, design the system architecture.

## Original Requirement
{requirement}

## User Stories
{stories_text}

Please provide:
1. Architecture overview
2. Component breakdown with responsibilities
3. Data flow description
4. API contracts
5. Key technical decisions"""

    elif persona_id == "alex":
        arch = context.get("architecture", {})
        arch_text = json.dumps(arch, indent=2) if arch else "See previous context"

        return f"""Implement the code based on the architecture design below.

## Original Requirement
{requirement}

## Architecture Design
{arch_text}

Please provide:
1. Implementation plan
2. Working Python code (not stubs)
3. Proper error handling
4. Type hints and docstrings"""

    elif persona_id == "priya":
        code = context.get("code", {})
        code_text = json.dumps(code, indent=2) if code else "See previous context"

        return f"""Create comprehensive test cases for the implementation below.

## Original Requirement
{requirement}

## Implementation
{code_text}

Please provide:
1. Test strategy
2. Test cases (unit, integration, e2e)
3. Working pytest code
4. Quality checklist"""

    return f"Complete your assigned task for: {requirement}"


async def _get_rag_context(
    rag_connector,
    requirement: str,
    persona_id: str,
    mode_config: Optional[WorkflowModeConfig],
) -> Optional[str]:
    """
    Retrieve and format RAG context for a persona.

    Args:
        rag_connector: RAG connector instance
        requirement: Project requirement for context search
        persona_id: Persona identifier for persona-specific results
        mode_config: Mode configuration with RAG settings

    Returns:
        Formatted RAG context string, or None if unavailable
    """
    if not rag_connector:
        return None

    try:
        # Get RAG config from mode_config
        top_k = mode_config.rag_top_k if mode_config else 5
        min_score = mode_config.rag_min_score if mode_config else 0.7

        # Retrieve context
        context = await rag_connector.retrieve(
            query=requirement,
            persona_id=persona_id,
            top_k=top_k,
            min_score=min_score,
        )

        if context and hasattr(context, 'results') and context.results:
            # Format results for prompt injection
            formatted_parts = []
            for i, result in enumerate(context.results[:top_k], 1):
                if hasattr(result, 'document'):
                    doc = result.document
                    content = doc.content[:500] if hasattr(doc, 'content') else str(doc)[:500]
                    formatted_parts.append(f"{i}. {content}")

            if formatted_parts:
                return "\n".join(formatted_parts)

        return None

    except Exception as e:
        logger.warning(f"RAG retrieval failed for {persona_id}: {e}")
        return None


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a Symphony session"""
    streamer = get_artifact_streamer()
    session = streamer.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    streamer.cleanup_session(session_id)

    return {"status": "deleted", "sessionId": session_id}


@router.get("/health")
async def health_check():
    """Symphony service health check"""
    streamer = get_artifact_streamer()
    return {
        "status": "healthy",
        "service": "symphony-artifact-streamer",
        "activeSessions": len(streamer.sessions),
        "activeConnections": len(ws_manager.connections),
        "timestamp": datetime.now().isoformat()
    }


# ============================================================
# Agent Mode Configuration Endpoints
# ============================================================

@router.get("/modes")
async def get_available_modes():
    """
    Get available agent execution modes and their defaults.

    Returns:
        - availableModes: List of mode values (simple, full, full_rag)
        - defaultModes: Per-persona default modes from config
        - modeDescriptions: Human-readable descriptions for each mode
        - ragAvailable: Whether RAG integration is available
        - ragDefaults: Default RAG configuration
    """
    # Check if RAG is available
    rag_available = False
    try:
        from maestro_hive.personas.rag_connector import get_rag_connector
        rag_available = True
    except ImportError:
        pass

    return {
        "availableModes": [mode.value for mode in AgentMode],
        "defaultModes": {k: v.value for k, v in load_default_modes().items()},
        "modeDescriptions": get_mode_descriptions(),
        "ragAvailable": rag_available,
        "ragDefaults": get_rag_defaults(),
    }


# ============================================================
# Persona Endpoints
# ============================================================

@router.get("/personas")
async def list_personas():
    """
    Get all Symphony AI personas.

    Returns the full list of personas available for the Symphony demo,
    including their personalities, expertise, and trigger keywords.
    """
    return {
        "personas": format_personas_for_frontend(),
        "count": len(get_all_personas()),
        "aiCount": len(get_ai_personas()),
    }


@router.get("/personas/{persona_id}")
async def get_persona_by_id(persona_id: str):
    """Get a specific persona by ID"""
    persona = get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")
    return persona.to_dict()


@router.post("/personas/select")
async def select_persona_for_message(message: str, exclude: Optional[str] = None):
    """
    Select the most appropriate persona to respond to a message.

    Uses trigger word matching and response priority to determine
    which AI persona should respond.
    """
    exclude_ids = [exclude] if exclude else []
    persona = select_responding_persona(message, exclude_ids)

    if not persona:
        return {
            "selected": None,
            "message": "No persona matched the message triggers"
        }

    return {
        "selected": persona.to_dict(),
        "typingDelayMs": persona.get_typing_delay(),
    }


# ============================================================
# Offline Fallback Endpoints (MD-3911)
# ============================================================

from symphony.offline_fallback import (
    get_fallback_manager,
    run_preflight_checks,
    FallbackMode,
    FallbackReason,
    PrerecordedMessage,
    PrerecordedArtifact,
)


@router.get("/fallback/status")
async def get_fallback_status():
    """
    Get current offline fallback status.

    Returns the current mode (live/offline/hybrid), reason for fallback
    if applicable, and health check status for dependencies.
    """
    fallback_mgr = get_fallback_manager()
    return fallback_mgr.get_status()


@router.post("/fallback/switch-offline")
async def switch_to_offline(reason: str = "manual"):
    """
    Manually switch to offline fallback mode.

    Use this to preemptively switch to offline mode before a demo
    if you suspect connectivity issues.
    """
    fallback_mgr = get_fallback_manager()
    try:
        fallback_reason = FallbackReason(reason)
    except ValueError:
        fallback_reason = FallbackReason.MANUAL

    fallback_mgr.switch_to_offline(fallback_reason)
    return {
        "status": "switched_to_offline",
        "reason": fallback_reason.value,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/fallback/switch-live")
async def switch_to_live():
    """
    Switch back to live mode.

    Attempts to restore live connectivity to Teams and LLM APIs.
    """
    fallback_mgr = get_fallback_manager()
    fallback_mgr.switch_to_live()
    return {
        "status": "switched_to_live",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/fallback/scenarios")
async def list_offline_scenarios():
    """
    List available offline demo scenarios.

    Returns prerecorded conversation and artifact scenarios that can be
    played back when in offline mode.
    """
    fallback_mgr = get_fallback_manager()
    return {
        "scenarios": fallback_mgr.list_scenarios(),
        "count": len(fallback_mgr.list_scenarios()),
    }


@router.get("/fallback/scenarios/{scenario_id}")
async def get_scenario_details(scenario_id: str):
    """Get detailed information about a specific scenario"""
    fallback_mgr = get_fallback_manager()
    scenario = fallback_mgr.get_scenario(scenario_id)

    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

    return {
        "scenario_id": scenario.scenario_id,
        "title": scenario.title,
        "description": scenario.description,
        "message_count": len(scenario.messages),
        "duration_estimate_ms": scenario.duration_estimate_ms,
        "messages": [
            {
                "index": i,
                "persona_id": m.persona_id,
                "display_name": m.display_name,
                "role": m.role,
                "is_human": m.is_human,
                "delay_ms": m.delay_ms,
                "content_preview": m.content[:100] + "..." if len(m.content) > 100 else m.content,
            }
            for i, m in enumerate(scenario.messages)
        ],
        "artifact_count": sum(len(v) for v in scenario.artifacts.values()),
    }


@router.post("/fallback/playback/{scenario_id}/start")
async def start_playback(scenario_id: str, session_id: Optional[str] = None):
    """
    Start playing back a prerecorded scenario.

    Optionally connects to an existing Symphony session to stream
    messages and artifacts via WebSocket.
    """
    fallback_mgr = get_fallback_manager()
    scenario = fallback_mgr.get_scenario(scenario_id)

    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

    # Use provided session or create a new one
    if not session_id:
        session_id = f"offline_{uuid.uuid4().hex[:12]}"

    # Define callbacks for playback
    async def on_message(msg: PrerecordedMessage):
        """Forward prerecorded message to WebSocket"""
        if ws_manager.is_connected(session_id):
            await ws_manager.send_event(session_id, {
                "type": "message",
                "personaId": msg.persona_id,
                "displayName": msg.display_name,
                "role": msg.role,
                "content": msg.content,
                "isHuman": msg.is_human,
                "isOfflinePlayback": True,
                "timestamp": datetime.now().isoformat(),
            })

    async def on_artifact(artifact: PrerecordedArtifact):
        """Forward prerecorded artifact to WebSocket"""
        if ws_manager.is_connected(session_id):
            await ws_manager.send_event(session_id, {
                "type": "artifact_created",
                "artifactType": artifact.artifact_type.value,
                "artifact": artifact.data,
                "isOfflinePlayback": True,
                "timestamp": datetime.now().isoformat(),
            })

    # Start playback
    playback = fallback_mgr.start_playback(
        scenario_id,
        on_message=lambda m: asyncio.create_task(on_message(m)),
        on_artifact=lambda a: asyncio.create_task(on_artifact(a)),
    )

    if not playback:
        raise HTTPException(status_code=500, detail="Failed to start playback")

    # Start async playback task
    asyncio.create_task(playback.start())

    return {
        "status": "playback_started",
        "scenario_id": scenario_id,
        "session_id": session_id,
        "message_count": len(scenario.messages),
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/fallback/playback/pause")
async def pause_playback():
    """Pause the current playback"""
    fallback_mgr = get_fallback_manager()
    if fallback_mgr.active_playback:
        fallback_mgr.active_playback.pause()
        return {"status": "paused"}
    return {"status": "no_active_playback"}


@router.post("/fallback/playback/resume")
async def resume_playback():
    """Resume the paused playback"""
    fallback_mgr = get_fallback_manager()
    if fallback_mgr.active_playback:
        fallback_mgr.active_playback.resume()
        return {"status": "resumed"}
    return {"status": "no_active_playback"}


@router.post("/fallback/playback/stop")
async def stop_playback():
    """Stop the current playback"""
    fallback_mgr = get_fallback_manager()
    if fallback_mgr.active_playback:
        fallback_mgr.active_playback.stop()
        fallback_mgr.active_playback = None
        return {"status": "stopped"}
    return {"status": "no_active_playback"}


@router.post("/fallback/playback/speed")
async def set_playback_speed(multiplier: float = 1.0):
    """
    Set playback speed.

    - 0.5 = half speed (slower, more time for audience to read)
    - 1.0 = normal speed
    - 2.0 = double speed (faster run-through)
    """
    fallback_mgr = get_fallback_manager()
    if fallback_mgr.active_playback:
        fallback_mgr.active_playback.set_speed(multiplier)
        return {
            "status": "speed_set",
            "multiplier": fallback_mgr.active_playback.speed_multiplier
        }
    return {"status": "no_active_playback"}


@router.get("/fallback/playback/status")
async def get_playback_status():
    """Get current playback status"""
    fallback_mgr = get_fallback_manager()
    if fallback_mgr.active_playback:
        return {
            "active": True,
            **fallback_mgr.active_playback.get_status()
        }
    return {"active": False}


@router.get("/preflight")
async def run_demo_preflight():
    """
    Run preflight checks for demo readiness.

    Checks Teams API, LLM API, and offline scenario availability.
    Returns recommendations based on check results.
    """
    results = await run_preflight_checks()
    return results


# ============================================================
# Metrics and Observability Endpoints (MD-3912)
# ============================================================

from symphony.metrics import (
    get_metrics_collector,
    TraceContext,
    SYMPHONY_SLOS,
)


@router.get("/metrics")
async def get_metrics_summary():
    """
    Get comprehensive metrics summary.

    Returns all counters, gauges, histograms with percentiles,
    and derived metrics like WebSocket uptime.
    """
    collector = get_metrics_collector()
    return collector.get_summary()


@router.get("/metrics/slos")
async def get_slo_status():
    """
    Evaluate all SLOs and return current status.

    Returns health status (healthy/warning/critical) for each SLO
    along with current values and targets.
    """
    collector = get_metrics_collector()
    return collector.evaluate_all_slos()


@router.get("/metrics/slos/{slo_name}")
async def get_single_slo(slo_name: str):
    """Get status for a specific SLO"""
    if slo_name not in SYMPHONY_SLOS:
        raise HTTPException(status_code=404, detail=f"SLO '{slo_name}' not found")

    collector = get_metrics_collector()
    status, value, message = collector.evaluate_slo(slo_name)
    slo_def = SYMPHONY_SLOS[slo_name]

    return {
        "name": slo_def.name,
        "description": slo_def.description,
        "target": slo_def.target,
        "current": value,
        "unit": slo_def.unit,
        "status": status.value,
        "message": message,
        "thresholds": {
            "warning": slo_def.threshold_warning,
            "critical": slo_def.threshold_critical,
        },
    }


@router.get("/metrics/histograms/{histogram_name}")
async def get_histogram_stats(histogram_name: str):
    """Get detailed statistics for a histogram metric"""
    collector = get_metrics_collector()
    stats = collector.get_histogram_stats(histogram_name)

    if stats["count"] == 0:
        raise HTTPException(status_code=404, detail=f"No data for histogram '{histogram_name}'")

    return {
        "name": histogram_name,
        "stats": stats,
    }


@router.post("/metrics/reset")
async def reset_metrics():
    """
    Reset all metrics.

    Use with caution - primarily for testing or starting a fresh demo session.
    """
    collector = get_metrics_collector()
    collector.reset()
    return {"status": "metrics_reset", "timestamp": datetime.now().isoformat()}


@router.get("/metrics/definitions")
async def list_slo_definitions():
    """List all SLO definitions with their targets and thresholds"""
    return {
        "slos": [
            {
                "key": key,
                "name": slo.name,
                "description": slo.description,
                "target": slo.target,
                "unit": slo.unit,
                "threshold_warning": slo.threshold_warning,
                "threshold_critical": slo.threshold_critical,
            }
            for key, slo in SYMPHONY_SLOS.items()
        ]
    }


@router.post("/metrics/record")
async def record_custom_metric(
    name: str,
    value: float,
    metric_type: str = "histogram",
    labels: Optional[Dict[str, str]] = None,
):
    """
    Record a custom metric value.

    Useful for frontend to report client-side metrics like
    artifact render time or animation frame rates.
    """
    collector = get_metrics_collector()

    if metric_type == "counter":
        collector.increment(name, int(value), labels)
    elif metric_type == "gauge":
        collector.set_gauge(name, value, labels)
    else:  # histogram
        collector.record_histogram(name, value, labels)

    return {
        "status": "recorded",
        "name": name,
        "value": value,
        "type": metric_type,
    }


@router.get("/trace/new")
async def create_new_trace(session_id: Optional[str] = None):
    """
    Create a new trace context.

    Use this at the start of a demo session to get a trace_id
    that correlates all subsequent events.
    """
    ctx = TraceContext.new(session_id)
    return ctx.to_dict()


# ============================================================
# Runbook and Preflight Endpoints (MD-3913)
# ============================================================

from symphony.runbook import (
    run_all_preflight_checks,
    get_demo_runbook,
    quick_start_demo,
    REQUIRED_ENV_VARS,
    OPTIONAL_ENV_VARS,
    CheckStatus,
)


@router.get("/runbook")
async def get_runbook():
    """
    Get the demo runbook with checkpoints and actions.

    Returns a minute-by-minute guide for running the Symphony demo,
    including pre-demo setup, demo execution, and post-demo wrap-up.
    """
    return {
        "checkpoints": get_demo_runbook(),
        "total_duration_minutes": 10,
        "description": "Symphony Demo: AI Team Collaboration",
    }


@router.get("/runbook/preflight")
async def run_preflight():
    """
    Run comprehensive preflight checks for demo readiness.

    Checks:
    - Environment variables
    - Backend health
    - WebSocket connectivity
    - Teams API (if configured)
    - LLM API
    - Persona registry
    - Offline scenarios
    - Metrics system
    """
    report = await run_all_preflight_checks(skip_external=False)
    return {
        "timestamp": report.timestamp.isoformat(),
        "overall_status": report.overall_status.value,
        "ready_for_demo": report.ready_for_demo,
        "total_duration_ms": report.total_duration_ms,
        "checks": [
            {
                "name": c.name,
                "status": c.status.value,
                "message": c.message,
                "duration_ms": c.duration_ms,
                "details": c.details,
            }
            for c in report.checks
        ],
        "recommendations": report.recommendations,
    }


@router.get("/runbook/preflight/quick")
async def run_quick_preflight():
    """
    Run quick preflight checks (skips external services).

    Faster than full preflight - only checks local components.
    """
    report = await run_all_preflight_checks(skip_external=True)
    return {
        "timestamp": report.timestamp.isoformat(),
        "overall_status": report.overall_status.value,
        "ready_for_demo": report.ready_for_demo,
        "total_duration_ms": report.total_duration_ms,
        "checks": [
            {
                "name": c.name,
                "status": c.status.value,
                "message": c.message,
            }
            for c in report.checks
        ],
    }


@router.post("/runbook/start")
async def start_demo(
    offline_mode: bool = False,
    session_id: Optional[str] = None,
):
    """
    Quick start a demo session with all necessary setup.

    This is a convenience endpoint that:
    1. Creates a new session
    2. Optionally enables offline mode
    3. Resets metrics
    4. Returns all necessary URLs for the demo
    """
    result = await quick_start_demo(
        offline_mode=offline_mode,
        session_id=session_id,
    )
    return result


@router.get("/runbook/environment")
async def get_environment_requirements():
    """
    Get required and optional environment variables.

    Use this to verify your environment is properly configured
    before running the demo.
    """
    import os

    required_status = {}
    for var, description in REQUIRED_ENV_VARS.items():
        required_status[var] = {
            "description": description,
            "set": bool(os.environ.get(var)),
        }

    optional_status = {}
    for var, description in OPTIONAL_ENV_VARS.items():
        value = os.environ.get(var)
        optional_status[var] = {
            "description": description,
            "set": bool(value),
            "value": value if value and "SECRET" not in var and "KEY" not in var else None,
        }

    all_required_set = all(s["set"] for s in required_status.values())

    return {
        "required": required_status,
        "optional": optional_status,
        "all_required_set": all_required_set,
        "recommendation": "Ready to proceed" if all_required_set else "Set missing required variables",
    }
