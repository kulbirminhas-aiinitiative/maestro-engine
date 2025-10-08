#!/usr/bin/env python3
"""
RAG Integration for Workflow Engine

Provides helpers for:
- Querying RAG Reader before persona execution
- Indexing results to RAG Writer after execution
- Quality score calculation
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# RAG Service URLs
RAG_READER_URL = os.getenv("RAG_READER_URL", "http://localhost:9801")
RAG_WRITER_URL = os.getenv("RAG_WRITER_URL", "http://localhost:9802")
RAG_READER_API_KEY = os.getenv("RAG_READER_API_KEY", "dev_rag_reader_key_12345")
RAG_WRITER_API_KEY = os.getenv("RAG_WRITER_API_KEY", "dev_rag_writer_key_98765")

# Feature flag
RAG_INTEGRATION_ENABLED = os.getenv("RAG_INTEGRATION_ENABLED", "false").lower() == "true"


class RAGIntegration:
    """Handles RAG integration for workflow engine"""

    def __init__(self, enabled: bool = None):
        self.enabled = enabled if enabled is not None else RAG_INTEGRATION_ENABLED
        if self.enabled:
            logger.info("🔗 RAG Integration: ENABLED")
        else:
            logger.info("🔗 RAG Integration: DISABLED")

    def get_persona_guidance(
        self, persona_id: str, requirement: str, top_k: int = 3
    ) -> Dict[str, Any]:
        """
        Get RAG guidance before persona executes task

        Returns:
            Dict with templates, best_practices, and frameworks
        """
        if not self.enabled:
            return {"templates": [], "best_practices": [], "frameworks": []}

        try:
            # Query templates
            templates_response = requests.post(
                f"{RAG_READER_URL}/api/v1/query/templates",
                headers={"X-API-Key": RAG_READER_API_KEY},
                json={
                    "persona_id": persona_id,
                    "requirement": requirement,
                    "top_k": top_k,
                    "min_quality_score": 60.0,
                },
                timeout=10,
            )
            templates_data = templates_response.json() if templates_response.ok else {}

            # Query best practices
            practices_response = requests.post(
                f"{RAG_READER_URL}/api/v1/query/best-practices",
                headers={"X-API-Key": RAG_READER_API_KEY},
                json={"persona_id": persona_id},
                timeout=10,
            )
            practices_data = practices_response.json() if practices_response.ok else {}

            guidance = {
                "templates": templates_data.get("templates", [])[:top_k],
                "best_practices": practices_data.get("best_practices", [])[:5],
                "frameworks": practices_data.get("proven_patterns", {}).get(
                    "most_used_frameworks", []
                )[:3],
            }

            logger.info(
                f"📚 RAG Guidance for {persona_id}: {len(guidance['templates'])} templates, "
                f"{len(guidance['best_practices'])} practices, {len(guidance['frameworks'])} frameworks"
            )

            return guidance

        except Exception as e:
            logger.warning(f"⚠️  RAG guidance query failed: {e}")
            return {"templates": [], "best_practices": [], "frameworks": []}

    def format_guidance_for_prompt(self, guidance: Dict[str, Any]) -> str:
        """
        Format RAG guidance for inclusion in persona prompt

        Returns:
            Formatted string to add to prompt
        """
        if not guidance or not any(guidance.values()):
            return ""

        prompt_addition = "\n\n## RAG KNOWLEDGE BASE GUIDANCE\n\n"

        # Add templates
        if guidance.get("templates"):
            prompt_addition += "### Relevant Code Templates:\n"
            for i, template in enumerate(guidance["templates"][:2], 1):
                prompt_addition += f"{i}. **{template.get('name', 'Unknown')}** "
                prompt_addition += (
                    f"({template.get('category', 'N/A')} | {template.get('language', 'N/A')})\n"
                )
                prompt_addition += f"   - Quality: {template.get('quality_score', 0):.1f}\n"
                if template.get("description"):
                    prompt_addition += f"   - {template['description']}\n"
            prompt_addition += "\n"

        # Add frameworks
        if guidance.get("frameworks"):
            prompt_addition += "### Recommended Frameworks/Tools:\n"
            for framework in guidance["frameworks"]:
                prompt_addition += f"- {framework}\n"
            prompt_addition += "\n"

        # Add best practices
        if guidance.get("best_practices"):
            prompt_addition += "### Best Practices from Similar Tasks:\n"
            for i, practice in enumerate(guidance["best_practices"][:3], 1):
                prompt_addition += f"{i}. {practice}\n"
            prompt_addition += "\n"

        prompt_addition += (
            "*Note: This guidance is from previous successful executions. Adapt as needed.*\n"
        )

        return prompt_addition

    def index_workflow_execution(
        self,
        session_id: str,
        requirement: str,
        personas: List[str],
        collaterals: List[Dict[str, Any]],
        quality_score: float,
        success: bool,
        execution_time: float = None,
    ) -> Optional[str]:
        """
        Index completed workflow execution to RAG Writer

        Returns:
            Task ID if successful, None otherwise
        """
        if not self.enabled:
            return None

        try:
            payload = {
                "session_id": session_id,
                "requirement": requirement,
                "personas": personas,
                "collaterals": collaterals,
                "quality_score": quality_score,
                "success": success,
                "execution_time": execution_time,
            }

            response = requests.post(
                f"{RAG_WRITER_URL}/api/v1/index/execution",
                headers={"X-API-Key": RAG_WRITER_API_KEY},
                json=payload,
                timeout=10,
            )

            if response.ok:
                result = response.json()
                task_id = result.get("task_id")
                logger.info(f"📥 Workflow indexed to RAG Writer (task: {task_id})")
                return task_id
            else:
                logger.warning(f"⚠️  RAG indexing failed: {response.status_code}")
                return None

        except Exception as e:
            logger.warning(f"⚠️  RAG indexing error: {e}")
            return None

    def calculate_quality_score(
        self,
        success: bool,
        files_generated: List[str],
        personas_count: int,
        execution_time: float = None,
    ) -> float:
        """
        Calculate quality score for execution

        Returns:
            Quality score (0.0 - 1.0)
        """
        score = 0.0

        # Base score from success (50%)
        if success:
            score += 0.5

        # Files generated (20% max)
        files_score = min(0.2, len(files_generated) / 20.0)
        score += files_score

        # Team composition (10% max)
        personas_score = min(0.1, personas_count / 10.0)
        score += personas_score

        # Execution time bonus (20% max - faster is better)
        if execution_time:
            # Baseline: 10 minutes = 600 seconds
            # < 5 min = +20%, 5-10 min = +10%, > 10 min = 0%
            if execution_time < 300:
                score += 0.2
            elif execution_time < 600:
                score += 0.1

        return min(1.0, score)

    def check_indexing_status(self, task_id: str, timeout: int = 5) -> Dict[str, Any]:
        """
        Check status of indexing task

        Returns:
            Task status dict
        """
        if not self.enabled or not task_id:
            return {}

        try:
            response = requests.get(
                f"{RAG_WRITER_URL}/api/v1/task/{task_id}",
                headers={"X-API-Key": RAG_WRITER_API_KEY},
                timeout=timeout,
            )

            if response.ok:
                return response.json()
            else:
                return {"status": "unknown"}

        except Exception as e:
            logger.warning(f"⚠️  Failed to check indexing status: {e}")
            return {"status": "error", "error": str(e)}
