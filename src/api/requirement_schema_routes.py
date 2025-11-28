#!/usr/bin/env python3
"""
Requirement Schema API Routes
Implements Epic MD-1820 [ME-900] Requirement Schema Contract & Validation

REST API endpoints for schema management:
- GET /api/schemas - List all schemas
- GET /api/schemas/{name} - Get schema by name
- GET /api/schemas/{name}/versions - Get all versions
- POST /api/schemas/{name}/validate - Validate data against schema
- GET /api/schemas/{name}/compatibility - Check version compatibility
- GET /api/schemas/{name}/documentation - Get contract documentation
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# Import schema service
try:
    from services.requirement_schema_service import (
        get_requirement_schema_service,
        RequirementSchemaService,
        ServiceType,
    )
    HAS_SCHEMA_SERVICE = True
except ImportError:
    HAS_SCHEMA_SERVICE = False

logger = logging.getLogger("requirement_schema_routes")

# Create router
router = APIRouter(prefix="/api/schemas", tags=["requirement-schemas"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ValidateRequest(BaseModel):
    """Request to validate data."""
    data: Dict[str, Any] = Field(..., description="Data to validate")
    service_type: Optional[str] = Field("all", description="Service type context")


class RegisterSchemaRequest(BaseModel):
    """Request to register a new schema version."""
    name: str = Field(..., description="Schema name")
    version: str = Field(..., description="Version string (semver)")
    description: str = Field(..., description="Schema description")
    fields: List[Dict[str, Any]] = Field(..., description="Field definitions")
    supported_services: List[str] = Field(default=["all"])
    migration_notes: Optional[str] = Field(None)
    examples: List[Dict[str, Any]] = Field(default=[])


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/health")
async def schema_health():
    """Health check for schema service."""
    return {
        "status": "healthy" if HAS_SCHEMA_SERVICE else "unavailable",
        "service": "requirement-schemas",
    }


@router.get("")
async def list_schemas():
    """List all registered schemas."""
    if not HAS_SCHEMA_SERVICE:
        raise HTTPException(status_code=503, detail="Schema service not available")

    service = get_requirement_schema_service()
    return {
        "schemas": service.list_schemas(),
        "total": len(service.list_schemas()),
    }


@router.get("/{name}")
async def get_schema(
    name: str,
    version: Optional[str] = Query(None, description="Specific version"),
):
    """Get a schema by name and optional version."""
    if not HAS_SCHEMA_SERVICE:
        raise HTTPException(status_code=503, detail="Schema service not available")

    service = get_requirement_schema_service()
    schema = service.get_schema(name, version)

    if not schema:
        raise HTTPException(status_code=404, detail=f"Schema '{name}' not found")

    return schema.to_dict()


@router.get("/{name}/versions")
async def get_schema_versions(name: str):
    """Get all versions of a schema."""
    if not HAS_SCHEMA_SERVICE:
        raise HTTPException(status_code=503, detail="Schema service not available")

    service = get_requirement_schema_service()
    versions = service.get_schema_versions(name)

    if not versions:
        raise HTTPException(status_code=404, detail=f"Schema '{name}' not found")

    return {
        "name": name,
        "versions": versions,
        "current": versions[-1] if versions else None,
    }


@router.post("/{name}/validate")
async def validate_data(
    name: str,
    request: ValidateRequest,
    version: Optional[str] = Query(None, description="Schema version"),
):
    """
    Validate data against a schema.
    AC-2: Validation errors returned with actionable messages.
    """
    if not HAS_SCHEMA_SERVICE:
        raise HTTPException(status_code=503, detail="Schema service not available")

    service = get_requirement_schema_service()

    try:
        service_type = ServiceType(request.service_type) if request.service_type else ServiceType.ALL
    except ValueError:
        service_type = ServiceType.ALL

    result = service.validate(
        data=request.data,
        schema_name=name,
        schema_version=version,
        service_type=service_type,
    )

    return result.to_dict()


@router.get("/{name}/compatibility")
async def check_compatibility(
    name: str,
    from_version: str = Query(..., description="Source version"),
    to_version: str = Query(..., description="Target version"),
):
    """
    Check compatibility between schema versions.
    AC-1: Incompatible changes blocked without migration notes.
    """
    if not HAS_SCHEMA_SERVICE:
        raise HTTPException(status_code=503, detail="Schema service not available")

    service = get_requirement_schema_service()
    result = service.check_compatibility(name, from_version, to_version)

    return result.to_dict()


@router.get("/{name}/can-upgrade")
async def can_upgrade(
    name: str,
    from_version: str = Query(..., description="Source version"),
    to_version: str = Query(..., description="Target version"),
):
    """
    Check if upgrade is allowed.
    AC-1: Incompatible changes blocked without migration notes.
    """
    if not HAS_SCHEMA_SERVICE:
        raise HTTPException(status_code=503, detail="Schema service not available")

    service = get_requirement_schema_service()
    allowed, migration_notes = service.can_upgrade(name, from_version, to_version)

    return {
        "allowed": allowed,
        "migration_notes": migration_notes,
        "from_version": from_version,
        "to_version": to_version,
    }


@router.get("/{name}/documentation")
async def get_documentation(
    name: str,
    version: Optional[str] = Query(None, description="Schema version"),
):
    """
    Get contract documentation for a schema.
    AC-3: Contract doc published.
    """
    if not HAS_SCHEMA_SERVICE:
        raise HTTPException(status_code=503, detail="Schema service not available")

    service = get_requirement_schema_service()
    doc = service.get_contract_documentation(name, version)

    if "error" in doc:
        raise HTTPException(status_code=404, detail=doc["error"])

    return doc


@router.get("/{name}/examples")
async def get_examples(
    name: str,
    version: Optional[str] = Query(None, description="Schema version"),
):
    """
    Get examples for a schema.
    AC-3: Examples covered by tests.
    """
    if not HAS_SCHEMA_SERVICE:
        raise HTTPException(status_code=503, detail="Schema service not available")

    service = get_requirement_schema_service()
    examples = service.get_examples(name, version)

    return {
        "name": name,
        "examples": examples,
        "count": len(examples),
    }


@router.get("/{name}/validate-examples")
async def validate_examples(
    name: str,
    version: Optional[str] = Query(None, description="Schema version"),
):
    """
    Validate all examples in a schema.
    AC-3: Examples covered by tests.
    """
    if not HAS_SCHEMA_SERVICE:
        raise HTTPException(status_code=503, detail="Schema service not available")

    service = get_requirement_schema_service()
    result = service.validate_examples(name, version)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


# ============================================================================
# HELPER FUNCTION TO REGISTER ROUTER
# ============================================================================

def register_requirement_schema_routes(app):
    """Register requirement schema routes with a FastAPI app."""
    app.include_router(router)
    logger.info("Requirement schema routes registered")
