#!/usr/bin/env python3
"""
MAESTRO Engine - Main FastAPI Application

Serves APIs for:
- Persona workflow execution (Schema v3.0)
- Legacy workflow APIs
- Health checks and monitoring
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Import logging
import logging

from api.document_api import router as document_router

# Import API routers
from api.persona_workflow_api import router as persona_workflow_router

# Import configuration
from config import get_settings

# Get settings
settings = get_settings()

# Configure logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    # Startup
    logger.info("=" * 80)
    logger.info(f"🚀 MAESTRO Engine Starting (v{settings.version})")
    logger.info("=" * 80)
    logger.info(f"🌐 Environment: {settings.environment}")
    logger.info(f"📦 Persona System: Schema v3.0")
    logger.info(f"🌐 Server: http://{settings.engine_host}:{settings.engine_port}")
    logger.info(f"📚 Docs: http://{settings.engine_host}:{settings.engine_port}/docs")
    logger.info(
        f"🔍 Health: http://{settings.engine_host}:{settings.engine_port}/api/workflow/health"
    )
    logger.info("=" * 80)

    # Preload personas to avoid async event loop issues
    logger.info("📦 Preloading Schema v3.0 personas...")
    from personas import get_adapter

    adapter = get_adapter()
    await adapter.ensure_loaded()
    persona_count = len(adapter.registry.personas)
    logger.info(f"✅ Loaded {persona_count} personas")
    logger.info("=" * 80)

    yield

    # Shutdown
    logger.info("👋 MAESTRO Engine Shutting Down")


# Create FastAPI app
app = FastAPI(
    title="MAESTRO Engine",
    description="AI-powered SDLC workflow execution engine with Schema v3.0 personas",
    version=settings.version,
    lifespan=lifespan,
    debug=settings.debug,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(persona_workflow_router)
app.include_router(document_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "MAESTRO Engine",
        "version": settings.version,
        "environment": settings.environment,
        "persona_system": "Schema v3.0",
        "docs": "/docs",
        "health": "/api/workflow/health",
    }


@app.get("/health")
async def health_check():
    """Main health check"""
    return {
        "status": "healthy",
        "service": "maestro-engine",
        "version": settings.version,
        "environment": settings.environment,
        "components": {"persona_workflow_api": True, "document_api": True},
    }


if __name__ == "__main__":
    uvicorn.run(
        "maestro_engine_app:app",
        host=settings.engine_host,
        port=settings.engine_port,
        reload=settings.engine_reload,
        log_level=settings.log_level.lower(),
    )
