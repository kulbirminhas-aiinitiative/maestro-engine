import os
import re

import pytest
import requests

# Base URL for the API gateway. This should be the entry point for all E2E tests.
# In a docker-compose setup, this would be something like 'http://orchestration-gateway:8000'
# For local testing, you might port-forward and use 'http://localhost:8000'
BASE_URL = os.environ.get("MAESTRO_API_BASE_URL", "http://localhost:8000")

# A mapping from the service name in the spec to its actual host and port if not behind a gateway.
# This is useful for testing services individually.
SERVICE_HOST_MAPPING = {
    "orchestration-gateway": os.environ.get("GW_URL", "http://localhost:8000"),
    "template-registry-service": os.environ.get("TEMPLATE_URL", "http://localhost:9500"),
    "intelligence-service": os.environ.get("INTELLIGENCE_URL", "http://localhost:9501"),
    # Add other services here as they come online
}


def get_services_from_spec():
    """
    Parses the MAESTRO_MICROSERVICES_API_SPEC.md to find all defined services.
    """
    services = []
    try:
        with open("MAESTRO_MICROSERVICES_API_SPEC.md", "r") as f:
            content = f.read()
        # Find all headings like "## 1. Orchestration Gateway (service: `orchestration-gateway`)"
        matches = re.findall(r"## \d+\. .* \(service: `(.*)`\)", content)
        services = [m for m in matches if m in SERVICE_HOST_MAPPING]
        return services
    except FileNotFoundError:
        pytest.fail(
            "MAESTRO_MICROSERVICES_API_SPEC.md not found. Cannot determine services to test."
        )
        return []


@pytest.mark.parametrize("service_name", get_services_from_spec())
def test_service_health_check(service_name):
    """
    A parameterized test that checks the /v1/health endpoint of each service.
    """
    if service_name not in SERVICE_HOST_MAPPING:
        pytest.skip(f"Service '{service_name}' is not configured in the test environment.")

    service_url = SERVICE_HOST_MAPPING[service_name]
    health_endpoint = f"{service_url}/v1/health"

    try:
        response = requests.get(health_endpoint, timeout=5)

        # Check for a successful response
        assert (
            response.status_code == 200
        ), f"Expected 200 OK, but got {response.status_code} for {health_endpoint}"

        # Check for a meaningful JSON body
        data = response.json()
        assert "status" in data, "Health check response must contain a 'status' field."
        assert (
            data["status"] == "ok"
        ), f"Expected status 'ok', but got '{data['status']}' for {health_endpoint}"
        assert "version" in data, "Health check response must contain a 'version' field."

    except requests.exceptions.RequestException as e:
        pytest.fail(f"Could not connect to {health_endpoint}. Error: {e}. Is the service running?")


def test_orchestration_gateway_docs():
    """
    Tests if the main API gateway's documentation is available.
    """
    docs_url = f"{BASE_URL}/v1/docs"
    try:
        response = requests.get(docs_url, timeout=5)
        assert response.status_code == 200
        # Check for HTML content
        assert "text/html" in response.headers["content-type"]
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Could not connect to {docs_url}. Error: {e}.")


# You can add more E2E tests here, for example:
# def test_create_template_end_to_end():
#     """
#     A full E2E test that creates a template via the gateway and verifies it.
#     """
#     # This test would be more complex:
#     # 1. POST to BASE_URL/v1/templates (assuming gateway routes this)
#     # 2. Assert 201 Created
#     # 3. GET from BASE_URL/v1/templates/{id} to verify
#     # 4. DELETE to clean up
#     pass
