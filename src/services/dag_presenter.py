#!/usr/bin/env python3
"""
DAG Presenter

Formats generated DAG workflows for user presentation in chat.
Creates visual ASCII diagrams and formatted approval messages.
"""

import logging
from typing import List, Dict
from services.ai_dag_generator import GeneratedDAG
from workflow.dag import DAG, TaskType

logger = logging.getLogger(__name__)


class DAGPresenter:
    """
    Formats DAG workflows for presentation to users.

    Features:
    - ASCII/Unicode visual DAG diagram
    - Phase breakdown with details
    - Dependency tree visualization
    - Timeline and complexity estimates
    - Approval action buttons
    """

    # Task type emoji mapping
    TASK_TYPE_ICONS = {
        TaskType.RESEARCH: "🔍",
        TaskType.DECISION: "📋",  # Using DECISION instead of PLANNING
        TaskType.CODE: "💻",
        TaskType.REVIEW: "👀",
        TaskType.TEST: "🧪",  # Using TEST instead of TESTING
        TaskType.DEPLOY: "🚀",  # Using DEPLOY instead of DEPLOYMENT
        TaskType.CUSTOM: "📌"
    }

    async def format_dag_for_approval(
        self,
        generated_dag: GeneratedDAG,
        pending_dag_id: str
    ) -> Dict[str, any]:
        """
        Format generated DAG for user approval.

        Args:
            generated_dag: Generated DAG with metadata
            pending_dag_id: ID for tracking pending approval

        Returns:
            Dict with formatted message and metadata
        """
        dag = generated_dag.dag
        metadata = generated_dag.metadata

        # Build the presentation message
        lines = []

        # Header
        lines.append("# 🎯 Generated Workflow")
        lines.append("")
        lines.append(f"**{dag.name}**")
        lines.append("")
        lines.append(f"_{dag.description}_")
        lines.append("")

        # Quick stats
        lines.append("## 📊 Overview")
        lines.append("")
        lines.append(f"- **Phases:** {len(dag.nodes)}")
        lines.append(f"- **Complexity:** {metadata.get('complexity', 'medium').title()}")
        lines.append(f"- **Timeline:** {generated_dag.estimated_timeline}")
        lines.append(f"- **Validation:** {'✅ Passed' if generated_dag.validation_passed else '⚠️ Needs Review'}")
        lines.append("")

        # Visual DAG diagram
        lines.append("## 🔄 Workflow Diagram")
        lines.append("")
        lines.append("```")
        lines.extend(self._create_ascii_diagram(dag))
        lines.append("```")
        lines.append("")

        # Phase breakdown
        lines.append("## 📝 Phase Breakdown")
        lines.append("")

        sorted_phases = dag.topological_sort()
        for i, phase in enumerate(sorted_phases, 1):
            icon = self.TASK_TYPE_ICONS.get(phase.task_type, "📌")

            # Phase header
            lines.append(f"### {i}. {icon} {phase.title}")
            lines.append("")
            lines.append(f"**Description:** {phase.description}")
            lines.append("")

            # Dependencies
            if phase.depends_on:
                dep_names = [dag.nodes[dep_id].title for dep_id in phase.depends_on if dep_id in dag.nodes]
                lines.append(f"**Depends on:** {', '.join(dep_names)}")
            else:
                lines.append(f"**Depends on:** None (starting phase)")
            lines.append("")

            # Details
            details = []
            details.append(f"Type: {phase.task_type.value}")
            details.append(f"Priority: {phase.priority}")

            # Check for estimated_duration in metadata
            estimated_duration = phase.metadata.get('estimated_duration') if phase.metadata else None
            if estimated_duration:
                details.append(f"Duration: {estimated_duration}")

            # Check for agent_persona in metadata
            agent_persona = phase.metadata.get('agent_persona') if phase.metadata else None
            if agent_persona:
                details.append(f"Agent: {agent_persona.replace('_', ' ').title()}")

            lines.append(f"_{' | '.join(details)}_")
            lines.append("")

        # Parallel opportunities
        if generated_dag.parallel_opportunities:
            lines.append("## ⚡ Parallel Execution")
            lines.append("")
            for opp in generated_dag.parallel_opportunities:
                lines.append(f"- {opp}")
            lines.append("")

        # Reasoning
        lines.append("## 💡 Design Rationale")
        lines.append("")
        lines.append(generated_dag.reasoning)
        lines.append("")

        # Risk factors (if any)
        if generated_dag.risk_factors:
            lines.append("## ⚠️ Risk Factors")
            lines.append("")
            for risk in generated_dag.risk_factors:
                lines.append(f"- {risk}")
            lines.append("")

        # Tech stack
        if metadata.get('tech_stack'):
            lines.append("## 🛠️ Tech Stack")
            lines.append("")
            lines.append(', '.join(metadata['tech_stack']))
            lines.append("")

        # Action buttons
        lines.append("---")
        lines.append("")
        lines.append("## ✨ Ready to Proceed?")
        lines.append("")
        lines.append("Review the workflow above and choose an action:")
        lines.append("")

        # Build structured response with overview and phases
        sorted_phases = dag.topological_sort()
        phases_list = []
        for phase in sorted_phases:
            estimated_duration = phase.metadata.get('estimated_duration') if phase.metadata else None
            agent_persona = phase.metadata.get('agent_persona') if phase.metadata else None

            phases_list.append({
                'id': phase.id,
                'name': phase.title,
                'description': phase.description,
                'task_type': phase.task_type.value,
                'depends_on': phase.depends_on,
                'priority': phase.priority,
                'estimated_duration': estimated_duration,
                'agent_persona': agent_persona
            })

        # Build response
        return {
            'type': 'dag_approval',
            'pending_dag_id': pending_dag_id,
            'content': '\n'.join(lines),
            'dag': self._serialize_dag(dag),
            'metadata': metadata,
            'overview': {
                'phase_count': len(dag.nodes),
                'complexity': metadata.get('complexity', 'medium'),
                'estimated_timeline': generated_dag.estimated_timeline,
                'validation_passed': generated_dag.validation_passed
            },
            'phases': phases_list,
            'approval_actions': [
                {
                    'id': 'approve',
                    'label': '✅ Approve & Start Execution',
                    'style': 'primary'
                },
                {
                    'id': 'modify',
                    'label': '✏️ Open Visual Editor',
                    'style': 'secondary'
                },
                {
                    'id': 'reject',
                    'label': '❌ Reject & Request Changes',
                    'style': 'danger'
                }
            ],
            'actions': [
                {
                    'id': 'approve',
                    'label': '✅ Approve & Start Execution',
                    'style': 'primary'
                },
                {
                    'id': 'modify',
                    'label': '✏️ Open Visual Editor',
                    'style': 'secondary'
                },
                {
                    'id': 'reject',
                    'label': '❌ Reject & Request Changes',
                    'style': 'danger'
                }
            ]
        }

    def _create_ascii_diagram(self, dag: DAG) -> List[str]:
        """Create ASCII diagram of DAG structure"""
        lines = []

        sorted_phases = dag.topological_sort()

        # Group phases by dependency level
        levels = self._group_by_level(dag, sorted_phases)

        for level_num, phase_ids in enumerate(levels):
            level_phases = [dag.nodes[pid] for pid in phase_ids]

            # Show phases at this level
            for phase in level_phases:
                icon = self.TASK_TYPE_ICONS.get(phase.task_type, "📌")

                # Indent based on level
                indent = "  " * level_num

                # Show dependencies with arrows
                if phase.depends_on:
                    lines.append(f"{indent}    ↓")

                # Show phase
                phase_line = f"{indent}[{icon} {phase.title}]"
                lines.append(phase_line)

                # Add parallel indicator
                if len(level_phases) > 1 and phase == level_phases[0]:
                    lines.append(f"{indent}    ║  (Parallel execution)")

        return lines

    def _group_by_level(self, dag: DAG, sorted_phases: List) -> List[List[str]]:
        """Group phases by dependency level for visualization"""
        levels = []
        processed = set()

        # Level 0: phases with no dependencies
        current_level = [p.id for p in sorted_phases if len(p.depends_on) == 0]

        while current_level:
            levels.append(current_level)
            processed.update(current_level)

            # Next level: phases whose dependencies are all processed
            next_level = []
            for phase in sorted_phases:
                if phase.id not in processed:
                    if all(dep in processed for dep in phase.depends_on):
                        next_level.append(phase.id)

            current_level = next_level

        return levels

    def _serialize_dag(self, dag: DAG) -> Dict:
        """Serialize DAG for JSON transmission"""
        return {
            'dag_id': dag.workflow_id,
            'name': dag.name,
            'description': dag.description,
            'nodes': {
                node_id: {
                    'name': node.title,
                    'description': node.description,
                    'task_type': node.task_type.value,
                    'depends_on': node.depends_on,
                    'priority': node.priority,
                    'estimated_duration': node.metadata.get('estimated_duration') if node.metadata else None,
                    'agent_persona': node.metadata.get('agent_persona') if node.metadata else None
                }
                for node_id, node in dag.nodes.items()
            }
        }

    async def format_approval_result(
        self,
        action: str,
        dag_id: str,
        dag_name: str,
        workflow_id: str = None
    ) -> str:
        """Format the result of user's approval action"""

        if action == 'approve':
            return f"""✅ **Workflow Approved!**

**{dag_name}** has been approved and saved.

**Workflow ID:** `{workflow_id}`
**DAG ID:** `{dag_id}`

🚀 Execution will begin shortly. I'll guide you through each phase and keep you updated on progress.

You can check workflow status anytime by asking me about workflow `{workflow_id}`.
"""

        elif action == 'modify':
            return f"""✏️ **Opening Visual Editor**

Loading the workflow editor for **{dag_name}**...

You can:
- Add or remove phases
- Modify dependencies
- Adjust phase properties
- Rearrange execution order

Save your changes when ready, and I'll validate the updated workflow.
"""

        elif action == 'reject':
            return f"""❌ **Workflow Rejected**

No problem! Let's refine the approach.

What would you like me to change about **{dag_name}**?

For example:
- "Too complex, make it simpler"
- "Add more testing phases"
- "I need a different architecture approach"
- "Focus more on X feature"

I'll generate an updated workflow based on your feedback.
"""

        else:
            return f"Unknown action: {action}"


# Standalone test
async def test_dag_presenter():
    """Test DAG presenter"""
    from workflow.dag import WorkflowBuilder, TaskType
    from services.ai_dag_generator import GeneratedDAG

    # Create a sample DAG
    dag = (
        WorkflowBuilder(
            workflow_id="test_dag_123",
            name="SaaS Application Workflow",
            description="Complete workflow for building a multi-tenant SaaS application"
        )
        .add_task(
            "requirements",
            "Requirements Analysis",
            "Gather user requirements and create technical specifications",
            TaskType.RESEARCH,
            priority=10,
            estimated_duration="1-2 weeks"
        )
        .add_task(
            "architecture",
            "System Architecture",
            "Design system architecture, database schema, and API structure",
            TaskType.DECISION,
            depends_on=["requirements"],
            priority=9,
            estimated_duration="1 week"
        )
        .add_task(
            "frontend",
            "Frontend Development",
            "Build React-based user interface",
            TaskType.CODE,
            depends_on=["architecture"],
            priority=8,
            estimated_duration="3 weeks"
        )
        .add_task(
            "backend",
            "Backend Development",
            "Build FastAPI backend with PostgreSQL",
            TaskType.CODE,
            depends_on=["architecture"],
            priority=8,
            estimated_duration="3 weeks"
        )
        .add_task(
            "testing",
            "Integration Testing",
            "End-to-end testing and QA",
            TaskType.TEST,
            depends_on=["frontend", "backend"],
            priority=7,
            estimated_duration="1 week"
        )
        .add_task(
            "deployment",
            "AWS Deployment",
            "Deploy to AWS with CI/CD pipeline",
            TaskType.DEPLOY,
            depends_on=["testing"],
            priority=6,
            estimated_duration="3-5 days"
        )
        .build()
    )

    # Create GeneratedDAG wrapper
    generated_dag = GeneratedDAG(
        dag=dag,
        metadata={
            'complexity': 'complex',
            'tech_stack': ['React', 'Python', 'FastAPI', 'PostgreSQL', 'AWS']
        },
        reasoning="This workflow structure ensures proper separation of concerns with parallel frontend/backend development after architecture phase, followed by comprehensive testing before deployment.",
        estimated_timeline="8-10 weeks",
        risk_factors=["Tight timeline for complex features", "Integration complexity"],
        parallel_opportunities=["Frontend and Backend can be developed simultaneously"],
        validation_passed=True
    )

    # Present DAG
    presenter = DAGPresenter()
    result = await presenter.format_dag_for_approval(generated_dag, "pending_abc123")

    print(result['content'])
    print("\n" + "="*80)
    print("ACTIONS:")
    for action in result['actions']:
        print(f"  [{action['id']}] {action['label']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_dag_presenter())
