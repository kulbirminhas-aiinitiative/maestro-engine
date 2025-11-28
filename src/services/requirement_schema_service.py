#!/usr/bin/env python3
"""
Requirement Schema Contract & Validation Service
Implements Epic MD-1820 [ME-900] Requirement Schema Contract & Validation

Features:
- Versioned requirement schema definitions
- Validators for FE/BFF/BE services
- Compatibility checking between schema versions
- Actionable validation error messages

Acceptance Criteria:
- AC-1: Schemas versioned; incompatible changes blocked without migration notes
- AC-2: Validation errors returned with actionable messages
- AC-3: Contract doc published; examples covered by tests
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

logger = logging.getLogger("requirement_schema_service")


class SchemaVersion(str, Enum):
    """Schema version identifiers."""
    V1_0_0 = "1.0.0"
    V1_1_0 = "1.1.0"
    V1_2_0 = "1.2.0"
    V2_0_0 = "2.0.0"


class ServiceType(str, Enum):
    """Service types that use schemas."""
    FRONTEND = "frontend"
    BFF = "bff"
    BACKEND = "backend"
    ENGINE = "engine"
    ALL = "all"


class FieldType(str, Enum):
    """Field types in schema."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    DATETIME = "datetime"
    UUID = "uuid"
    ENUM = "enum"


class ChangeType(str, Enum):
    """Types of schema changes."""
    COMPATIBLE = "compatible"  # Backward compatible
    BREAKING = "breaking"  # Requires migration
    DEPRECATED = "deprecated"  # Field deprecated


class ValidationSeverity(str, Enum):
    """Severity of validation errors."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class SchemaField:
    """Definition of a schema field."""
    name: str
    field_type: FieldType
    required: bool = True
    description: str = ""
    default: Any = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None
    enum_values: List[str] = field(default_factory=list)
    array_item_type: Optional[FieldType] = None
    nested_schema: Optional[str] = None
    deprecated: bool = False
    deprecated_message: Optional[str] = None
    introduced_in: str = "1.0.0"
    removed_in: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.field_type.value if isinstance(self.field_type, FieldType) else self.field_type,
            "required": self.required,
            "description": self.description,
            "default": self.default,
            "constraints": {
                "min_length": self.min_length,
                "max_length": self.max_length,
                "min_value": self.min_value,
                "max_value": self.max_value,
                "pattern": self.pattern,
                "enum_values": self.enum_values,
            },
            "deprecated": self.deprecated,
            "deprecated_message": self.deprecated_message,
            "introduced_in": self.introduced_in,
            "removed_in": self.removed_in,
        }


@dataclass
class ValidationError:
    """
    Validation error with actionable message.
    AC-2: Validation errors returned with actionable messages.
    """
    field: str
    message: str
    severity: ValidationSeverity
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    suggestion: Optional[str] = None
    documentation_link: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "field": self.field,
            "message": self.message,
            "severity": self.severity.value,
            "expected": self.expected,
            "actual": self.actual,
            "suggestion": self.suggestion,
            "documentation_link": self.documentation_link,
        }


@dataclass
class SchemaDefinition:
    """
    Schema definition with versioning.
    AC-1: Schemas versioned.
    """
    schema_id: str
    name: str
    version: str
    description: str
    fields: List[SchemaField]
    created_at: str
    updated_at: str
    supported_services: List[ServiceType] = field(default_factory=lambda: [ServiceType.ALL])
    migration_notes: Optional[str] = None
    examples: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "schema_id": self.schema_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "fields": [f.to_dict() for f in self.fields],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "supported_services": [s.value for s in self.supported_services],
            "migration_notes": self.migration_notes,
            "examples": self.examples,
            "metadata": self.metadata,
        }


@dataclass
class CompatibilityResult:
    """
    Result of schema compatibility check.
    AC-1: Incompatible changes blocked without migration notes.
    """
    is_compatible: bool
    change_type: ChangeType
    breaking_changes: List[str]
    compatible_changes: List[str]
    deprecated_fields: List[str]
    migration_required: bool
    migration_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_compatible": self.is_compatible,
            "change_type": self.change_type.value,
            "breaking_changes": self.breaking_changes,
            "compatible_changes": self.compatible_changes,
            "deprecated_fields": self.deprecated_fields,
            "migration_required": self.migration_required,
            "migration_notes": self.migration_notes,
        }


@dataclass
class ValidationResult:
    """Result of schema validation."""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    validated_at: str
    schema_version: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "validated_at": self.validated_at,
            "schema_version": self.schema_version,
        }


class RequirementSchemaService:
    """
    Service for requirement schema contract and validation.

    Implements ME-900 acceptance criteria:
    - AC-1: Schemas versioned; incompatible changes blocked without migration notes
    - AC-2: Validation errors returned with actionable messages
    - AC-3: Contract doc published; examples covered by tests
    """

    def __init__(self):
        """Initialize the service."""
        self._schemas: Dict[str, Dict[str, SchemaDefinition]] = {}
        self._current_versions: Dict[str, str] = {}
        self._initialize_default_schemas()

    def _initialize_default_schemas(self):
        """Initialize default requirement schemas."""
        # Requirement Schema v1.0.0
        requirement_fields_v1 = [
            SchemaField(
                name="requirement_id",
                field_type=FieldType.UUID,
                required=True,
                description="Unique identifier for the requirement",
            ),
            SchemaField(
                name="title",
                field_type=FieldType.STRING,
                required=True,
                description="Short title of the requirement",
                min_length=5,
                max_length=200,
            ),
            SchemaField(
                name="description",
                field_type=FieldType.STRING,
                required=True,
                description="Detailed description of the requirement",
                min_length=10,
                max_length=10000,
            ),
            SchemaField(
                name="priority",
                field_type=FieldType.ENUM,
                required=True,
                description="Priority level",
                enum_values=["critical", "high", "medium", "low"],
            ),
            SchemaField(
                name="type",
                field_type=FieldType.ENUM,
                required=True,
                description="Requirement type",
                enum_values=["feature", "bug", "enhancement", "task"],
            ),
            SchemaField(
                name="created_at",
                field_type=FieldType.DATETIME,
                required=True,
                description="Creation timestamp",
            ),
            SchemaField(
                name="created_by",
                field_type=FieldType.STRING,
                required=True,
                description="Creator user ID",
            ),
            SchemaField(
                name="tags",
                field_type=FieldType.ARRAY,
                required=False,
                description="Tags for categorization",
                array_item_type=FieldType.STRING,
                default=[],
            ),
            SchemaField(
                name="metadata",
                field_type=FieldType.OBJECT,
                required=False,
                description="Additional metadata",
                default={},
            ),
        ]

        self.register_schema(
            name="requirement",
            version="1.0.0",
            description="Core requirement schema for FE/BFF/BE",
            fields=requirement_fields_v1,
            supported_services=[ServiceType.ALL],
            examples=[
                {
                    "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
                    "title": "Implement user authentication",
                    "description": "Add OAuth2 authentication with Google and GitHub providers",
                    "priority": "high",
                    "type": "feature",
                    "created_at": "2025-01-15T10:30:00Z",
                    "created_by": "user_123",
                    "tags": ["auth", "security"],
                    "metadata": {"sprint": 5},
                }
            ],
        )

        # Requirement Schema v1.1.0 (compatible)
        requirement_fields_v1_1 = requirement_fields_v1.copy()
        requirement_fields_v1_1.append(
            SchemaField(
                name="estimated_hours",
                field_type=FieldType.FLOAT,
                required=False,
                description="Estimated hours to complete",
                min_value=0.0,
                max_value=1000.0,
                introduced_in="1.1.0",
            )
        )
        requirement_fields_v1_1.append(
            SchemaField(
                name="assignee",
                field_type=FieldType.STRING,
                required=False,
                description="Assigned user ID",
                introduced_in="1.1.0",
            )
        )

        self.register_schema(
            name="requirement",
            version="1.1.0",
            description="Core requirement schema with estimation support",
            fields=requirement_fields_v1_1,
            supported_services=[ServiceType.ALL],
            migration_notes="Compatible upgrade. New optional fields: estimated_hours, assignee",
            examples=[
                {
                    "requirement_id": "550e8400-e29b-41d4-a716-446655440000",
                    "title": "Implement user authentication",
                    "description": "Add OAuth2 authentication with Google and GitHub providers",
                    "priority": "high",
                    "type": "feature",
                    "created_at": "2025-01-15T10:30:00Z",
                    "created_by": "user_123",
                    "tags": ["auth", "security"],
                    "estimated_hours": 16.0,
                    "assignee": "dev_456",
                }
            ],
        )

        # Workflow Input Schema
        workflow_fields = [
            SchemaField(
                name="session_id",
                field_type=FieldType.UUID,
                required=True,
                description="Unique session identifier",
            ),
            SchemaField(
                name="requirement",
                field_type=FieldType.STRING,
                required=True,
                description="Requirement text or ID",
                min_length=1,
            ),
            SchemaField(
                name="personas",
                field_type=FieldType.ARRAY,
                required=False,
                description="List of persona IDs",
                array_item_type=FieldType.STRING,
                default=[],
            ),
            SchemaField(
                name="workflow_type",
                field_type=FieldType.ENUM,
                required=False,
                description="Type of workflow",
                enum_values=["standard", "expedited", "review"],
                default="standard",
            ),
            SchemaField(
                name="config",
                field_type=FieldType.OBJECT,
                required=False,
                description="Workflow configuration",
                default={},
            ),
        ]

        self.register_schema(
            name="workflow_input",
            version="1.0.0",
            description="Schema for workflow initiation requests",
            fields=workflow_fields,
            supported_services=[ServiceType.BFF, ServiceType.BACKEND, ServiceType.ENGINE],
            examples=[
                {
                    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "requirement": "Build a REST API for user management",
                    "personas": ["backend_developer", "qa_engineer"],
                    "workflow_type": "standard",
                    "config": {"max_iterations": 3},
                }
            ],
        )

    # ========================================================================
    # AC-1: Schemas versioned; incompatible changes blocked without migration
    # ========================================================================

    def register_schema(
        self,
        name: str,
        version: str,
        description: str,
        fields: List[SchemaField],
        supported_services: List[ServiceType] = None,
        migration_notes: Optional[str] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SchemaDefinition:
        """
        Register a new schema version.
        AC-1: Schemas versioned.
        """
        now = datetime.now().isoformat()

        schema = SchemaDefinition(
            schema_id=f"{name}_{version}",
            name=name,
            version=version,
            description=description,
            fields=fields,
            created_at=now,
            updated_at=now,
            supported_services=supported_services or [ServiceType.ALL],
            migration_notes=migration_notes,
            examples=examples or [],
            metadata=metadata or {},
        )

        if name not in self._schemas:
            self._schemas[name] = {}

        self._schemas[name][version] = schema
        self._current_versions[name] = version

        logger.info(f"Registered schema: {name} v{version}")
        return schema

    def get_schema(
        self,
        name: str,
        version: Optional[str] = None,
    ) -> Optional[SchemaDefinition]:
        """Get a schema by name and optional version."""
        if name not in self._schemas:
            return None

        if version is None:
            version = self._current_versions.get(name)

        return self._schemas[name].get(version)

    def get_schema_versions(self, name: str) -> List[str]:
        """Get all versions of a schema."""
        if name not in self._schemas:
            return []
        return sorted(self._schemas[name].keys())

    def check_compatibility(
        self,
        name: str,
        from_version: str,
        to_version: str,
    ) -> CompatibilityResult:
        """
        Check compatibility between schema versions.
        AC-1: Incompatible changes blocked without migration notes.
        """
        from_schema = self.get_schema(name, from_version)
        to_schema = self.get_schema(name, to_version)

        if not from_schema or not to_schema:
            return CompatibilityResult(
                is_compatible=False,
                change_type=ChangeType.BREAKING,
                breaking_changes=["Schema version not found"],
                compatible_changes=[],
                deprecated_fields=[],
                migration_required=True,
            )

        breaking_changes = []
        compatible_changes = []
        deprecated_fields = []

        from_fields = {f.name: f for f in from_schema.fields}
        to_fields = {f.name: f for f in to_schema.fields}

        # Check for removed required fields (breaking)
        for field_name, field in from_fields.items():
            if field_name not in to_fields:
                if field.required:
                    breaking_changes.append(f"Required field '{field_name}' removed")
                else:
                    compatible_changes.append(f"Optional field '{field_name}' removed")
            elif to_fields[field_name].deprecated and not field.deprecated:
                deprecated_fields.append(field_name)

        # Check for new required fields without defaults (breaking)
        for field_name, field in to_fields.items():
            if field_name not in from_fields:
                if field.required and field.default is None:
                    breaking_changes.append(
                        f"New required field '{field_name}' without default"
                    )
                else:
                    compatible_changes.append(f"New field '{field_name}' added")

        # Check for type changes (breaking)
        for field_name in set(from_fields.keys()) & set(to_fields.keys()):
            if from_fields[field_name].field_type != to_fields[field_name].field_type:
                breaking_changes.append(
                    f"Field '{field_name}' type changed from "
                    f"{from_fields[field_name].field_type.value} to "
                    f"{to_fields[field_name].field_type.value}"
                )

        is_compatible = len(breaking_changes) == 0
        change_type = (
            ChangeType.COMPATIBLE if is_compatible
            else ChangeType.BREAKING
        )

        migration_required = not is_compatible
        migration_notes = to_schema.migration_notes if migration_required else None

        return CompatibilityResult(
            is_compatible=is_compatible,
            change_type=change_type,
            breaking_changes=breaking_changes,
            compatible_changes=compatible_changes,
            deprecated_fields=deprecated_fields,
            migration_required=migration_required,
            migration_notes=migration_notes,
        )

    def can_upgrade(
        self,
        name: str,
        from_version: str,
        to_version: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if upgrade is allowed.
        AC-1: Incompatible changes blocked without migration notes.
        """
        result = self.check_compatibility(name, from_version, to_version)

        if result.is_compatible:
            return True, None

        if result.migration_required and not result.migration_notes:
            return False, "Breaking changes detected but no migration notes provided"

        return True, result.migration_notes

    # ========================================================================
    # AC-2: Validation errors returned with actionable messages
    # ========================================================================

    def validate(
        self,
        data: Dict[str, Any],
        schema_name: str,
        schema_version: Optional[str] = None,
        service_type: ServiceType = ServiceType.ALL,
    ) -> ValidationResult:
        """
        Validate data against a schema.
        AC-2: Validation errors returned with actionable messages.
        """
        schema = self.get_schema(schema_name, schema_version)
        if not schema:
            return ValidationResult(
                is_valid=False,
                errors=[
                    ValidationError(
                        field="_schema",
                        message=f"Schema '{schema_name}' not found",
                        severity=ValidationSeverity.ERROR,
                        suggestion=f"Available schemas: {list(self._schemas.keys())}",
                    )
                ],
                warnings=[],
                validated_at=datetime.now().isoformat(),
                schema_version=schema_version or "unknown",
            )

        errors = []
        warnings = []

        for field_def in schema.fields:
            field_errors, field_warnings = self._validate_field(
                data, field_def, schema_name
            )
            errors.extend(field_errors)
            warnings.extend(field_warnings)

        # Check for unknown fields
        known_fields = {f.name for f in schema.fields}
        for key in data.keys():
            if key not in known_fields:
                warnings.append(
                    ValidationError(
                        field=key,
                        message=f"Unknown field '{key}' not in schema",
                        severity=ValidationSeverity.WARNING,
                        suggestion=f"Valid fields: {sorted(known_fields)}",
                    )
                )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            validated_at=datetime.now().isoformat(),
            schema_version=schema.version,
        )

    def _validate_field(
        self,
        data: Dict[str, Any],
        field_def: SchemaField,
        schema_name: str,
    ) -> Tuple[List[ValidationError], List[ValidationError]]:
        """Validate a single field with actionable messages."""
        errors = []
        warnings = []
        field_name = field_def.name

        # Check deprecated
        if field_def.deprecated and field_name in data:
            warnings.append(
                ValidationError(
                    field=field_name,
                    message=field_def.deprecated_message or f"Field '{field_name}' is deprecated",
                    severity=ValidationSeverity.WARNING,
                    suggestion="Consider migrating to the replacement field",
                    documentation_link=f"/docs/schemas/{schema_name}#deprecations",
                )
            )

        # Check required
        if field_def.required and field_name not in data:
            errors.append(
                ValidationError(
                    field=field_name,
                    message=f"Required field '{field_name}' is missing",
                    severity=ValidationSeverity.ERROR,
                    expected=f"Value of type {field_def.field_type.value}",
                    actual="<missing>",
                    suggestion=f"Add '{field_name}' with a {field_def.field_type.value} value. {field_def.description}",
                    documentation_link=f"/docs/schemas/{schema_name}#fields",
                )
            )
            return errors, warnings

        if field_name not in data:
            return errors, warnings

        value = data[field_name]

        # Type validation
        type_valid, type_error = self._validate_type(value, field_def)
        if not type_valid:
            errors.append(
                ValidationError(
                    field=field_name,
                    message=type_error,
                    severity=ValidationSeverity.ERROR,
                    expected=field_def.field_type.value,
                    actual=type(value).__name__,
                    suggestion=f"Provide a value of type {field_def.field_type.value}",
                )
            )
            return errors, warnings

        # String constraints
        if field_def.field_type == FieldType.STRING and isinstance(value, str):
            if field_def.min_length and len(value) < field_def.min_length:
                errors.append(
                    ValidationError(
                        field=field_name,
                        message=f"String too short: {len(value)} < {field_def.min_length}",
                        severity=ValidationSeverity.ERROR,
                        expected=f">= {field_def.min_length} characters",
                        actual=f"{len(value)} characters",
                        suggestion=f"Provide at least {field_def.min_length} characters",
                    )
                )

            if field_def.max_length and len(value) > field_def.max_length:
                errors.append(
                    ValidationError(
                        field=field_name,
                        message=f"String too long: {len(value)} > {field_def.max_length}",
                        severity=ValidationSeverity.ERROR,
                        expected=f"<= {field_def.max_length} characters",
                        actual=f"{len(value)} characters",
                        suggestion=f"Limit to {field_def.max_length} characters",
                    )
                )

            if field_def.pattern:
                if not re.match(field_def.pattern, value):
                    errors.append(
                        ValidationError(
                            field=field_name,
                            message=f"String does not match pattern: {field_def.pattern}",
                            severity=ValidationSeverity.ERROR,
                            expected=f"Match pattern: {field_def.pattern}",
                            actual=value,
                            suggestion="Check the format and try again",
                        )
                    )

        # Numeric constraints
        if field_def.field_type in (FieldType.INTEGER, FieldType.FLOAT):
            if field_def.min_value is not None and value < field_def.min_value:
                errors.append(
                    ValidationError(
                        field=field_name,
                        message=f"Value too small: {value} < {field_def.min_value}",
                        severity=ValidationSeverity.ERROR,
                        expected=f">= {field_def.min_value}",
                        actual=value,
                        suggestion=f"Provide a value >= {field_def.min_value}",
                    )
                )

            if field_def.max_value is not None and value > field_def.max_value:
                errors.append(
                    ValidationError(
                        field=field_name,
                        message=f"Value too large: {value} > {field_def.max_value}",
                        severity=ValidationSeverity.ERROR,
                        expected=f"<= {field_def.max_value}",
                        actual=value,
                        suggestion=f"Provide a value <= {field_def.max_value}",
                    )
                )

        # Enum validation
        if field_def.field_type == FieldType.ENUM:
            if value not in field_def.enum_values:
                errors.append(
                    ValidationError(
                        field=field_name,
                        message=f"Invalid enum value: '{value}'",
                        severity=ValidationSeverity.ERROR,
                        expected=f"One of: {field_def.enum_values}",
                        actual=value,
                        suggestion=f"Use one of: {', '.join(field_def.enum_values)}",
                    )
                )

        return errors, warnings

    def _validate_type(
        self,
        value: Any,
        field_def: SchemaField,
    ) -> Tuple[bool, Optional[str]]:
        """Validate value type."""
        field_type = field_def.field_type

        if field_type == FieldType.STRING:
            return isinstance(value, str), f"Expected string, got {type(value).__name__}"

        if field_type == FieldType.INTEGER:
            return isinstance(value, int) and not isinstance(value, bool), \
                f"Expected integer, got {type(value).__name__}"

        if field_type == FieldType.FLOAT:
            return isinstance(value, (int, float)) and not isinstance(value, bool), \
                f"Expected number, got {type(value).__name__}"

        if field_type == FieldType.BOOLEAN:
            return isinstance(value, bool), f"Expected boolean, got {type(value).__name__}"

        if field_type == FieldType.ARRAY:
            return isinstance(value, list), f"Expected array, got {type(value).__name__}"

        if field_type == FieldType.OBJECT:
            return isinstance(value, dict), f"Expected object, got {type(value).__name__}"

        if field_type == FieldType.DATETIME:
            if isinstance(value, str):
                try:
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return True, None
                except ValueError:
                    return False, "Expected ISO 8601 datetime string"
            return False, f"Expected datetime string, got {type(value).__name__}"

        if field_type == FieldType.UUID:
            if isinstance(value, str):
                uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                if re.match(uuid_pattern, value.lower()):
                    return True, None
                return False, "Expected valid UUID format"
            return False, f"Expected UUID string, got {type(value).__name__}"

        if field_type == FieldType.ENUM:
            return isinstance(value, str), f"Expected enum string, got {type(value).__name__}"

        return True, None

    # ========================================================================
    # AC-3: Contract doc published; examples covered by tests
    # ========================================================================

    def get_contract_documentation(
        self,
        schema_name: str,
        schema_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get contract documentation for a schema.
        AC-3: Contract doc published.
        """
        schema = self.get_schema(schema_name, schema_version)
        if not schema:
            return {"error": f"Schema '{schema_name}' not found"}

        return {
            "schema": schema.to_dict(),
            "documentation": {
                "overview": schema.description,
                "version": schema.version,
                "supported_services": [s.value for s in schema.supported_services],
                "fields": [
                    {
                        "name": f.name,
                        "type": f.field_type.value,
                        "required": f.required,
                        "description": f.description,
                        "constraints": {
                            k: v for k, v in {
                                "min_length": f.min_length,
                                "max_length": f.max_length,
                                "min_value": f.min_value,
                                "max_value": f.max_value,
                                "pattern": f.pattern,
                                "enum_values": f.enum_values or None,
                            }.items() if v is not None
                        },
                    }
                    for f in schema.fields
                ],
                "examples": schema.examples,
                "migration_notes": schema.migration_notes,
            },
        }

    def get_examples(
        self,
        schema_name: str,
        schema_version: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get examples for a schema.
        AC-3: Examples covered by tests.
        """
        schema = self.get_schema(schema_name, schema_version)
        if not schema:
            return []
        return schema.examples

    def validate_examples(
        self,
        schema_name: str,
        schema_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate all examples in a schema.
        AC-3: Examples covered by tests.
        """
        schema = self.get_schema(schema_name, schema_version)
        if not schema:
            return {"error": f"Schema '{schema_name}' not found"}

        results = []
        all_valid = True

        for i, example in enumerate(schema.examples):
            result = self.validate(example, schema_name, schema_version)
            results.append({
                "example_index": i,
                "is_valid": result.is_valid,
                "errors": [e.to_dict() for e in result.errors],
            })
            if not result.is_valid:
                all_valid = False

        return {
            "schema": schema_name,
            "version": schema.version,
            "all_examples_valid": all_valid,
            "results": results,
        }

    def list_schemas(self) -> List[Dict[str, Any]]:
        """List all registered schemas."""
        return [
            {
                "name": name,
                "current_version": self._current_versions.get(name),
                "versions": sorted(versions.keys()),
            }
            for name, versions in self._schemas.items()
        ]

    def get_service_info(self) -> Dict[str, Any]:
        """Get service information."""
        return {
            "service": "requirement_schema_service",
            "version": "1.0.0",
            "total_schemas": len(self._schemas),
            "total_versions": sum(len(v) for v in self._schemas.values()),
        }


# Singleton instance
_service_instance: Optional[RequirementSchemaService] = None


def get_requirement_schema_service() -> RequirementSchemaService:
    """Get the singleton service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = RequirementSchemaService()
    return _service_instance
