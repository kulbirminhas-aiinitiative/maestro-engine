# MAESTRO Engine v3.0 - Technical Documentation

**Project**: MAESTRO Engine
**Version**: 3.0.0
**Type**: AI-Powered SDLC Workflow Automation Platform
**Status**: Production Ready (95%)
**Last Updated**: December 2025

---

## Table of Contents

1. [Overview](#1-overview)
2. [Technology Stack](#2-technology-stack)
3. [Directory Structure](#3-directory-structure)
4. [Core Architecture](#4-core-architecture)
5. [Persona System (Schema v3.0)](#5-persona-system-schema-v30)
6. [Data Models](#6-data-models)
7. [Key Components](#7-key-components)
8. [API Layer](#8-api-layer)
9. [Services](#9-services)
10. [Configuration](#10-configuration)
11. [Integration Points](#11-integration-points)
12. [Resilience Patterns](#12-resilience-patterns)
13. [Testing](#13-testing)
14. [Deployment](#14-deployment)
15. [Related Repositories](#15-related-repositories)

---

## 1. Overview

MAESTRO Engine is an autonomous SDLC workflow automation platform powered by 11 specialized AI personas that execute complete software development lifecycles from requirements to deployment.

### Key Features

- **Persona-Driven Execution**: Schema v3.0 system with 11 specialized AI agents
- **Workflow Orchestration**: DAG-based execution with dependency resolution
- **Session Management**: Resume capability for incremental execution
- **Real-time Updates**: WebSocket-based progress tracking
- **Quality Validation**: Integration with Quality Fabric for code validation
- **Template Management**: RAG-powered template retrieval and management
- **Frontend-Agnostic Design**: REST API + WebSocket interface

### Code Statistics

| Metric | Value |
|--------|-------|
| Python Files | 189 |
| Lines of Code | ~75,800 |
| Service Implementations | 39 |
| Persona Definitions | 17 |
| API Route Files | 24+ |
| Test Suites | 13+ |
| Docker Services | 9 |

---

## 2. Technology Stack

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Core runtime |
| FastAPI | Latest | REST API framework |
| Pydantic | v2 | Data validation |
| Uvicorn | Latest | ASGI server |

### AI/ML
| Technology | Purpose |
|------------|---------|
| Anthropic Claude API | AI model (claude-sonnet-4-20250514) |
| Claude Agent SDK | v3.0 agent framework |
| RAG System | Vector embeddings, semantic search |

### State Management
| Technology | Version | Purpose |
|------------|---------|---------|
| Redis | 6.2.14+ | Session state, caching |

### Frontend (Optional)
| Technology | Purpose |
|------------|---------|
| React 18 | UI framework |
| TypeScript | Type safety |
| Vite | Build tool |

### Infrastructure
| Technology | Purpose |
|------------|---------|
| Docker | Containerization |
| Docker Compose | Multi-service orchestration |
| Prometheus | Metrics collection |
| FastAPI Middleware | CORS, Auth, Rate Limiting |

### Development
| Tool | Purpose |
|------|---------|
| Poetry | Dependency management |
| pytest | Testing framework |
| Black, isort, flake8, mypy | Code quality |
| Pre-commit hooks | Git hooks |

---

## 3. Directory Structure

```
maestro-engine-new/
├── src/
│   ├── api/                    # REST API routes (24 route files)
│   ├── bff/                    # Backend-for-Frontend services
│   ├── config/                 # Configuration management
│   ├── gateway/                # API Gateway (ADR-003)
│   ├── integrations/           # Service integrations
│   ├── maestro_mcp/            # MCP/UTCP orchestration
│   ├── orchestration/          # Workflow orchestration engines
│   ├── personas/               # Persona system (Schema v3.0)
│   │   └── definitions/        # 17 JSON persona definitions
│   ├── rag/                    # RAG system components
│   ├── resilience/             # Resilience patterns (ADR-006)
│   ├── services/               # 39 service implementations
│   ├── templates/              # Template management
│   ├── utils/                  # Utilities (Redis, SQLite, PII masking)
│   ├── workflow/               # DAG and workflow engine
│   ├── database/               # Database schemas and migrations
│   ├── dde/                    # Distributed Deployment Engine
│   ├── knowledge/              # Knowledge base service
│   ├── registry/               # Service registry
│   ├── rag_system/             # Vector RAG manager
│   └── maestro_engine_app.py   # Main entry point (port 5000)
├── config/                     # Configuration YAML files
├── tests/                      # Test suite (unit, integration, e2e)
├── docs/                       # Comprehensive documentation
├── pyproject.toml              # Poetry dependency configuration
├── docker-compose.dev.yml      # Development Docker Compose
├── docker-compose.prod.yml     # Production Docker Compose
├── Dockerfile.*                # 8 Dockerfile variants
└── .env*                       # Environment configurations
```

---

## 4. Core Architecture

### Entry Points

| Service | File | Port | Purpose |
|---------|------|------|---------|
| **MAESTRO Engine** | `src/maestro_engine_app.py` | 5000 | Main FastAPI application |
| **Unified BFF** | `src/bff/unified_bff_service.py` | 4001 | Backend-for-Frontend with WebSocket |
| **API Gateway** | `src/gateway/main.py` | 8080 | Central routing, auth, rate limiting |

### Architecture Diagram

```
                    ┌─────────────────────────────────────┐
                    │           API Gateway               │
                    │         (Port 8080)                 │
                    │  - Request routing                  │
                    │  - CORS, Rate limiting              │
                    │  - Circuit breaker                  │
                    └─────────────┬───────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Unified BFF   │     │ MAESTRO Engine  │     │  Microservices  │
│   (Port 4001)   │     │   (Port 5000)   │     │                 │
│                 │     │                 │     │ - Quality: 8000 │
│ - WebSocket     │     │ - Persona API   │     │ - Templates:9600│
│ - AI Chat       │     │ - Workflow API  │     │ - RAG: 9803     │
│ - Claude Code   │     │ - Document API  │     │ - MCP: 9800     │
└────────┬────────┘     └────────┬────────┘     └─────────────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
          ┌─────────────────────┐
          │       Redis         │
          │    (Port 6379)      │
          │                     │
          │ - Session state     │
          │ - Caching           │
          │ - Pub/Sub           │
          └─────────────────────┘
```

### Design Patterns

1. **API Gateway Pattern** (ADR-003): Single entry point with dynamic routing
2. **Circuit Breaker Pattern** (ADR-006): Fault tolerance for external services
3. **Retry Pattern**: Exponential backoff with configurable max retries
4. **Bulkhead Pattern**: Resource isolation and concurrency limits
5. **Adapter Pattern**: Persona registry adapter for v3.0 schema
6. **Dependency Injection**: FastAPI dependencies for database, Redis, etc.
7. **MVC/Service Pattern**: Controllers (routes) → Services → Data access
8. **Observer Pattern**: WebSocket events for real-time updates
9. **Executor Pattern**: Thread pool for CPU-intensive tasks
10. **Strategy Pattern**: Multiple execution modes (sequential, parallel, hybrid)

---

## 5. Persona System (Schema v3.0)

### 11 SDLC Personas Across 5 Phases

| Phase | Persona | Human Alias | Role |
|-------|---------|-------------|------|
| **Requirements** | Requirement Analyst | Stephen | Gather & analyze requirements |
| **Design** | Solution Architect | - | System architecture |
| **Design** | UI/UX Designer | Emma | User experience design |
| **Implementation** | Frontend Developer | - | UI implementation |
| **Implementation** | Backend Developer | Marcus | API & business logic |
| **Implementation** | Database Admin | - | Data modeling |
| **Testing** | QA Engineer | - | Test planning & execution |
| **Testing** | Security Specialist | - | Security analysis |
| **Deployment** | DevOps Engineer | - | CI/CD & infrastructure |
| **Deployment** | Deployment Specialist | - | Release management |
| **Deployment** | Technical Writer | - | Documentation |

### Additional Personas

| Persona | Purpose |
|---------|---------|
| Amigo | General AI assistant |
| Maestro | System coordinator |
| Phase Reviewer | Phase quality review |
| Project Reviewer | Project-level review |
| Deliverable Validator | Output validation |

### Persona Definition Schema (v3.0)

```json
{
  "persona_id": "string",
  "schema_version": "3.0",
  "version": "string",
  "display_name": "string",

  "metadata": {
    "description": "string",
    "author": "string",
    "created_at": "ISO date",
    "updated_at": "ISO date",
    "category": "analysis_design|development|operations|quality_security|documentation",
    "status": "active|deprecated|experimental",
    "human_alias": "string (optional)"
  },

  "role": {
    "primary_role": "string",
    "experience_level": "1-10",
    "autonomy_level": "1-10",
    "specializations": ["string"]
  },

  "capabilities": {
    "core": ["string"],
    "tools": ["string"]
  },

  "contracts": {
    "input": {
      "required": ["string"],
      "optional": ["string"],
      "validation": {}
    },
    "output": {
      "required": ["string"],
      "optional": ["string"],
      "format": {}
    }
  },

  "dependencies": {
    "depends_on": ["persona_id"],
    "required_by": ["persona_id"],
    "collaboration_with": ["persona_id"]
  },

  "execution": {
    "timeout_seconds": 300,
    "max_retries": 3,
    "priority": "1-10",
    "parallel_capable": true,
    "estimated_duration_seconds": 120
  },

  "prompts": {
    "system_prompt": "string",
    "task_prompt_template": "string with {variables}"
  },

  "quality_metrics": {
    "expected_output_quality": {},
    "performance_targets": {}
  }
}
```

---

## 6. Data Models

### Task Node (DAG)

```python
@dataclass
class TaskNode:
    id: str                      # Unique task ID
    title: str                   # Task title
    description: str             # Detailed description
    task_type: TaskType          # CODE|REVIEW|TEST|DEPLOY|RESEARCH|DECISION|CUSTOM
    required_role: Optional[str] # Required persona
    priority: int                # Execution priority
    metadata: Dict[str, Any]     # Custom metadata
    tags: List[str]              # Classification tags
    depends_on: List[str]        # Dependency IDs
    dependents: List[str]        # Dependent task IDs
```

### DAG (Workflow)

```python
class DAG:
    workflow_id: str                  # Workflow ID
    name: str                         # Workflow name
    description: str                  # Description
    nodes: Dict[str, TaskNode]        # Task nodes
    edges: List[Tuple[str, str]]      # Dependencies (from, to)
```

### Session Data

```python
class SDLCSession:
    session_id: str
    requirement: str
    output_dir: Path
    created_at: datetime
    last_updated: datetime
    completed_personas: List[str]     # Already executed
    files_registry: Dict[str, Dict]   # Files created
    persona_outputs: Dict[str, Dict]  # Execution results
```

### Persona Execution Result

```python
class PersonaExecutionResult:
    persona_id: str
    success: bool
    output: Optional[Dict[str, Any]]
    error: Optional[str]
    execution_time: float
    files_created: List[str]
    timestamp: datetime
```

---

## 7. Key Components

### Orchestration Engine (`src/orchestration/`)

| Component | File | Purpose |
|-----------|------|---------|
| Session Manager | `session_manager.py` | Persistent session tracking |
| Persona Orchestrator | `persona_orchestrator.py` | Dependency-based execution |
| SDLC Engine V3 | `autonomous_sdlc_engine_v3_resumable.py` | Main execution engine |
| Team Organization | `team_organization.py` | Team structure management |
| RAG Integration | `rag_integration.py` | Template retrieval |

**Execution Commands:**
```bash
# Single persona
python autonomous_sdlc_engine_v3_resumable.py requirement_analyst --requirement "Create a blog"

# Multiple personas
python autonomous_sdlc_engine_v3_resumable.py frontend_developer backend_developer --resume blog_v1

# All remaining personas
python autonomous_sdlc_engine_v3_resumable.py --resume blog_v1 --all-remaining
```

### Workflow Engine (`src/workflow/`)

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| DAG | `dag.py` | 465 | Directed Acyclic Graph implementation |
| Workflow Engine | `workflow_engine.py` | - | DAG execution with topological sorting |
| Workflow Templates | `workflow_templates.py` | - | Template-based workflows |

**Supported Task Types:**
- `CODE` - Code generation
- `REVIEW` - Code review
- `TEST` - Testing
- `DEPLOY` - Deployment
- `RESEARCH` - Research tasks
- `DECISION` - Decision points
- `CUSTOM` - Custom tasks

### Persona Registry (`src/personas/`)

| Component | File | Purpose |
|-----------|------|---------|
| Registry | `registry.py` | Central persona registry |
| Models | `models.py` | Pydantic v2 data models |
| Adapter | `adapter.py` | Compatibility layer |
| Definitions | `definitions/*.json` | 17 persona JSON files |

### BFF Layer (`src/bff/`)

| Component | File | Purpose |
|-----------|------|---------|
| Unified BFF | `unified_bff_service.py` | Main BFF with WebSocket |
| Collaboration | `collaboration_service.py` | Multi-user collaboration |
| Redis State | `redis_state_manager.py` | Session persistence |
| WebSocket Manager | `websocket_manager.py` | Real-time updates |
| Confidence Scorer | `confidence_scorer.py` | AI confidence metrics |

### Gateway (`src/gateway/`)

| Component | File | Purpose |
|-----------|------|---------|
| Main Gateway | `main.py` | Gateway application |
| Route Manager | `routing/router.py` | Route configuration |
| Proxy Router | `routing/proxy.py` | HTTP proxying |
| Auth Middleware | `middleware/auth.py` | JWT/API key validation |
| Cache Middleware | `middleware/cache.py` | Response caching |
| Circuit Breaker | `middleware/circuit_breaker.py` | Fault tolerance |
| Rate Limiting | `middleware/rate_limit.py` | Per-route rate limits |

---

## 8. API Layer

### Route Files (`src/api/`)

| Route File | Endpoints | Purpose |
|------------|-----------|---------|
| `main.py` | `/api/v1/*` | Primary REST API |
| `persona_workflow_api.py` | `/workflow/*` | Persona execution |
| `ai_dag_routes.py` | `/dag/*` | AI-driven DAG generation |
| `dag_catalog_routes.py` | `/catalog/*` | DAG catalog management |
| `template_*.py` | `/templates/*` | Template management |
| `deployment_routes.py` | `/deployments/*` | Deployment management |
| `e2e_agent_routes.py` | `/e2e/*` | End-to-end testing |
| `jira_integration_routes.py` | `/jira/*` | Issue tracking |
| `quality_enforcement_routes.py` | `/quality/*` | Quality gates |
| `gate_routes.py` | `/gates/*` | Phase gates |

### API Examples

#### Health Check
```http
GET /health
```
```json
{
  "status": "healthy",
  "service": "maestro-engine",
  "version": "3.0.0",
  "environment": "development",
  "components": {
    "persona_workflow_api": true,
    "document_api": true
  }
}
```

#### Workflow Execution Request
```http
POST /api/v1/workflow/execute
Content-Type: application/json
```
```json
{
  "requirement": "Create a blog platform with authentication",
  "session_id": "blog_v1",
  "personas": ["requirement_analyst", "backend_developer"],
  "enable_quality_gates": true
}
```

#### Workflow Execution Response
```json
{
  "session_id": "blog_v1",
  "success": true,
  "message": "Workflow completed successfully",
  "requirement": "Create a blog platform...",
  "timestamp": "2025-10-08T10:00:00Z",
  "execution_time": 570.5,
  "files_generated": ["models.py", "api.py", "database.sql"],
  "project_path": "/tmp/maestro_projects/blog_v1"
}
```

### WebSocket Protocol

```json
{
  "type": "persona_update|progress|file_created|error|complete",
  "session_id": "string",
  "persona_id": "string",
  "data": {
    "status": "running|completed|failed",
    "message": "string",
    "progress": 0-100
  }
}
```

---

## 9. Services

### Service Directory (`src/services/` - 39 implementations)

#### DAG Services
| Service | Purpose |
|---------|---------|
| `dag_catalog.py` | Template catalog management (Redis-backed) |
| `dag_generator.py` | AI-driven DAG generation |
| `dag_validator.py` | DAG validation and integrity |
| `dag_presenter.py` | DAG visualization |

#### Deployment Services
| Service | Purpose |
|---------|---------|
| `deployment_service.py` | Deployment orchestration |
| `deployment_management_service.py` | Multi-environment management |
| `deployment_audit_service.py` | Audit trail tracking |
| `deployment_health_monitor.py` | Health monitoring |
| `deployment_rbac_service.py` | Role-based access control |
| `auto_rollback_service.py` | Automatic rollback |
| `post_deployment_verification_service.py` | Post-deploy checks |

#### Quality Services
| Service | Purpose |
|---------|---------|
| `gate_service.py` | Quality gates and approvals |
| `quality_fabric_enforcement.py` | Quality Fabric integration |
| `quality_remediation_service.py` | Auto-remediation |

#### Template Services
| Service | Purpose |
|---------|---------|
| `rag_template_manager.py` | RAG-based retrieval |
| `template_validation_service.py` | Template validation |
| `template_versions_service.py` | Version management |
| `template_promotion_service.py` | Promotion workflow |
| `template_provenance_service.py` | Origin tracking |

#### Integration Services
| Service | Purpose |
|---------|---------|
| `jira_integration_service.py` | Jira issue tracking |
| `github_actions_client.py` | GitHub Actions integration |
| `governance_service.py` | Governance policies |
| `policy_service.py` | Policy management |

#### Monitoring Services
| Service | Purpose |
|---------|---------|
| `metrics.py` | Prometheus metrics |
| `audit_trail_service.py` | Audit logging |
| `slo_monitoring_service.py` | SLO tracking |

---

## 10. Configuration

### Environment Variables

```bash
# Main Services
MAESTRO_ENGINE_HOST=0.0.0.0
MAESTRO_ENGINE_PORT=5000
MAESTRO_BFF_HOST=0.0.0.0
MAESTRO_BFF_PORT=4001
MAESTRO_FRONTEND_URL=http://localhost:4200

# Redis
REDIS_URL=redis://localhost:6379
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_TTL=3600

# Service URLs
QUALITY_FABRIC_URL=http://localhost:8000
TEMPLATE_REGISTRY_URL=http://localhost:9600
RAG_SERVICE_URL=http://localhost:9803
MCP_SERVICE_URL=http://localhost:9800

# Orchestration
EXECUTION_MODE=parallel  # sequential|parallel|utcp|hybrid
MAX_PARALLEL_PERSONAS=4
PERSONA_TIMEOUT=300
ENABLE_MCP=true
ENABLE_RAG=true
ENABLE_QUALITY_GATES=true

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Security
JWT_SECRET=change-me-in-production
CORS_ORIGINS=http://localhost:4200,http://localhost:3000
API_KEY_ENABLED=false

# API Gateway
API_GATEWAY_PORT=8080
ENABLE_RATE_LIMITING=true
ENABLE_CIRCUIT_BREAKER=true
```

### Configuration Files (`config/`)

| File | Purpose |
|------|---------|
| `default.yaml` | Default configuration |
| `development.yaml` | Development settings |
| `production.yaml` | Production settings |
| `services.yaml` | Service registry |
| `gateway_routes.yaml` | API Gateway routing |
| `deployment_config.yaml` | Deployment settings |
| `governance_protocol.yaml` | Governance policies |
| `phase_test_mapping.yaml` | Test configuration |

### Configuration Hierarchy

1. Environment variables (highest priority)
2. `.env.{ENVIRONMENT}` file
3. `config/{environment}.yaml`
4. `config/default.yaml`
5. Code defaults (lowest priority)

---

## 11. Integration Points

### External Services

| Service | URL | Purpose |
|---------|-----|---------|
| **Quality Fabric** | `:8000` | Code validation, test generation |
| **Template Registry** | `:9600` | Enterprise templates |
| **RAG Service** | `:9803` | Vector embeddings, semantic search |
| **MCP Service** | `:9800` | Claude session management |
| **Redis** | `:6379` | Session state, caching |
| **Claude API** | External | AI model (claude-sonnet-4-20250514) |

### API Gateway Routing

```yaml
/api/v1/accelerator/*     → Unified BFF (4001)
/api/v1/guardian/*        → MAESTRO Engine (5000)
/api/v1/templates/*       → Templates Service (9600)
/api/v1/rag/*             → RAG Service (9803)
/api/v1/mcp/*             → MCP Service (9800)
/api/v1/quality/*         → Quality Fabric (8000)
/api/v1/coordinator/*     → Coordinator (8002)
/api/v1/orchestration/*   → Orchestration (8004)
```

### Port Allocation (ADR-004)

```
1000-2999:   Reserved (system/well-known)
3000-3999:   Frontend services (Grafana: 3000)
4000-4999:   Backend APIs (BFF: 4001)
5000-5999:   Core engines (MAESTRO: 5000)
6000-6999:   Reserved
7000-7999:   Reserved
8000-8999:   Infrastructure (QF: 8000, Gateway: 8080)
9000-9999:   Microservices (Prometheus: 9090, Templates: 9600)
10000+:      Development/testing
```

---

## 12. Resilience Patterns

### Circuit Breaker (ADR-006)

| State | Description |
|-------|-------------|
| **CLOSED** | Normal operation, requests pass through |
| **OPEN** | Failing, requests immediately rejected |
| **HALF_OPEN** | Testing recovery with limited requests |

**Configuration:**
- Failure threshold before opening
- Recovery timeout before half-open
- Success threshold to close

### Retry Policy

```python
retry_config = {
    "max_retries": 3,
    "initial_delay": 1.0,
    "max_delay": 30.0,
    "exponential_base": 2,
    "jitter": True
}
```

### Bulkhead Pattern

- Max concurrent requests per service
- Resource isolation
- Queue management with overflow handling

### Timeout Management

| Scope | Timeout |
|-------|---------|
| Per-persona | 300 seconds |
| Per-workflow | 900 seconds |
| Service-specific | Configurable |

---

## 13. Testing

### Test Structure (`tests/`)

| Directory | Purpose |
|-----------|---------|
| `tests/unit/` | Component-level tests |
| `tests/integration/` | Service-to-service |
| `tests/e2e/` | Complete workflow execution |
| `tests/contract/` | OpenAPI compliance |
| `tests/fixtures/` | Test data and fixtures |
| `tests/pending/` | Future implementation tests |

### Coverage Areas

- Persona loading and validation
- Workflow execution
- Session management
- DAG validation
- Dependency resolution
- API endpoints
- Quality Fabric integration
- Template retrieval

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/integration/test_workflow_execution.py

# Run with coverage
pytest --cov=src tests/

# Run E2E tests only
pytest tests/e2e/

# Ignore pending tests
pytest --ignore=tests/pending
```

### Testing Tools

```toml
[tool.poetry.dev-dependencies]
pytest = "^8.3.0"
pytest-asyncio = "^0.24.0"
pytest-cov = "^5.0.0"
testcontainers = "^4.13.1"
```

---

## 14. Deployment

### Docker Files

| Dockerfile | Service |
|------------|---------|
| `Dockerfile.base` | Base Python 3.11 image |
| `Dockerfile.gateway` | API Gateway |
| `Dockerfile.bff` | Unified BFF |
| `Dockerfile.collaboration` | Collaboration BFF |
| `Dockerfile.mcp` | MCP Service |
| `Dockerfile.rag` | RAG Service |
| `Dockerfile.coordinator` | Coordinator |
| `Dockerfile.orchestration` | Orchestration Engine |

### Docker Compose

```bash
# Development
docker-compose -f docker-compose.dev.yml up -d

# Production
docker-compose -f docker-compose.prod.yml up -d
```

### Service Ports

| Service | Port |
|---------|------|
| Grafana | 3000 |
| Frontend | 4200 |
| Unified BFF | 4001 |
| MAESTRO Engine | 5000 |
| Redis | 6379 |
| PostgreSQL | 5432 |
| Quality Fabric | 8000 |
| Coordinator | 8002 |
| Orchestration | 8004 |
| API Gateway | 8080 |
| Prometheus | 9090 |
| Templates | 9600 |
| MCP | 9800 |
| RAG | 9803 |
| Portainer | 29000 |

---

## 15. Related Repositories

| Repository | Location | Purpose |
|------------|----------|---------|
| **maestro-hive** | `/home/ec2-user/projects/maestro-platform/maestro-hive` | Central platform hub |
| **quality-fabric** | `/home/ec2-user/projects/quality-fabric` | Test generation/healing |
| **maestro-templates** | `/home/ec2-user/projects/maestro-templates` | Template library |
| **maestro-frontend** | `/home/ec2-user/projects/maestro-frontend` | React UI |
| **maestro-shared** | `/home/ec2-user/projects/maestro-shared` | Common libraries |
| **gateway** | `/home/ec2-user/projects/gateway` | API routing |

### Shared Libraries (maestro-shared)

| Package | Purpose |
|---------|---------|
| `maestro-core-api` | FastAPI utilities |
| `maestro-core-auth` | Authentication |
| `maestro-core-config` | Configuration management |
| `maestro-core-logging` | Structured logging |
| `maestro-core-db` | Database abstraction |
| `maestro-core-messaging` | Event messaging |
| `maestro-monitoring` | Observability |

---

## Architecture Decision Records

| ADR | Title | Location |
|-----|-------|----------|
| ADR-003 | API Gateway Pattern | `docs/architecture/ADR-003.md` |
| ADR-004 | Port Allocation Strategy | `docs/architecture/ADR-004.md` |
| ADR-006 | Resilience Patterns | `docs/architecture/ADR-006.md` |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Redis 6.2.14+
- Docker (optional)

### Installation

```bash
# Clone repository
git clone <repo-url>
cd maestro-engine-new

# Install dependencies
poetry install

# Configure environment
cp .env.example .env.development
# Edit .env.development with your settings

# Start Redis
docker run -d -p 6379:6379 redis:6.2

# Run MAESTRO Engine
poetry run python src/maestro_engine_app.py
```

### Verify Installation

```bash
curl http://localhost:5000/health
```

---

*Generated: December 2025*
*MAESTRO Engine v3.0.0*
