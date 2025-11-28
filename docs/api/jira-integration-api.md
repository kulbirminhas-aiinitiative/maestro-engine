# JIRA Integration API Reference

## Overview

The JIRA Integration API provides endpoints to interact with JIRA Epics and Tasks for the End-to-End Development & QA workflow. The integration uses CSV-backed storage for JIRA data.

**Base URL:** `http://localhost:8080/api/jira` (via Gateway)  
**Direct URL:** `http://localhost:4001/api/jira` (BFF Service)

## Authentication

Currently, the API does not require authentication. In production, implement OAuth 2.0 or API key authentication.

---

## Endpoints

### 1. List Epics

**GET** `/api/jira/epics`

List all epics with optional filtering.

**Query Parameters:**
- `status` (optional): Filter by status (`To Do`, `In Progress`, `Done`)
- `priority` (optional): Filter by priority (`Highest`, `High`, `Medium`, `Low`)

**Example Request:**
```bash
curl http://localhost:8080/api/jira/epics?status=To%20Do&priority=Highest
```

**Response:**
```json
{
  "success": true,
  "count": 2,
  "epics": [
    {
      "Issue Type": "Epic",
      "Summary": "EPIC-3: Success Scoring Service",
      "Description": "Compute/persist scores per phase/persona/team; API /api/scores; WS updates; dashboards.",
      "Priority": "High",
      "Status": "To Do",
      "Assignee": "",
      "Start date": "2025-12-08",
      "Due date": "2025-12-22"
    }
  ]
}
```

---

### 2. Get To Do Epics

**GET** `/api/jira/epics/todo`

Get all epics in 'To Do' status. This is used in the E2E workflow initialization step.

**Example Request:**
```bash
curl http://localhost:8080/api/jira/epics/todo
```

**Response:**
```json
{
  "success": true,
  "count": 8,
  "epics": [...]
}
```

---

### 3. Get Epic Details

**GET** `/api/jira/epics/{epic_id}`

Get detailed information about a specific epic including associated tasks and progress.

**Path Parameters:**
- `epic_id`: Epic identifier (e.g., `EPIC-3`)

**Example Request:**
```bash
curl http://localhost:8080/api/jira/epics/EPIC-3
```

**Response:**
```json
{
  "success": true,
  "data": {
    "issue": {
      "Issue Type": "Epic",
      "Summary": "EPIC-3: Success Scoring Service",
      "Description": "...",
      "Status": "To Do"
    },
    "type": "Epic",
    "tasks": [...],
    "progress": {
      "total": 0,
      "done": 0,
      "percentage": 0
    }
  }
}
```

---

### 4. Get Epic Tasks

**GET** `/api/jira/epics/{epic_id}/tasks`

Get all tasks associated with an epic.

**Example Request:**
```bash
curl http://localhost:8080/api/jira/epics/EPIC-1/tasks
```

**Response:**
```json
{
  "success": true,
  "epic_id": "EPIC-1",
  "count": 1,
  "tasks": [
    {
      "Issue Type": "Task",
      "Summary": "P0: Implement /api/policy/route",
      "Status": "Done",
      "Priority": "Highest"
    }
  ]
}
```

---

### 5. Transition Epic Status

**POST** `/api/jira/epics/{epic_id}/transition`

Transition an epic to a new status.

**Path Parameters:**
- `epic_id`: Epic identifier

**Request Body:**
```json
{
  "target_status": "In Progress"
}
```

Or when marking as Done:
```json
{
  "target_status": "Done",
  "resolution": "All acceptance criteria verified; All tests passed"
}
```

**Example Request:**
```bash
curl -X POST http://localhost:8080/api/jira/epics/EPIC-3/transition \
  -H "Content-Type: application/json" \
  -d '{"target_status": "In Progress"}'
```

**Response:**
```json
{
  "success": true,
  "message": "Epic EPIC-3 transitioned to In Progress",
  "epic": {...}
}
```

---

### 6. List Tasks

**GET** `/api/jira/tasks`

List all tasks with optional filtering.

**Query Parameters:**
- `status` (optional): Filter by status
- `priority` (optional): Filter by priority
- `epic_id` (optional): Filter by associated epic

**Example Request:**
```bash
curl http://localhost:8080/api/jira/tasks?status=To%20Do&priority=Highest
```

---

### 7. Get Task Details

**GET** `/api/jira/tasks/{task_id}`

Get details about a specific task.

**Example Request:**
```bash
curl http://localhost:8080/api/jira/tasks/P0
```

---

### 8. Transition Task Status

**POST** `/api/jira/tasks/{task_id}/transition`

Transition a task to a new status.

**Request Body:**
```json
{
  "target_status": "Done",
  "resolution": "Implementation complete; All tests passed; 32/32 unit tests passed"
}
```

**Example Request:**
```bash
curl -X POST http://localhost:8080/api/jira/tasks/P0/transition \
  -H "Content-Type: application/json" \
  -d '{
    "target_status": "Done",
    "resolution": "Tests: 7/7 passed"
  }'
```

---

### 9. Check Epic Completion

**GET** `/api/jira/epics/{epic_id}/check-completion`

Check if all tasks in an epic are completed. Used in workflow closure step.

**Example Request:**
```bash
curl http://localhost:8080/api/jira/epics/EPIC-3/check-completion
```

**Response:**
```json
{
  "success": true,
  "epic_id": "EPIC-3",
  "is_complete": false,
  "total_tasks": 5,
  "done_tasks": 2,
  "remaining_tasks": 3
}
```

---

### 10. Reload Data

**POST** `/api/jira/reload`

Reload JIRA data from CSV files. Use after external updates to CSV.

**Example Request:**
```bash
curl -X POST http://localhost:8080/api/jira/reload
```

**Response:**
```json
{
  "success": true,
  "message": "JIRA data reloaded successfully",
  "epics_count": 13,
  "tasks_count": 11
}
```

---

### 11. Health Check

**GET** `/api/jira/health`

Check JIRA integration service health.

**Example Request:**
```bash
curl http://localhost:8080/api/jira/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "jira-integration",
  "epics_loaded": 13,
  "tasks_loaded": 11
}
```

---

## Data Models

### IssueStatus (Enum)
- `To Do`
- `In Progress`
- `Done`

### Priority (Enum)
- `Highest`
- `High`
- `Medium`
- `Low`

### Epic Object
```json
{
  "Issue Type": "Epic",
  "Summary": "EPIC-3: Success Scoring Service",
  "Description": "Full description with AC",
  "Priority": "High",
  "Labels": "maestro-v3;baseline;scoring",
  "Components": "backend;analytics",
  "Assignee": "AI-Agent",
  "Start date": "2025-12-08",
  "Due date": "2025-12-22",
  "Status": "To Do",
  "Resolution": ""
}
```

### Task Object
```json
{
  "Issue Type": "Task",
  "Summary": "P0: Implement /api/policy/route",
  "Description": "Task description",
  "Priority": "Highest",
  "Labels": "maestro-v3;baseline;routing",
  "Components": "bff",
  "Assignee": "AI-Agent",
  "Start date": "2025-11-27",
  "Due date": "2025-11-27",
  "Status": "Done",
  "Resolution": "All tests passed"
}
```

---

## E2E Dev & QA Agent Integration

The JIRA Integration API is designed to work seamlessly with the E2E Development & QA Agent workflow:

1. **Initialization**: Fetch 'To Do' epics and transition selected epic to 'In Progress'
2. **Strategy**: Use epic description and tasks to generate development plan
3. **Reporting**: Update task statuses based on test results
4. **Closure**: Check completion and transition epic to 'Done' when all tasks complete

See [E2E Agent API Documentation](./e2e-agent-api.md) for the complete workflow API.

---

## Error Handling

All endpoints return consistent error responses:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**
- `200`: Success
- `404`: Resource not found (epic/task doesn't exist)
- `400`: Bad request (missing required fields)
- `500`: Internal server error

---

## Usage Examples

### Complete Workflow Example

```bash
# 1. Get a To Do epic
curl http://localhost:8080/api/jira/epics/todo

# 2. Transition epic to In Progress
curl -X POST http://localhost:8080/api/jira/epics/EPIC-3/transition \
  -H "Content-Type: application/json" \
  -d '{"target_status": "In Progress"}'

# 3. Get epic tasks
curl http://localhost:8080/api/jira/epics/EPIC-3/tasks

# 4. Update task status after implementation
curl -X POST http://localhost:8080/api/jira/tasks/P4/transition \
  -H "Content-Type: application/json" \
  -d '{
    "target_status": "Done",
    "resolution": "Implementation complete; Tests passed"
  }'

# 5. Check if epic is complete
curl http://localhost:8080/api/jira/epics/EPIC-3/check-completion

# 6. If complete, mark epic as Done
curl -X POST http://localhost:8080/api/jira/epics/EPIC-3/transition \
  -H "Content-Type: application/json" \
  -d '{
    "target_status": "Done",
    "resolution": "All tasks completed successfully"
  }'
```

---

## CSV Data Files

The JIRA integration uses CSV files as the data backend:

- **Epics**: `/home/ec2-user/projects/maestro-engine-new/docs/jira_epics_export.csv`
- **Tasks**: `/home/ec2-user/projects/maestro-engine-new/docs/jira_actions_export.csv`

These files are automatically updated when statuses are changed via the API.

---

## Notes

- The integration is CSV-backed for simplicity. In production, connect to real JIRA REST API.
- Status transitions are automatically persisted to CSV files.
- Epic-task relationships are inferred from labels and descriptions.
- All timestamps use ISO 8601 format.

---

## Support

For issues or questions, check the logs at `/home/ec2-user/projects/maestro-engine-new/logs/` or contact the development team.
