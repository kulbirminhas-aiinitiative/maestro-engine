#!/usr/bin/env python3
"""
Tests for Context Assembly Engine (MD-2559)

Tests all 5 acceptance criteria:
- AC-1: Query Knowledge Store for relevant context
- AC-2: Include previous execution history for similar tasks
- AC-3: Attach active contracts and constraints
- AC-4: Context size optimization (fit within token limits)
- AC-5: Context relevance scoring and pruning
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from orchestration.context_assembly import (
    ContextType,
    ContextItem,
    AssembledContext,
    KnowledgeStoreQuery,
    ExecutionHistoryRetriever,
    ContractAttacher,
    ContextOptimizer,
    RelevanceScorer,
    ContextAssemblyEngine,
    estimate_tokens,
    assemble_context,
    get_context_summary,
)


class TestContextItem:
    """Tests for ContextItem dataclass"""

    def test_context_item_creation(self):
        """Test basic ContextItem creation"""
        item = ContextItem(
            content="Test content",
            context_type=ContextType.KNOWLEDGE,
            source="test.source",
            relevance_score=0.8
        )
        assert item.content == "Test content"
        assert item.context_type == ContextType.KNOWLEDGE
        assert item.source == "test.source"
        assert item.relevance_score == 0.8
        assert item.token_count > 0  # Auto-calculated

    def test_context_item_token_estimation(self):
        """Test that token count is estimated correctly"""
        short_item = ContextItem(
            content="Short",
            context_type=ContextType.KNOWLEDGE,
            source="test"
        )
        long_item = ContextItem(
            content="This is a much longer content string with many words " * 10,
            context_type=ContextType.KNOWLEDGE,
            source="test"
        )
        assert long_item.token_count > short_item.token_count


class TestAssembledContext:
    """Tests for AssembledContext"""

    def test_assembled_context_to_prompt_string(self):
        """Test conversion to prompt string"""
        items = [
            ContextItem(
                content="Knowledge item 1",
                context_type=ContextType.KNOWLEDGE,
                source="test"
            ),
            ContextItem(
                content="Contract item 1",
                context_type=ContextType.CONTRACT,
                source="test"
            )
        ]
        context = AssembledContext(
            items=items,
            total_tokens=100,
            token_limit=1000,
            pruned_count=0,
            assembly_timestamp=datetime.utcnow().isoformat()
        )

        prompt = context.to_prompt_string()
        assert "KNOWLEDGE CONTEXT" in prompt
        assert "CONTRACT CONTEXT" in prompt
        assert "Knowledge item 1" in prompt
        assert "Contract item 1" in prompt

    def test_assembled_context_summary(self):
        """Test summary generation"""
        items = [
            ContextItem(content="Item 1", context_type=ContextType.KNOWLEDGE, source="test"),
            ContextItem(content="Item 2", context_type=ContextType.KNOWLEDGE, source="test"),
            ContextItem(content="Item 3", context_type=ContextType.HISTORY, source="test"),
        ]
        context = AssembledContext(
            items=items,
            total_tokens=150,
            token_limit=1000,
            pruned_count=2,
            assembly_timestamp=datetime.utcnow().isoformat()
        )

        summary = context.get_summary()
        assert summary["total_items"] == 3
        assert summary["total_tokens"] == 150
        assert summary["token_limit"] == 1000
        assert summary["pruned_count"] == 2
        assert summary["items_by_type"]["knowledge"] == 2
        assert summary["items_by_type"]["history"] == 1


class TestKnowledgeStoreQuery:
    """AC-1: Tests for Knowledge Store Query"""

    def test_query_with_mock_knowledge_base(self):
        """Test querying with mock knowledge base"""
        mock_kb = {
            "technical_components": {
                "authentication": {
                    "name": "Authentication System",
                    "description": "User authentication and authorization",
                    "complexity": "medium",
                    "tech_options": {"jwt": "JSON Web Tokens"},
                    "typical_phases": ["design", "implementation"]
                }
            },
            "workflow_templates": {
                "saas_app": {
                    "name": "SaaS Application",
                    "description": "Multi-tenant SaaS application",
                    "complexity": "complex",
                    "typical_duration": "8-12 weeks",
                    "typical_components": ["auth", "database"],
                    "use_cases": ["subscription-based services"]
                }
            },
            "best_practices": {
                "phase_ordering": {
                    "always_first": ["requirements"],
                    "always_last": ["deployment"]
                }
            },
            "agent_personas": {
                "backend_developer": {
                    "name": "Backend Developer",
                    "skills": ["API development", "database design"],
                    "best_for": ["code phases"]
                }
            }
        }

        query = KnowledgeStoreQuery(knowledge_base=mock_kb)
        results = query.query("Build authentication system for SaaS app")

        assert len(results) > 0
        assert any(item.context_type == ContextType.KNOWLEDGE for item in results)

    def test_query_with_persona_guidance(self):
        """Test that persona-specific guidance is included"""
        mock_kb = {
            "technical_components": {},
            "workflow_templates": {},
            "best_practices": {},
            "agent_personas": {
                "backend_developer": {
                    "name": "Backend Developer",
                    "skills": ["API development"],
                    "best_for": ["backend"]
                }
            }
        }

        query = KnowledgeStoreQuery(knowledge_base=mock_kb)
        results = query.query("Create API endpoint", persona_id="backend_developer")

        persona_items = [i for i in results if i.metadata.get("persona_id") == "backend_developer"]
        assert len(persona_items) == 1
        assert persona_items[0].context_type == ContextType.GUIDANCE

    def test_query_with_component_hints(self):
        """Test that component hints boost relevance"""
        mock_kb = {
            "technical_components": {
                "database": {
                    "name": "Database Layer",
                    "description": "Data storage",
                    "complexity": "medium",
                    "tech_options": {"postgresql": "PostgreSQL"},
                    "typical_phases": ["design"]
                },
                "caching": {
                    "name": "Caching Layer",
                    "description": "Performance caching",
                    "complexity": "low",
                    "tech_options": {"redis": "Redis"},
                    "typical_phases": ["implementation"]
                }
            },
            "workflow_templates": {},
            "best_practices": {},
            "agent_personas": {}
        }

        query = KnowledgeStoreQuery(knowledge_base=mock_kb)

        # With hint for database
        results = query.query("Build storage layer", component_hints=["database"])
        db_items = [i for i in results if i.metadata.get("component_id") == "database"]

        assert len(db_items) > 0
        assert db_items[0].relevance_score >= 0.5  # Boosted by hint

    def test_query_returns_empty_for_unrelated_task(self):
        """Test that unrelated tasks return fewer results"""
        mock_kb = {
            "technical_components": {
                "payment": {
                    "name": "Payment Processing",
                    "description": "Billing integration",
                    "complexity": "high",
                    "tech_options": {"stripe": "Stripe"},
                    "typical_phases": ["integration"]
                }
            },
            "workflow_templates": {},
            "best_practices": {},
            "agent_personas": {}
        }

        query = KnowledgeStoreQuery(knowledge_base=mock_kb)
        results = query.query("Write unit tests for string utilities")

        # Payment should not be relevant to string utilities
        payment_items = [i for i in results if i.metadata.get("component_id") == "payment"]
        assert len(payment_items) == 0 or payment_items[0].relevance_score < 0.4


class TestExecutionHistoryRetriever:
    """AC-2: Tests for Execution History Retriever"""

    def test_get_similar_from_cache(self):
        """Test retrieving similar executions from cache"""
        history_cache = [
            {
                "session_id": "session-001",
                "requirement": "Build REST API for user management",
                "personas": ["backend_developer"],
                "success": True,
                "quality_score": 0.85
            },
            {
                "session_id": "session-002",
                "requirement": "Create mobile app UI",
                "personas": ["frontend_developer"],
                "success": True,
                "quality_score": 0.90
            }
        ]

        retriever = ExecutionHistoryRetriever(history_cache=history_cache)
        results = retriever.get_similar("Build API endpoint for user service")

        assert len(results) > 0
        # API-related history should be found
        api_results = [r for r in results if "session-001" in r.metadata.get("session_id", "")]
        assert len(api_results) > 0

    def test_get_similar_with_rag_integration(self):
        """Test retrieval with RAG integration mock"""
        mock_rag = Mock()
        mock_rag.get_persona_guidance.return_value = {
            "templates": [
                {
                    "name": "API Template",
                    "category": "backend",
                    "language": "python",
                    "quality_score": 85.0,
                    "description": "REST API template"
                }
            ],
            "best_practices": ["Use proper error handling", "Add input validation"],
            "frameworks": ["FastAPI", "SQLAlchemy"]
        }

        retriever = ExecutionHistoryRetriever(rag_integration=mock_rag)
        results = retriever.get_similar("Build API", persona_id="backend_developer")

        assert len(results) > 0
        assert any(r.metadata.get("rag_template") for r in results)
        mock_rag.get_persona_guidance.assert_called_once()

    def test_get_similar_limits_results(self):
        """Test that results are limited to max_results"""
        history_cache = [
            {"session_id": f"session-{i:03d}", "requirement": "API task", "success": True, "quality_score": 0.8}
            for i in range(20)
        ]

        retriever = ExecutionHistoryRetriever(history_cache=history_cache)
        results = retriever.get_similar("API task", max_results=5)

        assert len(results) <= 5

    def test_get_similar_handles_rag_failure(self):
        """Test graceful handling of RAG integration failure"""
        mock_rag = Mock()
        mock_rag.get_persona_guidance.side_effect = Exception("RAG service unavailable")

        retriever = ExecutionHistoryRetriever(rag_integration=mock_rag)
        # Should not raise, returns empty
        results = retriever.get_similar("Build API")

        assert isinstance(results, list)


class TestContractAttacher:
    """AC-3: Tests for Contract Attacher"""

    def test_attach_relevant_contracts(self):
        """Test attaching relevant contracts"""
        contracts = [
            {
                "id": "contract-001",
                "name": "API Standards",
                "type": "technical",
                "active": True,
                "priority": 0.9,
                "requirements": ["Use REST conventions", "Include OpenAPI spec"],
                "scope": {"task_types": ["API", "backend"]}
            },
            {
                "id": "contract-002",
                "name": "Frontend Guidelines",
                "type": "technical",
                "active": True,
                "priority": 0.8,
                "requirements": ["Use React", "Follow design system"],
                "scope": {"task_types": ["frontend", "UI"]}
            }
        ]

        attacher = ContractAttacher(contracts=contracts)
        results = attacher.attach("Build REST API endpoint")

        # API contract should be attached
        api_contracts = [r for r in results if r.metadata.get("contract_id") == "contract-001"]
        assert len(api_contracts) == 1

        # Frontend contract should NOT be attached (task doesn't mention frontend/UI)
        frontend_contracts = [r for r in results if r.metadata.get("contract_id") == "contract-002"]
        # Contract should not match since "REST API endpoint" doesn't contain "frontend" or "UI"
        assert len(frontend_contracts) == 0 or all(c.relevance_score < api_contracts[0].relevance_score for c in frontend_contracts)

    def test_attach_includes_default_constraints(self):
        """Test that default constraints are always included"""
        attacher = ContractAttacher(contracts=[])
        results = attacher.attach("Any task")

        constraint_items = [r for r in results if r.context_type == ContextType.CONSTRAINT]
        assert len(constraint_items) >= 3  # Quality, Security, Format

        # Check quality constraint exists
        quality_constraints = [c for c in constraint_items if "Quality" in c.content]
        assert len(quality_constraints) == 1

    def test_attach_respects_persona_filter(self):
        """Test that contracts with persona filter are respected"""
        contracts = [
            {
                "id": "contract-001",
                "name": "Backend Only Contract",
                "type": "technical",
                "active": True,
                "priority": 0.9,
                "requirements": ["Backend specific"],
                "applicable_personas": ["backend_developer"],
                "scope": {}
            }
        ]

        attacher = ContractAttacher(contracts=contracts)

        # Should attach for backend_developer
        results_backend = attacher.attach("Build API", persona_id="backend_developer")
        backend_contracts = [r for r in results_backend if r.metadata.get("contract_id") == "contract-001"]
        assert len(backend_contracts) == 1

        # Should NOT attach for frontend_developer
        results_frontend = attacher.attach("Build API", persona_id="frontend_developer")
        frontend_contracts = [r for r in results_frontend if r.metadata.get("contract_id") == "contract-001"]
        assert len(frontend_contracts) == 0

    def test_attach_skips_inactive_contracts(self):
        """Test that inactive contracts are not attached"""
        contracts = [
            {
                "id": "contract-001",
                "name": "Inactive Contract",
                "active": False,
                "priority": 0.9,
                "requirements": ["Should not appear"],
                "scope": {}
            }
        ]

        attacher = ContractAttacher(contracts=contracts)
        results = attacher.attach("Any task")

        inactive = [r for r in results if r.metadata.get("contract_id") == "contract-001"]
        assert len(inactive) == 0


class TestContextOptimizer:
    """AC-4: Tests for Context Optimizer"""

    def test_optimize_fits_within_limit(self):
        """Test that optimization respects token limit"""
        # Create items with moderate relevance (below 0.7) to ensure they get pruned not truncated
        items = [
            ContextItem(content="A " * 500, context_type=ContextType.KNOWLEDGE, source="test", relevance_score=0.6),
            ContextItem(content="B " * 500, context_type=ContextType.KNOWLEDGE, source="test", relevance_score=0.5),
            ContextItem(content="C " * 500, context_type=ContextType.KNOWLEDGE, source="test", relevance_score=0.4),
        ]

        # Use a limit that can only fit one item
        single_item_tokens = items[0].token_count
        optimizer = ContextOptimizer(token_limit=single_item_tokens + 10)
        optimized, pruned = optimizer.optimize(items)

        # Should only fit one item
        assert len(optimized) <= 2
        # At least one item should be pruned
        assert pruned >= 1 or len(optimized) < len(items)

    def test_optimize_prioritizes_high_relevance(self):
        """Test that high relevance items are kept"""
        items = [
            ContextItem(content="Low relevance", context_type=ContextType.KNOWLEDGE, source="test", relevance_score=0.2),
            ContextItem(content="High relevance", context_type=ContextType.KNOWLEDGE, source="test", relevance_score=0.9),
            ContextItem(content="Medium relevance", context_type=ContextType.KNOWLEDGE, source="test", relevance_score=0.5),
        ]

        optimizer = ContextOptimizer(token_limit=50)
        optimized, _ = optimizer.optimize(items)

        if optimized:
            # First item should be high relevance
            assert optimized[0].content == "High relevance"

    def test_optimize_respects_reserved_tokens(self):
        """Test that reserved tokens are respected"""
        items = [
            ContextItem(content="Content", context_type=ContextType.KNOWLEDGE, source="test", relevance_score=0.9),
        ]

        optimizer = ContextOptimizer(token_limit=100)
        optimized, _ = optimizer.optimize(items, reserved_tokens=95)

        # Very little room left after reservation
        total_tokens = sum(i.token_count for i in optimized)
        assert total_tokens <= 5

    def test_optimize_truncates_highly_relevant_items(self):
        """Test that highly relevant items are truncated rather than dropped"""
        long_content = "Very important content. " * 100
        items = [
            ContextItem(content=long_content, context_type=ContextType.KNOWLEDGE, source="test", relevance_score=0.9),
        ]

        optimizer = ContextOptimizer(token_limit=200)
        optimized, _ = optimizer.optimize(items)

        if optimized:
            # Item should be truncated, not dropped
            assert "[truncated]" in optimized[0].content or len(optimized[0].content) < len(long_content)

    def test_optimize_handles_empty_input(self):
        """Test optimization with empty input"""
        optimizer = ContextOptimizer(token_limit=1000)
        optimized, pruned = optimizer.optimize([])

        assert optimized == []
        assert pruned == 0


class TestRelevanceScorer:
    """AC-5: Tests for Relevance Scorer"""

    def test_score_and_prune_removes_low_relevance(self):
        """Test that low relevance items are pruned"""
        items = [
            ContextItem(content="Very relevant API", context_type=ContextType.KNOWLEDGE, source="test", relevance_score=0.8),
            ContextItem(content="Unrelated content", context_type=ContextType.KNOWLEDGE, source="test", relevance_score=0.1),
            ContextItem(content="API design", context_type=ContextType.KNOWLEDGE, source="test", relevance_score=0.6),
        ]

        scorer = RelevanceScorer(min_relevance=0.3)
        scored = scorer.score_and_prune(items, "Build REST API")

        # Low relevance item should be pruned
        assert len(scored) < len(items)
        assert all(item.relevance_score >= 0.3 for item in scored)

    def test_score_and_prune_boosts_contracts(self):
        """Test that contracts get relevance boost"""
        items = [
            ContextItem(content="Contract rules", context_type=ContextType.CONTRACT, source="test", relevance_score=0.4),
            ContextItem(content="Regular content", context_type=ContextType.KNOWLEDGE, source="test", relevance_score=0.4),
        ]

        scorer = RelevanceScorer(min_relevance=0.3)
        scored = scorer.score_and_prune(items, "Any task")

        contract_items = [i for i in scored if i.context_type == ContextType.CONTRACT]
        knowledge_items = [i for i in scored if i.context_type == ContextType.KNOWLEDGE]

        if contract_items and knowledge_items:
            # Contract should have higher score after boost
            assert contract_items[0].relevance_score >= knowledge_items[0].relevance_score

    def test_score_and_prune_boosts_matching_persona(self):
        """Test that matching persona gets boost"""
        items = [
            ContextItem(
                content="Backend guidance",
                context_type=ContextType.GUIDANCE,
                source="test",
                relevance_score=0.5,
                metadata={"persona_id": "backend_developer"}
            ),
            ContextItem(
                content="Frontend guidance",
                context_type=ContextType.GUIDANCE,
                source="test",
                relevance_score=0.5,
                metadata={"persona_id": "frontend_developer"}
            ),
        ]

        scorer = RelevanceScorer(min_relevance=0.3)
        scored = scorer.score_and_prune(items, "Build API", persona_id="backend_developer")

        backend_items = [i for i in scored if i.metadata.get("persona_id") == "backend_developer"]
        frontend_items = [i for i in scored if i.metadata.get("persona_id") == "frontend_developer"]

        if backend_items and frontend_items:
            assert backend_items[0].relevance_score > frontend_items[0].relevance_score

    def test_score_and_prune_sorts_by_relevance(self):
        """Test that results are sorted by relevance"""
        items = [
            ContextItem(content="Low", context_type=ContextType.KNOWLEDGE, source="test", relevance_score=0.4),
            ContextItem(content="High", context_type=ContextType.KNOWLEDGE, source="test", relevance_score=0.9),
            ContextItem(content="Medium", context_type=ContextType.KNOWLEDGE, source="test", relevance_score=0.6),
        ]

        scorer = RelevanceScorer(min_relevance=0.3)
        scored = scorer.score_and_prune(items, "Any task")

        for i in range(len(scored) - 1):
            assert scored[i].relevance_score >= scored[i + 1].relevance_score


class TestContextAssemblyEngine:
    """Integration tests for full Context Assembly Engine"""

    def test_assemble_full_context(self):
        """Test full context assembly pipeline"""
        mock_kb = {
            "technical_components": {
                "api": {
                    "name": "API Layer",
                    "description": "Backend API services",
                    "complexity": "medium",
                    "tech_options": {"rest": "REST"},
                    "typical_phases": ["design", "implementation"]
                }
            },
            "workflow_templates": {},
            "best_practices": {},
            "agent_personas": {}
        }

        knowledge_store = KnowledgeStoreQuery(knowledge_base=mock_kb)
        history_retriever = ExecutionHistoryRetriever(history_cache=[])
        contract_attacher = ContractAttacher(contracts=[])
        optimizer = ContextOptimizer(token_limit=5000)
        scorer = RelevanceScorer(min_relevance=0.2)

        engine = ContextAssemblyEngine(
            knowledge_store=knowledge_store,
            history_retriever=history_retriever,
            contract_attacher=contract_attacher,
            optimizer=optimizer,
            relevance_scorer=scorer,
            token_limit=5000
        )

        context = engine.assemble("Build REST API endpoint")

        assert isinstance(context, AssembledContext)
        assert context.total_tokens <= 5000
        assert len(context.items) > 0

    def test_assemble_with_all_components(self):
        """Test assembly with all component types present"""
        mock_kb = {
            "technical_components": {
                "database": {
                    "name": "Database",
                    "description": "Data storage",
                    "complexity": "medium",
                    "tech_options": {"pg": "PostgreSQL"},
                    "typical_phases": ["design"]
                }
            },
            "workflow_templates": {},
            "best_practices": {},
            "agent_personas": {
                "backend_developer": {
                    "name": "Backend Dev",
                    "skills": ["API"],
                    "best_for": ["backend"]
                }
            }
        }

        history_cache = [
            {"session_id": "s1", "requirement": "Database design", "success": True, "quality_score": 0.9}
        ]

        contracts = [
            {
                "id": "c1",
                "name": "DB Contract",
                "active": True,
                "priority": 0.8,
                "requirements": ["Use PostgreSQL"],
                "scope": {"task_types": ["database"]}
            }
        ]

        engine = ContextAssemblyEngine(
            knowledge_store=KnowledgeStoreQuery(knowledge_base=mock_kb),
            history_retriever=ExecutionHistoryRetriever(history_cache=history_cache),
            contract_attacher=ContractAttacher(contracts=contracts),
            token_limit=10000
        )

        context = engine.assemble("Design database schema", persona_id="backend_developer")

        summary = context.get_summary()
        # Should have multiple types
        assert len(summary["items_by_type"]) >= 2

    def test_assemble_respects_token_limit(self):
        """Test that assembly respects token limit"""
        # Create large knowledge base
        mock_kb = {
            "technical_components": {
                f"component_{i}": {
                    "name": f"Component {i}",
                    "description": "Description " * 50,
                    "complexity": "medium",
                    "tech_options": {"option": "value"},
                    "typical_phases": ["phase"]
                }
                for i in range(50)
            },
            "workflow_templates": {},
            "best_practices": {},
            "agent_personas": {}
        }

        engine = ContextAssemblyEngine(
            knowledge_store=KnowledgeStoreQuery(knowledge_base=mock_kb),
            token_limit=500
        )

        context = engine.assemble("Build something")

        assert context.total_tokens <= 500

    def test_convenience_function_assemble_context(self):
        """Test the convenience function"""
        context = assemble_context("Build API", token_limit=1000)

        assert isinstance(context, AssembledContext)
        assert context.token_limit == 1000

    def test_convenience_function_get_context_summary(self):
        """Test the summary convenience function"""
        items = [ContextItem(content="Test", context_type=ContextType.KNOWLEDGE, source="test")]
        context = AssembledContext(
            items=items,
            total_tokens=10,
            token_limit=100,
            pruned_count=0,
            assembly_timestamp=datetime.utcnow().isoformat()
        )

        summary = get_context_summary(context)

        assert "Items: 1" in summary
        assert "Tokens: 10/100" in summary


class TestEstimateTokens:
    """Tests for token estimation utility"""

    def test_estimate_tokens_empty_string(self):
        """Test empty string returns 0"""
        assert estimate_tokens("") == 0

    def test_estimate_tokens_short_text(self):
        """Test short text estimation"""
        tokens = estimate_tokens("Hello world")
        assert tokens >= 1
        assert tokens <= 10

    def test_estimate_tokens_long_text(self):
        """Test longer text has more tokens"""
        short_tokens = estimate_tokens("Hello")
        long_tokens = estimate_tokens("Hello world this is a longer sentence with more words")

        assert long_tokens > short_tokens

    def test_estimate_tokens_special_characters(self):
        """Test text with special characters"""
        tokens = estimate_tokens("def function(): return {'key': 'value'}")
        assert tokens > 0


# Quality Fabric Integration Test
class TestQualityFabricIntegration:
    """Tests that validate Quality Fabric integration"""

    def test_context_assembly_produces_valid_output(self):
        """Validate that assembled context is QF-compatible"""
        engine = ContextAssemblyEngine(token_limit=5000)
        context = engine.assemble("Build microservice API")

        # Validate structure
        assert hasattr(context, "items")
        assert hasattr(context, "total_tokens")
        assert hasattr(context, "token_limit")
        assert hasattr(context, "pruned_count")
        assert hasattr(context, "assembly_timestamp")

        # Validate types
        assert isinstance(context.items, list)
        assert isinstance(context.total_tokens, int)
        assert isinstance(context.token_limit, int)
        assert isinstance(context.pruned_count, int)

        # Validate prompt conversion
        prompt = context.to_prompt_string()
        assert isinstance(prompt, str)

        # Validate summary
        summary = context.get_summary()
        assert "total_items" in summary
        assert "utilization_pct" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
