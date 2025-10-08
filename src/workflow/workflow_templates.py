"""
Pre-built workflow templates for common scenarios
"""

import uuid
from typing import Any, Dict

from .dag import DAG, TaskType, WorkflowBuilder


class WorkflowTemplates:
    """Collection of pre-built workflow templates"""

    @staticmethod
    def software_development_workflow(feature_name: str, include_qa: bool = True) -> DAG:
        """
        Standard software development workflow

        Args:
            feature_name: Name of the feature being developed
            include_qa: Whether to include QA testing phase
        """
        workflow_id = f"sw_dev_{uuid.uuid4().hex[:8]}"

        builder = (
            WorkflowBuilder(
                workflow_id=workflow_id,
                name=f"Software Development: {feature_name}",
                description="Complete software development lifecycle",
            )
            .add_task(
                "requirements",
                "Requirements Gathering",
                f"Document requirements for {feature_name}",
                task_type=TaskType.RESEARCH,
                required_role="product_manager",
                priority=10,
                tags=["requirements", "planning"],
            )
            .add_task(
                "design",
                "Technical Design",
                "Create technical architecture and design",
                task_type=TaskType.RESEARCH,
                required_role="architect",
                depends_on=["requirements"],
                priority=9,
                tags=["design", "architecture"],
            )
            .add_task(
                "implement_backend",
                "Backend Implementation",
                "Implement server-side logic",
                task_type=TaskType.CODE,
                required_role="backend_developer",
                depends_on=["design"],
                priority=8,
                tags=["implementation", "backend"],
            )
            .add_task(
                "implement_frontend",
                "Frontend Implementation",
                "Implement user interface",
                task_type=TaskType.CODE,
                required_role="frontend_developer",
                depends_on=["design"],
                priority=8,
                tags=["implementation", "frontend"],
            )
            .add_task(
                "unit_tests",
                "Unit Testing",
                "Write and run unit tests",
                task_type=TaskType.TEST,
                required_role="developer",
                depends_on=["implement_backend", "implement_frontend"],
                priority=7,
                tags=["testing", "unit-tests"],
            )
        )

        if include_qa:
            builder.add_task(
                "qa_testing",
                "QA Testing",
                "Comprehensive quality assurance testing",
                task_type=TaskType.TEST,
                required_role="qa_engineer",
                depends_on=["unit_tests"],
                priority=8,
                tags=["testing", "qa"],
            )
            review_deps = ["qa_testing"]
        else:
            review_deps = ["unit_tests"]

        builder.add_task(
            "code_review",
            "Code Review",
            "Peer review of all changes",
            task_type=TaskType.REVIEW,
            required_role="reviewer",
            depends_on=review_deps,
            priority=9,
            tags=["review", "quality"],
        ).add_task(
            "deploy_staging",
            "Deploy to Staging",
            "Deploy to staging environment",
            task_type=TaskType.DEPLOY,
            required_role="devops",
            depends_on=["code_review"],
            priority=6,
            tags=["deployment", "staging"],
        ).add_task(
            "production_deploy",
            "Deploy to Production",
            "Deploy to production environment",
            task_type=TaskType.DEPLOY,
            required_role="devops",
            depends_on=["deploy_staging"],
            priority=10,
            tags=["deployment", "production"],
        )

        return builder.build()

    @staticmethod
    def research_workflow(research_topic: str, num_researchers: int = 2) -> DAG:
        """
        Research and analysis workflow

        Args:
            research_topic: Topic being researched
            num_researchers: Number of parallel researchers
        """
        workflow_id = f"research_{uuid.uuid4().hex[:8]}"

        builder = WorkflowBuilder(
            workflow_id=workflow_id,
            name=f"Research: {research_topic}",
            description="Comprehensive research workflow",
        ).add_task(
            "hypothesis",
            "Define Hypothesis",
            f"Define research hypothesis for {research_topic}",
            task_type=TaskType.RESEARCH,
            required_role="lead_researcher",
            priority=10,
            tags=["research", "planning"],
        )

        # Add parallel research tasks
        research_tasks = []
        for i in range(num_researchers):
            task_id = f"research_{i+1}"
            builder.add_task(
                task_id,
                f"Research Phase {i+1}",
                f"Conduct research investigation {i+1}",
                task_type=TaskType.RESEARCH,
                required_role="researcher",
                depends_on=["hypothesis"],
                priority=8,
                tags=["research", "investigation"],
            )
            research_tasks.append(task_id)

        # Synthesis depends on all research tasks
        builder.add_task(
            "synthesize",
            "Synthesize Findings",
            "Combine and analyze all research findings",
            task_type=TaskType.RESEARCH,
            required_role="lead_researcher",
            depends_on=research_tasks,
            priority=9,
            tags=["research", "analysis"],
        ).add_task(
            "write_report",
            "Write Research Report",
            "Document findings in comprehensive report",
            task_type=TaskType.CUSTOM,
            required_role="researcher",
            depends_on=["synthesize"],
            priority=7,
            tags=["documentation", "report"],
        ).add_task(
            "peer_review",
            "Peer Review",
            "Expert review of research and methodology",
            task_type=TaskType.REVIEW,
            required_role="senior_researcher",
            depends_on=["write_report"],
            priority=10,
            tags=["review", "quality"],
        )

        return builder.build()

    @staticmethod
    def incident_response_workflow(incident_name: str) -> DAG:
        """
        Emergency incident response workflow

        Args:
            incident_name: Name/ID of the incident
        """
        workflow_id = f"incident_{uuid.uuid4().hex[:8]}"

        return (
            WorkflowBuilder(
                workflow_id=workflow_id,
                name=f"Incident Response: {incident_name}",
                description="Emergency incident response procedure",
            )
            .add_task(
                "assess",
                "Initial Assessment",
                "Assess severity and impact of incident",
                task_type=TaskType.RESEARCH,
                required_role="incident_commander",
                priority=10,
                tags=["incident", "assessment", "urgent"],
            )
            .add_task(
                "contain",
                "Contain Incident",
                "Prevent further damage or spread",
                task_type=TaskType.CUSTOM,
                required_role="responder",
                depends_on=["assess"],
                priority=10,
                tags=["incident", "containment", "urgent"],
            )
            .add_task(
                "investigate",
                "Root Cause Investigation",
                "Determine root cause of incident",
                task_type=TaskType.RESEARCH,
                required_role="investigator",
                depends_on=["contain"],
                priority=9,
                tags=["incident", "investigation"],
            )
            .add_task(
                "fix",
                "Implement Fix",
                "Apply permanent solution",
                task_type=TaskType.CODE,
                required_role="developer",
                depends_on=["investigate"],
                priority=9,
                tags=["incident", "fix"],
            )
            .add_task(
                "verify",
                "Verify Resolution",
                "Confirm incident is fully resolved",
                task_type=TaskType.TEST,
                required_role="responder",
                depends_on=["fix"],
                priority=10,
                tags=["incident", "verification"],
            )
            .add_task(
                "postmortem",
                "Post-Mortem Analysis",
                "Document lessons learned",
                task_type=TaskType.CUSTOM,
                required_role="incident_commander",
                depends_on=["verify"],
                priority=7,
                tags=["incident", "documentation"],
            )
            .build()
        )

    @staticmethod
    def content_creation_workflow(content_type: str = "article") -> DAG:
        """
        Content creation and publishing workflow

        Args:
            content_type: Type of content (article, video, podcast, etc.)
        """
        workflow_id = f"content_{uuid.uuid4().hex[:8]}"

        return (
            WorkflowBuilder(
                workflow_id=workflow_id,
                name=f"Create {content_type.title()}",
                description=f"{content_type.title()} creation workflow",
            )
            .add_task(
                "brainstorm",
                "Brainstorm Ideas",
                f"Generate ideas for {content_type}",
                task_type=TaskType.RESEARCH,
                required_role="content_lead",
                priority=8,
                tags=["content", "planning"],
            )
            .add_task(
                "outline",
                "Create Outline",
                "Structure the content",
                task_type=TaskType.RESEARCH,
                required_role="writer",
                depends_on=["brainstorm"],
                priority=7,
                tags=["content", "planning"],
            )
            .add_task(
                "draft",
                "Write Draft",
                f"Create first draft of {content_type}",
                task_type=TaskType.CUSTOM,
                required_role="writer",
                depends_on=["outline"],
                priority=8,
                tags=["content", "creation"],
            )
            .add_task(
                "edit",
                "Editorial Review",
                "Edit for clarity, grammar, and style",
                task_type=TaskType.REVIEW,
                required_role="editor",
                depends_on=["draft"],
                priority=9,
                tags=["content", "review"],
            )
            .add_task(
                "fact_check",
                "Fact Checking",
                "Verify all facts and claims",
                task_type=TaskType.REVIEW,
                required_role="fact_checker",
                depends_on=["edit"],
                priority=9,
                tags=["content", "quality"],
            )
            .add_task(
                "finalize",
                "Finalize Content",
                "Apply final touches and formatting",
                task_type=TaskType.CUSTOM,
                required_role="writer",
                depends_on=["fact_check"],
                priority=7,
                tags=["content", "finalization"],
            )
            .add_task(
                "publish",
                "Publish Content",
                f"Publish {content_type} to platform",
                task_type=TaskType.DEPLOY,
                required_role="publisher",
                depends_on=["finalize"],
                priority=10,
                tags=["content", "publishing"],
            )
            .build()
        )

    @staticmethod
    def ml_model_development_workflow(model_name: str) -> DAG:
        """
        Machine learning model development workflow

        Args:
            model_name: Name of the ML model
        """
        workflow_id = f"ml_{uuid.uuid4().hex[:8]}"

        return (
            WorkflowBuilder(
                workflow_id=workflow_id,
                name=f"ML Model: {model_name}",
                description="Complete ML model development pipeline",
            )
            .add_task(
                "data_collection",
                "Data Collection",
                "Gather and prepare training data",
                task_type=TaskType.RESEARCH,
                required_role="data_engineer",
                priority=10,
                tags=["ml", "data"],
            )
            .add_task(
                "eda",
                "Exploratory Data Analysis",
                "Analyze data characteristics and patterns",
                task_type=TaskType.RESEARCH,
                required_role="data_scientist",
                depends_on=["data_collection"],
                priority=9,
                tags=["ml", "analysis"],
            )
            .add_task(
                "feature_engineering",
                "Feature Engineering",
                "Design and create features",
                task_type=TaskType.CODE,
                required_role="data_scientist",
                depends_on=["eda"],
                priority=8,
                tags=["ml", "features"],
            )
            .add_task(
                "model_training",
                "Model Training",
                "Train and tune ML model",
                task_type=TaskType.CODE,
                required_role="ml_engineer",
                depends_on=["feature_engineering"],
                priority=9,
                tags=["ml", "training"],
            )
            .add_task(
                "model_evaluation",
                "Model Evaluation",
                "Evaluate model performance",
                task_type=TaskType.TEST,
                required_role="ml_engineer",
                depends_on=["model_training"],
                priority=9,
                tags=["ml", "evaluation"],
            )
            .add_task(
                "model_review",
                "Model Review",
                "Peer review of model and methodology",
                task_type=TaskType.REVIEW,
                required_role="senior_data_scientist",
                depends_on=["model_evaluation"],
                priority=10,
                tags=["ml", "review"],
            )
            .add_task(
                "deploy_model",
                "Deploy Model",
                "Deploy model to production",
                task_type=TaskType.DEPLOY,
                required_role="ml_engineer",
                depends_on=["model_review"],
                priority=8,
                tags=["ml", "deployment"],
            )
            .add_task(
                "monitoring_setup",
                "Setup Monitoring",
                "Configure model performance monitoring",
                task_type=TaskType.CODE,
                required_role="ml_engineer",
                depends_on=["deploy_model"],
                priority=7,
                tags=["ml", "monitoring"],
            )
            .build()
        )


# Example usage
if __name__ == "__main__":
    # Create and visualize a software development workflow
    workflow = WorkflowTemplates.software_development_workflow(
        feature_name="User Authentication", include_qa=True
    )

    print(workflow.visualize())
    print("\n" + "=" * 70 + "\n")

    # Research workflow
    research = WorkflowTemplates.research_workflow(
        research_topic="Climate Change Impact", num_researchers=3
    )

    print(research.visualize())
