#!/usr/bin/env python3
"""
MAESTRO Backend API - Main Application
Exposes enhanced_lean_ultimate_mega_team_utcp workflow via REST API
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.models import HealthResponse, StatusResponse
from api.workflow_routes import router as workflow_router

# Symphony Demo (MD-3902) - Multi-Persona AI Conversation
try:
    from symphony.symphony_ws import router as symphony_router
    SYMPHONY_AVAILABLE = True
except ImportError as e:
    print(f"Symphony module not available: {e}")
    SYMPHONY_AVAILABLE = False
    symphony_router = None

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="MAESTRO Backend API",
    description="""
    MAESTRO Backend API for AI-powered development workflows

    ## Features
    - 🚀 Distributed execution via UTCP
    - 🔍 RAG template retrieval for enhanced context
    - ✅ Quality validation via Quality-Fabric
    - 📦 Template extraction and Git publishing
    - 🔗 MCP context sharing across personas

    ## Execution Flow
    1. Submit requirement via `/api/workflow/execute`
    2. Workflow executes via UTCP (distributed) or locally (fallback)
    3. RAG retrieves relevant templates from Template Registry
    4. AI team generates complete implementation
    5. Quality-Fabric validates output
    6. High-quality code extracted as templates
    7. Results returned with files, quality scores, and metadata

    ## Architecture
    - Frontend → Backend API (this service) → UTCP Workflow → UTCP Services
    - Fallback: Frontend → Backend API → Local Claude Tools
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include workflow routes
app.include_router(workflow_router)

# Include Symphony routes (MD-3902)
if SYMPHONY_AVAILABLE and symphony_router:
    app.include_router(symphony_router)
    print("✅ Symphony API routes registered at /symphony/*")


@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info("=" * 80)
    logger.info("🚀 MAESTRO Backend API Starting...")
    logger.info("=" * 80)
    logger.info(f"📚 Docs: http://localhost:5000/docs")
    logger.info(f"🔧 Health: http://localhost:5000/health")
    logger.info(f"📊 Stats: http://localhost:5000/api/workflow/stats")
    logger.info(f"🔄 Execute: POST http://localhost:5000/api/workflow/execute")
    logger.info("=" * 80)

    # Check dependencies
    try:
        from maestro_mcp.enhanced_lean_ultimate_mega_team_utcp import EnhancedTeamConfig

        logger.info("✅ UTCP workflow engine available")
    except ImportError as e:
        logger.error(f"❌ UTCP workflow engine not available: {e}")

    try:
        import httpx

        logger.info("✅ HTTPX available for UTCP client")
    except ImportError:
        logger.warning("⚠️ HTTPX not available - UTCP features may be limited")

    try:
        import chromadb

        logger.info("✅ ChromaDB available for RAG")
    except ImportError:
        logger.warning("⚠️ ChromaDB not available - RAG features disabled")

    logger.info("=" * 80)


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    logger.info("🛑 MAESTRO Backend API shutting down...")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "service": "MAESTRO Backend API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "execute_workflow": "POST /api/workflow/execute",
            "workflow_stats": "GET /api/workflow/stats",
        },
    }


async def check_service(url: str, timeout: float = 2.0) -> bool:
    """Check if a service is responding"""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            return response.status_code == 200
    except Exception:
        return False


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint

    Returns service health status and dependency availability.
    Now includes actual service availability checks (MD-3182 fix).
    """

    # Check dependencies (Python module imports)
    dependencies = {
        "utcp_workflow": False,
        "httpx": False,
        "chromadb": False,
        "claude_agent_sdk": False,
    }

    try:
        from maestro_mcp.enhanced_lean_ultimate_mega_team_utcp import EnhancedTeamConfig

        dependencies["utcp_workflow"] = True
    except ImportError:
        pass

    try:
        import httpx

        dependencies["httpx"] = True
    except ImportError:
        pass

    try:
        import chromadb

        dependencies["chromadb"] = True
    except ImportError:
        pass

    try:
        from claude_agent_sdk import query

        dependencies["claude_agent_sdk"] = True
    except ImportError:
        pass

    # MD-3182: Check actual service availability
    import asyncio
    service_checks = await asyncio.gather(
        check_service("http://localhost:19803/health"),  # RAG Service
        check_service("http://localhost:15001/health"),  # Workflow Service
        check_service("http://localhost:18002/health"),  # Coordinator
        check_service("http://localhost:18004/health"),  # Orchestration
        check_service("http://localhost:18200/api/v2/heartbeat"),  # ChromaDB
        return_exceptions=True
    )

    rag_available = service_checks[0] is True
    workflow_available = service_checks[1] is True
    coordinator_available = service_checks[2] is True
    orchestration_available = service_checks[3] is True
    chromadb_available = service_checks[4] is True

    # Update chromadb dependency based on actual service availability
    dependencies["chromadb"] = chromadb_available
    dependencies["utcp_workflow"] = workflow_available and coordinator_available

    # Determine features based on BOTH imports AND running services
    features = {
        "utcp_distributed_execution": dependencies["httpx"],
        "rag_template_retrieval": rag_available and chromadb_available,
        "workflow_execution": workflow_available,
        "chromadb": chromadb_available,
        "utcp_workflow": coordinator_available and orchestration_available,
        "claude_sdk": dependencies["claude_agent_sdk"],
    }

    # Determine overall status
    critical_deps = ["claude_agent_sdk"]
    critical_services = [workflow_available]

    if all(dependencies.get(dep, False) for dep in critical_deps) and all(critical_services):
        if all(features.values()):
            status = "healthy"
        else:
            status = "degraded"
    else:
        status = "degraded"

    return HealthResponse(
        status=status,
        timestamp=datetime.now().isoformat(),
        version="1.0.0",
        features=features,
        dependencies=dependencies,
    )


@app.get("/status", response_model=StatusResponse, tags=["Status"])
async def get_status():
    """
    Get service status with execution statistics
    """

    # Import stats from workflow routes
    from api.workflow_routes import execution_stats

    avg_time = (
        execution_stats["total_time"] / execution_stats["total"]
        if execution_stats["total"] > 0
        else 0.0
    )

    # Check if UTCP and RAG are enabled
    utcp_enabled = False
    rag_enabled = False

    try:
        import httpx

        utcp_enabled = True
    except ImportError:
        pass

    try:
        import chromadb

        rag_enabled = True
    except ImportError:
        pass

    return StatusResponse(
        total_executions=execution_stats["total"],
        successful_executions=execution_stats["successful"],
        failed_executions=execution_stats["failed"],
        average_execution_time=avg_time,
        utcp_enabled=utcp_enabled,
        rag_enabled=rag_enabled,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "message": str(exc), "path": str(request.url)},
    )


def start_server(host: str = "0.0.0.0", port: int = 5000, reload: bool = False):
    """
    Start the MAESTRO Backend API server

    Args:
        host: Host to bind to (default: 0.0.0.0)
        port: Port to bind to (default: 5000)
        reload: Enable auto-reload for development (default: False)
    """
    uvicorn.run("api.main:app", host=host, port=port, reload=reload, log_level="info")


if __name__ == "__main__":
    start_server(reload=True)
