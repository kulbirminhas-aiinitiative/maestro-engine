"""
Service Registry for MAESTRO Engine.

Provides service discovery, health checking, and configuration management.
Supports file-based configuration with environment variable overrides.
"""

import asyncio
import os
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import structlog
import yaml
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class ServiceStatus(str, Enum):
    """Service health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ServiceInfo(BaseModel):
    """Service information model."""

    name: str
    url: str
    port: int
    health_endpoint: str = "/health"
    external: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_heartbeat: Optional[datetime] = None
    latency_ms: Optional[float] = None


class ServiceRegistry:
    """
    Service registry with file-based configuration and health checking.

    Supports:
    - YAML configuration file
    - Environment variable overrides (MAESTRO_{SERVICE}_URL)
    - Health checks with status tracking
    - Service discovery
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize service registry.

        Args:
            config_path: Path to services.yaml config file.
                        Defaults to config/services.yaml
        """
        self.config_path = config_path or Path("config/services.yaml")
        self.services: Dict[str, ServiceInfo] = {}
        self._load_config()
        logger.info("Service registry initialized", services_count=len(self.services))

    def _load_config(self) -> None:
        """Load service configuration from YAML file."""
        if not self.config_path.exists():
            logger.warning(
                "Service config not found, using defaults",
                config_path=str(self.config_path),
            )
            self._load_defaults()
            return

        try:
            with open(self.config_path) as f:
                config = yaml.safe_load(f)

            for name, service_config in config.get("services", {}).items():
                # Check for environment variable override
                env_key = f"MAESTRO_{name.upper().replace('-', '_')}_SERVICE_URL"
                url = os.getenv(env_key, service_config.get("url"))

                # If URL not in config or env, construct from port
                if not url:
                    host = os.getenv("MAESTRO_SERVICE_HOST", "localhost")
                    port = service_config.get("port")
                    url = f"http://{host}:{port}"

                self.services[name] = ServiceInfo(
                    name=name,
                    url=url,
                    port=service_config.get("port"),
                    health_endpoint=service_config.get("health", "/health"),
                    external=service_config.get("external", False),
                    metadata=service_config.get("metadata", {}),
                )

            logger.info("Service config loaded", services=list(self.services.keys()))

        except Exception as e:
            logger.error("Failed to load service config", error=str(e))
            self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default service configuration."""
        defaults = {
            "coordinator": {"port": 8002, "health": "/health"},
            "mcp": {"port": 9800, "health": "/health"},
            "orchestration": {"port": 8004, "health": "/health"},
            "rag": {"port": 9803, "health": "/health"},
            "templates": {"port": 8001, "health": "/health", "external": True},
        }

        host = os.getenv("MAESTRO_SERVICE_HOST", "localhost")

        for name, config in defaults.items():
            env_key = f"MAESTRO_{name.upper()}_SERVICE_URL"
            url = os.getenv(env_key, f"http://{host}:{config['port']}")

            self.services[name] = ServiceInfo(
                name=name,
                url=url,
                port=config["port"],
                health_endpoint=config.get("health", "/health"),
                external=config.get("external", False),
            )

    def register_service(
        self,
        name: str,
        url: str,
        port: int,
        health_endpoint: str = "/health",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceInfo:
        """
        Register a service.

        Args:
            name: Service name
            url: Service base URL
            port: Service port
            health_endpoint: Health check endpoint
            metadata: Additional service metadata

        Returns:
            ServiceInfo for the registered service
        """
        service = ServiceInfo(
            name=name,
            url=url,
            port=port,
            health_endpoint=health_endpoint,
            metadata=metadata or {},
        )
        self.services[name] = service
        logger.info("Service registered", service=name, url=url, port=port)
        return service

    def deregister_service(self, name: str) -> bool:
        """
        Deregister a service.

        Args:
            name: Service name to remove

        Returns:
            True if service was removed, False if not found
        """
        if name in self.services:
            del self.services[name]
            logger.info("Service deregistered", service=name)
            return True
        return False

    def get_service(self, name: str) -> Optional[ServiceInfo]:
        """
        Get service information by name.

        Args:
            name: Service name

        Returns:
            ServiceInfo if found, None otherwise
        """
        return self.services.get(name)

    def get_all_services(self) -> List[ServiceInfo]:
        """
        Get all registered services.

        Returns:
            List of all ServiceInfo objects
        """
        return list(self.services.values())

    async def check_service_health(self, service: ServiceInfo) -> ServiceInfo:
        """
        Check health of a single service.

        Args:
            service: ServiceInfo to check

        Returns:
            Updated ServiceInfo with current status
        """
        health_url = f"{service.url}{service.health_endpoint}"
        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(health_url)
                latency_ms = (time.time() - start_time) * 1000

                service.latency_ms = round(latency_ms, 2)
                service.last_heartbeat = datetime.utcnow()

                if response.status_code == 200:
                    if latency_ms > 100:
                        service.status = ServiceStatus.DEGRADED
                    else:
                        service.status = ServiceStatus.HEALTHY
                else:
                    service.status = ServiceStatus.UNHEALTHY

        except httpx.TimeoutException:
            service.status = ServiceStatus.UNHEALTHY
            service.latency_ms = None
            logger.warning("Service health check timeout", service=service.name)

        except Exception as e:
            service.status = ServiceStatus.UNHEALTHY
            service.latency_ms = None
            logger.error("Service health check failed", service=service.name, error=str(e))

        return service

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Check health of all registered services.

        Returns:
            Dictionary mapping service names to health status
        """
        tasks = [self.check_service_health(service) for service in self.services.values()]
        results = await asyncio.gather(*tasks)

        health_report = {}
        for service in results:
            health_report[service.name] = {
                "status": service.status.value,
                "latency_ms": service.latency_ms,
                "last_heartbeat": (
                    service.last_heartbeat.isoformat() if service.last_heartbeat else None
                ),
                "url": service.url,
            }

        logger.info("Health check completed", services_checked=len(results))
        return health_report

    def get_service_url(self, name: str) -> Optional[str]:
        """
        Get service URL by name.

        Args:
            name: Service name

        Returns:
            Service URL if found, None otherwise
        """
        service = self.get_service(name)
        return service.url if service else None

    def list_healthy_services(self) -> List[str]:
        """
        Get list of healthy service names.

        Returns:
            List of service names with HEALTHY status
        """
        return [
            name
            for name, service in self.services.items()
            if service.status == ServiceStatus.HEALTHY
        ]

    def to_dict(self) -> Dict[str, Any]:
        """
        Export registry as dictionary.

        Returns:
            Dictionary representation of all services
        """
        return {
            "services": {name: service.model_dump() for name, service in self.services.items()},
            "total_services": len(self.services),
            "healthy_services": len(self.list_healthy_services()),
        }
