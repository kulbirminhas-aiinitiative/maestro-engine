"""
DAG (Directed Acyclic Graph) implementation for workflows
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class TaskType(str, Enum):
    """Task types in workflow"""

    CODE = "code"
    REVIEW = "review"
    TEST = "test"
    DEPLOY = "deploy"
    RESEARCH = "research"
    DECISION = "decision"
    CUSTOM = "custom"


@dataclass
class TaskNode:
    """
    Represents a task node in the DAG
    """

    id: str
    title: str
    description: str
    task_type: TaskType = TaskType.CUSTOM
    required_role: Optional[str] = None
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    # Runtime fields (set during execution)
    depends_on: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "task_type": (
                self.task_type.value if isinstance(self.task_type, TaskType) else self.task_type
            ),
            "required_role": self.required_role,
            "priority": self.priority,
            "metadata": self.metadata,
            "tags": self.tags,
            "depends_on": self.depends_on,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "TaskNode":
        return TaskNode(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            task_type=TaskType(data.get("task_type", "custom")),
            required_role=data.get("required_role"),
            priority=data.get("priority", 0),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
            depends_on=data.get("depends_on", []),
        )


class DAG:
    """
    Directed Acyclic Graph for workflow management
    """

    def __init__(self, workflow_id: str, name: str, description: str = ""):
        self.workflow_id = workflow_id
        self.name = name
        self.description = description
        self.nodes: Dict[str, TaskNode] = {}
        self.edges: List[tuple[str, str]] = []  # (from_id, to_id)

    def add_node(self, node: TaskNode):
        """Add a task node to the DAG"""
        if node.id in self.nodes:
            raise ValueError(f"Node {node.id} already exists in DAG")
        self.nodes[node.id] = node

    def add_edge(self, from_id: str, to_id: str):
        """
        Add a dependency edge: to_id depends on from_id

        Args:
            from_id: Task that must complete first
            to_id: Task that depends on from_id
        """
        if from_id not in self.nodes:
            raise ValueError(f"Node {from_id} not found in DAG")
        if to_id not in self.nodes:
            raise ValueError(f"Node {to_id} not found in DAG")

        # Check for cycles
        if self._would_create_cycle(from_id, to_id):
            raise ValueError(f"Adding edge {from_id} -> {to_id} would create a cycle")

        self.edges.append((from_id, to_id))
        self.nodes[to_id].depends_on.append(from_id)
        self.nodes[from_id].dependents.append(to_id)

    def _would_create_cycle(self, from_id: str, to_id: str) -> bool:
        """Check if adding this edge would create a cycle"""
        # DFS from to_id to see if we can reach from_id
        visited = set()
        stack = [to_id]

        while stack:
            current = stack.pop()
            if current == from_id:
                return True

            if current in visited:
                continue

            visited.add(current)

            # Add all dependents of current node
            if current in self.nodes:
                stack.extend(self.nodes[current].dependents)

        return False

    def get_entry_points(self) -> List[TaskNode]:
        """Get tasks with no dependencies (can start immediately)"""
        return [node for node in self.nodes.values() if not node.depends_on]

    def get_ready_tasks(self, completed_tasks: Set[str]) -> List[TaskNode]:
        """
        Get tasks that are ready to execute

        Args:
            completed_tasks: Set of task IDs that have been completed

        Returns:
            List of tasks whose dependencies are all satisfied
        """
        ready = []
        for node in self.nodes.values():
            if node.id not in completed_tasks:
                if all(dep in completed_tasks for dep in node.depends_on):
                    ready.append(node)

        # Sort by priority (higher first)
        ready.sort(key=lambda n: n.priority, reverse=True)
        return ready

    def get_descendants(self, node_id: str) -> Set[str]:
        """Get all tasks that depend on this task (directly or indirectly)"""
        descendants = set()
        stack = [node_id]

        while stack:
            current = stack.pop()
            if current in self.nodes:
                for dependent in self.nodes[current].dependents:
                    if dependent not in descendants:
                        descendants.add(dependent)
                        stack.append(dependent)

        return descendants

    def get_ancestors(self, node_id: str) -> Set[str]:
        """Get all tasks this task depends on (directly or indirectly)"""
        ancestors = set()
        stack = [node_id]

        while stack:
            current = stack.pop()
            if current in self.nodes:
                for dependency in self.nodes[current].depends_on:
                    if dependency not in ancestors:
                        ancestors.add(dependency)
                        stack.append(dependency)

        return ancestors

    def topological_sort(self) -> List[TaskNode]:
        """
        Return tasks in topological order (respecting dependencies)

        Returns:
            List of tasks in execution order
        """
        in_degree = {node_id: len(node.depends_on) for node_id, node in self.nodes.items()}
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Sort by priority
            queue.sort(key=lambda nid: self.nodes[nid].priority, reverse=True)
            node_id = queue.pop(0)
            result.append(self.nodes[node_id])

            for dependent in self.nodes[node_id].dependents:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self.nodes):
            raise ValueError("DAG contains a cycle (should have been caught earlier)")

        return result

    def validate(self) -> bool:
        """Validate DAG structure"""
        try:
            # Check for cycles via topological sort
            self.topological_sort()

            # Check all edges reference valid nodes
            for from_id, to_id in self.edges:
                if from_id not in self.nodes or to_id not in self.nodes:
                    return False

            return True
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize DAG to dictionary"""
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": self.edges,
        }

    def to_json(self) -> str:
        """Serialize DAG to JSON"""
        return json.dumps(self.to_dict(), indent=2)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "DAG":
        """Deserialize DAG from dictionary"""
        dag = DAG(
            workflow_id=data["workflow_id"],
            name=data["name"],
            description=data.get("description", ""),
        )

        # Add nodes
        for node_data in data["nodes"]:
            node = TaskNode.from_dict(node_data)
            dag.nodes[node.id] = node

        # Add edges (without validation, as dependencies are in nodes)
        for from_id, to_id in data["edges"]:
            if (from_id, to_id) not in dag.edges:
                dag.edges.append((from_id, to_id))

        return dag

    @staticmethod
    def from_json(json_str: str) -> "DAG":
        """Deserialize DAG from JSON"""
        return DAG.from_dict(json.loads(json_str))

    def visualize(self) -> str:
        """Generate a simple text visualization of the DAG"""
        lines = [f"Workflow: {self.name}", f"ID: {self.workflow_id}", ""]

        # Show topological order
        try:
            sorted_nodes = self.topological_sort()
            lines.append("Execution Order (topological):")
            for i, node in enumerate(sorted_nodes, 1):
                deps = f" (depends on: {', '.join(node.depends_on)})" if node.depends_on else ""
                lines.append(f"  {i}. [{node.id}] {node.title}{deps}")
        except Exception as e:
            lines.append(f"  Error: {e}")

        lines.append("")
        lines.append("Dependencies:")
        for from_id, to_id in self.edges:
            lines.append(f"  {from_id} → {to_id}")

        return "\n".join(lines)


class WorkflowBuilder:
    """
    Fluent builder for creating workflows
    """

    def __init__(self, workflow_id: str, name: str, description: str = ""):
        self.dag = DAG(workflow_id, name, description)

    def add_task(
        self,
        task_id: str,
        title: str,
        description: str,
        task_type: TaskType = TaskType.CUSTOM,
        required_role: Optional[str] = None,
        priority: int = 0,
        depends_on: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> "WorkflowBuilder":
        """Add a task to the workflow"""
        node = TaskNode(
            id=task_id,
            title=title,
            description=description,
            task_type=task_type,
            required_role=required_role,
            priority=priority,
            metadata=metadata or {},
            tags=tags or [],
        )
        self.dag.add_node(node)

        # Add dependencies
        if depends_on:
            for dep in depends_on:
                self.dag.add_edge(dep, task_id)

        return self

    def add_sequential_tasks(self, tasks: List[Dict[str, Any]]) -> "WorkflowBuilder":
        """
        Add tasks in sequence (each depends on the previous)

        Args:
            tasks: List of task definitions (same format as add_task kwargs)
        """
        previous_id = None

        for task_data in tasks:
            task_id = task_data["task_id"]
            depends_on = [previous_id] if previous_id else None

            self.add_task(
                task_id=task_id,
                title=task_data["title"],
                description=task_data["description"],
                task_type=TaskType(task_data.get("task_type", "custom")),
                required_role=task_data.get("required_role"),
                priority=task_data.get("priority", 0),
                depends_on=depends_on,
                metadata=task_data.get("metadata"),
                tags=task_data.get("tags"),
            )

            previous_id = task_id

        return self

    def add_parallel_tasks(
        self, tasks: List[Dict[str, Any]], depends_on: Optional[List[str]] = None
    ) -> "WorkflowBuilder":
        """
        Add tasks that can run in parallel (all depend on the same predecessors)

        Args:
            tasks: List of task definitions
            depends_on: List of task IDs these all depend on
        """
        for task_data in tasks:
            self.add_task(
                task_id=task_data["task_id"],
                title=task_data["title"],
                description=task_data["description"],
                task_type=TaskType(task_data.get("task_type", "custom")),
                required_role=task_data.get("required_role"),
                priority=task_data.get("priority", 0),
                depends_on=depends_on,
                metadata=task_data.get("metadata"),
                tags=task_data.get("tags"),
            )

        return self

    def build(self) -> DAG:
        """Build and validate the DAG"""
        if not self.dag.validate():
            raise ValueError("Invalid DAG structure")
        return self.dag


# Example usage
if __name__ == "__main__":
    # Example: Software development workflow
    builder = WorkflowBuilder(
        workflow_id="dev_workflow_1",
        name="Feature Development Workflow",
        description="Standard workflow for developing a new feature",
    )

    # Add tasks with dependencies
    workflow = (
        builder.add_task(
            "design",
            "Design Feature",
            "Create technical design document",
            task_type=TaskType.RESEARCH,
            required_role="architect",
            priority=10,
        )
        .add_task(
            "implement_backend",
            "Implement Backend",
            "Implement server-side logic",
            task_type=TaskType.CODE,
            required_role="developer",
            depends_on=["design"],
            priority=8,
        )
        .add_task(
            "implement_frontend",
            "Implement Frontend",
            "Implement user interface",
            task_type=TaskType.CODE,
            required_role="developer",
            depends_on=["design"],
            priority=8,
        )
        .add_task(
            "write_tests",
            "Write Tests",
            "Write unit and integration tests",
            task_type=TaskType.TEST,
            required_role="developer",
            depends_on=["implement_backend", "implement_frontend"],
            priority=7,
        )
        .add_task(
            "code_review",
            "Code Review",
            "Review all code changes",
            task_type=TaskType.REVIEW,
            required_role="reviewer",
            depends_on=["write_tests"],
            priority=9,
        )
        .add_task(
            "deploy",
            "Deploy to Staging",
            "Deploy feature to staging environment",
            task_type=TaskType.DEPLOY,
            required_role="developer",
            depends_on=["code_review"],
            priority=6,
        )
        .build()
    )

    print(workflow.visualize())
    print("\n" + "=" * 70 + "\n")
    print("Entry points:", [n.id for n in workflow.get_entry_points()])
    print("\nReady tasks (nothing completed):", [n.id for n in workflow.get_ready_tasks(set())])
    print("\nReady tasks (design completed):", [n.id for n in workflow.get_ready_tasks({"design"})])
    print("\nJSON representation:")
    print(workflow.to_json())
