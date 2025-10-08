#!/usr/bin/env python3
"""
Persona Orchestrator for MAESTRO Engine

Orchestrates persona execution with the new Schema v3.0 persona system.
Integrates with unified BFF for Guardian workflow execution.
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add maestro-engine to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import persona system
from src.personas import (
    MaestroPersonaAdapter,
    PersonaCategory,
    PersonaDefinition,
    PersonaRegistry,
    get_adapter,
)

# Import Claude Code SDK for persona execution
try:
    from claude_code_sdk import ClaudeCodeOptions, query

    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False
    logging.warning("Claude Code SDK not available - using mock execution")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PersonaExecutionResult:
    """Result of a single persona execution"""

    def __init__(
        self,
        persona_id: str,
        success: bool,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        execution_time: float = 0.0,
        files_created: List[str] = None,
    ):
        self.persona_id = persona_id
        self.success = success
        self.output = output or {}
        self.error = error
        self.execution_time = execution_time
        self.files_created = files_created or []
        self.timestamp = datetime.now()


class PersonaOrchestrator:
    """
    Orchestrates execution of multiple personas in the correct order.

    Features:
    - Dependency-based execution ordering
    - Progress tracking via callbacks
    - Redis state integration
    - MCP event emission
    """

    def __init__(self, work_dir: Path, session_id: str, redis_state=None, ws_manager=None):
        """
        Initialize orchestrator

        Args:
            work_dir: Working directory for generated files
            session_id: Session ID for tracking
            redis_state: Redis state manager (optional)
            ws_manager: WebSocket manager for progress updates (optional)
        """
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

        self.session_id = session_id
        self.redis_state = redis_state
        self.ws_manager = ws_manager

        # Load persona system
        self.adapter = get_adapter()
        self.registry = PersonaRegistry()

        # Execution state
        self.results: List[PersonaExecutionResult] = []
        self.context: Dict[str, Any] = {}

    async def initialize(self):
        """Load personas"""
        await self.registry.load_all()
        logger.info(f"✅ Loaded {len(self.registry.personas)} personas")

    async def execute_workflow(
        self,
        requirement: str,
        persona_ids: Optional[List[str]] = None,
        enable_progress_updates: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute a workflow with specified personas

        Args:
            requirement: User requirement/prompt
            persona_ids: List of personas to execute (None = all)
            enable_progress_updates: Send progress via WebSocket

        Returns:
            Dictionary with execution results
        """
        start_time = datetime.now()

        logger.info(f"🚀 Starting workflow execution for session: {self.session_id}")
        logger.info(f"📋 Requirement: {requirement[:100]}...")

        # Determine personas to execute
        if persona_ids is None:
            # Default: comprehensive SDLC workflow
            persona_ids = [
                "requirement_analyst",
                "solution_architect",
                "ui_ux_designer",
                "frontend_developer",
                "backend_developer",
                "database_administrator",
                "devops_engineer",
                "qa_engineer",
                "security_specialist",
                "technical_writer",
            ]

        logger.info(f"👥 Personas: {', '.join(persona_ids)}")

        # Get execution order
        execution_order = self.adapter.get_execution_order(persona_ids)
        logger.info(f"📊 Execution order: {' → '.join(execution_order)}")

        # Send initial progress
        if enable_progress_updates and self.ws_manager:
            await self._send_progress(
                {
                    "type": "workflow_started",
                    "session_id": self.session_id,
                    "total_personas": len(execution_order),
                    "execution_order": execution_order,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Execute personas in order
        for idx, persona_id in enumerate(execution_order, 1):
            logger.info(f"\n{'=' * 80}")
            logger.info(f"🤖 Executing {idx}/{len(execution_order)}: {persona_id}")
            logger.info(f"{'=' * 80}")

            # Send persona start
            if enable_progress_updates and self.ws_manager:
                await self._send_progress(
                    {
                        "type": "persona_started",
                        "persona_id": persona_id,
                        "progress": idx / len(execution_order),
                        "current": idx,
                        "total": len(execution_order),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # Execute persona
            result = await self._execute_persona(persona_id, requirement, self.context)

            self.results.append(result)

            # Update context with persona output
            if result.success and result.output:
                self.context[persona_id] = result.output

            # Send persona complete
            if enable_progress_updates and self.ws_manager:
                await self._send_progress(
                    {
                        "type": "persona_completed",
                        "persona_id": persona_id,
                        "success": result.success,
                        "execution_time": result.execution_time,
                        "files_created": len(result.files_created),
                        "progress": idx / len(execution_order),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # Log result
            status = "✅" if result.success else "❌"
            logger.info(f"{status} {persona_id}: {result.execution_time:.2f}s")

            if result.error:
                logger.error(f"   Error: {result.error}")

        # Calculate summary
        total_time = (datetime.now() - start_time).total_seconds()
        successful = sum(1 for r in self.results if r.success)
        failed = len(self.results) - successful
        total_files = sum(len(r.files_created) for r in self.results)

        summary = {
            "session_id": self.session_id,
            "success": failed == 0,
            "total_personas": len(execution_order),
            "successful": successful,
            "failed": failed,
            "total_time": total_time,
            "total_files": total_files,
            "work_dir": str(self.work_dir),
            "results": [
                {
                    "persona_id": r.persona_id,
                    "success": r.success,
                    "execution_time": r.execution_time,
                    "files_created": r.files_created,
                    "error": r.error,
                }
                for r in self.results
            ],
        }

        # Send workflow complete
        if enable_progress_updates and self.ws_manager:
            await self._send_progress(
                {"type": "workflow_completed", **summary, "timestamp": datetime.now().isoformat()}
            )

        logger.info(f"\n{'=' * 80}")
        logger.info(f"✅ Workflow completed in {total_time:.2f}s")
        logger.info(f"📊 {successful}/{len(execution_order)} personas successful")
        logger.info(f"📁 {total_files} files created in {self.work_dir}")
        logger.info(f"{'=' * 80}\n")

        return summary

    async def _execute_persona(
        self, persona_id: str, requirement: str, context: Dict[str, Any]
    ) -> PersonaExecutionResult:
        """
        Execute a single persona

        Args:
            persona_id: Persona to execute
            requirement: User requirement
            context: Context from previous personas

        Returns:
            PersonaExecutionResult
        """
        start_time = datetime.now()

        try:
            # Get persona definition
            persona_legacy = self.adapter.get_persona(persona_id)
            persona = self.registry.get(persona_id)

            if not persona or not persona_legacy:
                return PersonaExecutionResult(
                    persona_id=persona_id,
                    success=False,
                    error=f"Persona not found: {persona_id}",
                    execution_time=0.0,
                )

            # Build context prompt from previous personas
            context_prompt = self._build_context_prompt(context)

            # Build persona-specific prompt
            full_prompt = f"""{persona_legacy['system_prompt']}

USER REQUIREMENT:
{requirement}

PREVIOUS WORK (Context from other team members):
{context_prompt}

YOUR TASK:
Execute your role as {persona_legacy['name']}. Create all necessary files and deliverables in the current working directory: {self.work_dir}

Use the Write tool to create actual files with proper paths relative to the working directory.
"""

            # Execute with Claude Code SDK if available
            if CLAUDE_SDK_AVAILABLE:
                result = await self._execute_with_claude_sdk(persona_id, full_prompt)
            else:
                # Mock execution for testing
                result = await self._execute_mock(persona_id)

            execution_time = (datetime.now() - start_time).total_seconds()

            return PersonaExecutionResult(
                persona_id=persona_id,
                success=result["success"],
                output=result.get("output", {}),
                error=result.get("error"),
                execution_time=execution_time,
                files_created=result.get("files_created", []),
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.exception(f"❌ Error executing {persona_id}")

            return PersonaExecutionResult(
                persona_id=persona_id, success=False, error=str(e), execution_time=execution_time
            )

    async def _execute_with_claude_sdk(self, persona_id: str, prompt: str) -> Dict[str, Any]:
        """Execute persona using Claude Code SDK"""

        try:
            options = ClaudeCodeOptions(
                cwd=str(self.work_dir),
                permission_mode="bypassPermissions",
                system_prompt=prompt,
                continue_conversation=False,
            )

            # Execute in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: query(f"Execute as {persona_id}", options=options)
            )

            # Collect created files
            files_created = []
            if self.work_dir.exists():
                for file_path in self.work_dir.rglob("*"):
                    if file_path.is_file():
                        files_created.append(str(file_path.relative_to(self.work_dir)))

            return {"success": True, "output": {"response": result}, "files_created": files_created}

        except Exception as e:
            logger.error(f"Claude SDK execution failed: {e}")
            return {"success": False, "error": str(e), "files_created": []}

    async def _execute_mock(self, persona_id: str) -> Dict[str, Any]:
        """Mock execution for testing"""
        await asyncio.sleep(0.5)  # Simulate work

        # Create mock file
        mock_file = self.work_dir / f"{persona_id}_output.txt"
        mock_file.write_text(f"Mock output from {persona_id}")

        return {
            "success": True,
            "output": {"mock": True, "persona_id": persona_id},
            "files_created": [f"{persona_id}_output.txt"],
        }

    def _build_context_prompt(self, context: Dict[str, Any]) -> str:
        """Build context prompt from previous persona outputs"""
        if not context:
            return "No previous work yet - you are the first persona in the workflow."

        context_lines = []
        for persona_id, output in context.items():
            context_lines.append(f"\n**{persona_id}**:")
            if isinstance(output, dict):
                for key, value in output.items():
                    if isinstance(value, str) and len(value) < 500:
                        context_lines.append(f"  - {key}: {value}")
            else:
                context_lines.append(f"  - {str(output)[:200]}")

        return "\n".join(context_lines)

    async def _send_progress(self, data: Dict[str, Any]):
        """Send progress update via WebSocket"""
        if self.ws_manager and self.session_id:
            try:
                await self.ws_manager.send_message(self.session_id, data)
            except Exception as e:
                logger.warning(f"Failed to send progress update: {e}")


# Example usage
if __name__ == "__main__":

    async def test_orchestrator():
        """Test orchestrator with mock execution"""
        work_dir = Path("/tmp/maestro_test_orchestration")
        session_id = f"test_session_{int(datetime.now().timestamp())}"

        orchestrator = PersonaOrchestrator(work_dir=work_dir, session_id=session_id)

        await orchestrator.initialize()

        result = await orchestrator.execute_workflow(
            requirement="Build a simple task management web application",
            persona_ids=["requirement_analyst", "solution_architect", "frontend_developer"],
            enable_progress_updates=False,
        )

        print(f"\n✅ Test completed: {result['session_id']}")
        print(f"📊 {result['successful']}/{result['total_personas']} successful")
        print(f"⏱️  {result['total_time']:.2f}s")
        print(f"📁 {result['total_files']} files in {result['work_dir']}")

    asyncio.run(test_orchestrator())
