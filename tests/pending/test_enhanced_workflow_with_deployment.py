#!/usr/bin/env python3
"""
Unit tests for Enhanced Workflow with Deployment Integration
"""
import asyncio
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from enhanced_workflow_with_deployment import EnhancedWorkflowOrchestrator

# Fix import path for enhanced workflow system
# Use Poetry and relative imports instead of hardcoded paths



class TestEnhancedWorkflowOrchestrator:
    """Test suite for Enhanced Workflow Orchestrator"""

    def setup_method(self):
        """Setup test fixtures"""
        # Mock the dependencies to avoid import issues
        with patch("enhanced_workflow_with_deployment.FocusedOrchestrationCore"):
            with patch("enhanced_workflow_with_deployment.EnhancedCoherentDomainSystem"):
                with patch("enhanced_workflow_with_deployment.DeploymentOrchestrator"):
                    self.orchestrator = EnhancedWorkflowOrchestrator(auto_deploy=False)

                    # Mock the dependent systems
                    self.orchestrator.focused_orchestrator = MagicMock()
                    self.orchestrator.coherent_system = MagicMock()
                    self.orchestrator.deployment_orchestrator = MagicMock()

    def test_orchestrator_initialization(self):
        """Test enhanced workflow orchestrator initialization"""
        assert hasattr(self.orchestrator, "focused_orchestrator")
        assert hasattr(self.orchestrator, "coherent_system")
        assert hasattr(self.orchestrator, "deployment_orchestrator")
        assert self.orchestrator.auto_deploy is False

    def test_orchestrator_initialization_with_auto_deploy(self):
        """Test orchestrator initialization with auto-deploy enabled"""
        with patch("enhanced_workflow_with_deployment.FocusedOrchestrationCore"):
            with patch("enhanced_workflow_with_deployment.EnhancedCoherentDomainSystem"):
                with patch("enhanced_workflow_with_deployment.DeploymentOrchestrator"):
                    auto_deploy_orchestrator = EnhancedWorkflowOrchestrator(auto_deploy=True)
                    assert auto_deploy_orchestrator.auto_deploy is True

    @pytest.mark.asyncio
    async def test_execute_complete_workflow_success_without_deployment(self):
        """Test complete workflow execution without deployment"""
        # Mock successful code generation
        mock_workflow_result = {
            "success": True,
            "output_dir": "/tmp/test_output",
            "all_generated_files": ["file1.py", "file2.py", "file3.js"],
            "execution_time": 45.0,
            "personas_used": ["backend_developer", "frontend_developer"],
        }

        # Mock the code generation workflow
        with patch.object(
            self.orchestrator, "_execute_code_generation_workflow", new_callable=AsyncMock
        ) as mock_codegen:
            mock_codegen.return_value = mock_workflow_result

            result = await self.orchestrator.execute_complete_workflow(
                requirement="Create a simple web application",
                personas=["backend_developer", "frontend_developer"],
                deploy_after_generation=False,
            )

            assert result is not None
            assert result["success"] is True
            assert result["output_dir"] == "/tmp/test_output"
            assert len(result["all_generated_files"]) == 3
            assert result["deployment"]["status"] == "skipped"
            assert result["deployment"]["reason"] == "Deployment disabled"

    @pytest.mark.asyncio
    async def test_execute_complete_workflow_with_deployment(self):
        """Test complete workflow execution with deployment"""
        # Mock successful code generation
        mock_workflow_result = {
            "success": True,
            "output_dir": "/tmp/test_output",
            "all_generated_files": ["file1.py", "file2.py"],
            "execution_time": 60.0,
        }

        # Mock successful deployment
        mock_deployment_result = {
            "result": {
                "status": "success",
                "deployment_url": "https://test-app.example.com",
                "deployment_time": 120.0,
            },
            "infrastructure": {"containers": ["app-container"], "services": ["web-service"]},
        }

        with patch.object(
            self.orchestrator, "_execute_code_generation_workflow", new_callable=AsyncMock
        ) as mock_codegen:
            with patch.object(
                self.orchestrator, "_execute_deployment_phase", new_callable=AsyncMock
            ) as mock_deploy:
                mock_codegen.return_value = mock_workflow_result
                mock_deploy.return_value = mock_deployment_result

                result = await self.orchestrator.execute_complete_workflow(
                    requirement="Create deployable web service",
                    deploy_after_generation=True,
                    deployment_strategy="standard",
                )

                assert result["success"] is True
                assert result["deployment"]["result"]["status"] == "success"
                assert "deployment_url" in result["deployment"]["result"]
                mock_deploy.assert_called_once_with(mock_workflow_result, "standard")

    @pytest.mark.asyncio
    async def test_execute_complete_workflow_code_generation_failure(self):
        """Test workflow execution when code generation fails"""
        # Mock failed code generation
        mock_failed_result = {
            "success": False,
            "error": "Persona execution failed",
            "phase": "code_generation",
        }

        with patch.object(
            self.orchestrator, "_execute_code_generation_workflow", new_callable=AsyncMock
        ) as mock_codegen:
            mock_codegen.return_value = mock_failed_result

            result = await self.orchestrator.execute_complete_workflow(
                requirement="Invalid requirement that causes failure", deploy_after_generation=True
            )

            assert result["success"] is False
            assert result["phase"] == "code_generation_failed"
            assert result["deployment"]["status"] == "skipped"
            assert result["deployment"]["reason"] == "Code generation failed"

    @pytest.mark.asyncio
    async def test_execute_complete_workflow_deployment_failure(self):
        """Test workflow execution when deployment fails"""
        # Mock successful code generation
        mock_workflow_result = {
            "success": True,
            "output_dir": "/tmp/test_output",
            "all_generated_files": ["app.py"],
        }

        # Mock failed deployment
        mock_deployment_failure = {
            "result": {"status": "failed", "error": "Docker build failed", "deployment_time": 30.0}
        }

        with patch.object(
            self.orchestrator, "_execute_code_generation_workflow", new_callable=AsyncMock
        ) as mock_codegen:
            with patch.object(
                self.orchestrator, "_execute_deployment_phase", new_callable=AsyncMock
            ) as mock_deploy:
                mock_codegen.return_value = mock_workflow_result
                mock_deploy.return_value = mock_deployment_failure

                result = await self.orchestrator.execute_complete_workflow(
                    requirement="App with deployment issues", deploy_after_generation=True
                )

                assert result["success"] is True  # Code generation succeeded
                assert result["deployment"]["result"]["status"] == "failed"
                assert "error" in result["deployment"]["result"]

    @pytest.mark.asyncio
    async def test_auto_deploy_default_behavior(self):
        """Test auto-deploy default behavior"""
        # Test with auto_deploy=True instance
        with patch("enhanced_workflow_with_deployment.FocusedOrchestrationCore"):
            with patch("enhanced_workflow_with_deployment.EnhancedCoherentDomainSystem"):
                with patch("enhanced_workflow_with_deployment.DeploymentOrchestrator"):
                    auto_deploy_orchestrator = EnhancedWorkflowOrchestrator(auto_deploy=True)
                    auto_deploy_orchestrator.focused_orchestrator = MagicMock()
                    auto_deploy_orchestrator.coherent_system = MagicMock()
                    auto_deploy_orchestrator.deployment_orchestrator = MagicMock()

                    mock_workflow_result = {"success": True, "output_dir": "/tmp/test"}

                    with patch.object(
                        auto_deploy_orchestrator,
                        "_execute_code_generation_workflow",
                        new_callable=AsyncMock,
                    ) as mock_codegen:
                        with patch.object(
                            auto_deploy_orchestrator,
                            "_execute_deployment_phase",
                            new_callable=AsyncMock,
                        ) as mock_deploy:
                            mock_codegen.return_value = mock_workflow_result
                            mock_deploy.return_value = {"result": {"status": "success"}}

                            # Don't specify deploy_after_generation - should use instance default (True)
                            result = await auto_deploy_orchestrator.execute_complete_workflow(
                                requirement="Test auto-deploy behavior"
                            )

                            # Should have called deployment since auto_deploy=True
                            mock_deploy.assert_called_once()

    @pytest.mark.asyncio
    async def test_different_deployment_strategies(self):
        """Test different deployment strategies"""
        mock_workflow_result = {
            "success": True,
            "output_dir": "/tmp/test_output",
            "all_generated_files": ["app.py"],
        }

        mock_deployment_result = {"result": {"status": "success", "strategy": "canary"}}

        with patch.object(
            self.orchestrator, "_execute_code_generation_workflow", new_callable=AsyncMock
        ) as mock_codegen:
            with patch.object(
                self.orchestrator, "_execute_deployment_phase", new_callable=AsyncMock
            ) as mock_deploy:
                mock_codegen.return_value = mock_workflow_result
                mock_deploy.return_value = mock_deployment_result

                # Test canary deployment
                result = await self.orchestrator.execute_complete_workflow(
                    requirement="Test canary deployment",
                    deploy_after_generation=True,
                    deployment_strategy="canary",
                )

                mock_deploy.assert_called_with(mock_workflow_result, "canary")

                # Test blue-green deployment
                await self.orchestrator.execute_complete_workflow(
                    requirement="Test blue-green deployment",
                    deploy_after_generation=True,
                    deployment_strategy="blue_green",
                )

                mock_deploy.assert_called_with(mock_workflow_result, "blue_green")

    @pytest.mark.asyncio
    async def test_workflow_with_specific_personas(self):
        """Test workflow execution with specific personas"""
        test_personas = ["backend_developer", "devops_engineer", "qa_engineer"]
        requirement = "Create microservice with deployment pipeline"

        mock_workflow_result = {
            "success": True,
            "personas_used": test_personas,
            "output_dir": "/tmp/microservice",
        }

        with patch.object(
            self.orchestrator, "_execute_code_generation_workflow", new_callable=AsyncMock
        ) as mock_codegen:
            mock_codegen.return_value = mock_workflow_result

            result = await self.orchestrator.execute_complete_workflow(
                requirement=requirement, personas=test_personas, deploy_after_generation=False
            )

            # Verify personas were passed to code generation
            mock_codegen.assert_called_once_with(requirement, test_personas)
            assert result["personas_used"] == test_personas

    @pytest.mark.asyncio
    async def test_workflow_timing_and_metrics(self):
        """Test workflow timing and metrics collection"""
        mock_workflow_result = {
            "success": True,
            "execution_time": 75.5,
            "output_dir": "/tmp/timed_test",
        }

        mock_deployment_result = {
            "result": {
                "status": "success",
                "deployment_time": 180.2,
                "deployment_url": "https://test.example.com",
            }
        }

        with patch.object(
            self.orchestrator, "_execute_code_generation_workflow", new_callable=AsyncMock
        ) as mock_codegen:
            with patch.object(
                self.orchestrator, "_execute_deployment_phase", new_callable=AsyncMock
            ) as mock_deploy:
                mock_codegen.return_value = mock_workflow_result
                mock_deploy.return_value = mock_deployment_result

                start_time = datetime.now()
                result = await self.orchestrator.execute_complete_workflow(
                    requirement="Test timing metrics", deploy_after_generation=True
                )
                end_time = datetime.now()

                # Check timing information is preserved
                assert result["execution_time"] == 75.5
                assert result["deployment"]["result"]["deployment_time"] == 180.2

                # Verify workflow has timing data
                assert "workflow_start_time" in result
                assert "workflow_end_time" in result
                assert "total_workflow_time" in result

                # Verify total time is reasonable
                total_time = result["total_workflow_time"]
                actual_duration = (end_time - start_time).total_seconds()
                assert abs(total_time - actual_duration) < 1.0  # Within 1 second tolerance

    def test_workflow_configuration_options(self):
        """Test various workflow configuration options"""
        # Test different initialization configurations
        configs = [{"auto_deploy": True}, {"auto_deploy": False}]

        for config in configs:
            with patch("enhanced_workflow_with_deployment.FocusedOrchestrationCore"):
                with patch("enhanced_workflow_with_deployment.EnhancedCoherentDomainSystem"):
                    with patch("enhanced_workflow_with_deployment.DeploymentOrchestrator"):
                        orchestrator = EnhancedWorkflowOrchestrator(**config)
                        assert orchestrator.auto_deploy == config["auto_deploy"]

    @pytest.mark.asyncio
    async def test_error_handling_in_workflow_phases(self):
        """Test error handling in different workflow phases"""
        # Test exception in code generation
        with patch.object(
            self.orchestrator, "_execute_code_generation_workflow", new_callable=AsyncMock
        ) as mock_codegen:
            mock_codegen.side_effect = Exception("Code generation system error")

            with pytest.raises(Exception, match="Code generation system error"):
                await self.orchestrator.execute_complete_workflow(
                    requirement="Test error handling", deploy_after_generation=False
                )

        # Test exception in deployment phase
        mock_workflow_result = {"success": True, "output_dir": "/tmp/test"}

        with patch.object(
            self.orchestrator, "_execute_code_generation_workflow", new_callable=AsyncMock
        ) as mock_codegen:
            with patch.object(
                self.orchestrator, "_execute_deployment_phase", new_callable=AsyncMock
            ) as mock_deploy:
                mock_codegen.return_value = mock_workflow_result
                mock_deploy.side_effect = Exception("Deployment system error")

                with pytest.raises(Exception, match="Deployment system error"):
                    await self.orchestrator.execute_complete_workflow(
                        requirement="Test deployment error", deploy_after_generation=True
                    )

    @pytest.mark.asyncio
    async def test_workflow_result_structure(self):
        """Test the structure of workflow results"""
        mock_workflow_result = {
            "success": True,
            "output_dir": "/tmp/structure_test",
            "all_generated_files": ["main.py", "config.yaml", "Dockerfile"],
            "execution_time": 42.0,
            "personas_used": ["backend_developer"],
            "quality_metrics": {"test_coverage": 0.85, "code_quality": 0.90},
        }

        mock_deployment_result = {
            "result": {
                "status": "success",
                "deployment_url": "https://app.example.com",
                "deployment_time": 67.3,
                "health_check_url": "https://app.example.com/health",
            },
            "infrastructure": {
                "containers": ["app-container", "db-container"],
                "networks": ["app-network"],
                "volumes": ["data-volume"],
            },
        }

        with patch.object(
            self.orchestrator, "_execute_code_generation_workflow", new_callable=AsyncMock
        ) as mock_codegen:
            with patch.object(
                self.orchestrator, "_execute_deployment_phase", new_callable=AsyncMock
            ) as mock_deploy:
                mock_codegen.return_value = mock_workflow_result
                mock_deploy.return_value = mock_deployment_result

                result = await self.orchestrator.execute_complete_workflow(
                    requirement="Test result structure",
                    deploy_after_generation=True,
                    deployment_strategy="standard",
                )

                # Verify top-level structure
                assert "success" in result
                assert "output_dir" in result
                assert "all_generated_files" in result
                assert "execution_time" in result
                assert "deployment" in result
                assert "workflow_start_time" in result
                assert "workflow_end_time" in result
                assert "total_workflow_time" in result

                # Verify deployment structure
                deployment = result["deployment"]
                assert "result" in deployment
                assert "infrastructure" in deployment
                assert deployment["result"]["status"] == "success"
                assert "deployment_url" in deployment["result"]

                # Verify inherited fields from code generation
                assert result["quality_metrics"]["test_coverage"] == 0.85
                assert len(result["all_generated_files"]) == 3


class TestWorkflowIntegrationScenarios:
    """Test integration scenarios for Enhanced Workflow with Deployment"""

    @pytest.mark.asyncio
    async def test_end_to_end_workflow_simulation(self):
        """Test end-to-end workflow simulation"""
        with patch("enhanced_workflow_with_deployment.FocusedOrchestrationCore"):
            with patch("enhanced_workflow_with_deployment.EnhancedCoherentDomainSystem"):
                with patch("enhanced_workflow_with_deployment.DeploymentOrchestrator"):
                    orchestrator = EnhancedWorkflowOrchestrator(auto_deploy=True)

                    # Mock all dependencies
                    orchestrator.focused_orchestrator = MagicMock()
                    orchestrator.coherent_system = MagicMock()
                    orchestrator.deployment_orchestrator = MagicMock()

                    # Simulate realistic workflow result
                    realistic_workflow_result = {
                        "success": True,
                        "output_dir": "/tmp/e2e_test_project",
                        "all_generated_files": [
                            "src/main.py",
                            "src/models.py",
                            "src/api.py",
                            "tests/test_main.py",
                            "requirements.txt",
                            "Dockerfile",
                            "docker-compose.yml",
                            "README.md",
                        ],
                        "execution_time": 127.5,
                        "personas_used": [
                            "requirement_analyst",
                            "solution_architect",
                            "backend_developer",
                            "qa_engineer",
                            "devops_engineer",
                        ],
                        "quality_metrics": {
                            "test_coverage": 0.87,
                            "code_quality": 0.92,
                            "documentation_score": 0.89,
                        },
                    }

                    # Simulate realistic deployment result
                    realistic_deployment_result = {
                        "result": {
                            "status": "success",
                            "deployment_url": "https://e2e-test-app.example.com",
                            "deployment_time": 245.7,
                            "health_check_url": "https://e2e-test-app.example.com/health",
                            "deployment_id": "deploy_abc123",
                        },
                        "infrastructure": {
                            "containers": ["app-container", "db-container", "redis-container"],
                            "networks": ["app-network", "db-network"],
                            "volumes": ["data-volume", "logs-volume"],
                            "services": ["web-service", "api-service", "db-service"],
                        },
                    }

                    with patch.object(
                        orchestrator, "_execute_code_generation_workflow", new_callable=AsyncMock
                    ) as mock_codegen:
                        with patch.object(
                            orchestrator, "_execute_deployment_phase", new_callable=AsyncMock
                        ) as mock_deploy:
                            mock_codegen.return_value = realistic_workflow_result
                            mock_deploy.return_value = realistic_deployment_result

                            result = await orchestrator.execute_complete_workflow(
                                requirement="Create a scalable REST API with authentication, user management, and real-time notifications",
                                personas=[
                                    "requirement_analyst",
                                    "solution_architect",
                                    "backend_developer",
                                    "qa_engineer",
                                    "devops_engineer",
                                ],
                                deployment_strategy="standard",
                            )

                            # Verify comprehensive result
                            assert result["success"] is True
                            assert len(result["all_generated_files"]) == 8
                            assert len(result["personas_used"]) == 5
                            assert result["quality_metrics"]["test_coverage"] == 0.87
                            assert result["deployment"]["result"]["status"] == "success"
                            assert len(result["deployment"]["infrastructure"]["containers"]) == 3
                            assert result["total_workflow_time"] > 0

    @pytest.mark.asyncio
    async def test_canary_deployment_workflow(self):
        """Test workflow with canary deployment strategy"""
        with patch("enhanced_workflow_with_deployment.FocusedOrchestrationCore"):
            with patch("enhanced_workflow_with_deployment.EnhancedCoherentDomainSystem"):
                with patch("enhanced_workflow_with_deployment.DeploymentOrchestrator"):
                    orchestrator = EnhancedWorkflowOrchestrator()

                    orchestrator.focused_orchestrator = MagicMock()
                    orchestrator.coherent_system = MagicMock()
                    orchestrator.deployment_orchestrator = MagicMock()

                    canary_workflow_result = {
                        "success": True,
                        "output_dir": "/tmp/canary_app",
                        "all_generated_files": ["app.py", "Dockerfile"],
                    }

                    canary_deployment_result = {
                        "result": {
                            "status": "success",
                            "deployment_strategy": "canary",
                            "canary_percentage": 10,
                            "canary_url": "https://canary.example.com",
                            "production_url": "https://prod.example.com",
                        }
                    }

                    with patch.object(
                        orchestrator, "_execute_code_generation_workflow", new_callable=AsyncMock
                    ) as mock_codegen:
                        with patch.object(
                            orchestrator, "_execute_deployment_phase", new_callable=AsyncMock
                        ) as mock_deploy:
                            mock_codegen.return_value = canary_workflow_result
                            mock_deploy.return_value = canary_deployment_result

                            result = await orchestrator.execute_complete_workflow(
                                requirement="Deploy API with canary strategy",
                                deploy_after_generation=True,
                                deployment_strategy="canary",
                            )

                            mock_deploy.assert_called_with(canary_workflow_result, "canary")
                            assert result["deployment"]["result"]["deployment_strategy"] == "canary"
                            assert result["deployment"]["result"]["canary_percentage"] == 10

    @pytest.mark.asyncio
    async def test_workflow_with_rollback_scenario(self):
        """Test workflow handling rollback scenarios"""
        with patch("enhanced_workflow_with_deployment.FocusedOrchestrationCore"):
            with patch("enhanced_workflow_with_deployment.EnhancedCoherentDomainSystem"):
                with patch("enhanced_workflow_with_deployment.DeploymentOrchestrator"):
                    orchestrator = EnhancedWorkflowOrchestrator()

                    orchestrator.focused_orchestrator = MagicMock()
                    orchestrator.coherent_system = MagicMock()
                    orchestrator.deployment_orchestrator = MagicMock()

                    rollback_workflow_result = {
                        "success": True,
                        "output_dir": "/tmp/rollback_test",
                        "all_generated_files": ["app.py"],
                    }

                    # Simulate deployment failure that might require rollback
                    failed_deployment_result = {
                        "result": {
                            "status": "failed",
                            "error": "Health check failed after deployment",
                            "rollback_triggered": True,
                            "previous_version_restored": True,
                            "rollback_time": 45.2,
                        }
                    }

                    with patch.object(
                        orchestrator, "_execute_code_generation_workflow", new_callable=AsyncMock
                    ) as mock_codegen:
                        with patch.object(
                            orchestrator, "_execute_deployment_phase", new_callable=AsyncMock
                        ) as mock_deploy:
                            mock_codegen.return_value = rollback_workflow_result
                            mock_deploy.return_value = failed_deployment_result

                            result = await orchestrator.execute_complete_workflow(
                                requirement="Test deployment with rollback",
                                deploy_after_generation=True,
                                deployment_strategy="blue_green",
                            )

                            assert result["success"] is True  # Code generation succeeded
                            assert result["deployment"]["result"]["status"] == "failed"
                            assert result["deployment"]["result"]["rollback_triggered"] is True
                            assert (
                                result["deployment"]["result"]["previous_version_restored"] is True
                            )
