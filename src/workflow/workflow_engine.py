"""
Workflow execution engine with DAG support
"""

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from ..persistence.models import TaskStatus
from ..persistence.state_manager import StateManager
from .dag import DAG, TaskNode


class WorkflowStatus(str, Enum):
    """Workflow execution status"""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowEngine:
    """
    Workflow engine for managing and executing DAG-based workflows
    """

    def __init__(self, state_manager: StateManager):
        """
        Initialize workflow engine

        Args:
            state_manager: StateManager instance for persistence
        """
        self.state = state_manager
        self.active_workflows: Dict[str, WorkflowExecutor] = {}

    async def create_workflow(
        self, team_id: str, dag: DAG, created_by: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new workflow from DAG

        Args:
            team_id: Team ID
            dag: DAG definition
            created_by: Agent that created the workflow
            metadata: Additional metadata

        Returns:
            Workflow ID
        """
        # Store workflow definition in database
        from ..persistence.models import WorkflowDefinition

        workflow = WorkflowDefinition(
            id=dag.workflow_id,
            team_id=team_id,
            name=dag.name,
            description=dag.description,
            dag_definition=dag.to_dict(),
            created_by=created_by,
            status=WorkflowStatus.PENDING.value,
            metadata=metadata or {},
        )

        async with self.state.db.session() as session:
            session.add(workflow)

        # Create all tasks from DAG
        for node in dag.nodes.values():
            await self.state.create_task(
                team_id=team_id,
                title=node.title,
                description=node.description,
                created_by=created_by,
                required_role=node.required_role,
                priority=node.priority,
                workflow_id=dag.workflow_id,
                depends_on=node.depends_on,
                metadata=node.metadata,
                tags=node.tags,
            )

        return dag.workflow_id

    async def start_workflow(self, workflow_id: str):
        """
        Start executing a workflow

        Args:
            workflow_id: Workflow ID to execute
        """
        # Load workflow from database
        async with self.state.db.session() as session:
            from sqlalchemy import select

            from ..persistence.models import WorkflowDefinition

            result = await session.execute(
                select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id)
            )
            workflow_def = result.scalar_one()

        # Create DAG from definition
        dag = DAG.from_dict(workflow_def.dag_definition)

        # Create and start executor
        executor = WorkflowExecutor(
            workflow_id=workflow_id, team_id=workflow_def.team_id, dag=dag, state_manager=self.state
        )

        self.active_workflows[workflow_id] = executor

        # Update workflow status
        await self._update_workflow_status(workflow_id, WorkflowStatus.RUNNING)

        # Start execution in background
        asyncio.create_task(self._execute_workflow(executor))

    async def pause_workflow(self, workflow_id: str):
        """Pause workflow execution"""
        if workflow_id in self.active_workflows:
            self.active_workflows[workflow_id].paused = True
            await self._update_workflow_status(workflow_id, WorkflowStatus.PAUSED)

    async def resume_workflow(self, workflow_id: str):
        """Resume paused workflow"""
        if workflow_id in self.active_workflows:
            self.active_workflows[workflow_id].paused = False
            await self._update_workflow_status(workflow_id, WorkflowStatus.RUNNING)

    async def cancel_workflow(self, workflow_id: str):
        """Cancel workflow execution"""
        if workflow_id in self.active_workflows:
            self.active_workflows[workflow_id].cancelled = True
            await self._update_workflow_status(workflow_id, WorkflowStatus.CANCELLED)

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow execution status"""
        if workflow_id in self.active_workflows:
            return self.active_workflows[workflow_id].get_status()

        # Load from database
        async with self.state.db.session() as session:
            from sqlalchemy import select

            from ..persistence.models import Task, WorkflowDefinition

            # Get workflow
            workflow_result = await session.execute(
                select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id)
            )
            workflow = workflow_result.scalar_one_or_none()

            if not workflow:
                return {"error": "Workflow not found"}

            # Get tasks
            tasks_result = await session.execute(
                select(Task).where(Task.workflow_id == workflow_id)
            )
            tasks = tasks_result.scalars().all()

            task_counts = {}
            for task in tasks:
                status = task.status.value if isinstance(task.status, TaskStatus) else task.status
                task_counts[status] = task_counts.get(status, 0) + 1

            return {
                "workflow_id": workflow_id,
                "status": workflow.status,
                "task_counts": task_counts,
                "total_tasks": len(tasks),
            }

    async def _execute_workflow(self, executor: "WorkflowExecutor"):
        """Execute workflow in background"""
        try:
            await executor.execute()

            # Update final status
            if executor.cancelled:
                await self._update_workflow_status(executor.workflow_id, WorkflowStatus.CANCELLED)
            elif executor.failed:
                await self._update_workflow_status(executor.workflow_id, WorkflowStatus.FAILED)
            else:
                await self._update_workflow_status(executor.workflow_id, WorkflowStatus.COMPLETED)

        except Exception as e:
            print(f"Workflow execution error: {e}")
            await self._update_workflow_status(executor.workflow_id, WorkflowStatus.FAILED)

        finally:
            # Clean up
            if executor.workflow_id in self.active_workflows:
                del self.active_workflows[executor.workflow_id]

    async def _update_workflow_status(self, workflow_id: str, status: WorkflowStatus):
        """Update workflow status in database"""
        async with self.state.db.session() as session:
            from sqlalchemy import update

            from ..persistence.models import WorkflowDefinition

            await session.execute(
                update(WorkflowDefinition)
                .where(WorkflowDefinition.id == workflow_id)
                .values(status=status.value, updated_at=datetime.utcnow())
            )


class WorkflowExecutor:
    """
    Executes a single workflow
    Monitors task completion and manages dependencies
    """

    def __init__(self, workflow_id: str, team_id: str, dag: DAG, state_manager: StateManager):
        self.workflow_id = workflow_id
        self.team_id = team_id
        self.dag = dag
        self.state = state_manager

        self.completed_tasks: Set[str] = set()
        self.failed_tasks: Set[str] = set()
        self.paused = False
        self.cancelled = False
        self.failed = False

        self._task_completion_callbacks: Dict[str, List[Callable]] = {}

    async def execute(self):
        """Execute the workflow"""
        # Subscribe to task completion events
        await self.state.subscribe_to_events(self.team_id, "task.*", self._handle_task_event)

        # Initial tasks are those with no dependencies
        entry_points = self.dag.get_entry_points()

        if not entry_points:
            raise ValueError("Workflow has no entry points (all tasks have dependencies?)")

        # Monitor until workflow completes
        while not self._is_complete() and not self.cancelled:
            if self.paused:
                await asyncio.sleep(1)
                continue

            # Check for failures
            if self.failed_tasks:
                self.failed = True
                break

            await asyncio.sleep(2)  # Poll interval

        # Unsubscribe from events
        # (In production, implement proper cleanup)

    async def _handle_task_event(self, channel: str, event: Dict[str, Any]):
        """Handle task completion/failure events"""
        event_type = event.get("type")
        data = event.get("data", {})
        task_id = data.get("task_id")

        if not task_id or task_id not in self.dag.nodes:
            return  # Not part of this workflow

        if event_type == "task.completed":
            self.completed_tasks.add(task_id)

            # Trigger callbacks
            if task_id in self._task_completion_callbacks:
                for callback in self._task_completion_callbacks[task_id]:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(task_id, data)
                        else:
                            callback(task_id, data)
                    except Exception as e:
                        print(f"Error in task completion callback: {e}")

        elif event_type == "task.failed":
            self.failed_tasks.add(task_id)

    def _is_complete(self) -> bool:
        """Check if workflow is complete"""
        return len(self.completed_tasks) == len(self.dag.nodes)

    def on_task_complete(self, task_id: str, callback: Callable):
        """Register callback for task completion"""
        if task_id not in self._task_completion_callbacks:
            self._task_completion_callbacks[task_id] = []
        self._task_completion_callbacks[task_id].append(callback)

    def get_status(self) -> Dict[str, Any]:
        """Get current execution status"""
        ready_tasks = self.dag.get_ready_tasks(self.completed_tasks)

        return {
            "workflow_id": self.workflow_id,
            "total_tasks": len(self.dag.nodes),
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "ready_tasks": len(ready_tasks),
            "ready_task_ids": [t.id for t in ready_tasks],
            "paused": self.paused,
            "cancelled": self.cancelled,
            "failed": self.failed,
            "progress": len(self.completed_tasks) / len(self.dag.nodes) * 100,
        }

    def get_critical_path(self) -> List[str]:
        """
        Get the critical path (longest path through the DAG)
        Useful for identifying bottlenecks
        """
        # Simple implementation: find path with most dependencies
        max_depth = {}

        for node in self.dag.topological_sort():
            if not node.depends_on:
                max_depth[node.id] = 1
            else:
                max_depth[node.id] = max(max_depth[dep] for dep in node.depends_on) + 1

        # Find node with max depth
        critical_node = max(max_depth.items(), key=lambda x: x[1])[0]

        # Trace back the critical path
        path = [critical_node]
        current = critical_node

        while self.dag.nodes[current].depends_on:
            # Find dependency with max depth
            deps = self.dag.nodes[current].depends_on
            next_node = max(deps, key=lambda d: max_depth[d])
            path.append(next_node)
            current = next_node

        return list(reversed(path))


# Example workflow templates
async def example_feature_development_workflow(
    state_manager: StateManager, team_id: str, created_by: str
) -> str:
    """Create a standard feature development workflow"""
    from .dag import TaskType, WorkflowBuilder

    workflow = (
        WorkflowBuilder(
            workflow_id=f"feature_dev_{uuid.uuid4().hex[:8]}",
            name="Feature Development",
            description="Standard workflow for developing a new feature",
        )
        .add_task(
            "requirements",
            "Gather Requirements",
            "Document feature requirements and user stories",
            task_type=TaskType.RESEARCH,
            required_role="product_manager",
            priority=10,
        )
        .add_task(
            "design",
            "Technical Design",
            "Create technical design and architecture",
            task_type=TaskType.RESEARCH,
            required_role="architect",
            depends_on=["requirements"],
            priority=9,
        )
        .add_task(
            "implement",
            "Implementation",
            "Implement the feature",
            task_type=TaskType.CODE,
            required_role="developer",
            depends_on=["design"],
            priority=8,
        )
        .add_task(
            "test",
            "Testing",
            "Write and run tests",
            task_type=TaskType.TEST,
            required_role="tester",
            depends_on=["implement"],
            priority=7,
        )
        .add_task(
            "review",
            "Code Review",
            "Review code and tests",
            task_type=TaskType.REVIEW,
            required_role="reviewer",
            depends_on=["test"],
            priority=9,
        )
        .add_task(
            "deploy",
            "Deployment",
            "Deploy to production",
            task_type=TaskType.DEPLOY,
            required_role="developer",
            depends_on=["review"],
            priority=6,
        )
        .build()
    )

    engine = WorkflowEngine(state_manager)
    workflow_id = await engine.create_workflow(team_id=team_id, dag=workflow, created_by=created_by)

    return workflow_id


if __name__ == "__main__":
    print("Workflow Engine - Example")
    print("See workflow/dag.py for DAG examples")
