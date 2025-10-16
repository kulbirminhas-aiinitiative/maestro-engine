"""
Proxy Router

Forwards HTTP requests and WebSocket connections to backend services.
"""

import logging
from typing import Dict

import httpx
import websockets
from fastapi import Request, WebSocket
from fastapi.responses import Response, StreamingResponse

logger = logging.getLogger(__name__)


class ProxyRouter:
    """
    Proxies requests to backend services

    Handles:
    - HTTP requests (all methods)
    - WebSocket connections
    - Streaming responses
    - Header forwarding
    """

    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client

    async def forward_request(self, request: Request, route_config: Dict, path: str) -> Response:
        """
        Forward HTTP request to backend service

        Args:
            request: Incoming FastAPI request
            route_config: Route configuration (contains backend URL)
            path: Request path

        Returns:
            FastAPI Response
        """
        backend = route_config["backend"]
        request.state.backend_url = backend  # For circuit breaker middleware
        request.state.cache_ttl = route_config.get("cache_ttl", 0)  # For cache middleware

        # Build target URL
        # Remove route prefix and append to backend
        route_path = route_config["path"].rstrip("/*")
        remaining_path = path
        if path.startswith(route_path.lstrip("/")):
            remaining_path = path[len(route_path.lstrip("/")) :]

        target_url = f"{backend}/{remaining_path.lstrip('/')}"

        # Add query parameters
        if request.url.query:
            target_url += f"?{request.url.query}"

        logger.debug(f"Proxying {request.method} {path} -> {target_url}")

        # Prepare headers (exclude hop-by-hop headers)
        headers = dict(request.headers)
        hop_by_hop_headers = [
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
        ]
        for header in hop_by_hop_headers:
            headers.pop(header, None)

        # Add X-Forwarded headers
        headers["X-Forwarded-For"] = request.client.host if request.client else "unknown"
        headers["X-Forwarded-Proto"] = request.url.scheme
        headers["X-Forwarded-Host"] = request.headers.get("host", "")

        try:
            # Read request body
            body = await request.body()

            # Forward request to backend
            response = await self.http_client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                follow_redirects=False,
            )

            # Build response headers (exclude hop-by-hop headers)
            response_headers = dict(response.headers)
            for header in hop_by_hop_headers:
                response_headers.pop(header, None)

            # Remove content-encoding header to prevent browser decoding issues
            # The gateway returns decompressed content, so encoding header should not be set
            response_headers.pop("content-encoding", None)

            # Add gateway header
            response_headers["X-Gateway"] = "maestro-api-gateway"

            # Check if streaming response
            if response.headers.get("transfer-encoding") == "chunked":
                # Stream response
                async def stream_content():
                    async for chunk in response.aiter_bytes():
                        yield chunk

                return StreamingResponse(
                    stream_content(),
                    status_code=response.status_code,
                    headers=response_headers,
                    media_type=response.headers.get("content-type"),
                )
            else:
                # Regular response
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=response_headers,
                    media_type=response.headers.get("content-type"),
                )

        except httpx.TimeoutException:
            logger.error(f"Timeout proxying to {target_url}")
            return Response(
                content='{"error":"Gateway Timeout","message":"Backend service did not respond in time"}',  # noqa: E501
                status_code=504,
                media_type="application/json",
            )

        except httpx.ConnectError:
            logger.error(f"Connection error proxying to {target_url}")
            return Response(
                content='{"error":"Bad Gateway","message":"Cannot connect to backend service"}',
                status_code=502,
                media_type="application/json",
            )

        except Exception as e:
            logger.error(f"Error proxying to {target_url}: {e}")
            return Response(
                content=f'{{"error":"Internal Server Error","message":"{str(e)}"}}',
                status_code=500,
                media_type="application/json",
            )

    async def forward_websocket(self, websocket: WebSocket, route_config: Dict, path: str):
        """
        Forward WebSocket connection to backend service

        Args:
            websocket: Incoming WebSocket connection
            route_config: Route configuration (contains backend URL)
            path: Request path (without /ws prefix, e.g., "accelerator/session-123")
        """
        backend = route_config["backend"]

        # Build target URL (convert http:// to ws://)
        backend_ws = backend.replace("http://", "ws://").replace("https://", "wss://")

        # Extract route prefix (e.g., "/ws/accelerator/*" -> "accelerator")
        route_path = route_config["path"].rstrip("/*")  # "/ws/accelerator"
        route_prefix = route_path.split("/ws/")[-1] if "/ws/" in route_path else ""  # "accelerator"

        # Remove route prefix to get session/resource path
        remaining_path = path
        if route_prefix and path.startswith(route_prefix):
            # Strip the route prefix (e.g., "accelerator/session-123" -> "session-123")
            remaining_path = path[len(route_prefix) :].lstrip("/")

        # Reconstruct backend path with /ws prefix
        # Backend expects: /ws/{session_id}
        target_url = f"{backend_ws}/ws/{remaining_path}"

        logger.info(f"Proxying WebSocket {path} -> {target_url}")

        try:
            # Accept incoming WebSocket
            await websocket.accept()

            # Connect to backend WebSocket
            async with websockets.connect(target_url) as backend_ws:
                # Bidirectional proxy
                async def forward_to_backend():
                    try:
                        while True:
                            message = await websocket.receive_text()
                            await backend_ws.send(message)
                    except Exception:
                        pass

                async def forward_to_client():
                    try:
                        async for message in backend_ws:
                            await websocket.send_text(message)
                    except Exception:
                        pass

                # Run both directions concurrently
                import asyncio

                await asyncio.gather(forward_to_backend(), forward_to_client())

        except Exception as e:
            logger.error(f"WebSocket proxy error: {e}")
            try:
                await websocket.close(code=1011, reason=str(e))
            except Exception:
                pass
