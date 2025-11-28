"""
Unit Tests for Safe Error Response Handler (MD-1876)

Tests the error handling utilities for:
- Sensitive data masking
- Stack trace stripping
- Generic error messages for 500 errors
- Detailed validation errors for 4xx
"""

import pytest
from src.utils.error_handler import (
    safe_error_message,
    create_error_response,
    mask_sensitive_data,
    extract_safe_error_message,
    SafeHTTPException,
    validation_error_response,
    not_found_response,
)


class TestMaskSensitiveData:
    """Test sensitive data masking."""

    def test_mask_password(self):
        """TC-3.3: Passwords should be masked."""
        message = "Error connecting with password=secret123"
        result = mask_sensitive_data(message)
        assert "secret123" not in result
        assert "[REDACTED]" in result

    def test_mask_api_key(self):
        """API keys should be masked."""
        message = "Invalid api_key: abc123xyz"
        result = mask_sensitive_data(message)
        assert "abc123xyz" not in result
        assert "[REDACTED]" in result

    def test_mask_bearer_token(self):
        """Bearer tokens should be masked."""
        message = "Auth failed: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = mask_sensitive_data(message)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "[REDACTED]" in result

    def test_mask_email(self):
        """Email addresses should be masked."""
        message = "User not found: admin@example.com"
        result = mask_sensitive_data(message)
        assert "admin@example.com" not in result
        assert "[REDACTED]" in result

    def test_mask_connection_string(self):
        """Database connection strings should be masked."""
        message = "Failed to connect: postgres://user:pass@localhost:5432/db"
        result = mask_sensitive_data(message)
        assert "postgres://user:pass" not in result
        assert "[REDACTED]" in result

    def test_mask_credit_card(self):
        """Credit card numbers should be masked."""
        message = "Payment failed for card 4111-1111-1111-1111"
        result = mask_sensitive_data(message)
        assert "4111-1111-1111-1111" not in result
        assert "[REDACTED]" in result

    def test_preserve_safe_content(self):
        """Safe content should be preserved."""
        message = "Validation failed for field 'username'"
        result = mask_sensitive_data(message)
        assert result == message

    def test_none_input(self):
        """None input should return None."""
        result = mask_sensitive_data(None)
        assert result is None

    def test_empty_string(self):
        """Empty string should return empty string."""
        result = mask_sensitive_data("")
        assert result == ""


class TestExtractSafeErrorMessage:
    """Test safe error message extraction."""

    def test_remove_file_paths(self):
        """File paths should be removed from error messages."""
        exc = Exception('Error in File "/home/user/app/main.py", line 42')
        result = extract_safe_error_message(exc)
        assert "/home/user/app/main.py" not in result

    def test_remove_traceback(self):
        """Traceback content should be removed."""
        exc = Exception("Traceback (most recent call last):\n  File...")
        result = extract_safe_error_message(exc)
        assert "Traceback" not in result

    def test_remove_memory_addresses(self):
        """Memory addresses should be masked."""
        exc = Exception("Object at 0x7f1234567890")
        result = extract_safe_error_message(exc)
        assert "0x7f1234567890" not in result
        assert "[addr]" in result

    def test_mask_sensitive_data(self):
        """Sensitive data should be masked."""
        exc = Exception("Connection failed: password=mysecret123")
        result = extract_safe_error_message(exc)
        assert "mysecret123" not in result

    def test_truncate_long_message(self):
        """Long messages should be truncated."""
        long_text = "A" * 1000
        exc = Exception(long_text)
        result = extract_safe_error_message(exc)
        assert len(result) <= 500
        assert result.endswith("...")

    def test_none_exception(self):
        """None exception should return 'Unknown error'."""
        result = extract_safe_error_message(None)
        assert result == "Unknown error"


class TestSafeErrorMessage:
    """Test safe error message generation."""

    def test_500_error_production_generic(self):
        """TC-3.1: 500 errors in production should return generic message."""
        exc = Exception("Database connection failed: password=secret")
        result = safe_error_message(exc, status_code=500, is_production=True)
        assert result == "An internal error occurred. Please try again later."
        assert "password" not in result
        assert "secret" not in result

    def test_503_error_production_generic(self):
        """503 errors in production should return generic message."""
        exc = Exception("Redis server unavailable at redis://user:pass@localhost")
        result = safe_error_message(exc, status_code=503, is_production=True)
        assert result == "Service unavailable - please try again later"
        assert "redis" not in result.lower()

    def test_400_error_provides_detail(self):
        """TC-3.2: 4xx errors should provide sanitized details."""
        exc = Exception("Invalid input: field 'name' is required")
        result = safe_error_message(exc, status_code=400, is_production=True)
        assert "Invalid input" in result or "required" in result

    def test_422_validation_error_detail(self):
        """Validation errors should preserve useful detail."""
        exc = Exception("Validation error: string too long")
        result = safe_error_message(exc, status_code=422, is_production=True)
        assert "too long" in result or "Validation" in result

    def test_non_production_includes_more_detail(self):
        """Non-production should include more detail."""
        exc = ValueError("Invalid value provided")
        result = safe_error_message(exc, status_code=500, is_production=False)
        assert "Invalid value" in result

    def test_include_type_shows_exception_type(self):
        """include_type should show exception type in non-production."""
        exc = ValueError("Test error")
        result = safe_error_message(
            exc, status_code=400, include_type=True, is_production=False
        )
        assert "ValueError" in result


class TestCreateErrorResponse:
    """Test structured error response creation."""

    def test_response_structure(self):
        """Response should have required fields."""
        exc = Exception("Test error")
        response = create_error_response(exc, status_code=500)

        assert "error" in response
        assert response["error"] is True
        assert "error_id" in response
        assert "status_code" in response
        assert response["status_code"] == 500
        assert "message" in response
        assert "timestamp" in response

    def test_error_id_format(self):
        """Error ID should be valid."""
        exc = Exception("Test error")
        response = create_error_response(exc, status_code=500)

        assert len(response["error_id"]) == 8
        assert response["error_id"].isalnum() or "-" in response["error_id"]

    def test_custom_request_id(self):
        """Custom request ID should be used."""
        exc = Exception("Test error")
        response = create_error_response(exc, status_code=500, request_id="custom123")

        assert response["error_id"] == "custom123"

    def test_timestamp_format(self):
        """Timestamp should be ISO 8601 format."""
        exc = Exception("Test error")
        response = create_error_response(exc, status_code=500)

        assert response["timestamp"].endswith("Z")
        assert "T" in response["timestamp"]

    def test_no_sensitive_data_in_response(self):
        """TC-3.3: Response should not contain sensitive data."""
        exc = Exception("Failed: api_key=secret123 password=mysecret")
        response = create_error_response(exc, status_code=500, is_production=True)

        response_str = str(response)
        assert "secret123" not in response_str
        assert "mysecret" not in response_str

    def test_additional_context_sanitized(self):
        """Additional context should be sanitized."""
        exc = Exception("Test error")
        context = {"user_input": "test; DROP TABLE users;"}
        response = create_error_response(
            exc, status_code=400, additional_context=context, is_production=False
        )

        # Context should be present but sanitized
        assert "context" in response

    def test_password_context_excluded(self):
        """Password fields should be excluded from context."""
        exc = Exception("Test error")
        context = {"password": "secret123", "username": "admin"}
        response = create_error_response(
            exc, status_code=400, additional_context=context, is_production=False
        )

        if "context" in response:
            assert "password" not in response["context"]


class TestSafeHTTPException:
    """Test SafeHTTPException class."""

    def test_basic_creation(self):
        """Exception should store status_code and detail."""
        exc = SafeHTTPException(status_code=400, detail="Invalid input")

        assert exc.status_code == 400
        assert exc.detail == "Invalid input"
        assert str(exc) == "Invalid input"

    def test_internal_detail_stored(self):
        """Internal detail should be stored separately."""
        exc = SafeHTTPException(
            status_code=400,
            detail="Invalid input",
            internal_detail="SQL injection attempt: ' OR 1=1 --",
        )

        assert exc.detail == "Invalid input"
        assert exc.internal_detail == "SQL injection attempt: ' OR 1=1 --"

    def test_error_id_generated(self):
        """Error ID should be generated if not provided."""
        exc = SafeHTTPException(status_code=400, detail="Test")
        assert exc.error_id is not None
        assert len(exc.error_id) == 8

    def test_custom_error_id(self):
        """Custom error ID should be used."""
        exc = SafeHTTPException(
            status_code=400, detail="Test", error_id="custom123"
        )
        assert exc.error_id == "custom123"

    def test_to_response(self):
        """to_response should return proper dict."""
        exc = SafeHTTPException(status_code=400, detail="Invalid input")
        response = exc.to_response()

        assert response["error"] is True
        assert response["status_code"] == 400
        assert response["message"] == "Invalid input"
        assert "error_id" in response
        assert "timestamp" in response


class TestUtilityFunctions:
    """Test utility response functions."""

    def test_validation_error_response(self):
        """validation_error_response should create proper structure."""
        response = validation_error_response(
            field="email",
            message="Invalid email format",
        )

        assert response["error"] is True
        assert response["status_code"] == 422
        assert "validation_errors" in response
        assert len(response["validation_errors"]) == 1
        assert response["validation_errors"][0]["field"] == "email"

    def test_not_found_response(self):
        """not_found_response should create proper structure."""
        response = not_found_response(
            resource_type="User",
            resource_id="123",
        )

        assert response["error"] is True
        assert response["status_code"] == 404
        assert "User" in response["message"]
        assert "123" in response["message"]

    def test_not_found_sanitizes_id(self):
        """not_found_response should sanitize resource ID."""
        response = not_found_response(
            resource_type="User",
            resource_id="../../../etc/passwd",
        )

        assert "../" not in response["message"]
        assert "passwd" in response["message"]  # alphanumeric part kept


class TestEdgeCases:
    """Test edge cases."""

    def test_deeply_nested_exception(self):
        """Nested exceptions should be handled."""
        try:
            try:
                raise ValueError("Inner error: password=secret")
            except ValueError as e:
                raise RuntimeError(f"Outer error wrapping: {e}")
        except RuntimeError as exc:
            result = safe_error_message(exc, status_code=500, is_production=True)
            assert "password" not in result
            assert "secret" not in result

    def test_unicode_in_error(self):
        """Unicode characters should be handled."""
        exc = Exception("Error with unicode: 你好世界 🌍")
        result = safe_error_message(exc, status_code=400, is_production=True)
        assert isinstance(result, str)

    def test_empty_exception_message(self):
        """Empty exception message should return default."""
        exc = Exception("")
        result = extract_safe_error_message(exc)
        assert result == "An error occurred"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
