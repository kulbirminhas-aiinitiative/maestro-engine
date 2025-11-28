#!/usr/bin/env python3
"""
Unit tests for Template Versions & Recommendation Service
Epic: MD-1831 [MT-400] Template Versions & Recommendation APIs

Tests cover all Acceptance Criteria:
- AC-1: Versions API returns array with version, changes, date
- AC-2: Recommend API accepts persona, tag, min_score params
- AC-3: Recommendations ranked by composite score
- AC-4: Response includes usage_stats and citations
- AC-5: Pagination support for large result sets
"""

import pytest
from datetime import datetime
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from services.template_versions_service import (
    TemplateVersionsService,
    TemplateVersion,
    UsageStats,
    TemplateRecommendation,
    RecommendationRequest,
    RecommendationResponse,
    VersionChangeType,
    RecommendationStrategy,
    get_template_versions_service,
)


class TestTemplateVersionsService:
    """Tests for TemplateVersionsService."""

    @pytest.fixture
    def service(self):
        """Create a fresh service instance for testing."""
        return TemplateVersionsService()

    # ========================================================================
    # AC-1: Versions API Tests
    # ========================================================================

    def test_get_template_versions_returns_array(self, service):
        """AC-1: Versions API returns array with version, changes, date."""
        versions, total = service.get_template_versions("api_auth_v3")

        assert isinstance(versions, list)
        assert total > 0
        assert len(versions) <= total

        # Each version should have required fields
        for v in versions:
            assert hasattr(v, 'version')
            assert hasattr(v, 'changes')
            assert hasattr(v, 'created_at')
            assert isinstance(v.version, str)
            assert isinstance(v.changes, list)
            assert isinstance(v.created_at, datetime)

    def test_get_template_versions_sorted_by_version(self, service):
        """AC-1: Versions should be sorted by version number (newest first)."""
        versions, _ = service.get_template_versions("api_auth_v3")

        if len(versions) >= 2:
            for i in range(len(versions) - 1):
                # Newer versions should come first
                v1 = tuple(map(int, versions[i].version.split('.')))
                v2 = tuple(map(int, versions[i+1].version.split('.')))
                assert v1 >= v2

    def test_get_template_versions_pagination(self, service):
        """AC-1: Versions API supports pagination."""
        # Get first page
        versions_page1, total = service.get_template_versions(
            "api_auth_v3", limit=1, offset=0
        )
        assert len(versions_page1) == 1

        # Get second page
        versions_page2, _ = service.get_template_versions(
            "api_auth_v3", limit=1, offset=1
        )
        assert len(versions_page2) <= 1

        # Pages should have different versions (if available)
        if len(versions_page2) > 0:
            assert versions_page1[0].version != versions_page2[0].version

    def test_get_template_versions_not_found(self, service):
        """AC-1: Returns empty for non-existent template."""
        versions, total = service.get_template_versions("non_existent_template")
        assert versions == []
        assert total == 0

    def test_get_version_details(self, service):
        """Test getting specific version details."""
        version = service.get_version_details("api_auth_v3", "1.0.0")

        assert version is not None
        assert version.version == "1.0.0"
        assert version.template_id == "api_auth_v3"

    def test_create_version(self, service):
        """Test creating a new version."""
        new_version = service.create_version(
            template_id="api_auth_v3",
            version="1.2.0",
            changes=["Added rate limiting", "Fixed security issue"],
            changelog="Added rate limiting and fixed security vulnerability",
            created_by="test_user",
            change_type=VersionChangeType.MINOR,
            quality_score=93.0,
        )

        assert new_version.version == "1.2.0"
        assert len(new_version.changes) == 2
        assert new_version.parent_version == "1.1.0"  # Should reference previous version

        # Verify it was added
        versions, total = service.get_template_versions("api_auth_v3")
        assert any(v.version == "1.2.0" for v in versions)

    # ========================================================================
    # AC-2: Recommend API Filter Tests
    # ========================================================================

    def test_recommend_api_accepts_persona(self, service):
        """AC-2: Recommend API accepts persona parameter."""
        request = RecommendationRequest(persona="backend_developer")
        response = service.get_recommendations(request)

        assert isinstance(response, RecommendationResponse)
        assert response.filters_applied["persona"] == "backend_developer"

        # All results should match the persona
        for rec in response.recommendations:
            assert rec.persona_match is True

    def test_recommend_api_accepts_tags(self, service):
        """AC-2: Recommend API accepts tag parameter."""
        request = RecommendationRequest(tags=["auth", "security"])
        response = service.get_recommendations(request)

        assert response.filters_applied["tags"] == ["auth", "security"]

        # Results should have tag matches
        assert len(response.recommendations) > 0
        for rec in response.recommendations:
            assert rec.tag_match is True

    def test_recommend_api_accepts_min_score(self, service):
        """AC-2: Recommend API accepts min_score parameter."""
        min_score = 90.0
        request = RecommendationRequest(min_score=min_score)
        response = service.get_recommendations(request)

        assert response.filters_applied["min_score"] == min_score

        # All results should have quality_score >= min_score
        for rec in response.recommendations:
            assert rec.quality_score >= min_score

    def test_recommend_api_combined_filters(self, service):
        """AC-2: Recommend API accepts multiple parameters."""
        request = RecommendationRequest(
            persona="backend_developer",
            tags=["auth"],
            min_score=85.0,
        )
        response = service.get_recommendations(request)

        assert response.filters_applied["persona"] == "backend_developer"
        assert response.filters_applied["tags"] == ["auth"]
        assert response.filters_applied["min_score"] == 85.0

    def test_recommend_api_language_filter(self, service):
        """AC-2: Recommend API accepts language filter."""
        request = RecommendationRequest(language="python")
        response = service.get_recommendations(request)

        for rec in response.recommendations:
            assert rec.metadata.get("language") == "python"

    def test_recommend_api_framework_filter(self, service):
        """AC-2: Recommend API accepts framework filter."""
        request = RecommendationRequest(framework="fastapi")
        response = service.get_recommendations(request)

        for rec in response.recommendations:
            assert rec.metadata.get("framework") == "fastapi"

    # ========================================================================
    # AC-3: Ranking Tests
    # ========================================================================

    def test_recommendations_ranked_by_composite_score(self, service):
        """AC-3: Recommendations ranked by composite score."""
        request = RecommendationRequest()
        response = service.get_recommendations(request)

        scores = [rec.score for rec in response.recommendations]

        # Scores should be in descending order
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_recommendations_quality_first_strategy(self, service):
        """AC-3: Quality-first strategy prioritizes quality score."""
        request = RecommendationRequest(strategy=RecommendationStrategy.QUALITY_FIRST)
        response = service.get_recommendations(request)

        assert response.strategy_used == "quality_first"

        # Higher quality templates should rank higher
        quality_scores = [rec.quality_score for rec in response.recommendations]
        # Check that quality is the dominant factor (top results have high quality)
        if len(quality_scores) >= 2:
            assert quality_scores[0] >= 85  # Top result should have good quality

    def test_recommendations_usage_first_strategy(self, service):
        """AC-3: Usage-first strategy prioritizes success rate."""
        request = RecommendationRequest(strategy=RecommendationStrategy.USAGE_FIRST)
        response = service.get_recommendations(request)

        assert response.strategy_used == "usage_first"

    def test_recommendations_composite_strategy(self, service):
        """AC-3: Composite strategy balances multiple factors."""
        request = RecommendationRequest(strategy=RecommendationStrategy.COMPOSITE)
        response = service.get_recommendations(request)

        assert response.strategy_used == "composite"

    # ========================================================================
    # AC-4: Response Content Tests
    # ========================================================================

    def test_response_includes_usage_stats(self, service):
        """AC-4: Response includes usage_stats."""
        request = RecommendationRequest(include_usage_stats=True)
        response = service.get_recommendations(request)

        for rec in response.recommendations:
            assert rec.usage_stats is not None
            assert hasattr(rec.usage_stats, 'applied_count')
            assert hasattr(rec.usage_stats, 'success_rate')
            assert hasattr(rec.usage_stats, 'avg_quality_score')

    def test_response_includes_citations(self, service):
        """AC-4: Response includes citations."""
        request = RecommendationRequest(include_citations=True)
        response = service.get_recommendations(request)

        # At least some recommendations should have citations
        has_citations = any(len(rec.citations) > 0 for rec in response.recommendations)
        assert has_citations

    def test_response_includes_match_reasons(self, service):
        """AC-4: Response includes match_reasons explaining ranking."""
        request = RecommendationRequest(persona="backend_developer")
        response = service.get_recommendations(request)

        for rec in response.recommendations:
            assert isinstance(rec.match_reasons, list)
            # Should have at least one reason for matches
            assert len(rec.match_reasons) > 0

    def test_response_can_exclude_usage_stats(self, service):
        """AC-4: Usage stats can be excluded."""
        request = RecommendationRequest(include_usage_stats=False)
        response = service.get_recommendations(request)

        # Response should still work without detailed stats
        assert isinstance(response.recommendations, list)

    def test_response_can_exclude_citations(self, service):
        """AC-4: Citations can be excluded."""
        request = RecommendationRequest(include_citations=False)
        response = service.get_recommendations(request)

        # Citations should be empty when excluded
        for rec in response.recommendations:
            assert rec.citations == []

    # ========================================================================
    # AC-5: Pagination Tests
    # ========================================================================

    def test_pagination_limit(self, service):
        """AC-5: Pagination respects limit parameter."""
        request = RecommendationRequest(limit=2)
        response = service.get_recommendations(request)

        assert len(response.recommendations) <= 2
        assert response.page_size == 2

    def test_pagination_offset(self, service):
        """AC-5: Pagination respects offset parameter."""
        # Get all results
        all_request = RecommendationRequest(limit=10)
        all_response = service.get_recommendations(all_request)

        if all_response.total > 2:
            # Get first page
            page1 = RecommendationRequest(limit=2, offset=0)
            response1 = service.get_recommendations(page1)

            # Get second page
            page2 = RecommendationRequest(limit=2, offset=2)
            response2 = service.get_recommendations(page2)

            # Results should be different
            if len(response2.recommendations) > 0:
                assert response1.recommendations[0].template_id != response2.recommendations[0].template_id

    def test_pagination_has_more(self, service):
        """AC-5: Response includes has_more indicator."""
        request = RecommendationRequest(limit=1)
        response = service.get_recommendations(request)

        if response.total > 1:
            assert response.has_more is True
        else:
            assert response.has_more is False

    def test_pagination_total_count(self, service):
        """AC-5: Response includes total count."""
        request = RecommendationRequest(limit=2)
        response = service.get_recommendations(request)

        assert response.total >= len(response.recommendations)

    def test_pagination_page_number(self, service):
        """AC-5: Response includes page number."""
        request = RecommendationRequest(limit=2, offset=2)
        response = service.get_recommendations(request)

        assert response.page == 2  # Page 2 (0-indexed offset 2, size 2)

    # ========================================================================
    # Additional Tests
    # ========================================================================

    def test_record_template_usage(self, service):
        """Test recording template usage."""
        template_id = "api_auth_v3"
        initial_stats = service.get_usage_stats(template_id)
        initial_count = initial_stats.applied_count if initial_stats else 0

        service.record_template_usage(
            template_id=template_id,
            success=True,
            quality_score=95.0,
            user_id="test_user",
            project_id="test_project",
        )

        updated_stats = service.get_usage_stats(template_id)
        assert updated_stats.applied_count == initial_count + 1

    def test_get_usage_stats(self, service):
        """Test getting usage statistics."""
        stats = service.get_usage_stats("api_auth_v3")

        assert stats is not None
        assert stats.template_id == "api_auth_v3"
        assert stats.applied_count > 0
        assert 0 <= stats.success_rate <= 1

    def test_get_usage_stats_not_found(self, service):
        """Test getting stats for non-existent template."""
        stats = service.get_usage_stats("non_existent")
        assert stats is None

    def test_add_citation(self, service):
        """Test adding citations."""
        template_id = "api_auth_v3"
        new_citation = "test-citation/ref-123"

        service.add_citation(template_id, new_citation)
        citations = service.get_citations(template_id)

        assert new_citation in citations

    def test_add_duplicate_citation(self, service):
        """Test that duplicate citations are not added."""
        template_id = "api_auth_v3"
        citation = "unique-citation-12345"

        service.add_citation(template_id, citation)
        service.add_citation(template_id, citation)  # Add again

        citations = service.get_citations(template_id)
        assert citations.count(citation) == 1

    def test_singleton_instance(self):
        """Test singleton pattern."""
        service1 = get_template_versions_service()
        service2 = get_template_versions_service()

        assert service1 is service2

    def test_version_to_dict(self, service):
        """Test version serialization."""
        version = service.get_version_details("api_auth_v3", "1.0.0")
        version_dict = version.to_dict()

        assert "version" in version_dict
        assert "template_id" in version_dict
        assert "created_at" in version_dict
        assert "changes" in version_dict

    def test_recommendation_to_dict(self, service):
        """Test recommendation serialization."""
        request = RecommendationRequest(limit=1)
        response = service.get_recommendations(request)

        if response.recommendations:
            rec_dict = response.recommendations[0].to_dict()
            assert "template_id" in rec_dict
            assert "score" in rec_dict
            assert "usage_stats" in rec_dict
            assert "citations" in rec_dict

    # ========================================================================
    # Rollback Tests (MD-1869)
    # ========================================================================

    def test_rollback_version_success(self, service):
        """Test successful version rollback."""
        template_id = "api_auth_v3"

        # Get current versions
        versions_before, _ = service.get_template_versions(template_id)
        assert len(versions_before) >= 2

        # Rollback to version 1.0.0
        rollback = service.rollback_version(
            template_id=template_id,
            target_version="1.0.0",
            rolled_back_by="test_user",
            reason="Testing rollback functionality",
        )

        assert rollback is not None
        assert "rollback" in rollback.metadata
        assert rollback.metadata["rollback"]["to_version"] == "1.0.0"
        assert "Rolled back" in rollback.changes[0]

    def test_rollback_version_not_found(self, service):
        """Test rollback to non-existent version returns None."""
        result = service.rollback_version(
            template_id="api_auth_v3",
            target_version="99.99.99",
            rolled_back_by="test_user",
        )

        assert result is None

    def test_rollback_to_same_version(self, service):
        """Test rollback to current version returns current version."""
        template_id = "api_auth_v3"

        # Get current version
        versions, _ = service.get_template_versions(template_id, limit=1)
        current = versions[0]

        # Try to rollback to current version
        result = service.rollback_version(
            template_id=template_id,
            target_version=current.version,
            rolled_back_by="test_user",
        )

        # Should return the current version (no new version created)
        assert result is not None
        assert result.version == current.version

    def test_rollback_creates_new_version(self, service):
        """Test that rollback creates a new version entry."""
        template_id = "api_auth_v3"

        # Count versions before
        _, count_before = service.get_template_versions(template_id)

        # Perform rollback
        service.rollback_version(
            template_id=template_id,
            target_version="1.0.0",
            rolled_back_by="test_user",
            reason="Testing",
        )

        # Count versions after
        _, count_after = service.get_template_versions(template_id)

        assert count_after == count_before + 1

    def test_get_rollback_candidates(self, service):
        """Test getting rollback candidate versions."""
        candidates = service.get_rollback_candidates("api_auth_v3", max_versions=5)

        # Should not include current version
        versions, _ = service.get_template_versions("api_auth_v3", limit=1)
        current = versions[0]

        assert all(c.version != current.version for c in candidates)
        assert len(candidates) <= 5

    def test_get_rollback_candidates_empty(self, service):
        """Test rollback candidates for template with only one version."""
        # Create a new template with only one version
        service.create_version(
            template_id="single_version_template",
            version="1.0.0",
            changes=["Initial"],
            changelog="Initial release",
            created_by="test",
        )

        candidates = service.get_rollback_candidates("single_version_template")
        assert candidates == []

    def test_validate_rollback_valid(self, service):
        """Test rollback validation for valid target."""
        result = service.validate_rollback("api_auth_v3", "1.0.0")

        assert result["valid"] is True
        assert len(result["issues"]) == 0
        assert "target_version" in result

    def test_validate_rollback_invalid_version(self, service):
        """Test rollback validation for non-existent version."""
        result = service.validate_rollback("api_auth_v3", "99.99.99")

        assert result["valid"] is False
        assert len(result["issues"]) > 0
        assert "not found" in result["issues"][0]

    def test_validate_rollback_low_quality_warning(self, service):
        """Test rollback validation warns about low quality score."""
        # Create a version with low quality score
        service.create_version(
            template_id="low_quality_template",
            version="1.0.0",
            changes=["Initial"],
            changelog="Initial release",
            created_by="test",
            quality_score=50.0,
        )

        result = service.validate_rollback("low_quality_template", "1.0.0")

        # Should be valid but with warnings
        assert result["valid"] is True
        assert any("low quality" in w.lower() for w in result.get("warnings", []))


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
