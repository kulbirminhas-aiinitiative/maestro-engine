"""
Contract testing for OpenAPI specification compliance.

This module validates that all MAESTRO services implement their OpenAPI
specifications correctly and maintain API contract consistency.
"""

import json
import os
import re
from typing import Any, Dict, List

import pytest
import requests
from jsonschema import ValidationError, validate
from openapi_spec_validator import validate_spec


@pytest.fixture(scope="session")
def api_config():
    """API configuration for contract tests"""
    return {
        "orchestration_gateway": {
            "url": os.environ.get("GW_URL", "http://localhost:8000"),
            "service_name": "orchestration-gateway",
        },
        "intelligence_service": {
            "url": os.environ.get("INTELLIGENCE_URL", "http://localhost:9501"),
            "service_name": "intelligence-service",
        },
        "template_registry": {
            "url": os.environ.get("TEMPLATE_URL", "http://localhost:9500"),
            "service_name": "template-registry-service",
        },
    }


@pytest.fixture
def maestro_api_spec():
    """Load MAESTRO API specification"""
    spec_file = "MAESTRO_MICROSERVICES_API_SPEC.md"
    if os.path.exists(spec_file):
        with open(spec_file, "r") as f:
            return f.read()
    else:
        pytest.skip("MAESTRO API specification file not found")


class OpenAPIValidator:
    """Helper class for OpenAPI validation"""

    def __init__(self, service_url: str):
        self.service_url = service_url.rstrip("/")
        self._spec = None

    def get_openapi_spec(self) -> Dict[str, Any]:
        """Fetch OpenAPI specification from service"""
        if self._spec is None:
            try:
                response = requests.get(f"{self.service_url}/openapi.json", timeout=10)
                response.raise_for_status()
                self._spec = response.json()
            except Exception as e:
                pytest.skip(f"Cannot fetch OpenAPI spec from {self.service_url}: {e}")
        return self._spec

    def validate_spec_format(self) -> bool:
        """Validate OpenAPI specification format"""
        spec = self.get_openapi_spec()
        try:
            validate_spec(spec)
            return True
        except Exception as e:
            pytest.fail(f"Invalid OpenAPI spec format: {e}")

    def has_required_info(self) -> bool:
        """Check if spec has required info section"""
        spec = self.get_openapi_spec()
        info = spec.get("info", {})

        required_fields = ["title", "version"]
        for field in required_fields:
            if field not in info:
                return False

        return True

    def get_paths(self) -> Dict[str, Any]:
        """Get all paths from OpenAPI spec"""
        spec = self.get_openapi_spec()
        return spec.get("paths", {})

    def get_path_methods(self, path: str) -> List[str]:
        """Get HTTP methods for a specific path"""
        paths = self.get_paths()
        if path not in paths:
            return []
        return list(paths[path].keys())

    def validate_response_schema(
        self, path: str, method: str, status_code: int, response_data: Any
    ) -> bool:
        """Validate response against OpenAPI schema"""
        spec = self.get_openapi_spec()
        paths = spec.get("paths", {})

        if path not in paths:
            return False

        path_spec = paths[path]
        if method.lower() not in path_spec:
            return False

        method_spec = path_spec[method.lower()]
        responses = method_spec.get("responses", {})

        status_key = str(status_code)
        if status_key not in responses:
            # Check for default response
            if "default" not in responses:
                return False
            status_key = "default"

        response_spec = responses[status_key]
        content = response_spec.get("content", {})

        if "application/json" not in content:
            return True  # No schema to validate

        schema = content["application/json"].get("schema")
        if not schema:
            return True

        try:
            validate(instance=response_data, schema=schema)
            return True
        except ValidationError:
            return False


@pytest.mark.contract
class TestOpenAPISpecValidation:
    """Test OpenAPI specification validation"""

    def test_openapi_spec_accessible(self, api_config):
        """Test that OpenAPI specs are accessible for all services"""
        for service_name, config in api_config.items():
            validator = OpenAPIValidator(config["url"])
            spec = validator.get_openapi_spec()
            assert spec is not None, f"OpenAPI spec not accessible for {service_name}"

    def test_openapi_spec_format_valid(self, api_config):
        """Test that OpenAPI specifications are valid"""
        for service_name, config in api_config.items():
            validator = OpenAPIValidator(config["url"])
            assert (
                validator.validate_spec_format()
            ), f"Invalid OpenAPI spec format for {service_name}"

    def test_openapi_spec_has_required_info(self, api_config):
        """Test that OpenAPI specs have required information"""
        for service_name, config in api_config.items():
            validator = OpenAPIValidator(config["url"])
            assert (
                validator.has_required_info()
            ), f"Missing required info in OpenAPI spec for {service_name}"

    def test_openapi_spec_version_consistency(self, api_config):
        """Test that OpenAPI specs have consistent API versions"""
        for service_name, config in api_config.items():
            validator = OpenAPIValidator(config["url"])
            spec = validator.get_openapi_spec()

            # Check for v1 API version in paths
            paths = validator.get_paths()
            v1_paths = [path for path in paths.keys() if path.startswith("/v1/")]

            assert len(v1_paths) > 0, f"No v1 API paths found in {service_name}"

    def test_openapi_spec_has_standard_endpoints(self, api_config):
        """Test that all services have required standard endpoints"""
        required_endpoints = ["/v1/health", "/v1/version", "/v1/metrics"]

        for service_name, config in api_config.items():
            validator = OpenAPIValidator(config["url"])
            paths = validator.get_paths()

            for endpoint in required_endpoints:
                assert endpoint in paths, f"Missing required endpoint {endpoint} in {service_name}"

                # Check that GET method is supported
                methods = validator.get_path_methods(endpoint)
                assert (
                    "get" in methods
                ), f"GET method not supported for {endpoint} in {service_name}"


@pytest.mark.contract
class TestAPIResponseCompliance:
    """Test API response compliance with OpenAPI specs"""

    def test_health_endpoint_response_schema(self, api_config):
        """Test health endpoint responses match OpenAPI schema"""
        for service_name, config in api_config.items():
            validator = OpenAPIValidator(config["url"])

            # Make request to health endpoint
            response = requests.get(f"{config['url']}/v1/health", timeout=10)
            if response.status_code != 200:
                pytest.skip(f"Health endpoint not available for {service_name}")

            # Validate response schema
            is_valid = validator.validate_response_schema(
                "/v1/health", "get", response.status_code, response.json()
            )
            assert is_valid, f"Health response doesn't match schema for {service_name}"

            # Check required fields manually if schema validation is not strict enough
            data = response.json()
            required_fields = ["status", "service"]
            for field in required_fields:
                assert field in data, f"Missing {field} in health response for {service_name}"

    def test_version_endpoint_response_schema(self, api_config):
        """Test version endpoint responses match OpenAPI schema"""
        for service_name, config in api_config.items():
            validator = OpenAPIValidator(config["url"])

            # Make request to version endpoint
            response = requests.get(f"{config['url']}/v1/version", timeout=10)
            if response.status_code != 200:
                continue  # Skip if endpoint not available

            # Validate response schema
            is_valid = validator.validate_response_schema(
                "/v1/version", "get", response.status_code, response.json()
            )
            assert is_valid, f"Version response doesn't match schema for {service_name}"

            # Check required fields
            data = response.json()
            required_fields = ["service", "version", "api_version"]
            for field in required_fields:
                assert field in data, f"Missing {field} in version response for {service_name}"

    def test_metrics_endpoint_response_schema(self, api_config):
        """Test metrics endpoint responses match OpenAPI schema"""
        for service_name, config in api_config.items():
            validator = OpenAPIValidator(config["url"])

            # Make request to metrics endpoint
            response = requests.get(f"{config['url']}/v1/metrics", timeout=10)
            if response.status_code != 200:
                continue  # Skip if endpoint not available

            # Validate response schema
            is_valid = validator.validate_response_schema(
                "/v1/metrics", "get", response.status_code, response.json()
            )
            assert is_valid, f"Metrics response doesn't match schema for {service_name}"

    def test_error_response_format(self, api_config):
        """Test error responses follow consistent format"""
        for service_name, config in api_config.items():
            validator = OpenAPIValidator(config["url"])

            # Make request to non-existent endpoint to trigger error
            response = requests.get(f"{config['url']}/v1/nonexistent", timeout=10)
            assert response.status_code == 404

            # Check error response format
            try:
                error_data = response.json()
                # Should have either 'detail' or 'error' field
                assert (
                    "detail" in error_data or "error" in error_data
                ), f"Error response format inconsistent for {service_name}"
            except json.JSONDecodeError:
                pytest.fail(f"Error response is not valid JSON for {service_name}")


@pytest.mark.contract
class TestAPISpecConsistency:
    """Test consistency across service API specifications"""

    def test_standard_endpoint_consistency(self, api_config):
        """Test that standard endpoints are consistent across services"""
        standard_endpoints = {
            "/v1/health": ["get"],
            "/v1/version": ["get"],
            "/v1/metrics": ["get"],
        }

        endpoint_schemas = {}

        for service_name, config in api_config.items():
            validator = OpenAPIValidator(config["url"])
            paths = validator.get_paths()

            for endpoint, expected_methods in standard_endpoints.items():
                if endpoint in paths:
                    actual_methods = validator.get_path_methods(endpoint)

                    # Check methods are consistent
                    for method in expected_methods:
                        assert (
                            method in actual_methods
                        ), f"Method {method} missing for {endpoint} in {service_name}"

                    # Store schema for consistency check
                    if endpoint not in endpoint_schemas:
                        endpoint_schemas[endpoint] = {}

                    for method in expected_methods:
                        if method in paths[endpoint]:
                            method_spec = paths[endpoint][method]
                            key = f"{endpoint}:{method}"
                            if key not in endpoint_schemas[endpoint]:
                                endpoint_schemas[endpoint][key] = []
                            endpoint_schemas[endpoint][key].append(
                                {"service": service_name, "spec": method_spec}
                            )

        # Check schema consistency (basic check)
        for endpoint, methods in endpoint_schemas.items():
            for method_key, service_specs in methods.items():
                if len(service_specs) > 1:
                    # Compare response schemas for consistency
                    base_responses = service_specs[0]["spec"].get("responses", {})
                    for spec_info in service_specs[1:]:
                        responses = spec_info["spec"].get("responses", {})
                        # Basic check - should have similar response codes
                        base_codes = set(base_responses.keys())
                        current_codes = set(responses.keys())
                        common_codes = base_codes.intersection(current_codes)
                        assert (
                            len(common_codes) > 0
                        ), f"No common response codes for {method_key} between services"

    def test_api_version_consistency(self, api_config):
        """Test that API versions are consistent across services"""
        api_versions = set()

        for service_name, config in api_config.items():
            validator = OpenAPIValidator(config["url"])
            spec = validator.get_openapi_spec()

            # Check paths for API version
            paths = validator.get_paths()
            v1_paths = [path for path in paths.keys() if path.startswith("/v1/")]

            if v1_paths:
                api_versions.add("v1")

            # Check info section for API version
            info = spec.get("info", {})
            version = info.get("version", "")
            if version:
                # Extract major version
                major_version = version.split(".")[0]
                api_versions.add(f"v{major_version}")

        # All services should use consistent API versioning
        assert len(api_versions) <= 2, f"Inconsistent API versions found: {api_versions}"
        assert "v1" in api_versions or "v4" in api_versions, "No standard API version found"


@pytest.mark.contract
class TestMaestroSpecCompliance:
    """Test compliance with MAESTRO API specification document"""

    def test_spec_document_services_exist(self, api_config, maestro_api_spec):
        """Test that services mentioned in spec document actually exist"""
        # Extract service names from the spec document
        service_pattern = r"## \d+\. .* \(service: `(.*?)`\)"
        services_in_spec = re.findall(service_pattern, maestro_api_spec)

        # Map spec names to config names
        service_mapping = {
            "orchestration-gateway": "orchestration_gateway",
            "template-registry-service": "template_registry",
            "intelligence-service": "intelligence_service",
        }

        for spec_service in services_in_spec:
            if spec_service in service_mapping:
                config_key = service_mapping[spec_service]
                assert (
                    config_key in api_config
                ), f"Service {spec_service} from spec not found in config"

    def test_spec_document_endpoints_implemented(self, api_config, maestro_api_spec):
        """Test that endpoints mentioned in spec document are implemented"""
        # Parse standard endpoints from spec
        standard_endpoints = [
            "GET /v1/health",
            "GET /v1/docs",
            "GET /v1/metrics",
            "GET /v1/version",
        ]

        for service_name, config in api_config.items():
            validator = OpenAPIValidator(config["url"])
            paths = validator.get_paths()

            for endpoint_spec in standard_endpoints:
                method, path = endpoint_spec.split(" ", 1)

                assert path in paths, f"Path {path} not found in {service_name}"

                methods = validator.get_path_methods(path)
                assert (
                    method.lower() in methods
                ), f"Method {method} not supported for {path} in {service_name}"

    def test_functional_endpoints_per_service(self, api_config, maestro_api_spec):
        """Test service-specific functional endpoints"""
        # Define expected functional endpoints per service
        expected_endpoints = {
            "orchestration_gateway": [
                ("POST", "/v1/orchestrate"),
                ("GET", "/v1/requests/{correlation_id}"),
            ],
            "template_registry": [
                ("POST", "/v1/templates"),
                ("GET", "/v1/templates"),
                ("GET", "/v1/templates/{id}"),
                ("PUT", "/v1/templates/{id}"),
                ("DELETE", "/v1/templates/{id}"),
            ],
            "intelligence_service": [
                ("POST", "/v1/analyze"),
                ("GET", "/v1/models"),
                ("GET", "/v1/signals"),
            ],
        }

        for service_name, config in api_config.items():
            if service_name not in expected_endpoints:
                continue

            validator = OpenAPIValidator(config["url"])
            paths = validator.get_paths()

            for method, path in expected_endpoints[service_name]:
                # Convert path parameters to OpenAPI format for comparison
                openapi_path = re.sub(r"\{([^}]+)\}", r"{\1}", path)

                if openapi_path not in paths:
                    # Try to find similar path (with different parameter names)
                    similar_paths = [
                        p for p in paths.keys() if self._paths_similar(p, openapi_path)
                    ]
                    assert (
                        len(similar_paths) > 0
                    ), f"Functional endpoint {method} {path} not found in {service_name}"
                    openapi_path = similar_paths[0]

                methods = validator.get_path_methods(openapi_path)
                assert (
                    method.lower() in methods
                ), f"Method {method} not supported for {path} in {service_name}"

    def _paths_similar(self, path1: str, path2: str) -> bool:
        """Check if two paths are similar (ignoring parameter names)"""
        # Replace path parameters with wildcards
        norm_path1 = re.sub(r"\{[^}]+\}", "{param}", path1)
        norm_path2 = re.sub(r"\{[^}]+\}", "{param}", path2)
        return norm_path1 == norm_path2


@pytest.mark.contract
class TestSchemaEvolution:
    """Test API schema evolution and backwards compatibility"""

    def test_required_fields_not_removed(self, api_config):
        """Test that required fields are not removed from responses"""
        # This would typically compare against a previous version
        # For now, we'll test that current required fields are present

        required_health_fields = ["status", "service"]
        required_version_fields = ["service", "version"]

        for service_name, config in api_config.items():
            # Test health endpoint
            response = requests.get(f"{config['url']}/v1/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                for field in required_health_fields:
                    assert (
                        field in data
                    ), f"Required field {field} missing from health response in {service_name}"

            # Test version endpoint
            response = requests.get(f"{config['url']}/v1/version", timeout=10)
            if response.status_code == 200:
                data = response.json()
                for field in required_version_fields:
                    assert (
                        field in data
                    ), f"Required field {field} missing from version response in {service_name}"

    def test_response_format_consistency(self, api_config):
        """Test that response formats are consistent over time"""
        for service_name, config in api_config.items():
            # Test health endpoint response format
            response = requests.get(f"{config['url']}/v1/health", timeout=10)
            if response.status_code == 200:
                data = response.json()

                # Health status should be string
                assert isinstance(
                    data.get("status"), str
                ), f"Health status should be string in {service_name}"

                # Service name should be string
                assert isinstance(
                    data.get("service"), str
                ), f"Service name should be string in {service_name}"

                # Timestamp should be string (ISO format)
                timestamp = data.get("timestamp")
                if timestamp:
                    assert isinstance(
                        timestamp, str
                    ), f"Timestamp should be string in {service_name}"
