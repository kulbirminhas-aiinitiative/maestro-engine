# E2E Development & QA Agent - Quick Start Guide

## Overview

The End-to-End Development & QA Agent automates the complete development lifecycle by integrating JIRA project management with automated testing and validation.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Gateway (Port 8080)                      │
│                  Routes: /api/jira/*                        │
│                          /api/e2e-agent/*                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    BFF Service (Port 4001)                  │
│  • JIRA Integration Service                                 │
│  • E2E Development & QA Agent                               │
│  • Workflow Orchestration                                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┴──────────────────┐
        │                                    │
        ↓                                    ↓
┌──────────────────┐              ┌──────────────────────┐
│  JIRA CSV Data   │              │ Quality Fabric API   │
│  (docs/*.csv)    │              │  (Port 8000)         │
└──────────────────┘              └──────────────────────┘
```

## Quick Start

### 1. Access API Documentation

```bash
# JIRA Integration API Reference
cat ~/projects/maestro-engine-new/docs/api/jira-integration-api.md

# E2E Agent API Reference
cat ~/projects/maestro-engine-new/docs/api/e2e-agent-api.md
```

Or access via command:
```bash
# Use this command in your workflow
/integration-api-reference
# This will display: ~/project/maestro-frontend-production/docs/api/jira-integration-api.md
# (Note: In this implementation, the docs are at maestro-engine-new/docs/api/)
```

### 2. Check Service Health

```bash
# Check JIRA Integration
curl http://localhost:8080/api/jira/health

# Check E2E Agent
curl http://localhost:8080/api/e2e-agent/health

# Check Quality Fabric
curl http://localhost:8000/api/health
```

### 3. List Available Work Items

```bash
# Get all 'To Do' epics
curl http://localhost:8080/api/jira/epics/todo | jq '.'

# Get specific epic details
curl http://localhost:8080/api/jira/epics/EPIC-3 | jq '.'

# Get tasks for an epic
curl http://localhost:8080/api/jira/epics/EPIC-3/tasks | jq '.'
```

### 4. Run Complete E2E Workflow

**Option A: Auto-select first 'To Do' epic**
```bash
curl -X POST http://localhost:8080/api/e2e-agent/workflow/start \
  -H "Content-Type: application/json" \
  -d '{}' | jq '.'
```

**Option B: Specify epic**
```bash
curl -X POST http://localhost:8080/api/e2e-agent/workflow/start \
  -H "Content-Type: application/json" \
  -d '{
    "epic_id": "EPIC-3"
  }' | jq '.'
```

### 5. Run Comprehensive Test Suite

```bash
cd /home/ec2-user/projects/maestro-engine-new
python3 test_e2e_workflow.py
```

## Workflow Steps Explained

### Step 1: JIRA Initialization
- Fetches 'To Do' epic from JIRA
- Transitions epic status to 'In Progress'
- Loads all associated tasks
- **Output**: Epic data and task list

### Step 2: Strategy Generation
- Parses epic description for acceptance criteria
- Generates development plan
- Creates comprehensive test cases
- **Output**: DevelopmentPlan with test cases

### Step 3: Implementation
- Executes code development based on plan
- Modifies files as needed
- Prepares for testing
- **Output**: Implementation results

### Step 4: Validation
- Runs all test cases against Quality Fabric API
- Collects execution metrics and logs
- Determines pass/fail status
- **Output**: Validation results with test metrics

### Step 5: Reporting
- Updates test cases with results
- Updates JIRA task statuses
- Sets successful tasks to 'Done'
- **Output**: Updated JIRA tasks

### Step 6: Closure
- Checks if all epic tasks are complete
- IF all tasks 'Done' THEN sets epic to 'Done'
- Generates final workflow report
- **Output**: Epic closure status

## API Endpoints Summary

### JIRA Integration (`/api/jira`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/epics` | List all epics with filters |
| GET | `/epics/todo` | Get 'To Do' epics |
| GET | `/epics/{epic_id}` | Get epic details |
| GET | `/epics/{epic_id}/tasks` | Get epic tasks |
| POST | `/epics/{epic_id}/transition` | Change epic status |
| GET | `/tasks` | List all tasks |
| GET | `/tasks/{task_id}` | Get task details |
| POST | `/tasks/{task_id}/transition` | Change task status |
| GET | `/epics/{epic_id}/check-completion` | Check epic completion |
| POST | `/reload` | Reload JIRA data |
| GET | `/health` | Health check |

### E2E Agent (`/api/e2e-agent`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/workflow/start` | Start full E2E workflow |
| GET | `/workflow/status/{epic_id}` | Get workflow status |
| POST | `/workflow/step1/initialize` | Run Step 1 only |
| POST | `/workflow/step2/strategy` | Run Step 2 only |
| GET | `/logs/session` | Get session logs |
| GET | `/health` | Health check |

## Example Workflows

### Scenario 1: Automated Epic Completion

```bash
# 1. Start workflow (auto-selects first To Do epic)
RESULT=$(curl -s -X POST http://localhost:8080/api/e2e-agent/workflow/start \
  -H "Content-Type: application/json" \
  -d '{}')

# 2. Extract epic ID
EPIC_ID=$(echo $RESULT | jq -r '.workflow_id')

# 3. Check status
curl http://localhost:8080/api/e2e-agent/workflow/status/$EPIC_ID | jq '.'

# 4. View report
REPORT_PATH=$(echo $RESULT | jq -r '.report_path')
cat $REPORT_PATH | jq '.'
```

### Scenario 2: Manual Step-by-Step Execution

```bash
# Step 1: Initialize
STEP1=$(curl -s -X POST "http://localhost:8080/api/e2e-agent/workflow/step1/initialize?epic_id=EPIC-3")
echo $STEP1 | jq '.result' > epic_data.json

# Step 2: Generate strategy
STEP2=$(curl -s -X POST http://localhost:8080/api/e2e-agent/workflow/step2/strategy \
  -H "Content-Type: application/json" \
  -d @epic_data.json)
echo $STEP2 | jq '.plan'

# Continue with remaining steps manually...
```

### Scenario 3: Monitor Multiple Epics

```bash
# Get all To Do epics
TODO_EPICS=$(curl -s http://localhost:8080/api/jira/epics/todo | jq -r '.epics[].Summary' | cut -d: -f1)

# Process each epic
for EPIC_ID in $TODO_EPICS; do
  echo "Processing $EPIC_ID..."
  curl -X POST http://localhost:8080/api/e2e-agent/workflow/start \
    -H "Content-Type: application/json" \
    -d "{\"epic_id\": \"$EPIC_ID\"}" | jq '.'
  sleep 5
done
```

## Data Files

### JIRA Epics CSV
**Location**: `/home/ec2-user/projects/maestro-engine-new/docs/jira_epics_export.csv`

**Format**:
```csv
Issue Type,Summary,Description,Priority,Labels,Components,Assignee,Start date,Due date,Status,Resolution
Epic,EPIC-3: Success Scoring Service,Compute/persist scores...,High,maestro-v3;scoring,backend;analytics,,2025-12-08,2025-12-22,To Do,
```

### JIRA Tasks CSV
**Location**: `/home/ec2-user/projects/maestro-engine-new/docs/jira_actions_export.csv`

**Format**:
```csv
Issue Type,Summary,Description,Priority,Labels,Components,Assignee,Start date,Due date,Status,Resolution
Task,P4: Scoring service with /api/scores,Compute/persist scores...,High,maestro-v3;analytics,backend,,2025-12-08,2025-12-15,To Do,
```

## Testing Quality Gates

The E2E agent validates implementations against Quality Fabric API endpoints:

```bash
# Test endpoints the agent will call
curl http://localhost:8000/api/health
curl http://localhost:8000/api/execute
curl http://localhost:8000/api/insights
```

## Logs and Reports

### Session Logs
View agent execution logs:
```bash
curl http://localhost:8080/api/e2e-agent/logs/session?limit=50 | jq '.logs'
```

### Workflow Reports
Reports are saved to: `/home/ec2-user/projects/maestro-engine-new/logs/e2e_workflow_{epic_id}.json`

```bash
# View latest report
ls -lt /home/ec2-user/projects/maestro-engine-new/logs/e2e_workflow_*.json | head -1
cat $(ls -t /home/ec2-user/projects/maestro-engine-new/logs/e2e_workflow_*.json | head -1) | jq '.'
```

## Troubleshooting

### Issue: "Epic not found"
**Solution**: Check epic ID format (must be `EPIC-3`, not `Epic-3`)
```bash
curl http://localhost:8080/api/jira/epics/todo | jq '.epics[].Summary'
```

### Issue: "Quality Fabric API unreachable"
**Solution**: Verify service is running on port 8000
```bash
curl http://localhost:8000/api/health
# If fails, check service status
ps aux | grep quality
```

### Issue: "Tasks not updating"
**Solution**: Ensure task summaries start with task ID
```bash
# Correct: "P0: Implement /api/policy/route"
# Wrong: "Implement /api/policy/route (P0)"
```

### Issue: "Epic not closing"
**Solution**: Check task completion status
```bash
curl http://localhost:8080/api/jira/epics/EPIC-3/check-completion | jq '.'
```

## Integration with CI/CD

### GitHub Actions Example
```yaml
name: E2E Workflow
on:
  workflow_dispatch:
    inputs:
      epic_id:
        description: 'Epic ID to process'
        required: false

jobs:
  e2e-workflow:
    runs-on: ubuntu-latest
    steps:
      - name: Run E2E Workflow
        run: |
          curl -X POST http://localhost:8080/api/e2e-agent/workflow/start \
            -H "Content-Type: application/json" \
            -d '{"epic_id": "${{ github.event.inputs.epic_id }}"}'
```

## Best Practices

1. **Epic Descriptions**: Include clear acceptance criteria using format `AC: criteria1; criteria2`
2. **Task Naming**: Start task summaries with task ID (e.g., `P0: Task name`)
3. **Testing**: Run health checks before executing workflows
4. **Monitoring**: Review session logs and workflow reports regularly
5. **Validation**: Ensure Quality Fabric API is accessible before testing

## Support

- **API Documentation**: `/docs/api/jira-integration-api.md` and `/docs/api/e2e-agent-api.md`
- **Test Suite**: `python3 test_e2e_workflow.py`
- **Health Checks**: `GET /api/jira/health` and `GET /api/e2e-agent/health`
- **Logs**: `/home/ec2-user/projects/maestro-engine-new/logs/`

## Next Steps

1. Review the comprehensive test suite output
2. Examine workflow reports for detailed metrics
3. Integrate with your CI/CD pipeline
4. Customize test case generation for your use cases
5. Add custom validation endpoints to Quality Fabric

---

**Version**: 1.0.0  
**Last Updated**: 2025-11-27  
**Service**: MAESTRO E2E Development & QA Agent
