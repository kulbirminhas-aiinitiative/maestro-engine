"""
Circuit Breaker Middleware

Implements circuit breaker pattern per backend service to prevent cascading failures.
"""

import logging
from typing import Callable, Dict

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)


class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """
    Circuit breaker middleware for backend services

    Creates one circuit breaker per backend service to:
    - Prevent cascading failures
    - Fast-fail when service is down
    - Automatic recovery detection
    """

    def __init__(self, app):
        super().__init__(app)
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

    def _get_backend_from_request(self, request: Request) -> str:
        """
        Extract backend URL from request state

        Note: Backend URL should be set by routing layer
        """
        # This will be set by the routing layer before reaching here
        return getattr(request.state, "backend_url", "unknown")

    def _get_circuit_breaker(self, backend: str) -> CircuitBreaker:
        """Get or create circuit breaker for backend"""
        if backend not in self.circuit_breakers:
            self.circuit_breakers[backend] = CircuitBreaker(
                failure_threshold=5,
                success_threshold=2,
                timeout=60,
                name=f"gateway-{backend}",
            )
        return self.circuit_breakers[backend]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip circuit breaker for health checks
        if request.url.path in ["/health", "/health/ready", "/routes"]:
            return await call_next(request)

        # Get backend from request (if available)
        backend = self._get_backend_from_request(request)

        # Get circuit breaker for this backend
        circuit = self._get_circuit_breaker(backend)

        # Try to execute request through circuit breaker
        try:
            response = await circuit.call(call_next, request)
            return response

        except CircuitBreakerOpenError:
            # Circuit is open, fast-fail
            logger.error(
                f'{{"event":"circuit_breaker_open","backend":"{backend}",'
                f'"path":"{request.url.path}"}}'
            )
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service Unavailable",
                    "message": f"Circuit breaker open for {backend}",
                    "retry_after": 60,
                },
                headers={"Retry-After": "60"},
            )

        except Exception as e:
            # Unexpected error
            logger.error(
                f'{{"event":"circuit_breaker_error","backend":"{backend}",' f'"error":"{str(e)}"}}'
            )
            return JSONResponse(
                status_code=500, content={"error": "Internal Server Error", "message": str(e)}
            )
