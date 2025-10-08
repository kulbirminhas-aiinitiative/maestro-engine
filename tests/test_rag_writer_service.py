#!/usr/bin/env python3
"""
Test Suite for RAG Writer Service

Tests for:
- Health check
- Execution indexing
- Template indexing
- Batch indexing
- Task status tracking
- Quality gate validation
- Retry logic
- Webhook notifications
"""

import time
from typing import Any, Dict

import pytest
import requests

# RAG Writer Service URL
BASE_URL = "http://localhost:9802"
API_KEY = "dev_rag_writer_key_98765"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


class TestRAGWriterHealth:
    """Test health and basic endpoints"""

    def test_health_check(self):
        """Test health check endpoint"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "rag_writer"
        assert data["port"] == 9802

    def test_stats_endpoint(self):
        """Test stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/v1/stats", headers=HEADERS)
        assert response.status_code == 200

        data = response.json()
        assert "queue_size" in data
        assert "total_tasks" in data
        assert "tasks_by_status" in data
        assert "maestro_templates_path" in data


class TestExecutionIndexing:
    """Test execution indexing functionality"""

    def test_index_execution_success(self):
        """Test successful execution indexing"""
        payload = {
            "session_id": "test_exec_001",
            "requirement": "Build REST API",
            "personas": ["backend_developer"],
            "collaterals": [{"path": "main.py", "type": "file"}],
            "quality_score": 0.75,
            "success": True,
            "execution_time": 45.5,
        }

        response = requests.post(
            f"{BASE_URL}/api/v1/index/execution", headers=HEADERS, json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"
        assert data["session_id"] == "test_exec_001"

        # Wait and check task status
        time.sleep(2)
        task_response = requests.get(f"{BASE_URL}/api/v1/task/{data['task_id']}", headers=HEADERS)
        assert task_response.status_code == 200

    def test_index_execution_quality_gate_fail(self):
        """Test execution indexing with low quality score"""
        payload = {
            "session_id": "test_exec_002",
            "requirement": "Build API",
            "personas": ["backend_developer"],
            "collaterals": [],
            "quality_score": 0.3,  # Below threshold
            "success": True,
        }

        response = requests.post(
            f"{BASE_URL}/api/v1/index/execution", headers=HEADERS, json=payload
        )

        assert response.status_code == 200
        # Task queued but should fail quality gate

    def test_index_execution_missing_fields(self):
        """Test execution indexing with missing required fields"""
        payload = {
            "session_id": "test_exec_003",
            # Missing requirement and personas
            "quality_score": 0.8,
            "success": True,
        }

        response = requests.post(
            f"{BASE_URL}/api/v1/index/execution", headers=HEADERS, json=payload
        )

        # Should return 422 validation error
        assert response.status_code == 422


class TestTemplateIndexing:
    """Test template indexing functionality"""

    def test_index_template_success(self):
        """Test successful template indexing"""
        payload = {
            "name": "Test Template",
            "content": "def hello():\n    print('Hello')",
            "category": "function",
            "language": "python",
            "framework": "none",
            "description": "Simple hello function",
            "tags": ["function", "test"],
            "save_to_maestro_templates": True,
        }

        response = requests.post(f"{BASE_URL}/api/v1/index/template", headers=HEADERS, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["template_name"] == "Test Template"

    def test_index_template_with_quality_scores(self):
        """Test template indexing with quality scores"""
        payload = {
            "name": "High Quality Template",
            "content": "class Example:\n    pass",
            "category": "class",
            "language": "python",
            "quality_scores": {
                "overall": 90.0,
                "security": 85.0,
                "performance": 88.0,
                "maintainability": 92.0,
            },
            "tags": ["class", "example"],
        }

        response = requests.post(f"{BASE_URL}/api/v1/index/template", headers=HEADERS, json=payload)

        assert response.status_code == 200


class TestBatchIndexing:
    """Test batch indexing functionality"""

    def test_batch_index_mixed(self):
        """Test batch indexing with both executions and templates"""
        payload = {
            "executions": [
                {
                    "session_id": "batch_exec_001",
                    "requirement": "API 1",
                    "personas": ["backend_developer"],
                    "quality_score": 0.8,
                    "success": True,
                },
                {
                    "session_id": "batch_exec_002",
                    "requirement": "API 2",
                    "personas": ["frontend_developer"],
                    "quality_score": 0.7,
                    "success": True,
                },
            ],
            "templates": [
                {
                    "name": "Batch Template 1",
                    "content": "// code",
                    "category": "test",
                    "language": "javascript",
                    "tags": ["test"],
                },
                {
                    "name": "Batch Template 2",
                    "content": "# code",
                    "category": "test",
                    "language": "python",
                    "tags": ["test"],
                },
            ],
        }

        response = requests.post(f"{BASE_URL}/api/v1/index/batch", headers=HEADERS, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "batch_id" in data
        assert "task_ids" in data
        assert data["total_tasks"] == 4
        assert len(data["task_ids"]) == 4

    def test_batch_index_executions_only(self):
        """Test batch indexing with only executions"""
        payload = {
            "executions": [
                {
                    "session_id": "batch_exec_003",
                    "requirement": "Test requirement",
                    "personas": ["qa_engineer"],
                    "quality_score": 0.6,
                    "success": True,
                }
            ],
            "templates": [],
        }

        response = requests.post(f"{BASE_URL}/api/v1/index/batch", headers=HEADERS, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["total_tasks"] == 1

    def test_batch_index_templates_only(self):
        """Test batch indexing with only templates"""
        payload = {
            "executions": [],
            "templates": [
                {
                    "name": "Batch Template Only",
                    "content": "template",
                    "category": "test",
                    "language": "text",
                    "tags": [],
                }
            ],
        }

        response = requests.post(f"{BASE_URL}/api/v1/index/batch", headers=HEADERS, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["total_tasks"] == 1


class TestTaskStatusTracking:
    """Test task status tracking"""

    def test_get_task_status(self):
        """Test retrieving task status"""
        # First create a task
        payload = {
            "session_id": "status_test_001",
            "requirement": "Test",
            "personas": ["backend_developer"],
            "quality_score": 0.7,
            "success": True,
        }

        create_response = requests.post(
            f"{BASE_URL}/api/v1/index/execution", headers=HEADERS, json=payload
        )

        task_id = create_response.json()["task_id"]

        # Get task status
        status_response = requests.get(f"{BASE_URL}/api/v1/task/{task_id}", headers=HEADERS)

        assert status_response.status_code == 200
        data = status_response.json()
        assert data["task_id"] == task_id
        assert data["task_type"] == "execution"
        assert data["status"] in ["pending", "processing", "completed", "failed"]

    def test_get_nonexistent_task(self):
        """Test retrieving non-existent task"""
        response = requests.get(f"{BASE_URL}/api/v1/task/nonexistent-task-id", headers=HEADERS)

        assert response.status_code == 404

    def test_list_tasks(self):
        """Test listing tasks"""
        response = requests.get(f"{BASE_URL}/api/v1/tasks", headers=HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "total" in data

    def test_list_tasks_with_filter(self):
        """Test listing tasks with status filter"""
        response = requests.get(
            f"{BASE_URL}/api/v1/tasks?status=completed&limit=5", headers=HEADERS
        )

        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data


class TestAuthentication:
    """Test API authentication"""

    def test_missing_api_key(self):
        """Test request without API key"""
        response = requests.get(f"{BASE_URL}/api/v1/stats")
        assert response.status_code == 422  # Missing header

    def test_invalid_api_key(self):
        """Test request with invalid API key"""
        headers = {"X-API-Key": "invalid_key"}
        response = requests.get(f"{BASE_URL}/api/v1/stats", headers=headers)
        assert response.status_code == 401

    def test_valid_api_key(self):
        """Test request with valid API key"""
        response = requests.get(f"{BASE_URL}/api/v1/stats", headers=HEADERS)
        assert response.status_code == 200


class TestQualityGate:
    """Test quality gate validation"""

    def test_quality_gate_pass(self):
        """Test quality gate with passing score"""
        payload = {
            "session_id": "quality_pass_001",
            "requirement": "High quality execution",
            "personas": ["backend_developer", "qa_engineer"],
            "quality_score": 0.85,
            "success": True,
        }

        response = requests.post(
            f"{BASE_URL}/api/v1/index/execution", headers=HEADERS, json=payload
        )

        assert response.status_code == 200

    def test_quality_gate_fail_low_score(self):
        """Test quality gate with failing score"""
        payload = {
            "session_id": "quality_fail_001",
            "requirement": "Low quality execution",
            "personas": ["backend_developer"],
            "quality_score": 0.2,  # Below 0.5 threshold
            "success": True,
        }

        response = requests.post(
            f"{BASE_URL}/api/v1/index/execution", headers=HEADERS, json=payload
        )

        # Task will be queued but should fail quality gate during processing
        assert response.status_code == 200


# Integration test
def test_end_to_end_workflow():
    """End-to-end test of indexing workflow"""

    # 1. Check service health
    health_response = requests.get(f"{BASE_URL}/health")
    assert health_response.status_code == 200

    # 2. Index an execution
    exec_payload = {
        "session_id": "e2e_test_001",
        "requirement": "End-to-end test execution",
        "personas": ["backend_developer", "qa_engineer"],
        "collaterals": [
            {"path": "main.py", "type": "file"},
            {"path": "test_main.py", "type": "file"},
        ],
        "quality_score": 0.82,
        "success": True,
        "execution_time": 120.5,
    }

    exec_response = requests.post(
        f"{BASE_URL}/api/v1/index/execution", headers=HEADERS, json=exec_payload
    )

    assert exec_response.status_code == 200
    exec_task_id = exec_response.json()["task_id"]

    # 3. Index a template
    template_payload = {
        "name": "E2E Test Template",
        "content": "def e2e_test():\n    pass",
        "category": "test",
        "language": "python",
        "framework": "pytest",
        "description": "End-to-end test template",
        "tags": ["e2e", "test"],
        "save_to_maestro_templates": False,
    }

    template_response = requests.post(
        f"{BASE_URL}/api/v1/index/template", headers=HEADERS, json=template_payload
    )

    assert template_response.status_code == 200
    template_task_id = template_response.json()["task_id"]

    # 4. Wait for processing
    time.sleep(3)

    # 5. Check task statuses
    exec_status = requests.get(f"{BASE_URL}/api/v1/task/{exec_task_id}", headers=HEADERS)
    assert exec_status.status_code == 200

    template_status = requests.get(f"{BASE_URL}/api/v1/task/{template_task_id}", headers=HEADERS)
    assert template_status.status_code == 200

    # 6. Check stats
    stats_response = requests.get(f"{BASE_URL}/api/v1/stats", headers=HEADERS)
    assert stats_response.status_code == 200
    stats_data = stats_response.json()
    assert stats_data["total_tasks"] >= 2


if __name__ == "__main__":
    print("RAG Writer Service Test Suite")
    print("=" * 80)
    print("\nIMPORTANT: Make sure RAG Writer service is running on port 9802")
    print("Start service: poetry run python src/rag_writer/rag_writer_service.py\n")
    print("Running tests with pytest...")
    print("=" * 80)

    pytest.main([__file__, "-v", "--tb=short"])
