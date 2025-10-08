"""
Custom Exception Framework for MAESTRO Engine
Provides consistent error handling across all services
"""

import traceback
from datetime import datetime
from typing import Any, Dict, Optional


class MaestroException(Exception):
    """Base exception for all MAESTRO Engine errors"""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.cause = cause
        self.timestamp = datetime.utcnow().isoformat()
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        result = {
            "error": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
            "timestamp": self.timestamp,
        }

        if self.details:
            result["details"] = self.details

        if self.cause:
            result["cause"] = str(self.cause)

        return result


# ============================================================================
# Validation Errors (400)
# ============================================================================


class ValidationError(MaestroException):
    """Raised when input validation fails"""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if field:
            details["field"] = field
        super().__init__(message, status_code=400, details=details, **kwargs)


class InvalidInputError(ValidationError):
    """Raised when input is invalid"""

    pass


class MissingRequiredFieldError(ValidationError):
    """Raised when a required field is missing"""

    def __init__(self, field: str, **kwargs):
        super().__init__(f"Required field missing: {field}", field=field, **kwargs)


# ============================================================================
# Not Found Errors (404)
# ============================================================================


class NotFoundError(MaestroException):
    """Raised when a resource is not found"""

    def __init__(self, resource: str, identifier: str, **kwargs):
        super().__init__(
            f"{resource} not found: {identifier}",
            status_code=404,
            details={"resource": resource, "id": identifier},
            **kwargs,
        )


class PersonaNotFoundError(NotFoundError):
    """Raised when a persona is not found"""

    def __init__(self, persona_id: str, **kwargs):
        super().__init__("Persona", persona_id, **kwargs)


class WorkflowNotFoundError(NotFoundError):
    """Raised when a workflow is not found"""

    def __init__(self, workflow_id: str, **kwargs):
        super().__init__("Workflow", workflow_id, **kwargs)


class SessionNotFoundError(NotFoundError):
    """Raised when a session is not found"""

    def __init__(self, session_id: str, **kwargs):
        super().__init__("Session", session_id, **kwargs)


class TemplateNotFoundError(NotFoundError):
    """Raised when a template is not found"""

    def __init__(self, template_id: str, **kwargs):
        super().__init__("Template", template_id, **kwargs)


# ============================================================================
# Authentication & Authorization Errors (401, 403)
# ============================================================================


class AuthenticationError(MaestroException):
    """Raised when authentication fails"""

    def __init__(self, message: str = "Authentication required", **kwargs):
        super().__init__(message, status_code=401, **kwargs)


class AuthorizationError(MaestroException):
    """Raised when user doesn't have permission"""

    def __init__(self, message: str = "Insufficient permissions", **kwargs):
        super().__init__(message, status_code=403, **kwargs)


class InvalidTokenError(AuthenticationError):
    """Raised when token is invalid"""

    def __init__(self, **kwargs):
        super().__init__("Invalid or expired token", **kwargs)


# ============================================================================
# Service Errors (503)
# ============================================================================


class ServiceUnavailableError(MaestroException):
    """Raised when a service is unavailable"""

    def __init__(self, service: str, reason: Optional[str] = None, **kwargs):
        message = f"Service unavailable: {service}"
        if reason:
            message += f" - {reason}"
        super().__init__(
            message, status_code=503, details={"service": service, "reason": reason}, **kwargs
        )


class ExternalServiceError(ServiceUnavailableError):
    """Raised when an external service fails"""

    pass


class DatabaseError(ServiceUnavailableError):
    """Raised when database operations fail"""

    def __init__(self, operation: str, reason: Optional[str] = None, **kwargs):
        super().__init__("Database", f"{operation} failed: {reason}", **kwargs)


class RedisError(ServiceUnavailableError):
    """Raised when Redis operations fail"""

    def __init__(self, operation: str, reason: Optional[str] = None, **kwargs):
        super().__init__("Redis", f"{operation} failed: {reason}", **kwargs)


# ============================================================================
# Workflow & Execution Errors (500)
# ============================================================================


class WorkflowExecutionError(MaestroException):
    """Raised when workflow execution fails"""

    def __init__(self, workflow_id: str, reason: str, **kwargs):
        super().__init__(
            f"Workflow execution failed: {reason}",
            status_code=500,
            details={"workflow_id": workflow_id, "reason": reason},
            **kwargs,
        )


class PersonaExecutionError(MaestroException):
    """Raised when persona execution fails"""

    def __init__(self, persona_id: str, reason: str, **kwargs):
        super().__init__(
            f"Persona execution failed: {reason}",
            status_code=500,
            details={"persona_id": persona_id, "reason": reason},
            **kwargs,
        )


class TemplateRenderError(MaestroException):
    """Raised when template rendering fails"""

    def __init__(self, template_id: str, reason: str, **kwargs):
        super().__init__(
            f"Template rendering failed: {reason}",
            status_code=500,
            details={"template_id": template_id, "reason": reason},
            **kwargs,
        )


# ============================================================================
# Configuration Errors (500)
# ============================================================================


class ConfigurationError(MaestroException):
    """Raised when configuration is invalid"""

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if config_key:
            details["config_key"] = config_key
        super().__init__(message, status_code=500, details=details, **kwargs)


class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing"""

    def __init__(self, config_key: str, **kwargs):
        super().__init__(
            f"Missing required configuration: {config_key}", config_key=config_key, **kwargs
        )


# ============================================================================
# Rate Limiting Errors (429)
# ============================================================================


class RateLimitError(MaestroException):
    """Raised when rate limit is exceeded"""

    def __init__(
        self, resource: str, limit: int, window: str, retry_after: Optional[int] = None, **kwargs
    ):
        message = f"Rate limit exceeded for {resource}: {limit} requests per {window}"
        details = {
            "resource": resource,
            "limit": limit,
            "window": window,
        }
        if retry_after:
            details["retry_after"] = retry_after

        super().__init__(message, status_code=429, details=details, **kwargs)


# ============================================================================
# Timeout Errors (504)
# ============================================================================


class TimeoutError(MaestroException):
    """Raised when operation times out"""

    def __init__(self, operation: str, timeout: int, **kwargs):
        super().__init__(
            f"Operation timed out: {operation} (timeout: {timeout}s)",
            status_code=504,
            details={"operation": operation, "timeout": timeout},
            **kwargs,
        )


# ============================================================================
# Conflict Errors (409)
# ============================================================================


class ConflictError(MaestroException):
    """Raised when there's a conflict with current state"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, status_code=409, **kwargs)


class ResourceAlreadyExistsError(ConflictError):
    """Raised when trying to create a resource that already exists"""

    def __init__(self, resource: str, identifier: str, **kwargs):
        super().__init__(
            f"{resource} already exists: {identifier}",
            details={"resource": resource, "id": identifier},
            **kwargs,
        )


# ============================================================================
# Utility Functions
# ============================================================================


def get_error_traceback() -> str:
    """Get formatted traceback for current exception"""
    return traceback.format_exc()


def wrap_exception(e: Exception, message: Optional[str] = None) -> MaestroException:
    """Wrap a generic exception in MaestroException"""
    if isinstance(e, MaestroException):
        return e

    error_message = message or str(e)
    return MaestroException(
        message=error_message,
        status_code=500,
        details={"original_error": str(e), "error_type": type(e).__name__},
        cause=e,
    )
