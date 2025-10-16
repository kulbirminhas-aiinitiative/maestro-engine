# Quick Start: Async Workflow System

Get up and running with the async workflow system in 5 minutes.

## Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for frontend)
- Python 3.11+ (for backend)
- Redis (via Docker)

## 1. Start Redis

```bash
cd /home/ec2-user/projects/maestro-engine-new
docker-compose -f docker-compose.dev.yml up -d redis
```

Verify Redis is running:
```bash
docker ps | grep redis
redis-cli -p 6380 ping  # Should return "PONG"
```

## 2. Start Backend API

```bash
cd /home/ec2-user/projects/maestro-engine-new
python3.11 -m uvicorn src.api.workflow_api:app --reload --host 0.0.0.0 --port 8080
```

You should see:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8080
```

Test the API:
```bash
curl http://localhost:8080/api/workflow/active
# Should return: {"active_workflows": []}
```

## 3. Start Frontend

```bash
cd /home/ec2-user/projects/maestro-frontend-new
npm run dev
```

Navigate to: http://localhost:5173

## 4. Run Your First Workflow

### Via UI

1. Go to http://localhost:5173/workflow-studio
2. Click **"Start Workflow"** button
3. Enter requirement:
   ```
   Build a simple REST API for task management with CRUD operations
   ```
4. Enter project name: `task-api`
5. Click **"Start Workflow"**
6. Watch the progress in real-time!

### Via API

```bash
curl -X POST http://localhost:8080/api/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "requirement": "Build a calculator CLI application",
    "mode": "batch",
    "project_name": "calculator-cli",
    "quality_threshold": 0.70
  }'
```

Response:
```json
{
  "workflow_id": "wf-1728475200-abc123",
  "status": "starting",
  "project_name": "calculator-cli",
  "mode": "batch",
  "message": "Workflow started. Use /api/workflow/wf-1728475200-abc123/status to track progress."
}
```

## 5. Monitor Progress

### Check Status via API

```bash
# Replace with your workflow_id
curl http://localhost:8080/api/workflow/wf-1728475200-abc123/status
```

Response:
```json
{
  "workflow_id": "wf-1728475200-abc123",
  "status": "running",
  "current_phase": "implementation",
  "phases_completed": ["requirements", "design"],
  "progress": 0.6,
  "started_at": "2025-10-09T10:00:00Z",
  "updated_at": "2025-10-09T10:05:00Z"
}
```

### WebSocket Connection

```bash
# Install wscat if not available
npm install -g wscat

# Connect to WebSocket
wscat -c ws://localhost:8080/ws/workflow-async/wf-1728475200-abc123
```

You'll receive real-time events:
```json
{
  "type": "phase_started",
  "workflow_id": "wf-1728475200-abc123",
  "phase": "implementation",
  "timestamp": "2025-10-09T10:05:30Z"
}
```

## 6. View Artifacts

Artifacts are saved to:
```
~/projects/deployment/{project_name}/{phase}/
```

Example:
```bash
ls ~/projects/deployment/calculator-cli/
# requirements/  design/  implementation/  testing/  deployment/

ls ~/projects/deployment/calculator-cli/implementation/
# main.py  calculator.py  tests.py  README.md
```

In the UI:
1. Go to Workflow Studio
2. Click on a phase card (e.g., "Implementation")
3. Click the "Artifacts" tab
4. See real-time artifact list with live updates

## 7. Control Workflow

### Pause Workflow

```bash
curl -X POST http://localhost:8080/api/workflow/wf-1728475200-abc123/pause
```

Or click **"Pause"** button in UI.

### Cancel Workflow

```bash
curl -X POST http://localhost:8080/api/workflow/wf-1728475200-abc123/cancel
```

Or click **"Cancel"** button in UI.

### List Active Workflows

```bash
curl http://localhost:8080/api/workflow/active
```

## 8. Debug Issues

### Check Logs

**Backend logs:**
```bash
# If running via uvicorn
# Logs will be in terminal output

# Check Redis connection
redis-cli -p 6380 KEYS workflow:*
```

**Frontend logs:**
```bash
# Open browser console (F12)
# Look for WebSocket connection logs:
# ✅ WebSocket connected (async mode)
# 📨 WebSocket event: phase_started
```

### Common Issues

**"Disconnected" in UI:**
```bash
# Check if backend is running
curl http://localhost:8080/api/workflow/active

# Check if Redis is running
redis-cli -p 6380 ping
```

**No artifacts showing:**
```bash
# Check deployment folder
ls ~/projects/deployment/

# Verify project name matches
curl http://localhost:8080/api/workflow/projects
```

**Workflow stuck:**
```bash
# Check workflow status
curl http://localhost:8080/api/workflow/{workflow_id}/status

# Check Redis state
redis-cli -p 6380 HGETALL workflow:{workflow_id}

# Review backend logs for errors
```

## 9. Advanced Features

### Mixed Mode with Checkpoints

```bash
curl -X POST http://localhost:8080/api/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "requirement": "Build a blog platform",
    "mode": "mixed",
    "project_name": "blog-platform",
    "checkpoint_phases": ["design", "testing"]
  }'
```

This will:
1. Run requirements → design
2. **PAUSE** at design for review
3. Resume when approved
4. Run implementation → testing
5. **PAUSE** at testing for review
6. Resume when approved
7. Run deployment

### Get Checkpoints

```bash
curl http://localhost:8080/api/workflow/{workflow_id}/checkpoints
```

## 10. Clean Up

### Stop Services

```bash
# Stop frontend (Ctrl+C in terminal)

# Stop backend (Ctrl+C in terminal)

# Stop Redis
docker-compose -f docker-compose.dev.yml down
```

### Clear Redis Data

```bash
redis-cli -p 6380 FLUSHALL
```

## Next Steps

- Read [ASYNC_WORKFLOW_SYSTEM.md](./ASYNC_WORKFLOW_SYSTEM.md) for complete documentation
- Explore the UI components in Workflow Studio
- Try different execution modes (batch, phased, mixed)
- Customize quality thresholds per phase
- Integrate with your own workflow templates

## Support

- Documentation: See `ASYNC_WORKFLOW_SYSTEM.md`
- Examples: Check backend and frontend component files
- Issues: Report on GitHub

---

**Happy coding! 🚀**
