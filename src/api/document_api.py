#!/usr/bin/env python3
"""
Document API for MAESTRO Engine
Provides endpoints for retrieving SDLC documents for frontend rendering
"""

import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.models import DocumentsResponse, SDLCDocument

# Import configuration and services
from config import get_settings
from services.document_service import get_document_service

# Get configuration
settings = get_settings()

# Create router
router = APIRouter(prefix="/api/sdlc", tags=["documents"])

# Get document service
document_service = get_document_service()


@router.get("/documents/{document_id}", response_model=SDLCDocument)
async def get_document_by_id(document_id: str, session_id: Optional[str] = None):
    """
    Get a single SDLC document by ID

    Args:
        document_id: Unique document ID
        session_id: Optional session ID to narrow search

    Returns:
        SDLCDocument with renderType and rawContent
    """
    # Determine project directory
    if session_id:
        project_dir = settings.get_project_dir(session_id)
    else:
        # Search all project directories
        # This is a fallback - ideally session_id should be provided
        projects_base = settings.projects_dir
        if not projects_base.exists():
            raise HTTPException(status_code=404, detail="Projects directory not found")

        # Search for document in all project subdirectories
        for project_dir in projects_base.iterdir():
            if project_dir.is_dir():
                doc = document_service.get_document_by_id(project_dir, document_id)
                if doc:
                    return SDLCDocument(**doc)

        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    # Get document from specific session directory
    if not project_dir.exists():
        raise HTTPException(
            status_code=404, detail=f"Project directory not found for session: {session_id}"
        )

    doc = document_service.get_document_by_id(project_dir, document_id)

    if not doc:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    return SDLCDocument(**doc)


@router.get("/documents", response_model=DocumentsResponse)
async def list_documents(session_id: Optional[str] = None, phase: Optional[str] = None):
    """
    List all SDLC documents

    Args:
        session_id: Optional session ID to filter by
        phase: Optional SDLC phase to filter by

    Returns:
        List of SDLCDocuments
    """
    # Determine project directory
    if session_id:
        project_dir = settings.get_project_dir(session_id)

        if not project_dir.exists():
            raise HTTPException(
                status_code=404, detail=f"Project directory not found for session: {session_id}"
            )

        # Get documents, optionally filtered by phase
        if phase:
            documents = document_service.get_documents_by_phase(project_dir, phase, session_id)
        else:
            documents = document_service.get_documents_by_session(project_dir, session_id)

        return DocumentsResponse(
            documents=[SDLCDocument(**doc) for doc in documents],
            total=len(documents),
            phase=phase,
            sessionId=session_id,
        )

    else:
        # List documents from all sessions
        projects_base = settings.projects_dir

        if not projects_base.exists():
            return DocumentsResponse(documents=[], total=0)

        all_documents = []

        # Scan all project directories
        for project_dir in projects_base.iterdir():
            if project_dir.is_dir():
                if phase:
                    docs = document_service.get_documents_by_phase(project_dir, phase, None)
                else:
                    docs = document_service.get_documents_by_session(project_dir, None)

                all_documents.extend(docs)

        return DocumentsResponse(
            documents=[SDLCDocument(**doc) for doc in all_documents],
            total=len(all_documents),
            phase=phase,
        )


@router.get("/phases/{phase_id}/documents", response_model=DocumentsResponse)
async def get_phase_documents(phase_id: str, session_id: Optional[str] = None):
    """
    Get all documents for a specific SDLC phase

    Args:
        phase_id: SDLC phase (requirements, design, implementation, testing, deployment)
        session_id: Optional session ID to filter by

    Returns:
        List of SDLCDocuments for the phase
    """
    # Determine project directory
    if session_id:
        project_dir = settings.get_project_dir(session_id)

        if not project_dir.exists():
            raise HTTPException(
                status_code=404, detail=f"Project directory not found for session: {session_id}"
            )

        documents = document_service.get_documents_by_phase(project_dir, phase_id, session_id)

        return DocumentsResponse(
            documents=[SDLCDocument(**doc) for doc in documents],
            total=len(documents),
            phase=phase_id,
            sessionId=session_id,
        )

    else:
        # Search all project directories
        projects_base = settings.projects_dir

        if not projects_base.exists():
            return DocumentsResponse(documents=[], total=0, phase=phase_id)

        all_documents = []

        for project_dir in projects_base.iterdir():
            if project_dir.is_dir():
                docs = document_service.get_documents_by_phase(project_dir, phase_id, None)
                all_documents.extend(docs)

        return DocumentsResponse(
            documents=[SDLCDocument(**doc) for doc in all_documents],
            total=len(all_documents),
            phase=phase_id,
        )


@router.get("/sessions/{session_id}/documents", response_model=DocumentsResponse)
async def get_session_documents(session_id: str):
    """
    Get all documents for a specific session

    Args:
        session_id: Session ID

    Returns:
        List of all SDLCDocuments for the session
    """
    project_dir = settings.get_project_dir(session_id)

    if not project_dir.exists():
        raise HTTPException(
            status_code=404, detail=f"Project directory not found for session: {session_id}"
        )

    documents = document_service.get_documents_by_session(project_dir, session_id)

    return DocumentsResponse(
        documents=[SDLCDocument(**doc) for doc in documents],
        total=len(documents),
        sessionId=session_id,
    )


def get_document_router() -> APIRouter:
    """Get the document router for inclusion in main app"""
    return router
