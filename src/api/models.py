#!/usr/bin/env python3
"""
API Request/Response Models for MAESTRO Workflow API
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WorkflowRequest(BaseModel):
    """Request model for workflow execution"""

    requirement: str = Field(..., description="User requirement to execute", min_length=1)
    enable_utcp: bool = Field(default=True, description="Enable distributed UTCP execution")
    enable_rag: bool = Field(default=True, description="Enable RAG template retrieval")
    enable_mcp: bool = Field(default=True, description="Enable MCP context sharing")
    selected_personas: Optional[List[str]] = Field(
        default=None, description="Optional custom persona list"
    )
    session_id: Optional[str] = Field(default=None, description="Optional session ID for tracking")
    project_path: Optional[str] = Field(default=None, description="Optional custom project path")
    max_execution_time: Optional[int] = Field(
        default=3600, description="Max execution time in seconds"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "requirement": "Create a REST API for user management with FastAPI",
                "enable_utcp": True,
                "enable_rag": True,
                "enable_mcp": True,
            }
        }


class QualityValidation(BaseModel):
    """Quality validation results"""

    execution_id: Optional[str] = None
    quality_score: Optional[float] = None
    security_score: Optional[float] = None
    performance_score: Optional[float] = None
    maintainability_score: Optional[float] = None
    test_coverage: Optional[float] = None
    test_results: Optional[Dict[str, int]] = None
    duration: Optional[float] = None
    recommendations: Optional[List[str]] = None
    issues: Optional[List[Dict[str, Any]]] = None


class TemplateExtraction(BaseModel):
    """Template extraction results"""

    templates_created: int = 0
    template_ids: List[str] = []
    extraction_time: Optional[float] = None


class WorkflowResponse(BaseModel):
    """Response model for workflow execution"""

    success: bool = Field(..., description="Whether workflow succeeded")
    session_id: str = Field(..., description="Session ID for this execution")
    requirement: str = Field(..., description="Original requirement")
    execution_method: str = Field(
        ..., description="Execution method used (utcp/local_claude_tools)"
    )
    files_generated: List[str] = Field(default=[], description="List of generated file paths")
    total_execution_time: float = Field(..., description="Total execution time in seconds")
    project_path: str = Field(..., description="Path to generated project")
    team_members: List[str] = Field(default=[], description="Team members involved")

    # Optional fields
    error: Optional[str] = Field(default=None, description="Error message if failed")
    quality_validation: Optional[QualityValidation] = Field(
        default=None, description="Quality validation results"
    )
    template_extraction: Optional[TemplateExtraction] = Field(
        default=None, description="Template extraction results"
    )
    git_template_url: Optional[str] = Field(
        default=None, description="Git URL if published as template"
    )

    # Metadata
    start_time: Optional[float] = None
    artifacts: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "session_id": "enhanced_lean_utcp_1759320746",
                "requirement": "Create a REST API for user management",
                "execution_method": "local_claude_tools",
                "files_generated": ["main.py", "requirements.txt", "README.md"],
                "total_execution_time": 162.94,
                "project_path": "/home/ec2-user/projects/deployment/rest-api-user",
                "team_members": ["requirement_analyst", "backend_developer", "qa_engineer"],
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="Current timestamp")
    version: str = Field(default="1.0.0", description="API version")
    features: Dict[str, bool] = Field(..., description="Available features")
    dependencies: Dict[str, bool] = Field(..., description="Dependency health status")


class StatusResponse(BaseModel):
    """Status response with execution statistics"""

    total_executions: int = Field(default=0, description="Total workflow executions")
    successful_executions: int = Field(default=0, description="Successful executions")
    failed_executions: int = Field(default=0, description="Failed executions")
    average_execution_time: float = Field(default=0.0, description="Average execution time")
    utcp_enabled: bool = Field(..., description="Whether UTCP is enabled")
    rag_enabled: bool = Field(..., description="Whether RAG is enabled")


class SDLCDocument(BaseModel):
    """SDLC Document for frontend rendering"""

    id: str = Field(..., description="Unique document ID")
    title: str = Field(..., description="Document title")
    renderType: str = Field(
        ...,
        description="Visualization type: markdown, mermaid, openapi, user-journey, c4-diagram, raw",
    )
    rawContent: str = Field(..., description="Document content in appropriate format")
    generatedAt: str = Field(..., description="ISO 8601 timestamp")

    # Optional fields
    phase: Optional[str] = Field(None, description="SDLC phase")
    version: str = Field(default="1.0", description="Document version")
    generatedBy: Optional[str] = Field(None, description="Agent/persona that generated this")
    artifactType: Optional[str] = Field(None, description="Type of artifact")
    description: Optional[str] = Field(None, description="Document description")
    size: Optional[int] = Field(None, description="File size in bytes")
    filePath: Optional[str] = Field(None, description="Original file path")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "doc-arch-001",
                "title": "System Architecture",
                "renderType": "mermaid",
                "rawContent": "graph TB\n    A[Frontend] --> B[API Gateway]\n    B --> C[Backend]",
                "generatedAt": "2025-10-03T10:00:00Z",
                "phase": "design",
                "version": "1.0",
            }
        }


class DocumentsResponse(BaseModel):
    """Response containing list of documents"""

    documents: List[SDLCDocument] = Field(..., description="List of documents")
    total: int = Field(..., description="Total number of documents")
    phase: Optional[str] = Field(None, description="Phase if filtered")
    sessionId: Optional[str] = Field(None, description="Session ID if filtered")
