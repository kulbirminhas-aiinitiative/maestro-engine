#!/usr/bin/env python3
"""
Persona-Level RAG Tools for Claude SDK
Provides persona-scoped template and pattern queries integrated with maestro-templates
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from claude_code_sdk import tool

    from rag.persona_domains import (
        get_persona_domain,
        get_relevant_templates_for_persona,
        match_template_to_persona,
    )
    from rag_system.pattern_recommender import PatternRecommender
    from rag_system.vector_rag_manager import get_rag_manager

    DEPS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Dependencies not available: {e}")
    DEPS_AVAILABLE = False


# Maestro-templates storage path
MAESTRO_TEMPLATES_PATH = Path("/home/ec2-user/projects/maestro-templates/storage/templates")


def _load_maestro_templates() -> List[Dict[str, Any]]:
    """
    Load all templates from maestro-templates storage

    Returns:
        List of template metadata dicts
    """
    templates = []

    if not MAESTRO_TEMPLATES_PATH.exists():
        logger.warning(f"Maestro templates directory not found: {MAESTRO_TEMPLATES_PATH}")
        return templates

    try:
        for template_file in MAESTRO_TEMPLATES_PATH.glob("*.json"):
            try:
                with open(template_file, "r") as f:
                    template_data = json.load(f)
                    # Extract metadata (maestro-templates format)
                    if "metadata" in template_data:
                        templates.append(template_data["metadata"])
                    else:
                        templates.append(template_data)
            except Exception as e:
                logger.warning(f"Failed to load template {template_file}: {e}")

        logger.info(f"📚 Loaded {len(templates)} templates from maestro-templates")
        return templates

    except Exception as e:
        logger.error(f"Failed to load maestro templates: {e}")
        return []


@tool(
    name="query_persona_templates",
    description="Query code templates relevant to a specific persona's domain from maestro-templates repository. Returns templates matching the persona's technology stack and expertise area.",
    input_schema={
        "type": "object",
        "properties": {
            "persona_id": {
                "type": "string",
                "description": "The persona ID (e.g., 'frontend_developer', 'backend_developer')",
            },
            "requirement": {
                "type": "string",
                "description": "The specific requirement or task to find templates for",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of templates to return (default: 5)",
                "default": 5,
            },
        },
        "required": ["persona_id", "requirement"],
    },
)
def query_persona_templates(persona_id: str, requirement: str, top_k: int = 5) -> str:
    """Claude tool: Query templates for a specific persona"""

    if not DEPS_AVAILABLE:
        return json.dumps({"error": "RAG system not available"})

    try:
        # Load all templates from maestro-templates
        all_templates = _load_maestro_templates()

        if not all_templates:
            return json.dumps(
                {
                    "persona_id": persona_id,
                    "templates_found": 0,
                    "message": "No templates available in maestro-templates repository",
                }
            )

        # Get persona domain
        domain = get_persona_domain(persona_id)

        # Filter templates relevant to persona
        relevant_templates = get_relevant_templates_for_persona(persona_id, all_templates)

        # Limit to top_k
        top_templates = relevant_templates[:top_k]

        # Format response
        response = {
            "persona_id": persona_id,
            "persona_domain": {
                "categories": domain.get("template_categories", []),
                "languages": domain.get("languages", []),
                "frameworks": domain.get("frameworks", []),
            },
            "templates_found": len(top_templates),
            "templates": [
                {
                    "id": t.get("id", "unknown"),
                    "name": t.get("name", "Unnamed"),
                    "category": t.get("category", "general"),
                    "language": t.get("language", "unknown"),
                    "framework": t.get("framework", "none"),
                    "description": t.get("description", ""),
                    "quality_score": t.get("quality_score", 0),
                    "tags": t.get("tags", []),
                    "relevance_score": t.get("_relevance_score", 0),
                }
                for t in top_templates
            ],
        }

        logger.info(f"🎯 Persona templates query: {persona_id} → {len(top_templates)} templates")

        return json.dumps(response, indent=2)

    except Exception as e:
        logger.error(f"Persona template query failed: {e}")
        return json.dumps({"error": str(e)})


@tool(
    name="query_persona_similar_executions",
    description="Search for similar historical executions where this persona was involved. Returns persona-specific execution patterns and success rates.",
    input_schema={
        "type": "object",
        "properties": {
            "persona_id": {"type": "string", "description": "The persona ID"},
            "requirement": {
                "type": "string",
                "description": "The requirement to search for similar executions",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of similar executions to return (default: 3)",
                "default": 3,
            },
        },
        "required": ["persona_id", "requirement"],
    },
)
def query_persona_similar_executions(persona_id: str, requirement: str, top_k: int = 3) -> str:
    """Claude tool: Query similar executions involving a specific persona"""

    if not DEPS_AVAILABLE:
        return json.dumps({"error": "RAG system not available"})

    try:
        rag_manager = get_rag_manager()

        # Search similar executions
        similar_executions = rag_manager.search_similar_executions(requirement, top_k=top_k * 2)

        # Filter for persona involvement
        persona_executions = []
        for execution in similar_executions:
            team_members = execution["metadata"].get("team_members", "")
            if isinstance(team_members, list):
                team_list = team_members
            else:
                team_list = team_members.split(",")

            if persona_id in team_list or f"ai_{persona_id}" in team_list:
                persona_executions.append(execution)

        # Limit to top_k
        persona_executions = persona_executions[:top_k]

        # Format results
        results = []
        for execution in persona_executions:
            results.append(
                {
                    "requirement": execution["metadata"].get("requirement", "Unknown"),
                    "similarity": f"{execution['similarity']*100:.1f}%",
                    "team_used": execution["metadata"].get("team_members", []),
                    "files_generated": execution["metadata"].get("total_files", 0),
                    "success": execution["metadata"].get("success", False),
                    "quality_score": execution["metadata"].get("quality_score", 0),
                    "session_id": execution["execution_id"],
                }
            )

        response = {
            "persona_id": persona_id,
            "similar_executions_found": len(results),
            "executions": results,
            "success_rate": (
                f"{sum(1 for r in results if r['success']) / len(results) * 100:.1f}%"
                if results
                else "N/A"
            ),
        }

        logger.info(f"👤 Persona execution query: {persona_id} → {len(results)} similar executions")

        return json.dumps(response, indent=2)

    except Exception as e:
        logger.error(f"Persona similar executions query failed: {e}")
        return json.dumps({"error": str(e)})


@tool(
    name="get_persona_best_practices",
    description="Get best practices and proven patterns for a specific persona based on successful historical executions and high-quality templates.",
    input_schema={
        "type": "object",
        "properties": {
            "persona_id": {"type": "string", "description": "The persona ID"},
            "task_type": {
                "type": "string",
                "description": "The type of task (optional, e.g., 'authentication', 'deployment', 'testing')",
                "default": "",
            },
        },
        "required": ["persona_id"],
    },
)
def get_persona_best_practices(persona_id: str, task_type: str = "") -> str:
    """Claude tool: Get best practices for a persona"""

    if not DEPS_AVAILABLE:
        return json.dumps({"error": "RAG system not available"})

    try:
        # Get persona domain
        domain = get_persona_domain(persona_id)

        # Load templates
        all_templates = _load_maestro_templates()
        relevant_templates = get_relevant_templates_for_persona(persona_id, all_templates)

        # Filter high-quality templates (quality_score >= 80)
        high_quality_templates = [t for t in relevant_templates if t.get("quality_score", 0) >= 80]

        # Get common patterns from templates
        common_frameworks = {}
        common_tags = {}

        for template in high_quality_templates:
            framework = template.get("framework", "")
            if framework:
                common_frameworks[framework] = common_frameworks.get(framework, 0) + 1

            for tag in template.get("tags", []):
                common_tags[tag] = common_tags.get(tag, 0) + 1

        # Sort by frequency
        top_frameworks = sorted(common_frameworks.items(), key=lambda x: x[1], reverse=True)[:5]
        top_tags = sorted(common_tags.items(), key=lambda x: x[1], reverse=True)[:10]

        response = {
            "persona_id": persona_id,
            "domain_expertise": {
                "primary_languages": domain.get("languages", []),
                "primary_frameworks": domain.get("frameworks", []),
                "template_categories": domain.get("template_categories", []),
            },
            "proven_patterns": {
                "most_used_frameworks": [f[0] for f in top_frameworks],
                "common_tags": [t[0] for t in top_tags],
            },
            "high_quality_templates_available": len(high_quality_templates),
            "best_practices": [
                f"Use {framework} (used in {count} high-quality templates)"
                for framework, count in top_frameworks
            ],
            "git_search_keywords": domain.get("git_search_keywords", []),
        }

        logger.info(
            f"📖 Best practices query: {persona_id} → {len(high_quality_templates)} quality templates"
        )

        return json.dumps(response, indent=2)

    except Exception as e:
        logger.error(f"Best practices query failed: {e}")
        return json.dumps({"error": str(e)})


@tool(
    name="recommend_templates_for_task",
    description="Recommend specific templates from maestro-templates for a persona's task. Matches task requirements to available templates.",
    input_schema={
        "type": "object",
        "properties": {
            "persona_id": {"type": "string", "description": "The persona ID"},
            "task_description": {
                "type": "string",
                "description": "Description of the task to find templates for",
            },
            "min_quality_score": {
                "type": "number",
                "description": "Minimum quality score threshold (default: 70)",
                "default": 70,
            },
        },
        "required": ["persona_id", "task_description"],
    },
)
def recommend_templates_for_task(
    persona_id: str, task_description: str, min_quality_score: float = 70
) -> str:
    """Claude tool: Recommend templates for a specific task"""

    if not DEPS_AVAILABLE:
        return json.dumps({"error": "RAG system not available"})

    try:
        # Load templates
        all_templates = _load_maestro_templates()

        # Filter by persona relevance
        relevant_templates = get_relevant_templates_for_persona(persona_id, all_templates)

        # Filter by quality score
        quality_templates = [
            t for t in relevant_templates if t.get("quality_score", 0) >= min_quality_score
        ]

        # Simple keyword matching for task description
        task_keywords = task_description.lower().split()

        # Score templates by keyword overlap
        scored_templates = []
        for template in quality_templates:
            score = 0

            # Check name
            name_lower = template.get("name", "").lower()
            score += sum(1 for kw in task_keywords if kw in name_lower) * 3

            # Check description
            desc_lower = template.get("description", "").lower()
            score += sum(1 for kw in task_keywords if kw in desc_lower) * 2

            # Check tags
            tags = [tag.lower() for tag in template.get("tags", [])]
            score += sum(1 for kw in task_keywords if kw in tags)

            if score > 0:
                template_copy = template.copy()
                template_copy["_task_match_score"] = score
                scored_templates.append(template_copy)

        # Sort by task match score
        scored_templates.sort(key=lambda t: t["_task_match_score"], reverse=True)

        # Take top 3
        recommendations = scored_templates[:3]

        response = {
            "persona_id": persona_id,
            "task_description": task_description,
            "recommendations_found": len(recommendations),
            "recommendations": [
                {
                    "id": t.get("id", "unknown"),
                    "name": t.get("name", "Unnamed"),
                    "category": t.get("category", "general"),
                    "language": t.get("language", "unknown"),
                    "framework": t.get("framework", "none"),
                    "description": t.get("description", ""),
                    "quality_score": t.get("quality_score", 0),
                    "match_score": t.get("_task_match_score", 0),
                    "file_path": t.get("file_path", ""),
                }
                for t in recommendations
            ],
        }

        logger.info(
            f"🎯 Task recommendation: {persona_id} → {len(recommendations)} templates for '{task_description}'"
        )

        return json.dumps(response, indent=2)

    except Exception as e:
        logger.error(f"Template recommendation failed: {e}")
        return json.dumps({"error": str(e)})


# Export persona RAG tools
PERSONA_RAG_TOOLS = [
    query_persona_templates,
    query_persona_similar_executions,
    get_persona_best_practices,
    recommend_templates_for_task,
]


def get_persona_rag_tools_list():
    """Get list of all persona-level RAG tools"""
    return PERSONA_RAG_TOOLS


def get_persona_rag_tools_description() -> str:
    """Get description of persona RAG tools for Claude's system prompt"""

    description = """
You have access to the following PERSONA-LEVEL RAG tools for domain-specific queries:

🎯 **Persona-Scoped Template & Pattern Queries:**

1. **query_persona_templates** - Get templates relevant to a persona's domain
   - Use when: A persona needs code templates, scaffolding, or boilerplate
   - Searches: maestro-templates repository filtered by persona domain
   - Returns: Templates matching persona's tech stack (React for frontend, FastAPI for backend, etc.)

2. **query_persona_similar_executions** - Find executions where persona was involved
   - Use when: Wanting to see how this persona handled similar tasks before
   - Filters: Only executions with this persona in the team
   - Returns: Persona-specific success patterns and execution details

3. **get_persona_best_practices** - Get proven patterns for a persona
   - Use when: Wanting to know best practices for a persona's domain
   - Analyzes: High-quality templates and successful executions
   - Returns: Most-used frameworks, common patterns, git search keywords

4. **recommend_templates_for_task** - Match task to specific templates
   - Use when: Persona has a specific task and needs relevant templates
   - Matches: Task keywords to template names/descriptions/tags
   - Returns: Top 3 templates ranked by relevance and quality

**Integration with maestro-templates:**
- All tools query /storage/templates/ directory
- Templates include metadata: category, language, framework, quality_score, tags
- Templates may also be stored in GitHub repos (full project templates)

**Best Practice:**
- Use persona tools AFTER get_swift_mvp_plan to get domain-specific details
- Query templates before starting persona execution for boilerplate
- Check persona best practices for framework/pattern recommendations
"""

    return description
