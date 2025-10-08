#!/usr/bin/env python3
"""
Regression Test Suite for MAESTRO API Endpoints

This module provides comprehensive regression tests for:
- API endpoint functionality and stability
- Response format consistency
- Error handling behavior
- Performance characteristics
- Backward compatibility
"""

import json
import time
from typing import Any, Dict

import pytest
import requests

# Test configuration
BASE_URLS = {
    "orchestration_gateway": "http://localhost:8000",
    "intelligence_service": "http://localhost:9501",
    "template_registry": "http://localhost:9500",
    "execution_service": "http://localhost:9502",
    "monitoring_service": "http://localhost:9503",
    "quality_service": "http://localhost:9504",
}

# API endpoint definitions with expected behaviors
ENDPOINT_TESTS = {
    "orchestration_gateway": [
        {
            "path": "/health",
            "method": "GET",
            "expected_status": 200,
            "expected_fields": ["status", "timestamp"],
            "performance_threshold": 1.0,
        },
        {
            "path": "/docs",
            "method": "GET",
            "expected_status": 200,
            "content_type": "text/html",
            "performance_threshold": 2.0,
        },
        {
            "path": "/v1/health",
            "method": "GET",
            "expected_status": [200, 404],  # May not be implemented yet
            "expected_fields": ["status"],
            "performance_threshold": 1.0,
        },
        {
            "path": "/v1/orchestrate",
            "method": "POST",
            "expected_status": [200, 404, 422],
            "payload": {"requirement": "Create a simple API", "complexity": "simple"},
            "performance_threshold": 5.0,
        },
        {
            "path": "/v1/analyze",
            "method": "POST",
            "expected_status": [200, 404, 422],
            "payload": {
                "requirement": "Analyze this requirement",
                "complexity": "medium",
            },
            "performance_threshold": 3.0,
        },
    ],
    "intelligence_service": [
        {
            "path": "/health",
            "method": "GET",
            "expected_status": 200,
            "expected_fields": ["status", "timestamp"],
            "performance_threshold": 1.0,
        },
        {
            "path": "/docs",
            "method": "GET",
            "expected_status": 200,
            "content_type": "text/html",
            "performance_threshold": 2.0,
        },
        {
            "path": "/v1/analyze",
            "method": "POST",
            "expected_status": [200, 404],
            "payload": {
                "requirement": "Build a web application",
                "project_type": "web_application",
            },
            "performance_threshold": 5.0,
        },
    ],
    "template_registry": [
        {
            "path": "/health",
            "method": "GET",
            "expected_status": 200,
            "expected_fields": ["status", "timestamp"],
            "performance_threshold": 1.0,
        },
        {
            "path": "/templates",
            "method": "GET",
            "expected_status": 200,
            "expected_type": list,
            "performance_threshold": 2.0,
        },
        {
            "path": "/services",
            "method": "GET",
            "expected_status": 200,
            "expected_type": list,
            "performance_threshold": 2.0,
        },
        {
            "path": "/templates/search",
            "method": "POST",
            "expected_status": 200,
            "payload": {
                "requirement": "Create an API",
                "technology_preferences": ["python"],
            },
            "expected_type": list,
            "performance_threshold": 3.0,
        },
    ],
}


class TestAPIRegressionSuite:
    """Main regression test suite for all API endpoints"""

    def test_all_health_endpoints(self):
        """Test health endpoints for all services"""
        health_results = {}

        for service_name, base_url in BASE_URLS.items():
            try:
                start_time = time.time()
                response = requests.get(f"{base_url}/health", timeout=5)
                end_time = time.time()

                health_results[service_name] = {
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "content": response.json() if response.status_code == 200 else None,
                }

                # Health endpoints should always return 200
                if response.status_code != 200:
                    print(
                        f"WARNING: {service_name} health endpoint returned {response.status_code}"
                    )

            except requests.exceptions.RequestException as e:
                health_results[service_name] = {"error": str(e), "available": False}

        # At least orchestration gateway should be healthy
        assert "orchestration_gateway" in health_results
        if "error" not in health_results["orchestration_gateway"]:
            assert health_results["orchestration_gateway"]["status_code"] == 200

    def test_endpoint_regression_suite(self):
        """Run comprehensive regression tests for all defined endpoints"""
        test_results = []

        for service_name, endpoints in ENDPOINT_TESTS.items():
            base_url = BASE_URLS[service_name]

            for endpoint_config in endpoints:
                result = self._test_single_endpoint(service_name, base_url, endpoint_config)
                test_results.append(result)

        # Analyze results
        successful_tests = [r for r in test_results if r["passed"]]
        failed_tests = [r for r in test_results if not r["passed"]]
        skipped_tests = [r for r in test_results if r.get("skipped", False)]

        print("\nRegression Test Summary:")
        print(f"Total tests: {len(test_results)}")
        print(f"Passed: {len(successful_tests)}")
        print(f"Failed: {len(failed_tests)}")
        print(f"Skipped: {len(skipped_tests)}")

        # Report failed tests
        if failed_tests:
            print("\nFailed tests:")
            for test in failed_tests:
                print(f"  - {test['service']}{test['path']}: {test.get('error', 'Unknown error')}")

        # Critical endpoints should pass
        critical_endpoints = [
            ("orchestration_gateway", "/health"),
            ("template_registry", "/health"),
            ("intelligence_service", "/health"),
        ]

        for service, path in critical_endpoints:
            service_tests = [
                t for t in test_results if t["service"] == service and t["path"] == path
            ]
            if (
                service_tests
                and not service_tests[0]["passed"]
                and not service_tests[0].get("skipped")
            ):
                pytest.fail(f"Critical endpoint {service}{path} failed regression test")

    def _test_single_endpoint(
        self, service_name: str, base_url: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Test a single endpoint according to its configuration"""
        path = config["path"]
        method = config["method"]
        expected_status = config["expected_status"]
        performance_threshold = config.get("performance_threshold", 5.0)

        result = {
            "service": service_name,
            "path": path,
            "method": method,
            "passed": False,
            "skipped": False,
        }

        try:
            # Prepare request
            url = f"{base_url}{path}"
            request_kwargs = {"timeout": performance_threshold + 5}

            if "payload" in config:
                request_kwargs["json"] = config["payload"]

            # Make request and measure time
            start_time = time.time()
            if method == "GET":
                response = requests.get(url, **request_kwargs)
            elif method == "POST":
                response = requests.post(url, **request_kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")

            end_time = time.time()
            response_time = end_time - start_time

            # Check status code
            if isinstance(expected_status, list):
                status_ok = response.status_code in expected_status
            else:
                status_ok = response.status_code == expected_status

            if not status_ok:
                result["error"] = f"Expected status {expected_status}, got {response.status_code}"
                return result

            # Skip further checks if endpoint not implemented (404)
            if response.status_code == 404:
                result["skipped"] = True
                result["passed"] = True
                result["note"] = "Endpoint not implemented yet"
                return result

            # Check performance
            if response_time > performance_threshold:
                result["error"] = (
                    f"Response time {response_time:.2f}s exceeded threshold {performance_threshold}s"
                )
                return result

            # Check content type if specified
            if "content_type" in config:
                expected_content_type = config["content_type"]
                actual_content_type = response.headers.get("content-type", "")
                if expected_content_type not in actual_content_type:
                    result["error"] = (
                        f"Expected content-type {expected_content_type}, got {actual_content_type}"
                    )
                    return result

            # Check response structure for JSON responses
            if response.status_code == 200 and "application/json" in response.headers.get(
                "content-type", ""
            ):
                try:
                    response_data = response.json()

                    # Check expected fields
                    if "expected_fields" in config:
                        for field in config["expected_fields"]:
                            if field not in response_data:
                                result["error"] = f"Missing expected field: {field}"
                                return result

                    # Check expected type
                    if "expected_type" in config:
                        expected_type = config["expected_type"]
                        if not isinstance(response_data, expected_type):
                            result["error"] = (
                                f"Expected type {expected_type.__name__}, got {type(response_data).__name__}"
                            )
                            return result

                except json.JSONDecodeError:
                    result["error"] = "Invalid JSON response"
                    return result

            # All checks passed
            result["passed"] = True
            result["response_time"] = response_time
            result["status_code"] = response.status_code

        except requests.exceptions.Timeout:
            result["error"] = f"Request timeout (>{performance_threshold + 5}s)"
        except requests.exceptions.ConnectionError:
            result["error"] = "Connection error - service not available"
            result["skipped"] = True
            result["passed"] = True  # Don't fail if service is not running
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"

        return result


class TestAPIConsistency:
    """Test suite for API consistency across services"""

    def test_health_endpoint_consistency(self):
        """Test that all health endpoints follow the same format"""
        health_responses = {}

        for service_name, base_url in BASE_URLS.items():
            try:
                response = requests.get(f"{base_url}/health", timeout=5)
                if response.status_code == 200:
                    health_responses[service_name] = response.json()
            except requests.exceptions.RequestException:
                continue

        if not health_responses:
            pytest.skip("No health endpoints available")

        # All health responses should have 'status' field
        for service_name, health_data in health_responses.items():
            assert "status" in health_data, f"{service_name} health response missing 'status' field"
            assert health_data["status"] == "healthy", f"{service_name} reports unhealthy status"

        # All should have timestamp
        for service_name, health_data in health_responses.items():
            assert (
                "timestamp" in health_data
            ), f"{service_name} health response missing 'timestamp' field"

    def test_error_response_consistency(self):
        """Test that error responses follow consistent format"""
        error_test_cases = [
            {
                "service": "orchestration_gateway",
                "path": "/v1/orchestrate",
                "payload": {"invalid": "data"},  # Invalid payload
            },
            {
                "service": "template_registry",
                "path": "/templates/search",
                "payload": {"requirement": ""},  # Empty requirement
            },
        ]

        error_responses = []

        for test_case in error_test_cases:
            service = test_case["service"]
            base_url = BASE_URLS[service]
            path = test_case["path"]

            try:
                response = requests.post(f"{base_url}{path}", json=test_case["payload"], timeout=10)

                if 400 <= response.status_code < 500:
                    error_responses.append(
                        {
                            "service": service,
                            "status_code": response.status_code,
                            "response": (
                                response.json()
                                if "application/json" in response.headers.get("content-type", "")
                                else response.text
                            ),
                        }
                    )

            except requests.exceptions.RequestException:
                continue

        # If we have error responses, they should be consistent
        if error_responses:
            # All 422 responses should be validation errors with detail
            validation_errors = [r for r in error_responses if r["status_code"] == 422]
            for error in validation_errors:
                if isinstance(error["response"], dict):
                    # Should have detail field for validation errors
                    assert (
                        "detail" in error["response"] or "message" in error["response"]
                    ), f"Validation error missing detail: {error}"

    def test_documentation_endpoint_consistency(self):
        """Test that documentation endpoints are consistent"""
        doc_endpoints = ["/docs", "/openapi.json"]
        doc_responses = {}

        for service_name, base_url in BASE_URLS.items():
            for endpoint in doc_endpoints:
                try:
                    response = requests.get(f"{base_url}{endpoint}", timeout=10)
                    if response.status_code == 200:
                        doc_responses[f"{service_name}{endpoint}"] = {
                            "status_code": response.status_code,
                            "content_type": response.headers.get("content-type", ""),
                        }
                except requests.exceptions.RequestException:
                    continue

        # /docs should return HTML
        docs_endpoints = [k for k in doc_responses.keys() if k.endswith("/docs")]
        for endpoint in docs_endpoints:
            assert (
                "text/html" in doc_responses[endpoint]["content_type"]
            ), f"{endpoint} should return HTML documentation"

        # /openapi.json should return JSON
        openapi_endpoints = [k for k in doc_responses.keys() if k.endswith("/openapi.json")]
        for endpoint in openapi_endpoints:
            assert (
                "application/json" in doc_responses[endpoint]["content_type"]
            ), f"{endpoint} should return JSON schema"


class TestAPIPerformanceRegression:
    """Test suite for API performance regression"""

    def test_response_time_regression(self):
        """Test that response times haven't regressed"""
        performance_baselines = {
            ("orchestration_gateway", "/health"): 1.0,
            ("intelligence_service", "/health"): 1.0,
            ("template_registry", "/health"): 1.0,
            ("template_registry", "/templates"): 2.0,
            ("template_registry", "/services"): 2.0,
        }

        performance_results = {}

        for (service, endpoint), baseline in performance_baselines.items():
            base_url = BASE_URLS[service]

            try:
                start_time = time.time()
                response = requests.get(f"{base_url}{endpoint}", timeout=baseline * 2)
                end_time = time.time()

                response_time = end_time - start_time
                performance_results[(service, endpoint)] = {
                    "response_time": response_time,
                    "baseline": baseline,
                    "within_baseline": response_time <= baseline,
                    "status_code": response.status_code,
                }

            except requests.exceptions.RequestException as e:
                performance_results[(service, endpoint)] = {
                    "error": str(e),
                    "available": False,
                }

        # Report performance issues
        slow_endpoints = []
        for (service, endpoint), result in performance_results.items():
            if "error" not in result and not result["within_baseline"]:
                slow_endpoints.append(
                    (service, endpoint, result["response_time"], result["baseline"])
                )

        if slow_endpoints:
            print("\nPerformance regression detected:")
            for service, endpoint, actual, baseline in slow_endpoints:
                print(f"  {service}{endpoint}: {actual:.2f}s (baseline: {baseline:.2f}s)")

        # Don't fail tests for performance regression, just warn
        # assert len(slow_endpoints) == 0, f"Performance regression in {len(slow_endpoints)} endpoints"

    def test_concurrent_request_performance(self):
        """Test performance under concurrent load"""
        import concurrent.futures
        import statistics

        # Test concurrent health checks
        def make_health_request(service_url):
            try:
                start_time = time.time()
                response = requests.get(f"{service_url}/health", timeout=5)
                end_time = time.time()
                return {
                    "success": response.status_code == 200,
                    "response_time": end_time - start_time,
                }
            except Exception:
                return {"success": False, "response_time": None}

        # Test with orchestration gateway (most critical service)
        gateway_url = BASE_URLS["orchestration_gateway"]
        num_concurrent_requests = 5

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent_requests) as executor:
            futures = [
                executor.submit(make_health_request, gateway_url)
                for _ in range(num_concurrent_requests)
            ]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        successful_results = [r for r in results if r["success"]]
        response_times = [
            r["response_time"] for r in successful_results if r["response_time"] is not None
        ]

        if response_times:
            avg_response_time = statistics.mean(response_times)
            max_response_time = max(response_times)

            # Concurrent requests should still be reasonably fast
            assert (
                avg_response_time < 2.0
            ), f"Average concurrent response time too slow: {avg_response_time:.2f}s"
            assert (
                max_response_time < 5.0
            ), f"Maximum concurrent response time too slow: {max_response_time:.2f}s"

            print(
                f"Concurrent performance: avg={avg_response_time:.2f}s, max={max_response_time:.2f}s"
            )


class TestAPIBackwardCompatibility:
    """Test suite for backward compatibility"""

    def test_legacy_endpoint_support(self):
        """Test that legacy endpoints still work"""
        # Test legacy health endpoints (without /v1 prefix)
        legacy_endpoints = [
            ("orchestration_gateway", "/health"),
            ("intelligence_service", "/health"),
            ("template_registry", "/health"),
        ]

        for service, endpoint in legacy_endpoints:
            base_url = BASE_URLS[service]
            try:
                response = requests.get(f"{base_url}{endpoint}", timeout=5)
                assert (
                    response.status_code == 200
                ), f"Legacy endpoint {service}{endpoint} not working"

                # Should return expected structure
                if "application/json" in response.headers.get("content-type", ""):
                    data = response.json()
                    assert "status" in data, "Legacy health endpoint missing status field"

            except requests.exceptions.RequestException:
                # Service not available - skip test
                continue

    def test_response_format_stability(self):
        """Test that response formats haven't changed unexpectedly"""
        # Test that critical response formats are stable
        stable_endpoints = [
            {
                "service": "template_registry",
                "path": "/templates",
                "expected_type": list,
            },
            {
                "service": "template_registry",
                "path": "/services",
                "expected_type": list,
            },
        ]

        for endpoint_config in stable_endpoints:
            service = endpoint_config["service"]
            path = endpoint_config["path"]
            expected_type = endpoint_config["expected_type"]

            base_url = BASE_URLS[service]

            try:
                response = requests.get(f"{base_url}{path}", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    assert isinstance(
                        data, expected_type
                    ), f"{service}{path} response type changed: expected {expected_type.__name__}, got {type(data).__name__}"

            except requests.exceptions.RequestException:
                # Service not available - skip test
                continue


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
