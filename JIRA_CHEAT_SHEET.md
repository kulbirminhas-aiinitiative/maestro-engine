# JIRA Integration - Agent Cheat Sheet

**Quick reference for AI agents connecting to JIRA through Maestro API**
**Updated**: 2025-11-29

---

## QUICK START - Copy & Paste Ready

```bash
# ONE-LINER SETUP (run this first!)
cd /home/ec2-user/projects/maestro-frontend-production/backend && \
JWT_TOKEN=$(node -e "const jwt=require('jsonwebtoken');console.log(jwt.sign({sub:'2ZPhoXxter4L9sjFQbqLv',email:'test@maestro.ai',role:'admin'},'maestro-production-secret-change-in-production-2024',{expiresIn:'24h'}))") && \
echo $JWT_TOKEN > /tmp/jwt_token.txt && \
echo "Token saved to /tmp/jwt_token.txt"
```

**After running the above, use these in any terminal:**
```bash
TOKEN=$(cat /tmp/jwt_token.txt)
API="http://localhost:14100/api"
```

---

## Environment Configuration

| Environment | Backend Port | API Base URL | Status |
|-------------|-------------|--------------|--------|
| **Sandbox** | **14100** | `http://localhost:14100/api` | **USE THIS** |
| Production | 3100 | `http://localhost:3100/api` | Available |

**IMPORTANT**: Always use **Sandbox (14100)** for development work.

---

## Verify Connection

```bash
# Quick health check
curl -s http://localhost:14100/health | head -c 100

# Test JIRA connectivity
TOKEN=$(cat /tmp/jwt_token.txt)
curl -s "http://localhost:14100/api/integrations/tasks?types=epic&pageSize=1" \
  -H "Authorization: Bearer $TOKEN" | head -c 500
```

If you see JSON with Epic data, you're connected!

---

## Essential Operations

### 1. List To Do Epics
```bash
TOKEN=$(cat /tmp/jwt_token.txt)
curl -s "http://localhost:14100/api/integrations/tasks?types=epic&statusCategories=todo" \
  -H "Authorization: Bearer $TOKEN" | head -c 3000
```

### 2. Get Epic Details
```bash
TOKEN=$(cat /tmp/jwt_token.txt)
curl -s "http://localhost:14100/api/integrations/tasks/MD-1920" \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Get Child Tasks of Epic
```bash
TOKEN=$(cat /tmp/jwt_token.txt)
curl -s -X POST "http://localhost:14100/api/integrations/tasks/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jql": "parent = MD-1920 ORDER BY key ASC", "maxResults": 50}'
```

### 4. Transition Task to "In Progress"
```bash
TOKEN=$(cat /tmp/jwt_token.txt)
curl -s -X POST "http://localhost:14100/api/integrations/tasks/MD-1937/transition" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"targetStatus":"In Progress","comment":"Starting work"}'
```

### 5. Transition Task to "Done"
```bash
TOKEN=$(cat /tmp/jwt_token.txt)
curl -s -X POST "http://localhost:14100/api/integrations/tasks/MD-1937/transition" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"targetStatus":"Done","comment":"Implementation complete"}'
```

### 6. Add Comment to Task
```bash
TOKEN=$(cat /tmp/jwt_token.txt)
curl -s -X POST "http://localhost:14100/api/integrations/tasks/MD-1937/comments" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body":"Progress update: Completed feature X"}'
```

---

## Query Parameters

| Parameter | Values | Example |
|-----------|--------|---------|
| `types` | epic, story, task, bug, subtask | `types=epic,task` |
| `statusCategories` | todo, in_progress, done | `statusCategories=todo` |
| `priorities` | highest, high, medium, low, lowest | `priorities=high` |
| `epicIds` | Epic keys (comma-separated) | `epicIds=MD-1920` |
| `pageSize` | 1-100 | `pageSize=50` |

---

## Response Structure

All responses follow this structure:
```json
{
  "success": true,
  "output": {
    "items": [...],      // For list operations
    "totalCount": 10,
    "pageSize": 50
  }
}
```

**Key fields per item:**
- `externalId`: JIRA key like "MD-1920"
- `title`: Task summary
- `status.name`: Current status ("To Do", "In Progress", "Done")
- `status.category`: Status category ("todo", "in_progress", "done")
- `type`: Issue type ("epic", "story", "task", "bug")
- `priority`: Priority level

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **401 Unauthorized** | Token expired - regenerate with one-liner above |
| **Connection refused** | Run: `pm2 restart sandbox-backend` |
| **Empty results** | Remove filters or try `statusCategories=in_progress` |
| **Transition failed** | Task may already be in target status |
| **jq parse error** | Use `head -c 2000` instead of jq to see raw response |
| **Token not found** | Run the one-liner setup again |

### Restart Services
```bash
pm2 restart sandbox-backend   # Port 14100
pm2 restart sandbox-frontend  # Port 13000
pm2 list                      # Check all services
```

---

## Common Workflows

### Find and Start Work on Next Task
```bash
TOKEN=$(cat /tmp/jwt_token.txt)

# 1. Find To Do tasks in an Epic
curl -s -X POST "http://localhost:14100/api/integrations/tasks/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jql": "parent = MD-1920 AND status = \"To Do\" ORDER BY priority DESC", "maxResults": 5}' \
  > /tmp/tasks.json

# 2. Parse first task ID
TASK=$(python3 -c "import json; d=json.load(open('/tmp/tasks.json')); print(d['output']['items'][0]['externalId'] if d.get('output',{}).get('items') else '')")
echo "Next task: $TASK"

# 3. Transition to In Progress
curl -s -X POST "http://localhost:14100/api/integrations/tasks/$TASK/transition" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"targetStatus":"In Progress"}'
```

### Complete Task with Comment
```bash
TOKEN=$(cat /tmp/jwt_token.txt)
TASK="MD-1937"

# Add completion comment
curl -s -X POST "http://localhost:14100/api/integrations/tasks/$TASK/comments" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body":"Implementation complete:\n- Created service file\n- Added tests\n- Updated documentation"}'

# Transition to Done
curl -s -X POST "http://localhost:14100/api/integrations/tasks/$TASK/transition" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"targetStatus":"Done"}'
```

---

## File Locations

| Resource | Path |
|----------|------|
| This Cheat Sheet | `/home/ec2-user/projects/maestro-engine-new/JIRA_CHEAT_SHEET.md` |
| Detailed Guide | `/home/ec2-user/projects/maestro-engine-new/JIRA_INTEGRATION_QUICK_START.md` |
| Port Strategy | `/home/ec2-user/projects/SERVICE_PORT_STRATEGY_FINAL.md` |
| Environment Setup | `/home/ec2-user/projects/ENVIRONMENT_SETUP_MD1920.md` |
| Backend .env | `/home/ec2-user/projects/maestro-frontend-production/backend/.env` |
| Saved JWT Token | `/tmp/jwt_token.txt` |

---

## JIRA Project Info

| Setting | Value |
|---------|-------|
| Project Key | MD (Maestro Development) |
| Site URL | https://fifth9.atlassian.net |
| API Email | kulbir.minhas@fifth-9.com |

---

## API Policy Reminder

**IMPORTANT**: Per CLAUDE.md policy, agents must use the internal adapter API (`/api/integrations/tasks/*`) and NOT make direct calls to `*.atlassian.net`. The adapter handles authentication, rate limiting, and error handling.

---

**Last Updated**: 2025-11-29
