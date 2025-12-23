"""
Symphony Offline Fallback Mode

EPIC: MD-3902 - Maestro Symphony Demo
Story: MD-3911 - Create Offline Fallback Mode for Demo Resilience

Provides prerecorded conversation and artifact playback when live
dependencies (MS Teams, LLM APIs) are unavailable. Auto-switches
to offline mode on failure detection.
"""

import asyncio
import json
import time
import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import logging

from symphony.models import (
    ArtifactEvent,
    ArtifactType,
    StoryArtifact,
    ArchitectureArtifact,
    CodeArtifact,
    SymphonyTestArtifact,
    WorkflowPhase,
)
from symphony.personas import (
    PersonaRole,
    get_all_personas,
    SARAH_PM,
    MARCUS_ARCHITECT,
    ALEX_DEVELOPER,
    PRIYA_QA,
    HUMAN_PRESENTER,
)

logger = logging.getLogger(__name__)


class FallbackMode(str, Enum):
    """Fallback mode states"""
    LIVE = "live"           # Using live dependencies
    OFFLINE = "offline"     # Using prerecorded playback
    HYBRID = "hybrid"       # Mix of live and cached


class FallbackReason(str, Enum):
    """Reasons for switching to offline mode"""
    MANUAL = "manual"               # User requested offline mode
    TEAMS_UNAVAILABLE = "teams_unavailable"
    LLM_UNAVAILABLE = "llm_unavailable"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    PREFLIGHT_FAILED = "preflight_failed"


@dataclass
class PrerecordedMessage:
    """A prerecorded conversation message"""
    persona_id: str
    display_name: str
    role: str
    content: str
    is_human: bool
    delay_ms: int = 0  # Delay before showing this message
    triggers_artifacts: List[str] = field(default_factory=list)


@dataclass
class PrerecordedArtifact:
    """A prerecorded artifact"""
    artifact_type: ArtifactType
    artifact_id: str
    data: Dict[str, Any]
    delay_ms: int = 0  # Delay after message before showing artifact


@dataclass
class DemoScenario:
    """A complete prerecorded demo scenario"""
    scenario_id: str
    title: str
    description: str
    messages: List[PrerecordedMessage]
    artifacts: Dict[str, List[PrerecordedArtifact]]  # message_index -> artifacts
    duration_estimate_ms: int = 0


# =============================================================================
# Prerecorded Demo Data - "Customer Feedback Portal"
# =============================================================================

DEMO_SCENARIO_FEEDBACK_PORTAL = DemoScenario(
    scenario_id="customer_feedback_portal",
    title="Customer Feedback Portal",
    description="AI team designs and builds a customer feedback portal",
    messages=[
        PrerecordedMessage(
            persona_id="human",
            display_name="Demo Presenter",
            role="Human Facilitator",
            content="Good morning team! Let's discuss building a customer feedback portal for our enterprise clients. We need something that allows customers to submit feedback and our support team to track and respond to it.",
            is_human=True,
            delay_ms=0,
        ),
        PrerecordedMessage(
            persona_id="sarah_pm",
            display_name="Sarah Chen",
            role="Product Manager",
            content="Great idea! I see three key personas we need to address: enterprise admins who configure the system, end-users who submit feedback, and support teams who manage responses. Let me draft the initial requirements focusing on these user journeys.",
            is_human=False,
            delay_ms=3500,
            triggers_artifacts=["story_1", "story_2"],
        ),
        PrerecordedMessage(
            persona_id="marcus_arch",
            display_name="Marcus Williams",
            role="Architect",
            content="While Sarah works on requirements, I'm thinking microservices architecture with a React frontend. We should consider authentication early - SSO integration will be critical for enterprise clients. I'll sketch out the high-level design.",
            is_human=False,
            delay_ms=4200,
            triggers_artifacts=["arch_1"],
        ),
        PrerecordedMessage(
            persona_id="human",
            display_name="Demo Presenter",
            role="Human Facilitator",
            content="What about mobile support? Many of our customers are on the go.",
            is_human=True,
            delay_ms=2800,
        ),
        PrerecordedMessage(
            persona_id="alex_dev",
            display_name="Alex Rivera",
            role="Developer",
            content="I'd recommend React Native for mobile to share code with the web frontend. Let me sketch out the component architecture. We can use a shared API layer that works for both platforms.",
            is_human=False,
            delay_ms=2500,
            triggers_artifacts=["code_1"],
        ),
        PrerecordedMessage(
            persona_id="sarah_pm",
            display_name="Sarah Chen",
            role="Product Manager",
            content="Good point on mobile! I'll add user stories for mobile feedback submission. We should also consider offline support for spotty network conditions - let customers draft feedback and sync when connected.",
            is_human=False,
            delay_ms=3800,
            triggers_artifacts=["story_3", "story_4"],
        ),
        PrerecordedMessage(
            persona_id="priya_qa",
            display_name="Priya Sharma",
            role="QA Lead",
            content="I'm already thinking about our test strategy. API contracts will need comprehensive testing - both happy paths and edge cases. What happens if a user submits feedback with special characters or very long text? I'll draft test scenarios.",
            is_human=False,
            delay_ms=4000,
            triggers_artifacts=["test_1"],
        ),
        PrerecordedMessage(
            persona_id="marcus_arch",
            display_name="Marcus Williams",
            role="Architect",
            content="For the API, I'm proposing REST with OpenAPI spec. We'll have endpoints for feedback CRUD, category management, and analytics. Rate limiting at the gateway level will prevent abuse. Here's the updated architecture.",
            is_human=False,
            delay_ms=4500,
            triggers_artifacts=["arch_2"],
        ),
        PrerecordedMessage(
            persona_id="alex_dev",
            display_name="Alex Rivera",
            role="Developer",
            content="I've got a basic FeedbackService class started. It handles creation, retrieval, and status updates. I'm using async/await throughout for performance. Want me to add the category filtering logic?",
            is_human=False,
            delay_ms=3200,
            triggers_artifacts=["code_2", "code_3"],
        ),
        PrerecordedMessage(
            persona_id="priya_qa",
            display_name="Priya Sharma",
            role="QA Lead",
            content="Alex, I'll need to review those endpoints. I'm setting up contract tests using Pact so we catch API drift early. Also adding load tests - we should handle at least 1000 concurrent submissions without degradation.",
            is_human=False,
            delay_ms=3700,
            triggers_artifacts=["test_2", "test_3"],
        ),
        PrerecordedMessage(
            persona_id="human",
            display_name="Demo Presenter",
            role="Human Facilitator",
            content="This is great progress! Can we get a summary of what we've designed so far?",
            is_human=True,
            delay_ms=2000,
        ),
        PrerecordedMessage(
            persona_id="sarah_pm",
            display_name="Sarah Chen",
            role="Product Manager",
            content="Absolutely! We have 6 user stories covering admin configuration, user submission (web and mobile), support dashboard, and offline sync. Marcus has the microservices architecture, Alex has the core API implementation started, and Priya has our test strategy mapped out. Ready to execute?",
            is_human=False,
            delay_ms=4000,
            triggers_artifacts=["story_5", "story_6"],
        ),
    ],
    artifacts={
        # Artifacts triggered by message index
        "1": [
            PrerecordedArtifact(
                artifact_type=ArtifactType.STORY,
                artifact_id="US-001",
                data={
                    "id": "US-001",
                    "title": "Admin configures feedback categories",
                    "description": "As an enterprise admin, I want to configure feedback categories so that customers can classify their submissions.",
                    "acceptance_criteria": [
                        "Admin can create, edit, delete categories",
                        "Categories support hierarchy (parent/child)",
                        "Changes reflect immediately in customer portal",
                    ],
                    "priority": "high",
                    "status": "defined",
                },
                delay_ms=800,
            ),
            PrerecordedArtifact(
                artifact_type=ArtifactType.STORY,
                artifact_id="US-002",
                data={
                    "id": "US-002",
                    "title": "User submits feedback via web portal",
                    "description": "As an end-user, I want to submit feedback through the web portal so that I can report issues or suggestions.",
                    "acceptance_criteria": [
                        "User can select category from dropdown",
                        "User can add title and detailed description",
                        "User can attach screenshots or files",
                        "User receives confirmation with ticket ID",
                    ],
                    "priority": "high",
                    "status": "defined",
                },
                delay_ms=1200,
            ),
        ],
        "2": [
            PrerecordedArtifact(
                artifact_type=ArtifactType.ARCHITECTURE,
                artifact_id="ARCH-001",
                data={
                    "id": "ARCH-001",
                    "title": "High-Level System Architecture",
                    "diagram_type": "system",
                    "components": [
                        {"name": "API Gateway", "type": "gateway", "description": "Rate limiting, auth, routing"},
                        {"name": "Auth Service", "type": "service", "description": "SSO, JWT tokens"},
                        {"name": "Feedback Service", "type": "service", "description": "Core feedback CRUD"},
                        {"name": "Notification Service", "type": "service", "description": "Email, push notifications"},
                        {"name": "Analytics Service", "type": "service", "description": "Metrics, reporting"},
                        {"name": "PostgreSQL", "type": "database", "description": "Primary data store"},
                        {"name": "Redis", "type": "cache", "description": "Session cache, rate limiting"},
                    ],
                    "connections": [
                        {"from": "API Gateway", "to": "Auth Service"},
                        {"from": "API Gateway", "to": "Feedback Service"},
                        {"from": "Feedback Service", "to": "PostgreSQL"},
                        {"from": "Feedback Service", "to": "Notification Service"},
                        {"from": "Feedback Service", "to": "Analytics Service"},
                    ],
                },
                delay_ms=1500,
            ),
        ],
        "4": [
            PrerecordedArtifact(
                artifact_type=ArtifactType.CODE,
                artifact_id="CODE-001",
                data={
                    "id": "CODE-001",
                    "filename": "feedback_api.py",
                    "language": "python",
                    "content": '''"""Feedback API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])

class FeedbackCreate(BaseModel):
    title: str
    description: str
    category_id: str
    attachments: Optional[List[str]] = None

class FeedbackResponse(BaseModel):
    id: str
    title: str
    status: str
    created_at: str

@router.post("/", response_model=FeedbackResponse)
async def create_feedback(feedback: FeedbackCreate):
    """Create new feedback submission"""
    # Implementation here
    pass

@router.get("/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback(feedback_id: str):
    """Retrieve feedback by ID"""
    pass
''',
                    "line_count": 30,
                },
                delay_ms=1000,
            ),
        ],
        "5": [
            PrerecordedArtifact(
                artifact_type=ArtifactType.STORY,
                artifact_id="US-003",
                data={
                    "id": "US-003",
                    "title": "User submits feedback via mobile app",
                    "description": "As a mobile user, I want to submit feedback from my phone so I can report issues on the go.",
                    "acceptance_criteria": [
                        "Native mobile experience (iOS/Android)",
                        "Camera integration for screenshots",
                        "Offline draft support",
                        "Push notification on response",
                    ],
                    "priority": "medium",
                    "status": "defined",
                },
                delay_ms=800,
            ),
            PrerecordedArtifact(
                artifact_type=ArtifactType.STORY,
                artifact_id="US-004",
                data={
                    "id": "US-004",
                    "title": "Offline feedback synchronization",
                    "description": "As a user with spotty connectivity, I want my drafted feedback to sync when I'm back online.",
                    "acceptance_criteria": [
                        "Feedback saved locally when offline",
                        "Automatic sync on reconnection",
                        "Conflict resolution for edits",
                        "Visual indicator of sync status",
                    ],
                    "priority": "medium",
                    "status": "defined",
                },
                delay_ms=1200,
            ),
        ],
        "6": [
            PrerecordedArtifact(
                artifact_type=ArtifactType.TEST,
                artifact_id="TEST-001",
                data={
                    "id": "TEST-001",
                    "name": "Feedback API Contract Tests",
                    "type": "contract",
                    "scenarios": [
                        {"name": "Create feedback with valid data", "status": "planned"},
                        {"name": "Create feedback with missing required fields", "status": "planned"},
                        {"name": "Create feedback with special characters", "status": "planned"},
                        {"name": "Create feedback with max length description", "status": "planned"},
                        {"name": "Retrieve existing feedback", "status": "planned"},
                        {"name": "Retrieve non-existent feedback returns 404", "status": "planned"},
                    ],
                    "coverage_target": "90%",
                },
                delay_ms=1000,
            ),
        ],
        "7": [
            PrerecordedArtifact(
                artifact_type=ArtifactType.ARCHITECTURE,
                artifact_id="ARCH-002",
                data={
                    "id": "ARCH-002",
                    "title": "API Design - REST Endpoints",
                    "diagram_type": "api",
                    "endpoints": [
                        {"method": "POST", "path": "/api/v1/feedback", "description": "Create feedback"},
                        {"method": "GET", "path": "/api/v1/feedback/{id}", "description": "Get feedback"},
                        {"method": "PUT", "path": "/api/v1/feedback/{id}", "description": "Update feedback"},
                        {"method": "DELETE", "path": "/api/v1/feedback/{id}", "description": "Delete feedback"},
                        {"method": "GET", "path": "/api/v1/feedback", "description": "List feedback with filters"},
                        {"method": "GET", "path": "/api/v1/categories", "description": "List categories"},
                        {"method": "POST", "path": "/api/v1/categories", "description": "Create category"},
                    ],
                    "rate_limits": {
                        "default": "100 req/min",
                        "authenticated": "1000 req/min",
                    },
                },
                delay_ms=1200,
            ),
        ],
        "8": [
            PrerecordedArtifact(
                artifact_type=ArtifactType.CODE,
                artifact_id="CODE-002",
                data={
                    "id": "CODE-002",
                    "filename": "feedback_service.py",
                    "language": "python",
                    "content": '''"""Feedback Service - Core business logic"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from enum import Enum

class FeedbackStatus(Enum):
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    CLOSED = "closed"

@dataclass
class Feedback:
    id: str
    title: str
    description: str
    category_id: str
    status: FeedbackStatus
    created_at: datetime
    updated_at: datetime
    submitter_id: str

class FeedbackService:
    """Service for managing customer feedback"""

    async def create(self, title: str, description: str,
                     category_id: str, submitter_id: str) -> Feedback:
        """Create new feedback submission"""
        feedback = Feedback(
            id=self._generate_id(),
            title=title,
            description=description,
            category_id=category_id,
            status=FeedbackStatus.SUBMITTED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            submitter_id=submitter_id,
        )
        await self._repository.save(feedback)
        await self._notify_support_team(feedback)
        return feedback

    async def update_status(self, feedback_id: str,
                           new_status: FeedbackStatus) -> Feedback:
        """Update feedback status"""
        feedback = await self._repository.get(feedback_id)
        feedback.status = new_status
        feedback.updated_at = datetime.utcnow()
        await self._repository.save(feedback)
        return feedback
''',
                    "line_count": 50,
                },
                delay_ms=800,
            ),
            PrerecordedArtifact(
                artifact_type=ArtifactType.CODE,
                artifact_id="CODE-003",
                data={
                    "id": "CODE-003",
                    "filename": "FeedbackForm.tsx",
                    "language": "typescript",
                    "content": '''// FeedbackForm.tsx - React component for feedback submission
import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { feedbackApi } from '../api/feedback';

interface FeedbackFormProps {
  categories: Category[];
  onSuccess: (feedbackId: string) => void;
}

export const FeedbackForm: React.FC<FeedbackFormProps> = ({
  categories,
  onSuccess,
}) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [categoryId, setCategoryId] = useState('');

  const mutation = useMutation({
    mutationFn: feedbackApi.create,
    onSuccess: (data) => onSuccess(data.id),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate({ title, description, categoryId });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Feedback title"
        className="w-full p-2 border rounded"
      />
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Describe your feedback..."
        className="w-full p-2 border rounded h-32"
      />
      <select
        value={categoryId}
        onChange={(e) => setCategoryId(e.target.value)}
        className="w-full p-2 border rounded"
      >
        {categories.map((cat) => (
          <option key={cat.id} value={cat.id}>{cat.name}</option>
        ))}
      </select>
      <button type="submit" className="px-4 py-2 bg-blue-500 text-white rounded">
        Submit Feedback
      </button>
    </form>
  );
};
''',
                    "line_count": 55,
                },
                delay_ms=1500,
            ),
        ],
        "9": [
            PrerecordedArtifact(
                artifact_type=ArtifactType.TEST,
                artifact_id="TEST-002",
                data={
                    "id": "TEST-002",
                    "name": "Load Test Scenarios",
                    "type": "performance",
                    "scenarios": [
                        {"name": "1000 concurrent submissions", "target_rps": 1000, "p99_latency_ms": 500},
                        {"name": "Sustained load (10 min)", "target_rps": 500, "error_rate_max": 0.1},
                        {"name": "Spike test (2x baseline)", "target_rps": 2000, "recovery_time_s": 30},
                    ],
                },
                delay_ms=800,
            ),
            PrerecordedArtifact(
                artifact_type=ArtifactType.TEST,
                artifact_id="TEST-003",
                data={
                    "id": "TEST-003",
                    "name": "Pact Contract Tests",
                    "type": "contract",
                    "provider": "FeedbackService",
                    "consumer": "WebPortal",
                    "interactions": [
                        {"description": "POST /feedback creates new entry", "status": "defined"},
                        {"description": "GET /feedback/{id} returns feedback", "status": "defined"},
                        {"description": "PUT /feedback/{id}/status updates status", "status": "defined"},
                    ],
                },
                delay_ms=1200,
            ),
        ],
        "11": [
            PrerecordedArtifact(
                artifact_type=ArtifactType.STORY,
                artifact_id="US-005",
                data={
                    "id": "US-005",
                    "title": "Support team dashboard",
                    "description": "As a support team member, I want a dashboard to view and manage all feedback submissions.",
                    "acceptance_criteria": [
                        "List view with filtering and sorting",
                        "Status updates with audit trail",
                        "Assignment to team members",
                        "Response templates",
                    ],
                    "priority": "high",
                    "status": "defined",
                },
                delay_ms=800,
            ),
            PrerecordedArtifact(
                artifact_type=ArtifactType.STORY,
                artifact_id="US-006",
                data={
                    "id": "US-006",
                    "title": "Analytics and reporting",
                    "description": "As an admin, I want analytics on feedback trends to identify common issues.",
                    "acceptance_criteria": [
                        "Dashboard with key metrics",
                        "Category breakdown charts",
                        "Response time tracking",
                        "Export to CSV/PDF",
                    ],
                    "priority": "low",
                    "status": "defined",
                },
                delay_ms=1200,
            ),
        ],
    },
    duration_estimate_ms=45000,  # ~45 seconds total
)


# =============================================================================
# Fallback Manager
# =============================================================================

class OfflineFallbackManager:
    """
    Manages offline fallback mode for Symphony demos.

    Detects failures and automatically switches to prerecorded playback
    when live dependencies (MS Teams, LLM APIs) become unavailable.
    """

    def __init__(self):
        self.mode: FallbackMode = FallbackMode.LIVE
        self.fallback_reason: Optional[FallbackReason] = None
        self.fallback_started_at: Optional[datetime] = None
        self.failure_count: int = 0
        self.failure_threshold: int = 3  # Auto-switch after N failures
        self.available_scenarios: Dict[str, DemoScenario] = {
            DEMO_SCENARIO_FEEDBACK_PORTAL.scenario_id: DEMO_SCENARIO_FEEDBACK_PORTAL,
        }
        self.active_playback: Optional["DemoPlayback"] = None
        self._health_checks: Dict[str, bool] = {
            "teams_api": True,
            "llm_api": True,
            "websocket": True,
        }

    def get_status(self) -> Dict[str, Any]:
        """Get current fallback status"""
        return {
            "mode": self.mode.value,
            "fallback_reason": self.fallback_reason.value if self.fallback_reason else None,
            "fallback_started_at": self.fallback_started_at.isoformat() if self.fallback_started_at else None,
            "failure_count": self.failure_count,
            "health_checks": self._health_checks.copy(),
            "available_scenarios": list(self.available_scenarios.keys()),
            "active_playback": self.active_playback.get_status() if self.active_playback else None,
        }

    def record_failure(self, reason: FallbackReason) -> bool:
        """
        Record a failure event. Returns True if auto-switched to offline mode.
        """
        self.failure_count += 1
        logger.warning(f"Failure recorded: {reason.value} (count: {self.failure_count})")

        # Update health check
        if reason == FallbackReason.TEAMS_UNAVAILABLE:
            self._health_checks["teams_api"] = False
        elif reason == FallbackReason.LLM_UNAVAILABLE:
            self._health_checks["llm_api"] = False

        # Auto-switch if threshold exceeded
        if self.failure_count >= self.failure_threshold and self.mode == FallbackMode.LIVE:
            self.switch_to_offline(reason)
            return True
        return False

    def record_success(self):
        """Record a successful operation, reducing failure count"""
        if self.failure_count > 0:
            self.failure_count -= 1
        # Restore health checks gradually
        self._health_checks["teams_api"] = True
        self._health_checks["llm_api"] = True

    def switch_to_offline(self, reason: FallbackReason):
        """Switch to offline fallback mode"""
        logger.info(f"Switching to offline mode: {reason.value}")
        self.mode = FallbackMode.OFFLINE
        self.fallback_reason = reason
        self.fallback_started_at = datetime.utcnow()

    def switch_to_live(self):
        """Switch back to live mode"""
        logger.info("Switching back to live mode")
        self.mode = FallbackMode.LIVE
        self.fallback_reason = None
        self.fallback_started_at = None
        self.failure_count = 0
        self._health_checks = {k: True for k in self._health_checks}
        if self.active_playback:
            self.active_playback.stop()
            self.active_playback = None

    def is_offline(self) -> bool:
        """Check if currently in offline mode"""
        return self.mode == FallbackMode.OFFLINE

    def get_scenario(self, scenario_id: str) -> Optional[DemoScenario]:
        """Get a prerecorded scenario by ID"""
        return self.available_scenarios.get(scenario_id)

    def list_scenarios(self) -> List[Dict[str, Any]]:
        """List available demo scenarios"""
        return [
            {
                "scenario_id": s.scenario_id,
                "title": s.title,
                "description": s.description,
                "duration_estimate_ms": s.duration_estimate_ms,
                "message_count": len(s.messages),
            }
            for s in self.available_scenarios.values()
        ]

    def start_playback(
        self,
        scenario_id: str,
        on_message: Callable[[PrerecordedMessage], None],
        on_artifact: Callable[[PrerecordedArtifact], None],
    ) -> Optional["DemoPlayback"]:
        """Start playing a prerecorded scenario"""
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            logger.error(f"Scenario not found: {scenario_id}")
            return None

        self.active_playback = DemoPlayback(
            scenario=scenario,
            on_message=on_message,
            on_artifact=on_artifact,
        )
        return self.active_playback


class DemoPlayback:
    """
    Plays back a prerecorded demo scenario with realistic timing.
    """

    def __init__(
        self,
        scenario: DemoScenario,
        on_message: Callable[[PrerecordedMessage], None],
        on_artifact: Callable[[PrerecordedArtifact], None],
    ):
        self.scenario = scenario
        self.on_message = on_message
        self.on_artifact = on_artifact
        self.current_index: int = 0
        self.is_playing: bool = False
        self.is_paused: bool = False
        self.started_at: Optional[datetime] = None
        self.playback_task: Optional[asyncio.Task] = None
        self.speed_multiplier: float = 1.0  # 1.0 = normal speed

    def get_status(self) -> Dict[str, Any]:
        """Get playback status"""
        return {
            "scenario_id": self.scenario.scenario_id,
            "current_index": self.current_index,
            "total_messages": len(self.scenario.messages),
            "is_playing": self.is_playing,
            "is_paused": self.is_paused,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "speed_multiplier": self.speed_multiplier,
            "progress_percent": (self.current_index / len(self.scenario.messages)) * 100 if self.scenario.messages else 0,
        }

    async def start(self):
        """Start playback"""
        if self.is_playing:
            logger.warning("Playback already running")
            return

        self.is_playing = True
        self.is_paused = False
        self.started_at = datetime.utcnow()
        self.playback_task = asyncio.create_task(self._playback_loop())
        logger.info(f"Started playback: {self.scenario.scenario_id}")

    async def _playback_loop(self):
        """Main playback loop"""
        try:
            while self.current_index < len(self.scenario.messages):
                if not self.is_playing:
                    break

                # Wait while paused
                while self.is_paused and self.is_playing:
                    await asyncio.sleep(0.1)

                if not self.is_playing:
                    break

                message = self.scenario.messages[self.current_index]

                # Apply delay before message (simulates natural conversation flow)
                delay_seconds = (message.delay_ms / 1000) / self.speed_multiplier
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)

                if not self.is_playing:
                    break

                # Emit message
                try:
                    self.on_message(message)
                except Exception as e:
                    logger.error(f"Error in message callback: {e}")

                # Emit associated artifacts with their delays
                message_index_str = str(self.current_index)
                if message_index_str in self.scenario.artifacts:
                    for artifact in self.scenario.artifacts[message_index_str]:
                        artifact_delay = (artifact.delay_ms / 1000) / self.speed_multiplier
                        if artifact_delay > 0:
                            await asyncio.sleep(artifact_delay)
                        if not self.is_playing:
                            break
                        try:
                            self.on_artifact(artifact)
                        except Exception as e:
                            logger.error(f"Error in artifact callback: {e}")

                self.current_index += 1

            logger.info(f"Playback completed: {self.scenario.scenario_id}")
        except asyncio.CancelledError:
            logger.info("Playback cancelled")
        except Exception as e:
            logger.error(f"Playback error: {e}")
        finally:
            self.is_playing = False

    def pause(self):
        """Pause playback"""
        self.is_paused = True
        logger.info("Playback paused")

    def resume(self):
        """Resume playback"""
        self.is_paused = False
        logger.info("Playback resumed")

    def stop(self):
        """Stop playback"""
        self.is_playing = False
        if self.playback_task:
            self.playback_task.cancel()
        logger.info("Playback stopped")

    def skip_to(self, message_index: int):
        """Skip to a specific message index"""
        if 0 <= message_index < len(self.scenario.messages):
            self.current_index = message_index
            logger.info(f"Skipped to message {message_index}")

    def set_speed(self, multiplier: float):
        """Set playback speed (0.5 = half speed, 2.0 = double speed)"""
        self.speed_multiplier = max(0.25, min(4.0, multiplier))
        logger.info(f"Playback speed set to {self.speed_multiplier}x")


# =============================================================================
# Health Check Utilities
# =============================================================================

async def check_teams_health(timeout_seconds: float = 5.0) -> bool:
    """Check if MS Teams API is accessible"""
    # In a real implementation, this would ping the Graph API
    # For demo purposes, we simulate the check
    try:
        # Simulate network call
        await asyncio.sleep(0.1)
        return True  # Assume healthy unless configured otherwise
    except Exception as e:
        logger.error(f"Teams health check failed: {e}")
        return False


async def check_llm_health(timeout_seconds: float = 5.0) -> bool:
    """Check if LLM API is accessible"""
    # In a real implementation, this would ping the Claude API
    try:
        await asyncio.sleep(0.1)
        return True
    except Exception as e:
        logger.error(f"LLM health check failed: {e}")
        return False


async def run_preflight_checks() -> Dict[str, Any]:
    """
    Run all preflight checks for demo readiness.
    Returns status of each check.
    """
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {},
        "overall_status": "pass",
    }

    # Check Teams
    teams_ok = await check_teams_health()
    results["checks"]["teams_api"] = {
        "status": "pass" if teams_ok else "fail",
        "message": "MS Teams API accessible" if teams_ok else "MS Teams API unavailable",
    }

    # Check LLM
    llm_ok = await check_llm_health()
    results["checks"]["llm_api"] = {
        "status": "pass" if llm_ok else "fail",
        "message": "LLM API accessible" if llm_ok else "LLM API unavailable",
    }

    # Check offline scenarios available
    fallback_mgr = get_fallback_manager()
    scenarios = fallback_mgr.list_scenarios()
    results["checks"]["offline_scenarios"] = {
        "status": "pass" if scenarios else "fail",
        "message": f"{len(scenarios)} offline scenarios available",
        "scenarios": scenarios,
    }

    # Overall status
    if not teams_ok or not llm_ok:
        results["overall_status"] = "degraded"
        results["recommendation"] = "Consider using offline fallback mode"
    if not teams_ok and not llm_ok:
        results["overall_status"] = "fail"
        results["recommendation"] = "Live mode unavailable - use offline fallback"

    return results


# =============================================================================
# Singleton Instance
# =============================================================================

_fallback_manager: Optional[OfflineFallbackManager] = None


def get_fallback_manager() -> OfflineFallbackManager:
    """Get singleton OfflineFallbackManager instance"""
    global _fallback_manager
    if _fallback_manager is None:
        _fallback_manager = OfflineFallbackManager()
    return _fallback_manager


def reset_fallback_manager():
    """Reset the fallback manager (for testing)"""
    global _fallback_manager
    _fallback_manager = None
