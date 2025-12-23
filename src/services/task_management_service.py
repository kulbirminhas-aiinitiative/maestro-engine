#!/usr/bin/env python3
"""
TaskManagementService - DDE to JIRA Task Integration

MD-2117: [Task T9] TaskManagementService class
MD-2118: [Task T10] EPIC generation from DDE workflows
MD-2119: [Task T11] Bidirectional status sync
MD-2120: [Task T12] Task closure workflow

Parent: MD-2106 (Sub-Story 3: Task Management Service)

Features:
- Create JIRA Epics from DDE WorkflowDAGs
- Create Tasks from ExecutionManifest nodes
- Bidirectional status synchronization
- Automatic task closure on completion
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

# Configuration
TASK_ADAPTER_URL = os.getenv("TASK_ADAPTER_URL", "http://localhost:14100/api")


class DDEStatus(Enum):
    """DDE execution status."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class JIRAStatus(Enum):
    """JIRA task status."""
    TO_DO = "To Do"
    IN_PROGRESS = "In Progress"
    DONE = "Done"
    BLOCKED = "Blocked"


# Status mapping: DDE -> JIRA
DDE_TO_JIRA_STATUS: Dict[DDEStatus, JIRAStatus] = {
    DDEStatus.PENDING: JIRAStatus.TO_DO,
    DDEStatus.QUEUED: JIRAStatus.TO_DO,
    DDEStatus.RUNNING: JIRAStatus.IN_PROGRESS,
    DDEStatus.COMPLETED: JIRAStatus.DONE,
    DDEStatus.FAILED: JIRAStatus.IN_PROGRESS,  # Keep in progress for retry
    DDEStatus.SKIPPED: JIRAStatus.DONE,
    DDEStatus.BLOCKED: JIRAStatus.BLOCKED,
}

# Status mapping: JIRA -> DDE
JIRA_TO_DDE_STATUS: Dict[str, DDEStatus] = {
    "To Do": DDEStatus.PENDING,
    "In Progress": DDEStatus.RUNNING,
    "Done": DDEStatus.COMPLETED,
    "Blocked": DDEStatus.BLOCKED,
}


@dataclass
class WorkflowNode:
    """Represents a node in a DDE workflow."""
    id: str
    name: str
    phase: str
    dependencies: List[str] = field(default_factory=list)
    status: DDEStatus = DDEStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowDAG:
    """Represents a DDE workflow DAG."""
    id: str
    name: str
    description: str
    project_key: str
    nodes: List[WorkflowNode]
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        """Get node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_root_nodes(self) -> List[WorkflowNode]:
        """Get nodes with no dependencies."""
        return [n for n in self.nodes if not n.dependencies]

    def get_dependents(self, node_id: str) -> List[WorkflowNode]:
        """Get nodes that depend on the given node."""
        return [n for n in self.nodes if node_id in n.dependencies]


@dataclass
class TaskMapping:
    """Maps DDE nodes to JIRA tasks."""
    workflow_id: str
    epic_key: Optional[str]
    node_task_map: Dict[str, str]  # node_id -> task_key
    task_node_map: Dict[str, str]  # task_key -> node_id
    created_at: datetime = field(default_factory=datetime.utcnow)

    def get_task_key(self, node_id: str) -> Optional[str]:
        return self.node_task_map.get(node_id)

    def get_node_id(self, task_key: str) -> Optional[str]:
        return self.task_node_map.get(task_key)


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    synced_count: int
    failed_count: int
    details: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "synced_count": self.synced_count,
            "failed_count": self.failed_count,
            "details": self.details,
            "error": self.error
        }


@dataclass
class EpicCreationResult:
    """Result of creating an Epic from workflow."""
    success: bool
    epic_key: Optional[str]
    epic_url: Optional[str]
    task_keys: List[str]
    mapping: Optional[TaskMapping]
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "epic_key": self.epic_key,
            "epic_url": self.epic_url,
            "task_keys": self.task_keys,
            "mapping": {
                "workflow_id": self.mapping.workflow_id,
                "node_task_map": self.mapping.node_task_map
            } if self.mapping else None,
            "error": self.error
        }


class TaskManagementService:
    """
    Service for managing DDE workflow tasks in JIRA.

    Integrates with:
    - JIRA via internal adapter API
    - DDE ExecutionManifest for node tracking
    - WorkflowDAG for dependency mapping

    Usage:
        service = TaskManagementService(auth_token="...")

        # Create Epic from workflow
        result = service.createEpicFromWorkflow(workflow_dag)

        # Sync status changes
        sync_result = service.syncTaskStatus(mapping, workflow_dag)

        # Close completed tasks
        service.closeCompletedTasks(mapping, workflow_dag)
    """

    def __init__(
        self,
        adapter_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        on_status_change: Optional[Callable[[str, DDEStatus, JIRAStatus], None]] = None
    ):
        self.adapter_url = adapter_url or TASK_ADAPTER_URL
        self.auth_token = auth_token
        self._on_status_change = on_status_change

        # Cache for task mappings
        self._mappings: Dict[str, TaskMapping] = {}

        logger.info(f"TaskManagementService initialized (adapter: {self.adapter_url})")

    def createEpicFromWorkflow(
        self,
        workflow: WorkflowDAG,
        auth_token: Optional[str] = None,
        parent_epic_key: Optional[str] = None,
        create_subtasks: bool = True
    ) -> EpicCreationResult:
        """
        Create a JIRA Epic from a DDE WorkflowDAG.

        Maps the workflow structure to JIRA:
        - WorkflowDAG -> Epic
        - WorkflowNodes -> Tasks (linked to Epic)
        - Node dependencies -> Task links

        Args:
            workflow: The DDE workflow DAG
            auth_token: Optional auth token
            parent_epic_key: Optional parent epic to link to
            create_subtasks: If True, create tasks for each node

        Returns:
            EpicCreationResult with epic key and task mappings
        """
        logger.info(f"Creating Epic from workflow: {workflow.name} ({len(workflow.nodes)} nodes)")

        token = auth_token or self.auth_token
        if not token:
            return EpicCreationResult(
                success=False,
                epic_key=None,
                epic_url=None,
                task_keys=[],
                mapping=None,
                error="No authentication token provided"
            )

        try:
            # Create the Epic
            epic_result = self._create_epic(workflow, token, parent_epic_key)
            if not epic_result.get("success"):
                return EpicCreationResult(
                    success=False,
                    epic_key=None,
                    epic_url=None,
                    task_keys=[],
                    mapping=None,
                    error=epic_result.get("error", "Failed to create Epic")
                )

            epic_key = epic_result["epic_key"]
            epic_url = epic_result.get("epic_url")

            # Create tasks for each node
            task_keys = []
            node_task_map = {}
            task_node_map = {}

            if create_subtasks:
                for node in workflow.nodes:
                    task_result = self._create_task_for_node(
                        node, workflow, epic_key, token
                    )

                    if task_result.get("success"):
                        task_key = task_result["task_key"]
                        task_keys.append(task_key)
                        node_task_map[node.id] = task_key
                        task_node_map[task_key] = node.id
                    else:
                        logger.warning(f"Failed to create task for node {node.id}: {task_result.get('error')}")

            # Create and cache the mapping
            mapping = TaskMapping(
                workflow_id=workflow.id,
                epic_key=epic_key,
                node_task_map=node_task_map,
                task_node_map=task_node_map
            )
            self._mappings[workflow.id] = mapping

            logger.info(f"Created Epic {epic_key} with {len(task_keys)} tasks")

            return EpicCreationResult(
                success=True,
                epic_key=epic_key,
                epic_url=epic_url,
                task_keys=task_keys,
                mapping=mapping
            )

        except Exception as e:
            logger.error(f"Failed to create Epic from workflow: {e}")
            return EpicCreationResult(
                success=False,
                epic_key=None,
                epic_url=None,
                task_keys=[],
                mapping=None,
                error=str(e)
            )

    def createTasksFromManifest(
        self,
        manifest_nodes: List[Dict[str, Any]],
        epic_key: str,
        workflow_id: str,
        auth_token: Optional[str] = None
    ) -> Tuple[List[str], TaskMapping]:
        """
        Create JIRA tasks from ExecutionManifest nodes.

        Args:
            manifest_nodes: List of node dictionaries from ExecutionManifest
            epic_key: Parent Epic key
            workflow_id: Workflow ID for mapping
            auth_token: Optional auth token

        Returns:
            Tuple of (task_keys, mapping)
        """
        logger.info(f"Creating tasks from manifest: {len(manifest_nodes)} nodes")

        token = auth_token or self.auth_token
        task_keys = []
        node_task_map = {}
        task_node_map = {}

        for node_data in manifest_nodes:
            node = WorkflowNode(
                id=node_data.get("node_id", str(uuid4())),
                name=node_data.get("name", "Unnamed Node"),
                phase=node_data.get("phase", "execution"),
                dependencies=node_data.get("dependencies", []),
                status=DDEStatus(node_data.get("status", "pending")),
                metadata=node_data.get("metadata", {})
            )

            # Create workflow stub for the node
            workflow_stub = WorkflowDAG(
                id=workflow_id,
                name="Manifest Import",
                description="Tasks created from ExecutionManifest",
                project_key=epic_key.split("-")[0],
                nodes=[node]
            )

            task_result = self._create_task_for_node(node, workflow_stub, epic_key, token)

            if task_result.get("success"):
                task_key = task_result["task_key"]
                task_keys.append(task_key)
                node_task_map[node.id] = task_key
                task_node_map[task_key] = node.id

        mapping = TaskMapping(
            workflow_id=workflow_id,
            epic_key=epic_key,
            node_task_map=node_task_map,
            task_node_map=task_node_map
        )
        self._mappings[workflow_id] = mapping

        return task_keys, mapping

    def syncTaskStatus(
        self,
        mapping: TaskMapping,
        workflow: WorkflowDAG,
        direction: str = "dde_to_jira",
        auth_token: Optional[str] = None
    ) -> SyncResult:
        """
        Synchronize status between DDE and JIRA.

        Args:
            mapping: Task mapping for the workflow
            workflow: Current workflow state
            direction: "dde_to_jira" or "jira_to_dde"
            auth_token: Optional auth token

        Returns:
            SyncResult with sync details
        """
        logger.info(f"Syncing task status ({direction}) for workflow {workflow.id}")

        token = auth_token or self.auth_token
        synced = 0
        failed = 0
        details = []

        if direction == "dde_to_jira":
            # Push DDE status to JIRA
            for node in workflow.nodes:
                task_key = mapping.get_task_key(node.id)
                if not task_key:
                    continue

                target_status = DDE_TO_JIRA_STATUS.get(node.status, JIRAStatus.TO_DO)

                result = self._transition_task(task_key, target_status.value, token)

                if result.get("success"):
                    synced += 1
                    details.append({
                        "node_id": node.id,
                        "task_key": task_key,
                        "status": target_status.value,
                        "success": True
                    })

                    if self._on_status_change:
                        self._on_status_change(node.id, node.status, target_status)
                else:
                    failed += 1
                    details.append({
                        "node_id": node.id,
                        "task_key": task_key,
                        "error": result.get("error"),
                        "success": False
                    })

        elif direction == "jira_to_dde":
            # Pull JIRA status to DDE
            for node in workflow.nodes:
                task_key = mapping.get_task_key(node.id)
                if not task_key:
                    continue

                task_status = self._get_task_status(task_key, token)
                if task_status:
                    dde_status = JIRA_TO_DDE_STATUS.get(task_status, DDEStatus.PENDING)
                    old_status = node.status
                    node.status = dde_status
                    synced += 1
                    details.append({
                        "node_id": node.id,
                        "task_key": task_key,
                        "old_status": old_status.value,
                        "new_status": dde_status.value,
                        "success": True
                    })
                else:
                    failed += 1
                    details.append({
                        "node_id": node.id,
                        "task_key": task_key,
                        "error": "Could not get task status",
                        "success": False
                    })

        return SyncResult(
            success=failed == 0,
            synced_count=synced,
            failed_count=failed,
            details=details
        )

    def closeCompletedTasks(
        self,
        mapping: TaskMapping,
        workflow: WorkflowDAG,
        auth_token: Optional[str] = None,
        add_completion_comment: bool = True
    ) -> SyncResult:
        """
        Close tasks for completed workflow nodes.

        Args:
            mapping: Task mapping for the workflow
            workflow: Current workflow state
            auth_token: Optional auth token
            add_completion_comment: If True, add completion summary

        Returns:
            SyncResult with closure details
        """
        logger.info(f"Closing completed tasks for workflow {workflow.id}")

        token = auth_token or self.auth_token
        closed = 0
        failed = 0
        details = []

        for node in workflow.nodes:
            if node.status != DDEStatus.COMPLETED:
                continue

            task_key = mapping.get_task_key(node.id)
            if not task_key:
                continue

            # Check current status
            current_status = self._get_task_status(task_key, token)
            if current_status == "Done":
                # Already closed
                continue

            # Add completion comment
            if add_completion_comment:
                comment = f"Node '{node.name}' completed successfully in phase: {node.phase}"
                self._add_comment(task_key, comment, token)

            # Transition to Done
            result = self._transition_task(task_key, "Done", token)

            if result.get("success"):
                closed += 1
                details.append({
                    "node_id": node.id,
                    "task_key": task_key,
                    "action": "closed",
                    "success": True
                })
            else:
                failed += 1
                details.append({
                    "node_id": node.id,
                    "task_key": task_key,
                    "error": result.get("error"),
                    "success": False
                })

        # Check if Epic should be closed
        if mapping.epic_key:
            all_done = all(
                node.status in (DDEStatus.COMPLETED, DDEStatus.SKIPPED)
                for node in workflow.nodes
            )

            if all_done:
                epic_result = self._close_epic(mapping.epic_key, workflow, token)
                if epic_result.get("success"):
                    details.append({
                        "epic_key": mapping.epic_key,
                        "action": "epic_closed",
                        "success": True
                    })
                    closed += 1

        return SyncResult(
            success=failed == 0,
            synced_count=closed,
            failed_count=failed,
            details=details
        )

    def getMapping(self, workflow_id: str) -> Optional[TaskMapping]:
        """Get cached task mapping for a workflow."""
        return self._mappings.get(workflow_id)

    def setAuthToken(self, token: str) -> None:
        """Set the authentication token."""
        self.auth_token = token

    # Private methods

    def _create_epic(
        self,
        workflow: WorkflowDAG,
        token: str,
        parent_epic_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create JIRA Epic from workflow."""
        payload = {
            "summary": f"[DDE] {workflow.name}",
            "description": self._build_epic_description(workflow),
            "projectKey": workflow.project_key,
            "issueType": "Epic"
        }

        if parent_epic_key:
            payload["parentKey"] = parent_epic_key

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.adapter_url}/integrations/tasks",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code in [200, 201]:
                    data = response.json()
                    output = data.get("output", data)
                    return {
                        "success": True,
                        "epic_key": output.get("externalId") or output.get("key"),
                        "epic_url": output.get("deepLink") or output.get("url")
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API error {response.status_code}: {response.text[:200]}"
                    }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _create_task_for_node(
        self,
        node: WorkflowNode,
        workflow: WorkflowDAG,
        epic_key: str,
        token: str
    ) -> Dict[str, Any]:
        """Create JIRA Task for a workflow node."""
        # Build task description
        description = f"Phase: {node.phase}\n\n"
        if node.dependencies:
            description += f"Dependencies: {', '.join(node.dependencies)}\n\n"
        if node.metadata:
            description += f"Metadata: {json.dumps(node.metadata, indent=2)}\n\n"
        description += f"Workflow: {workflow.name} ({workflow.id})"

        payload = {
            "summary": f"[{node.phase.upper()}] {node.name}",
            "description": description,
            "projectKey": workflow.project_key,
            "issueType": "Task",
            "parentKey": epic_key
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.adapter_url}/integrations/tasks",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code in [200, 201]:
                    data = response.json()
                    output = data.get("output", data)
                    return {
                        "success": True,
                        "task_key": output.get("externalId") or output.get("key")
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API error {response.status_code}: {response.text[:200]}"
                    }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _transition_task(
        self,
        task_key: str,
        target_status: str,
        token: str
    ) -> Dict[str, Any]:
        """Transition a JIRA task to a new status."""
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.adapter_url}/integrations/tasks/{task_key}/transition",
                    json={"targetStatus": target_status},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code in [200, 201]:
                    return {"success": True}
                else:
                    return {
                        "success": False,
                        "error": f"Transition failed: {response.text[:200]}"
                    }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_task_status(self, task_key: str, token: str) -> Optional[str]:
        """Get current status of a JIRA task."""
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{self.adapter_url}/integrations/tasks/{task_key}",
                    headers={"Authorization": f"Bearer {token}"}
                )

                if response.status_code == 200:
                    data = response.json()
                    output = data.get("output", data)
                    status = output.get("status", {})
                    return status.get("name") if isinstance(status, dict) else status

        except Exception as e:
            logger.error(f"Failed to get task status for {task_key}: {e}")

        return None

    def _add_comment(self, task_key: str, body: str, token: str) -> bool:
        """Add a comment to a JIRA task."""
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.adapter_url}/integrations/tasks/{task_key}/comments",
                    json={"body": body},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                )
                return response.status_code in [200, 201]

        except Exception as e:
            logger.error(f"Failed to add comment to {task_key}: {e}")
            return False

    def _close_epic(
        self,
        epic_key: str,
        workflow: WorkflowDAG,
        token: str
    ) -> Dict[str, Any]:
        """Close an Epic when all tasks are complete."""
        # Add completion summary
        summary = f"Workflow '{workflow.name}' completed.\n\n"
        summary += f"Total nodes: {len(workflow.nodes)}\n"
        completed = sum(1 for n in workflow.nodes if n.status == DDEStatus.COMPLETED)
        skipped = sum(1 for n in workflow.nodes if n.status == DDEStatus.SKIPPED)
        summary += f"Completed: {completed}, Skipped: {skipped}"

        self._add_comment(epic_key, summary, token)

        # Transition to Done
        return self._transition_task(epic_key, "Done", token)

    def _build_epic_description(self, workflow: WorkflowDAG) -> str:
        """Build Epic description from workflow."""
        desc = f"{workflow.description}\n\n"
        desc += f"**Workflow ID**: {workflow.id}\n"
        desc += f"**Created**: {workflow.created_at.isoformat()}\n\n"
        desc += "## Nodes\n"

        for node in workflow.nodes:
            deps = f" (depends on: {', '.join(node.dependencies)})" if node.dependencies else ""
            desc += f"- [{node.phase}] {node.name}{deps}\n"

        return desc


class StatusSyncHandler:
    """
    Handler for bidirectional status sync with webhooks.

    Can be used with JIRA webhooks to automatically update
    DDE status when JIRA tasks change.

    Usage:
        handler = StatusSyncHandler(task_service, workflow_store)

        # Called by webhook endpoint
        handler.handle_jira_webhook(webhook_payload)
    """

    def __init__(
        self,
        task_service: TaskManagementService,
        workflow_store: Optional[Dict[str, WorkflowDAG]] = None
    ):
        self.task_service = task_service
        self.workflow_store = workflow_store or {}

    def handle_jira_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle JIRA webhook for status changes.

        Args:
            payload: JIRA webhook payload

        Returns:
            Processing result
        """
        event_type = payload.get("webhookEvent", "")

        if "issue_updated" not in event_type:
            return {"processed": False, "reason": "Not a status change event"}

        issue = payload.get("issue", {})
        issue_key = issue.get("key")
        changelog = payload.get("changelog", {})

        # Find status change in changelog
        status_change = None
        for item in changelog.get("items", []):
            if item.get("field") == "status":
                status_change = {
                    "from": item.get("fromString"),
                    "to": item.get("toString")
                }
                break

        if not status_change:
            return {"processed": False, "reason": "No status change in event"}

        # Find mapping for this task
        for workflow_id, mapping in self.task_service._mappings.items():
            node_id = mapping.get_node_id(issue_key)
            if node_id:
                workflow = self.workflow_store.get(workflow_id)
                if workflow:
                    node = workflow.get_node(node_id)
                    if node:
                        new_status = JIRA_TO_DDE_STATUS.get(
                            status_change["to"],
                            DDEStatus.PENDING
                        )
                        old_status = node.status
                        node.status = new_status

                        logger.info(
                            f"Updated node {node_id} status: {old_status.value} -> {new_status.value}"
                        )

                        return {
                            "processed": True,
                            "node_id": node_id,
                            "workflow_id": workflow_id,
                            "old_status": old_status.value,
                            "new_status": new_status.value
                        }

        return {"processed": False, "reason": "No mapping found for task"}

    def register_workflow(self, workflow: WorkflowDAG) -> None:
        """Register a workflow for webhook handling."""
        self.workflow_store[workflow.id] = workflow


# Global service instance
_task_management_service: Optional[TaskManagementService] = None


def get_task_management_service() -> TaskManagementService:
    """Get singleton TaskManagementService instance."""
    global _task_management_service
    if _task_management_service is None:
        _task_management_service = TaskManagementService()
    return _task_management_service
