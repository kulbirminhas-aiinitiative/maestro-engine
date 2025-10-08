#!/usr/bin/env python3
"""
Persona Integration Scenarios Test Suite
Tests complex persona interaction workflows and real-world scenarios
"""

import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

# Add project root to path
sys.path.append("/data/maestro-services")

from personas.classes.backend_developer_persona import BackendDeveloperPersona
from personas.classes.devops_engineer_persona import DevopsEngineerPersona
from personas.classes.frontend_developer_persona import FrontendDeveloperPersona
from personas.classes.qa_engineer_persona import QAEngineerPersona
from personas.classes.requirement_analyst_persona import RequirementAnalystPersona
from personas.classes.solution_architect_persona import SolutionArchitectPersona
from tests.fixtures.persona_test_fixtures import PersonaTestFixtures


class TestPersonaIntegrationScenarios:
    """Test complex persona integration scenarios"""

    def setup_method(self):
        """Setup test environment"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="persona_integration_test_"))
        self.fixtures = PersonaTestFixtures()
        self._setup_test_environment()

    def teardown_method(self):
        """Cleanup test environment"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def _setup_test_environment(self):
        """Setup comprehensive test environment"""
        # Create directories
        self.personas_dir = self.test_dir / "personas"
        self.shared_dir = self.test_dir / "shared" / "config"
        self.output_dir = self.test_dir / "output"

        for directory in [self.personas_dir, self.shared_dir, self.output_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        # Create persona configurations
        self.persona_configs = self.fixtures.create_mock_persona_configs()
        for name, config in self.persona_configs.items():
            json_file = self.personas_dir / f"{name}.json"
            with open(json_file, "w") as f:
                json.dump(config, f, indent=2)

        # Create shared configuration
        backend_config = {
            "requirement_analysis_patterns": {
                "data_storage_indicators": ["database", "storage"],
                "data_complexity_indicators": {
                    "low": ["simple"],
                    "medium": ["moderate"],
                    "high": ["complex"],
                },
                "integration_patterns": {
                    "external_apis": ["api", "service"],
                    "file_handling": ["file", "upload"],
                    "real_time_communication": ["realtime", "live"],
                },
                "performance_indicators": {"standard": ["normal"], "high": ["fast", "performance"]},
                "security_sensitivity_markers": {
                    "medium": ["user", "auth"],
                    "high": ["security", "encryption"],
                },
            },
            "framework_selection_matrix": {
                "low_complexity": {"default": "flask"},
                "medium_complexity": {"default": "fastapi"},
                "high_complexity": {"default": "fastapi"},
            },
            "technology_selection_rules": {
                "database": {"low_complexity": ["sqlite"], "medium_complexity": ["postgresql"]},
                "performance": {"standard": ["redis"], "high": ["redis", "memcached"]},
                "security": {"medium": ["jwt"], "high": ["jwt", "oauth2"]},
                "integration": {"external_apis": ["requests"], "file_handling": ["boto3"]},
            },
            "confidence_factors": {
                "experience_multiplier": 8,
                "complexity_bonus": {"low": 5, "medium": 10, "high": 15},
                "specialization_bonus": 5,
                "max_confidence": 95,
            },
            "api_patterns": {
                "entity_patterns": {"users": ["user", "account"], "projects": ["project", "task"]},
                "action_patterns": {
                    "create": ["create", "add"],
                    "read": ["get", "list"],
                    "update": ["update", "edit"],
                    "delete": ["delete", "remove"],
                },
                "rest": {
                    "crud_pattern": {
                        "create": "POST /{resource}",
                        "read": "GET /{resource}",
                        "update": "PUT /{resource}/{id}",
                        "delete": "DELETE /{resource}/{id}",
                    },
                    "standard_endpoints": {"health": "GET /health"},
                },
            },
            "database_defaults": {
                "postgresql": {
                    "features": ["ACID", "JSON support"],
                    "dependencies": ["psycopg2-binary==2.9.7"],
                },
                "sqlite": {"features": ["Lightweight"], "dependencies": []},
            },
            "database_schema_patterns": {
                "common_entity_schemas": {
                    "users": {
                        "fields": ["id", "username", "email", "password_hash", "created_at"],
                        "indexes": ["username", "email"],
                        "constraints": ["UNIQUE(username)"],
                    }
                },
                "field_types": {
                    "id": {"postgresql": "SERIAL PRIMARY KEY", "sqlite": "INTEGER PRIMARY KEY"},
                    "string_fields": {"postgresql": "VARCHAR(255)", "sqlite": "TEXT"},
                    "text_fields": {"postgresql": "TEXT", "sqlite": "TEXT"},
                    "datetime_fields": {"postgresql": "TIMESTAMP", "sqlite": "DATETIME"},
                    "boolean_fields": {"postgresql": "BOOLEAN", "sqlite": "BOOLEAN"},
                    "foreign_key": {"postgresql": "INTEGER", "sqlite": "INTEGER"},
                },
            },
            "security_defaults": {
                "basic": {"authentication": None, "measures": ["Input validation"]},
                "medium": {"authentication": "JWT", "measures": ["JWT authentication"]},
            },
            "performance_defaults": {
                "standard": {
                    "strategies": ["Database indexing"],
                    "caching": "Memory",
                    "monitoring": ["Basic metrics"],
                }
            },
            "deployment_defaults": {
                "direct_deployment": {
                    "environments": ["development", "production"],
                    "features": ["Basic deployment"],
                },
                "docker_compose": {
                    "environments": ["development", "staging", "production"],
                    "features": ["Containerization"],
                    "base_services": ["api", "db", "redis"],
                },
            },
            "framework_defaults": {
                "fastapi": {
                    "dependencies": ["fastapi==0.104.1"],
                    "security_packages": ["python-jose[cryptography]==3.3.0"],
                    "testing_packages": ["pytest==7.4.3"],
                }
            },
            "project_management": {
                "package_manager": "poetry",
                "python_version": "^3.8",
                "code_quality": ["black"],
            },
            "dependency_management": {
                "package_extraction_patterns": {
                    "security": {"keywords": ["auth", "jwt"], "packages": ["python-jose"]}
                }
            },
        }

        with open(self.shared_dir / "backend_defaults.json", "w") as f:
            json.dump(backend_config, f, indent=2)

    # Scenario 1: Simple Web Application Development Flow
    def test_simple_web_app_development_flow(self):
        """Test complete flow for simple web application development"""
        requirement = "Create a simple user registration and login web application"

        # Step 1: Requirement Analysis
        req_analyst = RequirementAnalystPersona(str(self.personas_dir / "requirement_analyst.json"))

        with patch.object(req_analyst, "analyze_requirements") as mock_req_analysis:
            mock_req_analysis.return_value = {
                "functional_requirements": [
                    {"requirement": "User registration with email and password"},
                    {"requirement": "User login functionality"},
                    {"requirement": "Basic user profile page"},
                ],
                "non_functional_requirements": [
                    {"requirement": "Responsive design"},
                    {"requirement": "Basic security measures"},
                ],
                "key_concepts": ["user", "registration", "login", "profile"],
                "requirement_classification": {"complexity_level": "low", "complexity_score": 3},
            }

            req_result = req_analyst.analyze_requirements(requirement)

        # Step 2: Solution Architecture
        sol_architect = SolutionArchitectPersona(str(self.personas_dir / "solution_architect.json"))

        with patch.object(
            sol_architect, "_ai_comprehensive_architecture_analysis"
        ) as mock_arch_analysis:
            mock_arch_analysis.return_value = {
                "platform_analysis": {"platform_detected": "web"},
                "solution_architecture_overview": {"architecture_style": "monolithic"},
                "technology_stack": {"primary_stack": "Python Flask"},
                "system_architecture": {"estimated_service_count": 1},
                "key_concepts_processed": ["user", "auth"],
                "database_design": {"type": "SQLite", "entities": ["users"]},
                "security_implementation": {"level": "basic", "authentication": "session"},
            }

            arch_result = sol_architect.analyze_requirements_for_architecture(
                req_result, requirement
            )

        # Step 3: Backend Implementation
        program_plan = {
            "original_requirement": requirement,
            "input_analyses": {"requirement_analysis": req_result},
        }

        with patch(
            "builtins.open",
            mock_open(read_data=json.dumps(self.persona_configs["backend_developer"])),
        ):
            with patch("pathlib.Path.exists", return_value=True):
                backend_dev = BackendDeveloperPersona(
                    str(self.personas_dir / "backend_developer.json")
                )

                backend_result = backend_dev.implement_backend_solution(
                    program_plan, arch_result, str(self.output_dir)
                )

        # Assertions
        assert req_result is not None
        assert "functional_requirements" in req_result
        assert len(req_result["functional_requirements"]) == 3

        assert arch_result is not None
        assert "solution_architecture_overview" in arch_result
        assert arch_result["solution_architecture_overview"]["architecture_style"] == "monolithic"

        assert backend_result is not None
        assert "technology_selection" in backend_result
        assert "api_architecture" in backend_result
        assert "database_design" in backend_result

        # Verify flow integrity
        assert req_result["requirement_classification"]["complexity_level"] == "low"
        assert backend_result["ai_backend_analysis"]["persona_id"] == "backend_developer_001"

    # Scenario 2: E-commerce Platform Development (Complex)
    def test_ecommerce_platform_development_flow(self):
        """Test complete flow for complex e-commerce platform development"""
        requirement = "Build a comprehensive e-commerce platform with payment processing"

        # Step 1: Requirement Analysis
        req_analyst = RequirementAnalystPersona(str(self.personas_dir / "requirement_analyst.json"))

        complex_requirements = {
            "functional_requirements": [
                {"requirement": "Product catalog management"},
                {"requirement": "Shopping cart functionality"},
                {"requirement": "Payment processing integration"},
                {"requirement": "Order management system"},
                {"requirement": "User authentication and authorization"},
                {"requirement": "Admin dashboard"},
                {"requirement": "Email notifications"},
                {"requirement": "Inventory tracking"},
            ],
            "non_functional_requirements": [
                {"requirement": "High availability (99.9% uptime)"},
                {"requirement": "Support for 10,000 concurrent users"},
                {"requirement": "PCI DSS compliance"},
                {"requirement": "Response time under 2 seconds"},
            ],
            "key_concepts": ["product", "cart", "payment", "order", "user", "admin", "inventory"],
            "requirement_classification": {"complexity_level": "high", "complexity_score": 9},
        }

        with patch.object(req_analyst, "analyze_requirements") as mock_req_analysis:
            mock_req_analysis.return_value = complex_requirements
            req_result = req_analyst.analyze_requirements(requirement)

        # Step 2: Solution Architecture
        sol_architect = SolutionArchitectPersona(str(self.personas_dir / "solution_architect.json"))

        complex_architecture = {
            "platform_analysis": {"platform_detected": "web"},
            "solution_architecture_overview": {"architecture_style": "microservices"},
            "technology_stack": {"primary_stack": "Python FastAPI"},
            "system_architecture": {"estimated_service_count": 5},
            "key_concepts_processed": ["product", "cart", "payment", "order", "user"],
            "services": [
                "user-service",
                "product-service",
                "cart-service",
                "order-service",
                "payment-service",
            ],
            "database_design": {
                "type": "PostgreSQL",
                "entities": ["users", "products", "orders", "payments"],
            },
            "security_implementation": {
                "level": "high",
                "authentication": "OAuth2",
                "compliance": ["PCI DSS"],
            },
        }

        with patch.object(
            sol_architect, "_ai_comprehensive_architecture_analysis"
        ) as mock_arch_analysis:
            mock_arch_analysis.return_value = complex_architecture
            arch_result = sol_architect.analyze_requirements_for_architecture(
                req_result, requirement
            )

        # Step 3: Backend Implementation
        program_plan = {
            "original_requirement": requirement,
            "input_analyses": {"requirement_analysis": req_result},
        }

        with patch(
            "builtins.open",
            mock_open(read_data=json.dumps(self.persona_configs["backend_developer"])),
        ):
            with patch("pathlib.Path.exists", return_value=True):
                backend_dev = BackendDeveloperPersona(
                    str(self.personas_dir / "backend_developer.json")
                )

                backend_result = backend_dev.implement_backend_solution(
                    program_plan, arch_result, str(self.output_dir)
                )

        # Step 4: QA Planning
        qa_engineer = QAEngineerPersona(str(self.personas_dir / "qa_engineer.json"))

        test_plan = {
            "test_strategy": "Comprehensive testing for e-commerce platform",
            "test_types": [
                "unit_testing",
                "integration_testing",
                "performance_testing",
                "security_testing",
                "payment_testing",
            ],
            "test_cases": [
                "User registration and login",
                "Product catalog browsing",
                "Shopping cart operations",
                "Payment processing",
                "Order management",
                "Admin functionality",
            ],
            "automation_framework": "pytest + selenium",
            "performance_criteria": {
                "response_time": "< 2 seconds",
                "concurrent_users": "10,000",
                "availability": "99.9%",
            },
        }

        with patch.object(qa_engineer, "create_comprehensive_test_plan") as mock_test_plan:
            mock_test_plan.return_value = test_plan
            qa_result = qa_engineer.create_comprehensive_test_plan(program_plan, arch_result)

        # Assertions for complex scenario
        assert req_result["requirement_classification"]["complexity_level"] == "high"
        assert len(req_result["functional_requirements"]) == 8
        assert len(req_result["non_functional_requirements"]) == 4

        assert (
            arch_result["solution_architecture_overview"]["architecture_style"] == "microservices"
        )
        assert arch_result["system_architecture"]["estimated_service_count"] == 5

        assert backend_result is not None
        assert backend_result["security_implementation"]["level"] == "high"

        assert qa_result is not None
        assert "security_testing" in qa_result["test_types"]
        assert "payment_testing" in qa_result["test_types"]

    # Scenario 3: API Microservice Development
    def test_api_microservice_development_flow(self):
        """Test flow for API microservice development"""
        requirement = "Develop a REST API microservice for task management"

        # Mock requirement analysis focused on API development
        api_requirements = {
            "functional_requirements": [
                {"requirement": "CRUD operations for tasks"},
                {"requirement": "Task assignment to users"},
                {"requirement": "Task status tracking"},
                {"requirement": "API authentication with JWT"},
            ],
            "non_functional_requirements": [
                {"requirement": "API rate limiting"},
                {"requirement": "API documentation with Swagger"},
                {"requirement": "Response time under 500ms"},
            ],
            "key_concepts": ["task", "user", "api", "crud", "auth"],
            "requirement_classification": {"complexity_level": "medium", "complexity_score": 5},
        }

        # Mock architecture focused on API design
        api_architecture = {
            "platform_analysis": {"platform_detected": "api"},
            "solution_architecture_overview": {"architecture_style": "restful_api"},
            "technology_stack": {"primary_stack": "Python FastAPI"},
            "system_architecture": {"estimated_service_count": 1},
            "key_concepts_processed": ["task", "user", "api"],
            "api_design": {
                "endpoints": [
                    "GET /tasks",
                    "POST /tasks",
                    "GET /tasks/{id}",
                    "PUT /tasks/{id}",
                    "DELETE /tasks/{id}",
                    "POST /tasks/{id}/assign",
                ],
                "authentication": "JWT Bearer Token",
                "documentation": "OpenAPI 3.0",
            },
        }

        # Test backend implementation with API focus
        req_analyst = RequirementAnalystPersona(str(self.personas_dir / "requirement_analyst.json"))
        sol_architect = SolutionArchitectPersona(str(self.personas_dir / "solution_architect.json"))

        with patch.object(req_analyst, "analyze_requirements") as mock_req:
            mock_req.return_value = api_requirements
            req_result = req_analyst.analyze_requirements(requirement)

        with patch.object(sol_architect, "_ai_comprehensive_architecture_analysis") as mock_arch:
            mock_arch.return_value = api_architecture
            arch_result = sol_architect.analyze_requirements_for_architecture(
                req_result, requirement
            )

        program_plan = {
            "original_requirement": requirement,
            "input_analyses": {"requirement_analysis": req_result},
        }

        with patch(
            "builtins.open",
            mock_open(read_data=json.dumps(self.persona_configs["backend_developer"])),
        ):
            with patch("pathlib.Path.exists", return_value=True):
                backend_dev = BackendDeveloperPersona(
                    str(self.personas_dir / "backend_developer.json")
                )

                backend_result = backend_dev.implement_backend_solution(
                    program_plan, arch_result, str(self.output_dir)
                )

        # Assertions for API microservice
        assert req_result["requirement_classification"]["complexity_level"] == "medium"
        assert any("CRUD" in req["requirement"] for req in req_result["functional_requirements"])

        assert arch_result["solution_architecture_overview"]["architecture_style"] == "restful_api"
        assert "api_design" in arch_result

        assert backend_result is not None
        assert "api_architecture" in backend_result
        assert backend_result["api_architecture"]["design_approach"] in [
            "RESTful API",
            "Standard API",
        ]

    # Scenario 4: Real-time Application Development
    def test_realtime_application_development_flow(self):
        """Test flow for real-time application development"""
        requirement = "Create a real-time chat application with WebSocket support"

        # Mock real-time focused requirements
        realtime_requirements = {
            "functional_requirements": [
                {"requirement": "Real-time messaging between users"},
                {"requirement": "Chat room creation and management"},
                {"requirement": "Message history and search"},
                {"requirement": "User presence indicators"},
                {"requirement": "Push notifications"},
            ],
            "non_functional_requirements": [
                {"requirement": "Low latency messaging (< 100ms)"},
                {"requirement": "Scalable to 1000+ concurrent connections"},
                {"requirement": "Message encryption"},
                {"requirement": "High availability"},
            ],
            "key_concepts": ["chat", "realtime", "websocket", "message", "notification"],
            "requirement_classification": {"complexity_level": "high", "complexity_score": 8},
        }

        # Mock real-time architecture
        realtime_architecture = {
            "platform_analysis": {"platform_detected": "realtime_web"},
            "solution_architecture_overview": {"architecture_style": "event_driven"},
            "technology_stack": {"primary_stack": "Python FastAPI + WebSockets"},
            "system_architecture": {"estimated_service_count": 3},
            "key_concepts_processed": ["chat", "realtime", "websocket"],
            "realtime_components": {
                "websocket_handler": "FastAPI WebSocket",
                "message_broker": "Redis Pub/Sub",
                "presence_tracking": "Redis TTL",
                "message_storage": "PostgreSQL",
            },
            "scalability": {
                "connection_pooling": "Redis connection pool",
                "load_balancing": "Sticky sessions",
                "horizontal_scaling": "Multiple server instances",
            },
        }

        # Test implementation
        req_analyst = RequirementAnalystPersona(str(self.personas_dir / "requirement_analyst.json"))
        sol_architect = SolutionArchitectPersona(str(self.personas_dir / "solution_architect.json"))

        with patch.object(req_analyst, "analyze_requirements") as mock_req:
            mock_req.return_value = realtime_requirements
            req_result = req_analyst.analyze_requirements(requirement)

        with patch.object(sol_architect, "_ai_comprehensive_architecture_analysis") as mock_arch:
            mock_arch.return_value = realtime_architecture
            arch_result = sol_architect.analyze_requirements_for_architecture(
                req_result, requirement
            )

        program_plan = {
            "original_requirement": requirement,
            "input_analyses": {"requirement_analysis": req_result},
        }

        with patch(
            "builtins.open",
            mock_open(read_data=json.dumps(self.persona_configs["backend_developer"])),
        ):
            with patch("pathlib.Path.exists", return_value=True):
                backend_dev = BackendDeveloperPersona(
                    str(self.personas_dir / "backend_developer.json")
                )

                backend_result = backend_dev.implement_backend_solution(
                    program_plan, arch_result, str(self.output_dir)
                )

        # Assertions for real-time application
        assert req_result["requirement_classification"]["complexity_level"] == "high"
        assert any(
            "real-time" in req["requirement"].lower()
            for req in req_result["functional_requirements"]
        )

        assert arch_result["solution_architecture_overview"]["architecture_style"] == "event_driven"
        assert "realtime_components" in arch_result

        assert backend_result is not None
        assert backend_result["performance_strategy"]["async_processing"] is True

    # Scenario 5: Multi-Persona Collaboration
    def test_multi_persona_collaboration_workflow(self):
        """Test complex workflow involving multiple personas"""
        requirement = "Build a comprehensive project management platform"

        # Initialize all personas
        req_analyst = RequirementAnalystPersona(str(self.personas_dir / "requirement_analyst.json"))
        sol_architect = SolutionArchitectPersona(str(self.personas_dir / "solution_architect.json"))

        with patch(
            "builtins.open",
            mock_open(read_data=json.dumps(self.persona_configs["backend_developer"])),
        ):
            with patch("pathlib.Path.exists", return_value=True):
                backend_dev = BackendDeveloperPersona(
                    str(self.personas_dir / "backend_developer.json")
                )

        frontend_dev = FrontendDeveloperPersona(str(self.personas_dir / "frontend_developer.json"))
        qa_engineer = QAEngineerPersona(str(self.personas_dir / "qa_engineer.json"))
        devops_engineer = DevopsEngineerPersona(str(self.personas_dir / "devops_engineer.json"))

        # Mock comprehensive project management requirements
        pm_requirements = {
            "functional_requirements": [
                {"requirement": "Project creation and management"},
                {"requirement": "Task assignment and tracking"},
                {"requirement": "Team collaboration features"},
                {"requirement": "Time tracking and reporting"},
                {"requirement": "File sharing and documentation"},
                {"requirement": "Gantt charts and project visualization"},
            ],
            "non_functional_requirements": [
                {"requirement": "Support 1000+ concurrent users"},
                {"requirement": "Real-time updates"},
                {"requirement": "Mobile responsive design"},
                {"requirement": "Data backup and recovery"},
            ],
            "key_concepts": ["project", "task", "team", "collaboration", "tracking"],
            "requirement_classification": {"complexity_level": "high", "complexity_score": 9},
        }

        # Mock complex architecture
        pm_architecture = {
            "platform_analysis": {"platform_detected": "web_platform"},
            "solution_architecture_overview": {"architecture_style": "microservices"},
            "technology_stack": {"primary_stack": "Python FastAPI + React"},
            "system_architecture": {"estimated_service_count": 6},
            "key_concepts_processed": ["project", "task", "team", "collaboration"],
        }

        # Mock implementation results
        backend_implementation = {
            "technology_selection": {"framework": "FastAPI"},
            "api_architecture": {"design_approach": "RESTful API"},
            "database_design": {"type": "PostgreSQL"},
            "security_implementation": {"level": "High"},
            "performance_strategy": {"approach": "High-Performance"},
        }

        frontend_implementation = {
            "framework_selection": "React",
            "component_architecture": {"pattern": "Container/Presenter"},
            "state_management": "Redux",
            "ui_design": {"approach": "Material-UI"},
        }

        test_implementation = {
            "test_strategy": "Comprehensive testing approach",
            "test_types": ["unit", "integration", "e2e", "performance"],
            "automation_coverage": "90%",
        }

        deployment_implementation = {
            "deployment_strategy": "Kubernetes",
            "ci_cd_pipeline": "GitLab CI/CD",
            "monitoring": "Prometheus + Grafana",
            "infrastructure": "AWS EKS",
        }

        # Execute workflow with mocks
        with patch.object(req_analyst, "analyze_requirements") as mock_req:
            mock_req.return_value = pm_requirements
            req_result = req_analyst.analyze_requirements(requirement)

        with patch.object(sol_architect, "_ai_comprehensive_architecture_analysis") as mock_arch:
            mock_arch.return_value = pm_architecture
            arch_result = sol_architect.analyze_requirements_for_architecture(
                req_result, requirement
            )

        program_plan = {
            "original_requirement": requirement,
            "input_analyses": {"requirement_analysis": req_result},
        }

        backend_result = backend_dev.implement_backend_solution(
            program_plan, arch_result, str(self.output_dir)
        )

        with patch.object(frontend_dev, "implement_frontend_solution") as mock_frontend:
            mock_frontend.return_value = frontend_implementation
            frontend_result = frontend_dev.implement_frontend_solution(
                program_plan, arch_result, str(self.output_dir)
            )

        with patch.object(qa_engineer, "create_comprehensive_test_plan") as mock_qa:
            mock_qa.return_value = test_implementation
            qa_result = qa_engineer.create_comprehensive_test_plan(program_plan, arch_result)

        with patch.object(devops_engineer, "design_deployment_strategy") as mock_devops:
            mock_devops.return_value = deployment_implementation
            devops_result = devops_engineer.design_deployment_strategy(program_plan, arch_result)

        # Comprehensive assertions
        assert req_result is not None
        assert arch_result is not None
        assert backend_result is not None
        assert frontend_result is not None
        assert qa_result is not None
        assert devops_result is not None

        # Verify workflow consistency
        assert req_result["requirement_classification"]["complexity_level"] == "high"
        assert (
            arch_result["solution_architecture_overview"]["architecture_style"] == "microservices"
        )
        assert backend_result["technology_selection"]["framework"] == "FastAPI"
        assert frontend_result["framework_selection"] == "React"
        assert "performance" in qa_result["test_types"]
        assert devops_result["deployment_strategy"] == "Kubernetes"

    # Performance and Stress Tests
    @pytest.mark.performance
    def test_persona_workflow_performance(self):
        """Test performance of persona workflows"""
        import time

        requirement = "Create a simple CRUD API"

        start_time = time.time()

        # Quick workflow execution
        req_analyst = RequirementAnalystPersona(str(self.personas_dir / "requirement_analyst.json"))

        with patch.object(req_analyst, "analyze_requirements") as mock_req:
            mock_req.return_value = {
                "functional_requirements": [{"requirement": "CRUD operations"}],
                "requirement_classification": {"complexity_level": "low"},
            }
            req_result = req_analyst.analyze_requirements(requirement)

        end_time = time.time()
        execution_time = end_time - start_time

        assert execution_time < 1.0  # Should complete in under 1 second
        assert req_result is not None

    @pytest.mark.stress
    def test_concurrent_persona_execution(self):
        """Test concurrent execution of multiple personas"""
        import threading
        import time

        results = []
        errors = []

        def persona_task(persona_id):
            try:
                req_analyst = RequirementAnalystPersona(
                    str(self.personas_dir / "requirement_analyst.json")
                )
                with patch.object(req_analyst, "analyze_requirements") as mock_req:
                    mock_req.return_value = {
                        "functional_requirements": [{"requirement": f"Requirement {persona_id}"}],
                        "requirement_classification": {"complexity_level": "low"},
                    }
                    result = req_analyst.analyze_requirements(f"Requirement {persona_id}")
                    results.append(result)
            except Exception as e:
                errors.append(e)

        # Launch 10 concurrent persona tasks
        threads = []
        for i in range(10):
            thread = threading.Thread(target=persona_task, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Assertions
        assert len(errors) == 0  # No errors should occur
        assert len(results) == 10  # All tasks should complete

        # Verify result integrity
        for result in results:
            assert result is not None
            assert "functional_requirements" in result

    def test_error_recovery_in_workflow(self):
        """Test error recovery and graceful handling in persona workflows"""
        requirement = "Create an application"

        req_analyst = RequirementAnalystPersona(str(self.personas_dir / "requirement_analyst.json"))

        # Test error in requirement analysis
        with patch.object(req_analyst, "analyze_requirements") as mock_req:
            mock_req.side_effect = Exception("Analysis failed")

            try:
                req_result = req_analyst.analyze_requirements(requirement)
                assert False, "Should have raised an exception"
            except Exception as e:
                assert str(e) == "Analysis failed"

        # Test recovery with valid data
        with patch.object(req_analyst, "analyze_requirements") as mock_req:
            mock_req.return_value = {
                "functional_requirements": [{"requirement": "Basic functionality"}],
                "requirement_classification": {"complexity_level": "low"},
            }
            req_result = req_analyst.analyze_requirements(requirement)

        assert req_result is not None
        assert "functional_requirements" in req_result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
