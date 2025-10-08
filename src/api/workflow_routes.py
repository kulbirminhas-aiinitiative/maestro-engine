#!/usr/bin/env python3
"""
Workflow Routes for MAESTRO Backend API
Exposes enhanced_lean_ultimate_mega_team_utcp functionality
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.models import QualityValidation, TemplateExtraction, WorkflowRequest, WorkflowResponse

# Import UTCP workflow
try:
    from maestro_mcp.enhanced_lean_ultimate_mega_team_utcp import (
        EnhancedTeamConfig,
        execute_enhanced_lean_workflow_utcp,
    )

    UTCP_AVAILABLE = True
except ImportError as e:
    logging.error(f"Failed to import UTCP workflow: {e}")
    UTCP_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflow", tags=["Workflow"])

# Execution statistics
execution_stats = {"total": 0, "successful": 0, "failed": 0, "total_time": 0.0}


@router.post("/execute", response_model=WorkflowResponse)
async def execute_workflow(request: WorkflowRequest):
    """
    Execute MAESTRO workflow with UTCP support

    This endpoint exposes the enhanced_lean_ultimate_mega_team_utcp workflow,
    which can execute either via distributed UTCP services or locally.

    Features:
    - Distributed execution via UTCP (if enabled)
    - RAG template retrieval for context enhancement
    - Quality validation via Quality-Fabric
    - Template extraction and Git publishing
    - MCP context sharing
    """

    if not UTCP_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="UTCP workflow engine not available. Check server configuration.",
        )

    start_time = time.time()
    execution_stats["total"] += 1

    try:
        # Build configuration
        config = EnhancedTeamConfig(
            selected_personas=request.selected_personas,
            enable_rag=request.enable_rag,
            enable_mcp=request.enable_mcp,
            enable_utcp=request.enable_utcp,
            session_id=request.session_id or f"api_session_{int(time.time())}",
            project_path=request.project_path or "",
            max_execution_time=request.max_execution_time,
            cache_enabled=True,
            async_operations=True,
            resource_cleanup=True,
        )

        logger.info(f"🚀 Executing workflow: {request.requirement[:100]}...")
        logger.info(
            f"📋 Config: UTCP={request.enable_utcp}, RAG={request.enable_rag}, MCP={request.enable_mcp}"
        )

        # Execute workflow
        result = await execute_enhanced_lean_workflow_utcp(
            requirement=request.requirement, config=config
        )

        execution_time = time.time() - start_time
        execution_stats["total_time"] += execution_time

        # Check success
        if result.get("success"):
            execution_stats["successful"] += 1
            logger.info(f"✅ Workflow completed successfully in {execution_time:.2f}s")
        else:
            execution_stats["failed"] += 1
            logger.warning(f"⚠️ Workflow failed: {result.get('error', 'Unknown error')}")

        # Build response with optional fields
        response_data = {
            "success": result.get("success", False),
            "session_id": result.get("session_id", config.session_id),
            "requirement": result.get("requirement", request.requirement),
            "execution_method": result.get("execution_method", "unknown"),
            "files_generated": result.get("files_generated", []),
            "total_execution_time": result.get("total_execution_time", execution_time),
            "project_path": result.get("project_path", config.project_path),
            "team_members": result.get("team_members", config.selected_personas or []),
            "start_time": result.get("start_time"),
            "artifacts": result.get("artifacts"),
            "error": result.get("error"),
        }

        # Add quality validation if available
        if result.get("quality_validation"):
            qv = result["quality_validation"]
            response_data["quality_validation"] = QualityValidation(
                execution_id=qv.get("execution_id"),
                quality_score=qv.get("quality_score"),
                security_score=qv.get("security_score"),
                performance_score=qv.get("performance_score"),
                maintainability_score=qv.get("maintainability_score"),
                test_coverage=qv.get("test_coverage"),
                test_results=qv.get("test_results"),
                duration=qv.get("duration"),
                recommendations=qv.get("recommendations"),
                issues=qv.get("issues"),
            )

        # Add template extraction if available
        if result.get("template_extraction"):
            te = result["template_extraction"]
            response_data["template_extraction"] = TemplateExtraction(
                templates_created=te.get("templates_created", 0),
                template_ids=te.get("template_ids", []),
                extraction_time=te.get("extraction_time"),
            )

        # Add Git template URL if available
        if result.get("git_template"):
            response_data["git_template_url"] = result["git_template"].get("git_url")

        return WorkflowResponse(**response_data)

    except Exception as e:
        execution_stats["failed"] += 1
        execution_time = time.time() - start_time
        execution_stats["total_time"] += execution_time

        logger.error(f"❌ Workflow execution failed: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail={
                "error": "Workflow execution failed",
                "message": str(e),
                "requirement": request.requirement,
                "execution_time": execution_time,
            },
        )


@router.get("/stats")
async def get_execution_stats():
    """Get workflow execution statistics"""
    avg_time = (
        execution_stats["total_time"] / execution_stats["total"]
        if execution_stats["total"] > 0
        else 0.0
    )

    return {
        "total_executions": execution_stats["total"],
        "successful_executions": execution_stats["successful"],
        "failed_executions": execution_stats["failed"],
        "success_rate": (
            (execution_stats["successful"] / execution_stats["total"] * 100)
            if execution_stats["total"] > 0
            else 0.0
        ),
        "average_execution_time": avg_time,
        "total_execution_time": execution_stats["total_time"],
        "utcp_available": UTCP_AVAILABLE,
    }


@router.post("/stats/reset")
async def reset_execution_stats():
    """Reset execution statistics (admin endpoint)"""
    execution_stats["total"] = 0
    execution_stats["successful"] = 0
    execution_stats["failed"] = 0
    execution_stats["total_time"] = 0.0

    return {
        "message": "Execution statistics reset successfully",
        "timestamp": datetime.now().isoformat(),
    }
