#!/usr/bin/env python3
"""
Confidence Scorer Module
Calculates confidence scores for team assignments in intelligent workflow generation.

This module provides algorithms to calculate how confident the AI is in its
team recommendations based on:
- Skill matching
- Historical success rates
- Collaboration scores
- Agent availability
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("confidence_scorer")

# ============================================================================
# ENUMS
# ============================================================================

class ConfidenceLevel(str, Enum):
    """Confidence level categories."""
    HIGH = "high"       # >= 0.90
    MEDIUM = "medium"   # 0.75 - 0.89
    LOW = "low"         # < 0.75


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ConfidenceScore:
    """
    Represents a confidence score with breakdown.
    """
    overall_score: float  # 0-1
    confidence_level: ConfidenceLevel
    breakdown: Dict[str, float]  # Individual component scores
    reasoning: str  # Explanation of the score
    strengths: List[str]  # What makes this a good match
    concerns: List[str]  # What might be concerning


# ============================================================================
# CONFIDENCE SCORER CLASS
# ============================================================================

class ConfidenceScorer:
    """
    Calculates confidence scores for team assignments.

    The confidence score is calculated as a weighted combination of:
    - Skill match score (40%)
    - Historical success rate (30%)
    - Collaboration score (20%)
    - Availability score (10%)
    """

    # Weights for different components
    WEIGHTS = {
        "skill_match": 0.40,
        "historical_success": 0.30,
        "collaboration": 0.20,
        "availability": 0.10
    }

    # Thresholds for confidence levels
    THRESHOLDS = {
        "high": 0.90,
        "medium": 0.75
    }

    def __init__(self):
        """Initialize confidence scorer."""
        logger.info("Confidence Scorer initialized")

    def calculate_confidence(
        self,
        agent: Any,  # AIAgent from api_integrator
        phase_type: Any,  # PhaseType from api_integrator
        expertise: Optional[Any] = None,  # PersonaPhaseExpertise from api_integrator
        project_requirements: Optional[List[str]] = None
    ) -> ConfidenceScore:
        """
        Calculate overall confidence score for an agent-phase assignment.

        Args:
            agent: AIAgent object with skills and capabilities
            phase_type: PhaseType object with requirements
            expertise: Optional PersonaPhaseExpertise with historical data
            project_requirements: Optional list of project-specific requirements

        Returns:
            ConfidenceScore object with detailed breakdown
        """
        logger.info(f"Calculating confidence for {agent.name} on {phase_type.display_name}")

        # Calculate individual scores
        skill_score = self._calculate_skill_match_score(agent, phase_type, project_requirements)
        historical_score = self._calculate_historical_success_rate(agent, expertise)
        collaboration_score = self._calculate_collaboration_score(agent)
        availability_score = self._calculate_availability_score(agent)

        # Calculate weighted overall score
        overall_score = (
            skill_score * self.WEIGHTS["skill_match"] +
            historical_score * self.WEIGHTS["historical_success"] +
            collaboration_score * self.WEIGHTS["collaboration"] +
            availability_score * self.WEIGHTS["availability"]
        )

        # Determine confidence level
        if overall_score >= self.THRESHOLDS["high"]:
            confidence_level = ConfidenceLevel.HIGH
        elif overall_score >= self.THRESHOLDS["medium"]:
            confidence_level = ConfidenceLevel.MEDIUM
        else:
            confidence_level = ConfidenceLevel.LOW

        # Generate reasoning and insights
        reasoning = self._generate_reasoning(
            agent, phase_type, overall_score,
            skill_score, historical_score, collaboration_score
        )
        strengths = self._identify_strengths(
            agent, phase_type, skill_score, historical_score, collaboration_score
        )
        concerns = self._identify_concerns(
            agent, phase_type, skill_score, historical_score, collaboration_score
        )

        # Create breakdown
        breakdown = {
            "skill_match": round(skill_score, 3),
            "historical_success": round(historical_score, 3),
            "collaboration": round(collaboration_score, 3),
            "availability": round(availability_score, 3)
        }

        logger.info(f"✓ Confidence score: {overall_score:.2f} ({confidence_level.value})")

        return ConfidenceScore(
            overall_score=round(overall_score, 3),
            confidence_level=confidence_level,
            breakdown=breakdown,
            reasoning=reasoning,
            strengths=strengths,
            concerns=concerns
        )

    # ========================================================================
    # SCORE CALCULATION METHODS
    # ========================================================================

    def _calculate_skill_match_score(
        self,
        agent: Any,
        phase_type: Any,
        project_requirements: Optional[List[str]] = None
    ) -> float:
        """
        Calculate how well agent's skills match phase requirements.

        Args:
            agent: AIAgent object
            phase_type: PhaseType object
            project_requirements: Optional project-specific requirements

        Returns:
            Skill match score (0-1)
        """
        if not phase_type.required_skills:
            return 0.8  # Default if no specific skills required

        # Combine agent's technical skills and specializations
        agent_skills = set(
            skill.lower() for skill in
            (agent.technical_skills + agent.specializations + agent.capabilities)
        )

        # Required skills from phase type
        required_skills = set(skill.lower() for skill in phase_type.required_skills)

        # Calculate overlap
        if not required_skills:
            return 0.8

        matched_skills = agent_skills.intersection(required_skills)
        match_ratio = len(matched_skills) / len(required_skills)

        # Boost score if agent can produce expected deliverables
        deliverable_match = 0.0
        if phase_type.expected_deliverable_types and agent.deliverable_types:
            agent_deliverables = set(d.lower() for d in agent.deliverable_types)
            expected_deliverables = set(d.lower() for d in phase_type.expected_deliverable_types)
            deliverable_overlap = agent_deliverables.intersection(expected_deliverables)
            if expected_deliverables:
                deliverable_match = len(deliverable_overlap) / len(expected_deliverables)

        # Weighted combination
        final_score = (match_ratio * 0.7) + (deliverable_match * 0.3)

        # Cap at 1.0
        return min(final_score, 1.0)

    def _calculate_historical_success_rate(
        self,
        agent: Any,
        expertise: Optional[Any] = None
    ) -> float:
        """
        Calculate historical success rate.

        Args:
            agent: AIAgent object
            expertise: Optional PersonaPhaseExpertise object

        Returns:
            Historical success score (0-1)
        """
        # If we have expertise data, use it
        if expertise and expertise.total_assignments > 0:
            success_rate = expertise.successful_completions / expertise.total_assignments

            # Adjust based on sample size (more assignments = more reliable)
            if expertise.total_assignments < 5:
                # Low sample size, reduce confidence
                confidence_adjustment = expertise.total_assignments / 5
                return success_rate * confidence_adjustment
            else:
                return success_rate

        # If we have agent-level performance data
        if agent.total_assignments > 0:
            success_rate = agent.successful_completions / agent.total_assignments

            # Adjust based on sample size
            if agent.total_assignments < 10:
                confidence_adjustment = agent.total_assignments / 10
                return success_rate * confidence_adjustment
            else:
                return success_rate

        # No historical data - use conservative estimate
        return 0.70  # 70% default for new agents

    def _calculate_collaboration_score(self, agent: Any) -> float:
        """
        Calculate collaboration score.

        Args:
            agent: AIAgent object

        Returns:
            Collaboration score (0-1)
        """
        # Use agent's collaboration rating if available
        if hasattr(agent, 'collaboration_rating') and agent.collaboration_rating is not None:
            return agent.collaboration_rating

        # Default to 0.8 (good collaboration assumed)
        return 0.80

    def _calculate_availability_score(self, agent: Any) -> float:
        """
        Calculate availability score.

        Args:
            agent: AIAgent object

        Returns:
            Availability score (0-1)
        """
        # Check agent status
        if agent.status != "active":
            return 0.0

        # For now, assume all active agents are available
        # In future, could check current workload, assignments, etc.
        return 1.0

    # ========================================================================
    # REASONING GENERATION
    # ========================================================================

    def _generate_reasoning(
        self,
        agent: Any,
        phase_type: Any,
        overall_score: float,
        skill_score: float,
        historical_score: float,
        collaboration_score: float
    ) -> str:
        """Generate human-readable reasoning for the confidence score."""

        parts = []

        # Overall assessment
        if overall_score >= 0.90:
            parts.append(f"Excellent match for {phase_type.display_name}.")
        elif overall_score >= 0.75:
            parts.append(f"Good match for {phase_type.display_name}.")
        else:
            parts.append(f"Moderate match for {phase_type.display_name}.")

        # Skill match
        if skill_score >= 0.85:
            parts.append(f"Strong skill alignment ({skill_score:.0%}).")
        elif skill_score >= 0.70:
            parts.append(f"Adequate skill match ({skill_score:.0%}).")
        else:
            parts.append(f"Limited skill overlap ({skill_score:.0%}).")

        # Historical performance
        if historical_score >= 0.85:
            assignments_msg = ""
            if hasattr(agent, 'total_assignments') and agent.total_assignments > 0:
                assignments_msg = f" across {agent.total_assignments} assignments"
            parts.append(f"Excellent track record ({historical_score:.0%} success rate{assignments_msg}).")
        elif historical_score >= 0.70:
            parts.append(f"Good historical performance ({historical_score:.0%} success rate).")
        else:
            if agent.total_assignments == 0:
                parts.append("Limited historical data available.")
            else:
                parts.append(f"Mixed historical performance ({historical_score:.0%} success rate).")

        # Collaboration
        if collaboration_score >= 0.85:
            parts.append("Strong collaborator.")

        return " ".join(parts)

    def _identify_strengths(
        self,
        agent: Any,
        phase_type: Any,
        skill_score: float,
        historical_score: float,
        collaboration_score: float
    ) -> List[str]:
        """Identify strengths of this assignment."""
        strengths = []

        # Skill strengths
        if skill_score >= 0.85:
            matching_skills = self._get_matching_skills(agent, phase_type)
            if matching_skills:
                strengths.append(f"Expert in: {', '.join(matching_skills[:3])}")

        # Deliverable strengths
        if phase_type.expected_deliverable_types and agent.deliverable_types:
            matching_deliverables = set(
                d.lower() for d in agent.deliverable_types
            ).intersection(set(
                d.lower() for d in phase_type.expected_deliverable_types
            ))
            if matching_deliverables:
                strengths.append(f"Can produce: {', '.join(list(matching_deliverables)[:2])}")

        # Historical strengths
        if historical_score >= 0.85 and agent.total_assignments >= 5:
            strengths.append(f"High success rate ({historical_score:.0%})")

        # Quality strengths
        if hasattr(agent, 'avg_quality_score') and agent.avg_quality_score and agent.avg_quality_score >= 85:
            strengths.append(f"High quality work (avg: {agent.avg_quality_score:.0f}/100)")

        # Collaboration strengths
        if collaboration_score >= 0.85:
            strengths.append("Excellent team collaborator")

        return strengths

    def _identify_concerns(
        self,
        agent: Any,
        phase_type: Any,
        skill_score: float,
        historical_score: float,
        collaboration_score: float
    ) -> List[str]:
        """Identify potential concerns with this assignment."""
        concerns = []

        # Skill concerns
        if skill_score < 0.70:
            missing_skills = self._get_missing_skills(agent, phase_type)
            if missing_skills:
                concerns.append(f"Limited experience with: {', '.join(missing_skills[:2])}")

        # Historical concerns
        if historical_score < 0.70:
            if agent.total_assignments == 0:
                concerns.append("No historical data for this phase type")
            else:
                concerns.append(f"Lower success rate ({historical_score:.0%})")

        # Experience concerns
        if agent.total_assignments < 5:
            concerns.append("Limited assignment history")

        # Collaboration concerns
        if collaboration_score < 0.70:
            concerns.append("May need collaboration support")

        return concerns

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _get_matching_skills(self, agent: Any, phase_type: Any) -> List[str]:
        """Get list of matching skills between agent and phase type."""
        agent_skills = set(
            skill.lower() for skill in
            (agent.technical_skills + agent.specializations)
        )
        required_skills = set(skill.lower() for skill in phase_type.required_skills)
        matching = agent_skills.intersection(required_skills)
        return list(matching)

    def _get_missing_skills(self, agent: Any, phase_type: Any) -> List[str]:
        """Get list of skills agent doesn't have but phase type requires."""
        agent_skills = set(
            skill.lower() for skill in
            (agent.technical_skills + agent.specializations + agent.capabilities)
        )
        required_skills = set(skill.lower() for skill in phase_type.required_skills)
        missing = required_skills - agent_skills
        return list(missing)


# ============================================================================
# MODULE FUNCTIONS
# ============================================================================

def calculate_confidence_for_assignment(
    agent: Any,
    phase_type: Any,
    expertise: Optional[Any] = None,
    project_requirements: Optional[List[str]] = None
) -> ConfidenceScore:
    """
    Calculate confidence score for an agent-phase assignment.

    Args:
        agent: AIAgent object
        phase_type: PhaseType object
        expertise: Optional PersonaPhaseExpertise object
        project_requirements: Optional project requirements

    Returns:
        ConfidenceScore object
    """
    scorer = ConfidenceScorer()
    return scorer.calculate_confidence(agent, phase_type, expertise, project_requirements)


def rank_agents_by_confidence(
    agents: List[Any],
    phase_type: Any,
    expertise_map: Optional[Dict[str, Any]] = None
) -> List[Tuple[Any, ConfidenceScore]]:
    """
    Rank agents by confidence score for a phase type.

    Args:
        agents: List of AIAgent objects
        phase_type: PhaseType object
        expertise_map: Optional mapping of agent_id -> PersonaPhaseExpertise

    Returns:
        List of (agent, confidence_score) tuples, sorted by score descending
    """
    scorer = ConfidenceScorer()
    ranked = []

    for agent in agents:
        expertise = expertise_map.get(agent.id) if expertise_map else None
        confidence = scorer.calculate_confidence(agent, phase_type, expertise)
        ranked.append((agent, confidence))

    # Sort by overall score descending
    ranked.sort(key=lambda x: x[1].overall_score, reverse=True)

    return ranked


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    from dataclasses import dataclass

    # Mock data for testing
    @dataclass
    class MockAgent:
        id: str = "ai-product-manager"
        name: str = "AI Product Manager"
        technical_skills: list = None
        specializations: list = None
        capabilities: list = None
        deliverable_types: list = None
        status: str = "active"
        total_assignments: int = 45
        successful_completions: int = 40
        avg_quality_score: float = 92.5
        collaboration_rating: float = 0.94

        def __post_init__(self):
            if self.technical_skills is None:
                self.technical_skills = ["requirements_analysis", "stakeholder_management", "documentation"]
            if self.specializations is None:
                self.specializations = ["agile", "user_stories"]
            if self.capabilities is None:
                self.capabilities = ["planning", "communication"]
            if self.deliverable_types is None:
                self.deliverable_types = ["requirements-doc", "user-stories", "acceptance-criteria"]

    @dataclass
    class MockPhaseType:
        type_key: str = "requirements"
        display_name: str = "Requirements Gathering"
        required_skills: list = None
        expected_deliverable_types: list = None
        expected_artifact_formats: list = None

        def __post_init__(self):
            if self.required_skills is None:
                self.required_skills = ["requirements_analysis", "stakeholder_management"]
            if self.expected_deliverable_types is None:
                self.expected_deliverable_types = ["requirements-doc", "user-stories"]
            if self.expected_artifact_formats is None:
                self.expected_artifact_formats = ["markdown", "pdf"]

    @dataclass
    class MockExpertise:
        ai_agent_id: str = "ai-product-manager"
        phase_type_key: str = "requirements"
        expertise_level: float = 9.2
        confidence_score: float = 0.92
        total_assignments: int = 45
        successful_completions: int = 40
        avg_quality_score: float = 92.5

    # Test confidence calculation
    print("Testing Confidence Scorer\n" + "="*50)

    agent = MockAgent()
    phase_type = MockPhaseType()
    expertise = MockExpertise()

    scorer = ConfidenceScorer()
    confidence = scorer.calculate_confidence(agent, phase_type, expertise)

    print(f"\nAgent: {agent.name}")
    print(f"Phase: {phase_type.display_name}")
    print(f"\n📊 Overall Confidence: {confidence.overall_score:.2%}")
    print(f"   Level: {confidence.confidence_level.value.upper()}")
    print(f"\n📈 Breakdown:")
    for component, score in confidence.breakdown.items():
        print(f"   - {component}: {score:.2%}")
    print(f"\n💭 Reasoning: {confidence.reasoning}")
    print(f"\n✅ Strengths:")
    for strength in confidence.strengths:
        print(f"   - {strength}")
    if confidence.concerns:
        print(f"\n⚠️  Concerns:")
        for concern in confidence.concerns:
            print(f"   - {concern}")
