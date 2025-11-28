"""
JIRA Integration API Routes
FastAPI endpoints for JIRA integration
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, Field
import logging
from pathlib import Path

from ..services.jira_integration_service import (
    JiraIntegrationService,
    IssueStatus,
    IssueType,
    Priority
)

logger = logging.getLogger(__name__)

# Initialize service with CSV paths
DOCS_DIR = Path(__file__).parent.parent.parent / "docs"
jira_service = JiraIntegrationService(
    epics_csv_path=str(DOCS_DIR / "jira_epics_export.csv"),
    tasks_csv_path=str(DOCS_DIR / "jira_actions_export.csv")
)

router = APIRouter(prefix="/api/jira", tags=["JIRA Integration"])


# Pydantic Models
class IssueStatusUpdate(BaseModel):
    """Request model for status updates"""
    status: IssueStatus
    resolution: Optional[str] = Field(None, description="Resolution text when marking as Done")


class TransitionRequest(BaseModel):
    """Request to transition issue to a new status"""
    target_status: IssueStatus
    resolution: Optional[str] = None


# API Endpoints
@router.get("/epics")
async def list_epics(
    status: Optional[IssueStatus] = Query(None, description="Filter by status"),
    priority: Optional[Priority] = Query(None, description="Filter by priority")
):
    """
    List all epics with optional filtering
    
    **Example**: `GET /api/jira/epics?status=To Do&priority=Highest`
    """
    try:
        epics = jira_service.list_epics(status=status, priority=priority)
        return {
            "success": True,
            "count": len(epics),
            "epics": epics
        }
    except Exception as e:
        logger.error(f"Error listing epics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/epics/todo")
async def get_todo_epics():
    """
    Get all epics in 'To Do' status
    
    **Use Case**: JIRA Initialization step to fetch relevant work items
    """
    try:
        epics = jira_service.get_todo_epics()
        return {
            "success": True,
            "count": len(epics),
            "epics": epics
        }
    except Exception as e:
        logger.error(f"Error getting todo epics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/epics/{epic_id}")
async def get_epic(epic_id: str):
    """
    Get epic details with associated tasks and progress
    
    **Example**: `GET /api/jira/epics/EPIC-3`
    """
    try:
        summary = jira_service.get_issue_summary(epic_id, IssueType.EPIC)
        return {
            "success": True,
            "data": summary
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting epic {epic_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/epics/{epic_id}/tasks")
async def get_epic_tasks(epic_id: str):
    """
    Get all tasks associated with an epic
    
    **Example**: `GET /api/jira/epics/EPIC-1/tasks`
    """
    try:
        tasks = jira_service.get_epic_tasks(epic_id)
        return {
            "success": True,
            "epic_id": epic_id,
            "count": len(tasks),
            "tasks": tasks
        }
    except Exception as e:
        logger.error(f"Error getting tasks for {epic_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/epics/{epic_id}/transition")
async def transition_epic(epic_id: str, request: TransitionRequest):
    """
    Transition epic to a new status
    
    **Use Case**: 
    - Start work: transition 'To Do' -> 'In Progress'
    - Complete work: transition 'In Progress' -> 'Done'
    
    **Example**: 
    ```json
    {
        "target_status": "In Progress"
    }
    ```
    """
    try:
        if request.target_status == IssueStatus.DONE and not request.resolution:
            raise HTTPException(
                status_code=400, 
                detail="Resolution required when transitioning to Done"
            )
        
        updated_epic = jira_service.update_epic_status(
            epic_id, 
            request.target_status,
            request.resolution
        )
        return {
            "success": True,
            "message": f"Epic {epic_id} transitioned to {request.target_status}",
            "epic": updated_epic
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error transitioning epic {epic_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks")
async def list_tasks(
    status: Optional[IssueStatus] = Query(None, description="Filter by status"),
    priority: Optional[Priority] = Query(None, description="Filter by priority"),
    epic_id: Optional[str] = Query(None, description="Filter by epic ID")
):
    """
    List all tasks with optional filtering
    
    **Example**: `GET /api/jira/tasks?status=To Do&priority=Highest`
    """
    try:
        tasks = jira_service.list_tasks(status=status, priority=priority, epic_id=epic_id)
        return {
            "success": True,
            "count": len(tasks),
            "tasks": tasks
        }
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """
    Get task details
    
    **Example**: `GET /api/jira/tasks/P0`
    """
    try:
        summary = jira_service.get_issue_summary(task_id, IssueType.TASK)
        return {
            "success": True,
            "data": summary
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/transition")
async def transition_task(task_id: str, request: TransitionRequest):
    """
    Transition task to a new status
    
    **Use Case**: Update task status after implementation/testing
    
    **Example**:
    ```json
    {
        "target_status": "Done",
        "resolution": "All tests passed; Implementation complete"
    }
    ```
    """
    try:
        if request.target_status == IssueStatus.DONE and not request.resolution:
            raise HTTPException(
                status_code=400,
                detail="Resolution required when transitioning to Done"
            )
        
        updated_task = jira_service.update_task_status(
            task_id,
            request.target_status,
            request.resolution
        )
        return {
            "success": True,
            "message": f"Task {task_id} transitioned to {request.target_status}",
            "task": updated_task
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error transitioning task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/epics/{epic_id}/check-completion")
async def check_epic_completion(epic_id: str):
    """
    Check if all tasks in an epic are completed
    
    **Use Case**: Determine if epic should be closed after all tasks are done
    
    **Example**: `GET /api/jira/epics/EPIC-3/check-completion`
    """
    try:
        is_complete = jira_service.check_epic_completion(epic_id)
        tasks = jira_service.get_epic_tasks(epic_id)
        done_tasks = [t for t in tasks if t.get('Status') == IssueStatus.DONE.value]
        
        return {
            "success": True,
            "epic_id": epic_id,
            "is_complete": is_complete,
            "total_tasks": len(tasks),
            "done_tasks": len(done_tasks),
            "remaining_tasks": len(tasks) - len(done_tasks)
        }
    except Exception as e:
        logger.error(f"Error checking completion for {epic_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload")
async def reload_data():
    """
    Reload JIRA data from CSV files
    
    **Use Case**: Refresh cache after external updates to CSV files
    """
    try:
        jira_service.reload_data()
        return {
            "success": True,
            "message": "JIRA data reloaded successfully",
            "epics_count": len(jira_service.epics),
            "tasks_count": len(jira_service.tasks)
        }
    except Exception as e:
        logger.error(f"Error reloading data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        epics_count = len(jira_service.epics)
        tasks_count = len(jira_service.tasks)
        return {
            "status": "healthy",
            "service": "jira-integration",
            "epics_loaded": epics_count,
            "tasks_loaded": tasks_count
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))
