#!/usr/bin/env python3
"""
Workflow Suggestion Engine

Analyzes user conversation and suggests appropriate workflow templates
based on requirements, keywords, and context.
"""

import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from services.dag_catalog import DAGCatalogService
from utils.redis_manager import RedisManager

logger = logging.getLogger(__name__)


@dataclass
class WorkflowSuggestion:
    """A suggested workflow with confidence score"""
    dag_id: str
    name: str
    description: str
    confidence: float  # 0.0 to 1.0
    match_reason: str
    category: str
    complexity: str
    estimated_duration: Optional[str] = None
    tech_stack: Optional[List[str]] = None


class WorkflowSuggestionEngine:
    """
    Analyzes conversation context and suggests appropriate workflow templates.

    Features:
    - Keyword-based matching
    - Context analysis from conversation history
    - Confidence scoring
    - Multi-template ranking
    """

    # Keyword patterns for workflow detection
    WORKFLOW_PATTERNS = {
        "saas": [
            r"\bsaas\b",
            r"\bsoftware as a service\b",
            r"\bmulti.?tenant\b",
            r"\bsubscription\b",
            r"\bcloud.?based\b",
            r"\bweb.?app\b",
            r"\bapi.?and.?frontend\b",
        ],
        "microservice": [
            r"\bmicroservice\b",
            r"\brest.?api\b",
            r"\bapi.?endpoint\b",
            r"\bbackend.?service\b",
            r"\bservice.?oriented\b",
            r"\bapi.?gateway\b",
        ],
        "mobile": [
            r"\bmobile.?app\b",
            r"\bios\b",
            r"\bandroid\b",
            r"\bnative.?app\b",
            r"\bmobile.?dev\b",
            r"\bapp.?store\b",
            r"\bswift\b",
            r"\bkotlin\b",
            r"\breact.?native\b",
        ],
        "enterprise": [
            r"\benterprise\b",
            r"\bcompliance\b",
            r"\bsecurity.?audit\b",
            r"\bgovernance\b",
            r"\blarge.?scale\b",
            r"\bmission.?critical\b",
            r"\benterprise.?grade\b",
        ],
    }

    # Tech stack indicators
    TECH_INDICATORS = {
        "python": [r"\bpython\b", r"\bflask\b", r"\bdjango\b", r"\bfastapi\b"],
        "javascript": [r"\bjavascript\b", r"\bnode\.?js\b", r"\breact\b", r"\bvue\b", r"\bangular\b"],
        "typescript": [r"\btypescript\b", r"\bts\b"],
        "java": [r"\bjava\b", r"\bspring\b"],
        "go": [r"\bgolang\b", r"\bgo\b"],
        "rust": [r"\brust\b"],
    }

    def __init__(self, dag_catalog: Optional[DAGCatalogService] = None):
        """
        Initialize workflow suggestion engine.

        Args:
            dag_catalog: DAG catalog service (creates new instance if not provided)
        """
        self.dag_catalog = dag_catalog or DAGCatalogService(redis_manager=RedisManager())
        logger.info("WorkflowSuggestionEngine initialized")

    async def detect_workflow_request(self, message: str) -> bool:
        """
        Detect if message contains @workflow keyword.

        Args:
            message: User message to analyze

        Returns:
            True if @workflow detected
        """
        pattern = r"@workflow"
        return bool(re.search(pattern, message, re.IGNORECASE))

    async def extract_requirement(self, message: str, conversation_history: Optional[List[Dict]] = None) -> str:
        """
        Extract requirement from user message and conversation context.

        Args:
            message: Current user message
            conversation_history: Previous messages for context

        Returns:
            Extracted requirement text
        """
        # Remove @workflow keyword
        requirement = re.sub(r"@workflow\s*", "", message, flags=re.IGNORECASE).strip()

        # If requirement is too short, look at conversation history
        if len(requirement) < 20 and conversation_history:
            # Get last 3 user messages
            recent_messages = [
                msg.get("content", "")
                for msg in conversation_history[-6:]
                if msg.get("role") == "user"
            ][-3:]

            if recent_messages:
                # Combine recent context
                context = " ".join(recent_messages)
                requirement = f"{requirement} {context}".strip()

        logger.debug(f"Extracted requirement: {requirement[:100]}...")
        return requirement

    async def suggest_workflows(
        self,
        requirement: str,
        limit: int = 3
    ) -> List[WorkflowSuggestion]:
        """
        Suggest workflows based on requirement analysis.

        Args:
            requirement: User requirement text
            limit: Maximum number of suggestions

        Returns:
            List of workflow suggestions sorted by confidence
        """
        logger.info(f"Analyzing requirement for workflow suggestions: {requirement[:100]}...")

        # Get all template DAGs
        templates = await self.dag_catalog.list_dags(limit=100)
        template_dags = [t for t in templates if t.get("is_template", False)]

        if not template_dags:
            logger.warning("No template DAGs found in catalog")
            return []

        # Score each template
        suggestions = []
        requirement_lower = requirement.lower()

        for template in template_dags:
            dag_id = template.get("dag_id", "")
            name = template.get("name", "Unknown")
            description = template.get("description", "")
            category = template.get("category", "unknown")
            complexity = template.get("complexity", "unknown")

            # Calculate confidence score
            confidence, match_reason = self._calculate_confidence(
                requirement_lower,
                category,
                description.lower() if description else "",
                template
            )

            if confidence > 0.1:  # Only include if some confidence
                suggestions.append(WorkflowSuggestion(
                    dag_id=dag_id,
                    name=name,
                    description=description,
                    confidence=confidence,
                    match_reason=match_reason,
                    category=category,
                    complexity=complexity,
                    estimated_duration=template.get("duration"),
                    tech_stack=template.get("tech_stack", [])
                ))

        # Sort by confidence (highest first)
        suggestions.sort(key=lambda x: x.confidence, reverse=True)

        # Return top N
        top_suggestions = suggestions[:limit]

        logger.info(f"Generated {len(top_suggestions)} workflow suggestions")
        for i, sug in enumerate(top_suggestions, 1):
            logger.info(f"  {i}. {sug.name} (confidence: {sug.confidence:.2f})")

        return top_suggestions

    def _calculate_confidence(
        self,
        requirement: str,
        category: str,
        description: str,
        template_metadata: Dict[str, Any]
    ) -> tuple[float, str]:
        """
        Calculate confidence score for a template match.

        Args:
            requirement: User requirement (lowercased)
            category: Template category
            description: Template description (lowercased)
            template_metadata: Full template metadata

        Returns:
            Tuple of (confidence_score, match_reason)
        """
        score = 0.0
        reasons = []

        # 1. Check category keyword patterns (40 points)
        if category in self.WORKFLOW_PATTERNS:
            patterns = self.WORKFLOW_PATTERNS[category]
            matches = sum(1 for pattern in patterns if re.search(pattern, requirement))

            if matches > 0:
                category_score = min(0.40, matches * 0.15)
                score += category_score
                reasons.append(f"{category} keywords matched")

        # 2. Check description similarity (20 points)
        if description:
            # Simple word overlap
            req_words = set(re.findall(r'\w+', requirement))
            desc_words = set(re.findall(r'\w+', description))
            overlap = len(req_words & desc_words)

            if overlap > 2:
                desc_score = min(0.20, overlap * 0.03)
                score += desc_score
                reasons.append(f"description similarity")

        # 3. Tech stack detection (20 points)
        tech_stack = template_metadata.get("tech_stack", [])
        if tech_stack:
            tech_matches = 0
            for tech in tech_stack:
                if tech.lower() in requirement:
                    tech_matches += 1

            if tech_matches > 0:
                tech_score = min(0.20, tech_matches * 0.10)
                score += tech_score
                reasons.append(f"{tech_matches} tech stack match(es)")

        # 4. Complexity indicators (10 points)
        complexity = template_metadata.get("complexity", "")
        if "simple" in requirement and complexity == "simple":
            score += 0.10
            reasons.append("complexity match")
        elif "complex" in requirement and complexity in ("complex", "enterprise"):
            score += 0.10
            reasons.append("complexity match")

        # 5. Use case match (10 points)
        use_cases = template_metadata.get("typical_use_cases", [])
        if use_cases:
            for use_case in use_cases:
                if use_case.lower() in requirement:
                    score += 0.10
                    reasons.append(f"use case: {use_case}")
                    break

        # Normalize to 0.0-1.0
        score = min(1.0, score)

        match_reason = ", ".join(reasons) if reasons else "general match"

        return score, match_reason

    async def format_suggestion_response(
        self,
        suggestions: List[WorkflowSuggestion],
        requirement: str
    ) -> str:
        """
        Format workflow suggestions into a user-friendly response.

        Args:
            suggestions: List of workflow suggestions
            requirement: Original user requirement

        Returns:
            Formatted response text
        """
        if not suggestions:
            return (
                "I couldn't find any workflow templates that match your requirement. "
                "Would you like me to help you create a custom workflow?"
            )

        # Build response
        lines = [
            f"Based on your requirement: \"{requirement[:100]}...\"\n",
            "Here are my recommended workflows:\n"
        ]

        for i, sug in enumerate(suggestions, 1):
            confidence_pct = int(sug.confidence * 100)

            lines.append(f"\n**{i}. {sug.name}** ({confidence_pct}% match)")
            lines.append(f"   Category: {sug.category.title()}")
            lines.append(f"   Complexity: {sug.complexity.title()}")

            if sug.estimated_duration:
                lines.append(f"   Duration: {sug.estimated_duration}")

            if sug.tech_stack:
                tech = ", ".join(sug.tech_stack[:3])
                lines.append(f"   Tech Stack: {tech}")

            lines.append(f"   Why: {sug.match_reason}")
            lines.append(f"   DAG ID: `{sug.dag_id}`")

        lines.append("\n---")
        lines.append("💡 **Next Steps:**")
        lines.append("1. Review the suggestions above")
        lines.append("2. Select a workflow template by its DAG ID")
        lines.append("3. I'll create the workflow and guide you through execution")

        return "\n".join(lines)


# Standalone test
async def test_workflow_suggestions():
    """Test workflow suggestion engine"""
    engine = WorkflowSuggestionEngine()

    # Initialize templates
    await engine.dag_catalog.initialize_templates()

    # Test cases
    test_requirements = [
        "I need to build a SaaS application with user authentication and subscription management",
        "Create a REST API microservice for user management",
        "Build a mobile app for iOS and Android with backend",
        "Need an enterprise-grade system with compliance and security features",
    ]

    for requirement in test_requirements:
        print(f"\n{'='*80}")
        print(f"Requirement: {requirement}")
        print(f"{'='*80}")

        suggestions = await engine.suggest_workflows(requirement, limit=3)
        response = await engine.format_suggestion_response(suggestions, requirement)
        print(response)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_workflow_suggestions())
