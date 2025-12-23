"""
Contract Testing System for MD-2511

Implements consumer-driven contract testing (Pact-style):
- Consumers define expectations of providers
- Providers verify their implementation against expectations
- Registry tracks compatibility matrix across versions

This enables:
- Multiple consumers to have different contracts with same provider
- Loose matching with type/format matchers
- Version compatibility tracking
- Automated contract test execution

Author: Maestro Platform Team
Created: 2025-12-06
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import hashlib
import json
import logging
import re
import uuid

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class MatcherType(str, Enum):
    """Types of matchers for flexible contract testing."""
    TYPE = "type"
    REGEX = "regex"
    ARRAY = "array"
    OBJECT = "object"
    EXACT = "exact"
    ANY = "any"


class VerificationStatus(str, Enum):
    """Status of a verification result."""
    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"
    SKIPPED = "skipped"


class InteractionType(str, Enum):
    """Type of interaction in a contract."""
    HTTP = "http"
    MESSAGE = "message"
    FUNCTION = "function"
    EVENT = "event"


# ============================================================================
# PACT MATCHERS - AC-2: Flexible type-based matching
# ============================================================================

@dataclass
class MatcherSpec:
    """
    Specification for a matcher.

    Attributes:
        matcher_type: Type of matching to perform
        expected: Expected value or pattern
        example: Example value for documentation
        options: Additional matcher options
    """
    matcher_type: MatcherType
    expected: Any = None
    example: Any = None
    options: Dict[str, Any] = field(default_factory=dict)


class PactMatchers:
    """
    Loose matchers for flexible contract testing (Pact-style).

    Instead of exact value matching, these matchers check:
    - Type (string, integer, boolean, etc.)
    - Format (uuid, datetime, email, etc.)
    - Structure (arrays, objects)
    - Patterns (regex)

    Example:
        >>> response = {"id": PactMatchers.uuid(), "name": PactMatchers.string()}
        >>> # Matches any response with valid UUID id and any string name
    """

    @staticmethod
    def string(example: str = "string") -> MatcherSpec:
        """
        Match any string value.

        Args:
            example: Example string for documentation

        Returns:
            MatcherSpec configured for string matching
        """
        return MatcherSpec(
            matcher_type=MatcherType.TYPE,
            expected="string",
            example=example
        )

    @staticmethod
    def integer(example: int = 1) -> MatcherSpec:
        """
        Match any integer value.

        Args:
            example: Example integer for documentation

        Returns:
            MatcherSpec configured for integer matching
        """
        return MatcherSpec(
            matcher_type=MatcherType.TYPE,
            expected="integer",
            example=example
        )

    @staticmethod
    def number(example: float = 1.0) -> MatcherSpec:
        """
        Match any numeric value (int or float).

        Args:
            example: Example number for documentation

        Returns:
            MatcherSpec configured for number matching
        """
        return MatcherSpec(
            matcher_type=MatcherType.TYPE,
            expected="number",
            example=example
        )

    @staticmethod
    def boolean(example: bool = True) -> MatcherSpec:
        """
        Match any boolean value.

        Args:
            example: Example boolean for documentation

        Returns:
            MatcherSpec configured for boolean matching
        """
        return MatcherSpec(
            matcher_type=MatcherType.TYPE,
            expected="boolean",
            example=example
        )

    @staticmethod
    def uuid(example: str = "550e8400-e29b-41d4-a716-446655440000") -> MatcherSpec:
        """
        Match UUID format (8-4-4-4-12 hex pattern).

        Args:
            example: Example UUID for documentation

        Returns:
            MatcherSpec configured for UUID matching
        """
        return MatcherSpec(
            matcher_type=MatcherType.REGEX,
            expected=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            example=example,
            options={"case_insensitive": True}
        )

    @staticmethod
    def iso_datetime(example: str = "2025-12-06T12:00:00Z") -> MatcherSpec:
        """
        Match ISO 8601 datetime format.

        Args:
            example: Example datetime for documentation

        Returns:
            MatcherSpec configured for datetime matching
        """
        return MatcherSpec(
            matcher_type=MatcherType.REGEX,
            expected=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
            example=example
        )

    @staticmethod
    def email(example: str = "user@example.com") -> MatcherSpec:
        """
        Match email format.

        Args:
            example: Example email for documentation

        Returns:
            MatcherSpec configured for email matching
        """
        return MatcherSpec(
            matcher_type=MatcherType.REGEX,
            expected=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            example=example
        )

    @staticmethod
    def url(example: str = "https://example.com") -> MatcherSpec:
        """
        Match URL format.

        Args:
            example: Example URL for documentation

        Returns:
            MatcherSpec configured for URL matching
        """
        return MatcherSpec(
            matcher_type=MatcherType.REGEX,
            expected=r"^https?://[^\s]+$",
            example=example
        )

    @staticmethod
    def regex(pattern: str, example: str = "") -> MatcherSpec:
        """
        Match custom regex pattern.

        Args:
            pattern: Regex pattern to match
            example: Example value for documentation

        Returns:
            MatcherSpec configured for regex matching
        """
        return MatcherSpec(
            matcher_type=MatcherType.REGEX,
            expected=pattern,
            example=example
        )

    @staticmethod
    def array_of(item_matcher: MatcherSpec, min_items: int = 0) -> MatcherSpec:
        """
        Match array with typed items.

        Args:
            item_matcher: Matcher for array items
            min_items: Minimum number of items required

        Returns:
            MatcherSpec configured for array matching
        """
        return MatcherSpec(
            matcher_type=MatcherType.ARRAY,
            expected=item_matcher,
            options={"min_items": min_items}
        )

    @staticmethod
    def object_with(fields: Dict[str, MatcherSpec]) -> MatcherSpec:
        """
        Match object with specific field matchers.

        Args:
            fields: Dictionary of field names to matchers

        Returns:
            MatcherSpec configured for object matching
        """
        return MatcherSpec(
            matcher_type=MatcherType.OBJECT,
            expected=fields
        )

    @staticmethod
    def exact(value: Any) -> MatcherSpec:
        """
        Match exact value (not type).

        Args:
            value: Exact value to match

        Returns:
            MatcherSpec configured for exact matching
        """
        return MatcherSpec(
            matcher_type=MatcherType.EXACT,
            expected=value,
            example=value
        )

    @staticmethod
    def any_value() -> MatcherSpec:
        """
        Match any value (just check field exists).

        Returns:
            MatcherSpec that accepts any value
        """
        return MatcherSpec(
            matcher_type=MatcherType.ANY
        )


# ============================================================================
# DATA CLASSES - Contract structures
# ============================================================================

@dataclass
class InteractionPact:
    """
    Pact interaction (request/response pair).

    Represents a single interaction between consumer and provider.
    Can be HTTP, message, function call, or event.

    Attributes:
        description: Human-readable description
        interaction_type: Type of interaction
        provider_state: Required provider state before interaction
        request: Request/input specification
        response: Expected response/output
        matchers: Field-level matchers for flexible matching
    """
    description: str
    interaction_type: InteractionType = InteractionType.HTTP
    provider_state: Optional[str] = None
    request: Dict[str, Any] = field(default_factory=dict)
    response: Dict[str, Any] = field(default_factory=dict)
    matchers: Dict[str, MatcherSpec] = field(default_factory=dict)


@dataclass
class ConsumerExpectation:
    """
    Consumer's expectation of a provider (AC-1).

    In consumer-driven contracts, the CONSUMER defines what they expect,
    not the provider. This inverts the traditional approach where
    providers define contracts.

    Attributes:
        expectation_id: Unique identifier for this expectation
        consumer_agent: Identifier of the consuming agent/service
        consumer_version: Version of the consumer
        provider_agent: Identifier of the providing agent/service
        interactions: List of expected interactions
        created_at: When this expectation was created
        verified_by_provider: Whether provider has verified
        verification_date: When verification occurred
        metadata: Additional metadata
    """
    expectation_id: str
    consumer_agent: str
    provider_agent: str
    consumer_version: str = "1.0.0"
    interactions: List[InteractionPact] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    verified_by_provider: bool = False
    verification_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Generate ID if not provided."""
        if not self.expectation_id:
            self.expectation_id = f"{self.consumer_agent}_{self.provider_agent}_{uuid.uuid4().hex[:8]}"


@dataclass
class MatchResult:
    """
    Result of matching actual vs expected values.

    Attributes:
        passed: Whether all matching passed
        field_path: Path to the field being matched
        expected: What was expected
        actual: What was actually received
        failures: List of failure messages
    """
    passed: bool
    field_path: str = ""
    expected: Any = None
    actual: Any = None
    failures: List[str] = field(default_factory=list)


@dataclass
class InteractionResult:
    """
    Result of executing a single interaction.

    Attributes:
        interaction_description: Description of the interaction
        status: Verification status
        request_sent: Actual request sent
        response_received: Actual response received
        match_results: Results of matching response
        duration_ms: Time taken in milliseconds
        error: Error message if any
    """
    interaction_description: str
    status: VerificationStatus
    request_sent: Dict[str, Any] = field(default_factory=dict)
    response_received: Dict[str, Any] = field(default_factory=dict)
    match_results: List[MatchResult] = field(default_factory=list)
    duration_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class ExpectationVerification:
    """
    Verification result for single consumer expectation (AC-4).

    Attributes:
        expectation_id: ID of the expectation being verified
        consumer: Consumer agent identifier
        consumer_version: Consumer version
        provider_version: Provider version that verified
        status: Overall verification status
        interaction_results: Results for each interaction
        verified_at: When verification occurred
    """
    expectation_id: str
    consumer: str
    consumer_version: str
    provider_version: str
    status: VerificationStatus
    interaction_results: List[InteractionResult] = field(default_factory=list)
    verified_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def passed(self) -> bool:
        """Check if all interactions passed."""
        return self.status == VerificationStatus.PASSED

    @property
    def failure_count(self) -> int:
        """Count failed interactions."""
        return sum(1 for r in self.interaction_results if r.status == VerificationStatus.FAILED)


@dataclass
class ProviderVerificationResult:
    """
    Result of provider verification against all consumer expectations (AC-4).

    Attributes:
        provider: Provider identifier
        provider_version: Provider version
        total_expectations: Total expectations verified
        verified: Number that passed
        failed: Number that failed
        results: Individual verification results
        compatibility_matrix: Version compatibility info
    """
    provider: str
    provider_version: str
    total_expectations: int
    verified: int
    failed: int
    results: List[ExpectationVerification] = field(default_factory=list)
    verified_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def all_passed(self) -> bool:
        """Check if all expectations passed."""
        return self.failed == 0

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate percentage."""
        if self.total_expectations == 0:
            return 100.0
        return (self.verified / self.total_expectations) * 100


# ============================================================================
# MATCHER ENGINE - Core matching logic
# ============================================================================

class MatcherEngine:
    """
    Engine for matching actual values against expected with matchers.

    Supports:
    - Type matching (string, int, bool, etc.)
    - Regex matching for formats
    - Array matching with item types
    - Object matching with field matchers
    - Exact value matching
    """

    def match(
        self,
        actual: Any,
        expected: Any,
        matcher: Optional[MatcherSpec] = None,
        path: str = ""
    ) -> MatchResult:
        """
        Match actual value against expected.

        Args:
            actual: Actual value received
            expected: Expected value or structure
            matcher: Optional matcher spec for flexible matching
            path: Current field path for error messages

        Returns:
            MatchResult with pass/fail and details
        """
        # If matcher provided, use it
        if matcher:
            return self._match_with_matcher(actual, matcher, path)

        # If expected is a MatcherSpec, use it
        if isinstance(expected, MatcherSpec):
            return self._match_with_matcher(actual, expected, path)

        # Otherwise do structural matching
        return self._match_structural(actual, expected, path)

    def _match_with_matcher(
        self,
        actual: Any,
        matcher: MatcherSpec,
        path: str
    ) -> MatchResult:
        """Match using a MatcherSpec."""
        if matcher.matcher_type == MatcherType.TYPE:
            return self._match_type(actual, matcher.expected, path)
        elif matcher.matcher_type == MatcherType.REGEX:
            return self._match_regex(actual, matcher.expected, path, matcher.options)
        elif matcher.matcher_type == MatcherType.ARRAY:
            return self._match_array(actual, matcher, path)
        elif matcher.matcher_type == MatcherType.OBJECT:
            return self._match_object(actual, matcher.expected, path)
        elif matcher.matcher_type == MatcherType.EXACT:
            return self._match_exact(actual, matcher.expected, path)
        elif matcher.matcher_type == MatcherType.ANY:
            return MatchResult(passed=True, field_path=path)
        else:
            return MatchResult(
                passed=False,
                field_path=path,
                failures=[f"Unknown matcher type: {matcher.matcher_type}"]
            )

    def _match_type(self, actual: Any, expected_type: str, path: str) -> MatchResult:
        """Match value type."""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None)
        }

        expected_types = type_map.get(expected_type, str)
        if isinstance(expected_types, tuple):
            passed = isinstance(actual, expected_types)
        else:
            passed = isinstance(actual, expected_types)

        if passed:
            return MatchResult(passed=True, field_path=path, expected=expected_type, actual=type(actual).__name__)
        else:
            return MatchResult(
                passed=False,
                field_path=path,
                expected=expected_type,
                actual=type(actual).__name__,
                failures=[f"Expected type '{expected_type}' at '{path}', got '{type(actual).__name__}'"]
            )

    def _match_regex(
        self,
        actual: Any,
        pattern: str,
        path: str,
        options: Dict[str, Any]
    ) -> MatchResult:
        """Match value against regex pattern."""
        if not isinstance(actual, str):
            return MatchResult(
                passed=False,
                field_path=path,
                expected=f"string matching /{pattern}/",
                actual=type(actual).__name__,
                failures=[f"Expected string at '{path}' for regex match, got {type(actual).__name__}"]
            )

        flags = re.IGNORECASE if options.get("case_insensitive") else 0

        if re.match(pattern, actual, flags):
            return MatchResult(passed=True, field_path=path, expected=pattern, actual=actual)
        else:
            return MatchResult(
                passed=False,
                field_path=path,
                expected=pattern,
                actual=actual,
                failures=[f"Value '{actual}' at '{path}' doesn't match pattern '{pattern}'"]
            )

    def _match_array(self, actual: Any, matcher: MatcherSpec, path: str) -> MatchResult:
        """Match array with item type checking."""
        if not isinstance(actual, list):
            return MatchResult(
                passed=False,
                field_path=path,
                failures=[f"Expected array at '{path}', got {type(actual).__name__}"]
            )

        min_items = matcher.options.get("min_items", 0)
        if len(actual) < min_items:
            return MatchResult(
                passed=False,
                field_path=path,
                failures=[f"Array at '{path}' has {len(actual)} items, need at least {min_items}"]
            )

        # Match each item against item matcher
        item_matcher = matcher.expected
        failures = []
        for i, item in enumerate(actual):
            item_result = self._match_with_matcher(item, item_matcher, f"{path}[{i}]")
            if not item_result.passed:
                failures.extend(item_result.failures)

        return MatchResult(
            passed=len(failures) == 0,
            field_path=path,
            failures=failures
        )

    def _match_object(
        self,
        actual: Any,
        field_matchers: Dict[str, MatcherSpec],
        path: str
    ) -> MatchResult:
        """Match object with field-level matchers."""
        if not isinstance(actual, dict):
            return MatchResult(
                passed=False,
                field_path=path,
                failures=[f"Expected object at '{path}', got {type(actual).__name__}"]
            )

        failures = []
        for field_name, field_matcher in field_matchers.items():
            field_path = f"{path}.{field_name}" if path else field_name

            if field_name not in actual:
                failures.append(f"Missing required field '{field_path}'")
                continue

            field_result = self._match_with_matcher(actual[field_name], field_matcher, field_path)
            if not field_result.passed:
                failures.extend(field_result.failures)

        return MatchResult(
            passed=len(failures) == 0,
            field_path=path,
            failures=failures
        )

    def _match_exact(self, actual: Any, expected: Any, path: str) -> MatchResult:
        """Match exact value."""
        if actual == expected:
            return MatchResult(passed=True, field_path=path, expected=expected, actual=actual)
        else:
            return MatchResult(
                passed=False,
                field_path=path,
                expected=expected,
                actual=actual,
                failures=[f"Expected exact value '{expected}' at '{path}', got '{actual}'"]
            )

    def _match_structural(
        self,
        actual: Any,
        expected: Any,
        path: str
    ) -> MatchResult:
        """Structural matching when no explicit matcher provided."""
        # If expected is dict, match structure
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                return MatchResult(
                    passed=False,
                    field_path=path,
                    failures=[f"Expected object at '{path}', got {type(actual).__name__}"]
                )

            failures = []
            for key, exp_value in expected.items():
                key_path = f"{path}.{key}" if path else key

                if key not in actual:
                    failures.append(f"Missing field '{key_path}'")
                    continue

                result = self.match(actual[key], exp_value, path=key_path)
                if not result.passed:
                    failures.extend(result.failures)

            return MatchResult(passed=len(failures) == 0, field_path=path, failures=failures)

        # If expected is list, match items
        elif isinstance(expected, list):
            if not isinstance(actual, list):
                return MatchResult(
                    passed=False,
                    field_path=path,
                    failures=[f"Expected array at '{path}', got {type(actual).__name__}"]
                )

            # Just check types match for each expected item
            return MatchResult(passed=True, field_path=path)

        # Otherwise, just check type matches
        else:
            if type(actual) == type(expected):
                return MatchResult(passed=True, field_path=path)
            else:
                return MatchResult(
                    passed=False,
                    field_path=path,
                    expected=type(expected).__name__,
                    actual=type(actual).__name__,
                    failures=[f"Type mismatch at '{path}': expected {type(expected).__name__}, got {type(actual).__name__}"]
                )


# ============================================================================
# CONSUMER-DRIVEN CONTRACT REGISTRY - AC-3
# ============================================================================

class ConsumerDrivenContractRegistry:
    """
    Manages consumer-driven contracts (Pact-style) - AC-3.

    Flow:
    1. Consumer writes expectations and publishes to registry
    2. Provider retrieves expectations and verifies implementation
    3. Provider publishes verification results
    4. Registry tracks which consumer/provider versions are compatible

    Attributes:
        expectations: Provider -> list of consumer expectations
        verification_matrix: Tracks version compatibility
        matcher_engine: Engine for matching values
    """

    def __init__(self):
        """Initialize the registry."""
        self.expectations: Dict[str, List[ConsumerExpectation]] = {}
        self.verification_matrix: Dict[str, Dict[str, Dict[str, bool]]] = {}
        self.verification_results: Dict[str, ProviderVerificationResult] = {}
        self.matcher_engine = MatcherEngine()

    def publish_consumer_expectation(
        self,
        expectation: ConsumerExpectation
    ) -> str:
        """
        Consumer publishes their expectations.

        Args:
            expectation: Consumer's expectation of provider

        Returns:
            Expectation ID
        """
        provider = expectation.provider_agent

        if provider not in self.expectations:
            self.expectations[provider] = []

        # Check for duplicate
        existing_ids = [e.expectation_id for e in self.expectations[provider]]
        if expectation.expectation_id in existing_ids:
            # Update existing
            for i, e in enumerate(self.expectations[provider]):
                if e.expectation_id == expectation.expectation_id:
                    self.expectations[provider][i] = expectation
                    break
            logger.info(f"Updated expectation {expectation.expectation_id}")
        else:
            self.expectations[provider].append(expectation)
            logger.info(
                f"Consumer {expectation.consumer_agent} published expectation "
                f"for provider {provider}"
            )

        return expectation.expectation_id

    def get_expectations_for_provider(
        self,
        provider_agent: str,
        consumer_agent: Optional[str] = None
    ) -> List[ConsumerExpectation]:
        """
        Provider retrieves consumer expectations.

        Args:
            provider_agent: Provider identifier
            consumer_agent: Optional filter by consumer

        Returns:
            List of consumer expectations
        """
        expectations = self.expectations.get(provider_agent, [])

        if consumer_agent:
            expectations = [e for e in expectations if e.consumer_agent == consumer_agent]

        return expectations

    def get_consumers_for_provider(self, provider_agent: str) -> List[str]:
        """Get list of consumers that have expectations for a provider."""
        expectations = self.expectations.get(provider_agent, [])
        return list(set(e.consumer_agent for e in expectations))

    def record_verification(
        self,
        provider: str,
        provider_version: str,
        consumer: str,
        consumer_version: str,
        passed: bool
    ) -> None:
        """
        Record a verification result in the compatibility matrix.

        Args:
            provider: Provider identifier
            provider_version: Provider version
            consumer: Consumer identifier
            consumer_version: Consumer version
            passed: Whether verification passed
        """
        key = f"{provider}:{consumer}"

        if key not in self.verification_matrix:
            self.verification_matrix[key] = {}

        if consumer_version not in self.verification_matrix[key]:
            self.verification_matrix[key][consumer_version] = {}

        self.verification_matrix[key][consumer_version][provider_version] = passed

    def is_compatible(
        self,
        provider: str,
        provider_version: str,
        consumer: str,
        consumer_version: str
    ) -> Optional[bool]:
        """
        Check if a provider/consumer version pair is compatible.

        Args:
            provider: Provider identifier
            provider_version: Provider version
            consumer: Consumer identifier
            consumer_version: Consumer version

        Returns:
            True if compatible, False if incompatible, None if not verified
        """
        key = f"{provider}:{consumer}"

        try:
            return self.verification_matrix[key][consumer_version][provider_version]
        except KeyError:
            return None

    def get_compatible_versions(
        self,
        provider: str,
        consumer: str,
        consumer_version: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Get compatible provider versions for a consumer.

        Args:
            provider: Provider identifier
            consumer: Consumer identifier
            consumer_version: Optional specific consumer version

        Returns:
            Dict mapping consumer versions to compatible provider versions
        """
        key = f"{provider}:{consumer}"

        if key not in self.verification_matrix:
            return {}

        result = {}
        for cv, provider_versions in self.verification_matrix[key].items():
            if consumer_version and cv != consumer_version:
                continue

            compatible = [pv for pv, passed in provider_versions.items() if passed]
            if compatible:
                result[cv] = compatible

        return result


# ============================================================================
# CONTRACT TEST RUNNER - AC-5: Automated testing
# ============================================================================

class ContractTestRunner:
    """
    Runs contract tests for providers against consumer expectations (AC-5).

    Supports:
    - Running all expectations for a provider
    - Running specific consumer expectations
    - Setting up provider state
    - Generating test reports
    """

    def __init__(
        self,
        registry: ConsumerDrivenContractRegistry,
        provider_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    ):
        """
        Initialize the test runner.

        Args:
            registry: Contract registry
            provider_handler: Function to execute interactions against provider
        """
        self.registry = registry
        self.matcher_engine = MatcherEngine()
        self.provider_handler = provider_handler
        self._provider_states: Dict[str, Callable[[], None]] = {}

    def register_provider_state(
        self,
        state_name: str,
        setup_fn: Callable[[], None]
    ) -> None:
        """
        Register a provider state setup function.

        Args:
            state_name: Name of the provider state
            setup_fn: Function to set up the state
        """
        self._provider_states[state_name] = setup_fn

    def set_provider_handler(
        self,
        handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        """
        Set the provider handler for executing interactions.

        Args:
            handler: Function that takes a request and returns a response
        """
        self.provider_handler = handler

    def verify_provider(
        self,
        provider_agent: str,
        provider_version: str,
        consumer_agent: Optional[str] = None
    ) -> ProviderVerificationResult:
        """
        Verify provider against all consumer expectations (AC-4).

        Args:
            provider_agent: Provider identifier
            provider_version: Provider version
            consumer_agent: Optional filter by consumer

        Returns:
            ProviderVerificationResult with all results
        """
        expectations = self.registry.get_expectations_for_provider(
            provider_agent, consumer_agent
        )

        if not expectations:
            return ProviderVerificationResult(
                provider=provider_agent,
                provider_version=provider_version,
                total_expectations=0,
                verified=0,
                failed=0,
                results=[]
            )

        results = []
        for expectation in expectations:
            verification = self._verify_expectation(
                expectation, provider_version
            )
            results.append(verification)

            # Record in compatibility matrix
            self.registry.record_verification(
                provider=provider_agent,
                provider_version=provider_version,
                consumer=expectation.consumer_agent,
                consumer_version=expectation.consumer_version,
                passed=verification.passed
            )

            # Update expectation
            if verification.passed:
                expectation.verified_by_provider = True
                expectation.verification_date = datetime.utcnow()

        verified_count = sum(1 for r in results if r.passed)
        failed_count = len(results) - verified_count

        result = ProviderVerificationResult(
            provider=provider_agent,
            provider_version=provider_version,
            total_expectations=len(expectations),
            verified=verified_count,
            failed=failed_count,
            results=results
        )

        # Store result
        self.registry.verification_results[f"{provider_agent}:{provider_version}"] = result

        return result

    def _verify_expectation(
        self,
        expectation: ConsumerExpectation,
        provider_version: str
    ) -> ExpectationVerification:
        """Verify a single consumer expectation."""
        interaction_results = []
        all_passed = True

        for interaction in expectation.interactions:
            result = self._verify_interaction(interaction)
            interaction_results.append(result)

            if result.status != VerificationStatus.PASSED:
                all_passed = False

        return ExpectationVerification(
            expectation_id=expectation.expectation_id,
            consumer=expectation.consumer_agent,
            consumer_version=expectation.consumer_version,
            provider_version=provider_version,
            status=VerificationStatus.PASSED if all_passed else VerificationStatus.FAILED,
            interaction_results=interaction_results
        )

    def _verify_interaction(self, interaction: InteractionPact) -> InteractionResult:
        """Verify a single interaction."""
        import time
        start_time = time.time()

        try:
            # Set up provider state if needed
            if interaction.provider_state:
                self._setup_provider_state(interaction.provider_state)

            # Execute interaction
            if self.provider_handler:
                response = self.provider_handler(interaction.request)
            else:
                # Simulate response for testing
                response = interaction.response

            # Match response
            match_results = self._match_response(
                response,
                interaction.response,
                interaction.matchers
            )

            duration_ms = (time.time() - start_time) * 1000

            all_passed = all(r.passed for r in match_results)

            return InteractionResult(
                interaction_description=interaction.description,
                status=VerificationStatus.PASSED if all_passed else VerificationStatus.FAILED,
                request_sent=interaction.request,
                response_received=response,
                match_results=match_results,
                duration_ms=duration_ms
            )

        except Exception as e:
            return InteractionResult(
                interaction_description=interaction.description,
                status=VerificationStatus.FAILED,
                request_sent=interaction.request,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000
            )

    def _setup_provider_state(self, state_name: str) -> None:
        """Set up provider state before interaction."""
        if state_name in self._provider_states:
            self._provider_states[state_name]()
        else:
            logger.warning(f"Provider state '{state_name}' not registered")

    def _match_response(
        self,
        actual: Dict[str, Any],
        expected: Dict[str, Any],
        matchers: Dict[str, MatcherSpec]
    ) -> List[MatchResult]:
        """Match actual response against expected."""
        results = []

        # Match status if present
        if "status" in expected:
            status_result = self.matcher_engine.match(
                actual.get("status"),
                expected["status"],
                path="status"
            )
            results.append(status_result)

        # Match body if present
        if "body" in expected:
            body_result = self._match_body(
                actual.get("body", actual),
                expected["body"],
                matchers
            )
            results.extend(body_result)

        return results

    def _match_body(
        self,
        actual: Any,
        expected: Any,
        matchers: Dict[str, MatcherSpec]
    ) -> List[MatchResult]:
        """Match response body with matchers."""
        results = []

        if isinstance(expected, dict):
            for field, exp_value in expected.items():
                path = f"body.{field}"

                # Use field-specific matcher if provided
                if field in matchers:
                    result = self.matcher_engine.match(
                        actual.get(field) if isinstance(actual, dict) else actual,
                        exp_value,
                        matchers[field],
                        path
                    )
                else:
                    result = self.matcher_engine.match(
                        actual.get(field) if isinstance(actual, dict) else actual,
                        exp_value,
                        path=path
                    )

                results.append(result)
        else:
            result = self.matcher_engine.match(actual, expected, path="body")
            results.append(result)

        return results

    def generate_report(
        self,
        result: ProviderVerificationResult
    ) -> Dict[str, Any]:
        """
        Generate a test report from verification results.

        Args:
            result: Provider verification result

        Returns:
            Report dictionary
        """
        return {
            "provider": result.provider,
            "provider_version": result.provider_version,
            "verified_at": result.verified_at.isoformat(),
            "summary": {
                "total_expectations": result.total_expectations,
                "passed": result.verified,
                "failed": result.failed,
                "pass_rate": result.pass_rate
            },
            "results": [
                {
                    "expectation_id": r.expectation_id,
                    "consumer": r.consumer,
                    "consumer_version": r.consumer_version,
                    "status": r.status.value,
                    "interactions": [
                        {
                            "description": ir.interaction_description,
                            "status": ir.status.value,
                            "duration_ms": ir.duration_ms,
                            "failures": [
                                mr.failures for mr in ir.match_results if not mr.passed
                            ],
                            "error": ir.error
                        }
                        for ir in r.interaction_results
                    ]
                }
                for r in result.results
            ]
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_expectation(
    consumer: str,
    provider: str,
    description: str,
    request: Dict[str, Any],
    response: Dict[str, Any],
    matchers: Optional[Dict[str, MatcherSpec]] = None,
    provider_state: Optional[str] = None
) -> ConsumerExpectation:
    """
    Create a consumer expectation with a single interaction.

    Args:
        consumer: Consumer identifier
        provider: Provider identifier
        description: Interaction description
        request: Request specification
        response: Expected response
        matchers: Optional field matchers
        provider_state: Optional required provider state

    Returns:
        ConsumerExpectation with the interaction
    """
    interaction = InteractionPact(
        description=description,
        provider_state=provider_state,
        request=request,
        response=response,
        matchers=matchers or {}
    )

    return ConsumerExpectation(
        expectation_id="",  # Will be auto-generated
        consumer_agent=consumer,
        provider_agent=provider,
        interactions=[interaction]
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "MatcherType",
    "VerificationStatus",
    "InteractionType",
    # Matchers (AC-2)
    "MatcherSpec",
    "PactMatchers",
    # Data classes
    "InteractionPact",
    "ConsumerExpectation",
    "MatchResult",
    "InteractionResult",
    "ExpectationVerification",
    "ProviderVerificationResult",
    # Core classes
    "MatcherEngine",
    "ConsumerDrivenContractRegistry",
    "ContractTestRunner",
    # Utilities
    "create_expectation",
]
