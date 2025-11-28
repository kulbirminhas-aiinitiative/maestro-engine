# Quick Start: Testing Workflow Blueprint Generation

**Feature:** Chat-to-DAG Workflow Blueprint Generation
**Status:** ✅ Ready for Testing

---

## Prerequisites

Ensure all services are running:

```bash
# Check backend (should show healthy)
curl http://localhost:3100/health

# Check frontend (should load)
curl http://localhost:4300

# Check collaboration BFF (should show healthy)
curl http://localhost:4002/health

# Check Maestro Engine (optional but recommended)
curl http://localhost:5001/health
```

---

## Quick Test (5 minutes)

### Step 1: Login

1. Open browser: `http://localhost:4300/login`
2. Login with:
   - Email: `admin@maestro.com`
   - Password: `Admin123@`

### Step 2: Navigate to Chat

1. From dashboard, click **"Mission Control"** or **"Collaboration Hub"**
2. Or go directly to: `http://localhost:4300/mission-control`

### Step 3: Send Workflow Request

In the chat input, send:

```
Create a workflow for building a mobile app with the following phases:
- Requirements gathering
- Backend API development
- Mobile app development
- Testing and QA
- Deployment
```

### Step 4: Verify AI Response

Amigo should respond within 30-60 seconds with:
- A message starting with "I've created a workflow blueprint for your project:"
- A `maestro-dag` code block containing JSON
- A visual preview card showing:
  - Workflow name (e.g., "Mobile App Development Workflow")
  - Phase count (e.g., "5 phases • 4 dependencies")
  - **"Import to DAG Studio"** button

### Step 5: Import to DAG Studio

1. Click the **"Import to DAG Studio"** button
2. Verify:
   - Button changes to **"Imported Successfully"** ✓
   - Success message appears

### Step 6: View in DAG Studio

1. Navigate to **"Orchestration Hub"** from main menu
2. Or go to: `http://localhost:4300/orchestration`
3. Verify:
   - Workflow appears on canvas
   - All phases are visible
   - Edges connect phases correctly
   - You can click on phases to edit them

---

## Expected Results

✅ **Success Indicators:**

1. Amigo responds with `maestro-dag` code block
2. Visual preview card displays with workflow details
3. Import button works and shows success
4. Workflow appears in DAG Studio
5. Workflow is editable

❌ **If Something Fails:**

Check the troubleshooting section below.

---

## Alternative Test Prompts

### Simple (30 seconds response):
```
Create a workflow for a REST API project
```

### Medium (45 seconds response):
```
Create a workflow for an e-commerce platform with user authentication,
product catalog, shopping cart, checkout, and payment integration
```

### Complex (60+ seconds response):
```
Create a workflow for a complete SaaS application including:
- User authentication and authorization
- Multi-tenant architecture
- Admin dashboard
- Customer portal
- Billing and subscription management
- Analytics and reporting
- Load testing and performance optimization
- Security audit
- Production deployment
```

---

## Troubleshooting

### Issue: No Response from Amigo

**Check:**
```bash
# Verify Collaboration BFF is running
curl http://localhost:4002/health

# Restart if needed
cd /home/ec2-user/projects/maestro-engine-new/src/bff
python3 collaboration_service.py &
```

### Issue: Amigo Responds but No DAG Code Block

**Possible Causes:**
1. Maestro Engine not running (backend will timeout)
2. Backend API not accessible

**Check:**
```bash
# Verify backend can reach Maestro Engine
curl http://host.docker.internal:5001/health

# Or if running locally:
curl http://localhost:5001/health
```

### Issue: DAG Preview Doesn't Appear

**Check:**
1. Open browser console (F12)
2. Look for JavaScript errors
3. Verify the response contains ````maestro-dag` markdown

**Manual Test:**
Paste this in chat to test rendering only (bypasses AI):

````
Here's your workflow:

```maestro-dag
{
  "version": "1.0",
  "workflow": {
    "id": "test-workflow",
    "name": "Test Workflow",
    "description": "Simple test workflow",
    "nodes": [
      {
        "id": "node-1",
        "type": "phase",
        "position": {"x": 300, "y": 100},
        "data": {
          "label": "Phase 1",
          "phaseType": "requirements",
          "assignedTeam": [],
          "assignedExecutorAI": "amigo",
          "timeout": 604800,
          "attributes": {
            "requirements": ["Test requirement"],
            "acceptanceCriteria": ["Test criteria"]
          }
        }
      }
    ],
    "edges": [],
    "settings": {"layoutDirection": "TB", "autoLayout": true},
    "validation": {"valid": true, "errors": [], "warnings": []}
  },
  "metadata": {
    "exportedAt": "2025-10-17T12:00:00Z",
    "exportedBy": "test",
    "application": "maestro-dag-studio"
  }
}
```
````

### Issue: Import Button Doesn't Work

**Check:**
1. Browser console for errors
2. Verify DAG JSON is valid (use JSON validator)
3. Check DAGStudioStore is initialized

**Fix:**
- Refresh the page
- Clear browser cache
- Try a different workflow

### Issue: Workflow Doesn't Appear in DAG Studio

**Check:**
1. Did you click the import button? (Look for "Imported Successfully")
2. Did you navigate to the correct page? (Orchestration Hub)
3. Try refreshing the DAG Studio page

---

## What to Look For During Testing

### Log Messages (Collaboration BFF Console)

You should see:
```
🏗️  Executing workflow blueprint generation tool...
   Requirement: Create a workflow for building a mobile app...
   Project Type: web_app
   Calling backend API: http://host.docker.internal:3100/api/v1/workflow-dag/generate
   ✅ Received DAG from backend
   ✅ Converted to frontend format: 5 nodes
```

### Browser Network Tab (F12 → Network)

Look for:
1. WebSocket connection to collaboration BFF
2. Messages being sent/received
3. No 404 or 500 errors

### Backend Logs

Look for:
```
🏗️  Generating workflow DAG for chat...
✅ DAG generated successfully: dag-xxx
   - Nodes: 5
   - Edges: 4
   - Validation: PASSED
```

---

## Performance Expectations

**Typical Response Times:**

- Simple workflow (3-5 phases): **30-45 seconds**
- Medium workflow (6-8 phases): **45-60 seconds**
- Complex workflow (10+ phases): **60-90 seconds**

**Breakdown:**
- AI decision to use tool: 2-5s
- Backend API call: 5-10s
- Maestro Engine DAG generation: 20-60s (depends on complexity)
- Format conversion: <1s
- Rendering in chat: <1s

---

## Success Criteria

To consider the feature working correctly, verify:

- [ ] Amigo responds to workflow requests
- [ ] Response includes maestro-dag code block
- [ ] Visual preview card displays
- [ ] Preview shows correct phase count
- [ ] Import button is clickable
- [ ] Import succeeds with success message
- [ ] Workflow appears in DAG Studio
- [ ] Workflow has correct phases
- [ ] Edges connect phases properly
- [ ] Phases can be edited
- [ ] No errors in console

---

## Reporting Issues

If you encounter issues, please collect:

1. **Browser Console Errors** (F12 → Console tab)
2. **Network Requests** (F12 → Network tab, filter: WS)
3. **Backend Logs** (from terminal running backend)
4. **Collaboration BFF Logs** (from terminal running BFF)
5. **Exact prompt you used**
6. **Screenshot of the issue**

---

## Additional Testing Scenarios

### Test 1: Multiple Sequential Workflows
1. Generate first workflow
2. Import it
3. Generate second workflow
4. Import it
5. Verify both appear in DAG Studio

### Test 2: Edit After Import
1. Generate and import workflow
2. Open in DAG Studio
3. Add a new phase
4. Delete an edge
5. Save changes
6. Verify changes persist

### Test 3: Error Handling
1. Disconnect Maestro Engine
2. Try to generate workflow
3. Verify graceful error message
4. Reconnect Maestro Engine
5. Try again - should work

---

## Next Steps After Successful Test

1. ✅ Mark feature as tested
2. Test with different project types
3. Test with more complex requirements
4. Provide feedback on generated workflows
5. Suggest improvements

---

**Happy Testing! 🚀**

If everything works, you now have a complete chat-to-DAG workflow feature that turns natural language project descriptions into visual, editable workflow blueprints!
