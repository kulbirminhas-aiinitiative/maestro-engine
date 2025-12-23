"""
MAESTRO Persona Lifecycle Management (PLMS-001)

Runtime lifecycle tracking models for personas. These complement the
PersonaDefinition schema (models.py) by tracking execution state.

- PersonaDefinition (models.py) = Static configuration loaded from JSON
- PersonaRuntime (lifecycle.py) = Dynamic runtime state during execution
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from typing import Dict, List, Optional
from uuid import uuid4


class PersonaState(str, Enum):
    """
    Lifecycle states for a persona at runtime.

    State Machine:
        CREATING -> EVOLVING -> MATURE -> ARCHIVED
                        |           |
                        v           v
                      RETIRED    RETIRED

    RETIRED is terminal - no transitions out.
    """

    CREATING = "creating"     # Initial state, being configured
    EVOLVING = "evolving"     # Learning and improving
    MATURE = "mature"         # Stable, high quality
    ARCHIVED = "archived"     # Inactive, preserved
    RETIRED = "retired"       # Terminal state, soft-deleted

    def __str__(self) -> str:
        return self.value


class PrimaryLLM(str, Enum):
    """Supported LLM providers for personas."""

    CLAUDE = "claude"
    GEMINI = "gemini"
    GPT = "gpt"
    LLAMA = "llama"

    def __str__(self) -> str:
        return self.value


class CoreActivity(str, Enum):
    """Primary activity types for personas."""

    CODE = "code"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    SECURITY = "security"
    DEVOPS = "devops"

    def __str__(self) -> str:
        return self.value


class ConfidentialityLevel(IntEnum):
    """
    Confidentiality levels for knowledge classification.

    CRITICAL: Classification can only ESCALATE, never downgrade.
    """

    PUBLIC = 1       # Can promote to domain, can fine-tune
    INTERNAL = 2     # Can promote to domain, can fine-tune
    CONFIDENTIAL = 3 # NEVER promotes, NEVER fine-tunes, RAG-only
    RESTRICTED = 4   # NEVER promotes, NEVER fine-tunes, immediate purge

    def can_promote_to_domain(self) -> bool:
        """
        Check if this level allows promotion to domain layer.

        Only PUBLIC and INTERNAL data can be promoted - CONFIDENTIAL
        and RESTRICTED data must never leak to domain layer.
        """
        return self <= ConfidentialityLevel.INTERNAL

    def can_enter_finetune_pipeline(self) -> bool:
        """
        Check if this level allows entry to fine-tune pipeline.

        Only PUBLIC and INTERNAL data can be used for fine-tuning -
        CONFIDENTIAL/RESTRICTED could embed secrets into model weights.
        """
        return self <= ConfidentialityLevel.INTERNAL

    def requires_immediate_purge(self) -> bool:
        """Check if this level requires immediate purge on project end."""
        return self == ConfidentialityLevel.RESTRICTED

    def __str__(self) -> str:
        return self.name


# Valid state transitions
VALID_STATE_TRANSITIONS: Dict[PersonaState, List[PersonaState]] = {
    PersonaState.CREATING: [PersonaState.EVOLVING, PersonaState.ARCHIVED, PersonaState.RETIRED],
    PersonaState.EVOLVING: [PersonaState.MATURE, PersonaState.ARCHIVED, PersonaState.RETIRED],
    PersonaState.MATURE: [PersonaState.EVOLVING, PersonaState.ARCHIVED, PersonaState.RETIRED],
    PersonaState.ARCHIVED: [PersonaState.EVOLVING, PersonaState.RETIRED],
    PersonaState.RETIRED: [],  # Terminal state
}


@dataclass
class PersonaRuntime:
    """
    Runtime state for a persona during execution.

    This tracks the dynamic state of a persona instance, complementing
    the static PersonaDefinition configuration.

    Attributes:
        persona_id: Links to PersonaDefinition.persona_id
        instance_id: Unique ID for this runtime instance
        state: Current lifecycle state
        quality_score: Dynamic quality metric (0.0-1.0)
        tasks_completed: Count of completed tasks
        active_projects: Projects this persona is currently working on
    """

    persona_id: str
    name: str
    primary_llm: PrimaryLLM
    core_activity: CoreActivity
    description: str = ""
    model_version: str = "claude-3-5-sonnet-20241022"

    # Auto-generated
    instance_id: str = field(default_factory=lambda: str(uuid4()))
    state: PersonaState = PersonaState.CREATING

    # Runtime metrics
    quality_score: float = 0.5
    tasks_completed: int = 0
    domain_expertise: List[str] = field(default_factory=list)
    active_projects: List[str] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)

    # Extensible metadata
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        """Validate and normalize fields after initialization."""
        if not self.persona_id:
            raise ValueError("persona_id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")

        # Ensure enums are correct type
        if isinstance(self.state, str):
            self.state = PersonaState(self.state)
        if isinstance(self.primary_llm, str):
            self.primary_llm = PrimaryLLM(self.primary_llm)
        if isinstance(self.core_activity, str):
            self.core_activity = CoreActivity(self.core_activity)

    def can_transition_to(self, target_state: PersonaState) -> bool:
        """Check if transition to target state is valid."""
        valid_targets = VALID_STATE_TRANSITIONS.get(self.state, [])
        return target_state in valid_targets

    def transition_to(self, target_state: PersonaState, reason: str = "") -> None:
        """
        Transition to a new state.

        Raises:
            InvalidStateTransitionError: If transition is not allowed.
        """
        if not self.can_transition_to(target_state):
            raise InvalidStateTransitionError(
                str(self.state), str(target_state),
                f"Invalid transition for persona {self.persona_id}"
            )

        # Record transition in metadata
        if "state_history" not in self.metadata:
            self.metadata["state_history"] = []
        self.metadata["state_history"].append({
            "from": str(self.state),
            "to": str(target_state),
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        })

        self.state = target_state
        self.last_active = datetime.utcnow()

    def update_quality(self, score: float) -> None:
        """Update quality score (0.0-1.0)."""
        if not 0.0 <= score <= 1.0:
            raise ValueError("quality_score must be between 0.0 and 1.0")
        self.quality_score = score
        self.last_active = datetime.utcnow()

    def increment_tasks(self, count: int = 1) -> None:
        """Increment completed task count."""
        if count < 0:
            raise ValueError("count cannot be negative")
        self.tasks_completed += count
        self.last_active = datetime.utcnow()

    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            "persona_id": self.persona_id,
            "instance_id": self.instance_id,
            "name": self.name,
            "description": self.description,
            "primary_llm": str(self.primary_llm),
            "model_version": self.model_version,
            "core_activity": str(self.core_activity),
            "state": str(self.state),
            "quality_score": self.quality_score,
            "tasks_completed": self.tasks_completed,
            "domain_expertise": self.domain_expertise,
            "active_projects": self.active_projects,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PersonaRuntime":
        """Create from dictionary."""
        data = data.copy()
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "last_active" in data and isinstance(data["last_active"], str):
            data["last_active"] = datetime.fromisoformat(data["last_active"])
        return cls(**data)


# =============================================================================
# Exceptions
# =============================================================================

class PersonaError(Exception):
    """Base exception for persona operations."""

    def __init__(self, message: str = "A persona error occurred"):
        self.message = message
        super().__init__(message)


class PersonaNotFoundError(PersonaError):
    """Raised when a persona is not found."""

    def __init__(self, persona_id: str, message: Optional[str] = None):
        self.persona_id = persona_id
        super().__init__(message or f"Persona not found: {persona_id}")


class InvalidStateTransitionError(PersonaError):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, from_state: str, to_state: str, message: Optional[str] = None):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            message or f"Invalid state transition: {from_state} -> {to_state}"
        )


class PersonaAlreadyExistsError(PersonaError):
    """Raised when trying to create a persona that already exists."""

    def __init__(self, persona_id: str, message: Optional[str] = None):
        self.persona_id = persona_id
        super().__init__(message or f"Persona already exists: {persona_id}")


class ClassificationDowngradeError(PersonaError):
    """Raised when attempting to downgrade confidentiality classification."""

    def __init__(
        self,
        current_level: int,
        requested_level: int,
        message: Optional[str] = None
    ):
        self.current_level = current_level
        self.requested_level = requested_level
        super().__init__(
            message or f"Cannot downgrade classification from {current_level} to {requested_level}"
        )
