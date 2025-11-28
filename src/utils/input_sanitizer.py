"""
Input Sanitization Module for MD-1876: API Validation Layer Phase 2 - Hardening

This module provides comprehensive input sanitization to protect against:
- XSS attacks (script tag injection)
- Path traversal attacks
- SQL injection patterns (defense in depth)
- Oversized input attacks

Usage:
    from src.utils.input_sanitizer import InputSanitizer

    sanitizer = InputSanitizer()
    clean_text = sanitizer.sanitize_string(user_input, max_length=5000)
    clean_path = sanitizer.sanitize_path(file_path)
"""

import re
import html
import logging
from typing import Optional, List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class InputSanitizer:
    """
    Comprehensive input sanitization for API endpoints.

    Provides defense-in-depth against common injection attacks
    while preserving legitimate input where possible.
    """

    # Patterns for detecting potentially malicious input
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b.*\b(FROM|INTO|TABLE|DATABASE)\b)",
        r"(;\s*(DROP|DELETE|TRUNCATE)\s+)",
        r"(--\s*$)",  # SQL comment at end
        r"(/\*.*\*/)",  # Block comments
        r"(\bOR\b\s+\d+\s*=\s*\d+)",  # OR 1=1 pattern
        r"(\bAND\b\s+\d+\s*=\s*\d+)",  # AND 1=1 pattern
        r"(\bUNION\b\s+\bSELECT\b)",  # UNION SELECT
        r"(;\s*EXEC\s+)",  # Stored procedure execution
    ]

    # HTML/Script patterns to strip
    DANGEROUS_HTML_PATTERNS = [
        r"<script[^>]*>.*?</script>",  # Script tags with content
        r"<script[^>]*/>",  # Self-closing script tags
        r"<script[^>]*>",  # Opening script tags
        r"</script>",  # Closing script tags
        r"javascript:",  # JavaScript protocol
        r"vbscript:",  # VBScript protocol
        r"on\w+\s*=",  # Event handlers (onclick, onerror, etc.)
        r"<iframe[^>]*>.*?</iframe>",  # Iframe tags
        r"<iframe[^>]*>",  # Opening iframe
        r"<object[^>]*>.*?</object>",  # Object tags
        r"<embed[^>]*>",  # Embed tags
        r"<link[^>]*>",  # Link tags (can load external resources)
        r"<meta[^>]*http-equiv[^>]*>",  # Meta refresh
    ]

    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",  # Unix parent directory
        r"\.\.\\",  # Windows parent directory
        r"%2e%2e%2f",  # URL encoded ../
        r"%2e%2e/",  # Partial URL encoded
        r"\.%2e/",  # Mixed encoding
        r"%2e\./",  # Mixed encoding
        r"\.\.%5c",  # URL encoded ..\
        r"%252e%252e%252f",  # Double URL encoded
    ]

    # Default length limits
    DEFAULT_MAX_LENGTHS = {
        "name": 200,
        "description": 5000,
        "requirement": 10000,
        "template_content": 100000,
        "comment": 2000,
        "default": 1000,
    }

    def __init__(self, log_security_events: bool = True):
        """
        Initialize the sanitizer.

        Args:
            log_security_events: Whether to log detected security threats
        """
        self.log_security_events = log_security_events
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        self._sql_patterns = [
            re.compile(p, re.IGNORECASE | re.DOTALL)
            for p in self.SQL_INJECTION_PATTERNS
        ]
        self._html_patterns = [
            re.compile(p, re.IGNORECASE | re.DOTALL)
            for p in self.DANGEROUS_HTML_PATTERNS
        ]
        self._path_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in self.PATH_TRAVERSAL_PATTERNS
        ]

    def sanitize_string(
        self,
        value: Optional[str],
        max_length: Optional[int] = None,
        field_type: str = "default",
        strip_html: bool = True,
        allow_newlines: bool = True,
    ) -> Optional[str]:
        """
        Sanitize a string input.

        Args:
            value: The input string to sanitize
            max_length: Maximum allowed length (uses defaults if not specified)
            field_type: Type of field for default max_length lookup
            strip_html: Whether to strip dangerous HTML/script tags
            allow_newlines: Whether to preserve newlines

        Returns:
            Sanitized string or None if input was None
        """
        if value is None:
            return None

        if not isinstance(value, str):
            value = str(value)

        original_value = value

        # Step 1: Trim whitespace
        value = value.strip()

        # Step 2: Remove dangerous HTML/script patterns
        if strip_html:
            value = self._strip_dangerous_html(value)

        # Step 3: Escape remaining HTML entities
        # Only escape if we're not allowing HTML (for rich text fields)
        if strip_html:
            # Preserve already escaped entities
            value = html.escape(value, quote=True)

        # Step 4: Normalize newlines
        if allow_newlines:
            # Normalize to Unix-style newlines
            value = value.replace('\r\n', '\n').replace('\r', '\n')
        else:
            # Replace newlines with spaces
            value = value.replace('\n', ' ').replace('\r', ' ')

        # Step 5: Remove null bytes and other control characters
        value = self._remove_control_chars(value, allow_newlines)

        # Step 6: Enforce max length
        if max_length is None:
            max_length = self.DEFAULT_MAX_LENGTHS.get(
                field_type,
                self.DEFAULT_MAX_LENGTHS["default"]
            )

        if len(value) > max_length:
            value = value[:max_length]
            if self.log_security_events:
                logger.warning(
                    f"Input truncated from {len(original_value)} to {max_length} chars"
                )

        # Step 7: Check for SQL injection patterns (defense in depth - log but don't block)
        self._check_sql_injection(value, original_value)

        return value

    def sanitize_path(
        self,
        path: Optional[str],
        allowed_prefixes: Optional[List[str]] = None,
        max_length: int = 500,
    ) -> Optional[str]:
        """
        Sanitize a file path to prevent path traversal attacks.

        Args:
            path: The path to sanitize
            allowed_prefixes: List of allowed path prefixes
            max_length: Maximum path length

        Returns:
            Sanitized path or None if invalid/dangerous
        """
        if path is None:
            return None

        if not isinstance(path, str):
            path = str(path)

        original_path = path

        # Step 1: Trim and normalize
        path = path.strip()

        # Step 2: Check for path traversal patterns
        for pattern in self._path_patterns:
            if pattern.search(path):
                if self.log_security_events:
                    logger.warning(
                        f"Path traversal attempt detected: {original_path[:100]}"
                    )
                return None

        # Step 3: Normalize path separators
        path = path.replace('\\', '/')

        # Step 4: Resolve and normalize path
        try:
            # Use pathlib to normalize
            normalized = Path(path)
            # Convert back to string with forward slashes
            path = str(normalized).replace('\\', '/')
        except Exception:
            if self.log_security_events:
                logger.warning(f"Invalid path format: {original_path[:100]}")
            return None

        # Step 5: Verify against allowed prefixes if specified
        if allowed_prefixes:
            if not any(path.startswith(prefix) for prefix in allowed_prefixes):
                if self.log_security_events:
                    logger.warning(
                        f"Path outside allowed prefixes: {path[:100]}"
                    )
                return None

        # Step 6: Enforce max length
        if len(path) > max_length:
            if self.log_security_events:
                logger.warning(f"Path too long: {len(path)} chars")
            return None

        # Step 7: Validate characters (alphanumeric, dots, dashes, underscores, slashes)
        if not re.match(r'^[a-zA-Z0-9._/-]+$', path):
            if self.log_security_events:
                logger.warning(f"Path contains invalid characters: {path[:100]}")
            return None

        return path

    def sanitize_identifier(
        self,
        identifier: Optional[str],
        pattern: str = r'^[a-zA-Z0-9_-]+$',
        max_length: int = 100,
    ) -> Optional[str]:
        """
        Sanitize an identifier (ID, key, etc.).

        Args:
            identifier: The identifier to sanitize
            pattern: Regex pattern for valid characters
            max_length: Maximum length

        Returns:
            Sanitized identifier or None if invalid
        """
        if identifier is None:
            return None

        if not isinstance(identifier, str):
            identifier = str(identifier)

        identifier = identifier.strip()

        # Check length
        if len(identifier) > max_length:
            if self.log_security_events:
                logger.warning(f"Identifier too long: {len(identifier)} chars")
            return None

        # Validate against pattern
        if not re.match(pattern, identifier):
            if self.log_security_events:
                logger.warning(f"Invalid identifier format: {identifier[:50]}")
            return None

        return identifier

    def check_for_threats(self, value: str) -> List[Tuple[str, str]]:
        """
        Check input for potential security threats without sanitizing.

        Args:
            value: The input to check

        Returns:
            List of (threat_type, matched_pattern) tuples
        """
        threats = []

        # Check SQL injection
        for pattern in self._sql_patterns:
            match = pattern.search(value)
            if match:
                threats.append(("SQL_INJECTION", match.group()[:50]))

        # Check XSS/HTML injection
        for pattern in self._html_patterns:
            match = pattern.search(value)
            if match:
                threats.append(("XSS_HTML", match.group()[:50]))

        # Check path traversal
        for pattern in self._path_patterns:
            match = pattern.search(value)
            if match:
                threats.append(("PATH_TRAVERSAL", match.group()[:50]))

        return threats

    def _strip_dangerous_html(self, value: str) -> str:
        """Strip dangerous HTML/script patterns from input."""
        for pattern in self._html_patterns:
            value = pattern.sub('', value)
        return value

    def _remove_control_chars(self, value: str, allow_newlines: bool) -> str:
        """Remove control characters except optionally newlines/tabs."""
        result = []
        for char in value:
            code = ord(char)
            # Allow printable ASCII and extended Unicode
            if code >= 32 or (allow_newlines and char in '\n\t'):
                result.append(char)
        return ''.join(result)

    def _check_sql_injection(self, value: str, original_value: str):
        """Check for SQL injection patterns and log if found."""
        if not self.log_security_events:
            return

        for pattern in self._sql_patterns:
            if pattern.search(value) or pattern.search(original_value):
                logger.warning(
                    f"Potential SQL injection pattern detected in input "
                    f"(length: {len(original_value)})"
                )
                break


# Singleton instance for convenience
_default_sanitizer: Optional[InputSanitizer] = None


def get_sanitizer() -> InputSanitizer:
    """Get the default sanitizer instance."""
    global _default_sanitizer
    if _default_sanitizer is None:
        _default_sanitizer = InputSanitizer()
    return _default_sanitizer


def sanitize_string(
    value: Optional[str],
    max_length: Optional[int] = None,
    field_type: str = "default",
    **kwargs
) -> Optional[str]:
    """Convenience function to sanitize a string using the default sanitizer."""
    return get_sanitizer().sanitize_string(
        value, max_length=max_length, field_type=field_type, **kwargs
    )


def sanitize_path(
    path: Optional[str],
    allowed_prefixes: Optional[List[str]] = None,
    **kwargs
) -> Optional[str]:
    """Convenience function to sanitize a path using the default sanitizer."""
    return get_sanitizer().sanitize_path(path, allowed_prefixes=allowed_prefixes, **kwargs)


def sanitize_identifier(
    identifier: Optional[str],
    pattern: str = r'^[a-zA-Z0-9_-]+$',
    max_length: int = 100,
) -> Optional[str]:
    """Convenience function to sanitize an identifier using the default sanitizer."""
    return get_sanitizer().sanitize_identifier(identifier, pattern, max_length)
