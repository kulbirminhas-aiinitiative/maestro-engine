# 🤖 Multi-Agent Collaboration BFF Service

**Location:** `/home/ec2-user/projects/maestro-engine-new/src/bff/collaboration_service.py`
**Port:** 4002
**Container:** maestro-collaboration-bff

## 🚀 Quick Start

### Deploy Service
```bash
cd /home/ec2-user/projects/maestro-engine-new
./deploy-collaboration.sh
```

### Stop Service
```bash
docker-compose -f docker-compose.dev.yml stop collaboration-bff
```

### View Logs
```bash
docker logs -f maestro-collaboration-bff
```

## 📡 Service Endpoints

- **Health:** `http://localhost:4002/health`
- **WebSocket:** `ws://localhost:4002/ws/collaboration/{room_id}`

## 🤖 AI Agents

| Agent | Role | Avatar | Color |
|-------|------|--------|-------|
| Stephen | Requirements Analyst | 📋 | Blue |
| Andy | Solution Architect | 🏗️ | Purple |
| Sarah | UX Designer | 🎨 | Pink |
| Marcus | Backend Developer | ⚙️ | Orange |
| Emma | Frontend Developer | 💻 | Green |
| Maestro | Code Synthesis | 🤖 | Indigo |

## 💬 Usage

### Access from Frontend
```
http://localhost:4200  →  Click "💬 Collaboration" tab
```

### Test with WebSocket
```javascript
const ws = new WebSocket('ws://localhost:4002/ws/collaboration/test_room');

// Send message
ws.send(JSON.stringify({
  type: 'user_message',
  roomId: 'test_room',
  sender: { id: 'user1', name: 'User', type: 'human' },
  content: '@Stephen what requirements do we need?',
  mentions: ['stephen'],
  timestamp: new Date().toISOString()
}));
```

## 🏗️ Architecture

```
maestro-engine-new/
├── src/bff/
│   ├── collaboration_service.py    # Main service (932 lines)
│   ├── main.py                     # Unified BFF (port 4001)
│   └── ...
├── Dockerfile.collaboration        # Docker build file
├── docker-compose.dev.yml          # Service configuration
└── deploy-collaboration.sh         # Deployment script
```

## 🔧 Configuration

**docker-compose.dev.yml:**
```yaml
collaboration-bff:
  build:
    context: ../
    dockerfile: maestro-engine-new/Dockerfile.collaboration
  container_name: maestro-collaboration-bff
  ports:
    - "4002:4002"
  environment:
    - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
```

## 📊 Frontend Integration

**Already configured in:** `maestro-frontend-new/src/config/api.ts`
```typescript
COLLABORATION_BFF: 'http://localhost:4002/api/collaboration',
COLLABORATION_WS: 'ws://localhost:4002/ws/collaboration',
```

## ✅ Health Check

```bash
curl http://localhost:4002/health

# Expected response:
{
  "status": "healthy",
  "service": "collaboration-bff",
  "timestamp": "2025-10-09T...",
  "claude_sdk": false,
  "active_rooms": 0
}
```

## 🎯 Features

- ✅ Real-time WebSocket communication
- ✅ 6 AI agent personas with unique expertise
- ✅ @mention routing to specific agents
- ✅ @Maestro code synthesis and preview generation
- ✅ Typing indicators
- ✅ Room-based state management
- ✅ Auto-reconnection
- ✅ Claude Code SDK integration (optional)
- ✅ Simulated responses (fallback)

## 📝 Full Documentation

- **Implementation Guide:** `/home/ec2-user/projects/maestro-frontend-new/MULTI_AGENT_COLLABORATION_COMPLETE.md`
- **Quick Start:** `/home/ec2-user/projects/maestro-v2/QUICK_START_COLLABORATION.md` (legacy)

## 🐛 Troubleshooting

### Service won't start
```bash
# Check container logs
docker logs maestro-collaboration-bff

# Restart service
docker-compose -f docker-compose.dev.yml restart collaboration-bff
```

### Port already in use
```bash
# Check what's using port 4002
lsof -i :4002

# Stop the conflicting process
kill -9 <PID>
```

### Frontend can't connect
1. Verify service is running: `curl http://localhost:4002/health`
2. Check browser console for WebSocket errors
3. Ensure frontend config points to port 4002

## 🔄 Integration with Existing Services

The collaboration BFF runs alongside other maestro-engine services:

- **Port 4001:** Unified BFF (Accelerator/Guardian)
- **Port 4002:** Collaboration BFF (Multi-Agent Chat)
- **Port 8002:** Coordinator
- **Port 8004:** Orchestration
- **Port 8080:** API Gateway

All services share the `maestro-dev-network` Docker network.

---

**Status:** ✅ Production Ready
**Last Updated:** 2025-10-09
