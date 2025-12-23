#!/usr/bin/env python3
"""
Context Assembly Engine for MAESTRO Runtime

Builds full execution context by:
- AC-1: Querying Knowledge Store for relevant context
- AC-2: Including previous execution history for similar tasks
- AC-3: Attaching active contracts and constraints
- AC-4: Context size optimization (fit within token limits)
- AC-5: Context relevance scoring and pruning

Part of MD-2559: [RUNTIME-ENGINE] Context Assembly
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ContextType(Enum):
    """Types of context that can be assembled"""
    KNOWLEDGE = "knowledge"
    HISTORY = "history"
    CONTRACT = "contract"
    CONSTRAINT = "constraint"
    TEMPLATE = "template"
    GUIDANCE = "guidance"


@dataclass
class ContextItem:
    """Single item of context with metadata"""
    content: str
    context_type: ContextType
    source: str
    relevance_score: float = 0.0
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Calculate token count if not provided"""
        if self.token_count == 0:
            self.token_count = estimate_tokens(self.content)


@dataclass
class AssembledContext:
    """Full assembled context ready for execution"""
    items: List[ContextItem]
    total_tokens: int
    token_limit: int
    pruned_count: int
    assembly_timestamp: str

    def to_prompt_string(self) -> str:
        """Convert assembled context to a prompt-ready string"""
        sections = {}
        for item in self.items:
            section_name = item.context_type.value.upper()
            if section_name not in sections:
                sections[section_name] = []
            sections[section_name].append(item.content)

        result = []
        for section_name, contents in sections.items():
            result.append(f"## {section_name} CONTEXT\n")
            for content in contents:
                result.append(f"{content}\n")
            result.append("")

        return "\n".join(result)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of assembled context"""
        type_counts = {}
        for item in self.items:
            type_name = item.context_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        return {
            "total_items": len(self.items),
            "total_tokens": self.total_tokens,
            "token_limit": self.token_limit,
            "utilization_pct": round(self.total_tokens / self.token_limit * 100, 1) if self.token_limit > 0 else 0,
            "pruned_count": self.pruned_count,
            "items_by_type": type_counts
        }


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    Uses simple heuristic: ~4 characters per token for English text.
    """
    if not text:
        return 0
    # More accurate: count words and special characters
    words = len(text.split())
    chars = len(text)
    # Estimate based on average of word count and char/4
    return max(1, int((words + chars / 4) / 2))


class KnowledgeStoreQuery:
    """
    AC-1: Query Knowledge Store for relevant context

    Retrieves relevant technical components, workflow templates,
    and best practices from the knowledge base.
    """

    def __init__(self, knowledge_base: Optional[Dict[str, Any]] = None):
        """
        Initialize with optional knowledge base.
        If not provided, imports from dag_knowledge_base.
        """
        if knowledge_base is not None:
            self.knowledge_base = knowledge_base
        else:
            try:
                from ..knowledge.dag_knowledge_base import (
                    TECHNICAL_COMPONENTS,
                    WORKFLOW_TEMPLATES,
                    BEST_PRACTICES,
                    AGENT_PERSONAS
                )
                self.knowledge_base = {
                    "technical_components": TECHNICAL_COMPONENTS,
                    "workflow_templates": WORKFLOW_TEMPLATES,
                    "best_practices": BEST_PRACTICES,
                    "agent_personas": AGENT_PERSONAS
                }
            except ImportError:
                logger.warning("Knowledge base not available, using empty")
                self.knowledge_base = {
                    "technical_components": {},
                    "workflow_templates": {},
                    "best_practices": {},
                    "agent_personas": {}
                }

    def query(
        self,
        task_description: str,
        persona_id: Optional[str] = None,
        component_hints: Optional[List[str]] = None
    ) -> List[ContextItem]:
        """
        Query knowledge store for relevant context.

        Args:
            task_description: Description of the task to execute
            persona_id: Optional persona to filter for
            component_hints: Optional list of component names to include

        Returns:
            List of ContextItems with relevant knowledge
        """
        results = []
        task_lower = task_description.lower()

        # Query technical components
        for comp_id, comp_data in self.knowledge_base.get("technical_components", {}).items():
            relevance = self._calculate_component_relevance(
                comp_id, comp_data, task_lower, component_hints
            )
            if relevance > 0.3:
                content = self._format_component(comp_id, comp_data)
                results.append(ContextItem(
                    content=content,
                    context_type=ContextType.KNOWLEDGE,
                    source=f"knowledge.components.{comp_id}",
                    relevance_score=relevance,
                    metadata={"component_id": comp_id}
                ))

        # Query workflow templates
        for template_id, template_data in self.knowledge_base.get("workflow_templates", {}).items():
            relevance = self._calculate_template_relevance(
                template_id, template_data, task_lower
            )
            if relevance > 0.3:
                content = self._format_template(template_id, template_data)
                results.append(ContextItem(
                    content=content,
                    context_type=ContextType.TEMPLATE,
                    source=f"knowledge.templates.{template_id}",
                    relevance_score=relevance,
                    metadata={"template_id": template_id}
                ))

        # Query persona guidance if persona specified
        if persona_id:
            persona_data = self.knowledge_base.get("agent_personas", {}).get(persona_id)
            if persona_data:
                content = self._format_persona_guidance(persona_id, persona_data)
                results.append(ContextItem(
                    content=content,
                    context_type=ContextType.GUIDANCE,
                    source=f"knowledge.personas.{persona_id}",
                    relevance_score=0.8,
                    metadata={"persona_id": persona_id}
                ))

        # Query best practices
        for practice_category, practice_data in self.knowledge_base.get("best_practices", {}).items():
            relevance = self._calculate_practice_relevance(practice_category, task_lower)
            if relevance > 0.4:
                content = self._format_best_practice(practice_category, practice_data)
                results.append(ContextItem(
                    content=content,
                    context_type=ContextType.GUIDANCE,
                    source=f"knowledge.practices.{practice_category}",
                    relevance_score=relevance,
                    metadata={"practice_category": practice_category}
                ))

        logger.info(f"KnowledgeStoreQuery: Found {len(results)} relevant items")
        return results

    def _calculate_component_relevance(
        self,
        comp_id: str,
        comp_data: Dict,
        task_lower: str,
        hints: Optional[List[str]]
    ) -> float:
        """Calculate relevance score for a component"""
        score = 0.0

        # Check if component is in hints
        if hints and comp_id in hints:
            score += 0.5

        # Check name/description match
        name = comp_data.get("name", "").lower()
        description = comp_data.get("description", "").lower()

        if comp_id in task_lower or name in task_lower:
            score += 0.4

        # Check for keyword overlap
        keywords = set(task_lower.split())
        component_keywords = set(name.split() + description.split())
        overlap = len(keywords & component_keywords)
        score += min(0.3, overlap * 0.05)

        return min(1.0, score)

    def _calculate_template_relevance(
        self,
        template_id: str,
        template_data: Dict,
        task_lower: str
    ) -> float:
        """Calculate relevance score for a workflow template"""
        score = 0.0

        name = template_data.get("name", "").lower()
        description = template_data.get("description", "").lower()
        use_cases = [uc.lower() for uc in template_data.get("use_cases", [])]

        if template_id in task_lower or name in task_lower:
            score += 0.5

        for use_case in use_cases:
            if any(word in task_lower for word in use_case.split()):
                score += 0.2
                break

        keywords = set(task_lower.split())
        template_keywords = set(name.split() + description.split())
        overlap = len(keywords & template_keywords)
        score += min(0.3, overlap * 0.05)

        return min(1.0, score)

    def _calculate_practice_relevance(
        self,
        practice_category: str,
        task_lower: str
    ) -> float:
        """Calculate relevance for best practice category"""
        category_keywords = {
            "phase_ordering": ["phase", "order", "sequence", "workflow"],
            "dependencies": ["depends", "require", "need", "before", "after"],
            "parallel_execution": ["parallel", "concurrent", "simultaneous"],
            "complexity_indicators": ["complex", "simple", "enterprise", "scale"]
        }

        keywords = category_keywords.get(practice_category, [])
        matches = sum(1 for kw in keywords if kw in task_lower)
        return min(1.0, matches * 0.3)

    def _format_component(self, comp_id: str, comp_data: Dict) -> str:
        """Format component data for context"""
        tech_options = ", ".join(comp_data.get("tech_options", {}).keys())
        return (
            f"**{comp_data.get('name', comp_id)}**: {comp_data.get('description', '')}\n"
            f"- Complexity: {comp_data.get('complexity', 'unknown')}\n"
            f"- Tech Options: {tech_options}\n"
            f"- Typical Phases: {', '.join(comp_data.get('typical_phases', []))}"
        )

    def _format_template(self, template_id: str, template_data: Dict) -> str:
        """Format template data for context"""
        components = ", ".join(template_data.get("typical_components", [])[:5])
        return (
            f"**{template_data.get('name', template_id)}**: {template_data.get('description', '')}\n"
            f"- Complexity: {template_data.get('complexity', 'unknown')}\n"
            f"- Duration: {template_data.get('typical_duration', 'unknown')}\n"
            f"- Key Components: {components}"
        )

    def _format_persona_guidance(self, persona_id: str, persona_data: Dict) -> str:
        """Format persona guidance for context"""
        skills = ", ".join(persona_data.get("skills", []))
        best_for = ", ".join(persona_data.get("best_for", []))
        return (
            f"**Persona: {persona_data.get('name', persona_id)}**\n"
            f"- Skills: {skills}\n"
            f"- Best For: {best_for}"
        )

    def _format_best_practice(self, category: str, practice_data: Dict) -> str:
        """Format best practice for context"""
        lines = [f"**Best Practice: {category.replace('_', ' ').title()}**"]
        for key, value in practice_data.items():
            if isinstance(value, list):
                lines.append(f"- {key}: {', '.join(str(v) for v in value[:5])}")
            else:
                lines.append(f"- {key}: {value}")
        return "\n".join(lines)


class ExecutionHistoryRetriever:
    """
    AC-2: Include previous execution history for similar tasks

    Retrieves execution history from RAG integration or local cache.
    """

    def __init__(self, rag_integration=None, history_cache: Optional[List[Dict]] = None):
        """
        Initialize with optional RAG integration.
        """
        self.rag_integration = rag_integration
        self.history_cache = history_cache or []

    def get_similar(
        self,
        task_description: str,
        persona_id: Optional[str] = None,
        max_results: int = 5
    ) -> List[ContextItem]:
        """
        Retrieve similar execution history.

        Args:
            task_description: Description of current task
            persona_id: Optional persona to filter for
            max_results: Maximum number of results

        Returns:
            List of ContextItems with execution history
        """
        results = []

        # Try RAG integration first
        if self.rag_integration:
            try:
                guidance = self.rag_integration.get_persona_guidance(
                    persona_id or "general",
                    task_description,
                    top_k=max_results
                )

                for template in guidance.get("templates", []):
                    content = self._format_rag_template(template)
                    results.append(ContextItem(
                        content=content,
                        context_type=ContextType.HISTORY,
                        source="rag.templates",
                        relevance_score=template.get("quality_score", 0.5) / 100,
                        metadata={"rag_template": True}
                    ))

                for i, practice in enumerate(guidance.get("best_practices", [])):
                    results.append(ContextItem(
                        content=f"Previous Success Pattern: {practice}",
                        context_type=ContextType.HISTORY,
                        source="rag.best_practices",
                        relevance_score=0.6 - (i * 0.1),
                        metadata={"rag_practice": True}
                    ))

            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}")

        # Check local history cache
        for history_item in self.history_cache:
            similarity = self._calculate_similarity(
                task_description,
                history_item.get("requirement", "")
            )
            if similarity > 0.4:
                content = self._format_history_item(history_item)
                results.append(ContextItem(
                    content=content,
                    context_type=ContextType.HISTORY,
                    source="cache.history",
                    relevance_score=similarity * history_item.get("quality_score", 0.7),
                    metadata={"session_id": history_item.get("session_id")}
                ))

        # Sort by relevance and limit
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        results = results[:max_results]

        logger.info(f"ExecutionHistoryRetriever: Found {len(results)} similar executions")
        return results

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity using word overlap"""
        if not text1 or not text2:
            return 0.0

        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _format_rag_template(self, template: Dict) -> str:
        """Format RAG template for context"""
        return (
            f"**Previous Template: {template.get('name', 'Unknown')}**\n"
            f"- Category: {template.get('category', 'N/A')}\n"
            f"- Language: {template.get('language', 'N/A')}\n"
            f"- Quality: {template.get('quality_score', 0):.1f}\n"
            f"- Description: {template.get('description', '')}"
        )

    def _format_history_item(self, item: Dict) -> str:
        """Format history item for context"""
        personas = ", ".join(item.get("personas", [])[:3])
        return (
            f"**Previous Execution**\n"
            f"- Requirement: {item.get('requirement', 'N/A')[:100]}\n"
            f"- Personas: {personas}\n"
            f"- Success: {item.get('success', False)}\n"
            f"- Quality: {item.get('quality_score', 0):.2f}"
        )


class ContractAttacher:
    """
    AC-3: Attach active contracts and constraints

    Attaches relevant contracts, SLAs, and constraints to the context.
    """

    def __init__(self, contracts: Optional[List[Dict]] = None):
        """
        Initialize with optional list of active contracts.
        """
        self.contracts = contracts or []

    def attach(
        self,
        task_description: str,
        persona_id: Optional[str] = None
    ) -> List[ContextItem]:
        """
        Attach relevant contracts and constraints.

        Args:
            task_description: Description of current task
            persona_id: Optional persona to filter contracts

        Returns:
            List of ContextItems with contracts/constraints
        """
        results = []

        for contract in self.contracts:
            if self._is_contract_applicable(contract, task_description, persona_id):
                content = self._format_contract(contract)
                results.append(ContextItem(
                    content=content,
                    context_type=ContextType.CONTRACT,
                    source=f"contracts.{contract.get('id', 'unknown')}",
                    relevance_score=contract.get("priority", 0.5),
                    metadata={
                        "contract_id": contract.get("id"),
                        "contract_type": contract.get("type")
                    }
                ))

        # Add default constraints
        default_constraints = self._get_default_constraints()
        for constraint in default_constraints:
            results.append(ContextItem(
                content=constraint["content"],
                context_type=ContextType.CONSTRAINT,
                source="constraints.default",
                relevance_score=constraint["priority"],
                metadata={"constraint_type": constraint["type"]}
            ))

        logger.info(f"ContractAttacher: Attached {len(results)} contracts/constraints")
        return results

    def _is_contract_applicable(
        self,
        contract: Dict,
        task_description: str,
        persona_id: Optional[str]
    ) -> bool:
        """Check if contract applies to current context"""
        # Check if contract is active
        if not contract.get("active", True):
            return False

        # Check persona filter
        applicable_personas = contract.get("applicable_personas", [])
        if applicable_personas and persona_id and persona_id not in applicable_personas:
            return False

        # Check scope
        scope = contract.get("scope", {})
        task_types = scope.get("task_types", [])
        if task_types:
            task_lower = task_description.lower()
            if not any(tt.lower() in task_lower for tt in task_types):
                return False

        return True

    def _format_contract(self, contract: Dict) -> str:
        """Format contract for context"""
        requirements = contract.get("requirements", [])
        req_str = "\n".join(f"  - {r}" for r in requirements[:5])
        return (
            f"**Contract: {contract.get('name', 'Unnamed')}**\n"
            f"- Type: {contract.get('type', 'general')}\n"
            f"- Priority: {contract.get('priority', 'medium')}\n"
            f"- Requirements:\n{req_str}"
        )

    def _get_default_constraints(self) -> List[Dict]:
        """Get default constraints that always apply"""
        return [
            {
                "type": "quality",
                "content": "**Quality Constraint**: All outputs must pass Quality Fabric validation with score >= 80%",
                "priority": 0.9
            },
            {
                "type": "security",
                "content": "**Security Constraint**: Never expose secrets, credentials, or sensitive data in outputs",
                "priority": 1.0
            },
            {
                "type": "format",
                "content": "**Format Constraint**: Code must include proper documentation and follow project style guidelines",
                "priority": 0.7
            }
        ]


class ContextOptimizer:
    """
    AC-4: Context size optimization (fit within token limits)

    Optimizes context to fit within model token limits while preserving
    the most important information.
    """

    DEFAULT_TOKEN_LIMIT = 8000  # Conservative default for context window

    def __init__(self, token_limit: Optional[int] = None):
        """
        Initialize with token limit.
        """
        self.token_limit = token_limit or self.DEFAULT_TOKEN_LIMIT

    def optimize(
        self,
        items: List[ContextItem],
        reserved_tokens: int = 0
    ) -> Tuple[List[ContextItem], int]:
        """
        Optimize context items to fit within token limit.

        Args:
            items: List of context items to optimize
            reserved_tokens: Tokens to reserve for other content

        Returns:
            Tuple of (optimized items, pruned count)
        """
        available_tokens = self.token_limit - reserved_tokens

        if available_tokens <= 0:
            logger.warning("No tokens available after reservation")
            return [], len(items)

        # Sort by relevance (highest first)
        sorted_items = sorted(items, key=lambda x: x.relevance_score, reverse=True)

        optimized = []
        total_tokens = 0
        pruned_count = 0

        for item in sorted_items:
            if total_tokens + item.token_count <= available_tokens:
                optimized.append(item)
                total_tokens += item.token_count
            else:
                # Try to truncate item if it's highly relevant
                if item.relevance_score >= 0.7:
                    remaining = available_tokens - total_tokens
                    if remaining > 100:  # Minimum useful content
                        truncated = self._truncate_item(item, remaining)
                        optimized.append(truncated)
                        total_tokens += truncated.token_count
                        continue
                pruned_count += 1

        logger.info(
            f"ContextOptimizer: {len(optimized)} items kept, "
            f"{pruned_count} pruned, {total_tokens}/{available_tokens} tokens"
        )
        return optimized, pruned_count

    def _truncate_item(self, item: ContextItem, max_tokens: int) -> ContextItem:
        """Truncate item to fit within token limit"""
        # Estimate characters from tokens (rough: 4 chars/token)
        max_chars = max_tokens * 4

        if len(item.content) <= max_chars:
            return item

        truncated_content = item.content[:max_chars - 20] + "... [truncated]"

        return ContextItem(
            content=truncated_content,
            context_type=item.context_type,
            source=item.source,
            relevance_score=item.relevance_score * 0.9,  # Slight penalty
            metadata={**item.metadata, "truncated": True}
        )


class RelevanceScorer:
    """
    AC-5: Context relevance scoring and pruning

    Scores context items for relevance and prunes low-value items.
    """

    def __init__(self, min_relevance: float = 0.3):
        """
        Initialize with minimum relevance threshold.
        """
        self.min_relevance = min_relevance

    def score_and_prune(
        self,
        items: List[ContextItem],
        task_description: str,
        persona_id: Optional[str] = None
    ) -> List[ContextItem]:
        """
        Score items for relevance and prune low-value items.

        Args:
            items: List of context items
            task_description: Task to score against
            persona_id: Optional persona context

        Returns:
            List of items with updated scores, pruned of low-relevance items
        """
        scored_items = []
        pruned_count = 0

        for item in items:
            # Recalculate relevance score based on task
            new_score = self._calculate_relevance(
                item, task_description, persona_id
            )

            if new_score >= self.min_relevance:
                # Create new item with updated score
                scored_item = ContextItem(
                    content=item.content,
                    context_type=item.context_type,
                    source=item.source,
                    relevance_score=new_score,
                    token_count=item.token_count,
                    metadata=item.metadata
                )
                scored_items.append(scored_item)
            else:
                pruned_count += 1

        # Sort by relevance
        scored_items.sort(key=lambda x: x.relevance_score, reverse=True)

        logger.info(
            f"RelevanceScorer: {len(scored_items)} items kept, "
            f"{pruned_count} pruned (min_relevance={self.min_relevance})"
        )
        return scored_items

    def _calculate_relevance(
        self,
        item: ContextItem,
        task_description: str,
        persona_id: Optional[str]
    ) -> float:
        """Calculate relevance score for item"""
        base_score = item.relevance_score

        # Boost for direct term matches
        task_words = set(task_description.lower().split())
        content_words = set(item.content.lower().split())
        overlap = len(task_words & content_words)
        term_boost = min(0.2, overlap * 0.02)

        # Boost for contract/constraint items (always important)
        type_boost = 0.0
        if item.context_type in (ContextType.CONTRACT, ContextType.CONSTRAINT):
            type_boost = 0.15

        # Boost for persona-specific guidance
        persona_boost = 0.0
        if persona_id and item.metadata.get("persona_id") == persona_id:
            persona_boost = 0.1

        # Recency boost (if timestamp in metadata)
        recency_boost = 0.0
        if "timestamp" in item.metadata:
            # Could implement recency scoring here
            pass

        final_score = base_score + term_boost + type_boost + persona_boost + recency_boost
        return min(1.0, final_score)


class ContextAssemblyEngine:
    """
    Main Context Assembly Engine

    Orchestrates all context assembly components to build
    full execution context for the runtime engine.
    """

    def __init__(
        self,
        knowledge_store: Optional[KnowledgeStoreQuery] = None,
        history_retriever: Optional[ExecutionHistoryRetriever] = None,
        contract_attacher: Optional[ContractAttacher] = None,
        optimizer: Optional[ContextOptimizer] = None,
        relevance_scorer: Optional[RelevanceScorer] = None,
        token_limit: int = 8000
    ):
        """
        Initialize the Context Assembly Engine.

        Args:
            knowledge_store: Knowledge store query component
            history_retriever: Execution history retriever
            contract_attacher: Contract/constraint attacher
            optimizer: Context optimizer
            relevance_scorer: Relevance scorer
            token_limit: Maximum tokens for assembled context
        """
        self.knowledge_store = knowledge_store or KnowledgeStoreQuery()
        self.history_retriever = history_retriever or ExecutionHistoryRetriever()
        self.contract_attacher = contract_attacher or ContractAttacher()
        self.optimizer = optimizer or ContextOptimizer(token_limit)
        self.relevance_scorer = relevance_scorer or RelevanceScorer()
        self.token_limit = token_limit

    def assemble(
        self,
        task_description: str,
        persona_id: Optional[str] = None,
        component_hints: Optional[List[str]] = None,
        reserved_tokens: int = 0
    ) -> AssembledContext:
        """
        Assemble full execution context.

        Args:
            task_description: Description of task to execute
            persona_id: Optional persona executing the task
            component_hints: Optional hints for relevant components
            reserved_tokens: Tokens to reserve for prompt/response

        Returns:
            AssembledContext ready for execution
        """
        logger.info(f"Assembling context for task: {task_description[:50]}...")

        all_items = []

        # AC-1: Query Knowledge Store
        knowledge_items = self.knowledge_store.query(
            task_description,
            persona_id,
            component_hints
        )
        all_items.extend(knowledge_items)

        # AC-2: Get execution history
        history_items = self.history_retriever.get_similar(
            task_description,
            persona_id
        )
        all_items.extend(history_items)

        # AC-3: Attach contracts and constraints
        contract_items = self.contract_attacher.attach(
            task_description,
            persona_id
        )
        all_items.extend(contract_items)

        # AC-5: Score and prune for relevance
        scored_items = self.relevance_scorer.score_and_prune(
            all_items,
            task_description,
            persona_id
        )

        # AC-4: Optimize for token limit
        optimized_items, pruned_count = self.optimizer.optimize(
            scored_items,
            reserved_tokens
        )

        # Calculate total tokens
        total_tokens = sum(item.token_count for item in optimized_items)

        # Build assembled context
        assembled = AssembledContext(
            items=optimized_items,
            total_tokens=total_tokens,
            token_limit=self.token_limit - reserved_tokens,
            pruned_count=pruned_count,
            assembly_timestamp=datetime.utcnow().isoformat()
        )

        summary = assembled.get_summary()
        logger.info(
            f"Context assembled: {summary['total_items']} items, "
            f"{summary['total_tokens']} tokens ({summary['utilization_pct']}% utilization)"
        )

        return assembled


# Convenience functions for direct usage
def assemble_context(
    task_description: str,
    persona_id: Optional[str] = None,
    token_limit: int = 8000
) -> AssembledContext:
    """
    Convenience function to assemble context.

    Args:
        task_description: Task description
        persona_id: Optional persona ID
        token_limit: Token limit

    Returns:
        AssembledContext
    """
    engine = ContextAssemblyEngine(token_limit=token_limit)
    return engine.assemble(task_description, persona_id)


def get_context_summary(context: AssembledContext) -> str:
    """
    Get human-readable summary of assembled context.

    Args:
        context: AssembledContext to summarize

    Returns:
        Summary string
    """
    summary = context.get_summary()
    return (
        f"Context Summary:\n"
        f"- Items: {summary['total_items']}\n"
        f"- Tokens: {summary['total_tokens']}/{summary['token_limit']} "
        f"({summary['utilization_pct']}%)\n"
        f"- Pruned: {summary['pruned_count']}\n"
        f"- By Type: {summary['items_by_type']}"
    )
