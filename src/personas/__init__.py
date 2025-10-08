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
    WorkflowConfig,
    WorkflowResult,
)
from .registry import PersonaRegistry, get_registry

__all__ = [
    # Models
    "PersonaDefinition",
    "PersonaCategory",
    "PersonaStatus",
    "PersonaExecutionResult",
    "WorkflowConfig",
    "WorkflowResult",
    # Registry
    "PersonaRegistry",
    "get_registry",
    # Adapter (for legacy system integration)
    "MaestroPersonaAdapter",
    "MaestroPersonasCompat",
    "get_adapter",
]

__version__ = "3.0.0"
