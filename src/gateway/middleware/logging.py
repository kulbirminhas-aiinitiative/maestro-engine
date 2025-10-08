"""
Logging Middleware

Logs all incoming requests and outgoing responses with structured JSON format.
"""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs all HTTP requests and responses

    Logged information:
    - Request method, path, headers
    - Response status, duration
    - Client IP
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Start timer
        start_time = time.time()

        # Extract request details
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        query = str(request.url.query) if request.url.query else ""

        # Log incoming request
        logger.info(
            f'{{"event":"request_received","method":"{method}","path":"{path}",'
            f'"query":"{query}","client_ip":"{client_ip}"}}'
        )

        # Process request
        try:
            response = await call_next(request)

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log outgoing response
            logger.info(
                f'{{"event":"request_completed","method":"{method}","path":"{path}",'
                f'"status":{response.status_code},"duration_ms":{duration_ms},'
                f'"client_ip":"{client_ip}"}}'
            )

            # Add timing header
            response.headers["X-Response-Time"] = f"{duration_ms}ms"

            return response

        except Exception as e:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log error
            logger.error(
                f'{{"event":"request_failed","method":"{method}","path":"{path}",'
                f'"error":"{str(e)}","duration_ms":{duration_ms},'
                f'"client_ip":"{client_ip}"}}'
            )
            raise
