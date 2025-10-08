#!/usr/bin/env python3
"""
Vector RAG Manager for MAESTRO Engine
Manages vector storage and similarity search using ChromaDB
"""

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .chroma_client import CHROMADB_AVAILABLE, get_chroma_client

logger = logging.getLogger(__name__)


class VectorRAGManager:
    """
    Manages vector storage and retrieval for RAG queries

    Collections:
    - executions: Historical workflow executions with requirements
    - collaterals: Individual files (code, docs, configs)
    - patterns: Successful patterns and best practices
    """

    def __init__(self, chroma_client=None):
        """Initialize RAG manager with ChromaDB client"""
        self.client = chroma_client or get_chroma_client()

        if self.client is None:
            logger.warning("ChromaDB not available - RAG features disabled")
            self.enabled = False
            return

        self.enabled = True

        # Get or create collections
        try:
            self.executions_collection = self.client.get_or_create_collection(
                name="executions", metadata={"description": "Historical workflow executions"}
            )
            self.collaterals_collection = self.client.get_or_create_collection(
                name="collaterals", metadata={"description": "Code files, docs, configs"}
            )
            self.patterns_collection = self.client.get_or_create_collection(
                name="patterns", metadata={"description": "Successful patterns and templates"}
            )
            logger.info("✅ RAG collections initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize RAG collections: {e}")
            self.enabled = False

    def index_execution(
        self,
        session_id: str,
        requirement: str,
        personas: List[str],
        collaterals: List[Dict[str, Any]],
        quality_score: Optional[float] = None,
        success: bool = True,
    ) -> bool:
        """
        Index a workflow execution for future RAG queries

        Args:
            session_id: Unique session ID
            requirement: User requirement text
            personas: List of personas executed
            collaterals: List of generated files/documents
            quality_score: Optional quality score (0-1)
            success: Whether execution was successful

        Returns:
            True if indexed successfully
        """
        if not self.enabled:
            return False

        try:
            # Generate document ID
            doc_id = f"exec-{session_id}"

            # Metadata
            metadata = {
                "session_id": session_id,
                "requirement": requirement[:500],  # Truncate for metadata
                "team_members": ",".join(personas),
                "total_files": len(collaterals),
                "quality_score": quality_score or 0.0,
                "success": success,
                "indexed_at": datetime.now().isoformat(),
            }

            # Add to collection
            self.executions_collection.add(
                documents=[requirement], metadatas=[metadata], ids=[doc_id]
            )

            logger.info(f"✅ Indexed execution: {session_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to index execution: {e}")
            return False

    def search_similar_executions(
        self, requirement: str, top_k: int = 3, min_quality: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search for similar historical executions

        Args:
            requirement: User requirement to search for
            top_k: Number of similar executions to return
            min_quality: Minimum quality score filter

        Returns:
            List of similar executions with metadata
        """
        if not self.enabled:
            return []

        try:
            # Query ChromaDB
            results = self.executions_collection.query(
                query_texts=[requirement],
                n_results=top_k * 2,  # Get more for filtering
                include=["metadatas", "distances", "documents"],
            )

            # Extract and format results
            similar_executions = []

            if results and "ids" in results and results["ids"]:
                for i, exec_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i]
                    distance = results["distances"][0][i]

                    # Convert distance to similarity score (0-1)
                    similarity = 1.0 / (1.0 + distance)

                    # Filter by quality if specified
                    if metadata.get("quality_score", 0) < min_quality:
                        continue

                    similar_executions.append(
                        {
                            "execution_id": exec_id,
                            "similarity": similarity,
                            "distance": distance,
                            "metadata": metadata,
                            "requirement": results["documents"][0][i],
                        }
                    )

            # Sort by similarity and limit
            similar_executions = sorted(
                similar_executions, key=lambda x: x["similarity"], reverse=True
            )[:top_k]

            logger.info(f"🔍 Found {len(similar_executions)} similar executions")
            return similar_executions

        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return []

    def index_template(self, content: str, metadata: Dict[str, Any]) -> bool:
        """
        Index a template/collateral for future retrieval

        Args:
            content: Template content
            metadata: Template metadata (persona, file_type, tags, etc.)

        Returns:
            True if indexed successfully
        """
        if not self.enabled:
            return False

        try:
            # Generate template ID from content hash
            content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
            template_id = f"template-{metadata.get('persona', 'unknown')}-{content_hash}"

            # Add indexed timestamp
            metadata["indexed_at"] = datetime.now().isoformat()

            # Add to collaterals collection
            self.collaterals_collection.add(
                documents=[content[:1000]],  # First 1000 chars for embedding
                metadatas=[metadata],
                ids=[template_id],
            )

            logger.debug(f"✅ Indexed template: {template_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to index template: {e}")
            return False

    def search_templates(
        self,
        requirement: str,
        persona_id: Optional[str] = None,
        domain_tags: Optional[List[str]] = None,
        template_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant templates

        Args:
            requirement: User requirement or query
            persona_id: Filter by persona
            domain_tags: Filter by domain tags (e.g., ["react", "typescript"])
            template_type: Filter by template type
            top_k: Number of templates to return

        Returns:
            List of relevant templates
        """
        if not self.enabled:
            return []

        try:
            # Build where filter
            where = {}
            if persona_id:
                where["persona"] = persona_id

            # Query
            results = self.collaterals_collection.query(
                query_texts=[requirement],
                n_results=top_k,
                where=where if where else None,
                include=["metadatas", "distances", "documents"],
            )

            # Format results
            templates = []

            if results and "ids" in results and results["ids"]:
                for i, template_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i]
                    distance = results["distances"][0][i]
                    similarity = 1.0 / (1.0 + distance)

                    # Filter by tags if specified
                    if domain_tags:
                        template_tags = metadata.get("tags", "").split(",")
                        if not any(tag in template_tags for tag in domain_tags):
                            continue

                    templates.append(
                        {
                            "template_id": template_id,
                            "similarity": similarity,
                            "metadata": metadata,
                            "content_preview": results["documents"][0][i][:200],
                        }
                    )

            logger.info(f"🔍 Found {len(templates)} relevant templates")
            return templates

        except Exception as e:
            logger.error(f"❌ Template search failed: {e}")
            return []

    def search_patterns(
        self, persona_id: str, task: str, success_only: bool = True, top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Search for proven patterns for a persona's task

        Args:
            persona_id: Persona ID
            task: Task description
            success_only: Only return successful patterns
            top_k: Number of patterns to return

        Returns:
            List of relevant patterns
        """
        if not self.enabled:
            return []

        try:
            where = {"persona": persona_id}
            if success_only:
                where["success"] = True

            results = self.patterns_collection.query(
                query_texts=[task],
                n_results=top_k,
                where=where,
                include=["metadatas", "distances", "documents"],
            )

            patterns = []

            if results and "ids" in results and results["ids"]:
                for i, pattern_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i]
                    distance = results["distances"][0][i]
                    similarity = 1.0 / (1.0 + distance)

                    patterns.append(
                        {
                            "pattern_id": pattern_id,
                            "similarity": similarity,
                            "metadata": metadata,
                            "pattern_description": results["documents"][0][i],
                        }
                    )

            logger.info(f"🔍 Found {len(patterns)} relevant patterns")
            return patterns

        except Exception as e:
            logger.error(f"❌ Pattern search failed: {e}")
            return []

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about RAG collections"""
        if not self.enabled:
            return {"enabled": False, "error": "ChromaDB not available"}

        try:
            stats = {
                "enabled": True,
                "executions": {"count": self.executions_collection.count()},
                "collaterals": {"count": self.collaterals_collection.count()},
                "patterns": {"count": self.patterns_collection.count()},
            }

            return stats

        except Exception as e:
            logger.error(f"❌ Failed to get stats: {e}")
            return {"enabled": False, "error": str(e)}


# Global RAG manager instance
_rag_manager: Optional[VectorRAGManager] = None


def get_rag_manager() -> VectorRAGManager:
    """Get singleton RAG manager instance"""
    global _rag_manager

    if _rag_manager is None:
        _rag_manager = VectorRAGManager()

    return _rag_manager
