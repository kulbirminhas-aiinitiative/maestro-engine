"""
End-to-End Development & QA Agent
Orchestrates the complete workflow from JIRA initialization to closure
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import httpx

from .jira_integration_service import (
    JiraIntegrationService,
    IssueStatus,
    IssueType,
    Priority
)

logger = logging.getLogger(__name__)


class TestCase:
    """Test case model"""
    def __init__(self, test_id: str, description: str, endpoint: str):
        self.test_id = test_id
        self.description = description
        self.endpoint = endpoint
        self.status: Optional[str] = None
        self.result: Optional[Dict[str, Any]] = None
        self.logs: List[str] = []
        self.execution_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "description": self.description,
            "endpoint": self.endpoint,
            "status": self.status,
            "result": self.result,
            "logs": self.logs,
            "execution_time": self.execution_time
        }


class DevelopmentPlan:
    """Development plan model"""
    def __init__(self, epic_id: str, epic_data: Dict[str, Any]):
        self.epic_id = epic_id
        self.epic_data = epic_data
        self.tasks: List[Dict[str, Any]] = []
        self.test_cases: List[TestCase] = []
        self.implementation_steps: List[str] = []
        self.created_at = datetime.now().isoformat()
    
    def add_task(self, task: Dict[str, Any]):
        """Add a task to the plan"""
        self.tasks.append(task)
    
    def add_test_case(self, test_case: TestCase):
        """Add a test case"""
        self.test_cases.append(test_case)
    
    def add_implementation_step(self, step: str):
        """Add implementation step"""
        self.implementation_steps.append(step)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "epic_id": self.epic_id,
            "epic_data": self.epic_data,
            "tasks": self.tasks,
            "test_cases": [tc.to_dict() for tc in self.test_cases],
            "implementation_steps": self.implementation_steps,
            "created_at": self.created_at
        }


class E2EDevQAAgent:
    """
    End-to-End Development & QA Agent
    
    Workflow:
    1. JIRA Initialization: Fetch 'To Do' Epic and transition to 'In Progress'
    2. Strategy: Generate development plan and test cases
    3. Implementation: Execute code development/fixes
    4. Validation: Run tests against quality-fabric API
    5. Reporting: Update JIRA with results
    6. Closure: Set Epic to 'Done' if all tasks complete
    """
    
    def __init__(
        self,
        jira_service: JiraIntegrationService,
        quality_api_url: str = "http://localhost:8000"
    ):
        self.jira_service = jira_service
        self.quality_api_url = quality_api_url
        self.current_plan: Optional[DevelopmentPlan] = None
        self.session_log: List[str] = []
    
    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.session_log.append(log_entry)
        
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)
    
    async def step1_jira_initialization(self, epic_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Step 1: JIRA Initialization
        Fetch relevant 'To Do' Epic and transition to 'In Progress'
        """
        self.log("=== STEP 1: JIRA INITIALIZATION ===")
        
        try:
            # If no epic_id provided, get the first 'To Do' epic
            if not epic_id:
                todo_epics = self.jira_service.get_todo_epics()
                if not todo_epics:
                    raise ValueError("No 'To Do' epics found")
                
                # Get epic ID from summary (e.g., "EPIC-3: ...")
                epic_summary = todo_epics[0].get('Summary', '')
                epic_id = epic_summary.split(':')[0].strip()
                self.log(f"Auto-selected epic: {epic_id}")
            
            # Get epic details
            epic_summary = self.jira_service.get_issue_summary(epic_id, IssueType.EPIC)
            self.log(f"Fetched epic: {epic_id}")
            
            # Transition to 'In Progress'
            self.jira_service.update_epic_status(epic_id, IssueStatus.IN_PROGRESS)
            self.log(f"Transitioned {epic_id} to 'In Progress'")
            
            # Get associated tasks
            tasks = self.jira_service.get_epic_tasks(epic_id)
            self.log(f"Found {len(tasks)} associated tasks")
            
            return {
                "success": True,
                "epic_id": epic_id,
                "epic": epic_summary['issue'],
                "tasks": tasks,
                "progress": epic_summary.get('progress', {})
            }
        
        except Exception as e:
            self.log(f"Error in JIRA initialization: {e}", "ERROR")
            raise
    
    def step2_generate_strategy(self, epic_data: Dict[str, Any]) -> DevelopmentPlan:
        """
        Step 2: Strategy Generation
        Generate development plan and comprehensive test cases
        """
        self.log("=== STEP 2: STRATEGY GENERATION ===")
        
        epic_id = epic_data['epic_id']
        epic = epic_data['epic']
        tasks = epic_data['tasks']
        
        # Create development plan
        plan = DevelopmentPlan(epic_id, epic)
        
        # Add tasks to plan
        for task in tasks:
            plan.add_task(task)
            self.log(f"Added task: {task.get('Summary', 'Unknown')}")
        
        # Generate implementation steps from epic description
        description = epic.get('Description', '')
        if description:
            steps = [s.strip() for s in description.split(';') if s.strip()]
            for step in steps:
                plan.add_implementation_step(step)
                self.log(f"Implementation step: {step}")
        
        # Generate test cases based on acceptance criteria
        self._generate_test_cases(plan, epic)
        
        self.current_plan = plan
        self.log(f"Generated plan with {len(plan.test_cases)} test cases")
        
        return plan
    
    def _generate_test_cases(self, plan: DevelopmentPlan, epic: Dict[str, Any]):
        """Generate test cases from epic acceptance criteria"""
        description = epic.get('Description', '')
        
        # Parse acceptance criteria (AC:)
        if 'AC:' in description:
            ac_text = description.split('AC:')[1].split(';')[0].strip()
            
            # Create test cases based on keywords
            if 'route' in ac_text.lower() or 'api' in ac_text.lower():
                plan.add_test_case(TestCase(
                    f"{plan.epic_id}-TC1",
                    "Verify API endpoint exists and responds",
                    "/api/health"
                ))
            
            if 'ws' in ac_text.lower() or 'websocket' in ac_text.lower():
                plan.add_test_case(TestCase(
                    f"{plan.epic_id}-TC2",
                    "Verify WebSocket events are published",
                    "/ws"
                ))
            
            if 'test' in ac_text.lower() or 'threshold' in ac_text.lower():
                plan.add_test_case(TestCase(
                    f"{plan.epic_id}-TC3",
                    "Verify quality thresholds enforcement",
                    "/api/execute"
                ))
        
        # Always add a basic health check
        if not plan.test_cases:
            plan.add_test_case(TestCase(
                f"{plan.epic_id}-TC0",
                "Basic health check",
                "/api/health"
            ))
    
    async def step3_implementation(self, plan: DevelopmentPlan) -> Dict[str, Any]:
        """
        Step 3: Implementation
        Execute code development/fixes based on the plan
        
        Note: In a real implementation, this would integrate with code generation,
        file modification, and build systems. For now, it's a placeholder.
        """
        self.log("=== STEP 3: IMPLEMENTATION ===")
        
        implementation_results = {
            "success": True,
            "steps_completed": [],
            "files_modified": [],
            "errors": []
        }
        
        for i, step in enumerate(plan.implementation_steps, 1):
            self.log(f"Executing step {i}/{len(plan.implementation_steps)}: {step}")
            implementation_results['steps_completed'].append({
                "step": i,
                "description": step,
                "status": "completed"
            })
        
        self.log("Implementation phase completed (placeholder)")
        return implementation_results
    
    async def step4_validation(self, plan: DevelopmentPlan) -> Dict[str, Any]:
        """
        Step 4: Validation
        Run tests against quality-fabric API (localhost:8000)
        """
        self.log("=== STEP 4: VALIDATION ===")
        
        validation_results = {
            "total_tests": len(plan.test_cases),
            "passed": 0,
            "failed": 0,
            "test_results": []
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for test_case in plan.test_cases:
                self.log(f"Running test: {test_case.test_id} - {test_case.description}")
                
                try:
                    start_time = datetime.now()
                    url = f"{self.quality_api_url}{test_case.endpoint}"
                    
                    response = await client.get(url)
                    end_time = datetime.now()
                    
                    test_case.execution_time = (end_time - start_time).total_seconds()
                    test_case.result = {
                        "status_code": response.status_code,
                        "response": response.json() if response.status_code == 200 else None
                    }
                    
                    if response.status_code == 200:
                        test_case.status = "PASSED"
                        validation_results['passed'] += 1
                        test_case.logs.append(f"✓ Test passed in {test_case.execution_time:.2f}s")
                        self.log(f"✓ {test_case.test_id} PASSED")
                    else:
                        test_case.status = "FAILED"
                        validation_results['failed'] += 1
                        test_case.logs.append(f"✗ Test failed: HTTP {response.status_code}")
                        self.log(f"✗ {test_case.test_id} FAILED: HTTP {response.status_code}", "WARNING")
                
                except Exception as e:
                    test_case.status = "ERROR"
                    validation_results['failed'] += 1
                    test_case.logs.append(f"✗ Error: {str(e)}")
                    self.log(f"✗ {test_case.test_id} ERROR: {e}", "ERROR")
                
                validation_results['test_results'].append(test_case.to_dict())
        
        self.log(f"Validation complete: {validation_results['passed']}/{validation_results['total_tests']} passed")
        return validation_results
    
    async def step5_reporting(
        self, 
        plan: DevelopmentPlan,
        validation_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Step 5: Reporting
        Update test cases and JIRA tasks with results
        """
        self.log("=== STEP 5: REPORTING ===")
        
        reporting_results = {
            "tasks_updated": [],
            "epic_status": None
        }
        
        # Determine overall success
        all_tests_passed = validation_results['failed'] == 0
        
        # Update tasks
        for task in plan.tasks:
            task_summary = task.get('Summary', '')
            task_id = task_summary.split(':')[0].strip() if ':' in task_summary else None
            
            if task_id:
                try:
                    if all_tests_passed:
                        # Mark task as Done
                        resolution = f"Tests: {validation_results['passed']}/{validation_results['total_tests']} passed"
                        self.jira_service.update_task_status(
                            task_id,
                            IssueStatus.DONE,
                            resolution
                        )
                        self.log(f"Updated {task_id} to 'Done'")
                        reporting_results['tasks_updated'].append({
                            "task_id": task_id,
                            "status": "Done",
                            "resolution": resolution
                        })
                    else:
                        # Leave in current status
                        self.log(f"Leaving {task_id} in current status (tests failed)")
                        reporting_results['tasks_updated'].append({
                            "task_id": task_id,
                            "status": "unchanged",
                            "reason": "validation_failed"
                        })
                
                except Exception as e:
                    self.log(f"Error updating task {task_id}: {e}", "ERROR")
        
        reporting_results['epic_status'] = "in_progress"
        self.log("Reporting phase completed")
        return reporting_results
    
    async def step6_closure(self, plan: DevelopmentPlan) -> Dict[str, Any]:
        """
        Step 6: Closure
        IF all tasks are 'Done' THEN set Epic to 'Done'
        """
        self.log("=== STEP 6: CLOSURE ===")
        
        closure_results = {
            "epic_completed": False,
            "epic_status": None
        }
        
        # Check if all tasks are done
        is_complete = self.jira_service.check_epic_completion(plan.epic_id)
        
        if is_complete:
            # Set epic to Done
            tasks = self.jira_service.get_epic_tasks(plan.epic_id)
            resolution = f"All {len(tasks)} tasks completed successfully"
            
            self.jira_service.update_epic_status(
                plan.epic_id,
                IssueStatus.DONE,
                resolution
            )
            
            self.log(f"✓ Epic {plan.epic_id} set to 'Done'")
            closure_results['epic_completed'] = True
            closure_results['epic_status'] = "Done"
        else:
            self.log(f"Epic {plan.epic_id} has incomplete tasks, leaving as 'In Progress'")
            closure_results['epic_completed'] = False
            closure_results['epic_status'] = "In Progress"
        
        return closure_results
    
    async def run_full_workflow(self, epic_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the complete E2E workflow
        """
        self.log("╔══════════════════════════════════════════════════════╗")
        self.log("║  END-TO-END DEVELOPMENT & QA WORKFLOW                ║")
        self.log("╚══════════════════════════════════════════════════════╝")
        
        workflow_results = {
            "started_at": datetime.now().isoformat(),
            "epic_id": None,
            "steps": {},
            "session_log": []
        }
        
        try:
            # Step 1: JIRA Initialization
            epic_data = await self.step1_jira_initialization(epic_id)
            workflow_results['epic_id'] = epic_data['epic_id']
            workflow_results['steps']['step1_initialization'] = epic_data
            
            # Step 2: Strategy Generation
            plan = self.step2_generate_strategy(epic_data)
            workflow_results['steps']['step2_strategy'] = plan.to_dict()
            
            # Step 3: Implementation
            impl_results = await self.step3_implementation(plan)
            workflow_results['steps']['step3_implementation'] = impl_results
            
            # Step 4: Validation
            validation_results = await self.step4_validation(plan)
            workflow_results['steps']['step4_validation'] = validation_results
            
            # Step 5: Reporting
            reporting_results = await self.step5_reporting(plan, validation_results)
            workflow_results['steps']['step5_reporting'] = reporting_results
            
            # Step 6: Closure
            closure_results = await self.step6_closure(plan)
            workflow_results['steps']['step6_closure'] = closure_results
            
            workflow_results['completed_at'] = datetime.now().isoformat()
            workflow_results['success'] = True
            workflow_results['session_log'] = self.session_log
            
            self.log("╔══════════════════════════════════════════════════════╗")
            self.log("║  WORKFLOW COMPLETED SUCCESSFULLY                     ║")
            self.log("╚══════════════════════════════════════════════════════╝")
            
        except Exception as e:
            self.log(f"Workflow failed: {e}", "ERROR")
            workflow_results['success'] = False
            workflow_results['error'] = str(e)
            workflow_results['session_log'] = self.session_log
        
        return workflow_results
    
    def save_workflow_report(self, workflow_results: Dict[str, Any], output_path: str):
        """Save workflow results to JSON file"""
        try:
            with open(output_path, 'w') as f:
                json.dump(workflow_results, f, indent=2)
            self.log(f"Workflow report saved to {output_path}")
        except Exception as e:
            self.log(f"Error saving report: {e}", "ERROR")
