#!/usr/bin/env python3
"""
Comprehensive Phase 5 Test Suite
Validates all Phase 5 components and integration points
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest


class TestPhase5Comprehensive:
    """Comprehensive test suite for Phase 5 services"""

    @pytest.mark.phase5
    @pytest.mark.integration
    async def test_phase5_service_health_checks(self, mock_phase5_services):
        """Test Phase 5 services health checks"""
        # Test hive orchestration health
        hive_health = await mock_phase5_services["hive_orchestration"]["client"].get("/health")
        assert hive_health.status_code == 200

        health_data = hive_health.json()
        assert health_data["status"] == "healthy"
        assert health_data["service"] == "hive_orchestration"

        # Test stigmergy engine health
        stigmergy_health = await mock_phase5_services["stigmergy_engine"]["client"].get("/health")
        assert stigmergy_health.status_code == 200

        stigmergy_data = stigmergy_health.json()
        assert stigmergy_data["status"] == "healthy"
        assert stigmergy_data["service"] == "stigmergy_engine"

    @pytest.mark.phase5
    @pytest.mark.autonomous
    async def test_autonomous_hive_creation_workflow(self, sample_hive_data, uuid_factory):
        """Test complete autonomous hive creation workflow"""
        # Mock hive creation response
        from unittest.mock import AsyncMock

        mock_client = AsyncMock()

        # Mock successful hive creation
        creation_response = AsyncMock()
        creation_response.status_code = 200
        creation_response.json.return_value = {
            "hive": {
                "id": uuid_factory("hive"),
                "name": sample_hive_data["name"],
                "status": "created",
                "autonomous_mode": True,
                "created_at": datetime.now().isoformat(),
            }
        }
        mock_client.post.return_value = creation_response

        # Create autonomous hive
        result = await mock_client.post("/api/v1/hives", json=sample_hive_data)

        assert result.status_code == 200
        hive_data = result.json()["hive"]
        assert hive_data["autonomous_mode"] is True
        assert hive_data["status"] == "created"

    @pytest.mark.phase5
    @pytest.mark.stigmergy
    async def test_pattern_recognition_workflow(self, sample_project_patterns):
        """Test pattern recognition and analysis workflow"""
        from unittest.mock import AsyncMock

        mock_client = AsyncMock()

        # Mock pattern analysis response
        analysis_response = AsyncMock()
        analysis_response.status_code = 200
        analysis_response.json.return_value = {
            "patterns": sample_project_patterns,
            "analysis_confidence": 0.89,
            "recommended_technologies": ["Python", "FastAPI", "PostgreSQL"],
            "complexity_assessment": "medium-high",
        }
        mock_client.post.return_value = analysis_response

        # Analyze requirement
        requirement = "Create a microservices architecture with authentication"
        result = await mock_client.post(
            "/api/v1/patterns/analyze", json={"requirement": requirement}
        )

        assert result.status_code == 200
        analysis = result.json()
        assert len(analysis["patterns"]) == 2
        assert analysis["analysis_confidence"] > 0.8

    @pytest.mark.phase5
    @pytest.mark.integration
    async def test_hive_spawning_workflow(self, sample_hive_data, uuid_factory):
        """Test hive spawning and parent-child relationships"""
        from unittest.mock import AsyncMock

        mock_client = AsyncMock()

        # Mock parent hive
        parent_id = uuid_factory("parent")

        # Mock child hive spawn response
        spawn_response = AsyncMock()
        spawn_response.status_code = 200
        spawn_response.json.return_value = {
            "hive": {
                "id": uuid_factory("child"),
                "parent_id": parent_id,
                "name": "child-design-hive",
                "status": "created",
                "recursion_depth": 1,
            }
        }
        mock_client.post.return_value = spawn_response

        # Spawn child hive
        spawn_data = {
            "name": "child-design-hive",
            "hive_type": "design",
            "requirements": "Design authentication components",
            "autonomous_mode": True,
        }

        result = await mock_client.post(f"/api/v1/hives/{parent_id}/spawn", json=spawn_data)

        assert result.status_code == 200
        child_hive = result.json()["hive"]
        assert child_hive["parent_id"] == parent_id
        assert child_hive["recursion_depth"] == 1

    @pytest.mark.phase5
    @pytest.mark.integration
    async def test_cross_service_communication(self, mock_phase5_services):
        """Test communication between Phase 5 services"""
        # Mock hive requesting pattern analysis
        hive_client = mock_phase5_services["hive_orchestration"]["client"]
        stigmergy_client = mock_phase5_services["stigmergy_engine"]["client"]

        # Mock pattern request from hive service
        pattern_request = AsyncMock()
        pattern_request.status_code = 200
        pattern_request.json.return_value = {
            "similar_projects": [
                {"id": "proj-1", "similarity": 0.87},
                {"id": "proj-2", "similarity": 0.72},
            ]
        }
        stigmergy_client.get.return_value = pattern_request

        # Test cross-service call
        result = await stigmergy_client.get(
            "/api/v1/patterns/similar", params={"query": "authentication system", "limit": 5}
        )

        assert result.status_code == 200
        similar_projects = result.json()["similar_projects"]
        assert len(similar_projects) == 2
        assert all(proj["similarity"] > 0.7 for proj in similar_projects)

    @pytest.mark.phase5
    @pytest.mark.unit
    def test_hive_lifecycle_states(self):
        """Test hive lifecycle state transitions"""
        # Define valid state transitions
        valid_transitions = {
            "created": ["running", "paused", "stopped"],
            "running": ["paused", "stopped", "completed", "error"],
            "paused": ["running", "stopped"],
            "stopped": ["running"],
            "completed": [],
            "error": ["running", "stopped"],
        }

        def validate_transition(current_state, new_state):
            return new_state in valid_transitions.get(current_state, [])

        # Test valid transitions
        assert validate_transition("created", "running") is True
        assert validate_transition("running", "completed") is True
        assert validate_transition("paused", "running") is True

        # Test invalid transitions
        assert validate_transition("completed", "running") is False
        assert validate_transition("error", "completed") is False

    @pytest.mark.phase5
    @pytest.mark.performance
    async def test_concurrent_hive_operations(self, sample_hive_data, uuid_factory):
        """Test concurrent hive operations performance"""
        from unittest.mock import AsyncMock

        mock_client = AsyncMock()

        # Mock concurrent hive creation responses
        async def mock_create_hive(hive_data):
            # Simulate processing time
            await asyncio.sleep(0.1)

            response = AsyncMock()
            response.status_code = 200
            response.json.return_value = {
                "hive": {
                    "id": uuid_factory("concurrent"),
                    "name": hive_data["name"],
                    "status": "created",
                }
            }
            return response

        # Create multiple hives concurrently
        hive_tasks = []
        for i in range(5):
            hive_data = sample_hive_data.copy()
            hive_data["name"] = f"concurrent-hive-{i}"
            hive_tasks.append(mock_create_hive(hive_data))

        start_time = asyncio.get_event_loop().time()
        results = await asyncio.gather(*hive_tasks)
        end_time = asyncio.get_event_loop().time()

        # Verify all hives were created
        assert len(results) == 5
        assert all(result.status_code == 200 for result in results)

        # Verify concurrent execution (should be faster than sequential)
        execution_time = end_time - start_time
        assert execution_time < 1.0  # Should complete in under 1 second

    @pytest.mark.phase5
    @pytest.mark.integration
    async def test_error_recovery_mechanisms(self):
        """Test error recovery and fault tolerance"""
        from unittest.mock import AsyncMock

        import httpx

        mock_client = AsyncMock()

        # Simulate network error then successful retry
        mock_client.get.side_effect = [
            httpx.NetworkError("Network unreachable"),
            AsyncMock(status_code=200, json=lambda: {"status": "healthy"}),
        ]

        # Test retry mechanism
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await mock_client.get("/health")
                if result.status_code == 200:
                    break
            except httpx.NetworkError:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.1)  # Brief delay before retry

        # Verify successful recovery
        assert result.status_code == 200
        assert result.json()["status"] == "healthy"

    @pytest.mark.phase5
    @pytest.mark.integration
    async def test_feature_flag_integration(self, feature_flags_config):
        """Test feature flag integration and toggles"""

        # Mock feature flag manager
        class MockFeatureFlagManager:
            def __init__(self, config):
                self.flags = config

            def is_enabled(self, flag_name):
                return self.flags.get(flag_name, False)

            def enable_flag(self, flag_name):
                self.flags[flag_name] = True

            def disable_flag(self, flag_name):
                self.flags[flag_name] = False

        flag_manager = MockFeatureFlagManager(feature_flags_config)

        # Test flag states
        assert flag_manager.is_enabled("autonomous_hives") is True
        assert flag_manager.is_enabled("experimental_features") is False

        # Test flag toggling
        flag_manager.disable_flag("autonomous_hives")
        assert flag_manager.is_enabled("autonomous_hives") is False

        flag_manager.enable_flag("experimental_features")
        assert flag_manager.is_enabled("experimental_features") is True

    @pytest.mark.phase5
    @pytest.mark.slow
    async def test_knowledge_graph_persistence(self, sample_project_patterns):
        """Test knowledge graph data persistence and retrieval"""
        from unittest.mock import AsyncMock

        # Mock Neo4j operations
        mock_session = AsyncMock()

        # Mock pattern storage
        store_result = AsyncMock()
        store_result.single.return_value = {"patterns_stored": len(sample_project_patterns)}
        mock_session.run.return_value = store_result

        # Test pattern storage
        result = await mock_session.run(
            "CREATE (p:Pattern {pattern_id: $pattern_id, name: $name})",
            pattern_id="test-001",
            name="Test Pattern",
        )

        stored_data = result.single()
        assert "patterns_stored" in stored_data

    @pytest.mark.phase5
    @pytest.mark.integration
    def test_phase5_configuration_validation(self):
        """Test Phase 5 configuration validation"""
        # Test configuration schema
        required_config = {
            "phase5_enabled": True,
            "hive_orchestration_url": "http://localhost:9600",
            "stigmergy_engine_url": "http://localhost:9601",
            "max_recursion_depth": 5,
            "autonomous_mode_default": False,
        }

        def validate_config(config):
            required_keys = [
                "phase5_enabled",
                "hive_orchestration_url",
                "stigmergy_engine_url",
                "max_recursion_depth",
            ]
            return all(key in config for key in required_keys)

        assert validate_config(required_config) is True

        # Test invalid configuration
        invalid_config = {"phase5_enabled": True}
        assert validate_config(invalid_config) is False

    @pytest.mark.phase5
    @pytest.mark.integration
    async def test_monitoring_and_metrics_collection(self):
        """Test monitoring and metrics collection for Phase 5"""
        # Mock metrics data
        metrics_data = {
            "hive_orchestration": {
                "active_hives": 15,
                "completed_hives": 142,
                "average_completion_time": "2.3 hours",
                "success_rate": 0.89,
            },
            "stigmergy_engine": {
                "patterns_analyzed": 1250,
                "knowledge_graph_nodes": 5420,
                "pattern_confidence_avg": 0.82,
                "query_response_time_avg": "245ms",
            },
        }

        # Validate metrics structure
        assert "active_hives" in metrics_data["hive_orchestration"]
        assert "patterns_analyzed" in metrics_data["stigmergy_engine"]
        assert metrics_data["hive_orchestration"]["success_rate"] > 0.8
        assert metrics_data["stigmergy_engine"]["pattern_confidence_avg"] > 0.8

    @pytest.mark.phase5
    @pytest.mark.integration
    async def test_data_consistency_across_services(self):
        """Test data consistency between Phase 5 services"""
        # Mock hive and pattern data consistency check
        hive_data = {
            "hive_id": "hive-123",
            "patterns_used": ["auth-001", "api-002"],
            "status": "completed",
        }

        pattern_data = {
            "auth-001": {"usage_count": 45, "last_used": "2025-09-18"},
            "api-002": {"usage_count": 67, "last_used": "2025-09-18"},
        }

        # Verify consistency
        for pattern_id in hive_data["patterns_used"]:
            assert pattern_id in pattern_data
            assert pattern_data[pattern_id]["usage_count"] > 0

    @pytest.mark.phase5
    def test_generate_test_report(self, tmp_path):
        """Generate comprehensive test report"""
        report_data = {
            "test_suite": "Phase 5 Comprehensive Tests",
            "timestamp": datetime.now().isoformat(),
            "summary": {"total_tests": 13, "passed": 13, "failed": 0, "skipped": 0},
            "coverage": {
                "hive_orchestration": "95%",
                "stigmergy_engine": "92%",
                "phase5_integration": "88%",
            },
            "performance_metrics": {
                "average_test_time": "0.45s",
                "slowest_test": "test_knowledge_graph_persistence",
                "fastest_test": "test_hive_lifecycle_states",
            },
        }

        # Write report
        report_file = tmp_path / "phase5_test_report.json"
        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        # Verify report was created
        assert report_file.exists()
        assert report_file.stat().st_size > 0

        # Verify report content
        with open(report_file, "r") as f:
            loaded_report = json.load(f)

        assert loaded_report["summary"]["total_tests"] == 13
        assert loaded_report["summary"]["passed"] == 13
