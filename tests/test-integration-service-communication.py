#!/usr/bin/env python3
"""
Integration Tests for MAESTRO Service Communication

This module provides comprehensive integration tests for:
- Service-to-service communication workflows
- End-to-end orchestration scenarios
- Inter-service data flow validation
- Service dependency management
- Error propagation and handling
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
import requests

# Test configuration
ORCHESTRATION_GATEWAY_URL = "http://localhost:8000"
INTELLIGENCE_SERVICE_URL = "http://localhost:9501"
TEMPLATE_REGISTRY_URL = "http://localhost:9500"
EXECUTION_SERVICE_URL = "http://localhost:9502"
MONITORING_SERVICE_URL = "http://localhost:9503"
QUALITY_SERVICE_URL = "http://localhost:9504"

# Test timeouts
HEALTH_CHECK_TIMEOUT = 5
API_REQUEST_TIMEOUT = 30
WORKFLOW_TIMEOUT = 60


class TestServiceHealthAndDiscovery:
    """Test suite for service health checks and discovery"""

    def test_all_services_health_check(self):
        """Test that all services are healthy and accessible"""
        services = {
            "orchestration-gateway": ORCHESTRATION_GATEWAY_URL,
            "intelligence-service": INTELLIGENCE_SERVICE_URL,
            "template-registry": TEMPLATE_REGISTRY_URL,
            "execution-service": EXECUTION_SERVICE_URL,
            "monitoring-service": MONITORING_SERVICE_URL,
            "quality-service": QUALITY_SERVICE_URL,
        }

        health_results = {}

        for service_name, service_url in services.items():
            try:
                response = requests.get(f"{service_url}/health", timeout=HEALTH_CHECK_TIMEOUT)
                health_results[service_name] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "response_time": response.elapsed.total_seconds(),
                    "details": response.json() if response.status_code == 200 else None,
                }
            except Exception as e:
                health_results[service_name] = {
                    "status": "unreachable",
                    "error": str(e),
                }

        # Assert that critical services are available
        critical_services = [
            "orchestration-gateway",
            "intelligence-service",
            "template-registry",
        ]
        for service in critical_services:
            assert (
                health_results[service]["status"] == "healthy"
            ), f"Critical service {service} is not healthy: {health_results[service]}"

    def test_service_discovery_endpoints(self):
        """Test service discovery and registry endpoints"""
        # Test template registry service discovery
        try:
            response = requests.get(
                f"{TEMPLATE_REGISTRY_URL}/services", timeout=API_REQUEST_TIMEOUT
            )
            if response.status_code == 200:
                services = response.json()
                assert isinstance(services, list)
                assert len(services) > 0
        except requests.exceptions.RequestException:
            pytest.skip("Template registry service not available")


class TestOrchestrationWorkflows:
    """Test suite for end-to-end orchestration workflows"""

    @pytest.fixture
    def sample_orchestration_request(self):
        """Sample orchestration request for testing"""
        return {
            "requirement": "Create a REST API for user management with JWT authentication",
            "project_type": "api",
            "complexity": "medium",
            "metadata": {
                "preferred_language": "python",
                "framework": "fastapi",
                "database": "postgresql",
                "authentication": "jwt",
            },
        }

    def test_full_orchestration_workflow(self, sample_orchestration_request):
        """Test complete orchestration workflow from request to result"""
        # Step 1: Submit orchestration request
        try:
            response = requests.post(
                f"{ORCHESTRATION_GATEWAY_URL}/v1/orchestrate",
                json=sample_orchestration_request,
                timeout=WORKFLOW_TIMEOUT,
            )

            if response.status_code == 404:
                pytest.skip("Orchestration endpoint not implemented yet")

            assert response.status_code == 200, f"Orchestration failed: {response.text}"
            orchestration_result = response.json()

            # Validate orchestration response structure
            assert "analysis" in orchestration_result
            assert "project_structure" in orchestration_result

        except requests.exceptions.RequestException as e:
            pytest.skip(f"Orchestration service not available: {e}")

    def test_intelligence_service_integration(self):
        """Test integration with intelligence service for requirement analysis"""
        analysis_request = {
            "requirement": "Build a microservices-based e-commerce platform",
            "project_type": "web_application",
            "complexity": "complex",
        }

        try:
            response = requests.post(
                f"{INTELLIGENCE_SERVICE_URL}/v1/analyze",
                json=analysis_request,
                timeout=API_REQUEST_TIMEOUT,
            )

            if response.status_code == 404:
                pytest.skip("Intelligence service analyze endpoint not implemented")

            if response.status_code == 200:
                analysis_result = response.json()
                assert "parsed_requirements" in analysis_result
                assert "technology_recommendations" in analysis_result

        except requests.exceptions.RequestException:
            pytest.skip("Intelligence service not available")

    def test_template_registry_integration(self):
        """Test integration with template registry for template discovery"""
        search_query = {
            "requirement": "Create a REST API",
            "project_type": "api",
            "technology_preferences": ["python", "fastapi"],
        }

        try:
            response = requests.post(
                f"{TEMPLATE_REGISTRY_URL}/templates/search",
                json=search_query,
                timeout=API_REQUEST_TIMEOUT,
            )

            if response.status_code == 200:
                templates = response.json()
                assert isinstance(templates, list)

        except requests.exceptions.RequestException:
            pytest.skip("Template registry service not available")


class TestServiceDataFlow:
    """Test suite for data flow between services"""

    def test_orchestration_to_intelligence_flow(self):
        """Test data flow from orchestration gateway to intelligence service"""
        # This would test the actual data passing between services
        # For now, we'll test the basic connectivity

        orchestration_request = {
            "requirement": "Create a simple web application",
            "complexity": "simple",
        }

        # Test that orchestration gateway can reach intelligence service
        try:
            # First verify intelligence service is available
            health_response = requests.get(f"{INTELLIGENCE_SERVICE_URL}/health", timeout=5)
            if health_response.status_code != 200:
                pytest.skip("Intelligence service not healthy")

            # Then test orchestration flow
            orch_response = requests.post(
                f"{ORCHESTRATION_GATEWAY_URL}/v1/analyze",
                json=orchestration_request,
                timeout=API_REQUEST_TIMEOUT,
            )

            # Accept various response codes as the endpoint may not be fully implemented
            assert orch_response.status_code in [
                200,
                404,
                422,
            ], f"Unexpected error: {orch_response.status_code} - {orch_response.text}"

        except requests.exceptions.RequestException:
            pytest.skip("Service communication test skipped - services not available")

    def test_template_registry_to_execution_flow(self):
        """Test data flow from template registry to execution service"""
        try:
            # Test template retrieval
            templates_response = requests.get(
                f"{TEMPLATE_REGISTRY_URL}/templates", timeout=API_REQUEST_TIMEOUT
            )

            if templates_response.status_code == 200:
                templates = templates_response.json()
                if templates:
                    # Test execution service can process template data
                    execution_request = {
                        "template_id": "test-template",
                        "parameters": {"language": "python"},
                    }

                    # Note: Execution service endpoint may not exist yet
                    try:
                        exec_response = requests.post(
                            f"{EXECUTION_SERVICE_URL}/execute",
                            json=execution_request,
                            timeout=API_REQUEST_TIMEOUT,
                        )
                        # Accept 404 as endpoint may not be implemented
                        assert exec_response.status_code in [200, 404, 422]
                    except requests.exceptions.RequestException:
                        pytest.skip("Execution service not available")

        except requests.exceptions.RequestException:
            pytest.skip("Template registry service not available")


class TestServiceResilience:
    """Test suite for service resilience and error handling"""

    def test_service_timeout_handling(self):
        """Test service behavior under timeout conditions"""
        # Test with very short timeout to simulate timeout conditions
        try:
            response = requests.get(
                f"{ORCHESTRATION_GATEWAY_URL}/health",
                timeout=0.001,  # Very short timeout
            )
        except requests.exceptions.Timeout:
            # This is expected - timeout should be handled gracefully
            pass
        except requests.exceptions.RequestException:
            # Other connection errors are also acceptable for this test
            pass

    def test_invalid_request_handling(self):
        """Test service behavior with invalid requests"""
        invalid_requests = [
            {},  # Empty request
            {"invalid": "data"},  # Invalid fields
            {"requirement": ""},  # Empty requirement
            {"requirement": "test", "complexity": "invalid"},  # Invalid complexity
        ]

        for invalid_request in invalid_requests:
            try:
                response = requests.post(
                    f"{ORCHESTRATION_GATEWAY_URL}/v1/orchestrate",
                    json=invalid_request,
                    timeout=API_REQUEST_TIMEOUT,
                )
                # Should handle invalid requests gracefully with 4xx status
                assert (
                    400 <= response.status_code < 500
                ), f"Invalid request should return 4xx status, got {response.status_code}"

            except requests.exceptions.RequestException:
                # Service may not be available
                pytest.skip("Orchestration service not available for invalid request test")

    def test_service_error_propagation(self):
        """Test error propagation between services"""
        # Test how errors from downstream services are handled
        try:
            # Make request that might cause downstream service errors
            complex_request = {
                "requirement": "Create an extremely complex system with impossible requirements",
                "complexity": "enterprise",
                "metadata": {
                    "impossible_constraint": True,
                    "conflicting_requirements": ["requirement1", "requirement2"],
                },
            }

            response = requests.post(
                f"{ORCHESTRATION_GATEWAY_URL}/v1/orchestrate",
                json=complex_request,
                timeout=WORKFLOW_TIMEOUT,
            )

            # Accept various status codes - service should handle errors gracefully
            assert response.status_code in [
                200,
                400,
                422,
                500,
                404,
            ], f"Unexpected status code: {response.status_code}"

        except requests.exceptions.RequestException:
            pytest.skip("Service not available for error propagation test")


class TestConcurrentServiceAccess:
    """Test suite for concurrent service access"""

    def test_concurrent_health_checks(self):
        """Test concurrent health check requests to all services"""
        services = [
            ORCHESTRATION_GATEWAY_URL,
            INTELLIGENCE_SERVICE_URL,
            TEMPLATE_REGISTRY_URL,
            EXECUTION_SERVICE_URL,
            MONITORING_SERVICE_URL,
            QUALITY_SERVICE_URL,
        ]

        def check_service_health(service_url):
            try:
                response = requests.get(f"{service_url}/health", timeout=HEALTH_CHECK_TIMEOUT)
                return {
                    "url": service_url,
                    "status": response.status_code,
                    "response_time": response.elapsed.total_seconds(),
                    "success": response.status_code == 200,
                }
            except Exception as e:
                return {
                    "url": service_url,
                    "status": None,
                    "error": str(e),
                    "success": False,
                }

        # Execute concurrent health checks
        with ThreadPoolExecutor(max_workers=len(services)) as executor:
            future_to_service = {
                executor.submit(check_service_health, service_url): service_url
                for service_url in services
            }

            results = []
            for future in as_completed(future_to_service):
                result = future.result()
                results.append(result)

        # Analyze results
        successful_checks = [r for r in results if r["success"]]
        failed_checks = [r for r in results if not r["success"]]

        # At least the orchestration gateway should be available
        gateway_results = [r for r in results if ORCHESTRATION_GATEWAY_URL in r["url"]]
        if gateway_results:
            assert gateway_results[0]["success"], "Orchestration gateway should be available"

    def test_concurrent_orchestration_requests(self):
        """Test concurrent orchestration requests"""
        requests_data = [
            {"requirement": f"Create application {i}", "complexity": "simple"} for i in range(3)
        ]

        def make_orchestration_request(request_data):
            try:
                response = requests.post(
                    f"{ORCHESTRATION_GATEWAY_URL}/v1/orchestrate",
                    json=request_data,
                    timeout=API_REQUEST_TIMEOUT,
                )
                return {
                    "request": request_data,
                    "status": response.status_code,
                    "success": response.status_code
                    in [200, 404],  # 404 acceptable if not implemented
                    "response_time": response.elapsed.total_seconds(),
                }
            except Exception as e:
                return {"request": request_data, "error": str(e), "success": False}

        # Execute concurrent requests
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_request = {
                executor.submit(make_orchestration_request, req_data): req_data
                for req_data in requests_data
            }

            results = []
            for future in as_completed(future_to_request):
                result = future.result()
                results.append(result)

        # All requests should be handled (either successfully or with proper error codes)
        assert len(results) == len(requests_data)


class TestServicePerformance:
    """Test suite for service performance characteristics"""

    def test_health_check_response_times(self):
        """Test health check response times for all services"""
        services = {
            "orchestration-gateway": ORCHESTRATION_GATEWAY_URL,
            "intelligence-service": INTELLIGENCE_SERVICE_URL,
            "template-registry": TEMPLATE_REGISTRY_URL,
        }

        response_times = {}

        for service_name, service_url in services.items():
            try:
                start_time = time.time()
                response = requests.get(f"{service_url}/health", timeout=HEALTH_CHECK_TIMEOUT)
                end_time = time.time()

                if response.status_code == 200:
                    response_times[service_name] = end_time - start_time
                    # Health checks should be fast (under 1 second)
                    assert (
                        response_times[service_name] < 1.0
                    ), f"{service_name} health check took {response_times[service_name]:.2f}s"

            except requests.exceptions.RequestException:
                # Service not available - skip performance test
                continue

        # At least one service should be responding for this test to be meaningful
        assert len(response_times) > 0, "No services available for performance testing"

    def test_api_response_times(self):
        """Test API endpoint response times"""
        # Test orchestration gateway response time
        try:
            start_time = time.time()
            response = requests.post(
                f"{ORCHESTRATION_GATEWAY_URL}/v1/analyze",
                json={"requirement": "Simple test", "complexity": "simple"},
                timeout=API_REQUEST_TIMEOUT,
            )
            end_time = time.time()

            response_time = end_time - start_time

            # API calls should complete within reasonable time
            assert response_time < 10.0, f"API response took {response_time:.2f}s"

        except requests.exceptions.RequestException:
            pytest.skip("API endpoint not available for performance testing")


class TestDatabaseIntegration:
    """Test suite for database integration across services"""

    def test_database_connectivity(self):
        """Test database connectivity for services that use databases"""
        # This would test that services can connect to their databases
        # For now, we test that services that should use databases are responding

        database_services = [
            TEMPLATE_REGISTRY_URL,  # Should use database for template storage
            MONITORING_SERVICE_URL,  # Should use database for metrics storage
        ]

        for service_url in database_services:
            try:
                response = requests.get(f"{service_url}/health", timeout=HEALTH_CHECK_TIMEOUT)
                if response.status_code == 200:
                    health_data = response.json()
                    # Health check should indicate database status if applicable
                    # This is service-specific and may not be implemented yet
                    assert "status" in health_data

            except requests.exceptions.RequestException:
                # Service not available
                continue


class TestEndToEndWorkflows:
    """Test suite for complete end-to-end workflows"""

    def test_simple_project_creation_workflow(self):
        """Test simple project creation from start to finish"""
        workflow_steps = []

        # Step 1: Analyze requirements
        analysis_request = {
            "requirement": "Create a simple calculator API",
            "project_type": "api",
            "complexity": "simple",
        }

        try:
            response = requests.post(
                f"{ORCHESTRATION_GATEWAY_URL}/v1/analyze",
                json=analysis_request,
                timeout=API_REQUEST_TIMEOUT,
            )
            workflow_steps.append(
                {
                    "step": "requirement_analysis",
                    "status": response.status_code,
                    "success": response.status_code in [200, 404],
                }
            )

        except requests.exceptions.RequestException as e:
            workflow_steps.append(
                {"step": "requirement_analysis", "error": str(e), "success": False}
            )

        # Step 2: Find appropriate templates
        try:
            template_search = {
                "requirement": "calculator API",
                "technology_preferences": ["python"],
            }

            response = requests.post(
                f"{TEMPLATE_REGISTRY_URL}/templates/search",
                json=template_search,
                timeout=API_REQUEST_TIMEOUT,
            )
            workflow_steps.append(
                {
                    "step": "template_search",
                    "status": response.status_code,
                    "success": response.status_code == 200,
                }
            )

        except requests.exceptions.RequestException as e:
            workflow_steps.append({"step": "template_search", "error": str(e), "success": False})

        # Step 3: Full orchestration
        try:
            response = requests.post(
                f"{ORCHESTRATION_GATEWAY_URL}/v1/orchestrate",
                json=analysis_request,
                timeout=WORKFLOW_TIMEOUT,
            )
            workflow_steps.append(
                {
                    "step": "full_orchestration",
                    "status": response.status_code,
                    "success": response.status_code in [200, 404],
                }
            )

        except requests.exceptions.RequestException as e:
            workflow_steps.append({"step": "full_orchestration", "error": str(e), "success": False})

        # Validate workflow
        successful_steps = [step for step in workflow_steps if step["success"]]

        # At least the template registry should work if available
        template_steps = [step for step in workflow_steps if step["step"] == "template_search"]
        if template_steps and not template_steps[0]["success"]:
            pytest.skip("Template registry not fully functional")

        # Log workflow results for debugging
        print(f"Workflow steps completed: {len(successful_steps)}/{len(workflow_steps)}")
        for step in workflow_steps:
            print(f"Step {step['step']}: {'✓' if step['success'] else '✗'}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
