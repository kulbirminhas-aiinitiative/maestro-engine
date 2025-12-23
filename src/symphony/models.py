"""
Symphony Data Models

EPIC: MD-3902 - Maestro Symphony Demo
Story: MD-3908 - Wire Artifact Streaming via WebSocket

Pydantic models for Symphony artifact streaming.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, ConfigDict, model_validator
import uuid

from symphony.agent_modes import AgentMode


class ArtifactType(str, Enum):
    """Types of artifacts generated during Symphony demo"""
    STORY = "stories"
    ARCHITECTURE = "architecture"
    CODE = "code"
    TEST = "tests"


class StoryArtifact(BaseModel):
    """User story artifact generated from conversation"""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: f"story-{uuid.uuid4().hex[:8]}")
    title: str
    story_id: str = Field(alias="storyId")
    description: str
    acceptance_criteria: List[str] = Field(default_factory=list, alias="acceptanceCriteria")
    priority: str = "medium"
    status: str = "pending"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), alias="createdAt")


class ArchitectureArtifact(BaseModel):
    """Architecture diagram artifact"""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: f"arch-{uuid.uuid4().hex[:8]}")
    title: str
    diagram_type: str = Field(alias="diagramType")
    mermaid_code: str = Field(alias="mermaidCode")
    description: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), alias="createdAt")


class CodeArtifact(BaseModel):
    """Code artifact generated from conversation"""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: f"code-{uuid.uuid4().hex[:8]}")
    title: str
    filename: str
    code: str
    language: str
    lines: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), alias="createdAt")

    @model_validator(mode='after')
    def compute_lines(self) -> 'CodeArtifact':
        if self.lines == 0:
            self.lines = len(self.code.split('\n'))
        return self


class SymphonyTestArtifact(BaseModel):
    """Test case artifact (named to avoid pytest collection)"""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: f"test-{uuid.uuid4().hex[:8]}")
    title: str
    name: str
    suite: Optional[str] = None
    type: str = "unit"  # unit, integration, e2e, contract
    status: str = "pending"  # pending, passed, failed
    code: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), alias="createdAt")


# Alias for backwards compatibility
TestArtifact = SymphonyTestArtifact


class ArtifactEvent(BaseModel):
    """Event payload for artifact streaming"""
    model_config = ConfigDict(populate_by_name=True)

    event_type: str = Field(alias="eventType")  # artifact_created, artifact_updated
    artifact_type: ArtifactType = Field(alias="artifactType")
    artifact: dict
    session_id: str = Field(alias="sessionId")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class WorkflowPhase(BaseModel):
    """SDLC workflow phase status"""
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    status: str = "pending"  # pending, running, completed, error
    progress: int = 0
    current_activity: Optional[str] = Field(None, alias="currentActivity")


class WorkflowProgress(BaseModel):
    """Overall workflow progress"""
    model_config = ConfigDict(populate_by_name=True)

    phases: List[WorkflowPhase]
    current_phase: str = Field(alias="currentPhase")
    overall_progress: int = Field(0, alias="overallProgress")


class SymphonySession(BaseModel):
    """Symphony demo session state"""
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId")
    channel_id: str = Field(alias="channelId")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), alias="createdAt")
    workflow_status: str = Field("ready", alias="workflowStatus")
    artifacts: dict = Field(default_factory=lambda: {
        "stories": [],
        "architecture": [],
        "code": [],
        "tests": []
    })
    workflow_progress: Optional[WorkflowProgress] = Field(None, alias="workflowProgress")


class KickstartRequest(BaseModel):
    """Request to kickstart Symphony workflow with configurable agent modes"""
    model_config = ConfigDict(populate_by_name=True)

    requirement: str = Field(..., description="The project requirement to build")
    channel_id: Optional[str] = Field(None, alias="channelId")

    # Agent mode configuration
    global_mode: Optional[AgentMode] = Field(
        None,
        alias="globalMode",
        description="Override mode for all personas (simple, full, full_rag)"
    )
    persona_modes: Optional[Dict[str, AgentMode]] = Field(
        None,
        alias="personaModes",
        description="Per-persona mode overrides: {sarah: 'simple', alex: 'full_rag'}"
    )

    # RAG configuration
    rag_enabled: Optional[bool] = Field(
        None,
        alias="ragEnabled",
        description="Explicit RAG toggle. None = auto (enabled for full_rag mode)"
    )
    rag_config: Optional[Dict[str, Any]] = Field(
        None,
        alias="ragConfig",
        description="RAG configuration: {top_k: 5, min_score: 0.7}"
    )


class KickstartResponse(BaseModel):
    """Response from kickstart endpoint"""
    session_id: str = Field(alias="sessionId")
    status: str
    message: str
