"""
Comprehensive Health Check System for MAESTRO Engine
Provides liveness, readiness, and dependency health checks
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import structlog
from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


# ============================================================================
# Response Models
# ============================================================================


class HealthStatus(BaseModel):
    """Health check status response"""

    status: str = Field(..., description="Overall health status: healthy, degraded, unhealthy")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(default="3.0.0", description="Service version")
    service: str = Field(..., description="Service name")
    uptime: float = Field(..., description="Service uptime in seconds")


class DependencyStatus(BaseModel):
    """Individual dependency health status"""

    name: str
    status: str  # healthy, degraded, unhealthy
    response_time: Optional[float] = None  # in milliseconds
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class DetailedHealthStatus(HealthStatus):
    """Detailed health check with dependency statuses"""

    dependencies: Dict[str, DependencyStatus] = Field(
        default_factory=dict, description="Health status of dependencies"
    )
    checks: Dict[str, bool] = Field(
        default_factory=dict, description="Individual health check results"
    )


# ============================================================================
# Health Check Utilities
# ============================================================================


class HealthChecker:
    """Health check utility class"""

    def __init__(self):
        self.start_time = datetime.utcnow()
        self._checks = {}

    def get_uptime(self) -> float:
        """Get service uptime in seconds"""
        return (datetime.utcnow() - self.start_time).total_seconds()

    async def check_database(self) -> DependencyStatus:
        """Check database connectivity"""
        start = datetime.utcnow()
        try:
            # Import here to avoid circular dependencies
            from src.database import get_db_session

            async with get_db_session() as session:
                # Simple query to check connection
                await session.execute("SELECT 1")

            response_time = (datetime.utcnow() - start).total_seconds() * 1000
            return DependencyStatus(
                name="database",
                status="healthy",
                response_time=response_time,
                message="Database connection successful",
            )
        except Exception as e:
            response_time = (datetime.utcnow() - start).total_seconds() * 1000
            logger.error("database_health_check_failed", error=str(e))
            return DependencyStatus(
                name="database",
                status="unhealthy",
                response_time=response_time,
                message=f"Database connection failed: {str(e)}",
            )

    async def check_redis(self) -> DependencyStatus:
        """Check Redis connectivity"""
        start = datetime.utcnow()
        try:
            from src.redis_client import get_redis

            redis = await get_redis()
            await redis.ping()

            response_time = (datetime.utcnow() - start).total_seconds() * 1000
            return DependencyStatus(
                name="redis",
                status="healthy",
                response_time=response_time,
                message="Redis connection successful",
            )
        except Exception as e:
            response_time = (datetime.utcnow() - start).total_seconds() * 1000
            logger.error("redis_health_check_failed", error=str(e))
            return DependencyStatus(
                name="redis",
                status="unhealthy",
                response_time=response_time,
                message=f"Redis connection failed: {str(e)}",
            )

    async def check_external_service(
        self, name: str, url: str, timeout: float = 5.0
    ) -> DependencyStatus:
        """Check external service health"""
        start = datetime.utcnow()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url)
                response.raise_for_status()

            response_time = (datetime.utcnow() - start).total_seconds() * 1000
            return DependencyStatus(
                name=name,
                status="healthy",
                response_time=response_time,
                message=f"Service responding (HTTP {response.status_code})",
            )
        except httpx.TimeoutException:
            response_time = (datetime.utcnow() - start).total_seconds() * 1000
            logger.warning("external_service_timeout", service=name, url=url)
            return DependencyStatus(
                name=name,
                status="degraded",
                response_time=response_time,
                message=f"Service timeout after {timeout}s",
            )
        except Exception as e:
            response_time = (datetime.utcnow() - start).total_seconds() * 1000
            logger.error("external_service_check_failed", service=name, url=url, error=str(e))
            return DependencyStatus(
                name=name,
                status="unhealthy",
                response_time=response_time,
                message=f"Service check failed: {str(e)}",
            )

    async def check_all_dependencies(self) -> Dict[str, DependencyStatus]:
        """Check all dependencies in parallel"""
        checks = await asyncio.gather(
            self.check_database(),
            self.check_redis(),
            # Add more dependency checks as needed
            return_exceptions=True,
        )

        result = {}
        for check in checks:
            if isinstance(check, DependencyStatus):
                result[check.name] = check
            elif isinstance(check, Exception):
                logger.error("dependency_check_exception", error=str(check))

        return result

    def determine_overall_status(self, dependencies: Dict[str, DependencyStatus]) -> str:
        """Determine overall health status from dependencies"""
        if not dependencies:
            return "healthy"

        statuses = [dep.status for dep in dependencies.values()]

        if "unhealthy" in statuses:
            # If any critical dependency is unhealthy, service is unhealthy
            return "unhealthy"
        elif "degraded" in statuses:
            # If any dependency is degraded, service is degraded
            return "degraded"
        else:
            return "healthy"


# ============================================================================
# Global health checker instance
# ============================================================================

health_checker = HealthChecker()


# ============================================================================
# Health Check Endpoints
# ============================================================================


@router.get("/", response_model=HealthStatus, status_code=status.HTTP_200_OK)
async def health_check() -> HealthStatus:
    """
    Basic health check endpoint

    Returns:
        HealthStatus: Basic health information

    This endpoint should always return 200 if the service is running.
    Use for basic liveness probes.
    """
    return HealthStatus(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        service="maestro-engine",
        uptime=health_checker.get_uptime(),
    )


@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness_probe() -> Dict[str, str]:
    """
    Kubernetes liveness probe

    Returns:
        Simple response indicating service is alive

    This endpoint checks if the service process is running.
    If this fails, Kubernetes will restart the pod.
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/ready", response_model=DetailedHealthStatus)
async def readiness_probe(response: Response) -> DetailedHealthStatus:
    """
    Kubernetes readiness probe with dependency checks

    Returns:
        DetailedHealthStatus: Health status with dependency information

    This endpoint checks if the service is ready to accept traffic.
    If dependencies are unhealthy, returns 503.
    """
    # Check all dependencies
    dependencies = await health_checker.check_all_dependencies()

    # Determine overall status
    overall_status = health_checker.determine_overall_status(dependencies)

    # Set appropriate HTTP status code
    if overall_status == "unhealthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif overall_status == "degraded":
        response.status_code = status.HTTP_200_OK  # Still accept traffic but log warnings

    return DetailedHealthStatus(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        service="maestro-engine",
        uptime=health_checker.get_uptime(),
        dependencies=dependencies,
        checks={
            "database": dependencies.get(
                "database", DependencyStatus(name="database", status="unknown")
            ).status
            == "healthy",
            "redis": dependencies.get(
                "redis", DependencyStatus(name="redis", status="unknown")
            ).status
            == "healthy",
        },
    )


@router.get("/startup", status_code=status.HTTP_200_OK)
async def startup_probe() -> Dict[str, Any]:
    """
    Kubernetes startup probe

    Returns:
        Startup status information

    This endpoint checks if the service has completed startup.
    Used for slow-starting applications.
    """
    # Check if all critical dependencies are available
    dependencies = await health_checker.check_all_dependencies()

    all_healthy = all(dep.status == "healthy" for dep in dependencies.values())

    return {
        "status": "ready" if all_healthy else "starting",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": health_checker.get_uptime(),
        "dependencies_ready": all_healthy,
    }


@router.get("/detailed", response_model=DetailedHealthStatus)
async def detailed_health_check() -> DetailedHealthStatus:
    """
    Detailed health check with all dependency information

    Returns:
        DetailedHealthStatus: Comprehensive health information

    Use for monitoring dashboards and debugging.
    Always returns 200 even if dependencies are unhealthy.
    """
    dependencies = await health_checker.check_all_dependencies()
    overall_status = health_checker.determine_overall_status(dependencies)

    return DetailedHealthStatus(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        service="maestro-engine",
        uptime=health_checker.get_uptime(),
        dependencies=dependencies,
        checks={dep_name: dep.status == "healthy" for dep_name, dep in dependencies.items()},
    )


# ============================================================================
# Metrics Endpoint (Prometheus format)
# ============================================================================


@router.get("/metrics/health", include_in_schema=False)
async def health_metrics() -> Response:
    """
    Health metrics in Prometheus format

    Returns:
        Plain text metrics for Prometheus scraping
    """
    dependencies = await health_checker.check_all_dependencies()

    metrics = []

    # Service uptime
    metrics.append(
        f'service_uptime_seconds{{service="maestro-engine"}} {health_checker.get_uptime()}'
    )

    # Dependency status (1 = healthy, 0.5 = degraded, 0 = unhealthy)
    for name, dep in dependencies.items():
        status_value = {"healthy": 1.0, "degraded": 0.5, "unhealthy": 0.0}.get(dep.status, 0.0)

        metrics.append(
            f'dependency_health{{service="maestro-engine",dependency="{name}"}} {status_value}'
        )

        if dep.response_time is not None:
            metrics.append(
                f'dependency_response_time_ms{{service="maestro-engine",dependency="{name}"}} {dep.response_time}'
            )

    return Response(content="\n".join(metrics), media_type="text/plain")
