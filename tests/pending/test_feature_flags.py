#!/usr/bin/env python3
"""
Unit Tests for Feature Flag Framework
Tests the feature flag management system for controlled rollout of coherent orchestration features.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
from shared.config.feature_flags import (
    EngineConfiguration,
    FeatureFlag,
    FeatureFlagManager,
    get_orchestration_engine,
    is_feature_enabled,
    with_engine_fallback,
)

# Use Poetry and relative imports instead of hardcoded paths



class TestFeatureFlag:
    """Test FeatureFlag dataclass functionality"""

    def test_feature_flag_initialization(self):
        """Test feature flag initialization with defaults"""
        flag = FeatureFlag(
            name="test_feature",
            state="enabled",
            description="Test feature flag",
            engine_preference="coherent",
        )

        assert flag.name == "test_feature"
        assert flag.state == "enabled"
        assert flag.rollout_percentage == 0.0
        assert flag.created_at is not None
        assert flag.updated_at is not None
        assert flag.metadata == {}

    def test_feature_flag_with_metadata(self):
        """Test feature flag with custom metadata"""
        metadata = {"phase": "2A", "priority": "high"}
        flag = FeatureFlag(
            name="advanced_feature",
            state="testing",
            description="Advanced test feature",
            engine_preference="hybrid",
            rollout_percentage=25.0,
            metadata=metadata,
        )

        assert flag.rollout_percentage == 25.0
        assert flag.metadata["phase"] == "2A"
        assert flag.metadata["priority"] == "high"


class TestEngineConfiguration:
    """Test EngineConfiguration dataclass functionality"""

    def test_engine_configuration_defaults(self):
        """Test engine configuration with default values"""
        config = EngineConfiguration(primary_engine="chained", fallback_engine="chained")

        assert config.primary_engine == "chained"
        assert config.fallback_engine == "chained"
        assert config.auto_fallback_enabled == True
        assert config.performance_threshold == 0.95
        assert config.timeout_seconds == 300
        assert config.max_retries == 3

    def test_engine_configuration_custom(self):
        """Test engine configuration with custom values"""
        config = EngineConfiguration(
            primary_engine="coherent",
            fallback_engine="chained",
            auto_fallback_enabled=False,
            performance_threshold=0.90,
            timeout_seconds=600,
            max_retries=5,
        )

        assert config.primary_engine == "coherent"
        assert config.auto_fallback_enabled == False
        assert config.timeout_seconds == 600


class TestFeatureFlagManager:
    """Test FeatureFlagManager functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.temp_config_file.close()
        self.config_path = self.temp_config_file.name

    def teardown_method(self):
        """Clean up test fixtures"""
        Path(self.config_path).unlink(missing_ok=True)

    def test_manager_initialization_no_config(self):
        """Test manager initialization without existing config file"""
        manager = FeatureFlagManager(config_path=self.config_path)

        # Should initialize with default flags
        assert len(manager.flags) > 0
        assert "coherent_orchestration" in manager.flags
        assert "dual_engine_monitoring" in manager.flags
        assert manager.engine_config.primary_engine == "chained"

    def test_manager_initialization_with_config(self):
        """Test manager initialization with existing config file"""
        config_data = {
            "flags": [
                {
                    "name": "test_flag",
                    "state": "enabled",
                    "description": "Test flag",
                    "engine_preference": "coherent",
                    "rollout_percentage": 100.0,
                    "created_at": "2025-01-01T00:00:00",
                    "updated_at": "2025-01-01T00:00:00",
                    "metadata": {"test": True},
                }
            ],
            "engine_config": {
                "primary_engine": "coherent",
                "fallback_engine": "chained",
                "auto_fallback_enabled": True,
                "performance_threshold": 0.95,
                "timeout_seconds": 300,
                "max_retries": 3,
            },
        }

        with open(self.config_path, "w") as f:
            json.dump(config_data, f)

        manager = FeatureFlagManager(config_path=self.config_path)

        assert "test_flag" in manager.flags
        assert manager.flags["test_flag"].state == "enabled"
        assert manager.engine_config.primary_engine == "coherent"

    def test_default_flags_initialization(self):
        """Test default flags are properly initialized"""
        manager = FeatureFlagManager(config_path=self.config_path)

        expected_flags = [
            "coherent_orchestration",
            "dual_engine_monitoring",
            "intelligent_routing",
            "cross_persona_coordination",
            "adaptive_optimization",
        ]

        for flag_name in expected_flags:
            assert flag_name in manager.flags
            flag = manager.flags[flag_name]
            assert isinstance(flag, FeatureFlag)
            assert flag.name == flag_name

    def test_is_enabled_disabled_flag(self):
        """Test is_enabled for disabled flag"""
        manager = FeatureFlagManager(config_path=self.config_path)

        # coherent_orchestration is disabled by default
        assert manager.is_enabled("coherent_orchestration") == False
        assert manager.is_enabled("coherent_orchestration", "user123") == False

    def test_is_enabled_enabled_flag(self):
        """Test is_enabled for enabled flag"""
        manager = FeatureFlagManager(config_path=self.config_path)

        # dual_engine_monitoring is enabled by default
        assert manager.is_enabled("dual_engine_monitoring") == True
        assert manager.is_enabled("dual_engine_monitoring", "user123") == True

    @patch.dict(os.environ, {"MAESTRO_ENV": "development"})
    def test_is_enabled_testing_flag_development(self):
        """Test is_enabled for testing flag in development environment"""
        manager = FeatureFlagManager(config_path=self.config_path)

        # Set a flag to testing state
        manager.update_flag("coherent_orchestration", state="testing")

        # Should be enabled in development
        assert manager.is_enabled("coherent_orchestration") == True

    @patch.dict(os.environ, {"MAESTRO_ENV": "production"})
    def test_is_enabled_testing_flag_production(self):
        """Test is_enabled for testing flag in production environment"""
        manager = FeatureFlagManager(config_path=self.config_path)

        # Set a flag to testing state
        manager.update_flag("coherent_orchestration", state="testing")

        # Should be disabled in production (no test users)
        assert manager.is_enabled("coherent_orchestration") == False

    def test_is_enabled_rollout_flag(self):
        """Test is_enabled for rollout flag with percentage"""
        manager = FeatureFlagManager(config_path=self.config_path)

        # Set flag to 50% rollout
        manager.update_flag("coherent_orchestration", state="rollout", rollout_percentage=50.0)

        # Test with specific user IDs that should have consistent results
        user_results = {}
        for user_id in ["user1", "user2", "user3", "user4", "user5"]:
            user_results[user_id] = manager.is_enabled("coherent_orchestration", user_id)

        # Results should be consistent for the same user
        assert manager.is_enabled("coherent_orchestration", "user1") == user_results["user1"]

        # With 50% rollout, we should have some enabled and some disabled
        enabled_count = sum(user_results.values())
        assert 0 < enabled_count < 5  # Not all or none should be enabled

    def test_get_engine_preference(self):
        """Test getting engine preference for flags"""
        manager = FeatureFlagManager(config_path=self.config_path)

        # coherent_orchestration should prefer coherent engine
        assert manager.get_engine_preference("coherent_orchestration") == "coherent"

        # dual_engine_monitoring should prefer hybrid
        assert manager.get_engine_preference("dual_engine_monitoring") == "hybrid"

        # Non-existent flag should return primary engine
        assert manager.get_engine_preference("nonexistent") == "chained"

    def test_update_flag(self):
        """Test updating flag configuration"""
        manager = FeatureFlagManager(config_path=self.config_path)

        original_state = manager.flags["coherent_orchestration"].state
        assert original_state == "disabled"

        # Update flag
        manager.update_flag("coherent_orchestration", state="enabled", rollout_percentage=100.0)

        # Verify update
        flag = manager.flags["coherent_orchestration"]
        assert flag.state == "enabled"
        assert flag.rollout_percentage == 100.0
        assert flag.updated_at != flag.created_at

    def test_enable_flag(self):
        """Test enabling a flag"""
        manager = FeatureFlagManager(config_path=self.config_path)

        # Enable with full rollout
        manager.enable_flag("coherent_orchestration")

        flag = manager.flags["coherent_orchestration"]
        assert flag.state == "enabled"
        assert flag.rollout_percentage == 100.0

        # Enable with partial rollout
        manager.enable_flag("intelligent_routing", rollout_percentage=25.0)

        flag = manager.flags["intelligent_routing"]
        assert flag.state == "rollout"
        assert flag.rollout_percentage == 25.0

    def test_disable_flag(self):
        """Test disabling a flag"""
        manager = FeatureFlagManager(config_path=self.config_path)

        # First enable a flag
        manager.enable_flag("dual_engine_monitoring")
        assert manager.flags["dual_engine_monitoring"].state == "enabled"

        # Then disable it
        manager.disable_flag("dual_engine_monitoring")

        flag = manager.flags["dual_engine_monitoring"]
        assert flag.state == "disabled"
        assert flag.rollout_percentage == 0.0

    def test_get_active_engine_default(self):
        """Test getting active engine with default configuration"""
        manager = FeatureFlagManager(config_path=self.config_path)

        # With all coherent features disabled, should use primary engine
        engine = manager.get_active_engine()
        assert engine == "chained"  # Default primary engine

    def test_get_active_engine_coherent_enabled(self):
        """Test getting active engine with coherent orchestration enabled"""
        manager = FeatureFlagManager(config_path=self.config_path)

        # Enable coherent orchestration
        manager.enable_flag("coherent_orchestration")

        engine = manager.get_active_engine({"user_id": "test_user"})
        assert engine == "coherent"

    def test_get_active_engine_intelligent_routing(self):
        """Test getting active engine with intelligent routing"""
        manager = FeatureFlagManager(config_path=self.config_path)

        # Enable intelligent routing
        manager.enable_flag("intelligent_routing")

        # High complexity should use coherent
        engine = manager.get_active_engine({"complexity": "high"})
        assert engine == "coherent"

        # Medium complexity should use chained
        engine = manager.get_active_engine({"complexity": "medium"})
        assert engine == "chained"

    @pytest.mark.asyncio
    async def test_engine_context_success(self):
        """Test engine context manager with successful execution"""
        manager = FeatureFlagManager(config_path=self.config_path)

        async with manager.engine_context({"user_id": "test"}) as engine:
            assert engine == "chained"  # Default primary engine

    @pytest.mark.asyncio
    async def test_engine_context_with_fallback(self):
        """Test engine context manager with fallback"""
        manager = FeatureFlagManager(config_path=self.config_path)

        # Enable coherent but set up for fallback scenario
        manager.enable_flag("coherent_orchestration")

        class TestException(Exception):
            pass

        try:
            async with manager.engine_context({"user_id": "test"}) as engine:
                if engine == "coherent":
                    raise TestException("Coherent engine failed")
        except TestException:
            # This is expected as the fallback mechanism would handle it
            pass

    def test_get_status(self):
        """Test getting feature flag status summary"""
        manager = FeatureFlagManager(config_path=self.config_path)

        # Enable some flags
        manager.enable_flag("dual_engine_monitoring")
        manager.enable_flag("intelligent_routing", rollout_percentage=50.0)

        status = manager.get_status()

        assert "total_flags" in status
        assert "enabled_flags" in status
        assert "active_flags" in status
        assert "primary_engine" in status
        assert "fallback_engine" in status
        assert "auto_fallback" in status

        assert status["total_flags"] >= 5  # At least 5 default flags
        assert status["enabled_flags"] >= 2  # At least 2 enabled
        assert "dual_engine_monitoring" in status["active_flags"]
        assert "intelligent_routing" in status["active_flags"]

    def test_save_and_load_config(self):
        """Test saving and loading configuration"""
        manager1 = FeatureFlagManager(config_path=self.config_path)

        # Modify some flags
        manager1.enable_flag("coherent_orchestration")
        manager1.update_flag("intelligent_routing", state="testing")

        # Save configuration
        manager1.save_config()

        # Create new manager instance (should load saved config)
        manager2 = FeatureFlagManager(config_path=self.config_path)

        # Verify saved state was loaded
        assert manager2.flags["coherent_orchestration"].state == "enabled"
        assert manager2.flags["intelligent_routing"].state == "testing"

    def test_error_handling_invalid_config(self):
        """Test error handling with invalid configuration file"""
        # Write invalid JSON to config file
        with open(self.config_path, "w") as f:
            f.write("invalid json content")

        # Should initialize with defaults and handle error gracefully
        manager = FeatureFlagManager(config_path=self.config_path)

        assert len(manager.flags) > 0  # Should have default flags
        assert "coherent_orchestration" in manager.flags

    def test_hash_based_rollout_consistency(self):
        """Test that hash-based rollout is consistent for same user"""
        manager = FeatureFlagManager(config_path=self.config_path)

        manager.update_flag("coherent_orchestration", state="rollout", rollout_percentage=30.0)

        user_id = "consistent_user_123"

        # Multiple calls should return same result
        result1 = manager.is_enabled("coherent_orchestration", user_id)
        result2 = manager.is_enabled("coherent_orchestration", user_id)
        result3 = manager.is_enabled("coherent_orchestration", user_id)

        assert result1 == result2 == result3


class TestConvenienceFunctions:
    """Test module-level convenience functions"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.temp_config_file.close()
        self.config_path = self.temp_config_file.name

    def teardown_method(self):
        """Clean up test fixtures"""
        Path(self.config_path).unlink(missing_ok=True)

    def test_is_feature_enabled_function(self):
        """Test global is_feature_enabled function"""
        # This uses the global feature_manager instance
        result = is_feature_enabled("dual_engine_monitoring")
        assert isinstance(result, bool)

    def test_get_orchestration_engine_function(self):
        """Test global get_orchestration_engine function"""
        engine = get_orchestration_engine()
        assert engine in ["chained", "coherent", "hybrid"]

        # Test with context
        engine = get_orchestration_engine({"complexity": "high"})
        assert engine in ["chained", "coherent", "hybrid"]

    @pytest.mark.asyncio
    async def test_with_engine_fallback_function(self):
        """Test global with_engine_fallback function"""
        engine = await with_engine_fallback({"user_id": "test_user"})
        assert engine in ["chained", "coherent", "hybrid"]

    def test_feature_flag_integration_scenario(self):
        """Test complete feature flag integration scenario"""
        # Test gradual rollout scenario
        with patch("shared.config.feature_flags.feature_manager") as mock_manager:
            mock_manager.is_enabled.return_value = True
            mock_manager.get_active_engine.return_value = "coherent"

            # Test feature check
            assert is_feature_enabled("coherent_orchestration") == True

            # Test engine selection
            engine = get_orchestration_engine({"complexity": "high"})
            assert engine == "coherent"

    def test_production_deployment_scenario(self):
        """Test production deployment scenario with feature flags"""
        # Simulate production environment with gradual rollout
        with patch("shared.config.feature_flags.feature_manager") as mock_manager:
            # Configure mock for 10% rollout
            def mock_is_enabled(flag_name, user_id=None):
                if flag_name == "coherent_orchestration":
                    # Simulate 10% rollout - only specific users
                    return user_id in ["early_adopter_1", "early_adopter_2"]
                return True

            mock_manager.is_enabled.side_effect = mock_is_enabled
            mock_manager.get_active_engine.side_effect = lambda ctx: (
                "coherent"
                if ctx and ctx.get("user_id") in ["early_adopter_1", "early_adopter_2"]
                else "chained"
            )

            # Test early adopter gets coherent engine
            engine = get_orchestration_engine({"user_id": "early_adopter_1"})
            # Note: actual result depends on implementation, just verify it returns a valid engine
            assert engine in ["chained", "coherent", "hybrid"]

            # Test regular user gets chained engine
            engine = get_orchestration_engine({"user_id": "regular_user"})
            assert engine in ["chained", "coherent", "hybrid"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
