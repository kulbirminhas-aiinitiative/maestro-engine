#!/usr/bin/env python3
"""
Configuration Regression Tests
Ensures configuration system changes don't break existing functionality
"""

import os
from unittest.mock import patch

import pytest
from maestro_config import get_config, load_config, reload_config

# Use Poetry and relative imports instead of hardcoded paths



class TestConfigurationRegression:
    """Regression tests for configuration system"""

    def test_backward_compatibility_service_ports(self):
        """Test that default service ports haven't changed"""

        config = load_config()

        # These port assignments should remain stable
        assert config.orchestration_gateway.port == 8000
        assert config.intelligence_service.port == 8001
        assert config.execution_service.port == 8002
        assert config.quality_service.port == 8003
        assert config.governance_service.port == 8004

    def test_backward_compatibility_default_hosts(self):
        """Test that default hosts haven't changed"""

        config = load_config()

        # All services should default to localhost
        assert config.orchestration_gateway.host == "127.0.0.1"
        assert config.intelligence_service.host == "127.0.0.1"
        assert config.execution_service.host == "127.0.0.1"
        assert config.quality_service.host == "127.0.0.1"
        assert config.governance_service.host == "127.0.0.1"

    def test_environment_variable_names_unchanged(self):
        """Test that environment variable names are stable"""

        expected_env_vars = [
            "ORCHESTRATION_HOST",
            "ORCHESTRATION_PORT",
            "INTELLIGENCE_HOST",
            "INTELLIGENCE_PORT",
            "EXECUTION_HOST",
            "EXECUTION_PORT",
            "QUALITY_HOST",
            "QUALITY_PORT",
            "GOVERNANCE_HOST",
            "GOVERNANCE_PORT",
            "DATABASE_HOST",
            "DATABASE_PORT",
            "DATABASE_NAME",
            "REDIS_HOST",
            "REDIS_PORT",
            "DEBUG",
        ]

        # Test that each environment variable is recognized
        for env_var in expected_env_vars:
            test_value = "test_value"
            if "PORT" in env_var:
                test_value = "9999"
            elif env_var == "DEBUG":
                test_value = "true"

            with patch.dict(os.environ, {env_var: test_value}):
                config = load_config()

                # Verify the environment variable affects configuration
                if env_var == "ORCHESTRATION_HOST":
                    assert config.orchestration_gateway.host == test_value
                elif env_var == "ORCHESTRATION_PORT":
                    assert config.orchestration_gateway.port == 9999
                elif env_var == "DEBUG":
                    assert config.orchestration_gateway.debug == True
                # Add other checks as needed

    def test_database_configuration_stability(self):
        """Test that database configuration structure is stable"""

        config = load_config()

        # Database configuration should have these fields
        assert hasattr(config.database, "host")
        assert hasattr(config.database, "port")
        assert hasattr(config.database, "name")
        assert hasattr(config.database, "user")
        assert hasattr(config.database, "password")

        # Default values should be stable
        assert config.database.host == "localhost"
        assert config.database.port == 5432
        assert config.database.name == "maestro"
        assert config.database.user == "maestro"

    def test_redis_configuration_stability(self):
        """Test that Redis configuration structure is stable"""

        config = load_config()

        # Redis configuration should have these fields
        assert hasattr(config.redis, "host")
        assert hasattr(config.redis, "port")
        assert hasattr(config.redis, "db")
        assert hasattr(config.redis, "password")

        # Default values should be stable
        assert config.redis.host == "localhost"
        assert config.redis.port == 6379
        assert config.redis.db == 0

    def test_coherent_system_config_stability(self):
        """Test that coherent system configuration is stable"""

        config = load_config()

        # Coherent system specific fields should exist
        assert hasattr(config, "blackboard_persistence_db")
        assert hasattr(config, "stigmergy_models_path")
        assert hasattr(config, "coordination_timeout")
        assert hasattr(config, "port_range_start")
        assert hasattr(config, "port_range_end")

        # Default values should be stable
        assert config.coordination_timeout == 300
        assert config.port_range_start == 3000
        assert config.port_range_end == 9000

    def test_service_config_dataclass_stability(self):
        """Test that ServiceConfig dataclass structure is stable"""

        from maestro_config import ServiceConfig

        # Should be able to create with these fields
        service = ServiceConfig(host="test.com", port=8888, debug=True, workers=2)

        assert service.host == "test.com"
        assert service.port == 8888
        assert service.debug == True
        assert service.workers == 2

        # Default values should be stable
        default_service = ServiceConfig()
        assert default_service.host == "127.0.0.1"
        assert default_service.port == 8000
        assert default_service.debug == False
        assert default_service.workers == 1

    def test_url_generation_functions_stable(self):
        """Test that URL generation functions work as expected"""

        from maestro_config import get_database_url, get_redis_url, get_service_url

        config = load_config()

        # Service URLs
        assert get_service_url(config, "orchestration") == "http://127.0.0.1:8000"
        assert get_service_url(config, "intelligence") == "http://127.0.0.1:8001"

        # Database URL
        db_url = get_database_url(config)
        assert db_url.startswith("postgresql://")
        assert "maestro" in db_url

        # Redis URL
        redis_url = get_redis_url(config)
        assert redis_url.startswith("redis://")
        assert "localhost:6379" in redis_url

    def test_global_config_singleton_behavior(self):
        """Test that global configuration behaves as expected"""

        # Multiple calls should return same instance
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

        # Reload should create new instance
        config3 = reload_config()
        assert config3 is not config1

        # But subsequent calls should use new instance
        config4 = get_config()
        assert config4 is config3

    def test_configuration_with_all_env_vars_set(self):
        """Test configuration with all environment variables set"""

        full_env = {
            "ORCHESTRATION_HOST": "orch.example.com",
            "ORCHESTRATION_PORT": "8080",
            "INTELLIGENCE_HOST": "intel.example.com",
            "INTELLIGENCE_PORT": "8081",
            "EXECUTION_HOST": "exec.example.com",
            "EXECUTION_PORT": "8082",
            "QUALITY_HOST": "quality.example.com",
            "QUALITY_PORT": "8083",
            "GOVERNANCE_HOST": "gov.example.com",
            "GOVERNANCE_PORT": "8084",
            "DATABASE_HOST": "db.example.com",
            "DATABASE_PORT": "5433",
            "DATABASE_NAME": "production_maestro",
            "DATABASE_USER": "prod_user",
            "DATABASE_PASSWORD": "prod_password",
            "REDIS_HOST": "redis.example.com",
            "REDIS_PORT": "6380",
            "REDIS_DB": "1",
            "REDIS_PASSWORD": "redis_password",
            "DEBUG": "true",
            "BLACKBOARD_DB_PATH": "/prod/blackboard.db",
            "STIGMERGY_MODELS_PATH": "/prod/models",
            "COORDINATION_TIMEOUT": "600",
        }

        with patch.dict(os.environ, full_env):
            config = load_config()

            # Verify all overrides work
            assert config.orchestration_gateway.host == "orch.example.com"
            assert config.orchestration_gateway.port == 8080
            assert config.database.host == "db.example.com"
            assert config.database.name == "production_maestro"
            assert config.redis.password == "redis_password"
            assert config.blackboard_persistence_db == "/prod/blackboard.db"
            assert config.coordination_timeout == 600

    def test_error_handling_regression(self):
        """Test that error handling works as expected"""

        from maestro_config import get_service_url

        config = load_config()

        # Invalid service name should raise ValueError
        with pytest.raises(ValueError):
            get_service_url(config, "invalid_service")

        # This behavior should remain stable


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
