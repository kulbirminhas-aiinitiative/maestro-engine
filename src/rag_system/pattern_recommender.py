#!/usr/bin/env python3
"""
Pattern Recommender for MAESTRO Engine
Recommends teams, templates, and execution patterns based on RAG data
"""

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from .vector_rag_manager import get_rag_manager

logger = logging.getLogger(__name__)


class PatternRecommender:
    """
    Recommends patterns based on historical data

    Provides:
    - Team composition recommendations
    - Deliverables templates
    - Execution time estimates
    - Success pattern suggestions
    """

    def __init__(self, rag_manager=None):
        """Initialize pattern recommender"""
        self.rag_manager = rag_manager or get_rag_manager()

    def recommend_team_composition(
        self, requirement: str, max_team_size: int = 10
    ) -> Dict[str, Any]:
        """
        Recommend team composition based on similar successful projects

        Args:
            requirement: User requirement
            max_team_size: Maximum team size

        Returns:
            Recommendation with team members and confidence scores
        """
        # Get similar successful executions
        similar_executions = self.rag_manager.search_similar_executions(
            requirement, top_k=10, min_quality=0.6
        )

        if not similar_executions:
            # Return default SDLC team if no data
            return {
                "recommended_team": [
                    "requirement_analyst",
                    "solution_architect",
                    "backend_developer",
                    "frontend_developer",
                    "qa_engineer",
                ],
                "confidence": 0.3,
                "evidence_count": 0,
                "reasoning": "Default SDLC team (no historical data)",
            }

        # Count persona frequency across similar projects
        persona_counter = Counter()
        successful_projects = 0

        for execution in similar_executions:
            if execution["metadata"].get("success", False):
                successful_projects += 1
                team_members = execution["metadata"].get("team_members", "").split(",")
                for member in team_members:
                    member = member.strip()
                    if member:
                        # Weight by similarity
                        weight = execution["similarity"]
                        persona_counter[member] += weight

        # Get most common personas
        recommended_team = []
        for persona, weight in persona_counter.most_common(max_team_size):
            recommended_team.append(persona)

        # Calculate confidence based on evidence
        confidence = min(0.9, 0.4 + (successful_projects * 0.05))

        return {
            "recommended_team": recommended_team,
            "confidence": confidence,
            "evidence_count": len(similar_executions),
            "successful_projects": successful_projects,
            "persona_weights": dict(persona_counter.most_common()),
            "reasoning": f"Based on {successful_projects} successful similar projects",
        }

    def recommend_deliverables_template(self, requirement: str) -> Dict[str, Any]:
        """
        Recommend deliverables structure based on similar projects

        Args:
            requirement: User requirement

        Returns:
            Deliverables template
        """
        # Get similar executions
        similar_executions = self.rag_manager.search_similar_executions(
            requirement, top_k=5, min_quality=0.5
        )

        if not similar_executions:
            # Return default template
            return {
                "template": {
                    "requirement_analyst": ["requirements.md", "user_stories.md"],
                    "solution_architect": ["architecture.md", "design.md"],
                    "backend_developer": ["api_implementation.py", "services/"],
                    "frontend_developer": ["ui_components/", "app.tsx"],
                    "qa_engineer": ["test_plan.md", "tests/"],
                },
                "confidence": 0.3,
                "source": "default_template",
            }

        # Aggregate deliverables from similar projects
        deliverables_by_persona = {}
        file_types_counter = Counter()

        for execution in similar_executions:
            if execution["metadata"].get("success", False):
                team_members = execution["metadata"].get("team_members", "").split(",")

                # Estimate typical deliverables per persona
                for persona in team_members:
                    persona = persona.strip()
                    if persona and persona not in deliverables_by_persona:
                        # Infer typical deliverables based on persona role
                        deliverables_by_persona[persona] = self._get_default_deliverables(persona)

        return {
            "template": deliverables_by_persona,
            "confidence": 0.7 if len(similar_executions) > 2 else 0.5,
            "source": f"aggregated_from_{len(similar_executions)}_projects",
        }

    def _get_default_deliverables(self, persona: str) -> List[str]:
        """Get default deliverables for a persona"""
        defaults = {
            "requirement_analyst": ["requirements.md", "user_stories.md", "acceptance_criteria.md"],
            "solution_architect": ["architecture.md", "system_design.md", "tech_stack.md"],
            "ui_ux_designer": ["wireframes/", "mockups/", "design_system.md"],
            "frontend_developer": ["src/components/", "src/pages/", "src/hooks/", "package.json"],
            "backend_developer": ["src/api/", "src/services/", "src/models/", "requirements.txt"],
            "database_administrator": ["schema.sql", "migrations/", "database_design.md"],
            "qa_engineer": ["test_plan.md", "tests/", "test_cases.md"],
            "security_specialist": ["security_audit.md", "security_checklist.md"],
            "devops_engineer": ["Dockerfile", "kubernetes/", "ci_cd_pipeline.yaml"],
            "technical_writer": ["README.md", "API_DOCUMENTATION.md", "USER_GUIDE.md"],
        }

        return defaults.get(persona, ["README.md"])

    def get_execution_estimate(self, requirement: str) -> Dict[str, Any]:
        """
        Estimate execution time and output based on similar projects

        Args:
            requirement: User requirement

        Returns:
            Execution estimate
        """
        # Get similar executions
        similar_executions = self.rag_manager.search_similar_executions(requirement, top_k=5)

        if not similar_executions:
            # Return conservative estimate
            return {
                "estimated_time_seconds": 300,
                "estimated_files": 10,
                "confidence": "low",
                "reasoning": "Default estimate (no historical data)",
            }

        # Calculate averages from similar projects
        total_files = 0
        count = 0

        for execution in similar_executions:
            metadata = execution["metadata"]
            if metadata.get("success", False):
                total_files += metadata.get("total_files", 0)
                count += 1

        avg_files = total_files / count if count > 0 else 10

        # Estimate time based on file count (rough heuristic)
        estimated_time = avg_files * 15  # ~15 seconds per file

        return {
            "estimated_time_seconds": estimated_time,
            "estimated_files": int(avg_files),
            "confidence": "high" if count >= 3 else "medium",
            "based_on_projects": count,
            "reasoning": f"Based on {count} similar successful projects",
        }

    def suggest_improvements(self, requirement: str) -> List[str]:
        """
        Suggest improvements based on historical patterns

        Args:
            requirement: User requirement

        Returns:
            List of suggestions
        """
        suggestions = []

        # Get similar executions
        similar_executions = self.rag_manager.search_similar_executions(requirement, top_k=10)

        if not similar_executions:
            suggestions.append(
                "Consider breaking down the requirement into smaller, specific tasks"
            )
            suggestions.append("Add acceptance criteria for better clarity")
            return suggestions

        # Analyze patterns
        high_quality_count = sum(
            1 for ex in similar_executions if ex["metadata"].get("quality_score", 0) > 0.8
        )

        if high_quality_count > 2:
            suggestions.append(
                "This type of requirement has historically produced high-quality results"
            )

        # Check for common patterns
        all_teams = []
        for ex in similar_executions:
            team = ex["metadata"].get("team_members", "").split(",")
            all_teams.extend([t.strip() for t in team if t.strip()])

        team_counter = Counter(all_teams)
        most_common = team_counter.most_common(3)

        if most_common:
            top_personas = ", ".join([p[0] for p in most_common[:2]])
            suggestions.append(f"Consider including {top_personas} based on similar projects")

        return suggestions
