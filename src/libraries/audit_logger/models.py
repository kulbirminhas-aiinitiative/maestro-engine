"""
Data models for audit logging
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ChatInteraction:
    """Model for chat interaction data"""

    interaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str = ""
    interaction_type: str = ""
    model: Optional[str] = None

    # Content information
    prompt_length: int = 0
    prompt_hash: Optional[str] = None
    response_length: int = 0
    response_hash: Optional[str] = None

    # Performance metrics
    tokens_used: Optional[int] = None
    duration_seconds: Optional[float] = None

    # Content storage flags
    store_full_content: bool = True
    prompt_preview: Optional[str] = None
    response_preview: Optional[str] = None
    prompt_full: Optional[str] = None
    response_full: Optional[str] = None

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "interaction_id": self.interaction_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "type": self.interaction_type,
            "model": self.model,
            "prompt_length": self.prompt_length,
            "prompt_hash": self.prompt_hash,
            "response_length": self.response_length,
            "response_hash": self.response_hash,
            "tokens_used": self.tokens_used,
            "duration_seconds": self.duration_seconds,
            "store_full_content": self.store_full_content,
            "prompt_preview": self.prompt_preview,
            "response_preview": self.response_preview,
            "metadata": self.metadata,
        }


@dataclass
class PersonaActivity:
    """Model for persona activity data"""

    activity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str = ""
    persona: str = ""
    activity: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "activity_id": self.activity_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "persona": self.persona,
            "activity": self.activity,
            "details": self.details,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class ToolUsage:
    """Model for tool usage data"""

    usage_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str = ""
    tool_name: str = ""
    operation: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    result_summary: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None
    duration_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "usage_id": self.usage_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "operation": self.operation,
            "parameters": self.parameters,
            "result_summary": self.result_summary,
            "success": self.success,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class FileOperation:
    """Model for file operation data"""

    operation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str = ""
    operation: str = ""  # create, read, update, delete, create_secure
    file_path: str = ""
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "operation_id": self.operation_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "operation": self.operation,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "file_hash": self.file_hash,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class PerformanceMetric:
    """Model for performance metric data"""

    metric_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str = ""
    metric_name: str = ""
    value: float = 0.0
    unit: str = "seconds"
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "metric_id": self.metric_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "metric_name": self.metric_name,
            "value": self.value,
            "unit": self.unit,
            "context": self.context,
        }


@dataclass
class AuditError:
    """Model for error logging data"""

    error_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str = ""
    error_type: str = ""
    error_message: str = ""
    stack_trace: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "error_id": self.error_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "context": self.context,
        }


@dataclass
class AuditSession:
    """Model for audit session metadata"""

    session_id: str
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    project_path: str = ""
    audit_version: str = "2.0"
    full_content_logging: bool = True
    python_version: str = ""
    user_agent: str = "AuditLogger"
    custom_metadata: Dict[str, Any] = field(default_factory=dict)

    # Statistics
    chat_interactions_count: int = 0
    persona_activities_count: int = 0
    tool_usages_count: int = 0
    file_operations_count: int = 0
    performance_metrics_count: int = 0
    errors_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "project_path": self.project_path,
            "audit_version": self.audit_version,
            "full_content_logging": self.full_content_logging,
            "python_version": self.python_version,
            "user_agent": self.user_agent,
            "custom_metadata": self.custom_metadata,
            "statistics": {
                "chat_interactions": self.chat_interactions_count,
                "persona_activities": self.persona_activities_count,
                "tool_usages": self.tool_usages_count,
                "file_operations": self.file_operations_count,
                "performance_metrics": self.performance_metrics_count,
                "errors": self.errors_count,
            },
        }
