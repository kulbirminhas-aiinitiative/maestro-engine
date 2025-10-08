#!/usr/bin/env python3
"""
Hot Claude Live Backend - MCP Service
Port: 9800
Provides Hot Claude sessions, MCP caching, and context sharing
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MAESTRO MCP Service",
    description="Hot Claude sessions, MCP caching, and context sharing",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
MCP_CACHE_DIR = Path(os.getenv("MCP_CACHE_DIR", "/tmp/mcp_cache"))
MCP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
MCP_CACHE_TTL = int(os.getenv("MCP_CACHE_TTL", 3600))

# In-memory session storage (in production, use Redis or persistent storage)
sessions: Dict[str, Dict[str, Any]] = {}


# Pydantic models
class SessionCreateRequest(BaseModel):
    session_id: str = Field(..., description="Unique session identifier")
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Session context data"
    )


class SessionResponse(BaseModel):
    session_id: str
    status: str
    created_at: str
    context: Dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    cache_dir: str
    total_sessions: int


# API Endpoints


@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info("=" * 80)
    logger.info("🚀 MAESTRO MCP Service Starting on port 9800...")
    logger.info(f"📁 Cache Directory: {MCP_CACHE_DIR}")
    logger.info(f"⏱️  Cache TTL: {MCP_CACHE_TTL}s")
    logger.info("=" * 80)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "service": "MAESTRO MCP Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "sessions": "/sessions",
            "create_session": "POST /sessions",
            "get_session": "GET /sessions/{session_id}",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0",
        cache_dir=str(MCP_CACHE_DIR),
        total_sessions=len(sessions),
    )


@app.post("/sessions", response_model=SessionResponse, tags=["Sessions"])
async def create_session(request: SessionCreateRequest):
    """Create a new MCP session"""
    session_id = request.session_id

    if session_id in sessions:
        raise HTTPException(status_code=400, detail=f"Session {session_id} already exists")

    session_data = {
        "session_id": session_id,
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "context": request.context or {},
    }

    sessions[session_id] = session_data
    logger.info(f"✅ Created session: {session_id}")

    return SessionResponse(**session_data)


@app.get("/sessions/{session_id}", response_model=SessionResponse, tags=["Sessions"])
async def get_session(session_id: str):
    """Get session by ID"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return SessionResponse(**sessions[session_id])


@app.get("/sessions", tags=["Sessions"])
async def list_sessions():
    """List all sessions"""
    return {"total": len(sessions), "sessions": list(sessions.keys())}


@app.delete("/sessions/{session_id}", tags=["Sessions"])
async def delete_session(session_id: str):
    """Delete a session"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    del sessions[session_id]
    logger.info(f"🗑️  Deleted session: {session_id}")

    return {"message": f"Session {session_id} deleted successfully"}


@app.post("/cache/store", tags=["Cache"])
async def store_cache(session_id: str, key: str, value: Dict[str, Any]):
    """Store data in MCP cache"""
    cache_file = MCP_CACHE_DIR / f"{session_id}_{key}.json"

    cache_data = {
        "session_id": session_id,
        "key": key,
        "value": value,
        "timestamp": datetime.now().isoformat(),
    }

    with open(cache_file, "w") as f:
        json.dump(cache_data, f, indent=2)

    logger.info(f"💾 Cached: {session_id}/{key}")
    return {"message": "Cache stored successfully", "cache_file": str(cache_file)}


@app.get("/cache/retrieve", tags=["Cache"])
async def retrieve_cache(session_id: str, key: str):
    """Retrieve data from MCP cache"""
    cache_file = MCP_CACHE_DIR / f"{session_id}_{key}.json"

    if not cache_file.exists():
        raise HTTPException(status_code=404, detail=f"Cache not found for {session_id}/{key}")

    with open(cache_file, "r") as f:
        cache_data = json.load(f)

    logger.info(f"📖 Retrieved: {session_id}/{key}")
    return cache_data


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "message": str(exc), "path": str(request.url)},
    )


if __name__ == "__main__":
    uvicorn.run(
        "hot_claude_live_backend_sdk:app", host="0.0.0.0", port=9800, reload=False, log_level="info"
    )
