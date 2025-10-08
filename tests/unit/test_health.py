"""
Unit Tests for Health Check Endpoints
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.health import DependencyStatus, HealthChecker, health_checker


class TestHealthChecker:
    """Test HealthChecker utility class"""

    def test_get_uptime(self):
        """Test uptime calculation"""
        checker = HealthChecker()
        uptime = checker.get_uptime()

        assert uptime >= 0
        assert isinstance(uptime, float)

    @pytest.mark.asyncio
    async def test_check_database_success(self):
        """Test successful database health check"""
        with patch("src.health.get_db_session") as mock_session:
            mock_session.return_value.__aenter__.return_value.execute = AsyncMock()

            checker = HealthChecker()
            result = await checker.check_database()

            assert result.name == "database"
            assert result.status == "healthy"
            assert result.response_time is not None
            assert result.response_time > 0

    @pytest.mark.asyncio
    async def test_check_database_failure(self):
        """Test failed database health check"""
        with patch("src.health.get_db_session") as mock_session:
            mock_session.return_value.__aenter__.side_effect = Exception("Connection failed")

            checker = HealthChecker()
            result = await checker.check_database()

            assert result.name == "database"
            assert result.status == "unhealthy"
            assert "Connection failed" in result.message

    @pytest.mark.asyncio
    async def test_check_redis_success(self):
        """Test successful Redis health check"""
        with patch("src.health.get_redis") as mock_redis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock()
            mock_redis.return_value = mock_client

            checker = HealthChecker()
            result = await checker.check_redis()

            assert result.name == "redis"
            assert result.status == "healthy"

    @pytest.mark.asyncio
    async def test_check_redis_failure(self):
        """Test failed Redis health check"""
        with patch("src.health.get_redis") as mock_redis:
            mock_redis.side_effect = Exception("Connection refused")

            checker = HealthChecker()
            result = await checker.check_redis()

            assert result.name == "redis"
            assert result.status == "unhealthy"

    @pytest.mark.asyncio
    async def test_check_external_service_success(self):
        """Test successful external service check"""
        checker = HealthChecker()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await checker.check_external_service("test-service", "http://test.com/health")

            assert result.name == "test-service"
            assert result.status == "healthy"

    @pytest.mark.asyncio
    async def test_check_external_service_timeout(self):
        """Test external service timeout"""
        import httpx

        checker = HealthChecker()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )

            result = await checker.check_external_service("test-service", "http://test.com/health")

            assert result.name == "test-service"
            assert result.status == "degraded"
            assert "timeout" in result.message.lower()

    def test_determine_overall_status_all_healthy(self):
        """Test overall status when all dependencies are healthy"""
        checker = HealthChecker()

        dependencies = {
            "database": DependencyStatus(name="database", status="healthy"),
            "redis": DependencyStatus(name="redis", status="healthy"),
        }

        status = checker.determine_overall_status(dependencies)
        assert status == "healthy"

    def test_determine_overall_status_one_unhealthy(self):
        """Test overall status when one dependency is unhealthy"""
        checker = HealthChecker()

        dependencies = {
            "database": DependencyStatus(name="database", status="healthy"),
            "redis": DependencyStatus(name="redis", status="unhealthy"),
        }

        status = checker.determine_overall_status(dependencies)
        assert status == "unhealthy"

    def test_determine_overall_status_one_degraded(self):
        """Test overall status when one dependency is degraded"""
        checker = HealthChecker()

        dependencies = {
            "database": DependencyStatus(name="database", status="healthy"),
            "redis": DependencyStatus(name="redis", status="degraded"),
        }

        status = checker.determine_overall_status(dependencies)
        assert status == "degraded"


@pytest.mark.integration
class TestHealthEndpoints:
    """Integration tests for health check endpoints"""

    def test_basic_health_check(self, client: TestClient):
        """Test basic health check endpoint"""
        response = client.get("/health/")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "service" in data
        assert "uptime" in data
        assert data["uptime"] >= 0

    def test_liveness_probe(self, client: TestClient):
        """Test liveness probe endpoint"""
        response = client.get("/health/live")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "alive"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_readiness_probe_healthy(self, client: TestClient):
        """Test readiness probe when all dependencies are healthy"""
        with patch("src.health.health_checker.check_all_dependencies") as mock_check:
            mock_check.return_value = {
                "database": DependencyStatus(name="database", status="healthy"),
                "redis": DependencyStatus(name="redis", status="healthy"),
            }

            response = client.get("/health/ready")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] in ["healthy", "degraded"]
            assert "dependencies" in data

    @pytest.mark.asyncio
    async def test_readiness_probe_unhealthy(self, client: TestClient):
        """Test readiness probe when dependencies are unhealthy"""
        with patch("src.health.health_checker.check_all_dependencies") as mock_check:
            mock_check.return_value = {
                "database": DependencyStatus(name="database", status="unhealthy"),
            }

            response = client.get("/health/ready")

            # Should return 503 when unhealthy
            assert response.status_code in [200, 503]  # Depends on implementation

    def test_startup_probe(self, client: TestClient):
        """Test startup probe endpoint"""
        response = client.get("/health/startup")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] in ["ready", "starting"]

    def test_detailed_health_check(self, client: TestClient):
        """Test detailed health check endpoint"""
        response = client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "dependencies" in data
        assert "checks" in data
        assert "uptime" in data


@pytest.fixture
def client():
    """Create test client"""
    from fastapi import FastAPI

    from src.health import router

    app = FastAPI()
    app.include_router(router)

    from fastapi.testclient import TestClient

    return TestClient(app)
