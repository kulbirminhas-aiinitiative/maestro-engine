"""
Symphony Module - AI-Driven Team Collaboration Demo

EPIC: MD-3902 - Maestro Symphony Demo
Stories:
- MD-3908 - Wire Artifact Streaming via WebSocket
- MD-3909 - Define Symphony AI Personas
- MD-3911 - Offline Fallback Mode
- MD-3912 - Observability, Metrics, and SLOs
- MD-3913 - Demo Runbook with Preflight Checks

This module provides:
- Real-time artifact streaming during AI persona conversations
- WebSocket handlers for Symphony dashboard
- Artifact generation based on conversation context
- AI personas with distinct personalities and triggers
- Offline fallback mode for demo resilience
- Observability with structured logging, metrics, and SLO monitoring
- Demo runbook with preflight checks
"""

from .artifact_streamer import ArtifactStreamer, get_artifact_streamer
from .symphony_ws import router as symphony_router
from .metrics import (
    SLODefinition,
    SLOStatus,
    MetricType,
    MetricSample,
    TimerMetric,
    TraceContext,
    MetricsCollector,
    SYMPHONY_SLOS,
    get_metrics_collector,
    reset_metrics_collector,
    timed,
    counted,
)
from .offline_fallback import (
    FallbackMode,
    FallbackReason,
    PrerecordedMessage,
    PrerecordedArtifact,
    DemoScenario,
    OfflineFallbackManager,
    DemoPlayback,
    get_fallback_manager,
    reset_fallback_manager,
    run_preflight_checks,
    check_teams_health,
    check_llm_health,
    DEMO_SCENARIO_FEEDBACK_PORTAL,
)
from .runbook import (
    CheckStatus,
    PreflightCheckResult,
    PreflightReport,
    DemoCheckpoint,
    DEMO_RUNBOOK,
    REQUIRED_ENV_VARS,
    OPTIONAL_ENV_VARS,
    DEFAULT_URLS,
    run_all_preflight_checks,
    format_preflight_report,
    get_demo_runbook,
    format_demo_runbook,
    quick_start_demo,
)
from .personas import (
    SymphonyPersona,
    PersonaRole,
    PersonaPersonality,
    SYMPHONY_PERSONAS,
    AI_PERSONAS,
    SARAH_PM,
    MARCUS_ARCHITECT,
    ALEX_DEVELOPER,
    PRIYA_QA,
    HUMAN_PRESENTER,
    get_persona,
    get_all_personas,
    get_ai_personas,
    select_responding_persona,
    format_personas_for_frontend,
)
from .models import (
    ArtifactType,
    StoryArtifact,
    ArchitectureArtifact,
    CodeArtifact,
    TestArtifact,
    SymphonyTestArtifact,
    ArtifactEvent,
    WorkflowPhase,
    WorkflowProgress,
)
from .agent_modes import (
    AgentMode,
    WorkflowModeConfig,
    load_default_modes,
    get_effective_mode,
    is_rag_enabled,
    get_mode_descriptions,
    get_rag_defaults,
)
from .persona_prompts import (
    get_persona_prompt_by_mode,
    PROMPT_VARIANTS,
)

__all__ = [
    # Artifact Streamer
    "ArtifactStreamer",
    "get_artifact_streamer",
    "symphony_router",
    # Models
    "ArtifactType",
    "StoryArtifact",
    "ArchitectureArtifact",
    "CodeArtifact",
    "TestArtifact",
    "SymphonyTestArtifact",
    "ArtifactEvent",
    "WorkflowPhase",
    "WorkflowProgress",
    # Personas
    "SymphonyPersona",
    "PersonaRole",
    "PersonaPersonality",
    "SYMPHONY_PERSONAS",
    "AI_PERSONAS",
    "SARAH_PM",
    "MARCUS_ARCHITECT",
    "ALEX_DEVELOPER",
    "PRIYA_QA",
    "HUMAN_PRESENTER",
    "get_persona",
    "get_all_personas",
    "get_ai_personas",
    "select_responding_persona",
    "format_personas_for_frontend",
    # Offline Fallback
    "FallbackMode",
    "FallbackReason",
    "PrerecordedMessage",
    "PrerecordedArtifact",
    "DemoScenario",
    "OfflineFallbackManager",
    "DemoPlayback",
    "get_fallback_manager",
    "reset_fallback_manager",
    "run_preflight_checks",
    "check_teams_health",
    "check_llm_health",
    "DEMO_SCENARIO_FEEDBACK_PORTAL",
    # Metrics and Observability
    "SLODefinition",
    "SLOStatus",
    "MetricType",
    "MetricSample",
    "TimerMetric",
    "TraceContext",
    "MetricsCollector",
    "SYMPHONY_SLOS",
    "get_metrics_collector",
    "reset_metrics_collector",
    "timed",
    "counted",
    # Runbook and Preflight
    "CheckStatus",
    "PreflightCheckResult",
    "PreflightReport",
    "DemoCheckpoint",
    "DEMO_RUNBOOK",
    "REQUIRED_ENV_VARS",
    "OPTIONAL_ENV_VARS",
    "DEFAULT_URLS",
    "run_all_preflight_checks",
    "format_preflight_report",
    "get_demo_runbook",
    "format_demo_runbook",
    "quick_start_demo",
    # Agent Modes
    "AgentMode",
    "WorkflowModeConfig",
    "load_default_modes",
    "get_effective_mode",
    "is_rag_enabled",
    "get_mode_descriptions",
    "get_rag_defaults",
    "get_persona_prompt_by_mode",
    "PROMPT_VARIANTS",
]
