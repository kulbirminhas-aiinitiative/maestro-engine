# MAESTRO Engine - Current Architecture

**Last Updated:** 2025-10-16
**Version:** 3.0.0
**Status:** Production Ready

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Service Topology](#service-topology)
3. [Service Details](#service-details)
4. [Data Flow](#data-flow)
5. [Persona System](#persona-system)
6. [Integration Points](#integration-points)
7. [Deployment Architecture](#deployment-architecture)
8. [Known Issues](#known-issues)

---

## System Overview

MAESTRO Engine is a microservices-based AI-powered SDLC automation platform consisting of **9 core services** orchestrated through Docker Compose.

### Architecture Principles

- **API Gateway Pattern (ADR-003):** Single entry point for all external requests
- **Service Discovery:** Internal service mesh with Docker networking
- **State Management:** Redis for session state and caching
- **Event-Driven:** WebSocket-based real-time updates
- **Frontend-Agnostic:** Standard REST + WebSocket API contract

---

## Service Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                          │
│                      (Any HTTP/WS client)                       │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway (8080)                          │
│              Routes, CORS, Rate Limiting, Auth                   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
         ▼                ▼                ▼
┌─────────────────┐ ┌──────────┐ ┌──────────────────┐
│ BFF Layer       │ │ Core     │ │ Support Services │
├─────────────────┤ │ Services │ ├──────────────────┤
│ • BFF (4001)    │ │ • Coord  │ │ • MCP (9800)     │
│ • Collab (4002) │ │   (8002) │ │ • RAG (9803)     │
└─────────────────┘ │ • Orch   │ │ • Quality (8000) │
                    │   (8004) │ │ • Redis (6380)   │
                    └──────────┘ └──────────────────┘
```

### Service Count: 9 Services

| Layer | Service | Port | Status |
|-------|---------|------|--------|
| **Gateway** | API Gateway | 8080 | ✅ Healthy |
| **Core** | Coordinator | 8002 | ✅ Healthy |
| **Core** | Orchestration | 8004 | ✅ Healthy |
| **BFF** | Unified BFF | 4001 | ✅ Healthy |
| **BFF** | Collaboration BFF | 4002 | ✅ Healthy |
| **Support** | MCP Service | 9800 | ✅ Healthy |
| **Support** | RAG Service | 9803 | ✅ Healthy |
| **Support** | Quality Fabric | 8000 | ✅ Healthy |
| **State** | Redis | 6380 | ✅ Healthy |

---

## Service Details

### 1. API Gateway (Port 8080)

**Container:** `maestro-gateway`
**Purpose:** Single entry point for all API requests
**Technology:** FastAPI + Python 3.11

**Responsibilities:**
- Route management (17 configured routes)
- CORS handling
- Rate limiting (per route)
- Request/response logging
- Health check aggregation

**Key Routes:**
- `/api/v1/accelerator/*` → BFF (4001)
- `/api/v1/guardian/*` → Maestro Engine (5000) [external]
- `/api/v1/templates/*` → Template Service (9600) [external]
- `/api/v1/rag/*` → RAG Service (9803)
- `/api/v1/mcp/*` → MCP Service (9800)
- `/api/v1/quality/*` → Quality Fabric (8000)
- `/api/v1/coordinator/*` → Coordinator (8002)
- `/api/v1/orchestration/*` → Orchestration (8004)
- `/api/workflow/*` → Workflow API (5001) [external]
- `/api/collaboration/*` → Collaboration BFF (4002)
- `/ws/*` → WebSocket routes

**Configuration:** `config/gateway_routes.yaml`

**Known Issues:**
- ⚠️ Auth route references non-existent service on port 3100 (causes 502 errors)

---

### 2. Coordinator Service (Port 8002)

**Container:** `maestro-coordinator`
**Purpose:** Service coordination and orchestration gateway
**Technology:** FastAPI + Python 3.11

**Responsibilities:**
- Service health monitoring
- Inter-service communication coordination
- Request orchestration
- API gateway for internal services

**Dependencies:**
- MCP Service (9800)
- Orchestration Service (8004)
- RAG Service (9803)

**Environment Variables:**
- `ANTHROPIC_API_KEY` - Claude API access
- `MAESTRO_MCP_SERVICE_URL`
- `MAESTRO_ORCHESTRATION_SERVICE_URL`
- `MAESTRO_RAG_SERVICE_URL`

---

### 3. Orchestration Service (Port 8004)

**Container:** `maestro-orchestration`
**Purpose:** Workflow orchestration and execution
**Technology:** FastAPI + Python 3.11

**Responsibilities:**
- Workflow DAG execution
- Phase management
- Persona coordination
- Context propagation

**Dependencies:**
- MCP Service (9800) - Context caching

**Key Features:**
- Sequential, parallel, and hierarchical execution modes
- Checkpoint/resume capability
- Quality gate validation

---

### 4. MCP Service (Port 9800)

**Container:** `maestro-mcp`
**Purpose:** Model Context Protocol - Claude session caching
**Technology:** FastAPI + Python 3.11

**Responsibilities:**
- Hot Claude session management
- Context caching (TTL: 3600s)
- Session state persistence
- Event streaming

**Storage:**
- Cache directory: `/tmp/mcp_cache` (Docker volume)

**Cache Strategy:**
- In-memory + disk persistence
- Automatic TTL cleanup
- Session recovery support

---

### 5. RAG Service (Port 9803)

**Container:** `maestro-rag`
**Purpose:** Vector search and retrieval-augmented generation
**Technology:** FastAPI + Python 3.11 + ChromaDB

**Responsibilities:**
- Template retrieval (vector search)
- Best practice recommendations
- Pattern matching
- Collateral extraction

**Storage:**
- ChromaDB: `/app/chroma_db` (Docker volume)
- Embedding model: `all-MiniLM-L6-v2`

**Key Endpoints:**
- `POST /api/v1/query/templates` - Search templates
- `POST /api/v1/query/best-practices` - Get best practices
- `GET /health` - Service health

**Code Organization:**
```
src/rag/
├── api.py                    # Main RAG service API
├── claude_rag_session.py     # Claude session integration
├── persona_rag_tools.py      # Persona-specific RAG tools
└── rag_tools.py              # Common RAG utilities

src/rag_reader/
└── rag_reader_service.py     # Query/retrieval service

src/rag_writer/
└── rag_writer_service.py     # Indexing/storage service

src/rag_system/
├── chroma_client.py          # ChromaDB client
├── vector_rag_manager.py     # Vector DB manager
├── collateral_extractor.py   # Pattern extraction
└── pattern_recommender.py    # Recommendation engine
```

---

### 6. Unified BFF Service (Port 4001)

**Container:** `maestro-bff`
**Purpose:** Primary backend-for-frontend (Accelerator + Guardian modes)
**Technology:** FastAPI + Python 3.11

**Responsibilities:**
- Chat interface (`POST /ai/chat`)
- Guardian workflow triggering
- Session state management
- WebSocket hub (`/ws/{session_id}`)
- MCP event polling
- Real-time progress updates

**Code:** `src/bff/unified_bff_service.py` (42KB, 1000+ lines)

**Key Features:**
- Accelerator Mode: Rapid prototyping with Claude
- Guardian Mode: Full SDLC workflow execution
- Real-time file preview
- Session persistence (Redis)

**Dependencies:**
- Redis (6380) - State storage
- Coordinator (8002) - Workflow execution
- MCP (9800) - Context management
- RAG (9803) - Template retrieval

---

### 7. Collaboration BFF Service (Port 4002)

**Container:** `maestro-collaboration-bff`
**Purpose:** Multi-agent collaboration chat interface
**Technology:** FastAPI + Python 3.11

**Responsibilities:**
- Multi-agent chat room management
- WebSocket-based real-time collaboration
- AI agent routing (@mentions)
- Typing indicators
- Room state management

**Code:** `src/bff/collaboration_service.py` (34KB, 932 lines)

**AI Agents (6):**
1. **Stephen** (📋) - Requirements Analyst (Blue)
2. **Andy** (🏗️) - Solution Architect (Purple)
3. **Sarah** (🎨) - UX Designer (Pink)
4. **Marcus** (⚙️) - Backend Developer (Orange)
5. **Emma** (💻) - Frontend Developer (Green)
6. **Maestro** (🤖) - Code Synthesis (Indigo)

**WebSocket Protocol:**
- `ws://localhost:4002/ws/collaboration/{room_id}`
- Message types: `user_message`, `agent_response`, `typing_indicator`

**Guide:** `docs/guides/COLLABORATION_SERVICE.md`

---

### 8. Quality Fabric Service (Port 8000)

**Container:** `maestro-quality-fabric`
**Purpose:** Universal Testing-as-a-Service platform
**Technology:** FastAPI + Python 3.11

**Responsibilities:**
- Code validation (syntax, security, best practices)
- Test execution (unit, integration, E2E)
- Quality scoring
- Template validation

**Key Endpoints:**
- `POST /api/validate` - Code validation
- `POST /api/test` - Run tests
- `GET /api/quality-score/{project_id}` - Get quality metrics

**Quality Thresholds:**
- Template creation: ≥80.0 quality score
- Test coverage: ≥70.0%
- Test success rate: ≥90%

**Integration:** Used by workflow engine for quality gates

---

### 9. Redis Service (Port 6380)

**Container:** `maestro-redis`
**Image:** `redis:7-alpine`
**Purpose:** Shared state management and caching

**Configuration:**
- Persistence: AOF (append-only file)
- Max memory: 256MB
- Eviction policy: `allkeys-lru`

**Usage:**
- Session state (BFF services)
- Workflow state (async execution)
- WebSocket connection registry
- MCP cache metadata
- Temporary data storage

**Data Structures:**
```
workflow:{id}                 → Hash (workflow metadata)
workflow:{id}:phase:{phase}   → Hash (phase results)
active_workflows              → Set (active workflow IDs)
ws:connections:{workflow_id}  → Set (WebSocket connection IDs)
session:{session_id}          → Hash (BFF session state)
```

**TTLs:**
- Active workflows: 7 days
- Completed workflows: 24 hours
- Sessions: 30 minutes (sliding window)

---

## Data Flow

### Request Flow: Frontend → Backend

```
1. USER REQUEST
   ↓
2. API Gateway (8080)
   - CORS validation
   - Rate limiting
   - Route matching
   ↓
3. Target Service (BFF, Coordinator, etc.)
   - Request processing
   - Service logic
   ↓
4. Dependencies (MCP, RAG, Quality, etc.)
   - Context retrieval (MCP)
   - Template search (RAG)
   - Validation (Quality)
   ↓
5. State Persistence (Redis)
   - Session state
   - Workflow state
   ↓
6. RESPONSE
   - HTTP response
   - WebSocket events
```

### Workflow Execution Flow

```
1. Frontend: Submit requirement
   ↓
2. BFF (4001): Receive request
   - Create session
   - Initialize state
   ↓
3. Coordinator (8002): Orchestrate workflow
   - Load personas
   - Determine execution order
   ↓
4. RAG (9803): Retrieve guidance
   - Query templates
   - Get best practices
   ↓
5. Orchestration (8004): Execute phases
   - Requirements → Design → Implementation → Testing → Deployment
   - For each phase:
     ↓
6. MCP (9800): Cache context
   - Store persona outputs
   - Maintain session state
   ↓
7. Quality Fabric (8000): Validate
   - Run tests
   - Calculate quality score
   - Check thresholds
   ↓
8. Template Extraction (if quality ≥ 80)
   - Extract patterns
   - Create template metadata
   - Publish to template library
   ↓
9. WebSocket Updates (BFF → Frontend)
   - Real-time progress
   - Phase completion
   - File generation
   ↓
10. Final Response
    - Execution results
    - Quality scores
    - Generated artifacts
```

---

## Persona System

### Persona Count: 17 Total

**Core SDLC Personas (11):**
1. Requirement Analyst
2. Solution Architect
3. UI/UX Designer
4. Frontend Developer
5. Backend Developer
6. Database Administrator
7. QA Engineer
8. Security Specialist
9. DevOps Engineer
10. Deployment Specialist
11. Technical Writer

**Meta/Quality Personas (4):**
12. Phase Reviewer
13. Project Reviewer
14. Deliverable Validator
15. Test Engineer

**AI Assistant Personas (2):**
16. **Maestro** - Code synthesis and orchestration
17. **Amigo** - Conversational AI assistant

### Persona Definitions

**Location:** `src/personas/definitions/*.json`

**Schema:** JSON (Pydantic v2 validated)

**Structure:**
```json
{
  "id": "backend_developer",
  "name": "Backend Developer",
  "role": "Implement server-side logic",
  "expertise": ["Python", "FastAPI", "PostgreSQL"],
  "dependencies": ["solution_architect", "database_administrator"],
  "deliverables": ["API endpoints", "Business logic", "Database models"],
  "phase": "implementation",
  "tools": ["code_generator", "test_runner"]
}
```

### Persona Loader

**Code:** `src/bff/persona_loader.py` (new)

**Purpose:** Centralized persona loading for BFF services

**Features:**
- Load from JSON definitions
- Pydantic validation
- Caching
- Error handling

---

## Integration Points

### External Services (Not Managed by Docker Compose)

1. **Maestro Engine (Port 5000)**
   - Main SDLC execution engine
   - External process (not containerized)
   - Accessed via gateway route: `/api/v1/guardian/*`

2. **Workflow API (Port 5001)**
   - Async workflow execution service
   - External process
   - Accessed via gateway route: `/api/workflow/*`

3. **Template Service (Port 9600)**
   - Template library and publishing
   - External container (separate compose)
   - Accessed via gateway route: `/api/v1/templates/*`
   - **Status:** Referenced but not currently running

4. **Frontend (Port 4200 or 5173)**
   - React + TypeScript + Vite
   - Separate project (`maestro-frontend-new`)
   - Connects to gateway (8080)

### Authentication Integration (ISSUE)

**Problem:** Gateway routes reference auth service on port 3100, but no service exists there.

**Current State:** Auth route commented out in `config/gateway_routes.yaml`

**Options:**
1. Implement dedicated auth service on port 3100
2. Use gateway middleware for JWT validation
3. Integrate with external identity provider (OAuth, OIDC)
4. Use Quality Fabric for basic auth

**Impact:** Frontend login currently returns 502 Bad Gateway

---

## Deployment Architecture

### Docker Compose Configuration

**File:** `docker-compose.dev.yml`

**Network:** `maestro-dev-network` (external bridge)

**Volumes:**
- `maestro-mcp-cache-dev` - MCP session cache
- `maestro-chroma-data-dev` - RAG vector database
- `maestro-redis-data-dev` - Redis persistence

### Service Dependencies

```
Gateway
  ↓ (external routing)
BFF ────────┬───→ Coordinator ──→ Orchestration ──→ MCP
            │         ↓                              ↑
            │       RAG ←───────────────────────────┘
            │         ↓
            └─────→ Redis ←─────── MCP (cache metadata)
                      ↑
Collaboration BFF ────┘

Quality Fabric (standalone, accessed via gateway)
```

### Health Checks

All services implement health check endpoints:
- Interval: 30s
- Timeout: 5s (10s for Quality Fabric)
- Retries: 3
- Start period: 10s (60s for Quality Fabric)

**Health Check Endpoints:**
- Gateway: `http://localhost:8080/health`
- Coordinator: `http://localhost:8002/health`
- Orchestration: `http://localhost:8004/health`
- MCP: `http://localhost:9800/health`
- RAG: `http://localhost:9803/health`
- BFF: `http://localhost:4001/health`
- Collaboration BFF: `http://localhost:4002/health`
- Quality Fabric: `http://localhost:8000/api/health`
- Redis: `redis-cli ping`

---

## Known Issues

### Critical Issues

1. **Authentication Service Missing (Port 3100)**
   - **Impact:** Frontend login fails with 502 Bad Gateway
   - **Status:** Route disabled in gateway config
   - **Fix Required:** Implement auth service or use alternative

### Code Organization Issues

1. **RAG Code Duplication**
   - 4 separate directories: `rag/`, `rag_reader/`, `rag_writer/`, `rag_system/`
   - Unclear separation of concerns
   - **Recommendation:** Consolidate under `src/rag/` with subdirectories

2. **BFF Service Overlap**
   - Two BFF services (4001, 4002) with some functional overlap
   - **Recommendation:** Document clear separation of concerns
   - Unified BFF: Accelerator/Guardian workflows
   - Collaboration BFF: Multi-agent chat

3. **Persona Count Discrepancy**
   - README claims 11 personas
   - Actually 17 persona definition files
   - **Fix:** Update README to reflect 17 total (11 core + 4 meta + 2 AI)

### Documentation Issues

1. **Architecture Diagram Out of Date**
   - README shows 4 services (Engine, BFF, Frontend, Redis)
   - Actually 9 containerized services
   - **Fix:** Update README architecture diagram

2. **Port Inconsistencies**
   - README mentions Redis on 6379
   - Actually exposed on 6380
   - **Fix:** Update all port references

---

## Architecture Decision Records

Related ADRs:
- **ADR-001:** Service Discovery
- **ADR-003:** API Gateway Pattern
- **ADR-004:** Port Allocation
- **ADR-006:** Resilience Patterns
- **ADR-007:** Code Organization

**Location:** `docs/architecture/ADR-*.md`

---

## References

- **Main README:** `/README.md`
- **API Specification:** `/API_SPECIFICATION.md`
- **Documentation Index:** `/docs/INDEX.md`
- **Gateway Config:** `/config/gateway_routes.yaml`
- **Docker Compose:** `/docker-compose.dev.yml`
- **Cleanup Summary:** `/docs/CLEANUP_SUMMARY.md`

---

**Last Updated:** 2025-10-16
**Reviewer:** Claude Code Assistant
**Status:** ✅ Current and Accurate
