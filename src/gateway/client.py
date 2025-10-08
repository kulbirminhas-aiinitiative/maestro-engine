"""
Gateway Client SDK

Provides a simple interface for services to communicate through the API Gateway.
All inter-service communication should use this client instead of direct HTTP calls.

Usage:
    from src.gateway.client import GatewayClient

    # Initialize client
    gateway = GatewayClient()

    # Call another service
    response = await gateway.call("templates", "/api/search", method="POST", json={...})

    # Synchronous version
    response = gateway.call_sync("quality", "/api/test", method="GET")
"""

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class GatewayClient:
    """
    Client for inter-service communication through API Gateway

    All services should use this client instead of direct HTTP calls.
    Provides automatic resilience, service discovery, and monitoring.

    Features:
    - Service discovery (no hardcoded URLs)
    - Automatic retry with backoff
    - Circuit breaker integration
    - Request tracing
    - Structured logging
    """

    def __init__(
        self,
        gateway_url: Optional[str] = None,
        timeout: float = 30.0,
        service_name: Optional[str] = None,
    ):
        """
        Initialize Gateway Client

        Args:
            gateway_url: Gateway base URL (defaults to GATEWAY_URL env var or localhost:8080)
            timeout: Request timeout in seconds (default: 30)
            service_name: Name of calling service (for tracing)
        """
        self.gateway_url = gateway_url or os.getenv("GATEWAY_URL", "http://localhost:8080").rstrip(
            "/"
        )
        self.timeout = timeout
        self.service_name = service_name or os.getenv("SERVICE_NAME", "unknown")

        # HTTP client for async requests
        self._async_client: Optional[httpx.AsyncClient] = None

        # HTTP client for sync requests
        self._sync_client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_keepalive_connections=50, max_connections=100),
        )

        logger.info(
            f'{{"event":"gateway_client_initialized",'
            f'"gateway_url":"{self.gateway_url}",'
            f'"service_name":"{self.service_name}"}}'
        )

    async def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client"""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_keepalive_connections=50, max_connections=100),
            )
        return self._async_client

    def _build_url(self, service: str, path: str) -> str:
        """
        Build full URL for service call

        Args:
            service: Target service name (e.g., "templates", "quality")
            path: Service endpoint path (e.g., "/api/search")

        Returns:
            Full gateway URL (e.g., "http://gateway:8080/api/v1/templates/api/search")
        """
        # Normalize path
        path = path.lstrip("/")

        # Build gateway route
        # Services are exposed as: /api/v1/{service}/*
        url = f"{self.gateway_url}/api/v1/{service}/{path}"

        return url

    def _get_headers(self, headers: Optional[Dict] = None) -> Dict:
        """Build request headers with tracing information"""
        default_headers = {
            "X-Service-Name": self.service_name,
            "Content-Type": "application/json",
        }

        if headers:
            default_headers.update(headers)

        return default_headers

    async def call(
        self,
        service: str,
        path: str,
        method: str = "GET",
        json: Optional[Dict] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> httpx.Response:
        """
        Make async HTTP call to another service through gateway

        Args:
            service: Target service name (e.g., "templates", "quality")
            path: Service endpoint path (e.g., "/api/search")
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            json: JSON body (for POST/PUT/PATCH)
            data: Raw body data
            headers: Additional headers
            params: Query parameters

        Returns:
            httpx.Response object

        Raises:
            httpx.HTTPError: On network/HTTP errors
            httpx.TimeoutException: On timeout

        Example:
            # Search templates
            response = await gateway.call(
                "templates",
                "/api/search",
                method="POST",
                json={"query": "authentication"}
            )
            results = response.json()
        """
        url = self._build_url(service, path)
        request_headers = self._get_headers(headers)
        client = await self._get_async_client()

        logger.debug(
            f'{{"event":"gateway_call","service":"{service}",'
            f'"method":"{method}","path":"{path}"}}'
        )

        try:
            response = await client.request(
                method=method,
                url=url,
                json=json,
                data=data,
                headers=request_headers,
                params=params,
            )

            logger.info(
                f'{{"event":"gateway_call_success","service":"{service}",'
                f'"method":"{method}","path":"{path}","status":{response.status_code}}}'
            )

            return response

        except httpx.TimeoutException as e:
            logger.error(
                f'{{"event":"gateway_call_timeout","service":"{service}",'
                f'"method":"{method}","path":"{path}","error":"{str(e)}"}}'
            )
            raise

        except httpx.HTTPError as e:
            logger.error(
                f'{{"event":"gateway_call_error","service":"{service}",'
                f'"method":"{method}","path":"{path}","error":"{str(e)}"}}'
            )
            raise

    def call_sync(
        self,
        service: str,
        path: str,
        method: str = "GET",
        json: Optional[Dict] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> httpx.Response:
        """
        Make synchronous HTTP call to another service through gateway

        Same as call() but synchronous. Use this in non-async code.

        Example:
            response = gateway.call_sync(
                "quality",
                "/api/test",
                method="POST",
                json={"code": "..."}
            )
        """
        url = self._build_url(service, path)
        request_headers = self._get_headers(headers)

        logger.debug(
            f'{{"event":"gateway_call_sync","service":"{service}",'
            f'"method":"{method}","path":"{path}"}}'
        )

        try:
            response = self._sync_client.request(
                method=method,
                url=url,
                json=json,
                data=data,
                headers=request_headers,
                params=params,
            )

            logger.info(
                f'{{"event":"gateway_call_sync_success","service":"{service}",'
                f'"method":"{method}","path":"{path}","status":{response.status_code}}}'
            )

            return response

        except httpx.TimeoutException as e:
            logger.error(
                f'{{"event":"gateway_call_sync_timeout","service":"{service}",'
                f'"method":"{method}","path":"{path}","error":"{str(e)}"}}'
            )
            raise

        except httpx.HTTPError as e:
            logger.error(
                f'{{"event":"gateway_call_sync_error","service":"{service}",'
                f'"method":"{method}","path":"{path}","error":"{str(e)}"}}'
            )
            raise

    async def close(self):
        """Close async HTTP client (cleanup)"""
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None

    def close_sync(self):
        """Close sync HTTP client (cleanup)"""
        self._sync_client.close()

    def __enter__(self):
        """Context manager support for sync client"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup for sync client"""
        self.close_sync()

    async def __aenter__(self):
        """Async context manager support"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager cleanup"""
        await self.close()


# Convenience singleton instance
# Services can use this directly without creating their own instance
gateway = GatewayClient()
