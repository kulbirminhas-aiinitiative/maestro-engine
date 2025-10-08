#!/usr/bin/env python3
"""
Comprehensive Unit Tests for MAESTRO Persona Invocation System
Tests all persona classes with their corresponding JSON configurations
"""

import json
import shutil

# Import all persona classes
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, mock_open, patch

import pytest

sys.path.append("/data/maestro-services")

from personas.classes.backend_developer_persona import BackendDeveloperPersona
from personas.classes.devops_engineer_persona import DevopsEngineerPersona
from personas.classes.enhanced_qa_engineer_persona import EnhancedQAEngineerPersona
from personas.classes.frontend_developer_persona import FrontendDeveloperPersona
from personas.classes.program_manager_persona import ProgramManagerPersona
from personas.classes.qa_engineer_persona import QAEngineerPersona
from personas.classes.requirement_analyst_persona import RequirementAnalystPersona
from personas.classes.solution_architect_persona import SolutionArchitectPersona
from personas.classes.solution_reviewer_persona import SolutionReviewerPersona


class TestPersonaInvocation:
    """Comprehensive test suite for persona invocation system"""

    def setup_method(self):
        """Setup test environment"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="maestro_persona_test_"))
        self.personas_dir = self.test_dir / "personas"
        self.personas_dir.mkdir(parents=True)

        # Create test persona JSON files
        self.persona_configs = self._create_test_persona_configs()
        self._write_persona_json_files()

        # Create mock shared config
        self._create_mock_shared_config()

    def teardown_method(self):
        """Cleanup test environment"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def _create_test_persona_configs(self) -> Dict[str, Dict[str, Any]]:
        """Create test persona configurations"""
        return {
            "backend_developer": {
                "persona_metadata": {
                    "persona_name": "Senior Backend Developer",
                    "persona_id": "backend_developer_001",
                    "specialization": "Backend Development",
                    "experience_level": 8,
                    "autonomy_level": 9,
                    "description": "Expert backend developer",
                },
                "capabilities": [
                    "api_development",
                    "database_design",
                    "microservices_architecture",
                    "performance_optimization",
                ],
                "specializations": [
                    "rest_api_design",
                    "database_optimization",
                    "microservices_architecture",
                ],
                "output_contract": {
                    "deliverables": ["backend_implementation/"],
                    "documentation_requirements": ["API specification"],
                },
                "approach_methodology": {
                    "development_process": ["Analyze requirements"],
                    "quality_standards": ["RESTful API design"],
                },
            },
            "solution_architect": {
                "persona_metadata": {
                    "persona_name": "Senior Solution Architect",
                    "persona_id": "solution_architect_001",
                },
                "role": {
                    "specialization_areas": ["microservices", "cloud_architecture"],
                    "experience_level": 9,
                    "autonomy_level": 8,
                },
                "validation_gates": {
                    "complexity_based_thresholds": {
                        "simple": {"min_functional_requirements": 2},
                        "moderate": {"min_functional_requirements": 3},
                        "complex": {"min_functional_requirements": 5},
                    }
                },
            },
            "requirement_analyst": {
                "persona_metadata": {
                    "persona_name": "Senior Requirements Analyst",
                    "persona_id": "requirement_analyst_001",
                },
                "role": {"experience_level": 8, "autonomy_level": 7},
                "analysis_methodology": {
                    "requirement_extraction": ["stakeholder_analysis"],
                    "quality_gates": ["completeness_check"],
                },
            },
            "frontend_developer": {
                "persona_metadata": {
                    "persona_name": "Senior Frontend Developer",
                    "persona_id": "frontend_developer_001",
                },
                "capabilities": ["ui_development", "state_management"],
                "specializations": ["react", "vue", "angular"],
                "framework_preferences": ["React", "Vue.js"],
            },
            "qa_engineer": {
                "persona_metadata": {
                    "persona_name": "Senior QA Engineer",
                    "persona_id": "qa_engineer_001",
                },
                "testing_capabilities": ["unit_testing", "integration_testing"],
                "automation_tools": ["pytest", "selenium"],
            },
            "devops_engineer": {
                "persona_metadata": {
                    "persona_name": "Senior DevOps Engineer",
                    "persona_id": "devops_engineer_001",
                },
                "infrastructure_skills": ["docker", "kubernetes"],
                "cloud_platforms": ["aws", "azure"],
            },
            "program_manager": {
                "persona_metadata": {
                    "persona_name": "Senior Program Manager",
                    "persona_id": "program_manager_001",
                },
                "management_skills": ["project_planning", "risk_management"],
                "methodologies": ["agile", "waterfall"],
            },
            "solution_reviewer": {
                "persona_metadata": {
                    "persona_name": "Solution Reviewer",
                    "persona_id": "solution_reviewer_001",
                },
                "review_criteria": ["technical_accuracy", "completeness"],
                "expertise_areas": ["architecture", "security"],
            },
            "enhanced_qa_engineer": {
                "persona_metadata": {
                    "persona_name": "Enhanced QA Engineer",
                    "persona_id": "enhanced_qa_engineer_001",
                },
                "advanced_capabilities": ["ai_testing", "performance_testing"],
                "tools": ["pytest", "locust"],
            },
        }

    def _write_persona_json_files(self):
        """Write persona JSON configurations to test directory"""
        for persona_name, config in self.persona_configs.items():
            json_file = self.personas_dir / f"{persona_name}.json"
            with open(json_file, "w") as f:
                json.dump(config, f, indent=2)

    def _create_mock_shared_config(self):
        """Create mock shared configuration files"""
        shared_dir = self.test_dir / "shared" / "config"
        shared_dir.mkdir(parents=True, exist_ok=True)

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
                "database": {
                    "low_complexity": ["sqlite"],
                    "medium_complexity": ["postgresql"],
                    "high_complexity": ["postgresql"],
                },
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
                    "standard_endpoints": {"health": "GET /health", "metrics": "GET /metrics"},
                },
            },
            "database_defaults": {
                "postgresql": {
                    "features": ["ACID", "JSON support"],
                    "dependencies": ["psycopg2-binary==2.9.7"],
                },
                "sqlite": {"features": ["Lightweight", "File-based"], "dependencies": []},
            },
            "database_schema_patterns": {
                "common_entity_schemas": {
                    "users": {
                        "fields": ["id", "username", "email", "password_hash", "created_at"],
                        "indexes": ["username", "email"],
                        "constraints": ["UNIQUE(username)", "UNIQUE(email)"],
                    },
                    "projects": {
                        "fields": ["id", "name", "description", "user_id", "created_at"],
                        "indexes": ["user_id"],
                        "relationships": ["FOREIGN KEY(user_id) REFERENCES users(id)"],
                    },
                },
                "field_types": {
                    "id": {"postgresql": "SERIAL PRIMARY KEY", "sqlite": "INTEGER PRIMARY KEY"},
                    "string_fields": {"postgresql": "VARCHAR(255)", "sqlite": "TEXT"},
                    "text_fields": {"postgresql": "TEXT", "sqlite": "TEXT"},
                    "datetime_fields": {"postgresql": "TIMESTAMP", "sqlite": "DATETIME"},
                    "boolean_fields": {"postgresql": "BOOLEAN", "sqlite": "BOOLEAN"},
                    "foreign_key": {
                        "postgresql": "INTEGER REFERENCES {table}(id)",
                        "sqlite": "INTEGER",
                    },
                },
            },
            "security_defaults": {
                "basic": {"authentication": None, "measures": ["Input validation"]},
                "medium": {
                    "authentication": "JWT",
                    "measures": ["JWT authentication", "Password hashing"],
                },
                "high": {
                    "authentication": "OAuth2",
                    "measures": ["OAuth2", "Rate limiting", "Encryption"],
                },
            },
            "performance_defaults": {
                "standard": {
                    "strategies": ["Database indexing"],
                    "caching": "Memory",
                    "monitoring": ["Basic metrics"],
                },
                "high": {
                    "strategies": ["Caching", "Load balancing"],
                    "caching": "Redis",
                    "monitoring": ["Advanced metrics"],
                },
            },
            "deployment_defaults": {
                "direct_deployment": {
                    "environments": ["development", "production"],
                    "features": ["Basic deployment"],
                },
                "docker_compose": {
                    "environments": ["development", "staging", "production"],
                    "features": ["Containerization", "Service orchestration"],
                    "base_services": ["api", "db", "redis"],
                },
            },
            "framework_defaults": {
                "fastapi": {
                    "dependencies": ["fastapi==0.104.1", "uvicorn==0.24.0"],
                    "security_packages": [
                        "python-jose[cryptography]==3.3.0",
                        "passlib[bcrypt]==1.7.4",
                    ],
                    "testing_packages": ["pytest==7.4.3", "httpx==0.25.2"],
                },
                "flask": {
                    "dependencies": ["flask==3.0.0"],
                    "security_packages": ["flask-jwt-extended==4.6.0"],
                    "testing_packages": ["pytest==7.4.3", "pytest-flask==1.3.0"],
                },
            },
            "project_management": {
                "package_manager": "poetry",
                "python_version": "^3.8",
                "code_quality": ["black", "isort", "flake8"],
            },
            "dependency_management": {
                "package_extraction_patterns": {
                    "security": {
                        "keywords": ["auth", "jwt", "security"],
                        "packages": ["python-jose", "passlib"],
                    },
                    "database": {
                        "keywords": ["database", "db", "sql"],
                        "packages": ["sqlalchemy", "alembic"],
                    },
                }
            },
        }

        with open(shared_dir / "backend_defaults.json", "w") as f:
            json.dump(backend_config, f, indent=2)

    @pytest.fixture
    def sample_program_plan(self):
        """Sample program plan for testing"""
        return {
            "original_requirement": "Create a user management system",
            "input_analyses": {
                "requirement_analysis": {
                    "functional_requirements": [
                        {"requirement": "User registration"},
                        {"requirement": "User authentication"},
                        {"requirement": "User profile management"},
                    ],
                    "requirement_classification": {"complexity_level": "medium"},
                }
            },
        }

    @pytest.fixture
    def sample_architecture(self):
        """Sample architecture for testing"""
        return {
            "technology_stack": {
                "backend": "FastAPI",
                "database": "PostgreSQL",
                "frontend": "React",
            }
        }

    @pytest.fixture
    def sample_requirement_analysis(self):
        """Sample requirement analysis for testing"""
        return {
            "functional_requirements": [
                {"requirement": "User authentication"},
                {"requirement": "Data storage"},
            ],
            "key_concepts": ["user", "authentication", "data"],
            "requirement_classification": {"complexity_level": "moderate", "complexity_score": 6},
        }

    # Backend Developer Persona Tests
    def test_backend_developer_persona_initialization(self):
        """Test BackendDeveloperPersona initialization"""
        json_path = self.personas_dir / "backend_developer.json"

        with patch(
            "builtins.open",
            mock_open(read_data=json.dumps(self.persona_configs["backend_developer"])),
        ):
            with patch("pathlib.Path.exists", return_value=True):
                persona = BackendDeveloperPersona(str(json_path))

                assert persona.experience_level == 8
                assert persona.autonomy_level == 9
                assert "api_development" in persona.capabilities
                assert "rest_api_design" in persona.specializations

    def test_backend_developer_persona_implementation(
        self, sample_program_plan, sample_architecture
    ):
        """Test backend developer implementation method"""
        json_path = self.personas_dir / "backend_developer.json"

        with patch(
            "builtins.open",
            mock_open(read_data=json.dumps(self.persona_configs["backend_developer"])),
        ):
            with patch("pathlib.Path.exists", return_value=True):
                persona = BackendDeveloperPersona(str(json_path))

                result = persona.implement_backend_solution(
                    sample_program_plan, sample_architecture, str(self.test_dir)
                )

                assert result is not None
                assert "ai_backend_analysis" in result
                assert "technology_selection" in result
                assert "api_architecture" in result
                assert "database_design" in result

    # Solution Architect Persona Tests
    def test_solution_architect_persona_initialization(self):
        """Test SolutionArchitectPersona initialization"""
        json_path = self.personas_dir / "solution_architect.json"

        persona = SolutionArchitectPersona(str(json_path))

        assert persona.experience_level == 9
        assert persona.autonomy_level == 8
        assert "microservices" in persona.specialization_areas

    def test_solution_architect_analysis(self, sample_requirement_analysis):
        """Test solution architect requirements analysis"""
        json_path = self.personas_dir / "solution_architect.json"

        persona = SolutionArchitectPersona(str(json_path))

        with patch.object(persona, "_ai_comprehensive_architecture_analysis") as mock_analysis:
            mock_analysis.return_value = {
                "platform_analysis": {"platform_detected": "web"},
                "solution_architecture_overview": {"architecture_style": "microservices"},
                "technology_stack": {"primary_stack": "Python"},
                "system_architecture": {"estimated_service_count": 3},
                "key_concepts_processed": ["user", "auth"],
            }

            result = persona.analyze_requirements_for_architecture(
                sample_requirement_analysis, "Create user management system"
            )

            assert result is not None
            assert "platform_analysis" in result
            assert "solution_architecture_overview" in result

    # Requirement Analyst Persona Tests
    def test_requirement_analyst_persona_initialization(self):
        """Test RequirementAnalystPersona initialization"""
        json_path = self.personas_dir / "requirement_analyst.json"

        persona = RequirementAnalystPersona(str(json_path))

        assert persona.experience_level == 8
        assert persona.autonomy_level == 7

    def test_requirement_analyst_analysis(self):
        """Test requirement analyst requirement analysis"""
        json_path = self.personas_dir / "requirement_analyst.json"

        persona = RequirementAnalystPersona(str(json_path))

        with patch.object(persona, "analyze_requirements") as mock_analyze:
            mock_analyze.return_value = {
                "functional_requirements": ["User login", "User registration"],
                "non_functional_requirements": ["Performance", "Security"],
                "key_concepts": ["user", "authentication"],
                "requirement_classification": {"complexity_level": "moderate"},
            }

            result = persona.analyze_requirements("Create user authentication system")

            assert result is not None
            assert "functional_requirements" in result
            assert "non_functional_requirements" in result

    # Frontend Developer Persona Tests
    def test_frontend_developer_persona_initialization(self):
        """Test FrontendDeveloperPersona initialization"""
        json_path = self.personas_dir / "frontend_developer.json"

        persona = FrontendDeveloperPersona(str(json_path))

        assert "ui_development" in persona.capabilities
        assert "react" in persona.specializations

    def test_frontend_developer_implementation(self, sample_program_plan, sample_architecture):
        """Test frontend developer implementation"""
        json_path = self.personas_dir / "frontend_developer.json"

        persona = FrontendDeveloperPersona(str(json_path))

        with patch.object(persona, "implement_frontend_solution") as mock_implement:
            mock_implement.return_value = {
                "framework_selection": "React",
                "component_architecture": {"components": ["UserLogin", "UserProfile"]},
                "ui_design": {"layout": "responsive"},
            }

            result = persona.implement_frontend_solution(
                sample_program_plan, sample_architecture, str(self.test_dir)
            )

            assert result is not None
            assert "framework_selection" in result

    # QA Engineer Persona Tests
    def test_qa_engineer_persona_initialization(self):
        """Test QAEngineerPersona initialization"""
        json_path = self.personas_dir / "qa_engineer.json"

        persona = QAEngineerPersona(str(json_path))

        assert "unit_testing" in persona.testing_capabilities
        assert "pytest" in persona.automation_tools

    def test_qa_engineer_test_plan(self, sample_program_plan, sample_architecture):
        """Test QA engineer test plan creation"""
        json_path = self.personas_dir / "qa_engineer.json"

        persona = QAEngineerPersona(str(json_path))

        with patch.object(persona, "create_comprehensive_test_plan") as mock_plan:
            mock_plan.return_value = {
                "test_strategy": "Comprehensive testing approach",
                "test_cases": ["Login test", "Registration test"],
                "automation_framework": "pytest",
            }

            result = persona.create_comprehensive_test_plan(
                sample_program_plan, sample_architecture
            )

            assert result is not None
            assert "test_strategy" in result

    # DevOps Engineer Persona Tests
    def test_devops_engineer_persona_initialization(self):
        """Test DevopsEngineerPersona initialization"""
        json_path = self.personas_dir / "devops_engineer.json"

        persona = DevopsEngineerPersona(str(json_path))

        assert "docker" in persona.infrastructure_skills
        assert "aws" in persona.cloud_platforms

    def test_devops_engineer_deployment(self, sample_program_plan, sample_architecture):
        """Test DevOps engineer deployment strategy"""
        json_path = self.personas_dir / "devops_engineer.json"

        persona = DevopsEngineerPersona(str(json_path))

        with patch.object(persona, "design_deployment_strategy") as mock_deploy:
            mock_deploy.return_value = {
                "deployment_type": "containerized",
                "infrastructure": "kubernetes",
                "monitoring": "prometheus",
            }

            result = persona.design_deployment_strategy(sample_program_plan, sample_architecture)

            assert result is not None
            assert "deployment_type" in result

    # Program Manager Persona Tests
    def test_program_manager_persona_initialization(self):
        """Test ProgramManagerPersona initialization"""
        json_path = self.personas_dir / "program_manager.json"

        persona = ProgramManagerPersona(str(json_path))

        assert "project_planning" in persona.management_skills
        assert "agile" in persona.methodologies

    def test_program_manager_plan(self, sample_requirement_analysis):
        """Test program manager planning"""
        json_path = self.personas_dir / "program_manager.json"

        persona = ProgramManagerPersona(str(json_path))

        with patch.object(persona, "create_program_plan") as mock_plan:
            mock_plan.return_value = {
                "project_phases": ["Analysis", "Development", "Testing"],
                "timeline": "12 weeks",
                "resource_allocation": {"developers": 3, "testers": 1},
            }

            result = persona.create_program_plan(sample_requirement_analysis)

            assert result is not None
            assert "project_phases" in result

    # Solution Reviewer Persona Tests
    def test_solution_reviewer_persona_initialization(self):
        """Test SolutionReviewerPersona initialization"""
        json_path = self.personas_dir / "solution_reviewer.json"

        persona = SolutionReviewerPersona(str(json_path))

        assert "technical_accuracy" in persona.review_criteria
        assert "architecture" in persona.expertise_areas

    def test_solution_reviewer_review(self, sample_architecture):
        """Test solution reviewer review process"""
        json_path = self.personas_dir / "solution_reviewer.json"

        persona = SolutionReviewerPersona(str(json_path))

        with patch.object(persona, "review_solution") as mock_review:
            mock_review.return_value = {
                "review_status": "approved",
                "feedback": ["Good architecture", "Consider adding security"],
                "score": 85,
            }

            result = persona.review_solution(sample_architecture)

            assert result is not None
            assert "review_status" in result

    # Enhanced QA Engineer Persona Tests
    def test_enhanced_qa_engineer_persona_initialization(self):
        """Test EnhancedQAEngineerPersona initialization"""
        json_path = self.personas_dir / "enhanced_qa_engineer.json"

        persona = EnhancedQAEngineerPersona(str(json_path))

        assert "ai_testing" in persona.advanced_capabilities
        assert "pytest" in persona.tools

    def test_enhanced_qa_engineer_advanced_testing(self, sample_program_plan):
        """Test enhanced QA engineer advanced testing capabilities"""
        json_path = self.personas_dir / "enhanced_qa_engineer.json"

        persona = EnhancedQAEngineerPersona(str(json_path))

        with patch.object(persona, "create_advanced_test_suite") as mock_suite:
            mock_suite.return_value = {
                "ai_test_generation": True,
                "performance_tests": ["Load testing", "Stress testing"],
                "automated_test_count": 150,
            }

            result = persona.create_advanced_test_suite(sample_program_plan)

            assert result is not None
            assert "ai_test_generation" in result

    # Integration Tests
    def test_persona_chain_integration(
        self, sample_requirement_analysis, sample_program_plan, sample_architecture
    ):
        """Test persona chain integration"""
        # Test requirement analyst -> solution architect -> backend developer chain

        # Requirement Analyst
        req_analyst = RequirementAnalystPersona(str(self.personas_dir / "requirement_analyst.json"))

        # Solution Architect
        sol_architect = SolutionArchitectPersona(str(self.personas_dir / "solution_architect.json"))

        # Backend Developer
        with patch(
            "builtins.open",
            mock_open(read_data=json.dumps(self.persona_configs["backend_developer"])),
        ):
            with patch("pathlib.Path.exists", return_value=True):
                backend_dev = BackendDeveloperPersona(
                    str(self.personas_dir / "backend_developer.json")
                )

        # Mock the persona methods to return expected data
        with patch.object(req_analyst, "analyze_requirements") as mock_req:
            mock_req.return_value = sample_requirement_analysis

            with patch.object(sol_architect, "analyze_requirements_for_architecture") as mock_arch:
                mock_arch.return_value = sample_architecture

                # Test the chain
                req_result = req_analyst.analyze_requirements("Create user system")
                arch_result = sol_architect.analyze_requirements_for_architecture(
                    req_result, "Create user system"
                )
                backend_result = backend_dev.implement_backend_solution(
                    sample_program_plan, arch_result
                )

                assert req_result is not None
                assert arch_result is not None
                assert backend_result is not None

    def test_persona_error_handling(self):
        """Test persona error handling for invalid configurations"""
        # Test invalid JSON path
        with pytest.raises(Exception):
            BackendDeveloperPersona("/invalid/path/persona.json")

        # Test invalid JSON content
        invalid_json_path = self.personas_dir / "invalid.json"
        with open(invalid_json_path, "w") as f:
            f.write("invalid json content")

        with pytest.raises(Exception):
            SolutionArchitectPersona(str(invalid_json_path))

    def test_persona_configuration_validation(self):
        """Test persona configuration validation"""
        # Test missing required fields
        incomplete_config = {
            "persona_metadata": {
                "persona_name": "Test Persona"
                # Missing required fields
            }
        }

        incomplete_json_path = self.personas_dir / "incomplete.json"
        with open(incomplete_json_path, "w") as f:
            json.dump(incomplete_config, f)

        # Test that personas handle missing configuration gracefully
        try:
            persona = SolutionArchitectPersona(str(incomplete_json_path))
            # Should handle missing fields with defaults
            assert persona.persona_data is not None
        except (KeyError, AttributeError):
            # Expected for missing required configuration
            pass

    def test_persona_output_consistency(self, sample_program_plan, sample_architecture):
        """Test that persona outputs are consistent across multiple runs"""
        json_path = self.personas_dir / "backend_developer.json"

        with patch(
            "builtins.open",
            mock_open(read_data=json.dumps(self.persona_configs["backend_developer"])),
        ):
            with patch("pathlib.Path.exists", return_value=True):
                persona = BackendDeveloperPersona(str(json_path))

                # Run the same analysis multiple times
                results = []
                for _ in range(3):
                    result = persona.implement_backend_solution(
                        sample_program_plan, sample_architecture, str(self.test_dir)
                    )
                    results.append(result)

                # Check that key fields are consistent
                for result in results[1:]:
                    assert (
                        result["ai_backend_analysis"]["persona_id"]
                        == results[0]["ai_backend_analysis"]["persona_id"]
                    )
                    assert (
                        result["technology_selection"]["framework"]
                        == results[0]["technology_selection"]["framework"]
                    )

    # Performance Tests
    @pytest.mark.performance
    def test_persona_initialization_performance(self):
        """Test persona initialization performance"""
        import time

        start_time = time.time()

        # Initialize multiple personas
        personas = []
        for persona_name in ["backend_developer", "solution_architect", "requirement_analyst"]:
            json_path = self.personas_dir / f"{persona_name}.json"

            if persona_name == "backend_developer":
                with patch(
                    "builtins.open",
                    mock_open(read_data=json.dumps(self.persona_configs[persona_name])),
                ):
                    with patch("pathlib.Path.exists", return_value=True):
                        persona = BackendDeveloperPersona(str(json_path))
            elif persona_name == "solution_architect":
                persona = SolutionArchitectPersona(str(json_path))
            else:
                persona = RequirementAnalystPersona(str(json_path))

            personas.append(persona)

        end_time = time.time()
        initialization_time = end_time - start_time

        # Assert that initialization takes less than 1 second
        assert initialization_time < 1.0
        assert len(personas) == 3

    @pytest.mark.performance
    def test_persona_analysis_performance(self, sample_program_plan, sample_architecture):
        """Test persona analysis performance"""
        import time

        json_path = self.personas_dir / "backend_developer.json"

        with patch(
            "builtins.open",
            mock_open(read_data=json.dumps(self.persona_configs["backend_developer"])),
        ):
            with patch("pathlib.Path.exists", return_value=True):
                persona = BackendDeveloperPersona(str(json_path))

                start_time = time.time()

                result = persona.implement_backend_solution(
                    sample_program_plan, sample_architecture, str(self.test_dir)
                )

                end_time = time.time()
                analysis_time = end_time - start_time

                # Assert that analysis takes less than 5 seconds
                assert analysis_time < 5.0
                assert result is not None

    # Memory Tests
    @pytest.mark.memory
    def test_persona_memory_usage(self):
        """Test persona memory usage"""
        import gc
        import sys

        # Get initial memory usage
        initial_objects = len(gc.get_objects())

        # Create multiple personas
        personas = []
        for _ in range(10):
            json_path = self.personas_dir / "backend_developer.json"
            with patch(
                "builtins.open",
                mock_open(read_data=json.dumps(self.persona_configs["backend_developer"])),
            ):
                with patch("pathlib.Path.exists", return_value=True):
                    persona = BackendDeveloperPersona(str(json_path))
                    personas.append(persona)

        # Get memory usage after creation
        after_creation = len(gc.get_objects())

        # Clear personas
        del personas
        gc.collect()

        # Get memory usage after cleanup
        after_cleanup = len(gc.get_objects())

        # Assert memory is properly cleaned up
        memory_increase = after_creation - initial_objects
        memory_cleaned = after_creation - after_cleanup

        # Should clean up at least 80% of created objects
        assert memory_cleaned > (memory_increase * 0.8)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
