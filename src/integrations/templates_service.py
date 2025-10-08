"""
Templates Service Integration

Uses API Gateway to communicate with maestro-templates service.
Replaces direct HTTP calls to http://localhost:9600

Usage:
    from src.integrations.templates_service import templates_service

    # Search templates
    templates = await templates_service.search_templates("authentication")

    # Get template
    template = await templates_service.get_template("tmpl-123")
"""

import logging
from typing import Dict, List, Optional

from src.gateway_client import gateway_client

logger = logging.getLogger(__name__)


class TemplatesService:
    """
    Interface to maestro-templates service via API Gateway

    Replaces MaestroTemplatesIntegration and direct HTTP calls
    """

    def __init__(self):
        self.gateway = gateway_client

    async def search_templates(
        self,
        query: str,
        category: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """
        Search for templates

        Args:
            query: Search query
            category: Template category (e.g., "web", "api", "test")
            language: Programming language (e.g., "python", "javascript")
            limit: Maximum number of results

        Returns:
            List of matching templates
        """
        try:
            # Use actual templates service endpoint: /api/v1/templates/search (GET with params)
            params = {"query": query, "page_size": limit}
            if category:
                params["category"] = category
            if language:
                params["language"] = language

            response = await self.gateway.call(
                service="templates",
                path="/api/v1/templates/search",
                method="GET",
                params=params,
            )

            if response.status_code == 200:
                return response.json().get("templates", [])
            else:
                logger.warning(f"Template search failed: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Template search error: {e}")
            return []

    async def get_template(self, template_id: str) -> Optional[Dict]:
        """
        Get template by ID

        Args:
            template_id: Template ID

        Returns:
            Template details or None if not found
        """
        try:
            # Use actual templates service endpoint: /api/v1/templates/{id}
            response = await self.gateway.call(
                service="templates", path=f"/api/v1/templates/{template_id}", method="GET"
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.warning(f"Template not found: {template_id}")
                return None
            else:
                logger.warning(f"Template fetch failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Template fetch error: {e}")
            return None

    async def get_template_by_category(self, category: str) -> List[Dict]:
        """
        Get all templates in a category

        Args:
            category: Template category

        Returns:
            List of templates
        """
        try:
            # Use actual templates service endpoint: /api/v1/templates with params
            response = await self.gateway.call(
                service="templates",
                path="/api/v1/templates",
                method="GET",
                params={"category": category},
            )

            if response.status_code == 200:
                return response.json().get("templates", [])
            else:
                return []

        except Exception as e:
            logger.error(f"Template category fetch error: {e}")
            return []

    async def create_template(self, template_data: Dict) -> Optional[str]:
        """
        Create a new template

        Args:
            template_data: Template data (name, content, category, etc.)

        Returns:
            Template ID if successful, None otherwise
        """
        try:
            # Use actual templates service endpoint: /api/v1/templates (POST)
            response = await self.gateway.call(
                service="templates", path="/api/v1/templates", method="POST", json=template_data
            )

            if response.status_code in (200, 201):
                return response.json().get("id", response.json().get("template_id"))
            else:
                logger.warning(f"Template creation failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Template creation error: {e}")
            return None

    async def update_template(self, template_id: str, updates: Dict) -> bool:
        """
        Update template

        Args:
            template_id: Template ID
            updates: Fields to update

        Returns:
            True if successful
        """
        try:
            # Use actual templates service endpoint: /api/v1/templates/{id}
            response = await self.gateway.call(
                service="templates",
                path=f"/api/v1/templates/{template_id}",
                method="PUT",
                json=updates,
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"Template update error: {e}")
            return False

    async def get_template_recommendations(
        self, project_context: Dict, limit: int = 5
    ) -> List[Dict]:
        """
        Get template recommendations based on project context

        Args:
            project_context: Project context (type, tech stack, etc.)
            limit: Maximum number of recommendations

        Returns:
            List of recommended templates
        """
        try:
            response = await self.gateway.call(
                service="templates",
                path="/api/recommendations",
                method="POST",
                json={"context": project_context, "limit": limit},
            )

            if response.status_code == 200:
                return response.json().get("recommendations", [])
            else:
                return []

        except Exception as e:
            logger.error(f"Template recommendations error: {e}")
            return []

    def search_templates_sync(self, query: str, category: Optional[str] = None) -> List[Dict]:
        """Synchronous version of search_templates"""
        try:
            # Use actual templates service endpoint: /api/v1/templates/search (GET with params)
            params = {"query": query}
            if category:
                params["category"] = category

            response = self.gateway.call_sync(
                service="templates",
                path="/api/v1/templates/search",
                method="GET",
                params=params,
            )

            if response.status_code == 200:
                return response.json().get("templates", [])
            else:
                return []

        except Exception as e:
            logger.error(f"Template search error: {e}")
            return []


# Singleton instance
templates_service = TemplatesService()
