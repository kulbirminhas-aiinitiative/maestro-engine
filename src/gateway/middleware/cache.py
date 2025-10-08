"""
Cache Middleware

Implements response caching for GET requests to reduce backend load.
"""

import hashlib
import json
import logging
import time
from typing import Callable, Dict, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class CacheEntry:
    """Cache entry with TTL"""

    def __init__(self, response_body: bytes, status_code: int, headers: Dict, ttl: int):
        self.response_body = response_body
        self.status_code = status_code
        self.headers = headers
        self.created_at = time.time()
        self.ttl = ttl

    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return (time.time() - self.created_at) > self.ttl


class CacheMiddleware(BaseHTTPMiddleware):
    """
    Response caching middleware

    Caches GET requests based on:
    - Path
    - Query parameters
    - Headers (if specified)

    Cache key format: sha256(path + query + headers)
    """

    def __init__(self, app, config: Dict):
        super().__init__(app)
        self.config = config
        self.enabled = config.get("enabled", True)
        self.default_ttl = config.get("default_ttl", 300)  # 5 minutes
        self.cache: Dict[str, CacheEntry] = {}
        self.max_cache_size = config.get("max_size", 1000)

    def _generate_cache_key(self, request: Request) -> str:
        """Generate cache key from request"""
        # Include path, query, and method
        key_parts = [request.method, request.url.path, str(request.url.query)]

        # Hash to get fixed-length key
        key_str = "|".join(key_parts)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def _get_ttl(self, request: Request) -> int:
        """Get TTL for request (from route config or default)"""
        # TTL can be set by route config (via request.state)
        return getattr(request.state, "cache_ttl", self.default_ttl)

    def _should_cache(self, request: Request) -> bool:
        """Determine if request should be cached"""
        # Only cache GET requests
        if request.method != "GET":
            return False

        # Don't cache health checks
        if request.url.path in ["/health", "/health/ready", "/routes"]:
            return False

        # Check TTL (0 = no caching)
        ttl = self._get_ttl(request)
        if ttl <= 0:
            return False

        return True

    def _evict_expired(self):
        """Evict expired cache entries"""
        expired_keys = [key for key, entry in self.cache.items() if entry.is_expired()]
        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.debug(f"Evicted {len(expired_keys)} expired cache entries")

    def _evict_oldest(self):
        """Evict oldest cache entry if cache is full"""
        if len(self.cache) >= self.max_cache_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k].created_at)
            del self.cache[oldest_key]
            logger.debug(f"Evicted oldest cache entry: {oldest_key}")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if caching is enabled
        if not self.enabled:
            return await call_next(request)

        # Check if request should be cached
        if not self._should_cache(request):
            return await call_next(request)

        # Generate cache key
        cache_key = self._generate_cache_key(request)

        # Periodically evict expired entries
        if len(self.cache) % 100 == 0:
            self._evict_expired()

        # Check cache
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if not entry.is_expired():
                # Cache hit
                logger.debug(
                    f'{{"event":"cache_hit","path":"{request.url.path}",'
                    f'"cache_key":"{cache_key[:16]}..."}}'
                )
                response = Response(
                    content=entry.response_body,
                    status_code=entry.status_code,
                    headers=dict(entry.headers),
                )
                response.headers["X-Cache"] = "HIT"
                response.headers["X-Cache-Age"] = str(int(time.time() - entry.created_at))
                return response
            else:
                # Cache expired
                del self.cache[cache_key]

        # Cache miss - execute request
        logger.debug(
            f'{{"event":"cache_miss","path":"{request.url.path}",'
            f'"cache_key":"{cache_key[:16]}..."}}'
        )
        response = await call_next(request)

        # Cache successful responses (2xx)
        if 200 <= response.status_code < 300:
            # Evict oldest if cache is full
            self._evict_oldest()

            # Read response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            # Store in cache
            ttl = self._get_ttl(request)
            self.cache[cache_key] = CacheEntry(
                response_body=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                ttl=ttl,
            )

            # Create new response with cached body
            response = Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
            )
            response.headers["X-Cache"] = "MISS"

        return response
