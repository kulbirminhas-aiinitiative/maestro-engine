# Async Workflow Execution System

## Overview

The Async Workflow Execution System provides **non-blocking, real-time workflow execution** with comprehensive progress tracking, WebSocket updates, and state persistence. This system enables long-running SDLC workflows (requirements → design → implementation → testing → deployment) to run asynchronously while providing real-time updates to the frontend.

## Architecture

### High-Level Flow

```
┌─────────────┐      HTTP POST      ┌──────────────────┐
│   Frontend  │ ─────────────────▶  │  workflow_api.py │
│ (React App) │                     │   (FastAPI)      │
└─────────────┘                     └──────────────────┘
      │                                      │
      │                                      ├── Creates AsyncIO Task
      │                                      │
      │ WebSocket                            ▼
      │ Connection         ┌────────────────────────────────┐
      └───────────────────▶│  workflow_executor.py          │
                           │  (MaestroWorkflowExecutor)     │
                           └────────────────────────────────┘
                                      │
                                      ├── Executes Phases
                                      │
                                      ▼
                           ┌────────────────────────────────┐
                           │  team_execution_v2_split_mode  │
                           │  (Core Workflow Engine)        │
                           └────────────────────────────────┘
                                      │
                                      ├── Emits Progress Events
                                      │
                  ┌───────────────────┴───────────────────┐
                  │                                       │
                  ▼                                       ▼
         ┌──────────────────┐              ┌──────────────────────┐
         │  redis_manager    │              │  websocket_manager   │
         │  (State Storage)  │              │  (Event Broadcasting)│
         └──────────────────┘              └──────────────────────┘
```

### Components

#### Backend Infrastructure

1. **redis_manager.py** - State persistence and recovery
2. **workflow_executor.py** - Async orchestration and event handling
3. **websocket_manager.py** - WebSocket connection pooling and broadcasting
4. **workflow_api.py** - REST API endpoints and WebSocket routes
5. **team_execution_v2_split_mode.py** - Core SDLC execution engine

#### Frontend Components

1. **useWorkflowExecution.ts** - React hook for workflow control and state
2. **WorkflowStudio.tsx** - Main UI with workflow controls
3. **ArtifactsTab.tsx** - Real-time artifact display
4. **WorkflowProgressDashboard.tsx** - Comprehensive progress visualization

---

## Backend Components

### 1. Redis Manager (`redis_manager.py`)

**Purpose:** Persistent state storage for workflows, phases, and metadata.

**Key Features:**
- Workflow state tracking (starting, running, paused, completed, error)
- Phase-level metadata storage
- WebSocket connection registry
- Checkpoint metadata storage
- Automatic TTL management (7 days for active, 24 hours for completed)

**Redis Schema:**
```
workflow:{id}                 → Hash of workflow metadata
workflow:{id}:phase:{phase}   → Hash of phase results
active_workflows              → Set of active workflow IDs
ws:connections:{workflow_id}  → Set of WebSocket connection IDs
workflow:{id}:checkpoints     → List of checkpoint metadata
```

**Example Usage:**
```python
redis_manager = WorkflowStateManager(redis_url="redis://localhost:6380", db=0)

# Create workflow
await redis_manager.create_workflow("wf-123", {
    "requirement": "Build REST API",
    "mode": "batch",
    "project_name": "my-api"
})

# Update progress
await redis_manager.update_workflow("wf-123", {
    "current_phase": "implementation",
    "progress": 0.6
})

# Complete phase
await redis_manager.complete_phase(
    "wf-123",
    "implementation",
    quality_score=0.85,
    artifacts=["main.py", "models.py", "routes.py"]
)
```

### 2. Workflow Executor (`workflow_executor.py`)

**Purpose:** Orchestrate async workflow execution and manage progress callbacks.

**Key Features:**
- AsyncIO task management
- Three execution modes: batch, phased, mixed
- Progress callback system
- Workflow control (pause, cancel, resume)
- Automatic cleanup on completion

**Execution Modes:**

1. **Batch Mode** - All phases run continuously
   ```python
   result = await executor.start_workflow(WorkflowExecutionRequest(
       workflow_id="wf-123",
       requirement="Build API",
       mode="batch",
       project_name="my-api"
   ))
   ```

2. **Phased Mode** - One phase at a time with manual progression
   ```python
   result = await executor.start_workflow(WorkflowExecutionRequest(
       workflow_id="wf-123",
       requirement="Build API",
       mode="phased"
   ))
   ```

3. **Mixed Mode** - Selective checkpoints at specified phases
   ```python
   result = await executor.start_workflow(WorkflowExecutionRequest(
       workflow_id="wf-123",
       requirement="Build API",
       mode="mixed",
       checkpoint_phases=["design", "testing"]
   ))
   ```

**Event Types Emitted:**
- `workflow_started` - Workflow begins
- `phase_started` - Phase execution begins
- `blueprint_selected` - Team blueprint chosen
- `artifacts_created` - Files generated
- `quality_check` - Quality metrics calculated
- `phase_completed` - Phase finishes
- `checkpoint_created` - Checkpoint saved
- `workflow_completed` - All phases done
- `workflow_error` - Error occurred

### 3. WebSocket Manager (`websocket_manager.py`)

**Purpose:** Manage WebSocket connections and broadcast events.

**Key Features:**
- Connection pooling by workflow_id
- Message broadcasting to all subscribers
- Message queuing for offline delivery
- Connection health monitoring (ping/pong)
- Automatic cleanup of stale connections

**Example Usage:**
```python
ws_manager = WebSocketConnectionManager(redis_manager=redis)

# Accept connection
await ws_manager.connect(websocket, workflow_id="wf-123", client_id="user-456")

# Broadcast event
await ws_manager.broadcast_to_workflow("wf-123", {
    "type": "phase_started",
    "phase": "implementation",
    "timestamp": datetime.now().isoformat()
})

# Get statistics
stats = ws_manager.get_stats()
# {
#   "total_connections": 3,
#   "workflows_with_connections": 2,
#   "workflow_breakdown": {"wf-123": 2, "wf-456": 1}
# }
```

### 4. Workflow API (`workflow_api.py`)

**Purpose:** REST API endpoints and WebSocket routes.

**REST Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/workflow/execute` | Start async workflow |
| GET | `/api/workflow/{id}/status` | Get workflow status |
| GET | `/api/workflow/{id}/checkpoints` | List checkpoints |
| POST | `/api/workflow/{id}/pause` | Pause workflow |
| POST | `/api/workflow/{id}/cancel` | Cancel workflow |
| GET | `/api/workflow/active` | List active workflows |
| WS | `/ws/workflow-async/{id}` | WebSocket for real-time updates |

**Example Request:**
```bash
curl -X POST http://localhost:8080/api/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "requirement": "Build a REST API for user management",
    "mode": "batch",
    "project_name": "user-api",
    "quality_threshold": 0.70
  }'
```

**Response:**
```json
{
  "workflow_id": "wf-1234567890-abc123",
  "status": "starting",
  "project_name": "user-api",
  "mode": "batch",
  "message": "Workflow started. Use /api/workflow/wf-1234567890-abc123/status to track progress."
}
```

### 5. Team Execution Engine (`team_execution_v2_split_mode.py`)

**Purpose:** Core SDLC workflow execution with phase-by-phase processing.

**Enhanced Features:**
- Optional `progress_callback` parameter on all execution methods
- Real-time event emissions at key workflow points
- Phase transition validation with contract checking
- Quality thresholds per phase
- Checkpoint creation at configurable boundaries

**Progress Callback Integration:**
```python
engine = TeamExecutionEngineV2SplitMode(
    output_dir="./generated_project",
    checkpoint_dir="./checkpoints"
)

async def handle_progress(event: Dict[str, Any]):
    print(f"Event: {event['type']} - Phase: {event.get('phase')}")
    # Broadcast to WebSocket clients
    await ws_manager.broadcast_to_workflow(workflow_id, event)

# Execute with callback
context = await engine.execute_batch(
    requirement="Build REST API",
    progress_callback=handle_progress
)
```

---

## Frontend Components

### 1. useWorkflowExecution Hook

**Purpose:** React hook for workflow control and real-time updates.

**Features:**
- Start workflow execution (non-blocking)
- Real-time progress via WebSocket
- Workflow control (pause, cancel, resume)
- Automatic reconnection on disconnect
- Status polling fallback
- Event subscription system

**Example Usage:**
```tsx
const {
  startWorkflow,
  pauseWorkflow,
  cancelWorkflow,
  workflowId,
  status,
  progress,
  currentPhase,
  events,
  isConnected,
  isRunning
} = useWorkflowExecution();

// Start workflow
const handleStart = async () => {
  const result = await startWorkflow({
    requirement: "Build a REST API",
    mode: "batch",
    project_name: "my-api"
  });

  if (result) {
    console.log('Workflow started:', result.workflow_id);
  }
};

// Monitor progress
useEffect(() => {
  if (progress > 0) {
    console.log(`Progress: ${(progress * 100).toFixed(0)}%`);
  }
}, [progress]);

// Listen to events
useEffect(() => {
  const lastEvent = events[events.length - 1];
  if (lastEvent?.type === 'phase_completed') {
    console.log('Phase completed:', lastEvent.phase);
  }
}, [events]);
```

**Return Values:**

| Property | Type | Description |
|----------|------|-------------|
| `startWorkflow` | `function` | Start async workflow |
| `pauseWorkflow` | `function` | Pause active workflow |
| `cancelWorkflow` | `function` | Cancel workflow |
| `workflowId` | `string\|null` | Current workflow ID |
| `status` | `WorkflowStatusData\|null` | Full status object |
| `progress` | `number` | Progress 0.0-1.0 |
| `currentPhase` | `string\|undefined` | Active phase name |
| `events` | `WorkflowEvent[]` | All events received |
| `isConnected` | `boolean` | WebSocket connected |
| `isRunning` | `boolean` | Workflow executing |
| `isCompleted` | `boolean` | Workflow finished |
| `isPaused` | `boolean` | Workflow paused |
| `hasError` | `boolean` | Error occurred |

### 2. WorkflowStudio Component

**Purpose:** Main UI for designing and executing workflows.

**Enhanced Features:**
- Workflow execution control bar
- Real-time connection status
- Start workflow modal with requirement input
- Pause/cancel/refresh controls
- Phase status visualization
- Event logging integration

**Key Additions:**
```tsx
// Workflow control bar (lines 614-760)
- Connection status indicator (green pulse when connected)
- Workflow info display (ID, phase, progress)
- Dynamic control buttons (Start/Pause/Cancel/Refresh)

// Start workflow modal (lines 1205-1341)
- Requirement textarea
- Project name input
- Execution mode display
- Artifacts path preview

// Real-time event handling (lines 186-237)
- Maps backend events to frontend phases
- Updates phase status automatically
- Logs events to workflow log
```

### 3. ArtifactsTab Component

**Purpose:** Display phase artifacts with real-time updates.

**Enhanced Features:**
- Dual WebSocket support (async and legacy)
- Automatic fallback mechanism
- Real-time artifact detection
- Connection status indicator
- New artifacts flash indicator
- Phase name mapping

**WebSocket Integration:**
```tsx
// Tries async WebSocket first, falls back to legacy
const asyncWsUrl = `ws://localhost:8080/ws/workflow-async/${workflowId}`;
const legacyWsUrl = `ws://localhost:8080/ws/workflow/${workflowId}`;

// Listens for multiple event types:
// - artifacts_created (async workflow)
// - file_created (legacy)
// - phase_completed (may include artifacts)

// Auto-refreshes artifact list when detected
```

### 4. WorkflowProgressDashboard Component

**Purpose:** Comprehensive real-time progress visualization.

**Features:**
- Overall progress bar
- Connection status indicator
- Workflow control buttons
- Phase-by-phase breakdown with metrics
- Event timeline (last 10 events)
- Quality scores per phase
- Artifact counts
- Duration tracking

**Metrics Displayed:**
- Current phase name
- Phases completed (e.g., "3 / 5")
- Total events received
- Workflow status
- Per-phase duration, quality, and artifacts

---

## Event Flow

### Complete Event Sequence

```
1. USER ACTION: Click "Start Workflow" in WorkflowStudio
   ↓
2. FRONTEND: useWorkflowExecution.startWorkflow()
   → POST /api/workflow/execute
   ↓
3. BACKEND: workflow_api.py receives request
   → Creates workflow in Redis
   → Starts AsyncIO task
   → Returns workflow_id immediately
   ↓
4. ASYNC TASK: workflow_executor._execute_workflow_async()
   → Calls team_execution_v2_split_mode.execute_batch()
   ↓
5. WORKFLOW ENGINE: Executes phase-by-phase
   → Emits progress events via callback
   ↓
6. CALLBACK: workflow_executor._handle_progress_event()
   → Updates Redis state
   → Broadcasts via WebSocket
   ↓
7. WEBSOCKET: ws_manager.broadcast_to_workflow()
   → Sends to all connected clients
   ↓
8. FRONTEND: WebSocket.onmessage
   → Updates React state
   → UI refreshes automatically
   ↓
9. COMPLETION: workflow_completed event
   → Frontend shows success
   → Cleanup async task
```

### Event Types and Payloads

#### `workflow_started`
```json
{
  "type": "workflow_started",
  "workflow_id": "wf-123",
  "mode": "batch",
  "timestamp": "2025-10-09T10:30:00Z"
}
```

#### `phase_started`
```json
{
  "type": "phase_started",
  "workflow_id": "wf-123",
  "phase": "implementation",
  "execution_mode": "batch",
  "phases_completed": 2,
  "timestamp": "2025-10-09T10:35:00Z"
}
```

#### `blueprint_selected`
```json
{
  "type": "blueprint_selected",
  "workflow_id": "wf-123",
  "phase": "implementation",
  "blueprint": "parallel_team",
  "execution_mode": "parallel",
  "personas": ["Lead Developer", "Code Reviewer"],
  "timestamp": "2025-10-09T10:35:30Z"
}
```

#### `artifacts_created`
```json
{
  "type": "artifacts_created",
  "workflow_id": "wf-123",
  "phase": "implementation",
  "artifacts": ["main.py", "models.py", "routes.py"],
  "artifact_count": 3,
  "timestamp": "2025-10-09T10:40:00Z"
}
```

#### `quality_check`
```json
{
  "type": "quality_check",
  "workflow_id": "wf-123",
  "phase": "implementation",
  "quality_score": 0.85,
  "contract_fulfillment": 0.90,
  "threshold": 0.70,
  "passed": true,
  "timestamp": "2025-10-09T10:40:30Z"
}
```

#### `phase_completed`
```json
{
  "type": "phase_completed",
  "workflow_id": "wf-123",
  "phase": "implementation",
  "quality_score": 0.85,
  "quality_gate_passed": true,
  "artifacts": ["main.py", "models.py", "routes.py"],
  "duration_seconds": 120.5,
  "next_phase": "testing",
  "timestamp": "2025-10-09T10:42:00Z"
}
```

#### `workflow_completed`
```json
{
  "type": "workflow_completed",
  "workflow_id": "wf-123",
  "total_phases": 5,
  "completed_phases": 5,
  "total_duration": 450.2,
  "timestamp": "2025-10-09T11:00:00Z"
}
```

---

## Configuration

### Environment Variables

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6380
REDIS_DB=0

# Workflow Configuration
DEFAULT_QUALITY_THRESHOLD=0.70
WORKFLOW_TTL_DAYS=7
COMPLETED_WORKFLOW_TTL_HOURS=24

# WebSocket Configuration
WS_MAX_RECONNECT_ATTEMPTS=5
WS_RECONNECT_DELAY_MS=2000
WS_PING_TIMEOUT_MINUTES=30

# Status Polling (fallback)
STATUS_POLL_INTERVAL_MS=5000
```

### Docker Compose Setup

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: maestro-redis
    ports:
      - "6380:6379"
    command: redis-server --appendonly yes --maxmemory 256mb
    volumes:
      - redis-data:/data
    networks:
      - maestro-network

  workflow-api:
    build: ./maestro-engine-new
    container_name: maestro-workflow-api
    ports:
      - "8080:8080"
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
    networks:
      - maestro-network
```

---

## Testing

### Manual Testing Workflow

1. **Start Redis**:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d redis
   ```

2. **Start Workflow API**:
   ```bash
   cd maestro-engine-new
   python3.11 -m uvicorn src.api.workflow_api:app --reload --host 0.0.0.0 --port 8080
   ```

3. **Start Frontend**:
   ```bash
   cd maestro-frontend-new
   npm run dev
   ```

4. **Test Workflow Execution**:
   - Navigate to http://localhost:5173/workflow-studio
   - Click "Start Workflow"
   - Enter requirement: "Build a simple REST API"
   - Click "Start Workflow"
   - Watch real-time progress updates

### Testing WebSocket Connection

```bash
# Test WebSocket endpoint
wscat -c ws://localhost:8080/ws/workflow-async/test-workflow-id

# You should see:
{
  "type": "connection_established",
  "connection_id": "ws-1",
  "workflow_id": "test-workflow-id",
  "timestamp": "2025-10-09T10:00:00Z"
}
```

### Testing REST API

```bash
# Start workflow
curl -X POST http://localhost:8080/api/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "requirement": "Build a calculator",
    "mode": "batch",
    "project_name": "calculator"
  }'

# Get status
curl http://localhost:8080/api/workflow/wf-123/status

# List active workflows
curl http://localhost:8080/api/workflow/active

# Pause workflow
curl -X POST http://localhost:8080/api/workflow/wf-123/pause

# Cancel workflow
curl -X POST http://localhost:8080/api/workflow/wf-123/cancel
```

---

## Troubleshooting

### Common Issues

#### 1. WebSocket Connection Fails

**Symptoms:**
- "Disconnected" indicator in UI
- No real-time updates
- Console errors: "WebSocket failed"

**Solutions:**
- Check if workflow API is running on port 8080
- Verify Redis is running: `docker ps | grep redis`
- Check WebSocket endpoint: `wscat -c ws://localhost:8080/ws/workflow-async/test`
- Review browser console for CORS errors

#### 2. Workflow Stuck in "Starting" State

**Symptoms:**
- Status never changes from "starting"
- No phase progress
- No events received

**Solutions:**
- Check workflow API logs for errors
- Verify team_execution_v2_split_mode.py is accessible
- Check Redis connection: `redis-cli -p 6380 ping`
- Review AsyncIO task exceptions in logs

#### 3. Artifacts Not Showing

**Symptoms:**
- Workflow completes but no artifacts
- ArtifactsTab shows "No artifacts yet"

**Solutions:**
- Check deployment folder exists: `ls ~/projects/deployment`
- Verify project name matches in workflow and artifacts API
- Check file permissions on deployment folder
- Review artifact creation logs in workflow execution

#### 4. Progress Updates Delayed

**Symptoms:**
- Progress bar updates slowly
- Phase transitions not immediate

**Solutions:**
- Check WebSocket connection status
- Verify status polling is working (fallback)
- Check Redis persistence: `redis-cli -p 6380 KEYS workflow:*`
- Review network latency

### Debug Mode

Enable detailed logging:

```python
# In workflow_api.py
import logging
logging.basicConfig(level=logging.DEBUG)

# In useWorkflowExecution.ts
console.log('📨 WebSocket event:', eventData);
```

### Inspecting Redis State

```bash
# Connect to Redis
redis-cli -p 6380

# List all workflows
KEYS workflow:*

# Get workflow details
HGETALL workflow:wf-123

# Get phase details
HGETALL workflow:wf-123:phase:implementation

# List active workflows
SMEMBERS active_workflows

# Get WebSocket connections
SMEMBERS ws:connections:wf-123
```

---

## Performance Considerations

### Scalability

- **WebSocket Connections**: Current implementation supports ~1000 concurrent connections per server
- **Redis Memory**: Each workflow uses ~10KB, phases add ~5KB each
- **Async Tasks**: Python AsyncIO can handle ~10,000 concurrent tasks

### Optimization Tips

1. **Connection Pooling**: WebSocket manager already implements per-workflow pooling
2. **Message Queuing**: Offline messages limited to 100 per workflow
3. **TTL Management**: Automatic cleanup after 7 days (active) or 24 hours (completed)
4. **Status Polling**: Only used as fallback when WebSocket unavailable

### Load Testing

```bash
# Simulate 10 concurrent workflows
for i in {1..10}; do
  curl -X POST http://localhost:8080/api/workflow/execute \
    -H "Content-Type: application/json" \
    -d "{\"requirement\": \"Test $i\", \"mode\": \"batch\"}" &
done
```

---

## Future Enhancements

### Planned Features

1. **Multi-Project Support**: Run multiple projects concurrently
2. **Advanced Checkpointing**: Resume from any phase with edits
3. **Quality Dashboard**: Historical quality metrics visualization
4. **Team Collaboration**: Multiple users on same workflow
5. **Custom Blueprints**: User-defined team configurations
6. **Artifact Comparison**: Diff between checkpoint versions
7. **Scheduled Workflows**: Cron-based execution
8. **Workflow Templates**: Predefined requirements and configurations

### API Enhancements

- **GraphQL Support**: More flexible queries
- **Streaming SSE**: Alternative to WebSocket
- **Batch Operations**: Start/pause/cancel multiple workflows
- **Webhook Notifications**: External system integration

---

## Contributing

### Code Structure

```
maestro-engine-new/
├── src/
│   ├── api/
│   │   ├── workflow_api.py          # REST endpoints
│   │   └── workflow_executor.py     # Async orchestration
│   └── utils/
│       ├── redis_manager.py         # State persistence
│       └── websocket_manager.py     # Connection pooling

maestro-platform/maestro-hive/
└── team_execution_v2_split_mode.py  # Core workflow engine

maestro-frontend-new/src/
├── hooks/
│   └── useWorkflowExecution.ts      # React hook
├── components/
│   ├── WorkflowProgressDashboard.tsx
│   └── collaboration/
│       └── ArtifactsTab.tsx
└── pages/
    └── WorkflowStudio.tsx           # Main UI
```

### Adding New Event Types

1. **Backend** - Emit event in team_execution_v2_split_mode.py:
   ```python
   await self._emit_progress_event(progress_callback, {
       "type": "custom_event",
       "workflow_id": context.workflow.workflow_id,
       "data": {...}
   })
   ```

2. **Executor** - Handle in workflow_executor.py:
   ```python
   if event_type == "custom_event":
       await self.redis.update_workflow(workflow_id, {...})
       await self._broadcast_event(workflow_id, event)
   ```

3. **Frontend** - Listen in component:
   ```tsx
   useEffect(() => {
       if (lastEvent?.type === 'custom_event') {
           // Handle event
       }
   }, [events]);
   ```

---

## License

This async workflow system is part of the Maestro Platform and follows the same license terms.

## Support

For issues, questions, or contributions:
- GitHub Issues: [maestro-platform/issues](https://github.com/maestro-platform/issues)
- Documentation: See individual component README files
- Examples: Check `examples/` directory

---

**Last Updated:** October 2025
**Version:** 1.0.0
**Status:** ✅ Production Ready
