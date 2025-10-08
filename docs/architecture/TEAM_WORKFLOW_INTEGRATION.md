# CRITICAL CORRECTION: Team Workflow Integration

**Date**: 2025-10-03
**Status**: IN PROGRESS - Correcting Approach

---

## ❌ What I Built (Incorrect)

I created a simple `PersonaOrchestrator` from scratch that:
- ✅ Uses Schema v3.0 personas
- ✅ Has dependency resolution
- ❌ **LOSES critical team workflow features**
- ❌ **LOSES DAG-based execution**
- ❌ **LOSES hierarchical team organization**
- ❌ **LOSES parallel execution capabilities**
- ❌ **LOSES session resume features**

## ✅ What We Should Use (Correct)

The existing **autonomous_sdlc_engine_v3_resumable.py** from shared/claude_team_sdk:

### Critical Features in Existing System:

1. **Session Management**
   - Resume workflows across multiple sessions
   - Incremental execution
   - Session persistence
   - Context propagation

2. **DAG Workflows** (`workflow/dag.py`)
   - Task dependencies
   - Parallel execution
   - Phase-based structure
   - Execution optimization

3. **Team Organization** (`team_organization.py`)
   - Phase structure (Requirements → Design → Implementation → Testing → Deployment)
   - Collaboration patterns
   - Decision authority
   - Escalation paths
   - Communication channels

4. **Multiple Execution Modes**
   - Sequential execution
   - Hierarchical execution
   - Parallel execution where possible
   - Phase-based execution

5. **Workflow Templates** (`sdlc_workflow.py`)
   - Feature development workflow
   - Bug fix workflow
   - Hotfix workflow
   - Custom workflows with DAG

## 🔧 Correct Integration Approach

### Step 1: Integrate Personas with Autonomous Engine

Instead of replacing, we update `autonomous_sdlc_engine_v3_resumable.py` to use new personas:

```python
# OLD (in shared/claude_team_sdk):
from personas import SDLCPersonas

# NEW (integrate Schema v3.0):
from maestro_engine.personas import MaestroPersonasCompat as SDLCPersonas
```

That's it! The adapter makes Schema v3.0 personas compatible.

### Step 2: Preserve ALL Existing Features

- ✅ Keep DAG workflow system
- ✅ Keep team organization structure
- ✅ Keep session management
- ✅ Keep parallel execution
- ✅ Keep hierarchical modes
- ✅ Keep workflow templates

### Step 3: Add to MAESTRO Engine

Copy autonomous engine to maestro-engine and enhance:

1. **Keep**: All existing workflow logic
2. **Add**: FastAPI wrapper for BFF to call
3. **Add**: WebSocket progress updates
4. **Add**: Redis state integration

## 📋 Correct File Structure

```
maestro-engine/
├── src/
│   ├── personas/
│   │   ├── definitions/              # ✅ Schema v3.0 personas
│   │   ├── models.py
│   │   ├── registry.py
│   │   └── adapter.py                # ✅ Makes personas compatible
│   │
│   ├── workflow/                     # ✨ COPY from shared/claude_team_sdk
│   │   ├── dag.py                    # DAG workflow system
│   │   ├── workflow_engine.py        # Workflow execution
│   │   └── workflow_templates.py     # Pre-built workflows
│   │
│   ├── orchestration/
│   │   ├── autonomous_engine.py      # ✨ COPY & UPDATE from shared
│   │   ├── team_organization.py      # ✨ COPY from shared
│   │   └── session_manager.py        # ✨ COPY from shared
│   │
│   └── api/
│       └── workflow_api.py           # FastAPI wrapper for autonomous engine
```

## 🎯 What Needs to be Done

1. ✅ Schema v3.0 personas created
2. ✅ Adapter for backward compatibility
3. ❌ **Copy DAG workflow system** from shared/claude_team_sdk
4. ❌ **Copy autonomous engine** from shared/claude_team_sdk
5. ❌ **Copy team organization** from shared/claude_team_sdk
6. ❌ **Update autonomous engine** to use new personas via adapter
7. ❌ **Create FastAPI wrapper** for BFF integration
8. ❌ **Test all workflow modes** (sequential, hierarchical, parallel)

## 🚀 Execution Modes We Must Support

### Mode 1: Sequential Execution
```bash
# Run personas one by one
python autonomous_engine.py requirement_analyst solution_architect frontend_developer
```

### Mode 2: Hierarchical Execution
```bash
# Run by phases with proper dependencies
python autonomous_engine.py --mode hierarchical --phases requirements,design,implementation
```

### Mode 3: Parallel Execution
```bash
# Run independent personas in parallel
python autonomous_engine.py --mode parallel frontend_developer backend_developer
```

### Mode 4: DAG Workflow
```bash
# Use pre-defined workflow template
python autonomous_engine.py --workflow feature_development --feature "User Authentication"
```

### Mode 5: Resume Session
```bash
# Resume from where you left off
python autonomous_engine.py --resume session_123 --all-remaining
```

## 📊 Features Matrix

| Feature | Custom Orchestrator | Autonomous Engine |
|---------|-------------------|-------------------|
| Schema v3.0 Personas | ✅ | ✅ (via adapter) |
| Dependency Resolution | ✅ | ✅ |
| Session Management | ❌ | ✅ |
| Resume Capability | ❌ | ✅ |
| DAG Workflows | ❌ | ✅ |
| Parallel Execution | ❌ | ✅ |
| Hierarchical Mode | ❌ | ✅ |
| Team Organization | ❌ | ✅ |
| Workflow Templates | ❌ | ✅ |
| Phase Structure | ❌ | ✅ |
| Collaboration Patterns | ❌ | ✅ |

**Winner**: Autonomous Engine ✅

## 🔄 Next Steps (Corrected)

1. **Copy workflow module** from shared/claude_team_sdk to maestro-engine
2. **Copy autonomous engine** from shared/claude_team_sdk to maestro-engine
3. **Update imports** to use Schema v3.0 personas via adapter
4. **Create FastAPI wrapper** that preserves all execution modes
5. **Test all modes**: sequential, hierarchical, parallel, DAG, resume
6. **Update BFF** to call the autonomous engine API
7. **Document** all workflow modes and features

---

## 🎯 Correct Architecture

```
Frontend (4200)
    ↓ WebSocket
BFF (4001)
    ↓ HTTP POST /api/workflow/execute
MAESTRO Engine API (5000)
    ↓
Autonomous SDLC Engine V3 ← Uses Schema v3.0 via adapter
    ↓
DAG Workflow Engine
    ↓
Team Organization (Phases, Collaboration)
    ↓
11 Schema v3.0 Personas
```

---

**Status**: Correcting approach - will preserve all team workflow features
**Priority**: CRITICAL - Do NOT lose DAG/hierarchical/parallel execution
