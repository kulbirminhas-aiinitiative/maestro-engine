#!/usr/bin/env python3
"""
Unit Tests for Health Endpoint Verification
MD-1861: Add Health Endpoint Verification

Tests the timeout and retry logic for deployment health checks.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from services.deployment_health_monitor import (
    DeploymentHealthMonitor,
    HealthCheckResult,
    HealthStatus,
    HealthSnapshotStorage,
)


class TestHealthEndpointRetryLogic:
    """Test suite for MD-1861: Health Endpoint Verification with retry logic."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config with retry settings."""
        return {
            "interval_seconds": 30,
            "timeout_seconds": 5,
            "unhealthy_threshold": 3,
            "healthy_threshold": 2,
            "max_retries": 3,
            "retry_delay_seconds": 0.01,  # Fast for testing
            "retry_backoff_multiplier": 2.0,
            "expected_status_codes": [200, 204],
        }

    @pytest.fixture
    def monitor(self, mock_config):
        """Create health monitor with mock config."""
        with patch.object(DeploymentHealthMonitor, '_load_config', return_value=mock_config):
            monitor = DeploymentHealthMonitor()
            monitor.register_environment(
                "test-env-1",
                "Test Environment",
                "http://localhost:8080/health"
            )
            return monitor

    @pytest.mark.asyncio
    async def test_successful_health_check_no_retry(self, monitor):
        """Test successful health check requires no retries."""
        mock_result = HealthCheckResult(
            environment_id="test-env-1",
            environment_name="Test Environment",
            status=HealthStatus.HEALTHY,
            response_time_ms=50,
            status_code=200,
        )

        with patch.object(monitor, '_single_health_check', return_value=mock_result):
            result = await monitor.check_environment_health("test-env-1")

        assert result.status == HealthStatus.HEALTHY
        assert result.error_message is None
        assert monitor._last_retry_counts.get("test-env-1", 0) == 0

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, monitor):
        """Test retry logic triggers on timeout."""
        call_count = 0
        mock_result = HealthCheckResult(
            environment_id="test-env-1",
            environment_name="Test Environment",
            status=HealthStatus.HEALTHY,
            response_time_ms=50,
            status_code=200,
        )

        async def mock_single_check(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise asyncio.TimeoutError()
            return mock_result

        with patch.object(monitor, '_single_health_check', side_effect=mock_single_check):
            result = await monitor.check_environment_health("test-env-1")

        assert result.status == HealthStatus.HEALTHY
        assert call_count == 3
        assert monitor._last_retry_counts.get("test-env-1") == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted_returns_error(self, monitor):
        """Test that exhausted retries result in error with appropriate message."""
        async def mock_single_check(*args, **kwargs):
            raise asyncio.TimeoutError()

        with patch.object(monitor, '_single_health_check', side_effect=mock_single_check):
            result = await monitor.check_environment_health("test-env-1")

        # After all retries exhausted, the result indicates failure
        # Status could be UNHEALTHY, DEGRADED, or UNKNOWN depending on threshold logic
        assert result.error_message is not None
        assert "timed out" in result.error_message.lower()
        assert "retries" in result.error_message.lower()
        # retry_count should equal max_retries (3) when all retries exhausted
        assert result.details.get("retry_count") == 3
        assert result.details.get("max_retries") == 3

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self, monitor):
        """Test retry logic triggers on connection error."""
        import aiohttp

        call_count = 0
        mock_result = HealthCheckResult(
            environment_id="test-env-1",
            environment_name="Test Environment",
            status=HealthStatus.HEALTHY,
            response_time_ms=50,
            status_code=200,
        )

        async def mock_single_check(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise aiohttp.ClientError("Connection refused")
            return mock_result

        with patch.object(monitor, '_single_health_check', side_effect=mock_single_check):
            result = await monitor.check_environment_health("test-env-1")

        assert result.status == HealthStatus.HEALTHY
        assert call_count == 2
        assert monitor._last_retry_counts.get("test-env-1") == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_bad_status_code(self, monitor):
        """Test that bad status codes don't trigger retries (server returned response)."""
        # Bad status code means the server responded - no retry
        # This is handled inside _single_health_check, not as an exception
        mock_result = HealthCheckResult(
            environment_id="test-env-1",
            environment_name="Test Environment",
            status=HealthStatus.UNHEALTHY,
            response_time_ms=50,
            status_code=503,
        )

        call_count = 0

        async def mock_single_check(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_result

        with patch.object(monitor, '_single_health_check', side_effect=mock_single_check):
            result = await monitor.check_environment_health("test-env-1")

        # Bad status code = server responded, no retry
        assert call_count == 1
        assert result.status_code == 503

    def test_retry_config_properties(self, monitor):
        """Test retry configuration properties are correctly read."""
        assert monitor.max_retries == 3
        assert monitor.retry_delay == 0.01
        assert monitor.retry_backoff_multiplier == 2.0
        assert monitor.check_timeout == 5

    def test_get_retry_config(self, monitor):
        """Test get_retry_config returns correct settings."""
        config = monitor.get_retry_config()

        assert config["max_retries"] == 3
        assert config["retry_delay_seconds"] == 0.01
        assert config["retry_backoff_multiplier"] == 2.0
        assert config["timeout_seconds"] == 5

    def test_get_retry_stats_all_environments(self, monitor):
        """Test get_retry_stats returns stats for all environments."""
        monitor._last_retry_counts["test-env-1"] = 2

        stats = monitor.get_retry_stats()

        assert "config" in stats
        assert "environments" in stats
        assert stats["environments"]["test-env-1"]["last_retry_count"] == 2

    def test_get_retry_stats_single_environment(self, monitor):
        """Test get_retry_stats for a specific environment."""
        monitor._last_retry_counts["test-env-1"] = 1

        stats = monitor.get_retry_stats("test-env-1")

        assert stats["environment_id"] == "test-env-1"
        assert stats["last_retry_count"] == 1
        assert stats["max_retries"] == 3

    def test_health_summary_includes_retry_count(self, monitor):
        """Test health summary includes retry information."""
        # Set up mock current status
        result = HealthCheckResult(
            environment_id="test-env-1",
            environment_name="Test Environment",
            status=HealthStatus.HEALTHY,
            response_time_ms=50,
        )
        monitor.storage.set_current_status(result)
        monitor._last_retry_counts["test-env-1"] = 1

        summary = monitor.get_health_summary()

        assert "environments" in summary
        env_info = summary["environments"].get("test-env-1")
        assert env_info is not None
        assert env_info["last_retry_count"] == 1


class TestExponentialBackoff:
    """Test exponential backoff behavior."""

    @pytest.fixture
    def fast_monitor(self):
        """Create monitor with fast retry settings for testing."""
        config = {
            "interval_seconds": 30,
            "timeout_seconds": 1,
            "unhealthy_threshold": 3,
            "healthy_threshold": 2,
            "max_retries": 3,
            "retry_delay_seconds": 0.01,  # 10ms for fast tests
            "retry_backoff_multiplier": 2.0,
            "expected_status_codes": [200],
        }

        with patch.object(DeploymentHealthMonitor, '_load_config', return_value=config):
            monitor = DeploymentHealthMonitor()
            monitor.register_environment(
                "backoff-test",
                "Backoff Test",
                "http://localhost:9999/health"
            )
            return monitor

    @pytest.mark.asyncio
    async def test_backoff_delays_increase(self, fast_monitor):
        """Test that retry delays increase exponentially."""
        delays = []

        async def mock_sleep(delay):
            delays.append(delay)
            # Don't actually sleep in tests

        async def mock_single_check(*args, **kwargs):
            raise asyncio.TimeoutError()

        with patch('asyncio.sleep', mock_sleep):
            with patch.object(fast_monitor, '_single_health_check', side_effect=mock_single_check):
                await fast_monitor.check_environment_health("backoff-test")

        # Should have 3 delays (for 3 retries after initial attempt)
        assert len(delays) == 3
        # Delays should be increasing: 0.01, 0.02, 0.04 (exponential with multiplier 2)
        assert delays[0] == pytest.approx(0.01, rel=0.1)
        assert delays[1] == pytest.approx(0.02, rel=0.1)
        assert delays[2] == pytest.approx(0.04, rel=0.1)


class TestDefaultConfig:
    """Test default configuration values."""

    def test_default_retry_config_without_yaml(self):
        """Test default values when config file is missing."""
        with patch.object(DeploymentHealthMonitor, '_load_config', return_value={}):
            monitor = DeploymentHealthMonitor()

        # Defaults should be applied
        assert monitor.max_retries == 3
        assert monitor.retry_delay == 1.0
        assert monitor.retry_backoff_multiplier == 2.0


class TestRetryCountInDetails:
    """Test that retry count is included in health check details."""

    @pytest.fixture
    def monitor(self):
        """Create health monitor with mock config."""
        config = {
            "interval_seconds": 30,
            "timeout_seconds": 5,
            "unhealthy_threshold": 3,
            "healthy_threshold": 2,
            "max_retries": 2,
            "retry_delay_seconds": 0.01,
            "retry_backoff_multiplier": 2.0,
            "expected_status_codes": [200],
        }
        with patch.object(DeploymentHealthMonitor, '_load_config', return_value=config):
            monitor = DeploymentHealthMonitor()
            monitor.register_environment(
                "retry-test",
                "Retry Test",
                "http://localhost:8080/health"
            )
            return monitor

    @pytest.mark.asyncio
    async def test_retry_count_in_success_details(self, monitor):
        """Test retry count is included when check succeeds after retries."""
        call_count = 0
        mock_result = HealthCheckResult(
            environment_id="retry-test",
            environment_name="Retry Test",
            status=HealthStatus.HEALTHY,
            response_time_ms=50,
            status_code=200,
            details={},  # Will be modified
        )

        async def mock_single_check(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise asyncio.TimeoutError()
            return mock_result

        with patch.object(monitor, '_single_health_check', side_effect=mock_single_check):
            result = await monitor.check_environment_health("retry-test")

        assert result.status == HealthStatus.HEALTHY
        assert result.details.get("retry_count") == 1


class TestNonRetryableErrors:
    """Test handling of non-retryable errors."""

    @pytest.fixture
    def monitor(self):
        """Create health monitor with mock config."""
        config = {
            "interval_seconds": 30,
            "timeout_seconds": 5,
            "unhealthy_threshold": 3,
            "healthy_threshold": 2,
            "max_retries": 3,
            "retry_delay_seconds": 0.01,
            "retry_backoff_multiplier": 2.0,
            "expected_status_codes": [200],
        }
        with patch.object(DeploymentHealthMonitor, '_load_config', return_value=config):
            monitor = DeploymentHealthMonitor()
            monitor.register_environment(
                "error-test",
                "Error Test",
                "http://localhost:8080/health"
            )
            return monitor

    @pytest.mark.asyncio
    async def test_non_retryable_error_returns_unknown(self, monitor):
        """Test that non-retryable errors return UNKNOWN status immediately."""
        async def mock_single_check(*args, **kwargs):
            raise ValueError("Invalid configuration")

        with patch.object(monitor, '_single_health_check', side_effect=mock_single_check):
            result = await monitor.check_environment_health("error-test")

        # Non-retryable errors should immediately return UNKNOWN
        assert result.status == HealthStatus.UNKNOWN
        assert "unexpected error" in result.error_message.lower()
        assert result.details.get("retry_count") == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
