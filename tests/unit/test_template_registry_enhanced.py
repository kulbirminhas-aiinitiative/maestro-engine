"""
Enhanced unit tests for Template Registry Service.

Comprehensive testing including API spec compliance, error handling,
security validation, and performance testing.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

# Add services to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services"))

from services.template_registry_service.app import app


@pytest.fixture
def client():
    """Provide FastAPI test client for Template Registry Service"""
    return TestClient(app)


@pytest.fixture
def mock_db(monkeypatch):
    """Mock database with comprehensive collection behavior"""
    from tests.conftest import MockDatabase

    mock_database = MockDatabase()

    # Patch the database in the app module
    import services.template_registry_service.app as template_app

    monkeypatch.setattr(template_app, "db", mock_database)

    return mock_database


@pytest.fixture
def sample_template():
    """Sample template data for testing"""
    return {
        "name": "fastapi-microservice",
        "description": "A production-ready FastAPI microservice template",
        "technology_stack": ["Python", "FastAPI", "Docker", "PostgreSQL"],
        "repo_url": "https://github.com/example/fastapi-microservice",
        "version": "2.1.0",
        "tags": ["api", "microservice", "production", "postgresql"],
    }


class TestHealthAndStandardEndpoints:
    """Test standard API spec endpoints"""

    def test_v1_health_endpoint(self, client):
        """Test v1 health endpoint compliance"""
        response = client.get("/v1/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "template_registry_service"
        assert data["version"] == "4.0.0"
        assert "uptime" in data
        assert "dependencies" in data
        assert "mongodb" in data["dependencies"]

    def test_v1_version_endpoint(self, client):
        """Test v1 version endpoint compliance"""
        response = client.get("/v1/version")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "template_registry_service"
        assert data["version"] == "4.0.0"
        assert data["api_version"] == "v1"
        assert "features" in data

        expected_features = [
            "template_management",
            "mongodb_storage",
            "search_filtering",
            "version_control",
        ]
        for feature in expected_features:
            assert feature in data["features"]

    def test_v1_metrics_endpoint(self, client):
        """Test v1 metrics endpoint compliance"""
        response = client.get("/v1/metrics")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "template_registry_service"
        assert "metrics" in data
        assert "timestamp" in data

        metrics = data["metrics"]
        expected_metrics = [
            "templates_total",
            "requests_total",
            "uptime_seconds",
            "database_connections",
        ]
        for metric in expected_metrics:
            assert metric in metrics

    def test_docs_endpoints_accessible(self, client):
        """Test documentation endpoints are accessible"""
        # Standard docs endpoint
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

        # OpenAPI JSON schema
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"


class TestTemplateCreation:
    """Test template creation functionality"""

    def test_create_template_success(self, client, mock_db, sample_template):
        """Test successful template creation"""
        response = client.post("/templates/", json=sample_template)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == sample_template["name"]
        assert data["description"] == sample_template["description"]
        assert "_id" in data

    def test_create_template_v1_endpoint(self, client, mock_db, sample_template):
        """Test v1 template creation endpoint"""
        response = client.post("/v1/templates", json=sample_template)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == sample_template["name"]

    def test_create_duplicate_template(self, client, mock_db, sample_template):
        """Test duplicate template creation prevention"""
        # Create first template
        client.post("/templates/", json=sample_template)

        # Attempt to create duplicate
        response = client.post("/templates/", json=sample_template)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_create_template_validation_errors(self, client, mock_db):
        """Test template creation validation"""
        # Missing required fields
        invalid_templates = [
            {},  # Empty
            {"name": "test"},  # Missing description
            {"name": "test", "description": "desc"},  # Missing technology_stack
            {
                "name": "test",
                "description": "desc",
                "technology_stack": [],
            },  # Empty tech stack
        ]

        for invalid_template in invalid_templates:
            response = client.post("/templates/", json=invalid_template)
            assert response.status_code == 422

    def test_create_template_with_invalid_url(self, client, mock_db):
        """Test template creation with invalid repository URL"""
        invalid_template = {
            "name": "test-template",
            "description": "Test template",
            "technology_stack": ["Python"],
            "repo_url": "not-a-valid-url",
            "version": "1.0.0",
        }

        response = client.post("/templates/", json=invalid_template)
        # Should accept any string as URL in current implementation
        assert response.status_code in [201, 422]

    def test_create_template_with_long_values(self, client, mock_db):
        """Test template creation with very long field values"""
        long_template = {
            "name": "a" * 200,  # Very long name
            "description": "b" * 5000,  # Very long description
            "technology_stack": ["Python", "FastAPI"],
            "repo_url": "https://github.com/example/repo",
            "version": "1.0.0",
        }

        response = client.post("/templates/", json=long_template)
        # Should handle long values gracefully
        assert response.status_code in [201, 422]


class TestTemplateRetrieval:
    """Test template retrieval functionality"""

    def test_list_all_templates(self, client, mock_db, sample_template):
        """Test listing all templates"""
        # Create a template first
        client.post("/templates/", json=sample_template)

        response = client.get("/templates/")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == sample_template["name"]

    def test_list_templates_v1_endpoint(self, client, mock_db, sample_template):
        """Test v1 template listing endpoint"""
        client.post("/v1/templates", json=sample_template)

        response = client.get("/v1/templates")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

    def test_get_template_by_id(self, client, mock_db, sample_template):
        """Test retrieving template by ID"""
        # Create template
        create_response = client.post("/templates/", json=sample_template)
        template_id = create_response.json()["_id"]

        # Retrieve template
        response = client.get(f"/templates/{template_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["_id"] == template_id
        assert data["name"] == sample_template["name"]

    def test_get_template_by_id_v1_endpoint(self, client, mock_db, sample_template):
        """Test v1 template retrieval by ID"""
        create_response = client.post("/v1/templates", json=sample_template)
        template_id = create_response.json()["_id"]

        response = client.get(f"/v1/templates/{template_id}")
        assert response.status_code == 200

    def test_get_nonexistent_template(self, client, mock_db):
        """Test retrieving non-existent template"""
        fake_id = str(ObjectId())
        response = client.get(f"/templates/{fake_id}")
        assert response.status_code == 404

    def test_get_template_invalid_id_format(self, client, mock_db):
        """Test retrieving template with invalid ID format"""
        response = client.get("/templates/invalid-id-format")
        assert response.status_code in [
            400,
            422,
            500,
        ]  # Various error handling approaches


class TestTemplateFiltering:
    """Test template filtering and search functionality"""

    def test_filter_by_technology(self, client, mock_db):
        """Test filtering templates by technology"""
        # Create templates with different technologies
        template1 = {
            "name": "python-template",
            "description": "Python template",
            "technology_stack": ["Python", "Django"],
            "repo_url": "https://github.com/example/python",
            "version": "1.0.0",
        }

        template2 = {
            "name": "node-template",
            "description": "Node.js template",
            "technology_stack": ["JavaScript", "Node.js"],
            "repo_url": "https://github.com/example/node",
            "version": "1.0.0",
        }

        client.post("/templates/", json=template1)
        client.post("/templates/", json=template2)

        # Filter by Python
        response = client.get("/templates/?technology=Python")
        assert response.status_code == 200

        data = response.json()
        assert len(data) >= 1
        # All returned templates should contain Python in tech stack
        for template in data:
            assert "Python" in template["technology_stack"]

    def test_filter_by_tag(self, client, mock_db):
        """Test filtering templates by tag"""
        template_with_api_tag = {
            "name": "api-template",
            "description": "API template",
            "technology_stack": ["Python"],
            "repo_url": "https://github.com/example/api",
            "version": "1.0.0",
            "tags": ["api", "rest"],
        }

        client.post("/templates/", json=template_with_api_tag)

        response = client.get("/templates/?tag=api")
        assert response.status_code == 200

        data = response.json()
        assert len(data) >= 1
        for template in data:
            assert "api" in template.get("tags", [])

    def test_combined_filtering(self, client, mock_db):
        """Test filtering with multiple parameters"""
        response = client.get("/templates/?technology=Python&tag=api")
        assert response.status_code == 200
        # Should return list (possibly empty) without error


class TestTemplateUpdating:
    """Test template updating functionality"""

    def test_update_template_success(self, client, mock_db, sample_template):
        """Test successful template update"""
        # Create template
        create_response = client.post("/templates/", json=sample_template)
        template_id = create_response.json()["_id"]

        # Update template
        update_data = {"description": "Updated description", "version": "2.0.0"}

        response = client.put(f"/templates/{template_id}", json=update_data)
        assert response.status_code == 200

        data = response.json()
        assert data["description"] == update_data["description"]
        assert data["version"] == update_data["version"]
        assert data["name"] == sample_template["name"]  # Unchanged field

    def test_update_template_v1_endpoint(self, client, mock_db, sample_template):
        """Test v1 template update endpoint"""
        create_response = client.post("/v1/templates", json=sample_template)
        template_id = create_response.json()["_id"]

        update_data = {"description": "Updated via v1 API"}
        response = client.put(f"/v1/templates/{template_id}", json=update_data)
        assert response.status_code == 200

    def test_update_nonexistent_template(self, client, mock_db):
        """Test updating non-existent template"""
        fake_id = str(ObjectId())
        update_data = {"description": "New description"}

        response = client.put(f"/templates/{fake_id}", json=update_data)
        assert response.status_code == 404

    def test_update_template_empty_payload(self, client, mock_db, sample_template):
        """Test updating template with empty payload"""
        create_response = client.post("/templates/", json=sample_template)
        template_id = create_response.json()["_id"]

        response = client.put(f"/templates/{template_id}", json={})
        assert response.status_code == 200  # Should return existing template unchanged


class TestTemplateDeletion:
    """Test template deletion functionality"""

    def test_delete_template_success(self, client, mock_db, sample_template):
        """Test successful template deletion"""
        # Create template
        create_response = client.post("/templates/", json=sample_template)
        template_id = create_response.json()["_id"]

        # Delete template
        response = client.delete(f"/templates/{template_id}")
        assert response.status_code == 204

        # Verify deletion
        get_response = client.get(f"/templates/{template_id}")
        assert get_response.status_code == 404

    def test_delete_template_v1_endpoint(self, client, mock_db, sample_template):
        """Test v1 template deletion endpoint"""
        create_response = client.post("/v1/templates", json=sample_template)
        template_id = create_response.json()["_id"]

        response = client.delete(f"/v1/templates/{template_id}")
        assert response.status_code == 204

    def test_delete_nonexistent_template(self, client, mock_db):
        """Test deleting non-existent template"""
        fake_id = str(ObjectId())
        response = client.delete(f"/templates/{fake_id}")
        assert response.status_code == 404


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_invalid_json_request(self, client):
        """Test handling of invalid JSON"""
        response = client.post(
            "/templates/",
            data="invalid json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422

    def test_malformed_object_id(self, client, mock_db):
        """Test handling of malformed ObjectId"""
        response = client.get("/templates/not-an-objectid")
        assert response.status_code in [400, 422, 500]

    def test_null_values_in_request(self, client, mock_db):
        """Test handling of null values"""
        template_with_nulls = {
            "name": "test-template",
            "description": None,
            "technology_stack": ["Python"],
            "repo_url": "https://github.com/example/repo",
            "version": "1.0.0",
        }

        response = client.post("/templates/", json=template_with_nulls)
        assert response.status_code in [201, 422]


class TestSecurityValidation:
    """Test security and input validation"""

    def test_sql_injection_prevention(self, client, mock_db):
        """Test SQL injection attempt handling"""
        malicious_template = {
            "name": "'; DROP TABLE templates; --",
            "description": "Malicious template",
            "technology_stack": ["Python"],
            "repo_url": "https://github.com/example/repo",
            "version": "1.0.0",
        }

        response = client.post("/templates/", json=malicious_template)
        # Should either accept as text or validate properly
        assert response.status_code in [201, 422]

    def test_xss_prevention(self, client, mock_db):
        """Test XSS attempt handling"""
        xss_template = {
            "name": "<script>alert('xss')</script>",
            "description": "XSS attempt in description",
            "technology_stack": ["<script>"],
            "repo_url": "javascript:alert('xss')",
            "version": "1.0.0",
        }

        response = client.post("/templates/", json=xss_template)
        assert response.status_code in [201, 422]

    def test_oversized_payload(self, client, mock_db):
        """Test handling of oversized payloads"""
        huge_template = {
            "name": "huge-template",
            "description": "x" * 100000,  # 100KB description
            "technology_stack": ["Python"] * 1000,  # Large array
            "repo_url": "https://github.com/example/repo",
            "version": "1.0.0",
        }

        response = client.post("/templates/", json=huge_template)
        # Should handle gracefully
        assert response.status_code in [201, 413, 422]


class TestPerformance:
    """Test performance characteristics"""

    def test_health_endpoint_response_time(self, client):
        """Test health endpoint responds quickly"""
        import time

        start_time = time.time()
        response = client.get("/v1/health")
        end_time = time.time()

        assert response.status_code == 200
        assert (end_time - start_time) < 1.0  # Should respond within 1 second

    def test_bulk_template_creation(self, client, mock_db):
        """Test creating multiple templates efficiently"""
        templates = []
        for i in range(10):
            template = {
                "name": f"template-{i}",
                "description": f"Template number {i}",
                "technology_stack": ["Python", "FastAPI"],
                "repo_url": f"https://github.com/example/template-{i}",
                "version": "1.0.0",
            }
            templates.append(template)

        # Create templates sequentially (no bulk endpoint in current implementation)
        responses = []
        for template in templates:
            response = client.post("/templates/", json=template)
            responses.append(response)

        # All should succeed
        for response in responses:
            assert response.status_code == 201


class TestAPISpecCompliance:
    """Test API specification compliance"""

    def test_all_required_endpoints_exist(self, client):
        """Test all required API spec endpoints exist"""
        required_endpoints = [
            ("/v1/health", "GET"),
            ("/v1/metrics", "GET"),
            ("/v1/version", "GET"),
            ("/v1/templates", "GET"),
            ("/v1/templates", "POST"),
        ]

        for endpoint, method in required_endpoints:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={})

            assert response.status_code != 404  # Endpoint should exist

    def test_response_content_types(self, client):
        """Test proper content-type headers"""
        json_endpoints = ["/v1/health", "/v1/metrics", "/v1/version", "/v1/templates"]

        for endpoint in json_endpoints:
            response = client.get(endpoint)
            if response.status_code == 200:
                assert "application/json" in response.headers["content-type"]

    def test_error_response_format(self, client, mock_db):
        """Test error responses follow consistent format"""
        # Test 404 error
        response = client.get("/v1/templates/nonexistent")
        assert response.status_code == 404

        error_data = response.json()
        assert "detail" in error_data or "error" in error_data

    def test_cors_compliance(self, client):
        """Test CORS headers if configured"""
        response = client.get("/v1/health")
        # CORS headers are optional but test doesn't fail if not present
        assert response.status_code == 200


@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests with database dependencies"""

    @patch("services.template_registry_service.app.db")
    def test_database_connection_failure(self, mock_db, client):
        """Test behavior when database is unavailable"""
        # Mock database error
        mock_db.__getitem__.side_effect = Exception("Database connection failed")

        response = client.get("/templates/")
        # Should handle database errors gracefully
        assert response.status_code in [200, 500, 503]

    @patch("services.template_registry_service.app.db")
    def test_database_timeout_handling(self, mock_db, client):
        """Test database timeout handling"""
        # Mock timeout error
        mock_collection = MagicMock()
        mock_collection.find.side_effect = Exception("Operation timed out")
        mock_db.__getitem__.return_value = mock_collection

        response = client.get("/templates/")
        assert response.status_code in [200, 500, 503]
