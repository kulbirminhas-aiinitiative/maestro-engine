"""
MAESTRO Orchestration Module

Integrates Schema v3.0 personas with autonomous SDLC engine and team workflows.

NOTE: The main workflow API now uses AutonomousSDLCEngineV3_1_Resumable from
/home/ec2-user/projects/shared/claude_team_sdk/examples/sdlc_team/team_execution.py
which includes V3.1 persona-level intelligent reuse capabilities.

This module's AutonomousSDLCEngineV3Resumable is maintained for backward
compatibility with existing test scripts and examples.
"""

from .autonomous_sdlc_engine_v3_resumable import AutonomousSDLCEngineV3Resumable
from .session_manager import SDLCSession, SessionManager
from .team_organization import TeamOrganization, get_deliverables_for_persona
from .context_assembly import (
    ContextAssemblyEngine,
    ContextItem,
    ContextType,
    AssembledContext,
    KnowledgeStoreQuery,
    ExecutionHistoryRetriever,
    ContractAttacher,
    ContextOptimizer,
    RelevanceScorer,
    assemble_context,
    get_context_summary,
)
from .block_promotion import (
    BlockStatus,
    ApproverRole,
    ApprovalStatus,
    GateResult,
    PromotionCriteria,
    CriteriaResult,
    HumanApproval,
    PromotionLevelConfig,
    GateEvaluation,
    PromotionAttempt,
    BlockInfo,
    PromotionGate,
    NewToSharableGate,
    SharableToCataloguedGate,
    CataloguedToTrustedGate,
    PromotionHistoryTracker,
    BlockPromotionPipeline,
    create_default_criteria_validators,
)
from .contract_testing import (
    MatcherType,
    VerificationStatus,
    InteractionType,
    MatcherSpec,
    PactMatchers,
    InteractionPact,
    ConsumerExpectation,
    MatchResult,
    InteractionResult,
    ExpectationVerification,
    ProviderVerificationResult,
    MatcherEngine,
    ConsumerDrivenContractRegistry,
    ContractTestRunner,
    create_expectation,
)

__all__ = [
    "AutonomousSDLCEngineV3Resumable",
    "SessionManager",
    "SDLCSession",
    "TeamOrganization",
    "get_deliverables_for_persona",
    # Context Assembly (MD-2559)
    "ContextAssemblyEngine",
    "ContextItem",
    "ContextType",
    "AssembledContext",
    "KnowledgeStoreQuery",
    "ExecutionHistoryRetriever",
    "ContractAttacher",
    "ContextOptimizer",
    "RelevanceScorer",
    "assemble_context",
    "get_context_summary",
    # Block Promotion Pipeline (MD-2510)
    "BlockStatus",
    "ApproverRole",
    "ApprovalStatus",
    "GateResult",
    "PromotionCriteria",
    "CriteriaResult",
    "HumanApproval",
    "PromotionLevelConfig",
    "GateEvaluation",
    "PromotionAttempt",
    "BlockInfo",
    "PromotionGate",
    "NewToSharableGate",
    "SharableToCataloguedGate",
    "CataloguedToTrustedGate",
    "PromotionHistoryTracker",
    "BlockPromotionPipeline",
    "create_default_criteria_validators",
    # Contract Testing (MD-2511)
    "MatcherType",
    "VerificationStatus",
    "InteractionType",
    "MatcherSpec",
    "PactMatchers",
    "InteractionPact",
    "ConsumerExpectation",
    "MatchResult",
    "InteractionResult",
    "ExpectationVerification",
    "ProviderVerificationResult",
    "MatcherEngine",
    "ConsumerDrivenContractRegistry",
    "ContractTestRunner",
    "create_expectation",
]
