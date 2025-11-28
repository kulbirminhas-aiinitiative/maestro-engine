# E2E Development & QA Agent API Reference

## Overview

The End-to-End Development & QA Agent orchestrates the complete workflow from JIRA initialization through testing and closure. It automates the development lifecycle by integrating with JIRA and Quality Fabric services.

**Base URL:** `http://localhost:8080/api/e2e-agent` (via Gateway)  
**Direct URL:** `http://localhost:4001/api/e2e-agent` (BFF Service)

---

## Workflow Architecture

The E2E Agent executes a 6-step workflow:

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: JIRA INITIALIZATION                                │
│  • Fetch 'To Do' Epic                                       │
│  • Transition Epic to 'In Progress'                         │
│  • Load associated tasks                                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: STRATEGY GENERATION                                │
│  • Generate development plan from epic description          │
│  • Parse acceptance criteria                                │
│  • Create comprehensive test cases                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: IMPLEMENTATION                                     │
│  • Execute code development/fixes                           │
│  • Modify files based on plan                               │
│  • Build and prepare for testing                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: VALIDATION                                         │
│  • Run tests against Quality Fabric API (localhost:8000)   │
│  • Collect test results and logs                            │
│  • Calculate pass/fail metrics                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 5: REPORTING                                          │
│  • Update test cases with status and logs                   │
│  • Update JIRA tasks with execution details                 │
│  • Set successful tasks to 'Done'                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 6: CLOSURE                                            │
│  • Check if all tasks are 'Done'                            │
│  • IF all tasks complete THEN set Epic to 'Done'            │
│  • Generate final workflow report                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Endpoints

### 1. Start Full Workflow

**POST** `/api/e2e-agent/workflow/start`

Execute the complete End-to-End Development & QA workflow.

**Request Body:**
```json
{
  "epic_id": "EPIC-3",
  "quality_api_url": "http://localhost:8000"
}
```

**Parameters:**
- `epic_id` (optional): Specific epic to process. If not provided, auto-selects first 'To Do' epic
- `quality_api_url` (optional): Quality Fabric API URL. Default: `http://localhost:8000`

**Example Request:**
```bash
curl -X POST http://localhost:8080/api/e2e-agent/workflow/start \
  -H "Content-Type: application/json" \
  -d '{
    "epic_id": "EPIC-3"
  }'
```

**Response:**
```json
{
  "success": true,
  "workflow_id": "EPIC-3",
  "results": {
    "started_at": "2025-11-27T21:00:00.000Z",
    "epic_id": "EPIC-3",
    "steps": {
      "step1_initialization": {
        "success": true,
        "epic_id": "EPIC-3",
        "epic": {...},
        "tasks": [...],
        "progress": {
          "total": 5,
          "done": 0,
          "percentage": 0
        }
      },
      "step2_strategy": {
        "epic_id": "EPIC-3",
        "test_cases": [
          {
            "test_id": "EPIC-3-TC1",
            "description": "Verify API endpoint exists and responds",
            "endpoint": "/api/scores"
          }
        ],
        "implementation_steps": [...]
      },
      "step4_validation": {
        "total_tests": 3,
        "passed": 3,
        "failed": 0,
        "test_results": [
          {
            "test_id": "EPIC-3-TC1",
            "status": "PASSED",
            "execution_time": 0.15,
            "logs": ["✓ Test passed in 0.15s"]
          }
        ]
      },
      "step5_reporting": {
        "tasks_updated": [
          {
            "task_id": "P4",
            "status": "Done",
            "resolution": "Tests: 3/3 passed"
          }
        ]
      },
      "step6_closure": {
        "epic_completed": true,
        "epic_status": "Done"
      }
    },
    "completed_at": "2025-11-27T21:05:00.000Z",
    "success": true,
    "session_log": [...]
  },
  "report_path": "/home/ec2-user/projects/maestro-engine-new/logs/e2e_workflow_EPIC-3.json"
}
```

---

### 2. Get Workflow Status

**GET** `/api/e2e-agent/workflow/status/{epic_id}`

Get current status of an epic workflow including progress and task completion.

**Example Request:**
```bash
curl http://localhost:8080/api/e2e-agent/workflow/status/EPIC-3
```

**Response:**
```json
{
  "success": true,
  "epic_id": "EPIC-3",
  "status": "In Progress",
  "is_complete": false,
  "progress": {
    "total": 5,
    "done": 2,
    "percentage": 40
  },
  "tasks": [...]
}
```

---

### 3. Run Step 1: Initialize

**POST** `/api/e2e-agent/workflow/step1/initialize`

Run only Step 1 of the workflow: JIRA Initialization.

**Query Parameters:**
- `epic_id` (optional): Epic to initialize

**Example Request:**
```bash
curl -X POST "http://localhost:8080/api/e2e-agent/workflow/step1/initialize?epic_id=EPIC-3"
```

**Response:**
```json
{
  "success": true,
  "step": "step1_initialization",
  "result": {
    "success": true,
    "epic_id": "EPIC-3",
    "epic": {...},
    "tasks": [...],
    "progress": {...}
  },
  "logs": [
    "[2025-11-27T21:00:00] [INFO] === STEP 1: JIRA INITIALIZATION ===",
    "[2025-11-27T21:00:00] [INFO] Fetched epic: EPIC-3",
    "[2025-11-27T21:00:01] [INFO] Transitioned EPIC-3 to 'In Progress'"
  ]
}
```

---

### 4. Run Step 2: Strategy

**POST** `/api/e2e-agent/workflow/step2/strategy`

Run only Step 2: Generate development plan and test cases.

**Request Body:**
```json
{
  "epic_id": "EPIC-3",
  "epic": {...},
  "tasks": [...],
  "progress": {...}
}
```

**Example Request:**
```bash
curl -X POST http://localhost:8080/api/e2e-agent/workflow/step2/strategy \
  -H "Content-Type: application/json" \
  -d @epic_data.json
```

**Response:**
```json
{
  "success": true,
  "step": "step2_strategy",
  "plan": {
    "epic_id": "EPIC-3",
    "tasks": [...],
    "test_cases": [
      {
        "test_id": "EPIC-3-TC1",
        "description": "Verify API endpoint exists",
        "endpoint": "/api/scores"
      }
    ],
    "implementation_steps": [
      "Compute/persist scores per phase/persona/team",
      "API /api/scores",
      "WS updates",
      "dashboards"
    ]
  },
  "logs": [...]
}
```

---

### 5. Health Check

**GET** `/api/e2e-agent/health`

Check E2E agent service health and dependencies.

**Example Request:**
```bash
curl http://localhost:8080/api/e2e-agent/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "e2e-dev-qa-agent",
  "jira": {
    "epics_loaded": 13,
    "tasks_loaded": 11
  },
  "quality_api": {
    "url": "http://localhost:8000",
    "status": "reachable"
  }
}
```

---

### 6. Get Session Logs

**GET** `/api/e2e-agent/logs/session`

Retrieve session logs from the E2E agent.

**Query Parameters:**
- `limit` (optional): Number of recent log entries. Default: 50

**Example Request:**
```bash
curl "http://localhost:8080/api/e2e-agent/logs/session?limit=20"
```

**Response:**
```json
{
  "success": true,
  "total_logs": 156,
  "returned_logs": 20,
  "logs": [
    "[2025-11-27T21:00:00] [INFO] === STEP 1: JIRA INITIALIZATION ===",
    "[2025-11-27T21:00:01] [INFO] Fetched epic: EPIC-3",
    "..."
  ]
}
```

---

## Data Models

### WorkflowRequest
```json
{
  "epic_id": "EPIC-3",
  "quality_api_url": "http://localhost:8000"
}
```

### TestCase
```json
{
  "test_id": "EPIC-3-TC1",
  "description": "Verify API endpoint exists and responds",
  "endpoint": "/api/scores",
  "status": "PASSED",
  "result": {
    "status_code": 200,
    "response": {...}
  },
  "logs": ["✓ Test passed in 0.15s"],
  "execution_time": 0.15
}
```

### DevelopmentPlan
```json
{
  "epic_id": "EPIC-3",
  "epic_data": {...},
  "tasks": [...],
  "test_cases": [...],
  "implementation_steps": [
    "Step 1: Implement score computation",
    "Step 2: Add persistence layer",
    "Step 3: Create API endpoints"
  ],
  "created_at": "2025-11-27T21:00:00.000Z"
}
```

---

## Integration with Quality Fabric

The E2E Agent validates implementations by running tests against the Quality Fabric API (port 8000):

### Test Execution Flow

1. **Test Case Generation**: Agent parses epic acceptance criteria to create test cases
2. **API Calls**: Agent makes HTTP requests to Quality Fabric endpoints
3. **Result Validation**: Checks HTTP status codes and response payloads
4. **Logging**: Captures detailed execution logs and timings

### Example Quality Fabric Endpoints Used

- `GET /api/health` - Health check
- `POST /api/execute` - Execute test suites
- `GET /api/results/{execution_id}` - Retrieve test results
- `GET /api/insights` - Get quality insights

---

## Workflow Report Format

After workflow completion, a detailed JSON report is saved to `/logs/e2e_workflow_{epic_id}.json`:

```json
{
  "started_at": "2025-11-27T21:00:00.000Z",
  "epic_id": "EPIC-3",
  "steps": {
    "step1_initialization": {...},
    "step2_strategy": {...},
    "step3_implementation": {...},
    "step4_validation": {
      "total_tests": 3,
      "passed": 3,
      "failed": 0,
      "test_results": [...]
    },
    "step5_reporting": {
      "tasks_updated": [...]
    },
    "step6_closure": {
      "epic_completed": true
    }
  },
  "completed_at": "2025-11-27T21:05:00.000Z",
  "success": true,
  "session_log": [...]
}
```

---

## Best Practices

### 1. Epic Selection
- Start with highest priority 'To Do' epics
- Ensure epic has clear acceptance criteria in description
- Verify associated tasks exist

### 2. Test Case Design
- Epic descriptions should include testable acceptance criteria
- Use format: `AC: criteria1; criteria2; criteria3`
- Include both positive and negative test scenarios

### 3. Error Handling
- Agent continues on non-critical failures
- Failed tests don't block reporting step
- Epic remains 'In Progress' if any task fails

### 4. Monitoring
- Check session logs for detailed execution trace
- Review generated reports for metrics
- Monitor Quality Fabric API connectivity

---

## Usage Examples

### Complete Workflow

```bash
# Start workflow (auto-select first To Do epic)
curl -X POST http://localhost:8080/api/e2e-agent/workflow/start \
  -H "Content-Type: application/json" \
  -d '{}'

# Start workflow with specific epic
curl -X POST http://localhost:8080/api/e2e-agent/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"epic_id": "EPIC-3"}'

# Check workflow status
curl http://localhost:8080/api/e2e-agent/workflow/status/EPIC-3

# View session logs
curl http://localhost:8080/api/e2e-agent/logs/session?limit=50
```

### Step-by-Step Execution

```bash
# Step 1: Initialize
curl -X POST "http://localhost:8080/api/e2e-agent/workflow/step1/initialize?epic_id=EPIC-3"

# Step 2: Generate strategy (use epic_data from step 1 response)
curl -X POST http://localhost:8080/api/e2e-agent/workflow/step2/strategy \
  -H "Content-Type: application/json" \
  -d @step1_output.json

# ... continue with remaining steps as needed
```

---

## Troubleshooting

### Workflow Fails at Step 1
- **Issue**: Epic not found
- **Solution**: Verify epic_id format (e.g., `EPIC-3`, not `Epic-3`)
- **Check**: `GET /api/jira/epics/todo`

### Workflow Fails at Step 4
- **Issue**: Quality Fabric API unreachable
- **Solution**: Verify service is running on port 8000
- **Check**: `curl http://localhost:8000/api/health`

### Tasks Not Updating
- **Issue**: Task ID parsing fails
- **Solution**: Ensure task summaries start with task ID (e.g., `P0: Task name`)
- **Check**: `GET /api/jira/tasks`

### Epic Not Closing
- **Issue**: Some tasks still in progress
- **Solution**: Check completion status
- **Check**: `GET /api/jira/epics/EPIC-3/check-completion`

---

## Performance Metrics

Typical workflow execution times:
- **Step 1 (Initialization)**: < 1 second
- **Step 2 (Strategy)**: < 2 seconds
- **Step 3 (Implementation)**: Variable (depends on complexity)
- **Step 4 (Validation)**: 5-30 seconds (depends on test count)
- **Step 5 (Reporting)**: < 2 seconds
- **Step 6 (Closure)**: < 1 second

**Total**: ~10-40 seconds for typical epic

---

## Support

- **Logs**: `/home/ec2-user/projects/maestro-engine-new/logs/`
- **JIRA Data**: `/home/ec2-user/projects/maestro-engine-new/docs/jira_*.csv`
- **Health Check**: `GET /api/e2e-agent/health`
