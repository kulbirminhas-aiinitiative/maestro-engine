"""
Authentication Middleware

Validates JWT tokens for protected routes.
"""

import logging
from typing import Callable, Dict

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    JWT authentication middleware

    Protected routes require valid JWT token in Authorization header.
    Currently in permissive mode (auth optional) to support gradual rollout.
    """

    def __init__(self, app, config: Dict):
        super().__init__(app)
        self.config = config
        self.jwt_secret = config.get("jwt_secret", "change-me-in-production")
        self.permissive_mode = config.get("permissive_mode", True)
        self.protected_paths = config.get("protected_paths", [])

    def _is_protected_path(self, path: str) -> bool:
        """Check if path requires authentication"""
        # Skip auth for health checks
        if path in ["/health", "/health/ready", "/routes"]:
            return False

        # Check protected paths
        for protected_path in self.protected_paths:
            if path.startswith(protected_path):
                return True

        return False

    def _extract_token(self, request: Request) -> str:
        """Extract JWT token from Authorization header"""
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            return auth_header[7:]

        return ""

    def _validate_token(self, token: str) -> bool:
        """
        Validate JWT token

        Note: Simplified validation for now.
        TODO: Implement proper JWT validation with PyJWT library
        """
        if not token:
            return False

        # In permissive mode, accept any non-empty token
        if self.permissive_mode:
            return True

        # TODO: Implement proper JWT validation
        # try:
        #     payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
        #     return True
        # except jwt.InvalidTokenError:
        #     return False

        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if path is protected
        if not self._is_protected_path(request.url.path):
            # Path not protected, allow through
            return await call_next(request)

        # Extract token
        token = self._extract_token(request)

        # Validate token
        if self._validate_token(token):
            # Token valid, allow through
            logger.debug(f"Auth successful for {request.url.path}")
            return await call_next(request)
        else:
            # Token invalid or missing
            if self.permissive_mode:
                # In permissive mode, log warning but allow through
                logger.warning(
                    f'{{"event":"auth_failed_permissive","path":"{request.url.path}",'
                    f'"client_ip":"{request.client.host if request.client else "unknown"}"}}'
                )
                return await call_next(request)
            else:
                # In strict mode, reject request
                logger.warning(
                    f'{{"event":"auth_failed_rejected","path":"{request.url.path}",'
                    f'"client_ip":"{request.client.host if request.client else "unknown"}"}}'
                )
                return JSONResponse(
                    status_code=401,
                    content={"error": "Unauthorized", "message": "Valid JWT token required"},
                )
