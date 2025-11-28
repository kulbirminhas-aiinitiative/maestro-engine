#!/usr/bin/env python3
"""
ML Routing Policy Service for MAESTRO Engine
Implements EPIC-1: Decides where requests run (FE/BFF quick-run vs Backend long-run)

This service provides:
- Feature extraction from requests (complexity, token count, resource needs)
- Policy-based routing decisions with reason codes
- Telemetry logging for ML training data collection
- Support for override headers (X-Route-Locus)
- Feature flag control (FF_ML_ROUTING_ENABLED)

Acceptance Criteria:
- AC-1: POST /api/policy/route returns {locus: fe|backend, reason_code, features} <50ms p50
- AC-2: Decisions logged with request_id; WS event ws:routing:decision emitted
- AC-3: Override header X-Route-Locus respected; audit recorded
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Try to import Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, Gauge

    ROUTING_DECISIONS = Counter(
        "maestro_routing_decisions_total",
        "Total routing decisions",
        ["locus", "reason_code"]
    )
    ROUTING_LATENCY = Histogram(
        "maestro_routing_latency_seconds",
        "Routing decision latency",
        buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.5]
    )
    ROUTING_OVERRIDES = Counter(
        "maestro_routing_overrides_total",
        "Total routing overrides via X-Route-Locus",
        ["original_locus", "override_locus"]
    )
    FEATURE_EXTRACTION_LATENCY = Histogram(
        "maestro_feature_extraction_latency_seconds",
        "Feature extraction latency"
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

    class StubMetric:
        def inc(self):
            pass
        def observe(self, value):
            pass
        def labels(self, **kwargs):
            return self

    ROUTING_DECISIONS = StubMetric()
    ROUTING_LATENCY = StubMetric()
    ROUTING_OVERRIDES = StubMetric()
    FEATURE_EXTRACTION_LATENCY = StubMetric()

logger = logging.getLogger("policy_service")


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class RoutingLocus(str, Enum):
    """Where a request should be executed."""
    FRONTEND = "fe"      # Quick-run in frontend/BFF
    BACKEND = "backend"  # Long-run in backend


class ReasonCode(str, Enum):
    """Reason codes for routing decisions."""
    # Frontend reasons
    LOW_COMPLEXITY = "LOW_COMPLEXITY"
    LOW_TOKEN_COUNT = "LOW_TOKEN_COUNT"
    CACHED_RESPONSE = "CACHED_RESPONSE"
    SIMPLE_QUERY = "SIMPLE_QUERY"
    QUICK_PREVIEW = "QUICK_PREVIEW"

    # Backend reasons
    HIGH_COMPLEXITY = "HIGH_COMPLEXITY"
    HIGH_TOKEN_COUNT = "HIGH_TOKEN_COUNT"
    REQUIRES_PERSISTENCE = "REQUIRES_PERSISTENCE"
    MULTI_AGENT_WORKFLOW = "MULTI_AGENT_WORKFLOW"
    REQUIRES_EXTERNAL_SERVICES = "REQUIRES_EXTERNAL_SERVICES"
    RESOURCE_INTENSIVE = "RESOURCE_INTENSIVE"

    # Override reasons
    USER_OVERRIDE = "USER_OVERRIDE"
    ADMIN_OVERRIDE = "ADMIN_OVERRIDE"

    # Fallback reasons
    FEATURE_FLAG_DISABLED = "FEATURE_FLAG_DISABLED"
    EVALUATION_ERROR = "EVALUATION_ERROR"
    DEFAULT_BACKEND = "DEFAULT_BACKEND"


# Feature thresholds (configurable)
DEFAULT_THRESHOLDS = {
    "max_fe_tokens": 500,           # Max tokens for frontend execution
    "max_fe_complexity": 3,         # Max complexity score (1-10) for frontend
    "max_fe_estimated_time_ms": 5000,  # Max estimated execution time for frontend
    "min_backend_complexity": 5,    # Min complexity to force backend
    "min_backend_tokens": 2000,     # Min tokens to force backend
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class RequestFeatures:
    """
    Extracted features from a request for routing decisions.
    Used for both immediate routing and ML training data.
    """
    # Basic metrics
    token_count: int
    char_count: int
    word_count: int

    # Complexity indicators
    complexity_score: float  # 1-10 scale
    has_code_blocks: bool
    has_urls: bool
    requires_file_operations: bool
    requires_external_api: bool
    requires_database: bool

    # Task indicators
    is_query: bool           # Simple question vs generation task
    is_preview_request: bool # Quick preview generation
    is_multi_step: bool      # Multi-phase workflow
    estimated_personas: int  # How many personas might be needed

    # Resource estimates
    estimated_time_ms: int   # Estimated execution time
    estimated_memory_mb: int # Estimated memory usage

    # Context
    session_has_history: bool
    request_type: str        # chat, workflow, preview, etc.

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "token_count": self.token_count,
            "char_count": self.char_count,
            "word_count": self.word_count,
            "complexity_score": round(self.complexity_score, 2),
            "has_code_blocks": self.has_code_blocks,
            "has_urls": self.has_urls,
            "requires_file_operations": self.requires_file_operations,
            "requires_external_api": self.requires_external_api,
            "requires_database": self.requires_database,
            "is_query": self.is_query,
            "is_preview_request": self.is_preview_request,
            "is_multi_step": self.is_multi_step,
            "estimated_personas": self.estimated_personas,
            "estimated_time_ms": self.estimated_time_ms,
            "estimated_memory_mb": self.estimated_memory_mb,
            "session_has_history": self.session_has_history,
            "request_type": self.request_type,
        }


@dataclass
class RoutingDecision:
    """
    Result of a routing decision.
    """
    locus: RoutingLocus
    reason_code: ReasonCode
    features: RequestFeatures
    confidence: float  # 0-1 confidence in the decision

    # Metadata for logging/auditing
    request_id: str
    session_id: Optional[str]
    timestamp: str
    decision_time_ms: float

    # Override tracking
    was_overridden: bool = False
    override_source: Optional[str] = None
    original_locus: Optional[RoutingLocus] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "locus": self.locus.value,
            "reason_code": self.reason_code.value,
            "features": self.features.to_dict(),
            "confidence": round(self.confidence, 3),
            "request_id": self.request_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "decision_time_ms": round(self.decision_time_ms, 2),
            "was_overridden": self.was_overridden,
            "override_source": self.override_source,
            "original_locus": self.original_locus.value if self.original_locus else None,
        }


@dataclass
class TelemetryRecord:
    """
    Telemetry record for ML training data collection.
    """
    request_id: str
    session_id: Optional[str]
    timestamp: str
    features: Dict[str, Any]
    decision: Dict[str, Any]
    actual_execution_time_ms: Optional[float] = None
    actual_locus: Optional[str] = None
    success: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "features": self.features,
            "decision": self.decision,
            "actual_execution_time_ms": self.actual_execution_time_ms,
            "actual_locus": self.actual_locus,
            "success": self.success,
        }


# ============================================================================
# FEATURE EXTRACTOR
# ============================================================================

class FeatureExtractor:
    """
    Extracts features from requests for routing decisions.

    Features are designed to enable both rule-based routing (Phase 1)
    and future ML model-based routing (Phase 2+).
    """

    # Keywords that indicate different task types
    QUERY_KEYWORDS = [
        "what", "how", "why", "when", "where", "who", "explain",
        "describe", "tell me", "show me", "list", "?",
    ]

    PREVIEW_KEYWORDS = [
        "preview", "quick", "simple", "basic", "demo",
        "prototype", "sketch", "draft", "mockup",
    ]

    WORKFLOW_KEYWORDS = [
        "build", "create", "develop", "implement", "design",
        "architect", "deploy", "test", "review", "document",
        "full", "complete", "comprehensive", "end-to-end",
    ]

    FILE_OPERATION_KEYWORDS = [
        "file", "save", "write", "read", "upload", "download",
        "export", "import", "storage", "persist",
    ]

    EXTERNAL_API_KEYWORDS = [
        "api", "endpoint", "fetch", "request", "call",
        "integration", "webhook", "external",
    ]

    DATABASE_KEYWORDS = [
        "database", "db", "sql", "query", "table", "schema",
        "postgres", "mysql", "mongodb", "redis", "migrate",
    ]

    def __init__(self):
        """Initialize feature extractor."""
        logger.info("Feature Extractor initialized")

    def extract_features(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        session_history: Optional[List[Dict]] = None,
        request_type: str = "chat"
    ) -> RequestFeatures:
        """
        Extract features from a request prompt.

        Args:
            prompt: The user's prompt/requirement
            session_id: Optional session ID
            session_history: Optional conversation history
            request_type: Type of request (chat, workflow, preview)

        Returns:
            RequestFeatures object with extracted features
        """
        start_time = time.time()

        prompt_lower = prompt.lower()

        # Basic text metrics
        token_count = self._estimate_token_count(prompt)
        char_count = len(prompt)
        word_count = len(prompt.split())

        # Content analysis
        has_code_blocks = "```" in prompt or "    " in prompt  # Code blocks or indented code
        has_urls = "http://" in prompt_lower or "https://" in prompt_lower

        # Task type detection
        is_query = self._is_query(prompt_lower)
        is_preview_request = self._is_preview_request(prompt_lower)
        is_multi_step = self._is_multi_step_workflow(prompt_lower)

        # Resource requirements
        requires_file_ops = self._requires_file_operations(prompt_lower)
        requires_external = self._requires_external_api(prompt_lower)
        requires_db = self._requires_database(prompt_lower)

        # Complexity scoring
        complexity_score = self._calculate_complexity(
            prompt=prompt,
            token_count=token_count,
            has_code=has_code_blocks,
            is_multi_step=is_multi_step,
            requires_external=requires_external,
            requires_db=requires_db,
        )

        # Persona estimation
        estimated_personas = self._estimate_personas(prompt_lower, is_multi_step)

        # Time/resource estimation
        estimated_time = self._estimate_execution_time(
            complexity=complexity_score,
            token_count=token_count,
            estimated_personas=estimated_personas,
        )
        estimated_memory = self._estimate_memory(
            complexity=complexity_score,
            token_count=token_count,
        )

        # Session context
        has_history = bool(session_history and len(session_history) > 0)

        features = RequestFeatures(
            token_count=token_count,
            char_count=char_count,
            word_count=word_count,
            complexity_score=complexity_score,
            has_code_blocks=has_code_blocks,
            has_urls=has_urls,
            requires_file_operations=requires_file_ops,
            requires_external_api=requires_external,
            requires_database=requires_db,
            is_query=is_query,
            is_preview_request=is_preview_request,
            is_multi_step=is_multi_step,
            estimated_personas=estimated_personas,
            estimated_time_ms=estimated_time,
            estimated_memory_mb=estimated_memory,
            session_has_history=has_history,
            request_type=request_type,
        )

        extraction_time = (time.time() - start_time) * 1000
        if HAS_PROMETHEUS:
            FEATURE_EXTRACTION_LATENCY.observe(extraction_time / 1000)

        logger.debug(f"Features extracted in {extraction_time:.2f}ms: {features.to_dict()}")

        return features

    def _estimate_token_count(self, text: str) -> int:
        """Estimate token count (rough approximation: ~4 chars per token)."""
        return max(1, len(text) // 4)

    def _is_query(self, prompt_lower: str) -> bool:
        """Check if the prompt is a simple query/question."""
        return any(kw in prompt_lower for kw in self.QUERY_KEYWORDS)

    def _is_preview_request(self, prompt_lower: str) -> bool:
        """Check if the prompt is a preview/quick generation request."""
        return any(kw in prompt_lower for kw in self.PREVIEW_KEYWORDS)

    def _is_multi_step_workflow(self, prompt_lower: str) -> bool:
        """Check if the prompt requires a multi-step workflow."""
        workflow_indicators = sum(
            1 for kw in self.WORKFLOW_KEYWORDS if kw in prompt_lower
        )
        return workflow_indicators >= 2

    def _requires_file_operations(self, prompt_lower: str) -> bool:
        """Check if the prompt requires file operations."""
        return any(kw in prompt_lower for kw in self.FILE_OPERATION_KEYWORDS)

    def _requires_external_api(self, prompt_lower: str) -> bool:
        """Check if the prompt requires external API calls."""
        return any(kw in prompt_lower for kw in self.EXTERNAL_API_KEYWORDS)

    def _requires_database(self, prompt_lower: str) -> bool:
        """Check if the prompt requires database operations."""
        return any(kw in prompt_lower for kw in self.DATABASE_KEYWORDS)

    def _calculate_complexity(
        self,
        prompt: str,
        token_count: int,
        has_code: bool,
        is_multi_step: bool,
        requires_external: bool,
        requires_db: bool,
    ) -> float:
        """
        Calculate complexity score (1-10 scale).

        Factors:
        - Token count (longer = more complex)
        - Code presence
        - Multi-step workflow
        - External dependencies
        """
        base_score = 1.0

        # Token count contribution (0-3 points)
        if token_count > 2000:
            base_score += 3.0
        elif token_count > 1000:
            base_score += 2.0
        elif token_count > 500:
            base_score += 1.0
        elif token_count > 200:
            base_score += 0.5

        # Code presence (+1)
        if has_code:
            base_score += 1.0

        # Multi-step workflow (+2)
        if is_multi_step:
            base_score += 2.0

        # External dependencies (+1 each)
        if requires_external:
            base_score += 1.0
        if requires_db:
            base_score += 1.0

        # Sentence/instruction count
        sentences = prompt.count('.') + prompt.count('!') + prompt.count('?')
        if sentences > 10:
            base_score += 1.0
        elif sentences > 5:
            base_score += 0.5

        return min(10.0, max(1.0, base_score))

    def _estimate_personas(self, prompt_lower: str, is_multi_step: bool) -> int:
        """Estimate number of personas needed."""
        if not is_multi_step:
            return 1

        persona_keywords = {
            "requirement": 1,
            "architect": 1,
            "backend": 1,
            "frontend": 1,
            "database": 1,
            "security": 1,
            "test": 1,
            "deploy": 1,
            "document": 1,
        }

        count = sum(
            v for k, v in persona_keywords.items()
            if k in prompt_lower
        )

        return max(1, min(count, 12))  # Cap at 12 (full SDLC team)

    def _estimate_execution_time(
        self,
        complexity: float,
        token_count: int,
        estimated_personas: int,
    ) -> int:
        """Estimate execution time in milliseconds."""
        # Base time per complexity level
        base_time = int(complexity * 500)  # 500ms per complexity point

        # Token processing time
        token_time = token_count * 2  # ~2ms per token

        # Persona overhead
        persona_time = estimated_personas * 2000  # ~2s per persona

        return base_time + token_time + persona_time

    def _estimate_memory(self, complexity: float, token_count: int) -> int:
        """Estimate memory usage in MB."""
        # Base memory
        base = 50

        # Token memory (rough estimate)
        token_mem = token_count // 100

        # Complexity overhead
        complexity_mem = int(complexity * 10)

        return base + token_mem + complexity_mem


# ============================================================================
# POLICY EVALUATOR
# ============================================================================

class PolicyEvaluator:
    """
    Evaluates routing policy based on extracted features.

    Phase 1: Rule-based heuristics
    Phase 2: Will add ML model support
    """

    def __init__(
        self,
        thresholds: Optional[Dict[str, Any]] = None,
        feature_flag_enabled: bool = True,
    ):
        """
        Initialize policy evaluator.

        Args:
            thresholds: Custom thresholds for routing decisions
            feature_flag_enabled: Whether ML routing is enabled
        """
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.feature_flag_enabled = feature_flag_enabled
        self.feature_extractor = FeatureExtractor()

        logger.info(f"Policy Evaluator initialized (FF_ML_ROUTING_ENABLED={feature_flag_enabled})")

    def evaluate(
        self,
        prompt: str,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        session_history: Optional[List[Dict]] = None,
        request_type: str = "chat",
        override_locus: Optional[str] = None,
    ) -> RoutingDecision:
        """
        Evaluate routing policy for a request.

        Args:
            prompt: The user's prompt/requirement
            request_id: Unique request identifier
            session_id: Session identifier
            session_history: Conversation history
            request_type: Type of request
            override_locus: Override value from X-Route-Locus header

        Returns:
            RoutingDecision with locus, reason, and features
        """
        start_time = time.time()

        # Generate request_id if not provided
        if not request_id:
            request_id = self._generate_request_id(prompt, session_id)

        # Check feature flag
        if not self.feature_flag_enabled:
            decision = self._create_decision(
                locus=RoutingLocus.BACKEND,
                reason_code=ReasonCode.FEATURE_FLAG_DISABLED,
                features=self._get_default_features(prompt),
                confidence=1.0,
                request_id=request_id,
                session_id=session_id,
                start_time=start_time,
            )
            self._record_telemetry(decision)
            return decision

        try:
            # Extract features
            features = self.feature_extractor.extract_features(
                prompt=prompt,
                session_id=session_id,
                session_history=session_history,
                request_type=request_type,
            )

            # Evaluate routing rules
            locus, reason_code, confidence = self._apply_rules(features)

            # Create decision
            decision = self._create_decision(
                locus=locus,
                reason_code=reason_code,
                features=features,
                confidence=confidence,
                request_id=request_id,
                session_id=session_id,
                start_time=start_time,
            )

            # Handle override if present
            if override_locus:
                decision = self._apply_override(decision, override_locus)

            # Record metrics
            if HAS_PROMETHEUS:
                ROUTING_DECISIONS.labels(
                    locus=decision.locus.value,
                    reason_code=decision.reason_code.value
                ).inc()
                ROUTING_LATENCY.observe(decision.decision_time_ms / 1000)

            # Record telemetry
            self._record_telemetry(decision)

            logger.info(
                f"Routing decision: {decision.locus.value} "
                f"(reason={decision.reason_code.value}, "
                f"confidence={decision.confidence:.2f}, "
                f"time={decision.decision_time_ms:.2f}ms)"
            )

            return decision

        except Exception as e:
            logger.error(f"Error evaluating routing policy: {e}")
            return self._create_decision(
                locus=RoutingLocus.BACKEND,
                reason_code=ReasonCode.EVALUATION_ERROR,
                features=self._get_default_features(prompt),
                confidence=0.5,
                request_id=request_id,
                session_id=session_id,
                start_time=start_time,
            )

    def _apply_rules(
        self,
        features: RequestFeatures,
    ) -> Tuple[RoutingLocus, ReasonCode, float]:
        """
        Apply routing rules based on features.

        Rule priority (checked in order):
        1. Multi-step workflow -> Backend (highest priority)
        2. External service requirements -> Backend
        3. File operations -> Backend
        4. Simple query -> Frontend (only if no backend requirements)
        5. Preview requests -> Frontend
        6. Low complexity -> Frontend
        7. High complexity -> Backend
        8. High token count -> Backend
        9. Resource intensive -> Backend
        10. Default -> Backend (conservative fallback)

        Returns:
            Tuple of (locus, reason_code, confidence)
        """
        # Rule 1: Multi-step workflow -> Backend (highest priority)
        if features.is_multi_step:
            return (RoutingLocus.BACKEND, ReasonCode.MULTI_AGENT_WORKFLOW, 0.95)

        # Rule 2: External service requirements -> Backend
        # Check this BEFORE low complexity to ensure database/API needs route to backend
        if features.requires_external_api or features.requires_database:
            return (RoutingLocus.BACKEND, ReasonCode.REQUIRES_EXTERNAL_SERVICES, 0.90)

        # Rule 3: File operations -> Backend (for persistence)
        if features.requires_file_operations:
            return (RoutingLocus.BACKEND, ReasonCode.REQUIRES_PERSISTENCE, 0.85)

        # Rule 4: Very simple queries -> Frontend (only if no backend requirements)
        if features.is_query and features.complexity_score <= 2:
            return (RoutingLocus.FRONTEND, ReasonCode.SIMPLE_QUERY, 0.95)

        # Rule 5: Preview requests with low complexity -> Frontend
        if features.is_preview_request and features.complexity_score <= 3:
            return (RoutingLocus.FRONTEND, ReasonCode.QUICK_PREVIEW, 0.90)

        # Rule 6: Low token count and low complexity -> Frontend
        if (features.token_count <= self.thresholds["max_fe_tokens"] and
            features.complexity_score <= self.thresholds["max_fe_complexity"]):
            return (RoutingLocus.FRONTEND, ReasonCode.LOW_COMPLEXITY, 0.85)

        # Rule 7: High complexity -> Backend
        if features.complexity_score >= self.thresholds["min_backend_complexity"]:
            return (RoutingLocus.BACKEND, ReasonCode.HIGH_COMPLEXITY, 0.88)

        # Rule 8: High token count -> Backend
        if features.token_count >= self.thresholds["min_backend_tokens"]:
            return (RoutingLocus.BACKEND, ReasonCode.HIGH_TOKEN_COUNT, 0.85)

        # Rule 9: Resource intensive -> Backend
        if features.estimated_time_ms > self.thresholds["max_fe_estimated_time_ms"]:
            return (RoutingLocus.BACKEND, ReasonCode.RESOURCE_INTENSIVE, 0.80)

        # Default: Backend (conservative fallback)
        return (RoutingLocus.BACKEND, ReasonCode.DEFAULT_BACKEND, 0.70)

    def _apply_override(
        self,
        decision: RoutingDecision,
        override_value: str,
    ) -> RoutingDecision:
        """
        Apply manual override to routing decision.

        Args:
            decision: Original routing decision
            override_value: Override value from header (fe|backend)

        Returns:
            Modified decision with override applied
        """
        override_locus = None
        if override_value.lower() in ("fe", "frontend"):
            override_locus = RoutingLocus.FRONTEND
        elif override_value.lower() in ("backend", "be"):
            override_locus = RoutingLocus.BACKEND

        if override_locus and override_locus != decision.locus:
            logger.warning(
                f"Routing override applied: {decision.locus.value} -> {override_locus.value} "
                f"(request_id={decision.request_id})"
            )

            if HAS_PROMETHEUS:
                ROUTING_OVERRIDES.labels(
                    original_locus=decision.locus.value,
                    override_locus=override_locus.value
                ).inc()

            decision.original_locus = decision.locus
            decision.locus = override_locus
            decision.reason_code = ReasonCode.USER_OVERRIDE
            decision.was_overridden = True
            decision.override_source = "X-Route-Locus"

        return decision

    def _create_decision(
        self,
        locus: RoutingLocus,
        reason_code: ReasonCode,
        features: RequestFeatures,
        confidence: float,
        request_id: str,
        session_id: Optional[str],
        start_time: float,
    ) -> RoutingDecision:
        """Create a routing decision object."""
        decision_time = (time.time() - start_time) * 1000

        return RoutingDecision(
            locus=locus,
            reason_code=reason_code,
            features=features,
            confidence=confidence,
            request_id=request_id,
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            decision_time_ms=decision_time,
        )

    def _get_default_features(self, prompt: str) -> RequestFeatures:
        """Get default features when extraction fails."""
        return RequestFeatures(
            token_count=len(prompt) // 4,
            char_count=len(prompt),
            word_count=len(prompt.split()),
            complexity_score=5.0,
            has_code_blocks=False,
            has_urls=False,
            requires_file_operations=False,
            requires_external_api=False,
            requires_database=False,
            is_query=False,
            is_preview_request=False,
            is_multi_step=False,
            estimated_personas=1,
            estimated_time_ms=5000,
            estimated_memory_mb=100,
            session_has_history=False,
            request_type="unknown",
        )

    def _generate_request_id(self, prompt: str, session_id: Optional[str]) -> str:
        """Generate a unique request ID."""
        timestamp = datetime.now().isoformat()
        data = f"{timestamp}:{session_id or ''}:{prompt[:50]}"
        return hashlib.md5(data.encode()).hexdigest()[:16]

    def _record_telemetry(self, decision: RoutingDecision):
        """Record telemetry for ML training data."""
        record = TelemetryRecord(
            request_id=decision.request_id,
            session_id=decision.session_id,
            timestamp=decision.timestamp,
            features=decision.features.to_dict(),
            decision={
                "locus": decision.locus.value,
                "reason_code": decision.reason_code.value,
                "confidence": decision.confidence,
                "decision_time_ms": decision.decision_time_ms,
            },
        )

        # Log telemetry (in production, would write to storage/queue)
        logger.debug(f"Telemetry record: {record.to_dict()}")


# ============================================================================
# SINGLETON & MODULE FUNCTIONS
# ============================================================================

_policy_evaluator: Optional[PolicyEvaluator] = None


def get_policy_evaluator(
    feature_flag_enabled: bool = True,
    thresholds: Optional[Dict[str, Any]] = None,
) -> PolicyEvaluator:
    """
    Get or create singleton PolicyEvaluator.

    Args:
        feature_flag_enabled: Whether FF_ML_ROUTING_ENABLED is true
        thresholds: Optional custom thresholds

    Returns:
        PolicyEvaluator instance
    """
    global _policy_evaluator
    if _policy_evaluator is None:
        _policy_evaluator = PolicyEvaluator(
            thresholds=thresholds,
            feature_flag_enabled=feature_flag_enabled,
        )
    return _policy_evaluator


def evaluate_routing(
    prompt: str,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    override_locus: Optional[str] = None,
) -> RoutingDecision:
    """
    Convenience function to evaluate routing.

    Args:
        prompt: The user's prompt
        request_id: Optional request ID
        session_id: Optional session ID
        override_locus: Optional override from X-Route-Locus header

    Returns:
        RoutingDecision
    """
    evaluator = get_policy_evaluator()
    return evaluator.evaluate(
        prompt=prompt,
        request_id=request_id,
        session_id=session_id,
        override_locus=override_locus,
    )


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("ML Routing Policy Service - Test")
    print("=" * 60)

    evaluator = get_policy_evaluator()

    # Test cases
    test_prompts = [
        # Should route to Frontend
        ("What is Python?", "Simple query"),
        ("Show me a quick preview of a button", "Preview request"),
        ("List the files in src/", "Simple file listing"),

        # Should route to Backend
        ("Build a complete e-commerce platform with user authentication, product catalog, and payment integration", "Complex workflow"),
        ("Implement a full SDLC workflow for a project management tool", "Multi-agent workflow"),
        ("Create a backend API with database integration and external service calls", "External dependencies"),
    ]

    print("\nTest Results:")
    print("-" * 60)

    for prompt, description in test_prompts:
        decision = evaluator.evaluate(prompt=prompt, session_id="test_session")

        print(f"\n{description}:")
        print(f"  Prompt: {prompt[:50]}...")
        print(f"  Locus: {decision.locus.value}")
        print(f"  Reason: {decision.reason_code.value}")
        print(f"  Confidence: {decision.confidence:.2%}")
        print(f"  Decision time: {decision.decision_time_ms:.2f}ms")
        print(f"  Complexity: {decision.features.complexity_score:.1f}/10")
        print(f"  Tokens: {decision.features.token_count}")

    print("\n" + "=" * 60)
    print("Override Test:")
    print("-" * 60)

    # Test override
    decision = evaluator.evaluate(
        prompt="Build a complex application",
        session_id="test_session",
        override_locus="fe",
    )

    print(f"  Original would be: {decision.original_locus.value if decision.original_locus else 'N/A'}")
    print(f"  After override: {decision.locus.value}")
    print(f"  Was overridden: {decision.was_overridden}")
    print(f"  Override source: {decision.override_source}")
