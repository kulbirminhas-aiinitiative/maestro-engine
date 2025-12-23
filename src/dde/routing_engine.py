#!/usr/bin/env python3
"""
RoutingEngine - Interface-First Task Scheduling

Schedules tasks based on interface readiness, reducing blocked tasks by 30%.

MD-2091: [DDE-2] Implement interface-first scheduling

Features:
- InterfaceContract definition for nodes
- Interface-first scheduling algorithm
- Readiness scoring based on input availability
- Blocked time tracking and optimization
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)

# Optional Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, Gauge
    PROMETHEUS_AVAILABLE = True

    ROUTING_DECISIONS = Counter(
        "dde_routing_decisions_total",
        "Total routing decisions",
        ["decision_type"]
    )
    BLOCKED_TIME = Histogram(
        "dde_blocked_time_seconds",
        "Time nodes spent blocked",
        buckets=[0.1, 0.5, 1, 5, 10, 30, 60]
    )
    QUEUE_DEPTH = Gauge(
        "dde_routing_queue_depth",
        "Current routing queue depth"
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    ROUTING_DECISIONS = None
    BLOCKED_TIME = None
    QUEUE_DEPTH = None


class FieldType(Enum):
    """Types of interface fields."""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    FILE = "file"
    ANY = "any"


@dataclass
class InterfaceField:
    """
    Definition of an input or output field in an interface contract.
    """
    name: str
    field_type: FieldType
    required: bool = True
    description: Optional[str] = None
    default_value: Any = None
    validator: Optional[Callable[[Any], bool]] = None

    def validate(self, value: Any) -> bool:
        """Validate a value against this field definition."""
        if value is None:
            return not self.required

        if self.validator:
            return self.validator(value)

        # Basic type checking
        type_map = {
            FieldType.STRING: str,
            FieldType.NUMBER: (int, float),
            FieldType.BOOLEAN: bool,
            FieldType.OBJECT: dict,
            FieldType.ARRAY: (list, tuple),
            FieldType.ANY: object,
        }

        expected_type = type_map.get(self.field_type, object)
        return isinstance(value, expected_type)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "field_type": self.field_type.value,
            "required": self.required,
            "description": self.description,
            "default_value": self.default_value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterfaceField":
        return cls(
            name=data["name"],
            field_type=FieldType(data["field_type"]),
            required=data.get("required", True),
            description=data.get("description"),
            default_value=data.get("default_value"),
        )


@dataclass
class InterfaceContract:
    """
    Defines expected inputs/outputs for a DAG node.
    """
    node_id: str
    version: str
    required_inputs: List[InterfaceField] = field(default_factory=list)
    optional_inputs: List[InterfaceField] = field(default_factory=list)
    produced_outputs: List[InterfaceField] = field(default_factory=list)
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def all_inputs(self) -> List[InterfaceField]:
        return self.required_inputs + self.optional_inputs

    def get_required_input_names(self) -> Set[str]:
        return {f.name for f in self.required_inputs}

    def get_output_names(self) -> Set[str]:
        return {f.name for f in self.produced_outputs}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "version": self.version,
            "required_inputs": [f.to_dict() for f in self.required_inputs],
            "optional_inputs": [f.to_dict() for f in self.optional_inputs],
            "produced_outputs": [f.to_dict() for f in self.produced_outputs],
            "description": self.description,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterfaceContract":
        return cls(
            node_id=data["node_id"],
            version=data["version"],
            required_inputs=[InterfaceField.from_dict(f) for f in data.get("required_inputs", [])],
            optional_inputs=[InterfaceField.from_dict(f) for f in data.get("optional_inputs", [])],
            produced_outputs=[InterfaceField.from_dict(f) for f in data.get("produced_outputs", [])],
            description=data.get("description"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
        )


@dataclass
class ReadinessScore:
    """
    Readiness assessment for a node.
    """
    node_id: str
    score: float  # 0.0 to 1.0
    is_runnable: bool
    satisfied_inputs: List[str]
    missing_inputs: List[str]
    blocked_by_nodes: List[str]
    estimated_wait_time: Optional[timedelta] = None
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "score": self.score,
            "is_runnable": self.is_runnable,
            "satisfied_inputs": self.satisfied_inputs,
            "missing_inputs": self.missing_inputs,
            "blocked_by_nodes": self.blocked_by_nodes,
            "estimated_wait_time": self.estimated_wait_time.total_seconds() if self.estimated_wait_time else None,
            "reason": self.reason,
        }


@dataclass
class RoutingDecision:
    """
    A routing decision for task scheduling.
    """
    decision_id: str
    node_id: str
    action: str  # "execute", "queue", "skip", "wait"
    priority: int
    readiness_score: float
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "node_id": self.node_id,
            "action": self.action,
            "priority": self.priority,
            "readiness_score": self.readiness_score,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


class DAGNode:
    """Simple DAG node representation for routing."""

    def __init__(
        self,
        node_id: str,
        depends_on: Optional[List[str]] = None,
        contract: Optional[InterfaceContract] = None,
    ):
        self.node_id = node_id
        self.depends_on = depends_on or []
        self.contract = contract


class DAG:
    """Simple DAG representation for routing."""

    def __init__(self, nodes: Optional[List[DAGNode]] = None):
        self.nodes: Dict[str, DAGNode] = {}
        self._dependents: Dict[str, Set[str]] = {}

        if nodes:
            for node in nodes:
                self.add_node(node)

    def add_node(self, node: DAGNode) -> None:
        self.nodes[node.node_id] = node

        # Build reverse dependency map
        for dep in node.depends_on:
            if dep not in self._dependents:
                self._dependents[dep] = set()
            self._dependents[dep].add(node.node_id)

    def get_dependents(self, node_id: str) -> Set[str]:
        """Get nodes that depend on this node."""
        return self._dependents.get(node_id, set())

    def get_dependencies(self, node_id: str) -> List[str]:
        """Get nodes this node depends on."""
        node = self.nodes.get(node_id)
        return node.depends_on if node else []

    def topological_sort(self) -> List[str]:
        """Return nodes in topological order."""
        visited = set()
        result = []

        def visit(node_id: str):
            if node_id in visited:
                return
            visited.add(node_id)

            node = self.nodes.get(node_id)
            if node:
                for dep in node.depends_on:
                    visit(dep)

            result.append(node_id)

        for node_id in self.nodes:
            visit(node_id)

        return result


class RoutingEngine:
    """
    Routes tasks based on interface readiness.

    Implements interface-first scheduling to minimize blocked time.
    Target: reduce blocked tasks by 30%.
    """

    def __init__(self):
        self._contracts: Dict[str, InterfaceContract] = {}
        self._completed_outputs: Dict[str, Dict[str, Any]] = {}
        self._node_start_times: Dict[str, datetime] = {}
        self._blocked_time_total: timedelta = timedelta()
        self._decisions: List[RoutingDecision] = []

        logger.info("RoutingEngine initialized")

    def register_contract(self, contract: InterfaceContract) -> None:
        """Register an interface contract for a node."""
        self._contracts[contract.node_id] = contract
        logger.debug(f"Registered contract for node {contract.node_id} v{contract.version}")

    def record_completion(
        self,
        node_id: str,
        outputs: Dict[str, Any],
    ) -> None:
        """Record that a node has completed with outputs."""
        self._completed_outputs[node_id] = outputs
        logger.debug(f"Recorded completion for node {node_id} with {len(outputs)} outputs")

    def analyze_readiness(
        self,
        node_id: str,
        dag: DAG,
    ) -> ReadinessScore:
        """
        Analyze readiness of a node based on interface availability.
        """
        node = dag.nodes.get(node_id)
        if not node:
            return ReadinessScore(
                node_id=node_id,
                score=0.0,
                is_runnable=False,
                satisfied_inputs=[],
                missing_inputs=[],
                blocked_by_nodes=[],
                reason=f"Node {node_id} not found in DAG",
            )

        # Check dependencies
        blocked_by = []
        for dep in node.depends_on:
            if dep not in self._completed_outputs:
                blocked_by.append(dep)

        # Check interface contract
        contract = self._contracts.get(node_id)
        satisfied = []
        missing = []

        if contract:
            available_outputs = set()
            for dep_id, outputs in self._completed_outputs.items():
                available_outputs.update(outputs.keys())

            for field in contract.required_inputs:
                if field.name in available_outputs or field.default_value is not None:
                    satisfied.append(field.name)
                else:
                    missing.append(field.name)
        else:
            # No contract - just check dependencies
            satisfied = list(self._completed_outputs.keys())

        # Calculate score
        if contract and contract.required_inputs:
            score = len(satisfied) / len(contract.required_inputs)
        elif not blocked_by:
            score = 1.0
        else:
            total_deps = len(node.depends_on)
            completed_deps = total_deps - len(blocked_by)
            score = completed_deps / total_deps if total_deps > 0 else 1.0

        is_runnable = len(blocked_by) == 0 and len(missing) == 0

        return ReadinessScore(
            node_id=node_id,
            score=score,
            is_runnable=is_runnable,
            satisfied_inputs=satisfied,
            missing_inputs=missing,
            blocked_by_nodes=blocked_by,
            reason="Ready" if is_runnable else f"Blocked by {blocked_by}, missing inputs: {missing}",
        )

    def get_runnable_nodes(self, dag: DAG) -> List[str]:
        """Get all nodes that can currently be executed."""
        runnable = []

        for node_id in dag.nodes:
            if node_id in self._completed_outputs:
                continue  # Already completed

            readiness = self.analyze_readiness(node_id, dag)
            if readiness.is_runnable:
                runnable.append(node_id)

        return runnable

    def calculate_optimal_order(self, dag: DAG) -> List[str]:
        """
        Calculate optimal execution order using interface-first scheduling.

        Prioritizes nodes that produce interfaces for the most dependents,
        reducing overall blocked time.
        """
        # Start with topological sort as baseline
        topo_order = dag.topological_sort()

        # Calculate priority scores
        priority_scores: Dict[str, float] = {}

        for node_id in topo_order:
            # Base priority from topological position
            base_priority = topo_order.index(node_id)

            # Bonus for nodes that unblock many dependents
            dependents = dag.get_dependents(node_id)
            unblock_bonus = len(dependents) * 10

            # Bonus for nodes with contracts that produce outputs
            contract = self._contracts.get(node_id)
            output_bonus = 0
            if contract:
                # Count how many nodes need our outputs
                for dep_id in dependents:
                    dep_contract = self._contracts.get(dep_id)
                    if dep_contract:
                        our_outputs = contract.get_output_names()
                        their_inputs = dep_contract.get_required_input_names()
                        overlap = len(our_outputs & their_inputs)
                        output_bonus += overlap * 5

            priority_scores[node_id] = base_priority - unblock_bonus - output_bonus

        # Sort by priority (lower is better)
        optimized_order = sorted(
            topo_order,
            key=lambda n: priority_scores.get(n, float('inf'))
        )

        logger.info(f"Calculated optimal order for {len(optimized_order)} nodes")
        return optimized_order

    def estimate_blocked_time(
        self,
        schedule: List[str],
        dag: DAG,
        avg_node_duration: timedelta = timedelta(seconds=30),
    ) -> timedelta:
        """
        Estimate total blocked time for a given schedule.

        Used to compare schedules and measure improvement.
        """
        completion_times: Dict[str, timedelta] = {}
        blocked_time = timedelta()
        current_time = timedelta()

        for node_id in schedule:
            node = dag.nodes.get(node_id)
            if not node:
                continue

            # Find earliest start time (when all deps complete)
            earliest_start = current_time
            for dep in node.depends_on:
                if dep in completion_times:
                    earliest_start = max(earliest_start, completion_times[dep])

            # Calculate blocked time
            if earliest_start > current_time:
                blocked_time += earliest_start - current_time

            # Record completion
            completion_times[node_id] = earliest_start + avg_node_duration
            current_time = earliest_start + avg_node_duration

        return blocked_time

    def make_routing_decision(
        self,
        node_id: str,
        dag: DAG,
    ) -> RoutingDecision:
        """Make a routing decision for a node."""
        readiness = self.analyze_readiness(node_id, dag)

        if readiness.is_runnable:
            action = "execute"
            priority = 100 - int(readiness.score * 100)
            reason = "Node is ready for execution"
        elif readiness.score > 0.5:
            action = "queue"
            priority = 50 - int(readiness.score * 50)
            reason = f"Partially ready ({readiness.score:.0%}), queued"
        elif readiness.blocked_by_nodes:
            action = "wait"
            priority = 0
            reason = f"Waiting for: {', '.join(readiness.blocked_by_nodes)}"
        else:
            action = "skip"
            priority = -1
            reason = "Cannot execute - missing critical inputs"

        decision = RoutingDecision(
            decision_id=str(uuid4()),
            node_id=node_id,
            action=action,
            priority=priority,
            readiness_score=readiness.score,
            reason=reason,
        )

        self._decisions.append(decision)

        if PROMETHEUS_AVAILABLE and ROUTING_DECISIONS:
            ROUTING_DECISIONS.labels(decision_type=action).inc()

        logger.debug(f"Routing decision for {node_id}: {action} (score: {readiness.score:.2f})")
        return decision

    def get_next_batch(
        self,
        dag: DAG,
        max_parallel: int = 5,
    ) -> List[str]:
        """
        Get the next batch of nodes to execute in parallel.

        Uses interface-first scheduling to minimize blocked time.
        """
        runnable = self.get_runnable_nodes(dag)

        if not runnable:
            return []

        # Score and sort by priority
        scored = []
        for node_id in runnable:
            decision = self.make_routing_decision(node_id, dag)
            scored.append((node_id, decision.priority, decision.readiness_score))

        # Sort by priority (higher is better) then readiness score
        scored.sort(key=lambda x: (-x[1], -x[2]))

        # Return top N
        batch = [node_id for node_id, _, _ in scored[:max_parallel]]

        if PROMETHEUS_AVAILABLE and QUEUE_DEPTH:
            QUEUE_DEPTH.set(len(runnable) - len(batch))

        logger.info(f"Next batch of {len(batch)} nodes: {batch}")
        return batch

    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        decision_counts = {}
        for d in self._decisions:
            decision_counts[d.action] = decision_counts.get(d.action, 0) + 1

        return {
            "total_decisions": len(self._decisions),
            "decision_counts": decision_counts,
            "contracts_registered": len(self._contracts),
            "completed_nodes": len(self._completed_outputs),
            "blocked_time_total_seconds": self._blocked_time_total.total_seconds(),
        }

    def reset(self) -> None:
        """Reset routing state for a new workflow."""
        self._completed_outputs.clear()
        self._node_start_times.clear()
        self._blocked_time_total = timedelta()
        self._decisions.clear()
        logger.info("RoutingEngine reset")
