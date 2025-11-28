#!/usr/bin/env python3
"""
API Request/Response Models for MAESTRO Workflow API

MD-1876: Phase 2 - Schema Hardening
- Added max_length constraints to string fields
- Added pattern validation for IDs
- Added enum validation for status fields
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
import re


# MD-1876: Enum definitions for validated status fields
class GateTypeEnum(str, Enum):
    """Valid gate types."""
    DDE = "DDE"  # Design Document Evaluation
    BRV = "BRV"  # Business Rule Validation
    ACC = "ACC"  # Acceptance Criteria Check


class GateStatusEnum(str, Enum):
    """Valid gate statuses."""
    OPEN = "open"
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class PriorityEnum(str, Enum):
    """Valid priority levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class WorkflowRequest(BaseModel):
    """Request model for workflow execution"""

    # MD-1876: Added max_length=10000 for requirement field
    requirement: str = Field(
        ...,
        description="User requirement to execute",
        min_length=1,
        max_length=10000
    )
    enable_utcp: bool = Field(default=True, description="Enable distributed UTCP execution")
    enable_rag: bool = Field(default=True, description="Enable RAG template retrieval")
    enable_mcp: bool = Field(default=True, description="Enable MCP context sharing")
    selected_personas: Optional[List[str]] = Field(
        default=None, description="Optional custom persona list"
    )
    # MD-1876: Added max_length=200 for session_id
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID for tracking",
        max_length=200
    )
    # MD-1876: Added max_length=500 for project_path
    project_path: Optional[str] = Field(
        default=None,
        description="Optional custom project path",
        max_length=500
    )
    max_execution_time: Optional[int] = Field(
        default=3600,
        description="Max execution time in seconds",
        ge=1,
        le=86400  # Max 24 hours
    )

    # MD-1876: Validator for session_id pattern
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v):
        if v is not None and not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('session_id must contain only alphanumeric characters, underscores, and hyphens')
        return v

    # MD-1876: Validator for project_path pattern
    @field_validator('project_path')
    @classmethod
    def validate_project_path(cls, v):
        if v is not None:
            # Check for path traversal attempts
            if '..' in v:
                raise ValueError('project_path cannot contain path traversal sequences')
            if not re.match(r'^[a-zA-Z0-9._/-]*$', v):
                raise ValueError('project_path contains invalid characters')
        return v

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


# MD-1876: Enum for render types
class RenderTypeEnum(str, Enum):
    """Valid render types for SDLC documents."""
    MARKDOWN = "markdown"
    MERMAID = "mermaid"
    OPENAPI = "openapi"
    USER_JOURNEY = "user-journey"
    C4_DIAGRAM = "c4-diagram"
    RAW = "raw"


class SDLCDocument(BaseModel):
    """SDLC Document for frontend rendering"""

    # MD-1876: Added max_length=100 for ID field
    id: str = Field(
        ...,
        description="Unique document ID",
        max_length=100
    )
    # MD-1876: Added max_length=200 for title
    title: str = Field(
        ...,
        description="Document title",
        max_length=200
    )
    renderType: str = Field(
        ...,
        description="Visualization type: markdown, mermaid, openapi, user-journey, c4-diagram, raw",
    )
    # MD-1876: Added max_length=100000 for content
    rawContent: str = Field(
        ...,
        description="Document content in appropriate format",
        max_length=100000
    )
    generatedAt: str = Field(..., description="ISO 8601 timestamp")

    # Optional fields with constraints
    phase: Optional[str] = Field(None, description="SDLC phase", max_length=50)
    version: str = Field(default="1.0", description="Document version", max_length=20)
    generatedBy: Optional[str] = Field(None, description="Agent/persona that generated this", max_length=100)
    artifactType: Optional[str] = Field(None, description="Type of artifact", max_length=50)
    description: Optional[str] = Field(None, description="Document description", max_length=5000)
    size: Optional[int] = Field(None, description="File size in bytes", ge=0)
    filePath: Optional[str] = Field(None, description="Original file path", max_length=500)

    # MD-1876: Validator for ID pattern
    @field_validator('id')
    @classmethod
    def validate_id(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('id must contain only alphanumeric characters, underscores, and hyphens')
        return v

    # MD-1876: Validator for filePath
    @field_validator('filePath')
    @classmethod
    def validate_file_path(cls, v):
        if v is not None:
            if '..' in v:
                raise ValueError('filePath cannot contain path traversal sequences')
        return v

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
