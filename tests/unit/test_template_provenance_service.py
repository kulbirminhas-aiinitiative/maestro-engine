#!/usr/bin/env python3
"""
Unit Tests for Template Provenance & Citations Service
Epic MD-1824: [MT-200] Template Provenance & Citations System

Tests cover all acceptance criteria:
- AC-1: Provenance fields added to template metadata schema
- AC-2: Create/promote APIs require provenance payload
- AC-3: GET /templates/{id} returns full provenance
- AC-4: Search results include provenance summary
- AC-5: Citations link to source artifacts with valid URIs
"""

import pytest
import sys
import os
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from services.template_provenance_service import (
    TemplateProvenanceService,
    TemplateProvenance,
    ProvenanceSource,
    ToolChain,
    Citation,
    ProvenanceType,
    CitationType,
    ProvenanceValidationStatus,
    ProvenanceValidationResult,
    LineageNode,
    get_template_provenance_service,
    create_template_provenance,
    get_template_provenance,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def provenance_service():
    """Create a fresh TemplateProvenanceService instance."""
    return TemplateProvenanceService()


@pytest.fixture
def sample_provenance_data():
    """Sample provenance data for testing."""
    return {
        "template_id": "tpl_test_001",
        "source_repo": "github://acme/templates",
        "commit": "abc123def456",
        "tool_chain": "maestro+quality-fabric",
        "validation_report_id": "qf-validate-789",
    }


@pytest.fixture
def sample_citations():
    """Sample citations for testing."""
    return [
        {
            "type": "derived_from",
            "source_uri": "maestro://templates/base-api",
            "title": "Base API Template",
            "description": "Derived from standard API template",
        },
        {
            "type": "golden_project",
            "source_uri": "github://acme/golden-api",
            "title": "Golden API Project",
            "description": "Reference implementation",
        },
    ]


# ============================================================================
# SERVICE INITIALIZATION TESTS
# ============================================================================

class TestProvenanceServiceInit:
    """Tests for service initialization."""

    def test_default_initialization(self):
        """Test service initializes correctly."""
        service = TemplateProvenanceService()
        assert service._provenance_cache == {}
        assert service._citation_index == {}

    def test_singleton_pattern(self):
        """Test get_template_provenance_service returns singleton."""
        import services.template_provenance_service as mod
        mod._template_provenance_service = None

        service1 = get_template_provenance_service()
        service2 = get_template_provenance_service()

        assert service1 is service2

    def test_get_config(self, provenance_service):
        """Test configuration retrieval."""
        config = provenance_service.get_config()

        assert "supported_uri_schemes" in config
        assert "provenance_types" in config
        assert "citation_types" in config
        assert "github" in config["supported_uri_schemes"]
        assert "derived_from" in config["citation_types"]


# ============================================================================
# PROVENANCE CREATION TESTS (AC-1, AC-2)
# ============================================================================

class TestProvenanceCreation:
    """Tests for AC-1 and AC-2: Provenance fields and create/promote requirements."""

    def test_create_basic_provenance(self, provenance_service, sample_provenance_data):
        """AC-1: Test creating provenance with basic fields."""
        provenance = provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
            commit=sample_provenance_data["commit"],
        )

        assert provenance is not None
        assert provenance.template_id == sample_provenance_data["template_id"]
        assert provenance.source.source_repo == sample_provenance_data["source_repo"]
        assert provenance.source.commit == sample_provenance_data["commit"]
        assert provenance.provenance_id.startswith("prov_")

    def test_create_provenance_with_validation_report(self, provenance_service, sample_provenance_data):
        """AC-1: Test provenance includes validation_report_id."""
        provenance = provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
            validation_report_id=sample_provenance_data["validation_report_id"],
        )

        assert provenance.validation_report_id == sample_provenance_data["validation_report_id"]

    def test_create_provenance_with_tool_chain(self, provenance_service, sample_provenance_data):
        """AC-1: Test provenance includes tool_chain field."""
        provenance = provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
            tool_chain="custom-toolchain",
        )

        assert provenance.tool_chain.name == "custom-toolchain"

    def test_create_provenance_with_citations(
        self, provenance_service, sample_provenance_data, sample_citations
    ):
        """AC-1 & AC-5: Test provenance with citations."""
        provenance = provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
            citations=sample_citations,
        )

        assert len(provenance.citations) == 2
        assert provenance.citations[0].citation_type == CitationType.DERIVED_FROM
        assert provenance.citations[1].citation_type == CitationType.GOLDEN_PROJECT

    def test_create_provenance_with_parent(self, provenance_service, sample_provenance_data):
        """AC-1: Test provenance with parent template (derivation)."""
        provenance = provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
            parent_template_id="tpl_parent_001",
        )

        assert provenance.parent_template_id == "tpl_parent_001"

    def test_convenience_function_create(self, sample_provenance_data):
        """Test create_template_provenance convenience function."""
        import services.template_provenance_service as mod
        mod._template_provenance_service = None

        provenance = create_template_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
        )

        assert provenance.template_id == sample_provenance_data["template_id"]


# ============================================================================
# PROVENANCE RETRIEVAL TESTS (AC-3)
# ============================================================================

class TestProvenanceRetrieval:
    """Tests for AC-3: GET /templates/{id} returns full provenance."""

    def test_get_provenance_by_template_id(self, provenance_service, sample_provenance_data):
        """AC-3: Test retrieving provenance by template ID."""
        provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
            commit=sample_provenance_data["commit"],
        )

        retrieved = provenance_service.get_provenance(sample_provenance_data["template_id"])

        assert retrieved is not None
        assert retrieved.template_id == sample_provenance_data["template_id"]

    def test_get_provenance_by_id(self, provenance_service, sample_provenance_data):
        """Test retrieving provenance by provenance ID."""
        created = provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
        )

        retrieved = provenance_service.get_provenance_by_id(created.provenance_id)

        assert retrieved is not None
        assert retrieved.provenance_id == created.provenance_id

    def test_get_nonexistent_provenance(self, provenance_service):
        """Test retrieving non-existent provenance returns None."""
        result = provenance_service.get_provenance("nonexistent_template")
        assert result is None

    def test_convenience_function_get(self, sample_provenance_data):
        """Test get_template_provenance convenience function."""
        import services.template_provenance_service as mod
        mod._template_provenance_service = None

        service = get_template_provenance_service()
        service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
        )

        result = get_template_provenance(sample_provenance_data["template_id"])
        assert result is not None


# ============================================================================
# PROVENANCE SUMMARY TESTS (AC-4)
# ============================================================================

class TestProvenanceSummary:
    """Tests for AC-4: Search results include provenance summary."""

    def test_get_summary(self, provenance_service, sample_provenance_data, sample_citations):
        """AC-4: Test provenance summary for search results."""
        provenance = provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
            commit=sample_provenance_data["commit"],
            tool_chain="maestro+quality-fabric",
            validation_report_id=sample_provenance_data["validation_report_id"],
            citations=sample_citations,
        )

        summary = provenance.get_summary()

        assert summary["source_repo"] == sample_provenance_data["source_repo"]
        assert summary["commit"] == sample_provenance_data["commit"]
        assert summary["tool_chain"] == "maestro+quality-fabric"
        assert summary["validation_report_id"] == sample_provenance_data["validation_report_id"]
        assert summary["citation_count"] == 2
        assert summary["provenance_type"] == "github"

    def test_summary_includes_provenance_type(self, provenance_service):
        """AC-4: Test summary includes inferred provenance type."""
        provenance = provenance_service.create_provenance(
            template_id="tpl_gitlab",
            source_repo="gitlab://company/repo",
        )

        summary = provenance.get_summary()
        assert summary["provenance_type"] == "gitlab"


# ============================================================================
# CITATION TESTS (AC-5)
# ============================================================================

class TestCitations:
    """Tests for AC-5: Citations link to source artifacts with valid URIs."""

    def test_add_citation(self, provenance_service, sample_provenance_data):
        """AC-5: Test adding a citation."""
        provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
        )

        citation = provenance_service.add_citation(
            template_id=sample_provenance_data["template_id"],
            citation_type="derived_from",
            source_uri="github://org/base-template",
            title="Base Template",
            description="Derived from this template",
        )

        assert citation is not None
        assert citation.citation_id.startswith("cite_")
        assert citation.source_uri == "github://org/base-template"

    def test_add_citation_to_nonexistent_template(self, provenance_service):
        """AC-5: Test adding citation to non-existent template returns None."""
        citation = provenance_service.add_citation(
            template_id="nonexistent",
            citation_type="derived_from",
            source_uri="github://org/repo",
        )

        assert citation is None

    def test_add_citation_with_invalid_uri(self, provenance_service, sample_provenance_data):
        """AC-5: Test adding citation with invalid URI fails."""
        provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
        )

        # Empty URI should fail
        citation = provenance_service.add_citation(
            template_id=sample_provenance_data["template_id"],
            citation_type="derived_from",
            source_uri="",
        )

        assert citation is None

    def test_get_citations(self, provenance_service, sample_provenance_data, sample_citations):
        """AC-5: Test retrieving all citations."""
        provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
            citations=sample_citations,
        )

        citations = provenance_service.get_citations(sample_provenance_data["template_id"])

        assert len(citations) == 2

    def test_verify_citation(self, provenance_service, sample_provenance_data):
        """AC-5: Test verifying a citation."""
        provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
        )

        citation = provenance_service.add_citation(
            template_id=sample_provenance_data["template_id"],
            citation_type="derived_from",
            source_uri="github://org/template",
        )

        verified = provenance_service.verify_citation(
            template_id=sample_provenance_data["template_id"],
            citation_id=citation.citation_id,
        )

        assert verified is True

        # Check citation was marked as verified
        citations = provenance_service.get_citations(sample_provenance_data["template_id"])
        verified_citation = next(c for c in citations if c.citation_id == citation.citation_id)
        assert verified_citation.verified is True
        assert verified_citation.verified_at is not None


# ============================================================================
# URI VALIDATION TESTS (AC-5)
# ============================================================================

class TestURIValidation:
    """Tests for AC-5: URI validation."""

    def test_validate_github_uri(self, provenance_service):
        """AC-5: Test valid GitHub URI."""
        is_valid, error = provenance_service.validate_uri("github://org/repo")
        assert is_valid is True
        assert error is None

    def test_validate_github_uri_with_path(self, provenance_service):
        """AC-5: Test valid GitHub URI with path."""
        is_valid, error = provenance_service.validate_uri("github://org/repo/path")
        assert is_valid is True

    def test_validate_gitlab_uri(self, provenance_service):
        """AC-5: Test valid GitLab URI."""
        is_valid, error = provenance_service.validate_uri("gitlab://company/project")
        assert is_valid is True

    def test_validate_s3_uri(self, provenance_service):
        """AC-5: Test valid S3 URI."""
        is_valid, error = provenance_service.validate_uri("s3://bucket/path/to/artifact")
        assert is_valid is True

    def test_validate_http_uri(self, provenance_service):
        """AC-5: Test valid HTTP URI."""
        is_valid, error = provenance_service.validate_uri("https://example.com/artifact")
        assert is_valid is True

    def test_validate_maestro_uri(self, provenance_service):
        """AC-5: Test valid Maestro URI."""
        is_valid, error = provenance_service.validate_uri("maestro://templates/base-api")
        assert is_valid is True

    def test_validate_empty_uri(self, provenance_service):
        """AC-5: Test empty URI is invalid."""
        is_valid, error = provenance_service.validate_uri("")
        assert is_valid is False
        assert error is not None

    def test_validate_malformed_uri(self, provenance_service):
        """AC-5: Test malformed URI is invalid."""
        is_valid, error = provenance_service.validate_uri("not-a-valid-uri")
        assert is_valid is False


# ============================================================================
# PROVENANCE VALIDATION TESTS (AC-2)
# ============================================================================

class TestProvenanceValidation:
    """Tests for AC-2: Validation of provenance payload."""

    def test_validate_complete_provenance(self, provenance_service, sample_provenance_data):
        """AC-2: Test validation of complete provenance."""
        provenance = provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
            commit=sample_provenance_data["commit"],
        )

        result = provenance_service.validate_provenance(provenance)

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.validation_time_ms > 0

    def test_validate_provenance_missing_source(self, provenance_service):
        """AC-2: Test validation fails without source_repo."""
        provenance = TemplateProvenance(
            provenance_id="prov_test",
            template_id="tpl_test",
            source=ProvenanceSource(source_repo=""),
            tool_chain=ToolChain(name="test"),
        )

        result = provenance_service.validate_provenance(provenance)

        assert result.is_valid is False
        assert "source_repo is required" in result.errors

    def test_validate_provenance_require_commit(self, provenance_service, sample_provenance_data):
        """AC-2: Test commit requirement for promote."""
        provenance = provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
            # No commit provided
        )

        result = provenance_service.validate_provenance(provenance, require_commit=True)

        assert result.is_valid is False
        assert "commit hash is required" in str(result.errors)

    def test_validate_provenance_invalid_citation(self, provenance_service, sample_provenance_data):
        """AC-2: Test validation fails with invalid citation URI."""
        provenance = provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
            citations=[{"type": "derived_from", "source_uri": ""}],
        )

        # The validation happens during creation
        assert provenance.validation_status == ProvenanceValidationStatus.INVALID


# ============================================================================
# LINEAGE TESTS
# ============================================================================

class TestLineage:
    """Tests for lineage chain retrieval."""

    def test_get_lineage_single_node(self, provenance_service, sample_provenance_data):
        """Test lineage for template with no parent."""
        provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
        )

        lineage = provenance_service.get_lineage(sample_provenance_data["template_id"])

        assert len(lineage) == 1
        assert lineage[0].template_id == sample_provenance_data["template_id"]
        assert lineage[0].depth == 0

    def test_get_lineage_with_parent(self, provenance_service):
        """Test lineage for derived template."""
        # Create parent
        provenance_service.create_provenance(
            template_id="tpl_parent",
            source_repo="github://org/parent",
        )

        # Create child
        provenance_service.create_provenance(
            template_id="tpl_child",
            source_repo="github://org/child",
            parent_template_id="tpl_parent",
        )

        lineage = provenance_service.get_lineage("tpl_child")

        assert len(lineage) == 2
        assert lineage[0].template_id == "tpl_child"
        assert lineage[0].depth == 0
        assert lineage[1].template_id == "tpl_parent"
        assert lineage[1].depth == 1

    def test_get_derived_templates(self):
        """Test getting templates derived from a parent."""
        # Use fresh service to avoid singleton pollution
        service = TemplateProvenanceService()

        # Create parent
        service.create_provenance(
            template_id="tpl_parent_derived",
            source_repo="github://org/parent",
        )

        # Create children
        service.create_provenance(
            template_id="tpl_child_d1",
            source_repo="github://org/child1",
            parent_template_id="tpl_parent_derived",
        )
        service.create_provenance(
            template_id="tpl_child_d2",
            source_repo="github://org/child2",
            parent_template_id="tpl_parent_derived",
        )

        derived = service.get_derived_templates("tpl_parent_derived")

        assert len(derived) == 2
        assert "tpl_child_d1" in derived
        assert "tpl_child_d2" in derived


# ============================================================================
# PROVENANCE TYPE INFERENCE TESTS
# ============================================================================

class TestProvenanceTypeInference:
    """Tests for provenance type inference from source URI."""

    def test_infer_github_type(self, provenance_service):
        """Test GitHub type inference."""
        ptype = provenance_service._infer_provenance_type("github://org/repo")
        assert ptype == ProvenanceType.GITHUB

    def test_infer_gitlab_type(self, provenance_service):
        """Test GitLab type inference."""
        ptype = provenance_service._infer_provenance_type("gitlab://company/project")
        assert ptype == ProvenanceType.GITLAB

    def test_infer_bitbucket_type(self, provenance_service):
        """Test Bitbucket type inference."""
        ptype = provenance_service._infer_provenance_type("bitbucket://team/repo")
        assert ptype == ProvenanceType.BITBUCKET

    def test_infer_golden_project_type(self, provenance_service):
        """Test golden project type inference."""
        ptype = provenance_service._infer_provenance_type("maestro://golden/api-template")
        assert ptype == ProvenanceType.GOLDEN_PROJECT

    def test_infer_local_type(self, provenance_service):
        """Test local type inference."""
        ptype = provenance_service._infer_provenance_type("file:///path/to/template")
        assert ptype == ProvenanceType.LOCAL

    def test_infer_generated_type(self, provenance_service):
        """Test generated type for unknown sources."""
        ptype = provenance_service._infer_provenance_type("custom://internal/template")
        assert ptype == ProvenanceType.GENERATED


# ============================================================================
# SEARCH TESTS
# ============================================================================

class TestSearch:
    """Tests for search functionality."""

    def test_search_by_source(self):
        """Test searching templates by source pattern."""
        # Use fresh service to avoid singleton pollution
        service = TemplateProvenanceService()

        # Create multiple provenances
        service.create_provenance(
            template_id="tpl_search_1",
            source_repo="github://acme/api-templates",
        )
        service.create_provenance(
            template_id="tpl_search_2",
            source_repo="github://acme/web-templates",
        )
        service.create_provenance(
            template_id="tpl_search_3",
            source_repo="gitlab://company/templates",
        )

        results = service.search_by_source("github://acme")

        assert len(results) == 2
        template_ids = [r.template_id for r in results]
        assert "tpl_search_1" in template_ids
        assert "tpl_search_2" in template_ids


# ============================================================================
# DATA CLASS TESTS
# ============================================================================

class TestDataClasses:
    """Tests for data class serialization."""

    def test_provenance_source_to_dict(self):
        """Test ProvenanceSource serialization."""
        source = ProvenanceSource(
            source_repo="github://org/repo",
            commit="abc123",
            branch="main",
        )

        result = source.to_dict()

        assert result["source_repo"] == "github://org/repo"
        assert result["commit"] == "abc123"
        assert result["branch"] == "main"

    def test_provenance_source_from_dict(self):
        """Test ProvenanceSource deserialization."""
        data = {"source_repo": "github://org/repo", "commit": "def456"}

        source = ProvenanceSource.from_dict(data)

        assert source.source_repo == "github://org/repo"
        assert source.commit == "def456"

    def test_tool_chain_to_dict(self):
        """Test ToolChain serialization."""
        tool_chain = ToolChain(
            name="maestro+qf",
            version="2.0.0",
            components=["maestro", "quality-fabric"],
        )

        result = tool_chain.to_dict()

        assert result["name"] == "maestro+qf"
        assert result["version"] == "2.0.0"
        assert "maestro" in result["components"]

    def test_citation_to_dict(self):
        """Test Citation serialization."""
        citation = Citation(
            citation_id="cite_123",
            citation_type=CitationType.DERIVED_FROM,
            source_uri="github://org/template",
            title="Test Citation",
        )

        result = citation.to_dict()

        assert result["citation_id"] == "cite_123"
        assert result["citation_type"] == "derived_from"
        assert result["source_uri"] == "github://org/template"

    def test_template_provenance_to_dict(self, provenance_service, sample_provenance_data):
        """Test TemplateProvenance serialization."""
        provenance = provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
        )

        result = provenance.to_dict()

        assert "provenance_id" in result
        assert "template_id" in result
        assert "source" in result
        assert "tool_chain" in result
        assert "citations" in result
        assert "provenance_type" in result

    def test_lineage_node_to_dict(self):
        """Test LineageNode serialization."""
        node = LineageNode(
            template_id="tpl_123",
            version="1.0.0",
            provenance_id="prov_456",
            source_repo="github://org/repo",
            created_at="2024-01-01T00:00:00",
            depth=0,
        )

        result = node.to_dict()

        assert result["template_id"] == "tpl_123"
        assert result["depth"] == 0


# ============================================================================
# ENUM TESTS
# ============================================================================

class TestEnums:
    """Tests for enum values."""

    def test_provenance_type_values(self):
        """Test ProvenanceType enum values."""
        assert ProvenanceType.GITHUB.value == "github"
        assert ProvenanceType.GITLAB.value == "gitlab"
        assert ProvenanceType.GOLDEN_PROJECT.value == "golden_project"

    def test_citation_type_values(self):
        """Test CitationType enum values."""
        assert CitationType.DERIVED_FROM.value == "derived_from"
        assert CitationType.INSPIRED_BY.value == "inspired_by"
        assert CitationType.GOLDEN_PROJECT.value == "golden_project"

    def test_validation_status_values(self):
        """Test ProvenanceValidationStatus enum values."""
        assert ProvenanceValidationStatus.VALID.value == "valid"
        assert ProvenanceValidationStatus.INVALID.value == "invalid"
        assert ProvenanceValidationStatus.PENDING.value == "pending"


# ============================================================================
# UPDATE OPERATIONS TESTS
# ============================================================================

class TestUpdateOperations:
    """Tests for update operations."""

    def test_update_validation_report(self, provenance_service, sample_provenance_data):
        """Test updating validation report ID."""
        provenance_service.create_provenance(
            template_id=sample_provenance_data["template_id"],
            source_repo=sample_provenance_data["source_repo"],
        )

        updated = provenance_service.update_validation_report(
            template_id=sample_provenance_data["template_id"],
            validation_report_id="new-report-123",
        )

        assert updated is True

        provenance = provenance_service.get_provenance(sample_provenance_data["template_id"])
        assert provenance.validation_report_id == "new-report-123"

    def test_update_validation_report_nonexistent(self, provenance_service):
        """Test updating non-existent template returns False."""
        updated = provenance_service.update_validation_report(
            template_id="nonexistent",
            validation_report_id="report-123",
        )

        assert updated is False


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
