#!/usr/bin/env python3
"""
RAG Service API - Main Entry Point
Port: 9803
Provides vector embeddings, semantic search, and context retrieval
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="MAESTRO RAG Service",
    description="Vector embeddings, semantic search, and context retrieval",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str


@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info("=" * 80)
    logger.info("🚀 MAESTRO RAG Service Starting on port 9803...")
    logger.info("=" * 80)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {"service": "MAESTRO RAG Service", "version": "1.0.0", "status": "running"}


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy", timestamp=datetime.now().isoformat(), version="1.0.0")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("rag.api:app", host="0.0.0.0", port=9803, reload=False, log_level="info")
