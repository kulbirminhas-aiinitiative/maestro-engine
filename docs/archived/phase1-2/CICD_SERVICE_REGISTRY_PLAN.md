# CI/CD & Service Registry Implementation Plan
**Date**: 2025-10-01
**Project**: MAESTRO Engine
**Status**: Planning Complete - Ready for Implementation

## Executive Summary

Based on analysis of existing MAESTRO V2 infrastructure, we have:
- ✓ Existing CI/CD in maestro-v2 (.github/workflows/, cicd/)
- ✓ Docker Compose configurations
- ✓ Service architecture patterns
- ✗ No service registry (Consul/etcd) - need to implement
- ✗ No maestro-engine specific CI/CD - need to create

## Current State Analysis

### Existing Infrastructure (maestro-v2)
```
maestro-v2/
├── .github/workflows/          # 11 GitHub Actions workflows
├── cicd/                        # CI/CD architecture docs
├── docker-compose.yml           # Microservices setup
├── docker-compose.dev.yml       # Dev environment
├── docker-compose.prod.yml      # Prod environment
└── services/                    # Individual service dirs
```

### Existing Services in V2
1. orchestration-gateway :8000
2. intelligence-service :9501
3. template-registry-service :9503
4. execution-service (port varies)
5. quality-service (port varies)
6. Infrastructure: RabbitMQ, Redis, PostgreSQL, MongoDB

## Proposed maestro-engine Architecture

### Service Registry Strategy

**Option 1: Lightweight Python Registry** (RECOMMENDED)
```python
# Built-in service registry using Redis
- Fast, simple, no new dependencies
- Redis already in tech stack
- Python client library available
- Service health checks built-in
```

**Option 2: Consul** (Enterprise-grade)
```
- Full service mesh capabilities
- Built-in health checks
- DNS integration
- Requires separate installation
```

**Option 3: File-based Registry** (Simplest)
```
- JSON config file with service URLs
- Environment variable overrides
- No external dependencies
- Limited health checking
```

**DECISION**: Start with Option 3 (File-based), migrate to Option 1 (Redis) when Redis is added

### Services to Deploy

```
┌─────────────────────────────────────────────────────┐
│                Service Coordinator                  │
│                   Port: 8002                        │
│        (API Gateway + Service Discovery)            │
└────────────────┬────────────────────────────────────┘
                 │
     ┌───────────┴───────────────┐
     │                           │
┌────▼─────┐           ┌─────────▼────────┐
│   MCP    │           │  Orchestration   │
│ Service  │           │     Gateway      │
│Port: 9800│           │   Port: 8004     │
│          │           │                  │
│• Sessions│◄──────────┤• Workflow        │
│• Cache   │           │  Routing         │
│• Audit   │           │• Coordination    │
└────┬─────┘           └────────┬─────────┘
     │                          │
     │     ┌────────────┐       │
     └────►│    RAG     │◄──────┘
           │  Service   │
           │ Port: 9803 │
           └──────┬─────┘
                  │
       ┌──────────▼──────────┐
       │   Template Service  │
       │     Port: 8001      │
       │   (Already running) │
       └─────────────────────┘
```

## Implementation Plan

### Phase 1: Service Registry (Week 1, Days 1-2)

#### 1.1 Create Service Registry Module
```python
# File: src/registry/service_registry.py
class ServiceRegistry:
    - register_service(name, url, health_endpoint)
    - deregister_service(name)
    - get_service(name) -> ServiceInfo
    - get_all_services() -> List[ServiceInfo]
    - health_check() -> Dict[str, bool]
```

#### 1.2 Configuration File
```yaml
# File: config/services.yaml
services:
  coordinator:
    port: 8002
    health: /health
  mcp:
    port: 9800
    health: /health
  orchestration:
    port: 8004
    health: /health
  rag:
    port: 9803
    health: /health
  templates:
    port: 8001
    health: /health
    external: true
```

#### 1.3 Environment Override
```.env
MAESTRO_MCP_SERVICE_URL=http://localhost:9800
MAESTRO_ORCHESTRATION_SERVICE_URL=http://localhost:8004
MAESTRO_RAG_SERVICE_URL=http://localhost:9803
MAESTRO_TEMPLATE_SERVICE_URL=http://localhost:8001
```

### Phase 2: Docker Configuration (Week 1, Days 3-4)

#### 2.1 Multi-stage Dockerfiles
```
maestro-engine/
├── Dockerfile.coordinator      # Main API gateway
├── Dockerfile.mcp              # MCP service
├── Dockerfile.orchestration    # Orchestration gateway
├── Dockerfile.rag              # RAG service
└── Dockerfile.base             # Shared base image
```

#### 2.2 Docker Compose for Development
```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  coordinator:
    build:
      dockerfile: Dockerfile.coordinator
    ports: ["8002:8002"]
    environment:
      - ENVIRONMENT=development
  mcp:
    build:
      dockerfile: Dockerfile.mcp
    ports: ["9800:9800"]
  orchestration:
    build:
      dockerfile: Dockerfile.orchestration
    ports: ["8004:8004"]
  rag:
    build:
      dockerfile: Dockerfile.rag
    ports: ["9803:9803"]
```

#### 2.3 Docker Compose for Production
```yaml
# docker-compose.prod.yml
- Health checks
- Resource limits
- Restart policies
- Volume mounts
- Networks
```

### Phase 3: CI/CD Pipeline (Week 1, Days 4-5)

#### 3.1 GitHub Actions Workflows

**File**: `.github/workflows/ci.yml`
```yaml
name: CI Pipeline
on: [push, pull_request]
jobs:
  test:
    - Python 3.11 setup
    - Poetry install
    - Run pytest
    - Code coverage

  lint:
    - black --check
    - flake8
    - mypy

  integration-test:
    - Docker Compose up
    - API health checks
    - Service communication tests
```

**File**: `.github/workflows/deploy.yml`
```yaml
name: Deploy Pipeline
on:
  push:
    branches: [main]
jobs:
  build:
    - Build Docker images
    - Tag with version
    - Push to registry

  deploy-dev:
    - Deploy to dev environment
    - Run smoke tests

  deploy-prod:
    - Manual approval required
    - Deploy to production
    - Run comprehensive tests
```

#### 3.2 Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
  - repo: https://github.com/pycqa/flake8
  - repo: https://github.com/pre-commit/pre-commit-hooks
```

### Phase 4: Health Checks & Monitoring (Week 1, Day 5)

#### 4.1 Service Health Endpoints
```python
# Each service exposes:
GET /health          # Basic health
GET /health/live     # Liveness probe
GET /health/ready    # Readiness probe
GET /health/detailed # Full diagnostics
```

#### 4.2 Monitoring Stack
```yaml
# docker-compose.monitoring.yml
services:
  prometheus:
    - Scrape metrics from all services
  grafana:
    - Dashboards for each service
  loki:
    - Log aggregation
```

### Phase 5: Deployment Automation (Week 2)

#### 5.1 Deployment Scripts
```bash
# scripts/deploy.sh
- Check prerequisites
- Build images
- Run migrations
- Deploy services
- Health check verification
- Rollback on failure
```

#### 5.2 Service Start/Stop Scripts
```bash
scripts/
├── start_all.sh           # Start all services
├── stop_all.sh            # Stop all services
├── restart_service.sh     # Restart individual service
└── health_check.sh        # Check all services health
```

## Service Registry API Design

### Register Service
```python
POST /registry/services
{
  "name": "mcp-service",
  "url": "http://localhost:9800",
  "health_endpoint": "/health",
  "metadata": {
    "version": "1.0.0",
    "environment": "development"
  }
}
```

### Get Service
```python
GET /registry/services/mcp-service
Response:
{
  "name": "mcp-service",
  "url": "http://localhost:9800",
  "status": "healthy",
  "last_heartbeat": "2025-10-01T08:00:00Z"
}
```

### Health Check All
```python
GET /registry/health
Response:
{
  "coordinator": {"status": "healthy", "latency_ms": 2},
  "mcp": {"status": "healthy", "latency_ms": 5},
  "orchestration": {"status": "healthy", "latency_ms": 3},
  "rag": {"status": "degraded", "latency_ms": 150},
  "templates": {"status": "healthy", "latency_ms": 10}
}
```

## Dependency Management

### Service Dependencies
```yaml
# config/dependencies.yaml
mcp:
  depends_on:
    - coordinator  # For service registration
orchestration:
  depends_on:
    - coordinator
    - mcp
rag:
  depends_on:
    - coordinator
    - mcp
```

### Shared Libraries
```
All services depend on:
- maestro-core-api (v1.0.0)
- maestro-core-logging (v1.0.0)
- maestro-core-config (v1.0.0)

Path: /home/ec2-user/projects/shared/packages/
```

## Testing Strategy

### Unit Tests
- Each service has its own test suite
- Run in isolation
- Mock external dependencies

### Integration Tests
- Docker Compose test environment
- Real service-to-service communication
- End-to-end workflows

### Load Tests
- Locust or k6 for load testing
- Test each service endpoint
- Test inter-service communication

## Rollout Strategy

### Week 1: Foundation
- Day 1-2: Service registry implementation
- Day 3-4: Docker configurations
- Day 4-5: CI/CD pipelines
- Day 5: Health checks & monitoring

### Week 2: Services Extraction
- Day 1: Extract MCP service
- Day 2: Extract Orchestration gateway
- Day 3: Create RAG service wrapper
- Day 4: Integration testing
- Day 5: Documentation & deployment automation

### Week 3: Production Readiness
- Comprehensive testing
- Performance tuning
- Security hardening
- Documentation review

## Migration from Current State

### Step 1: Add Registry to Current run_engine.py
```python
# Keep current monolith running
# Add service registry alongside
# Register current endpoint as "coordinator"
```

### Step 2: Extract Services One by One
```
1. MCP service (least dependencies)
2. RAG service (isolated functionality)
3. Orchestration gateway (complex dependencies)
```

### Step 3: Update Coordinator
```
# Becomes API gateway
# Routes to individual services
# Maintains backward compatibility
```

## Success Criteria

✅ All services independently deployable
✅ Service registry functioning with health checks
✅ CI/CD pipeline green on all PRs
✅ Docker Compose up starts all services
✅ < 5 seconds to detect service failure
✅ < 30 seconds to auto-restart failed service
✅ Zero-downtime deployments
✅ Automated rollback on failure
✅ Comprehensive monitoring dashboards

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Service discovery failures | High | Fallback to static config |
| Inter-service communication latency | Medium | Implement caching, async calls |
| Docker build time | Medium | Multi-stage builds, layer caching |
| Test flakiness | Low | Retry logic, better test isolation |

## Next Steps

1. **Approve this plan** ✓
2. **Create service registry module** (2 hours)
3. **Create Docker configurations** (4 hours)
4. **Setup CI/CD pipeline** (4 hours)
5. **Extract first service (MCP)** (6 hours)

**Total Estimated Time**: 2-3 weeks for full implementation

---

**Ready to proceed?** The foundation (service registry + CI/CD) can be completed in 2 days, then services can be extracted incrementally without breaking existing functionality.
