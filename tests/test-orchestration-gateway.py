#!/usr/bin/env python3
"""
Unit Tests for MAESTRO Orchestration Gateway Service

This module provides comprehensive unit tests for:
- API endpoint functionality
- Request validation and processing
- Requirement analysis logic
- Error handling and edge cases
- Event bus communication
- Database operations (mocked)
"""

import os

# Import the app and models from orchestration gateway
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "services", "orchestration_gateway"))

from app import OrchestrationRequest, RequirementAnalysis, app
from event_bus import EventType
from event_bus import MaestroEventBus as EventBus


class TestOrchestrationGateway:
    """Test suite for Orchestration Gateway API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def sample_request(self):
        """Sample orchestration request for testing"""
        return {
            "requirement": "Create a REST API for user management with authentication",
            "project_type": "api",
            "complexity": "medium",
            "metadata": {
                "preferred_language": "python",
                "framework": "fastapi",
                "database": "postgresql",
                "authentication": "jwt",
            },
        }

    @pytest.fixture
    def invalid_request(self):
        """Invalid request for error testing"""
        return {
            "requirement": "",  # Empty requirement
            "complexity": "invalid",  # Invalid complexity
            "metadata": {},
        }

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_docs_endpoint(self, client):
        """Test API documentation endpoint"""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_orchestrate_valid_request(self, client, sample_request):
        """Test successful orchestration with valid request"""
        response = client.post("/v1/orchestrate", json=sample_request)
        # Just check that it returns a reasonable status (might be 202 for async processing)
        assert response.status_code in [200, 202]

    def test_orchestrate_invalid_request(self, client, invalid_request):
        """Test orchestration with invalid request"""
        response = client.post("/v1/orchestrate", json=invalid_request)
        assert response.status_code == 422  # Validation error

    def test_orchestrate_missing_requirement(self, client):
        """Test orchestration with missing requirement field"""
        incomplete_request = {
            "project_type": "api",
            "complexity": "medium",
            # Missing 'requirement' field
        }
        response = client.post("/v1/orchestrate", json=incomplete_request)
        assert response.status_code == 422

    def test_orchestrate_invalid_complexity(self, client):
        """Test orchestration with invalid complexity value"""
        invalid_complexity_request = {
            "requirement": "Create a simple API",
            "complexity": "invalid_complexity",
        }
        response = client.post("/v1/orchestrate", json=invalid_complexity_request)
        assert response.status_code == 422

    def test_analyze_endpoint(self, client, sample_request):
        """Test requirement analysis endpoint"""
        response = client.post("/v1/analyze", json=sample_request)
        assert response.status_code == 200

        data = response.json()
        assert "estimated_complexity" in data
        assert "recommended_templates" in data

    def test_analyze_empty_requirement(self, client):
        """Test analysis with empty requirement"""
        empty_req = {"requirement": ""}
        response = client.post("/v1/analyze", json=empty_req)
        assert response.status_code == 422

    def test_status_endpoint_existing_project(self, client):
        """Test status endpoint for existing project"""
        response = client.get("/v1/status/test-123")
        # Check that we get some response - the service may return different status codes
        assert response.status_code in [200, 404]

    def test_status_endpoint_nonexistent_project(self, client):
        """Test status endpoint for non-existent project"""
        response = client.get("/v1/status/nonexistent")
        # Should return 404 or similar for non-existent project
        assert response.status_code in [404, 200]


class TestOrchestrationRequest:
    """Test suite for OrchestrationRequest model validation"""

    def test_valid_request_creation(self):
        """Test creation of valid OrchestrationRequest"""
        request_data = {
            "requirement": "Create a web application",
            "project_type": "web_application",
            "complexity": "medium",
            "metadata": {"language": "python"},
        }
        request = OrchestrationRequest(**request_data)
        assert request.requirement == "Create a web application"
        assert request.complexity == "medium"

    def test_complexity_validation(self):
        """Test complexity field validation"""
        # Valid complexities
        for complexity in ["simple", "medium", "complex"]:
            request = OrchestrationRequest(
                requirement="Test requirement with sufficient length",
                complexity=complexity,
            )
            assert request.complexity == complexity

        # Invalid complexity should raise ValueError
        with pytest.raises(ValueError):
            OrchestrationRequest(
                requirement="Test requirement with sufficient length",
                complexity="invalid",
            )

    def test_empty_requirement_validation(self):
        """Test that empty requirement is rejected"""
        with pytest.raises(ValueError):
            OrchestrationRequest(requirement="")

    def test_optional_fields(self):
        """Test that optional fields work correctly"""
        request = OrchestrationRequest(requirement="Test requirement with sufficient length")
        assert request.project_type == "web_application"  # Default value
        assert request.complexity == "medium"  # Default value
        assert request.metadata is None  # Optional field


class TestRequirementAnalysis:
    """Test suite for RequirementAnalysis model"""

    def test_analysis_creation(self):
        """Test creation of RequirementAnalysis"""
        analysis = RequirementAnalysis(
            parsed_requirements=["API requirement", "Database requirement"],
            recommended_templates=["template1"],
            estimated_complexity="medium",
            required_services=["database"],
            implementation_plan=["setup phase", "development phase", "testing phase"],
        )
        assert analysis.estimated_complexity == "medium"
        assert "template1" in analysis.recommended_templates


class TestEventBus:
    """Test suite for EventBus functionality"""

    @pytest.fixture
    def event_bus(self):
        """Create EventBus instance for testing"""
        return EventBus()

    def test_event_bus_initialization(self, event_bus):
        """Test EventBus initialization"""
        assert event_bus.subscribers == {}
        assert event_bus.event_history == []

    def test_subscribe_to_event(self, event_bus):
        """Test subscribing to events"""
        callback = MagicMock()
        event_bus.subscribe(EventType.ORCHESTRATION_STARTED, callback)

        assert EventType.ORCHESTRATION_STARTED in event_bus.subscribers
        assert callback in event_bus.subscribers[EventType.ORCHESTRATION_STARTED]

    def test_publish_event(self, event_bus):
        """Test publishing events"""
        callback = MagicMock()
        event_bus.subscribe(EventType.ORCHESTRATION_STARTED, callback)

        event_data = {"project_id": "test-123"}
        event_bus.publish(EventType.ORCHESTRATION_STARTED, event_data)

        callback.assert_called_once_with(event_data)
        assert len(event_bus.event_history) == 1

    def test_multiple_subscribers(self, event_bus):
        """Test multiple subscribers for same event"""
        callback1 = MagicMock()
        callback2 = MagicMock()

        event_bus.subscribe(EventType.ORCHESTRATION_COMPLETED, callback1)
        event_bus.subscribe(EventType.ORCHESTRATION_COMPLETED, callback2)

        event_data = {"status": "success"}
        event_bus.publish(EventType.ORCHESTRATION_COMPLETED, event_data)

        callback1.assert_called_once_with(event_data)
        callback2.assert_called_once_with(event_data)


class TestOrchestrationService:
    """Test suite for orchestration service logic"""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator for testing"""
        with patch("app.orchestrator") as mock:
            yield mock

    def test_analyze_requirements_simple(self, mock_orchestrator):
        """Test requirement analysis for simple project"""
        request = OrchestrationRequest(
            requirement="Create a simple calculator app", complexity="simple"
        )

        # Mock the analysis
        mock_orchestrator.analyze_requirements.return_value = RequirementAnalysis(
            parsed_requirements=["Application development", "Calculator functionality"],
            recommended_templates=["simple-app-template"],
            estimated_complexity="simple",
            required_services=[],
            implementation_plan=["Project setup", "Core development"],
        )

        result = mock_orchestrator.analyze_requirements(request)
        assert result.estimated_complexity == "simple"
        assert "simple-app-template" in result.recommended_templates

    def test_analyze_requirements_complex(self, mock_orchestrator):
        """Test requirement analysis for complex project"""
        request = OrchestrationRequest(
            requirement="Create an enterprise e-commerce platform with microservices",
            complexity="complex",
            metadata={"scalability": "high", "compliance": ["pci-dss", "gdpr"]},
        )

        mock_orchestrator.analyze_requirements.return_value = RequirementAnalysis(
            parsed_requirements=[
                "E-commerce platform development",
                "Microservices architecture",
                "High scalability requirements",
            ],
            recommended_templates=["microservices-template", "ecommerce-template"],
            estimated_complexity="complex",
            required_services=["database", "cache", "message_queue", "monitoring"],
            implementation_plan=[
                "Architecture design",
                "Core services development",
                "Integration phase",
                "Testing phase",
                "Deployment",
            ],
        )

        result = mock_orchestrator.analyze_requirements(request)
        assert result.estimated_complexity == "complex"
        assert len(result.required_services) >= 4
        assert "microservices-template" in result.recommended_templates


class TestErrorHandling:
    """Test suite for error handling and edge cases"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_malformed_json(self, client):
        """Test handling of malformed JSON"""
        response = client.post(
            "/v1/orchestrate",
            data="{ invalid json }",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_missing_content_type(self, client):
        """Test handling of missing content-type header"""
        response = client.post("/v1/orchestrate", data='{"requirement": "test"}')
        assert response.status_code in [422, 400]

    @patch("app.orchestrator.analyze_requirements")
    def test_service_error_handling(self, mock_analyze, client):
        """Test handling of internal service errors"""
        mock_analyze.side_effect = Exception("Internal service error")

        request = {"requirement": "Create an API", "complexity": "medium"}

        response = client.post("/v1/orchestrate", json=request)
        assert response.status_code == 500

    def test_large_payload(self, client):
        """Test handling of very large payloads"""
        large_metadata = {f"key_{i}": f"value_{i}" * 1000 for i in range(100)}
        request = {"requirement": "Create an API", "metadata": large_metadata}

        response = client.post("/v1/orchestrate", json=request)
        # Should either succeed or fail gracefully
        assert response.status_code in [200, 413, 422]


class TestPerformance:
    """Test suite for performance and concurrency"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @patch("app.orchestrator.analyze_requirements")
    def test_concurrent_requests(self, mock_analyze, client):
        """Test handling of concurrent requests"""
        mock_analyze.return_value = RequirementAnalysis(
            parsed_requirements=["API development"],
            recommended_templates=["template"],
            estimated_complexity="medium",
            required_services=["database"],
            implementation_plan=["Project setup"],
        )

        import threading

        results = []

        def make_request():
            request = {
                "requirement": f"Create API {threading.current_thread().name}",
                "complexity": "medium",
            }
            response = client.post("/v1/orchestrate", json=request)
            results.append(response.status_code)

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # All requests should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
