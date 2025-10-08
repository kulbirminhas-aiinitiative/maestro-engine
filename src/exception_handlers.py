"""
FastAPI Exception Handlers for MAESTRO Engine
Provides global exception handling and consistent error responses
"""

import traceback
from typing import Union

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .exceptions import MaestroException

logger = structlog.get_logger(__name__)


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Setup global exception handlers for the FastAPI application

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(MaestroException)
    async def maestro_exception_handler(request: Request, exc: MaestroException) -> JSONResponse:
        """Handle custom MAESTRO exceptions"""

        logger.error(
            "maestro_exception",
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
            path=request.url.path,
            method=request.method,
        )

        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic validation errors"""

        errors = []
        for error in exc.errors():
            errors.append(
                {
                    "field": " -> ".join(str(loc) for loc in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
            )

        logger.warning(
            "validation_error", errors=errors, path=request.url.path, method=request.method
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "ValidationError",
                "message": "Request validation failed",
                "status_code": 422,
                "details": {"errors": errors},
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Handle Starlette HTTP exceptions"""

        logger.warning(
            "http_exception",
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.url.path,
            method=request.method,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": f"HTTPError{exc.status_code}",
                "message": exc.detail,
                "status_code": exc.status_code,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle all other exceptions"""

        # Log the full traceback for debugging
        tb = traceback.format_exc()

        logger.error(
            "unhandled_exception",
            exception=str(exc),
            exception_type=type(exc).__name__,
            traceback=tb,
            path=request.url.path,
            method=request.method,
        )

        # Don't expose internal errors to clients in production
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An internal error occurred. Please contact support if the problem persists.",
                "status_code": 500,
                "details": {
                    "error_type": type(exc).__name__,
                    # Only include error message in development
                    "error_message": str(exc) if app.debug else None,
                },
            },
        )


# ============================================================================
# Helper Functions
# ============================================================================


def create_error_response(
    error_code: str, message: str, status_code: int = 500, details: dict = None
) -> JSONResponse:
    """
    Create a standardized error response

    Args:
        error_code: Error code identifier
        message: Human-readable error message
        status_code: HTTP status code
        details: Additional error details

    Returns:
        JSONResponse with error information
    """
    content = {"error": error_code, "message": message, "status_code": status_code}

    if details:
        content["details"] = details

    return JSONResponse(status_code=status_code, content=content)


def log_exception(exc: Exception, request: Request = None, context: dict = None) -> None:
    """
    Log exception with context

    Args:
        exc: Exception to log
        request: Optional request object
        context: Optional additional context
    """
    log_data = {
        "exception": str(exc),
        "exception_type": type(exc).__name__,
        "traceback": traceback.format_exc(),
    }

    if request:
        log_data.update(
            {
                "path": request.url.path,
                "method": request.method,
                "client": request.client.host if request.client else None,
            }
        )

    if context:
        log_data.update(context)

    logger.error("exception_logged", **log_data)
