#!/usr/bin/env python3
"""
API Contract Tests for Requirement Schema Service
Task: MD-1857 [ME-900] Create API Contract Tests

These tests verify:
1. API endpoint contracts are stable
2. Request/Response schemas match documentation
3. Error responses follow standard format
4. Version compatibility across API calls
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.requirement_schema_routes import router as schema_router


# Create test app
app = FastAPI()
app.include_router(schema_router)

client = TestClient(app)


class TestAPIContractSchemaEndpoints:
    """Contract tests for schema API endpoints."""

    # ========================================================================
    # GET /api/schemas - List all schemas
    # ========================================================================

    def test_list_schemas_contract(self):
        """Contract: GET /api/schemas returns list of schemas."""
        response = client.get("/api/schemas")

        assert response.status_code == 200
        data = response.json()

        # Contract: Response has 'schemas' array and 'total' count
        assert "schemas" in data
        assert "total" in data
        assert isinstance(data["schemas"], list)
        assert isinstance(data["total"], int)

    def test_list_schemas_item_contract(self):
        """Contract: Each schema in list has required fields."""
        response = client.get("/api/schemas")
        data = response.json()

        assert len(data["schemas"]) > 0

        # Contract: Each schema item has name, current_version, versions
        for schema in data["schemas"]:
            assert "name" in schema
            assert "current_version" in schema
            assert "versions" in schema
            assert isinstance(schema["versions"], list)

    # ========================================================================
    # GET /api/schemas/{name} - Get schema by name
    # ========================================================================

    def test_get_schema_contract(self):
        """Contract: GET /api/schemas/{name} returns schema definition."""
        response = client.get("/api/schemas/requirement")

        assert response.status_code == 200
        data = response.json()

        # Contract: Schema has required fields
        assert "schema_id" in data
        assert "name" in data
        assert "version" in data
        assert "description" in data
        assert "fields" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_schema_fields_contract(self):
        """Contract: Schema fields have required structure."""
        response = client.get("/api/schemas/requirement")
        data = response.json()

        # Contract: Each field has name, type, required, description
        for field in data["fields"]:
            assert "name" in field
            assert "type" in field
            assert "required" in field
            assert "description" in field
            assert "constraints" in field

    def test_get_schema_with_version_contract(self):
        """Contract: GET /api/schemas/{name}?version= returns specific version."""
        response = client.get("/api/schemas/requirement?version=1.0.0")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0.0"

    def test_get_schema_not_found_contract(self):
        """Contract: 404 for non-existent schema."""
        response = client.get("/api/schemas/nonexistent_schema")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    # ========================================================================
    # GET /api/schemas/{name}/versions - Get schema versions
    # ========================================================================

    def test_get_versions_contract(self):
        """Contract: GET /api/schemas/{name}/versions returns version list."""
        response = client.get("/api/schemas/requirement/versions")

        assert response.status_code == 200
        data = response.json()

        # Contract: Response has name, versions array, current
        assert "name" in data
        assert "versions" in data
        assert "current" in data
        assert isinstance(data["versions"], list)
        assert len(data["versions"]) > 0

    def test_get_versions_not_found_contract(self):
        """Contract: 404 for non-existent schema versions."""
        response = client.get("/api/schemas/nonexistent/versions")

        assert response.status_code == 404

    # ========================================================================
    # POST /api/schemas/{name}/validate - Validate data
    # ========================================================================

    def test_validate_request_contract(self):
        """Contract: POST /api/schemas/{name}/validate accepts data field."""
        response = client.post(
            "/api/schemas/requirement/validate",
            json={"data": {"title": "Test"}}
        )

        assert response.status_code == 200
        data = response.json()

        # Contract: Response has validation result fields
        assert "is_valid" in data
        assert "errors" in data
        assert "warnings" in data
        assert "error_count" in data
        assert "warning_count" in data
        assert "validated_at" in data
        assert "schema_version" in data

    def test_validate_error_response_contract(self):
        """Contract: Validation errors have actionable format."""
        response = client.post(
            "/api/schemas/requirement/validate",
            json={"data": {"priority": "invalid"}}
        )

        data = response.json()

        # Contract: Errors array with structured error objects
        assert isinstance(data["errors"], list)
        if len(data["errors"]) > 0:
            error = data["errors"][0]
            assert "field" in error
            assert "message" in error
            assert "severity" in error

    def test_validate_with_version_contract(self):
        """Contract: Validate with specific version."""
        response = client.post(
            "/api/schemas/requirement/validate?version=1.0.0",
            json={"data": {"title": "Test"}}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["schema_version"] == "1.0.0"

    def test_validate_with_service_type_contract(self):
        """Contract: Validate with service type context."""
        response = client.post(
            "/api/schemas/requirement/validate",
            json={"data": {"title": "Test"}, "service_type": "backend"}
        )

        assert response.status_code == 200

    # ========================================================================
    # GET /api/schemas/{name}/compatibility - Check compatibility
    # ========================================================================

    def test_compatibility_contract(self):
        """Contract: GET /api/schemas/{name}/compatibility returns result."""
        response = client.get(
            "/api/schemas/requirement/compatibility?from_version=1.0.0&to_version=1.1.0"
        )

        assert response.status_code == 200
        data = response.json()

        # Contract: Compatibility result has required fields
        assert "is_compatible" in data
        assert "change_type" in data
        assert "breaking_changes" in data
        assert "compatible_changes" in data
        assert "deprecated_fields" in data
        assert "migration_required" in data

    def test_compatibility_missing_params_contract(self):
        """Contract: 422 when missing required query params."""
        response = client.get("/api/schemas/requirement/compatibility")

        # FastAPI returns 422 for missing required params
        assert response.status_code == 422

    # ========================================================================
    # GET /api/schemas/{name}/can-upgrade - Check upgrade allowance
    # ========================================================================

    def test_can_upgrade_contract(self):
        """Contract: GET /api/schemas/{name}/can-upgrade returns result."""
        response = client.get(
            "/api/schemas/requirement/can-upgrade?from_version=1.0.0&to_version=1.1.0"
        )

        assert response.status_code == 200
        data = response.json()

        # Contract: Result has allowed, migration_notes, versions
        assert "allowed" in data
        assert "migration_notes" in data
        assert "from_version" in data
        assert "to_version" in data

    # ========================================================================
    # GET /api/schemas/{name}/documentation - Get docs
    # ========================================================================

    def test_documentation_contract(self):
        """Contract: GET /api/schemas/{name}/documentation returns docs."""
        response = client.get("/api/schemas/requirement/documentation")

        assert response.status_code == 200
        data = response.json()

        # Contract: Documentation has schema and documentation sections
        assert "schema" in data
        assert "documentation" in data

        doc = data["documentation"]
        assert "overview" in doc
        assert "version" in doc
        assert "supported_services" in doc
        assert "fields" in doc
        assert "examples" in doc

    def test_documentation_fields_contract(self):
        """Contract: Documentation fields have required info."""
        response = client.get("/api/schemas/requirement/documentation")
        data = response.json()

        fields = data["documentation"]["fields"]
        assert len(fields) > 0

        for field in fields:
            assert "name" in field
            assert "type" in field
            assert "required" in field
            assert "description" in field
            assert "constraints" in field

    def test_documentation_not_found_contract(self):
        """Contract: 404 for non-existent schema docs."""
        response = client.get("/api/schemas/nonexistent/documentation")

        assert response.status_code == 404

    # ========================================================================
    # GET /api/schemas/{name}/examples - Get examples
    # ========================================================================

    def test_examples_contract(self):
        """Contract: GET /api/schemas/{name}/examples returns examples."""
        response = client.get("/api/schemas/requirement/examples")

        assert response.status_code == 200
        data = response.json()

        # Contract: Result has name, examples array, count
        assert "name" in data
        assert "examples" in data
        assert "count" in data
        assert isinstance(data["examples"], list)

    def test_examples_with_version_contract(self):
        """Contract: Examples for specific version."""
        response = client.get("/api/schemas/requirement/examples?version=1.0.0")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] > 0

    # ========================================================================
    # GET /api/schemas/{name}/validate-examples - Validate examples
    # ========================================================================

    def test_validate_examples_contract(self):
        """Contract: GET /api/schemas/{name}/validate-examples returns result."""
        response = client.get("/api/schemas/requirement/validate-examples")

        assert response.status_code == 200
        data = response.json()

        # Contract: Result has schema, version, all_examples_valid, results
        assert "schema" in data
        assert "version" in data
        assert "all_examples_valid" in data
        assert "results" in data

    def test_validate_examples_results_contract(self):
        """Contract: Validation results have required fields."""
        response = client.get("/api/schemas/requirement/validate-examples")
        data = response.json()

        if len(data["results"]) > 0:
            result = data["results"][0]
            assert "example_index" in result
            assert "is_valid" in result
            assert "errors" in result

    def test_validate_examples_not_found_contract(self):
        """Contract: 404 for non-existent schema."""
        response = client.get("/api/schemas/nonexistent/validate-examples")

        assert response.status_code == 404

    # ========================================================================
    # GET /api/schemas/health - Health check
    # ========================================================================

    def test_health_contract(self):
        """Contract: GET /api/schemas/health returns status."""
        response = client.get("/api/schemas/health")

        assert response.status_code == 200
        data = response.json()

        # Contract: Health check has status and service
        assert "status" in data
        assert "service" in data
        assert data["service"] == "requirement-schemas"


class TestAPIContractErrorResponses:
    """Tests for API error response contracts."""

    def test_404_error_contract(self):
        """Contract: 404 errors have detail field."""
        response = client.get("/api/schemas/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)

    def test_422_validation_error_contract(self):
        """Contract: 422 validation errors have detail array."""
        response = client.post(
            "/api/schemas/requirement/validate",
            json={}  # Missing required 'data' field
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_400_bad_request_body_contract(self):
        """Contract: Invalid JSON returns error."""
        response = client.post(
            "/api/schemas/requirement/validate",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )

        # Should return 422 for invalid body
        assert response.status_code == 422


class TestAPIContractVersionConsistency:
    """Tests for version handling across API endpoints."""

    def test_version_consistent_in_list_and_get(self):
        """Contract: Version in list matches version in get."""
        # Get list
        list_response = client.get("/api/schemas")
        schemas = list_response.json()["schemas"]

        # Find requirement schema
        req_schema = next(s for s in schemas if s["name"] == "requirement")
        current_version = req_schema["current_version"]

        # Get specific schema
        get_response = client.get("/api/schemas/requirement")
        schema = get_response.json()

        assert schema["version"] == current_version

    def test_all_versions_accessible(self):
        """Contract: All listed versions are accessible."""
        versions_response = client.get("/api/schemas/requirement/versions")
        versions = versions_response.json()["versions"]

        for version in versions:
            response = client.get(f"/api/schemas/requirement?version={version}")
            assert response.status_code == 200
            assert response.json()["version"] == version

    def test_validation_uses_specified_version(self):
        """Contract: Validation respects version parameter."""
        for version in ["1.0.0", "1.1.0"]:
            response = client.post(
                f"/api/schemas/requirement/validate?version={version}",
                json={"data": {"title": "Test"}}
            )

            assert response.status_code == 200
            assert response.json()["schema_version"] == version


class TestAPIContractDataTypes:
    """Tests for data type contracts in responses."""

    def test_timestamps_are_iso8601(self):
        """Contract: Timestamps are ISO 8601 format."""
        import re

        response = client.get("/api/schemas/requirement")
        data = response.json()

        iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'

        assert re.match(iso_pattern, data["created_at"])
        assert re.match(iso_pattern, data["updated_at"])

    def test_validation_timestamp_is_iso8601(self):
        """Contract: Validation timestamp is ISO 8601."""
        import re

        response = client.post(
            "/api/schemas/requirement/validate",
            json={"data": {}}
        )

        iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
        assert re.match(iso_pattern, response.json()["validated_at"])

    def test_boolean_fields_are_boolean(self):
        """Contract: Boolean fields are actual booleans."""
        response = client.get(
            "/api/schemas/requirement/compatibility?from_version=1.0.0&to_version=1.1.0"
        )
        data = response.json()

        assert isinstance(data["is_compatible"], bool)
        assert isinstance(data["migration_required"], bool)

    def test_count_fields_are_integers(self):
        """Contract: Count fields are integers."""
        response = client.post(
            "/api/schemas/requirement/validate",
            json={"data": {}}
        )
        data = response.json()

        assert isinstance(data["error_count"], int)
        assert isinstance(data["warning_count"], int)


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
