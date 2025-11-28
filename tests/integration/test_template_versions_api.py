#!/usr/bin/env python3
"""
Integration tests for Template Versions & Recommendation API Routes
Epic: MD-1831 [MT-400] Template Versions & Recommendation APIs

Tests the REST API endpoints against quality-fabric API.
"""

import pytest
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from api.template_versions_routes import router, register_template_versions_routes


# Create test app
app = FastAPI()
app.include_router(router)

client = TestClient(app)


class TestTemplateVersionsAPI:
    """Integration tests for Template Versions API endpoints."""

    # ========================================================================
    # Health & Config Endpoints
    # ========================================================================

    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = client.get("/api/templates/versions/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "template-versions"

    def test_config_endpoint(self):
        """Test configuration endpoint."""
        response = client.get("/api/templates/versions/config")
        assert response.status_code == 200
        data = response.json()
        assert "feature_flag_enabled" in data
        assert "scoring_weights" in data
        assert "supported_strategies" in data

    # ========================================================================
    # AC-1: Versions API Tests
    # ========================================================================

    def test_get_versions_success(self):
        """AC-1: GET /templates/{id}/versions returns version array."""
        response = client.get("/api/templates/api_auth_v3/versions")
        assert response.status_code == 200
        data = response.json()

        assert "versions" in data
        assert isinstance(data["versions"], list)
        assert len(data["versions"]) > 0

        # Each version should have required fields
        for v in data["versions"]:
            assert "version" in v
            assert "changes" in v
            assert "created_at" in v

    def test_get_versions_pagination(self):
        """AC-1: Versions API supports pagination."""
        response = client.get("/api/templates/api_auth_v3/versions?limit=1&offset=0")
        assert response.status_code == 200
        data = response.json()

        assert data["limit"] == 1
        assert data["offset"] == 0
        assert len(data["versions"]) <= 1
        assert "has_more" in data
        assert "total" in data

    def test_get_versions_not_found(self):
        """AC-1: Returns 404 for non-existent template."""
        response = client.get("/api/templates/non_existent_template/versions")
        assert response.status_code == 404

    def test_get_version_details(self):
        """Test getting specific version details."""
        response = client.get("/api/templates/api_auth_v3/versions/1.0.0")
        assert response.status_code == 200
        data = response.json()

        assert data["version"] == "1.0.0"
        assert data["template_id"] == "api_auth_v3"

    def test_get_version_details_not_found(self):
        """Test 404 for non-existent version."""
        response = client.get("/api/templates/api_auth_v3/versions/99.0.0")
        assert response.status_code == 404

    def test_create_version(self):
        """Test creating a new version via API."""
        response = client.post(
            "/api/templates/api_auth_v3/versions",
            json={
                "version": "2.0.0",
                "changes": ["Major rewrite", "Added new authentication methods"],
                "changelog": "Version 2.0.0 - Major rewrite with new auth methods",
                "created_by": "test_api",
                "change_type": "major",
                "quality_score": 94.5,
            }
        )
        assert response.status_code == 200
        data = response.json()

        assert data["version"] == "2.0.0"
        assert len(data["changes"]) == 2
        assert data["change_type"] == "major"

    # ========================================================================
    # AC-2: Recommend API Filter Tests
    # ========================================================================

    def test_recommend_api_basic(self):
        """AC-2: GET /templates/recommend returns recommendations."""
        response = client.get("/api/templates/recommend")
        assert response.status_code == 200
        data = response.json()

        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)
        assert "total" in data
        assert "page" in data

    def test_recommend_api_persona_filter(self):
        """AC-2: Recommend API accepts persona parameter."""
        response = client.get("/api/templates/recommend?persona=backend_developer")
        assert response.status_code == 200
        data = response.json()

        assert data["filters_applied"]["persona"] == "backend_developer"
        for rec in data["recommendations"]:
            assert rec["persona_match"] is True

    def test_recommend_api_tags_filter(self):
        """AC-2: Recommend API accepts tags parameter."""
        response = client.get("/api/templates/recommend?tags=auth,security")
        assert response.status_code == 200
        data = response.json()

        assert "auth" in data["filters_applied"]["tags"]
        assert "security" in data["filters_applied"]["tags"]

    def test_recommend_api_min_score_filter(self):
        """AC-2: Recommend API accepts min_score parameter."""
        response = client.get("/api/templates/recommend?min_score=90")
        assert response.status_code == 200
        data = response.json()

        assert data["filters_applied"]["min_score"] == 90.0
        for rec in data["recommendations"]:
            assert rec["quality_score"] >= 90

    def test_recommend_api_combined_filters(self):
        """AC-2: Recommend API accepts multiple parameters."""
        response = client.get(
            "/api/templates/recommend?persona=backend_developer&tags=auth&min_score=85"
        )
        assert response.status_code == 200
        data = response.json()

        assert data["filters_applied"]["persona"] == "backend_developer"
        assert "auth" in data["filters_applied"]["tags"]
        assert data["filters_applied"]["min_score"] == 85.0

    # ========================================================================
    # AC-3: Ranking Tests
    # ========================================================================

    def test_recommendations_ranked_by_score(self):
        """AC-3: Recommendations ranked by composite score."""
        response = client.get("/api/templates/recommend")
        assert response.status_code == 200
        data = response.json()

        scores = [rec["score"] for rec in data["recommendations"]]
        # Scores should be in descending order
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_recommendations_strategy_parameter(self):
        """AC-3: Strategy parameter affects ranking."""
        response = client.get("/api/templates/recommend?strategy=quality_first")
        assert response.status_code == 200
        data = response.json()

        assert data["strategy_used"] == "quality_first"

    # ========================================================================
    # AC-4: Response Content Tests
    # ========================================================================

    def test_response_includes_usage_stats(self):
        """AC-4: Response includes usage_stats."""
        response = client.get("/api/templates/recommend")
        assert response.status_code == 200
        data = response.json()

        for rec in data["recommendations"]:
            assert "usage_stats" in rec
            stats = rec["usage_stats"]
            assert "applied_count" in stats
            assert "success_rate" in stats
            assert "avg_quality_score" in stats

    def test_response_includes_citations(self):
        """AC-4: Response includes citations."""
        response = client.get("/api/templates/recommend?include_citations=true")
        assert response.status_code == 200
        data = response.json()

        # At least some recommendations should have citations
        has_citations = any(
            len(rec["citations"]) > 0 for rec in data["recommendations"]
        )
        assert has_citations

    def test_response_excludes_citations_when_requested(self):
        """AC-4: Citations can be excluded."""
        response = client.get("/api/templates/recommend?include_citations=false")
        assert response.status_code == 200
        data = response.json()

        for rec in data["recommendations"]:
            assert rec["citations"] == []

    # ========================================================================
    # AC-5: Pagination Tests
    # ========================================================================

    def test_pagination_limit(self):
        """AC-5: Pagination respects limit parameter."""
        response = client.get("/api/templates/recommend?limit=2")
        assert response.status_code == 200
        data = response.json()

        assert len(data["recommendations"]) <= 2
        assert data["page_size"] == 2

    def test_pagination_offset(self):
        """AC-5: Pagination respects offset parameter."""
        response = client.get("/api/templates/recommend?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()

        assert data["page"] == 2

    def test_pagination_has_more(self):
        """AC-5: Response includes has_more indicator."""
        response = client.get("/api/templates/recommend?limit=1")
        assert response.status_code == 200
        data = response.json()

        assert "has_more" in data

    def test_pagination_total(self):
        """AC-5: Response includes total count."""
        response = client.get("/api/templates/recommend")
        assert response.status_code == 200
        data = response.json()

        assert "total" in data
        assert data["total"] >= len(data["recommendations"])

    # ========================================================================
    # Usage Tracking Tests
    # ========================================================================

    def test_record_usage(self):
        """Test recording template usage."""
        response = client.post(
            "/api/templates/api_auth_v3/usage",
            json={
                "success": True,
                "quality_score": 92.0,
                "user_id": "test_user",
                "project_id": "test_project",
            }
        )
        assert response.status_code == 200
        data = response.json()

        assert data["template_id"] == "api_auth_v3"
        assert "recorded_at" in data

    def test_get_usage_stats(self):
        """Test getting usage statistics."""
        response = client.get("/api/templates/api_auth_v3/usage-stats")
        assert response.status_code == 200
        data = response.json()

        assert "applied_count" in data
        assert "success_rate" in data
        assert "avg_quality_score" in data


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
