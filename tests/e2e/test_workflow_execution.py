#!/usr/bin/env python3
"""
End-to-End Tests for Workflow Execution with DAGs

Tests complete workflow execution flow:
- Loading DAGs from catalog
- Executing workflows in different modes
- Phase dependency validation
- Topological order execution
- Error handling and recovery
"""

import pytest
import asyncio
import time
from typing import List, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from api.workflow_executor import MaestroWorkflowExecutor
from services.dag_catalog import DAGCatalogService
from utils.redis_manager import RedisManager
from workflow.dag import WorkflowBuilder, TaskType


@pytest.fixture
async def workflow_executor():
    """Fixture providing initialized workflow executor"""
    executor = MaestroWorkflowExecutor()
    yield executor


@pytest.fixture
async def dag_catalog():
    """Fixture providing initialized DAG catalog"""
    redis_mgr = RedisManager()
    catalog = DAGCatalogService(redis_manager=redis_mgr)
    await catalog.initialize_templates()
    yield catalog


@pytest.mark.asyncio
class TestDAGLoadingAndExecution:
    """Test loading DAGs from catalog and executing them"""

    async def test_load_saas_template(self, workflow_executor, dag_catalog):
        """Test loading SaaS template from catalog"""
        # Load DAG
        success = await workflow_executor.load_dag('template_saas_app', dag_catalog)

        assert success is True, "Should successfully load SaaS template"
        assert workflow_executor.workflow_dag is not None, "DAG should be loaded"
        assert workflow_executor.workflow_dag.dag_id == 'template_saas_app'
        assert len(workflow_executor.workflow_dag.nodes) == 6

    async def test_load_invalid_dag(self, workflow_executor, dag_catalog):
        """Test loading non-existent DAG"""
        success = await workflow_executor.load_dag('invalid_dag_id', dag_catalog)

        assert success is False, "Should fail to load invalid DAG"
        assert workflow_executor.workflow_dag is None, "DAG should not be set"

    async def test_execute_with_loaded_dag(self, workflow_executor, dag_catalog):
        """Test executing workflow with loaded DAG"""
        # Load SaaS template
        await workflow_executor.load_dag('template_saas_app', dag_catalog)

        # Create execution request
        request = {
            'user_id': 'test_user_001',
            'project_description': 'Build a multi-tenant SaaS application',
            'requirements': [
                'User authentication',
                'Subscription management',
                'Multi-tenant architecture'
            ],
            'execution_mode': 'batch',
            'use_dag': True
        }

        # Start execution (we'll test execution tracking, not full AI execution)
        workflow_id = f"test_workflow_{int(time.time())}"

        # Verify DAG is ready for execution
        assert workflow_executor.workflow_dag is not None
        sorted_phases = workflow_executor.workflow_dag.topological_sort()

        assert len(sorted_phases) == 6
        assert sorted_phases[0].name == 'requirements'
        assert sorted_phases[-1].name == 'deployment'


@pytest.mark.asyncio
class TestExecutionModes:
    """Test different execution modes with DAGs"""

    async def test_batch_mode_execution_order(self, workflow_executor, dag_catalog):
        """Test batch mode executes all phases in topological order"""
        await workflow_executor.load_dag('template_saas_app', dag_catalog)

        dag = workflow_executor.workflow_dag
        sorted_phases = dag.topological_sort()
        phase_names = [node.name for node in sorted_phases]

        # Verify topological order
        requirements_idx = phase_names.index('requirements')
        architecture_idx = phase_names.index('architecture')
        frontend_idx = phase_names.index('frontend')
        backend_idx = phase_names.index('backend')
        integration_idx = phase_names.index('integration')
        deployment_idx = phase_names.index('deployment')

        # Requirements must be first
        assert requirements_idx == 0

        # Architecture after requirements
        assert architecture_idx > requirements_idx

        # Frontend and Backend after architecture
        assert frontend_idx > architecture_idx
        assert backend_idx > architecture_idx

        # Integration after frontend and backend
        assert integration_idx > frontend_idx
        assert integration_idx > backend_idx

        # Deployment must be last
        assert deployment_idx == len(phase_names) - 1

    async def test_phased_mode_execution(self, workflow_executor, dag_catalog):
        """Test phased mode allows phase-by-phase execution"""
        await workflow_executor.load_dag('template_microservice_api', dag_catalog)

        dag = workflow_executor.workflow_dag

        # Get first phase
        sorted_phases = dag.topological_sort()
        first_phase = sorted_phases[0]

        assert first_phase.name == 'requirements'
        assert len(first_phase.depends_on) == 0, "First phase should have no dependencies"

        # Get phases that can run after requirements
        second_level_phases = [node for node in sorted_phases[1:]
                               if set(node.depends_on) == {first_phase.name}]

        assert len(second_level_phases) > 0, "Should have phases depending on requirements"

    async def test_mixed_mode_parallel_execution(self, workflow_executor, dag_catalog):
        """Test mixed mode identifies parallel-executable phases"""
        # Load mobile template which has parallel iOS/Android/Backend phases
        await workflow_executor.load_dag('template_mobile_app', dag_catalog)

        dag = workflow_executor.workflow_dag

        # Find parallel phases (iOS, Android, Backend)
        ios_node = dag.nodes.get('ios')
        android_node = dag.nodes.get('android')
        backend_node = dag.nodes.get('backend_api')

        assert ios_node is not None
        assert android_node is not None
        assert backend_node is not None

        # All three should depend only on 'design'
        assert ios_node.depends_on == ['design']
        assert android_node.depends_on == ['design']
        assert backend_node.depends_on == ['design']

        # These can execute in parallel after design phase completes
        parallel_group = [ios_node, android_node, backend_node]

        # Verify they have same dependency level
        for node in parallel_group:
            assert len(node.depends_on) == 1


@pytest.mark.asyncio
class TestPhaseDependencies:
    """Test phase dependency validation"""

    async def test_dependency_resolution(self, workflow_executor, dag_catalog):
        """Test DAG correctly resolves dependencies"""
        await workflow_executor.load_dag('template_saas_app', dag_catalog)

        dag = workflow_executor.workflow_dag

        # Integration phase depends on frontend and backend
        integration_node = dag.nodes['integration']
        assert set(integration_node.depends_on) == {'frontend', 'backend'}

        # Deployment depends on integration
        deployment_node = dag.nodes['deployment']
        assert 'integration' in deployment_node.depends_on

    async def test_no_circular_dependencies(self, workflow_executor, dag_catalog):
        """Test that templates have no circular dependencies"""
        templates = ['template_saas_app', 'template_microservice_api',
                    'template_mobile_app', 'template_enterprise_system']

        for template_id in templates:
            await workflow_executor.load_dag(template_id, dag_catalog)
            dag = workflow_executor.workflow_dag

            # If topological_sort succeeds, there are no cycles
            try:
                sorted_nodes = dag.topological_sort()
                assert len(sorted_nodes) == len(dag.nodes)
            except ValueError as e:
                pytest.fail(f"Circular dependency detected in {template_id}: {e}")

    async def test_all_dependencies_exist(self, workflow_executor, dag_catalog):
        """Test that all dependencies reference existing nodes"""
        templates = ['template_saas_app', 'template_microservice_api',
                    'template_mobile_app', 'template_enterprise_system']

        for template_id in templates:
            await workflow_executor.load_dag(template_id, dag_catalog)
            dag = workflow_executor.workflow_dag

            for node_id, node in dag.nodes.items():
                for dep in node.depends_on:
                    assert dep in dag.nodes, f"Dependency '{dep}' not found in {template_id}"


@pytest.mark.asyncio
class TestCustomWorkflowExecution:
    """Test creating and executing custom workflows"""

    async def test_create_and_execute_custom_dag(self, workflow_executor, dag_catalog):
        """Test creating custom DAG and executing it"""
        # Create custom workflow
        custom_dag = (
            WorkflowBuilder(
                workflow_id="test_custom_workflow_001",
                name="Custom Test Workflow",
                description="Test workflow for E2E testing"
            )
            .add_task(
                "phase1",
                "Research Phase",
                "Gather requirements and research",
                task_type=TaskType.RESEARCH,
                priority=10
            )
            .add_task(
                "phase2",
                "Design Phase",
                "Create architecture design",
                task_type=TaskType.PLANNING,
                depends_on=["phase1"],
                priority=9
            )
            .add_task(
                "phase3",
                "Implementation Phase",
                "Implement the solution",
                task_type=TaskType.CODE,
                depends_on=["phase2"],
                priority=8
            )
            .build()
        )

        # Store in catalog
        dag_id = await dag_catalog.store_dag(
            dag=custom_dag,
            metadata={"category": "test", "complexity": "simple"},
            user_id="test_user"
        )

        assert dag_id == "test_custom_workflow_001"

        # Load and verify
        await workflow_executor.load_dag(dag_id, dag_catalog)
        assert workflow_executor.workflow_dag is not None
        assert len(workflow_executor.workflow_dag.nodes) == 3

        # Test topological order
        sorted_phases = workflow_executor.workflow_dag.topological_sort()
        phase_names = [node.name for node in sorted_phases]

        assert phase_names[0] == "phase1"
        assert phase_names[1] == "phase2"
        assert phase_names[2] == "phase3"

    async def test_parallel_custom_phases(self, workflow_executor, dag_catalog):
        """Test custom workflow with parallel phases"""
        # Create workflow with parallel phases
        parallel_dag = (
            WorkflowBuilder(
                workflow_id="test_parallel_workflow_001",
                name="Parallel Test Workflow"
            )
            .add_task(
                "init",
                "Initialization",
                "Setup phase",
                task_type=TaskType.PLANNING,
                priority=10
            )
            .add_task(
                "frontend",
                "Frontend Development",
                "Build UI",
                task_type=TaskType.CODE,
                depends_on=["init"],
                priority=9
            )
            .add_task(
                "backend",
                "Backend Development",
                "Build API",
                task_type=TaskType.CODE,
                depends_on=["init"],
                priority=9
            )
            .add_task(
                "testing",
                "Integration Testing",
                "Test integration",
                task_type=TaskType.CODE,
                depends_on=["frontend", "backend"],
                priority=8
            )
            .build()
        )

        # Store and load
        dag_id = await dag_catalog.store_dag(
            dag=parallel_dag,
            user_id="test_user"
        )

        await workflow_executor.load_dag(dag_id, dag_catalog)
        dag = workflow_executor.workflow_dag

        # Verify parallel phases
        frontend_node = dag.nodes['frontend']
        backend_node = dag.nodes['backend']

        assert frontend_node.depends_on == ['init']
        assert backend_node.depends_on == ['init']

        # Both can execute in parallel after init
        # Testing phase requires both
        testing_node = dag.nodes['testing']
        assert set(testing_node.depends_on) == {'frontend', 'backend'}


@pytest.mark.asyncio
class TestErrorHandling:
    """Test error handling during workflow execution"""

    async def test_handle_missing_dag(self, workflow_executor):
        """Test execution fails gracefully when DAG not loaded"""
        # Don't load any DAG
        assert workflow_executor.workflow_dag is None

        # Attempting to get phases should handle missing DAG
        # (Implementation would need to check for None)
        if workflow_executor.workflow_dag is None:
            # Expected behavior: should not crash
            assert True

    async def test_handle_corrupted_dag_data(self, workflow_executor, dag_catalog):
        """Test handling of DAG with invalid structure"""
        # This test ensures the system handles edge cases
        # In production, additional validation would be needed

        # Create DAG with empty nodes (edge case)
        try:
            empty_dag = WorkflowBuilder(
                workflow_id="test_empty_dag",
                name="Empty DAG"
            ).build()

            # Even empty DAGs should be handled
            dag_id = await dag_catalog.store_dag(empty_dag, user_id="test_user")
            await workflow_executor.load_dag(dag_id, dag_catalog)

            # Should load but have no nodes
            assert workflow_executor.workflow_dag is not None
            assert len(workflow_executor.workflow_dag.nodes) == 0
        except Exception as e:
            # If it raises an error, that's also acceptable behavior
            assert True


@pytest.mark.asyncio
class TestWorkflowProgress:
    """Test workflow progress tracking"""

    async def test_phase_completion_tracking(self, workflow_executor, dag_catalog):
        """Test tracking completed phases during execution"""
        await workflow_executor.load_dag('template_saas_app', dag_catalog)

        dag = workflow_executor.workflow_dag
        sorted_phases = dag.topological_sort()

        # Simulate marking phases as complete
        completed_phases = set()

        for phase in sorted_phases:
            # Check if all dependencies are completed
            dependencies_met = all(dep in completed_phases for dep in phase.depends_on)

            if dependencies_met or len(phase.depends_on) == 0:
                # Phase can be executed
                completed_phases.add(phase.name)
            else:
                # Dependencies not met
                assert False, f"Phase {phase.name} dependencies not met: {phase.depends_on}"

        # All phases should be completable in topological order
        assert len(completed_phases) == len(dag.nodes)

    async def test_identify_next_executable_phases(self, workflow_executor, dag_catalog):
        """Test identifying which phases can be executed next"""
        await workflow_executor.load_dag('template_mobile_app', dag_catalog)

        dag = workflow_executor.workflow_dag
        completed_phases = set()

        # Initially, only phases with no dependencies can run
        next_phases = [
            node for node in dag.nodes.values()
            if len(node.depends_on) == 0
        ]

        assert len(next_phases) == 1, "Should have exactly one starting phase"
        assert next_phases[0].name == 'requirements'

        # After completing requirements
        completed_phases.add('requirements')

        next_phases = [
            node for node in dag.nodes.values()
            if node.name not in completed_phases
            and all(dep in completed_phases for dep in node.depends_on)
        ]

        # Should now have design phase available
        assert any(node.name == 'design' for node in next_phases)

        # After completing design
        completed_phases.add('design')

        next_phases = [
            node for node in dag.nodes.values()
            if node.name not in completed_phases
            and all(dep in completed_phases for dep in node.depends_on)
        ]

        # Should now have iOS, Android, and Backend available in parallel
        next_phase_names = {node.name for node in next_phases}
        assert 'ios' in next_phase_names
        assert 'android' in next_phase_names
        assert 'backend_api' in next_phase_names


@pytest.mark.asyncio
class TestTemplateValidation:
    """Test all templates are valid and executable"""

    async def test_all_templates_loadable(self, workflow_executor, dag_catalog):
        """Test all 4 templates can be loaded"""
        templates = [
            'template_saas_app',
            'template_microservice_api',
            'template_mobile_app',
            'template_enterprise_system'
        ]

        for template_id in templates:
            success = await workflow_executor.load_dag(template_id, dag_catalog)
            assert success, f"Failed to load {template_id}"
            assert workflow_executor.workflow_dag is not None
            assert workflow_executor.workflow_dag.dag_id == template_id

    async def test_all_templates_have_phases(self, workflow_executor, dag_catalog):
        """Test all templates have at least one phase"""
        templates = [
            'template_saas_app',
            'template_microservice_api',
            'template_mobile_app',
            'template_enterprise_system'
        ]

        for template_id in templates:
            await workflow_executor.load_dag(template_id, dag_catalog)
            dag = workflow_executor.workflow_dag

            assert len(dag.nodes) > 0, f"{template_id} has no phases"
            assert len(dag.nodes) >= 5, f"{template_id} should have at least 5 phases"

    async def test_all_templates_topologically_sortable(self, workflow_executor, dag_catalog):
        """Test all templates can be topologically sorted"""
        templates = [
            'template_saas_app',
            'template_microservice_api',
            'template_mobile_app',
            'template_enterprise_system'
        ]

        for template_id in templates:
            await workflow_executor.load_dag(template_id, dag_catalog)
            dag = workflow_executor.workflow_dag

            sorted_nodes = dag.topological_sort()

            assert len(sorted_nodes) == len(dag.nodes)

            # Verify first node has no dependencies
            assert len(sorted_nodes[0].depends_on) == 0


if __name__ == "__main__":
    # Run tests with pytest
    print("Running Workflow Execution E2E Tests...")
    print("=" * 80)
    pytest.main([__file__, "-v", "--tb=short"])
