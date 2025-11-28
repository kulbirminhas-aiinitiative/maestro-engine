#!/usr/bin/env python3
"""
Test E2E Development & QA Agent Workflow
Complete integration test of JIRA integration and E2E workflow
"""

import asyncio
import json
import httpx
from datetime import datetime
from typing import Dict, Any


BASE_URL = "http://localhost:8080"  # Gateway
QUALITY_API_URL = "http://localhost:8000"


class Colors:
    """Terminal colors"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def log_step(message: str, level: str = "INFO"):
    """Log a test step with color"""
    colors = {
        "INFO": Colors.OKBLUE,
        "SUCCESS": Colors.OKGREEN,
        "WARNING": Colors.WARNING,
        "ERROR": Colors.FAIL,
        "HEADER": Colors.HEADER
    }
    color = colors.get(level, Colors.OKBLUE)
    print(f"{color}[{level}] {message}{Colors.ENDC}")


async def test_health_checks():
    """Test health checks for all services"""
    log_step("=" * 70, "HEADER")
    log_step("HEALTH CHECKS", "HEADER")
    log_step("=" * 70, "HEADER")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test JIRA service health
        try:
            response = await client.get(f"{BASE_URL}/api/jira/health")
            if response.status_code == 200:
                data = response.json()
                log_step(f"✓ JIRA Integration: {data['status']} (Epics: {data['epics_loaded']}, Tasks: {data['tasks_loaded']})", "SUCCESS")
            else:
                log_step(f"✗ JIRA Integration health check failed: {response.status_code}", "ERROR")
        except Exception as e:
            log_step(f"✗ JIRA Integration unreachable: {e}", "ERROR")
        
        # Test E2E Agent health
        try:
            response = await client.get(f"{BASE_URL}/api/e2e-agent/health")
            if response.status_code == 200:
                data = response.json()
                log_step(f"✓ E2E Agent: {data['status']}", "SUCCESS")
                log_step(f"  Quality API: {data['quality_api']['status']}", "INFO")
            else:
                log_step(f"✗ E2E Agent health check failed: {response.status_code}", "ERROR")
        except Exception as e:
            log_step(f"✗ E2E Agent unreachable: {e}", "ERROR")
        
        # Test Quality Fabric API
        try:
            response = await client.get(f"{QUALITY_API_URL}/api/health")
            if response.status_code == 200:
                log_step("✓ Quality Fabric API: operational", "SUCCESS")
            else:
                log_step(f"✗ Quality Fabric API check failed: {response.status_code}", "WARNING")
        except Exception as e:
            log_step(f"✗ Quality Fabric API unreachable: {e}", "WARNING")


async def test_jira_endpoints():
    """Test JIRA integration endpoints"""
    log_step("\n" + "=" * 70, "HEADER")
    log_step("JIRA INTEGRATION API TESTS", "HEADER")
    log_step("=" * 70, "HEADER")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. List all epics
        log_step("\n1. Testing GET /api/jira/epics", "INFO")
        try:
            response = await client.get(f"{BASE_URL}/api/jira/epics")
            if response.status_code == 200:
                data = response.json()
                log_step(f"✓ Found {data['count']} epics", "SUCCESS")
            else:
                log_step(f"✗ Failed: {response.status_code}", "ERROR")
        except Exception as e:
            log_step(f"✗ Error: {e}", "ERROR")
        
        # 2. Get To Do epics
        log_step("\n2. Testing GET /api/jira/epics/todo", "INFO")
        try:
            response = await client.get(f"{BASE_URL}/api/jira/epics/todo")
            if response.status_code == 200:
                data = response.json()
                log_step(f"✓ Found {data['count']} 'To Do' epics", "SUCCESS")
                if data['count'] > 0:
                    epic = data['epics'][0]
                    epic_id = epic.get('Summary', '').split(':')[0].strip()
                    log_step(f"  First epic: {epic_id} - {epic.get('Summary', '')}", "INFO")
                    return epic_id
            else:
                log_step(f"✗ Failed: {response.status_code}", "ERROR")
        except Exception as e:
            log_step(f"✗ Error: {e}", "ERROR")
        
        return None


async def test_jira_epic_details(epic_id: str):
    """Test getting epic details and tasks"""
    log_step(f"\n3. Testing GET /api/jira/epics/{epic_id}", "INFO")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Get epic details
        try:
            response = await client.get(f"{BASE_URL}/api/jira/epics/{epic_id}")
            if response.status_code == 200:
                data = response.json()
                log_step(f"✓ Retrieved epic details", "SUCCESS")
                progress = data['data'].get('progress', {})
                log_step(f"  Progress: {progress.get('done', 0)}/{progress.get('total', 0)} tasks ({progress.get('percentage', 0):.1f}%)", "INFO")
            else:
                log_step(f"✗ Failed: {response.status_code}", "ERROR")
        except Exception as e:
            log_step(f"✗ Error: {e}", "ERROR")
        
        # Get epic tasks
        log_step(f"\n4. Testing GET /api/jira/epics/{epic_id}/tasks", "INFO")
        try:
            response = await client.get(f"{BASE_URL}/api/jira/epics/{epic_id}/tasks")
            if response.status_code == 200:
                data = response.json()
                log_step(f"✓ Found {data['count']} tasks", "SUCCESS")
                for task in data['tasks'][:3]:  # Show first 3
                    log_step(f"  - {task.get('Summary', 'Unknown')[:60]}...", "INFO")
            else:
                log_step(f"✗ Failed: {response.status_code}", "ERROR")
        except Exception as e:
            log_step(f"✗ Error: {e}", "ERROR")


async def test_e2e_workflow(epic_id: str = None):
    """Test the complete E2E workflow"""
    log_step("\n" + "=" * 70, "HEADER")
    log_step("END-TO-END WORKFLOW EXECUTION", "HEADER")
    log_step("=" * 70, "HEADER")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        log_step(f"\nStarting E2E workflow for epic: {epic_id or 'auto-select'}", "INFO")
        
        try:
            request_data = {}
            if epic_id:
                request_data["epic_id"] = epic_id
            
            start_time = datetime.now()
            response = await client.post(
                f"{BASE_URL}/api/e2e-agent/workflow/start",
                json=request_data
            )
            end_time = datetime.now()
            
            if response.status_code == 200:
                data = response.json()
                duration = (end_time - start_time).total_seconds()
                
                log_step(f"\n✓ Workflow completed in {duration:.2f}s", "SUCCESS")
                log_step(f"  Workflow ID: {data.get('workflow_id')}", "INFO")
                log_step(f"  Success: {data.get('success')}", "INFO")
                log_step(f"  Report: {data.get('report_path')}", "INFO")
                
                results = data.get('results', {})
                
                # Display step results
                steps = results.get('steps', {})
                
                # Step 1: Initialization
                if 'step1_initialization' in steps:
                    step1 = steps['step1_initialization']
                    log_step(f"\n  Step 1 - Initialization:", "SUCCESS")
                    log_step(f"    Epic: {step1.get('epic_id')}", "INFO")
                    log_step(f"    Tasks: {len(step1.get('tasks', []))}", "INFO")
                
                # Step 2: Strategy
                if 'step2_strategy' in steps:
                    step2 = steps['step2_strategy']
                    log_step(f"\n  Step 2 - Strategy:", "SUCCESS")
                    log_step(f"    Test cases: {len(step2.get('test_cases', []))}", "INFO")
                    log_step(f"    Implementation steps: {len(step2.get('implementation_steps', []))}", "INFO")
                
                # Step 4: Validation
                if 'step4_validation' in steps:
                    step4 = steps['step4_validation']
                    log_step(f"\n  Step 4 - Validation:", "SUCCESS")
                    log_step(f"    Total tests: {step4.get('total_tests')}", "INFO")
                    log_step(f"    Passed: {step4.get('passed')}", "SUCCESS")
                    log_step(f"    Failed: {step4.get('failed')}", "ERROR" if step4.get('failed') > 0 else "INFO")
                    
                    # Show test results
                    for test in step4.get('test_results', []):
                        status_color = "SUCCESS" if test['status'] == "PASSED" else "ERROR"
                        log_step(f"      {test['status']}: {test['test_id']} - {test['description']}", status_color)
                
                # Step 5: Reporting
                if 'step5_reporting' in steps:
                    step5 = steps['step5_reporting']
                    log_step(f"\n  Step 5 - Reporting:", "SUCCESS")
                    for task_update in step5.get('tasks_updated', []):
                        log_step(f"    Task {task_update.get('task_id')}: {task_update.get('status')}", "INFO")
                
                # Step 6: Closure
                if 'step6_closure' in steps:
                    step6 = steps['step6_closure']
                    log_step(f"\n  Step 6 - Closure:", "SUCCESS")
                    log_step(f"    Epic completed: {step6.get('epic_completed')}", "SUCCESS" if step6.get('epic_completed') else "INFO")
                    log_step(f"    Epic status: {step6.get('epic_status')}", "INFO")
                
                # Show session logs (last 10)
                session_logs = results.get('session_log', [])
                if session_logs:
                    log_step(f"\n  Session Logs (last 10):", "INFO")
                    for log_entry in session_logs[-10:]:
                        print(f"    {log_entry}")
                
                return True
            else:
                log_step(f"✗ Workflow failed: {response.status_code}", "ERROR")
                log_step(f"  {response.text}", "ERROR")
                return False
        
        except Exception as e:
            log_step(f"✗ Workflow error: {e}", "ERROR")
            return False


async def test_workflow_status(epic_id: str):
    """Test workflow status endpoint"""
    log_step(f"\nTesting GET /api/e2e-agent/workflow/status/{epic_id}", "INFO")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{BASE_URL}/api/e2e-agent/workflow/status/{epic_id}")
            if response.status_code == 200:
                data = response.json()
                log_step("✓ Retrieved workflow status", "SUCCESS")
                log_step(f"  Status: {data.get('status')}", "INFO")
                log_step(f"  Complete: {data.get('is_complete')}", "INFO")
                progress = data.get('progress', {})
                log_step(f"  Progress: {progress.get('done')}/{progress.get('total')} ({progress.get('percentage'):.1f}%)", "INFO")
            else:
                log_step(f"✗ Failed: {response.status_code}", "ERROR")
        except Exception as e:
            log_step(f"✗ Error: {e}", "ERROR")


async def main():
    """Run all tests"""
    log_step("\n" + "=" * 70, "HEADER")
    log_step("E2E DEVELOPMENT & QA AGENT - COMPREHENSIVE TEST SUITE", "HEADER")
    log_step("=" * 70, "HEADER")
    
    # 1. Health checks
    await test_health_checks()
    
    # 2. JIRA API tests
    epic_id = await test_jira_endpoints()
    
    # 3. Epic details tests
    if epic_id:
        await test_jira_epic_details(epic_id)
        
        # 4. Run E2E workflow
        workflow_success = await test_e2e_workflow(epic_id)
        
        # 5. Check workflow status
        await test_workflow_status(epic_id)
    else:
        log_step("\n⚠ No 'To Do' epics found, skipping workflow test", "WARNING")
    
    log_step("\n" + "=" * 70, "HEADER")
    log_step("TEST SUITE COMPLETE", "HEADER")
    log_step("=" * 70, "HEADER")


if __name__ == "__main__":
    asyncio.run(main())
