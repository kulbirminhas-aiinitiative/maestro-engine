#!/usr/bin/env python3
"""
Unit tests for Requirement Schema Contract & Validation Service
Epic: MD-1820 [ME-900] Requirement Schema Contract & Validation

Tests cover all Acceptance Criteria:
- AC-1: Schemas versioned; incompatible changes blocked without migration notes
- AC-2: Validation errors returned with actionable messages
- AC-3: Contract doc published; examples covered by tests
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from services.requirement_schema_service import (
    RequirementSchemaService,
    SchemaDefinition,
    SchemaField,
    ValidationError,
    ValidationResult,
    CompatibilityResult,
    FieldType,
    ServiceType,
    ChangeType,
    ValidationSeverity,
    get_requirement_schema_service,
)


class TestRequirementSchemaService:
    """Tests for RequirementSchemaService."""

    @pytest.fixture
    def service(self):
        """Create a fresh service instance for testing."""
        return RequirementSchemaService()

    # ========================================================================
    # AC-1: Schemas versioned; incompatible changes blocked without migration
    # ========================================================================

    def test_register_schema_with_version(self, service):
        """AC-1: Schemas are versioned."""
        schema = service.register_schema(
            name="test_schema",
            version="1.0.0",
            description="Test schema",
            fields=[
                SchemaField(
                    name="field1",
                    field_type=FieldType.STRING,
                    required=True,
                )
            ],
        )

        assert schema.version == "1.0.0"
        assert schema.name == "test_schema"

    def test_get_schema_versions(self, service):
        """AC-1: Multiple versions can be registered."""
        service.register_schema(
            name="multi_version",
            version="1.0.0",
            description="V1",
            fields=[],
        )
        service.register_schema(
            name="multi_version",
            version="1.1.0",
            description="V1.1",
            fields=[],
        )
        service.register_schema(
            name="multi_version",
            version="2.0.0",
            description="V2",
            fields=[],
        )

        versions = service.get_schema_versions("multi_version")
        assert "1.0.0" in versions
        assert "1.1.0" in versions
        assert "2.0.0" in versions

    def test_get_specific_schema_version(self, service):
        """AC-1: Can retrieve specific schema version."""
        service.register_schema(
            name="versioned",
            version="1.0.0",
            description="Version 1",
            fields=[],
        )
        service.register_schema(
            name="versioned",
            version="2.0.0",
            description="Version 2",
            fields=[],
        )

        schema_v1 = service.get_schema("versioned", "1.0.0")
        schema_v2 = service.get_schema("versioned", "2.0.0")

        assert schema_v1.description == "Version 1"
        assert schema_v2.description == "Version 2"

    def test_compatible_change_detection(self, service):
        """AC-1: Compatible changes are detected."""
        service.register_schema(
            name="compat_test",
            version="1.0.0",
            description="V1",
            fields=[
                SchemaField(name="required_field", field_type=FieldType.STRING, required=True),
            ],
        )
        service.register_schema(
            name="compat_test",
            version="1.1.0",
            description="V1.1",
            fields=[
                SchemaField(name="required_field", field_type=FieldType.STRING, required=True),
                SchemaField(name="optional_field", field_type=FieldType.STRING, required=False),
            ],
            migration_notes="Added optional field",
        )

        result = service.check_compatibility("compat_test", "1.0.0", "1.1.0")

        assert result.is_compatible is True
        assert result.change_type == ChangeType.COMPATIBLE
        assert "optional_field" in str(result.compatible_changes)

    def test_breaking_change_detection(self, service):
        """AC-1: Breaking changes are detected."""
        service.register_schema(
            name="breaking_test",
            version="1.0.0",
            description="V1",
            fields=[
                SchemaField(name="required_field", field_type=FieldType.STRING, required=True),
            ],
        )
        service.register_schema(
            name="breaking_test",
            version="2.0.0",
            description="V2",
            fields=[
                SchemaField(name="new_required", field_type=FieldType.STRING, required=True),
            ],
        )

        result = service.check_compatibility("breaking_test", "1.0.0", "2.0.0")

        assert result.is_compatible is False
        assert result.change_type == ChangeType.BREAKING
        assert len(result.breaking_changes) > 0

    def test_incompatible_changes_blocked_without_migration(self, service):
        """AC-1: Incompatible changes blocked without migration notes."""
        service.register_schema(
            name="no_migration",
            version="1.0.0",
            description="V1",
            fields=[
                SchemaField(name="field1", field_type=FieldType.STRING, required=True),
            ],
        )
        service.register_schema(
            name="no_migration",
            version="2.0.0",
            description="V2 - breaking",
            fields=[
                SchemaField(name="field2", field_type=FieldType.STRING, required=True),
            ],
            migration_notes=None,  # No migration notes
        )

        can_upgrade, reason = service.can_upgrade("no_migration", "1.0.0", "2.0.0")

        assert can_upgrade is False
        assert "migration notes" in reason.lower()

    def test_incompatible_changes_allowed_with_migration(self, service):
        """AC-1: Incompatible changes allowed with migration notes."""
        service.register_schema(
            name="with_migration",
            version="1.0.0",
            description="V1",
            fields=[
                SchemaField(name="old_field", field_type=FieldType.STRING, required=True),
            ],
        )
        service.register_schema(
            name="with_migration",
            version="2.0.0",
            description="V2",
            fields=[
                SchemaField(name="new_field", field_type=FieldType.STRING, required=True),
            ],
            migration_notes="Rename old_field to new_field in your data",
        )

        can_upgrade, migration_notes = service.can_upgrade("with_migration", "1.0.0", "2.0.0")

        assert can_upgrade is True
        assert migration_notes is not None
        assert "new_field" in migration_notes

    def test_type_change_is_breaking(self, service):
        """AC-1: Type changes are breaking."""
        service.register_schema(
            name="type_change",
            version="1.0.0",
            description="V1",
            fields=[
                SchemaField(name="field", field_type=FieldType.STRING, required=True),
            ],
        )
        service.register_schema(
            name="type_change",
            version="2.0.0",
            description="V2",
            fields=[
                SchemaField(name="field", field_type=FieldType.INTEGER, required=True),
            ],
        )

        result = service.check_compatibility("type_change", "1.0.0", "2.0.0")

        assert result.is_compatible is False
        assert any("type changed" in change.lower() for change in result.breaking_changes)

    # ========================================================================
    # AC-2: Validation errors returned with actionable messages
    # ========================================================================

    def test_validation_error_has_field(self, service):
        """AC-2: Validation error identifies the field."""
        result = service.validate(
            {"title": ""},  # Too short
            "requirement",
            "1.0.0",
        )

        assert not result.is_valid
        assert any(e.field == "title" for e in result.errors)

    def test_validation_error_has_message(self, service):
        """AC-2: Validation error has descriptive message."""
        result = service.validate(
            {"priority": "invalid_priority"},
            "requirement",
            "1.0.0",
        )

        priority_errors = [e for e in result.errors if e.field == "priority"]
        assert len(priority_errors) > 0
        assert "invalid" in priority_errors[0].message.lower()

    def test_validation_error_has_suggestion(self, service):
        """AC-2: Validation error has actionable suggestion."""
        result = service.validate(
            {"type": "unknown_type"},
            "requirement",
            "1.0.0",
        )

        type_errors = [e for e in result.errors if e.field == "type"]
        assert len(type_errors) > 0
        assert type_errors[0].suggestion is not None
        assert len(type_errors[0].suggestion) > 0

    def test_validation_error_shows_expected_vs_actual(self, service):
        """AC-2: Validation error shows expected vs actual."""
        result = service.validate(
            {"priority": 123},  # Should be string enum
            "requirement",
            "1.0.0",
        )

        priority_errors = [e for e in result.errors if e.field == "priority"]
        assert len(priority_errors) > 0
        assert priority_errors[0].expected is not None
        assert priority_errors[0].actual is not None

    def test_missing_required_field_error(self, service):
        """AC-2: Missing required field returns actionable error."""
        result = service.validate(
            {"title": "Test"},  # Missing many required fields
            "requirement",
            "1.0.0",
        )

        assert not result.is_valid
        missing_errors = [e for e in result.errors if "missing" in e.message.lower()]
        assert len(missing_errors) > 0

    def test_string_too_short_error(self, service):
        """AC-2: String too short returns actionable error."""
        result = service.validate(
            {
                "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "ab",  # Too short (min 5)
                "description": "This is a valid description",
                "priority": "high",
                "type": "feature",
                "created_at": "2025-01-15T10:30:00Z",
                "created_by": "user_123",
            },
            "requirement",
            "1.0.0",
        )

        title_errors = [e for e in result.errors if e.field == "title"]
        assert len(title_errors) > 0
        assert "short" in title_errors[0].message.lower()
        assert title_errors[0].suggestion is not None

    def test_enum_validation_shows_valid_options(self, service):
        """AC-2: Enum error shows valid options."""
        result = service.validate(
            {
                "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Valid title here",
                "description": "Valid description",
                "priority": "urgent",  # Invalid enum
                "type": "feature",
                "created_at": "2025-01-15T10:30:00Z",
                "created_by": "user_123",
            },
            "requirement",
            "1.0.0",
        )

        priority_errors = [e for e in result.errors if e.field == "priority"]
        assert len(priority_errors) > 0
        assert "critical" in str(priority_errors[0].expected) or \
               "critical" in str(priority_errors[0].suggestion)

    def test_validation_warnings_for_deprecated_fields(self, service):
        """AC-2: Deprecated fields generate warnings."""
        # Register schema with deprecated field
        service.register_schema(
            name="deprecated_test",
            version="1.0.0",
            description="Test",
            fields=[
                SchemaField(
                    name="old_field",
                    field_type=FieldType.STRING,
                    required=False,
                    deprecated=True,
                    deprecated_message="Use new_field instead",
                ),
                SchemaField(
                    name="new_field",
                    field_type=FieldType.STRING,
                    required=False,
                ),
            ],
        )

        result = service.validate(
            {"old_field": "value"},
            "deprecated_test",
            "1.0.0",
        )

        assert len(result.warnings) > 0
        # Check that warning mentions either "deprecated" or the deprecated_message
        assert any(
            "deprecated" in w.message.lower() or "new_field" in w.message.lower()
            for w in result.warnings
        )

    def test_unknown_field_warning(self, service):
        """AC-2: Unknown fields generate warnings."""
        result = service.validate(
            {
                "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Valid title",
                "description": "Valid description",
                "priority": "high",
                "type": "feature",
                "created_at": "2025-01-15T10:30:00Z",
                "created_by": "user_123",
                "unknown_field": "some value",
            },
            "requirement",
            "1.0.0",
        )

        assert any(w.field == "unknown_field" for w in result.warnings)

    # ========================================================================
    # AC-3: Contract doc published; examples covered by tests
    # ========================================================================

    def test_get_contract_documentation(self, service):
        """AC-3: Contract doc is published."""
        doc = service.get_contract_documentation("requirement")

        assert "schema" in doc
        assert "documentation" in doc
        assert doc["documentation"]["overview"] is not None
        assert "fields" in doc["documentation"]

    def test_contract_doc_includes_field_details(self, service):
        """AC-3: Contract doc includes field details."""
        doc = service.get_contract_documentation("requirement")

        fields = doc["documentation"]["fields"]
        assert len(fields) > 0

        # Check field has required info
        field = fields[0]
        assert "name" in field
        assert "type" in field
        assert "required" in field
        assert "description" in field

    def test_contract_doc_includes_examples(self, service):
        """AC-3: Contract doc includes examples."""
        doc = service.get_contract_documentation("requirement")

        assert "examples" in doc["documentation"]
        assert len(doc["documentation"]["examples"]) > 0

    def test_get_examples(self, service):
        """AC-3: Examples can be retrieved."""
        examples = service.get_examples("requirement")

        assert len(examples) > 0
        assert "requirement_id" in examples[0]
        assert "title" in examples[0]

    def test_validate_examples_pass(self, service):
        """AC-3: Built-in examples pass validation."""
        result = service.validate_examples("requirement")

        assert result["all_examples_valid"] is True

    def test_examples_covered_by_validation(self, service):
        """AC-3: Examples are validated."""
        examples = service.get_examples("requirement", "1.0.0")

        for example in examples:
            result = service.validate(example, "requirement", "1.0.0")
            assert result.is_valid, f"Example failed validation: {result.errors}"

    def test_workflow_input_examples_valid(self, service):
        """AC-3: Workflow input examples pass validation."""
        result = service.validate_examples("workflow_input")

        assert result["all_examples_valid"] is True

    # ========================================================================
    # Additional Tests
    # ========================================================================

    def test_valid_requirement_passes(self, service):
        """Test valid requirement passes validation."""
        valid_data = {
            "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Implement user authentication",
            "description": "Add OAuth2 authentication with Google and GitHub providers",
            "priority": "high",
            "type": "feature",
            "created_at": "2025-01-15T10:30:00Z",
            "created_by": "user_123",
            "tags": ["auth", "security"],
        }

        result = service.validate(valid_data, "requirement", "1.0.0")

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_uuid_validation(self, service):
        """Test UUID field validation."""
        invalid_uuid_data = {
            "requirement_id": "not-a-valid-uuid",
            "title": "Test title",
            "description": "Test description",
            "priority": "high",
            "type": "feature",
            "created_at": "2025-01-15T10:30:00Z",
            "created_by": "user_123",
        }

        result = service.validate(invalid_uuid_data, "requirement", "1.0.0")

        assert not result.is_valid
        uuid_errors = [e for e in result.errors if e.field == "requirement_id"]
        assert len(uuid_errors) > 0

    def test_datetime_validation(self, service):
        """Test datetime field validation."""
        invalid_datetime_data = {
            "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Test title",
            "description": "Test description",
            "priority": "high",
            "type": "feature",
            "created_at": "not-a-datetime",
            "created_by": "user_123",
        }

        result = service.validate(invalid_datetime_data, "requirement", "1.0.0")

        assert not result.is_valid
        datetime_errors = [e for e in result.errors if e.field == "created_at"]
        assert len(datetime_errors) > 0

    def test_list_schemas(self, service):
        """Test listing all schemas."""
        schemas = service.list_schemas()

        assert len(schemas) >= 2  # requirement and workflow_input
        names = [s["name"] for s in schemas]
        assert "requirement" in names
        assert "workflow_input" in names

    def test_schema_not_found(self, service):
        """Test handling of nonexistent schema."""
        result = service.validate({}, "nonexistent_schema")

        assert not result.is_valid
        assert any("not found" in e.message.lower() for e in result.errors)

    def test_singleton_instance(self):
        """Test singleton pattern."""
        service1 = get_requirement_schema_service()
        service2 = get_requirement_schema_service()

        assert service1 is service2

    def test_service_info(self, service):
        """Test service info."""
        info = service.get_service_info()

        assert info["service"] == "requirement_schema_service"
        assert info["version"] == "1.0.0"
        assert info["total_schemas"] >= 2

    def test_validation_result_to_dict(self, service):
        """Test validation result serialization."""
        result = service.validate({}, "requirement")
        data = result.to_dict()

        assert "is_valid" in data
        assert "errors" in data
        assert "warnings" in data
        assert "error_count" in data
        assert "validated_at" in data

    def test_compatibility_result_to_dict(self, service):
        """Test compatibility result serialization."""
        result = service.check_compatibility("requirement", "1.0.0", "1.1.0")
        data = result.to_dict()

        assert "is_compatible" in data
        assert "change_type" in data
        assert "breaking_changes" in data
        assert "compatible_changes" in data

    def test_schema_to_dict(self, service):
        """Test schema serialization."""
        schema = service.get_schema("requirement")
        data = schema.to_dict()

        assert "schema_id" in data
        assert "name" in data
        assert "version" in data
        assert "fields" in data
        assert "examples" in data


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
