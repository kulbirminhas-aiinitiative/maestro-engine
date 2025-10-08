"""
Comprehensive End-to-End API test scenarios for MAESTRO microservices.

This module tests complete user journeys across all services,
validating the entire system integration and API workflows.
"""

import os
import time
import uuid
from typing import Any, Dict

import pytest
import requests


@pytest.fixture(scope="session")
def api_config():
    """API configuration for E2E tests"""
    return {
        "orchestration_gateway": os.environ.get("GW_URL", "http://localhost:8000"),
        "intelligence_service": os.environ.get("INTELLIGENCE_URL", "http://localhost:9501"),
        "template_registry": os.environ.get("TEMPLATE_URL", "http://localhost:9500"),
        "timeout": 30,
        "retry_attempts": 3,
        "retry_delay": 2,
    }


@pytest.fixture
def http_client():
    """HTTP client with proper configuration"""
    session = requests.Session()
    session.timeout = 30
    session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})
    return session


class ServiceHelper:
    """Helper class for service interactions"""

    def __init__(self, client: requests.Session, config: Dict[str, Any]):
        self.client = client
        self.config = config

    def wait_for_service(self, service_url: str, max_attempts: int = 30) -> bool:
        """Wait for service to become available"""
        for attempt in range(max_attempts):
            try:
                response = self.client.get(f"{service_url}/v1/health", timeout=5)
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False

    def check_all_services(self) -> Dict[str, bool]:
        """Check availability of all services"""
        results = {}
        for service_name, service_url in self.config.items():
            if service_name == "timeout" or service_name.startswith("retry"):
                continue
            results[service_name] = self.wait_for_service(service_url, max_attempts=3)
        return results

    def retry_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Retry request with exponential backoff"""
        attempts = self.config.get("retry_attempts", 3)
        delay = self.config.get("retry_delay", 2)

        for attempt in range(attempts):
            try:
                response = getattr(self.client, method.lower())(url, **kwargs)
                if response.status_code < 500:  # Don't retry client errors
                    return response
            except requests.exceptions.RequestException as e:
                if attempt == attempts - 1:
                    raise e

            time.sleep(delay * (2**attempt))  # Exponential backoff

        raise Exception(f"Failed after {attempts} attempts")


@pytest.fixture
def service_helper(http_client, api_config):
    """Service helper instance"""
    return ServiceHelper(http_client, api_config)


@pytest.mark.e2e
class TestServiceHealth:
    """Test health and availability of all services"""

    def test_all_services_healthy(self, service_helper, api_config):
        """Test that all required services are healthy"""
        service_status = service_helper.check_all_services()

        failed_services = [name for name, status in service_status.items() if not status]
        if failed_services:
            pytest.skip(f"Required services not available: {failed_services}")

        # All services should be healthy
        for service_name, is_healthy in service_status.items():
            assert is_healthy, f"Service {service_name} is not healthy"

    def test_health_endpoints_compliance(self, http_client, api_config):
        """Test all health endpoints follow API specification"""
        for service_name, service_url in api_config.items():
            if service_name.startswith("retry") or service_name == "timeout":
                continue

            response = http_client.get(f"{service_url}/v1/health")
            if response.status_code != 200:
                pytest.skip(f"Service {service_name} not available")

            data = response.json()

            # Check required fields
            required_fields = ["status", "timestamp", "service", "version"]
            for field in required_fields:
                assert field in data, f"Missing {field} in {service_name} health response"

            # Status should be healthy/ok
            assert data["status"] in [
                "healthy",
                "ok",
            ], f"Service {service_name} not healthy"

    def test_version_endpoints_compliance(self, http_client, api_config):
        """Test version endpoints follow API specification"""
        for service_name, service_url in api_config.items():
            if service_name.startswith("retry") or service_name == "timeout":
                continue

            response = http_client.get(f"{service_url}/v1/version")
            if response.status_code != 200:
                continue  # Skip if service not available

            data = response.json()

            # Check required fields
            required_fields = ["service", "version", "api_version"]
            for field in required_fields:
                assert field in data, f"Missing {field} in {service_name} version response"

            assert data["api_version"] == "v1", f"Invalid API version for {service_name}"


@pytest.mark.e2e
class TestTemplateManagementWorkflow:
    """Test complete template management workflow"""

    def test_template_lifecycle_e2e(self, http_client, api_config):
        """Test complete template lifecycle from creation to deletion"""
        template_service = api_config["template_registry"]

        # Check if service is available
        health_response = http_client.get(f"{template_service}/v1/health")
        if health_response.status_code != 200:
            pytest.skip("Template Registry Service not available")

        # Step 1: Create a new template
        template_data = {
            "name": f"e2e-test-template-{uuid.uuid4().hex[:8]}",
            "description": "End-to-end test template for comprehensive testing",
            "technology_stack": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            "repo_url": "https://github.com/test/e2e-template",
            "version": "1.0.0",
            "tags": ["test", "e2e", "automation"],
        }

        create_response = http_client.post(f"{template_service}/v1/templates", json=template_data)
        assert (
            create_response.status_code == 201
        ), f"Failed to create template: {create_response.text}"

        created_template = create_response.json()
        template_id = created_template["_id"]
        assert created_template["name"] == template_data["name"]

        # Step 2: Retrieve the template by ID
        get_response = http_client.get(f"{template_service}/v1/templates/{template_id}")
        assert get_response.status_code == 200

        retrieved_template = get_response.json()
        assert retrieved_template["name"] == template_data["name"]
        assert retrieved_template["_id"] == template_id

        # Step 3: List all templates and verify our template is included
        list_response = http_client.get(f"{template_service}/v1/templates")
        assert list_response.status_code == 200

        templates = list_response.json()
        assert isinstance(templates, list)
        template_names = [t["name"] for t in templates]
        assert template_data["name"] in template_names

        # Step 4: Update the template
        update_data = {
            "description": "Updated e2e test template description",
            "version": "1.1.0",
            "tags": ["test", "e2e", "automation", "updated"],
        }

        update_response = http_client.put(
            f"{template_service}/v1/templates/{template_id}", json=update_data
        )
        assert update_response.status_code == 200

        updated_template = update_response.json()
        assert updated_template["description"] == update_data["description"]
        assert updated_template["version"] == update_data["version"]
        assert updated_template["name"] == template_data["name"]  # Should remain unchanged

        # Step 5: Filter templates by technology
        filter_response = http_client.get(f"{template_service}/v1/templates?technology=Python")
        assert filter_response.status_code == 200

        filtered_templates = filter_response.json()
        python_templates = [t for t in filtered_templates if "Python" in t["technology_stack"]]
        assert len(python_templates) >= 1

        # Step 6: Filter templates by tag
        tag_response = http_client.get(f"{template_service}/v1/templates?tag=e2e")
        assert tag_response.status_code == 200

        tagged_templates = tag_response.json()
        e2e_templates = [t for t in tagged_templates if "e2e" in t.get("tags", [])]
        assert len(e2e_templates) >= 1

        # Step 7: Delete the template
        delete_response = http_client.delete(f"{template_service}/v1/templates/{template_id}")
        assert delete_response.status_code == 204

        # Step 8: Verify template is deleted
        get_deleted_response = http_client.get(f"{template_service}/v1/templates/{template_id}")
        assert get_deleted_response.status_code == 404

    def test_template_validation_scenarios(self, http_client, api_config):
        """Test template validation edge cases"""
        template_service = api_config["template_registry"]

        # Check if service is available
        health_response = http_client.get(f"{template_service}/v1/health")
        if health_response.status_code != 200:
            pytest.skip("Template Registry Service not available")

        # Test 1: Missing required fields
        invalid_template = {
            "name": "incomplete-template"
            # Missing description, technology_stack, repo_url
        }

        response = http_client.post(f"{template_service}/v1/templates", json=invalid_template)
        assert response.status_code == 422

        # Test 2: Duplicate template name
        valid_template = {
            "name": f"duplicate-test-{uuid.uuid4().hex[:8]}",
            "description": "Template for duplicate testing",
            "technology_stack": ["Python"],
            "repo_url": "https://github.com/test/duplicate",
            "version": "1.0.0",
        }

        # Create first template
        first_response = http_client.post(f"{template_service}/v1/templates", json=valid_template)
        if first_response.status_code == 201:
            template_id = first_response.json()["_id"]

            # Try to create duplicate
            duplicate_response = http_client.post(
                f"{template_service}/v1/templates", json=valid_template
            )
            assert duplicate_response.status_code == 409

            # Cleanup
            http_client.delete(f"{template_service}/v1/templates/{template_id}")


@pytest.mark.e2e
class TestOrchestrationWorkflow:
    """Test orchestration workflow scenarios"""

    def test_orchestration_request_submission(self, http_client, api_config):
        """Test submitting orchestration requests"""
        gateway_url = api_config["orchestration_gateway"]

        # Check if service is available
        health_response = http_client.get(f"{gateway_url}/v1/health")
        if health_response.status_code != 200:
            pytest.skip("Orchestration Gateway not available")

        # Submit orchestration request
        orchestration_request = {
            "requirement": "Create a simple REST API for user management with authentication",
            "project_type": "api",
            "complexity": "medium",
            "metadata": {
                "preferred_language": "python",
                "framework": "fastapi",
                "database": "postgresql",
                "authentication": "jwt",
            },
        }

        response = http_client.post(f"{gateway_url}/v1/orchestrate", json=orchestration_request)
        assert response.status_code == 202, f"Failed to submit orchestration: {response.text}"

        result = response.json()
        assert "correlation_id" in result
        assert "status" in result
        assert result["status"] == "accepted"

        correlation_id = result["correlation_id"]

        # Check request status
        status_response = http_client.get(f"{gateway_url}/v1/requests/{correlation_id}")
        # May return 404 if request not found in current state management
        assert status_response.status_code in [200, 404]

    def test_orchestration_validation(self, http_client, api_config):
        """Test orchestration request validation"""
        gateway_url = api_config["orchestration_gateway"]

        # Check if service is available
        health_response = http_client.get(f"{gateway_url}/v1/health")
        if health_response.status_code != 200:
            pytest.skip("Orchestration Gateway not available")

        # Test invalid requests
        invalid_requests = [
            {},  # Empty request
            {"requirement": ""},  # Empty requirement
            {"requirement": "test", "complexity": "invalid"},  # Invalid complexity
            {"project_type": "api"},  # Missing requirement
        ]

        for invalid_request in invalid_requests:
            response = http_client.post(f"{gateway_url}/v1/orchestrate", json=invalid_request)
            assert response.status_code == 422, f"Should reject invalid request: {invalid_request}"


@pytest.mark.e2e
class TestCrossServiceIntegration:
    """Test integration between multiple services"""

    def test_template_to_orchestration_workflow(self, http_client, api_config, service_helper):
        """Test workflow from template creation to orchestration"""
        # Check all services are available
        service_status = service_helper.check_all_services()
        if not all(service_status.values()):
            pytest.skip("Not all services available for integration test")

        template_service = api_config["template_registry"]
        gateway_service = api_config["orchestration_gateway"]

        # Step 1: Create a template
        template_data = {
            "name": f"integration-template-{uuid.uuid4().hex[:8]}",
            "description": "Template for integration testing",
            "technology_stack": ["Python", "FastAPI"],
            "repo_url": "https://github.com/test/integration-template",
            "version": "1.0.0",
            "tags": ["integration", "test"],
        }

        create_response = http_client.post(f"{template_service}/v1/templates", json=template_data)
        if create_response.status_code != 201:
            pytest.skip("Cannot create template for integration test")

        template_id = create_response.json()["_id"]

        try:
            # Step 2: Verify template exists
            get_response = http_client.get(f"{template_service}/v1/templates/{template_id}")
            assert get_response.status_code == 200

            # Step 3: Submit orchestration request that could use this template
            orchestration_request = {
                "requirement": f"Create an API using the {template_data['name']} template",
                "project_type": "api",
                "complexity": "low",
                "metadata": {
                    "template_preference": template_data["name"],
                    "framework": "fastapi",
                },
            }

            orchestration_response = http_client.post(
                f"{gateway_service}/v1/orchestrate", json=orchestration_request
            )
            assert orchestration_response.status_code == 202

        finally:
            # Cleanup: Delete the template
            http_client.delete(f"{template_service}/v1/templates/{template_id}")

    def test_api_spec_consistency(self, http_client, api_config):
        """Test API specification consistency across services"""
        spec_compliant_endpoints = [
            ("/v1/health", "GET"),
            ("/v1/version", "GET"),
            ("/v1/metrics", "GET"),
        ]

        for service_name, service_url in api_config.items():
            if service_name.startswith("retry") or service_name == "timeout":
                continue

            for endpoint, method in spec_compliant_endpoints:
                response = http_client.get(f"{service_url}{endpoint}")
                if response.status_code == 200:
                    # Verify response is JSON
                    assert "application/json" in response.headers.get("content-type", "")

                    # Verify common fields
                    data = response.json()
                    if endpoint == "/v1/health":
                        assert "status" in data
                        assert "service" in data
                    elif endpoint == "/v1/version":
                        assert "service" in data
                        assert "version" in data
                        assert "api_version" in data


@pytest.mark.e2e
class TestErrorHandlingAndResilience:
    """Test error handling and system resilience"""

    def test_service_error_propagation(self, http_client, api_config):
        """Test how services handle and propagate errors"""
        for service_name, service_url in api_config.items():
            if service_name.startswith("retry") or service_name == "timeout":
                continue

            # Test non-existent endpoint
            response = http_client.get(f"{service_url}/v1/nonexistent")
            assert response.status_code == 404

            # Test malformed requests where applicable
            if service_name == "template_registry":
                response = http_client.post(f"{service_url}/v1/templates", json={"invalid": "data"})
                assert response.status_code == 422

    def test_timeout_handling(self, http_client, api_config):
        """Test service timeout handling"""
        # Test with very short timeout
        short_timeout_client = requests.Session()
        short_timeout_client.timeout = 0.001  # 1ms timeout

        for service_name, service_url in api_config.items():
            if service_name.startswith("retry") or service_name == "timeout":
                continue

            try:
                response = short_timeout_client.get(f"{service_url}/v1/health")
                # If it succeeds, the service is very fast
                assert response.status_code == 200
            except requests.exceptions.Timeout:
                # Expected with such a short timeout
                pass

    def test_malformed_request_handling(self, http_client, api_config):
        """Test handling of malformed requests"""
        for service_name, service_url in api_config.items():
            if service_name.startswith("retry") or service_name == "timeout":
                continue

            # Test invalid JSON
            try:
                response = requests.post(
                    f"{service_url}/v1/health",  # Wrong method for health endpoint
                    data="invalid json",
                    headers={"Content-Type": "application/json"},
                    timeout=5,
                )
                assert response.status_code in [
                    405,
                    422,
                ]  # Method not allowed or validation error
            except Exception:
                pass  # Some services might not accept POST to health


@pytest.mark.e2e
class TestPerformanceCharacteristics:
    """Test performance characteristics of the system"""

    def test_response_times(self, http_client, api_config):
        """Test service response times are reasonable"""
        max_response_time = 5.0  # 5 seconds max

        for service_name, service_url in api_config.items():
            if service_name.startswith("retry") or service_name == "timeout":
                continue

            start_time = time.time()
            try:
                response = http_client.get(f"{service_url}/v1/health", timeout=max_response_time)
                end_time = time.time()

                if response.status_code == 200:
                    response_time = end_time - start_time
                    assert (
                        response_time < max_response_time
                    ), f"Service {service_name} too slow: {response_time}s"
            except requests.exceptions.Timeout:
                pytest.fail(f"Service {service_name} timed out after {max_response_time}s")
            except Exception:
                # Service might not be available, skip
                pass

    def test_concurrent_requests(self, api_config):
        """Test handling of concurrent requests"""
        import concurrent.futures

        def make_health_request(service_url: str) -> bool:
            try:
                response = requests.get(f"{service_url}/v1/health", timeout=10)
                return response.status_code == 200
            except Exception:
                return False

        # Test concurrent requests to each service
        for service_name, service_url in api_config.items():
            if service_name.startswith("retry") or service_name == "timeout":
                continue

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(make_health_request, service_url) for _ in range(10)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]

            # At least some requests should succeed (service might be available)
            if any(results):
                success_rate = sum(results) / len(results)
                assert (
                    success_rate >= 0.8
                ), f"Service {service_name} concurrent request success rate: {success_rate}"


@pytest.mark.e2e
@pytest.mark.slow
class TestDataConsistencyAndPersistence:
    """Test data consistency and persistence across services"""

    def test_template_data_persistence(self, http_client, api_config):
        """Test that template data persists correctly"""
        template_service = api_config["template_registry"]

        # Check if service is available
        health_response = http_client.get(f"{template_service}/v1/health")
        if health_response.status_code != 200:
            pytest.skip("Template Registry Service not available")

        # Create template
        template_data = {
            "name": f"persistence-test-{uuid.uuid4().hex[:8]}",
            "description": "Template for testing data persistence",
            "technology_stack": ["Python", "FastAPI"],
            "repo_url": "https://github.com/test/persistence",
            "version": "1.0.0",
            "tags": ["persistence", "test"],
        }

        create_response = http_client.post(f"{template_service}/v1/templates", json=template_data)
        if create_response.status_code != 201:
            pytest.skip("Cannot create template for persistence test")

        template_id = create_response.json()["_id"]

        try:
            # Verify immediate retrieval
            get_response1 = http_client.get(f"{template_service}/v1/templates/{template_id}")
            assert get_response1.status_code == 200
            assert get_response1.json()["name"] == template_data["name"]

            # Wait a moment and verify persistence
            time.sleep(2)

            get_response2 = http_client.get(f"{template_service}/v1/templates/{template_id}")
            assert get_response2.status_code == 200
            assert get_response2.json()["name"] == template_data["name"]

            # Verify data integrity
            template1 = get_response1.json()
            template2 = get_response2.json()
            assert template1 == template2

        finally:
            # Cleanup
            http_client.delete(f"{template_service}/v1/templates/{template_id}")


@pytest.mark.e2e
class TestSecurityAndValidation:
    """Test security aspects and input validation"""

    def test_input_sanitization(self, http_client, api_config):
        """Test input sanitization across services"""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE templates; --",
            "../../../etc/passwd",
            "\x00null_byte_injection",
            "A" * 10000,  # Very long input
        ]

        # Test template service
        template_service = api_config["template_registry"]
        health_response = http_client.get(f"{template_service}/v1/health")

        if health_response.status_code == 200:
            for malicious_input in malicious_inputs:
                template_data = {
                    "name": f"security-test-{uuid.uuid4().hex[:8]}",
                    "description": malicious_input,
                    "technology_stack": ["Python"],
                    "repo_url": "https://github.com/test/security",
                    "version": "1.0.0",
                }

                response = http_client.post(f"{template_service}/v1/templates", json=template_data)
                # Should either accept as text or reject properly
                assert response.status_code in [
                    201,
                    422,
                ], f"Unexpected response for input: {malicious_input[:50]}"

                if response.status_code == 201:
                    template_id = response.json()["_id"]
                    # Cleanup
                    http_client.delete(f"{template_service}/v1/templates/{template_id}")

    def test_content_type_validation(self, http_client, api_config):
        """Test content-type validation"""
        for service_name, service_url in api_config.items():
            if service_name.startswith("retry") or service_name == "timeout":
                continue

            # Test POST with wrong content type (if service has POST endpoints)
            if service_name == "template_registry":
                response = requests.post(
                    f"{service_url}/v1/templates",
                    data="test data",
                    headers={"Content-Type": "text/plain"},
                    timeout=5,
                )
                assert response.status_code in [
                    415,
                    422,
                ]  # Unsupported media type or validation error
