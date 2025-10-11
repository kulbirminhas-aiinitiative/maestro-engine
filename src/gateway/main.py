"""
MAESTRO API Gateway - Main Application

Part of ADR-003: API Gateway Pattern
Single entry point for all client requests to MAESTRO platform services.

Usage:
    uvicorn src.gateway.main:app --port 8080 --host 0.0.0.0
"""

import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Any, Dict, List

import httpx
import yaml
from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.gateway.middleware.auth import AuthMiddleware
from src.gateway.middleware.cache import CacheMiddleware
from src.gateway.middleware.circuit_breaker import CircuitBreakerMiddleware
from src.gateway.middleware.logging import LoggingMiddleware
from src.gateway.middleware.rate_limit import RateLimitMiddleware
from src.gateway.routing.proxy import ProxyRouter
from src.gateway.routing.router import RouteManager

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","service":"api-gateway","message":"%(message)s"}',  # noqa: E501
)
logger = logging.getLogger(__name__)


class GatewayConfig:
    """Gateway configuration loader"""

    def __init__(self, config_path: str = "config/gateway_routes.yaml"):
        self.config_path = config_path
        self.routes: List[Dict] = []
        self.cors_config: Dict = {}
        self.rate_limit_defaults: Dict = {}
        self.auth_config: Dict = {}
        self.cache_config: Dict = {}

    @staticmethod
    def _expand_env_vars(value: Any) -> Any:
        """
        Recursively expand environment variables in config values.

        Supports syntax: ${VAR_NAME:default_value}
        Examples:
            ${BFF_SERVICE_URL:http://localhost:4001}
            ${MAESTRO_ENGINE_URL}
        """
        if isinstance(value, str):
            # Pattern matches ${VAR_NAME:default} or ${VAR_NAME}
            pattern = r"\$\{(\w+)(?::([^}]*))?\}"

            def replace(match):
                var_name, default = match.groups()
                return os.environ.get(var_name, default or "")

            return re.sub(pattern, replace, value)
        elif isinstance(value, dict):
            return {k: GatewayConfig._expand_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [GatewayConfig._expand_env_vars(item) for item in value]
        else:
            return value

    def load(self):
        """Load gateway configuration from YAML"""
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)

            # Expand environment variables in all config values
            config = self._expand_env_vars(config)

            self.routes = config.get("routes", [])
            self.cors_config = config.get("cors", {})
            self.rate_limit_defaults = config.get("rate_limit_defaults", {})
            self.auth_config = config.get("auth", {})
            self.cache_config = config.get("cache", {})

            logger.info(f"Loaded {len(self.routes)} route(s) from {self.config_path}")

            # Log expanded backends for debugging
            for route in self.routes:
                logger.info(f"Route: {route['path']} -> {route['backend']}")

        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}, using defaults")
            self._load_defaults()
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")
            self._load_defaults()

    def _load_defaults(self):
        """Load default configuration"""
        self.routes = [
            {
                "path": "/api/v1/accelerator",
                "backend": "http://localhost:4001",
                "rate_limit": "100/minute",
                "requires_auth": False,
                "cache_ttl": 0,
            },
            {
                "path": "/api/v1/guardian",
                "backend": "http://localhost:5000",
                "rate_limit": "20/minute",
                "requires_auth": False,
                "cache_ttl": 0,
            },
        ]
        self.cors_config = {
            "allow_origins": ["http://localhost:4200"],
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            "allow_headers": ["*"],
            "allow_credentials": True,
        }
        self.rate_limit_defaults = {"default": "60/minute"}
        self.auth_config = {"jwt_secret": "change-me-in-production"}
        self.cache_config = {"enabled": True, "default_ttl": 300}


# Gateway configuration
config = GatewayConfig()
# Load config immediately (before creating FastAPI app)
config.load()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting MAESTRO API Gateway...")

    # Initialize route manager
    route_manager = RouteManager(config.routes)
    app.state.route_manager = route_manager

    # Initialize HTTP client for proxying
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_keepalive_connections=100, max_connections=200),
    )

    logger.info("MAESTRO API Gateway started successfully")
    logger.info(f"Registered {len(config.routes)} routes")

    yield

    # Shutdown
    logger.info("Shutting down MAESTRO API Gateway...")
    await app.state.http_client.aclose()
    logger.info("MAESTRO API Gateway stopped")


# Create FastAPI application
app = FastAPI(
    title="MAESTRO API Gateway",
    description="Single entry point for all MAESTRO platform services",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware (first in chain)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_config.get("allow_origins", ["http://localhost:4200"]),
    allow_origin_regex=config.cors_config.get("allow_origin_regex"),
    allow_credentials=config.cors_config.get("allow_credentials", True),
    allow_methods=config.cors_config.get("allow_methods", ["*"]),
    allow_headers=config.cors_config.get("allow_headers", ["*"]),
)

# Add custom middleware (in reverse order due to FastAPI stacking)
# Stack order: Logging -> CORS -> Rate Limit -> Auth -> Circuit Breaker -> Cache -> Routing
app.add_middleware(CacheMiddleware, config=config.cache_config)
app.add_middleware(CircuitBreakerMiddleware)
app.add_middleware(AuthMiddleware, config=config.auth_config)
app.add_middleware(RateLimitMiddleware, config=config.rate_limit_defaults)
app.add_middleware(LoggingMiddleware)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "api-gateway", "version": "1.0.0"}


@app.get("/health/ready")
async def readiness_check(request: Request):
    """Readiness check - verifies all backend services are reachable"""
    route_manager = request.app.state.route_manager
    http_client = request.app.state.http_client

    results = {}
    all_ready = True

    for route_config in route_manager.routes:
        backend = route_config["backend"]
        try:
            response = await http_client.get(
                f"{backend}/health", timeout=2.0, follow_redirects=False
            )
            results[backend] = {"status": "ready" if response.status_code == 200 else "degraded"}
        except Exception as e:
            results[backend] = {"status": "unavailable", "error": str(e)}
            all_ready = False

    return JSONResponse(
        status_code=200 if all_ready else 503,
        content={"status": "ready" if all_ready else "degraded", "backends": results},
    )


@app.get("/routes")
async def list_routes(request: Request):
    """List all registered routes (for debugging)"""
    route_manager = request.app.state.route_manager
    return {
        "routes": [
            {"path": r["path"], "backend": r["backend"], "rate_limit": r.get("rate_limit", "N/A")}
            for r in route_manager.routes
        ]
    }


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_handler(request: Request, path: str):
    """
    Main proxy handler - routes requests to backend services

    Flow:
    1. Middleware stack processes request (auth, rate limit, etc.)
    2. RouteManager finds matching backend service
    3. ProxyRouter forwards request to backend
    4. Response returned through middleware stack
    """
    route_manager = request.app.state.route_manager
    http_client = request.app.state.http_client

    # Find matching route
    route_config = route_manager.match_route(f"/{path}")
    if not route_config:
        return JSONResponse(status_code=404, content={"error": "Route not found"})

    # Proxy request to backend
    proxy = ProxyRouter(http_client)
    return await proxy.forward_request(request, route_config, path)


@app.websocket("/ws/{path:path}")
async def websocket_proxy(websocket: WebSocket, path: str):
    """WebSocket proxy handler"""
    route_manager = websocket.app.state.route_manager

    # Find matching route
    route_config = route_manager.match_route(f"/ws/{path}")
    if not route_config:
        await websocket.close(code=1008, reason="Route not found")
        return

    # Proxy WebSocket connection
    proxy = ProxyRouter(None)
    await proxy.forward_websocket(websocket, route_config, path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
