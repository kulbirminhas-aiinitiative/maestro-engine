#!/usr/bin/env python3
"""
RAG Tools for Claude SDK
Provides @tool decorated functions for Claude to query RAG dynamically
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from claude_agent_sdk import tool

    from rag_system.collateral_extractor import CollateralExtractor
    from rag_system.pattern_recommender import PatternRecommender
    from rag_system.vector_rag_manager import get_rag_manager

    DEPS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Dependencies not available: {e}")
    DEPS_AVAILABLE = False


@tool(
    name="query_similar_projects",
    description="Search for similar historical projects using semantic similarity. Returns projects with similar requirements, their teams, execution details, and success status.",
    input_schema={
        "type": "object",
        "properties": {
            "requirement": {
                "type": "string",
                "description": "The requirement to search for similar projects",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of similar projects to return (default: 3)",
                "default": 3,
            },
        },
        "required": ["requirement"],
    },
)
def query_similar_projects(requirement: str, top_k: int = 3) -> str:
    """Claude tool: Query RAG for similar historical projects"""

    if not DEPS_AVAILABLE:
        return json.dumps({"error": "RAG system not available"})

    try:
        rag_manager = get_rag_manager()
        similar_executions = rag_manager.search_similar_executions(requirement, top_k)

        results = []
        for execution in similar_executions:
            results.append(
                {
                    "requirement": execution["metadata"].get("requirement", "Unknown"),
                    "similarity": f"{execution['similarity']*100:.1f}%",
                    "team_used": execution["metadata"].get("team_members", []),
                    "files_generated": execution["metadata"].get("total_files", 0),
                    "execution_time": f"{execution['metadata'].get('execution_time', 0):.1f}s",
                    "success": execution["metadata"].get("success", False),
                    "session_id": execution["execution_id"],
                }
            )

        response = {"similar_projects_found": len(results), "projects": results}

        logger.info(f"🔍 Claude queried RAG: Found {len(results)} similar projects")

        return json.dumps(response, indent=2)

    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        return json.dumps({"error": str(e)})


@tool(
    name="get_recommended_team",
    description="Get recommended team composition based on historical successful projects with similar requirements. Returns team members with confidence level and evidence.",
    input_schema={
        "type": "object",
        "properties": {
            "requirement": {
                "type": "string",
                "description": "The requirement to get team recommendation for",
            }
        },
        "required": ["requirement"],
    },
)
def get_recommended_team(requirement: str) -> str:
    """Claude tool: Get RAG-based team recommendation"""

    if not DEPS_AVAILABLE:
        return json.dumps({"error": "RAG system not available"})

    try:
        recommender = PatternRecommender()
        recommendation = recommender.recommend_team_composition(requirement)

        logger.info(
            f"👥 Claude requested team recommendation: {', '.join(recommendation['recommended_team'])}"
        )

        return json.dumps(recommendation, indent=2)

    except Exception as e:
        logger.error(f"Team recommendation failed: {e}")
        return json.dumps({"error": str(e)})


@tool(
    name="get_deliverables_template",
    description="Get recommended deliverables.json template based on similar historical projects. Returns reusable template with task distribution.",
    input_schema={
        "type": "object",
        "properties": {
            "requirement": {
                "type": "string",
                "description": "The requirement to get deliverables template for",
            }
        },
        "required": ["requirement"],
    },
)
def get_deliverables_template(requirement: str) -> str:
    """Claude tool: Get recommended deliverables template from RAG"""

    if not DEPS_AVAILABLE:
        return json.dumps({"error": "RAG system not available"})

    try:
        recommender = PatternRecommender()
        template = recommender.recommend_deliverables_template(requirement)

        logger.info(f"📋 Claude requested deliverables template")

        return json.dumps(template, indent=2)

    except Exception as e:
        logger.error(f"Deliverables template recommendation failed: {e}")
        return json.dumps({"error": str(e)})


@tool(
    name="analyze_historical_failures",
    description="Analyze similar projects that failed in the past to identify potential pitfalls and mistakes to avoid.",
    input_schema={
        "type": "object",
        "properties": {
            "requirement": {
                "type": "string",
                "description": "The requirement to analyze historical failures for",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of failures to analyze (default: 5)",
                "default": 5,
            },
        },
        "required": ["requirement"],
    },
)
def analyze_historical_failures(requirement: str, top_k: int = 5) -> str:
    """Claude tool: Find and analyze historical failures to avoid mistakes"""

    if not DEPS_AVAILABLE:
        return json.dumps({"error": "RAG system not available"})

    try:
        rag_manager = get_rag_manager()
        similar_executions = rag_manager.search_similar_executions(requirement, top_k=top_k)

        failures = []
        for execution in similar_executions:
            if not execution["metadata"].get("success", True):
                failures.append(
                    {
                        "requirement": execution["metadata"].get("requirement", "Unknown"),
                        "similarity": f"{execution['similarity']*100:.1f}%",
                        "team_used": execution["metadata"].get("team_members", []),
                        "execution_time": f"{execution['metadata'].get('execution_time', 0):.1f}s",
                        "session_id": execution["execution_id"],
                    }
                )

        response = {
            "failures_found": len(failures),
            "failures": failures,
            "recommendation": (
                "Review these failures to avoid similar mistakes"
                if failures
                else "No historical failures found for similar requirements"
            ),
        }

        logger.info(f"⚠️  Claude analyzed failures: Found {len(failures)} failed attempts")

        return json.dumps(response, indent=2)

    except Exception as e:
        logger.error(f"Failure analysis failed: {e}")
        return json.dumps({"error": str(e)})


@tool(
    name="get_execution_estimate",
    description="Get estimated execution time and file count based on similar historical projects.",
    input_schema={
        "type": "object",
        "properties": {
            "requirement": {
                "type": "string",
                "description": "The requirement to get execution estimate for",
            }
        },
        "required": ["requirement"],
    },
)
def get_execution_estimate(requirement: str) -> str:
    """Claude tool: Get execution time and output estimates from RAG"""

    if not DEPS_AVAILABLE:
        return json.dumps({"error": "RAG system not available"})

    try:
        recommender = PatternRecommender()
        estimate = recommender.get_execution_estimate(requirement)

        logger.info(
            f"⏱️  Claude requested estimate: ~{estimate['estimated_time_seconds']:.1f}s, ~{estimate['estimated_files']} files"
        )

        return json.dumps(estimate, indent=2)

    except Exception as e:
        logger.error(f"Execution estimate failed: {e}")
        return json.dumps({"error": str(e)})


@tool(
    name="get_requirement_insights",
    description="Analyze the requirement type and get insights about what has worked well historically for this type of project.",
    input_schema={
        "type": "object",
        "properties": {
            "requirement": {"type": "string", "description": "The requirement to get insights for"}
        },
        "required": ["requirement"],
    },
)
def get_requirement_insights(requirement: str) -> str:
    """Claude tool: Get insights about requirement type and historical patterns"""

    if not DEPS_AVAILABLE:
        return json.dumps({"error": "RAG system not available"})

    try:
        extractor = CollateralExtractor()
        req_type = extractor._classify_requirement(requirement)

        recommender = PatternRecommender()
        suggestions = recommender.suggest_improvements(requirement)

        insights = {
            "requirement_type": req_type,
            "classification": req_type.replace("_", " ").title(),
            "suggestions": suggestions,
        }

        logger.info(f"💡 Claude requested insights: {req_type}")

        return json.dumps(insights, indent=2)

    except Exception as e:
        logger.error(f"Insights generation failed: {e}")
        return json.dumps({"error": str(e)})


@tool(
    name="get_swift_mvp_plan",
    description="[FIRST-STRIKE TOOL] Unified tool that orchestrates critical RAG queries in parallel (similar projects, deliverables templates) and returns a synthesized, opinionated MVP execution plan immediately. Use this FIRST before individual RAG tools for fastest initial response.",
    input_schema={
        "type": "object",
        "properties": {
            "requirement": {
                "type": "string",
                "description": "The requirement to create Swift MVP plan for",
            }
        },
        "required": ["requirement"],
    },
)
def get_swift_mvp_plan(requirement: str) -> str:
    """Claude tool: First-Strike unified RAG query - Returns opinionated MVP plan immediately"""

    if not DEPS_AVAILABLE:
        return json.dumps({"error": "RAG system not available"})

    try:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        logger.info(f"⚡ FIRST-STRIKE: Orchestrating parallel RAG queries for Swift MVP plan...")

        rag_manager = get_rag_manager()
        recommender = PatternRecommender()

        with ThreadPoolExecutor(max_workers=4) as executor:
            similar_future = executor.submit(rag_manager.search_similar_executions, requirement, 3)
            team_future = executor.submit(recommender.recommend_team_composition, requirement)
            deliverables_future = executor.submit(
                recommender.recommend_deliverables_template, requirement
            )
            estimate_future = executor.submit(recommender.get_execution_estimate, requirement)

            similar_projects = similar_future.result()
            team_recommendation = team_future.result()
            deliverables_template = deliverables_future.result()
            execution_estimate = estimate_future.result()

        successful_projects = [p for p in similar_projects if p["metadata"].get("success", False)]

        mvp_plan = {
            "swift_mvp_strategy": {
                "execution_mode": (
                    "fast_track"
                    if execution_estimate.get("estimated_time_seconds", 0) < 10
                    else "standard"
                ),
                "estimated_time": f"{execution_estimate.get('estimated_time_seconds', 0):.1f}s",
                "estimated_files": execution_estimate.get("estimated_files", 0),
                "confidence": execution_estimate.get("confidence", "medium"),
            },
            "recommended_team": {
                "members": team_recommendation.get("recommended_team", []),
                "confidence": team_recommendation.get("confidence", 0),
                "evidence_count": team_recommendation.get("evidence_count", 0),
            },
            "historical_insights": {
                "similar_projects_found": len(similar_projects),
                "successful_projects": len(successful_projects),
                "best_match": (
                    successful_projects[0]["metadata"].get("requirement", "None")
                    if successful_projects
                    else None
                ),
                "best_match_similarity": (
                    f"{successful_projects[0]['similarity']*100:.1f}%"
                    if successful_projects
                    else None
                ),
            },
            "deliverables_template": deliverables_template.get("template", {}),
            "opinionated_next_steps": [
                f"Start with {len(team_recommendation.get('recommended_team', []))} proven team members",
                f"Generate {execution_estimate.get('estimated_files', 0)} files based on historical patterns",
                f"Leverage {len(successful_projects)} successful similar projects",
                "Execute immediately using proven patterns - no over-analysis needed",
            ],
        }

        logger.info(f"✅ FIRST-STRIKE complete: Plan synthesized in parallel execution")
        logger.info(f"   Team: {', '.join(team_recommendation.get('recommended_team', []))}")
        logger.info(
            f"   Estimate: {execution_estimate.get('estimated_time_seconds', 0):.1f}s, {execution_estimate.get('estimated_files', 0)} files"
        )
        logger.info(f"   Similar projects: {len(successful_projects)} successful matches")

        return json.dumps(mvp_plan, indent=2)

    except Exception as e:
        logger.error(f"Swift MVP plan generation failed: {e}")
        return json.dumps({"error": str(e)})


@tool(
    name="get_rag_stats",
    description="Get statistics about the RAG knowledge base including total executions, patterns, and collaterals indexed.",
    input_schema={"type": "object", "properties": {}},
)
def get_rag_stats() -> str:
    """Claude tool: Get RAG system statistics"""

    if not DEPS_AVAILABLE:
        return json.dumps({"error": "RAG system not available"})

    try:
        rag_manager = get_rag_manager()
        stats = rag_manager.get_collection_stats()

        summary = {
            "total_executions": stats.get("executions", {}).get("count", 0),
            "total_collaterals": stats.get("collaterals", {}).get("count", 0),
            "total_patterns": stats.get("patterns", {}).get("count", 0),
            "cache_size": stats.get("cache_size", 0),
        }

        logger.info(
            f"📊 Claude requested RAG stats: {summary['total_executions']} executions indexed"
        )

        return json.dumps(summary, indent=2)

    except Exception as e:
        logger.error(f"RAG stats retrieval failed: {e}")
        return json.dumps({"error": str(e)})


RAG_TOOLS = [
    get_swift_mvp_plan,
    query_similar_projects,
    get_recommended_team,
    get_deliverables_template,
    analyze_historical_failures,
    get_execution_estimate,
    get_requirement_insights,
    get_rag_stats,
]


def get_rag_tools_list():
    """Get list of all RAG tools for Claude"""
    return RAG_TOOLS


def get_rag_tools_description() -> str:
    """Get description of RAG tools for Claude's system prompt"""

    description = """
You have access to the following RAG (Retrieval-Augmented Generation) tools to query historical project data:

🚀 **FIRST-STRIKE TOOL (Use This First!):**

1. **get_swift_mvp_plan** - ⚡ UNIFIED First-Strike RAG Tool
   - Use when: Starting ANY new requirement (use this FIRST!)
   - What it does: Orchestrates ALL critical RAG queries in PARALLEL (similar projects, team, deliverables, estimates)
   - Returns: Complete opinionated MVP execution plan with all insights synthesized
   - Speed: ~2-3x faster than sequential individual tool calls
   - **PRIORITY: Always call this FIRST to avoid analysis paralysis**

📊 **Individual RAG Tools (Use for specific deep-dives after First-Strike):**

2. **query_similar_projects** - Find similar historical projects by semantic similarity
   - Use when: You need detailed analysis of specific similar projects
   - Returns: List of similar projects with teams, execution details, success status

3. **get_recommended_team** - Get team composition recommendations
   - Use when: You need deeper team justification beyond First-Strike result
   - Returns: Recommended team with confidence level and evidence

4. **get_deliverables_template** - Get deliverables.json template from history
   - Use when: You need detailed template customization
   - Returns: Reusable template with task distribution

5. **analyze_historical_failures** - Find and analyze past failures
   - Use when: You want to avoid mistakes from similar projects
   - Returns: List of failed attempts with details

6. **get_execution_estimate** - Estimate execution time and output
   - Use when: You need detailed breakdown beyond First-Strike estimate
   - Returns: Time estimate, file count estimate, confidence level

7. **get_requirement_insights** - Analyze requirement type and patterns
   - Use when: You want to understand the requirement category
   - Returns: Classification, historical insights, suggestions

8. **get_rag_stats** - View RAG knowledge base statistics
   - Use when: You want to know what data is available
   - Returns: Total executions, patterns, collaterals indexed

**EXECUTION STRATEGY:**
1. ⚡ ALWAYS call get_swift_mvp_plan FIRST for instant synthesized plan
2. 📋 Review the opinionated_next_steps and execute immediately
3. 🔍 Only call individual tools if you need deeper analysis on specific aspects
4. 🚀 Prioritize speed - the First-Strike tool gives you everything to start

**Best Practice:** Start with get_swift_mvp_plan to get complete context in one parallel query, then execute. Avoid over-analysis.
"""

    return description
