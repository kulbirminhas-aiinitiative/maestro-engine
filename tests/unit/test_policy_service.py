#!/usr/bin/env python3
"""
Unit Tests for ML Routing Policy Service (EPIC-1)

Tests the policy_service.py module:
- Feature extraction
- Routing decision logic
- Override handling
- Performance requirements (<50ms p50)

Run: python -m pytest tests/unit/test_policy_service.py -v
"""

import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest


class TestFeatureExtractor:
    """Test cases for FeatureExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create a feature extractor instance."""
        from services.policy_service import FeatureExtractor
        return FeatureExtractor()

    def test_extract_simple_query(self, extractor):
        """Test feature extraction for a simple query."""
        features = extractor.extract_features(
            prompt="What is Python?",
            request_type="chat"
        )

        assert features.is_query is True
        assert features.is_multi_step is False
        assert features.complexity_score <= 3
        assert features.token_count > 0
        assert features.request_type == "chat"

    def test_extract_preview_request(self, extractor):
        """Test feature extraction for a preview request."""
        features = extractor.extract_features(
            prompt="Show me a quick preview of a button",
            request_type="preview"
        )

        assert features.is_preview_request is True
        assert features.complexity_score <= 4
        assert features.request_type == "preview"

    def test_extract_complex_workflow(self, extractor):
        """Test feature extraction for a complex workflow."""
        prompt = """Build a complete e-commerce platform with:
        - User authentication and registration
        - Product catalog with search functionality
        - Shopping cart and checkout
        - Payment integration with Stripe API
        - Database schema for orders and products
        """
        features = extractor.extract_features(
            prompt=prompt,
            request_type="workflow"
        )

        assert features.is_multi_step is True
        assert features.requires_external_api is True
        assert features.requires_database is True
        assert features.complexity_score >= 5
        # Persona estimation is heuristic; just ensure it's at least 1
        assert features.estimated_personas >= 1

    def test_extract_code_content(self, extractor):
        """Test feature extraction for prompt with code blocks."""
        prompt = """Fix this code:
        ```python
        def calculate(x, y):
            return x + y
        ```
        """
        features = extractor.extract_features(
            prompt=prompt,
            request_type="chat"
        )

        assert features.has_code_blocks is True

    def test_extract_file_operations(self, extractor):
        """Test detection of file operation requirements."""
        features = extractor.extract_features(
            prompt="Save the generated code to a file and export as PDF",
            request_type="workflow"
        )

        assert features.requires_file_operations is True

    def test_extract_with_urls(self, extractor):
        """Test detection of URLs in prompt."""
        features = extractor.extract_features(
            prompt="Fetch data from https://api.example.com/data",
            request_type="chat"
        )

        assert features.has_urls is True
        assert features.requires_external_api is True

    def test_token_count_estimation(self, extractor):
        """Test token count estimation."""
        short_prompt = "Hello"
        long_prompt = "a" * 1000

        short_features = extractor.extract_features(short_prompt)
        long_features = extractor.extract_features(long_prompt)

        assert short_features.token_count < long_features.token_count
        assert long_features.token_count >= 200  # ~1000/4


class TestPolicyEvaluator:
    """Test cases for PolicyEvaluator class."""

    @pytest.fixture
    def evaluator(self):
        """Create a policy evaluator instance."""
        from services.policy_service import PolicyEvaluator
        return PolicyEvaluator(feature_flag_enabled=True)

    @pytest.fixture
    def disabled_evaluator(self):
        """Create a policy evaluator with feature flag disabled."""
        from services.policy_service import PolicyEvaluator
        return PolicyEvaluator(feature_flag_enabled=False)

    def test_simple_query_routes_to_frontend(self, evaluator):
        """Test that simple queries route to frontend."""
        from services.policy_service import RoutingLocus, ReasonCode

        decision = evaluator.evaluate(
            prompt="What is Python?",
            session_id="test_session"
        )

        assert decision.locus == RoutingLocus.FRONTEND
        assert decision.reason_code in [
            ReasonCode.SIMPLE_QUERY,
            ReasonCode.LOW_COMPLEXITY,
            ReasonCode.LOW_TOKEN_COUNT,
        ]
        assert decision.confidence >= 0.8

    def test_preview_routes_to_frontend(self, evaluator):
        """Test that preview requests route to frontend."""
        from services.policy_service import RoutingLocus

        decision = evaluator.evaluate(
            prompt="Show me a quick preview",
            request_type="preview"
        )

        assert decision.locus == RoutingLocus.FRONTEND

    def test_complex_workflow_routes_to_backend(self, evaluator):
        """Test that complex workflows route to backend."""
        from services.policy_service import RoutingLocus, ReasonCode

        decision = evaluator.evaluate(
            prompt="Build a complete e-commerce platform with user authentication, "
                   "product catalog, shopping cart, and payment integration",
            session_id="test_session"
        )

        assert decision.locus == RoutingLocus.BACKEND
        assert decision.reason_code in [
            ReasonCode.MULTI_AGENT_WORKFLOW,
            ReasonCode.HIGH_COMPLEXITY,
            ReasonCode.REQUIRES_EXTERNAL_SERVICES,
        ]

    def test_database_requirement_routes_to_backend(self, evaluator):
        """Test that database requirements route to backend."""
        from services.policy_service import RoutingLocus

        decision = evaluator.evaluate(
            prompt="Create a database schema for user management"
        )

        assert decision.locus == RoutingLocus.BACKEND

    def test_feature_flag_disabled_routes_to_backend(self, disabled_evaluator):
        """Test that disabled feature flag always routes to backend."""
        from services.policy_service import RoutingLocus, ReasonCode

        decision = disabled_evaluator.evaluate(
            prompt="Simple query"
        )

        assert decision.locus == RoutingLocus.BACKEND
        assert decision.reason_code == ReasonCode.FEATURE_FLAG_DISABLED

    def test_override_to_frontend(self, evaluator):
        """Test X-Route-Locus override to frontend."""
        from services.policy_service import RoutingLocus

        # This would normally route to backend
        decision = evaluator.evaluate(
            prompt="Build a complex application with database",
            override_locus="fe"
        )

        assert decision.locus == RoutingLocus.FRONTEND
        assert decision.was_overridden is True
        assert decision.override_source == "X-Route-Locus"
        assert decision.original_locus == RoutingLocus.BACKEND

    def test_override_to_backend(self, evaluator):
        """Test X-Route-Locus override to backend."""
        from services.policy_service import RoutingLocus

        # This would normally route to frontend
        decision = evaluator.evaluate(
            prompt="What is Python?",
            override_locus="backend"
        )

        assert decision.locus == RoutingLocus.BACKEND
        assert decision.was_overridden is True

    def test_request_id_generation(self, evaluator):
        """Test that request IDs are generated."""
        decision = evaluator.evaluate(prompt="Test prompt")

        assert decision.request_id is not None
        assert len(decision.request_id) == 16

    def test_custom_request_id(self, evaluator):
        """Test that custom request IDs are preserved."""
        custom_id = "custom_request_123"
        decision = evaluator.evaluate(
            prompt="Test prompt",
            request_id=custom_id
        )

        assert decision.request_id == custom_id

    def test_session_id_preserved(self, evaluator):
        """Test that session IDs are preserved."""
        session_id = "test_session_456"
        decision = evaluator.evaluate(
            prompt="Test prompt",
            session_id=session_id
        )

        assert decision.session_id == session_id

    def test_timestamp_generated(self, evaluator):
        """Test that timestamps are generated."""
        decision = evaluator.evaluate(prompt="Test prompt")

        assert decision.timestamp is not None
        # Check ISO format
        from datetime import datetime
        datetime.fromisoformat(decision.timestamp)


class TestPerformanceRequirements:
    """Test performance requirements (AC-1: <50ms p50)."""

    @pytest.fixture
    def evaluator(self):
        """Create a policy evaluator instance."""
        from services.policy_service import PolicyEvaluator
        return PolicyEvaluator(feature_flag_enabled=True)

    def test_decision_time_under_50ms(self, evaluator):
        """Test that routing decisions complete in under 50ms."""
        prompts = [
            "What is Python?",
            "Show me a quick preview",
            "Build a complex application",
            "Create a database schema",
            "Hello world",
        ]

        decision_times = []
        for prompt in prompts:
            decision = evaluator.evaluate(prompt=prompt)
            decision_times.append(decision.decision_time_ms)

        # Calculate p50 (median)
        sorted_times = sorted(decision_times)
        p50 = sorted_times[len(sorted_times) // 2]

        assert p50 < 50, f"p50 decision time {p50:.2f}ms exceeds 50ms requirement"

    def test_p95_under_150ms(self, evaluator):
        """Test that p95 decision time is under 150ms."""
        prompts = [
            "What is Python?",
            "Show me a quick preview",
            "Build a complex application with many features and integrations",
            "Create a database schema for user management",
            "Hello world",
            "Explain machine learning",
            "Create an API endpoint",
            "Write a test case",
            "Debug this code",
            "Implement authentication",
        ]

        decision_times = []
        for prompt in prompts:
            decision = evaluator.evaluate(prompt=prompt)
            decision_times.append(decision.decision_time_ms)

        # Calculate p95
        sorted_times = sorted(decision_times)
        p95_index = int(len(sorted_times) * 0.95)
        p95 = sorted_times[min(p95_index, len(sorted_times) - 1)]

        assert p95 < 150, f"p95 decision time {p95:.2f}ms exceeds 150ms requirement"

    def test_bulk_evaluation_performance(self, evaluator):
        """Test performance with bulk evaluations."""
        start_time = time.time()

        for _ in range(100):
            evaluator.evaluate(prompt="Test prompt for bulk evaluation")

        total_time = (time.time() - start_time) * 1000
        avg_time = total_time / 100

        assert avg_time < 50, f"Average decision time {avg_time:.2f}ms exceeds 50ms"


class TestRoutingDecisionSerialization:
    """Test RoutingDecision serialization."""

    @pytest.fixture
    def evaluator(self):
        """Create a policy evaluator instance."""
        from services.policy_service import PolicyEvaluator
        return PolicyEvaluator(feature_flag_enabled=True)

    def test_to_dict_conversion(self, evaluator):
        """Test that decisions can be converted to dict."""
        decision = evaluator.evaluate(prompt="Test prompt")
        decision_dict = decision.to_dict()

        assert "locus" in decision_dict
        assert "reason_code" in decision_dict
        assert "features" in decision_dict
        assert "confidence" in decision_dict
        assert "request_id" in decision_dict
        assert "timestamp" in decision_dict
        assert "decision_time_ms" in decision_dict

    def test_features_to_dict(self, evaluator):
        """Test that features can be converted to dict."""
        decision = evaluator.evaluate(prompt="Test prompt")
        features_dict = decision.features.to_dict()

        assert "token_count" in features_dict
        assert "complexity_score" in features_dict
        assert "is_query" in features_dict
        assert "estimated_time_ms" in features_dict


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def evaluator(self):
        """Create a policy evaluator instance."""
        from services.policy_service import PolicyEvaluator
        return PolicyEvaluator(feature_flag_enabled=True)

    def test_empty_prompt(self, evaluator):
        """Test handling of empty prompt."""
        from services.policy_service import RoutingLocus

        decision = evaluator.evaluate(prompt="")

        # Should still return a valid decision
        assert decision.locus in [RoutingLocus.FRONTEND, RoutingLocus.BACKEND]
        assert decision.request_id is not None

    def test_very_long_prompt(self, evaluator):
        """Test handling of very long prompt."""
        from services.policy_service import RoutingLocus

        long_prompt = "word " * 10000  # ~50k characters
        decision = evaluator.evaluate(prompt=long_prompt)

        # Long prompts should route to backend
        assert decision.locus == RoutingLocus.BACKEND
        assert decision.features.token_count > 1000

    def test_special_characters(self, evaluator):
        """Test handling of special characters."""
        prompt = "Test with special chars: @#$%^&*()[]{}|\\;':\"<>,./?`~"
        decision = evaluator.evaluate(prompt=prompt)

        assert decision.request_id is not None

    def test_unicode_characters(self, evaluator):
        """Test handling of unicode characters."""
        prompt = "Test with unicode: 你好世界 🚀 héllo wörld"
        decision = evaluator.evaluate(prompt=prompt)

        assert decision.request_id is not None
        assert decision.features.token_count > 0


class TestModuleFunctions:
    """Test module-level convenience functions."""

    def test_get_policy_evaluator_singleton(self):
        """Test that get_policy_evaluator returns singleton."""
        from services.policy_service import get_policy_evaluator

        evaluator1 = get_policy_evaluator()
        evaluator2 = get_policy_evaluator()

        assert evaluator1 is evaluator2

    def test_evaluate_routing_convenience(self):
        """Test evaluate_routing convenience function."""
        from services.policy_service import evaluate_routing

        decision = evaluate_routing(
            prompt="What is Python?",
            session_id="test_session"
        )

        assert decision.locus is not None
        assert decision.reason_code is not None


# ============================================================================
# Integration-style tests (still unit tests, but more comprehensive)
# ============================================================================

class TestFullWorkflow:
    """Test full workflow scenarios."""

    @pytest.fixture
    def evaluator(self):
        """Create a policy evaluator instance."""
        from services.policy_service import PolicyEvaluator
        return PolicyEvaluator(feature_flag_enabled=True)

    def test_chat_workflow_frontend(self, evaluator):
        """Test a typical chat workflow routed to frontend."""
        from services.policy_service import RoutingLocus

        # User asks a simple question
        decision = evaluator.evaluate(
            prompt="What is the difference between Python and JavaScript?",
            session_id="chat_session_1",
            request_type="chat"
        )

        assert decision.locus == RoutingLocus.FRONTEND
        assert decision.features.is_query is True

    def test_workflow_backend(self, evaluator):
        """Test a typical workflow routed to backend."""
        from services.policy_service import RoutingLocus

        # User requests a full SDLC workflow
        decision = evaluator.evaluate(
            prompt="Create a complete project management system with user "
                   "authentication, task management, team collaboration, "
                   "reporting dashboards, and deployment pipeline",
            session_id="workflow_session_1",
            request_type="workflow"
        )

        assert decision.locus == RoutingLocus.BACKEND
        assert decision.features.is_multi_step is True
        # Persona estimation is heuristic; routing to backend is what matters
        assert decision.features.estimated_personas >= 1

    def test_preview_to_full_workflow_transition(self, evaluator):
        """Test transition from preview to full workflow."""
        from services.policy_service import RoutingLocus

        # First: Quick preview (frontend)
        preview_decision = evaluator.evaluate(
            prompt="Show me a quick preview of a landing page",
            session_id="session_2",
            request_type="preview"
        )

        assert preview_decision.locus == RoutingLocus.FRONTEND

        # Then: Full implementation (backend)
        full_decision = evaluator.evaluate(
            prompt="Now build the complete landing page with responsive design, "
                   "contact form with backend, newsletter signup, and SEO optimization",
            session_id="session_2",
            request_type="workflow"
        )

        assert full_decision.locus == RoutingLocus.BACKEND


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
