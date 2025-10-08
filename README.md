# MAESTRO Engine v3.0

**AI-Powered SDLC Workflow Automation Platform**

[![Status](https://img.shields.io/badge/status-production--ready-green.svg)](https://github.com/maestro-engine)
[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)](https://github.com/maestro-engine)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 🔌 Frontend-Agnostic Design

**The Maestro Engine can work with ANY frontend** that implements the API contract (see [API_SPECIFICATION.md](./API_SPECIFICATION.md)).

### Swappable Frontends

The backend exposes a standard REST API + WebSocket interface:
```bash
# Use Maestro Frontend (official)
# Connect to: http://localhost:8080/api

# OR use your custom frontend
# Just implement the API contract documented in API_SPECIFICATION.md

# OR use any HTTP client (Postman, curl, etc.)
curl http://localhost:8080/api/workflows
```

**No frontend dependencies** - the backend is completely independent!

### API Contract

See [API_SPECIFICATION.md](./API_SPECIFICATION.md) for:
- ✅ Complete REST API endpoints
- ✅ WebSocket message protocol
- ✅ Authentication (optional)
- ✅ Error handling
- ✅ OpenAPI/Swagger documentation

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Redis 6+
- Claude API key
- [maestro-shared](https://github.com/kulbirminhas-aiinitiative/maestro-shared) repository (cloned locally)

### Dependencies

The Maestro Engine uses shared packages from the [maestro-shared](https://github.com/kulbirminhas-aiinitiative/maestro-shared) repository:
- `maestro-core-api` - FastAPI framework and utilities
- `maestro-core-auth` - Authentication and authorization
- `maestro-core-config` - Configuration management
- `maestro-core-logging` - Structured logging
- `maestro-core-db` - Database abstraction
- `maestro-core-messaging` - Event messaging
- `maestro-monitoring` - Observability

**Current approach**: Using local path dependencies during migration:
```toml
# pyproject.toml
maestro-core-api = {path = "../maestro-shared/packages/core-api", develop = true}
```

**Future approach**: Will use published packages from GitHub Packages:
```toml
# pyproject.toml (after publishing)
maestro-core-api = "^0.1.0"
```

### Start All Services

```bash
# 1. Start Redis
sudo systemctl start redis6

# 2. Start MAESTRO Engine (Port 5000)
cd /home/ec2-user/projects/maestro-engine
nohup python3.11 src/maestro_engine_app.py > /tmp/maestro_engine.log 2>&1 &
echo $! > /tmp/maestro_engine.pid

# 3. Start Unified BFF (Port 4001)
cd /home/ec2-user/projects/maestro-engine/src
nohup python3.11 -m bff.unified_bff_service > /tmp/bff_service.log 2>&1 &
echo $! > /tmp/bff_service.pid

# 4. Start Frontend (Port 4200)
cd /home/ec2-user/projects/maestro-frontend
npm run dev

# 5. Verify all services
curl http://localhost:5000/health  # Engine
curl http://localhost:4001/health  # BFF
curl http://localhost:4200         # Frontend
```

### Access the Platform
- **Frontend**: http://localhost:4200
- **Engine API**: http://localhost:5000/docs
- **BFF API**: http://localhost:4001/docs

---

## 📖 Overview

MAESTRO Engine is an **autonomous SDLC workflow automation platform** powered by **11 specialized AI personas** that execute complete software development lifecycles from requirements to deployment.

### Key Features

✅ **Schema v3.0 Persona System**
- 11 specialized personas (Analyst, Architect, Developers, QA, Security, DevOps, etc.)
- Clean JSON definitions with Pydantic v2 validation
- Dependency resolution and team organization

✅ **Autonomous SDLC Engine V3**
- Session management with resume capability
- DAG-based workflow execution
- Parallel, sequential, and hierarchical execution modes
- Context propagation between personas

✅ **Full Stack Architecture**
- FastAPI backend (Python 3.11)
- React + TypeScript frontend (Vite)
- WebSocket real-time updates
- Redis state management

✅ **Production Ready**
- Comprehensive testing
- Session persistence
- Real-time progress tracking
- Clean architecture

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MAESTRO Platform v3.0                     │
│              (Persona-Driven SDLC Automation)                │
└─────────────────────────────────────────────────────────────┘

Frontend (4200)    ──HTTP/WS──>   BFF (4001)    ──HTTP──>    Engine (5000)
  React + Vite                     FastAPI                     FastAPI
  - Accelerator UI                 - Chat API                 - Persona API
  - Workflow Monitor               - Guardian Trigger          - Workflow Engine
  - File Explorer                  - WebSocket Hub            - Session Manager
                                   - State Management          - DAG Workflows
                                         │
                                         ▼
                                   Redis (6379)
                                   State + Cache

                                                                    │
                                                                    ▼
                                                    ┌───────────────────────────┐
                                                    │  Schema v3.0 Personas     │
                                                    │  - 11 Specialized Agents  │
                                                    │  - Team Organization      │
                                                    │  - Context Propagation    │
                                                    └───────────────────────────┘
```

---

## 👥 Personas (Schema v3.0)

The platform includes 11 specialized personas organized across 5 SDLC phases:

| Phase | Personas | Role |
|-------|----------|------|
| **Requirements** | Requirement Analyst | Gather and analyze requirements |
| **Design** | Solution Architect, UI/UX Designer | Architecture and design |
| **Implementation** | Frontend Dev, Backend Dev, Database Admin | Code implementation |
| **Testing** | QA Engineer, Security Specialist | Quality and security |
| **Deployment** | DevOps Engineer, Deployment Specialist, Technical Writer | Deploy and document |

Each persona:
- Has specialized expertise and responsibilities
- Creates specific deliverables
- Collaborates with other personas
- Contributes to the complete SDLC

---

## 📚 Documentation

Comprehensive documentation is organized in the `docs/` directory:

### Quick Links
- **Architecture**: `docs/architecture/IMPLEMENTATION_STATUS.md`
- **Phase Progress**: `docs/phases/`
- **User Guides**: `docs/guides/`
- **API Reference**: `docs/api/`

### Documentation Structure

```
docs/
├── architecture/          # Architecture documentation
├── phases/                # Phase-by-phase progress
├── guides/                # User guides
├── api/                   # API documentation
└── archived/              # Historical documents
```

---

## 🎯 Use Cases

### 1. Complete SDLC Workflow
```bash
curl -X POST http://localhost:5000/api/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "requirement": "Build a blog platform with user authentication",
    "session_id": "blog_v1"
  }'
```

### 2. Guardian Mode (via Frontend)
1. Open http://localhost:4200
2. Enter requirement
3. Click "Execute Guardian Workflow"
4. Watch real-time persona execution
5. Review generated files

---

## 🧪 Testing

### Health Checks
```bash
curl http://localhost:5000/health           # Engine
curl http://localhost:4001/health           # BFF
/usr/bin/redis6-cli ping                    # Redis
```

### Test Results (Phase 3)
- ✅ 11/11 personas loaded
- ✅ Workflow execution verified (570s, 8 files)
- ✅ Session persistence working
- ✅ All endpoints functional

---

## 📊 Project Stats

| Metric | Value |
|--------|-------|
| **Personas** | 11 specialized AI agents |
| **Services** | 4 (Engine, BFF, Frontend, Redis) |
| **Production Ready** | 95% |
| **Code Archived** | 648KB cleaned up |
| **Documentation** | 40+ documents organized |

---

## 🔧 Development

### Project Structure
```
maestro-engine/
├── src/
│   ├── personas/                # Schema v3.0 persona system
│   ├── orchestration/           # Workflow orchestration
│   ├── api/                     # REST API endpoints
│   ├── bff/                     # Backend-for-Frontend
│   ├── workflow/                # DAG workflows
│   └── archived/                # Archived code (648KB)
├── docs/                        # Documentation (organized)
├── tests/                       # Test suites
└── README.md                    # This file
```

### Key Technologies
- **Backend**: Python 3.11, FastAPI, Pydantic v2
- **Frontend**: React 18, TypeScript, Vite
- **State**: Redis 6.2.14
- **AI**: Claude Code SDK
- **WebSocket**: Real-time updates

---

## 🌟 Recent Updates (Phase 5)

- ✅ Documentation organized (53 → 1 MD in root)
- ✅ Code cleanup (648KB archived)
- ✅ Clean architecture verified
- ✅ All services running smoothly

---

## 🔗 Related Projects

- **Quality Fabric**: `/home/ec2-user/projects/quality-fabric`
- **Maestro Templates**: `/home/ec2-user/projects/maestro-templates`
- **Maestro Frontend**: `/home/ec2-user/projects/maestro-frontend`

---

## 📝 License

MIT License

---

**Built with ❤️ using Claude Code SDK**

**Status**: ✅ Production Ready (95%)
**Version**: 3.0.0
**Last Updated**: 2025-10-03
