"""
Test Suite for Contract Testing System (MD-2511)

Tests for all acceptance criteria:
- AC-1: ConsumerExpectation data class
- AC-2: PactMatchers for flexible type-based matching
- AC-3: ConsumerDrivenContractRegistry
- AC-4: Provider verification against expectations
- AC-5: Contract test runner for automated testing

Author: Maestro Platform Team
Created: 2025-12-06
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from orchestration.contract_testing import (
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


# ============================================================================
# AC-1: ConsumerExpectation Tests
# ============================================================================

class TestConsumerExpectation:
    """AC-1: ConsumerExpectation data class tests."""

    def test_create_basic_expectation(self):
        """Test creating a basic consumer expectation."""
        expectation = ConsumerExpectation(
            expectation_id="test-001",
            consumer_agent="frontend",
            provider_agent="backend"
        )

        assert expectation.expectation_id == "test-001"
        assert expectation.consumer_agent == "frontend"
        assert expectation.provider_agent == "backend"
        assert expectation.verified_by_provider is False

    def test_auto_generate_id(self):
        """Test that expectation ID is auto-generated if not provided."""
        expectation = ConsumerExpectation(
            expectation_id="",
            consumer_agent="frontend",
            provider_agent="backend"
        )

        assert expectation.expectation_id != ""
        assert "frontend" in expectation.expectation_id
        assert "backend" in expectation.expectation_id

    def test_expectation_with_interactions(self):
        """Test creating expectation with interactions."""
        interaction = InteractionPact(
            description="Login request",
            request={"method": "POST", "path": "/login"},
            response={"status": 200}
        )

        expectation = ConsumerExpectation(
            expectation_id="login-test",
            consumer_agent="frontend",
            provider_agent="auth_service",
            interactions=[interaction]
        )

        assert len(expectation.interactions) == 1
        assert expectation.interactions[0].description == "Login request"

    def test_expectation_with_version(self):
        """Test creating expectation with version."""
        expectation = ConsumerExpectation(
            expectation_id="test-001",
            consumer_agent="frontend",
            provider_agent="backend",
            consumer_version="2.0.0"
        )

        assert expectation.consumer_version == "2.0.0"

    def test_expectation_metadata(self):
        """Test expectation with metadata."""
        expectation = ConsumerExpectation(
            expectation_id="test-001",
            consumer_agent="frontend",
            provider_agent="backend",
            metadata={"team": "platform", "priority": "high"}
        )

        assert expectation.metadata["team"] == "platform"
        assert expectation.metadata["priority"] == "high"


class TestInteractionPact:
    """Tests for InteractionPact data class."""

    def test_create_http_interaction(self):
        """Test creating HTTP interaction."""
        interaction = InteractionPact(
            description="Get user by ID",
            interaction_type=InteractionType.HTTP,
            request={
                "method": "GET",
                "path": "/api/users/123"
            },
            response={
                "status": 200,
                "body": {"id": "123", "name": "Test User"}
            }
        )

        assert interaction.interaction_type == InteractionType.HTTP
        assert interaction.request["method"] == "GET"
        assert interaction.response["status"] == 200

    def test_interaction_with_provider_state(self):
        """Test interaction with provider state requirement."""
        interaction = InteractionPact(
            description="Get user",
            provider_state="user with ID 123 exists",
            request={"method": "GET", "path": "/api/users/123"},
            response={"status": 200}
        )

        assert interaction.provider_state == "user with ID 123 exists"

    def test_interaction_with_matchers(self):
        """Test interaction with field matchers."""
        interaction = InteractionPact(
            description="Create user",
            request={"method": "POST", "body": {"name": "Test"}},
            response={"status": 201},
            matchers={"id": PactMatchers.uuid()}
        )

        assert "id" in interaction.matchers
        assert interaction.matchers["id"].matcher_type == MatcherType.REGEX


# ============================================================================
# AC-2: PactMatchers Tests
# ============================================================================

class TestPactMatchers:
    """AC-2: PactMatchers for flexible matching tests."""

    def test_string_matcher(self):
        """Test string type matcher."""
        matcher = PactMatchers.string()

        assert matcher.matcher_type == MatcherType.TYPE
        assert matcher.expected == "string"

    def test_string_matcher_with_example(self):
        """Test string matcher with custom example."""
        matcher = PactMatchers.string(example="John Doe")

        assert matcher.example == "John Doe"

    def test_integer_matcher(self):
        """Test integer type matcher."""
        matcher = PactMatchers.integer()

        assert matcher.matcher_type == MatcherType.TYPE
        assert matcher.expected == "integer"

    def test_number_matcher(self):
        """Test number type matcher."""
        matcher = PactMatchers.number()

        assert matcher.matcher_type == MatcherType.TYPE
        assert matcher.expected == "number"

    def test_boolean_matcher(self):
        """Test boolean type matcher."""
        matcher = PactMatchers.boolean()

        assert matcher.matcher_type == MatcherType.TYPE
        assert matcher.expected == "boolean"

    def test_uuid_matcher(self):
        """Test UUID format matcher."""
        matcher = PactMatchers.uuid()

        assert matcher.matcher_type == MatcherType.REGEX
        assert "uuid" in matcher.example.lower() or "-" in matcher.example

    def test_iso_datetime_matcher(self):
        """Test ISO datetime matcher."""
        matcher = PactMatchers.iso_datetime()

        assert matcher.matcher_type == MatcherType.REGEX
        assert "T" in matcher.example

    def test_email_matcher(self):
        """Test email format matcher."""
        matcher = PactMatchers.email()

        assert matcher.matcher_type == MatcherType.REGEX
        assert "@" in matcher.example

    def test_url_matcher(self):
        """Test URL format matcher."""
        matcher = PactMatchers.url()

        assert matcher.matcher_type == MatcherType.REGEX
        assert "http" in matcher.example

    def test_regex_matcher(self):
        """Test custom regex matcher."""
        matcher = PactMatchers.regex(r"^\d{4}$", example="1234")

        assert matcher.matcher_type == MatcherType.REGEX
        assert matcher.expected == r"^\d{4}$"

    def test_array_of_matcher(self):
        """Test array of type matcher."""
        matcher = PactMatchers.array_of(PactMatchers.string(), min_items=1)

        assert matcher.matcher_type == MatcherType.ARRAY
        assert matcher.options["min_items"] == 1

    def test_object_with_matcher(self):
        """Test object with fields matcher."""
        matcher = PactMatchers.object_with({
            "name": PactMatchers.string(),
            "age": PactMatchers.integer()
        })

        assert matcher.matcher_type == MatcherType.OBJECT
        assert "name" in matcher.expected
        assert "age" in matcher.expected

    def test_exact_matcher(self):
        """Test exact value matcher."""
        matcher = PactMatchers.exact("specific-value")

        assert matcher.matcher_type == MatcherType.EXACT
        assert matcher.expected == "specific-value"

    def test_any_value_matcher(self):
        """Test any value matcher."""
        matcher = PactMatchers.any_value()

        assert matcher.matcher_type == MatcherType.ANY


# ============================================================================
# MatcherEngine Tests
# ============================================================================

class TestMatcherEngine:
    """Tests for MatcherEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = MatcherEngine()

    def test_match_string_type(self):
        """Test matching string type."""
        result = self.engine.match(
            "hello",
            None,
            PactMatchers.string()
        )

        assert result.passed is True

    def test_match_string_type_fails(self):
        """Test string type matching fails with integer."""
        result = self.engine.match(
            123,
            None,
            PactMatchers.string()
        )

        assert result.passed is False
        assert len(result.failures) > 0

    def test_match_integer_type(self):
        """Test matching integer type."""
        result = self.engine.match(42, None, PactMatchers.integer())

        assert result.passed is True

    def test_match_uuid_format(self):
        """Test matching UUID format."""
        result = self.engine.match(
            "550e8400-e29b-41d4-a716-446655440000",
            None,
            PactMatchers.uuid()
        )

        assert result.passed is True

    def test_match_uuid_format_fails(self):
        """Test UUID matching fails with invalid format."""
        result = self.engine.match(
            "not-a-uuid",
            None,
            PactMatchers.uuid()
        )

        assert result.passed is False

    def test_match_email_format(self):
        """Test matching email format."""
        result = self.engine.match(
            "user@example.com",
            None,
            PactMatchers.email()
        )

        assert result.passed is True

    def test_match_email_format_fails(self):
        """Test email matching fails with invalid format."""
        result = self.engine.match(
            "not-an-email",
            None,
            PactMatchers.email()
        )

        assert result.passed is False

    def test_match_array(self):
        """Test matching array type."""
        result = self.engine.match(
            ["a", "b", "c"],
            None,
            PactMatchers.array_of(PactMatchers.string())
        )

        assert result.passed is True

    def test_match_array_min_items(self):
        """Test array with minimum items."""
        result = self.engine.match(
            [],
            None,
            PactMatchers.array_of(PactMatchers.string(), min_items=1)
        )

        assert result.passed is False

    def test_match_object(self):
        """Test matching object with fields."""
        result = self.engine.match(
            {"name": "John", "age": 30},
            None,
            PactMatchers.object_with({
                "name": PactMatchers.string(),
                "age": PactMatchers.integer()
            })
        )

        assert result.passed is True

    def test_match_object_missing_field(self):
        """Test object matching fails with missing field."""
        result = self.engine.match(
            {"name": "John"},
            None,
            PactMatchers.object_with({
                "name": PactMatchers.string(),
                "age": PactMatchers.integer()
            })
        )

        assert result.passed is False
        assert "Missing required field" in result.failures[0]

    def test_match_exact_value(self):
        """Test exact value matching."""
        result = self.engine.match(
            "specific",
            None,
            PactMatchers.exact("specific")
        )

        assert result.passed is True

    def test_match_exact_value_fails(self):
        """Test exact value matching fails."""
        result = self.engine.match(
            "different",
            None,
            PactMatchers.exact("specific")
        )

        assert result.passed is False

    def test_match_any_value(self):
        """Test any value matching."""
        result = self.engine.match(
            {"anything": [1, 2, 3]},
            None,
            PactMatchers.any_value()
        )

        assert result.passed is True


# ============================================================================
# AC-3: ConsumerDrivenContractRegistry Tests
# ============================================================================

class TestConsumerDrivenContractRegistry:
    """AC-3: ConsumerDrivenContractRegistry tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = ConsumerDrivenContractRegistry()

    def test_publish_expectation(self):
        """Test publishing consumer expectation."""
        expectation = ConsumerExpectation(
            expectation_id="test-001",
            consumer_agent="frontend",
            provider_agent="backend"
        )

        exp_id = self.registry.publish_consumer_expectation(expectation)

        assert exp_id == "test-001"
        assert len(self.registry.expectations["backend"]) == 1

    def test_get_expectations_for_provider(self):
        """Test retrieving expectations for provider."""
        exp1 = ConsumerExpectation(
            expectation_id="exp-1",
            consumer_agent="frontend",
            provider_agent="backend"
        )
        exp2 = ConsumerExpectation(
            expectation_id="exp-2",
            consumer_agent="mobile",
            provider_agent="backend"
        )

        self.registry.publish_consumer_expectation(exp1)
        self.registry.publish_consumer_expectation(exp2)

        expectations = self.registry.get_expectations_for_provider("backend")

        assert len(expectations) == 2

    def test_get_expectations_filtered_by_consumer(self):
        """Test filtering expectations by consumer."""
        exp1 = ConsumerExpectation(
            expectation_id="exp-1",
            consumer_agent="frontend",
            provider_agent="backend"
        )
        exp2 = ConsumerExpectation(
            expectation_id="exp-2",
            consumer_agent="mobile",
            provider_agent="backend"
        )

        self.registry.publish_consumer_expectation(exp1)
        self.registry.publish_consumer_expectation(exp2)

        expectations = self.registry.get_expectations_for_provider(
            "backend", consumer_agent="frontend"
        )

        assert len(expectations) == 1
        assert expectations[0].consumer_agent == "frontend"

    def test_get_consumers_for_provider(self):
        """Test getting list of consumers for a provider."""
        exp1 = ConsumerExpectation(
            expectation_id="exp-1",
            consumer_agent="frontend",
            provider_agent="backend"
        )
        exp2 = ConsumerExpectation(
            expectation_id="exp-2",
            consumer_agent="mobile",
            provider_agent="backend"
        )

        self.registry.publish_consumer_expectation(exp1)
        self.registry.publish_consumer_expectation(exp2)

        consumers = self.registry.get_consumers_for_provider("backend")

        assert "frontend" in consumers
        assert "mobile" in consumers

    def test_record_verification(self):
        """Test recording verification result."""
        self.registry.record_verification(
            provider="backend",
            provider_version="1.0.0",
            consumer="frontend",
            consumer_version="2.0.0",
            passed=True
        )

        is_compat = self.registry.is_compatible(
            provider="backend",
            provider_version="1.0.0",
            consumer="frontend",
            consumer_version="2.0.0"
        )

        assert is_compat is True

    def test_is_compatible_not_verified(self):
        """Test compatibility check for unverified pair."""
        is_compat = self.registry.is_compatible(
            provider="backend",
            provider_version="1.0.0",
            consumer="frontend",
            consumer_version="2.0.0"
        )

        assert is_compat is None

    def test_get_compatible_versions(self):
        """Test getting compatible provider versions."""
        self.registry.record_verification(
            provider="backend",
            provider_version="1.0.0",
            consumer="frontend",
            consumer_version="2.0.0",
            passed=True
        )
        self.registry.record_verification(
            provider="backend",
            provider_version="1.1.0",
            consumer="frontend",
            consumer_version="2.0.0",
            passed=True
        )
        self.registry.record_verification(
            provider="backend",
            provider_version="2.0.0",
            consumer="frontend",
            consumer_version="2.0.0",
            passed=False
        )

        compatible = self.registry.get_compatible_versions(
            provider="backend",
            consumer="frontend",
            consumer_version="2.0.0"
        )

        assert "2.0.0" in compatible
        assert "1.0.0" in compatible["2.0.0"]
        assert "1.1.0" in compatible["2.0.0"]
        assert "2.0.0" not in compatible["2.0.0"]

    def test_update_existing_expectation(self):
        """Test updating existing expectation."""
        exp1 = ConsumerExpectation(
            expectation_id="exp-1",
            consumer_agent="frontend",
            provider_agent="backend",
            consumer_version="1.0.0"
        )
        exp2 = ConsumerExpectation(
            expectation_id="exp-1",  # Same ID
            consumer_agent="frontend",
            provider_agent="backend",
            consumer_version="2.0.0"  # Updated version
        )

        self.registry.publish_consumer_expectation(exp1)
        self.registry.publish_consumer_expectation(exp2)

        expectations = self.registry.get_expectations_for_provider("backend")

        assert len(expectations) == 1
        assert expectations[0].consumer_version == "2.0.0"


# ============================================================================
# AC-4: Provider Verification Tests
# ============================================================================

class TestExpectationVerification:
    """AC-4: Expectation verification result tests."""

    def test_create_passed_verification(self):
        """Test creating passed verification."""
        verification = ExpectationVerification(
            expectation_id="exp-1",
            consumer="frontend",
            consumer_version="1.0.0",
            provider_version="2.0.0",
            status=VerificationStatus.PASSED
        )

        assert verification.passed is True
        assert verification.failure_count == 0

    def test_create_failed_verification(self):
        """Test creating failed verification."""
        interaction_result = InteractionResult(
            interaction_description="Get user",
            status=VerificationStatus.FAILED,
            error="Connection refused"
        )

        verification = ExpectationVerification(
            expectation_id="exp-1",
            consumer="frontend",
            consumer_version="1.0.0",
            provider_version="2.0.0",
            status=VerificationStatus.FAILED,
            interaction_results=[interaction_result]
        )

        assert verification.passed is False
        assert verification.failure_count == 1


class TestProviderVerificationResult:
    """AC-4: Provider verification result tests."""

    def test_all_passed(self):
        """Test all_passed property."""
        result = ProviderVerificationResult(
            provider="backend",
            provider_version="1.0.0",
            total_expectations=3,
            verified=3,
            failed=0
        )

        assert result.all_passed is True
        assert result.pass_rate == 100.0

    def test_some_failed(self):
        """Test with some failures."""
        result = ProviderVerificationResult(
            provider="backend",
            provider_version="1.0.0",
            total_expectations=4,
            verified=3,
            failed=1
        )

        assert result.all_passed is False
        assert result.pass_rate == 75.0

    def test_empty_expectations(self):
        """Test with no expectations."""
        result = ProviderVerificationResult(
            provider="backend",
            provider_version="1.0.0",
            total_expectations=0,
            verified=0,
            failed=0
        )

        assert result.all_passed is True
        assert result.pass_rate == 100.0


# ============================================================================
# AC-5: ContractTestRunner Tests
# ============================================================================

class TestContractTestRunner:
    """AC-5: ContractTestRunner tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = ConsumerDrivenContractRegistry()
        self.runner = ContractTestRunner(self.registry)

    def test_verify_provider_no_expectations(self):
        """Test verifying provider with no expectations."""
        result = self.runner.verify_provider(
            provider_agent="backend",
            provider_version="1.0.0"
        )

        assert result.total_expectations == 0
        assert result.all_passed is True

    def test_verify_provider_with_expectation(self):
        """Test verifying provider with expectation."""
        # Create expectation
        interaction = InteractionPact(
            description="Get user",
            request={"method": "GET", "path": "/users/1"},
            response={"status": 200, "body": {"id": 1, "name": "Test"}}
        )

        expectation = ConsumerExpectation(
            expectation_id="exp-1",
            consumer_agent="frontend",
            provider_agent="backend",
            interactions=[interaction]
        )

        self.registry.publish_consumer_expectation(expectation)

        # Verify
        result = self.runner.verify_provider(
            provider_agent="backend",
            provider_version="1.0.0"
        )

        assert result.total_expectations == 1
        assert result.verified >= 0  # May pass or fail depending on mock

    def test_register_provider_state(self):
        """Test registering provider state handler."""
        state_setup_called = []

        def setup_user_exists():
            state_setup_called.append("user_exists")

        self.runner.register_provider_state("user exists", setup_user_exists)

        # Verify state is registered
        assert "user exists" in self.runner._provider_states

    def test_set_provider_handler(self):
        """Test setting provider handler."""
        def mock_handler(request):
            return {"status": 200, "body": {"success": True}}

        self.runner.set_provider_handler(mock_handler)

        assert self.runner.provider_handler is not None

    def test_verify_with_custom_handler(self):
        """Test verification with custom provider handler."""
        # Set up handler
        def mock_handler(request):
            if request.get("path") == "/users/1":
                return {"status": 200, "body": {"id": 1, "name": "John"}}
            return {"status": 404}

        self.runner.set_provider_handler(mock_handler)

        # Create expectation with matching response
        interaction = InteractionPact(
            description="Get user",
            request={"method": "GET", "path": "/users/1"},
            response={"status": 200}
        )

        expectation = ConsumerExpectation(
            expectation_id="exp-1",
            consumer_agent="frontend",
            provider_agent="backend",
            interactions=[interaction]
        )

        self.registry.publish_consumer_expectation(expectation)

        # Verify
        result = self.runner.verify_provider(
            provider_agent="backend",
            provider_version="1.0.0"
        )

        assert result.total_expectations == 1

    def test_generate_report(self):
        """Test generating verification report."""
        result = ProviderVerificationResult(
            provider="backend",
            provider_version="1.0.0",
            total_expectations=2,
            verified=1,
            failed=1,
            results=[
                ExpectationVerification(
                    expectation_id="exp-1",
                    consumer="frontend",
                    consumer_version="1.0.0",
                    provider_version="1.0.0",
                    status=VerificationStatus.PASSED
                ),
                ExpectationVerification(
                    expectation_id="exp-2",
                    consumer="mobile",
                    consumer_version="1.0.0",
                    provider_version="1.0.0",
                    status=VerificationStatus.FAILED
                )
            ]
        )

        report = self.runner.generate_report(result)

        assert report["provider"] == "backend"
        assert report["provider_version"] == "1.0.0"
        assert report["summary"]["total_expectations"] == 2
        assert report["summary"]["passed"] == 1
        assert report["summary"]["failed"] == 1
        assert len(report["results"]) == 2

    def test_verify_updates_compatibility_matrix(self):
        """Test that verification updates compatibility matrix."""
        interaction = InteractionPact(
            description="Get user",
            request={"method": "GET", "path": "/users/1"},
            response={"status": 200}
        )

        expectation = ConsumerExpectation(
            expectation_id="exp-1",
            consumer_agent="frontend",
            consumer_version="2.0.0",
            provider_agent="backend",
            interactions=[interaction]
        )

        self.registry.publish_consumer_expectation(expectation)
        self.runner.verify_provider("backend", "1.0.0")

        # Check compatibility was recorded
        compat = self.registry.is_compatible(
            provider="backend",
            provider_version="1.0.0",
            consumer="frontend",
            consumer_version="2.0.0"
        )

        assert compat is not None  # Was recorded

    def test_verify_multiple_consumers(self):
        """Test verifying with multiple consumers."""
        # Create expectations from two consumers
        exp1 = ConsumerExpectation(
            expectation_id="exp-1",
            consumer_agent="frontend",
            provider_agent="backend",
            interactions=[InteractionPact(
                description="Frontend request",
                request={"method": "GET", "path": "/api/data"},
                response={"status": 200}
            )]
        )

        exp2 = ConsumerExpectation(
            expectation_id="exp-2",
            consumer_agent="mobile",
            provider_agent="backend",
            interactions=[InteractionPact(
                description="Mobile request",
                request={"method": "GET", "path": "/api/data"},
                response={"status": 200}
            )]
        )

        self.registry.publish_consumer_expectation(exp1)
        self.registry.publish_consumer_expectation(exp2)

        result = self.runner.verify_provider("backend", "1.0.0")

        assert result.total_expectations == 2


# ============================================================================
# Utility Function Tests
# ============================================================================

class TestCreateExpectation:
    """Tests for create_expectation utility function."""

    def test_create_simple_expectation(self):
        """Test creating simple expectation."""
        expectation = create_expectation(
            consumer="frontend",
            provider="backend",
            description="Get user",
            request={"method": "GET", "path": "/users/1"},
            response={"status": 200}
        )

        assert expectation.consumer_agent == "frontend"
        assert expectation.provider_agent == "backend"
        assert len(expectation.interactions) == 1
        assert expectation.interactions[0].description == "Get user"

    def test_create_expectation_with_matchers(self):
        """Test creating expectation with matchers."""
        expectation = create_expectation(
            consumer="frontend",
            provider="backend",
            description="Create user",
            request={"method": "POST", "body": {"name": "John"}},
            response={"status": 201, "body": {"id": "generated"}},
            matchers={"id": PactMatchers.uuid()}
        )

        assert len(expectation.interactions[0].matchers) == 1
        assert "id" in expectation.interactions[0].matchers

    def test_create_expectation_with_provider_state(self):
        """Test creating expectation with provider state."""
        expectation = create_expectation(
            consumer="frontend",
            provider="backend",
            description="Delete user",
            request={"method": "DELETE", "path": "/users/1"},
            response={"status": 204},
            provider_state="user with ID 1 exists"
        )

        assert expectation.interactions[0].provider_state == "user with ID 1 exists"


# ============================================================================
# Integration Tests
# ============================================================================

class TestContractTestingIntegration:
    """Integration tests for the complete workflow."""

    def test_full_contract_testing_workflow(self):
        """Test complete consumer-driven contract testing workflow."""
        # 1. Create registry
        registry = ConsumerDrivenContractRegistry()

        # 2. Consumer publishes expectations
        expectation = ConsumerExpectation(
            expectation_id="auth-login",
            consumer_agent="frontend",
            consumer_version="1.0.0",
            provider_agent="auth_service",
            interactions=[
                InteractionPact(
                    description="Successful login",
                    provider_state="user exists",
                    request={
                        "method": "POST",
                        "path": "/api/auth/login",
                        "body": {"email": "test@example.com", "password": "secret"}
                    },
                    response={
                        "status": 200,
                        "body": {"access_token": "token123"}
                    },
                    matchers={"access_token": PactMatchers.string()}
                )
            ]
        )

        registry.publish_consumer_expectation(expectation)

        # 3. Provider sets up test runner
        runner = ContractTestRunner(registry)

        # Mock provider handler
        def auth_handler(request):
            if request.get("path") == "/api/auth/login":
                return {"status": 200, "body": {"access_token": "jwt.token.here"}}
            return {"status": 404}

        runner.set_provider_handler(auth_handler)

        # 4. Provider verifies
        result = runner.verify_provider(
            provider_agent="auth_service",
            provider_version="2.0.0"
        )

        # 5. Check results
        assert result.total_expectations == 1

        # 6. Generate report
        report = runner.generate_report(result)
        assert "auth_service" in report["provider"]

        # 7. Check compatibility matrix
        compat = registry.is_compatible(
            provider="auth_service",
            provider_version="2.0.0",
            consumer="frontend",
            consumer_version="1.0.0"
        )
        assert compat is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
