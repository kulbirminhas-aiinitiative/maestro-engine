#!/usr/bin/env python3
"""
Unit Tests for DAGCatalogService

Tests DAG storage, retrieval, search, and template management.
"""

import pytest
import asyncio
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.dag_catalog import DAGCatalogService
from utils.redis_manager import RedisManager
from workflow.dag import DAG, TaskNode, TaskType


@pytest.fixture
async def dag_catalog():
    """Fixture providing initialized DAG catalog"""
    redis_mgr = RedisManager()
    catalog = DAGCatalogService(redis_manager=redis_mgr)
    await catalog.initialize_templates()
    yield catalog
    # Cleanup after tests
    # Note: In production, implement proper cleanup


@pytest.mark.asyncio
class TestDAGCatalogTemplates:
    """Test template initialization and retrieval"""

    async def test_initialize_templates(self, dag_catalog):
        """Test that all 4 templates are initialized"""
        # List all templates
        templates = await dag_catalog.list_dags()
        template_dags = [t for t in templates if t.get('is_template', False)]

        assert len(template_dags) == 4, "Should have 4 template DAGs"

        # Verify template IDs
        template_ids = {t['dag_id'] for t in template_dags}
        expected_ids = {
            'template_saas_app',
            'template_microservice_api',
            'template_mobile_app',
            'template_enterprise_system'
        }
        assert template_ids == expected_ids, "Should have all expected template IDs"

    async def test_saas_template_structure(self, dag_catalog):
        """Test SaaS template has correct structure"""
        dag = await dag_catalog.get_dag('template_saas_app')

        assert dag is not None, "SaaS template should exist"
        assert dag.name == "SaaS Application Development"
        assert len(dag.nodes) == 6, "SaaS template should have 6 phases"

        # Verify phases
        phase_names = {node.name for node in dag.nodes.values()}
        expected_phases = {
            'requirements', 'architecture', 'frontend',
            'backend', 'integration', 'deployment'
        }
        assert phase_names == expected_phases

        # Verify dependencies
        integration_node = dag.nodes['integration']
        assert set(integration_node.depends_on) == {'frontend', 'backend'}

    async def test_mobile_template_parallel_tasks(self, dag_catalog):
        """Test mobile template has parallel iOS/Android/Backend tasks"""
        dag = await dag_catalog.get_dag('template_mobile_app')

        assert dag is not None
        assert len(dag.nodes) == 7, "Mobile template should have 7 phases"

        # Verify iOS, Android, and Backend can run in parallel
        ios_node = dag.nodes['ios']
        android_node = dag.nodes['android']
        backend_node = dag.nodes['backend_api']

        # All three depend on design
        assert ios_node.depends_on == ['design']
        assert android_node.depends_on == ['design']
        assert backend_node.depends_on == ['design']

        # Testing depends on all three
        testing_node = dag.nodes['testing']
        assert set(testing_node.depends_on) == {'ios', 'android', 'backend_api'}

    async def test_topological_sort(self, dag_catalog):
        """Test topological sort produces valid execution order"""
        dag = await dag_catalog.get_dag('template_saas_app')

        sorted_nodes = dag.topological_sort()
        sorted_names = [node.name for node in sorted_nodes]

        # Verify requirements comes first
        assert sorted_names[0] == 'requirements'

        # Verify deployment comes last
        assert sorted_names[-1] == 'deployment'

        # Verify architecture comes before frontend/backend
        arch_idx = sorted_names.index('architecture')
        frontend_idx = sorted_names.index('frontend')
        backend_idx = sorted_names.index('backend')

        assert arch_idx < frontend_idx
        assert arch_idx < backend_idx

        # Verify integration comes after frontend/backend
        integration_idx = sorted_names.index('integration')
        assert integration_idx > frontend_idx
        assert integration_idx > backend_idx


@pytest.mark.asyncio
class TestDAGCatalogOperations:
    """Test CRUD operations"""

    async def test_store_and_retrieve_dag(self, dag_catalog):
        """Test storing and retrieving a custom DAG"""
        # Create custom DAG
        from workflow.dag import WorkflowBuilder

        custom_dag = (
            WorkflowBuilder(
                workflow_id="test_dag_001",
                name="Test Workflow",
                description="Test DAG for unit testing"
            )
            .add_task(
                "step1",
                "First Step",
                "Do something",
                task_type=TaskType.RESEARCH,
                priority=10
            )
            .add_task(
                "step2",
                "Second Step",
                "Do something else",
                task_type=TaskType.CODE,
                depends_on=["step1"],
                priority=9
            )
            .build()
        )

        # Store DAG
        dag_id = await dag_catalog.store_dag(
            dag=custom_dag,
            metadata={"category": "test", "author": "test_suite"},
            user_id="test_user"
        )

        assert dag_id == "test_dag_001"

        # Retrieve DAG
        retrieved_dag = await dag_catalog.get_dag(dag_id)
        assert retrieved_dag is not None
        assert retrieved_dag.name == "Test Workflow"
        assert len(retrieved_dag.nodes) == 2

        # Verify metadata
        metadata = await dag_catalog.get_dag_metadata(dag_id)
        assert metadata['category'] == 'test'
        assert metadata['author'] == 'test_user'

    async def test_search_dags(self, dag_catalog):
        """Test searching DAGs by keywords"""
        # Search for "SaaS"
        results = await dag_catalog.search_dags("saas", limit=10)

        assert len(results) > 0
        assert any('saas' in r['name'].lower() for r in results)

        # Search for "mobile"
        results = await dag_catalog.search_dags("mobile", limit=10)

        assert len(results) > 0
        assert any('mobile' in r['name'].lower() for r in results)

    async def test_list_by_category(self, dag_catalog):
        """Test listing DAGs by category"""
        # List SaaS category
        saas_dags = await dag_catalog.list_dags(category="saas")

        assert len(saas_dags) > 0
        assert all(d['category'] == 'saas' for d in saas_dags)

        # List microservice category
        micro_dags = await dag_catalog.list_dags(category="microservice")

        assert len(micro_dags) > 0
        assert all(d['category'] == 'microservice' for d in micro_dags)

    async def test_delete_dag(self, dag_catalog):
        """Test deleting a custom DAG"""
        # Create and store DAG
        from workflow.dag import WorkflowBuilder

        test_dag = (
            WorkflowBuilder(
                workflow_id="delete_test_001",
                name="To Be Deleted"
            )
            .add_task("task1", "Task 1", "Description", task_type=TaskType.RESEARCH)
            .build()
        )

        dag_id = await dag_catalog.store_dag(test_dag, user_id="test_user")

        # Verify it exists
        dag = await dag_catalog.get_dag(dag_id)
        assert dag is not None

        # Delete it
        deleted = await dag_catalog.delete_dag(dag_id)
        assert deleted is True

        # Verify it's gone
        dag = await dag_catalog.get_dag(dag_id)
        assert dag is None


@pytest.mark.asyncio
class TestDAGMetadata:
    """Test DAG metadata management"""

    async def test_template_metadata(self, dag_catalog):
        """Test template metadata completeness"""
        templates = ['template_saas_app', 'template_microservice_api',
                     'template_mobile_app', 'template_enterprise_system']

        for template_id in templates:
            metadata = await dag_catalog.get_dag_metadata(template_id)

            assert metadata is not None
            assert 'category' in metadata
            assert 'complexity' in metadata
            assert 'duration' in metadata
            assert 'tech_stack' in metadata
            assert 'team_roles' in metadata
            assert 'is_template' in metadata
            assert metadata['is_template'] is True

    async def test_dag_metadata_includes_node_count(self, dag_catalog):
        """Test metadata includes node count"""
        metadata = await dag_catalog.get_dag_metadata('template_saas_app')

        assert 'node_count' in metadata
        assert metadata['node_count'] == 6  # SaaS has 6 phases


if __name__ == "__main__":
    # Run tests with pytest
    print("Running DAG Catalog Service Unit Tests...")
    print("=" * 80)
    pytest.main([__file__, "-v", "--tb=short"])
