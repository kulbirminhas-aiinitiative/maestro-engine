# E2E Agent Command Reference Card

Quick reference for common operations with the E2E Development & QA Agent.

---

## Quick Commands

### Health Checks
```bash
# Check all services
curl http://localhost:8080/api/jira/health && \
curl http://localhost:8080/api/e2e-agent/health && \
curl http://localhost:8000/api/health

# One-liner status
curl -s http://localhost:8080/api/jira/health | jq '.status'
```

### JIRA Operations
```bash
# List To Do epics
curl -s http://localhost:8080/api/jira/epics/todo | jq '.epics[] | {id: .Summary | split(":")[0], title: .Summary}'

# Get epic details
curl -s http://localhost:8080/api/jira/epics/EPIC-3 | jq '.data.issue | {Summary, Status, Priority}'

# Check epic progress
curl -s http://localhost:8080/api/jira/epics/EPIC-3 | jq '.data.progress'

# List epic tasks
curl -s http://localhost:8080/api/jira/epics/EPIC-3/tasks | jq '.tasks[] | {Summary, Status}'
```

### Workflow Execution
```bash
# Run workflow (auto-select)
curl -X POST http://localhost:8080/api/e2e-agent/workflow/start \
  -H "Content-Type: application/json" \
  -d '{}' | jq '.success, .workflow_id'

# Run workflow (specific epic)
curl -X POST http://localhost:8080/api/e2e-agent/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"epic_id": "EPIC-3"}' | jq '.results.steps.step6_closure'

# Check workflow status
curl -s http://localhost:8080/api/e2e-agent/workflow/status/EPIC-3 | jq '{status, is_complete, progress}'
```

### Test Suite
```bash
# Run comprehensive tests
cd /home/ec2-user/projects/maestro-engine-new && python3 test_e2e_workflow.py

# Quick smoke test
curl http://localhost:8080/api/jira/health && \
curl http://localhost:8080/api/e2e-agent/health && \
echo "✅ All services healthy"
```

### Logs & Reports
```bash
# View session logs
curl -s http://localhost:8080/api/e2e-agent/logs/session?limit=20 | jq '.logs[]'

# View latest workflow report
cat $(ls -t logs/e2e_workflow_*.json | head -1) | jq '.steps | keys'

# View test results
cat $(ls -t logs/e2e_workflow_*.json | head -1) | jq '.steps.step4_validation.test_results'
```

---

## API Endpoints Quick Reference

### JIRA Integration (`/api/jira`)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/epics/todo` | GET | Get To Do epics |
| `/epics/{id}` | GET | Get epic details |
| `/epics/{id}/transition` | POST | Change epic status |
| `/tasks/{id}` | GET | Get task details |
| `/tasks/{id}/transition` | POST | Change task status |

### E2E Agent (`/api/e2e-agent`)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/workflow/start` | POST | Start workflow |
| `/workflow/status/{id}` | GET | Check status |
| `/logs/session` | GET | Get logs |

---

## Common Workflows

### Auto Process Next Epic
```bash
EPIC_ID=$(curl -s http://localhost:8080/api/jira/epics/todo | jq -r '.epics[0].Summary' | cut -d: -f1)
curl -X POST http://localhost:8080/api/e2e-agent/workflow/start \
  -H "Content-Type: application/json" \
  -d "{\"epic_id\": \"$EPIC_ID\"}"
```

### Monitor Epic Progress
```bash
watch -n 5 'curl -s http://localhost:8080/api/jira/epics/EPIC-3 | jq ".data.progress"'
```

### Batch Process All To Do Epics
```bash
for EPIC in $(curl -s http://localhost:8080/api/jira/epics/todo | jq -r '.epics[].Summary' | cut -d: -f1); do
  echo "Processing $EPIC..."
  curl -X POST http://localhost:8080/api/e2e-agent/workflow/start \
    -H "Content-Type: application/json" \
    -d "{\"epic_id\": \"$EPIC\"}"
  sleep 10
done
```

---

## Documentation Access

```bash
# Via command (as specified)
/integration-api-reference

# Via filesystem
cat ~/projects/maestro-engine-new/docs/api/jira-integration-api.md
cat ~/projects/maestro-engine-new/docs/api/e2e-agent-api.md
cat ~/projects/maestro-engine-new/docs/E2E_AGENT_QUICK_START.md
```

---

## Troubleshooting One-Liners

```bash
# Check if services are running
ps aux | grep -E "uvicorn|fastapi" | grep -v grep

# Check ports
netstat -tlnp | grep -E "8080|8000|4001"

# Reload JIRA data
curl -X POST http://localhost:8080/api/jira/reload

# Verify JIRA CSV files
wc -l docs/jira_*.csv

# Check latest logs
tail -f logs/e2e_workflow_*.json 2>/dev/null | head -20

# Test Quality Fabric connectivity
curl -s http://localhost:8000/api/health | jq '.status'
```

---

## Environment Variables

```bash
# Set custom Quality Fabric URL
export QUALITY_API_URL="http://localhost:8000"

# Set log level
export LOG_LEVEL="DEBUG"
```

---

## Quick Test Snippets

### Test JIRA Integration
```bash
curl http://localhost:8080/api/jira/health && echo " ✅ JIRA OK"
```

### Test E2E Agent
```bash
curl http://localhost:8080/api/e2e-agent/health && echo " ✅ E2E OK"
```

### Test Full Stack
```bash
python3 test_e2e_workflow.py 2>&1 | grep -E "SUCCESS|ERROR" | tail -5
```

---

## File Locations

```
Code:
  src/services/jira_integration_service.py
  src/services/e2e_dev_qa_agent.py
  src/api/jira_integration_routes.py
  src/api/e2e_agent_routes.py

Data:
  docs/jira_epics_export.csv
  docs/jira_actions_export.csv

Docs:
  docs/api/jira-integration-api.md
  docs/api/e2e-agent-api.md
  docs/E2E_AGENT_QUICK_START.md

Logs:
  logs/e2e_workflow_*.json
```

---

## Copy-Paste Examples

### Example 1: Run workflow and save report
```bash
RESULT=$(curl -s -X POST http://localhost:8080/api/e2e-agent/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"epic_id": "EPIC-3"}')
echo $RESULT | jq '.report_path' | xargs cat | jq '.steps.step4_validation'
```

### Example 2: Check if epic can be closed
```bash
curl -s http://localhost:8080/api/jira/epics/EPIC-3/check-completion | \
  jq 'if .is_complete then "✅ Ready to close" else "⏳ Still in progress" end'
```

### Example 3: Get test summary
```bash
curl -s http://localhost:8080/api/e2e-agent/workflow/status/EPIC-3 | \
  jq '{status, progress: .progress.percentage, tasks_done: .progress.done, total: .progress.total}'
```

---

**For full documentation, see:**
- E2E_AGENT_IMPLEMENTATION_SUMMARY.md
- docs/E2E_AGENT_QUICK_START.md
- docs/api/jira-integration-api.md
- docs/api/e2e-agent-api.md
