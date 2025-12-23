#!/usr/bin/env python3
"""
ExecutionManifest - DAG Node Iteration Tracking

Tracks all DAG node executions with iteration metadata for resumable workflows.

MD-2090: [DDE-1] Complete ExecutionManifest with full iteration tracking

Features:
- NodeExecution dataclass with full iteration tracking
- Persist/restore capability for workflow resumption
- Query API for execution history
- Performance target: <10ms overhead per node recording
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

logger = logging.getLogger(__name__)

# Optional Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, Gauge
    PROMETHEUS_AVAILABLE = True

    MANIFEST_OPERATIONS = Counter(
        "dde_manifest_operations_total",
        "Total manifest operations",
        ["operation", "status"]
    )
    MANIFEST_LATENCY = Histogram(
        "dde_manifest_operation_duration_seconds",
        "Manifest operation duration",
        ["operation"],
        buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1]
    )
    ACTIVE_EXECUTIONS = Gauge(
        "dde_active_executions",
        "Number of currently active node executions"
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    MANIFEST_OPERATIONS = None
    MANIFEST_LATENCY = None
    ACTIVE_EXECUTIONS = None


class ExecutionStatus(Enum):
    """Status of a node execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class ErrorInfo:
    """Detailed error information for failed executions."""
    error_type: str
    message: str
    stack_trace: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    recoverable: bool = False
    retry_suggested: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "stack_trace": self.stack_trace,
            "timestamp": self.timestamp.isoformat(),
            "recoverable": self.recoverable,
            "retry_suggested": self.retry_suggested,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErrorInfo":
        return cls(
            error_type=data["error_type"],
            message=data["message"],
            stack_trace=data.get("stack_trace"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            recoverable=data.get("recoverable", False),
            retry_suggested=data.get("retry_suggested", False),
        )

    @classmethod
    def from_exception(cls, exc: Exception, recoverable: bool = False) -> "ErrorInfo":
        import traceback
        return cls(
            error_type=type(exc).__name__,
            message=str(exc),
            stack_trace=traceback.format_exc(),
            recoverable=recoverable,
            retry_suggested=recoverable,
        )


@dataclass
class NodeExecution:
    """
    Represents a single execution of a DAG node.

    Tracks iteration count, timing, inputs/outputs, and dependency chain.
    """
    execution_id: str
    node_id: str
    iteration: int
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    parent_executions: List[str] = field(default_factory=list)
    retry_count: int = 0
    error_info: Optional[ErrorInfo] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None

    def __post_init__(self):
        if self.completed_at and not self.duration_ms:
            delta = self.completed_at - self.started_at
            self.duration_ms = delta.total_seconds() * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "node_id": self.node_id,
            "iteration": self.iteration,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "parent_executions": self.parent_executions,
            "retry_count": self.retry_count,
            "error_info": self.error_info.to_dict() if self.error_info else None,
            "metadata": self.metadata,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeExecution":
        return cls(
            execution_id=data["execution_id"],
            node_id=data["node_id"],
            iteration=data["iteration"],
            status=ExecutionStatus(data["status"]),
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", {}),
            parent_executions=data.get("parent_executions", []),
            retry_count=data.get("retry_count", 0),
            error_info=ErrorInfo.from_dict(data["error_info"]) if data.get("error_info") else None,
            metadata=data.get("metadata", {}),
            duration_ms=data.get("duration_ms"),
        )


class ExecutionManifest:
    """
    Tracks all DAG node executions for a workflow.

    Provides:
    - Recording of node starts, completions, and failures
    - Iteration tracking per node
    - Dependency chain tracking
    - Persist/restore for workflow resumption
    - Query API for execution history
    """

    def __init__(
        self,
        workflow_id: str,
        workflow_name: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        self.workflow_id = workflow_id
        self.workflow_name = workflow_name or workflow_id
        self.session_id = session_id or str(uuid4())
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        # Execution tracking
        self._executions: Dict[str, NodeExecution] = {}
        self._node_iterations: Dict[str, int] = {}
        self._active_executions: Set[str] = set()
        self._execution_order: List[str] = []

        # Metrics
        self._total_nodes = 0
        self._completed_nodes = 0
        self._failed_nodes = 0

        logger.info(f"ExecutionManifest created for workflow {workflow_id}")

    def record_start(
        self,
        node_id: str,
        inputs: Optional[Dict[str, Any]] = None,
        parent_executions: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record the start of a node execution.

        Returns the execution_id for tracking.
        Performance target: <10ms
        """
        start_time = time.perf_counter()

        try:
            # Increment iteration count
            iteration = self._node_iterations.get(node_id, 0) + 1
            self._node_iterations[node_id] = iteration

            # Generate execution ID
            execution_id = f"{node_id}:{iteration}:{uuid4().hex[:8]}"

            # Create execution record
            execution = NodeExecution(
                execution_id=execution_id,
                node_id=node_id,
                iteration=iteration,
                status=ExecutionStatus.RUNNING,
                started_at=datetime.utcnow(),
                inputs=inputs or {},
                parent_executions=parent_executions or [],
                metadata=metadata or {},
            )

            self._executions[execution_id] = execution
            self._active_executions.add(execution_id)
            self._execution_order.append(execution_id)
            self._total_nodes += 1
            self.updated_at = datetime.utcnow()

            if PROMETHEUS_AVAILABLE and ACTIVE_EXECUTIONS:
                ACTIVE_EXECUTIONS.inc()

            logger.debug(f"Started execution {execution_id} for node {node_id} (iteration {iteration})")

            return execution_id

        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if PROMETHEUS_AVAILABLE and MANIFEST_LATENCY:
                MANIFEST_LATENCY.labels(operation="record_start").observe(elapsed_ms / 1000)
            if PROMETHEUS_AVAILABLE and MANIFEST_OPERATIONS:
                MANIFEST_OPERATIONS.labels(operation="record_start", status="success").inc()

            if elapsed_ms > 10:
                logger.warning(f"record_start took {elapsed_ms:.2f}ms (target: <10ms)")

    def record_completion(
        self,
        execution_id: str,
        outputs: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record successful completion of a node execution."""
        start_time = time.perf_counter()

        try:
            if execution_id not in self._executions:
                raise ValueError(f"Unknown execution_id: {execution_id}")

            execution = self._executions[execution_id]
            execution.completed_at = datetime.utcnow()
            execution.status = ExecutionStatus.COMPLETED
            execution.outputs = outputs or {}
            if metadata:
                execution.metadata.update(metadata)

            # Calculate duration
            delta = execution.completed_at - execution.started_at
            execution.duration_ms = delta.total_seconds() * 1000

            self._active_executions.discard(execution_id)
            self._completed_nodes += 1
            self.updated_at = datetime.utcnow()

            if PROMETHEUS_AVAILABLE and ACTIVE_EXECUTIONS:
                ACTIVE_EXECUTIONS.dec()

            logger.debug(f"Completed execution {execution_id} in {execution.duration_ms:.2f}ms")

        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if PROMETHEUS_AVAILABLE and MANIFEST_LATENCY:
                MANIFEST_LATENCY.labels(operation="record_completion").observe(elapsed_ms / 1000)
            if PROMETHEUS_AVAILABLE and MANIFEST_OPERATIONS:
                MANIFEST_OPERATIONS.labels(operation="record_completion", status="success").inc()

    def record_failure(
        self,
        execution_id: str,
        error: Exception,
        recoverable: bool = False,
    ) -> None:
        """Record failure of a node execution."""
        start_time = time.perf_counter()

        try:
            if execution_id not in self._executions:
                raise ValueError(f"Unknown execution_id: {execution_id}")

            execution = self._executions[execution_id]
            execution.completed_at = datetime.utcnow()
            execution.status = ExecutionStatus.FAILED
            execution.error_info = ErrorInfo.from_exception(error, recoverable)

            # Calculate duration
            delta = execution.completed_at - execution.started_at
            execution.duration_ms = delta.total_seconds() * 1000

            self._active_executions.discard(execution_id)
            self._failed_nodes += 1
            self.updated_at = datetime.utcnow()

            if PROMETHEUS_AVAILABLE and ACTIVE_EXECUTIONS:
                ACTIVE_EXECUTIONS.dec()

            logger.warning(f"Failed execution {execution_id}: {error}")

        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if PROMETHEUS_AVAILABLE and MANIFEST_LATENCY:
                MANIFEST_LATENCY.labels(operation="record_failure").observe(elapsed_ms / 1000)
            if PROMETHEUS_AVAILABLE and MANIFEST_OPERATIONS:
                MANIFEST_OPERATIONS.labels(operation="record_failure", status="success").inc()

    def record_skip(
        self,
        node_id: str,
        reason: str,
        parent_executions: Optional[List[str]] = None,
    ) -> str:
        """Record that a node was skipped."""
        execution_id = self.record_start(
            node_id=node_id,
            parent_executions=parent_executions,
            metadata={"skip_reason": reason},
        )

        execution = self._executions[execution_id]
        execution.completed_at = datetime.utcnow()
        execution.status = ExecutionStatus.SKIPPED
        execution.duration_ms = 0

        self._active_executions.discard(execution_id)
        self.updated_at = datetime.utcnow()

        if PROMETHEUS_AVAILABLE and ACTIVE_EXECUTIONS:
            ACTIVE_EXECUTIONS.dec()

        logger.debug(f"Skipped node {node_id}: {reason}")
        return execution_id

    def record_retry(self, execution_id: str) -> str:
        """
        Record a retry attempt for a failed execution.

        Returns a new execution_id for the retry.
        """
        if execution_id not in self._executions:
            raise ValueError(f"Unknown execution_id: {execution_id}")

        original = self._executions[execution_id]
        if original.status != ExecutionStatus.FAILED:
            raise ValueError(f"Can only retry failed executions, got {original.status}")

        # Start new execution with incremented retry count
        new_execution_id = self.record_start(
            node_id=original.node_id,
            inputs=original.inputs,
            parent_executions=original.parent_executions,
            metadata={
                **original.metadata,
                "retry_of": execution_id,
                "retry_count": original.retry_count + 1,
            },
        )

        # Update retry count
        self._executions[new_execution_id].retry_count = original.retry_count + 1

        logger.info(f"Retrying execution {execution_id} as {new_execution_id} (attempt {original.retry_count + 1})")
        return new_execution_id

    def get_execution(self, execution_id: str) -> Optional[NodeExecution]:
        """Get a specific execution by ID."""
        return self._executions.get(execution_id)

    def get_node_history(self, node_id: str) -> List[NodeExecution]:
        """Get all executions for a specific node."""
        return [
            e for e in self._executions.values()
            if e.node_id == node_id
        ]

    def get_latest_execution(self, node_id: str) -> Optional[NodeExecution]:
        """Get the most recent execution for a node."""
        history = self.get_node_history(node_id)
        if not history:
            return None
        return max(history, key=lambda e: e.iteration)

    def get_active_executions(self) -> List[NodeExecution]:
        """Get all currently running executions."""
        return [
            self._executions[eid]
            for eid in self._active_executions
        ]

    def get_failed_executions(self) -> List[NodeExecution]:
        """Get all failed executions."""
        return [
            e for e in self._executions.values()
            if e.status == ExecutionStatus.FAILED
        ]

    def get_execution_graph(self) -> Dict[str, Any]:
        """
        Get serializable representation of the execution DAG.

        Useful for visualization and debugging.
        """
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "stats": {
                "total_nodes": self._total_nodes,
                "completed_nodes": self._completed_nodes,
                "failed_nodes": self._failed_nodes,
                "active_nodes": len(self._active_executions),
                "unique_nodes": len(self._node_iterations),
            },
            "node_iterations": dict(self._node_iterations),
            "executions": [e.to_dict() for e in self._executions.values()],
            "execution_order": self._execution_order,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        total_duration = sum(
            e.duration_ms or 0
            for e in self._executions.values()
            if e.duration_ms
        )

        return {
            "workflow_id": self.workflow_id,
            "total_executions": self._total_nodes,
            "completed": self._completed_nodes,
            "failed": self._failed_nodes,
            "active": len(self._active_executions),
            "skipped": sum(1 for e in self._executions.values() if e.status == ExecutionStatus.SKIPPED),
            "unique_nodes": len(self._node_iterations),
            "total_duration_ms": total_duration,
            "avg_duration_ms": total_duration / self._completed_nodes if self._completed_nodes > 0 else 0,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manifest to dictionary for persistence."""
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "node_iterations": dict(self._node_iterations),
            "executions": {eid: e.to_dict() for eid, e in self._executions.items()},
            "active_executions": list(self._active_executions),
            "execution_order": self._execution_order,
            "metrics": {
                "total_nodes": self._total_nodes,
                "completed_nodes": self._completed_nodes,
                "failed_nodes": self._failed_nodes,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionManifest":
        """Restore manifest from dictionary."""
        manifest = cls(
            workflow_id=data["workflow_id"],
            workflow_name=data.get("workflow_name"),
            session_id=data.get("session_id"),
        )

        manifest.created_at = datetime.fromisoformat(data["created_at"])
        manifest.updated_at = datetime.fromisoformat(data["updated_at"])
        manifest._node_iterations = data.get("node_iterations", {})
        manifest._executions = {
            eid: NodeExecution.from_dict(edata)
            for eid, edata in data.get("executions", {}).items()
        }
        manifest._active_executions = set(data.get("active_executions", []))
        manifest._execution_order = data.get("execution_order", [])

        metrics = data.get("metrics", {})
        manifest._total_nodes = metrics.get("total_nodes", 0)
        manifest._completed_nodes = metrics.get("completed_nodes", 0)
        manifest._failed_nodes = metrics.get("failed_nodes", 0)

        return manifest

    def persist(self, storage_path: Optional[str] = None) -> str:
        """
        Persist manifest to storage.

        Returns the storage path/key.
        """
        if storage_path is None:
            storage_path = f"/tmp/manifest_{self.workflow_id}_{self.session_id}.json"

        data = self.to_dict()
        with open(storage_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Manifest persisted to {storage_path}")
        return storage_path

    @classmethod
    def restore(cls, storage_path: str) -> "ExecutionManifest":
        """Restore manifest from storage."""
        with open(storage_path, "r") as f:
            data = json.load(f)

        manifest = cls.from_dict(data)
        logger.info(f"Manifest restored from {storage_path}")
        return manifest

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of manifest state for integrity checking."""
        data = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def is_resumable(self) -> bool:
        """Check if workflow can be resumed from current state."""
        # Can resume if there are no active executions and some nodes haven't completed
        return (
            len(self._active_executions) == 0 and
            self._failed_nodes > 0
        )

    def get_resumable_nodes(self) -> List[str]:
        """Get list of nodes that can be retried."""
        failed = self.get_failed_executions()
        return list(set(
            e.node_id for e in failed
            if e.error_info and e.error_info.recoverable
        ))
