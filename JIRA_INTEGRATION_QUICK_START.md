# 🚀 JIRA Integration Quick Start Guide for Agents

> **Last Updated**: 2025-11-27  
> **Status**: Production Ready ✅

## 📋 Overview

This guide helps AI agents connect to JIRA through the Maestro Integration API. No direct JIRA API knowledge required - everything goes through our unified interface.

---

## 🔑 Step 1: Authentication

### Generate a Fresh JWT Token

```bash
cd /home/ec2-user/projects/maestro-frontend-production/backend

# Generate token (valid for 24 hours)
node -e "
const jwt = require('jsonwebtoken');
const token = jwt.sign(
  { 
    sub: '2ZPhoXxter4L9sjFQbqLv', 
    email: 'test@maestro.ai', 
    role: 'admin' 
  },
  'maestro-production-secret-change-in-production-2024',
  { expiresIn: '24h' }
);
console.log(token);
"
```

### Set Environment Variable

```bash
export JWT_TOKEN="<paste_token_here>"
```

**Test Authentication:**
```bash
curl -s http://localhost:3100/health \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.'
```

---

## 📡 Step 2: API Base URLs

```bash
# Maestro Integration API (JIRA gateway)
API_BASE="http://localhost:3100/api"

# Quality-Fabric API (testing/validation)
QF_API_BASE="http://localhost:8000"
```

**Health Check:**
```bash
# Maestro API
curl -s http://localhost:3100/health | jq '.status'

# Quality-Fabric API  
curl -s http://localhost:8000/health | jq '.status'
```

Both should return `"healthy"`

---

## 🎯 Step 3: Common JIRA Operations

### 3.1 List Epics

**To Do Epics:**
```bash
curl -s -X GET "${API_BASE}/integrations/tasks?types=epic&statusCategories=todo&pageSize=10" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" | jq '.output.items[] | {id: .externalId, title: .title, status: .status.name}'
```

**In Progress Epics:**
```bash
curl -s -X GET "${API_BASE}/integrations/tasks?types=epic&statusCategories=in_progress&pageSize=10" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" | jq '.output.items'
```

**All Epics (any status):**
```bash
curl -s -X GET "${API_BASE}/integrations/tasks?types=epic&pageSize=20" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" | jq '.output.items'
```

### 3.2 Get a Single Epic

```bash
EPIC_ID="MD-1841"

curl -s -X GET "${API_BASE}/integrations/tasks/${EPIC_ID}" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output'
```

### 3.3 List Tasks Under an Epic

```bash
EPIC_ID="MD-1841"

curl -s -X GET "${API_BASE}/integrations/tasks?epicIds=${EPIC_ID}&pageSize=50" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items[] | {id: .externalId, title: .title, status: .status.name, type: .type}'
```

### 3.4 Transition Epic/Task Status

**Transition to "In Progress":**
```bash
EPIC_ID="MD-1841"

curl -s -X POST "${API_BASE}/integrations/tasks/${EPIC_ID}/transition" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "targetStatus": "In Progress",
    "comment": "Agent started working on this epic"
  }' | jq '.'
```

**Transition to "Done":**
```bash
EPIC_ID="MD-1841"

curl -s -X POST "${API_BASE}/integrations/tasks/${EPIC_ID}/transition" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "targetStatus": "Done",
    "comment": "All validation tests passed. Epic completed successfully.",
    "resolution": "Fixed"
  }' | jq '.'
```

### 3.5 Create a New Task

```bash
curl -s -X POST "${API_BASE}/integrations/tasks" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "projectId": "MD",
    "title": "Implement new feature",
    "description": "Detailed description of the task",
    "type": "task",
    "priority": "high",
    "labels": ["automation", "agent-created"],
    "parentId": "MD-1841"
  }' | jq '.'
```

---

## 🔍 Step 4: Advanced Queries

### Search with JQL

```bash
curl -s -X POST "${API_BASE}/integrations/tasks/search" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jql": "project = MD AND status = \"To Do\" AND type = Epic ORDER BY priority DESC",
    "startAt": 0,
    "maxResults": 10
  }' | jq '.output.items'
```

### Filter by Multiple Criteria

```bash
# Get high-priority bugs in To Do status
curl -s -X GET "${API_BASE}/integrations/tasks?types=bug&statusCategories=todo&priorities=high,highest&pageSize=20" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items'
```

---

## 🐛 Troubleshooting

### Issue: "Access token is required" or 401 Error

**Solution:**
```bash
# Token expired or invalid - generate a new one
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

# Then export it
export JWT_TOKEN="<new_token>"
```

### Issue: "Cannot connect" or Connection Refused

**Solution:**
```bash
# Check if Maestro API is running
curl -s http://localhost:3100/health

# If not running, start it
cd /home/ec2-user/projects/maestro-frontend-production/backend
npm run dev &

# Wait 10 seconds for startup
sleep 10
```

### Issue: Empty Results or No Epics Found

**Solution:**
```bash
# Try different status categories
curl -s -X GET "${API_BASE}/integrations/tasks?types=epic&statusCategories=in_progress" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items | length'

# Or search all statuses
curl -s -X GET "${API_BASE}/integrations/tasks?types=epic" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items | length'
```

### Issue: Cannot Transition Status

**Check Available Transitions:**
```bash
EPIC_ID="MD-1841"

# Get current status
curl -s -X GET "${API_BASE}/integrations/tasks/${EPIC_ID}" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.status'

# Available transitions depend on workflow
# Common statuses: "To Do", "In Progress", "Done"
```

---

## 📚 Common Query Parameters

| Parameter | Type | Example | Description |
|-----------|------|---------|-------------|
| `types` | string[] | `epic,story,task,bug` | Filter by issue type |
| `statusCategories` | string[] | `todo,in_progress,done` | Filter by status category |
| `statuses` | string[] | `To Do,Done` | Filter by exact status name |
| `priorities` | string[] | `highest,high` | Filter by priority |
| `epicIds` | string[] | `MD-1841,MD-1842` | Filter by parent epic |
| `assigneeIds` | string[] | `712020:abc123` | Filter by assignee |
| `labels` | string[] | `feature,bug` | Filter by labels |
| `pageSize` | number | `50` | Results per page (max 100) |
| `page` | number | `1` | Page number (1-based) |

---

## 💡 Quick Tips

### 1. Always Use Fresh Tokens
Tokens expire after 24 hours. Generate new ones daily.

### 2. Check Service Health First
Before making API calls, verify services are running:
```bash
curl -s http://localhost:3100/health | jq '.status'
curl -s http://localhost:8000/health | jq '.status'
```

### 3. Use jq for JSON Parsing
Install if not available: `sudo yum install -y jq`

### 4. Save Responses for Debugging
```bash
curl -s ... > /tmp/response.json
cat /tmp/response.json | jq '.'
```

### 5. Common Field Mappings

**Epic ID**: Use `externalId` (e.g., "MD-1841") not internal `id`

**Status Categories**:
- `todo` = "To Do" 
- `in_progress` = "In Progress"
- `done` = "Done"

---

## 📖 Complete Example: Process an Epic

```bash
#!/bin/bash
# Complete workflow example

# 1. Setup
export JWT_TOKEN="<your_token>"
API_BASE="http://localhost:3100/api"

# 2. Find To Do Epic
EPIC_ID=$(curl -s -X GET "${API_BASE}/integrations/tasks?types=epic&statusCategories=todo&pageSize=1" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq -r '.output.items[0].externalId')

echo "Selected Epic: $EPIC_ID"

# 3. Get Epic Details
curl -s -X GET "${API_BASE}/integrations/tasks/${EPIC_ID}" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output | {id: .externalId, title: .title, status: .status.name}'

# 4. Transition to In Progress
curl -s -X POST "${API_BASE}/integrations/tasks/${EPIC_ID}/transition" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "targetStatus": "In Progress",
    "comment": "Agent started working"
  }' | jq '.'

# 5. Get Tasks Under Epic
curl -s -X GET "${API_BASE}/integrations/tasks?epicIds=${EPIC_ID}" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items | length'

# 6. Do work here...
echo "Performing work on epic..."

# 7. Transition to Done
curl -s -X POST "${API_BASE}/integrations/tasks/${EPIC_ID}/transition" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "targetStatus": "Done",
    "comment": "Work completed successfully"
  }' | jq '.'

echo "Epic $EPIC_ID completed!"
```

---

## 🔗 Reference Documentation

- **Full API Spec**: `~/projects/maestro-frontend-production/docs/api/jira-integration-api.md`
- **E2E Agent Example**: `~/projects/maestro-engine-new/e2e_jira_workflow.sh`
- **E2E Documentation**: `~/projects/maestro-engine-new/E2E_JIRA_WORKFLOW_AGENT.md`

---

## ✅ Quick Validation Checklist

Before starting JIRA operations:

- [ ] JWT token generated and exported
- [ ] Maestro API healthy (`curl http://localhost:3100/health`)
- [ ] Quality-Fabric API healthy (`curl http://localhost:8000/health`)
- [ ] Can fetch epics successfully
- [ ] Can retrieve single epic by ID
- [ ] Can transition epic status

---

## 🆘 Need Help?

**Test Your Setup:**
```bash
# Run this complete test
export JWT_TOKEN="<your_token>"

echo "Testing JIRA Integration..."
echo "1. Maestro Health: $(curl -s http://localhost:3100/health | jq -r '.status')"
echo "2. Quality-Fabric Health: $(curl -s http://localhost:8000/health | jq -r '.status')"
echo "3. Epic Count: $(curl -s -X GET 'http://localhost:3100/api/integrations/tasks?types=epic&pageSize=5' -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items | length')"
echo "Test complete!"
```

If any step fails, refer to the troubleshooting section above.

---

**Created**: 2025-11-27  
**Author**: E2E Development & QA Agent  
**Version**: 1.0.0
