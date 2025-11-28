# E2E Workflow Agent - Quick Reference

## 🚀 Quick Start

```bash
cd /home/ec2-user/projects/maestro-engine-new
./e2e_jira_workflow.sh
```

## 🔑 Authentication Setup

```bash
# Generate JWT Token
cd /home/ec2-user/projects/maestro-frontend-production/backend
node -e "
const jwt = require('jsonwebtoken');
const token = jwt.sign(
  { sub: '2ZPhoXxter4L9sjFQbqLv', email: 'test@maestro.ai', role: 'admin' },
  'maestro-production-secret-change-in-production-2024',
  { expiresIn: '24h' }
);
console.log(token);
"
```

## 📡 API Endpoints

### Check Services
```bash
# Maestro API Health
curl http://localhost:3100/health

# Quality-Fabric Health
curl http://localhost:8000/health
```

### JIRA Integration
```bash
export JWT_TOKEN="<your_token>"

# List To Do Epics
curl -s "http://localhost:3100/api/integrations/tasks?types=epic&statusCategories=todo&pageSize=10" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items[] | {id: .externalId, title: .title, status: .status.name}'

# Get Specific Epic
curl -s "http://localhost:3100/api/integrations/tasks/MD-1842" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output'

# List Tasks for Epic
curl -s "http://localhost:3100/api/integrations/tasks?epicIds=MD-1842" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items[] | {id: .externalId, title: .title}'

# Transition Epic
curl -s -X POST "http://localhost:3100/api/integrations/tasks/MD-1842/transition" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"targetStatus": "Done", "comment": "Completed by E2E agent"}' | jq '.'
```

## 📊 View Results

```bash
# Latest Strategy
ls -lt /tmp/e2e_strategy_*.md | head -1 | awk '{print $NF}' | xargs cat

# Latest Test Results
ls -lt /tmp/e2e_test_cases_*.json | head -1 | awk '{print $NF}' | xargs cat | jq '.'

# Test Summary
ls -lt /tmp/e2e_test_cases_*.json | head -1 | awk '{print $NF}' | xargs cat | jq '{
  epic: .epic_id,
  total: .test_cases | length,
  passed: [.test_cases[] | select(.status == "passed")] | length,
  failed: [.test_cases[] | select(.status == "failed")] | length
}'
```

## 🔍 JIRA Queries

```bash
# All Quality-Fabric Epics
curl -s "http://localhost:3100/api/integrations/tasks?types=epic&labels=quality-fabric&pageSize=20" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items[] | {id: .externalId, title: .title, status: .status.name, priority: .priority}'

# High Priority To Do Items
curl -s "http://localhost:3100/api/integrations/tasks?types=epic,task&statusCategories=todo&priorities=high,highest" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items[] | {id: .externalId, title: .title, priority: .priority}'

# Search with JQL
curl -s -X POST "http://localhost:3100/api/integrations/tasks/search" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jql": "project = MD AND type = Epic AND status = \"To Do\"", "maxResults": 10}' | jq '.output.items[] | {id: .externalId, title: .title}'
```

## 🧪 Manual Test Execution

```bash
# Test 1: Health Check
curl -w "\nTime: %{time_total}s\n" http://localhost:8000/health

# Test 2: Epic Retrieval
curl -w "\nTime: %{time_total}s\n" \
  "http://localhost:3100/api/integrations/tasks/MD-1842" \
  -H "Authorization: Bearer $JWT_TOKEN"

# Test 3: List Epic Tasks
curl -w "\nTime: %{time_total}s\n" \
  "http://localhost:3100/api/integrations/tasks?epicIds=MD-1842" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

## 🛠️ Troubleshooting

### Check Running Services
```bash
# List processes
ps aux | grep -E "(maestro|gateway|uvicorn)" | grep -v grep

# Check ports
netstat -tlnp | grep -E "(3100|8000|8080)"
```

### Database Query
```bash
cd /home/ec2-user/projects/maestro-frontend-production/backend
node -e "
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();
prisma.users.findMany({ take: 5, select: { id: true, email: true } })
  .then(users => console.log(JSON.stringify(users, null, 2)))
  .catch(console.error)
  .finally(() => prisma.\$disconnect());
"
```

### Clean Artifacts
```bash
# Remove old test results
rm /tmp/e2e_test_cases_*.json
rm /tmp/e2e_strategy_*.md

# Fresh run
./e2e_jira_workflow.sh
```

## 📁 File Locations

| File | Location | Purpose |
|------|----------|---------|
| Workflow Script | `e2e_jira_workflow.sh` | Main execution script |
| Documentation | `E2E_JIRA_WORKFLOW_AGENT.md` | Full documentation |
| Summary | `E2E_WORKFLOW_SUMMARY.md` | Execution summary |
| Quick Ref | `E2E_QUICK_REFERENCE.md` | This file |
| Strategy | `/tmp/e2e_strategy_*.md` | Generated strategies |
| Test Results | `/tmp/e2e_test_cases_*.json` | Test execution data |

## 🎯 Common Tasks

### Run on Specific Epic
```bash
# Edit script line ~94 to force epic selection
EPIC_ID="MD-1841"  # Your epic ID
./e2e_jira_workflow.sh
```

### Add Custom Test Case
Edit `e2e_jira_workflow.sh` around line 150 to add new test case to JSON.

### Change Test Filters
Modify line ~41 in script:
```bash
# Current
statusCategories=todo,in_progress

# Change to
statusCategories=done  # Only completed epics
```

## 📞 Key Endpoints Summary

| Service | URL | Purpose |
|---------|-----|---------|
| Maestro API | `http://localhost:3100/api` | JIRA integration |
| Quality-Fabric | `http://localhost:8000` | Testing validation |
| Gateway | `http://localhost:8080` | API routing |

## 💡 Pro Tips

1. **Token Expires**: Generate new token every 24h
2. **Failed Tests**: Check `/tmp/e2e_test_cases_*.json` for error details
3. **Rate Limits**: Add delays between API calls if needed
4. **Parallel Runs**: Use different epic IDs to avoid conflicts

## 🔗 Related Documentation

- Full Agent Docs: `E2E_JIRA_WORKFLOW_AGENT.md`
- JIRA API Spec: `~/projects/maestro-frontend-production/docs/api/jira-integration-api.md`
- Execution Summary: `E2E_WORKFLOW_SUMMARY.md`

---

**Last Updated**: 2025-11-27  
**Quick Ref Version**: 1.0
