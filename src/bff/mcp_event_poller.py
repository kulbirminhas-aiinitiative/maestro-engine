#!/usr/bin/env python3
"""
MCP Event Poller for Real-Time Guardian Workflow Progress
Polls MCP cache for workflow events and maps them to SDLC phases
"""

import asyncio
import logging

# Import MCP cache from maestro-engine (now in same repo)
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Add parent directory to path to access maestro_mcp
sys.path.insert(0, str(Path(__file__).parent.parent))
from maestro_mcp.mcp_cache_config import get_mcp_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPEventPoller:
    """
    Polls MCP cache for workflow events and maps to SDLC phases
    Sends real-time progress updates via callback
    """

    def __init__(self, session_id: str, on_event: Callable):
        self.session_id = session_id
        self.on_event = on_event
        self.mcp_cache = get_mcp_cache()
        self.processed_events = set()
        self.phase_progress = defaultdict(int)
        self.file_count_by_phase = defaultdict(int)
        self.is_polling = False

    # Event type to SDLC phase mapping
    EVENT_PHASE_MAP = {
        "team_initialization": ("requirements", "start"),
        "workflow_start": ("requirements", "progress", 25),
        "prompt_generated": ("requirements", "progress", 50),
        "unified_tools_start": ("architecture", "start"),
        "tool_execution_start": ("implementation", "start"),
        "utcp_call_start": ("implementation", "start"),
        "file_created": ("implementation", "file"),  # Special: increment progress
        "unified_tools_complete": ("implementation", "progress", 80),
        "utcp_call_complete": ("implementation", "progress", 85),
        "quality_validation_started": ("testing", "start"),
        "quality_validation_complete": ("testing", "complete"),
        "template_extraction_started": ("deployment", "start"),
        "git_template_publishing_started": ("deployment", "progress", 50),
        "git_template_published": ("deployment", "progress", 90),
        "workflow_complete": ("deployment", "complete"),
    }

    # Phase sequence for tracking
    PHASE_SEQUENCE = ["requirements", "architecture", "implementation", "testing", "deployment"]

    async def start_polling(self, poll_interval: float = 2.0, max_duration: int = 600):
        """Start polling MCP cache for events"""
        self.is_polling = True
        start_time = asyncio.get_event_loop().time()

        logger.info(f"📡 Started MCP event polling for session: {self.session_id}")

        try:
            while self.is_polling:
                current_time = asyncio.get_event_loop().time()
                if (current_time - start_time) > max_duration:
                    logger.warning(f"⏱️ Polling timeout after {max_duration}s")
                    break

                await self._poll_events()
                await asyncio.sleep(poll_interval)

        except Exception as e:
            logger.error(f"Polling error: {e}", exc_info=True)
        finally:
            logger.info("🛑 Stopped MCP event polling")

    def stop_polling(self):
        """Stop the polling loop"""
        self.is_polling = False

    async def _poll_events(self):
        """Poll for new events and process them"""
        try:
            # Get all events for this session from MCP cache
            events = self.mcp_cache.get_all_workflow_events(self.session_id)

            # Find new events (not yet processed)
            new_events = []
            for event in events:
                event_id = self._get_event_id(event)
                if event_id not in self.processed_events:
                    new_events.append(event)
                    self.processed_events.add(event_id)

            # Process new events
            for event in new_events:
                await self._process_event(event)

        except Exception as e:
            logger.error(f"Failed to poll events: {e}")

    def _get_event_id(self, event: Dict[str, Any]) -> str:
        """Generate unique event ID"""
        return f"{event.get('type', 'unknown')}_{event.get('timestamp', '')}"

    async def _process_event(self, event: Dict[str, Any]):
        """Process a single event and emit phase update"""
        event_type = event.get("type", "unknown")

        logger.info(f"📥 Event: {event_type}")

        # Map event to phase
        phase_info = self.EVENT_PHASE_MAP.get(event_type)

        if not phase_info:
            logger.debug(f"No phase mapping for event: {event_type}")
            return

        phase_id = phase_info[0]
        action = phase_info[1]

        # Handle different actions
        if action == "start":
            await self._emit_phase_start(phase_id, event)

        elif action == "progress":
            progress = phase_info[2] if len(phase_info) > 2 else 50
            await self._emit_phase_progress(phase_id, progress, event)

        elif action == "complete":
            await self._emit_phase_complete(phase_id, event)

        elif action == "file":
            await self._handle_file_created(event)

    async def _emit_phase_start(self, phase_id: str, event: Dict[str, Any]):
        """Emit phase start event"""
        # Mark all previous phases as complete
        phase_idx = self.PHASE_SEQUENCE.index(phase_id)
        for prev_phase in self.PHASE_SEQUENCE[:phase_idx]:
            if self.phase_progress[prev_phase] < 100:
                await self._emit_phase_complete(prev_phase, event)

        self.phase_progress[phase_id] = 0

        await self.on_event(
            {
                "type": "phase_start",
                "phase": phase_id,
                "message": f"Starting {phase_id}...",
                "timestamp": event.get("timestamp", datetime.now().isoformat()),
            }
        )

    async def _emit_phase_progress(self, phase_id: str, progress: int, event: Dict[str, Any]):
        """Emit phase progress event"""
        self.phase_progress[phase_id] = max(self.phase_progress[phase_id], progress)

        await self.on_event(
            {
                "type": "phase_progress",
                "phase": phase_id,
                "progress": progress,
                "message": event.get("message", f"{phase_id}: {progress}%"),
                "timestamp": event.get("timestamp", datetime.now().isoformat()),
            }
        )

    async def _emit_phase_complete(self, phase_id: str, event: Dict[str, Any]):
        """Emit phase complete event"""
        self.phase_progress[phase_id] = 100

        await self.on_event(
            {
                "type": "phase_complete",
                "phase": phase_id,
                "duration": event.get("execution_time", 0),
                "timestamp": event.get("timestamp", datetime.now().isoformat()),
            }
        )

    async def _handle_file_created(self, event: Dict[str, Any]):
        """Handle file creation event - map to appropriate phase"""
        file_path = event.get("file_path", "")
        file_name = file_path.split("/")[-1] if file_path else ""

        # Classify file into SDLC phase
        phase = self._classify_file(file_path)
        self.file_count_by_phase[phase] += 1

        # Calculate progress for implementation phase based on file count
        if phase == "implementation":
            # Assume ~10 files for full implementation
            file_progress = min(20 + (self.file_count_by_phase[phase] * 7), 90)
            self.phase_progress["implementation"] = max(
                self.phase_progress["implementation"], file_progress
            )

            await self.on_event(
                {
                    "type": "phase_progress",
                    "phase": "implementation",
                    "progress": file_progress,
                    "message": f"Generated: {file_name}",
                    "file": {"path": file_path, "phase": phase},
                    "timestamp": event.get("timestamp", datetime.now().isoformat()),
                }
            )

        # Send file artifact notification
        await self.on_event(
            {
                "type": "file_generated",
                "phase": phase,
                "file": {"path": file_path, "name": file_name},
                "timestamp": event.get("timestamp", datetime.now().isoformat()),
            }
        )

    def _classify_file(self, file_path: str) -> str:
        """Classify file into SDLC phase based on path/extension"""
        file_lower = file_path.lower()

        # Requirements
        if any(keyword in file_lower for keyword in ["requirement", "analysis", "spec.md", "prd"]):
            return "requirements"

        # Architecture
        if any(
            keyword in file_lower for keyword in ["architecture", "design", "diagram", ".drawio"]
        ):
            return "architecture"

        # Testing
        if any(
            keyword in file_lower for keyword in ["test", "__tests__", ".test.", ".spec.", "qa"]
        ):
            return "testing"

        # Deployment
        if any(
            keyword in file_lower
            for keyword in ["dockerfile", "docker-compose", ".yml", ".yaml", "deploy", "ci/cd"]
        ):
            return "deployment"

        # Default to implementation
        return "implementation"

    def get_progress_summary(self) -> Dict[str, Any]:
        """Get current progress summary"""
        return {
            "phases": dict(self.phase_progress),
            "files_by_phase": dict(self.file_count_by_phase),
            "total_events": len(self.processed_events),
            "is_polling": self.is_polling,
        }
