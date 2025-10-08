#!/usr/bin/env python3
"""
Enhanced Pytest configuration for MAESTRO Testing Framework
Provides comprehensive fixtures and modern testing patterns with industry-best tools.
"""
import asyncio
import os
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import structlog
from factory import Factory, Sequence, SubFactory
from faker import Faker
from testcontainers.compose import DockerCompose
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

# Configure structured logging for tests
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_blackboard():
    """Provide a mock digital blackboard for testing"""
    blackboard = MagicMock()
    blackboard.emit_signal = AsyncMock()
    blackboard.subscribe_observer = MagicMock()
    blackboard.unsubscribe_observer = MagicMock()
    blackboard.get_active_signals = AsyncMock(return_value=[])
    blackboard.get_signal_analytics = AsyncMock(
        return_value={
            "active_signals": 0,
            "total_observers": 0,
            "signal_type_distribution": {},
            "avg_response_rate_24h": 0.0,
        }
    )
    blackboard.start = AsyncMock()
    blackboard.stop = AsyncMock()
    blackboard.is_running = False
    return blackboard


@pytest.fixture
def sample_coordination_signal():
    """Provide a sample coordination signal for testing"""
    signal = MagicMock()
    signal.signal_id = "test_signal_001"
    signal.signal_type = MagicMock()
    signal.signal_type.value = "coordination_request"
    signal.priority = MagicMock()
    signal.priority.value = 3  # MEDIUM priority
    signal.title = "Test Coordination Signal"
    signal.description = "Test signal for unit testing"
    signal.data = {"test": "data", "confidence": "high"}
    signal.emitted_by = "test_emitter"
    signal.target_domains = ["test_domain"]
    signal.is_expired = MagicMock(return_value=False)
    signal.should_escalate = MagicMock(return_value=False)
    return signal


@pytest.fixture
def temp_test_directory():
    """Provide a temporary directory for test files"""
    temp_dir = tempfile.mkdtemp(prefix="maestro_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_persona_data():
    """Provide sample persona data for testing"""
    return {
        "persona_id": "test_persona",
        "name": "Test Persona",
        "role": "Testing and Validation",
        "capabilities": [
            "Unit testing",
            "Integration testing",
            "Test automation",
            "Quality assurance",
        ],
    }


# Phase 5 specific fixtures
@pytest.fixture
def sample_hive_data():
    """Sample hive data for Phase 5 testing"""
    return {
        "name": "test-integration-hive",
        "hive_type": "execution",
        "requirements": "Create a comprehensive test suite for Phase 5 integration",
        "configuration": {
            "test_mode": True,
            "integration_test": True,
            "created_by": "phase5_test_suite",
        },
        "priority": "high",
        "autonomous_mode": True,
        "max_recursion_depth": 3,
    }


@pytest.fixture
def sample_project_patterns():
    """Sample project patterns for testing"""
    return [
        {
            "pattern_id": "microservices-001",
            "name": "Microservices Architecture",
            "category": "architecture",
            "confidence": 0.95,
            "frequency": 234,
            "success_rate": 0.87,
            "complexity": "high",
        },
        {
            "pattern_id": "auth-002",
            "name": "JWT Authentication",
            "category": "security",
            "confidence": 0.92,
            "frequency": 456,
            "success_rate": 0.93,
            "complexity": "medium",
        },
    ]


@pytest.fixture
def mock_phase5_services():
    """Mock Phase 5 services for integration testing"""
    services = {
        "hive_orchestration": {
            "client": AsyncMock(),
            "base_url": "http://localhost:9600",
            "health_endpoint": "/health",
        },
        "stigmergy_engine": {
            "client": AsyncMock(),
            "base_url": "http://localhost:9601",
            "health_endpoint": "/health",
        },
    }

    # Configure default responses
    for service_name, service in services.items():
        # Health check response
        health_response = AsyncMock()
        health_response.status_code = 200
        health_response.json.return_value = {"status": "healthy", "service": service_name}
        service["client"].get.return_value = health_response

    return services


@pytest.fixture
def feature_flags_config():
    """Feature flags configuration for testing"""
    return {
        "autonomous_hives": True,
        "stigmergy_patterns": True,
        "cross_hive_communication": True,
        "pattern_learning": True,
        "recursive_spawning": True,
        "enterprise_features": True,
        "advanced_analytics": False,
        "experimental_features": False,
    }


@pytest.fixture
def uuid_factory():
    """Factory for generating predictable UUIDs"""
    import uuid

    counter = 0

    def generate(prefix="test"):
        nonlocal counter
        counter += 1
        base_uuid = f"00000000-0000-0000-0000-{counter:012d}"
        return str(uuid.UUID(base_uuid))

    return generate


# Pytest configuration
# ============================================================================
# MODERN TESTING INFRASTRUCTURE FIXTURES
# ============================================================================


@pytest.fixture(scope="session")
def faker_instance():
    """Provide Faker instance for generating test data"""
    fake = Faker()
    Faker.seed(42)  # Deterministic fake data for tests
    return fake


@pytest.fixture(scope="session")
def test_logger():
    """Provide structured logger for tests"""
    return structlog.get_logger("maestro.tests")


@pytest.fixture
def correlation_id():
    """Generate unique correlation ID for request tracking"""
    return f"test-{uuid.uuid4().hex[:8]}"


# ============================================================================
# CONTAINER-BASED TESTING FIXTURES
# ============================================================================


@pytest.fixture(scope="session")
def postgres_container():
    """Provide PostgreSQL container for integration tests"""
    with PostgresContainer("postgres:15-alpine") as postgres:
        postgres.start()
        yield postgres


@pytest.fixture(scope="session")
def redis_container():
    """Provide Redis container for integration tests"""
    with RedisContainer("redis:7-alpine") as redis:
        redis.start()
        yield redis


@pytest.fixture(scope="session")
def maestro_services_compose():
    """Provide Docker Compose environment for full integration tests"""
    # Only start if docker-compose.yml exists and INTEGRATION_TESTS env var is set
    if os.path.exists("docker-compose.yml") and os.getenv("INTEGRATION_TESTS"):
        with DockerCompose(".", compose_file_name="docker-compose.yml") as compose:
            compose.start()
            # Wait for services to be ready
            compose.wait_for("http://localhost:8000/health")
            yield compose
    else:
        yield None


# ============================================================================
# SERVICE REGISTRY AND API TESTING FIXTURES
# ============================================================================


@pytest.fixture
def service_registry_client():
    """Mock service registry client for testing"""
    mock_registry = MagicMock()
    mock_registry.register_service = AsyncMock(
        return_value={"service_id": "test-123", "status": "registered"}
    )
    mock_registry.discover_services = AsyncMock(
        return_value={
            "services": [
                {
                    "name": "intelligence-service",
                    "url": "http://localhost:9501",
                    "status": "healthy",
                },
                {"name": "template-registry", "url": "http://localhost:9500", "status": "healthy"},
                {"name": "sync-coordinator", "url": "http://localhost:9600", "status": "healthy"},
            ]
        }
    )
    mock_registry.health_check = AsyncMock(return_value={"status": "healthy", "services": 3})
    return mock_registry


@pytest.fixture
async def async_http_client():
    """Provide async HTTP client for API testing"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


@pytest.fixture
def maestro_service_urls():
    """Provide service URLs for testing"""
    return {
        "orchestration_gateway": os.getenv("ORCHESTRATION_GATEWAY_URL", "http://localhost:8000"),
        "sync_coordinator": os.getenv("SYNC_COORDINATOR_URL", "http://localhost:9600"),
        "intelligence_service": os.getenv("INTELLIGENCE_SERVICE_URL", "http://localhost:9501"),
        "template_registry": os.getenv("TEMPLATE_REGISTRY_URL", "http://localhost:9500"),
        "config_management": os.getenv("CONFIG_MANAGEMENT_URL", "http://localhost:9700"),
        "quality_service": os.getenv("QUALITY_SERVICE_URL", "http://localhost:9503"),
    }


@pytest.fixture
def api_headers():
    """Provide standard API headers for testing"""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Test-Mode": "true",
        "X-API-Version": "v1",
    }


# ============================================================================
# DATA FACTORIES AND GENERATORS
# ============================================================================


class ServiceConfigFactory(Factory):
    """Factory for generating service configurations"""

    class Meta:
        model = dict

    service_name = Sequence(lambda n: f"test-service-{n}")
    port = Sequence(lambda n: 9000 + n)
    environment = "test"
    health_endpoint = "/health"
    capabilities = ["testing", "validation"]


class OrchestrationRequestFactory(Factory):
    """Factory for generating orchestration requests"""

    class Meta:
        model = dict

    requirement = Sequence(lambda n: f"Build test application #{n}")
    project_type = "web_application"
    complexity = "simple"
    features = ["authentication", "database"]
    priority = "medium"


@pytest.fixture
def service_config_factory():
    """Provide service configuration factory"""
    return ServiceConfigFactory


@pytest.fixture
def orchestration_request_factory():
    """Provide orchestration request factory"""
    return OrchestrationRequestFactory


# ============================================================================
# CONTRACT TESTING FIXTURES
# ============================================================================


@pytest.fixture
def pact_consumer():
    """Provide Pact consumer for contract testing"""
    from pact import Consumer, Provider

    consumer = Consumer("maestro-test-consumer")
    provider = Provider("maestro-services")

    return consumer.has_pact_with(provider)


@pytest.fixture
def openapi_spec_validator():
    """Provide OpenAPI spec validator"""
    from openapi_spec_validator import validate_spec

    def validator(spec_dict):
        """Validate OpenAPI specification"""
        try:
            validate_spec(spec_dict)
            return True, None
        except Exception as e:
            return False, str(e)

    return validator


# ============================================================================
# PROPERTY-BASED TESTING FIXTURES
# ============================================================================


@pytest.fixture
def hypothesis_settings():
    """Configure Hypothesis for property-based testing"""
    from hypothesis import Verbosity, settings

    return settings(
        max_examples=100,
        verbosity=Verbosity.verbose,
        deadline=None,  # No deadline for complex operations
        suppress_health_check=[],
    )


# ============================================================================
# PERFORMANCE AND LOAD TESTING FIXTURES
# ============================================================================


@pytest.fixture
def performance_metrics_collector():
    """Collect performance metrics during tests"""
    import threading
    import time

    import psutil

    class MetricsCollector:
        def __init__(self):
            self.metrics = []
            self.running = False
            self.thread = None

        def start(self):
            self.running = True
            self.thread = threading.Thread(target=self._collect)
            self.thread.start()

        def stop(self):
            self.running = False
            if self.thread:
                self.thread.join()
            return self.metrics

        def _collect(self):
            while self.running:
                self.metrics.append(
                    {
                        "timestamp": time.time(),
                        "cpu_percent": psutil.cpu_percent(),
                        "memory_percent": psutil.virtual_memory().percent,
                        "disk_io": (
                            psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else {}
                        ),
                        "network_io": (
                            psutil.net_io_counters()._asdict() if psutil.net_io_counters() else {}
                        ),
                    }
                )
                time.sleep(0.1)

    return MetricsCollector()


# ============================================================================
# CHAOS ENGINEERING FIXTURES
# ============================================================================


@pytest.fixture
def chaos_toolkit():
    """Provide chaos engineering toolkit for resilience testing"""
    from unittest.mock import MagicMock

    # Mock chaos toolkit for testing purposes
    toolkit = MagicMock()
    toolkit.inject_network_delay = MagicMock()
    toolkit.inject_service_failure = MagicMock()
    toolkit.inject_cpu_stress = MagicMock()
    toolkit.inject_memory_stress = MagicMock()

    return toolkit


# ============================================================================
# SECURITY TESTING FIXTURES
# ============================================================================


@pytest.fixture
def security_scanner():
    """Provide security scanning utilities"""

    class SecurityScanner:
        @staticmethod
        def scan_sql_injection(endpoint, payload):
            """Mock SQL injection testing"""
            suspicious_patterns = ["'", "UNION", "DROP", "DELETE"]
            return any(pattern in payload.upper() for pattern in suspicious_patterns)

        @staticmethod
        def scan_xss(endpoint, payload):
            """Mock XSS testing"""
            xss_patterns = ["<script>", "javascript:", "onload="]
            return any(pattern in payload.lower() for pattern in xss_patterns)

        @staticmethod
        def check_auth_bypass(endpoint, headers):
            """Mock authentication bypass testing"""
            # Check for missing or weak authentication
            return (
                "Authorization" not in headers
                or headers.get("Authorization") == "Bearer weak-token"
            )

    return SecurityScanner()


# ============================================================================
# VISUAL TESTING FIXTURES (for utilities with web interfaces)
# ============================================================================


@pytest.fixture
def visual_testing_setup():
    """Setup for visual regression testing"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    def get_driver():
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        return webdriver.Chrome(options=chrome_options)

    return get_driver


# ============================================================================
# PYTEST CONFIGURATION AND HOOKS
# ============================================================================


def pytest_configure(config):
    """Configure pytest with enhanced markers and settings"""
    # Core test categories
    config.addinivalue_line("markers", "unit: Unit tests for individual components")
    config.addinivalue_line("markers", "integration: Integration tests for service communication")
    config.addinivalue_line("markers", "e2e: End-to-end tests for complete workflows")
    config.addinivalue_line("markers", "contract: Contract testing for API compatibility")
    config.addinivalue_line("markers", "performance: Performance and load tests")
    config.addinivalue_line(
        "markers", "security: Security testing including vulnerability scanning"
    )
    config.addinivalue_line("markers", "chaos: Chaos engineering tests for resilience")

    # Infrastructure markers
    config.addinivalue_line("markers", "requires_docker: Tests requiring Docker containers")
    config.addinivalue_line("markers", "requires_k8s: Tests requiring Kubernetes cluster")
    config.addinivalue_line("markers", "requires_network: Tests requiring network connectivity")

    # Service-specific markers
    config.addinivalue_line("markers", "config_management: Config management service tests")
    config.addinivalue_line("markers", "orchestration_gateway: Orchestration gateway tests")
    config.addinivalue_line("markers", "utilities: Utilities service tests")

    # Advanced testing markers
    config.addinivalue_line("markers", "property_based: Property-based testing with Hypothesis")
    config.addinivalue_line("markers", "mutation: Mutation testing")
    config.addinivalue_line("markers", "visual_testing: Visual regression testing")
    config.addinivalue_line("markers", "load_testing: Load and stress testing")


def pytest_collection_modifyitems(config, items):
    """Modify test collection for better organization"""
    for item in items:
        # Auto-mark slow tests based on name patterns
        if "slow" in item.name or "load" in item.name or "stress" in item.name:
            item.add_marker(pytest.mark.slow)

        # Auto-mark integration tests
        if "integration" in str(item.fspath) or "test_integration" in item.name:
            item.add_marker(pytest.mark.integration)

        # Auto-mark service-specific tests based on path
        if "config_management" in str(item.fspath):
            item.add_marker(pytest.mark.config_management)
        elif "orchestration_gateway" in str(item.fspath):
            item.add_marker(pytest.mark.orchestration_gateway)


@pytest.fixture(autouse=True)
def test_environment_setup(test_logger):
    """Automatically setup test environment for all tests"""
    test_logger.info("Starting test", test_name=os.environ.get("PYTEST_CURRENT_TEST", "unknown"))

    # Set test environment variables
    os.environ["TESTING"] = "true"
    os.environ["LOG_LEVEL"] = "DEBUG"

    yield

    test_logger.info("Completed test")


# ============================================================================
# LEGACY FIXTURES (maintained for compatibility)
# ============================================================================
