#!/usr/bin/env python3
"""
Template RAG Integration
Retrieval-Augmented Generation using MAESTRO Template Registry

This module:
1. Retrieves relevant templates from Template Registry based on requirements
2. Enhances prompts with template context
3. Stores execution history in ChromaDB for future retrieval
"""

import asyncio
import httpx
import logging
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re

# ChromaDB for execution history
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logging.warning("⚠️ ChromaDB not available - execution history disabled")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TemplateMatch:
    """A matched template from the registry"""
    id: str
    name: str
    description: str
    category: str
    language: str
    framework: Optional[str]
    tags: List[str]
    relevance_score: float
    git_url: Optional[str] = None


class TemplateRAGEngine:
    """
    RAG engine for template-enhanced code generation

    Features:
    - Semantic search for relevant templates
    - Template content retrieval
    - Execution history storage and retrieval
    - Context enhancement for prompts
    """

    def __init__(
        self,
        template_registry_url: str = "http://localhost:9600",
        chroma_collection: str = "maestro_executions",
        max_templates: int = 3
    ):
        self.template_registry_url = template_registry_url
        self.chroma_collection = chroma_collection
        self.max_templates = max_templates
        self.http_client = httpx.AsyncClient(timeout=30.0)

        # ChromaDB for execution history
        self.chroma_client = None
        self.history_collection = None

        if CHROMADB_AVAILABLE:
            try:
                self.chroma_client = chromadb.Client(Settings(anonymized_telemetry=False))
                self.history_collection = self.chroma_client.get_or_create_collection(
                    name=self.chroma_collection
                )
                logger.info("✅ ChromaDB initialized for execution history")
            except Exception as e:
                logger.warning(f"⚠️ ChromaDB initialization failed: {e}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()

    async def search_templates(self, requirement: str) -> List[TemplateMatch]:
        """
        Search for relevant templates based on requirement

        Args:
            requirement: User requirement text

        Returns:
            List of matched templates sorted by relevance
        """
        try:
            # Extract keywords from requirement
            keywords = self._extract_keywords(requirement)

            logger.info(f"🔍 Searching templates with keywords: {keywords}")

            # Search by category if detected
            category = self._detect_category(requirement)
            language = self._detect_language(requirement)
            framework = self._detect_framework(requirement)

            # Build search query
            search_params = {}
            if category:
                search_params['category'] = category
            if language:
                search_params['language'] = language
            if framework:
                search_params['framework'] = framework

            # First try filtered search
            templates = await self._fetch_templates(search_params)

            # If no results, try general search
            if not templates:
                logger.info("  No templates found with filters, trying general search")
                templates = await self._fetch_templates({})

            # Rank templates by relevance
            matches = self._rank_templates(templates, requirement, keywords)

            # Limit to max_templates
            top_matches = matches[:self.max_templates]

            if top_matches:
                logger.info(f"✅ Found {len(top_matches)} relevant templates:")
                for match in top_matches:
                    logger.info(f"  - {match.name} ({match.category}) - relevance: {match.relevance_score:.2f}")
            else:
                logger.info("  No templates found")

            return top_matches

        except Exception as e:
            logger.error(f"❌ Template search failed: {e}")
            return []

    async def _fetch_templates(self, params: Dict[str, str]) -> List[Dict[str, Any]]:
        """Fetch templates from registry"""
        try:
            url = f"{self.template_registry_url}/api/v1/templates"
            response = await self.http_client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                return data.get('templates', [])
            else:
                logger.warning(f"⚠️ Template fetch failed: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"❌ Failed to fetch templates: {e}")
            return []

    def _extract_keywords(self, requirement: str) -> List[str]:
        """Extract keywords from requirement"""
        # Remove common words
        stop_words = {
            'create', 'build', 'make', 'develop', 'implement', 'design',
            'a', 'an', 'the', 'with', 'for', 'and', 'or', 'that', 'this',
            'in', 'on', 'at', 'to', 'from', 'by', 'of', 'is', 'are', 'was', 'were'
        }

        # Extract words
        words = re.findall(r'\b[a-zA-Z]+\b', requirement.lower())

        # Filter stop words and short words
        keywords = [w for w in words if w not in stop_words and len(w) > 3]

        return keywords[:10]  # Limit to 10 keywords

    def _detect_category(self, requirement: str) -> Optional[str]:
        """Detect category from requirement"""
        req_lower = requirement.lower()

        category_patterns = {
            'api': ['api', 'rest', 'restful', 'endpoint', 'service'],
            'frontend': ['frontend', 'ui', 'web page', 'website', 'react', 'vue', 'angular'],
            'backend': ['backend', 'server', 'database', 'api server'],
            'fullstack': ['fullstack', 'full stack', 'full-stack', 'web application'],
            'library': ['library', 'package', 'module'],
            'cli': ['cli', 'command line', 'terminal'],
            'mobile': ['mobile', 'ios', 'android', 'app'],
            'devops': ['devops', 'docker', 'kubernetes', 'deployment', 'ci/cd']
        }

        for category, patterns in category_patterns.items():
            if any(pattern in req_lower for pattern in patterns):
                return category

        return None

    def _detect_language(self, requirement: str) -> Optional[str]:
        """Detect programming language from requirement"""
        req_lower = requirement.lower()

        language_patterns = {
            'python': ['python', 'flask', 'django', 'fastapi'],
            'javascript': ['javascript', 'js', 'node', 'express', 'react', 'vue'],
            'typescript': ['typescript', 'ts'],
            'java': ['java', 'spring'],
            'go': ['go', 'golang'],
            'rust': ['rust'],
            'ruby': ['ruby', 'rails']
        }

        for language, patterns in language_patterns.items():
            if any(pattern in req_lower for pattern in patterns):
                return language

        return None

    def _detect_framework(self, requirement: str) -> Optional[str]:
        """Detect framework from requirement"""
        req_lower = requirement.lower()

        frameworks = [
            'react', 'vue', 'angular', 'svelte',
            'fastapi', 'django', 'flask', 'express',
            'spring', 'rails', 'next', 'nuxt'
        ]

        for framework in frameworks:
            if framework in req_lower:
                return framework

        return None

    def _rank_templates(
        self,
        templates: List[Dict[str, Any]],
        requirement: str,
        keywords: List[str]
    ) -> List[TemplateMatch]:
        """Rank templates by relevance to requirement"""
        matches = []

        req_lower = requirement.lower()

        for template in templates:
            score = 0.0

            # Score by name match
            name = template.get('name', '').lower()
            if any(kw in name for kw in keywords):
                score += 2.0

            # Score by description match
            description = template.get('description', '').lower()
            keyword_matches = sum(1 for kw in keywords if kw in description)
            score += keyword_matches * 0.5

            # Score by tags match
            tags = template.get('tags', [])
            tag_matches = sum(1 for tag in tags if any(kw in tag.lower() for kw in keywords))
            score += tag_matches * 1.0

            # Score by category match
            category = template.get('category', '')
            if category and category.lower() in req_lower:
                score += 3.0

            # Score by framework match
            framework = template.get('framework', '')
            if framework and framework.lower() in req_lower:
                score += 2.5

            # Score by quality
            quality_score = template.get('quality_score', 0)
            if quality_score:
                score += quality_score / 100.0  # Normalize to 0-1

            if score > 0:
                matches.append(TemplateMatch(
                    id=template.get('id', ''),
                    name=template.get('name', ''),
                    description=template.get('description', ''),
                    category=category,
                    language=template.get('language', ''),
                    framework=framework,
                    tags=tags,
                    relevance_score=score,
                    git_url=template.get('git_url')
                ))

        # Sort by relevance score
        matches.sort(key=lambda x: x.relevance_score, reverse=True)

        return matches

    def enhance_prompt_with_templates(
        self,
        requirement: str,
        templates: List[TemplateMatch]
    ) -> str:
        """
        Enhance prompt with template context

        Args:
            requirement: Original requirement
            templates: Matched templates

        Returns:
            Enhanced prompt with template examples
        """
        if not templates:
            return requirement

        # Build context from templates
        context_parts = [
            "# Context: Relevant Templates",
            "",
            "The following templates are similar to what you're building:",
            ""
        ]

        for i, template in enumerate(templates, 1):
            context_parts.extend([
                f"## Template {i}: {template.name}",
                f"**Category**: {template.category}",
                f"**Language**: {template.language}",
                f"**Framework**: {template.framework or 'None'}",
                f"**Description**: {template.description}",
                f"**Tags**: {', '.join(template.tags[:5])}",
                ""
            ])

        context_parts.extend([
            "---",
            "",
            "# Your Task",
            "",
            requirement,
            "",
            "**Note**: Use the templates above as inspiration for architecture, patterns, and best practices.",
            ""
        ])

        return "\n".join(context_parts)

    async def store_execution(
        self,
        session_id: str,
        requirement: str,
        result: Dict[str, Any],
        templates_used: List[TemplateMatch]
    ):
        """Store execution result in ChromaDB for future retrieval"""
        if not self.history_collection:
            return

        try:
            # Create document
            document = {
                "session_id": session_id,
                "requirement": requirement,
                "success": result.get("success", False),
                "files_generated": result.get("files_generated", []),
                "execution_method": result.get("execution_method", ""),
                "templates_used": [t.name for t in templates_used],
                "quality_score": result.get("quality_validation", {}).get("quality_score"),
            }

            # Add to ChromaDB
            doc_id = f"{session_id}_{int(asyncio.get_event_loop().time())}"

            self.history_collection.add(
                documents=[json.dumps(document)],
                metadatas=[{
                    "session_id": session_id,
                    "requirement": requirement[:200],  # Truncate for metadata
                    "success": str(result.get("success", False))
                }],
                ids=[doc_id]
            )

            logger.info(f"✅ Execution history stored: {doc_id}")

        except Exception as e:
            logger.warning(f"⚠️ Failed to store execution history: {e}")

    async def retrieve_similar_executions(
        self,
        requirement: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Retrieve similar past executions from ChromaDB"""
        if not self.history_collection:
            return []

        try:
            # Query ChromaDB for similar requirements
            results = self.history_collection.query(
                query_texts=[requirement],
                n_results=limit
            )

            if results and results['documents']:
                executions = []
                for doc_str in results['documents'][0]:
                    try:
                        executions.append(json.loads(doc_str))
                    except:
                        pass

                logger.info(f"✅ Retrieved {len(executions)} similar executions")
                return executions

        except Exception as e:
            logger.warning(f"⚠️ Failed to retrieve execution history: {e}")

        return []


async def test_rag_system():
    """Test the RAG system"""
    print("🔍 Testing Template RAG System\n")

    async with TemplateRAGEngine() as rag:
        # Test 1: Search for REST API templates
        print("="*60)
        print("Test 1: Search for REST API templates")
        print("="*60)

        requirement = "Create a REST API for user management with FastAPI"
        templates = await rag.search_templates(requirement)

        print(f"\nRequirement: {requirement}")
        print(f"Templates found: {len(templates)}\n")

        if templates:
            # Test 2: Enhance prompt
            print("="*60)
            print("Test 2: Enhanced Prompt")
            print("="*60)

            enhanced = rag.enhance_prompt_with_templates(requirement, templates)
            print(enhanced[:500] + "...\n")

        # Test 3: Search for frontend templates
        print("="*60)
        print("Test 3: Search for frontend templates")
        print("="*60)

        requirement2 = "Build a React frontend with responsive design"
        templates2 = await rag.search_templates(requirement2)

        print(f"\nRequirement: {requirement2}")
        print(f"Templates found: {len(templates2)}\n")


if __name__ == "__main__":
    asyncio.run(test_rag_system())
