#!/usr/bin/env python3
"""
RAG Writer Service - FastAPI Microservice for RAG Indexing
Port: 9802
Provides async indexing of workflow executions and templates
"""

import json
import logging
import os
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.persona_domains import match_template_to_persona
from rag_system.collateral_extractor import Collateral, CollateralExtractor
from rag_system.vector_rag_manager import get_rag_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="MAESTRO RAG Writer Service",
    description="Async indexing service for RAG knowledge base",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Keys
VALID_API_KEYS = {
    os.getenv("RAG_WRITER_API_KEY", "dev_rag_writer_key_98765"): "maestro_engine",
    os.getenv("WORKFLOW_API_KEY", "dev_workflow_key_54321"): "workflow_engine",
}

# maestro-templates storage path
MAESTRO_TEMPLATES_PATH = Path(
    os.getenv(
        "MAESTRO_TEMPLATES_PATH", "/home/ec2-user/projects/maestro-templates/storage/templates"
    )
)

# Webhook configuration
WEBHOOK_URL = os.getenv("RAG_WRITER_WEBHOOK_URL")
WEBHOOK_ENABLED = WEBHOOK_URL is not None

# Retry configuration
MAX_RETRIES = int(os.getenv("RAG_WRITER_MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RAG_WRITER_RETRY_DELAY", "5"))  # seconds

# Background task queue
indexing_queue: Queue = Queue()
task_status: Dict[str, Dict] = {}


# ==============================================================================
# Data Models
# ==============================================================================


@dataclass
class IndexingTask:
    """Represents an indexing task"""

    task_id: str
    task_type: str  # execution, template, collateral
    data: Dict[str, Any]
    status: str  # pending, processing, completed, failed
    created_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    retry_count: int = 0
    webhook_url: Optional[str] = None


class ExecutionIndexRequest(BaseModel):
    """Request to index a workflow execution"""

    session_id: str = Field(..., description="Workflow session ID")
    requirement: str = Field(..., description="Original requirement")
    personas: List[str] = Field(..., description="Team members involved")
    collaterals: List[Dict[str, Any]] = Field(default_factory=list, description="Files generated")
    quality_score: Optional[float] = Field(None, description="Quality score (0-1)")
    success: bool = Field(True, description="Whether execution succeeded")
    execution_time: Optional[float] = Field(None, description="Execution time in seconds")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )


class TemplateIndexRequest(BaseModel):
    """Request to index a code template"""

    name: str = Field(..., description="Template name")
    content: str = Field(..., description="Template content")
    category: str = Field(..., description="Template category")
    language: str = Field(..., description="Programming language")
    framework: Optional[str] = Field(None, description="Framework/library")
    description: str = Field("", description="Template description")
    tags: List[str] = Field(default_factory=list, description="Template tags")
    quality_scores: Optional[Dict[str, float]] = Field(None, description="Quality metrics")
    save_to_maestro_templates: bool = Field(False, description="Save to maestro-templates repo")


class BatchIndexRequest(BaseModel):
    """Request to index multiple items in batch"""

    executions: List[ExecutionIndexRequest] = Field(
        default_factory=list, description="Executions to index"
    )
    templates: List[TemplateIndexRequest] = Field(
        default_factory=list, description="Templates to index"
    )
    webhook_url: Optional[str] = Field(None, description="Webhook URL for batch completion")


class TaskStatusResponse(BaseModel):
    """Response for task status query"""

    task_id: str
    task_type: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


# ==============================================================================
# Authentication
# ==============================================================================


def verify_api_key(x_api_key: str = Header(...)) -> str:
    """Verify API key from header"""
    if x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return VALID_API_KEYS[x_api_key]


# ==============================================================================
# Quality Gate Validation
# ==============================================================================


def validate_quality_gate(data: Dict[str, Any], min_quality: float = 0.5) -> bool:
    """
    Validate quality gate before indexing

    Returns:
        True if passes quality gate, False otherwise
    """
    quality_score = data.get("quality_score", 0.0)

    # Minimum quality threshold
    if quality_score < min_quality:
        logger.warning(f"Quality gate failed: {quality_score} < {min_quality}")
        return False

    # Check for required fields
    required_fields = ["requirement", "personas"]
    for field in required_fields:
        if field not in data or not data[field]:
            logger.warning(f"Quality gate failed: missing required field '{field}'")
            return False

    # Success flag check
    if not data.get("success", True):
        logger.info("Indexing failed execution (success=False)")

    logger.info(f"✅ Quality gate passed: {quality_score}")
    return True


# ==============================================================================
# Webhook Notifications
# ==============================================================================


def send_webhook_notification(task: IndexingTask, result: Optional[Dict[str, Any]] = None):
    """Send webhook notification for task completion"""
    if not WEBHOOK_ENABLED and not task.webhook_url:
        return

    webhook_url = task.webhook_url or WEBHOOK_URL

    try:
        payload = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": task.status,
            "created_at": task.created_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "error": task.error,
            "result": result,
            "retry_count": task.retry_count,
        }

        import requests

        response = requests.post(
            webhook_url, json=payload, timeout=5, headers={"Content-Type": "application/json"}
        )

        if response.ok:
            logger.info(f"📤 Webhook sent for task {task.task_id}")
        else:
            logger.warning(f"⚠️  Webhook failed: {response.status_code}")

    except Exception as e:
        logger.warning(f"⚠️  Webhook error: {e}")


# ==============================================================================
# Background Indexing Worker
# ==============================================================================


def indexing_worker():
    """Background worker that processes indexing tasks"""
    logger.info("🔄 Indexing worker started")

    while True:
        try:
            # Get task from queue (blocking with timeout)
            task = indexing_queue.get(timeout=1.0)

            if task is None:  # Poison pill to stop worker
                break

            # Update status
            task.status = "processing"
            task_status[task.task_id] = asdict(task)

            logger.info(f"📝 Processing task {task.task_id} ({task.task_type})")

            # Process based on task type with retry logic
            result = None
            try:
                if task.task_type == "execution":
                    result = index_execution(task.data)
                elif task.task_type == "template":
                    result = index_template(task.data)
                else:
                    raise ValueError(f"Unknown task type: {task.task_type}")

                # Mark as completed
                task.status = "completed"
                task.completed_at = datetime.now()
                task_status[task.task_id] = {**asdict(task), "result": result}

                logger.info(f"✅ Task {task.task_id} completed")

                # Send webhook notification
                send_webhook_notification(task, result)

            except Exception as e:
                logger.error(
                    f"❌ Task {task.task_id} failed (attempt {task.retry_count + 1}/{MAX_RETRIES}): {e}"
                )

                # Retry logic
                if task.retry_count < MAX_RETRIES - 1:
                    task.retry_count += 1
                    task.status = "retrying"
                    logger.info(f"🔄 Retrying task {task.task_id} in {RETRY_DELAY}s...")

                    # Re-queue task after delay
                    time.sleep(RETRY_DELAY)
                    indexing_queue.put(task)
                else:
                    # Max retries reached
                    task.status = "failed"
                    task.error = str(e)
                    task.completed_at = datetime.now()
                    task_status[task.task_id] = asdict(task)

                    # Send webhook notification for failure
                    send_webhook_notification(task, None)

            # Mark task as done in queue
            indexing_queue.task_done()

        except Exception as e:
            if "Empty" not in str(e):  # Ignore queue timeout
                logger.error(f"Worker error: {e}")
            time.sleep(0.1)


def index_execution(data: Dict[str, Any]) -> Dict[str, Any]:
    """Index a workflow execution"""
    rag_manager = get_rag_manager()

    if not rag_manager.enabled:
        raise Exception("RAG system not available")

    # Validate quality gate
    if not validate_quality_gate(data, min_quality=0.5):
        logger.warning("Skipping indexing due to quality gate failure")
        return {"indexed": False, "reason": "quality_gate_failed"}

    # Index execution
    success = rag_manager.index_execution(
        session_id=data["session_id"],
        requirement=data["requirement"],
        personas=data["personas"],
        collaterals=data.get("collaterals", []),
        quality_score=data.get("quality_score"),
        success=data.get("success", True),
    )

    if not success:
        raise Exception("Failed to index execution")

    logger.info(f"✅ Indexed execution: {data['session_id']}")

    return {
        "indexed": True,
        "session_id": data["session_id"],
        "personas_count": len(data["personas"]),
        "collaterals_count": len(data.get("collaterals", [])),
    }


def index_template(data: Dict[str, Any]) -> Dict[str, Any]:
    """Index a code template"""
    template_id = str(uuid.uuid4())

    # Prepare template metadata
    quality_scores = data.get("quality_scores") or {}
    template_data = {
        "metadata": {
            "id": template_id,
            "name": data["name"],
            "category": data["category"],
            "language": data["language"],
            "framework": data.get("framework"),
            "description": data["description"],
            "tags": data.get("tags", []),
            "quality_score": quality_scores.get("overall", 50.0),
            "security_score": quality_scores.get("security", 50.0),
            "performance_score": quality_scores.get("performance", 50.0),
            "maintainability_score": quality_scores.get("maintainability", 50.0),
            "status": "pending_review",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        },
        "content": data["content"],
    }

    # Save to maestro-templates if requested
    if data.get("save_to_maestro_templates", False):
        save_to_maestro_templates(template_id, template_data)

    logger.info(f"✅ Indexed template: {data['name']} ({template_id})")

    return {
        "indexed": True,
        "template_id": template_id,
        "name": data["name"],
        "saved_to_maestro_templates": data.get("save_to_maestro_templates", False),
    }


def save_to_maestro_templates(template_id: str, template_data: Dict[str, Any]):
    """Save template to maestro-templates repository"""
    if not MAESTRO_TEMPLATES_PATH.exists():
        MAESTRO_TEMPLATES_PATH.mkdir(parents=True, exist_ok=True)

    template_file = MAESTRO_TEMPLATES_PATH / f"{template_id}.json"

    with open(template_file, "w") as f:
        json.dump(template_data, f, indent=2)

    logger.info(f"💾 Saved template to maestro-templates: {template_file}")


# ==============================================================================
# API Endpoints
# ==============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "rag_writer",
        "version": "1.0.0",
        "port": 9802,
        "queue_size": indexing_queue.qsize(),
        "tasks_pending": sum(1 for t in task_status.values() if t["status"] == "pending"),
        "tasks_processing": sum(1 for t in task_status.values() if t["status"] == "processing"),
        "tasks_completed": sum(1 for t in task_status.values() if t["status"] == "completed"),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/v1/index/execution")
async def index_execution_endpoint(
    request: ExecutionIndexRequest, client: str = Depends(verify_api_key)
):
    """
    Index a workflow execution (async)

    Returns task ID for status tracking
    """
    try:
        # Create indexing task
        task_id = str(uuid.uuid4())
        task = IndexingTask(
            task_id=task_id,
            task_type="execution",
            data={
                "session_id": request.session_id,
                "requirement": request.requirement,
                "personas": request.personas,
                "collaterals": request.collaterals,
                "quality_score": request.quality_score,
                "success": request.success,
                "execution_time": request.execution_time,
                **request.metadata,
            },
            status="pending",
            created_at=datetime.now(),
        )

        # Store task status
        task_status[task_id] = asdict(task)

        # Add to queue
        indexing_queue.put(task)

        logger.info(f"📥 Queued execution indexing: {request.session_id} (task: {task_id})")

        return JSONResponse(
            content={
                "task_id": task_id,
                "status": "pending",
                "message": "Execution indexing queued",
                "session_id": request.session_id,
            }
        )

    except Exception as e:
        logger.error(f"Failed to queue execution indexing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/index/template")
async def index_template_endpoint(
    request: TemplateIndexRequest, client: str = Depends(verify_api_key)
):
    """
    Index a code template (async)

    Returns task ID for status tracking
    """
    try:
        # Create indexing task
        task_id = str(uuid.uuid4())
        task = IndexingTask(
            task_id=task_id,
            task_type="template",
            data={
                "name": request.name,
                "content": request.content,
                "category": request.category,
                "language": request.language,
                "framework": request.framework,
                "description": request.description,
                "tags": request.tags,
                "quality_scores": request.quality_scores,
                "save_to_maestro_templates": request.save_to_maestro_templates,
            },
            status="pending",
            created_at=datetime.now(),
        )

        # Store task status
        task_status[task_id] = asdict(task)

        # Add to queue
        indexing_queue.put(task)

        logger.info(f"📥 Queued template indexing: {request.name} (task: {task_id})")

        return JSONResponse(
            content={
                "task_id": task_id,
                "status": "pending",
                "message": "Template indexing queued",
                "template_name": request.name,
            }
        )

    except Exception as e:
        logger.error(f"Failed to queue template indexing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/index/batch")
async def index_batch_endpoint(request: BatchIndexRequest, client: str = Depends(verify_api_key)):
    """
    Index multiple executions and templates in batch

    Returns batch task ID and individual task IDs
    """
    try:
        batch_id = str(uuid.uuid4())
        task_ids = []

        # Queue execution indexing tasks
        for execution in request.executions:
            task_id = str(uuid.uuid4())
            task = IndexingTask(
                task_id=task_id,
                task_type="execution",
                data={
                    "session_id": execution.session_id,
                    "requirement": execution.requirement,
                    "personas": execution.personas,
                    "collaterals": execution.collaterals,
                    "quality_score": execution.quality_score,
                    "success": execution.success,
                    "execution_time": execution.execution_time,
                    **execution.metadata,
                },
                status="pending",
                created_at=datetime.now(),
                webhook_url=request.webhook_url,
            )
            task_status[task_id] = asdict(task)
            indexing_queue.put(task)
            task_ids.append({"type": "execution", "task_id": task_id})

        # Queue template indexing tasks
        for template in request.templates:
            task_id = str(uuid.uuid4())
            task = IndexingTask(
                task_id=task_id,
                task_type="template",
                data={
                    "name": template.name,
                    "content": template.content,
                    "category": template.category,
                    "language": template.language,
                    "framework": template.framework,
                    "description": template.description,
                    "tags": template.tags,
                    "quality_scores": template.quality_scores,
                    "save_to_maestro_templates": template.save_to_maestro_templates,
                },
                status="pending",
                created_at=datetime.now(),
                webhook_url=request.webhook_url,
            )
            task_status[task_id] = asdict(task)
            indexing_queue.put(task)
            task_ids.append({"type": "template", "task_id": task_id})

        logger.info(f"📥 Queued batch indexing: {len(task_ids)} tasks (batch: {batch_id})")

        return JSONResponse(
            content={
                "batch_id": batch_id,
                "task_ids": task_ids,
                "total_tasks": len(task_ids),
                "message": "Batch indexing queued",
            }
        )

    except Exception as e:
        logger.error(f"Failed to queue batch indexing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/task/{task_id}")
async def get_task_status(task_id: str, client: str = Depends(verify_api_key)):
    """Get status of an indexing task"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="Task not found")

    task = task_status[task_id]

    return JSONResponse(
        content={
            "task_id": task["task_id"],
            "task_type": task["task_type"],
            "status": task["status"],
            "created_at": (
                task["created_at"].isoformat()
                if isinstance(task["created_at"], datetime)
                else task["created_at"]
            ),
            "completed_at": (
                task["completed_at"].isoformat()
                if task.get("completed_at") and isinstance(task["completed_at"], datetime)
                else task.get("completed_at")
            ),
            "error": task.get("error"),
            "result": task.get("result"),
        }
    )


@app.get("/api/v1/tasks")
async def list_tasks(
    status: Optional[str] = None, limit: int = 50, client: str = Depends(verify_api_key)
):
    """List indexing tasks"""
    tasks = list(task_status.values())

    # Filter by status if provided
    if status:
        tasks = [t for t in tasks if t["status"] == status]

    # Sort by created_at (most recent first)
    tasks = sorted(
        tasks,
        key=lambda t: (
            t["created_at"]
            if isinstance(t["created_at"], datetime)
            else datetime.fromisoformat(t["created_at"])
        ),
        reverse=True,
    )

    # Limit
    tasks = tasks[:limit]

    return JSONResponse(content={"tasks": tasks, "total": len(tasks)})


@app.get("/api/v1/stats")
async def get_stats(client: str = Depends(verify_api_key)):
    """Get RAG Writer statistics"""
    return JSONResponse(
        content={
            "queue_size": indexing_queue.qsize(),
            "total_tasks": len(task_status),
            "tasks_by_status": {
                "pending": sum(1 for t in task_status.values() if t["status"] == "pending"),
                "processing": sum(1 for t in task_status.values() if t["status"] == "processing"),
                "completed": sum(1 for t in task_status.values() if t["status"] == "completed"),
                "failed": sum(1 for t in task_status.values() if t["status"] == "failed"),
            },
            "maestro_templates_path": str(MAESTRO_TEMPLATES_PATH),
            "maestro_templates_exists": MAESTRO_TEMPLATES_PATH.exists(),
            "timestamp": datetime.now().isoformat(),
        }
    )


# ==============================================================================
# Startup / Shutdown
# ==============================================================================


@app.on_event("startup")
async def startup_event():
    """Startup tasks"""
    logger.info("=" * 80)
    logger.info("🚀 MAESTRO RAG Writer Service Starting")
    logger.info("=" * 80)
    logger.info(f"📡 Port: 9802")
    logger.info(f"💾 maestro-templates: {MAESTRO_TEMPLATES_PATH}")
    logger.info(f"📚 Docs: http://0.0.0.0:9802/docs")
    logger.info("=" * 80)

    # Start background worker thread
    worker_thread = threading.Thread(target=indexing_worker, daemon=True)
    worker_thread.start()
    logger.info("✅ Background indexing worker started")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown tasks"""
    logger.info("👋 MAESTRO RAG Writer Service Shutting Down")
    # Send poison pill to stop worker
    indexing_queue.put(None)


# ==============================================================================
# Main
# ==============================================================================

if __name__ == "__main__":
    uvicorn.run("rag_writer_service:app", host="0.0.0.0", port=9802, reload=True, log_level="info")
