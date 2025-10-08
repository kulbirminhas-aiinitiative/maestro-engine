# MAESTRO Phase 2 - Quick Start Guide

## 🚀 Start All Services

### Step 1: Start MAESTRO Engine (Port 5000)

```bash
cd /home/ec2-user/projects/maestro-engine
python3.11 src/maestro_engine_app.py
```

**Verify:**
```bash
curl http://localhost:5000/api/workflow/health
# Should return: {"status": "healthy", "persona_system": {...}}
```

### Step 2: Start Unified BFF (Port 4001)

```bash
cd /home/ec2-user/projects/maestro-engine/src/bff
python3.11 unified_bff_service.py
```

**Verify:**
```bash
curl http://localhost:4001/health
# Should return: {"status": "healthy", "service": "maestro-unified-bff"}
```

### Step 3: Start Frontend (Port 4200)

```bash
cd /home/ec2-user/projects/maestro-frontend
npm run dev
```

**Access:**
- Frontend: http://localhost:4200
- BFF Docs: http://localhost:4001/docs
- Engine Docs: http://localhost:5000/docs

## 🧪 Quick Tests

### Test 1: List Personas
```bash
curl http://localhost:5000/api/workflow/personas | jq '.total'
# Should return: 11
```

### Test 2: Get Execution Order
```bash
curl -X POST http://localhost:5000/api/workflow/execution-order \
  -H "Content-Type: application/json" \
  -d '["frontend_developer", "requirement_analyst"]' | jq '.ordered'
# Should return: ["requirement_analyst", "frontend_developer"]
```

### Test 3: Run Mock Workflow
```bash
curl -X POST http://localhost:5000/api/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "requirement": "Build a simple task list",
    "session_id": "test_123",
    "persona_ids": ["requirement_analyst"]
  }' | jq '.success'
# Should return: true
```

## 📊 Architecture Overview

```
Frontend (4200) → BFF (4001) → Engine (5000) → Personas (Schema v3.0)
```

## 🎯 What You Can Do Now

1. **Chat with Accelerator Mode** - Frontend sends prompts to BFF
2. **Trigger Guardian Workflow** - Full SDLC execution with 11 personas
3. **View Live Progress** - WebSocket updates during execution
4. **Browse Generated Files** - File explorer shows artifacts
5. **Resume Sessions** - Continue from where you left off

## 📚 Documentation

- **Phase 1**: `INTEGRATION_COMPLETE.md` - Persona system
- **Phase 2**: `PHASE_2_INTEGRATION_COMPLETE.md` - Frontend integration
- **Quick Reference**: `README_PERSONAS.md` - Usage examples
- **Integration Guide**: `PERSONA_INTEGRATION_GUIDE.md` - Detailed docs

## 🔧 Troubleshooting

**Port already in use:**
```bash
# Check what's using the port
lsof -ti:5000
# Kill the process
kill -9 $(lsof -ti:5000)
```

**Personas not loading:**
```bash
cd /home/ec2-user/projects/maestro-engine
python3.11 test_persona_system.py
# Should show: ✅ Loaded 11 persona(s)
```

**Integration tests failing:**
```bash
python3.11 test_integration_with_executor.py
# Should show: Results: 5/5 tests passed
```

## 🎊 Success Indicators

✅ All 3 services running
✅ Health checks passing
✅ 11 personas available
✅ Frontend loads without errors
✅ Can trigger workflows

---

**Status**: Ready for testing with mock execution
**Next**: Enable real Claude Code SDK execution for production
