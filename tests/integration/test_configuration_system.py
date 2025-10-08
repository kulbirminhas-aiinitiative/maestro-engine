#!/usr/bin/env python3
"""
Configuration System Integration Tests
Verifies that the centralized configuration system works correctly
"""

import os
import tempfile
from unittest.mock import patch

import pytest
from maestro_config import (
    DatabaseConfig,
    MaestroConfig,
    RedisConfig,
    ServiceConfig,
    get_config,
    get_database_url,
    get_redis_url,
    get_service_url,
    load_config,
    reload_config,
)

# Use Poetry and relative imports instead of hardcoded paths



class TestMaestroConfiguration:
    """Test the centralized configuration system"""

    def test_default_configuration_loading(self):
        """Test that default configuration loads correctly"""
        config = load_config()

        # Test service configurations
        assert config.orchestration_gateway.host == "127.0.0.1"
        assert config.orchestration_gateway.port == 8000
        assert config.intelligence_service.port == 8001
        assert config.execution_service.port == 8002
        assert config.quality_service.port == 8003
        assert config.governance_service.port == 8004

        # Test database configuration
        assert config.database.host == "localhost"
        assert config.database.port == 5432
        assert config.database.name == "maestro"

        # Test Redis configuration
        assert config.redis.host == "localhost"
        assert config.redis.port == 6379

    def test_environment_variable_override(self):
        """Test that environment variables override defaults"""
        test_env = {
            "ORCHESTRATION_HOST": "0.0.0.0",
            "ORCHESTRATION_PORT": "9000",
            "DATABASE_HOST": "db.example.com",
            "REDIS_HOST": "redis.example.com",
            "DEBUG": "true",
        }

        with patch.dict(os.environ, test_env):
            config = load_config()

            assert config.orchestration_gateway.host == "0.0.0.0"
            assert config.orchestration_gateway.port == 9000
            assert config.orchestration_gateway.debug == True
            assert config.database.host == "db.example.com"
            assert config.redis.host == "redis.example.com"

    def test_service_url_generation(self):
        """Test service URL generation"""
        config = load_config()

        orch_url = get_service_url(config, "orchestration")
        assert orch_url == "http://127.0.0.1:8000"

        intel_url = get_service_url(config, "intelligence")
        assert intel_url == "http://127.0.0.1:8001"

        with pytest.raises(ValueError):
            get_service_url(config, "nonexistent")

    def test_database_url_generation(self):
        """Test database URL generation"""
        config = load_config()
        db_url = get_database_url(config)
        assert db_url == "postgresql://maestro@localhost:5432/maestro"

        # Test with password
        config.database.password = "secret"
        db_url_with_pass = get_database_url(config)
        assert db_url_with_pass == "postgresql://maestro:secret@localhost:5432/maestro"

    def test_redis_url_generation(self):
        """Test Redis URL generation"""
        config = load_config()
        redis_url = get_redis_url(config)
        assert redis_url == "redis://localhost:6379/0"

        # Test with password
        config.redis.password = "redispass"
        redis_url_with_pass = get_redis_url(config)
        assert redis_url_with_pass == "redis://:redispass@localhost:6379/0"

    def test_global_configuration_singleton(self):
        """Test that the global configuration works as singleton"""
        config1 = get_config()
        config2 = get_config()

        # Should be the same instance
        assert config1 is config2

    def test_configuration_reload(self):
        """Test configuration reloading"""
        # Get initial config
        config1 = get_config()
        original_host = config1.orchestration_gateway.host

        # Reload with new environment
        test_env = {"ORCHESTRATION_HOST": "new.host.com"}
        with patch.dict(os.environ, test_env):
            config2 = reload_config()

            assert config2.orchestration_gateway.host == "new.host.com"
            assert config2.orchestration_gateway.host != original_host

    def test_port_range_configuration(self):
        """Test port range configuration"""
        config = load_config()

        assert config.port_range_start == 3000
        assert config.port_range_end == 9000
        assert config.port_range_end > config.port_range_start

    def test_coherent_system_configuration(self):
        """Test coherent system specific configuration"""
        config = load_config()

        assert config.blackboard_persistence_db == "/tmp/maestro-blackboard.db"
        assert config.stigmergy_models_path == "/tmp/maestro-models"
        assert config.coordination_timeout == 300

    def test_service_config_dataclass(self):
        """Test ServiceConfig dataclass functionality"""
        service = ServiceConfig(host="test.com", port=9999, debug=True, workers=4)

        assert service.host == "test.com"
        assert service.port == 9999
        assert service.debug == True
        assert service.workers == 4

    def test_database_config_dataclass(self):
        """Test DatabaseConfig dataclass functionality"""
        db = DatabaseConfig(
            host="db.test.com", port=5433, name="test_db", user="test_user", password="test_pass"
        )

        assert db.host == "db.test.com"
        assert db.port == 5433
        assert db.name == "test_db"
        assert db.user == "test_user"
        assert db.password == "test_pass"

    def test_redis_config_dataclass(self):
        """Test RedisConfig dataclass functionality"""
        redis = RedisConfig(host="redis.test.com", port=6380, db=1, password="redis_pass")

        assert redis.host == "redis.test.com"
        assert redis.port == 6380
        assert redis.db == 1
        assert redis.password == "redis_pass"

    def test_configuration_with_missing_env_vars(self):
        """Test that configuration works with missing environment variables"""
        # Clear potential environment variables
        env_vars_to_clear = [
            "ORCHESTRATION_HOST",
            "ORCHESTRATION_PORT",
            "DATABASE_HOST",
            "REDIS_HOST",
            "DEBUG",
        ]

        # Don't set None values, just clear the environment
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()

            # Should fall back to defaults
            assert config.orchestration_gateway.host == "127.0.0.1"
            assert config.orchestration_gateway.port == 8000
            assert config.orchestration_gateway.debug == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
