#!/usr/bin/env python3
"""
Hot Claude RAG Session Manager
Manages persistent Claude session with dynamic RAG query capabilities
ONE Claude instance serves as both RAG advisor and file executor
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from claude_agent_sdk import ClaudeAgentOptions, query
    from rag_tools import RAG_TOOLS, get_rag_tools_description
    from unified_claude_tools import (
        create_code_file,
        create_config_file,
        create_documentation,
        create_project_structure,
        save_persona_analysis,
    )

    CLAUDE_SDK_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Claude SDK or RAG tools not available: {e}")
    CLAUDE_SDK_AVAILABLE = False


class HotClaudeRAGSession:
    """
    Hot (persistent) Claude instance with RAG awareness
    - Maintains conversation history
    - Has access to RAG query tools
    - Can generate files
    - Learns from past executions
    """

    def __init__(self, session_id: str = None, project_path=None):
        if not CLAUDE_SDK_AVAILABLE:
            raise ImportError("Claude SDK not available")

        self.session_id = session_id or f"hot_claude_{int(time.time())}"

        # Handle both string and Path objects
        if project_path is None:
            self.project_path = Path(f"hot_claude_output/{self.session_id}")
        elif isinstance(project_path, Path):
            self.project_path = project_path
        else:
            self.project_path = Path(project_path)

        self.project_path.mkdir(parents=True, exist_ok=True)

        self.conversation_history = []
        self.rag_queries_made = []
        self.files_generated = []

        self.system_prompt = self._build_system_prompt()

        from assumption_logger import ASSUMPTION_TOOL

        assumption_tools = [ASSUMPTION_TOOL] if ASSUMPTION_TOOL else []

        self.all_tools = (
            RAG_TOOLS
            + assumption_tools
            + [
                create_code_file,
                create_documentation,
                create_config_file,
                save_persona_analysis,
                create_project_structure,
            ]
        )

        logger.info(f"🔥 Hot Claude RAG Session Initialized: {self.session_id}")
        logger.info(f"📁 Project path: {self.project_path}")
        logger.info(f"🔧 Tools available: {len(self.all_tools)}")

    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt with RAG awareness"""

        rag_tools_desc = get_rag_tools_description()

        system_prompt = f"""
You are a Hot Claude RAG Session - a persistent AI assistant with access to historical project data.

SESSION INFO:
- Session ID: {self.session_id}
- Project Path: {self.project_path}
- Role: RAG-aware advisor AND file executor (unified role)

YOUR CAPABILITIES:

1. **RAG Query Tools** - Query historical project data:
{rag_tools_desc}

2. **Assumption Logging Tool** - Track execution decisions:
   - log_execution_assumption: Log assumptions made during execution
     * USE THIS when making architectural decisions
     * REQUIRED for HIGH/CRITICAL impact assumptions
     * Enables human review and validation
     * Categories: technical, business, architectural, team_composition, scope, requirements, timeline
     * Impact levels: low, medium, high, critical

3. **File Generation Tools** - Create deliverables:
   - create_code_file: Create code files with syntax highlighting
   - create_documentation: Create documentation files
   - create_config_file: Create configuration files
   - create_project_structure: Create directory structures

4. **Conversation Memory** - You maintain context across multiple interactions

SWIFT MVP WORKFLOW (PRIORITY):

1. **⚡ FIRST-STRIKE Query**
   - IMMEDIATELY call get_swift_mvp_plan(requirement) as your FIRST action
   - This gives you complete context in ONE parallel query:
     * Similar projects (what worked)
     * Recommended team (proven combinations)
     * Deliverables template (reusable structure)
     * Execution estimates (time/files)
   - NO need to call individual RAG tools unless you need deeper analysis

2. **📋 Review Synthesized Plan**
   - Examine the opinionated_next_steps
   - Review team recommendations
   - Check historical insights
   - Validate deliverables template

3. **🔍 Log Key Assumptions (REQUIRED for HIGH/CRITICAL impact)**
   - Call log_execution_assumption for important decisions:
     * Architectural choices (framework, database, patterns)
     * Timeline/scope interpretations
     * Team composition decisions
     * Requirement clarifications
   - Include: assumption, impact_level, category, rationale, evidence, alternatives
   - High/Critical assumptions REQUIRE human validation

4. **🚀 Execute Immediately**
   - Use proven patterns from Swift MVP plan
   - Generate deliverables.json from template
   - Create files using historical best practices
   - NO over-analysis - the First-Strike gave you everything

5. **📊 (Optional) Deep-Dive**
   - ONLY use individual RAG tools if you need specific details
   - For most requirements, First-Strike is sufficient

IMPORTANT GUIDELINES:

- **⚡ ALWAYS call get_swift_mvp_plan FIRST** - it orchestrates all critical queries in parallel
- **🔍 LOG assumptions** - especially HIGH/CRITICAL impact decisions for human review
- **🎯 Trust the First-Strike result** - it's synthesized from proven successful projects
- **🚀 Prioritize speed over perfection** - execute with confidence using historical patterns
- **❌ AVOID analysis paralysis** - don't make excessive sequential RAG calls
- **✅ Synthesize intelligently** - combine First-Strike insights with your expertise

You are NOT just following instructions - you are a SWIFT MVP EXECUTOR that uses First-Strike RAG to deliver fast, proven solutions.
"""

        return system_prompt

    async def execute(self, requirement: str, team_members: List[str] = None) -> Dict[str, Any]:
        """
        Execute requirement with RAG awareness using unified Claude tools
        """

        execution_start = time.time()

        logger.info(f"\n{'='*80}")
        logger.info(f"🔥 HOT CLAUDE RAG SESSION EXECUTION")
        logger.info(f"{'='*80}")
        logger.info(f"📋 Requirement: {requirement}")

        result = {
            "success": False,
            "session_id": self.session_id,
            "requirement": requirement,
            "files_generated": [],
            "rag_queries_made": [],
            "execution_time": 0,
            "claude_response": "",
        }

        try:
            # Import unified tools generator
            from unified_claude_tools import generate_with_unified_tools

            logger.info(f"🤖 Using unified Claude tools for generation...")

            claude_start = time.time()

            # Use unified tools generation (proven to work)
            persona_config = {
                "persona": {"name": "Full Stack Web Developer", "role": "senior developer"},
                "enhanced_context": {
                    "requirement": requirement,
                    "team_members": team_members or [],
                },
            }

            generation_result = await generate_with_unified_tools(
                requirement=requirement,
                persona_config=persona_config,
                project_path=str(self.project_path),
                session_id=self.session_id,
            )

            claude_duration = time.time() - claude_start

            files = generation_result.get("generated_files", [])

            result.update(
                {
                    "success": generation_result.get("success", False) and len(files) > 0,
                    "files_generated": files,
                    "rag_queries_made": [],  # RAG integration coming in next version
                    "execution_time": time.time() - execution_start,
                    "claude_response": f"Generated {len(files)} files using unified tools",
                    "claude_duration": claude_duration,
                    "conversation_turns": 1,
                    "file_count": len(files),
                    "method": generation_result.get("method", "unknown"),
                }
            )

            self.files_generated.extend(files)

            logger.info(f"✅ Claude responded in {claude_duration:.2f}s")
            logger.info(f"📁 Files generated: {len(files)}")
            logger.info(f"🔧 Method: {generation_result.get('method', 'unknown')}")

        except Exception as e:
            logger.error(f"❌ Hot Claude execution failed: {e}")
            result["error"] = str(e)

        finally:
            await self._save_session_state(result)

            logger.info(f"{'='*80}")
            logger.info(f"✅ Session execution complete: {result['success']}")
            logger.info(f"⏱️  Total time: {result['execution_time']:.2f}s")
            logger.info(f"{'='*80}\n")

        return result

    def _build_execution_prompt(self, requirement: str, team_members: List[str] = None) -> str:
        """Build execution prompt for Claude"""

        prompt = f"""
I need you to help with the following requirement:

**REQUIREMENT:** {requirement}
"""

        if team_members:
            prompt += f"""

**SUGGESTED TEAM:** {', '.join(team_members)}
(You can query RAG for better recommendations if needed)
"""

        prompt += """

**YOUR TASK (SWIFT MVP APPROACH):**

1. **⚡ FIRST-STRIKE Query (Do This First!):**
   - IMMEDIATELY call get_swift_mvp_plan(requirement)
   - This ONE call orchestrates ALL critical queries in PARALLEL:
     * Similar successful projects
     * Evidence-based team recommendations
     * Proven deliverables template
     * Execution time/file estimates
   - Returns complete synthesized MVP plan in ~2-3 seconds

2. **📋 Review Swift MVP Plan:**
   - Examine opinionated_next_steps
   - Review recommended_team with confidence scores
   - Check historical_insights for proven patterns
   - Validate deliverables_template structure

3. **🔍 Log Key Assumptions:**
   - Use log_execution_assumption for HIGH/CRITICAL decisions
   - Examples to log:
     * "Using FastAPI framework" - if not explicitly stated (technical, medium/high)
     * "MVP timeline is 2 weeks" - timeline estimates (timeline, critical)
     * "User authentication required" - scope additions (requirements, high)
     * "Team of 3 developers" - team decisions (team_composition, medium)
   - Always include: rationale from RAG data, alternatives considered, evidence

4. **🚀 Execute Immediately:**
   - Create deliverables.json from the template provided
   - Generate files using proven patterns from similar projects
   - Use recommended team from First-Strike result
   - NO over-analysis needed - you have everything from First-Strike

5. **📊 (Optional Deep-Dive):**
   - ONLY use individual RAG tools if you need specific details
   - For most requirements, First-Strike provides sufficient context
   - Examples: analyze_historical_failures for risk analysis, query_similar_projects for detailed comparison

6. **✅ Report:**
   - Explain Swift MVP plan insights used
   - Mention key assumptions logged
   - Describe execution approach
   - List files created

**PRIORITY:** Begin by calling get_swift_mvp_plan(requirement) - this is your FIRST action for maximum speed.
"""

        return prompt

    def _extract_files_from_response(self, response: str) -> List[str]:
        """Extract generated files from Claude's response"""

        files = []

        # Ensure project_path is a Path object
        project_dir = (
            Path(self.project_path) if isinstance(self.project_path, str) else self.project_path
        )

        for file_path in project_dir.rglob("*"):
            if file_path.is_file():
                files.append(str(file_path))

        return files

    def _extract_rag_queries_from_history(self) -> List[Dict[str, Any]]:
        """Extract RAG queries made by Claude from conversation history"""

        queries = []

        for entry in self.conversation_history:
            if entry.get("role") == "assistant":
                content = entry.get("content", "")

                if "query_similar_projects" in content:
                    queries.append({"tool": "query_similar_projects"})
                if "get_recommended_team" in content:
                    queries.append({"tool": "get_recommended_team"})
                if "analyze_historical_failures" in content:
                    queries.append({"tool": "analyze_historical_failures"})
                if "get_deliverables_template" in content:
                    queries.append({"tool": "get_deliverables_template"})

        return queries

    async def followup(self, followup_prompt: str) -> Dict[str, Any]:
        """
        Continue conversation in same session
        Claude has full context of previous interactions
        """

        logger.info(f"💬 Follow-up query: {followup_prompt}")

        result = {"success": False, "followup_prompt": followup_prompt, "response": ""}

        try:
            response_text = ""
            async for message in query(
                prompt=followup_prompt,
                options=ClaudeAgentOptions(
                    cwd=str(self.project_path),
                    system_prompt=self.system_prompt,
                    continue_conversation=True,
                ),
            ):
                if hasattr(message, "text"):
                    response_text += message.text
                elif hasattr(message, "content"):
                    if isinstance(message.content, str):
                        response_text += message.content

            response = response_text

            self.conversation_history.append({"role": "user", "content": followup_prompt})
            self.conversation_history.append({"role": "assistant", "content": response})

            result.update(
                {
                    "success": True,
                    "response": response,
                    "conversation_turns": len(self.conversation_history) // 2,
                }
            )

            logger.info(f"✅ Follow-up complete")

        except Exception as e:
            logger.error(f"❌ Follow-up failed: {e}")
            result["error"] = str(e)

        return result

    async def _save_session_state(self, execution_result: Dict[str, Any]):
        """Save session state for persistence"""

        session_state = {
            "session_id": self.session_id,
            "project_path": str(self.project_path),
            "conversation_turns": len(self.conversation_history) // 2,
            "files_generated": self.files_generated,
            "rag_queries_made": self.rag_queries_made,
            "last_execution": execution_result,
            "timestamp": datetime.now().isoformat(),
        }

        state_file = self.project_path / "session_state.json"
        with open(state_file, "w") as f:
            json.dump(session_state, f, indent=2, default=str)

        logger.info(f"💾 Session state saved: {state_file}")

    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of current session"""

        return {
            "session_id": self.session_id,
            "conversation_turns": len(self.conversation_history) // 2,
            "files_generated": len(self.files_generated),
            "rag_queries_made": len(self.rag_queries_made),
            "project_path": str(self.project_path),
            "tools_available": len(self.all_tools),
        }


async def create_hot_claude_session(
    session_id: str = None, project_path: str = None
) -> HotClaudeRAGSession:
    """Factory function to create hot Claude session"""

    session = HotClaudeRAGSession(session_id, project_path)

    logger.info(f"🔥 Created Hot Claude RAG Session")
    summary = session.get_session_summary()

    for key, value in summary.items():
        logger.info(f"   {key}: {value}")

    return session
