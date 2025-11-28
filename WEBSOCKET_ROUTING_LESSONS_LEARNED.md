# WebSocket Routing Lessons Learned - API Gateway

**Date**: 2025-10-18
**Issue**: Frontend workflow execution failing due to routing issues
**Root Causes**: Multiple configuration and code issues in gateway routing

---

## Problem Summary

Frontend was unable to execute workflows through the API gateway due to:
1. Frontend configured to bypass gateway (direct port 5001 connection)
2. Gateway WebSocket path construction logic was broken
3. Gateway HTTP route configuration missing full backend paths
4. Backend server hung from stuck curl connections

---

## Issues Found & Fixed

### 1. Frontend API Configuration ❌→✅

**File**: `/frontend/src/config/api.ts`

**Problem**:
```typescript
// WRONG - Direct connection bypassing gateway
WORKFLOW_API: typeof window !== 'undefined'
  ? `${window.location.protocol}//${window.location.hostname}:5001`
  : 'http://localhost:5001',
```

**Fix**:
```typescript
// CORRECT - Route through gateway
WORKFLOW_API: `${GATEWAY_BASE}/api/workflow`,
WORKFLOW_WS: `${GATEWAY_WS}/workflow`,
```

**Lesson**: Always route through the gateway! Direct backend connections break:
- Load balancing
- Rate limiting
- Authentication middleware
- Logging/monitoring
- Circuit breaking

---

### 2. Gateway WebSocket Path Construction ❌→✅

**File**: `/src/gateway/routing/proxy.py`

**First Attempt (WRONG)**:
```python
# Oversimplified - creates DOUBLE /ws/ prefix
target_url = f"{backend_ws}/ws/{path}"
# Result: ws://host:5001/ws/workflow/ws/workflow/workflow-123 ❌
```

**Second Attempt (CORRECT)**:
```python
# Parse route config to extract suffix
route_path = route_config["path"].rstrip("/*")  # "/ws/workflow"
route_suffix = route_path.split("/ws/")[-1]  # "workflow"

# Strip route suffix from incoming path
remaining_path = path
if route_suffix and path.startswith(route_suffix):
    remaining_path = path[len(route_suffix):].lstrip("/")  # "workflow-123"

# Backend URL already has full path, just append resource ID
target_url = f"{backend_ws}/{remaining_path}"
# Result: ws://host:5001/ws/workflow/workflow-123 ✅
```

**Lesson**: WebSocket path routing is TRICKY! Must account for:
- Backend URL may already include the full path
- Gateway receives path WITHOUT `/ws/` prefix
- Need to strip route prefix before appending to backend URL
- Always log the constructed URL for debugging

---

### 3. Gateway HTTP Route Configuration ❌→✅

**File**: `/config/gateway_routes.yaml`

**Problem**:
```yaml
# WRONG - Missing backend path, causes 404
- path: /api/workflow/*
  backend: http://host.docker.internal:5001
  # Gateway strips /api/workflow and sends to /execute
  # Backend receives: POST /execute (404!)
```

**Fix**:
```yaml
# CORRECT - Include full backend path
- path: /api/workflow/*
  backend: http://host.docker.internal:5001/api/workflow
  # Gateway strips /api/workflow prefix
  # Reconstructs: POST /api/workflow/execute ✅
```

**Lesson**: Backend URL in gateway config should include the FULL PATH that the backend expects, similar to how the auth service is configured:
```yaml
- path: /api/v1/auth/*
  backend: ${AUTH_SERVICE_URL:http://host.docker.internal:3100/api/v1/auth}
```

---

### 4. HTTP Client Timeout ❌→✅

**File**: `/src/gateway/main.py`

**Problem**:
```python
# Too short for workflow initialization
httpx.AsyncClient(timeout=httpx.Timeout(30.0))
```

**Fix**:
```python
# Increased for workflow engine initialization
httpx.AsyncClient(timeout=httpx.Timeout(60.0))
```

**Lesson**: Different backends have different latency characteristics:
- Workflow execution: 30-60s for initialization
- Database queries: 5-10s
- File operations: 1-5s
- Configure timeouts based on backend SLAs

---

### 5. Backend Server Stuck Connections

**Problem**:
- Multiple hanging curl connections from testing
- Server unable to accept new connections
- Process appeared running but unresponsive

**Fix**:
```bash
# Kill hung process
kill -9 1340129

# Restart fresh
env POSTGRES_PASSWORD=maestro_dev python3 dag_api_server_robust.py
```

**Lesson**: During development/testing:
- Use `timeout` with curl commands
- Monitor active connections: `lsof -p <PID> | grep TCP`
- Implement connection limits in backend
- Add request timeouts in backend
- Use health check endpoints to verify responsiveness

---

## Correct Architecture

```
Frontend (port 4300)
    ↓
API Gateway (port 8080) ← SINGLE ENTRY POINT
    ↓ (routes /api/workflow/*)
    ↓
Workflow API Server (port 5001)
    ↓
PostgreSQL (port 5432)
```

**WebSocket Flow**:
```
Frontend: ws://hostname:8080/ws/workflow/workflow-123
    ↓
Gateway: Receives "workflow/workflow-123" (no /ws/ prefix)
    ↓
Gateway: Routes to ws://host.docker.internal:5001/ws/workflow
    ↓
Gateway: Strips "workflow" prefix → "workflow-123"
    ↓
Gateway: Constructs ws://host.docker.internal:5001/ws/workflow/workflow-123
    ↓
Backend: Accepts WebSocket connection
```

---

## Testing Checklist

### HTTP Endpoint
```bash
curl -X POST http://localhost:8080/api/workflow/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "workflow_id": "test-123",
    "workflow_name": "Test",
    "nodes": [...],
    "edges": []
  }'
```

Expected:
- ✅ Status 200/201
- ✅ Returns execution_id
- ✅ Gateway logs show routing to backend
- ✅ Backend logs show request received

### WebSocket Connection
```javascript
const ws = new WebSocket('ws://localhost:8080/ws/workflow/workflow-123');
ws.onopen = () => console.log('Connected');
ws.onmessage = (event) => console.log('Message:', event.data);
```

Expected:
- ✅ Connection established
- ✅ Gateway logs show WebSocket upgrade
- ✅ Backend accepts connection
- ✅ Real-time messages received

---

## Key Takeaways

1. **Always use the gateway** - Don't bypass it even during development
2. **Path construction is subtle** - Log URLs, test thoroughly
3. **Backend URLs need full paths** - Include the path prefix in config
4. **WebSocket routing is different** - Can't just append paths blindly
5. **Monitor connections** - Watch for hangs, implement timeouts
6. **Restart is OK** - Better to restart than debug stuck state
7. **Test incrementally** - Test HTTP before WebSocket
8. **Document as you go** - Future you will thank present you

---

## Files Modified

1. `/frontend/src/config/api.ts` - Fixed to use gateway
2. `/config/gateway_routes.yaml` - Added full backend paths
3. `/src/gateway/routing/proxy.py` - Fixed WebSocket path construction
4. `/src/gateway/main.py` - Increased HTTP timeout to 60s

---

## Related Documents

- Gateway Routes Config: `/config/gateway_routes.yaml`
- Gateway Proxy Logic: `/src/gateway/routing/proxy.py`
- Frontend API Config: `/frontend/src/config/api.ts`
- Integration Test: `/tmp/test_workflow_via_gateway.sh`

---

**Status**: ✅ All issues resolved, ready for E2E testing
