"""
Symphony Agent Modes Configuration

EPIC: MD-4123 - Symphony Real LLM Integration
Story: Configurable Agent Modes for Workflow Personas

Defines three execution modes for Symphony workflow personas:
- SIMPLE: Basic LLM with concise system prompt (fast, minimal context)
- FULL: Detailed system prompt with full context and schema
- FULL_RAG: Full prompt enhanced with RAG-retrieved context
"""

import os
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AgentMode(str, Enum):
    """Agent execution modes with varying complexity and context"""
    SIMPLE = "simple"      # Mode 1: Basic LLM with concise system prompt
    FULL = "full"          # Mode 2: Detailed prompt with full context and schema
    FULL_RAG = "full_rag"  # Mode 3: Full prompt + RAG-enhanced context injection


class WorkflowModeConfig(BaseModel):
    """
    Configuration for workflow execution modes.

    Supports global mode override and per-persona overrides.
    RAG can be explicitly enabled/disabled or auto-determined from mode.
    """
    global_mode: Optional[AgentMode] = Field(
        None,
        description="Override mode for all personas"
    )
    persona_modes: Dict[str, AgentMode] = Field(
        default_factory=dict,
        description="Per-persona mode overrides: {sarah: 'simple', alex: 'full_rag'}"
    )
    rag_enabled: Optional[bool] = Field(
        None,
        description="Explicit RAG toggle. None = auto (enabled for FULL_RAG mode)"
    )
    rag_top_k: int = Field(
        5,
        description="Number of RAG results to retrieve"
    )
    rag_min_score: float = Field(
        0.7,
        description="Minimum similarity score for RAG results"
    )


# Default config file location
# Path: src/symphony/agent_modes.py -> src/symphony -> src -> maestro-engine -> config
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "agent_modes.yaml"

# Cached configuration
_config_cache: Optional[Dict[str, Any]] = None
_config_path: Optional[Path] = None


def _load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load agent modes configuration from YAML file.

    Args:
        config_path: Optional path to config file. Uses default if not provided.

    Returns:
        Configuration dictionary
    """
    global _config_cache, _config_path

    path = config_path or Path(os.getenv("AGENT_MODES_CONFIG", str(DEFAULT_CONFIG_PATH)))

    # Return cached config if same path
    if _config_cache is not None and _config_path == path:
        return _config_cache

    try:
        if path.exists():
            with open(path, "r") as f:
                _config_cache = yaml.safe_load(f)
                _config_path = path
                logger.info(f"Loaded agent modes config from {path}")
                return _config_cache
        else:
            logger.warning(f"Config file not found at {path}, using defaults")
    except Exception as e:
        logger.error(f"Error loading config from {path}: {e}")

    # Return default configuration
    _config_cache = {
        "persona_defaults": {
            "sarah": "full",
            "marcus": "full",
            "alex": "full_rag",
            "priya": "full_rag",
        },
        "mode_descriptions": {
            "simple": "Basic prompt - fast, minimal context",
            "full": "Comprehensive prompt with full schema and guidelines",
            "full_rag": "Full prompt enhanced with RAG-retrieved context",
        },
        "rag_defaults": {
            "top_k": 5,
            "min_score": 0.7,
        }
    }
    _config_path = path
    return _config_cache


def load_default_modes(config_path: Optional[Path] = None) -> Dict[str, AgentMode]:
    """
    Load default modes for each persona from config file.

    Args:
        config_path: Optional path to config file

    Returns:
        Dictionary mapping persona_id to default AgentMode
    """
    config = _load_config(config_path)
    persona_defaults = config.get("persona_defaults", {})

    result = {}
    for persona_id, mode_str in persona_defaults.items():
        try:
            result[persona_id] = AgentMode(mode_str)
        except ValueError:
            logger.warning(f"Invalid mode '{mode_str}' for persona '{persona_id}', using FULL")
            result[persona_id] = AgentMode.FULL

    return result


def get_mode_descriptions(config_path: Optional[Path] = None) -> Dict[str, str]:
    """
    Get human-readable descriptions for each mode.

    Returns:
        Dictionary mapping mode value to description
    """
    config = _load_config(config_path)
    return config.get("mode_descriptions", {
        "simple": "Basic prompt - fast, minimal context",
        "full": "Comprehensive prompt with full schema and guidelines",
        "full_rag": "Full prompt enhanced with RAG-retrieved context",
    })


def get_rag_defaults(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Get default RAG configuration.

    Returns:
        Dictionary with top_k and min_score defaults
    """
    config = _load_config(config_path)
    return config.get("rag_defaults", {
        "top_k": 5,
        "min_score": 0.7,
    })


def get_effective_mode(
    persona_id: str,
    mode_config: Optional[WorkflowModeConfig] = None,
    config_path: Optional[Path] = None,
) -> AgentMode:
    """
    Determine effective mode for a persona with priority resolution.

    Priority order:
    1. persona_modes[persona_id] (per-persona override from request)
    2. global_mode (global override from request)
    3. YAML config defaults (from agent_modes.yaml)
    4. AgentMode.FULL (hardcoded fallback)

    Args:
        persona_id: Persona identifier (sarah, marcus, alex, priya)
        mode_config: Optional workflow mode configuration from request
        config_path: Optional path to config file

    Returns:
        Effective AgentMode for the persona
    """
    # Priority 1: Per-persona override from request
    if mode_config and persona_id in mode_config.persona_modes:
        return mode_config.persona_modes[persona_id]

    # Priority 2: Global override from request
    if mode_config and mode_config.global_mode:
        return mode_config.global_mode

    # Priority 3: YAML config defaults
    defaults = load_default_modes(config_path)
    if persona_id in defaults:
        return defaults[persona_id]

    # Priority 4: Hardcoded fallback
    return AgentMode.FULL


def is_rag_enabled(
    effective_mode: AgentMode,
    mode_config: Optional[WorkflowModeConfig] = None,
) -> bool:
    """
    Determine if RAG should be enabled for the given mode.

    Logic:
    - Explicit rag_enabled override takes priority
    - Otherwise, RAG is auto-enabled for FULL_RAG mode

    Args:
        effective_mode: The resolved mode for the persona
        mode_config: Optional workflow mode configuration

    Returns:
        True if RAG should be enabled
    """
    # Explicit override takes priority
    if mode_config and mode_config.rag_enabled is not None:
        return mode_config.rag_enabled

    # Auto-enable for FULL_RAG mode
    return effective_mode == AgentMode.FULL_RAG


def reload_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Force reload configuration from file.

    Useful for testing or dynamic config updates.
    """
    global _config_cache, _config_path
    _config_cache = None
    _config_path = None
    return _load_config(config_path)
