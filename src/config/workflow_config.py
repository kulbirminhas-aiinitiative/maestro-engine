#!/usr/bin/env python3
"""
Workflow Configuration

Defines workflow presets, persona lists, and execution configurations.
This file can be modified to customize SDLC workflows without changing code.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class WorkflowPreset:
    """Workflow preset configuration"""

    name: str
    description: str
    personas: List[str]
    execution_mode: str = "dag"  # dag, sequential, parallel, hierarchical
    enable_mcp: bool = True
    enable_rag: bool = True
    tags: List[str] = field(default_factory=list)


class WorkflowConfig:
    """
    Workflow configuration management

    Defines standard workflows and persona combinations that can be
    referenced by name instead of hardcoding persona lists.
    """

    # ==================== SDLC WORKFLOW PRESETS ====================

    FULL_SDLC: WorkflowPreset = WorkflowPreset(
        name="full_sdlc",
        description="Complete SDLC workflow with all 11 personas",
        personas=[
            "requirement_analyst",
            "solution_architect",
            "ui_ux_designer",
            "frontend_developer",
            "backend_developer",
            "database_administrator",
            "devops_engineer",
            "qa_engineer",
            "security_specialist",
            "deployment_specialist",
            "technical_writer",
        ],
        execution_mode="dag",
        tags=["complete", "production", "guardian"],
    )

    GUARDIAN_WORKFLOW: WorkflowPreset = WorkflowPreset(
        name="guardian",
        description="Guardian mode - supervised SDLC with all checkpoints",
        personas=[
            "requirement_analyst",
            "solution_architect",
            "ui_ux_designer",
            "frontend_developer",
            "backend_developer",
            "database_administrator",
            "qa_engineer",
            "security_specialist",
            "technical_writer",
            "devops_engineer",
        ],
        execution_mode="hierarchical",
        tags=["supervised", "production", "guardian"],
    )

    ACCELERATOR_WORKFLOW: WorkflowPreset = WorkflowPreset(
        name="accelerator",
        description="Accelerator mode - fast autonomous execution",
        personas=[
            "requirement_analyst",
            "solution_architect",
            "frontend_developer",
            "backend_developer",
            "qa_engineer",
        ],
        execution_mode="parallel",
        tags=["fast", "autonomous", "accelerator"],
    )

    REQUIREMENTS_PHASE: WorkflowPreset = WorkflowPreset(
        name="requirements",
        description="Requirements gathering phase only",
        personas=["requirement_analyst"],
        execution_mode="sequential",
        tags=["phase", "requirements"],
    )

    DESIGN_PHASE: WorkflowPreset = WorkflowPreset(
        name="design",
        description="Design phase - architecture and UI/UX",
        personas=["solution_architect", "ui_ux_designer"],
        execution_mode="parallel",
        tags=["phase", "design"],
    )

    IMPLEMENTATION_PHASE: WorkflowPreset = WorkflowPreset(
        name="implementation",
        description="Implementation phase - development team",
        personas=["frontend_developer", "backend_developer", "database_administrator"],
        execution_mode="parallel",
        tags=["phase", "development"],
    )

    TESTING_PHASE: WorkflowPreset = WorkflowPreset(
        name="testing",
        description="Testing phase - QA and Security",
        personas=["qa_engineer", "security_specialist"],
        execution_mode="parallel",
        tags=["phase", "testing"],
    )

    DEPLOYMENT_PHASE: WorkflowPreset = WorkflowPreset(
        name="deployment",
        description="Deployment phase - DevOps and Documentation",
        personas=["devops_engineer", "deployment_specialist", "technical_writer"],
        execution_mode="sequential",
        tags=["phase", "deployment"],
    )

    # Quick workflows for specific tasks
    FRONTEND_ONLY: WorkflowPreset = WorkflowPreset(
        name="frontend_only",
        description="Frontend development only",
        personas=["ui_ux_designer", "frontend_developer", "qa_engineer"],
        execution_mode="sequential",
        tags=["specialized", "frontend"],
    )

    BACKEND_ONLY: WorkflowPreset = WorkflowPreset(
        name="backend_only",
        description="Backend development only",
        personas=[
            "solution_architect",
            "backend_developer",
            "database_administrator",
            "qa_engineer",
        ],
        execution_mode="sequential",
        tags=["specialized", "backend"],
    )

    SECURITY_AUDIT: WorkflowPreset = WorkflowPreset(
        name="security_audit",
        description="Security review and audit",
        personas=["security_specialist", "qa_engineer"],
        execution_mode="sequential",
        tags=["specialized", "security"],
    )

    # ==================== PERSONA GROUPS ====================

    # Organize personas by SDLC phase for reference
    PERSONA_PHASES = {
        "requirements": ["requirement_analyst"],
        "design": ["solution_architect", "ui_ux_designer"],
        "implementation": ["frontend_developer", "backend_developer", "database_administrator"],
        "testing": ["qa_engineer", "security_specialist"],
        "deployment": ["devops_engineer", "deployment_specialist", "technical_writer"],
    }

    # Organize personas by role type
    PERSONA_ROLES = {
        "analysts": ["requirement_analyst"],
        "architects": ["solution_architect"],
        "designers": ["ui_ux_designer"],
        "developers": ["frontend_developer", "backend_developer", "database_administrator"],
        "quality": ["qa_engineer", "security_specialist"],
        "operations": ["devops_engineer", "deployment_specialist"],
        "documentation": ["technical_writer"],
    }

    # All available personas (from Schema v3.0)
    ALL_PERSONAS = [
        "requirement_analyst",
        "solution_architect",
        "ui_ux_designer",
        "frontend_developer",
        "backend_developer",
        "database_administrator",
        "devops_engineer",
        "deployment_specialist",
        "qa_engineer",
        "security_specialist",
        "technical_writer",
    ]

    # ==================== METHODS ====================

    @classmethod
    def get_preset(cls, name: str) -> Optional[WorkflowPreset]:
        """
        Get workflow preset by name

        Args:
            name: Preset name (e.g., 'full_sdlc', 'guardian', 'accelerator')

        Returns:
            WorkflowPreset if found, None otherwise
        """
        presets = {
            "full_sdlc": cls.FULL_SDLC,
            "guardian": cls.GUARDIAN_WORKFLOW,
            "accelerator": cls.ACCELERATOR_WORKFLOW,
            "requirements": cls.REQUIREMENTS_PHASE,
            "design": cls.DESIGN_PHASE,
            "implementation": cls.IMPLEMENTATION_PHASE,
            "testing": cls.TESTING_PHASE,
            "deployment": cls.DEPLOYMENT_PHASE,
            "frontend_only": cls.FRONTEND_ONLY,
            "backend_only": cls.BACKEND_ONLY,
            "security_audit": cls.SECURITY_AUDIT,
        }
        return presets.get(name.lower())

    @classmethod
    def list_presets(cls) -> List[str]:
        """List all available workflow presets"""
        return [
            "full_sdlc",
            "guardian",
            "accelerator",
            "requirements",
            "design",
            "implementation",
            "testing",
            "deployment",
            "frontend_only",
            "backend_only",
            "security_audit",
        ]

    @classmethod
    def get_personas_by_phase(cls, phase: str) -> List[str]:
        """Get personas for a specific SDLC phase"""
        return cls.PERSONA_PHASES.get(phase.lower(), [])

    @classmethod
    def get_personas_by_role(cls, role: str) -> List[str]:
        """Get personas for a specific role type"""
        return cls.PERSONA_ROLES.get(role.lower(), [])

    @classmethod
    def get_default_workflow(cls) -> WorkflowPreset:
        """Get default workflow (Full SDLC)"""
        return cls.FULL_SDLC

    @classmethod
    def validate_personas(cls, personas: List[str]) -> tuple[bool, List[str]]:
        """
        Validate that all personas exist

        Args:
            personas: List of persona IDs to validate

        Returns:
            Tuple of (all_valid, invalid_personas)
        """
        invalid = [p for p in personas if p not in cls.ALL_PERSONAS]
        return (len(invalid) == 0, invalid)

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> Dict[str, WorkflowPreset]:
        """
        Load custom workflows from YAML file

        Args:
            yaml_path: Path to YAML configuration file

        Returns:
            Dictionary of workflow name to WorkflowPreset

        YAML Format:
            workflows:
              my_custom_workflow:
                description: "My custom workflow"
                personas:
                  - requirement_analyst
                  - frontend_developer
                execution_mode: sequential
                enable_mcp: true
                enable_rag: false
                tags: ["custom"]
        """
        if not yaml_path.exists():
            return {}

        with open(yaml_path, "r") as f:
            config = yaml.safe_load(f)

        workflows = {}
        for name, workflow_config in config.get("workflows", {}).items():
            workflows[name] = WorkflowPreset(
                name=name,
                description=workflow_config.get("description", ""),
                personas=workflow_config.get("personas", []),
                execution_mode=workflow_config.get("execution_mode", "dag"),
                enable_mcp=workflow_config.get("enable_mcp", True),
                enable_rag=workflow_config.get("enable_rag", True),
                tags=workflow_config.get("tags", []),
            )

        return workflows


# Singleton instance
_workflow_config: Optional[WorkflowConfig] = None


def get_workflow_config() -> WorkflowConfig:
    """
    Get workflow configuration singleton

    Returns:
        WorkflowConfig: Global workflow configuration instance
    """
    global _workflow_config
    if _workflow_config is None:
        _workflow_config = WorkflowConfig()
    return _workflow_config
