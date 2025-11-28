# 🎯 JIRA Integration - Agent Cheat Sheet

**Quick reference for agents connecting to JIRA through Maestro API**

---

## ⚡ 30-Second Setup

```bash
# 1. Generate token
cd /home/ec2-user/projects/maestro-frontend-production/backend
export JWT_TOKEN=$(node -e "const jwt=require('jsonwebtoken');console.log(jwt.sign({sub:'2ZPhoXxter4L9sjFQbqLv',email:'test@maestro.ai',role:'admin'},'maestro-production-secret-change-in-production-2024',{expiresIn:'24h'}))")

# 2. Set API base
export API_BASE="http://localhost:3100/api"

# 3. Test connection
curl -s "${API_BASE}/integrations/tasks?types=epic&pageSize=1" -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items[0].externalId'
```

**If you see an Epic ID (e.g., "MD-1841"), you're connected! ✅**

---

## 📋 Essential Commands

### Get To Do Epics
```bash
curl -s "${API_BASE}/integrations/tasks?types=epic&statusCategories=todo" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items'
```

### Get Epic Details
```bash
curl -s "${API_BASE}/integrations/tasks/MD-1841" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output'
```

### Get Tasks Under Epic
```bash
curl -s "${API_BASE}/integrations/tasks?epicIds=MD-1841" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items'
```

### Transition to "In Progress"
```bash
curl -s -X POST "${API_BASE}/integrations/tasks/MD-1841/transition" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"targetStatus":"In Progress","comment":"Started work"}' | jq '.'
```

### Transition to "Done"
```bash
curl -s -X POST "${API_BASE}/integrations/tasks/MD-1841/transition" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"targetStatus":"Done","comment":"Completed"}' | jq '.'
```

---

## 🔧 Common Filters

```bash
# High priority bugs in To Do
curl -s "${API_BASE}/integrations/tasks?types=bug&statusCategories=todo&priorities=high"

# In Progress stories
curl -s "${API_BASE}/integrations/tasks?types=story&statusCategories=in_progress"

# All tasks for epic
curl -s "${API_BASE}/integrations/tasks?epicIds=MD-1841&pageSize=50"
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| **401 Unauthorized** | Token expired - regenerate: `export JWT_TOKEN=$(node -e "...")` |
| **Connection refused** | Start Maestro: `cd ~/projects/maestro-frontend-production/backend && npm run dev &` |
| **Empty results** | Try different status: `statusCategories=in_progress` or remove filter |
| **Transition failed** | Check current status - may already be in target state |

---

## 📊 Query Parameters Reference

| Parameter | Values | Example |
|-----------|--------|---------|
| `types` | epic, story, task, bug | `types=epic,task` |
| `statusCategories` | todo, in_progress, done | `statusCategories=todo` |
| `priorities` | highest, high, medium, low | `priorities=high` |
| `epicIds` | Epic IDs (comma-separated) | `epicIds=MD-1841` |
| `pageSize` | 1-100 | `pageSize=50` |

---

## 💡 Pro Tips

1. **Always check services first:**
   ```bash
   curl -s http://localhost:3100/health | jq '.status'  # Should be "healthy"
   ```

2. **Use `externalId` not `id`** - that's the "MD-1841" format

3. **Save token in file for reuse:**
   ```bash
   echo "$JWT_TOKEN" > ~/.jira_token
   export JWT_TOKEN=$(cat ~/.jira_token)
   ```

4. **Pretty print responses:** Always pipe to `jq '.'`

5. **Test before workflow:** Run one epic fetch to verify everything works

---

## 🚀 Complete Workflow Template

```bash
#!/bin/bash
# Copy-paste ready workflow

export JWT_TOKEN="<your_token_here>"
API_BASE="http://localhost:3100/api"

# 1. Get first To Do epic
EPIC_ID=$(curl -s "${API_BASE}/integrations/tasks?types=epic&statusCategories=todo&pageSize=1" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq -r '.output.items[0].externalId')

echo "Working on: $EPIC_ID"

# 2. Start work
curl -s -X POST "${API_BASE}/integrations/tasks/${EPIC_ID}/transition" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"targetStatus":"In Progress"}' > /dev/null

# 3. Do your work here
echo "Doing work..."

# 4. Complete
curl -s -X POST "${API_BASE}/integrations/tasks/${EPIC_ID}/transition" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"targetStatus":"Done","comment":"Work completed"}' > /dev/null

echo "Done: $EPIC_ID"
```

---

## 📚 Full Documentation

- **Detailed Guide**: `/home/ec2-user/projects/maestro-engine-new/JIRA_INTEGRATION_QUICK_START.md`
- **API Spec**: `~/projects/maestro-frontend-production/docs/api/jira-integration-api.md`
- **Working Example**: `~/projects/maestro-engine-new/e2e_jira_workflow.sh`

---

**Quick Test:**
```bash
curl -s http://localhost:3100/health && echo " ✅ Ready to go!"
```
