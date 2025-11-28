"""
Safe Error Response Handler for MD-1876: API Validation Layer Phase 2 - Hardening

This module provides safe error handling that:
- Strips stack traces from production error responses
- Returns generic error messages for 500 errors
- Preserves detail for 4xx validation errors
- Logs full errors server-side only
- Prevents sensitive data exposure in error messages

Usage:
    from src.utils.error_handler import safe_error_message, create_error_response

    # In exception handler:
    raise HTTPException(status_code=500, detail=safe_error_message(e))

    # Or use the full error response:
    return create_error_response(e, status_code=500)
"""

import logging
import re
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# Patterns that indicate sensitive data
SENSITIVE_PATTERNS = [
    r"password\s*[=:]\s*['\"]?[^'\"\s]+",  # Password assignments
    r"api[_-]?key\s*[=:]\s*['\"]?[^'\"\s]+",  # API keys
    r"secret\s*[=:]\s*['\"]?[^'\"\s]+",  # Secrets
    r"token\s*[=:]\s*['\"]?[^'\"\s]+",  # Tokens
    r"auth[a-z]*\s*[=:]\s*['\"]?[^'\"\s]+",  # Auth credentials
    r"bearer\s+[A-Za-z0-9\-_\.]+",  # Bearer tokens
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # Email addresses
    r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",  # Credit card numbers
    r"jdbc:[a-z]+://[^\s]+",  # JDBC connection strings
    r"postgres://[^\s]+",  # PostgreSQL connection strings
    r"mysql://[^\s]+",  # MySQL connection strings
    r"mongodb://[^\s]+",  # MongoDB connection strings
    r"redis://[^\s]+",  # Redis connection strings
]

# Compiled patterns for performance
_compiled_sensitive_patterns = [
    re.compile(p, re.IGNORECASE) for p in SENSITIVE_PATTERNS
]

# Generic error messages for different status codes
GENERIC_ERROR_MESSAGES = {
    400: "Bad request - please check your input",
    401: "Authentication required",
    403: "Access denied - insufficient permissions",
    404: "Resource not found",
    405: "Method not allowed",
    409: "Conflict - resource already exists or state mismatch",
    422: "Validation error - please check input requirements",
    429: "Too many requests - please try again later",
    500: "An internal error occurred. Please try again later.",
    502: "Service temporarily unavailable",
    503: "Service unavailable - please try again later",
    504: "Request timeout - please try again",
}


def mask_sensitive_data(message: str) -> str:
    """
    Mask sensitive data patterns in error messages.

    Args:
        message: The message to sanitize

    Returns:
        Message with sensitive data masked
    """
    if not message:
        return message

    result = message
    for pattern in _compiled_sensitive_patterns:
        result = pattern.sub("[REDACTED]", result)

    return result


def extract_safe_error_message(exception: Exception) -> str:
    """
    Extract a safe, user-friendly error message from an exception.

    Removes:
    - Stack traces
    - File paths
    - Internal details
    - Sensitive data

    Args:
        exception: The exception to process

    Returns:
        Safe error message string
    """
    if exception is None:
        return "Unknown error"

    # Get the base exception message
    message = str(exception)

    # Remove file paths
    message = re.sub(r'File "[^"]+",?\s*', '', message)
    message = re.sub(r'/[a-zA-Z0-9_/.-]+\.py', '[file]', message)

    # Remove line numbers
    message = re.sub(r'line \d+', '', message)

    # Remove stack trace indicators
    message = re.sub(r'Traceback \(most recent call last\):.*', '', message, flags=re.DOTALL)
    message = re.sub(r'^\s*at\s+.*$', '', message, flags=re.MULTILINE)

    # Remove memory addresses
    message = re.sub(r'0x[0-9a-fA-F]+', '[addr]', message)

    # Mask sensitive data
    message = mask_sensitive_data(message)

    # Clean up whitespace
    message = ' '.join(message.split())

    # Truncate if too long
    if len(message) > 500:
        message = message[:497] + "..."

    return message or "An error occurred"


def safe_error_message(
    exception: Exception,
    status_code: int = 500,
    include_type: bool = False,
    is_production: bool = True,
) -> str:
    """
    Generate a safe error message suitable for API responses.

    Args:
        exception: The exception to process
        status_code: HTTP status code for context
        include_type: Whether to include the exception type
        is_production: Whether this is a production environment

    Returns:
        Safe error message string
    """
    # For 5xx errors in production, return generic message
    if is_production and 500 <= status_code < 600:
        return GENERIC_ERROR_MESSAGES.get(status_code, "An internal error occurred")

    # For 4xx errors, provide more detail (but still sanitized)
    message = extract_safe_error_message(exception)

    # Optionally include exception type for debugging
    if include_type and not is_production:
        exc_type = type(exception).__name__
        message = f"{exc_type}: {message}"

    return message


def create_error_response(
    exception: Exception,
    status_code: int = 500,
    request_id: Optional[str] = None,
    is_production: bool = True,
    additional_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a structured error response for API endpoints.

    Args:
        exception: The exception that occurred
        status_code: HTTP status code
        request_id: Optional request ID for tracking
        is_production: Whether this is production environment
        additional_context: Additional context to include (will be sanitized)

    Returns:
        Structured error response dict
    """
    # Generate request ID if not provided
    error_id = request_id or str(uuid.uuid4())[:8]

    # Log the full error server-side
    log_error(exception, error_id, status_code, additional_context)

    # Build response
    response = {
        "error": True,
        "error_id": error_id,
        "status_code": status_code,
        "message": safe_error_message(exception, status_code, is_production=is_production),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    # For validation errors (422), include field details if available
    if status_code == 422 and hasattr(exception, 'errors'):
        try:
            errors = exception.errors()
            if isinstance(errors, list):
                # Sanitize error details
                safe_errors = []
                for err in errors[:10]:  # Limit to 10 errors
                    safe_err = {
                        "field": err.get("loc", ["unknown"])[-1] if "loc" in err else "unknown",
                        "message": mask_sensitive_data(str(err.get("msg", "Invalid value")))[:200],
                    }
                    if "type" in err:
                        safe_err["type"] = str(err["type"])[:50]
                    safe_errors.append(safe_err)
                response["validation_errors"] = safe_errors
        except Exception:
            pass  # Ignore errors in error handling

    # Add additional context if provided (sanitized)
    if additional_context and not is_production:
        safe_context = {}
        for key, value in additional_context.items():
            if key not in ["password", "secret", "token", "api_key", "auth"]:
                safe_value = mask_sensitive_data(str(value)[:500])
                safe_context[key] = safe_value
        if safe_context:
            response["context"] = safe_context

    return response


def log_error(
    exception: Exception,
    error_id: str,
    status_code: int,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log the full error details server-side.

    Args:
        exception: The exception to log
        error_id: Error ID for correlation
        status_code: HTTP status code
        context: Additional context
    """
    # Get full traceback
    tb = traceback.format_exc()

    # Mask sensitive data even in logs
    safe_tb = mask_sensitive_data(tb)
    safe_context = None

    if context:
        safe_context = {}
        for key, value in context.items():
            safe_context[key] = mask_sensitive_data(str(value))

    # Log at appropriate level
    if status_code >= 500:
        logger.error(
            f"Server Error [{error_id}] (HTTP {status_code}): {type(exception).__name__}: {str(exception)}\n"
            f"Context: {safe_context}\n"
            f"Traceback:\n{safe_tb}"
        )
    elif status_code >= 400:
        logger.warning(
            f"Client Error [{error_id}] (HTTP {status_code}): {type(exception).__name__}: {str(exception)}\n"
            f"Context: {safe_context}"
        )
    else:
        logger.info(
            f"Error [{error_id}] (HTTP {status_code}): {type(exception).__name__}: {str(exception)}"
        )


class SafeHTTPException(Exception):
    """
    Exception class that produces safe error messages.

    Usage:
        raise SafeHTTPException(
            status_code=400,
            detail="Invalid input",
            internal_detail="User provided SQL injection pattern: ...",
        )
    """

    def __init__(
        self,
        status_code: int = 500,
        detail: str = "An error occurred",
        internal_detail: Optional[str] = None,
        error_id: Optional[str] = None,
    ):
        self.status_code = status_code
        self.detail = detail  # Safe message for external response
        self.internal_detail = internal_detail  # Full detail for logging
        self.error_id = error_id or str(uuid.uuid4())[:8]

        # Log the internal detail if different from external
        if internal_detail and internal_detail != detail:
            logger.warning(
                f"SafeHTTPException [{self.error_id}] (HTTP {status_code}): "
                f"External: {detail} | Internal: {mask_sensitive_data(internal_detail)}"
            )

        super().__init__(detail)

    def to_response(self) -> Dict[str, Any]:
        """Convert to API response dict."""
        return {
            "error": True,
            "error_id": self.error_id,
            "status_code": self.status_code,
            "message": self.detail,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


# Utility function for common error scenarios
def validation_error_response(
    field: str,
    message: str,
    error_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a validation error response for a specific field."""
    return {
        "error": True,
        "error_id": error_id or str(uuid.uuid4())[:8],
        "status_code": 422,
        "message": f"Validation error: {mask_sensitive_data(message)}",
        "validation_errors": [{"field": field, "message": message}],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def not_found_response(
    resource_type: str,
    resource_id: str,
    error_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a not found error response."""
    # Sanitize resource_id to prevent information disclosure
    safe_id = re.sub(r'[^\w\-]', '', resource_id)[:50]
    return {
        "error": True,
        "error_id": error_id or str(uuid.uuid4())[:8],
        "status_code": 404,
        "message": f"{resource_type} not found: {safe_id}",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
