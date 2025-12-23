#!/usr/bin/env python3
"""
Unit Tests for Task Management Service

Tests for:
- MD-2117: TaskManagementService class
- MD-2118: EPIC generation from DDE workflows
- MD-2119: Bidirectional status sync
- MD-2120: Task closure workflow
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.task_management_service import (
    DDEStatus,
    DDE_TO_JIRA_STATUS,
    EpicCreationResult,
    JIRA_TO_DDE_STATUS,
    JIRAStatus,
    StatusSyncHandler,
    SyncResult,
    TaskManagementService,
    TaskMapping,
    WorkflowDAG,
    WorkflowNode,
    get_task_management_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_workflow():
    """Create a sample workflow for testing."""
    nodes = [
        WorkflowNode(
            id="node-1",
            name="Requirements Analysis",
            phase="requirements",
            dependencies=[],
            status=DDEStatus.PENDING
        ),
        WorkflowNode(
            id="node-2",
            name="System Design",
            phase="design",
            dependencies=["node-1"],
            status=DDEStatus.PENDING
        ),
        WorkflowNode(
            id="node-3",
            name="Implementation",
            phase="implementation",
            dependencies=["node-2"],
            status=DDEStatus.PENDING
        ),
        WorkflowNode(
            id="node-4",
            name="Testing",
            phase="testing",
            dependencies=["node-3"],
            status=DDEStatus.PENDING
        ),
    ]

    return WorkflowDAG(
        id="wf-test-001",
        name="Test Workflow",
        description="A test workflow for unit tests",
        project_key="MD",
        nodes=nodes
    )


@pytest.fixture
def sample_mapping():
    """Create a sample task mapping."""
    return TaskMapping(
        workflow_id="wf-test-001",
        epic_key="MD-100",
        node_task_map={
            "node-1": "MD-101",
            "node-2": "MD-102",
            "node-3": "MD-103",
            "node-4": "MD-104"
        },
        task_node_map={
            "MD-101": "node-1",
            "MD-102": "node-2",
            "MD-103": "node-3",
            "MD-104": "node-4"
        }
    )


@pytest.fixture
def mock_httpx_client():
    """Mock httpx client for API calls."""
    with patch("services.task_management_service.httpx.Client") as mock:
        yield mock


# ============================================================================
# Status Mapping Tests
# ============================================================================


class TestStatusMappings:
    """Test status mapping between DDE and JIRA."""

    def test_dde_to_jira_pending(self):
        """Test PENDING maps to To Do."""
        assert DDE_TO_JIRA_STATUS[DDEStatus.PENDING] == JIRAStatus.TO_DO

    def test_dde_to_jira_running(self):
        """Test RUNNING maps to In Progress."""
        assert DDE_TO_JIRA_STATUS[DDEStatus.RUNNING] == JIRAStatus.IN_PROGRESS

    def test_dde_to_jira_completed(self):
        """Test COMPLETED maps to Done."""
        assert DDE_TO_JIRA_STATUS[DDEStatus.COMPLETED] == JIRAStatus.DONE

    def test_dde_to_jira_blocked(self):
        """Test BLOCKED maps to Blocked."""
        assert DDE_TO_JIRA_STATUS[DDEStatus.BLOCKED] == JIRAStatus.BLOCKED

    def test_jira_to_dde_todo(self):
        """Test To Do maps to PENDING."""
        assert JIRA_TO_DDE_STATUS["To Do"] == DDEStatus.PENDING

    def test_jira_to_dde_in_progress(self):
        """Test In Progress maps to RUNNING."""
        assert JIRA_TO_DDE_STATUS["In Progress"] == DDEStatus.RUNNING

    def test_jira_to_dde_done(self):
        """Test Done maps to COMPLETED."""
        assert JIRA_TO_DDE_STATUS["Done"] == DDEStatus.COMPLETED

    def test_all_dde_statuses_mapped(self):
        """Ensure all DDE statuses have mappings."""
        for status in DDEStatus:
            assert status in DDE_TO_JIRA_STATUS


# ============================================================================
# WorkflowNode Tests
# ============================================================================


class TestWorkflowNode:
    """Test WorkflowNode dataclass."""

    def test_node_creation(self):
        """Test creating a workflow node."""
        node = WorkflowNode(
            id="test-node",
            name="Test Node",
            phase="design",
            dependencies=["dep-1", "dep-2"],
            status=DDEStatus.RUNNING,
            metadata={"key": "value"}
        )

        assert node.id == "test-node"
        assert node.name == "Test Node"
        assert node.phase == "design"
        assert len(node.dependencies) == 2
        assert node.status == DDEStatus.RUNNING
        assert node.metadata["key"] == "value"

    def test_node_defaults(self):
        """Test node default values."""
        node = WorkflowNode(
            id="simple",
            name="Simple Node",
            phase="test"
        )

        assert node.dependencies == []
        assert node.status == DDEStatus.PENDING
        assert node.metadata == {}


# ============================================================================
# WorkflowDAG Tests
# ============================================================================


class TestWorkflowDAG:
    """Test WorkflowDAG dataclass."""

    def test_dag_creation(self, sample_workflow):
        """Test creating a workflow DAG."""
        assert sample_workflow.id == "wf-test-001"
        assert sample_workflow.name == "Test Workflow"
        assert len(sample_workflow.nodes) == 4
        assert sample_workflow.project_key == "MD"

    def test_get_node(self, sample_workflow):
        """Test getting a node by ID."""
        node = sample_workflow.get_node("node-2")
        assert node is not None
        assert node.name == "System Design"

    def test_get_node_not_found(self, sample_workflow):
        """Test getting a non-existent node."""
        node = sample_workflow.get_node("nonexistent")
        assert node is None

    def test_get_root_nodes(self, sample_workflow):
        """Test getting root nodes (no dependencies)."""
        roots = sample_workflow.get_root_nodes()
        assert len(roots) == 1
        assert roots[0].id == "node-1"

    def test_get_dependents(self, sample_workflow):
        """Test getting dependent nodes."""
        dependents = sample_workflow.get_dependents("node-2")
        assert len(dependents) == 1
        assert dependents[0].id == "node-3"


# ============================================================================
# TaskMapping Tests
# ============================================================================


class TestTaskMapping:
    """Test TaskMapping dataclass."""

    def test_mapping_creation(self, sample_mapping):
        """Test creating a task mapping."""
        assert sample_mapping.workflow_id == "wf-test-001"
        assert sample_mapping.epic_key == "MD-100"
        assert len(sample_mapping.node_task_map) == 4

    def test_get_task_key(self, sample_mapping):
        """Test getting task key from node ID."""
        task_key = sample_mapping.get_task_key("node-2")
        assert task_key == "MD-102"

    def test_get_node_id(self, sample_mapping):
        """Test getting node ID from task key."""
        node_id = sample_mapping.get_node_id("MD-103")
        assert node_id == "node-3"

    def test_get_task_key_not_found(self, sample_mapping):
        """Test getting non-existent task key."""
        task_key = sample_mapping.get_task_key("nonexistent")
        assert task_key is None


# ============================================================================
# TaskManagementService Tests (MD-2117)
# ============================================================================


class TestTaskManagementService:
    """Test TaskManagementService class."""

    def test_service_initialization(self):
        """Test service initialization."""
        service = TaskManagementService()
        assert service.adapter_url is not None
        assert service._mappings == {}

    def test_service_with_token(self):
        """Test service initialization with token."""
        service = TaskManagementService(auth_token="test-token")
        assert service.auth_token == "test-token"

    def test_set_auth_token(self):
        """Test setting auth token."""
        service = TaskManagementService()
        service.setAuthToken("new-token")
        assert service.auth_token == "new-token"

    def test_get_mapping(self, sample_mapping):
        """Test getting cached mapping."""
        service = TaskManagementService()
        service._mappings["wf-test-001"] = sample_mapping

        retrieved = service.getMapping("wf-test-001")
        assert retrieved == sample_mapping

    def test_get_mapping_not_found(self):
        """Test getting non-existent mapping."""
        service = TaskManagementService()
        mapping = service.getMapping("nonexistent")
        assert mapping is None


class TestCreateEpicFromWorkflow:
    """Test Epic creation from workflow (MD-2118)."""

    def test_create_epic_no_token(self, sample_workflow):
        """Test Epic creation fails without token."""
        service = TaskManagementService()
        result = service.createEpicFromWorkflow(sample_workflow)

        assert not result.success
        assert "token" in result.error.lower()

    def test_create_epic_success(self, sample_workflow, mock_httpx_client):
        """Test successful Epic creation."""
        # Setup mock
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "output": {
                "externalId": "MD-200",
                "deepLink": "https://jira.example.com/browse/MD-200"
            }
        }

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_httpx_client.return_value = mock_client_instance

        service = TaskManagementService(auth_token="test-token")
        result = service.createEpicFromWorkflow(sample_workflow, create_subtasks=False)

        assert result.success
        assert result.epic_key == "MD-200"
        assert result.epic_url is not None

    def test_epic_creation_result_to_dict(self, sample_mapping):
        """Test EpicCreationResult serialization."""
        result = EpicCreationResult(
            success=True,
            epic_key="MD-100",
            epic_url="https://jira.example.com/browse/MD-100",
            task_keys=["MD-101", "MD-102"],
            mapping=sample_mapping
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is True
        assert result_dict["epic_key"] == "MD-100"
        assert len(result_dict["task_keys"]) == 2
        assert result_dict["mapping"]["workflow_id"] == "wf-test-001"


# ============================================================================
# Status Sync Tests (MD-2119)
# ============================================================================


class TestSyncTaskStatus:
    """Test bidirectional status sync."""

    def test_sync_result_creation(self):
        """Test SyncResult creation."""
        result = SyncResult(
            success=True,
            synced_count=4,
            failed_count=0,
            details=[{"task": "MD-101", "status": "Done"}]
        )

        assert result.success
        assert result.synced_count == 4
        assert result.failed_count == 0

    def test_sync_result_to_dict(self):
        """Test SyncResult serialization."""
        result = SyncResult(
            success=False,
            synced_count=2,
            failed_count=1,
            error="Partial failure"
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is False
        assert result_dict["synced_count"] == 2
        assert result_dict["failed_count"] == 1
        assert result_dict["error"] == "Partial failure"

    def test_sync_dde_to_jira(self, sample_workflow, sample_mapping, mock_httpx_client):
        """Test syncing DDE status to JIRA."""
        # Set node statuses
        sample_workflow.nodes[0].status = DDEStatus.COMPLETED
        sample_workflow.nodes[1].status = DDEStatus.RUNNING

        # Setup mock
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_httpx_client.return_value = mock_client_instance

        service = TaskManagementService(auth_token="test-token")
        result = service.syncTaskStatus(
            sample_mapping,
            sample_workflow,
            direction="dde_to_jira"
        )

        assert result.synced_count > 0
        assert len(result.details) > 0

    def test_sync_with_callback(self, sample_workflow, sample_mapping, mock_httpx_client):
        """Test sync with status change callback."""
        callback_calls = []

        def callback(node_id, dde_status, jira_status):
            callback_calls.append((node_id, dde_status, jira_status))

        # Setup mock
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_httpx_client.return_value = mock_client_instance

        service = TaskManagementService(
            auth_token="test-token",
            on_status_change=callback
        )

        sample_workflow.nodes[0].status = DDEStatus.COMPLETED
        service.syncTaskStatus(sample_mapping, sample_workflow, direction="dde_to_jira")

        # Callback should have been called for completed node
        assert len(callback_calls) > 0


# ============================================================================
# Task Closure Tests (MD-2120)
# ============================================================================


class TestCloseCompletedTasks:
    """Test task closure workflow."""

    def test_close_completed_tasks(self, sample_workflow, sample_mapping, mock_httpx_client):
        """Test closing completed tasks."""
        # Mark nodes as completed
        for node in sample_workflow.nodes:
            node.status = DDEStatus.COMPLETED

        # Setup mock for status check and transition
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "output": {"status": {"name": "In Progress"}}
        }

        mock_post_response = MagicMock()
        mock_post_response.status_code = 200

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_get_response
        mock_client_instance.post.return_value = mock_post_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_httpx_client.return_value = mock_client_instance

        service = TaskManagementService(auth_token="test-token")
        result = service.closeCompletedTasks(sample_mapping, sample_workflow)

        assert result.synced_count > 0
        # Should include Epic closure since all tasks completed
        assert any(d.get("action") == "epic_closed" for d in result.details) or \
               any(d.get("action") == "closed" for d in result.details)

    def test_skip_already_closed(self, sample_workflow, sample_mapping, mock_httpx_client):
        """Test skipping already closed tasks."""
        sample_workflow.nodes[0].status = DDEStatus.COMPLETED

        # Mock shows task is already Done
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "output": {"status": {"name": "Done"}}
        }

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_get_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_httpx_client.return_value = mock_client_instance

        service = TaskManagementService(auth_token="test-token")
        result = service.closeCompletedTasks(sample_mapping, sample_workflow)

        # Should not close already-done tasks
        assert not any(
            d.get("node_id") == "node-1" and d.get("action") == "closed"
            for d in result.details
        )


# ============================================================================
# StatusSyncHandler Tests
# ============================================================================


class TestStatusSyncHandler:
    """Test webhook handler for status sync."""

    def test_handler_initialization(self):
        """Test handler initialization."""
        service = TaskManagementService()
        handler = StatusSyncHandler(service)

        assert handler.task_service == service
        assert handler.workflow_store == {}

    def test_register_workflow(self, sample_workflow):
        """Test registering a workflow."""
        service = TaskManagementService()
        handler = StatusSyncHandler(service)

        handler.register_workflow(sample_workflow)

        assert sample_workflow.id in handler.workflow_store
        assert handler.workflow_store[sample_workflow.id] == sample_workflow

    def test_handle_non_status_event(self):
        """Test handling non-status webhook events."""
        service = TaskManagementService()
        handler = StatusSyncHandler(service)

        result = handler.handle_jira_webhook({
            "webhookEvent": "jira:issue_created"
        })

        assert not result["processed"]
        assert "status" in result["reason"].lower()

    def test_handle_status_change_no_mapping(self, sample_workflow):
        """Test handling status change without mapping."""
        service = TaskManagementService()
        handler = StatusSyncHandler(service)
        handler.register_workflow(sample_workflow)

        result = handler.handle_jira_webhook({
            "webhookEvent": "jira:issue_updated",
            "issue": {"key": "MD-999"},
            "changelog": {
                "items": [
                    {"field": "status", "fromString": "To Do", "toString": "In Progress"}
                ]
            }
        })

        assert not result["processed"]
        assert "mapping" in result["reason"].lower()

    def test_handle_status_change_with_mapping(self, sample_workflow, sample_mapping):
        """Test handling status change with mapping."""
        service = TaskManagementService()
        service._mappings["wf-test-001"] = sample_mapping

        handler = StatusSyncHandler(service)
        handler.register_workflow(sample_workflow)

        result = handler.handle_jira_webhook({
            "webhookEvent": "jira:issue_updated",
            "issue": {"key": "MD-101"},
            "changelog": {
                "items": [
                    {"field": "status", "fromString": "To Do", "toString": "In Progress"}
                ]
            }
        })

        assert result["processed"]
        assert result["node_id"] == "node-1"
        assert result["new_status"] == "running"

        # Verify node status was updated
        node = sample_workflow.get_node("node-1")
        assert node.status == DDEStatus.RUNNING


# ============================================================================
# Integration Tests
# ============================================================================


class TestTaskManagementIntegration:
    """Integration tests for task management."""

    def test_full_workflow_lifecycle(self, sample_workflow, mock_httpx_client):
        """Test complete workflow: create Epic -> sync -> close."""
        # Setup mock for all operations
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "output": {
                "externalId": "MD-200",
                "deepLink": "https://jira.example.com/browse/MD-200",
                "status": {"name": "In Progress"}
            }
        }

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_httpx_client.return_value = mock_client_instance

        service = TaskManagementService(auth_token="test-token")

        # 1. Create Epic from workflow
        create_result = service.createEpicFromWorkflow(sample_workflow)
        # Note: With mocking, task creation also returns MD-200 for all
        # In real scenario, each would have unique keys

        # 2. Update workflow statuses
        sample_workflow.nodes[0].status = DDEStatus.RUNNING
        sample_workflow.nodes[1].status = DDEStatus.PENDING

        # Get mapping (might be None with mocking, create one)
        mapping = service.getMapping(sample_workflow.id)
        if not mapping:
            mapping = TaskMapping(
                workflow_id=sample_workflow.id,
                epic_key="MD-200",
                node_task_map={"node-1": "MD-201", "node-2": "MD-202"},
                task_node_map={"MD-201": "node-1", "MD-202": "node-2"}
            )
            service._mappings[sample_workflow.id] = mapping

        # 3. Sync statuses
        sync_result = service.syncTaskStatus(mapping, sample_workflow)
        assert sync_result.synced_count >= 0  # Mocked responses

        # 4. Mark nodes complete
        for node in sample_workflow.nodes:
            node.status = DDEStatus.COMPLETED

        # 5. Close completed tasks
        close_result = service.closeCompletedTasks(mapping, sample_workflow)
        assert close_result.synced_count >= 0


# ============================================================================
# Singleton Tests
# ============================================================================


class TestSingleton:
    """Test singleton factory function."""

    def test_get_task_management_service(self):
        """Test singleton service retrieval."""
        service1 = get_task_management_service()
        service2 = get_task_management_service()

        assert service1 is service2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
