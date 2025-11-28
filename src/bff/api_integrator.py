#!/usr/bin/env python3
"""
API Integrator Module
Fetches organizational data from backend APIs for intelligent workflow generation.

This module provides functions to retrieve:
- Available AI agents with skills and expertise
- Phase type catalog
- Checkpoint templates
- Similar successful workflows
- Team performance metrics
"""

import aiohttp
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("api_integrator")

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class AIAgent:
    """Represents an AI agent/persona from the database."""
    id: str
    name: str
    display_name: str
    primary_role: str
    role: str
    specializations: List[str]
    technical_skills: List[str]
    soft_skills: List[str]
    capabilities: List[str]
    deliverable_types: List[str]
    artifact_formats: List[str]
    status: str = "active"

    # Performance metrics (if available)
    total_assignments: int = 0
    successful_completions: int = 0
    avg_quality_score: Optional[float] = None
    collaboration_rating: float = 0.8


@dataclass
class PhaseType:
    """Represents a phase type from the catalog."""
    type_key: str
    display_name: str
    description: str
    category: str
    typical_duration_days: int
    complexity_score: float
    required_skills: List[str]
    typical_team_size: int
    expected_deliverable_types: List[str]
    expected_artifact_formats: List[str]


@dataclass
class PersonaPhaseExpertise:
    """Represents a persona's expertise in a specific phase type."""
    ai_agent_id: str
    phase_type_key: str
    expertise_level: float
    confidence_score: float
    total_assignments: int
    successful_completions: int
    avg_quality_score: Optional[float] = None


@dataclass
class CheckpointTemplate:
    """Represents a checkpoint template."""
    id: str
    key: str
    name: str
    description: str
    type: str
    criteria: List[Dict[str, Any]]
    required_role: Optional[str] = None


@dataclass
class SimilarWorkflow:
    """Represents a similar workflow from history."""
    id: str
    name: str
    project_type: str
    complexity: str
    tech_stack: List[str]
    success_score: float
    total_phases: int
    team_assignments: Dict[str, List[str]]
    execution_time_days: int


# ============================================================================
# API INTEGRATOR CLASS
# ============================================================================

class WorkflowAPIIntegrator:
    """
    Integrates with backend APIs to fetch organizational data.

    This class provides methods to retrieve data needed for intelligent
    workflow generation including agents, phase types, templates, and
    historical workflow data.
    """

    def __init__(self, base_url: str = "http://localhost:3100", timeout: int = 10):
        """
        Initialize API integrator.

        Args:
            base_url: Base URL of the backend API (default: http://localhost:3100)
            timeout: Request timeout in seconds (default: 10)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        logger.info(f"API Integrator initialized with base URL: {self.base_url}")

    async def _make_request(self, endpoint: str, method: str = "GET", params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make HTTP request to backend API.

        Args:
            endpoint: API endpoint path
            method: HTTP method (GET, POST, etc.)
            params: Query parameters

        Returns:
            Response data as dictionary
        """
        url = f"{self.base_url}{endpoint}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                if method == "GET":
                    async with session.get(url, params=params) as response:
                        response.raise_for_status()
                        return await response.json()
                elif method == "POST":
                    async with session.post(url, json=params) as response:
                        response.raise_for_status()
                        return await response.json()

        except aiohttp.ClientError as e:
            logger.error(f"API request failed: {url} - {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during API request: {e}")
            raise

    # ========================================================================
    # AI AGENTS
    # ========================================================================

    async def fetch_available_agents(self, phase_type: Optional[str] = None) -> List[AIAgent]:
        """
        Fetch available AI agents from the backend.

        Args:
            phase_type: Optional filter by phase type expertise

        Returns:
            List of AIAgent objects
        """
        logger.info(f"Fetching available agents{f' for phase type: {phase_type}' if phase_type else ''}")

        try:
            # Fetch from backend API
            response = await self._make_request("/api/intelligent-workflow/agents", params={"status": "active"})

            agents = []
            for agent_data in response.get("agents", []):
                agent = AIAgent(
                    id=agent_data.get("id", ""),
                    name=agent_data.get("name", ""),
                    display_name=agent_data.get("display_name", agent_data.get("name", "")),
                    primary_role=agent_data.get("primary_role", ""),
                    role=agent_data.get("role", ""),
                    specializations=agent_data.get("specializations", []),
                    technical_skills=agent_data.get("technical_skills", []),
                    soft_skills=agent_data.get("soft_skills", []),
                    capabilities=agent_data.get("capabilities", []),
                    deliverable_types=agent_data.get("deliverable_types", []),
                    artifact_formats=agent_data.get("artifact_formats", []),
                    status=agent_data.get("status", "active"),
                    total_assignments=agent_data.get("total_assignments", 0),
                    successful_completions=agent_data.get("successful_completions", 0),
                    avg_quality_score=agent_data.get("avg_quality_score"),
                    collaboration_rating=agent_data.get("collaboration_rating", 0.8)
                )
                agents.append(agent)

            logger.info(f"✓ Fetched {len(agents)} available agents")
            return agents

        except Exception as e:
            logger.error(f"Failed to fetch agents: {e}")
            # Return empty list on error (graceful degradation)
            return []

    async def fetch_agent_by_id(self, agent_id: str) -> Optional[AIAgent]:
        """
        Fetch specific agent by ID.

        Args:
            agent_id: Agent identifier

        Returns:
            AIAgent object or None if not found
        """
        try:
            response = await self._make_request(f"/api/ai-agents/{agent_id}")

            if response and "agent" in response:
                agent_data = response["agent"]
                return AIAgent(
                    id=agent_data.get("id", ""),
                    name=agent_data.get("name", ""),
                    display_name=agent_data.get("display_name", agent_data.get("name", "")),
                    primary_role=agent_data.get("primary_role", ""),
                    role=agent_data.get("role", ""),
                    specializations=agent_data.get("specializations", []),
                    technical_skills=agent_data.get("technical_skills", []),
                    soft_skills=agent_data.get("soft_skills", []),
                    capabilities=agent_data.get("capabilities", []),
                    deliverable_types=agent_data.get("deliverable_types", []),
                    artifact_formats=agent_data.get("artifact_formats", []),
                    status=agent_data.get("status", "active")
                )
            return None

        except Exception as e:
            logger.error(f"Failed to fetch agent {agent_id}: {e}")
            return None

    # ========================================================================
    # PHASE TYPES
    # ========================================================================

    async def fetch_phase_types(self, category: Optional[str] = None) -> List[PhaseType]:
        """
        Fetch phase types from the catalog.

        Args:
            category: Optional filter by category (planning, development, quality, deployment)

        Returns:
            List of PhaseType objects
        """
        logger.info(f"Fetching phase types{f' for category: {category}' if category else ''}")

        try:
            params = {"is_active": "true"}
            if category:
                params["category"] = category

            response = await self._make_request("/api/intelligent-workflow/phase-types", params=params)

            phase_types = []
            for pt_data in response.get("phase_types", []):
                phase_type = PhaseType(
                    type_key=pt_data.get("type_key", ""),
                    display_name=pt_data.get("display_name", ""),
                    description=pt_data.get("description", ""),
                    category=pt_data.get("category", ""),
                    typical_duration_days=pt_data.get("typical_duration_days", 7),
                    complexity_score=pt_data.get("complexity_score", 5.0),
                    required_skills=pt_data.get("required_skills", []),
                    typical_team_size=pt_data.get("typical_team_size", 2),
                    expected_deliverable_types=pt_data.get("expected_deliverable_types", []),
                    expected_artifact_formats=pt_data.get("expected_artifact_formats", [])
                )
                phase_types.append(phase_type)

            logger.info(f"✓ Fetched {len(phase_types)} phase types")
            return phase_types

        except Exception as e:
            logger.error(f"Failed to fetch phase types: {e}")
            # Return default phase types on error
            return self._get_default_phase_types()

    def _get_default_phase_types(self) -> List[PhaseType]:
        """Return default phase types as fallback."""
        return [
            PhaseType(
                type_key="requirements",
                display_name="Requirements Gathering",
                description="Gather and document project requirements",
                category="planning",
                typical_duration_days=5,
                complexity_score=6.0,
                required_skills=["requirements_analysis", "stakeholder_management"],
                typical_team_size=2,
                expected_deliverable_types=["requirements-doc", "user-stories"],
                expected_artifact_formats=["markdown", "pdf"]
            ),
            PhaseType(
                type_key="architecture",
                display_name="System Architecture",
                description="Design system architecture",
                category="planning",
                typical_duration_days=7,
                complexity_score=8.0,
                required_skills=["system_design", "architecture"],
                typical_team_size=3,
                expected_deliverable_types=["architecture-doc", "design-diagrams"],
                expected_artifact_formats=["markdown", "json", "svg"]
            ),
            PhaseType(
                type_key="implementation",
                display_name="Implementation",
                description="Develop features according to design",
                category="development",
                typical_duration_days=21,
                complexity_score=8.0,
                required_skills=["coding", "software_development"],
                typical_team_size=4,
                expected_deliverable_types=["source-code", "unit-tests"],
                expected_artifact_formats=["typescript", "javascript", "python"]
            ),
            PhaseType(
                type_key="testing",
                display_name="Quality Assurance",
                description="Execute comprehensive testing",
                category="quality",
                typical_duration_days=10,
                complexity_score=7.0,
                required_skills=["quality_assurance", "testing"],
                typical_team_size=3,
                expected_deliverable_types=["test-reports", "bug-reports"],
                expected_artifact_formats=["markdown", "html", "json"]
            ),
            PhaseType(
                type_key="deployment",
                display_name="Deployment",
                description="Deploy to production",
                category="deployment",
                typical_duration_days=3,
                complexity_score=8.0,
                required_skills=["devops", "deployment"],
                typical_team_size=2,
                expected_deliverable_types=["deployment-plan", "runbook"],
                expected_artifact_formats=["markdown", "yaml", "sh"]
            )
        ]

    # ========================================================================
    # PERSONA EXPERTISE
    # ========================================================================

    async def fetch_persona_expertise(
        self,
        phase_type_key: str,
        min_confidence: float = 0.5
    ) -> List[PersonaPhaseExpertise]:
        """
        Fetch persona expertise for a specific phase type.

        Args:
            phase_type_key: Phase type identifier
            min_confidence: Minimum confidence threshold (0-1)

        Returns:
            List of PersonaPhaseExpertise objects
        """
        logger.info(f"Fetching persona expertise for phase: {phase_type_key}")

        try:
            response = await self._make_request(
                "/api/intelligent-workflow/persona-expertise",
                params={
                    "phase_type_key": phase_type_key,
                    "min_confidence": min_confidence
                }
            )

            expertise_list = []
            for exp_data in response.get("expertise", []):
                expertise = PersonaPhaseExpertise(
                    ai_agent_id=exp_data.get("ai_agent_id", ""),
                    phase_type_key=exp_data.get("phase_type_key", ""),
                    expertise_level=exp_data.get("expertise_level", 5.0),
                    confidence_score=exp_data.get("confidence_score", 0.75),
                    total_assignments=exp_data.get("total_assignments", 0),
                    successful_completions=exp_data.get("successful_completions", 0),
                    avg_quality_score=exp_data.get("avg_quality_score")
                )
                expertise_list.append(expertise)

            logger.info(f"✓ Fetched {len(expertise_list)} expertise records")
            return expertise_list

        except Exception as e:
            logger.error(f"Failed to fetch persona expertise: {e}")
            return []

    # ========================================================================
    # CHECKPOINT TEMPLATES
    # ========================================================================

    async def fetch_checkpoint_templates(self, phase_type: Optional[str] = None) -> List[CheckpointTemplate]:
        """
        Fetch checkpoint templates.

        Args:
            phase_type: Optional filter by phase type

        Returns:
            List of CheckpointTemplate objects
        """
        logger.info(f"Fetching checkpoint templates{f' for phase: {phase_type}' if phase_type else ''}")

        try:
            params = {"is_active": True}
            if phase_type:
                params["phase_type"] = phase_type

            response = await self._make_request("/api/checkpoint-templates", params=params)

            templates = []
            for tmpl_data in response.get("templates", []):
                template = CheckpointTemplate(
                    id=tmpl_data.get("id", ""),
                    key=tmpl_data.get("key", ""),
                    name=tmpl_data.get("name", ""),
                    description=tmpl_data.get("description", ""),
                    type=tmpl_data.get("type", "manual"),
                    criteria=tmpl_data.get("criteria", []),
                    required_role=tmpl_data.get("required_role")
                )
                templates.append(template)

            logger.info(f"✓ Fetched {len(templates)} checkpoint templates")
            return templates

        except Exception as e:
            logger.error(f"Failed to fetch checkpoint templates: {e}")
            return []

    # ========================================================================
    # SIMILAR WORKFLOWS
    # ========================================================================

    async def fetch_similar_workflows(
        self,
        project_type: str,
        tech_stack: Optional[List[str]] = None,
        min_success_score: float = 80.0,
        limit: int = 5
    ) -> List[SimilarWorkflow]:
        """
        Fetch similar successful workflows for learning.

        Args:
            project_type: Type of project (saas_platform, mobile_app, etc.)
            tech_stack: Optional technology stack filter
            min_success_score: Minimum success score threshold (0-100)
            limit: Maximum number of results

        Returns:
            List of SimilarWorkflow objects
        """
        logger.info(f"Fetching similar workflows for project type: {project_type}")

        try:
            params = {
                "project_type": project_type,
                "min_success_score": min_success_score,
                "status": "completed",
                "limit": limit
            }
            if tech_stack:
                params["tech_stack"] = ",".join(tech_stack)

            response = await self._make_request("/api/similar-workflows", params=params)

            workflows = []
            for wf_data in response.get("workflows", []):
                workflow = SimilarWorkflow(
                    id=wf_data.get("id", ""),
                    name=wf_data.get("name", ""),
                    project_type=wf_data.get("project_type", ""),
                    complexity=wf_data.get("complexity", "medium"),
                    tech_stack=wf_data.get("tech_stack", []),
                    success_score=wf_data.get("success_score", 0.0),
                    total_phases=wf_data.get("total_phases", 0),
                    team_assignments=wf_data.get("team_assignments", {}),
                    execution_time_days=wf_data.get("execution_time_days", 0)
                )
                workflows.append(workflow)

            logger.info(f"✓ Fetched {len(workflows)} similar workflows")
            return workflows

        except Exception as e:
            logger.error(f"Failed to fetch similar workflows: {e}")
            return []

    # ========================================================================
    # LEARNING PATTERNS
    # ========================================================================

    async def fetch_learning_patterns(
        self,
        project_type: str,
        pattern_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch learning patterns extracted from successful workflows.

        Args:
            project_type: Type of project
            pattern_type: Optional pattern type filter (team_composition, phase_sequence, etc.)

        Returns:
            List of learning pattern dictionaries
        """
        logger.info(f"Fetching learning patterns for project type: {project_type}")

        try:
            params = {
                "project_type": project_type,
                "is_active": True
            }
            if pattern_type:
                params["pattern_type"] = pattern_type

            response = await self._make_request("/api/learning-patterns", params=params)

            patterns = response.get("patterns", [])
            logger.info(f"✓ Fetched {len(patterns)} learning patterns")
            return patterns

        except Exception as e:
            logger.error(f"Failed to fetch learning patterns: {e}")
            return []

    # ========================================================================
    # HEALTH CHECK
    # ========================================================================

    async def check_health(self) -> bool:
        """
        Check if backend API is available.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            response = await self._make_request("/health")
            return response.get("status") == "healthy"
        except Exception:
            return False


# ============================================================================
# MODULE FUNCTIONS
# ============================================================================

async def get_api_integrator(base_url: str = "http://localhost:3100") -> WorkflowAPIIntegrator:
    """
    Get API integrator instance.

    Args:
        base_url: Base URL of backend API

    Returns:
        WorkflowAPIIntegrator instance
    """
    integrator = WorkflowAPIIntegrator(base_url=base_url)

    # Check health
    is_healthy = await integrator.check_health()
    if is_healthy:
        logger.info("✓ Backend API is healthy and ready")
    else:
        logger.warning("⚠ Backend API health check failed - will use fallback data")

    return integrator


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    import asyncio

    async def example():
        """Example usage of API integrator."""

        # Initialize
        api = WorkflowAPIIntegrator(base_url="http://localhost:3100")

        # Check health
        print("Checking API health...")
        is_healthy = await api.check_health()
        print(f"API healthy: {is_healthy}\n")

        # Fetch agents
        print("Fetching available agents...")
        agents = await api.fetch_available_agents()
        print(f"Found {len(agents)} agents")
        for agent in agents[:3]:
            print(f"  - {agent.name} ({agent.primary_role})")
        print()

        # Fetch phase types
        print("Fetching phase types...")
        phase_types = await api.fetch_phase_types()
        print(f"Found {len(phase_types)} phase types")
        for pt in phase_types[:3]:
            print(f"  - {pt.display_name} ({pt.category})")
        print()

        # Fetch persona expertise
        print("Fetching persona expertise for 'requirements'...")
        expertise = await api.fetch_persona_expertise("requirements")
        print(f"Found {len(expertise)} expertise records")
        for exp in expertise[:3]:
            print(f"  - Agent: {exp.ai_agent_id}, Level: {exp.expertise_level}, Confidence: {exp.confidence_score}")
        print()

        # Fetch similar workflows
        print("Fetching similar workflows...")
        workflows = await api.fetch_similar_workflows("saas_platform", limit=3)
        print(f"Found {len(workflows)} similar workflows")
        for wf in workflows:
            print(f"  - {wf.name} (Success: {wf.success_score})")

    # Run example
    asyncio.run(example())
