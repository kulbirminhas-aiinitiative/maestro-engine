#!/usr/bin/env python3
"""
Celery Tasks for MAESTRO Workflow Execution
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from celery_config import celery_app, get_redis_client
from config import get_settings
from orchestration import AutonomousSDLCEngineV3Resumable, SessionManager

logger = logging.getLogger(__name__)
redis_client = get_redis_client()


def update_job_status(job_id: str, status: str, **kwargs):
    """Update job status in Redis"""
    data = {"status": status, "updated_at": datetime.now().isoformat(), **kwargs}

    for key, value in data.items():
        redis_client.hset(
            f"job:{job_id}",
            key,
            json.dumps(value) if isinstance(value, (dict, list)) else str(value),
        )

    logger.info(f"📊 Job {job_id} status: {status}")


@celery_app.task(
    bind=True, name="celery_tasks.execute_workflow_task", max_retries=3, default_retry_delay=60
)
def execute_workflow_task(self, request_data: Dict[str, Any]):
    """
    Celery task to execute MAESTRO workflow

    Args:
        self: Celery task instance
        request_data: Workflow request data
            {
                'requirement': str,
                'session_id': str,
                'persona_ids': List[str],
                'enable_rag': bool,
                'enable_mcp': bool
            }

    Returns:
        Workflow execution result
    """

    session_id = request_data["session_id"]
    job_id = self.request.id  # Celery task ID

    logger.info(f"🚀 Starting workflow execution for session: {session_id}")

    try:
        # Update status: STARTED
        update_job_status(
            job_id,
            "STARTED",
            session_id=session_id,
            started_at=datetime.now().isoformat(),
            total_personas=len(request_data.get("persona_ids", [])),
        )

        # Get settings
        settings = get_settings()
        work_dir = settings.get_project_dir(session_id)

        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Load personas in worker process
            from personas import get_adapter

            adapter = get_adapter()
            loop.run_until_complete(adapter.ensure_loaded())
            logger.info(f"📦 Loaded {len(adapter.registry.personas)} personas in worker")

            # Personas to execute
            from config import get_workflow_config

            workflow_config = get_workflow_config()
            personas = request_data.get("persona_ids") or workflow_config.GUARDIAN_WORKFLOW.personas

            # Create engine
            session_manager = SessionManager()
            engine = AutonomousSDLCEngineV3Resumable(
                selected_personas=personas,
                output_dir=str(work_dir),
                session_manager=session_manager,
                enable_rag=request_data.get("enable_rag", True),
            )

            # Update progress callback
            def progress_callback(persona: str, progress: int, total: int):
                update_job_status(
                    job_id,
                    "PROGRESS",
                    current_persona=persona,
                    progress_percent=(progress / total) * 100,
                    personas_completed=progress,
                    personas_total=total,
                )

            result = loop.run_until_complete(
                engine.execute(
                    requirement=request_data["requirement"],
                    session_id=session_id,
                    resume_session_id=None,
                )
            )
        finally:
            loop.close()

        # Update status: SUCCESS
        update_job_status(
            job_id,
            "SUCCESS",
            completed_at=datetime.now().isoformat(),
            result=result,
            total_files=result.get("file_count", 0),
            total_time=result.get("total_duration", 0),
            work_dir=result.get("project_dir", str(work_dir)),
        )

        logger.info(f"✅ Workflow completed successfully for session: {session_id}")

        return {"job_id": job_id, "session_id": session_id, "status": "SUCCESS", "result": result}

    except Exception as e:
        logger.error(f"❌ Workflow execution failed: {e}", exc_info=True)

        # Update status: FAILURE
        update_job_status(job_id, "FAILURE", failed_at=datetime.now().isoformat(), error=str(e))

        # Retry if appropriate
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {"job_id": job_id, "session_id": session_id, "status": "FAILURE", "error": str(e)}


@celery_app.task(name="celery_tasks.get_job_status")
def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Get job status from Redis

    Args:
        job_id: Celery task ID

    Returns:
        Job status dictionary
    """
    status_data = redis_client.hgetall(f"job:{job_id}")

    if not status_data:
        return {"job_id": job_id, "status": "NOT_FOUND"}

    # Parse JSON fields
    for key in ["result"]:
        if key in status_data:
            try:
                status_data[key] = json.loads(status_data[key])
            except:
                pass

    return {"job_id": job_id, **status_data}
