# 🆘 JIRA Integration Help for Agents

**Quick navigation for agents who need to connect to JIRA**

---

## 🚀 I'm New - Where Do I Start?

### Option 1: Super Quick (30 seconds)
👉 **Read the cheat sheet first:**
```bash
cat /home/ec2-user/projects/maestro-engine-new/JIRA_CHEAT_SHEET.md
```

This gives you everything you need in one page.

### Option 2: Detailed Guide (5 minutes)
👉 **Read the complete guide:**
```bash
cat /home/ec2-user/projects/maestro-engine-new/JIRA_INTEGRATION_QUICK_START.md
```

This includes troubleshooting, examples, and best practices.

### Option 3: Learn by Example
👉 **See a working implementation:**
```bash
cat /home/ec2-user/projects/maestro-engine-new/e2e_jira_workflow.sh
```

This shows a complete end-to-end workflow.

---

## 📚 Documentation Files

| File | Size | Purpose | When to Use |
|------|------|---------|-------------|
| **JIRA_CHEAT_SHEET.md** | 5KB | One-page reference | Quick lookups |
| **JIRA_INTEGRATION_QUICK_START.md** | 10KB | Complete guide | First-time setup |
| **e2e_jira_workflow.sh** | 17KB | Working script | See it in action |
| **E2E_EXECUTION_SUMMARY_2025-11-27.md** | 8KB | Example execution | See results |
| **E2E_JIRA_WORKFLOW_AGENT.md** | 14KB | Technical docs | Architecture details |

---

## 🎯 Common Tasks

### I need to generate a JWT token
```bash
cd /home/ec2-user/projects/maestro-frontend-production/backend
node -e "const jwt=require('jsonwebtoken');console.log(jwt.sign({sub:'2ZPhoXxter4L9sjFQbqLv',email:'test@maestro.ai',role:'admin'},'maestro-production-secret-change-in-production-2024',{expiresIn:'24h'}))"
```

### I need to fetch epics from JIRA
```bash
export JWT_TOKEN="<your_token>"
curl -s "http://localhost:3100/api/integrations/tasks?types=epic&statusCategories=todo" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items'
```

### I need to transition an epic to Done
```bash
curl -s -X POST "http://localhost:3100/api/integrations/tasks/MD-1841/transition" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"targetStatus":"Done","comment":"Work completed"}' | jq '.'
```

### I'm getting "unauthorized" errors
**Your token expired (24h lifetime). Generate a new one:**
```bash
cd /home/ec2-user/projects/maestro-frontend-production/backend
export JWT_TOKEN=$(node -e "const jwt=require('jsonwebtoken');console.log(jwt.sign({sub:'2ZPhoXxter4L9sjFQbqLv',email:'test@maestro.ai',role:'admin'},'maestro-production-secret-change-in-production-2024',{expiresIn:'24h'}))")
echo "New token: $JWT_TOKEN"
```

### I can't connect to the API
**Check if services are running:**
```bash
curl -s http://localhost:3100/health | jq '.status'  # Should return "healthy"
curl -s http://localhost:8000/health | jq '.status'   # Should return "healthy"
```

**If not running, start Maestro:**
```bash
cd /home/ec2-user/projects/maestro-frontend-production/backend
npm run dev &
```

---

## 🔍 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| 401 Unauthorized | Generate new JWT token (expires after 24h) |
| Connection refused | Start Maestro API: `npm run dev` in backend directory |
| Empty results | Try `statusCategories=in_progress` or remove filter |
| Transition failed | Check current status - may already be in target state |
| No epics found | Use `types=epic` without status filter to see all |

---

## 💡 Pro Tips

1. **Always check service health first**
   ```bash
   curl -s http://localhost:3100/health && echo "✅ Ready!"
   ```

2. **Save your token to avoid regenerating**
   ```bash
   echo "$JWT_TOKEN" > ~/.jira_token
   export JWT_TOKEN=$(cat ~/.jira_token)
   ```

3. **Use jq for pretty JSON output**
   ```bash
   # Install if needed
   sudo yum install -y jq
   
   # Then pipe all responses through it
   curl ... | jq '.'
   ```

4. **Test with a simple query first**
   ```bash
   curl -s "http://localhost:3100/api/integrations/tasks?types=epic&pageSize=1" \
     -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items[0].externalId'
   ```

---

## 🎓 Learning Path

### Beginner (10 minutes)
1. Read: `JIRA_CHEAT_SHEET.md`
2. Generate a JWT token
3. Fetch one epic
4. Success! ✅

### Intermediate (30 minutes)
1. Read: `JIRA_INTEGRATION_QUICK_START.md`
2. Try all the example commands
3. Transition an epic status
4. Create a new task

### Advanced (1 hour)
1. Read: `e2e_jira_workflow.sh`
2. Understand the 6-phase workflow
3. Run the complete workflow
4. Customize for your use case

---

## 📖 Full Documentation Reference

### In This Repository
- `JIRA_CHEAT_SHEET.md` - Quick reference (this is your best friend!)
- `JIRA_INTEGRATION_QUICK_START.md` - Complete setup guide
- `E2E_JIRA_WORKFLOW_AGENT.md` - Technical architecture docs
- `E2E_EXECUTION_SUMMARY_2025-11-27.md` - Real execution example
- `e2e_jira_workflow.sh` - Working bash script

### External References
- Full API Spec: `~/projects/maestro-frontend-production/docs/api/jira-integration-api.md`
- JIRA REST API: https://developer.atlassian.com/cloud/jira/platform/rest/v3/

---

## ✅ Validation Checklist

Before you start working with JIRA, verify:

- [ ] JWT token generated
- [ ] JWT token exported as environment variable
- [ ] Maestro API is healthy (http://localhost:3100/health)
- [ ] Quality-Fabric API is healthy (http://localhost:8000/health)
- [ ] Can fetch epics successfully
- [ ] Can retrieve single epic by ID
- [ ] jq is installed for JSON parsing

**Run this test:**
```bash
export JWT_TOKEN="<your_token>"
echo "Testing..."
curl -s "http://localhost:3100/api/integrations/tasks?types=epic&pageSize=1" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.output.items[0].externalId'
```

If you see an epic ID (like "MD-1841"), you're ready! ✅

---

## 🆘 Still Stuck?

### Step-by-Step Debugging

**1. Check if you have jq installed:**
```bash
which jq || sudo yum install -y jq
```

**2. Verify services are running:**
```bash
curl http://localhost:3100/health
curl http://localhost:8000/health
```

**3. Generate fresh token:**
```bash
cd /home/ec2-user/projects/maestro-frontend-production/backend
node -e "const jwt=require('jsonwebtoken');console.log(jwt.sign({sub:'2ZPhoXxter4L9sjFQbqLv',email:'test@maestro.ai',role:'admin'},'maestro-production-secret-change-in-production-2024',{expiresIn:'24h'}))"
```

**4. Test with the token:**
```bash
export JWT_TOKEN="<paste_token_here>"
curl -s "http://localhost:3100/api/integrations/tasks?types=epic&pageSize=1" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

**5. If you see data, you're connected! If not:**
- Check the response for error messages
- Verify the token is correctly set
- Make sure services are running
- Read the troubleshooting section in JIRA_CHEAT_SHEET.md

---

## 🎉 Success Stories

**Recent Execution:**
- Epic MD-1841 processed successfully
- 4/4 tests passed (100%)
- Epic transitioned from "In Progress" to "Done"
- Total time: < 1 second for API calls
- See full results: `E2E_EXECUTION_SUMMARY_2025-11-27.md`

---

**Created**: 2025-11-27  
**Last Updated**: 2025-11-27  
**Status**: Active and Maintained  
**Maintainer**: E2E Development & QA Agent

---

**Quick Links:**
- [Cheat Sheet](JIRA_CHEAT_SHEET.md) ← Start here!
- [Quick Start Guide](JIRA_INTEGRATION_QUICK_START.md)
- [Working Example](e2e_jira_workflow.sh)
- [Execution Summary](E2E_EXECUTION_SUMMARY_2025-11-27.md)
