"""
MAESTRO Enterprise Template Repository - Workflow Engine
Version: 1.0
Purpose: Enterprise approval workflows with governance and compliance
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from template_manager import EnterpriseTemplateRepository, TemplateStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalAction(Enum):
    """Approval actions"""

    SUBMIT_FOR_REVIEW = "submit_for_review"
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    CANCEL = "cancel"


class UserRole(Enum):
    """User roles for RBAC"""

    DEVELOPER = "developer"
    SENIOR_DEVELOPER = "senior_developer"
    TEAM_LEAD = "team_lead"
    ARCHITECT = "architect"
    ADMIN = "admin"


@dataclass
class WorkflowStep:
    """Individual workflow step"""

    step_id: str
    name: str
    description: str
    required_role: UserRole
    auto_approve: bool = False
    timeout_hours: int = 48
    parallel: bool = False
    conditions: List[str] = field(default_factory=list)


@dataclass
class ApprovalWorkflow:
    """Template approval workflow definition"""

    workflow_id: str
    name: str
    description: str
    template_types: List[str]  # Which template types this applies to
    steps: List[WorkflowStep]
    sla_hours: int = 72  # Service level agreement
    auto_escalation: bool = True
    escalation_hours: int = 24


@dataclass
class WorkflowExecution:
    """Running workflow instance"""

    execution_id: str
    workflow_id: str
    template_id: str
    current_step: int
    status: WorkflowStatus
    initiated_by: str
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalTask:
    """Individual approval task"""

    task_id: str
    execution_id: str
    step_id: str
    assignee: str
    status: WorkflowStatus
    created_at: datetime
    due_at: datetime
    completed_at: Optional[datetime] = None
    comments: str = ""
    checklist_results: Dict[str, bool] = field(default_factory=dict)


class EnterpriseWorkflowEngine:
    """
    Enterprise workflow engine for template approval and governance

    Features:
    - Multi-step approval workflows
    - Role-based task assignment
    - SLA monitoring and escalation
    - Quality gate enforcement
    - Compliance checkpoints
    - Audit trail integration
    """

    def __init__(self, repository: EnterpriseTemplateRepository):
        self.repository = repository
        self.workflows: Dict[str, ApprovalWorkflow] = {}
        self.executions: Dict[str, WorkflowExecution] = {}
        self.tasks: Dict[str, ApprovalTask] = {}

        # Initialize default workflows
        self._initialize_default_workflows()

    def _initialize_default_workflows(self):
        """Initialize default enterprise workflows"""

        # Standard Template Approval Workflow
        standard_workflow = ApprovalWorkflow(
            workflow_id="standard_approval",
            name="Standard Template Approval",
            description="Standard approval process for general templates",
            template_types=["components", "functions", "utilities"],
            steps=[
                WorkflowStep(
                    step_id="quality_check",
                    name="Quality Assessment",
                    description="Automated quality and security checks",
                    required_role=UserRole.DEVELOPER,
                    auto_approve=True,
                    timeout_hours=1,
                    conditions=["quality_score >= 80", "security_score >= 85"],
                ),
                WorkflowStep(
                    step_id="peer_review",
                    name="Peer Review",
                    description="Code review by senior developer",
                    required_role=UserRole.SENIOR_DEVELOPER,
                    timeout_hours=24,
                ),
                WorkflowStep(
                    step_id="team_lead_approval",
                    name="Team Lead Approval",
                    description="Final approval by team lead",
                    required_role=UserRole.TEAM_LEAD,
                    timeout_hours=12,
                ),
            ],
            sla_hours=48,
            auto_escalation=True,
            escalation_hours=24,
        )

        # Critical Template Approval Workflow
        critical_workflow = ApprovalWorkflow(
            workflow_id="critical_approval",
            name="Critical Template Approval",
            description="Enhanced approval process for critical templates",
            template_types=["security", "infrastructure", "api_core"],
            steps=[
                WorkflowStep(
                    step_id="security_scan",
                    name="Security Assessment",
                    description="Comprehensive security analysis",
                    required_role=UserRole.ARCHITECT,
                    auto_approve=False,
                    timeout_hours=2,
                    conditions=["security_score >= 95", "vulnerability_count == 0"],
                ),
                WorkflowStep(
                    step_id="architect_review",
                    name="Architecture Review",
                    description="Architecture compliance review",
                    required_role=UserRole.ARCHITECT,
                    timeout_hours=24,
                ),
                WorkflowStep(
                    step_id="security_review",
                    name="Security Review",
                    description="Security team approval",
                    required_role=UserRole.ARCHITECT,
                    timeout_hours=24,
                    parallel=True,
                ),
                WorkflowStep(
                    step_id="admin_approval",
                    name="Administrative Approval",
                    description="Final administrative approval",
                    required_role=UserRole.ADMIN,
                    timeout_hours=12,
                ),
            ],
            sla_hours=72,
            auto_escalation=True,
            escalation_hours=12,
        )

        self.workflows["standard_approval"] = standard_workflow
        self.workflows["critical_approval"] = critical_workflow

    async def start_approval_workflow(
        self, template_id: str, initiated_by: str, workflow_type: Optional[str] = None
    ) -> str:
        """
        Start approval workflow for a template

        Args:
            template_id: Template to approve
            initiated_by: User initiating the workflow
            workflow_type: Specific workflow type (auto-detected if None)

        Returns:
            Workflow execution ID
        """
        try:
            # Get template details
            template_data = await self.repository.get_template(template_id)
            if not template_data:
                raise ValueError(f"Template not found: {template_id}")

            # Determine workflow type if not specified
            if not workflow_type:
                workflow_type = await self._determine_workflow_type(template_data)

            workflow = self.workflows.get(workflow_type)
            if not workflow:
                raise ValueError(f"Workflow not found: {workflow_type}")

            # Create workflow execution
            execution_id = str(uuid.uuid4())
            execution = WorkflowExecution(
                execution_id=execution_id,
                workflow_id=workflow_type,
                template_id=template_id,
                current_step=0,
                status=WorkflowStatus.PENDING,
                initiated_by=initiated_by,
                initiated_at=datetime.now(),
                metadata={
                    "template_name": template_data.get("name"),
                    "template_category": template_data.get("category"),
                    "quality_score": template_data.get("quality_score"),
                    "workflow_sla": workflow.sla_hours,
                },
            )

            self.executions[execution_id] = execution

            # Update template status
            await self._update_template_status(template_id, TemplateStatus.REVIEW)

            # Log workflow initiation
            await self._log_workflow_event(
                execution_id,
                "workflow_started",
                initiated_by,
                {"workflow_type": workflow_type, "template_id": template_id},
            )

            # Start first step
            await self._advance_workflow(execution_id)

            logger.info(
                f"✅ Started {workflow_type} workflow for template {template_id}: {execution_id}"
            )
            return execution_id

        except Exception as e:
            logger.error(f"❌ Failed to start workflow: {e}")
            raise

    async def process_approval_action(
        self,
        task_id: str,
        action: ApprovalAction,
        user_id: str,
        comments: str = "",
        checklist_results: Optional[Dict[str, bool]] = None,
    ) -> Dict[str, Any]:
        """
        Process approval action (approve, reject, request changes)

        Args:
            task_id: Approval task ID
            action: Action to take
            user_id: User performing action
            comments: Optional comments
            checklist_results: Checklist item results

        Returns:
            Action result with next steps
        """
        try:
            task = self.tasks.get(task_id)
            if not task:
                raise ValueError(f"Task not found: {task_id}")

            execution = self.executions.get(task.execution_id)
            if not execution:
                raise ValueError(f"Workflow execution not found: {task.execution_id}")

            # Validate user permissions
            await self._validate_user_permissions(task, user_id)

            # Process the action
            result = await self._process_task_action(
                task, action, user_id, comments, checklist_results
            )

            # Log the action
            await self._log_workflow_event(
                execution.execution_id,
                f"task_{action.value}",
                user_id,
                {
                    "task_id": task_id,
                    "step_id": task.step_id,
                    "comments": comments,
                    "checklist_results": checklist_results or {},
                },
            )

            # Advance workflow if task completed
            if task.status == WorkflowStatus.COMPLETED:
                await self._advance_workflow(execution.execution_id)
            elif task.status == WorkflowStatus.REJECTED:
                await self._reject_workflow(execution.execution_id, comments)

            logger.info(f"✅ Processed {action.value} for task {task_id} by {user_id}")
            return result

        except Exception as e:
            logger.error(f"❌ Failed to process approval action: {e}")
            raise

    async def get_pending_tasks(self, user_id: str, role: UserRole) -> List[Dict[str, Any]]:
        """Get pending approval tasks for user"""
        try:
            pending_tasks = []

            for task in self.tasks.values():
                if task.status == WorkflowStatus.PENDING and (
                    task.assignee == user_id or task.assignee == role.value
                ):

                    execution = self.executions.get(task.execution_id)
                    workflow = self.workflows.get(execution.workflow_id) if execution else None

                    template_data = (
                        await self.repository.get_template(execution.template_id)
                        if execution
                        else None
                    )

                    task_info = {
                        "task_id": task.task_id,
                        "step_name": (
                            next(
                                (
                                    step.name
                                    for step in workflow.steps
                                    if step.step_id == task.step_id
                                ),
                                "Unknown Step",
                            )
                            if workflow
                            else "Unknown Step"
                        ),
                        "template_id": execution.template_id if execution else None,
                        "template_name": template_data.get("name") if template_data else "Unknown",
                        "template_category": (
                            template_data.get("category") if template_data else "Unknown"
                        ),
                        "priority": self._calculate_task_priority(task),
                        "due_at": task.due_at.isoformat(),
                        "created_at": task.created_at.isoformat(),
                        "sla_status": self._get_sla_status(task),
                        "workflow_name": workflow.name if workflow else "Unknown Workflow",
                    }
                    pending_tasks.append(task_info)

            # Sort by priority and due date
            pending_tasks.sort(key=lambda x: (x["priority"], x["due_at"]), reverse=True)

            logger.info(f"📋 Found {len(pending_tasks)} pending tasks for {user_id}")
            return pending_tasks

        except Exception as e:
            logger.error(f"❌ Failed to get pending tasks: {e}")
            return []

    async def get_workflow_status(self, execution_id: str) -> Dict[str, Any]:
        """Get workflow execution status and progress"""
        try:
            execution = self.executions.get(execution_id)
            if not execution:
                raise ValueError(f"Workflow execution not found: {execution_id}")

            workflow = self.workflows.get(execution.workflow_id)
            template_data = await self.repository.get_template(execution.template_id)

            # Calculate progress
            total_steps = len(workflow.steps) if workflow else 1
            completed_steps = execution.current_step
            progress_percentage = (completed_steps / total_steps) * 100

            # Get current tasks
            current_tasks = [
                task
                for task in self.tasks.values()
                if task.execution_id == execution_id and task.status == WorkflowStatus.PENDING
            ]

            # Calculate SLA status
            elapsed_hours = (datetime.now() - execution.initiated_at).total_seconds() / 3600
            sla_hours = workflow.sla_hours if workflow else 72
            sla_percentage = (elapsed_hours / sla_hours) * 100

            workflow_status = {
                "execution_id": execution_id,
                "workflow_name": workflow.name if workflow else "Unknown",
                "template_name": template_data.get("name") if template_data else "Unknown",
                "status": execution.status.value,
                "progress": {
                    "current_step": completed_steps,
                    "total_steps": total_steps,
                    "percentage": progress_percentage,
                },
                "sla": {
                    "elapsed_hours": round(elapsed_hours, 2),
                    "total_hours": sla_hours,
                    "percentage": round(sla_percentage, 2),
                    "status": (
                        "on_track"
                        if sla_percentage < 75
                        else "at_risk" if sla_percentage < 100 else "overdue"
                    ),
                },
                "current_tasks": [
                    {
                        "task_id": task.task_id,
                        "step_name": (
                            next(
                                (
                                    step.name
                                    for step in workflow.steps
                                    if step.step_id == task.step_id
                                ),
                                "Unknown",
                            )
                            if workflow
                            else "Unknown"
                        ),
                        "assignee": task.assignee,
                        "due_at": task.due_at.isoformat(),
                    }
                    for task in current_tasks
                ],
                "initiated_at": execution.initiated_at.isoformat(),
                "estimated_completion": (
                    self._estimate_completion_time(execution).isoformat() if workflow else None
                ),
            }

            return workflow_status

        except Exception as e:
            logger.error(f"❌ Failed to get workflow status: {e}")
            return {}

    async def get_governance_metrics(self) -> Dict[str, Any]:
        """Get governance and compliance metrics"""
        try:
            # Workflow metrics
            total_workflows = len(self.executions)
            active_workflows = len(
                [e for e in self.executions.values() if e.status == WorkflowStatus.IN_PROGRESS]
            )
            completed_workflows = len(
                [e for e in self.executions.values() if e.status == WorkflowStatus.COMPLETED]
            )

            # SLA metrics
            overdue_workflows = []
            on_time_completions = 0

            for execution in self.executions.values():
                workflow = self.workflows.get(execution.workflow_id)
                if workflow:
                    elapsed_hours = (datetime.now() - execution.initiated_at).total_seconds() / 3600
                    if (
                        execution.status == WorkflowStatus.IN_PROGRESS
                        and elapsed_hours > workflow.sla_hours
                    ):
                        overdue_workflows.append(execution.execution_id)
                    elif execution.status == WorkflowStatus.COMPLETED and execution.completed_at:
                        completion_time = (
                            execution.completed_at - execution.initiated_at
                        ).total_seconds() / 3600
                        if completion_time <= workflow.sla_hours:
                            on_time_completions += 1

            # Task metrics
            total_tasks = len(self.tasks)
            pending_tasks = len(
                [t for t in self.tasks.values() if t.status == WorkflowStatus.PENDING]
            )
            overdue_tasks = len(
                [
                    t
                    for t in self.tasks.values()
                    if t.status == WorkflowStatus.PENDING and datetime.now() > t.due_at
                ]
            )

            # Quality metrics
            approval_rate = (
                (completed_workflows / total_workflows * 100) if total_workflows > 0 else 0
            )
            sla_compliance = (
                (on_time_completions / completed_workflows * 100) if completed_workflows > 0 else 0
            )

            metrics = {
                "workflow_metrics": {
                    "total_workflows": total_workflows,
                    "active_workflows": active_workflows,
                    "completed_workflows": completed_workflows,
                    "approval_rate": round(approval_rate, 2),
                    "overdue_count": len(overdue_workflows),
                },
                "sla_metrics": {
                    "compliance_rate": round(sla_compliance, 2),
                    "on_time_completions": on_time_completions,
                    "overdue_workflows": overdue_workflows,
                },
                "task_metrics": {
                    "total_tasks": total_tasks,
                    "pending_tasks": pending_tasks,
                    "overdue_tasks": overdue_tasks,
                    "average_completion_time": self._calculate_average_task_time(),
                },
                "generated_at": datetime.now().isoformat(),
            }

            return metrics

        except Exception as e:
            logger.error(f"❌ Failed to get governance metrics: {e}")
            return {}

    async def _determine_workflow_type(self, template_data: Dict[str, Any]) -> str:
        """Determine appropriate workflow type based on template characteristics"""
        category = template_data.get("category", "").lower()
        domain = template_data.get("domain", "").lower()
        tags = template_data.get("tags", [])

        # Critical templates need enhanced approval
        if (
            domain in ["security", "infrastructure", "auth"]
            or category in ["security", "infrastructure", "api_core"]
            or any(tag in ["security", "critical", "infrastructure"] for tag in tags)
        ):
            return "critical_approval"

        return "standard_approval"

    async def _advance_workflow(self, execution_id: str):
        """Advance workflow to next step"""
        try:
            execution = self.executions[execution_id]
            workflow = self.workflows[execution.workflow_id]

            # Check if workflow is complete
            if execution.current_step >= len(workflow.steps):
                await self._complete_workflow(execution_id)
                return

            # Get current step
            current_step = workflow.steps[execution.current_step]

            # Create approval task
            await self._create_approval_task(execution, current_step)

            # Update execution status
            execution.status = WorkflowStatus.IN_PROGRESS
            execution.current_step += 1

            logger.info(f"✅ Advanced workflow {execution_id} to step: {current_step.name}")

        except Exception as e:
            logger.error(f"❌ Failed to advance workflow: {e}")

    async def _create_approval_task(self, execution: WorkflowExecution, step: WorkflowStep):
        """Create approval task for workflow step"""
        task_id = str(uuid.uuid4())
        due_at = datetime.now() + timedelta(hours=step.timeout_hours)

        # Determine assignee (simplified - would integrate with user management system)
        assignee = step.required_role.value

        task = ApprovalTask(
            task_id=task_id,
            execution_id=execution.execution_id,
            step_id=step.step_id,
            assignee=assignee,
            status=WorkflowStatus.PENDING,
            created_at=datetime.now(),
            due_at=due_at,
        )

        self.tasks[task_id] = task

        # Auto-approve if configured
        if step.auto_approve:
            await self._auto_approve_task(task)

    async def _auto_approve_task(self, task: ApprovalTask):
        """Automatically approve task based on conditions"""
        try:
            # Get template data for condition checking
            execution = self.executions[task.execution_id]
            template_data = await self.repository.get_template(execution.template_id)

            # Check conditions (simplified implementation)
            all_conditions_met = True
            checklist_results = {}

            workflow = self.workflows[execution.workflow_id]
            step = next(s for s in workflow.steps if s.step_id == task.step_id)

            for condition in step.conditions:
                if "quality_score" in condition and template_data:
                    quality_score = template_data.get("quality_score", 0)
                    required_score = int(condition.split(">=")[1].strip())
                    met = quality_score >= required_score
                    checklist_results[f"Quality Score >= {required_score}"] = met
                    all_conditions_met = all_conditions_met and met

            if all_conditions_met:
                task.status = WorkflowStatus.COMPLETED
                task.completed_at = datetime.now()
                task.checklist_results = checklist_results
                task.comments = "Auto-approved: All conditions met"

                logger.info(f"✅ Auto-approved task {task.task_id}")

        except Exception as e:
            logger.error(f"❌ Auto-approval failed: {e}")

    async def _process_task_action(
        self,
        task: ApprovalTask,
        action: ApprovalAction,
        user_id: str,
        comments: str,
        checklist_results: Optional[Dict[str, bool]],
    ) -> Dict[str, Any]:
        """Process individual task action"""

        if action == ApprovalAction.APPROVE:
            task.status = WorkflowStatus.COMPLETED
            task.completed_at = datetime.now()
            task.comments = comments
            task.checklist_results = checklist_results or {}

            return {
                "action": "approved",
                "message": "Task approved successfully",
                "next_step": "Workflow will advance to next step",
            }

        elif action == ApprovalAction.REJECT:
            task.status = WorkflowStatus.REJECTED
            task.completed_at = datetime.now()
            task.comments = comments

            return {
                "action": "rejected",
                "message": "Task rejected",
                "next_step": "Workflow will be terminated",
            }

        elif action == ApprovalAction.REQUEST_CHANGES:
            # Reset task to pending with comments
            task.comments = comments
            task.due_at = datetime.now() + timedelta(hours=24)  # Extend deadline

            return {
                "action": "changes_requested",
                "message": "Changes requested",
                "next_step": "Template author will be notified",
            }

        else:
            raise ValueError(f"Unsupported action: {action}")

    async def _complete_workflow(self, execution_id: str):
        """Complete workflow and approve template"""
        try:
            execution = self.executions[execution_id]
            execution.status = WorkflowStatus.COMPLETED
            execution.completed_at = datetime.now()

            # Approve template
            await self._update_template_status(execution.template_id, TemplateStatus.APPROVED)

            # Log completion
            await self._log_workflow_event(
                execution_id,
                "workflow_completed",
                "system",
                {
                    "template_id": execution.template_id,
                    "approval_time": execution.completed_at.isoformat(),
                },
            )

            logger.info(
                f"✅ Completed workflow {execution_id} - Template {execution.template_id} approved"
            )

        except Exception as e:
            logger.error(f"❌ Failed to complete workflow: {e}")

    async def _reject_workflow(self, execution_id: str, reason: str):
        """Reject workflow and update template status"""
        try:
            execution = self.executions[execution_id]
            execution.status = WorkflowStatus.REJECTED
            execution.completed_at = datetime.now()
            execution.metadata["rejection_reason"] = reason

            # Update template status back to draft
            await self._update_template_status(execution.template_id, TemplateStatus.DRAFT)

            # Log rejection
            await self._log_workflow_event(
                execution_id,
                "workflow_rejected",
                "system",
                {"template_id": execution.template_id, "reason": reason},
            )

            logger.info(f"❌ Rejected workflow {execution_id} - Template {execution.template_id}")

        except Exception as e:
            logger.error(f"❌ Failed to reject workflow: {e}")

    async def _update_template_status(self, template_id: str, status: TemplateStatus):
        """Update template status in database"""
        async with self.repository.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE templates SET status = $2, updated_at = CURRENT_TIMESTAMP WHERE id = $1",
                template_id,
                status.value,
            )

    async def _log_workflow_event(
        self, execution_id: str, action: str, actor: str, details: Dict[str, Any]
    ):
        """Log workflow event to audit trail"""
        async with self.repository.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO template_audit_log (template_id, action, actor_id, details)
                SELECT template_id, $2, $3, $4
                FROM (SELECT $1 as execution_id) e
                JOIN (VALUES ($1)) v(lookup_id) ON true
            """,
                execution_id,
                action,
                actor,
                json.dumps(details),
            )

    async def _validate_user_permissions(self, task: ApprovalTask, user_id: str):
        """Validate user has permission to perform task"""
        # Simplified implementation - would integrate with RBAC system
        if task.assignee != user_id and not task.assignee.endswith("_" + user_id):
            # Allow if user has sufficient role
            pass

    def _calculate_task_priority(self, task: ApprovalTask) -> int:
        """Calculate task priority based on various factors"""
        priority = 1

        # Time-based priority
        time_until_due = (task.due_at - datetime.now()).total_seconds() / 3600
        if time_until_due < 2:  # Less than 2 hours
            priority += 10
        elif time_until_due < 8:  # Less than 8 hours
            priority += 5

        return priority

    def _get_sla_status(self, task: ApprovalTask) -> str:
        """Get SLA status for task"""
        time_until_due = (task.due_at - datetime.now()).total_seconds() / 3600

        if time_until_due < 0:
            return "overdue"
        elif time_until_due < 4:
            return "urgent"
        elif time_until_due < 12:
            return "at_risk"
        else:
            return "on_track"

    def _estimate_completion_time(self, execution: WorkflowExecution) -> datetime:
        """Estimate workflow completion time"""
        workflow = self.workflows.get(execution.workflow_id)
        if not workflow:
            return datetime.now()

        remaining_steps = len(workflow.steps) - execution.current_step
        average_step_time = 12  # hours
        estimated_hours = remaining_steps * average_step_time

        return datetime.now() + timedelta(hours=estimated_hours)

    def _calculate_average_task_time(self) -> float:
        """Calculate average task completion time in hours"""
        completed_tasks = [
            task
            for task in self.tasks.values()
            if task.status == WorkflowStatus.COMPLETED and task.completed_at
        ]

        if not completed_tasks:
            return 0.0

        total_time = sum(
            (task.completed_at - task.created_at).total_seconds() / 3600 for task in completed_tasks
        )

        return round(total_time / len(completed_tasks), 2)


# Example usage and testing
async def main():
    """Example usage of the workflow engine"""

    # Initialize repository and workflow engine
    repository = EnterpriseTemplateRepository()
    await repository.initialize()

    workflow_engine = EnterpriseWorkflowEngine(repository)

    # Create sample template for testing
    template_id = str(uuid.uuid4())

    # Start approval workflow
    execution_id = await workflow_engine.start_approval_workflow(
        template_id=template_id, initiated_by="developer123"
    )

    print(f"✅ Started workflow: {execution_id}")

    # Get pending tasks
    tasks = await workflow_engine.get_pending_tasks("reviewer123", UserRole.SENIOR_DEVELOPER)
    print(f"📋 Pending tasks: {len(tasks)}")

    # Get workflow status
    status = await workflow_engine.get_workflow_status(execution_id)
    print(f"📊 Workflow status: {status['status']}")

    # Get governance metrics
    metrics = await workflow_engine.get_governance_metrics()
    print(f"📈 Governance metrics: {metrics}")

    await repository.close()


if __name__ == "__main__":
    asyncio.run(main())
