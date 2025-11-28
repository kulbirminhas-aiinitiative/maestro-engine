"""
Utilities Module

Common utilities and helper functions.

MD-1876: API Validation Layer Phase 2 - Hardening
- Input sanitization for XSS, SQL injection, path traversal prevention
- Safe error handling to prevent sensitive data exposure
"""

from src.utils.input_sanitizer import (
    InputSanitizer,
    get_sanitizer,
    sanitize_string,
    sanitize_path,
    sanitize_identifier,
)

from src.utils.error_handler import (
    safe_error_message,
    create_error_response,
    mask_sensitive_data,
    SafeHTTPException,
    validation_error_response,
    not_found_response,
    log_error,
)

from src.utils.pii_masker import (
    PIIMasker,
    get_pii_masker,
    mask_pii,
    mask_for_logging,
)

__all__ = [
    # Input sanitization
    "InputSanitizer",
    "get_sanitizer",
    "sanitize_string",
    "sanitize_path",
    "sanitize_identifier",
    # Error handling
    "safe_error_message",
    "create_error_response",
    "mask_sensitive_data",
    "SafeHTTPException",
    "validation_error_response",
    "not_found_response",
    "log_error",
    # PII masking
    "PIIMasker",
    "get_pii_masker",
    "mask_pii",
    "mask_for_logging",
]
