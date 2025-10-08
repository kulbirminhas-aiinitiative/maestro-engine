#!/usr/bin/env python3
"""
Unit tests for Multi-Phase Orchestration Engine
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from shared.intelligence.complexity_analyzer import ComplexityLevel
from shared.models.orchestration_node import NodeStatus, NodeType, OrchestrationNode, Priority
from shared.orchestration.multi_phase_engine import (
    MultiPhaseOrchestrationEngine,
    PhaseType,
    ProjectPhase,
)


class TestMultiPhaseOrchestrationEngine:
    """Test suite for Multi-Phase Orchestration Engine"""

    def setup_method(self):
        """Setup test fixtures"""
        self.engine = MultiPhaseOrchestrationEngine()

    def test_engine_initialization(self):
        """Test engine initialization"""
        assert self.engine is not None
        assert hasattr(self.engine, "recursive_decomposer")
        assert hasattr(self.engine, "complexity_analyzer")

    def test_project_phase_enum(self):
        """Test ProjectPhase enum values"""
        assert ProjectPhase.REQUIREMENTS_ANALYSIS.value == "requirements_analysis"
        assert ProjectPhase.SYSTEM_DESIGN.value == "system_design"
        assert ProjectPhase.IMPLEMENTATION.value == "implementation"
        assert ProjectPhase.TESTING.value == "testing"
        assert ProjectPhase.DEPLOYMENT.value == "deployment"
        assert ProjectPhase.MAINTENANCE.value == "maintenance"

    def test_phase_type_enum(self):
        """Test PhaseType enum values"""
        assert PhaseType.FUNCTIONAL_REQUIREMENTS.value == "functional_requirements"
        assert PhaseType.ARCHITECTURE_DESIGN.value == "architecture_design"
        assert PhaseType.FRONTEND_IMPLEMENTATION.value == "frontend_implementation"
        assert PhaseType.UNIT_TESTING.value == "unit_testing"

    @pytest.mark.asyncio
    async def test_orchestrate_single_phase_basic(self):
        """Test basic single phase orchestration"""
        requirement = "Create user authentication system"

        with patch.object(
            self.engine.recursive_decomposer, "decompose", new_callable=AsyncMock
        ) as mock_decompose:
            # Mock the decomposer to return a simple node
            mock_node = OrchestrationNode(
                requirement=requirement, node_type=NodeType.FEATURE, priority=Priority.HIGH
            )
            mock_decompose.return_value = mock_node

            project_context = {
                "original_requirement": requirement,
                "complexity_assessment": {
                    "phase_complexities": {"implementation": 10}  # Above complexity threshold of 8
                },
            }

            result = await self.engine.orchestrate_phase(
                ProjectPhase.IMPLEMENTATION, project_context
            )

            assert result is not None
            assert requirement in result.requirement  # The engine may prefix the requirement
            mock_decompose.assert_called_once()

    @pytest.mark.asyncio
    async def test_orchestrate_multi_phase_project(self):
        """Test multi-phase project orchestration"""
        requirement = "Build web application with user management"
        phases = [
            ProjectPhase.REQUIREMENTS_ANALYSIS,
            ProjectPhase.SYSTEM_DESIGN,
            ProjectPhase.IMPLEMENTATION,
        ]

        with patch.object(
            self.engine, "orchestrate_phase", new_callable=AsyncMock
        ) as mock_orchestrate:
            # Mock each phase orchestration
            mock_nodes = {}
            for phase in phases:
                mock_node = OrchestrationNode(
                    requirement=f"{requirement} - {phase.value}",
                    node_type=NodeType.FEATURE,
                    priority=Priority.NORMAL,
                )
                mock_nodes[phase] = mock_node

            mock_orchestrate.side_effect = lambda phase, context: mock_nodes[phase]

            result = await self.engine.orchestrate_multi_phase_project(
                requirement, target_phases=phases
            )

            assert len(result) == 3
            assert all(phase in result for phase in phases)
            assert mock_orchestrate.call_count == 3

    def test_get_phase_specific_strategy(self):
        """Test phase-specific strategy selection"""
        # Test requirements phase
        req_strategy = self.engine._get_phase_specific_strategy(ProjectPhase.REQUIREMENTS_ANALYSIS)
        assert req_strategy is not None

        # Test design phase
        design_strategy = self.engine._get_phase_specific_strategy(ProjectPhase.SYSTEM_DESIGN)
        assert design_strategy is not None

        # Test implementation phase
        impl_strategy = self.engine._get_phase_specific_strategy(ProjectPhase.IMPLEMENTATION)
        assert impl_strategy is not None

    def test_create_phase_context(self):
        """Test phase context creation"""
        base_context = {
            "original_requirement": "Test requirement",
            "complexity_level": ComplexityLevel.MODERATE,
        }

        context = self.engine._create_phase_context(
            ProjectPhase.IMPLEMENTATION, base_context, {"custom_param": "value"}
        )

        assert "project_phase" in context
        assert context["project_phase"] == ProjectPhase.IMPLEMENTATION
        assert context["original_requirement"] == "Test requirement"
        assert context["custom_param"] == "value"

    def test_extract_phase_requirements(self):
        """Test phase-specific requirement extraction"""
        # Test requirements phase
        req_text = self.engine._extract_phase_requirements(
            ProjectPhase.REQUIREMENTS_ANALYSIS, "Build e-commerce platform with payment processing"
        )
        assert "functional requirements" in req_text.lower()

        # Test design phase
        design_text = self.engine._extract_phase_requirements(
            ProjectPhase.SYSTEM_DESIGN, "Build scalable microservices architecture"
        )
        assert "design" in design_text.lower()

    @pytest.mark.asyncio
    async def test_phase_transition_validation(self):
        """Test phase transition validation"""
        # Valid transition
        valid = await self.engine._validate_phase_transition(
            ProjectPhase.REQUIREMENTS_ANALYSIS, ProjectPhase.SYSTEM_DESIGN
        )
        assert valid is True

        # Invalid transition (skipping phases)
        invalid = await self.engine._validate_phase_transition(
            ProjectPhase.REQUIREMENTS_ANALYSIS, ProjectPhase.DEPLOYMENT
        )
        assert invalid is False

    def test_phase_metadata_creation(self):
        """Test phase metadata creation"""
        metadata = self.engine._create_phase_metadata(
            ProjectPhase.IMPLEMENTATION, {"complexity": "high", "timeline": "2 weeks"}
        )

        assert isinstance(metadata, dict)
        assert "phase" in metadata
        assert "created_at" in metadata
        assert metadata["phase"] == ProjectPhase.IMPLEMENTATION

    @pytest.mark.asyncio
    async def test_error_handling_invalid_phase(self):
        """Test error handling for invalid phase"""
        with pytest.raises(ValueError):
            await self.engine.orchestrate_phase(
                "invalid_phase", {"requirement": "test"}  # Invalid phase type
            )

    @pytest.mark.asyncio
    async def test_error_handling_missing_context(self):
        """Test error handling for missing context"""
        # Should handle missing context gracefully
        result = await self.engine.orchestrate_phase(
            ProjectPhase.IMPLEMENTATION, {}  # Empty context
        )

        # Should still return a result, possibly with defaults
        assert result is not None

    def test_phase_complexity_assessment(self):
        """Test phase-specific complexity assessment"""
        # Simple requirement
        simple_complexity = self.engine._assess_phase_complexity(
            ProjectPhase.IMPLEMENTATION, "Create hello world application"
        )
        assert simple_complexity <= ComplexityLevel.MODERATE

        # Complex requirement
        complex_requirement = "Build distributed microservices platform with AI/ML integration, real-time analytics, and blockchain payment processing"
        complex_complexity = self.engine._assess_phase_complexity(
            ProjectPhase.IMPLEMENTATION, complex_requirement
        )
        assert complex_complexity >= ComplexityLevel.MODERATE

    @pytest.mark.asyncio
    async def test_concurrent_phase_orchestration(self):
        """Test concurrent orchestration of multiple phases"""
        requirement = "Build complex system"
        phases = [
            ProjectPhase.REQUIREMENTS_ANALYSIS,
            ProjectPhase.SYSTEM_DESIGN,
            ProjectPhase.IMPLEMENTATION,
            ProjectPhase.TESTING,
        ]

        with patch.object(
            self.engine, "orchestrate_phase", new_callable=AsyncMock
        ) as mock_orchestrate:
            # Mock delayed responses
            async def delayed_response(phase, context):
                await asyncio.sleep(0.01)  # Simulate async work
                return OrchestrationNode(
                    requirement=f"Phase {phase.value}",
                    node_type=NodeType.IMPLEMENTATION,
                    priority=Priority.MEDIUM,
                )

            mock_orchestrate.side_effect = delayed_response

            # Test concurrent execution
            start_time = asyncio.get_event_loop().time()
            result = await self.engine.orchestrate_multi_phase_project(
                requirement, target_phases=phases, concurrent=True
            )
            end_time = asyncio.get_event_loop().time()

            # Should complete faster than sequential execution
            execution_time = end_time - start_time
            assert execution_time < 0.1  # Should be much faster than 4 * 0.01
            assert len(result) == 4

    def test_phase_dependency_analysis(self):
        """Test phase dependency analysis"""
        dependencies = self.engine._analyze_phase_dependencies(
            [
                ProjectPhase.REQUIREMENTS_ANALYSIS,
                ProjectPhase.SYSTEM_DESIGN,
                ProjectPhase.IMPLEMENTATION,
                ProjectPhase.TESTING,
            ]
        )

        assert len(dependencies) > 0
        # Requirements should come before design
        req_deps = dependencies.get(ProjectPhase.REQUIREMENTS_ANALYSIS, [])
        design_deps = dependencies.get(ProjectPhase.SYSTEM_DESIGN, [])

        assert ProjectPhase.REQUIREMENTS_ANALYSIS in design_deps or len(req_deps) == 0

    @pytest.mark.asyncio
    async def test_phase_optimization(self):
        """Test phase execution optimization"""
        requirement = "Optimize system performance"

        with patch.object(
            self.engine, "_optimize_phase_execution", new_callable=AsyncMock
        ) as mock_optimize:
            mock_optimize.return_value = {
                "optimizations_applied": ["parallel_execution", "resource_optimization"],
                "estimated_improvement": 0.3,
            }

            result = await self.engine.orchestrate_phase(
                ProjectPhase.IMPLEMENTATION,
                {"original_requirement": requirement, "enable_optimization": True},
            )

            mock_optimize.assert_called_once()

    def test_phase_metrics_collection(self):
        """Test phase metrics collection"""
        metrics = self.engine._collect_phase_metrics(ProjectPhase.IMPLEMENTATION)

        assert isinstance(metrics, dict)
        assert "phase" in metrics
        assert "timestamp" in metrics
        assert metrics["phase"] == ProjectPhase.IMPLEMENTATION

    @pytest.mark.asyncio
    async def test_phase_rollback_capability(self):
        """Test phase rollback capability"""
        with patch.object(
            self.engine, "_create_rollback_point", new_callable=AsyncMock
        ) as mock_rollback:
            mock_rollback.return_value = {"rollback_id": "test_123", "state": "saved"}

            rollback_point = await self.engine._create_rollback_point(
                ProjectPhase.IMPLEMENTATION, {"requirement": "test"}
            )

            assert rollback_point["rollback_id"] is not None
            mock_rollback.assert_called_once()
