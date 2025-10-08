"""
Example: Maestro Templates Integration with API Gateway

This file shows how maestro-templates service would integrate with the API Gateway
to communicate with other services (rag, quality-fabric, maestro-engine).

File Location (in maestro-templates repo): src/services/gateway_integration.py
"""

import asyncio
from typing import Dict, List, Optional

from src.gateway.client import GatewayClient


class TemplatesGatewayIntegration:
    """
    Maestro Templates service integration with API Gateway

    Uses gateway to communicate with:
    - RAG Service (semantic search, embeddings)
    - Quality Fabric (validate template quality)
    - Maestro Engine (sync template usage stats)
    """

    def __init__(self):
        self.gateway = GatewayClient(service_name="maestro-templates")

    # ========================================
    # RAG Service Integration
    # ========================================

    async def semantic_search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Semantic search using RAG embeddings

        Args:
            query: Search query
            limit: Max results

        Returns:
            List of semantically similar templates

        Example:
            results = await templates.semantic_search("authentication with JWT")
        """
        response = await self.gateway.call(
            service="rag",
            path="/api/search",
            method="POST",
            json={"query": query, "collection": "templates", "limit": limit},
        )

        if response.status_code == 200:
            return response.json().get("results", [])
        else:
            print(f"RAG search failed: {response.status_code}")
            return []

    async def index_template(self, template_id: str, content: str, metadata: Dict):
        """
        Add template to RAG index for semantic search

        Args:
            template_id: Unique template ID
            content: Template content + description
            metadata: Template metadata (category, language, etc.)
        """
        response = await self.gateway.call(
            service="rag",
            path="/api/documents",
            method="POST",
            json={
                "id": template_id,
                "content": content,
                "collection": "templates",
                "metadata": metadata,
            },
        )

        if response.status_code == 201:
            print(f"Template {template_id} indexed successfully")
            return True
        else:
            print(f"Template indexing failed: {response.status_code}")
            return False

    async def update_template_embedding(self, template_id: str, content: str):
        """Update template embedding in RAG index"""
        response = await self.gateway.call(
            service="rag",
            path=f"/api/documents/{template_id}",
            method="PUT",
            json={"content": content},
        )

        return response.status_code == 200

    async def delete_template_embedding(self, template_id: str):
        """Remove template from RAG index"""
        response = await self.gateway.call(
            service="rag", path=f"/api/documents/{template_id}", method="DELETE"
        )

        return response.status_code == 204

    # ========================================
    # Quality Fabric Integration
    # ========================================

    async def validate_template_quality(self, template_content: str, language: str) -> Dict:
        """
        Validate template quality using Quality Fabric

        Args:
            template_content: Template source code
            language: Programming language

        Returns:
            Quality validation results

        Example:
            results = await templates.validate_template_quality(code, "python")
        """
        response = await self.gateway.call(
            service="quality",
            path="/api/validate",
            method="POST",
            json={
                "code": template_content,
                "language": language,
                "checks": ["syntax", "security", "best_practices"],
            },
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {"valid": False, "errors": [f"Validation failed: {response.status_code}"]}

    async def run_template_tests(self, template_content: str, test_cases: List[Dict]) -> Dict:
        """
        Run tests on template using Quality Fabric

        Args:
            template_content: Template code
            test_cases: Test cases to run

        Returns:
            Test results
        """
        response = await self.gateway.call(
            service="quality",
            path="/api/test",
            method="POST",
            json={"code": template_content, "test_cases": test_cases, "auto_heal": False},
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {"passed": False, "results": []}

    async def get_quality_recommendations(self, template_id: str) -> List[str]:
        """Get quality improvement recommendations from Quality Fabric"""
        response = await self.gateway.call(
            service="quality", path=f"/api/recommendations/{template_id}", method="GET"
        )

        if response.status_code == 200:
            return response.json().get("recommendations", [])
        else:
            return []

    # ========================================
    # Maestro Engine Integration
    # ========================================

    async def report_template_usage(self, template_id: str, project_id: str, outcome: str):
        """
        Report template usage to maestro-engine

        Args:
            template_id: Template ID
            project_id: Project where template was used
            outcome: Usage outcome (success, modified, rejected)
        """
        response = await self.gateway.call(
            service="guardian",
            path="/api/templates/usage",
            method="POST",
            json={
                "template_id": template_id,
                "project_id": project_id,
                "outcome": outcome,
                "timestamp": "2025-10-04T10:30:00Z",
            },
        )

        return response.status_code == 200

    async def sync_template_stats(self, template_id: str, stats: Dict):
        """Sync template statistics to maestro-engine"""
        response = await self.gateway.call(
            service="guardian",
            path=f"/api/templates/{template_id}/stats",
            method="PUT",
            json=stats,
        )

        return response.status_code == 200

    async def get_template_recommendations(self, project_id: str) -> List[str]:
        """Get template recommendations from maestro-engine based on project context"""
        response = await self.gateway.call(
            service="guardian",
            path=f"/api/projects/{project_id}/template-recommendations",
            method="GET",
        )

        if response.status_code == 200:
            return response.json().get("template_ids", [])
        else:
            return []

    # ========================================
    # MCP Service Integration
    # ========================================

    async def get_mcp_context(self, session_id: str) -> Optional[Dict]:
        """Get MCP session context for template personalization"""
        response = await self.gateway.call(
            service="mcp", path=f"/api/sessions/{session_id}/context", method="GET"
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
    Example workflow showing how Templates Service uses gateway
    to coordinate with multiple services
    """
    templates = TemplatesGatewayIntegration()

    print("=== Maestro Templates Gateway Integration Example ===\n")

    # 1. Semantic search via RAG
    print("1. Semantic search for authentication templates...")
    results = await templates.semantic_search(query="JWT authentication with refresh tokens")
    print(f"   Found {len(results)} semantically similar templates\n")

    # 2. Index new template in RAG
    print("2. Indexing new template in RAG...")
    indexed = await templates.index_template(
        template_id="tmpl-auth-001",
        content="JWT authentication template with refresh token support",
        metadata={"category": "auth", "language": "python", "tags": ["jwt", "security"]},
    )
    print(f"   Indexed: {indexed}\n")

    # 3. Validate template quality
    print("3. Validating template quality...")
    template_code = """
def authenticate(username, password):
    # JWT authentication logic
    return generate_token(username)
    """
    validation = await templates.validate_template_quality(template_code, "python")
    print(f"   Valid: {validation.get('valid', False)}\n")

    # 4. Run template tests
    print("4. Running template tests...")
    test_results = await templates.run_template_tests(
        template_content=template_code,
        test_cases=[
            {"name": "test_auth_success", "input": {"username": "user", "password": "pass"}}
        ],
    )
    print(f"   Tests passed: {test_results.get('passed', False)}\n")

    # 5. Report usage to maestro-engine
    print("5. Reporting template usage...")
    reported = await templates.report_template_usage(
        template_id="tmpl-auth-001", project_id="proj-123", outcome="success"
    )
    print(f"   Usage reported: {reported}\n")

    # 6. Get recommendations from maestro-engine
    print("6. Getting template recommendations...")
    recommendations = await templates.get_template_recommendations(project_id="proj-123")
    print(f"   Recommended templates: {len(recommendations)}\n")

    # Cleanup
    await templates.gateway.close()


if __name__ == "__main__":
    # Run example
    asyncio.run(example_workflow())
