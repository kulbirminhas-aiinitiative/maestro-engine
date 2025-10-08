"""
MAESTRO Enterprise Template Repository - Semantic Search Engine
Version: 1.0
Purpose: AI-powered semantic search with ChromaDB for intelligent template discovery
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import chromadb
import numpy as np
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from template_manager import EnterpriseTemplateRepository, TemplateSearchQuery

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SemanticSearchResult:
    """Semantic search result with similarity score"""

    template_id: str
    template_name: str
    similarity_score: float
    metadata: Dict[str, Any]
    content_snippet: str


class TemplateSemanticSearch:
    """
    AI-powered semantic search for template repository

    Features:
    - ChromaDB vector database integration
    - Sentence transformer embeddings
    - Multi-modal search (semantic + metadata)
    - Real-time embedding generation
    - Similarity scoring and ranking
    """

    def __init__(
        self,
        repository: EnterpriseTemplateRepository,
        chroma_path: str = "/data/maestro-v1/enterprise_template_repository/chroma_db",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        self.repository = repository
        self.chroma_path = chroma_path
        self.embedding_model_name = embedding_model

        # Initialize embedding model
        logger.info(f"🔄 Loading embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        logger.info(f"✅ Embedding model loaded")

        # Initialize ChromaDB
        self.chroma_client = None
        self.collection = None
        self.collection_name = "maestro_templates"

    async def initialize(self):
        """Initialize ChromaDB connection and collections"""
        try:
            # Initialize ChromaDB client
            self.chroma_client = chromadb.PersistentClient(
                path=self.chroma_path,
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )

            # Get or create collection
            try:
                self.collection = self.chroma_client.get_collection(
                    name=self.collection_name,
                    embedding_function=chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
                        model_name=self.embedding_model_name
                    ),
                )
                logger.info(f"✅ Connected to existing ChromaDB collection: {self.collection_name}")
            except Exception:
                self.collection = self.chroma_client.create_collection(
                    name=self.collection_name,
                    embedding_function=chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
                        model_name=self.embedding_model_name
                    ),
                    metadata={"description": "MAESTRO enterprise template embeddings"},
                )
                logger.info(f"✅ Created new ChromaDB collection: {self.collection_name}")

            # Check collection stats
            count = self.collection.count()
            logger.info(f"📊 ChromaDB collection stats: {count} embeddings")

        except Exception as e:
            logger.error(f"❌ Failed to initialize ChromaDB: {e}")
            raise

    async def add_template_embedding(
        self, template_id: str, template_data: Dict[str, Any], content: str
    ) -> str:
        """
        Add template embedding to vector database

        Args:
            template_id: Template UUID
            template_data: Template metadata
            content: Template source code content

        Returns:
            Vector ID
        """
        try:
            # Create searchable text combining metadata and content
            searchable_text = await self._create_searchable_text(template_data, content)

            # Generate embedding
            embedding = self.embedding_model.encode(searchable_text).tolist()

            # Prepare metadata for ChromaDB
            chroma_metadata = {
                "template_id": template_id,
                "name": template_data.get("name", ""),
                "category": template_data.get("category", ""),
                "language": template_data.get("language", ""),
                "framework": template_data.get("framework", ""),
                "domain": template_data.get("domain", ""),
                "pattern": template_data.get("pattern", ""),
                "complexity": template_data.get("complexity_level", ""),
                "quality_score": float(template_data.get("quality_score", 0)),
                "tags": json.dumps(template_data.get("tags", [])),
                "description": template_data.get("description", "")[:500],  # Truncate for storage
                "created_at": template_data.get("created_at", ""),
                "popularity": template_data.get("popularity", ""),
                "usage_count": int(template_data.get("usage_count", 0)),
            }

            # Generate vector ID
            vector_id = f"tpl_{template_id}_{int(datetime.now().timestamp())}"

            # Add to ChromaDB
            self.collection.add(
                embeddings=[embedding],
                documents=[searchable_text],
                metadatas=[chroma_metadata],
                ids=[vector_id],
            )

            # Update template record with vector_id
            await self._update_template_vector_id(template_id, vector_id)

            logger.info(f"✅ Added embedding for template {template_id}: {vector_id}")
            return vector_id

        except Exception as e:
            logger.error(f"❌ Failed to add template embedding: {e}")
            raise

    async def semantic_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        min_similarity: float = 0.0,
    ) -> List[SemanticSearchResult]:
        """
        Perform semantic search for templates

        Args:
            query: Natural language search query
            filters: Metadata filters (language, framework, domain, etc.)
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold

        Returns:
            List of semantic search results
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query).tolist()

            # Build ChromaDB where clause for filters
            where_clause = {}
            if filters:
                for key, value in filters.items():
                    if key in ["language", "framework", "domain", "category", "complexity"]:
                        if isinstance(value, list):
                            # For list values, we'll need to search individually
                            continue
                        else:
                            where_clause[key] = value
                    elif key == "quality_min":
                        where_clause["quality_score"] = {"$gte": float(value)}
                    elif key == "tags":
                        # Tags are stored as JSON strings, need special handling
                        continue

            # Perform semantic search
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(limit * 2, 50),  # Get extra results for filtering
                where=where_clause if where_clause else None,
                include=["embeddings", "documents", "metadatas", "distances"],
            )

            # Process results
            search_results = []
            if results["ids"] and results["ids"][0]:
                for i, (template_id, distance, metadata, document) in enumerate(
                    zip(
                        results["ids"][0],
                        results["distances"][0],
                        results["metadatas"][0],
                        results["documents"][0],
                    )
                ):
                    # Convert distance to similarity score (1 - normalized distance)
                    similarity_score = max(0, 1 - distance)

                    # Apply minimum similarity threshold
                    if similarity_score < min_similarity:
                        continue

                    # Apply additional filters not handled by ChromaDB
                    if not await self._passes_additional_filters(metadata, filters):
                        continue

                    # Create search result
                    search_result = SemanticSearchResult(
                        template_id=metadata["template_id"],
                        template_name=metadata["name"],
                        similarity_score=similarity_score,
                        metadata=metadata,
                        content_snippet=document[:200] + "..." if len(document) > 200 else document,
                    )
                    search_results.append(search_result)

                    # Stop when we have enough results
                    if len(search_results) >= limit:
                        break

            logger.info(f"🔍 Semantic search for '{query}': {len(search_results)} results")
            return search_results

        except Exception as e:
            logger.error(f"❌ Semantic search failed: {e}")
            return []

    async def hybrid_search(self, search_query: TemplateSearchQuery) -> List[Dict[str, Any]]:
        """
        Hybrid search combining semantic search with metadata filtering

        Args:
            search_query: Comprehensive search query

        Returns:
            Combined and ranked search results
        """
        try:
            results = []

            if search_query.query and search_query.semantic_search:
                # Perform semantic search
                semantic_filters = {
                    "language": search_query.language[0] if search_query.language else None,
                    "framework": search_query.framework[0] if search_query.framework else None,
                    "domain": search_query.domain[0] if search_query.domain else None,
                    "category": search_query.category[0] if search_query.category else None,
                    "quality_min": search_query.quality_min,
                }

                semantic_results = await self.semantic_search(
                    search_query.query,
                    semantic_filters,
                    search_query.limit * 2,  # Get more results for hybrid ranking
                )

                # Convert to template data
                for result in semantic_results:
                    template_data = await self.repository.get_template(result.template_id)
                    if template_data:
                        template_data["semantic_similarity"] = result.similarity_score
                        template_data["search_score"] = result.similarity_score * 100
                        results.append(template_data)

            # Perform traditional metadata search
            metadata_results = await self.repository.search_templates(search_query)

            # Combine results and remove duplicates
            combined_results = {}

            # Add semantic results with higher weight
            for result in results:
                template_id = result["id"]
                result["hybrid_score"] = (
                    result.get("search_score", 0) * 0.7
                )  # 70% weight for semantic
                combined_results[template_id] = result

            # Add metadata results with lower weight
            for result in metadata_results:
                template_id = result["id"]
                if template_id in combined_results:
                    # Boost score for results found in both
                    combined_results[template_id]["hybrid_score"] += 30  # Boost for metadata match
                else:
                    result["hybrid_score"] = (
                        result.get("quality_score", 0) * 0.3
                    )  # 30% weight for metadata only
                    result["search_score"] = result.get("quality_score", 0)
                    combined_results[template_id] = result

            # Sort by hybrid score
            final_results = list(combined_results.values())
            final_results.sort(key=lambda x: x.get("hybrid_score", 0), reverse=True)

            # Apply limit
            final_results = final_results[: search_query.limit]

            logger.info(
                f"🔍 Hybrid search: {len(final_results)} results (semantic: {len(results)}, metadata: {len(metadata_results)})"
            )
            return final_results

        except Exception as e:
            logger.error(f"❌ Hybrid search failed: {e}")
            return []

    async def find_similar_templates(
        self, template_id: str, limit: int = 5, min_similarity: float = 0.3
    ) -> List[SemanticSearchResult]:
        """
        Find templates similar to a given template

        Args:
            template_id: Reference template ID
            limit: Maximum number of similar templates
            min_similarity: Minimum similarity threshold

        Returns:
            List of similar templates
        """
        try:
            # Get the reference template
            template_data = await self.repository.get_template(template_id)
            if not template_data:
                logger.warning(f"⚠️ Template not found: {template_id}")
                return []

            # Create query from template characteristics
            query_parts = [
                template_data.get("name", ""),
                template_data.get("description", ""),
                template_data.get("language", ""),
                template_data.get("framework", ""),
                template_data.get("domain", ""),
            ]

            # Add tags
            if template_data.get("tags"):
                query_parts.extend(template_data["tags"])

            search_query = " ".join(filter(None, query_parts))

            # Perform semantic search
            filters = {
                "language": template_data.get("language"),
                "framework": template_data.get("framework"),
                "domain": template_data.get("domain"),
            }

            results = await self.semantic_search(
                search_query, filters, limit + 1, min_similarity  # Get one extra to exclude self
            )

            # Remove the original template from results
            similar_templates = [r for r in results if r.template_id != template_id][:limit]

            logger.info(f"🔍 Found {len(similar_templates)} similar templates for {template_id}")
            return similar_templates

        except Exception as e:
            logger.error(f"❌ Failed to find similar templates: {e}")
            return []

    async def get_recommendations(
        self, user_context: Dict[str, Any], limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get template recommendations based on user context

        Args:
            user_context: User preferences and history
            limit: Maximum number of recommendations

        Returns:
            List of recommended templates
        """
        try:
            # Build recommendation query from user context
            query_parts = []

            # Add user preferences
            if user_context.get("preferred_language"):
                query_parts.append(user_context["preferred_language"])
            if user_context.get("preferred_framework"):
                query_parts.append(user_context["preferred_framework"])
            if user_context.get("current_project_type"):
                query_parts.append(user_context["current_project_type"])
            if user_context.get("working_domain"):
                query_parts.append(user_context["working_domain"])

            # Add recent interests
            if user_context.get("recent_searches"):
                query_parts.extend(user_context["recent_searches"][-3:])  # Last 3 searches

            recommendation_query = " ".join(query_parts)

            if not recommendation_query:
                # Fallback to popular templates
                return await self._get_popular_templates(limit)

            # Perform semantic search for recommendations
            filters = {
                "language": user_context.get("preferred_language"),
                "framework": user_context.get("preferred_framework"),
                "domain": user_context.get("working_domain"),
                "quality_min": 80.0,  # Only recommend high-quality templates
            }

            semantic_results = await self.semantic_search(recommendation_query, filters, limit)

            # Get full template data
            recommendations = []
            for result in semantic_results:
                template_data = await self.repository.get_template(result.template_id)
                if template_data:
                    template_data["recommendation_score"] = result.similarity_score
                    template_data["recommendation_reason"] = (
                        await self._generate_recommendation_reason(
                            template_data, user_context, result.similarity_score
                        )
                    )
                    recommendations.append(template_data)

            logger.info(f"💡 Generated {len(recommendations)} recommendations")
            return recommendations

        except Exception as e:
            logger.error(f"❌ Failed to generate recommendations: {e}")
            return await self._get_popular_templates(limit)

    async def update_embeddings_batch(self, batch_size: int = 100):
        """Update embeddings for templates that don't have them"""
        try:
            # Get templates without embeddings
            async with self.repository.db_pool.acquire() as conn:
                templates = await conn.fetch(
                    """
                    SELECT id, name, description, language, framework, domain, tags
                    FROM templates
                    WHERE vector_id IS NULL OR vector_id = ''
                    LIMIT $1
                """,
                    batch_size,
                )

            logger.info(f"🔄 Updating embeddings for {len(templates)} templates")

            for template_row in templates:
                template_data = dict(template_row)

                # Get template content
                template_full = await self.repository.get_template(template_data["id"])
                if template_full and template_full.get("content"):
                    try:
                        vector_id = await self.add_template_embedding(
                            template_data["id"], template_data, template_full["content"]
                        )
                        logger.info(
                            f"✅ Updated embedding for {template_data['name']}: {vector_id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"❌ Failed to update embedding for {template_data['id']}: {e}"
                        )

            logger.info("✅ Batch embedding update completed")

        except Exception as e:
            logger.error(f"❌ Batch embedding update failed: {e}")

    async def _create_searchable_text(self, template_data: Dict[str, Any], content: str) -> str:
        """Create searchable text combining metadata and content"""
        parts = [
            template_data.get("name", ""),
            template_data.get("description", ""),
            template_data.get("language", ""),
            template_data.get("framework", ""),
            template_data.get("domain", ""),
            template_data.get("pattern", ""),
            template_data.get("category", ""),
        ]

        # Add tags
        if template_data.get("tags"):
            parts.extend(template_data["tags"])

        # Add content (first 1000 chars to avoid too large embeddings)
        if content:
            parts.append(content[:1000])

        return " ".join(filter(None, parts))

    async def _passes_additional_filters(
        self, metadata: Dict[str, Any], filters: Optional[Dict[str, Any]]
    ) -> bool:
        """Check if result passes additional filters not handled by ChromaDB"""
        if not filters:
            return True

        # Handle list filters
        if filters.get("language") and isinstance(filters["language"], list):
            if metadata.get("language") not in filters["language"]:
                return False

        if filters.get("framework") and isinstance(filters["framework"], list):
            if metadata.get("framework") not in filters["framework"]:
                return False

        if filters.get("domain") and isinstance(filters["domain"], list):
            if metadata.get("domain") not in filters["domain"]:
                return False

        # Handle tag filters
        if filters.get("tags"):
            template_tags = json.loads(metadata.get("tags", "[]"))
            if not any(tag in template_tags for tag in filters["tags"]):
                return False

        return True

    async def _update_template_vector_id(self, template_id: str, vector_id: str):
        """Update template record with vector ID"""
        async with self.repository.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE templates SET vector_id = $2 WHERE id = $1", template_id, vector_id
            )

    async def _get_popular_templates(self, limit: int) -> List[Dict[str, Any]]:
        """Get popular templates as fallback recommendations"""
        async with self.repository.db_pool.acquire() as conn:
            templates = await conn.fetch(
                """
                SELECT * FROM templates
                WHERE status = 'approved' AND quality_score > 80
                ORDER BY usage_count DESC, quality_score DESC
                LIMIT $1
            """,
                limit,
            )

        recommendations = []
        for template_row in templates:
            template_data = dict(template_row)
            # Convert timestamps
            for date_field in ["created_at", "updated_at", "approved_at", "last_accessed_at"]:
                if template_data.get(date_field):
                    template_data[date_field] = template_data[date_field].isoformat()

            template_data["recommendation_score"] = template_data.get("usage_count", 0) / 100.0
            template_data["recommendation_reason"] = "Popular template with high usage"
            recommendations.append(template_data)

        return recommendations

    async def _generate_recommendation_reason(
        self, template_data: Dict[str, Any], user_context: Dict[str, Any], similarity_score: float
    ) -> str:
        """Generate explanation for why template was recommended"""
        reasons = []

        # Match reasons
        if template_data.get("language") == user_context.get("preferred_language"):
            reasons.append(f"matches your preferred language ({template_data['language']})")

        if template_data.get("framework") == user_context.get("preferred_framework"):
            reasons.append(f"uses your preferred framework ({template_data['framework']})")

        if template_data.get("domain") == user_context.get("working_domain"):
            reasons.append(f"relevant to your domain ({template_data['domain']})")

        # Quality reasons
        if template_data.get("quality_score", 0) > 90:
            reasons.append("high quality score")

        # Popularity reasons
        if template_data.get("usage_count", 0) > 10:
            reasons.append("popular among developers")

        # Similarity reason
        if similarity_score > 0.8:
            reasons.append("high semantic similarity to your query")

        if not reasons:
            reasons.append("good match for your needs")

        return "Recommended because it " + " and ".join(reasons[:3]) + "."

    async def get_search_analytics(self) -> Dict[str, Any]:
        """Get analytics about search usage and performance"""
        try:
            collection_stats = {
                "total_embeddings": self.collection.count(),
                "embedding_model": self.embedding_model_name,
                "collection_name": self.collection_name,
            }

            # Get top search terms (would need to implement search logging)
            analytics = {
                "collection_stats": collection_stats,
                "generated_at": datetime.now().isoformat(),
            }

            return analytics

        except Exception as e:
            logger.error(f"❌ Failed to get search analytics: {e}")
            return {}

    async def close(self):
        """Clean up resources"""
        # ChromaDB client doesn't need explicit closing
        logger.info("✅ Semantic search engine closed")


# Example usage and testing
async def main():
    """Example usage and testing"""

    # Initialize repository and semantic search
    repository = EnterpriseTemplateRepository()
    await repository.initialize()

    search_engine = TemplateSemanticSearch(repository)
    await search_engine.initialize()

    # Example: Add sample template embedding
    sample_template = {
        "id": str(uuid.uuid4()),
        "name": "React Login Component",
        "category": "components",
        "language": "typescript",
        "framework": "react",
        "domain": "auth",
        "description": "A reusable login component with form validation",
        "tags": ["react", "authentication", "form", "typescript"],
        "quality_score": 92.5,
        "complexity_level": "intermediate",
    }

    sample_content = """
import React, { useState } from 'react';

interface LoginProps {
    onSubmit: (credentials: LoginCredentials) => void;
}

export const LoginComponent: React.FC<LoginProps> = ({ onSubmit }) => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onSubmit({ username, password });
    };

    return (
        <form onSubmit={handleSubmit}>
            <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Username"
            />
            <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
            />
            <button type="submit">Login</button>
        </form>
    );
};
"""

    # Add embedding
    vector_id = await search_engine.add_template_embedding(
        sample_template["id"], sample_template, sample_content
    )
    print(f"✅ Added embedding: {vector_id}")

    # Test semantic search
    results = await search_engine.semantic_search(
        "login form component with validation",
        {"language": "typescript", "framework": "react"},
        limit=5,
    )

    print(f"🔍 Semantic search results: {len(results)}")
    for result in results:
        print(f"  - {result.template_name} (similarity: {result.similarity_score:.3f})")

    # Test recommendations
    user_context = {
        "preferred_language": "typescript",
        "preferred_framework": "react",
        "working_domain": "auth",
        "recent_searches": ["login", "authentication", "form validation"],
    }

    recommendations = await search_engine.get_recommendations(user_context, limit=3)
    print(f"💡 Recommendations: {len(recommendations)}")
    for rec in recommendations:
        print(f"  - {rec['name']} (score: {rec.get('recommendation_score', 0):.3f})")

    # Get analytics
    analytics = await search_engine.get_search_analytics()
    print(f"📊 Analytics: {analytics}")

    await search_engine.close()
    await repository.close()


if __name__ == "__main__":
    asyncio.run(main())
