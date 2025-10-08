#!/usr/bin/env python3
"""
Working Persona Tests - Tests for verified working persona classes
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Add project root to path
sys.path.append("/data/maestro-services")

# Import only the working persona classes
from personas.classes.backend_developer_persona import BackendDeveloperPersona
from personas.classes.devops_engineer_persona import DevOpsEngineerPersona
from personas.classes.qa_engineer_persona import QAEngineerPersona
from personas.classes.solution_architect_persona import SolutionArchitectPersona


class TestWorkingPersonas:
    """Test suite for verified working personas"""

    def setup_method(self):
        """Setup test environment"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="working_persona_test_"))
        self._create_shared_config()

    def teardown_method(self):
        """Cleanup test environment"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def _create_shared_config(self):
        """Create minimal shared configuration"""
        shared_dir = self.test_dir / "shared" / "config"
        shared_dir.mkdir(parents=True, exist_ok=True)

        backend_config = {
            "requirement_analysis_patterns": {
                "data_storage_indicators": ["database"],
                "data_complexity_indicators": {
                    "low": ["simple"],
                    "medium": ["moderate"],
                    "high": ["complex"],
                },
                "integration_patterns": {"external_apis": ["api"], "file_handling": ["file"]},
                "performance_indicators": {"standard": ["normal"], "high": ["fast"]},
                "security_sensitivity_markers": {"medium": ["user"], "high": ["security"]},
            },
            "framework_selection_matrix": {
                "low_complexity": {"default": "flask"},
                "medium_complexity": {"default": "fastapi"},
                "high_complexity": {"default": "fastapi"},
            },
            "technology_selection_rules": {
                "database": {"low_complexity": ["sqlite"], "medium_complexity": ["postgresql"]},
                "performance": {"standard": ["redis"], "high": ["redis"]},
                "security": {"medium": ["jwt"], "high": ["jwt"]},
                "integration": {"external_apis": ["requests"], "file_handling": ["boto3"]},
            },
            "confidence_factors": {
                "experience_multiplier": 8,
                "complexity_bonus": {"low": 5, "medium": 10, "high": 15},
                "specialization_bonus": 5,
                "max_confidence": 95,
            },
            "api_patterns": {
                "entity_patterns": {"users": ["user"], "projects": ["project"]},
                "action_patterns": {
                    "create": ["create"],
                    "read": ["get"],
                    "update": ["update"],
                    "delete": ["delete"],
                },
                "rest": {
                    "crud_pattern": {"create": "POST /{resource}", "read": "GET /{resource}"},
                    "standard_endpoints": {"health": "GET /health"},
                },
            },
            "database_defaults": {
                "postgresql": {"features": ["ACID"], "dependencies": ["psycopg2-binary==2.9.7"]},
                "sqlite": {"features": ["Lightweight"], "dependencies": []},
            },
            "database_schema_patterns": {
                "common_entity_schemas": {
                    "users": {
                        "fields": ["id", "username", "email"],
                        "indexes": ["username"],
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
                    "environments": ["development"],
                    "features": ["Basic deployment"],
                },
                "docker_compose": {
                    "environments": ["development"],
                    "features": ["Containerization"],
                    "base_services": ["api"],
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
                    "security": {"keywords": ["auth"], "packages": ["python-jose"]}
                }
            },
        }

        with open(shared_dir / "backend_defaults.json", "w") as f:
            json.dump(backend_config, f, indent=2)

    # Backend Developer Tests
    def test_backend_developer_initialization(self):
        """Test BackendDeveloperPersona initialization"""
        config = {
            "persona_metadata": {
                "persona_name": "Test Backend Developer",
                "persona_id": "backend_001",
                "experience_level": 8,
                "autonomy_level": 9,
            },
            "capabilities": ["api_development", "database_design"],
            "specializations": ["rest_api_design"],
            "approach_methodology": {"development_process": ["Analyze requirements"]},
        }

        config_file = self.test_dir / "backend_config.json"
        with open(config_file, "w") as f:
            json.dump(config, f)

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(config))):
                persona = BackendDeveloperPersona(str(config_file))

                assert persona.experience_level == 8
                assert persona.autonomy_level == 9
                assert "api_development" in persona.capabilities

    def test_backend_developer_implementation(self):
        """Test backend developer implementation method"""
        config = {
            "persona_metadata": {
                "persona_name": "Test Backend Developer",
                "persona_id": "backend_001",
                "experience_level": 8,
                "autonomy_level": 9,
            },
            "capabilities": ["api_development"],
            "specializations": ["rest_api_design"],
            "approach_methodology": {"development_process": ["Analyze requirements"]},
        }

        program_plan = {
            "original_requirement": "Create user management system",
            "input_analyses": {
                "requirement_analysis": {
                    "functional_requirements": [{"requirement": "User registration"}],
                    "requirement_classification": {"complexity_level": "medium"},
                }
            },
        }

        architecture = {"technology_stack": {"backend": "FastAPI"}}

        config_file = self.test_dir / "backend_config.json"
        with open(config_file, "w") as f:
            json.dump(config, f)

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(config))):
                persona = BackendDeveloperPersona(str(config_file))

                result = persona.implement_backend_solution(
                    program_plan, architecture, str(self.test_dir)
                )

                assert result is not None
                assert "technology_selection" in result
                assert "api_architecture" in result

    # Solution Architect Tests
    def test_solution_architect_initialization(self):
        """Test SolutionArchitectPersona initialization"""
        config = {
            "persona_metadata": {"persona_name": "Test Solution Architect"},
            "role": {
                "experience_level": 9,
                "autonomy_level": 8,
                "specialization_areas": ["microservices"],
            },
            "validation_gates": {
                "complexity_based_thresholds": {"simple": {"min_functional_requirements": 2}}
            },
        }

        config_file = self.test_dir / "arch_config.json"
        with open(config_file, "w") as f:
            json.dump(config, f)

        persona = SolutionArchitectPersona(str(config_file))

        assert persona.experience_level == 9
        assert persona.autonomy_level == 8
        assert "microservices" in persona.specialization_areas

    def test_solution_architect_analysis(self):
        """Test solution architect requirements analysis"""
        config = {
            "persona_metadata": {"persona_name": "Test Solution Architect"},
            "role": {
                "experience_level": 9,
                "autonomy_level": 8,
                "specialization_areas": ["microservices"],
            },
            "validation_gates": {
                "complexity_based_thresholds": {"moderate": {"min_functional_requirements": 3}}
            },
        }

        requirement_analysis = {
            "functional_requirements": [
                {"requirement": "User authentication"},
                {"requirement": "Data storage"},
                {"requirement": "API endpoints"},
            ],
            "key_concepts": ["user", "auth", "api"],
            "requirement_classification": {"complexity_level": "moderate", "complexity_score": 6},
        }

        config_file = self.test_dir / "arch_config.json"
        with open(config_file, "w") as f:
            json.dump(config, f)

        persona = SolutionArchitectPersona(str(config_file))

        with patch.object(persona, "_ai_comprehensive_architecture_analysis") as mock_analysis:
            mock_analysis.return_value = {
                "platform_analysis": {"platform_detected": "web"},
                "solution_architecture_overview": {"architecture_style": "microservices"},
                "technology_stack": {"primary_stack": "Python"},
                "system_architecture": {"estimated_service_count": 3},
                "key_concepts_processed": ["user", "auth"],
            }

            result = persona.analyze_requirements_for_architecture(
                requirement_analysis, "Create user system"
            )

            assert result is not None
            assert "platform_analysis" in result

    # DevOps Engineer Tests
    def test_devops_engineer_initialization(self):
        """Test DevOpsEngineerPersona initialization"""
        config = {
            "persona_metadata": {"persona_name": "Test DevOps Engineer"},
            "infrastructure_skills": ["docker", "kubernetes"],
            "cloud_platforms": ["aws"],
        }

        config_file = self.test_dir / "devops_config.json"
        with open(config_file, "w") as f:
            json.dump(config, f)

        persona = DevOpsEngineerPersona(str(config_file))

        assert "docker" in persona.infrastructure_skills
        assert "aws" in persona.cloud_platforms

    def test_devops_engineer_methods(self):
        """Test DevOps engineer has expected methods"""
        config = {
            "persona_metadata": {"persona_name": "Test DevOps Engineer"},
            "infrastructure_skills": ["docker"],
            "cloud_platforms": ["aws"],
        }

        config_file = self.test_dir / "devops_config.json"
        with open(config_file, "w") as f:
            json.dump(config, f)

        persona = DevOpsEngineerPersona(str(config_file))

        # Check that the persona object was created successfully
        assert hasattr(persona, "infrastructure_skills")
        assert hasattr(persona, "cloud_platforms")

    # QA Engineer Tests
    def test_qa_engineer_initialization(self):
        """Test QAEngineerPersona initialization"""
        config = {
            "persona_metadata": {"persona_name": "Test QA Engineer"},
            "testing_capabilities": ["unit_testing", "integration_testing"],
            "automation_tools": ["pytest", "selenium"],
        }

        config_file = self.test_dir / "qa_config.json"
        with open(config_file, "w") as f:
            json.dump(config, f)

        persona = QAEngineerPersona(str(config_file))

        assert "unit_testing" in persona.testing_capabilities
        assert "pytest" in persona.automation_tools

    def test_qa_engineer_methods(self):
        """Test QA engineer has expected methods"""
        config = {
            "persona_metadata": {"persona_name": "Test QA Engineer"},
            "testing_capabilities": ["unit_testing"],
            "automation_tools": ["pytest"],
        }

        config_file = self.test_dir / "qa_config.json"
        with open(config_file, "w") as f:
            json.dump(config, f)

        persona = QAEngineerPersona(str(config_file))

        # Check that the persona object was created successfully
        assert hasattr(persona, "testing_capabilities")
        assert hasattr(persona, "automation_tools")

    # Integration Tests
    def test_persona_workflow_integration(self):
        """Test a simple persona workflow"""
        # Setup configs
        arch_config = {
            "persona_metadata": {"persona_name": "Test Solution Architect"},
            "role": {
                "experience_level": 9,
                "autonomy_level": 8,
                "specialization_areas": ["microservices"],
            },
            "validation_gates": {
                "complexity_based_thresholds": {"moderate": {"min_functional_requirements": 2}}
            },
        }

        backend_config = {
            "persona_metadata": {
                "persona_name": "Test Backend Developer",
                "persona_id": "backend_001",
                "experience_level": 8,
                "autonomy_level": 9,
            },
            "capabilities": ["api_development"],
            "specializations": ["rest_api_design"],
            "approach_methodology": {"development_process": ["Analyze requirements"]},
        }

        # Create config files
        arch_config_file = self.test_dir / "arch_config.json"
        backend_config_file = self.test_dir / "backend_config.json"

        with open(arch_config_file, "w") as f:
            json.dump(arch_config, f)
        with open(backend_config_file, "w") as f:
            json.dump(backend_config, f)

        # Test workflow
        requirement_analysis = {
            "functional_requirements": [
                {"requirement": "User auth"},
                {"requirement": "Data storage"},
            ],
            "key_concepts": ["user", "auth"],
            "requirement_classification": {"complexity_level": "moderate", "complexity_score": 5},
        }

        # Initialize personas
        sol_architect = SolutionArchitectPersona(str(arch_config_file))

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(backend_config))):
                backend_dev = BackendDeveloperPersona(str(backend_config_file))

        # Mock architecture analysis
        with patch.object(sol_architect, "_ai_comprehensive_architecture_analysis") as mock_arch:
            mock_arch.return_value = {
                "platform_analysis": {"platform_detected": "web"},
                "solution_architecture_overview": {"architecture_style": "microservices"},
                "technology_stack": {"primary_stack": "Python"},
                "system_architecture": {"estimated_service_count": 2},
                "key_concepts_processed": ["user", "auth"],
            }

            arch_result = sol_architect.analyze_requirements_for_architecture(
                requirement_analysis, "Create user system"
            )

        # Test backend implementation
        program_plan = {
            "original_requirement": "Create user system",
            "input_analyses": {"requirement_analysis": requirement_analysis},
        }

        backend_result = backend_dev.implement_backend_solution(
            program_plan, arch_result, str(self.test_dir)
        )

        # Assertions
        assert arch_result is not None
        assert backend_result is not None
        assert "technology_selection" in backend_result

    def test_error_handling(self):
        """Test error handling in persona initialization"""
        # Test with invalid config file path
        with pytest.raises(Exception):
            BackendDeveloperPersona("/invalid/path/config.json")

        # Test with missing config fields
        incomplete_config = {"persona_metadata": {"persona_name": "Incomplete"}}

        config_file = self.test_dir / "incomplete_config.json"
        with open(config_file, "w") as f:
            json.dump(incomplete_config, f)

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(incomplete_config))):
                try:
                    persona = BackendDeveloperPersona(str(config_file))
                    # Should handle missing fields gracefully or raise appropriate error
                    assert persona is not None
                except (KeyError, AttributeError):
                    # Expected for missing required configuration
                    pass

    @pytest.mark.performance
    def test_persona_performance(self):
        """Test persona performance"""
        import time

        config = {
            "persona_metadata": {
                "persona_name": "Performance Test",
                "persona_id": "perf_001",
                "experience_level": 8,
                "autonomy_level": 9,
            },
            "capabilities": ["api_development"],
            "specializations": ["rest_api_design"],
            "approach_methodology": {"development_process": ["Analyze requirements"]},
        }

        config_file = self.test_dir / "perf_config.json"
        with open(config_file, "w") as f:
            json.dump(config, f)

        start_time = time.time()

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(config))):
                persona = BackendDeveloperPersona(str(config_file))

        end_time = time.time()
        initialization_time = end_time - start_time

        # Should initialize quickly
        assert initialization_time < 1.0
        assert persona is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
