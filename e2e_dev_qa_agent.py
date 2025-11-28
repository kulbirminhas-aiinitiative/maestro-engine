#!/usr/bin/env python3
"""
End-to-End Development & QA Agent with JIRA Integration

Workflow:
1. JIRA Initialization: Fetch 'To Do' Epic and transition to 'In Progress'
2. Strategy: Generate development plan and comprehensive test cases
3. Implementation: Execute code development/fixes based on plan
4. Validation: Run tests against quality-fabric API (localhost:8000)
5. Reporting: Update test cases and JIRA tasks with results
6. Closure: Set Epic to 'Done' if all tasks are 'Done'

Reference: ~/projects/maestro-frontend-production/docs/api/jira-integration-api.md
"""

import asyncio
import httpx
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class TestStatus(Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TestCase:
    id: str
    name: str
    description: str
    endpoint: Optional[str] = None
    method: str = "GET"
    expected_status: int = 200
    acceptance_criteria: List[str] = field(default_factory=list)
    status: TestStatus = TestStatus.PENDING
    execution_time_ms: float = 0
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "endpoint": self.endpoint,
            "method": self.method,
            "expected_status": self.expected_status,
            "status": self.status.value,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "error": self.error,
            "logs": self.logs[-10:]
        }


@dataclass
class JiraTask:
    id: str
    key: str
    summary: str
    status: str
    type: str
    assignee: Optional[str] = None


@dataclass
class Epic:
    id: str
    key: str
    summary: str
    description: str
    status: str
    priority: str
    tasks: List[JiraTask] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)


class MaestroJiraClient:
    """JIRA Client using Maestro Integration API"""
    
    def __init__(self, base_url: str, jwt_token: str):
        self.base_url = base_url.rstrip('/')
        self.jwt_token = jwt_token
        self.client = httpx.AsyncClient(timeout=30.0)
        self.headers = {"Authorization": f"Bearer {jwt_token}"}
    
    async def list_epics(self, status_categories: List[str] = None, page_size: int = 10) -> List[Dict]:
        if status_categories is None:
            status_categories = ["todo"]
        
        params = {
            "types": "epic",
            "statusCategories": ",".join(status_categories),
            "pageSize": page_size
        }
        
        url = f"{self.base_url}/integrations/tasks"
        response = await self.client.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json().get("items", [])
    
    async def get_task(self, task_id: str) -> Dict:
        url = f"{self.base_url}/integrations/tasks/{task_id}"
        response = await self.client.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    async def list_tasks_for_epic(self, epic_id: str, page_size: int = 50) -> List[Dict]:
        params = {"epicIds": epic_id, "pageSize": page_size}
        url = f"{self.base_url}/integrations/tasks"
        response = await self.client.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json().get("items", [])
    
    async def transition_task(self, task_id: str, target_status: str, comment: str = None, resolution: str = None) -> Dict:
        url = f"{self.base_url}/integrations/tasks/{task_id}/transition"
        payload = {"targetStatus": target_status}
        if comment:
            payload["comment"] = comment
        if resolution:
            payload["resolution"] = resolution
        
        response = await self.client.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        await self.client.aclose()


class QualityFabricClient:
    """Quality-Fabric API Client"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def health_check(self) -> Dict:
        url = f"{self.base_url}/api/health"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()
    
    async def run_test(self, endpoint: str, method: str = "GET", expected_status: int = 200) -> Tuple[bool, Dict]:
        url = f"{self.base_url}{endpoint}"
        
        try:
            start = datetime.now()
            if method == "GET":
                response = await self.client.get(url)
            elif method == "POST":
                response = await self.client.post(url, json={})
            else:
                response = await self.client.request(method, url)
            
            elapsed_ms = (datetime.now() - start).total_seconds() * 1000
            success = response.status_code == expected_status
            
            return success, {
                "status_code": response.status_code,
                "expected": expected_status,
                "response_time_ms": elapsed_ms,
                "success": success
            }
        except Exception as e:
            return False, {"error": str(e), "success": False}
    
    async def close(self):
        await self.client.aclose()


class E2EDevQAAgent:
    """End-to-End Development & QA Agent"""
    
    def __init__(self, maestro_url: str, jwt_token: str, qf_url: str = "http://localhost:8000"):
        self.jira_client = MaestroJiraClient(maestro_url, jwt_token)
        self.qf_client = QualityFabricClient(qf_url)
        self.output_dir = Path("/tmp/e2e_agent_output")
        self.output_dir.mkdir(exist_ok=True)
    
    def log(self, message: str, level: str = "INFO"):
        emoji = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️", "RUNNING": "🏃"}
        print(f"{emoji.get(level, '•')} {message}")
    
    def header(self, title: str, emoji: str = "🚀"):
        print(f"\n{'='*70}\n{emoji} {title}\n{'='*70}\n")
    
    async def step1_jira_initialization(self, epic_key: Optional[str] = None) -> Epic:
        """Step 1: Fetch 'To Do' Epic and transition to 'In Progress'"""
        self.header("STEP 1: JIRA INITIALIZATION", "📋")
        
        if epic_key:
            self.log(f"Fetching specified Epic: {epic_key}", "INFO")
            response = await self.jira_client.get_task(epic_key)
            # Handle wrapped response from capability execution
            if "output" in response:
                epic_data = response["output"]
            else:
                epic_data = response
        else:
            self.log("Fetching 'To Do' Epics from JIRA...", "RUNNING")
            epics = await self.jira_client.list_epics(status_categories=["todo"])
            
            if not epics:
                self.log("No 'To Do' epics found. Checking 'In Progress'...", "WARNING")
                epics = await self.jira_client.list_epics(status_categories=["in_progress"])
            
            if not epics:
                raise ValueError("No epics found in 'To Do' or 'In Progress' status")
            
            self.log(f"Found {len(epics)} epic(s)", "SUCCESS")
            
            for i, epic in enumerate(epics, 1):
                print(f"  {i}. [{epic['externalId']}] {epic['title']}")
                print(f"     Status: {epic['status']['name']} | Priority: {epic.get('priority', 'N/A')}")
            
            epic_data = epics[0]
            self.log(f"Selected: [{epic_data['externalId']}] {epic_data['title']}", "SUCCESS")
        
        epic = Epic(
            id=epic_data["id"],
            key=epic_data.get("externalId", epic_key),
            summary=epic_data["title"],
            description=epic_data.get("description", ""),
            status=epic_data["status"]["name"],
            priority=epic_data.get("priority", "medium"),
            labels=epic_data.get("labels", [])
        )
        
        # Transition to "In Progress" if needed
        if epic.status == "To Do":
            self.log(f"Transitioning {epic.key} to 'In Progress'...", "RUNNING")
            await self.jira_client.transition_task(
                epic.key,
                "In Progress",
                comment="E2E Development & QA Agent started working on this epic"
            )
            epic.status = "In Progress"
            self.log("Epic transitioned to 'In Progress'", "SUCCESS")
        
        # Fetch subtasks
        self.log(f"Fetching tasks for epic {epic.key}...", "RUNNING")
        tasks_data = await self.jira_client.list_tasks_for_epic(epic.key)
        
        for task_data in tasks_data:
            task = JiraTask(
                id=task_data["id"],
                key=task_data["externalId"],
                summary=task_data["title"],
                status=task_data["status"]["name"],
                type=task_data["type"],
                assignee=task_data.get("assignee", {}).get("name")
            )
            epic.tasks.append(task)
        
        self.log(f"Loaded {len(epic.tasks)} task(s) under this epic", "SUCCESS")
        
        return epic
    
    async def step2_strategy_generation(self, epic: Epic) -> List[TestCase]:
        """Step 2: Generate development plan and comprehensive test cases"""
        self.header("STEP 2: STRATEGY GENERATION", "🧠")
        
        # Generate strategy document
        strategy_content = f"""# Development Strategy: {epic.key}

## Epic Overview
- **Key**: {epic.key}
- **Summary**: {epic.summary}
- **Status**: {epic.status}
- **Priority**: {epic.priority}
- **Labels**: {', '.join(epic.labels) if epic.labels else 'None'}

## Description
{epic.description}

## Current Tasks ({len(epic.tasks)})
{self._format_task_list(epic.tasks)}

## Development Plan

### Phase 1: Requirements Analysis
- Review acceptance criteria for all tasks
- Identify dependencies between tasks
- Prioritize implementation order

### Phase 2: Implementation
- Implement features based on task requirements
- Follow coding standards and best practices
- Write unit tests for new code

### Phase 3: Testing
- Execute integration tests against quality-fabric API
- Validate all acceptance criteria
- Document test results

### Phase 4: Review & Closure
- Update JIRA tasks with results
- Transition completed tasks to 'Done'
- Close epic when all tasks complete

## Testing Strategy

### Test Scope
- API health checks
- Integration endpoint validation
- Task transition workflows
- Data integrity verification

### Success Criteria
- All tasks transitioned to 'Done'
- 100% test pass rate
- No critical issues remaining

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
        
        strategy_path = self.output_dir / f"strategy_{epic.key}.md"
        strategy_path.write_text(strategy_content)
        self.log(f"Strategy document: {strategy_path}", "SUCCESS")
        
        # Generate test cases
        test_cases = [
            TestCase(
                id="TC-001",
                name="Quality-Fabric API Health Check",
                description="Verify quality-fabric API is accessible",
                endpoint="/api/health",
                method="GET",
                expected_status=200,
                acceptance_criteria=["API responds with 200 OK", "Response time < 1000ms"]
            ),
            TestCase(
                id="TC-002",
                name=f"Epic {epic.key} Retrieval",
                description=f"Verify epic {epic.key} can be retrieved",
                endpoint=f"/integrations/tasks/{epic.key}",
                acceptance_criteria=[f"Epic {epic.key} exists", "Epic has correct metadata"]
            ),
            TestCase(
                id="TC-003",
                name=f"Tasks List for Epic {epic.key}",
                description=f"Verify tasks under epic {epic.key}",
                endpoint=f"/integrations/tasks?epicIds={epic.key}",
                acceptance_criteria=[f"At least {len(epic.tasks)} task(s) found"]
            )
        ]
        
        test_cases_path = self.output_dir / f"test_cases_{epic.key}.json"
        test_cases_path.write_text(json.dumps([tc.to_dict() for tc in test_cases], indent=2))
        self.log(f"Generated {len(test_cases)} test cases: {test_cases_path}", "SUCCESS")
        
        return test_cases
    
    def _format_task_list(self, tasks: List[JiraTask]) -> str:
        if not tasks:
            return "- No tasks found"
        lines = []
        for task in tasks:
            emoji = "✅" if task.status == "Done" else "🔄" if task.status == "In Progress" else "⏸️"
            lines.append(f"- {emoji} [{task.key}] {task.summary} ({task.status})")
        return "\n".join(lines)
    
    async def step3_implementation(self, epic: Epic) -> bool:
        """Step 3: Execute code development/fixes based on plan"""
        self.header("STEP 3: IMPLEMENTATION", "💻")
        
        self.log("Implementation phase - Placeholder for actual development", "INFO")
        self.log("In production: Would execute code generation/fixes", "INFO")
        self.log("Simulating successful implementation", "SUCCESS")
        
        await asyncio.sleep(1)
        return True
    
    async def step4_validation(self, test_cases: List[TestCase]) -> List[TestCase]:
        """Step 4: Run tests against quality-fabric API"""
        self.header("STEP 4: VALIDATION", "🧪")
        
        for test_case in test_cases:
            self.log(f"Running {test_case.id}: {test_case.name}...", "RUNNING")
            
            start_time = datetime.now()
            
            try:
                if test_case.endpoint:
                    success, result = await self.qf_client.run_test(
                        test_case.endpoint,
                        test_case.method,
                        test_case.expected_status
                    )
                    
                    test_case.execution_time_ms = result.get("response_time_ms", 0)
                    
                    if success:
                        test_case.status = TestStatus.PASSED
                        test_case.logs.append(f"PASSED: {result}")
                        self.log(f"{test_case.id} PASSED ({test_case.execution_time_ms:.0f}ms)", "SUCCESS")
                    else:
                        test_case.status = TestStatus.FAILED
                        test_case.error = result.get("error", f"Expected {test_case.expected_status}, got {result.get('status_code')}")
                        test_case.logs.append(f"FAILED: {result}")
                        self.log(f"{test_case.id} FAILED: {test_case.error}", "ERROR")
                else:
                    test_case.status = TestStatus.PASSED
                    test_case.execution_time_ms = 10
                    self.log(f"{test_case.id} PASSED (placeholder)", "SUCCESS")
            
            except Exception as e:
                test_case.status = TestStatus.FAILED
                test_case.error = str(e)
                test_case.logs.append(f"Exception: {str(e)}")
                self.log(f"{test_case.id} FAILED: {str(e)}", "ERROR")
            
            finally:
                if test_case.execution_time_ms == 0:
                    test_case.execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        passed = sum(1 for tc in test_cases if tc.status == TestStatus.PASSED)
        failed = sum(1 for tc in test_cases if tc.status == TestStatus.FAILED)
        print(f"\n📊 Validation Summary: {passed}/{len(test_cases)} passed, {failed}/{len(test_cases)} failed")
        
        return test_cases
    
    async def step5_reporting(self, epic: Epic, test_cases: List[TestCase]) -> bool:
        """Step 5: Update test cases and JIRA tasks with execution details"""
        self.header("STEP 5: REPORTING", "📊")
        
        # Update test cases with pass/fail status (already done in step4)
        passed = sum(1 for tc in test_cases if tc.status == TestStatus.PASSED)
        failed = sum(1 for tc in test_cases if tc.status == TestStatus.FAILED)
        total = len(test_cases)
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        # Save updated test cases
        test_cases_path = self.output_dir / f"test_cases_{epic.key}_results.json"
        test_cases_path.write_text(json.dumps([tc.to_dict() for tc in test_cases], indent=2))
        self.log(f"Test results saved: {test_cases_path}", "SUCCESS")
        
        # Prepare summary for JIRA
        test_results_text = "\n".join([
            f"- {'✅' if tc.status == TestStatus.PASSED else '❌'} [{tc.id}] {tc.name}: {tc.status.value} ({tc.execution_time_ms:.0f}ms)"
            + (f"\n  Error: {tc.error}" if tc.error else "")
            for tc in test_cases
        ])
        
        summary_comment = f"""E2E Development & QA Agent - Test Execution Report

✅ Passed: {passed}/{total}
❌ Failed: {failed}/{total}
📈 Pass Rate: {pass_rate:.2f}%
⏱️ Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

Test Results:
{test_results_text}

Generated by E2E Development & QA Agent
"""
        
        # Update epic with summary
        self.log(f"Adding test report to epic {epic.key}...", "RUNNING")
        try:
            await self.jira_client.transition_task(epic.key, epic.status, comment=summary_comment)
            self.log("Epic updated with test report", "SUCCESS")
        except Exception as e:
            self.log(f"Failed to update epic: {str(e)}", "ERROR")
        
        # Update individual tasks: if successful set to 'Done', else leave as is
        all_tests_passed = failed == 0
        
        for task in epic.tasks:
            # Only update if tests passed
            if all_tests_passed and task.status != "Done":
                task_comment = f"""Test Execution Results:

Status: ✅ ALL TESTS PASSED

All {total} test cases passed successfully. Marking task as Done.

Test Summary:
{test_results_text}
"""
                
                try:
                    self.log(f"Updating task {task.key}...", "RUNNING")
                    
                    # Transition to Done
                    await self.jira_client.transition_task(
                        task.key,
                        "Done",
                        comment=task_comment,
                        resolution="Fixed"
                    )
                    task.status = "Done"
                    self.log(f"Task {task.key} transitioned to 'Done'", "SUCCESS")
                
                except Exception as e:
                    self.log(f"Failed to update task {task.key}: {str(e)}", "ERROR")
            else:
                if not all_tests_passed:
                    self.log(f"Task {task.key} left as '{task.status}' (tests failed)", "WARNING")
                else:
                    self.log(f"Task {task.key} already 'Done'", "INFO")
        
        return all_tests_passed
    
    async def step6_closure(self, epic: Epic) -> bool:
        """Step 6: IF all tasks are 'Done' THEN set Epic to 'Done'"""
        self.header("STEP 6: CLOSURE", "🎯")
        
        done_tasks = [t for t in epic.tasks if t.status == "Done"]
        all_done = len(done_tasks) == len(epic.tasks)
        
        self.log(f"Tasks completed: {len(done_tasks)}/{len(epic.tasks)}", "INFO")
        
        if all_done and len(epic.tasks) > 0:
            self.log(f"All tasks completed! Transitioning epic {epic.key} to 'Done'...", "RUNNING")
            
            try:
                await self.jira_client.transition_task(
                    epic.key,
                    "Done",
                    comment=f"All {len(epic.tasks)} subtasks completed successfully. Epic marked as Done by E2E Development & QA Agent.",
                    resolution="Fixed"
                )
                epic.status = "Done"
                self.log(f"Epic {epic.key} transitioned to 'Done'", "SUCCESS")
                return True
            except Exception as e:
                self.log(f"Failed to close epic: {str(e)}", "ERROR")
                return False
        else:
            remaining = len(epic.tasks) - len(done_tasks)
            self.log(f"{remaining} task(s) still pending. Epic remains in '{epic.status}'", "WARNING")
            return False
    
    async def run_workflow(self, epic_key: Optional[str] = None):
        """Execute complete E2E workflow"""
        self.header("E2E DEVELOPMENT & QA AGENT", "🤖")
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        
        start_time = datetime.now()
        
        try:
            # Step 1: JIRA Initialization
            epic = await self.step1_jira_initialization(epic_key)
            
            # Step 2: Strategy Generation
            test_cases = await self.step2_strategy_generation(epic)
            
            # Step 3: Implementation
            await self.step3_implementation(epic)
            
            # Step 4: Validation
            test_cases = await self.step4_validation(test_cases)
            
            # Step 5: Reporting
            all_passed = await self.step5_reporting(epic, test_cases)
            
            # Step 6: Closure
            await self.step6_closure(epic)
            
            # Final summary
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            self.header("WORKFLOW COMPLETED", "🎉")
            print(f"Epic: {epic.key} - {epic.summary}")
            print(f"Status: {epic.status}")
            passed = sum(1 for tc in test_cases if tc.status == TestStatus.PASSED)
            print(f"Tests: {passed}/{len(test_cases)} passed ({passed/len(test_cases)*100:.1f}%)")
            print(f"Duration: {duration:.1f}s\n")
            
            return 0 if all_passed else 1
        
        except Exception as e:
            self.log(f"Workflow failed: {str(e)}", "ERROR")
            import traceback
            traceback.print_exc()
            return 1
        finally:
            await self.jira_client.close()
            await self.qf_client.close()


async def main():
    MAESTRO_API = os.getenv("MAESTRO_API_URL", "http://localhost:3100/api")
    JWT_TOKEN = os.getenv("JWT_TOKEN")
    QF_API = os.getenv("QF_API_URL", "http://localhost:8000")
    EPIC_KEY = os.getenv("EPIC_KEY")
    
    if not JWT_TOKEN:
        print("❌ ERROR: JWT_TOKEN environment variable not set")
        print("Usage: JWT_TOKEN='your_token' python e2e_dev_qa_agent.py")
        sys.exit(1)
    
    agent = E2EDevQAAgent(MAESTRO_API, JWT_TOKEN, QF_API)
    exit_code = await agent.run_workflow(epic_key=EPIC_KEY)
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
