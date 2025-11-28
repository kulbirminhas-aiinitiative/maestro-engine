#!/usr/bin/env python3
"""
Quality Fabric Enforcement API Routes
Implements EPIC-4 (ME-400): Quality Fabric Enforcement

REST API endpoints for quality enforcement:
- GET /api/quality/config - Get enforcement configuration
- GET /api/quality/mappings - Get phase-to-test mappings
- POST /api/quality/mappings - Set custom phase mapping
- POST /api/quality/validate - Validate a phase
- POST /api/quality/waivers - Grant a waiver
- GET /api/quality/waivers/{workflow_id} - Get waivers for workflow
- GET /api/quality/history - Get validation history
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel, Field

# Import enforcement service
try:
    from services.quality_fabric_enforcement import (
        get_enforcement_service,
        QualityFabricEnforcementService,
        WaiverType,
        TestCategory,
        EnforcementLevel,
    )
    HAS_ENFORCEMENT_SERVICE = True
except ImportError:
    HAS_ENFORCEMENT_SERVICE = False

logger = logging.getLogger("quality_enforcement_routes")

# Create router
router = APIRouter(prefix="/api/quality", tags=["quality-enforcement"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class PhaseValidationRequest(BaseModel):
    """Request to validate a phase."""
    phase_id: str = Field(..., description="Phase ID")
    phase_type: str = Field(..., description="Phase type (requirements, design, etc.)")
    workflow_id: str = Field(..., description="Workflow ID")
    session_id: Optional[str] = Field(None, description="Session ID")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class PhaseMappingRequest(BaseModel):
    """Request to set phase mapping."""
    phase_type: str = Field(..., description="Phase type")
    test_categories: List[str] = Field(..., description="Test categories")
    custom_scenarios: Optional[List[Dict[str, Any]]] = Field(None, description="Custom test scenarios")
    thresholds: Optional[Dict[str, Any]] = Field(None, description="Custom thresholds")


class WaiverRequest(BaseModel):
    """Request to grant a waiver."""
    phase_id: str = Field(..., description="Phase ID")
    workflow_id: str = Field(..., description="Workflow ID")
    waiver_type: str = Field(..., description="Waiver type: emergency, technical_debt, external_dependency, temporary, executive")
    reason: str = Field(..., description="Reason for waiver")
    granted_by: str = Field(..., description="Who is granting the waiver")
    expires_at: Optional[str] = Field(None, description="Optional expiration timestamp")
    conditions: Optional[Dict[str, Any]] = Field(None, description="Optional conditions")


class ValidationResultResponse(BaseModel):
    """Quality validation result response."""
    validation_id: str
    phase_id: str
    workflow_id: str
    session_id: Optional[str]
    total_tests: int
    passed_tests: int
    failed_tests: int
    error_tests: int
    skipped_tests: int
    test_pass_rate: float
    test_coverage: float
    quality_score: float
    thresholds_met: bool
    threshold_violations: List[Dict[str, Any]]
    evidence_uri: str
    artifacts: List[str]
    execution_time_ms: float
    timestamp: str
    waiver_applied: bool
    waiver_reason: Optional[str]
    should_block_gate: bool
    block_reason: str


class EnforcementConfigResponse(BaseModel):
    """Enforcement configuration response."""
    environment: str
    enforcement_level: str
    feature_flag_enabled: bool
    is_enabled: bool
    thresholds: Dict[str, Any]
    quality_fabric_url: str


class PhaseMappingResponse(BaseModel):
    """Phase mapping response."""
    phase_id: str
    phase_type: str
    test_categories: List[str]
    custom_scenarios: List[Dict[str, Any]]
    enforcement_level: str
    is_valid: bool
    validation_message: str


class WaiverResponse(BaseModel):
    """Waiver response."""
    waiver_id: str
    phase_id: str
    workflow_id: str
    waiver_type: str
    reason: str
    granted_by: str
    granted_at: str
    expires_at: Optional[str]
    conditions: Dict[str, Any]


class ConfigUploadRequest(BaseModel):
    """Request to upload YAML config."""
    config_content: str = Field(..., description="YAML config content as string")
    save_to_file: bool = Field(False, description="Whether to save config to file")


class ConfigInfoResponse(BaseModel):
    """Response with config info."""
    config_loaded: bool
    config_path: Optional[str]
    config_version: str
    phases_from_config: List[str]
    environments_configured: List[str]


class RollbackCheckRequest(BaseModel):
    """Request to check if rollback is needed."""
    workflow_id: str = Field(..., description="Workflow ID")
    phase_id: str = Field(..., description="Phase ID")
    phase_type: str = Field(..., description="Phase type")
    validation_id: str = Field(..., description="Validation ID to check")


class RollbackResponse(BaseModel):
    """Rollback response."""
    rollback_id: str
    workflow_id: str
    phase_id: str
    reason: str
    triggered_at: str
    status: str
    context: Dict[str, Any]


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/health")
async def quality_enforcement_health():
    """Health check for quality enforcement service."""
    return {
        "status": "healthy" if HAS_ENFORCEMENT_SERVICE else "unavailable",
        "service": "quality-fabric-enforcement",
        "timestamp": datetime.now().isoformat(),
        "feature_flag": "FF_QUALITY_FABRIC_ENFORCEMENT",
    }


@router.get("/config", response_model=EnforcementConfigResponse)
async def get_enforcement_config():
    """
    Get current enforcement configuration.

    Returns environment, enforcement level, thresholds, and enablement status.
    """
    if not HAS_ENFORCEMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Quality enforcement service not available")

    service = get_enforcement_service()
    config = service.get_enforcement_config()

    return EnforcementConfigResponse(**config)


@router.get("/mappings")
async def get_phase_mappings(
    phase_type: Optional[str] = Query(None, description="Specific phase type to get"),
):
    """
    Get phase-to-test mappings.

    Query parameters:
    - phase_type: Optional specific phase type to retrieve
    """
    if not HAS_ENFORCEMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Quality enforcement service not available")

    service = get_enforcement_service()

    if phase_type:
        mapping = service.get_phase_mapping(phase_type)
        valid, msg = service.validate_phase_mapping(phase_type)

        return PhaseMappingResponse(
            phase_id=mapping.phase_id,
            phase_type=mapping.phase_type,
            test_categories=mapping.test_categories,
            custom_scenarios=mapping.custom_scenarios,
            enforcement_level=mapping.enforcement_level.value,
            is_valid=valid,
            validation_message=msg,
        )

    # Return all default mappings
    from services.quality_fabric_enforcement import DEFAULT_PHASE_TEST_MAPPING

    mappings = []
    for pt in DEFAULT_PHASE_TEST_MAPPING.keys():
        mapping = service.get_phase_mapping(pt)
        valid, msg = service.validate_phase_mapping(pt)
        mappings.append({
            "phase_id": mapping.phase_id,
            "phase_type": mapping.phase_type,
            "test_categories": mapping.test_categories,
            "enforcement_level": mapping.enforcement_level.value,
            "is_valid": valid,
            "validation_message": msg,
        })

    return {"mappings": mappings, "total": len(mappings)}


@router.post("/mappings", response_model=PhaseMappingResponse)
async def set_phase_mapping(request: PhaseMappingRequest):
    """
    Set custom phase-to-test mapping.

    Creates or updates the mapping of test categories to a phase type.
    """
    if not HAS_ENFORCEMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Quality enforcement service not available")

    service = get_enforcement_service()

    mapping = service.set_phase_mapping(
        phase_type=request.phase_type,
        test_categories=request.test_categories,
        custom_scenarios=request.custom_scenarios,
        thresholds=request.thresholds,
    )

    valid, msg = service.validate_phase_mapping(request.phase_type)

    return PhaseMappingResponse(
        phase_id=mapping.phase_id,
        phase_type=mapping.phase_type,
        test_categories=mapping.test_categories,
        custom_scenarios=mapping.custom_scenarios,
        enforcement_level=mapping.enforcement_level.value,
        is_valid=valid,
        validation_message=msg,
    )


@router.post("/validate", response_model=ValidationResultResponse)
async def validate_phase(request: PhaseValidationRequest):
    """
    Validate a phase using Quality Fabric.

    Executes quality validation and returns results with gate blocking decision.
    """
    if not HAS_ENFORCEMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Quality enforcement service not available")

    service = get_enforcement_service()

    # Execute validation
    result = await service.validate_phase(
        phase_id=request.phase_id,
        phase_type=request.phase_type,
        workflow_id=request.workflow_id,
        session_id=request.session_id,
        context=request.context or {},
    )

    # Check if waiver exists
    waiver = service.get_waiver(request.phase_id, request.workflow_id)

    # Determine if gate should be blocked
    should_block, block_reason = service.should_block_gate(result, waiver)

    return ValidationResultResponse(
        **result.to_dict(),
        should_block_gate=should_block,
        block_reason=block_reason,
    )


@router.post("/waivers", response_model=WaiverResponse)
async def grant_waiver(request: WaiverRequest):
    """
    Grant a waiver for bypassing quality gates.

    Creates a waiver that allows a phase to pass quality gates even if thresholds are not met.
    """
    if not HAS_ENFORCEMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Quality enforcement service not available")

    try:
        waiver_type = WaiverType(request.waiver_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid waiver type. Valid types: {[t.value for t in WaiverType]}"
        )

    service = get_enforcement_service()

    waiver = service.grant_waiver(
        phase_id=request.phase_id,
        workflow_id=request.workflow_id,
        waiver_type=waiver_type,
        reason=request.reason,
        granted_by=request.granted_by,
        expires_at=request.expires_at,
        conditions=request.conditions,
    )

    return WaiverResponse(**waiver.to_dict())


@router.get("/waivers/{workflow_id}")
async def get_waivers(
    workflow_id: str,
    phase_id: Optional[str] = Query(None, description="Filter by phase ID"),
):
    """
    Get waivers for a workflow.

    Query parameters:
    - phase_id: Optional filter by specific phase
    """
    if not HAS_ENFORCEMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Quality enforcement service not available")

    service = get_enforcement_service()

    waivers = []
    for waiver in service._waivers.values():
        if waiver.workflow_id == workflow_id:
            if phase_id is None or waiver.phase_id == phase_id:
                waivers.append(waiver.to_dict())

    return {"waivers": waivers, "total": len(waivers)}


@router.get("/history")
async def get_validation_history(
    workflow_id: Optional[str] = Query(None, description="Filter by workflow ID"),
    phase_id: Optional[str] = Query(None, description="Filter by phase ID"),
    limit: int = Query(100, description="Maximum results to return"),
):
    """
    Get validation history.

    Query parameters:
    - workflow_id: Optional filter by workflow
    - phase_id: Optional filter by phase
    - limit: Maximum number of results (default 100)
    """
    if not HAS_ENFORCEMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Quality enforcement service not available")

    service = get_enforcement_service()

    history = service.get_validation_history(
        workflow_id=workflow_id,
        phase_id=phase_id,
        limit=limit,
    )

    return {
        "validations": [r.to_dict() for r in history],
        "total": len(history),
    }


@router.get("/evidence/{validation_id}")
async def get_validation_evidence(validation_id: str):
    """
    Get gate evidence for a validation result.

    Returns evidence suitable for attaching to a gate.
    """
    if not HAS_ENFORCEMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Quality enforcement service not available")

    service = get_enforcement_service()

    # Find validation in history
    for result in service._validation_history:
        if result.validation_id == validation_id:
            evidence = service.create_gate_evidence(result)
            return evidence

    raise HTTPException(status_code=404, detail=f"Validation not found: {validation_id}")


# ============================================================================
# QF-200: CONFIG & ROLLBACK ENDPOINTS
# ============================================================================

@router.get("/config/info", response_model=ConfigInfoResponse)
async def get_config_info():
    """
    Get information about loaded YAML configuration.

    Returns details about the currently loaded phase-test mapping config.
    Part of QF-200: Phase-Test Mapping with Threshold Enforcement.
    """
    if not HAS_ENFORCEMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Quality enforcement service not available")

    service = get_enforcement_service()
    info = service.get_config_info()

    return ConfigInfoResponse(**info)


@router.post("/config/upload")
async def upload_config(request: ConfigUploadRequest):
    """
    Upload YAML configuration for phase-test mappings.

    Parses and validates the YAML config, optionally saving to file.
    Part of QF-200: Phase-Test Mapping with Threshold Enforcement.
    """
    if not HAS_ENFORCEMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Quality enforcement service not available")

    import yaml
    from pathlib import Path

    try:
        # Parse YAML content
        config = yaml.safe_load(request.config_content)
        if not config:
            raise HTTPException(status_code=400, detail="Empty or invalid YAML content")

        # Validate structure
        if "phase_test_map" not in config:
            raise HTTPException(status_code=400, detail="Config must contain 'phase_test_map' key")

        # Optionally save to file
        config_path = None
        if request.save_to_file:
            from services.quality_fabric_enforcement import PhaseTestConfigLoader
            config_path = str(PhaseTestConfigLoader.DEFAULT_CONFIG_PATH)
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)

        # Reload the service config
        service = get_enforcement_service()
        if request.save_to_file:
            service.reload_config(config_path)
        else:
            # Temporarily apply config without saving
            service._yaml_config = config
            service._phase_mappings.clear()
            service._load_phase_mappings_from_config()

        return {
            "status": "success",
            "message": "Configuration uploaded and applied",
            "saved_to_file": request.save_to_file,
            "config_path": config_path,
            "phases_loaded": list(config.get("phase_test_map", {}).keys()),
        }

    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML syntax: {str(e)}")
    except Exception as e:
        logger.error(f"Config upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Config upload failed: {str(e)}")


@router.post("/config/reload")
async def reload_config(config_path: Optional[str] = None):
    """
    Reload configuration from file.

    Reloads the phase-test mapping configuration from the YAML file.
    Part of QF-200: Phase-Test Mapping with Threshold Enforcement.
    """
    if not HAS_ENFORCEMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Quality enforcement service not available")

    service = get_enforcement_service()
    success = service.reload_config(config_path)

    if success:
        info = service.get_config_info()
        return {
            "status": "success",
            "message": "Configuration reloaded",
            "config_info": info,
        }
    else:
        raise HTTPException(status_code=500, detail="Config reload failed")


@router.post("/rollback/check")
async def check_rollback_needed(request: RollbackCheckRequest):
    """
    Check if rollback is needed based on validation result.

    Evaluates whether a deployment should be rolled back based on test results.
    Part of QF-200: Phase-Test Mapping with Threshold Enforcement.
    """
    if not HAS_ENFORCEMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Quality enforcement service not available")

    service = get_enforcement_service()

    # Find validation in history
    validation_result = None
    for result in service._validation_history:
        if result.validation_id == request.validation_id:
            validation_result = result
            break

    if not validation_result:
        raise HTTPException(status_code=404, detail=f"Validation not found: {request.validation_id}")

    # Get phase mapping
    mapping = service.get_phase_mapping(request.phase_type)

    # Check if rollback needed
    should_rollback, reason = service.check_rollback_needed(validation_result, mapping)

    return {
        "should_rollback": should_rollback,
        "reason": reason,
        "validation_id": request.validation_id,
        "phase_type": request.phase_type,
        "rollback_on_fail_configured": mapping.rollback_on_fail,
    }


@router.post("/rollback/trigger")
async def trigger_rollback(
    workflow_id: str,
    phase_id: str,
    reason: str,
    context: Optional[Dict[str, Any]] = None,
):
    """
    Trigger a rollback for failed deployment.

    Initiates the rollback process for a deployment that failed quality checks.
    Part of QF-200: Phase-Test Mapping with Threshold Enforcement.
    """
    if not HAS_ENFORCEMENT_SERVICE:
        raise HTTPException(status_code=503, detail="Quality enforcement service not available")

    service = get_enforcement_service()

    result = await service.trigger_rollback(
        workflow_id=workflow_id,
        phase_id=phase_id,
        reason=reason,
        context=context,
    )

    return RollbackResponse(**result)


# ============================================================================
# HELPER FUNCTION TO REGISTER ROUTER
# ============================================================================

def register_quality_enforcement_routes(app):
    """Register quality enforcement routes with a FastAPI app."""
    app.include_router(router)
    logger.info("Quality enforcement routes registered")
