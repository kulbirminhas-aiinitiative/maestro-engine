#!/usr/bin/env python3
"""
Unit Tests for Dual-Engine Workflow Executor
Tests the intelligent routing between ChainedWorkflow and CoherentPersonaExecutor engines.
"""

import asyncio
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from shared.orchestration.dual_engine_executor import (
    _execute_chained_workflow,
    _execute_coherent_workflow,
    _execute_hybrid_workflow,
    execute_dual_engine_workflow,
    get_engine_capabilities,
)

# Use Poetry and relative imports instead of hardcoded paths



class TestDualEngineExecutor:
    """Test dual-engine workflow execution functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.test_requirement = "Build a web application with user authentication"
        self.test_output_dir = tempfile.mkdtemp()
        self.test_request_context = {"complexity": "medium", "user_id": "test_user_123"}

    @pytest.mark.asyncio
    async def test_execute_dual_engine_workflow_success(self):
        """Test successful dual-engine workflow execution"""
        with (
            patch(
                "shared.orchestration.dual_engine_executor.get_orchestration_engine"
            ) as mock_get_engine,
            patch(
                "shared.orchestration.dual_engine_executor.start_execution_tracking"
            ) as mock_start_tracking,
            patch(
                "shared.orchestration.dual_engine_executor.end_execution_tracking"
            ) as mock_end_tracking,
            patch(
                "shared.orchestration.dual_engine_executor._execute_chained_workflow"
            ) as mock_chained,
        ):

            # Setup mocks
            mock_get_engine.return_value = "chained"
            mock_start_tracking.return_value = MagicMock(execution_id="test_123")
            mock_end_tracking.return_value = MagicMock()

            mock_result = {
                "success": True,
                "quality_score": 88.5,
                "persona_executions": ["RequirementAnalyst", "SolutionArchitect"],
                "output_directory": self.test_output_dir,
            }
            mock_chained.return_value = mock_result

            # Execute
            result = await execute_dual_engine_workflow(
                requirement=self.test_requirement,
                output_dir=self.test_output_dir,
                request_context=self.test_request_context,
            )

            # Verify results
            assert result["success"] == True
            assert result["engine_used"] == "chained"
            assert result["dual_engine_enabled"] == True
            assert "execution_id" in result
            assert result["quality_score"] == 88.5

            # Verify tracking calls
            mock_start_tracking.assert_called_once()
            mock_end_tracking.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_dual_engine_workflow_failure(self):
        """Test dual-engine workflow execution with failure"""
        with (
            patch(
                "shared.orchestration.dual_engine_executor.get_orchestration_engine"
            ) as mock_get_engine,
            patch(
                "shared.orchestration.dual_engine_executor.start_execution_tracking"
            ) as mock_start_tracking,
            patch(
                "shared.orchestration.dual_engine_executor.end_execution_tracking"
            ) as mock_end_tracking,
            patch(
                "shared.orchestration.dual_engine_executor._execute_coherent_workflow"
            ) as mock_coherent,
        ):

            # Setup mocks
            mock_get_engine.return_value = "coherent"
            mock_start_tracking.return_value = MagicMock(execution_id="test_456")
            mock_end_tracking.return_value = MagicMock()
            mock_coherent.side_effect = Exception("Coherent engine failed")

            # Execute
            result = await execute_dual_engine_workflow(
                requirement=self.test_requirement,
                output_dir=self.test_output_dir,
                request_context=self.test_request_context,
            )

            # Verify error handling
            assert result["success"] == False
            assert "error" in result
            assert result["engine_used"] == "coherent"
            assert result["dual_engine_enabled"] == True

            # Verify error tracking
            mock_end_tracking.assert_called_once()
            call_args = mock_end_tracking.call_args[1]
            assert call_args["success"] == False
            assert "error_message" in call_args

    @pytest.mark.asyncio
    async def test_execute_dual_engine_workflow_with_correlation_id(self):
        """Test dual-engine workflow with custom correlation ID"""
        correlation_id = "custom_correlation_123"

        with (
            patch(
                "shared.orchestration.dual_engine_executor.get_orchestration_engine"
            ) as mock_get_engine,
            patch(
                "shared.orchestration.dual_engine_executor.start_execution_tracking"
            ) as mock_start_tracking,
            patch(
                "shared.orchestration.dual_engine_executor._execute_chained_workflow"
            ) as mock_chained,
        ):

            mock_get_engine.return_value = "chained"
            mock_chained.return_value = {"success": True}

            result = await execute_dual_engine_workflow(
                requirement=self.test_requirement,
                output_dir=self.test_output_dir,
                correlation_id=correlation_id,
            )

            assert result["execution_id"] == correlation_id
            mock_start_tracking.assert_called_with(
                execution_id=correlation_id, engine_type="chained", request_context={}
            )

    @pytest.mark.asyncio
    async def test_execute_chained_workflow(self):
        """Test chained workflow execution"""
        with patch("chained_workflow.ChainedWorkflow") as mock_workflow_class:
            mock_workflow = MagicMock()
            mock_workflow.execute_chained_workflow.return_value = {
                "success": True,
                "quality_score": 92.0,
                "persona_results": {
                    "RequirementAnalyst": {"status": "complete"},
                    "SolutionArchitect": {"status": "complete"},
                },
            }
            mock_workflow_class.return_value = mock_workflow

            result = await _execute_chained_workflow(
                requirement=self.test_requirement,
                output_dir=self.test_output_dir,
                request_context=self.test_request_context,
            )

            assert result["success"] == True
            assert result["engine_type"] == "chained"
            assert "persona_executions" in result
            assert len(result["persona_executions"]) == 2
            mock_workflow.execute_chained_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_coherent_workflow_success(self):
        """Test coherent workflow execution success"""
        mock_coherent_executor = MagicMock()
        mock_coherent_executor.persona_classes = {
            "RequirementAnalyst": MagicMock(),
            "SolutionArchitect": MagicMock(),
            "BackendDeveloper": MagicMock(),
        }

        with patch(
            "coherent_persona_executor.CoherentPersonaExecutor", return_value=mock_coherent_executor
        ):
            result = await _execute_coherent_workflow(
                requirement=self.test_requirement,
                output_dir=self.test_output_dir,
                request_context=self.test_request_context,
            )

            assert result["success"] == True
            assert result["engine_type"] == "coherent"
            assert result["quality_score"] == 95.0  # Simulated enhanced quality
            assert len(result["persona_executions"]) == 3
            assert "enhanced_features" in result
            assert result["enhanced_features"]["cross_persona_coordination"] == True

    @pytest.mark.asyncio
    async def test_execute_coherent_workflow_unavailable(self):
        """Test coherent workflow when coherent executor is unavailable"""
        with patch(
            "coherent_persona_executor.CoherentPersonaExecutor",
            side_effect=ImportError("Module not available"),
        ):
            result = await _execute_coherent_workflow(
                requirement=self.test_requirement,
                output_dir=self.test_output_dir,
                request_context=self.test_request_context,
            )

            assert result["success"] == False
            assert "CoherentPersonaExecutor not available" in result["error"]
            assert result["fallback_recommended"] == True

    @pytest.mark.asyncio
    async def test_execute_coherent_workflow_execution_error(self):
        """Test coherent workflow with execution error"""
        mock_coherent_executor = MagicMock()
        mock_coherent_executor.persona_classes = {}

        with patch(
            "coherent_persona_executor.CoherentPersonaExecutor", return_value=mock_coherent_executor
        ):
            # Simulate an error during execution
            with patch("shared.orchestration.dual_engine_executor.datetime") as mock_datetime:
                mock_datetime.utcnow.side_effect = Exception("Execution error")

                result = await _execute_coherent_workflow(
                    requirement=self.test_requirement,
                    output_dir=self.test_output_dir,
                    request_context=self.test_request_context,
                )

                assert result["success"] == False
                assert "Coherent execution failed" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_hybrid_workflow_high_complexity(self):
        """Test hybrid workflow routing for high complexity"""
        mock_coherent_executor = MagicMock()
        mock_coherent_executor.persona_classes = {"test": MagicMock()}

        with (
            patch(
                "coherent_persona_executor.CoherentPersonaExecutor",
                return_value=mock_coherent_executor,
            ),
            patch(
                "shared.orchestration.dual_engine_executor._execute_coherent_workflow"
            ) as mock_coherent,
        ):

            mock_coherent.return_value = {"success": True, "engine_type": "coherent"}
            request_context = {"complexity": "high"}

            result = await _execute_hybrid_workflow(
                requirement=self.test_requirement,
                output_dir=self.test_output_dir,
                request_context=request_context,
            )

            mock_coherent.assert_called_once()
            assert result["engine_type"] == "coherent"

    @pytest.mark.asyncio
    async def test_execute_hybrid_workflow_low_complexity(self):
        """Test hybrid workflow routing for low complexity"""
        with patch(
            "shared.orchestration.dual_engine_executor._execute_chained_workflow"
        ) as mock_chained:
            mock_chained.return_value = {"success": True, "engine_type": "chained"}
            request_context = {"complexity": "low"}

            result = await _execute_hybrid_workflow(
                requirement=self.test_requirement,
                output_dir=self.test_output_dir,
                request_context=request_context,
            )

            mock_chained.assert_called_once()
            assert result["engine_type"] == "chained"

    @pytest.mark.asyncio
    async def test_execute_hybrid_workflow_coherent_fallback(self):
        """Test hybrid workflow fallback from coherent to chained"""
        with (
            patch(
                "shared.orchestration.dual_engine_executor._execute_coherent_workflow"
            ) as mock_coherent,
            patch(
                "shared.orchestration.dual_engine_executor._execute_chained_workflow"
            ) as mock_chained,
        ):

            # Coherent fails, should fallback to chained
            mock_coherent.side_effect = Exception("Coherent failed")
            mock_chained.return_value = {"success": True, "engine_type": "chained"}
            request_context = {"complexity": "enterprise"}

            result = await _execute_hybrid_workflow(
                requirement=self.test_requirement,
                output_dir=self.test_output_dir,
                request_context=request_context,
            )

            mock_coherent.assert_called_once()
            mock_chained.assert_called_once()
            assert result["engine_type"] == "chained"

    def test_get_engine_capabilities_with_coherent_executor(self):
        """Test getting engine capabilities when coherent executor is available"""
        mock_coherent_executor = MagicMock()
        mock_coherent_executor.persona_classes = {
            "RequirementAnalyst": MagicMock(),
            "SolutionArchitect": MagicMock(),
            "BackendDeveloper": MagicMock(),
            "QAEngineer": MagicMock(),
        }

        with patch(
            "coherent_persona_executor.CoherentPersonaExecutor", return_value=mock_coherent_executor
        ):
            capabilities = get_engine_capabilities()

            assert "chained" in capabilities
            assert "coherent" in capabilities
            assert capabilities["dual_engine_enabled"] == True
            assert capabilities["intelligent_routing"] == True

            # Check chained engine capabilities
            chained = capabilities["chained"]
            assert chained["status"] == "available"
            assert chained["personas"] == 10
            assert chained["quality_score"] == 98.8

            # Check coherent engine capabilities
            coherent = capabilities["coherent"]
            assert coherent["status"] == "available"
            assert coherent["personas"] == 4
            assert coherent["quality_score"] == 95.0
            assert "Parallel execution" in coherent["features"]

    def test_get_engine_capabilities_without_coherent_executor(self):
        """Test getting engine capabilities when coherent executor is unavailable"""
        with patch(
            "coherent_persona_executor.CoherentPersonaExecutor",
            side_effect=ImportError("Module not available"),
        ):
            capabilities = get_engine_capabilities()

            assert "chained" in capabilities
            assert "coherent" in capabilities
            assert capabilities["dual_engine_enabled"] == False

            # Chained should still be available
            assert capabilities["chained"]["status"] == "available"

            # Coherent should be unavailable
            assert capabilities["coherent"]["status"] == "unavailable"
            assert capabilities["coherent"]["personas"] == 0

    @pytest.mark.asyncio
    async def test_workflow_execution_with_quality_tracking(self):
        """Test workflow execution includes quality score tracking"""
        with (
            patch(
                "shared.orchestration.dual_engine_executor.get_orchestration_engine"
            ) as mock_get_engine,
            patch(
                "shared.orchestration.dual_engine_executor.start_execution_tracking"
            ) as mock_start_tracking,
            patch(
                "shared.orchestration.dual_engine_executor.end_execution_tracking"
            ) as mock_end_tracking,
            patch(
                "shared.orchestration.dual_engine_executor._execute_chained_workflow"
            ) as mock_chained,
        ):

            mock_get_engine.return_value = "chained"
            mock_start_tracking.return_value = MagicMock(execution_id="quality_test")

            mock_result = {
                "success": True,
                "quality_score": 91.5,
                "persona_executions": ["P1", "P2", "P3"],
            }
            mock_chained.return_value = mock_result

            result = await execute_dual_engine_workflow(
                requirement=self.test_requirement,
                output_dir=self.test_output_dir,
                request_context=self.test_request_context,
            )

            # Verify quality tracking
            mock_end_tracking.assert_called_once()
            call_args = mock_end_tracking.call_args[1]
            assert call_args["quality_score"] == 91.5
            assert call_args["persona_executions"] == ["P1", "P2", "P3"]
            assert call_args["success"] == True

    @pytest.mark.asyncio
    async def test_workflow_execution_performance_timing(self):
        """Test workflow execution includes performance timing"""
        start_time = datetime.utcnow()

        with (
            patch(
                "shared.orchestration.dual_engine_executor.get_orchestration_engine"
            ) as mock_get_engine,
            patch("shared.orchestration.dual_engine_executor.start_execution_tracking"),
            patch("shared.orchestration.dual_engine_executor.end_execution_tracking"),
            patch(
                "shared.orchestration.dual_engine_executor._execute_chained_workflow"
            ) as mock_chained,
        ):

            mock_get_engine.return_value = "chained"
            mock_chained.return_value = {"success": True, "quality_score": 85.0}

            result = await execute_dual_engine_workflow(
                requirement=self.test_requirement, output_dir=self.test_output_dir
            )

            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()

            # Execution should complete quickly in test
            assert execution_time < 1.0
            assert result["success"] == True

    @pytest.mark.asyncio
    async def test_engine_selection_based_on_context(self):
        """Test that engine selection respects request context"""
        test_cases = [
            ({"complexity": "low"}, "chained"),
            ({"complexity": "high"}, "coherent"),
            ({"user_id": "test_user"}, "chained"),  # Default case
        ]

        for request_context, expected_engine_type in test_cases:
            with patch(
                "shared.orchestration.dual_engine_executor.get_orchestration_engine"
            ) as mock_get_engine:
                mock_get_engine.return_value = expected_engine_type

                with patch(
                    f"shared.orchestration.dual_engine_executor._execute_{expected_engine_type}_workflow"
                ) as mock_execute:
                    mock_execute.return_value = {"success": True}

                    result = await execute_dual_engine_workflow(
                        requirement=self.test_requirement,
                        output_dir=self.test_output_dir,
                        request_context=request_context,
                    )

                    assert result["engine_used"] == expected_engine_type
                    mock_get_engine.assert_called_with(request_context)

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Test comprehensive error handling and recovery mechanisms"""
        # Test various error scenarios
        error_scenarios = [
            ("Engine selection failure", "get_orchestration_engine"),
            ("Execution tracking failure", "start_execution_tracking"),
        ]

        for error_description, mock_target in error_scenarios:
            with patch(
                f"shared.orchestration.dual_engine_executor.{mock_target}"
            ) as mock_component:
                mock_component.side_effect = Exception(f"Simulated {error_description}")

                result = await execute_dual_engine_workflow(
                    requirement=self.test_requirement, output_dir=self.test_output_dir
                )

                assert result["success"] == False
                assert "error" in result
                assert result["dual_engine_enabled"] == True

    @pytest.mark.asyncio
    async def test_concurrent_execution_support(self):
        """Test that multiple concurrent executions are supported"""
        concurrent_executions = []

        with (
            patch(
                "shared.orchestration.dual_engine_executor.get_orchestration_engine"
            ) as mock_get_engine,
            patch("shared.orchestration.dual_engine_executor.start_execution_tracking"),
            patch("shared.orchestration.dual_engine_executor.end_execution_tracking"),
            patch(
                "shared.orchestration.dual_engine_executor._execute_chained_workflow"
            ) as mock_chained,
        ):

            mock_get_engine.return_value = "chained"
            mock_chained.return_value = {"success": True, "quality_score": 88.0}

            # Start multiple concurrent executions
            for i in range(3):
                task = execute_dual_engine_workflow(
                    requirement=f"Requirement {i}",
                    output_dir=self.test_output_dir,
                    request_context={"user_id": f"user_{i}"},
                )
                concurrent_executions.append(task)

            # Wait for all to complete
            results = await asyncio.gather(*concurrent_executions)

            # All should succeed
            for result in results:
                assert result["success"] == True
                assert result["dual_engine_enabled"] == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
