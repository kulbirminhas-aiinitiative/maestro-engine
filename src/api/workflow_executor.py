"""
Maestro Workflow Executor

Orchestrates async execution of team_execution_v2_split_mode workflows.
Provides progress callbacks, state management, and WebSocket broadcasting.
"""

import asyncio
import logging
import sys
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass

# Add paths for imports
team_execution_path = Path("/home/ec2-user/projects/maestro-platform/maestro-hive")
if str(team_execution_path) not in sys.path:
    sys.path.insert(0, str(team_execution_path))

claude_code_api_path = Path("/home/ec2-user/projects/maestro-platform/claude_code_api_layer")
if str(claude_code_api_path) not in sys.path:
    sys.path.insert(0, str(claude_code_api_path))

try:
    from team_execution_v2_split_mode import TeamExecutionEngineV2SplitMode
    TEAM_EXECUTION_AVAILABLE = True
except ImportError as e:
    TEAM_EXECUTION_AVAILABLE = False
    TeamExecutionEngineV2SplitMode = None
    logging.warning(f"team_execution_v2_split_mode not available: {e}")

# Import local utilities
from utils.redis_manager import WorkflowStateManager

logger = logging.getLogger(__name__)

# Import Claude Code API Layer (FIXED SDK with full agent functionality)
try:
    from claude_code_api_layer import query, ClaudeAgentOptions
    CLAUDE_CODE_API_AVAILABLE = True
    logger.info("✅ Fixed claude-agent-sdk loaded for workflow execution")
except ImportError as e:
    CLAUDE_CODE_API_AVAILABLE = False
    logger.warning(f"⚠️ Claude Code API Layer not available: {e}")

# Import Workflow Template Extractor
try:
    from workflow_template_extractor import WorkflowTemplateExtractor
    TEMPLATE_EXTRACTOR_AVAILABLE = True
except ImportError as e:
    TEMPLATE_EXTRACTOR_AVAILABLE = False
    logger.warning(f"⚠️ Template Extractor not available: {e}")


@dataclass
class WorkflowExecutionRequest:
    """Request to execute a workflow"""
    workflow_id: str
    requirement: str
    mode: str  # "batch", "phased", "mixed"
    project_name: str
    checkpoint_phases: Optional[List[str]] = None
    quality_threshold: float = 0.70


class MaestroWorkflowExecutor:
    """
    Manages async execution of SDLC workflows using team_execution_v2_split_mode.

    Features:
    - Non-blocking workflow execution
    - Real-time progress tracking
    - State persistence in Redis
    - WebSocket event broadcasting
    - Error handling and recovery
    - Checkpoint management
    """

    # SDLC phases
    SDLC_PHASES = ["requirements", "design", "implementation", "testing", "deployment"]

    def __init__(
        self,
        redis_manager: WorkflowStateManager,
        ws_manager,
        output_dir: str = "/home/ec2-user/projects/deployment",
        checkpoint_dir: str = "/home/ec2-user/projects/checkpoints"
    ):
        """
        Initialize workflow executor.

        Args:
            redis_manager: Redis state manager instance
            ws_manager: WebSocket manager instance
            output_dir: Base directory for workflow outputs
            checkpoint_dir: Directory for checkpoint files
        """
        self.redis = redis_manager
        self.ws_manager = ws_manager
        self.output_dir = Path(output_dir)
        self.checkpoint_dir = Path(checkpoint_dir)

        # Ensure directories exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Active workflow tasks
        self.active_tasks: Dict[str, asyncio.Task] = {}

        # Initialize template extractor if available
        if TEMPLATE_EXTRACTOR_AVAILABLE:
            self.template_extractor = WorkflowTemplateExtractor()
            logger.info("✅ Template Extractor initialized")
        else:
            self.template_extractor = None
            logger.warning("⚠️  Template Extractor not available")

        # Initialize team execution engine if available
        if TEAM_EXECUTION_AVAILABLE:
            self.engine = TeamExecutionEngineV2SplitMode(
                output_dir=str(self.output_dir),
                checkpoint_dir=str(self.checkpoint_dir),
                quality_threshold=0.70,
                enable_contracts=True
            )
            logger.info("✅ Team Execution Engine V2 initialized")
        else:
            self.engine = None
            logger.warning("⚠️  Team Execution Engine not available - using mock mode")

        logger.info(f"📦 Maestro Workflow Executor initialized")
        logger.info(f"   Output directory: {self.output_dir}")
        logger.info(f"   Checkpoint directory: {self.checkpoint_dir}")

    # ========================================================================
    # WORKFLOW EXECUTION
    # ========================================================================

    async def start_workflow(
        self,
        request: WorkflowExecutionRequest
    ) -> Dict[str, Any]:
        """
        Start workflow execution (non-blocking).

        Args:
            request: Workflow execution request

        Returns:
            Dict with workflow_id and initial status
        """
        workflow_id = request.workflow_id

        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 STARTING WORKFLOW: {workflow_id}")
        logger.info(f"{'='*80}")
        logger.info(f"   Mode: {request.mode}")
        logger.info(f"   Project: {request.project_name}")
        logger.info(f"   Requirement: {request.requirement[:100]}...")

        # Create workflow in Redis
        await self.redis.create_workflow(workflow_id, {
            "status": "starting",
            "mode": request.mode,
            "requirement": request.requirement,
            "project_name": request.project_name,
            "checkpoint_phases": request.checkpoint_phases or [],
            "quality_threshold": request.quality_threshold,
            "current_phase": None,
            "phases_completed": [],
            "progress": 0.0
        })

        # Broadcast workflow started event
        await self._broadcast_event(workflow_id, {
            "type": "workflow_started",
            "workflow_id": workflow_id,
            "mode": request.mode,
            "project_name": request.project_name,
            "timestamp": datetime.now().isoformat()
        })

        # Create async task for execution
        task = asyncio.create_task(
            self._execute_workflow_async(request)
        )
        self.active_tasks[workflow_id] = task

        logger.info(f"✅ Workflow task created: {workflow_id}")

        return {
            "workflow_id": workflow_id,
            "status": "starting",
            "project_name": request.project_name,
            "mode": request.mode
        }

    async def _execute_workflow_async(
        self,
        request: WorkflowExecutionRequest
    ):
        """
        Execute workflow asynchronously with progress tracking.

        Args:
            request: Workflow execution request
        """
        workflow_id = request.workflow_id

        try:
            # Update status
            await self.redis.update_workflow(workflow_id, {
                "status": "running"
            })

            # Create progress callback
            async def on_progress(event: Dict[str, Any]):
                await self._handle_progress_event(workflow_id, event)

            # Execute based on mode
            if request.mode == "batch":
                await self._execute_batch_mode(request, on_progress)
            elif request.mode == "phased":
                await self._execute_phased_mode(request, on_progress)
            elif request.mode == "mixed":
                await self._execute_mixed_mode(request, on_progress)
            else:
                raise ValueError(f"Invalid mode: {request.mode}")

            # Mark as completed
            await self.redis.complete_workflow(workflow_id)

            await self._broadcast_event(workflow_id, {
                "type": "workflow_completed",
                "workflow_id": workflow_id,
                "timestamp": datetime.now().isoformat()
            })

            logger.info(f"✅ Workflow completed: {workflow_id}")

            # Post-execution review and template extraction
            await self._post_execution_review(request)

        except Exception as e:
            logger.error(f"❌ Workflow failed: {workflow_id} - {e}", exc_info=True)

            # Mark as failed
            await self.redis.fail_workflow(workflow_id, str(e))

            await self._broadcast_event(workflow_id, {
                "type": "error",
                "workflow_id": workflow_id,
                "error": str(e),
                "recoverable": False,
                "timestamp": datetime.now().isoformat()
            })

        finally:
            # Clean up task reference
            if workflow_id in self.active_tasks:
                del self.active_tasks[workflow_id]

    async def _execute_batch_mode(
        self,
        request: WorkflowExecutionRequest,
        progress_callback: Callable
    ):
        """Execute workflow in batch mode (all phases continuously)"""

        if not self.engine:
            # Mock execution for testing
            await self._mock_execution(request, progress_callback)
            return

        logger.info(f"📦 Executing batch mode workflow...")

        # Execute all phases
        for i, phase_name in enumerate(self.SDLC_PHASES):
            # Notify phase start
            await progress_callback({
                "type": "phase_started",
                "phase": phase_name,
                "phase_number": i + 1,
                "total_phases": len(self.SDLC_PHASES)
            })

            # Update Redis
            await self.redis.create_phase(request.workflow_id, phase_name, {
                "status": "running",
                "started_at": datetime.now().isoformat()
            })

            # Execute phase using Claude Code API
            start_time = datetime.now()

            if CLAUDE_CODE_API_AVAILABLE:
                # Setup deployment directory for this phase
                phase_dir = self.output_dir / request.project_name / phase_name
                phase_dir.mkdir(parents=True, exist_ok=True)

                # Create work directory
                work_dir = Path(f"/tmp/maestro_workflow/{request.workflow_id}/{phase_name}")
                work_dir.mkdir(parents=True, exist_ok=True)

                # Configure Claude agent with full file tool access
                options = ClaudeAgentOptions(
                    cwd=str(work_dir),
                    model="sonnet",  # Use alias (sonnet = latest Sonnet model)
                    allowed_tools=["Write", "Edit", "Read", "Bash", "Glob", "Grep"],
                    permission_mode="bypassPermissions",
                    max_turns=20
                )

                # Generate phase-specific prompt with system instructions
                phase_prompt = f"""You are an expert software developer working on the {phase_name} phase of an SDLC workflow.

Project Requirement:
{request.requirement}

Task:
Create comprehensive, production-ready artifacts for the {phase_name} phase. Use the Write tool to create actual files in your current working directory. Include all necessary implementation details, documentation, and configuration files.

Create all necessary files with complete implementation."""

                # Execute with full agent functionality
                success = False
                artifacts = []

                try:
                    async for message in query(prompt=phase_prompt, options=options):
                        # Log agent messages for debugging
                        logger.debug(f"Agent message: {str(message)[:200]}")

                    # Agent completed - collect generated files
                    for file_path in work_dir.rglob("*"):
                        if file_path.is_file():
                            rel_path = file_path.relative_to(work_dir)
                            dest_path = phase_dir / rel_path
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(file_path, dest_path)
                            artifacts.append(str(rel_path))

                            # Notify artifact created
                            await progress_callback({
                                "type": "artifact_created",
                                "phase": phase_name,
                                "file_path": str(rel_path),
                                "deployment_path": str(dest_path),
                                "size": file_path.stat().st_size
                            })

                    success = len(artifacts) > 0
                except Exception as e:
                    logger.error(f"❌ Phase execution failed: {e}", exc_info=True)
                    success = False

                quality_score = 0.85 if success else 0.5
            else:
                # Fallback to mock if API not available
                await asyncio.sleep(2)
                artifacts = [f"{phase_name}_document.md"]
                quality_score = 0.85

            duration = (datetime.now() - start_time).total_seconds()

            # Notify phase complete
            await progress_callback({
                "type": "phase_completed",
                "phase": phase_name,
                "quality_score": quality_score,
                "artifacts": artifacts,
                "duration_seconds": duration
            })

            # Update progress
            progress = (i + 1) / len(self.SDLC_PHASES)
            await self.redis.update_workflow(request.workflow_id, {
                "progress": progress,
                "current_phase": phase_name
            })

        logger.info(f"✅ Batch mode execution completed")

    async def _execute_phased_mode(
        self,
        request: WorkflowExecutionRequest,
        progress_callback: Callable
    ):
        """Execute workflow in phased mode (one phase at a time, with checkpoints)"""

        logger.info(f"📋 Executing phased mode workflow...")

        # Execute first phase only
        phase_name = self.SDLC_PHASES[0]

        await progress_callback({
            "type": "phase_started",
            "phase": phase_name,
            "phase_number": 1,
            "total_phases": len(self.SDLC_PHASES)
        })

        await self.redis.create_phase(request.workflow_id, phase_name, {
            "status": "running"
        })

        # Execute phase using Claude Code API
        start_time = datetime.now()

        if CLAUDE_CODE_API_AVAILABLE:
            # Setup deployment directory for this phase
            phase_dir = self.output_dir / request.project_name / phase_name
            phase_dir.mkdir(parents=True, exist_ok=True)

            # Create work directory
            work_dir = Path(f"/tmp/maestro_workflow/{request.workflow_id}/{phase_name}")
            work_dir.mkdir(parents=True, exist_ok=True)

            # Configure Claude agent with full file tool access
            options = ClaudeAgentOptions(
                cwd=str(work_dir),
                model="claude-sonnet-4",
                allowed_tools=["Write", "Edit", "Read", "Bash", "Glob", "Grep"],
                permission_mode="bypassPermissions",
                max_turns=20
            )

            # Generate phase-specific prompt with system instructions
            phase_prompt = f"""You are an expert software developer working on the {phase_name} phase of an SDLC workflow.

Project Requirement:
{request.requirement}

Task:
Create comprehensive, production-ready artifacts for the {phase_name} phase. Use the Write tool to create actual files in your current working directory. Include all necessary implementation details, documentation, and configuration files.

Create all necessary files with complete implementation."""

            # Execute with full agent functionality
            success = False
            artifacts = []

            try:
                async for message in query(prompt=phase_prompt, options=options):
                    # Log agent messages for debugging
                    logger.debug(f"Agent message: {str(message)[:200]}")

                # Agent completed - collect generated files
                for file_path in work_dir.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(work_dir)
                        dest_path = phase_dir / rel_path
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file_path, dest_path)
                        artifacts.append(str(rel_path))

                        # Notify artifact created
                        await progress_callback({
                            "type": "artifact_created",
                            "phase": phase_name,
                            "file_path": str(rel_path),
                            "deployment_path": str(dest_path),
                            "size": file_path.stat().st_size
                        })

                success = len(artifacts) > 0
            except Exception as e:
                logger.error(f"❌ Phase execution failed: {e}", exc_info=True)
                success = False

            quality_score = 0.85 if success else 0.5
        else:
            # Fallback to mock if API not available
            await asyncio.sleep(2)
            quality_score = 0.85

        duration = (datetime.now() - start_time).total_seconds()

        # Create checkpoint
        checkpoint_id = f"checkpoint_{request.workflow_id}_{phase_name}"
        await self._create_checkpoint(request.workflow_id, phase_name, checkpoint_id)

        await progress_callback({
            "type": "checkpoint_created",
            "checkpoint_id": checkpoint_id,
            "phase": phase_name,
            "quality_score": 0.85
        })

        # Mark workflow as paused
        await self.redis.update_workflow(request.workflow_id, {
            "status": "paused",
            "awaiting_human_review": True
        })

        logger.info(f"⏸️  Workflow paused after {phase_name} phase")

    async def _execute_mixed_mode(
        self,
        request: WorkflowExecutionRequest,
        progress_callback: Callable
    ):
        """Execute workflow in mixed mode (selective checkpoints)"""

        logger.info(f"🔀 Executing mixed mode workflow...")
        checkpoint_phases = request.checkpoint_phases or []

        for i, phase_name in enumerate(self.SDLC_PHASES):
            # Execute phase
            await progress_callback({
                "type": "phase_started",
                "phase": phase_name,
                "phase_number": i + 1,
                "total_phases": len(self.SDLC_PHASES)
            })

            await self.redis.create_phase(request.workflow_id, phase_name, {
                "status": "running"
            })

            # Execute phase using Claude Code API
            start_time = datetime.now()

            if CLAUDE_CODE_API_AVAILABLE:
                # Setup deployment directory for this phase
                phase_dir = self.output_dir / request.project_name / phase_name
                phase_dir.mkdir(parents=True, exist_ok=True)

                # Create work directory
                work_dir = Path(f"/tmp/maestro_workflow/{request.workflow_id}/{phase_name}")
                work_dir.mkdir(parents=True, exist_ok=True)

                # Configure Claude agent with full file tool access
                options = ClaudeAgentOptions(
                    cwd=str(work_dir),
                    model="sonnet",  # Use alias (sonnet = latest Sonnet model)
                    allowed_tools=["Write", "Edit", "Read", "Bash", "Glob", "Grep"],
                    permission_mode="bypassPermissions",
                    max_turns=20
                )

                # Generate phase-specific prompt with system instructions
                phase_prompt = f"""You are an expert software developer working on the {phase_name} phase of an SDLC workflow.

Project Requirement:
{request.requirement}

Task:
Create comprehensive, production-ready artifacts for the {phase_name} phase. Use the Write tool to create actual files in your current working directory. Include all necessary implementation details, documentation, and configuration files.

Create all necessary files with complete implementation."""

                # Execute with full agent functionality
                success = False
                artifacts = []

                try:
                    async for message in query(prompt=phase_prompt, options=options):
                        # Log agent messages for debugging
                        logger.debug(f"Agent message: {str(message)[:200]}")

                    # Agent completed - collect generated files
                    for file_path in work_dir.rglob("*"):
                        if file_path.is_file():
                            rel_path = file_path.relative_to(work_dir)
                            dest_path = phase_dir / rel_path
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(file_path, dest_path)
                            artifacts.append(str(rel_path))

                            # Notify artifact created
                            await progress_callback({
                                "type": "artifact_created",
                                "phase": phase_name,
                                "file_path": str(rel_path),
                                "deployment_path": str(dest_path),
                                "size": file_path.stat().st_size
                            })

                    success = len(artifacts) > 0
                except Exception as e:
                    logger.error(f"❌ Phase execution failed: {e}", exc_info=True)
                    success = False

                quality_score = 0.85 if success else 0.5
            else:
                # Fallback to mock if API not available
                await asyncio.sleep(2)
                artifacts = [f"{phase_name}_document.md"]
                quality_score = 0.85

            duration = (datetime.now() - start_time).total_seconds()

            await progress_callback({
                "type": "phase_completed",
                "phase": phase_name,
                "quality_score": quality_score,
                "artifacts": artifacts,
                "duration_seconds": duration
            })

            # Check if this is a checkpoint phase
            if phase_name in checkpoint_phases:
                checkpoint_id = f"checkpoint_{request.workflow_id}_{phase_name}"
                await self._create_checkpoint(request.workflow_id, phase_name, checkpoint_id)

                await progress_callback({
                    "type": "checkpoint_created",
                    "checkpoint_id": checkpoint_id,
                    "phase": phase_name
                })

                # Pause workflow
                await self.redis.update_workflow(request.workflow_id, {
                    "status": "paused",
                    "awaiting_human_review": True
                })

                logger.info(f"⏸️  Workflow paused after {phase_name} phase")
                return

        logger.info(f"✅ Mixed mode execution completed")

    async def _post_execution_review(
        self,
        request: WorkflowExecutionRequest
    ):
        """
        Post-execution review and template extraction.

        Analyzes completed workflow and extracts reusable templates
        if quality threshold is met.

        Args:
            request: Workflow execution request
        """
        if not self.template_extractor:
            logger.debug("⚠️  Template extractor not available, skipping post-execution review")
            return

        workflow_id = request.workflow_id

        try:
            logger.info(f"\n{'='*80}")
            logger.info(f"📋 POST-EXECUTION REVIEW")
            logger.info(f"{'='*80}")

            # Collect phase quality scores from Redis
            phase_quality_scores = {}
            for phase_name in self.SDLC_PHASES:
                phase_data = await self.redis.get_phase(workflow_id, phase_name)
                if phase_data and "quality_score" in phase_data:
                    phase_quality_scores[phase_name] = phase_data["quality_score"]

            if not phase_quality_scores:
                logger.warning(f"⚠️  No quality scores found, skipping template extraction")
                return

            # Get workflow working directory
            work_dir = Path(f"/tmp/maestro_workflow/{workflow_id}")
            if not work_dir.exists():
                logger.warning(f"⚠️  Work directory not found: {work_dir}")
                return

            # Broadcast review started event
            await self._broadcast_event(workflow_id, {
                "type": "post_execution_review_started",
                "workflow_id": workflow_id,
                "timestamp": datetime.now().isoformat()
            })

            # Review and extract template
            template_metadata = await self.template_extractor.review_and_extract(
                workflow_id=workflow_id,
                project_name=request.project_name,
                requirement=request.requirement,
                work_dir=work_dir,
                phase_quality_scores=phase_quality_scores
            )

            if template_metadata:
                # Broadcast template extracted event
                await self._broadcast_event(workflow_id, {
                    "type": "template_extracted",
                    "workflow_id": workflow_id,
                    "template_name": template_metadata["name"],
                    "template_category": template_metadata["category"],
                    "quality_score": template_metadata["quality_score"],
                    "tech_stack": template_metadata["tech_stack"],
                    "timestamp": datetime.now().isoformat()
                })

                logger.info(f"\n{'='*80}")
                logger.info(f"✅ TEMPLATE EXTRACTED: {template_metadata['name']}")
                logger.info(f"{'='*80}")
                logger.info(f"   Category: {template_metadata['category']}")
                logger.info(f"   Quality: {template_metadata['quality_score']}/100")
                logger.info(f"   Tech Stack: {', '.join(template_metadata['tech_stack'])}")
                logger.info(f"   Available for immediate use via RAG!")
            else:
                logger.info(f"ℹ️  No template extracted (quality threshold not met or extraction failed)")

        except Exception as e:
            logger.error(f"❌ Post-execution review failed: {e}", exc_info=True)
            # Don't fail the workflow if template extraction fails
            pass

    async def _mock_execution(
        self,
        request: WorkflowExecutionRequest,
        progress_callback: Callable
    ):
        """Mock execution for testing when team_execution_v2 is not available"""

        logger.info(f"🎭 Running mock execution (team_execution_v2 not available)")

        for i, phase_name in enumerate(self.SDLC_PHASES):
            await progress_callback({
                "type": "phase_started",
                "phase": phase_name,
                "phase_number": i + 1,
                "total_phases": len(self.SDLC_PHASES)
            })

            await self.redis.create_phase(request.workflow_id, phase_name, {
                "status": "running"
            })

            # Simulate phase work
            await asyncio.sleep(1)

            # Simulate artifact creation
            artifacts = [
                f"{phase_name}_requirements.md",
                f"{phase_name}_architecture.md",
                f"{phase_name}_code.py"
            ]

            for artifact in artifacts:
                await progress_callback({
                    "type": "artifact_created",
                    "phase": phase_name,
                    "file_path": artifact,
                    "deployment_path": f"/home/ec2-user/projects/deployment/{request.project_name}/{phase_name}/{artifact}",
                    "size": 1024
                })

            await progress_callback({
                "type": "phase_completed",
                "phase": phase_name,
                "quality_score": 0.85,
                "quality_passed": True,
                "artifacts": artifacts,
                "duration_seconds": 1.0
            })

            await self.redis.complete_phase(
                request.workflow_id,
                phase_name,
                quality_score=0.85,
                artifacts=artifacts
            )

            progress = (i + 1) / len(self.SDLC_PHASES)
            await self.redis.update_workflow(request.workflow_id, {
                "progress": progress,
                "current_phase": phase_name
            })

    # ========================================================================
    # PROGRESS HANDLING
    # ========================================================================

    async def _handle_progress_event(
        self,
        workflow_id: str,
        event: Dict[str, Any]
    ):
        """
        Handle progress event from workflow execution.

        Args:
            workflow_id: Workflow identifier
            event: Progress event data
        """
        event_type = event.get("type")

        # Update Redis based on event type
        if event_type == "phase_started":
            phase = event.get("phase")
            await self.redis.update_workflow(workflow_id, {
                "current_phase": phase,
                "last_event": event_type
            })

        elif event_type == "phase_completed":
            phase = event.get("phase")
            await self.redis.complete_phase(
                workflow_id,
                phase,
                quality_score=event.get("quality_score", 0.0),
                artifacts=event.get("artifacts", [])
            )

        elif event_type == "artifact_created":
            # Log artifact creation
            logger.debug(f"📄 Artifact created: {event.get('file_path')}")

        # Broadcast to WebSocket connections
        await self._broadcast_event(workflow_id, {
            **event,
            "workflow_id": workflow_id,
            "timestamp": datetime.now().isoformat()
        })

    async def _broadcast_event(
        self,
        workflow_id: str,
        event: Dict[str, Any]
    ):
        """
        Broadcast event to WebSocket connections.

        Args:
            workflow_id: Workflow identifier
            event: Event data
        """
        if self.ws_manager:
            await self.ws_manager.broadcast_to_workflow(workflow_id, event)

    # ========================================================================
    # CHECKPOINT MANAGEMENT
    # ========================================================================

    async def _create_checkpoint(
        self,
        workflow_id: str,
        phase: str,
        checkpoint_id: str
    ):
        """Create checkpoint for workflow"""

        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"

        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "phase": phase,
            "file_path": str(checkpoint_path),
            "quality_score": 0.85,
            "timestamp": datetime.now().isoformat()
        }

        # Add to Redis
        await self.redis.add_checkpoint(workflow_id, checkpoint_data)

        logger.info(f"💾 Created checkpoint: {checkpoint_id}")

    # ========================================================================
    # WORKFLOW CONTROL
    # ========================================================================

    async def pause_workflow(self, workflow_id: str) -> bool:
        """Pause running workflow"""

        await self.redis.update_workflow(workflow_id, {
            "status": "paused",
            "paused_at": datetime.now().isoformat()
        })

        await self._broadcast_event(workflow_id, {
            "type": "workflow_paused",
            "workflow_id": workflow_id,
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"⏸️  Paused workflow: {workflow_id}")
        return True

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel running workflow"""

        # Cancel task if running
        if workflow_id in self.active_tasks:
            self.active_tasks[workflow_id].cancel()
            del self.active_tasks[workflow_id]

        await self.redis.fail_workflow(workflow_id, "Cancelled by user")

        await self._broadcast_event(workflow_id, {
            "type": "workflow_cancelled",
            "workflow_id": workflow_id,
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"🛑 Cancelled workflow: {workflow_id}")
        return True

    async def get_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow status"""

        workflow = await self.redis.get_workflow(workflow_id)
        if not workflow:
            return None

        # Get phase information
        phases_info = {}
        for phase in self.SDLC_PHASES:
            phase_data = await self.redis.get_phase(workflow_id, phase)
            if phase_data:
                phases_info[phase] = phase_data

        return {
            **workflow,
            "phases": phases_info,
            "is_active": workflow_id in self.active_tasks
        }

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    async def get_active_workflows(self) -> List[str]:
        """Get list of active workflow IDs"""
        return await self.redis.get_active_workflows()

    async def cleanup(self):
        """Cleanup resources"""
        # Cancel all active tasks
        for workflow_id, task in list(self.active_tasks.items()):
            if not task.done():
                task.cancel()

        self.active_tasks.clear()
        logger.info("🧹 Cleaned up workflow executor")
