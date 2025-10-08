#!/usr/bin/env python3
"""
Unit tests for Phase 5 Integration Layer
"""

import os

# We need to add the path for imports
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/orchestration_gateway"))

from phase5_integration import Phase5Integration
from shared.config.feature_flags import FeatureFlagManager


class TestPhase5Integration:
    """Test suite for Phase 5 Integration Layer"""

    @pytest.fixture
    def mock_feature_flags(self):
        """Mock feature flag manager"""
        mock = MagicMock(spec=FeatureFlagManager)
        mock.is_enabled.return_value = True
        return mock

    @pytest.fixture
    def mock_hive_client(self):
        """Mock HTTPX client for hive service"""
        mock = AsyncMock(spec=httpx.AsyncClient)
        return mock

    @pytest.fixture
    def mock_stigmergy_client(self):
        """Mock HTTPX client for stigmergy service"""
        mock = AsyncMock(spec=httpx.AsyncClient)
        return mock

    @pytest.fixture
    async def phase5_integration(self, mock_feature_flags):
        """Create Phase5Integration instance with mocked dependencies"""
        integration = Phase5Integration(feature_flags=mock_feature_flags)
        integration.hive_client = AsyncMock()
        integration.stigmergy_client = AsyncMock()
        return integration

    @pytest.fixture
    def sample_context(self):
        """Sample context for testing"""
        return {
            "complexity": "high",
            "priority": "medium",
            "domain": "enterprise",
            "estimated_effort": "4 weeks",
            "team_size": 5,
        }

    @pytest.fixture
    def sample_requirement(self):
        """Sample requirement for testing"""
        return "Create a comprehensive microservices architecture with authentication, monitoring, and deployment automation"

    @pytest.mark.asyncio
    async def test_initialize_success(self, phase5_integration):
        """Test successful Phase 5 integration initialization"""
        # Mock health check responses
        health_response = AsyncMock()
        health_response.status_code = 200
        health_response.json.return_value = {"status": "healthy"}

        phase5_integration.hive_client.get.return_value = health_response
        phase5_integration.stigmergy_client.get.return_value = health_response

        # Initialize
        await phase5_integration.initialize()

        # Assert
        assert phase5_integration._phase5_enabled is True
        assert phase5_integration._initialized is True

        # Verify health checks were called
        phase5_integration.hive_client.get.assert_called_with("/health")
        phase5_integration.stigmergy_client.get.assert_called_with("/health")

    @pytest.mark.asyncio
    async def test_initialize_service_unavailable(self, phase5_integration):
        """Test initialization when Phase 5 services are unavailable"""
        # Mock service unavailable
        phase5_integration.hive_client.get.side_effect = httpx.ConnectError("Connection failed")
        phase5_integration.stigmergy_client.get.side_effect = httpx.ConnectError(
            "Connection failed"
        )

        # Initialize
        await phase5_integration.initialize()

        # Assert
        assert phase5_integration._phase5_enabled is False
        assert phase5_integration._initialized is True

    @pytest.mark.asyncio
    async def test_should_use_autonomous_orchestration_high_complexity(
        self, phase5_integration, sample_requirement, sample_context
    ):
        """Test autonomous orchestration decision for high complexity"""
        # Setup
        await phase5_integration.initialize()
        phase5_integration._phase5_enabled = True

        complex_context = sample_context.copy()
        complex_context["complexity"] = "enterprise"

        # Test
        result = await phase5_integration.should_use_autonomous_orchestration(
            sample_requirement, complex_context
        )

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_should_use_autonomous_orchestration_low_complexity(
        self, phase5_integration, sample_requirement
    ):
        """Test autonomous orchestration decision for low complexity"""
        # Setup
        await phase5_integration.initialize()
        phase5_integration._phase5_enabled = True

        simple_context = {"complexity": "low", "priority": "low"}

        # Test
        result = await phase5_integration.should_use_autonomous_orchestration(
            sample_requirement, simple_context
        )

        # Assert - should check patterns since complexity is low
        # Result depends on pattern analysis mock

    @pytest.mark.asyncio
    async def test_should_use_autonomous_orchestration_disabled(
        self, phase5_integration, sample_requirement, sample_context
    ):
        """Test autonomous orchestration when Phase 5 is disabled"""
        # Setup - Phase 5 disabled
        phase5_integration._phase5_enabled = False

        # Test
        result = await phase5_integration.should_use_autonomous_orchestration(
            sample_requirement, sample_context
        )

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_should_use_autonomous_orchestration_feature_flag_disabled(
        self, phase5_integration, sample_requirement, sample_context
    ):
        """Test autonomous orchestration when feature flag is disabled"""
        # Setup
        await phase5_integration.initialize()
        phase5_integration._phase5_enabled = True
        phase5_integration.feature_flags.is_enabled.return_value = False

        # Test
        result = await phase5_integration.should_use_autonomous_orchestration(
            sample_requirement, sample_context
        )

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_create_autonomous_hive_success(
        self, phase5_integration, sample_requirement, sample_context
    ):
        """Test successful autonomous hive creation"""
        # Setup
        await phase5_integration.initialize()
        phase5_integration._phase5_enabled = True

        # Mock successful hive creation
        hive_response = AsyncMock()
        hive_response.status_code = 200
        hive_response.json.return_value = {
            "hive": {
                "id": "hive-12345",
                "name": "autonomous-execution-20250918-120000",
                "status": "created",
                "autonomous_mode": True,
            }
        }
        phase5_integration.hive_client.post.return_value = hive_response

        # Test
        result = await phase5_integration.create_autonomous_hive(
            requirement=sample_requirement, context=sample_context, hive_type="execution"
        )

        # Assert
        assert result is not None
        assert result["id"] == "hive-12345"
        assert result["autonomous_mode"] is True

        # Verify API call
        phase5_integration.hive_client.post.assert_called_once_with(
            "/api/v1/hives", json=unittest.mock.ANY
        )

    @pytest.mark.asyncio
    async def test_create_autonomous_hive_service_unavailable(
        self, phase5_integration, sample_requirement, sample_context
    ):
        """Test hive creation when service is unavailable"""
        # Setup - Phase 5 disabled
        phase5_integration._phase5_enabled = False

        # Test
        with pytest.raises(RuntimeError, match="Phase 5 services not available"):
            await phase5_integration.create_autonomous_hive(
                requirement=sample_requirement, context=sample_context
            )

    @pytest.mark.asyncio
    async def test_create_autonomous_hive_api_error(
        self, phase5_integration, sample_requirement, sample_context
    ):
        """Test hive creation with API error"""
        # Setup
        await phase5_integration.initialize()
        phase5_integration._phase5_enabled = True

        # Mock API error
        error_response = AsyncMock()
        error_response.status_code = 500
        phase5_integration.hive_client.post.return_value = error_response

        # Test
        result = await phase5_integration.create_autonomous_hive(
            requirement=sample_requirement, context=sample_context
        )

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_hive_status_success(self, phase5_integration):
        """Test successful hive status retrieval"""
        # Setup
        hive_id = "hive-12345"
        status_response = AsyncMock()
        status_response.status_code = 200
        status_response.json.return_value = {
            "hive": {
                "id": hive_id,
                "status": "running",
                "progress": 45,
                "current_phase": "execution",
            }
        }
        phase5_integration.hive_client.get.return_value = status_response

        # Test
        result = await phase5_integration.get_hive_status(hive_id)

        # Assert
        assert result is not None
        assert result["id"] == hive_id
        assert result["status"] == "running"

        # Verify API call
        phase5_integration.hive_client.get.assert_called_once_with(f"/api/v1/hives/{hive_id}")

    @pytest.mark.asyncio
    async def test_get_hive_status_not_found(self, phase5_integration):
        """Test hive status retrieval for non-existent hive"""
        # Setup
        hive_id = "non-existent-hive"
        error_response = AsyncMock()
        error_response.status_code = 404
        phase5_integration.hive_client.get.return_value = error_response

        # Test
        result = await phase5_integration.get_hive_status(hive_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_spawn_child_hive_success(self, phase5_integration):
        """Test successful child hive spawning"""
        # Setup
        parent_hive_id = "parent-hive-123"
        child_requirement = "Design authentication UI components"

        spawn_response = AsyncMock()
        spawn_response.status_code = 200
        spawn_response.json.return_value = {
            "hive": {
                "id": "child-hive-456",
                "parent_id": parent_hive_id,
                "name": "child-recursive-120000",
                "status": "created",
            }
        }
        phase5_integration.hive_client.post.return_value = spawn_response

        # Test
        result = await phase5_integration.spawn_child_hive(
            parent_hive_id=parent_hive_id, child_requirement=child_requirement, child_type="design"
        )

        # Assert
        assert result is not None
        assert result["id"] == "child-hive-456"
        assert result["parent_id"] == parent_hive_id

        # Verify API call
        phase5_integration.hive_client.post.assert_called_once_with(
            f"/api/v1/hives/{parent_hive_id}/spawn", json=unittest.mock.ANY
        )

    @pytest.mark.asyncio
    async def test_analyze_requirement_patterns_success(
        self, phase5_integration, sample_requirement
    ):
        """Test successful requirement pattern analysis"""
        # Setup
        analysis_response = AsyncMock()
        analysis_response.status_code = 200
        analysis_response.json.return_value = {
            "patterns": [
                {"name": "microservices", "confidence": 0.92},
                {"name": "authentication", "confidence": 0.88},
                {"name": "monitoring", "confidence": 0.75},
            ],
            "complexity": "high",
            "technologies": ["Python", "Docker", "Kubernetes"],
        }
        phase5_integration.stigmergy_client.post.return_value = analysis_response

        # Test
        result = await phase5_integration.analyze_requirement_patterns(sample_requirement)

        # Assert
        assert result is not None
        assert "patterns" in result
        assert len(result["patterns"]) == 3

        # Verify API call
        phase5_integration.stigmergy_client.post.assert_called_once_with(
            "/api/v1/patterns/analyze", json={"requirement": sample_requirement}
        )

    @pytest.mark.asyncio
    async def test_analyze_requirement_patterns_failure(
        self, phase5_integration, sample_requirement
    ):
        """Test requirement pattern analysis failure"""
        # Setup
        error_response = AsyncMock()
        error_response.status_code = 500
        phase5_integration.stigmergy_client.post.return_value = error_response

        # Test
        result = await phase5_integration.analyze_requirement_patterns(sample_requirement)

        # Assert
        assert result is not None
        assert result["patterns"] == []
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_get_similar_projects_success(self, phase5_integration, sample_requirement):
        """Test successful similar projects retrieval"""
        # Setup
        similar_response = AsyncMock()
        similar_response.status_code = 200
        similar_response.json.return_value = {
            "similar_projects": [
                {"id": "proj-1", "name": "E-commerce Platform", "similarity": 0.89},
                {"id": "proj-2", "name": "Banking API", "similarity": 0.76},
            ]
        }
        phase5_integration.stigmergy_client.get.return_value = similar_response

        # Test
        result = await phase5_integration.get_similar_projects(sample_requirement, limit=3)

        # Assert
        assert result is not None
        assert len(result) == 2
        assert all("similarity" in proj for proj in result)

        # Verify API call
        phase5_integration.stigmergy_client.get.assert_called_once_with(
            "/api/v1/patterns/similar", params={"query": sample_requirement, "limit": 3}
        )

    @pytest.mark.asyncio
    async def test_integrate_with_existing_workflow_autonomous_recommended(
        self, phase5_integration, sample_requirement, sample_context
    ):
        """Test workflow integration when autonomous orchestration is recommended"""
        # Setup
        await phase5_integration.initialize()
        phase5_integration._phase5_enabled = True

        # Mock autonomous recommendation
        with patch.object(
            phase5_integration, "should_use_autonomous_orchestration", return_value=True
        ):
            with patch.object(
                phase5_integration,
                "analyze_requirement_patterns",
                return_value={"patterns": ["microservices"]},
            ):
                with patch.object(phase5_integration, "get_similar_projects", return_value=[]):
                    with patch.object(
                        phase5_integration,
                        "create_autonomous_hive",
                        return_value={"id": "hive-123", "status": "created"},
                    ):
                        # Test
                        result = await phase5_integration.integrate_with_existing_workflow(
                            sample_requirement, sample_context
                        )

                        # Assert
                        assert result["phase5_enabled"] is True
                        assert result["autonomous_recommended"] is True
                        assert result["hive_created"] is True
                        assert result["hive_id"] == "hive-123"
                        assert result["fallback_to_phase4"] is False

    @pytest.mark.asyncio
    async def test_integrate_with_existing_workflow_fallback_to_phase4(
        self, phase5_integration, sample_requirement, sample_context
    ):
        """Test workflow integration fallback to Phase 4"""
        # Setup
        await phase5_integration.initialize()
        phase5_integration._phase5_enabled = True

        # Mock autonomous recommendation but hive creation failure
        with patch.object(
            phase5_integration, "should_use_autonomous_orchestration", return_value=True
        ):
            with patch.object(
                phase5_integration, "analyze_requirement_patterns", return_value={"patterns": []}
            ):
                with patch.object(phase5_integration, "get_similar_projects", return_value=[]):
                    with patch.object(
                        phase5_integration, "create_autonomous_hive", return_value=None
                    ):
                        # Test
                        result = await phase5_integration.integrate_with_existing_workflow(
                            sample_requirement, sample_context
                        )

                        # Assert
                        assert result["autonomous_recommended"] is True
                        assert result["hive_created"] is False
                        assert result["fallback_to_phase4"] is True

    @pytest.mark.asyncio
    async def test_integrate_with_existing_workflow_phase5_disabled(
        self, phase5_integration, sample_requirement, sample_context
    ):
        """Test workflow integration when Phase 5 is disabled"""
        # Setup - Phase 5 disabled
        phase5_integration._phase5_enabled = False

        # Test
        result = await phase5_integration.integrate_with_existing_workflow(
            sample_requirement, sample_context
        )

        # Assert
        assert result["phase5_enabled"] is False
        assert result["autonomous_recommended"] is False
        assert result["hive_created"] is False
        assert result["fallback_to_phase4"] is False

    @pytest.mark.asyncio
    async def test_close_connections(self, phase5_integration):
        """Test proper cleanup of HTTP clients"""
        # Test
        await phase5_integration.close()

        # Assert
        phase5_integration.hive_client.aclose.assert_called_once()
        phase5_integration.stigmergy_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_enabled_property(self, phase5_integration):
        """Test is_enabled property"""
        # Initially not enabled
        assert phase5_integration.is_enabled is False

        # After successful initialization
        await phase5_integration.initialize()
        phase5_integration._phase5_enabled = True
        assert phase5_integration.is_enabled is True

    @pytest.mark.asyncio
    async def test_pattern_analysis_with_caching(self, phase5_integration, sample_requirement):
        """Test pattern analysis with caching behavior"""
        # Setup - first call
        analysis_response = AsyncMock()
        analysis_response.status_code = 200
        analysis_response.json.return_value = {"patterns": ["test-pattern"]}
        phase5_integration.stigmergy_client.post.return_value = analysis_response

        # First call
        result1 = await phase5_integration.analyze_requirement_patterns(sample_requirement)

        # Second call (should potentially use cache if implemented)
        result2 = await phase5_integration.analyze_requirement_patterns(sample_requirement)

        # Assert both calls return data
        assert result1 is not None
        assert result2 is not None

    @pytest.mark.asyncio
    async def test_error_handling_network_issues(
        self, phase5_integration, sample_requirement, sample_context
    ):
        """Test error handling for network issues"""
        # Setup
        await phase5_integration.initialize()
        phase5_integration._phase5_enabled = True

        # Mock network error
        phase5_integration.hive_client.post.side_effect = httpx.NetworkError("Network unreachable")

        # Test should handle gracefully
        with pytest.raises(Exception):  # Should propagate the error for hive creation
            await phase5_integration.create_autonomous_hive(
                requirement=sample_requirement, context=sample_context
            )

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, phase5_integration, sample_requirement):
        """Test concurrent Phase 5 operations"""
        # Setup
        await phase5_integration.initialize()
        phase5_integration._phase5_enabled = True

        # Mock responses
        analysis_response = AsyncMock()
        analysis_response.status_code = 200
        analysis_response.json.return_value = {"patterns": []}

        similar_response = AsyncMock()
        similar_response.status_code = 200
        similar_response.json.return_value = {"similar_projects": []}

        phase5_integration.stigmergy_client.post.return_value = analysis_response
        phase5_integration.stigmergy_client.get.return_value = similar_response

        # Test concurrent operations
        import asyncio

        tasks = [
            phase5_integration.analyze_requirement_patterns(sample_requirement),
            phase5_integration.get_similar_projects(sample_requirement),
        ]

        results = await asyncio.gather(*tasks)

        # Assert both operations completed
        assert len(results) == 2
        assert all(result is not None for result in results)

    @pytest.mark.asyncio
    async def test_configuration_validation(self, mock_feature_flags):
        """Test configuration validation during initialization"""
        # Test with valid configuration
        integration = Phase5Integration(feature_flags=mock_feature_flags)
        assert integration.feature_flags is not None

        # Test with None feature flags (should create default)
        integration_default = Phase5Integration(feature_flags=None)
        assert integration_default.feature_flags is not None


# Add required import for unittest.mock
import unittest.mock
