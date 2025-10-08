#!/usr/bin/env python3
"""
SDLC Team Organization Structure

Defines how the 11 SDLC personas are organized into phases and how they collaborate
to deliver software solutions from requirements to deployment.

Organization Principles:
1. Phase-based structure: Requirements → Design → Implementation → Testing → Deployment
2. Parallel workstreams: Documentation and Security run parallel to main phases
3. Clear handoffs: Each phase has defined entry/exit criteria
4. Continuous collaboration: Personas collaborate across phase boundaries
5. Feedback loops: Testing and security findings trigger earlier phases
"""

from enum import Enum
from typing import Any, Dict, List, Set


class SDLCPhase(str, Enum):
    """SDLC phases in execution order"""

    REQUIREMENTS = "requirements"
    DESIGN = "design"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    # Cross-cutting concerns (run parallel)
    SECURITY = "security"
    DOCUMENTATION = "documentation"


class TeamOrganization:
    """
    Defines the optimal organization of SDLC team members
    """

    @staticmethod
    def get_phase_structure() -> Dict[str, Dict[str, Any]]:
        """
        Returns the complete phase structure with:
        - Primary personas for each phase
        - Supporting personas
        - Entry criteria
        - Exit criteria
        - Key deliverables
        """
        return {
            SDLCPhase.REQUIREMENTS: {
                "name": "Requirements Gathering & Analysis",
                "primary_personas": ["requirement_analyst", "ui_ux_designer"],
                "supporting_personas": [
                    "solution_architect",  # Technical feasibility input
                    "security_specialist",  # Security requirements
                ],
                "entry_criteria": [
                    "Problem statement defined",
                    "Stakeholders identified",
                    "Business goals clarified",
                ],
                "exit_criteria": [
                    "Requirements document completed",
                    "User stories created with acceptance criteria",
                    "Non-functional requirements documented",
                    "UI/UX wireframes approved",
                    "Requirements review passed",
                ],
                "deliverables": [
                    "Requirements Document (functional & non-functional)",
                    "User Stories with acceptance criteria",
                    "Prioritized requirement backlog",
                    "User personas and journey maps",
                    "Wireframes and mockups",
                    "Accessibility requirements",
                ],
                "estimated_duration": "1-2 weeks",
                "parallel_activities": ["security_requirements_analysis"],
            },
            SDLCPhase.DESIGN: {
                "name": "Technical Design & Architecture",
                "primary_personas": ["solution_architect"],
                "supporting_personas": [
                    "security_specialist",  # Security architecture review
                    "devops_engineer",  # Infrastructure design
                    "frontend_developer",  # Frontend architecture input
                    "backend_developer",  # Backend architecture input
                    "ui_ux_designer",  # Design system alignment
                ],
                "entry_criteria": [
                    "Requirements approved",
                    "User stories finalized",
                    "Non-functional requirements clear",
                ],
                "exit_criteria": [
                    "Architecture document completed",
                    "Technology stack selected",
                    "API contracts defined",
                    "Database schema designed",
                    "Security architecture approved",
                    "Design review passed",
                ],
                "deliverables": [
                    "Solution Architecture Document",
                    "Technology Stack Specification",
                    "API Design & Contracts (OpenAPI/Swagger)",
                    "Database Schema & ERD",
                    "Component Diagrams (C4 model)",
                    "Infrastructure Architecture",
                    "Security Architecture",
                    "Performance & Scalability Plan",
                ],
                "estimated_duration": "1-2 weeks",
                "parallel_activities": ["security_threat_modeling", "infrastructure_planning"],
            },
            SDLCPhase.IMPLEMENTATION: {
                "name": "Development & Implementation",
                "primary_personas": ["frontend_developer", "backend_developer"],
                "supporting_personas": [
                    "solution_architect",  # Architecture guidance
                    "ui_ux_designer",  # Design refinements
                    "security_specialist",  # Code security review
                    "devops_engineer",  # CI/CD setup
                    "qa_engineer",  # Test case preparation
                ],
                "entry_criteria": [
                    "Architecture approved",
                    "API contracts defined",
                    "Database schema ready",
                    "Development environment setup",
                    "CI/CD pipeline configured",
                ],
                "exit_criteria": [
                    "All features implemented",
                    "Code review completed",
                    "Unit tests passing (>80% coverage)",
                    "Integration tests passing",
                    "Security code review passed",
                    "Documentation updated",
                ],
                "deliverables": [
                    "Frontend Application Code",
                    "Backend Application Code",
                    "API Implementation",
                    "Database Migrations",
                    "Unit Tests",
                    "Integration Tests",
                    "Code Documentation",
                ],
                "estimated_duration": "3-6 weeks",
                "parallel_activities": [
                    "security_code_review",
                    "test_case_preparation",
                    "api_documentation",
                ],
            },
            SDLCPhase.TESTING: {
                "name": "Quality Assurance & Testing",
                "primary_personas": ["qa_engineer", "deployment_integration_tester"],
                "supporting_personas": [
                    "security_specialist",  # Security testing
                    "frontend_developer",  # Bug fixes
                    "backend_developer",  # Bug fixes
                    "requirement_analyst",  # Acceptance criteria validation
                ],
                "entry_criteria": [
                    "All features implemented",
                    "Unit tests passing",
                    "Code review completed",
                    "Test environment ready",
                    "Test data prepared",
                ],
                "exit_criteria": [
                    "All test cases executed",
                    "Critical bugs resolved",
                    "Performance benchmarks met",
                    "Security testing passed",
                    "Acceptance criteria validated",
                    "Test report approved",
                ],
                "deliverables": [
                    "Test Plan & Strategy",
                    "Test Cases (functional, integration, E2E)",
                    "Test Execution Report",
                    "Bug Reports & Resolutions",
                    "Performance Test Results",
                    "Security Test Results",
                    "UAT Sign-off",
                ],
                "estimated_duration": "2-3 weeks",
                "parallel_activities": [
                    "security_penetration_testing",
                    "performance_testing",
                    "deployment_preparation",
                ],
            },
            SDLCPhase.DEPLOYMENT: {
                "name": "Deployment & Release",
                "primary_personas": [
                    "deployment_specialist",
                    "devops_engineer",
                    "deployment_integration_tester",
                ],
                "supporting_personas": [
                    "backend_developer",  # Production support
                    "frontend_developer",  # Production support
                    "qa_engineer",  # Smoke testing
                    "security_specialist",  # Security validation
                ],
                "entry_criteria": [
                    "All tests passing",
                    "Production environment ready",
                    "Deployment checklist completed",
                    "Rollback plan prepared",
                    "Monitoring configured",
                ],
                "exit_criteria": [
                    "Application deployed to production",
                    "Smoke tests passed",
                    "Integration tests passed in production",
                    "Monitoring dashboards active",
                    "Performance metrics validated",
                    "Deployment sign-off received",
                ],
                "deliverables": [
                    "Deployment Plan & Checklist",
                    "Release Notes",
                    "Deployment Scripts",
                    "Rollback Procedures",
                    "Smoke Test Results",
                    "Production Integration Test Results",
                    "Monitoring & Alerting Setup",
                    "Post-Deployment Report",
                ],
                "estimated_duration": "1 week",
                "parallel_activities": [
                    "final_security_validation",
                    "production_documentation_update",
                ],
            },
            # Cross-cutting concerns
            SDLCPhase.SECURITY: {
                "name": "Security (Cross-Cutting)",
                "primary_personas": ["security_specialist"],
                "supporting_personas": [
                    "solution_architect",
                    "backend_developer",
                    "frontend_developer",
                    "devops_engineer",
                ],
                "activities_by_phase": {
                    "requirements": [
                        "Identify security requirements",
                        "Define authentication/authorization needs",
                        "Compliance requirements analysis",
                    ],
                    "design": [
                        "Security architecture review",
                        "Threat modeling",
                        "Security controls design",
                    ],
                    "implementation": [
                        "Code security review",
                        "Dependency vulnerability scanning",
                        "SAST (Static Application Security Testing)",
                    ],
                    "testing": [
                        "Penetration testing",
                        "DAST (Dynamic Application Security Testing)",
                        "Security regression testing",
                    ],
                    "deployment": [
                        "Production security validation",
                        "Security monitoring setup",
                        "Incident response readiness",
                    ],
                },
                "deliverables": [
                    "Security Requirements Document",
                    "Threat Model",
                    "Security Architecture Document",
                    "Security Code Review Report",
                    "Penetration Test Report",
                    "Security Compliance Checklist",
                ],
            },
            SDLCPhase.DOCUMENTATION: {
                "name": "Documentation (Cross-Cutting)",
                "primary_personas": ["technical_writer"],
                "supporting_personas": [
                    "solution_architect",
                    "frontend_developer",
                    "backend_developer",
                    "qa_engineer",
                ],
                "activities_by_phase": {
                    "requirements": [
                        "Document user requirements",
                        "Create user story documentation",
                    ],
                    "design": [
                        "Document architecture decisions",
                        "Create API documentation structure",
                    ],
                    "implementation": [
                        "Write API documentation",
                        "Create code documentation",
                        "Develop user guides",
                    ],
                    "testing": ["Document test procedures", "Create troubleshooting guides"],
                    "deployment": [
                        "Write deployment guides",
                        "Create operations runbooks",
                        "Finalize release notes",
                    ],
                },
                "deliverables": [
                    "API Documentation (OpenAPI/Swagger)",
                    "User Guide & Tutorials",
                    "Administrator Guide",
                    "Developer Documentation",
                    "Deployment Guide",
                    "Operations Runbook",
                    "Release Notes",
                ],
            },
        }

    @staticmethod
    def get_collaboration_matrix() -> Dict[str, List[Dict[str, str]]]:
        """
        Defines who collaborates with whom and why

        Returns a matrix of collaboration patterns between personas
        """
        return {
            "requirement_analyst": [
                {
                    "persona": "ui_ux_designer",
                    "purpose": "Translate user needs into UI/UX requirements",
                    "frequency": "continuous",
                    "phase": "requirements",
                },
                {
                    "persona": "solution_architect",
                    "purpose": "Validate technical feasibility of requirements",
                    "frequency": "regular",
                    "phase": "requirements",
                },
                {
                    "persona": "qa_engineer",
                    "purpose": "Ensure acceptance criteria are testable",
                    "frequency": "regular",
                    "phase": "testing",
                },
            ],
            "solution_architect": [
                {
                    "persona": "requirement_analyst",
                    "purpose": "Understand business requirements",
                    "frequency": "regular",
                    "phase": "requirements",
                },
                {
                    "persona": "security_specialist",
                    "purpose": "Design secure architecture",
                    "frequency": "continuous",
                    "phase": "design",
                },
                {
                    "persona": "devops_engineer",
                    "purpose": "Plan infrastructure and deployment architecture",
                    "frequency": "continuous",
                    "phase": "design",
                },
                {
                    "persona": "frontend_developer",
                    "purpose": "Guide frontend architecture decisions",
                    "frequency": "regular",
                    "phase": "implementation",
                },
                {
                    "persona": "backend_developer",
                    "purpose": "Guide backend architecture decisions",
                    "frequency": "regular",
                    "phase": "implementation",
                },
            ],
            "frontend_developer": [
                {
                    "persona": "ui_ux_designer",
                    "purpose": "Implement designs accurately",
                    "frequency": "continuous",
                    "phase": "implementation",
                },
                {
                    "persona": "backend_developer",
                    "purpose": "Integrate with APIs",
                    "frequency": "continuous",
                    "phase": "implementation",
                },
                {
                    "persona": "qa_engineer",
                    "purpose": "Fix bugs and validate fixes",
                    "frequency": "regular",
                    "phase": "testing",
                },
            ],
            "backend_developer": [
                {
                    "persona": "solution_architect",
                    "purpose": "Follow architecture guidelines",
                    "frequency": "regular",
                    "phase": "implementation",
                },
                {
                    "persona": "frontend_developer",
                    "purpose": "Provide APIs and data contracts",
                    "frequency": "continuous",
                    "phase": "implementation",
                },
                {
                    "persona": "security_specialist",
                    "purpose": "Implement security controls",
                    "frequency": "regular",
                    "phase": "implementation",
                },
                {
                    "persona": "devops_engineer",
                    "purpose": "Ensure deployment compatibility",
                    "frequency": "regular",
                    "phase": "implementation",
                },
            ],
            "devops_engineer": [
                {
                    "persona": "solution_architect",
                    "purpose": "Implement infrastructure architecture",
                    "frequency": "continuous",
                    "phase": "design",
                },
                {
                    "persona": "backend_developer",
                    "purpose": "Setup CI/CD pipelines",
                    "frequency": "regular",
                    "phase": "implementation",
                },
                {
                    "persona": "deployment_specialist",
                    "purpose": "Coordinate deployment processes",
                    "frequency": "continuous",
                    "phase": "deployment",
                },
                {
                    "persona": "security_specialist",
                    "purpose": "Secure infrastructure and pipelines",
                    "frequency": "regular",
                    "phase": "all",
                },
            ],
            "qa_engineer": [
                {
                    "persona": "requirement_analyst",
                    "purpose": "Understand acceptance criteria",
                    "frequency": "regular",
                    "phase": "requirements",
                },
                {
                    "persona": "frontend_developer",
                    "purpose": "Report and validate bug fixes",
                    "frequency": "continuous",
                    "phase": "testing",
                },
                {
                    "persona": "backend_developer",
                    "purpose": "Report and validate bug fixes",
                    "frequency": "continuous",
                    "phase": "testing",
                },
                {
                    "persona": "deployment_integration_tester",
                    "purpose": "Coordinate testing activities",
                    "frequency": "regular",
                    "phase": "testing",
                },
            ],
            "security_specialist": [
                {
                    "persona": "solution_architect",
                    "purpose": "Review and enhance security architecture",
                    "frequency": "continuous",
                    "phase": "design",
                },
                {
                    "persona": "backend_developer",
                    "purpose": "Review code for security vulnerabilities",
                    "frequency": "regular",
                    "phase": "implementation",
                },
                {
                    "persona": "devops_engineer",
                    "purpose": "Secure infrastructure and deployment",
                    "frequency": "continuous",
                    "phase": "all",
                },
                {
                    "persona": "qa_engineer",
                    "purpose": "Coordinate security testing",
                    "frequency": "regular",
                    "phase": "testing",
                },
            ],
            "ui_ux_designer": [
                {
                    "persona": "requirement_analyst",
                    "purpose": "Understand user needs",
                    "frequency": "continuous",
                    "phase": "requirements",
                },
                {
                    "persona": "frontend_developer",
                    "purpose": "Ensure design implementation accuracy",
                    "frequency": "continuous",
                    "phase": "implementation",
                },
                {
                    "persona": "qa_engineer",
                    "purpose": "Validate UI/UX in testing",
                    "frequency": "regular",
                    "phase": "testing",
                },
            ],
            "technical_writer": [
                {
                    "persona": "solution_architect",
                    "purpose": "Document architecture decisions",
                    "frequency": "regular",
                    "phase": "design",
                },
                {
                    "persona": "backend_developer",
                    "purpose": "Create API documentation",
                    "frequency": "regular",
                    "phase": "implementation",
                },
                {
                    "persona": "frontend_developer",
                    "purpose": "Create user guides",
                    "frequency": "regular",
                    "phase": "implementation",
                },
                {
                    "persona": "devops_engineer",
                    "purpose": "Create deployment and operations documentation",
                    "frequency": "regular",
                    "phase": "deployment",
                },
            ],
            "deployment_specialist": [
                {
                    "persona": "devops_engineer",
                    "purpose": "Execute deployment strategies",
                    "frequency": "continuous",
                    "phase": "deployment",
                },
                {
                    "persona": "deployment_integration_tester",
                    "purpose": "Coordinate post-deployment testing",
                    "frequency": "continuous",
                    "phase": "deployment",
                },
                {
                    "persona": "backend_developer",
                    "purpose": "Production support during deployment",
                    "frequency": "regular",
                    "phase": "deployment",
                },
            ],
            "deployment_integration_tester": [
                {
                    "persona": "qa_engineer",
                    "purpose": "Align testing strategies",
                    "frequency": "regular",
                    "phase": "testing",
                },
                {
                    "persona": "deployment_specialist",
                    "purpose": "Validate deployments",
                    "frequency": "continuous",
                    "phase": "deployment",
                },
                {
                    "persona": "devops_engineer",
                    "purpose": "Test infrastructure and deployment",
                    "frequency": "regular",
                    "phase": "deployment",
                },
            ],
        }

    @staticmethod
    def get_communication_channels() -> Dict[str, List[str]]:
        """
        Defines which personas should be in which communication channels
        """
        return {
            "requirements_team": [
                "requirement_analyst",
                "ui_ux_designer",
                "solution_architect",
                "security_specialist",
            ],
            "design_team": [
                "solution_architect",
                "security_specialist",
                "devops_engineer",
                "frontend_developer",
                "backend_developer",
                "ui_ux_designer",
            ],
            "development_team": [
                "frontend_developer",
                "backend_developer",
                "solution_architect",
                "ui_ux_designer",
                "devops_engineer",
            ],
            "testing_team": [
                "qa_engineer",
                "deployment_integration_tester",
                "frontend_developer",
                "backend_developer",
                "security_specialist",
            ],
            "deployment_team": [
                "deployment_specialist",
                "devops_engineer",
                "deployment_integration_tester",
                "backend_developer",
                "security_specialist",
            ],
            "security_council": [
                "security_specialist",
                "solution_architect",
                "backend_developer",
                "devops_engineer",
            ],
            "documentation_team": [
                "technical_writer",
                "solution_architect",
                "frontend_developer",
                "backend_developer",
                "devops_engineer",
            ],
            "all_hands": [
                "requirement_analyst",
                "solution_architect",
                "frontend_developer",
                "backend_developer",
                "devops_engineer",
                "qa_engineer",
                "security_specialist",
                "ui_ux_designer",
                "technical_writer",
                "deployment_specialist",
                "deployment_integration_tester",
            ],
        }

    @staticmethod
    def get_decision_authority() -> Dict[str, Dict[str, Any]]:
        """
        Defines who has decision-making authority for different types of decisions
        """
        return {
            "requirements": {
                "primary": "requirement_analyst",
                "approvers": ["solution_architect", "ui_ux_designer"],
                "consultants": ["security_specialist"],
                "veto_power": None,
            },
            "architecture": {
                "primary": "solution_architect",
                "approvers": ["security_specialist", "devops_engineer"],
                "consultants": ["frontend_developer", "backend_developer"],
                "veto_power": "security_specialist",  # Can veto on security grounds
            },
            "implementation": {
                "primary": "frontend_developer/backend_developer",
                "approvers": ["solution_architect"],
                "consultants": ["security_specialist", "ui_ux_designer"],
                "veto_power": None,
            },
            "security": {
                "primary": "security_specialist",
                "approvers": [],
                "consultants": ["solution_architect", "devops_engineer"],
                "veto_power": "security_specialist",  # Final say on security
            },
            "deployment": {
                "primary": "deployment_specialist",
                "approvers": ["devops_engineer", "deployment_integration_tester"],
                "consultants": ["backend_developer"],
                "veto_power": "security_specialist",  # Can veto if security issues
            },
            "testing": {
                "primary": "qa_engineer",
                "approvers": ["requirement_analyst"],
                "consultants": ["frontend_developer", "backend_developer"],
                "veto_power": None,
            },
            "ui_ux": {
                "primary": "ui_ux_designer",
                "approvers": ["requirement_analyst"],
                "consultants": ["frontend_developer"],
                "veto_power": None,
            },
        }

    @staticmethod
    def get_escalation_path() -> List[Dict[str, Any]]:
        """
        Defines escalation paths for issues and blockers
        """
        return [
            {
                "level": 1,
                "title": "Peer Resolution",
                "personas": ["same_phase_team_members"],
                "timeframe": "2 hours",
                "examples": ["Code review feedback", "Minor design clarifications"],
            },
            {
                "level": 2,
                "title": "Cross-Team Resolution",
                "personas": ["solution_architect", "relevant_phase_leads"],
                "timeframe": "1 day",
                "examples": ["API contract disputes", "Design-implementation conflicts"],
            },
            {
                "level": 3,
                "title": "Architecture Decision",
                "personas": ["solution_architect", "security_specialist", "devops_engineer"],
                "timeframe": "2 days",
                "examples": ["Major architectural changes", "Technology stack decisions"],
            },
            {
                "level": 4,
                "title": "Security Override",
                "personas": ["security_specialist"],
                "timeframe": "Immediate",
                "examples": ["Security vulnerabilities", "Compliance violations"],
            },
            {
                "level": 5,
                "title": "Project Lead Decision",
                "personas": ["requirement_analyst", "solution_architect", "deployment_specialist"],
                "timeframe": "3 days",
                "examples": ["Scope changes", "Timeline adjustments", "Resource allocation"],
            },
        ]


# Helper functions for team coordination
def get_personas_for_phase(phase: SDLCPhase) -> List[str]:
    """Get all personas involved in a specific phase"""
    org = TeamOrganization()
    structure = org.get_phase_structure()

    if phase not in structure:
        return []

    phase_info = structure[phase]
    return phase_info.get("primary_personas", []) + phase_info.get("supporting_personas", [])


def get_next_phase(current_phase: SDLCPhase) -> SDLCPhase:
    """Get the next phase in the SDLC"""
    phase_order = [
        SDLCPhase.REQUIREMENTS,
        SDLCPhase.DESIGN,
        SDLCPhase.IMPLEMENTATION,
        SDLCPhase.TESTING,
        SDLCPhase.DEPLOYMENT,
    ]

    try:
        current_index = phase_order.index(current_phase)
        if current_index < len(phase_order) - 1:
            return phase_order[current_index + 1]
    except ValueError:
        pass

    return None


def get_deliverables_for_phase(phase: SDLCPhase) -> List[str]:
    """Get all deliverables for a specific phase"""
    org = TeamOrganization()
    structure = org.get_phase_structure()

    if phase not in structure:
        return []

    return structure[phase].get("deliverables", [])


def get_deliverables_for_persona(persona_id: str) -> List[str]:
    """
    Get deliverables that a specific persona is responsible for

    This centralizes the persona→deliverables mapping in one place
    instead of hardcoding it in multiple files.

    Args:
        persona_id: The persona identifier (e.g., "requirement_analyst")

    Returns:
        List of deliverable names that this persona should produce
    """
    deliverables_map = {
        "requirement_analyst": [
            "requirements_document",
            "user_stories",
            "acceptance_criteria",
            "requirement_backlog",
        ],
        "ui_ux_designer": [
            "wireframes",
            "mockups",
            "design_system",
            "user_personas",
            "user_journey_maps",
        ],
        "solution_architect": [
            "architecture_document",
            "tech_stack",
            "database_design",
            "api_specifications",
            "system_design",
        ],
        "security_specialist": [
            "security_review",
            "threat_model",
            "security_requirements",
            "penetration_test_results",
        ],
        "backend_developer": [
            "backend_code",
            "api_implementation",
            "database_schema",
            "backend_tests",
        ],
        "frontend_developer": [
            "frontend_code",
            "components",
            "frontend_tests",
            "responsive_design",
        ],
        "devops_engineer": [
            "docker_config",
            "ci_cd_pipeline",
            "infrastructure_code",
            "deployment_scripts",
        ],
        "qa_engineer": ["test_plan", "test_cases", "test_code", "test_report", "bug_reports"],
        "technical_writer": [
            "readme",
            "api_documentation",
            "user_guide",
            "tutorials",
            "architecture_diagrams",
        ],
        "deployment_specialist": [
            "deployment_guide",
            "rollback_procedures",
            "monitoring_setup",
            "release_notes",
        ],
        "integration_tester": ["integration_test_plan", "integration_tests", "validation_report"],
    }

    return deliverables_map.get(persona_id, [])


def get_agents_for_phase(phase: SDLCPhase) -> List[str]:
    """
    Get list of agent IDs for a specific phase

    Uses the primary_personas from phase structure (no hardcoding)

    Args:
        phase: The SDLC phase

    Returns:
        List of persona IDs (agent IDs) for that phase
    """
    org = TeamOrganization()
    structure = org.get_phase_structure()

    if phase not in structure:
        return []

    return structure[phase].get("primary_personas", [])


def get_workflow_transitions() -> Dict[str, Dict[str, List[str]]]:
    """
    Generate workflow transitions for state machine

    Defines which phases can transition to which other phases,
    including forward progression and backward loops for revisions.

    Returns:
        Dictionary mapping state names to their transitions:
        {
            "state_name": {
                "next": ["next_state"],
                "can_loop_to": ["previous_state"]
            }
        }
    """
    transitions = {
        "requirements": {"next": ["design"], "can_loop_to": []},
        "design": {"next": ["security_review"], "can_loop_to": ["requirements"]},
        "security_review": {"next": ["implementation"], "can_loop_to": ["design"]},
        "implementation": {"next": ["testing"], "can_loop_to": ["design"]},
        "testing": {"next": ["documentation"], "can_loop_to": ["implementation"]},
        "documentation": {"next": ["deployment"], "can_loop_to": []},
        "deployment": {"next": ["complete"], "can_loop_to": []},
    }

    return transitions


def validate_phase_exit_criteria(
    phase: SDLCPhase, completed_deliverables: Set[str]
) -> Dict[str, Any]:
    """
    Validate if a phase can be exited based on completed deliverables

    Returns:
        {
            "can_exit": bool,
            "missing_criteria": List[str],
            "completion_percentage": float
        }
    """
    org = TeamOrganization()
    structure = org.get_phase_structure()

    if phase not in structure:
        return {
            "can_exit": False,
            "missing_criteria": ["Invalid phase"],
            "completion_percentage": 0.0,
        }

    exit_criteria = structure[phase].get("exit_criteria", [])

    # Simple validation: check if key deliverables exist
    deliverables = set(structure[phase].get("deliverables", []))
    missing_deliverables = deliverables - completed_deliverables

    missing_criteria = []
    for criterion in exit_criteria:
        # Map criteria to deliverables (simplified check)
        if any(deliv.lower() in criterion.lower() for deliv in missing_deliverables):
            missing_criteria.append(criterion)

    completion_percentage = (
        (len(completed_deliverables & deliverables) / len(deliverables) * 100)
        if deliverables
        else 0
    )

    return {
        "can_exit": len(missing_criteria) == 0,
        "missing_criteria": missing_criteria,
        "completion_percentage": completion_percentage,
    }


if __name__ == "__main__":
    # Demo: Print team organization
    org = TeamOrganization()

    print("=" * 80)
    print("SDLC TEAM ORGANIZATION")
    print("=" * 80)

    structure = org.get_phase_structure()

    for phase_name, phase_info in structure.items():
        print(f"\n📋 {phase_info['name'].upper()}")
        print("-" * 80)
        print(f"Primary: {', '.join(phase_info['primary_personas'])}")
        if phase_info.get("supporting_personas"):
            print(f"Supporting: {', '.join(phase_info['supporting_personas'])}")
        print(f"\nDeliverables:")
        for deliverable in phase_info["deliverables"]:
            print(f"  - {deliverable}")

    print("\n" + "=" * 80)
    print("COLLABORATION MATRIX")
    print("=" * 80)

    collab = org.get_collaboration_matrix()
    for persona, collaborations in collab.items():
        print(f"\n{persona}:")
        for c in collaborations:
            print(f"  → {c['persona']}: {c['purpose']} ({c['frequency']})")

    print("\n" + "=" * 80)
    print("COMMUNICATION CHANNELS")
    print("=" * 80)

    channels = org.get_communication_channels()
    for channel, members in channels.items():
        print(f"\n#{channel}:")
        print(f"  Members: {', '.join(members)}")

    print("\n" + "=" * 80)
