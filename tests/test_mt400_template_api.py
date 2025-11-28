"""
MT-400: Test Suite for Template Versions & Recommendation APIs
Comprehensive tests validating all acceptance criteria
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from api.mt400_template_api import router


# Create test app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestTemplateVersionsAPI:
    """Test suite for GET /api/v1/templates/{id}/versions"""
    
    def test_versions_endpoint_exists(self):
        """AC-1: Endpoint is accessible"""
        response = client.get("/api/v1/templates/test_template/versions")
        assert response.status_code == 200
    
    def test_versions_returns_array(self):
        """AC-2: Returns array with version history"""
        response = client.get("/api/v1/templates/api_auth_v3/versions")
        assert response.status_code == 200
        
        data = response.json()
        assert "versions" in data
        assert isinstance(data["versions"], list)
        assert len(data["versions"]) > 0
    
    def test_versions_required_fields(self):
        """AC-3: Each version includes version, changes, date"""
        response = client.get("/api/v1/templates/api_auth_v3/versions")
        data = response.json()
        
        for version in data["versions"]:
            assert "version" in version
            assert "changes" in version
            assert "date" in version
            assert isinstance(version["version"], str)
            assert isinstance(version["changes"], str)
            assert isinstance(version["date"], str)
    
    def test_versions_response_structure(self):
        """AC-4: Response follows REST conventions"""
        response = client.get("/api/v1/templates/api_auth_v3/versions")
        data = response.json()
        
        # Check response structure
        assert "template_id" in data
        assert "current_version" in data
        assert "versions" in data
        assert "total" in data
        
        assert data["template_id"] == "api_auth_v3"
        assert isinstance(data["total"], int)
    
    def test_versions_limit_parameter(self):
        """AC-5: Supports limit parameter"""
        response = client.get("/api/v1/templates/api_auth_v3/versions?limit=2")
        data = response.json()
        
        assert len(data["versions"]) <= 2
    
    def test_versions_includes_metadata(self):
        """AC-6: Includes author and commit_sha metadata"""
        response = client.get("/api/v1/templates/api_auth_v3/versions")
        data = response.json()
        
        first_version = data["versions"][0]
        assert "author" in first_version
        assert "commit_sha" in first_version


class TestTemplateRecommendationAPI:
    """Test suite for GET /api/v1/templates/recommend"""
    
    def test_recommend_endpoint_exists(self):
        """AC-1: Endpoint is accessible"""
        response = client.get("/api/v1/templates/recommend")
        assert response.status_code == 200
    
    def test_recommend_accepts_persona_filter(self):
        """AC-2: Accepts persona query parameter"""
        response = client.get("/api/v1/templates/recommend?persona=backend_developer")
        assert response.status_code == 200
        
        data = response.json()
        assert data["filters_applied"]["persona"] == "backend_developer"
    
    def test_recommend_accepts_tag_filter(self):
        """AC-3: Accepts tag query parameter"""
        response = client.get("/api/v1/templates/recommend?tag=auth")
        assert response.status_code == 200
        
        data = response.json()
        assert data["filters_applied"]["tag"] == "auth"
    
    def test_recommend_accepts_min_score_filter(self):
        """AC-4: Accepts min_score query parameter"""
        response = client.get("/api/v1/templates/recommend?min_score=85")
        assert response.status_code == 200
        
        data = response.json()
        assert data["filters_applied"]["min_score"] == 85
    
    def test_recommend_returns_ranked_results(self):
        """AC-5: Recommendations ranked by composite score"""
        response = client.get("/api/v1/templates/recommend")
        data = response.json()
        
        assert "recommendations" in data
        recommendations = data["recommendations"]
        
        # Check scores are present and in valid range
        for rec in recommendations:
            assert "score" in rec
            assert 0 <= rec["score"] <= 100
        
        # Verify descending order (highest score first)
        if len(recommendations) > 1:
            scores = [r["score"] for r in recommendations]
            assert scores == sorted(scores, reverse=True)
    
    def test_recommend_includes_usage_stats(self):
        """AC-6: Response includes usage_stats"""
        response = client.get("/api/v1/templates/recommend")
        data = response.json()
        
        for rec in data["recommendations"]:
            assert "usage_stats" in rec
            usage_stats = rec["usage_stats"]
            
            assert "applied_count" in usage_stats
            assert "success_rate" in usage_stats
            assert isinstance(usage_stats["applied_count"], int)
            assert 0.0 <= usage_stats["success_rate"] <= 1.0
    
    def test_recommend_includes_citations(self):
        """AC-7: Response includes citations"""
        response = client.get("/api/v1/templates/recommend")
        data = response.json()
        
        for rec in data["recommendations"]:
            assert "citations" in rec
            assert isinstance(rec["citations"], list)
    
    def test_recommend_pagination_support(self):
        """AC-8: Pagination support for large result sets"""
        response = client.get("/api/v1/templates/recommend?page=1&page_size=2")
        data = response.json()
        
        assert "page" in data
        assert "page_size" in data
        assert "total" in data
        
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["recommendations"]) <= 2
    
    def test_recommend_filters_by_persona(self):
        """AC-9: Persona filter actually filters results"""
        response = client.get("/api/v1/templates/recommend?persona=backend_developer")
        data = response.json()
        
        for rec in data["recommendations"]:
            assert rec["persona"] == "backend_developer"
    
    def test_recommend_filters_by_tag(self):
        """AC-10: Tag filter actually filters results"""
        response = client.get("/api/v1/templates/recommend?tag=auth")
        data = response.json()
        
        for rec in data["recommendations"]:
            assert "auth" in rec["tags"]
    
    def test_recommend_filters_by_min_score(self):
        """AC-11: Min score filter actually filters results"""
        min_score = 90
        response = client.get(f"/api/v1/templates/recommend?min_score={min_score}")
        data = response.json()
        
        for rec in data["recommendations"]:
            assert rec["score"] >= min_score
    
    def test_recommend_combined_filters(self):
        """AC-12: Multiple filters work together"""
        response = client.get(
            "/api/v1/templates/recommend?"
            "persona=backend_developer&tag=auth&min_score=85"
        )
        data = response.json()
        
        for rec in data["recommendations"]:
            assert rec["persona"] == "backend_developer"
            assert "auth" in rec["tags"]
            assert rec["score"] >= 85
    
    def test_recommend_response_structure(self):
        """AC-13: Response follows REST conventions"""
        response = client.get("/api/v1/templates/recommend")
        data = response.json()
        
        required_fields = ["recommendations", "total", "filters_applied", "page", "page_size"]
        for field in required_fields:
            assert field in data


class TestTemplatesHealthEndpoint:
    """Test suite for health check endpoint"""
    
    def test_health_endpoint(self):
        """Health endpoint is accessible"""
        response = client.get("/api/v1/templates/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "endpoints" in data


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_versions_invalid_limit(self):
        """Test invalid limit parameter"""
        response = client.get("/api/v1/templates/test/versions?limit=0")
        assert response.status_code == 422  # Validation error
    
    def test_versions_limit_too_large(self):
        """Test limit exceeding maximum"""
        response = client.get("/api/v1/templates/test/versions?limit=200")
        assert response.status_code == 422  # Validation error
    
    def test_recommend_invalid_page(self):
        """Test invalid page number"""
        response = client.get("/api/v1/templates/recommend?page=0")
        assert response.status_code == 422  # Validation error
    
    def test_recommend_page_size_too_large(self):
        """Test page_size exceeding maximum"""
        response = client.get("/api/v1/templates/recommend?page_size=100")
        assert response.status_code == 422  # Validation error
    
    def test_recommend_invalid_min_score(self):
        """Test min_score outside valid range"""
        response = client.get("/api/v1/templates/recommend?min_score=150")
        assert response.status_code == 422  # Validation error
    
    def test_recommend_negative_min_score(self):
        """Test negative min_score"""
        response = client.get("/api/v1/templates/recommend?min_score=-10")
        assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
