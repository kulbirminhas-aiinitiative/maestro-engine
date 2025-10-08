# RAG & MCP Integration Status Analysis

**Date**: 2025-10-03
**Status**: NOT CURRENTLY INTEGRATED
**Priority**: Medium (Future Enhancement)

---

## Executive Summary

**RAG (Retrieval-Augmented Generation)** and **MCP (Model Context Protocol)** features are **configured but NOT actively integrated** in the current MAESTRO v3.0 implementation.

**Key Findings**:
- ✅ RAG code exists (`src/rag/`, 928 lines) but is **not called** by the workflow engine
- ✅ MCP code has been **archived** (`src/archived/maestro_mcp_original/`, 496KB)
- ❌ API accepts `enable_rag` and `enable_mcp` parameters but **doesn't use them**
- ❌ Current implementation is **Schema v3.0 personas** with **no RAG/MCP integration**

---

## Current Architecture

### What's Actually Running

```
User Request
     ↓
BFF Service (unified_bff_service.py)
     ↓
Engine API (persona_workflow_api.py)
     ↓
Autonomous SDLC Engine V3 Resumable
     ↓
Claude Code SDK directly (no RAG, no MCP)
     ↓
11 Schema v3.0 Personas execute sequentially/parallel
     ↓
Files created in /tmp/maestro_projects
```

**No RAG**: Personas don't retrieve historical context
**No MCP**: No event streaming, no context protocol

---

## RAG (Retrieval-Augmented Generation) Status

### What Exists

**Location**: `/home/ec2-user/projects/maestro-engine/src/rag/`

**Files**:
1. `claude_rag_session.py` (370 lines)
   - HotClaudeRAGSession class
   - RAG-aware Claude instance with conversation history
   - Vector query tools
   - NOT USED in current workflow

2. `rag_tools.py` (~558 lines)
   - RAG query tools (search similar projects, find code examples, etc.)
   - Vector storage integration
   - NOT USED in current workflow

**Dependencies**:
- ChromaDB for vector storage
- Embedding models for semantic search

### What's Missing

**Integration Points**:
```python
# persona_workflow_api.py - ACCEPTS parameter
class PersonaWorkflowRequest(BaseModel):
    enable_rag: bool = Field(default=True, description="Enable RAG context")

# autonomous_sdlc_engine_v3_resumable.py - DOESN'T USE IT
# No mention of enable_rag anywhere in the engine code
```

**Status**: Parameters accepted but **not implemented**.

### How RAG SHOULD Work (Planned)

```
User: "Build a blog platform like WordPress"
     ↓
RAG Query: Search for similar projects in vector DB
     ↓
Retrieved Context: "Previous blog platform built 2 months ago"
                   "Common patterns: User auth, Post CRUD, Comments"
                   "Tech stack: React + Node.js worked well"
     ↓
Enhanced Prompt: "Build blog platform [WITH CONTEXT FROM SIMILAR PROJECTS]"
     ↓
Personas execute with learned knowledge
```

**Benefit**: Personas learn from past executions, avoid repeating mistakes.

### Why It's Not Integrated

1. **ChromaDB dependency removed** in Phase 5 cleanup
2. **No vector database** currently configured
3. **Engine doesn't call RAG tools** - would need refactoring
4. **Focus on core persona system first** - RAG is an enhancement

---

## MCP (Model Context Protocol) Status

### What Existed (Now Archived)

**Location**: `/home/ec2-user/projects/maestro-engine/src/archived/maestro_mcp_original/`

**Files Archived** (496KB, 9 files):
1. `enhanced_lean_ultimate_mega_team_utcp.py` (147KB)
2. `mcp_enhanced_lean_ultimate_mega_team.py` (102KB)
3. `mcp_cache_config.py` (85KB)
4. `hot_claude_live_backend_sdk.py` (63KB)
5. Plus 5 more files

**What MCP Did**:
- Event streaming during workflow execution
- Context caching and propagation between personas
- Real-time progress tracking via event emission
- UTCP (Universal Tool Calling Protocol) integration

### What Remains (Broken)

**Location**: `/home/ec2-user/projects/maestro-engine/src/bff/mcp_event_poller.py`

```python
# mcp_event_poller.py - TRIES to import archived module
from maestro_mcp.mcp_cache_config import get_mcp_cache  # ❌ IMPORT ERROR

class MCPEventPoller:
    """Polls MCP cache for workflow events"""
    # This class is BROKEN - module was archived
```

**Status**: Event poller exists but **cannot function** (imports archived code).

### What's Missing

**Integration Points**:
```python
# persona_workflow_api.py - ACCEPTS parameters
class PersonaWorkflowRequest(BaseModel):
    enable_mcp: bool = Field(default=True, description="Enable MCP event emission")
    mcp_context: Optional[Dict] = Field(None, description="MCP context from previous session")

# autonomous_sdlc_engine_v3_resumable.py - DOESN'T USE THEM
# No mention of enable_mcp or mcp_context anywhere
```

**Status**: Parameters accepted but **not implemented**.

### How MCP SHOULD Work (Planned)

```
Workflow Start
     ↓
MCP Event: {"type": "workflow_start", "session": "123"}
     ↓
Frontend receives via WebSocket → Shows "Started"
     ↓
Persona 1 starts
     ↓
MCP Event: {"type": "persona_start", "persona": "requirement_analyst"}
     ↓
Frontend updates → "Requirement Analyst working..."
     ↓
File created
     ↓
MCP Event: {"type": "file_created", "file": "requirements.md"}
     ↓
Frontend shows → "Created requirements.md"
     ↓
Continue for all events...
```

**Benefit**: Real-time progress tracking, better UX, event-driven architecture.

### Why It's Not Integrated

1. **Old MCP code archived** in Phase 5 cleanup
2. **Autonomous engine doesn't emit events** - uses simpler session management
3. **WebSocket already works** via Redis state updates
4. **MCP adds complexity** without clear benefit over current approach

---

## Configuration vs Reality

### Configuration Claims

**.env file**:
```bash
# MCP/UTCP
ENABLE_MCP=true
MCP_CACHE_DIR=/tmp/mcp_cache
MCP_CACHE_TTL=3600

# RAG Service
RAG_ENABLED=false
RAG_SERVICE_URL=http://localhost:9803
CHROMA_PERSIST_DIR=./chroma_db
RAG_EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### Reality Check

```python
# settings.py - Configuration exists
enable_mcp: bool = Field(default=True)
rag_enabled: bool = Field(default=False)

# autonomous_sdlc_engine_v3_resumable.py - NOT USED
# Engine never references settings.enable_mcp
# Engine never references settings.rag_enabled
# Engine doesn't call RAG tools
# Engine doesn't emit MCP events
```

**Conclusion**: Configuration is **future-proofing** but features are **not implemented**.

---

## What Actually Works (Without RAG/MCP)

### Current Workflow

1. **User submits requirement** via API
2. **BFF forwards to Engine**
3. **Engine selects personas** (from workflow config)
4. **Session Manager** tracks state in memory
5. **Each persona executes** using Claude Code SDK
6. **Files created** in project directory
7. **Results returned** to BFF
8. **WebSocket updates** sent via Redis state changes

**No RAG**: Personas start fresh each time (no historical context)
**No MCP**: No event streaming (state tracked in Redis instead)

### Why This Works

- ✅ **Simpler architecture** - fewer moving parts
- ✅ **Session persistence** - via SessionManager, not MCP
- ✅ **Real-time updates** - via Redis + WebSocket, not MCP events
- ✅ **Context propagation** - via file outputs, not RAG queries

**Trade-off**: Less sophisticated but more reliable.

---

## Integration Paths (Future)

### Path 1: RAG Integration (Recommended First)

**Priority**: Medium
**Complexity**: Medium
**Value**: High (personas learn from past projects)

**Implementation**:
1. Add ChromaDB back as optional dependency
2. Create RAG service (separate microservice)
3. Integrate in `autonomous_sdlc_engine_v3_resumable.py`:
   ```python
   async def execute_persona(self, persona_id, requirement):
       # NEW: Query RAG for context
       if settings.rag_enabled:
           context = await rag_service.query_similar_projects(requirement)
           requirement = f"{requirement}\n\nContext: {context}"

       # Existing: Execute persona
       result = await claude_sdk.query(requirement, ...)
   ```
4. Index completed projects in vector DB
5. Test retrieval quality

**Benefit**: Personas get smarter over time.

### Path 2: MCP Event Streaming (Lower Priority)

**Priority**: Low
**Complexity**: High
**Value**: Medium (better UX but current approach works)

**Implementation**:
1. Create new MCP event bus (not the old 496KB implementation)
2. Integrate in `autonomous_sdlc_engine_v3_resumable.py`:
   ```python
   async def execute_persona(self, persona_id, requirement):
       # Emit start event
       await mcp_bus.emit("persona_start", {"persona": persona_id})

       # Execute
       result = await claude_sdk.query(...)

       # Emit complete event
       await mcp_bus.emit("persona_complete", {"persona": persona_id})
   ```
3. BFF subscribes to events
4. Forward to frontend via WebSocket

**Benefit**: Finer-grained progress tracking.

**Alternative**: Current Redis state updates are sufficient.

### Path 3: Hybrid Approach (Recommended)

**Priority**: Medium
**Complexity**: Medium

**Phase 1**: RAG integration only
- Add RAG queries to enhance persona prompts
- Index completed projects
- Measure quality improvement

**Phase 2**: Lightweight event tracking
- Add simple event logging (not full MCP)
- Store in Redis alongside state
- Frontend polls for events

**Phase 3**: Full MCP (if needed)
- Only if event-driven architecture proves valuable
- Build lightweight, not the old 496KB implementation

---

## Recommendations

### Immediate (Phase 5/6)

1. **Clean up misleading API parameters**:
   ```python
   # persona_workflow_api.py
   class PersonaWorkflowRequest(BaseModel):
       # REMOVE these unused parameters or mark as deprecated
       enable_mcp: bool = Field(default=False, deprecated=True)
       enable_rag: bool = Field(default=False, deprecated=True)
   ```

2. **Update documentation** to clarify:
   - RAG: Not integrated (future feature)
   - MCP: Not integrated (alternative approach used)

3. **Fix broken MCP event poller**:
   - Either remove it or create stub implementation
   - Currently imports archived module (broken)

### Future (Phase 6+)

1. **RAG Integration** (if value proven):
   - Set up ChromaDB or similar
   - Create RAG query service
   - Integrate into engine prompts
   - Measure quality improvements

2. **Event Tracking** (if UX needs it):
   - Add simple event logging
   - Store in Redis
   - Frontend polls for updates
   - Don't rebuild 496KB MCP system

3. **Keep It Simple**:
   - Current approach works
   - Only add complexity if proven value
   - Measure before building

---

## Testing Current System (Without RAG/MCP)

### Verify What Works

```bash
# 1. Start services
curl http://localhost:5000/health
curl http://localhost:4001/health

# 2. Execute workflow (no RAG, no MCP)
curl -X POST http://localhost:5000/api/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "requirement": "Build a TODO app",
    "session_id": "test_no_rag_mcp",
    "enable_rag": false,
    "enable_mcp": false
  }'

# 3. Check results (same as enable=true because not integrated)
ls /tmp/maestro_projects/guardian_test_no_rag_mcp/
```

**Result**: Works identically regardless of enable_rag/enable_mcp values (they're ignored).

---

## Conclusion

### Current State Summary

| Feature | Status | Location | Working? | Priority to Fix |
|---------|--------|----------|----------|-----------------|
| **RAG Code** | Exists | `src/rag/` | ❌ Not called | Medium |
| **RAG Integration** | Not integrated | - | ❌ No | Medium |
| **MCP Code** | Archived | `src/archived/maestro_mcp_original/` | ❌ Archived | Low |
| **MCP Event Poller** | Broken | `src/bff/mcp_event_poller.py` | ❌ Imports archived code | Low |
| **MCP Integration** | Not integrated | - | ❌ No | Low |
| **Current Workflow** | Simple, direct | `autonomous_sdlc_engine_v3_resumable.py` | ✅ Works great | - |
| **Session Management** | Redis-based | `SessionManager` | ✅ Works | - |
| **Real-time Updates** | WebSocket + Redis | `unified_bff_service.py` | ✅ Works | - |

### Bottom Line

**What the user asked**: "How are RAG and MCP being leveraged by backend scripts?"

**Answer**: They're **not**. The API accepts the parameters for future compatibility, but the backend engine doesn't use them. The current implementation is simpler and more reliable without these features.

**Should you integrate them?**
- **RAG**: Maybe - could improve persona quality by learning from past projects
- **MCP**: Probably not - current Redis/WebSocket approach works fine

**Next steps**:
1. Clean up misleading API parameters
2. Fix or remove broken MCP event poller
3. Document actual architecture clearly
4. Consider RAG integration if needed (Phase 6+)

---

**Created**: 2025-10-03
**Author**: Configuration System Review
**Status**: Analysis Complete
