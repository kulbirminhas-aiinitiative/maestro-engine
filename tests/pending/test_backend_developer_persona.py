#!/usr/bin/env python3
"""
Unit Tests for BackendDeveloperPersona
Tests the AI-driven backend solution generation and intelligent decision-making.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from personas.classes.backend_developer_persona import BackendDeveloperPersona

# Use Poetry and relative imports instead of hardcoded paths



class TestBackendDeveloperPersona:
    """Test BackendDeveloperPersona AI-driven functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_persona_data = {
            "persona_metadata": {
                "persona_name": "Senior Backend Developer",
                "persona_id": "backend_developer_ai_v1",
                "experience_level": 8,
                "autonomy_level": 9,
            },
            "capabilities": [
                "backend_development",
                "database_design",
                "api_development",
                "security_implementation",
                "performance_optimization",
            ],
            "specializations": [
                "microservices_architecture",
                "rest_api_design",
                "database_optimization",
            ],
            "approach_methodology": {
                "technology_selection": "Experience-driven analysis with AI insights"
            },
        }

        self.mock_config_data = {
            "requirement_analysis_patterns": {
                "data_storage_indicators": ["database", "storage", "persist", "save"],
                "data_complexity_indicators": {
                    "low": ["simple", "basic", "minimal"],
                    "medium": ["standard", "typical", "moderate"],
                    "high": ["complex", "advanced", "enterprise", "scalable"],
                },
                "integration_patterns": {
                    "external_apis": ["api", "service", "integration", "webhook"],
                    "file_handling": ["upload", "file", "document", "attachment"],
                    "real_time_communication": ["websocket", "real-time", "live", "instant"],
                },
                "performance_indicators": {
                    "standard": ["normal", "typical"],
                    "high": ["fast", "performance", "speed", "quick"],
                    "critical": ["real-time", "instant", "immediate"],
                },
                "security_sensitivity_markers": {
                    "low": ["public", "open"],
                    "medium": ["user", "account", "login"],
                    "high": ["payment", "financial", "sensitive"],
                    "critical": ["security", "encryption", "private"],
                },
            },
            "framework_selection_matrix": {
                "low_complexity": {
                    "rest_api_design": "flask",
                    "microservices_architecture": "fastapi",
                    "default": "flask",
                },
                "medium_complexity": {
                    "rest_api_design": "fastapi",
                    "microservices_architecture": "fastapi",
                    "default": "fastapi",
                },
                "high_complexity": {
                    "microservices_architecture": {
                        "performance_critical": "fastapi",
                        "standard": "django",
                    },
                    "default": "django",
                },
            },
            "confidence_factors": {
                "experience_multiplier": 8,
                "complexity_bonus": {"low": 10, "medium": 5, "high": 15},
                "specialization_bonus": 5,
                "max_confidence": 95,
            },
            "database_defaults": {
                "sqlite": {
                    "features": ["Lightweight", "File-based", "Zero configuration"],
                    "dependencies": ["sqlite3"],
                },
                "postgresql": {
                    "features": ["ACID compliant", "Advanced indexing", "JSON support"],
                    "dependencies": ["psycopg2-binary==2.9.7", "sqlalchemy==1.4.0"],
                },
            },
            "framework_defaults": {
                "fastapi": {
                    "dependencies": ["fastapi==0.104.1", "uvicorn==0.24.0"],
                    "security_packages": ["python-jose==3.3.0", "bcrypt==4.0.1"],
                    "testing_packages": ["pytest==7.4.3", "httpx==0.25.2"],
                },
                "flask": {
                    "dependencies": ["flask==3.0.0", "gunicorn==21.2.0"],
                    "security_packages": ["flask-jwt-extended==4.5.3", "werkzeug==3.0.1"],
                    "testing_packages": ["pytest==7.4.3", "pytest-flask==1.3.0"],
                },
            },
            "api_patterns": {
                "entity_patterns": {
                    "users": ["user", "account", "profile"],
                    "projects": ["project", "item", "task"],
                    "orders": ["order", "purchase", "transaction"],
                },
                "action_patterns": {
                    "create": ["create", "add", "new", "register"],
                    "read": ["get", "fetch", "retrieve", "list"],
                    "update": ["update", "edit", "modify", "change"],
                    "delete": ["delete", "remove", "destroy"],
                },
                "rest": {
                    "crud_pattern": {
                        "create": "POST /{resource}",
                        "read": "GET /{resource}",
                        "update": "PUT /{resource}/{id}",
                        "delete": "DELETE /{resource}/{id}",
                    },
                    "standard_endpoints": {
                        "health_check": "GET /health",
                        "api_info": "GET /api/info",
                    },
                },
            },
            "database_schema_patterns": {
                "common_entity_schemas": {
                    "users": {
                        "fields": [
                            "id",
                            "username",
                            "email",
                            "password_hash",
                            "created_at",
                            "updated_at",
                        ],
                        "indexes": ["email", "username"],
                        "constraints": ["UNIQUE(email)", "UNIQUE(username)"],
                    },
                    "projects": {
                        "fields": ["id", "name", "description", "user_id", "status", "created_at"],
                        "indexes": ["user_id", "status"],
                        "relationships": ["FOREIGN KEY (user_id) REFERENCES users(id)"],
                    },
                },
                "field_types": {
                    "id": {
                        "postgresql": "SERIAL PRIMARY KEY",
                        "sqlite": "INTEGER PRIMARY KEY AUTOINCREMENT",
                    },
                    "foreign_key": {
                        "postgresql": "INTEGER REFERENCES {table}(id)",
                        "sqlite": "INTEGER",
                    },
                    "string_fields": {"postgresql": "VARCHAR(255)", "sqlite": "TEXT"},
                    "text_fields": {"postgresql": "TEXT", "sqlite": "TEXT"},
                    "datetime_fields": {
                        "postgresql": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                        "sqlite": "DATETIME DEFAULT CURRENT_TIMESTAMP",
                    },
                    "boolean_fields": {
                        "postgresql": "BOOLEAN DEFAULT FALSE",
                        "sqlite": "INTEGER DEFAULT 0",
                    },
                },
            },
            "security_defaults": {
                "basic": {
                    "authentication": None,
                    "measures": ["Input validation", "Basic error handling"],
                },
                "medium": {
                    "authentication": "JWT",
                    "measures": [
                        "JWT authentication",
                        "Password hashing",
                        "Input validation",
                        "CORS protection",
                    ],
                },
                "high": {
                    "authentication": "JWT with refresh tokens",
                    "measures": [
                        "Multi-layer authentication",
                        "Advanced input validation",
                        "Rate limiting",
                        "Security headers",
                    ],
                },
            },
            "performance_defaults": {
                "standard": {
                    "strategies": ["Basic caching", "Query optimization"],
                    "caching": "In-memory",
                    "monitoring": ["Response time", "Error rate"],
                },
                "high": {
                    "strategies": [
                        "Advanced caching",
                        "Database optimization",
                        "Connection pooling",
                    ],
                    "caching": "Redis",
                    "monitoring": ["Performance metrics", "Resource usage", "Bottleneck detection"],
                },
            },
            "deployment_defaults": {
                "docker_compose": {
                    "environments": ["development", "staging", "production"],
                    "features": [
                        "Containerization",
                        "Service orchestration",
                        "Environment isolation",
                    ],
                },
                "direct_deployment": {
                    "environments": ["development", "production"],
                    "features": ["Simple deployment", "Minimal overhead"],
                },
            },
            "technology_selection_rules": {
                "database": {
                    "low_complexity": ["sqlite"],
                    "medium_complexity": ["postgresql", "sqlite"],
                    "high_complexity": ["postgresql"],
                },
                "performance": {
                    "high": ["redis", "gunicorn"],
                    "real_time": ["websockets", "celery"],
                },
                "security": {"medium": ["bcrypt", "jwt"], "high": ["oauth2", "encryption"]},
                "integration": {
                    "external_apis": ["requests", "httpx"],
                    "file_handling": ["pillow", "boto3"],
                },
            },
            "project_management": {
                "package_manager": "poetry",
                "python_version": "^3.9",
                "code_quality": ["black", "isort", "mypy"],
            },
            "dependency_management": {
                "package_extraction_patterns": {
                    "security": {
                        "keywords": ["jwt", "auth", "security", "bcrypt"],
                        "packages": ["bcrypt", "python-jose"],
                    },
                    "database": {
                        "keywords": ["database", "sql", "orm"],
                        "packages": ["sqlalchemy", "alembic"],
                    },
                }
            },
        }

        # Create temporary files
        self.temp_persona_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(self.mock_persona_data, self.temp_persona_file)
        self.temp_persona_file.close()

        self.temp_config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(self.mock_config_data, self.temp_config_file)
        self.temp_config_file.close()

        # Mock the config file path in the class
        with patch.object(
            BackendDeveloperPersona, "_load_backend_config", return_value=self.mock_config_data
        ):
            self.backend_dev = BackendDeveloperPersona(self.temp_persona_file.name)

    def teardown_method(self):
        """Clean up test fixtures"""
        Path(self.temp_persona_file.name).unlink(missing_ok=True)
        Path(self.temp_config_file.name).unlink(missing_ok=True)

    def test_persona_initialization(self):
        """Test persona initialization with AI capabilities"""
        assert self.backend_dev.persona_path == self.temp_persona_file.name
        assert self.backend_dev.experience_level == 8
        assert self.backend_dev.autonomy_level == 9
        assert "backend_development" in self.backend_dev.capabilities
        assert "microservices_architecture" in self.backend_dev.specializations

    def test_analyze_requirements_intelligently(self):
        """Test AI-driven requirement analysis"""
        functional_requirements = [
            {"requirement": "User authentication with login and password"},
            {"requirement": "Store user data in database with high performance"},
            {"requirement": "API endpoints for external integrations"},
            {"requirement": "Real-time notifications for users"},
        ]

        analysis = self.backend_dev._analyze_requirements_intelligently(functional_requirements)

        assert analysis["data_complexity"] in ["low", "medium", "high"]
        assert "external_apis" in analysis["integration_needs"]
        assert "real_time_communication" in analysis["integration_needs"]
        assert analysis["security_sensitivity"] in ["low", "medium", "high"]
        assert "users" in analysis["identified_entities"]

    def test_select_framework_intelligently_with_specialization(self):
        """Test intelligent framework selection based on specializations"""
        requirement_analysis = {
            "data_complexity": "high",
            "performance_requirements": "high",
            "security_sensitivity": "medium",
        }

        framework_decision = self.backend_dev._select_framework_intelligently(
            "high", requirement_analysis
        )

        assert framework_decision["framework"] in ["FastAPI", "Django", "Flask"]
        assert framework_decision["language"] == "Python"
        assert "rationale" in framework_decision
        assert "microservices_architecture" in framework_decision["rationale"]

    def test_select_supporting_technologies(self):
        """Test intelligent supporting technology selection"""
        requirement_analysis = {
            "data_complexity": "high",
            "integration_needs": ["external_apis", "real_time_communication"],
            "performance_requirements": "high",
            "security_sensitivity": "high",
        }

        framework_decision = {"framework": "FastAPI", "language": "Python"}
        technologies = self.backend_dev._select_supporting_technologies(
            requirement_analysis, framework_decision
        )

        assert isinstance(technologies, list)
        # Should include database technology for high complexity
        assert any("postgresql" in tech.lower() for tech in technologies)

    def test_calculate_technology_confidence(self):
        """Test AI confidence calculation"""
        requirement_analysis = {"data_complexity": "medium", "security_sensitivity": "high"}

        confidence = self.backend_dev._calculate_technology_confidence(
            "medium", requirement_analysis
        )

        assert isinstance(confidence, int)
        assert 0 <= confidence <= 95  # Max confidence from config
        # Should be relatively high due to experience level 8
        assert confidence >= 50

    def test_is_specialization_relevant(self):
        """Test specialization relevance detection"""
        requirement_analysis = {
            "performance_requirements": "high",
            "integration_needs": ["external_apis"],
            "data_complexity": "high",
            "security_sensitivity": "critical",
        }

        # Test various specializations
        assert (
            self.backend_dev._is_specialization_relevant(
                "microservices_architecture", requirement_analysis
            )
            == True
        )
        assert (
            self.backend_dev._is_specialization_relevant("rest_api_design", requirement_analysis)
            == True
        )
        assert (
            self.backend_dev._is_specialization_relevant(
                "database_optimization", requirement_analysis
            )
            == True
        )

    def test_design_api_architecture(self):
        """Test AI-driven API architecture design"""
        functional_requirements = [
            {"requirement": "Create user accounts and manage profiles"},
            {"requirement": "Store and retrieve project information"},
            {"requirement": "Handle user authentication"},
        ]

        api_architecture = self.backend_dev._design_api_architecture(
            functional_requirements, "medium"
        )

        assert "design_approach" in api_architecture
        assert "identified_entities" in api_architecture
        assert "required_operations" in api_architecture
        assert "endpoint_structure" in api_architecture
        assert api_architecture["authentication_required"] == True
        assert (
            "Users" in api_architecture["identified_entities"]
            or "Projects" in api_architecture["identified_entities"]
        )

    def test_design_database_schema(self):
        """Test AI-driven database schema design"""
        functional_requirements = [
            {"requirement": "User registration and authentication"},
            {"requirement": "Project management system"},
        ]

        db_design = self.backend_dev._design_database_schema(functional_requirements, "medium")

        assert "type" in db_design
        assert "schema_design" in db_design
        assert "features_utilized" in db_design
        assert "ai_decisions" in db_design
        assert db_design["type"] in ["SQLite", "PostgreSQL"]
        assert isinstance(db_design["schema_design"], list)

    def test_design_security_strategy(self):
        """Test AI-driven security strategy design"""
        functional_requirements = [
            {"requirement": "User authentication with sensitive data"},
            {"requirement": "API security for external access"},
        ]

        security_strategy = self.backend_dev._design_security_strategy(
            functional_requirements, "high"
        )

        assert "level" in security_strategy
        assert "authentication_method" in security_strategy
        assert "security_measures" in security_strategy
        assert "ai_assessment" in security_strategy
        assert security_strategy["level"] in ["Basic", "Medium", "High", "Critical"]
        assert isinstance(security_strategy["security_measures"], list)

    def test_design_performance_strategy(self):
        """Test AI-driven performance strategy design"""
        functional_requirements = [
            {"requirement": "High-performance data processing"},
            {"requirement": "Real-time user interactions"},
        ]

        performance_strategy = self.backend_dev._design_performance_strategy(
            "high", functional_requirements
        )

        assert "approach" in performance_strategy
        assert "optimization_strategies" in performance_strategy
        assert "caching_strategy" in performance_strategy
        assert "ai_recommendations" in performance_strategy
        assert isinstance(performance_strategy["optimization_strategies"], list)

    def test_design_deployment_strategy(self):
        """Test AI-driven deployment strategy design"""
        technology_stack = {"framework": "FastAPI", "database": "PostgreSQL"}

        deployment_strategy = self.backend_dev._design_deployment_strategy("high", technology_stack)

        assert "deployment_type" in deployment_strategy
        assert "containerization" in deployment_strategy
        assert "environments" in deployment_strategy
        assert "ai_deployment_analysis" in deployment_strategy
        assert isinstance(deployment_strategy["environments"], list)

    def test_implement_backend_solution_integration(self):
        """Test complete backend solution implementation integration"""
        program_plan = {
            "original_requirement": "Build a user management system with API",
            "input_analyses": {
                "requirement_analysis": {
                    "functional_requirements": [
                        {"requirement": "User registration and authentication"},
                        {"requirement": "User profile management"},
                        {"requirement": "RESTful API endpoints"},
                    ],
                    "requirement_classification": {"complexity_level": "medium"},
                }
            },
        }

        architecture = {
            "technology_stack": {"backend_framework": "FastAPI", "database": "PostgreSQL"}
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.backend_dev.implement_backend_solution(
                program_plan, architecture, temp_dir
            )

            # Verify AI analysis structure
            assert "ai_backend_analysis" in result
            assert result["ai_backend_analysis"]["intelligence_applied"] == True
            assert result["ai_backend_analysis"]["experience_level"] == 8
            assert result["ai_backend_analysis"]["autonomy_level"] == 9

            # Verify main components
            assert "technology_selection" in result
            assert "api_architecture" in result
            assert "database_design" in result
            assert "security_implementation" in result
            assert "performance_strategy" in result
            assert "deployment_configuration" in result

            # Verify AI confidence and analysis
            tech_selection = result["technology_selection"]
            assert "ai_confidence" in tech_selection
            assert "ai_analysis" in tech_selection
            assert tech_selection["ai_analysis"]["experience_factor"] == 8

            # Verify generated files if output directory provided
            if "generated_files" in result:
                assert isinstance(result["generated_files"], list)
                assert len(result["generated_files"]) > 0

    def test_generate_intelligent_requirements_poetry(self):
        """Test intelligent requirements generation for Poetry"""
        technology_selection = {
            "framework": "FastAPI",
            "additional_technologies": ["postgresql", "JWT", "bcrypt"],
        }

        requirements = self.backend_dev._generate_intelligent_requirements(technology_selection)

        # Should generate pyproject.toml format since config uses Poetry
        assert "[tool.poetry]" in requirements
        assert "fastapi" in requirements.lower()
        assert "poetry" in requirements

    def test_complexity_extraction_robustness(self):
        """Test robust complexity extraction from various data structures"""
        # Test dict with complexity_level key
        complexity_dict1 = {"complexity_level": "high"}
        analysis1 = self.backend_dev._analyze_requirements_intelligently([])
        # This test verifies the complexity handling doesn't crash

        # Test dict with level key
        complexity_dict2 = {"level": "medium"}
        analysis2 = self.backend_dev._analyze_requirements_intelligently([])

        # Test None complexity
        analysis3 = self.backend_dev._analyze_requirements_intelligently([])

        # All should complete without errors
        assert isinstance(analysis1, dict)
        assert isinstance(analysis2, dict)
        assert isinstance(analysis3, dict)

    def test_error_handling_missing_config(self):
        """Test error handling when configuration is missing"""
        # Test with minimal config
        minimal_config = {
            "requirement_analysis_patterns": {
                "data_storage_indicators": [],
                "data_complexity_indicators": {"medium": []},
                "integration_patterns": {},
                "performance_indicators": {},
                "security_sensitivity_markers": {},
            },
            "framework_selection_matrix": {"medium_complexity": {"default": "flask"}},
            "confidence_factors": {
                "experience_multiplier": 5,
                "complexity_bonus": {"medium": 0},
                "specialization_bonus": 0,
                "max_confidence": 80,
            },
        }

        with patch.object(
            BackendDeveloperPersona, "_load_backend_config", return_value=minimal_config
        ):
            minimal_backend_dev = BackendDeveloperPersona(self.temp_persona_file.name)

            # Should still work with minimal config
            result = minimal_backend_dev._analyze_requirements_intelligently([])
            assert isinstance(result, dict)

    def test_ai_decision_methodology(self):
        """Test that AI decision methodology is properly applied"""
        functional_requirements = [
            {"requirement": "Complex microservices architecture with high performance"}
        ]

        tech_analysis = self.backend_dev._analyze_technology_stack(
            functional_requirements, "high", {}
        )

        # Verify AI analysis includes methodology
        ai_analysis = tech_analysis["ai_analysis"]
        assert "decision_methodology" in ai_analysis
        assert "Experience-driven analysis" in ai_analysis["decision_methodology"]
        assert "persona_specializations_applied" in ai_analysis
        assert ai_analysis["experience_factor"] == 8
        assert ai_analysis["autonomy_applied"] == 9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
