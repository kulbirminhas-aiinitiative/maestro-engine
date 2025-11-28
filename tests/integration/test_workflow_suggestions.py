#!/usr/bin/env python3
"""
Integration Tests for Workflow Suggestion Engine

Tests @workflow detection, requirement extraction, and suggestion generation.
"""

import pytest
import asyncio

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.workflow_suggestion_engine import WorkflowSuggestionEngine
from services.dag_catalog import DAGCatalogService
from utils.redis_manager import RedisManager


@pytest.fixture
async def suggestion_engine():
    """Fixture providing initialized suggestion engine"""
    # Initialize DAG catalog with templates
    dag_catalog = DAGCatalogService(redis_manager=RedisManager())
    await dag_catalog.initialize_templates()

    # Create suggestion engine
    engine = WorkflowSuggestionEngine(dag_catalog=dag_catalog)
    yield engine


@pytest.mark.asyncio
class TestWorkflowDetection:
    """Test @workflow keyword detection"""

    async def test_detect_workflow_keyword(self, suggestion_engine):
        """Test @workflow keyword is detected"""
        assert await suggestion_engine.detect_workflow_request("@workflow build a SaaS app")
        assert await suggestion_engine.detect_workflow_request("I need @workflow help")
        assert await suggestion_engine.detect_workflow_request("@WORKFLOW uppercase")

    async def test_no_workflow_keyword(self, suggestion_engine):
        """Test messages without @workflow are not detected"""
        assert not await suggestion_engine.detect_workflow_request("Build a SaaS app")
        assert not await suggestion_engine.detect_workflow_request("workflow without @")
        assert not await suggestion_engine.detect_workflow_request("Just a regular message")


@pytest.mark.asyncio
class TestRequirementExtraction:
    """Test requirement extraction from messages"""

    async def test_extract_requirement_simple(self, suggestion_engine):
        """Test extracting requirement from simple message"""
        message = "@workflow Build a SaaS application with user management"
        requirement = await suggestion_engine.extract_requirement(message)

        assert "Build a SaaS application with user management" in requirement
        assert "@workflow" not in requirement

    async def test_extract_requirement_with_context(self, suggestion_engine):
        """Test extracting requirement using conversation context"""
        conversation = [
            {"role": "user", "content": "I need to build something for my startup"},
            {"role": "assistant", "content": "What kind of application?"},
            {"role": "user", "content": "A subscription-based web app"},
        ]

        message = "@workflow help me with this"
        requirement = await suggestion_engine.extract_requirement(message, conversation)

        # Should include context from conversation
        assert len(requirement) > len(message)


@pytest.mark.asyncio
class TestWorkflowSuggestions:
    """Test workflow suggestion generation"""

    async def test_saas_suggestion(self, suggestion_engine):
        """Test SaaS workflow is suggested for SaaS keywords"""
        requirement = "Build a multi-tenant SaaS application with subscription management"
        suggestions = await suggestion_engine.suggest_workflows(requirement, limit=3)

        assert len(suggestions) > 0

        # Should suggest SaaS template with high confidence
        top_suggestion = suggestions[0]
        assert top_suggestion.dag_id == 'template_saas_app'
        assert top_suggestion.confidence > 0.3  # Should have decent confidence

    async def test_microservice_suggestion(self, suggestion_engine):
        """Test microservice workflow is suggested for API keywords"""
        requirement = "Create a REST API microservice for user authentication"
        suggestions = await suggestion_engine.suggest_workflows(requirement, limit=3)

        assert len(suggestions) > 0

        # Microservice should be in top suggestions
        microservice_found = any(
            s.dag_id == 'template_microservice_api' and s.confidence > 0.2
            for s in suggestions
        )
        assert microservice_found

    async def test_mobile_suggestion(self, suggestion_engine):
        """Test mobile workflow is suggested for mobile keywords"""
        requirement = "Build a mobile app for iOS and Android with backend API"
        suggestions = await suggestion_engine.suggest_workflows(requirement, limit=3)

        assert len(suggestions) > 0

        # Mobile should be in top suggestions
        mobile_found = any(
            s.dag_id == 'template_mobile_app' and s.confidence > 0.2
            for s in suggestions
        )
        assert mobile_found

    async def test_enterprise_suggestion(self, suggestion_engine):
        """Test enterprise workflow is suggested for compliance keywords"""
        requirement = "Need an enterprise-grade system with security compliance and audit logging"
        suggestions = await suggestion_engine.suggest_workflows(requirement, limit=3)

        assert len(suggestions) > 0

        # Enterprise should be in top suggestions
        enterprise_found = any(
            s.dag_id == 'template_enterprise_system' and s.confidence > 0.2
            for s in suggestions
        )
        assert enterprise_found

    async def test_multiple_suggestions(self, suggestion_engine):
        """Test multiple relevant suggestions are returned"""
        requirement = "Build a web application with API and frontend"
        suggestions = await suggestion_engine.suggest_workflows(requirement, limit=3)

        # Should get multiple relevant suggestions
        assert len(suggestions) >= 2

        # Should be sorted by confidence
        confidences = [s.confidence for s in suggestions]
        assert confidences == sorted(confidences, reverse=True)

    async def test_tech_stack_matching(self, suggestion_engine):
        """Test suggestions consider tech stack keywords"""
        requirement = "Build a Python FastAPI microservice with React frontend"
        suggestions = await suggestion_engine.suggest_workflows(requirement, limit=3)

        assert len(suggestions) > 0

        # Should boost scores for templates matching tech stack
        for suggestion in suggestions:
            if 'python' in suggestion.tech_stack or 'fastapi' in suggestion.tech_stack:
                assert suggestion.confidence > 0.1


@pytest.mark.asyncio
class TestSuggestionFormatting:
    """Test suggestion response formatting"""

    async def test_format_multiple_suggestions(self, suggestion_engine):
        """Test formatting multiple suggestions"""
        requirement = "Build a SaaS application"
        suggestions = await suggestion_engine.suggest_workflows(requirement, limit=3)

        response = await suggestion_engine.format_suggestion_response(suggestions, requirement)

        assert "SaaS Application" in response or "saas" in response.lower()
        assert "DAG ID:" in response or "dag_id" in response.lower()
        assert len(suggestions) >= 1

        # Should include confidence percentages
        for sug in suggestions:
            confidence_pct = str(int(sug.confidence * 100))
            assert confidence_pct in response or "match" in response.lower()

    async def test_format_no_suggestions(self, suggestion_engine):
        """Test formatting when no suggestions found"""
        # Use very specific query unlikely to match
        requirement = "xyzabc123 nonexistent workflow type"
        suggestions = await suggestion_engine.suggest_workflows(requirement, limit=3)

        response = await suggestion_engine.format_suggestion_response(suggestions, requirement)

        # Should provide helpful message
        assert "custom workflow" in response.lower() or "no" in response.lower() or len(suggestions) == 0


@pytest.mark.asyncio
class TestConfidenceScoring:
    """Test confidence score calculation"""

    async def test_keyword_matching_increases_confidence(self, suggestion_engine):
        """Test keyword matches increase confidence"""
        # Strong SaaS keywords
        strong_requirement = "multi-tenant SaaS subscription cloud-based web app"
        strong_suggestions = await suggestion_engine.suggest_workflows(strong_requirement)

        # Weak SaaS keywords
        weak_requirement = "build an application"
        weak_suggestions = await suggestion_engine.suggest_workflows(weak_requirement)

        # Find SaaS suggestions in both
        strong_saas = next((s for s in strong_suggestions if s.dag_id == 'template_saas_app'), None)
        weak_saas = next((s for s in weak_suggestions if s.dag_id == 'template_saas_app'), None)

        # Strong keywords should have higher confidence
        if strong_saas and weak_saas:
            assert strong_saas.confidence > weak_saas.confidence

    async def test_match_reason_provided(self, suggestion_engine):
        """Test match reason is provided for suggestions"""
        requirement = "Build a REST API microservice"
        suggestions = await suggestion_engine.suggest_workflows(requirement, limit=3)

        for suggestion in suggestions:
            assert suggestion.match_reason is not None
            assert len(suggestion.match_reason) > 0


if __name__ == "__main__":
    # Run tests with pytest
    print("Running Workflow Suggestion Engine Integration Tests...")
    print("=" * 80)
    pytest.main([__file__, "-v", "--tb=short"])
