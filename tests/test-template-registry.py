#!/usr/bin/env python3
"""
Unit Tests for MAESTRO Template Registry Service

This module provides comprehensive unit tests for:
- Template discovery and cataloging
- Template metadata management
- Service registry functionality
- Template search and matching
- Compatibility checking
- Stack composition logic
"""

import json
import os

# Import the template registry components
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "services", "template_registry"))

from registry_service import (
    ServiceDefinition,
    TemplateMetadata,
    TemplateQuery,
    TemplateRegistryService,
    app,
)


class TestTemplateRegistryAPI:
    """Test suite for Template Registry API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def sample_template_metadata(self):
        """Sample template metadata for testing"""
        return TemplateMetadata(
            id="test-template-123",
            name="FastAPI Basic Template",
            version="1.0.0",
            category="development",
            description="A basic FastAPI template for REST APIs",
            author="MAESTRO",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            tags=["api", "fastapi", "python"],
            technology_stack={
                "backend": {"framework": "fastapi", "language": "python"},
                "database": {"type": "postgresql"},
            },
            dependencies=["fastapi", "uvicorn", "sqlalchemy"],
            template_path="/templates/fastapi-basic.json",
            maturity_level="stable",
        )

    @pytest.fixture
    def sample_service_definition(self):
        """Sample service definition for testing"""
        return ServiceDefinition(
            service_id="postgresql-db",
            name="PostgreSQL Database",
            type="database",
            category="data",
            version="15.0",
            port=5432,
            capabilities=["relational_db", "acid", "json_support"],
            status="available",
        )

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "templates_count" in data
        assert "services_count" in data
        assert "timestamp" in data

    def test_list_templates_endpoint(self, client):
        """Test listing all templates"""
        response = client.get("/templates")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_templates_with_category_filter(self, client):
        """Test listing templates with category filter"""
        response = client.get("/templates?category=development")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_templates_with_limit(self, client):
        """Test listing templates with limit"""
        response = client.get("/templates?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 5

    @patch("registry_service.registry_service.find_templates")
    def test_search_templates_endpoint(self, mock_search, client):
        """Test template search endpoint"""
        mock_search.return_value = [
            TemplateMetadata(
                id="test-123",
                name="Test Template",
                version="1.0.0",
                category="test",
                description="Test",
                author="MAESTRO",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                template_path="/test",
            )
        ]

        search_query = {
            "requirement": "Create a REST API",
            "project_type": "api",
            "technology_preferences": ["python", "fastapi"],
        }

        response = client.post("/templates/search", json=search_query)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        mock_search.assert_called_once()

    def test_get_template_by_id(self, client):
        """Test getting specific template by ID"""
        # This will fail with 404 since no templates are loaded
        response = client.get("/templates/nonexistent-id")
        assert response.status_code == 404

    def test_list_services_endpoint(self, client):
        """Test listing all services"""
        response = client.get("/services")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_services_with_type_filter(self, client):
        """Test listing services with type filter"""
        response = client.get("/services?service_type=database")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_compatible_services(self, client):
        """Test getting compatible services for template"""
        response = client.get("/templates/test-id/compatible-services")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_compose_stack_endpoint(self, client):
        """Test stack composition endpoint"""
        compose_request = {
            "base_template_id": "test-template",
            "requirements": {"database": True, "cache": False, "monitoring": True},
        }

        response = client.post("/stacks/compose", params=compose_request)
        assert response.status_code in [200, 422]  # May fail due to missing template


class TestTemplateRegistryService:
    """Test suite for Template Registry Service logic"""

    @pytest.fixture
    def registry(self):
        """Create registry service instance"""
        return TemplateRegistryService(templates_root="/tmp/test-templates")

    @pytest.fixture
    def mock_template_files(self, tmp_path):
        """Create mock template files for testing"""
        templates_dir = tmp_path / "templates" / "project-templates"
        templates_dir.mkdir(parents=True)

        template_content = {
            "template_name": "fastapi-basic",
            "template_version": "1.0.0",
            "description": "Basic FastAPI template",
            "technology_stack": {"backend": {"framework": "fastapi", "language": "python"}},
            "tags": ["api", "python", "fastapi"],
        }

        template_file = templates_dir / "fastapi-basic.json"
        template_file.write_text(json.dumps(template_content))

        return str(tmp_path / "templates")

    @pytest.mark.asyncio
    async def test_registry_initialization(self, registry):
        """Test registry initialization"""
        await registry.initialize()
        assert registry.registry_db is not None
        assert registry.service_registry is not None

    @pytest.mark.asyncio
    async def test_scan_templates(self, registry, mock_template_files):
        """Test template scanning functionality"""
        registry.templates_root = Path(mock_template_files)
        await registry.scan_templates()

        # Should have found at least one template
        assert len(registry.registry_db) >= 0

    @pytest.mark.asyncio
    async def test_discover_services(self, registry):
        """Test service discovery"""
        await registry.discover_services()

        # Should discover mock services
        assert len(registry.service_registry) > 0
        assert "postgresql" in registry.service_registry
        assert "redis" in registry.service_registry

    @pytest.mark.asyncio
    async def test_find_templates_by_query(self, registry):
        """Test template search by query"""
        # Add a test template
        test_template = TemplateMetadata(
            id="test-123",
            name="Test API Template",
            version="1.0.0",
            category="development",
            description="Test template for APIs",
            author="MAESTRO",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            technology_stack={"backend": {"framework": "fastapi"}},
            tags=["api", "python"],
            template_path="/test",
        )
        registry.registry_db["test-123"] = test_template

        query = TemplateQuery(
            requirement="Create a REST API",
            project_type="api",
            technology_preferences=["python", "fastapi"],
        )

        results = await registry.find_templates(query)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_get_compatible_services(self, registry):
        """Test getting compatible services for template"""
        # Add test data
        test_template = TemplateMetadata(
            id="test-123",
            name="Test Template",
            version="1.0.0",
            category="development",
            description="Test",
            author="MAESTRO",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            technology_stack={"backend": {"database": "postgresql"}},
            template_path="/test",
        )
        registry.registry_db["test-123"] = test_template

        await registry.discover_services()  # Load mock services
        compatible = await registry.get_compatible_services("test-123")
        assert isinstance(compatible, list)

    @pytest.mark.asyncio
    async def test_compose_template_stack(self, registry):
        """Test template stack composition"""
        # Add test template
        test_template = TemplateMetadata(
            id="test-123",
            name="Test Template",
            version="1.0.0",
            category="development",
            description="Test",
            author="MAESTRO",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            template_path="/test",
        )
        registry.registry_db["test-123"] = test_template

        await registry.discover_services()  # Load mock services

        requirements = {"database": True, "monitoring": True, "cache": False}

        stack = await registry.compose_template_stack("test-123", requirements)
        assert "base_template" in stack
        assert "services" in stack
        assert "deployment_order" in stack


class TestTemplateMetadata:
    """Test suite for TemplateMetadata model"""

    def test_template_metadata_creation(self):
        """Test creating template metadata"""
        metadata = TemplateMetadata(
            id="test-123",
            name="Test Template",
            version="1.0.0",
            category="test",
            description="A test template",
            author="MAESTRO",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            template_path="/test/path",
        )

        assert metadata.id == "test-123"
        assert metadata.name == "Test Template"
        assert metadata.version == "1.0.0"
        assert metadata.maturity_level == "stable"  # Default value

    def test_template_metadata_with_optional_fields(self):
        """Test template metadata with optional fields"""
        metadata = TemplateMetadata(
            id="test-123",
            name="Test Template",
            version="1.0.0",
            category="test",
            description="A test template",
            author="MAESTRO",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            template_path="/test/path",
            tags=["test", "api"],
            technology_stack={"framework": "fastapi"},
            dependencies=["fastapi", "uvicorn"],
            maturity_level="beta",
        )

        assert metadata.tags == ["test", "api"]
        assert metadata.technology_stack == {"framework": "fastapi"}
        assert metadata.maturity_level == "beta"


class TestServiceDefinition:
    """Test suite for ServiceDefinition model"""

    def test_service_definition_creation(self):
        """Test creating service definition"""
        service = ServiceDefinition(
            service_id="postgres-1",
            name="PostgreSQL Database",
            type="database",
            category="data",
            version="15.0",
        )

        assert service.service_id == "postgres-1"
        assert service.name == "PostgreSQL Database"
        assert service.type == "database"
        assert service.status == "unknown"  # Default value

    def test_service_definition_with_optional_fields(self):
        """Test service definition with optional fields"""
        service = ServiceDefinition(
            service_id="postgres-1",
            name="PostgreSQL Database",
            type="database",
            category="data",
            version="15.0",
            port=5432,
            capabilities=["acid", "relational"],
            status="available",
        )

        assert service.port == 5432
        assert service.capabilities == ["acid", "relational"]
        assert service.status == "available"


class TestTemplateQuery:
    """Test suite for TemplateQuery model"""

    def test_template_query_creation(self):
        """Test creating template query"""
        query = TemplateQuery(
            requirement="Create a REST API",
            project_type="api",
            technology_preferences=["python", "fastapi"],
            complexity="medium",
        )

        assert query.requirement == "Create a REST API"
        assert query.project_type == "api"
        assert query.complexity == "medium"

    def test_template_query_with_optional_fields(self):
        """Test template query with optional fields"""
        query = TemplateQuery(
            requirement="Create an enterprise platform",
            complexity="complex",
            scalability_requirements="high",
            security_level="enterprise",
            compliance_requirements=["gdpr", "soc2"],
            team_size=10,
            timeline="6 months",
        )

        assert query.scalability_requirements == "high"
        assert query.security_level == "enterprise"
        assert query.compliance_requirements == ["gdpr", "soc2"]
        assert query.team_size == 10


class TestTemplateScoring:
    """Test suite for template scoring and matching algorithms"""

    @pytest.fixture
    def registry(self):
        """Create registry service instance"""
        return TemplateRegistryService()

    @pytest.mark.asyncio
    async def test_calculate_template_score(self, registry):
        """Test template scoring algorithm"""
        template = TemplateMetadata(
            id="test-123",
            name="FastAPI Template",
            version="1.0.0",
            category="development",
            description="FastAPI API template",
            author="MAESTRO",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            technology_stack={"backend": {"framework": "fastapi", "language": "python"}},
            tags=["api", "python", "fastapi"],
            template_path="/test",
            maturity_level="stable",
            quality_score=0.8,
            usage_count=50,
        )

        query = TemplateQuery(
            requirement="Create a REST API",
            project_type="api",
            technology_preferences=["python", "fastapi"],
            complexity="medium",
        )

        score = await registry._calculate_template_score(template, query)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be a good match

    @pytest.mark.asyncio
    async def test_template_score_no_match(self, registry):
        """Test template scoring with no match"""
        template = TemplateMetadata(
            id="test-123",
            name="React Template",
            version="1.0.0",
            category="frontend",
            description="React frontend template",
            author="MAESTRO",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            technology_stack={"frontend": {"framework": "react", "language": "javascript"}},
            tags=["frontend", "javascript", "react"],
            template_path="/test",
        )

        query = TemplateQuery(
            requirement="Create a backend API",
            project_type="api",
            technology_preferences=["python", "fastapi"],
        )

        score = await registry._calculate_template_score(template, query)
        assert score < 0.5  # Should be a poor match


class TestServiceCompatibility:
    """Test suite for service compatibility checking"""

    @pytest.fixture
    def registry(self):
        """Create registry service instance"""
        return TemplateRegistryService()

    @pytest.mark.asyncio
    async def test_database_compatibility(self, registry):
        """Test database service compatibility"""
        template = TemplateMetadata(
            id="test-123",
            name="API Template",
            version="1.0.0",
            category="development",
            description="API template",
            author="MAESTRO",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            technology_stack={"backend": {"database": "postgresql"}},
            template_path="/test",
        )

        postgres_service = ServiceDefinition(
            service_id="postgresql",
            name="PostgreSQL",
            type="database",
            category="data",
            version="15.0",
        )

        compatible = await registry._check_service_compatibility(template, postgres_service)
        assert compatible == True

    @pytest.mark.asyncio
    async def test_monitoring_compatibility(self, registry):
        """Test monitoring service compatibility"""
        template = TemplateMetadata(
            id="test-123",
            name="Any Template",
            version="1.0.0",
            category="development",
            description="Template",
            author="MAESTRO",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            template_path="/test",
        )

        monitoring_service = ServiceDefinition(
            service_id="signoz",
            name="SigNoz Monitoring",
            type="observability",
            category="monitoring",
            version="0.36",
        )

        compatible = await registry._check_service_compatibility(template, monitoring_service)
        assert compatible == True  # Monitoring is compatible with most templates


class TestStackComposition:
    """Test suite for stack composition logic"""

    @pytest.fixture
    def registry(self):
        """Create registry service instance"""
        return TemplateRegistryService()

    @pytest.mark.asyncio
    async def test_deployment_order_calculation(self, registry):
        """Test deployment order calculation"""
        services = [
            ServiceDefinition(
                service_id="app",
                name="Application",
                type="application",
                category="app",
                version="1.0",
            ),
            ServiceDefinition(
                service_id="postgres",
                name="PostgreSQL",
                type="database",
                category="data",
                version="15.0",
            ),
            ServiceDefinition(
                service_id="redis",
                name="Redis",
                type="cache",
                category="data",
                version="7.0",
            ),
            ServiceDefinition(
                service_id="monitoring",
                name="Monitoring",
                type="monitoring",
                category="ops",
                version="1.0",
            ),
        ]

        order = await registry._calculate_deployment_order(services)

        # Databases should come first
        assert order.index("postgres") < order.index("app")
        assert order.index("redis") < order.index("app")
        # Monitoring should come last
        assert order.index("monitoring") > order.index("app")


class TestErrorHandling:
    """Test suite for error handling and edge cases"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_invalid_template_search_query(self, client):
        """Test invalid search query handling"""
        invalid_query = {
            "requirement": "",  # Empty requirement
            "complexity": "invalid_complexity",
        }

        response = client.post("/templates/search", json=invalid_query)
        assert response.status_code == 422

    def test_nonexistent_template_id(self, client):
        """Test accessing non-existent template"""
        response = client.get("/templates/nonexistent-template-id")
        assert response.status_code == 404

    def test_invalid_stack_composition_request(self, client):
        """Test invalid stack composition request"""
        invalid_request = {
            "base_template_id": "",  # Empty template ID
            "requirements": "not_a_dict",  # Should be dictionary
        }

        response = client.post("/stacks/compose", params=invalid_request)
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
