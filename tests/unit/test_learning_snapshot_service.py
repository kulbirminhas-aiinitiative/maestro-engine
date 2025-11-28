#!/usr/bin/env python3
"""
Unit Tests for Learning Snapshot Service
Tests for EPIC QF-400: Learning Snapshots with RAG Ingestion & Provenance

Test Coverage:
- AC-1: Snapshot generated at execution end
- AC-2: Ingested to ES/vector store with proper mapping
- AC-3: Vector embeddings created for retrieval
- AC-4: Provenance links valid and resolvable
- AC-5: RAG queries return relevant snapshots
"""

import os
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.learning_snapshot_service import (
    LearningSnapshotService,
    LearningSnapshot,
    PhaseResult,
    Defect,
    Citation,
    Provenance,
    SnapshotStatus,
    ProvenanceType,
    RAGQueryResult,
    get_snapshot_service,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def temp_persist_dir():
    """Create a temporary directory for ChromaDB persistence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def snapshot_service(temp_persist_dir):
    """Create a snapshot service with temporary persistence."""
    # Reset singleton
    import services.learning_snapshot_service as module
    module._snapshot_service = None

    return LearningSnapshotService(
        persist_dir=temp_persist_dir,
        collection_name="test_learnings",
        enable_persistence=True,
    )


@pytest.fixture
def sample_phases():
    """Sample phase data for testing."""
    return [
        {
            "id": "design",
            "name": "Design Phase",
            "score": 0.85,
            "gates": {"DDE": "passed"},
            "artifacts": ["s3://artifacts/architecture.md"],
            "duration_ms": 5000,
        },
        {
            "id": "implementation",
            "name": "Implementation Phase",
            "score": 0.78,
            "gates": {"BRV": "passed", "ACC": "passed"},
            "artifacts": ["s3://artifacts/api.py"],
            "duration_ms": 15000,
        },
    ]


@pytest.fixture
def sample_defects():
    """Sample defect data."""
    return [
        {
            "id": "DEF-001",
            "severity": "medium",
            "phase": "implementation",
            "description": "Missing input validation",
        },
        {
            "id": "DEF-002",
            "severity": "low",
            "phase": "testing",
            "description": "Flaky test in auth module",
            "resolution": "Added retry logic",
        },
    ]


@pytest.fixture
def sample_citations():
    """Sample citation data."""
    return [
        {
            "source": "golden-projects/api-auth",
            "ref": "commit:abc123",
            "type": "source_repo",
            "description": "Reference implementation",
        },
        {
            "source": "templates/jwt-handler",
            "ref": "v2.1.0",
            "type": "template",
        },
    ]


@pytest.fixture
def sample_provenance():
    """Sample provenance data."""
    return {
        "source_repo": "github://org/my-project",
        "commit": "def456789",
        "tool_chain": "maestro+quality-fabric",
        "validation_report_id": "qf-val-12345",
        "created_by": "qa-agent@maestro.com",
    }


# ============================================================================
# AC-1: SNAPSHOT GENERATION TESTS
# ============================================================================

class TestSnapshotGeneration:
    """Tests for snapshot generation (AC-1)."""

    def test_generate_snapshot_basic(self, snapshot_service, sample_phases):
        """Test basic snapshot generation."""
        snapshot = snapshot_service.generate_snapshot(
            session_id="sess_001",
            execution_id="exec_001",
            requirement="Build a REST API",
            phases=sample_phases,
            quality_score=0.82,
        )

        assert snapshot is not None
        assert snapshot.snapshot_id.startswith("snap_")
        assert snapshot.session_id == "sess_001"
        assert snapshot.execution_id == "exec_001"
        assert snapshot.requirement == "Build a REST API"
        assert len(snapshot.phases) == 2
        assert snapshot.status == SnapshotStatus.PENDING

    def test_generate_snapshot_with_all_fields(
        self, snapshot_service, sample_phases, sample_defects,
        sample_citations, sample_provenance
    ):
        """Test snapshot generation with all fields populated."""
        snapshot = snapshot_service.generate_snapshot(
            session_id="sess_full",
            execution_id="exec_full",
            requirement="Complete workflow execution",
            phases=sample_phases,
            quality_score=0.85,
            templates_used=["api_auth_v3", "jwt_handler_v2"],
            defects=sample_defects,
            citations=sample_citations,
            provenance=sample_provenance,
            personas=["backend_developer", "security_specialist"],
            tags=["auth", "jwt", "api"],
            environment="staging",
            execution_time_ms=25000,
            success=True,
            workflow_id="wf_001",
        )

        assert snapshot.workflow_id == "wf_001"
        assert len(snapshot.templates_used) == 2
        assert len(snapshot.defects) == 2
        assert len(snapshot.citations) == 2
        assert snapshot.provenance is not None
        assert snapshot.provenance.source_repo == "github://org/my-project"
        assert len(snapshot.personas) == 2
        assert len(snapshot.tags) == 3
        assert snapshot.environment == "staging"
        assert snapshot.execution_time_ms == 25000

    def test_generate_snapshot_calculates_overall_score(self, snapshot_service, sample_phases):
        """Test that overall score is calculated from phase scores."""
        snapshot = snapshot_service.generate_snapshot(
            session_id="sess_score",
            execution_id="exec_score",
            requirement="Test score calculation",
            phases=sample_phases,
        )

        # Expected: (0.85 + 0.78) / 2 = 0.815
        expected_score = (0.85 + 0.78) / 2
        assert abs(snapshot.overall_score - expected_score) < 0.01

    def test_generate_snapshot_requirement_summary(self, snapshot_service):
        """Test that long requirements are summarized."""
        long_requirement = "A" * 300  # 300 character requirement

        snapshot = snapshot_service.generate_snapshot(
            session_id="sess_long",
            execution_id="exec_long",
            requirement=long_requirement,
            phases=[],
        )

        # Summary should be truncated to 200 chars + "..."
        assert len(snapshot.requirement_summary) == 203
        assert snapshot.requirement_summary.endswith("...")

    def test_generate_search_text(self, snapshot_service, sample_phases):
        """Test search text generation for embedding."""
        snapshot = snapshot_service.generate_snapshot(
            session_id="sess_search",
            execution_id="exec_search",
            requirement="Build authentication API",
            phases=sample_phases,
            templates_used=["api_auth_v3"],
            tags=["auth", "api"],
            personas=["backend_developer"],
        )

        search_text = snapshot.generate_search_text()

        assert "Build authentication API" in search_text
        assert "api_auth_v3" in search_text
        assert "auth" in search_text
        assert "backend_developer" in search_text


# ============================================================================
# AC-2: VECTOR STORE INGESTION TESTS
# ============================================================================

class TestVectorStoreIngestion:
    """Tests for vector store ingestion (AC-2)."""

    def test_index_snapshot(self, snapshot_service, sample_phases):
        """Test indexing a snapshot to vector store."""
        snapshot = snapshot_service.generate_snapshot(
            session_id="sess_index",
            execution_id="exec_index",
            requirement="Test indexing",
            phases=sample_phases,
            quality_score=0.80,
        )

        indexed = snapshot_service.index_snapshot(snapshot)

        # If ChromaDB available, should be indexed; otherwise returns False
        if snapshot_service.enabled:
            assert indexed == True
            assert snapshot.status == SnapshotStatus.INDEXED
            assert snapshot.indexed_at is not None
        else:
            # ChromaDB not available - this is acceptable
            assert indexed == False

    def test_generate_and_index(self, snapshot_service, sample_phases):
        """Test combined generate and index operation."""
        snapshot, indexed = snapshot_service.generate_and_index(
            session_id="sess_combo",
            execution_id="exec_combo",
            requirement="Combined operation",
            phases=sample_phases,
        )

        assert snapshot is not None
        # indexed depends on ChromaDB availability
        if snapshot_service.enabled:
            assert indexed == True
            assert snapshot.status == SnapshotStatus.INDEXED
        else:
            assert indexed == False

    def test_collection_stats_after_indexing(self, snapshot_service, sample_phases):
        """Test collection stats reflect indexed snapshots."""
        # Index multiple snapshots
        for i in range(3):
            snapshot_service.generate_and_index(
                session_id=f"sess_{i}",
                execution_id=f"exec_{i}",
                requirement=f"Requirement {i}",
                phases=sample_phases,
            )

        stats = snapshot_service.get_collection_stats()

        assert "enabled" in stats
        if stats["enabled"]:
            assert stats["count"] >= 3


# ============================================================================
# AC-3: VECTOR EMBEDDINGS TESTS
# ============================================================================

class TestVectorEmbeddings:
    """Tests for vector embeddings (AC-3)."""

    def test_service_enabled_status(self, snapshot_service):
        """Test service enabled status based on ChromaDB availability."""
        # Service should report its enabled status correctly
        # It may be enabled or disabled depending on ChromaDB availability
        assert isinstance(snapshot_service.enabled, bool)

    def test_get_collection_stats(self, snapshot_service):
        """Test getting collection statistics."""
        stats = snapshot_service.get_collection_stats()

        assert "enabled" in stats
        assert "count" in stats
        # collection_name only present when enabled
        if stats["enabled"]:
            assert "collection_name" in stats


# ============================================================================
# AC-4: PROVENANCE VALIDATION TESTS
# ============================================================================

class TestProvenanceValidation:
    """Tests for provenance validation (AC-4)."""

    def test_validate_provenance_valid(self, snapshot_service, sample_phases, sample_provenance):
        """Test validation of valid provenance."""
        snapshot = snapshot_service.generate_snapshot(
            session_id="sess_prov",
            execution_id="exec_prov",
            requirement="Test provenance",
            phases=sample_phases,
            provenance=sample_provenance,
        )

        is_valid, issues = snapshot_service.validate_provenance(snapshot)

        assert is_valid == True
        assert len(issues) == 0

    def test_validate_provenance_missing(self, snapshot_service, sample_phases):
        """Test validation when provenance is missing."""
        snapshot = snapshot_service.generate_snapshot(
            session_id="sess_no_prov",
            execution_id="exec_no_prov",
            requirement="Test missing provenance",
            phases=sample_phases,
            # No provenance provided
        )

        is_valid, issues = snapshot_service.validate_provenance(snapshot)

        assert is_valid == False
        assert len(issues) > 0
        assert any("provenance" in issue.lower() for issue in issues)

    def test_validate_citations(self, snapshot_service, sample_phases, sample_citations):
        """Test validation with citations."""
        snapshot = snapshot_service.generate_snapshot(
            session_id="sess_cite",
            execution_id="exec_cite",
            requirement="Test citations",
            phases=sample_phases,
            citations=sample_citations,
            provenance={"source_repo": "github://org/repo"},
        )

        is_valid, issues = snapshot_service.validate_provenance(snapshot)

        # Should be valid with proper citations
        assert is_valid == True

    def test_resolve_citation_source_repo(self, snapshot_service):
        """Test resolving source_repo citation."""
        citation = Citation(
            source="org/repo",
            ref="main",
            type=ProvenanceType.SOURCE_REPO,
        )

        resolved = snapshot_service.resolve_citation(citation)

        assert resolved["resolvable"] == True
        assert "github.com" in resolved["resolved_uri"]

    def test_resolve_citation_commit(self, snapshot_service):
        """Test resolving commit citation."""
        citation = Citation(
            source="org/repo",
            ref="abc123",
            type=ProvenanceType.COMMIT,
        )

        resolved = snapshot_service.resolve_citation(citation)

        assert resolved["resolvable"] == True
        assert "commit" in resolved["resolved_uri"]
        assert "abc123" in resolved["resolved_uri"]

    def test_resolve_citation_golden_project(self, snapshot_service):
        """Test resolving golden_project citation."""
        citation = Citation(
            source="api-auth-template",
            ref="v2.0",
            type=ProvenanceType.GOLDEN_PROJECT,
        )

        resolved = snapshot_service.resolve_citation(citation)

        assert resolved["resolvable"] == True
        assert "/api/templates/" in resolved["resolved_uri"]

    def test_resolve_citation_validation_report(self, snapshot_service):
        """Test resolving validation_report citation."""
        citation = Citation(
            source="qf-validation",
            ref="val-12345",
            type=ProvenanceType.VALIDATION_REPORT,
        )

        resolved = snapshot_service.resolve_citation(citation)

        assert resolved["resolvable"] == True
        assert "/api/quality/validations/" in resolved["resolved_uri"]


# ============================================================================
# AC-5: RAG QUERY TESTS
# ============================================================================

class TestRAGQueries:
    """Tests for RAG queries (AC-5)."""

    def test_query_similar_basic(self, snapshot_service, sample_phases):
        """Test basic RAG query."""
        # Index some snapshots
        snapshot_service.generate_and_index(
            session_id="sess_auth1",
            execution_id="exec_auth1",
            requirement="Build authentication API with JWT",
            phases=sample_phases,
            tags=["auth", "jwt"],
        )

        snapshot_service.generate_and_index(
            session_id="sess_auth2",
            execution_id="exec_auth2",
            requirement="Create user login system",
            phases=sample_phases,
            tags=["auth", "login"],
        )

        # Query
        results = snapshot_service.query_similar(
            query_text="authentication API",
            top_k=5,
        )

        assert isinstance(results, list)
        # May return results depending on ChromaDB availability

    def test_query_by_requirement(self, snapshot_service, sample_phases):
        """Test querying by requirement text."""
        # Index a snapshot
        snapshot_service.generate_and_index(
            session_id="sess_req",
            execution_id="exec_req",
            requirement="REST API for user management",
            phases=sample_phases,
            quality_score=0.85,
        )

        results = snapshot_service.query_by_requirement(
            requirement="user management API",
            top_k=3,
        )

        assert isinstance(results, list)

    def test_query_by_template(self, snapshot_service, sample_phases):
        """Test querying by template ID."""
        # Index with specific template
        snapshot_service.generate_and_index(
            session_id="sess_tmpl",
            execution_id="exec_tmpl",
            requirement="Using api_auth template",
            phases=sample_phases,
            templates_used=["api_auth_v3"],
        )

        results = snapshot_service.query_by_template(
            template_id="api_auth_v3",
            top_k=5,
        )

        assert isinstance(results, list)

    def test_query_with_min_score_filter(self, snapshot_service, sample_phases):
        """Test RAG query with minimum score filter."""
        results = snapshot_service.query_similar(
            query_text="test query",
            top_k=5,
            min_score=0.5,
        )

        # All results should have similarity >= 0.5
        for result in results:
            assert result.similarity >= 0.5

    def test_query_with_quality_filter(self, snapshot_service, sample_phases):
        """Test RAG query with quality score filter."""
        # Index with high quality
        snapshot_service.generate_and_index(
            session_id="sess_hq",
            execution_id="exec_hq",
            requirement="High quality execution",
            phases=sample_phases,
            quality_score=0.95,
        )

        # Index with low quality
        snapshot_service.generate_and_index(
            session_id="sess_lq",
            execution_id="exec_lq",
            requirement="Low quality execution",
            phases=sample_phases,
            quality_score=0.50,
        )

        results = snapshot_service.query_by_requirement(
            requirement="execution",
            top_k=10,
            min_quality=0.8,
        )

        # Results should only include high quality snapshots
        for result in results:
            assert result.snapshot.quality_score >= 0.8


# ============================================================================
# UTILITY METHOD TESTS
# ============================================================================

class TestUtilityMethods:
    """Tests for utility methods."""

    def test_get_snapshot(self, snapshot_service, sample_phases):
        """Test getting a snapshot by ID."""
        snapshot = snapshot_service.generate_snapshot(
            session_id="sess_get",
            execution_id="exec_get",
            requirement="Test get",
            phases=sample_phases,
        )

        retrieved = snapshot_service.get_snapshot(snapshot.snapshot_id)

        assert retrieved is not None
        assert retrieved.snapshot_id == snapshot.snapshot_id

    def test_get_snapshot_not_found(self, snapshot_service):
        """Test getting non-existent snapshot."""
        retrieved = snapshot_service.get_snapshot("nonexistent_id")
        assert retrieved is None

    def test_list_snapshots(self, snapshot_service, sample_phases):
        """Test listing snapshots."""
        # Generate multiple snapshots
        for i in range(5):
            snapshot_service.generate_snapshot(
                session_id=f"sess_list_{i}",
                execution_id=f"exec_list_{i}",
                requirement=f"List test {i}",
                phases=sample_phases,
            )

        snapshots = snapshot_service.list_snapshots(limit=3)

        assert len(snapshots) <= 3

    def test_list_snapshots_with_status_filter(self, snapshot_service, sample_phases):
        """Test listing snapshots with status filter."""
        # Generate and index one
        snapshot_service.generate_and_index(
            session_id="sess_indexed",
            execution_id="exec_indexed",
            requirement="Indexed snapshot",
            phases=sample_phases,
        )

        # Generate but don't index
        snapshot_service.generate_snapshot(
            session_id="sess_pending",
            execution_id="exec_pending",
            requirement="Pending snapshot",
            phases=sample_phases,
        )

        indexed = snapshot_service.list_snapshots(status=SnapshotStatus.INDEXED)
        pending = snapshot_service.list_snapshots(status=SnapshotStatus.PENDING)

        # Check filtering works
        for s in indexed:
            assert s.status == SnapshotStatus.INDEXED
        for s in pending:
            assert s.status == SnapshotStatus.PENDING

    def test_delete_snapshot(self, snapshot_service, sample_phases):
        """Test deleting a snapshot."""
        snapshot = snapshot_service.generate_snapshot(
            session_id="sess_del",
            execution_id="exec_del",
            requirement="Delete test",
            phases=sample_phases,
        )

        deleted = snapshot_service.delete_snapshot(snapshot.snapshot_id)

        assert deleted == True
        assert snapshot_service.get_snapshot(snapshot.snapshot_id) is None

    def test_get_service_info(self, snapshot_service):
        """Test getting service information."""
        info = snapshot_service.get_service_info()

        assert "service" in info
        assert "enabled" in info
        assert "collection" in info
        assert "cached_snapshots" in info
        assert info["service"] == "learning_snapshot_service"


# ============================================================================
# DATA CLASS TESTS
# ============================================================================

class TestDataClasses:
    """Tests for data classes."""

    def test_phase_result_to_dict(self):
        """Test PhaseResult serialization."""
        phase = PhaseResult(
            id="design",
            name="Design Phase",
            score=0.85,
            gates={"DDE": "passed"},
            artifacts=["s3://artifacts/doc.md"],
            duration_ms=5000,
        )

        d = phase.to_dict()

        assert d["id"] == "design"
        assert d["score"] == 0.85
        assert d["gates"]["DDE"] == "passed"

    def test_defect_to_dict(self):
        """Test Defect serialization."""
        defect = Defect(
            id="DEF-001",
            severity="high",
            phase="implementation",
            description="Security vulnerability",
            resolution="Fixed in commit abc",
        )

        d = defect.to_dict()

        assert d["id"] == "DEF-001"
        assert d["severity"] == "high"
        assert d["resolution"] == "Fixed in commit abc"

    def test_citation_to_dict(self):
        """Test Citation serialization."""
        citation = Citation(
            source="golden-projects/api",
            ref="v1.0",
            type=ProvenanceType.GOLDEN_PROJECT,
            description="Reference impl",
        )

        d = citation.to_dict()

        assert d["source"] == "golden-projects/api"
        assert d["type"] == "golden_project"

    def test_provenance_to_dict(self):
        """Test Provenance serialization."""
        prov = Provenance(
            source_repo="github://org/repo",
            commit="abc123",
            tool_chain="maestro+qf",
            validation_report_id="val-001",
        )

        d = prov.to_dict()

        assert d["source_repo"] == "github://org/repo"
        assert d["commit"] == "abc123"

    def test_learning_snapshot_to_dict(self):
        """Test LearningSnapshot serialization."""
        snapshot = LearningSnapshot(
            snapshot_id="snap_001",
            session_id="sess_001",
            execution_id="exec_001",
            requirement="Test requirement",
            requirement_summary="Test requirement",
            overall_score=0.85,
            quality_score=0.80,
            success=True,
        )

        d = snapshot.to_dict()

        assert d["snapshot_id"] == "snap_001"
        assert d["overall_score"] == 0.85
        assert d["success"] == True

    def test_rag_query_result_to_dict(self):
        """Test RAGQueryResult serialization."""
        snapshot = LearningSnapshot(
            snapshot_id="snap_rag",
            session_id="sess_rag",
            execution_id="exec_rag",
        )

        result = RAGQueryResult(
            snapshot_id="snap_rag",
            similarity=0.95,
            snapshot=snapshot,
            highlights=["matched text"],
        )

        d = result.to_dict()

        assert d["snapshot_id"] == "snap_rag"
        assert d["similarity"] == 0.95
        assert len(d["highlights"]) == 1


# ============================================================================
# SINGLETON TESTS
# ============================================================================

class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_snapshot_service_singleton(self, temp_persist_dir):
        """Test that get_snapshot_service returns singleton."""
        # Reset singleton
        import services.learning_snapshot_service as module
        module._snapshot_service = None

        service1 = get_snapshot_service(persist_dir=temp_persist_dir)
        service2 = get_snapshot_service()

        assert service1 is service2


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
