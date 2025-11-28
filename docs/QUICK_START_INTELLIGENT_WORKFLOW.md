# Quick Start: Intelligent Workflow Testing

**Date**: 2025-10-20
**Goal**: Test intelligent workflow recommendations in 5 minutes

---

## 🚀 Quick Test (5 Minutes)

### Step 1: Start Backend Server (1 min)

```bash
cd /home/ec2-user/projects/maestro-frontend-production/backend
npm run dev
```

**Wait for**: `Server running on port 3100`

---

### Step 2: Test Backend APIs (1 min)

Open a new terminal:

```bash
# Test health check
curl -s http://localhost:3100/api/intelligent-workflow/health | jq

# Expected: {"status": "healthy", ...}

# Test agents endpoint
curl -s "http://localhost:3100/api/intelligent-workflow/agents?status=active" | jq '.agents | length'

# Expected: Number of agents (should be > 0)

# Test phase types endpoint
curl -s "http://localhost:3100/api/intelligent-workflow/phase-types?is_active=true" | jq '.phase_types | length'

# Expected: 14 (phase types)
```

✅ **If all return data, backend is working!**

---

### Step 3: Start Workflow Service (1 min)

```bash
cd /home/ec2-user/projects/maestro-engine-new/src/bff

# Kill existing service if running
lsof -i :8101 | awk 'NR>1 {print $2}' | xargs -r kill -9

# Start service
python3 workflow_generation_service.py
```

**Look for**:
```
✨ Intelligent Mode: ENABLED
   • AI-powered team recommendations with confidence scores
   • Backend API: http://localhost:3100
```

✅ **If you see this, intelligent mode is active!**

---

### Step 4: Generate Workflow with Recommendations (2 min)

Open a new terminal:

```bash
# Create test request
cat > /tmp/test_intelligent_workflow.json << 'EOF'
{
  "requirement": "Build a SaaS e-commerce platform with React, Node.js, and PostgreSQL",
  "conversation_context": [
    "User wants multi-tenant architecture",
    "Stripe payment integration required",
    "Need admin dashboard for vendors"
  ],
  "user_id": "test_user",
  "room_id": "test_room"
}
EOF

# Generate workflow
curl -X POST http://localhost:8101/generate-workflow \
  -H "Content-Type: application/json" \
  -d @/tmp/test_intelligent_workflow.json \
  -o /tmp/intelligent_workflow_result.json

# Check results
echo "=== Workflow Metadata ==="
jq '.workflow.metadata' /tmp/intelligent_workflow_result.json

echo -e "\n=== Recommendations Generated ==="
jq '.workflow.recommendations | keys' /tmp/intelligent_workflow_result.json

echo -e "\n=== Sample Recommendation ==="
jq '.workflow.recommendations | to_entries | first | .value.primary_recommendation | {agent: .agent_name, confidence: .confidence_score, level: .confidence_level}' /tmp/intelligent_workflow_result.json
```

---

### Expected Output

#### Metadata Should Show:
```json
{
  "aiGenerated": true,
  "intelligentMode": true,
  "recommendationsGenerated": true,
  "generationMethod": "claude-code-api-with-intelligent-recommendations"
}
```

#### Recommendations Should Include:
```json
{
  "agent": "AI Product Manager",
  "confidence": 0.92,
  "level": "high"
}
```

---

## ✅ Success Indicators

You'll know it's working when you see:

1. **Backend Health Check** ✅ Returns `"status": "healthy"`
2. **Agents Endpoint** ✅ Returns list of agents with metrics
3. **Phase Types** ✅ Returns 14 phase types
4. **Workflow Service** ✅ Shows "Intelligent Mode: ENABLED"
5. **Workflow Generation** ✅ Includes `recommendations` field
6. **Metadata** ✅ Shows `intelligentMode: true`, `recommendationsGenerated: true`

---

## 🔍 View Full Recommendation Details

```bash
# See all recommendations for all phases
jq '.workflow.recommendations' /tmp/intelligent_workflow_result.json

# See detailed breakdown for first phase
jq '.workflow.recommendations | to_entries | first | .value' /tmp/intelligent_workflow_result.json

# Count how many phases got recommendations
jq '.workflow.recommendations | length' /tmp/intelligent_workflow_result.json
```

---

## 📊 Check Service Logs

```bash
# View workflow service logs
tail -50 /tmp/workflow_service_test.log | grep -E "(Intelligent|recommendation|Backend|confidence)"
```

**Look for**:
```
✨ Intelligent Mode: ENABLED
📊 Fetching organizational data from backend APIs...
✓ Fetched 12 agents and 14 phase types
🎯 Generating team recommendations with confidence scores...
✓ Generated recommendations for 6 phases
```

---

## 🎯 What You Should See

### In Workflow Service Logs:
```
2025-10-20 12:00:00 - INFO - 📊 Fetching organizational data from backend APIs...
2025-10-20 12:00:00 - INFO - ✓ Fetched 12 agents and 14 phase types
2025-10-20 12:00:00 - INFO - 🎯 Generating team recommendations with confidence scores...
2025-10-20 12:00:00 - INFO - ✓ Generated recommendations for 6 phases
2025-10-20 12:00:00 - INFO - ✅ AI-generated workflow with 6 phases
2025-10-20 12:00:00 - INFO -    🎯 Team recommendations: 6 phases
2025-10-20 12:00:00 - INFO -       High confidence: 5/6
```

### In Generated Workflow:
```json
{
  "workflow": {
    "nodes": [...],  // 6-9 phases
    "metadata": {
      "intelligentMode": true,
      "recommendationsGenerated": true
    },
    "recommendations": {
      "requirements-001": {
        "primary_recommendation": {
          "agent_id": "product_manager",
          "agent_name": "AI Product Manager",
          "confidence_score": 0.92,
          "confidence_level": "high",
          "reasoning": "Excellent match for Requirements Gathering...",
          "strengths": [...],
          "concerns": [],
          "breakdown": {
            "skill_match": 0.95,
            "historical_success": 0.89,
            "collaboration": 0.94,
            "availability": 1.0
          }
        },
        "alternatives": [...]
      },
      ...
    }
  }
}
```

---

## 🆘 Troubleshooting

### Backend API Returns 404
```bash
# Check if route is registered
grep "intelligent-workflow" /home/ec2-user/projects/maestro-frontend-production/backend/src/server.ts

# Should see: app.use(`${config.server.apiPrefix}/intelligent-workflow`, intelligentWorkflowRoutes);
```

**Fix**: Restart backend server

---

### Workflow Service Shows "Basic Mode"
```bash
# Check if backend is accessible
curl -s http://localhost:3100/api/intelligent-workflow/health

# If it fails, check backend is running
lsof -i :3100
```

**Fix**: Start backend server first

---

### No Recommendations in Workflow
**Check workflow service logs**:
```bash
tail -100 /tmp/workflow_service_test.log | grep -i "recommendation\|agent\|phase"
```

**Look for errors or warnings**

---

## 🎉 You're Done!

If you see:
- ✅ Backend returning healthy status
- ✅ Agents and phase types data available
- ✅ Workflow service in intelligent mode
- ✅ Workflows include recommendations
- ✅ Confidence scores calculated

**Congratulations! Intelligent workflow recommendations are working!** 🚀

---

## 📝 Next Steps

1. **Populate Real Data**
   - Run database migrations
   - Add actual agent performance metrics

2. **Frontend Integration**
   - Display confidence badges
   - Show alternative suggestions
   - Add override UI

3. **Analytics**
   - Track recommendation acceptance
   - Monitor workflow success rates
   - Adjust confidence scoring weights

---

**Quick Start Time**: ~5 minutes
**Status**: Ready to Test
**Documentation**: See INTELLIGENT_WORKFLOW_APIS_COMPLETE.md for details

