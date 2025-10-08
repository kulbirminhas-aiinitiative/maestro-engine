#!/usr/bin/env python3
"""
MAESTRO Templates Integration
Connects Quality-Fabric template creation to maestro-templates central registry
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from quality_fabric_client import QualityValidationResult
from templates.enterprise_template_repository.template_manager import TemplateMetadata

logger = logging.getLogger(__name__)


class MaestroTemplatesClient:
    """
    Client for maestro-templates central registry
    Integrates with the central registry service on port 9600
    """

    def __init__(
        self,
        registry_url: str = "http://localhost:9600",
        storage_path: str = "/home/ec2-user/projects/maestro-templates/storage/templates",
        timeout_seconds: int = 30,
    ):
        """
        Initialize maestro-templates client

        Args:
            registry_url: URL of central registry service
            storage_path: Path to template storage directory
            timeout_seconds: Request timeout
        """
        self.registry_url = registry_url
        self.storage_path = Path(storage_path)
        self.timeout_seconds = timeout_seconds
        self.client = httpx.AsyncClient(timeout=timeout_seconds)
        self.logger = logging.getLogger(self.__class__.__name__)

        # Ensure storage path exists
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def check_registry_health(self) -> bool:
        """Check if central registry is available"""
        try:
            response = await self.client.get(f"{self.registry_url}/health")
            if response.status_code == 200:
                self.logger.info("✅ Central registry is healthy")
                return True
            else:
                self.logger.warning(f"⚠️ Central registry returned {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"❌ Central registry health check failed: {e}")
            return False

    async def register_template_asset(
        self, template_metadata: TemplateMetadata, workflow_result: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Register template as an asset in central registry

        Args:
            template_metadata: Template metadata from Quality-Fabric
            workflow_result: Original workflow execution result

        Returns:
            Registration result or None on failure
        """
        try:
            # Build asset registration payload
            asset_payload = {
                "name": f"template_{template_metadata.name}",
                "type": "template",
                "provider": "quality_fabric",
                "config": {
                    "template_id": template_metadata.id,
                    "template_name": template_metadata.name,
                    "category": template_metadata.category,
                    "language": template_metadata.language,
                    "framework": template_metadata.framework,
                    "quality_score": template_metadata.quality_score,
                    "complexity": template_metadata.complexity.value,
                    "file_path": template_metadata.file_path,
                    "storage_path": str(self.storage_path / f"{template_metadata.id}.json"),
                    "created_at": template_metadata.created_at.isoformat(),
                    "tags": template_metadata.tags,
                },
                "shared": True,  # Templates are shared assets
            }

            # Store template file in storage
            await self._store_template_file(template_metadata, workflow_result)

            self.logger.info(f"Template asset registered: {template_metadata.name}")
            return asset_payload

        except Exception as e:
            self.logger.error(f"Failed to register template asset: {e}")
            return None

    async def _store_template_file(
        self, template_metadata: TemplateMetadata, workflow_result: Dict[str, Any]
    ):
        """Store template file in maestro-templates storage"""
        try:
            # Prepare template data
            template_data = {
                "metadata": template_metadata.to_dict(),
                "workflow_context": {
                    "session_id": workflow_result.get("session_id"),
                    "requirement": workflow_result.get("requirement"),
                    "team_members": workflow_result.get("team_members", []),
                    "execution_time": workflow_result.get("total_execution_time", 0),
                },
                "quality_validation": workflow_result.get("quality_validation"),
                "stored_at": datetime.now().isoformat(),
            }

            # Read actual file content if it exists
            source_file = Path(template_metadata.file_path)
            if source_file.exists():
                try:
                    with open(source_file, "r", encoding="utf-8") as f:
                        template_data["code_content"] = f.read()
                except Exception as e:
                    self.logger.warning(f"Could not read source file: {e}")

            # Write to storage
            storage_file = self.storage_path / f"{template_metadata.id}.json"
            with open(storage_file, "w", encoding="utf-8") as f:
                json.dump(template_data, f, indent=2, default=str)

            self.logger.info(f"Template stored: {storage_file}")

        except Exception as e:
            self.logger.error(f"Failed to store template file: {e}")
            raise

    async def query_templates(
        self,
        category: Optional[str] = None,
        language: Optional[str] = None,
        min_quality_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Query templates from storage

        Args:
            category: Filter by category
            language: Filter by language
            min_quality_score: Minimum quality score

        Returns:
            List of matching templates
        """
        try:
            matching_templates = []

            # Scan storage directory
            for template_file in self.storage_path.glob("*.json"):
                try:
                    with open(template_file, "r", encoding="utf-8") as f:
                        template_data = json.load(f)

                    metadata = template_data.get("metadata", {})

                    # Apply filters
                    if category and metadata.get("category") != category:
                        continue
                    if language and metadata.get("language") != language:
                        continue
                    if metadata.get("quality_score", 0) < min_quality_score:
                        continue

                    matching_templates.append(template_data)

                except Exception as e:
                    self.logger.warning(f"Error reading template {template_file}: {e}")

            self.logger.info(f"Found {len(matching_templates)} matching templates")
            return matching_templates

        except Exception as e:
            self.logger.error(f"Template query failed: {e}")
            return []

    async def get_template_by_id(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve specific template by ID"""
        try:
            template_file = self.storage_path / f"{template_id}.json"

            if not template_file.exists():
                self.logger.warning(f"Template not found: {template_id}")
                return None

            with open(template_file, "r", encoding="utf-8") as f:
                template_data = json.load(f)

            self.logger.info(f"Retrieved template: {template_id}")
            return template_data

        except Exception as e:
            self.logger.error(f"Failed to retrieve template: {e}")
            return None

    async def get_registry_stats(self) -> Optional[Dict[str, Any]]:
        """Get statistics from central registry"""
        try:
            if not await self.check_registry_health():
                return None

            response = await self.client.get(f"{self.registry_url}/api/v1/stats")

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.warning(f"Failed to get stats: {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"Stats query failed: {e}")
            return None

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


class MaestroTemplatesIntegration:
    """
    Integration layer connecting Quality-Fabric templates to maestro-templates
    """

    def __init__(
        self, templates_client: MaestroTemplatesClient = None, enable_registry: bool = True
    ):
        """
        Initialize integration

        Args:
            templates_client: Optional maestro-templates client
            enable_registry: Enable central registry integration
        """
        self.templates_client = templates_client or MaestroTemplatesClient()
        self.enable_registry = enable_registry
        self.logger = logging.getLogger(self.__class__.__name__)

    async def register_templates(
        self, template_metadata_list: List[TemplateMetadata], workflow_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Register multiple templates from workflow execution

        Args:
            template_metadata_list: List of template metadata objects
            workflow_result: Original workflow execution result

        Returns:
            Registration summary
        """
        result = {
            "templates_registered": 0,
            "templates_stored": 0,
            "registry_available": False,
            "template_ids": [],
            "errors": [],
        }

        try:
            # Check registry availability
            if self.enable_registry:
                result["registry_available"] = await self.templates_client.check_registry_health()

            # Process each template
            for template_metadata in template_metadata_list:
                try:
                    # Register template asset
                    asset_result = await self.templates_client.register_template_asset(
                        template_metadata, workflow_result
                    )

                    if asset_result:
                        result["templates_registered"] += 1
                        result["templates_stored"] += 1
                        result["template_ids"].append(template_metadata.id)

                        self.logger.info(
                            f"✅ Template registered: {template_metadata.name} "
                            f"(Quality: {template_metadata.quality_score:.1f})"
                        )

                except Exception as e:
                    error_msg = f"Failed to register template {template_metadata.name}: {e}"
                    self.logger.error(error_msg)
                    result["errors"].append(error_msg)

            # Log summary
            self.logger.info(
                f"Template registration complete: "
                f"{result['templates_registered']} registered, "
                f"{result['templates_stored']} stored"
            )

            return result

        except Exception as e:
            self.logger.error(f"Template registration failed: {e}")
            result["errors"].append(str(e))
            return result

    async def query_templates_for_rag(
        self,
        requirement: str,
        language: Optional[str] = None,
        category: Optional[str] = None,
        min_quality_score: float = 80.0,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Query templates for RAG retrieval based on requirement

        Args:
            requirement: User requirement to match against
            language: Filter by language
            category: Filter by category
            min_quality_score: Minimum quality score
            limit: Maximum number of results

        Returns:
            List of relevant templates
        """
        try:
            # Query templates with filters
            templates = await self.templates_client.query_templates(
                category=category, language=language, min_quality_score=min_quality_score
            )

            # TODO: Implement semantic matching with requirement
            # For now, return top N by quality score
            sorted_templates = sorted(
                templates, key=lambda t: t.get("metadata", {}).get("quality_score", 0), reverse=True
            )

            limited_templates = sorted_templates[:limit]

            self.logger.info(
                f"RAG query returned {len(limited_templates)} templates for: {requirement[:50]}..."
            )

            return limited_templates

        except Exception as e:
            self.logger.error(f"RAG template query failed: {e}")
            return []

    async def get_template_stats(self) -> Dict[str, Any]:
        """Get template repository statistics"""
        try:
            stats = {
                "total_templates": 0,
                "templates_by_language": {},
                "templates_by_category": {},
                "average_quality_score": 0.0,
                "registry_stats": None,
            }

            # Count templates in storage
            template_files = list(self.templates_client.storage_path.glob("*.json"))
            stats["total_templates"] = len(template_files)

            # Analyze templates
            quality_scores = []
            for template_file in template_files:
                try:
                    with open(template_file, "r", encoding="utf-8") as f:
                        template_data = json.load(f)

                    metadata = template_data.get("metadata", {})
                    language = metadata.get("language", "unknown")
                    category = metadata.get("category", "unknown")
                    quality_score = metadata.get("quality_score", 0)

                    stats["templates_by_language"][language] = (
                        stats["templates_by_language"].get(language, 0) + 1
                    )
                    stats["templates_by_category"][category] = (
                        stats["templates_by_category"].get(category, 0) + 1
                    )

                    if quality_score > 0:
                        quality_scores.append(quality_score)

                except Exception as e:
                    self.logger.warning(f"Error analyzing template {template_file}: {e}")

            # Calculate average quality
            if quality_scores:
                stats["average_quality_score"] = sum(quality_scores) / len(quality_scores)

            # Get registry stats if available
            if self.enable_registry:
                stats["registry_stats"] = await self.templates_client.get_registry_stats()

            return stats

        except Exception as e:
            self.logger.error(f"Failed to get template stats: {e}")
            return {"error": str(e)}


# Convenience functions
async def register_templates_to_maestro(
    template_metadata_list: List[TemplateMetadata], workflow_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convenience function to register templates to maestro-templates

    Args:
        template_metadata_list: List of template metadata
        workflow_result: Original workflow result

    Returns:
        Registration result
    """
    integration = MaestroTemplatesIntegration()
    try:
        return await integration.register_templates(template_metadata_list, workflow_result)
    finally:
        await integration.templates_client.close()


async def query_maestro_templates(
    requirement: str, language: Optional[str] = None, category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function to query templates for RAG

    Args:
        requirement: User requirement
        language: Optional language filter
        category: Optional category filter

    Returns:
        List of matching templates
    """
    integration = MaestroTemplatesIntegration()
    try:
        return await integration.query_templates_for_rag(
            requirement=requirement, language=language, category=category
        )
    finally:
        await integration.templates_client.close()
