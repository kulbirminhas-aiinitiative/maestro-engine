"""
Service Registry API Routes for MAESTRO Engine.

Provides REST API for service discovery and health monitoring.
"""

from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, FastAPI, HTTPException, status
from pydantic import BaseModel

from src.registry import ServiceInfo, ServiceRegistry, ServiceStatus

logger = structlog.get_logger(__name__)


class ServiceRegisterRequest(BaseModel):
    """Request model for service registration."""

    name: str
    url: str
    port: int
    health_endpoint: str = "/health"
    metadata: Optional[Dict[str, Any]] = None


class ServiceHealthResponse(BaseModel):
    """Response model for service health."""

    name: str
    status: ServiceStatus
    url: str
    latency_ms: Optional[float] = None
    last_heartbeat: Optional[str] = None


class AllServicesHealthResponse(BaseModel):
    """Response model for all services health check."""

    services: Dict[str, Dict[str, Any]]
    total_services: int
    healthy_services: int


def create_registry_routes(app: FastAPI, registry: ServiceRegistry) -> None:
    """
    Create and register service registry routes.

    Args:
        app: FastAPI application instance
        registry: ServiceRegistry instance
    """
    router = APIRouter(prefix="/registry", tags=["Service Registry"])

    @router.get("/services", response_model=List[ServiceInfo])
    async def list_services() -> List[ServiceInfo]:
        """
        List all registered services.

        Returns:
            List of all registered services with their information
        """
        services = registry.get_all_services()
        logger.info("Listed all services", count=len(services))
        return services

    @router.get("/services/{service_name}", response_model=ServiceInfo)
    async def get_service(service_name: str) -> ServiceInfo:
        """
        Get information about a specific service.

        Args:
            service_name: Name of the service to retrieve

        Returns:
            ServiceInfo for the requested service

        Raises:
            HTTPException: 404 if service not found
        """
        service = registry.get_service(service_name)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found",
            )
        return service

    @router.post("/services", response_model=ServiceInfo, status_code=status.HTTP_201_CREATED)
    async def register_service(request: ServiceRegisterRequest) -> ServiceInfo:
        """
        Register a new service.

        Args:
            request: Service registration details

        Returns:
            Registered ServiceInfo
        """
        service = registry.register_service(
            name=request.name,
            url=request.url,
            port=request.port,
            health_endpoint=request.health_endpoint,
            metadata=request.metadata,
        )
        logger.info("Service registered via API", service=request.name)
        return service

    @router.delete("/services/{service_name}", status_code=status.HTTP_204_NO_CONTENT)
    async def deregister_service(service_name: str) -> None:
        """
        Deregister a service.

        Args:
            service_name: Name of the service to remove

        Raises:
            HTTPException: 404 if service not found
        """
        success = registry.deregister_service(service_name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found",
            )
        logger.info("Service deregistered via API", service=service_name)

    @router.get("/health", response_model=AllServicesHealthResponse)
    async def health_check_all() -> AllServicesHealthResponse:
        """
        Check health of all registered services.

        Returns:
            Health status for all services
        """
        health_report = await registry.health_check_all()

        healthy_count = sum(
            1 for service in health_report.values() if service["status"] == "healthy"
        )

        return AllServicesHealthResponse(
            services=health_report,
            total_services=len(health_report),
            healthy_services=healthy_count,
        )

    @router.get("/health/{service_name}")
    async def health_check_service(service_name: str) -> Dict[str, Any]:
        """
        Check health of a specific service.

        Args:
            service_name: Name of the service to check

        Returns:
            Health status for the service

        Raises:
            HTTPException: 404 if service not found
        """
        service = registry.get_service(service_name)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found",
            )

        updated_service = await registry.check_service_health(service)

        return {
            "name": updated_service.name,
            "status": updated_service.status.value,
            "url": updated_service.url,
            "latency_ms": updated_service.latency_ms,
            "last_heartbeat": (
                updated_service.last_heartbeat.isoformat()
                if updated_service.last_heartbeat
                else None
            ),
        }

    @router.get("/healthy")
    async def list_healthy_services() -> Dict[str, List[str]]:
        """
        List all healthy services.

        Returns:
            List of healthy service names
        """
        # First perform health check
        await registry.health_check_all()

        healthy_services = registry.list_healthy_services()
        return {"healthy_services": healthy_services, "count": len(healthy_services)}

    @router.get("/url/{service_name}")
    async def get_service_url(service_name: str) -> Dict[str, str]:
        """
        Get URL for a specific service.

        Args:
            service_name: Name of the service

        Returns:
            Service URL

        Raises:
            HTTPException: 404 if service not found
        """
        url = registry.get_service_url(service_name)
        if not url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found",
            )
        return {"service": service_name, "url": url}

    # Register the router with the app
    app.include_router(router)
    logger.info("Service registry routes registered")
