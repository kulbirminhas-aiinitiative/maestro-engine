"""
Rate Limiting Middleware

Implements token bucket algorithm for rate limiting per client/endpoint.
"""

import logging
import time
from collections import defaultdict
from typing import Callable, Dict, Tuple

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket implementation for rate limiting"""

    def __init__(self, rate: int, per_seconds: int):
        """
        Args:
            rate: Number of requests allowed
            per_seconds: Time window in seconds
        """
        self.rate = rate
        self.per_seconds = per_seconds
        self.tokens = rate
        self.last_update = time.time()

    def consume(self) -> bool:
        """
        Try to consume a token

        Returns:
            True if request allowed, False if rate limit exceeded
        """
        now = time.time()
        elapsed = now - self.last_update

        # Refill tokens based on elapsed time
        self.tokens = min(self.rate, self.tokens + (elapsed / self.per_seconds) * self.rate)
        self.last_update = now

        # Try to consume token
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using token bucket algorithm

    Rate limit format: "{count}/{unit}" (e.g., "100/minute", "20/minute")
    Limits are per client IP + endpoint path
    """

    def __init__(self, app, config: Dict):
        super().__init__(app)
        self.config = config
        self.buckets: Dict[str, TokenBucket] = {}
        self.route_limits: Dict[str, Tuple[int, int]] = {}
        self._parse_default_limit()

    def _parse_default_limit(self):
        """Parse default rate limit from config"""
        default = self.config.get("default", "60/minute")
        self.default_limit = self._parse_rate_limit(default)

    def _parse_rate_limit(self, limit_str: str) -> Tuple[int, int]:
        """
        Parse rate limit string into (count, seconds)

        Args:
            limit_str: Rate limit string (e.g., "100/minute", "20/hour")

        Returns:
            Tuple of (count, seconds)
        """
        try:
            count, unit = limit_str.split("/")
            count = int(count)

            unit_seconds = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}

            seconds = unit_seconds.get(unit.lower(), 60)
            return (count, seconds)
        except Exception:
            logger.warning(f"Invalid rate limit format: {limit_str}, using default")
            return (60, 60)  # 60/minute default

    def _get_bucket_key(self, request: Request) -> str:
        """Generate bucket key from client IP + path"""
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        return f"{client_ip}:{path}"

    def _get_rate_limit(self, path: str) -> Tuple[int, int]:
        """Get rate limit for path (from config or default)"""
        # Check if we have a specific limit for this path
        if path in self.route_limits:
            return self.route_limits[path]

        # Use default
        return self.default_limit

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/health/ready", "/routes"]:
            return await call_next(request)

        # Get or create token bucket for this client+path
        bucket_key = self._get_bucket_key(request)
        rate, per_seconds = self._get_rate_limit(request.url.path)

        if bucket_key not in self.buckets:
            self.buckets[bucket_key] = TokenBucket(rate, per_seconds)

        bucket = self.buckets[bucket_key]

        # Try to consume token
        if bucket.consume():
            # Request allowed
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(rate)
            response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
            return response
        else:
            # Rate limit exceeded
            logger.warning(
                f'{{"event":"rate_limit_exceeded","bucket_key":"{bucket_key}",'
                f'"limit":"{rate}/{per_seconds}s"}}'
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "limit": f"{rate}/{per_seconds}s",
                    "retry_after": per_seconds,
                },
                headers={
                    "Retry-After": str(per_seconds),
                    "X-RateLimit-Limit": str(rate),
                    "X-RateLimit-Remaining": "0",
                },
            )
