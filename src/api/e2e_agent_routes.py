"""
E2E Development & QA Agent API Routes
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging
from pathlib import Path

from ..services.jira_integration_service import JiraIntegrationService, IssueType
from ..services.e2e_dev_qa_agent import E2EDevQAAgent

logger = logging.getLogger(__name__)

# Initialize services
DOCS_DIR = Path(__file__).parent.parent.parent / "docs"
jira_service = JiraIntegrationService(
    epics_csv_path=str(DOCS_DIR / "jira_epics_export.csv"),
    tasks_csv_path=str(DOCS_DIR / "jira_actions_export.csv")
)

e2e_agent = E2EDevQAAgent(
    jira_service=jira_service,
    quality_api_url="http://localhost:8000"
)

router = APIRouter(prefix="/api/e2e-agent", tags=["E2E Dev & QA Agent"])


# Pydantic Models
class WorkflowRequest(BaseModel):
    """Request to start E2E workflow"""
    epic_id: Optional[str] = Field(None, description="Epic ID (e.g., EPIC-3). If not provided, auto-selects first 'To Do' epic")
    quality_api_url: Optional[str] = Field("http://localhost:8000", description="Quality Fabric API URL")


class WorkflowResponse(BaseModel):
    """Workflow execution response"""
    success: bool
    workflow_id: str
    message: str
    epic_id: Optional[str] = None


# API Endpoints
@router.post("/workflow/start")
async def start_workflow(request: WorkflowRequest):
    """
    Start the End-to-End Development & QA Workflow
    
    **Workflow Steps:**
    1. JIRA Initialization: Fetch 'To Do' Epic and transition to 'In Progress'
    2. Strategy: Generate development plan and test cases
    3. Implementation: Execute development (placeholder)
    4. Validation: Run tests against quality-fabric API
    5. Reporting: Update JIRA tasks with results
    6. Closure: Set Epic to 'Done' if all tasks complete
    
    **Example Request:**
    ```json
    {
        "epic_id": "EPIC-3"
    }
    ```
    
    **Returns:** Workflow execution results with test results and JIRA updates
    """
    try:
        # Update quality API URL if provided
        if request.quality_api_url:
            e2e_agent.quality_api_url = request.quality_api_url
        
        # Run full workflow
        results = await e2e_agent.run_full_workflow(epic_id=request.epic_id)
        
        # Save report
        report_dir = Path(__file__).parent.parent.parent / "logs"
        report_dir.mkdir(exist_ok=True)
        report_path = report_dir / f"e2e_workflow_{results.get('epic_id', 'unknown')}.json"
        e2e_agent.save_workflow_report(results, str(report_path))
        
        return {
            "success": results.get('success', False),
            "workflow_id": results.get('epic_id'),
            "results": results,
            "report_path": str(report_path)
        }
    
    except Exception as e:
        logger.error(f"Error starting workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow/status/{epic_id}")
async def get_workflow_status(epic_id: str):
    """
    Get current status of an epic workflow
    
    **Example:** `GET /api/e2e-agent/workflow/status/EPIC-3`
    """
    try:
        summary = jira_service.get_issue_summary(epic_id, IssueType.EPIC)
        completion_check = jira_service.check_epic_completion(epic_id)
        
        return {
            "success": True,
            "epic_id": epic_id,
            "status": summary['issue'].get('Status'),
            "is_complete": completion_check,
            "progress": summary.get('progress', {}),
            "tasks": summary.get('tasks', [])
        }
    
    except Exception as e:
        logger.error(f"Error getting workflow status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflow/step1/initialize")
async def run_step1_initialize(epic_id: Optional[str] = None):
    """
    Run Step 1: JIRA Initialization only
    
    Fetches 'To Do' epic and transitions to 'In Progress'
    """
    try:
        result = await e2e_agent.step1_jira_initialization(epic_id)
        return {
            "success": True,
            "step": "step1_initialization",
            "result": result,
            "logs": e2e_agent.session_log[-10:]  # Last 10 log entries
        }
    except Exception as e:
        logger.error(f"Error in step 1: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflow/step2/strategy")
async def run_step2_strategy(epic_data: Dict[str, Any]):
    """
    Run Step 2: Strategy Generation
    
    Generates development plan and test cases from epic data
    """
    try:
        plan = e2e_agent.step2_generate_strategy(epic_data)
        return {
            "success": True,
            "step": "step2_strategy",
            "plan": plan.to_dict(),
            "logs": e2e_agent.session_log[-10:]
        }
    except Exception as e:
        logger.error(f"Error in step 2: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check for E2E agent service"""
    try:
        # Check JIRA service
        epics_count = len(jira_service.epics)
        tasks_count = len(jira_service.tasks)
        
        # Check quality API connectivity
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{e2e_agent.quality_api_url}/api/health")
                quality_api_status = "reachable" if response.status_code == 200 else "unreachable"
        except:
            quality_api_status = "unreachable"
        
        return {
            "status": "healthy",
            "service": "e2e-dev-qa-agent",
            "jira": {
                "epics_loaded": epics_count,
                "tasks_loaded": tasks_count
            },
            "quality_api": {
                "url": e2e_agent.quality_api_url,
                "status": quality_api_status
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/logs/session")
async def get_session_logs(limit: int = 50):
    """
    Get recent session logs from E2E agent
    
    **Query Parameters:**
    - `limit`: Number of recent log entries to return (default: 50)
    """
    try:
        logs = e2e_agent.session_log[-limit:] if limit > 0 else e2e_agent.session_log
        return {
            "success": True,
            "total_logs": len(e2e_agent.session_log),
            "returned_logs": len(logs),
            "logs": logs
        }
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
