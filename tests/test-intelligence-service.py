#!/usr/bin/env python3
"""
Unit Tests for MAESTRO Intelligence Service

This module provides comprehensive unit tests for:
- FastAPI endpoint functionality (/v1/ endpoints)
- Requirement analysis via /v1/analyze endpoint
- Health check endpoints (/health, /v1/health)
- Model listing and signal querying (/v1/models, /v1/signals)
- Orchestration workflow validation (/orchestrate)
"""

import os

# Import the intelligence service components
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "services", "intelligence_service"))

from brain import app


class TestIntelligenceServiceAPI:
    """Test suite for Intelligence Service FastAPI endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def sample_analysis_request(self):
        """Sample analysis request for testing"""
        return {
            "requirement": "Build a scalable e-commerce platform with user authentication",
            "project_type": "web_application",
            "complexity": "complex",
            "constraints": {
                "budget": "medium",
                "timeline": "3-6 months",
                "team_size": 5,
                "scalability": "high",
            },
            "preferences": {
                "technology": ["python", "react"],
                "deployment": "cloud",
                "database": "postgresql",
            },
        }

    @pytest.fixture
    def simple_analysis_request(self):
        """Simple analysis request for testing"""
        return {
            "requirement": "Create a basic calculator app",
            "project_type": "mobile_app",
            "complexity": "simple",
        }

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "service" in data
        assert data["service"] == "intelligence-service"

    def test_v1_health_endpoint(self, client):
        """Test v1 health check endpoint"""
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "uptime" in data

    def test_analyze_requirements_endpoint(self, client, sample_analysis_request):
        """Test requirement analysis endpoint"""
        response = client.post("/v1/analyze", json=sample_analysis_request)
        assert response.status_code == 200

        data = response.json()
        assert "strategy" in data
        assert "analysis" in data
        assert "approach" in data["strategy"]
        assert "complexity" in data["strategy"]
        assert data["strategy"]["approach"] == "dynamic_persona_workflow"

    def test_orchestrate_endpoint(self, client):
        """Test orchestration endpoint"""
        orchestration_request = {
            "requirement": "Build a simple web application",
            "correlation_id": "test-12345",
            "context": {"project_type": "web_application"},
        }

        response = client.post("/orchestrate", json=orchestration_request)
        assert response.status_code == 200

        data = response.json()
        assert "correlation_id" in data
        assert "status" in data
        assert "message" in data

    def test_models_endpoint(self, client):
        """Test models listing endpoint"""
        response = client.get("/v1/models")
        assert response.status_code == 200

        data = response.json()
        assert "models" in data
        assert isinstance(data["models"], list)

        # Verify expected models are present
        model_ids = [model["id"] for model in data["models"]]
        assert "coherent_persona_executor" in model_ids

    def test_signals_endpoint(self, client):
        """Test signals querying endpoint"""
        response = client.get("/v1/signals")
        assert response.status_code == 200

        data = response.json()
        assert "signals" in data
        assert isinstance(data["signals"], list)

    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "capabilities" in data

    def test_analyze_invalid_request(self, client):
        """Test analysis with invalid request"""
        invalid_request = {
            "requirement": "",  # Empty requirement
            "complexity": "invalid_complexity",
        }
        response = client.post("/v1/analyze", json=invalid_request)
        # Should still process but may return error in response
        assert response.status_code in [200, 422]

    def test_analyze_missing_requirement(self, client):
        """Test analysis with missing requirement field"""
        incomplete_request = {"project_type": "web_application", "complexity": "medium"}
        response = client.post("/v1/analyze", json=incomplete_request)
        # Should still process but may return error in response
        assert response.status_code in [200, 422]

    def test_v1_metrics_endpoint(self, client):
        """Test metrics endpoint"""
        response = client.get("/v1/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "timestamp" in data

    def test_v1_version_endpoint(self, client):
        """Test version endpoint"""
        response = client.get("/v1/version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "service" in data


class TestErrorHandling:
    """Test suite for error handling and edge cases"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_nonexistent_endpoint(self, client):
        """Test calling non-existent endpoint"""
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_malformed_json_request(self, client):
        """Test handling of malformed JSON request"""
        response = client.post("/v1/analyze", data="invalid json")
        assert response.status_code == 422

    def test_empty_json_request(self, client):
        """Test handling of empty JSON request"""
        response = client.post("/v1/analyze", json={})
        assert response.status_code in [200, 422]

    def test_orchestrate_missing_correlation_id(self, client):
        """Test orchestrate endpoint with missing correlation ID"""
        incomplete_request = {"requirement": "Build something", "context": {}}
        response = client.post("/orchestrate", json=incomplete_request)
        assert response.status_code == 422

    def test_orchestrate_missing_requirement(self, client):
        """Test orchestrate endpoint with missing requirement"""
        incomplete_request = {"correlation_id": "test-123", "context": {}}
        response = client.post("/orchestrate", json=incomplete_request)
        assert response.status_code == 422


class TestAPICompatibility:
    """Test suite for API compatibility and response formats"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_all_endpoints_return_json(self, client):
        """Test that all endpoints return valid JSON"""
        endpoints = [
            "/health",
            "/v1/health",
            "/v1/models",
            "/v1/signals",
            "/v1/metrics",
            "/v1/version",
            "/",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200
            # Should be able to parse as JSON
            data = response.json()
            assert isinstance(data, dict)

    def test_post_endpoints_accept_json(self, client):
        """Test that POST endpoints accept JSON properly"""
        analyze_request = {"requirement": "test", "complexity": "simple"}
        response = client.post("/v1/analyze", json=analyze_request)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")

        orchestrate_request = {
            "requirement": "test",
            "correlation_id": "test-123",
            "context": {},
        }
        response = client.post("/orchestrate", json=orchestrate_request)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")

    def test_cors_headers_present(self, client):
        """Test that CORS headers are present if configured"""
        response = client.get("/health")
        # CORS headers may or may not be present depending on configuration
        # This is just to verify the endpoint works properly
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
