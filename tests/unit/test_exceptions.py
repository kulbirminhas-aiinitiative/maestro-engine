"""
Unit Tests for MAESTRO Engine Exception Framework
"""

from datetime import datetime

import pytest

from src.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ConflictError,
    MaestroException,
    NotFoundError,
    PersonaNotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    TimeoutError,
    ValidationError,
    WorkflowExecutionError,
    WorkflowNotFoundError,
    wrap_exception,
)


class TestMaestroException:
    """Test the base MaestroException class"""

    def test_basic_exception(self):
        """Test basic exception creation"""
        exc = MaestroException("Test error")

        assert exc.message == "Test error"
        assert exc.status_code == 500
        assert exc.error_code == "MaestroException"
        assert isinstance(exc.details, dict)
        assert exc.timestamp is not None

    def test_exception_with_details(self):
        """Test exception with additional details"""
        details = {"key": "value", "count": 42}
        exc = MaestroException("Test error", details=details)

        assert exc.details == details

    def test_exception_with_cause(self):
        """Test exception with cause"""
        original = ValueError("Original error")
        exc = MaestroException("Wrapped error", cause=original)

        assert exc.cause == original

    def test_to_dict(self):
        """Test conversion to dictionary"""
        exc = MaestroException(
            "Test error", status_code=400, error_code="TestError", details={"field": "email"}
        )

        result = exc.to_dict()

        assert result["error"] == "TestError"
        assert result["message"] == "Test error"
        assert result["status_code"] == 400
        assert result["details"]["field"] == "email"
        assert "timestamp" in result


class TestValidationErrors:
    """Test validation error classes"""

    def test_validation_error(self):
        """Test basic validation error"""
        exc = ValidationError("Invalid input", field="email")

        assert exc.status_code == 400
        assert exc.details["field"] == "email"

    def test_missing_required_field_error(self):
        """Test missing required field error"""
        from src.exceptions import MissingRequiredFieldError

        exc = MissingRequiredFieldError("username")

        assert "username" in exc.message
        assert exc.details["field"] == "username"
        assert exc.status_code == 400


class TestNotFoundErrors:
    """Test not found error classes"""

    def test_not_found_error(self):
        """Test generic not found error"""
        exc = NotFoundError("User", "123")

        assert exc.status_code == 404
        assert "User" in exc.message
        assert "123" in exc.message
        assert exc.details["resource"] == "User"
        assert exc.details["id"] == "123"

    def test_persona_not_found(self):
        """Test persona not found error"""
        exc = PersonaNotFoundError("backend_dev")

        assert exc.status_code == 404
        assert "Persona" in exc.message
        assert "backend_dev" in exc.message

    def test_workflow_not_found(self):
        """Test workflow not found error"""
        exc = WorkflowNotFoundError("workflow_123")

        assert exc.status_code == 404
        assert "Workflow" in exc.message


class TestAuthErrors:
    """Test authentication and authorization errors"""

    def test_authentication_error(self):
        """Test authentication error"""
        exc = AuthenticationError()

        assert exc.status_code == 401
        assert "Authentication" in exc.message

    def test_authorization_error(self):
        """Test authorization error"""
        exc = AuthorizationError()

        assert exc.status_code == 403
        assert "permission" in exc.message.lower()


class TestServiceErrors:
    """Test service unavailable errors"""

    def test_service_unavailable(self):
        """Test service unavailable error"""
        exc = ServiceUnavailableError("Database", "Connection timeout")

        assert exc.status_code == 503
        assert "Database" in exc.message
        assert "Connection timeout" in exc.message

    def test_database_error(self):
        """Test database error"""
        from src.exceptions import DatabaseError

        exc = DatabaseError("insert", "Duplicate key")

        assert exc.status_code == 503
        assert "insert" in exc.message


class TestWorkflowErrors:
    """Test workflow execution errors"""

    def test_workflow_execution_error(self):
        """Test workflow execution error"""
        exc = WorkflowExecutionError("workflow_123", "Task failed")

        assert exc.status_code == 500
        assert exc.details["workflow_id"] == "workflow_123"
        assert "Task failed" in exc.message


class TestConfigurationErrors:
    """Test configuration errors"""

    def test_configuration_error(self):
        """Test configuration error"""
        exc = ConfigurationError("Invalid config", "api_key")

        assert exc.status_code == 500
        assert exc.details["config_key"] == "api_key"


class TestRateLimitError:
    """Test rate limiting error"""

    def test_rate_limit_error(self):
        """Test rate limit error"""
        exc = RateLimitError("API", 100, "minute", retry_after=60)

        assert exc.status_code == 429
        assert exc.details["limit"] == 100
        assert exc.details["window"] == "minute"
        assert exc.details["retry_after"] == 60


class TestTimeoutError:
    """Test timeout error"""

    def test_timeout_error(self):
        """Test timeout error"""
        exc = TimeoutError("database_query", 30)

        assert exc.status_code == 504
        assert exc.details["operation"] == "database_query"
        assert exc.details["timeout"] == 30


class TestWrapException:
    """Test exception wrapping utility"""

    def test_wrap_maestro_exception(self):
        """Test wrapping a MaestroException returns it unchanged"""
        original = ValidationError("Test")
        wrapped = wrap_exception(original)

        assert wrapped is original

    def test_wrap_generic_exception(self):
        """Test wrapping a generic exception"""
        original = ValueError("Test value error")
        wrapped = wrap_exception(original)

        assert isinstance(wrapped, MaestroException)
        assert "Test value error" in wrapped.message
        assert wrapped.cause == original
        assert wrapped.details["error_type"] == "ValueError"

    def test_wrap_with_custom_message(self):
        """Test wrapping with custom message"""
        original = RuntimeError("Original")
        wrapped = wrap_exception(original, "Custom message")

        assert wrapped.message == "Custom message"
        assert wrapped.cause == original


class TestExceptionInheritance:
    """Test exception inheritance and isinstance checks"""

    def test_all_inherit_from_maestro_exception(self):
        """Test all custom exceptions inherit from MaestroException"""
        exceptions = [
            ValidationError("test"),
            NotFoundError("User", "123"),
            AuthenticationError(),
            ServiceUnavailableError("DB", "reason"),
            WorkflowExecutionError("wf", "reason"),
        ]

        for exc in exceptions:
            assert isinstance(exc, MaestroException)
            assert isinstance(exc, Exception)

    def test_exception_hierarchy(self):
        """Test exception hierarchy relationships"""
        persona_error = PersonaNotFoundError("test")

        assert isinstance(persona_error, PersonaNotFoundError)
        assert isinstance(persona_error, NotFoundError)
        assert isinstance(persona_error, MaestroException)
        assert isinstance(persona_error, Exception)
