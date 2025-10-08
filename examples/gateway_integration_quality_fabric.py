"""
Example: Quality Fabric Integration with API Gateway

This file shows how quality-fabric service would integrate with the API Gateway
to communicate with other services (templates, rag, maestro-engine).

File Location (in quality-fabric repo): src/services/gateway_integration.py
"""

import asyncio
from typing import Dict, List, Optional

from src.gateway.client import GatewayClient


class QualityFabricGatewayIntegration:
    """
    Quality Fabric service integration with API Gateway

    Uses gateway to communicate with:
    - Templates Service (search for test templates)
    - RAG Service (semantic search for quality patterns)
    - Maestro Engine (report quality scores)
    """

    def __init__(self):
        self.gateway = GatewayClient(service_name="quality-fabric")

    # ========================================
    # Templates Service Integration
    # ========================================

    async def search_test_templates(self, query: str, language: str = "python") -> List[Dict]:
        """
        Search for test templates from maestro-templates service

        Args:
            query: Search query (e.g., "unit test", "integration test")
            language: Programming language

        Returns:
            List of test templates

        Example:
            templates = await qf.search_test_templates("api testing", "python")
        """
        response = await self.gateway.call(
            service="templates",
            path="/api/search",
            method="POST",
            json={"query": query, "category": "test", "language": language, "limit": 10},
        )

        if response.status_code == 200:
            return response.json().get("templates", [])
        else:
            print(f"Template search failed: {response.status_code}")
            return []

    async def get_template_details(self, template_id: str) -> Optional[Dict]:
        """Get template details from templates service"""
        response = await self.gateway.call(
            service="templates", path=f"/api/templates/{template_id}", method="GET"
        )

        if response.status_code == 200:
            return response.json()
        else:
            return None

    async def submit_template(self, template_data: Dict) -> Optional[str]:
        """
        Submit a new test template to templates service

        Args:
            template_data: Template metadata and content

        Returns:
            Template ID if successful
        """
        response = await self.gateway.call(
            service="templates", path="/api/templates", method="POST", json=template_data
        )

        if response.status_code == 201:
            return response.json().get("id")
        else:
            print(f"Template submission failed: {response.status_code}")
            return None

    # ========================================
    # RAG Service Integration
    # ========================================

    async def search_quality_patterns(self, query: str) -> List[Dict]:
        """
        Search for quality patterns using RAG semantic search

        Args:
            query: Search query (e.g., "error handling best practices")

        Returns:
            List of relevant quality patterns

        Example:
            patterns = await qf.search_quality_patterns("exception handling")
        """
        response = await self.gateway.call(
            service="rag",
            path="/api/search",
            method="POST",
            json={"query": query, "collection": "quality_patterns", "limit": 5},
        )

        if response.status_code == 200:
            return response.json().get("results", [])
        else:
            return []

    async def add_quality_pattern(self, pattern_id: str, content: str, metadata: Dict):
        """Add quality pattern to RAG index"""
        response = await self.gateway.call(
            service="rag",
            path="/api/documents",
            method="POST",
            json={
                "id": pattern_id,
                "content": content,
                "collection": "quality_patterns",
                "metadata": metadata,
            },
        )

        return response.status_code == 201

    # ========================================
    # Maestro Engine Integration
    # ========================================

    async def report_quality_score(self, project_id: str, score: float, details: Dict):
        """
        Report quality score to maestro-engine

        Args:
            project_id: Project ID
            score: Quality score (0.0 - 1.0)
            details: Detailed quality metrics
        """
        response = await self.gateway.call(
            service="guardian",
            path=f"/api/projects/{project_id}/quality",
            method="POST",
            json={"score": score, "details": details, "source": "quality-fabric"},
        )

        return response.status_code == 200

    async def get_project_info(self, project_id: str) -> Optional[Dict]:
        """Get project information from maestro-engine"""
        response = await self.gateway.call(
            service="guardian", path=f"/api/projects/{project_id}", method="GET"
        )

        if response.status_code == 200:
            return response.json()
        else:
            return None


# ========================================
# Example Usage
# ========================================


async def example_workflow():
    """
    Example workflow showing how Quality Fabric uses gateway
    to coordinate with multiple services
    """
    qf = QualityFabricGatewayIntegration()

    print("=== Quality Fabric Gateway Integration Example ===\n")

    # 1. Search for test templates
    print("1. Searching for API test templates...")
    templates = await qf.search_test_templates(query="api testing", language="python")
    print(f"   Found {len(templates)} templates\n")

    # 2. Search for quality patterns
    print("2. Searching for error handling patterns...")
    patterns = await qf.search_quality_patterns(query="error handling best practices")
    print(f"   Found {len(patterns)} quality patterns\n")

    # 3. Submit new template
    print("3. Submitting new test template...")
    template_id = await qf.submit_template(
        {
            "name": "API Authentication Test",
            "category": "test",
            "language": "python",
            "content": "def test_auth(): ...",
        }
    )
    print(f"   Template ID: {template_id}\n")

    # 4. Report quality score to maestro-engine
    print("4. Reporting quality score...")
    success = await qf.report_quality_score(
        project_id="proj-123",
        score=0.92,
        details={
            "test_coverage": 0.95,
            "code_quality": 0.88,
            "security_score": 0.93,
        },
    )
    print(f"   Score reported: {success}\n")

    # Cleanup
    await qf.gateway.close()


if __name__ == "__main__":
    # Run example
    asyncio.run(example_workflow())
