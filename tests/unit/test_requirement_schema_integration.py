#!/usr/bin/env python3
"""
Integration Tests for Requirement Schema Contract & Validation
Task: MD-1859 [ME-900] Integration Testing

These tests verify:
1. Schema validation works across all endpoints
2. Version upgrades maintain data integrity
3. End-to-end flows work correctly
4. Cross-service validation scenarios
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.requirement_schema_routes import router as schema_router
from services.requirement_schema_service import (
    RequirementSchemaService,
    SchemaField,
    FieldType,
    ServiceType,
    get_requirement_schema_service,
)


# Create test app
app = FastAPI()
app.include_router(schema_router)

client = TestClient(app)


class TestEndToEndValidation:
    """End-to-end validation flow tests."""

    def test_full_validation_flow(self):
        """Test complete validation workflow."""
        # Step 1: Get available schemas
        schemas_response = client.get("/api/schemas")
        assert schemas_response.status_code == 200
        schemas = schemas_response.json()["schemas"]
        assert any(s["name"] == "requirement" for s in schemas)

        # Step 2: Get schema documentation
        docs_response = client.get("/api/schemas/requirement/documentation")
        assert docs_response.status_code == 200
        docs = docs_response.json()

        # Step 3: Get example from docs
        examples = docs["documentation"]["examples"]
        assert len(examples) > 0
        example = examples[0]

        # Step 4: Validate example
        validate_response = client.post(
            "/api/schemas/requirement/validate",
            json={"data": example}
        )
        assert validate_response.status_code == 200
        result = validate_response.json()
        assert result["is_valid"] is True

    def test_validation_with_invalid_data_shows_errors(self):
        """Test that invalid data returns actionable errors."""
        invalid_data = {
            "requirement_id": "not-a-uuid",
            "title": "ab",  # Too short
            "description": "short",  # Too short
            "priority": "urgent",  # Invalid enum
            "type": "unknown",  # Invalid enum
            "created_at": "not-a-date",
            "created_by": "",
        }

        response = client.post(
            "/api/schemas/requirement/validate",
            json={"data": invalid_data}
        )

        assert response.status_code == 200
        result = response.json()

        assert result["is_valid"] is False
        assert result["error_count"] > 0

        # Check errors have actionable info
        for error in result["errors"]:
            assert error["field"] is not None
            assert error["message"] is not None
            assert error["severity"] == "error"

    def test_partial_validation_identifies_missing_fields(self):
        """Test partial data validation identifies all missing required fields."""
        partial_data = {
            "title": "Valid title here"
        }

        response = client.post(
            "/api/schemas/requirement/validate",
            json={"data": partial_data}
        )

        result = response.json()
        assert result["is_valid"] is False

        # Check that multiple missing fields are reported
        missing_fields = [e["field"] for e in result["errors"] if "missing" in e["message"].lower()]
        assert len(missing_fields) > 0


class TestVersionMigration:
    """Tests for version migration scenarios."""

    def test_data_valid_in_v1_valid_in_v1_1(self):
        """Test v1.0.0 valid data is also valid in v1.1.0."""
        # v1.0.0 valid data
        v1_data = {
            "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Implement user authentication",
            "description": "Add OAuth2 authentication with Google and GitHub providers",
            "priority": "high",
            "type": "feature",
            "created_at": "2025-01-15T10:30:00Z",
            "created_by": "user_123",
            "tags": ["auth", "security"],
        }

        # Validate against v1.0.0
        v1_response = client.post(
            "/api/schemas/requirement/validate?version=1.0.0",
            json={"data": v1_data}
        )
        assert v1_response.json()["is_valid"] is True

        # Validate same data against v1.1.0
        v1_1_response = client.post(
            "/api/schemas/requirement/validate?version=1.1.0",
            json={"data": v1_data}
        )
        assert v1_1_response.json()["is_valid"] is True

    def test_v1_1_new_fields_optional(self):
        """Test v1.1.0 new fields are truly optional."""
        # v1.0.0 data without v1.1.0 fields
        data_without_new_fields = {
            "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Test requirement",
            "description": "Test description with enough characters",
            "priority": "medium",
            "type": "task",
            "created_at": "2025-01-15T10:30:00Z",
            "created_by": "user_123",
        }

        response = client.post(
            "/api/schemas/requirement/validate?version=1.1.0",
            json={"data": data_without_new_fields}
        )

        result = response.json()
        assert result["is_valid"] is True

    def test_v1_1_with_new_fields(self):
        """Test v1.1.0 data with new fields validates correctly."""
        v1_1_data = {
            "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Test requirement",
            "description": "Test description with enough characters",
            "priority": "high",
            "type": "feature",
            "created_at": "2025-01-15T10:30:00Z",
            "created_by": "user_123",
            "estimated_hours": 8.5,
            "assignee": "dev_456",
        }

        response = client.post(
            "/api/schemas/requirement/validate?version=1.1.0",
            json={"data": v1_1_data}
        )

        result = response.json()
        assert result["is_valid"] is True

    def test_compatibility_check_v1_to_v1_1(self):
        """Test compatibility check from v1.0.0 to v1.1.0."""
        response = client.get(
            "/api/schemas/requirement/compatibility?from_version=1.0.0&to_version=1.1.0"
        )

        assert response.status_code == 200
        result = response.json()

        # v1.0.0 to v1.1.0 should be compatible
        assert result["is_compatible"] is True
        assert result["change_type"] == "compatible"
        assert len(result["breaking_changes"]) == 0

    def test_upgrade_check_v1_to_v1_1(self):
        """Test upgrade allowance from v1.0.0 to v1.1.0."""
        response = client.get(
            "/api/schemas/requirement/can-upgrade?from_version=1.0.0&to_version=1.1.0"
        )

        assert response.status_code == 200
        result = response.json()

        assert result["allowed"] is True


class TestCrossServiceValidation:
    """Tests for validation across different service types."""

    def test_workflow_input_validation(self):
        """Test workflow_input schema validation."""
        workflow_data = {
            "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "requirement": "Build a REST API for user management",
            "personas": ["backend_developer", "qa_engineer"],
            "workflow_type": "standard",
            "config": {"max_iterations": 3},
        }

        response = client.post(
            "/api/schemas/workflow_input/validate",
            json={"data": workflow_data}
        )

        assert response.status_code == 200
        result = response.json()
        assert result["is_valid"] is True

    def test_workflow_input_with_service_type(self):
        """Test workflow_input validation with service type context."""
        workflow_data = {
            "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "requirement": "Build API",
        }

        response = client.post(
            "/api/schemas/workflow_input/validate",
            json={"data": workflow_data, "service_type": "backend"}
        )

        assert response.status_code == 200

    def test_invalid_workflow_type_enum(self):
        """Test workflow_input with invalid workflow_type."""
        workflow_data = {
            "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "requirement": "Build API",
            "workflow_type": "invalid_type",
        }

        response = client.post(
            "/api/schemas/workflow_input/validate",
            json={"data": workflow_data}
        )

        result = response.json()
        assert result["is_valid"] is False
        assert any(e["field"] == "workflow_type" for e in result["errors"])


class TestExamplesValidation:
    """Tests for schema examples validation."""

    def test_all_requirement_examples_valid(self):
        """Test all requirement schema examples are valid."""
        response = client.get("/api/schemas/requirement/validate-examples")

        assert response.status_code == 200
        result = response.json()
        assert result["all_examples_valid"] is True

    def test_all_workflow_input_examples_valid(self):
        """Test all workflow_input schema examples are valid."""
        response = client.get("/api/schemas/workflow_input/validate-examples")

        assert response.status_code == 200
        result = response.json()
        assert result["all_examples_valid"] is True

    def test_examples_match_version(self):
        """Test that examples validate against their schema version."""
        # Get v1.0.0 examples
        examples_response = client.get("/api/schemas/requirement/examples?version=1.0.0")
        examples = examples_response.json()["examples"]

        for example in examples:
            result = client.post(
                "/api/schemas/requirement/validate?version=1.0.0",
                json={"data": example}
            ).json()

            assert result["is_valid"] is True, f"Example failed: {result['errors']}"


class TestDocumentationIntegrity:
    """Tests for documentation integrity."""

    def test_documentation_matches_schema(self):
        """Test documentation matches actual schema."""
        # Get schema
        schema_response = client.get("/api/schemas/requirement")
        schema = schema_response.json()

        # Get documentation
        docs_response = client.get("/api/schemas/requirement/documentation")
        docs = docs_response.json()

        # Field count should match
        schema_fields = schema["fields"]
        doc_fields = docs["documentation"]["fields"]

        assert len(schema_fields) == len(doc_fields)

        # Field names should match
        schema_names = {f["name"] for f in schema_fields}
        doc_names = {f["name"] for f in doc_fields}

        assert schema_names == doc_names

    def test_documentation_version_matches(self):
        """Test documentation version matches schema version."""
        schema_response = client.get("/api/schemas/requirement")
        docs_response = client.get("/api/schemas/requirement/documentation")

        assert schema_response.json()["version"] == docs_response.json()["documentation"]["version"]


class TestErrorRecovery:
    """Tests for error recovery scenarios."""

    def test_validate_after_error(self):
        """Test validation works after previous error."""
        # First, cause an error
        client.post(
            "/api/schemas/nonexistent/validate",
            json={"data": {}}
        )

        # Then validate valid data
        valid_data = {
            "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Valid requirement title",
            "description": "Valid description with enough characters",
            "priority": "high",
            "type": "feature",
            "created_at": "2025-01-15T10:30:00Z",
            "created_by": "user_123",
        }

        response = client.post(
            "/api/schemas/requirement/validate",
            json={"data": valid_data}
        )

        assert response.status_code == 200
        assert response.json()["is_valid"] is True

    def test_multiple_validations_consistent(self):
        """Test multiple validations return consistent results."""
        data = {
            "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Test",
            "description": "Test description",
            "priority": "high",
            "type": "feature",
            "created_at": "2025-01-15T10:30:00Z",
            "created_by": "user_123",
        }

        results = []
        for _ in range(5):
            response = client.post(
                "/api/schemas/requirement/validate",
                json={"data": data}
            )
            results.append(response.json()["is_valid"])

        # All results should be the same
        assert all(r == results[0] for r in results)


class TestBoundaryConditions:
    """Tests for boundary conditions."""

    def test_min_length_boundary(self):
        """Test minimum length boundary (exactly at limit)."""
        # Title min_length is 5
        data = {
            "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "12345",  # Exactly 5 chars
            "description": "1234567890",  # Exactly 10 chars (min)
            "priority": "high",
            "type": "feature",
            "created_at": "2025-01-15T10:30:00Z",
            "created_by": "user_123",
        }

        response = client.post(
            "/api/schemas/requirement/validate",
            json={"data": data}
        )

        result = response.json()
        # Should pass - exactly at minimum
        title_errors = [e for e in result["errors"] if e["field"] == "title" and "short" in e["message"]]
        assert len(title_errors) == 0

    def test_max_length_boundary(self):
        """Test maximum length boundary (exactly at limit)."""
        # Title max_length is 200
        data = {
            "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "x" * 200,  # Exactly 200 chars
            "description": "Valid description text",
            "priority": "high",
            "type": "feature",
            "created_at": "2025-01-15T10:30:00Z",
            "created_by": "user_123",
        }

        response = client.post(
            "/api/schemas/requirement/validate",
            json={"data": data}
        )

        result = response.json()
        # Should pass - exactly at maximum
        title_errors = [e for e in result["errors"] if e["field"] == "title" and "long" in e["message"]]
        assert len(title_errors) == 0

    def test_empty_array_allowed(self):
        """Test empty arrays are allowed for optional array fields."""
        data = {
            "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Valid title here",
            "description": "Valid description text",
            "priority": "high",
            "type": "feature",
            "created_at": "2025-01-15T10:30:00Z",
            "created_by": "user_123",
            "tags": [],  # Empty array
        }

        response = client.post(
            "/api/schemas/requirement/validate",
            json={"data": data}
        )

        assert response.json()["is_valid"] is True

    def test_empty_object_allowed(self):
        """Test empty objects are allowed for optional object fields."""
        data = {
            "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Valid title here",
            "description": "Valid description text",
            "priority": "high",
            "type": "feature",
            "created_at": "2025-01-15T10:30:00Z",
            "created_by": "user_123",
            "metadata": {},  # Empty object
        }

        response = client.post(
            "/api/schemas/requirement/validate",
            json={"data": data}
        )

        assert response.json()["is_valid"] is True


class TestServiceIntegration:
    """Tests for service layer integration."""

    @pytest.fixture
    def service(self):
        """Get service instance."""
        return get_requirement_schema_service()

    def test_service_and_api_consistency(self, service):
        """Test service and API return consistent results."""
        data = {
            "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Test",
            "priority": "invalid",
        }

        # Direct service call
        service_result = service.validate(data, "requirement")

        # API call
        api_response = client.post(
            "/api/schemas/requirement/validate",
            json={"data": data}
        )
        api_result = api_response.json()

        # Results should match
        assert service_result.is_valid == api_result["is_valid"]
        assert len(service_result.errors) == api_result["error_count"]

    def test_list_schemas_matches_service(self, service):
        """Test list schemas API matches service."""
        # Service call
        service_schemas = service.list_schemas()

        # API call
        api_response = client.get("/api/schemas")
        api_schemas = api_response.json()["schemas"]

        # Names should match
        service_names = {s["name"] for s in service_schemas}
        api_names = {s["name"] for s in api_schemas}

        assert service_names == api_names


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
