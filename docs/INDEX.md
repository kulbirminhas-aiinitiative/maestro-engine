# MAESTRO Engine Documentation Index

**Complete documentation for MAESTRO Engine v3.0**

---

## 📖 Getting Started

**New to MAESTRO?** Start here:

1. **[Main README](../README.md)** - Project overview and quick start
2. **[Architecture Overview](architecture/IMPLEMENTATION_STATUS.md)** - Current system design
3. **[Phase 4 Integration](phases/PHASE_4_INTEGRATION.md)** - Full stack setup
4. **[Phase 5 Production](phases/PHASE_5_PRODUCTION.md)** - Production enhancement

---

## 🏗️ Architecture Documentation

**Understanding the system design**:

- **[Current Architecture](architecture/CURRENT_ARCHITECTURE.md)** ⭐ **START HERE - UPDATED 2025-10-16**
  - Complete service topology (9 services)
  - Service details and responsibilities
  - Data flow diagrams
  - Persona system (17 personas)
  - Integration points
  - Known issues

- **[Async Workflows](architecture/ASYNC_WORKFLOWS.md)** 🆕
  - Non-blocking workflow execution
  - Real-time progress tracking
  - WebSocket integration
  - Redis state management

- **[Implementation Status](architecture/IMPLEMENTATION_STATUS.md)**
  - Current vs original architecture
  - Architecture Decision Records (ADRs)
  - Compliance analysis
  - Production readiness assessment

- **[Original Architecture](architecture/ORIGINAL_ARCHITECTURE.md)**
  - MAESTRO Services Architecture
  - MCP/UTCP orchestration design
  - Template and Quality Fabric integration

- **[MCP Cache Architecture](architecture/MCP_CACHE_ARCHITECTURE.md)**
  - MCP cache design and implementation
  - Event streaming architecture

- **[Team Workflow Integration](architecture/TEAM_WORKFLOW_INTEGRATION.md)**
  - DAG workflow system
  - Team organization structure
  - Execution modes (sequential, hierarchical, parallel)

- **[BFF Architecture](architecture/BFF_ARCHITECTURE.md)**
  - Backend-for-Frontend design
  - WebSocket integration
  - State management

- **[MCP Architecture Gap Analysis](architecture/MCP_ARCHITECTURE_GAP_ANALYSIS.md)**
  - Gaps between original and current design
  - Migration considerations

---

## 📅 Phase Documentation

**Project evolution across 5 phases**:

### Completed Phases

- **[Phase 2: Integration](phases/PHASE_2_INTEGRATION.md)**
  - Persona system integration
  - Initial workflow engine setup

- **[Phase 3: Engine Testing](phases/PHASE_3_TESTING.md)** & **[Status](phases/PHASE_3_STATUS.md)**
  - Production testing
  - Real workflow execution (TODO app)
  - Session persistence verification
  - Async event loop fix

- **[Phase 4: Full Stack](phases/PHASE_4_INTEGRATION.md)**
  - BFF service integration
  - Frontend connection
  - WebSocket setup
  - Redis state management
  - **Result**: All 4 services running ✅

### Current Phase

- **[Phase 5: Production](phases/PHASE_5_PRODUCTION.md)**
  - Code cleanup (648KB archived)
  - Documentation organization
  - Service integrations (Quality Fabric, Templates)
  - Production deployment preparation

### Historical Documents

- **[Integration Complete](phases/INTEGRATION_COMPLETE.md)** - Final integration summary
- **[Early Integration](phases/EARLY_INTEGRATION.md)** - Initial integration
- **[Phase 5 Cleanup Assessment](phases/PHASE_5_CLEANUP_ASSESSMENT.md)** - Cleanup analysis

---

## 📘 User Guides

**How-to guides for common tasks**:

### Testing
- **[Testing Guide](guides/TESTING_GUIDE.md)**
  - E2E testing
  - Integration tests
  - Health checks

- **[E2E Testing](guides/E2E_TESTING.md)** 🆕
  - End-to-end test setup
  - Test scenarios
  - CI/CD integration

### Integration
- **[Frontend Integration](guides/FRONTEND_INTEGRATION.md)**
  - Frontend setup
  - WebSocket connection
  - API integration

- **[Gateway Integration](guides/GATEWAY_INTEGRATION.md)** 🆕
  - API Gateway setup
  - Route configuration
  - Service integration

- **[Persona Integration](guides/PERSONA_INTEGRATION.md)**
  - Schema v3.0 persona system
  - Adding new personas
  - Persona adapter

### Services
- **[Collaboration Service](guides/COLLABORATION_SERVICE.md)** 🆕
  - Multi-agent collaboration BFF
  - WebSocket chat interface
  - AI agent configuration
  - Room management

- **[RAG Guide](guides/RAG_GUIDE.md)** 🆕
  - Vector search setup
  - Template retrieval
  - Best practice recommendations

### Quick Starts
- **[Quick Start - Async Workflows](guides/QUICK_START_ASYNC.md)** 🆕
  - Async workflow execution
  - Real-time progress tracking
  - WebSocket integration

- **[Quick Start - Collaboration](guides/QUICK_START_COLLABORATION.md)** 🆕
  - Multi-agent chat setup
  - Agent interaction
  - Room management

### Git & Publishing
- **[GitHub Setup](guides/GITHUB_SETUP.md)**
  - Repository configuration
  - Authentication tokens

- **[Git Template Publishing](guides/GIT_TEMPLATE_PUBLISHING.md)**
  - Template publishing workflow

- **[Git Template Integration](guides/GIT_TEMPLATE_INTEGRATION.md)**
  - E2E template integration

### Other Guides
- **[UTCP Guide](guides/UTCP_GUIDE.md)**
  - Universal Tool Calling Protocol
  - MCP/UTCP functionality

- **[Configuration Guide](guides/CONFIGURATION.md)**
  - Service configuration
  - Environment variables

---

## 🔌 API Documentation

**API references**:

- **[Personas API](api/PERSONAS_API.md)**
  - Persona endpoints
  - Schema v3.0 format
  - Dependency resolution

### Engine API Endpoints

**Base URL**: `http://localhost:5000`

- `GET /health` - Engine health check
- `GET /api/workflow/health` - Workflow system health
- `GET /api/workflow/personas` - List all personas
- `GET /api/workflow/personas/{id}` - Get persona details
- `POST /api/workflow/execute` - Execute workflow
- `POST /api/workflow/execution-order` - Get execution order
- `GET /docs` - Interactive API documentation

### BFF API Endpoints

**Base URL**: `http://localhost:4001`

- `GET /health` - BFF health check
- `POST /ai/chat` - AI chat endpoint
- `WS /ws/{session_id}` - WebSocket connection
- `GET /api/session/{id}/state` - Session state
- `GET /api/session/{id}/preview` - Session preview
- `GET /docs` - Interactive API documentation

---

## 📦 Archived Documentation

**Historical documents for reference**:

### Phase 1-2 Archives
Located in `archived/phase1-2/`:
- Early status files
- Migration summaries
- CI/CD implementation docs
- Template integration docs
- Test reports
- Completion reports (COLLABORATION_BFF, PERSONA_MIGRATION, etc.) 🆕

### Status Reports 🆕
Located in `archived/status-reports/`:
- Workflow review and analysis
- Service readiness assessments
- Recommendations and status reviews
- Architecture centralization guides

### Fix Summaries
Located in `archived/fixes/`:
- Health check fixes
- Console error fixes
- TypeScript fixes
- Validation bypass issues

### Migrations
Located in `archived/migrations/`:
- Migration summaries
- MCP cache service status

**Note**: Archived documents are kept for historical reference but may not reflect the current system.

**Recent Cleanup (2025-10-16):**
- Moved 11 documents from root to appropriate archives
- Created status-reports archive directory
- Reduced root MD files from 19 → 2
- See `CLEANUP_SUMMARY.md` for details

---

## 🎯 Quick Reference

### Common Tasks

| Task | Document |
|------|----------|
| **Start all services** | [README - Quick Start](../README.md#quick-start) |
| **Understand architecture** | [Implementation Status](architecture/IMPLEMENTATION_STATUS.md) |
| **Execute workflow** | [README - Use Cases](../README.md#use-cases) |
| **Check system health** | [Testing Guide](guides/TESTING_GUIDE.md) |
| **Integrate frontend** | [Frontend Integration](guides/FRONTEND_INTEGRATION.md) |
| **Add new persona** | [Persona Integration](guides/PERSONA_INTEGRATION.md) |
| **Review test results** | [Phase 3 Status](phases/PHASE_3_STATUS.md) |
| **Deploy to production** | [Phase 5 Production](phases/PHASE_5_PRODUCTION.md) |

### Service Ports (Updated 2025-10-16)

| Service | Port | Health Check |
|---------|------|--------------|
| **API Gateway** | 8080 | `curl http://localhost:8080/health` |
| **Coordinator** | 8002 | `curl http://localhost:8002/health` |
| **Orchestration** | 8004 | `curl http://localhost:8004/health` |
| **Unified BFF** | 4001 | `curl http://localhost:4001/health` |
| **Collaboration BFF** | 4002 | `curl http://localhost:4002/health` |
| **MCP Service** | 9800 | `curl http://localhost:9800/health` |
| **RAG Service** | 9803 | `curl http://localhost:9803/health` |
| **Quality Fabric** | 8000 | `curl http://localhost:8000/api/health` |
| **Redis** | 6380 | `redis-cli -p 6380 ping` |
| **Frontend** (external) | 4200 | `curl http://localhost:4200` |

### Key Concepts

| Concept | Description | Documentation |
|---------|-------------|---------------|
| **Personas** | 17 specialized AI agents (11 core + 4 meta + 2 AI) | [Current Architecture](architecture/CURRENT_ARCHITECTURE.md) |
| **Schema v3.0** | Persona definition format | [Persona Integration](guides/PERSONA_INTEGRATION.md) |
| **DAG Workflows** | Directed Acyclic Graph workflows | [Team Workflow](architecture/TEAM_WORKFLOW_INTEGRATION.md) |
| **Guardian Mode** | Full SDLC workflow execution | [README](../README.md) |
| **Session Management** | Persistent workflow sessions | [Phase 3 Status](phases/PHASE_3_STATUS.md) |
| **API Gateway** | Single entry point for all requests | [Current Architecture](architecture/CURRENT_ARCHITECTURE.md) |

---

## 🔍 Search Tips

**Finding specific information**:

1. **Architecture questions**: Check `architecture/CURRENT_ARCHITECTURE.md` (most up-to-date)
2. **Setup issues**: Check `../README.md` or `phases/PHASE_4_INTEGRATION.md`
3. **API usage**: Check `api/` or service `/docs` endpoints
4. **Historical context**: Check `archived/` directory
5. **Testing**: Check `guides/TESTING_GUIDE.md`
6. **Recent changes**: Check `CLEANUP_SUMMARY.md`

---

## 📝 Documentation Standards

**When adding new documentation**:

- Place in appropriate directory (`architecture/`, `phases/`, `guides/`, `api/`)
- Use clear, descriptive filenames
- Include date and status at top
- Link from this INDEX.md
- Use markdown formatting
- Include code examples where applicable

---

## 🆘 Need Help?

**Can't find what you're looking for?**

1. Check the [Main README](../README.md)
2. Review [Current Architecture](architecture/CURRENT_ARCHITECTURE.md) ⭐ Most up-to-date
3. Browse [Phase Documentation](phases/)
4. Search archived docs for historical context
5. Check [Cleanup Summary](CLEANUP_SUMMARY.md) for recent changes

---

**Last Updated**: 2025-10-16
**Documentation Version**: 3.0.0
**Total Documents**: 50+ (organized)
**Root MD Files**: 2 (down from 19)
