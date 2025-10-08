#!/usr/bin/env python3
"""
Test Fixtures for MAESTRO Persona Testing
Provides comprehensive test data, mocks, and utilities for persona testing
"""

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest


class PersonaTestFixtures:
    """Comprehensive test fixtures for persona testing"""

    @staticmethod
    def create_sample_requirements() -> Dict[str, Any]:
        """Create comprehensive sample requirements for testing"""
        return {
            "simple_web_app": {
                "original_requirement": "Create a simple web application for user registration",
                "functional_requirements": [
                    {"requirement": "User registration with email and password"},
                    {"requirement": "User login functionality"},
                    {"requirement": "Basic user profile page"},
                ],
                "non_functional_requirements": [
                    {"requirement": "Responsive design"},
                    {"requirement": "Fast page load times"},
                ],
                "complexity_level": "low",
                "estimated_effort": "2-3 weeks",
            },
            "e_commerce_platform": {
                "original_requirement": "Build a comprehensive e-commerce platform",
                "functional_requirements": [
                    {"requirement": "Product catalog management"},
                    {"requirement": "Shopping cart functionality"},
                    {"requirement": "Payment processing integration"},
                    {"requirement": "Order management system"},
                    {"requirement": "User authentication and authorization"},
                    {"requirement": "Admin dashboard for product management"},
                    {"requirement": "Email notifications for orders"},
                    {"requirement": "Inventory tracking"},
                ],
                "non_functional_requirements": [
                    {"requirement": "High availability (99.9% uptime)"},
                    {"requirement": "Support for 10,000 concurrent users"},
                    {"requirement": "PCI DSS compliance for payment processing"},
                    {"requirement": "Response time under 2 seconds"},
                    {"requirement": "Mobile-responsive design"},
                ],
                "complexity_level": "high",
                "estimated_effort": "6-8 months",
            },
            "api_microservice": {
                "original_requirement": "Develop a REST API for task management",
                "functional_requirements": [
                    {"requirement": "CRUD operations for tasks"},
                    {"requirement": "Task assignment to users"},
                    {"requirement": "Task status tracking"},
                    {"requirement": "Due date management"},
                    {"requirement": "Task filtering and search"},
                ],
                "non_functional_requirements": [
                    {"requirement": "API rate limiting"},
                    {"requirement": "JWT authentication"},
                    {"requirement": "API documentation with Swagger"},
                    {"requirement": "Monitoring and logging"},
                ],
                "complexity_level": "medium",
                "estimated_effort": "4-6 weeks",
            },
            "real_time_chat": {
                "original_requirement": "Create a real-time chat application",
                "functional_requirements": [
                    {"requirement": "Real-time messaging between users"},
                    {"requirement": "Chat room creation and management"},
                    {"requirement": "Message history and search"},
                    {"requirement": "File sharing capabilities"},
                    {"requirement": "User presence indicators"},
                    {"requirement": "Push notifications"},
                ],
                "non_functional_requirements": [
                    {"requirement": "Low latency messaging (< 100ms)"},
                    {"requirement": "Scalable to 1000+ concurrent connections"},
                    {"requirement": "Message encryption"},
                    {"requirement": "Cross-platform compatibility"},
                ],
                "complexity_level": "high",
                "estimated_effort": "3-4 months",
            },
        }

    @staticmethod
    def create_sample_architectures() -> Dict[str, Any]:
        """Create sample architecture configurations"""
        return {
            "microservices_architecture": {
                "architecture_style": "Microservices",
                "technology_stack": {
                    "backend": "FastAPI",
                    "database": "PostgreSQL",
                    "cache": "Redis",
                    "message_queue": "RabbitMQ",
                    "api_gateway": "Kong",
                },
                "services": ["user-service", "product-service", "order-service", "payment-service"],
                "deployment": {
                    "containerization": "Docker",
                    "orchestration": "Kubernetes",
                    "monitoring": "Prometheus + Grafana",
                },
            },
            "monolithic_architecture": {
                "architecture_style": "Monolithic",
                "technology_stack": {
                    "backend": "Django",
                    "database": "PostgreSQL",
                    "cache": "Redis",
                    "frontend": "React",
                },
                "components": [
                    "authentication_module",
                    "user_management",
                    "business_logic",
                    "api_layer",
                ],
                "deployment": {
                    "containerization": "Docker",
                    "orchestration": "Docker Compose",
                    "monitoring": "Basic logging",
                },
            },
            "serverless_architecture": {
                "architecture_style": "Serverless",
                "technology_stack": {
                    "functions": "AWS Lambda",
                    "database": "DynamoDB",
                    "api_gateway": "AWS API Gateway",
                    "storage": "S3",
                },
                "functions": [
                    "user_registration",
                    "user_authentication",
                    "data_processing",
                    "notification_service",
                ],
                "deployment": {"platform": "AWS", "iac": "Terraform", "monitoring": "CloudWatch"},
            },
        }

    @staticmethod
    def create_mock_persona_configs() -> Dict[str, Dict[str, Any]]:
        """Create comprehensive mock persona configurations"""
        return {
            "backend_developer": {
                "persona_metadata": {
                    "persona_name": "Senior Backend Developer",
                    "persona_id": "backend_developer_001",
                    "specialization": "Backend Development",
                    "experience_level": 8,
                    "autonomy_level": 9,
                    "description": "Expert backend developer specializing in scalable server-side solutions",
                },
                "capabilities": [
                    "api_development",
                    "database_design",
                    "microservices_architecture",
                    "authentication_systems",
                    "performance_optimization",
                    "security_implementation",
                    "cloud_integration",
                ],
                "specializations": [
                    "rest_api_design",
                    "graphql_implementation",
                    "database_optimization",
                    "caching_strategies",
                    "message_queues",
                    "container_orchestration",
                ],
                "technology_preferences": {
                    "languages": ["Python", "Node.js", "Go"],
                    "frameworks": ["FastAPI", "Express", "Gin"],
                    "databases": ["PostgreSQL", "MongoDB", "Redis"],
                    "tools": ["Docker", "Kubernetes", "RabbitMQ"],
                },
            },
            "frontend_developer": {
                "persona_metadata": {
                    "persona_name": "Senior Frontend Developer",
                    "persona_id": "frontend_developer_001",
                    "specialization": "Frontend Development",
                    "experience_level": 7,
                    "autonomy_level": 8,
                },
                "capabilities": [
                    "ui_development",
                    "state_management",
                    "responsive_design",
                    "performance_optimization",
                    "accessibility",
                    "testing",
                ],
                "specializations": [
                    "react",
                    "vue",
                    "angular",
                    "typescript",
                    "css_animations",
                    "pwa_development",
                ],
                "technology_preferences": {
                    "frameworks": ["React", "Vue.js", "Angular"],
                    "styling": ["CSS3", "SCSS", "Styled Components"],
                    "build_tools": ["Webpack", "Vite", "Parcel"],
                    "testing": ["Jest", "Cypress", "Testing Library"],
                },
            },
            "devops_engineer": {
                "persona_metadata": {
                    "persona_name": "Senior DevOps Engineer",
                    "persona_id": "devops_engineer_001",
                    "specialization": "DevOps and Infrastructure",
                    "experience_level": 9,
                    "autonomy_level": 9,
                },
                "capabilities": [
                    "infrastructure_automation",
                    "ci_cd_pipelines",
                    "monitoring_setup",
                    "security_hardening",
                    "disaster_recovery",
                    "cost_optimization",
                ],
                "specializations": [
                    "kubernetes",
                    "terraform",
                    "ansible",
                    "jenkins",
                    "prometheus",
                    "elasticsearch",
                ],
                "cloud_platforms": ["AWS", "Azure", "GCP"],
                "tools": ["Docker", "Kubernetes", "Terraform", "Ansible"],
            },
            "qa_engineer": {
                "persona_metadata": {
                    "persona_name": "Senior QA Engineer",
                    "persona_id": "qa_engineer_001",
                    "specialization": "Quality Assurance",
                    "experience_level": 7,
                    "autonomy_level": 8,
                },
                "capabilities": [
                    "test_planning",
                    "test_automation",
                    "performance_testing",
                    "security_testing",
                    "api_testing",
                    "mobile_testing",
                ],
                "testing_types": [
                    "unit_testing",
                    "integration_testing",
                    "e2e_testing",
                    "load_testing",
                    "penetration_testing",
                ],
                "tools": ["Selenium", "Cypress", "JMeter", "Postman", "OWASP ZAP"],
            },
        }

    @staticmethod
    def create_test_scenarios() -> Dict[str, Dict[str, Any]]:
        """Create comprehensive test scenarios"""
        return {
            "startup_mvp": {
                "scenario_name": "Startup MVP Development",
                "description": "Rapid development of minimum viable product for startup",
                "requirements": {
                    "timeline": "6 weeks",
                    "budget": "limited",
                    "team_size": "3 developers",
                    "target_users": "early adopters",
                },
                "constraints": [
                    "Fast time to market",
                    "Cost-effective solutions",
                    "Scalable architecture for future growth",
                    "Mobile-first approach",
                ],
                "success_criteria": [
                    "Launch within 6 weeks",
                    "Support 1000 initial users",
                    "Basic feature completeness",
                    "User feedback integration capability",
                ],
            },
            "enterprise_migration": {
                "scenario_name": "Enterprise Legacy System Migration",
                "description": "Migration of legacy enterprise system to modern architecture",
                "requirements": {
                    "timeline": "18 months",
                    "budget": "high",
                    "team_size": "15 developers",
                    "target_users": "enterprise employees",
                },
                "constraints": [
                    "Zero downtime migration",
                    "Data integrity preservation",
                    "Compliance requirements",
                    "Integration with existing systems",
                ],
                "success_criteria": [
                    "Successful data migration",
                    "Performance improvement",
                    "User training completion",
                    "Compliance certification",
                ],
            },
            "high_traffic_platform": {
                "scenario_name": "High-Traffic Platform Development",
                "description": "Building platform to handle millions of users",
                "requirements": {
                    "timeline": "12 months",
                    "budget": "high",
                    "team_size": "20 developers",
                    "target_users": "millions of users",
                },
                "constraints": [
                    "High availability (99.99%)",
                    "Global distribution",
                    "Real-time data processing",
                    "Security at scale",
                ],
                "success_criteria": [
                    "Handle 10M+ concurrent users",
                    "Sub-second response times",
                    "Global deployment",
                    "Zero security breaches",
                ],
            },
        }

    @pytest.fixture
    def mock_persona_file_system(self):
        """Create mock file system for persona testing"""
        temp_dir = Path(tempfile.mkdtemp(prefix="persona_test_"))

        # Create directory structure
        personas_dir = temp_dir / "personas" / "json"
        classes_dir = temp_dir / "personas" / "classes"
        shared_dir = temp_dir / "shared" / "config"

        for directory in [personas_dir, classes_dir, shared_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        # Write persona JSON files
        configs = self.create_mock_persona_configs()
        for name, config in configs.items():
            json_file = personas_dir / f"{name}.json"
            with open(json_file, "w") as f:
                json.dump(config, f, indent=2)

        yield temp_dir

        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_backend_config(self):
        """Create mock backend configuration"""
        return {
            "requirement_analysis_patterns": {
                "data_storage_indicators": ["database", "storage", "persist", "save"],
                "data_complexity_indicators": {
                    "low": ["simple", "basic", "straightforward"],
                    "medium": ["moderate", "standard", "typical"],
                    "high": ["complex", "advanced", "sophisticated", "enterprise"],
                },
                "integration_patterns": {
                    "external_apis": ["api", "service", "integration", "webhook"],
                    "file_handling": ["file", "upload", "download", "attachment"],
                    "real_time_communication": ["realtime", "live", "socket", "streaming"],
                },
                "performance_indicators": {
                    "standard": ["normal", "regular", "basic"],
                    "high": ["fast", "performance", "speed", "optimized"],
                    "critical": ["critical", "urgent", "immediate", "instant"],
                },
                "security_sensitivity_markers": {
                    "low": ["public", "open", "basic"],
                    "medium": ["user", "auth", "login", "protected"],
                    "high": ["security", "encryption", "secure", "private"],
                    "critical": ["payment", "financial", "sensitive", "confidential"],
                },
            },
            "framework_selection_matrix": {
                "low_complexity": {
                    "default": "flask",
                    "rest_api_design": "fastapi",
                    "microservices_architecture": "fastapi",
                },
                "medium_complexity": {
                    "default": "fastapi",
                    "rest_api_design": "fastapi",
                    "microservices_architecture": "fastapi",
                    "graphql_implementation": "graphene",
                },
                "high_complexity": {
                    "default": "fastapi",
                    "microservices_architecture": {
                        "standard": "fastapi",
                        "performance_critical": "fastapi",
                    },
                    "graphql_implementation": "graphene",
                },
            },
            "api_patterns": {
                "entity_patterns": {
                    "users": ["user", "account", "profile", "member"],
                    "projects": ["project", "task", "item", "work"],
                    "orders": ["order", "purchase", "transaction", "sale"],
                    "products": ["product", "item", "catalog", "inventory"],
                },
                "action_patterns": {
                    "create": ["create", "add", "new", "register", "submit"],
                    "read": ["get", "list", "view", "fetch", "retrieve"],
                    "update": ["update", "edit", "modify", "change"],
                    "delete": ["delete", "remove", "destroy", "cancel"],
                },
                "rest": {
                    "crud_pattern": {
                        "create": "POST /{resource}",
                        "read": "GET /{resource}",
                        "update": "PUT /{resource}/{id}",
                        "delete": "DELETE /{resource}/{id}",
                    },
                    "standard_endpoints": {
                        "health": "GET /health",
                        "metrics": "GET /metrics",
                        "docs": "GET /docs",
                    },
                },
            },
        }

    @pytest.fixture
    def sample_complex_requirements(self):
        """Sample complex requirements for advanced testing"""
        return {
            "functional_requirements": [
                {
                    "requirement": "User authentication with OAuth2 and JWT",
                    "priority": "high",
                    "complexity": "medium",
                },
                {
                    "requirement": "Real-time chat with WebSocket support",
                    "priority": "high",
                    "complexity": "high",
                },
                {
                    "requirement": "File upload with virus scanning",
                    "priority": "medium",
                    "complexity": "medium",
                },
                {
                    "requirement": "Advanced search with Elasticsearch",
                    "priority": "medium",
                    "complexity": "high",
                },
                {
                    "requirement": "Payment processing with Stripe integration",
                    "priority": "high",
                    "complexity": "high",
                },
            ],
            "non_functional_requirements": [
                {"requirement": "99.9% uptime availability", "type": "availability"},
                {"requirement": "Support 10,000 concurrent users", "type": "scalability"},
                {"requirement": "Response time under 200ms", "type": "performance"},
                {"requirement": "GDPR and SOC2 compliance", "type": "compliance"},
            ],
            "technical_constraints": [
                "Must use existing PostgreSQL database",
                "Integration with legacy LDAP system required",
                "Deployment on AWS only",
                "Must support IE11 (legacy requirement)",
            ],
            "business_constraints": [
                "Budget limit: $500k",
                "Timeline: 8 months",
                "Team size: 12 developers",
                "Go-live date: Fixed (trade show demo)",
            ],
        }

    @pytest.fixture
    def mock_ai_responses(self):
        """Mock AI-driven analysis responses"""
        return {
            "requirement_analysis": {
                "complexity_assessment": "high",
                "technology_recommendations": ["FastAPI", "PostgreSQL", "Redis", "React"],
                "architecture_style": "microservices",
                "estimated_effort": "8-10 months",
                "risk_factors": ["Integration complexity", "Performance requirements"],
            },
            "architecture_analysis": {
                "service_decomposition": [
                    "user-service",
                    "chat-service",
                    "file-service",
                    "search-service",
                    "payment-service",
                ],
                "data_flow": "Event-driven with message queues",
                "security_model": "OAuth2 with JWT tokens",
                "monitoring_strategy": "Distributed tracing with APM",
            },
            "implementation_strategy": {
                "development_phases": [
                    "Core services (Months 1-2)",
                    "Integration layer (Months 3-4)",
                    "Advanced features (Months 5-6)",
                    "Testing and optimization (Months 7-8)",
                ],
                "technology_stack": {
                    "backend": "FastAPI + PostgreSQL",
                    "frontend": "React + TypeScript",
                    "infrastructure": "Kubernetes + AWS",
                    "monitoring": "Prometheus + Grafana",
                },
            },
        }

    @staticmethod
    def create_persona_interaction_scenarios():
        """Create scenarios for testing persona interactions"""
        return {
            "requirement_to_architecture": {
                "description": "Requirement Analyst -> Solution Architect flow",
                "input": "Build an e-commerce platform",
                "expected_flow": [
                    "requirement_analyst.analyze_requirements",
                    "solution_architect.analyze_requirements_for_architecture",
                ],
                "expected_outputs": ["functional_requirements", "architecture_design"],
            },
            "architecture_to_implementation": {
                "description": "Solution Architect -> Developer flow",
                "input": "Microservices architecture for e-commerce",
                "expected_flow": [
                    "solution_architect.analyze_requirements_for_architecture",
                    "backend_developer.implement_backend_solution",
                    "frontend_developer.implement_frontend_solution",
                ],
                "expected_outputs": [
                    "architecture_design",
                    "backend_implementation",
                    "frontend_implementation",
                ],
            },
            "implementation_to_testing": {
                "description": "Developer -> QA Engineer flow",
                "input": "Completed implementation artifacts",
                "expected_flow": [
                    "backend_developer.implement_backend_solution",
                    "qa_engineer.create_comprehensive_test_plan",
                ],
                "expected_outputs": ["backend_implementation", "test_plan"],
            },
            "testing_to_deployment": {
                "description": "QA Engineer -> DevOps Engineer flow",
                "input": "Tested application components",
                "expected_flow": [
                    "qa_engineer.create_comprehensive_test_plan",
                    "devops_engineer.design_deployment_strategy",
                ],
                "expected_outputs": ["test_plan", "deployment_strategy"],
            },
        }

    @staticmethod
    def create_performance_test_data():
        """Create data for performance testing"""
        return {
            "large_requirements_set": {
                "functional_requirements": [
                    {"requirement": f"Feature requirement {i}", "priority": "medium"}
                    for i in range(1, 101)  # 100 requirements
                ],
                "non_functional_requirements": [
                    {"requirement": f"NFR requirement {i}", "type": "performance"}
                    for i in range(1, 51)  # 50 NFRs
                ],
            },
            "complex_architecture": {
                "services": [f"service-{i}" for i in range(1, 21)],  # 20 services
                "databases": [f"db-{i}" for i in range(1, 6)],  # 5 databases
                "integrations": [f"integration-{i}" for i in range(1, 11)],  # 10 integrations
            },
            "stress_test_scenarios": [
                {"concurrent_personas": 10, "iterations": 100},
                {"concurrent_personas": 20, "iterations": 50},
                {"concurrent_personas": 50, "iterations": 20},
            ],
        }


@pytest.fixture(scope="session")
def persona_fixtures():
    """Session-scoped fixture providing all persona test utilities"""
    return PersonaTestFixtures()


@pytest.fixture
def sample_requirements(persona_fixtures):
    """Provide sample requirements for testing"""
    return persona_fixtures.create_sample_requirements()


@pytest.fixture
def sample_architectures(persona_fixtures):
    """Provide sample architectures for testing"""
    return persona_fixtures.create_sample_architectures()


@pytest.fixture
def mock_persona_configs(persona_fixtures):
    """Provide mock persona configurations"""
    return persona_fixtures.create_mock_persona_configs()


@pytest.fixture
def test_scenarios(persona_fixtures):
    """Provide test scenarios"""
    return persona_fixtures.create_test_scenarios()


@pytest.fixture
def interaction_scenarios():
    """Provide persona interaction scenarios"""
    return PersonaTestFixtures.create_persona_interaction_scenarios()


@pytest.fixture
def performance_test_data():
    """Provide performance test data"""
    return PersonaTestFixtures.create_performance_test_data()
