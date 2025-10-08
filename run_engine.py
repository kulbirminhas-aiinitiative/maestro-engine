#!/usr/bin/env python3
"""
MAESTRO Engine Main Entry Point

Run the MAESTRO backend execution engine with MCP/UTCP orchestration.
"""

import sys
from pathlib import Path

# Add shared libraries to path
shared_libs = Path("/home/ec2-user/projects/shared/packages")
sys.path.insert(0, str(shared_libs / "core-api" / "src"))
sys.path.insert(0, str(shared_libs / "core-logging" / "src"))
sys.path.insert(0, str(shared_libs / "core-config" / "src"))

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import asyncio

import uvicorn
from fastapi import FastAPI
from maestro_core_api import APIConfig, MaestroAPI
from maestro_core_logging import configure_logging, get_logger

from api.registry_routes import create_registry_routes

# Import service registry
from registry import ServiceRegistry

# Configure logging
configure_logging(service_name="maestro-engine", log_level="INFO", log_format="json")

logger = get_logger(__name__)

# Create FastAPI application
from maestro_core_api import SecurityConfig

config = APIConfig(
    title="MAESTRO Execution Engine",
    service_name="maestro-engine",
    version="1.0.0",
    description="Backend execution engine for MCP/UTCP orchestration, RAG, and template integration",
    security=SecurityConfig(
        jwt_secret_key="maestro_engine_secret_key_change_in_production_32chars_min"
    ),
)

maestro_api = MaestroAPI(config)
app = maestro_api.app

# Initialize service registry
registry = ServiceRegistry()
logger.info("Service registry initialized", services_count=len(registry.services))

# Add registry routes
create_registry_routes(app, registry)


@app.get("/")
async def root():
    """Root endpoint with service registry status"""
    # Get current service registry state
    all_services = registry.get_all_services()
    healthy_services = registry.list_healthy_services()

    return {
        "service": "MAESTRO Execution Engine",
        "version": "1.0.0",
        "status": "running",
        "components": {
            "mcp_utcp": "enabled",
            "orchestration": "enabled",
            "rag": "available",
            "templates": "integrated",
        },
        "service_registry": {
            "total_services": len(all_services),
            "healthy_services": len(healthy_services),
            "services": [s.name for s in all_services],
        },
    }


@app.get("/api/status")
async def status():
    """Status endpoint"""
    return {
        "status": "healthy",
        "modules": {"mcp": True, "orchestration": True, "rag": True, "templates": True},
    }


def main():
    """Main entry point"""
    logger.info("Starting MAESTRO Engine", version="1.0.0")

    # Run the application
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info", access_log=True)


if __name__ == "__main__":
    main()
