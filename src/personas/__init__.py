"""
MAESTRO Persona System

Clean, production-ready persona management for AI-powered SDLC workflows.
"""

from .adapter import MaestroPersonaAdapter, MaestroPersonasCompat, get_adapter
from .models import (
    PersonaCategory,
    PersonaDefinition,
    PersonaExecutionResult,
    PersonaStatus,
    ValidationRules,
    WorkflowConfig,
    WorkflowResult,
)
from .lifecycle import (
    # Enums
    PersonaState,
    PrimaryLLM,
    CoreActivity,
    ConfidentialityLevel,
    VALID_STATE_TRANSITIONS,
    # Runtime model
    PersonaRuntime,
    # Exceptions
    PersonaError,
    PersonaNotFoundError,
    InvalidStateTransitionError,
    PersonaAlreadyExistsError,
    ClassificationDowngradeError,
)
from .registry import PersonaRegistry, get_registry

__all__ = [
    # Schema Models (from models.py)
    "PersonaDefinition",
    "PersonaCategory",
    "PersonaStatus",
    "PersonaExecutionResult",
    "ValidationRules",
    "WorkflowConfig",
    "WorkflowResult",
    # Lifecycle Enums (from lifecycle.py)
    "PersonaState",
    "PrimaryLLM",
    "CoreActivity",
    "ConfidentialityLevel",
    "VALID_STATE_TRANSITIONS",
    # Runtime Model (from lifecycle.py)
    "PersonaRuntime",
    # Exceptions (from lifecycle.py)
    "PersonaError",
    "PersonaNotFoundError",
    "InvalidStateTransitionError",
    "PersonaAlreadyExistsError",
    "ClassificationDowngradeError",
    # Registry
    "PersonaRegistry",
    "get_registry",
    # Adapter (for legacy system integration)
    "MaestroPersonaAdapter",
    "MaestroPersonasCompat",
    "get_adapter",
]

__version__ = "3.0.0"
