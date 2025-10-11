#!/usr/bin/env python3
"""
Standalone Workflow API Service
Serves async workflow execution endpoints on port 5000
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import workflow API router
from api.workflow_api import get_workflow_router

# Create FastAPI app
app = FastAPI(
    title="MAESTRO Async Workflow API",
    description="Async workflow execution with real-time WebSocket updates",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://localhost:4300",
        "http://3.10.213.208:4300",
        "*"  # Allow all origins for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include workflow router
workflow_router = get_workflow_router()
app.include_router(workflow_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "MAESTRO Async Workflow API",
        "version": "1.0.0",
        "endpoints": {
            "execute": "POST /api/workflow/execute",
            "status": "GET /api/workflow/{workflow_id}/status",
            "active": "GET /api/workflow/active",
            "pause": "POST /api/workflow/{workflow_id}/pause",
            "cancel": "POST /api/workflow/{workflow_id}/cancel",
            "ws": "WS /ws/workflow-async/{workflow_id}",
        },
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "maestro-workflow-api",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    print("=" * 80)
    print("🚀 MAESTRO Async Workflow API Starting...")
    print("=" * 80)
    print(f"📡 Server: http://0.0.0.0:5001")
    print(f"📚 Docs: http://0.0.0.0:5001/docs")
    print(f"🔌 WebSocket: ws://localhost:5001/ws/workflow-async/{{workflow_id}}")
    print("=" * 80)

    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
