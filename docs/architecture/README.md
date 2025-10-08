# MAESTRO Engine Architecture

**Version**: 2.0
**Last Updated**: 2025-10-04
**Status**: Active

---

## Quick Links

- [Architecture Principles Implementation](./ARCHITECTURE_PRINCIPLES_IMPLEMENTATION.md) ⭐ **START HERE**
- [Architecture Decision Records](#architecture-decision-records)
- [Implementation Status](#implementation-status)
- [Validation & Enforcement](#validation--enforcement)
- [Development Guidelines](#development-guidelines)

---

## Platform Overview

**MAESTRO Engine** is the backend orchestration service for the MAESTRO AI Agent platform. It provides:

- **Guardian Mode**: Full SDLC workflow with multi-persona AI orchestration
- **Accelerator Mode BFF**: Backend for frontend rapid prototyping service
- **Persona System**: Specialized AI agents for different roles (architect, developer, QA, etc.)
- **RAG Integration**: Retrieval-augmented generation for context-aware responses
- **Template Integration**: Connection to enterprise template repository
- **Quality Integration**: Automated testing and validation via quality-fabric

---

## Architecture Decision Records

### Core ADRs (Required Reading)

| ADR | Title | Status | Priority | Summary |
|-----|-------|--------|----------|---------|
| [ADR-001](./ADR-001-service-discovery.md) | Service Discovery | ✅ Accepted | **High** | Replace hardcoded URLs with environment-based configuration |
| [ADR-004](./ADR-004-port-allocation.md) | Port Allocation Strategy | ✅ Accepted | **High** | Structured port ranges with validation |
| [ADR-006](./ADR-006-resilience-patterns.md) | Resilience Patterns | ✅ Accepted | **High** | Circuit breaker, retry, timeout, bulkhead, fallback |
| [ADR-007](./ADR-007-code-organization.md) | Code Organization | ✅ Accepted | **High** | Strict structure, cleanup automation, validation |

### Reading Guide

**For New Team Members:**
1. Start with [Architecture Principles Implementation](./ARCHITECTURE_PRINCIPLES_IMPLEMENTATION.md)
2. Read [ADR-007](./ADR-007-code-organization.md) - Code Organization (understand structure)
3. Read [ADR-006](./ADR-006-resilience-patterns.md) - Resilience Patterns (fault tolerance)
4. Browse other ADRs as needed

**For Developers:**
- [ADR-007](./ADR-007-code-organization.md) - Code organization rules
- [ADR-001](./ADR-001-service-discovery.md) - Service discovery
- [ADR-006](./ADR-006-resilience-patterns.md) - Resilience patterns
- [ADR-004](./ADR-004-port-allocation.md) - Port allocation

**For Operations:**
- [ADR-004](./ADR-004-port-allocation.md) - Port allocation
- [ADR-001](./ADR-001-service-discovery.md) - Service discovery and configuration

---

## Implementation Status

### ✅ Completed (12/14 Core Tasks)

**1. Validation & Automation Scripts** (ADR-007)
- ✅ `scripts/detect_hardcoded_urls.py` - Find hardcoded service URLs
- ✅ `scripts/validate_port_allocation.py` - Check port conflicts
- ✅ `scripts/cleanup.sh` - Automated cleanup & validation
- ✅ `scripts/find_unused_files.py` - Detect dead code
- ✅ `scripts/check_legacy_imports.py` - Block legacy imports

**2. Code Organization** (ADR-007)
- ✅ Moved `src/archived/` → `_legacy/` (repo root)
- ✅ Created `_experiments/` directory with policies
- ✅ Updated `.gitignore` with exclusion rules
- ✅ Pre-commit hooks configured (15+ hooks)

**3. Resilience Patterns** (ADR-006)
- ✅ Complete `src/resilience/` module
- ✅ Circuit Breaker implementation
- ✅ Retry with Exponential Backoff
- ✅ Timeout enforcement
- ✅ Bulkhead (concurrency limiting)
- ✅ Fallback pattern

**4. Port Allocation** (ADR-004)
- ✅ Updated `config/services.yaml` (15 services)
- ✅ Port range strategy documented
- ✅ Validation script operational

**5. Configuration Management** (ADR-001, ADR-005)
- ✅ `config/default.yaml` - Base configuration
- ✅ `config/development.yaml` - Dev overrides
- ✅ `config/production.yaml` - Production settings
- ✅ Hierarchical configuration with dynaconf

**6. Architecture Documentation**
- ✅ 4 ADRs created (ADR-001, ADR-004, ADR-006, ADR-007)
- ✅ Architecture Principles Implementation guide
- ✅ This README.md index

### ⏳ Remaining Tasks

- [ ] Create .github/workflows/code-quality.yml (CI/CD)
- [ ] Fix 10 identified files with hardcoded URLs

**Full Details**: [ARCHITECTURE_PRINCIPLES_IMPLEMENTATION.md](./ARCHITECTURE_PRINCIPLES_IMPLEMENTATION.md)

---

## Validation & Enforcement

### Pre-commit Hooks

**File**: `.pre-commit-config.yaml`

Automatically enforces on every commit:
- ✅ Code formatting (Black, line-length=100)
- ✅ Import sorting (isort)
- ✅ Linting (flake8)
- ✅ No large files (>1MB)
- ✅ No secrets
- ✅ No imports from `_legacy/` or `_experiments/`
- ✅ No hardcoded URLs
- ✅ No TODOs in production code
- ✅ Port allocation validation

**Installation**:
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files  # Test
```

### Validation Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `detect_hardcoded_urls.py` | Find hardcoded localhost URLs | `python scripts/detect_hardcoded_urls.py` |
| `validate_port_allocation.py` | Check port conflicts | `python scripts/validate_port_allocation.py` |
| `cleanup.sh` | Automated cleanup | `./scripts/cleanup.sh` |
| `find_unused_files.py` | Find dead code | `python scripts/find_unused_files.py` |
| `check_legacy_imports.py` | Block legacy imports | `python scripts/check_legacy_imports.py` |

### Run All Validations

```bash
# 1. Check code organization
./scripts/cleanup.sh

# 2. Find unused files
python scripts/find_unused_files.py

# 3. Check for hardcoded URLs
python scripts/detect_hardcoded_urls.py

# 4. Validate port allocation
python scripts/validate_port_allocation.py

# 5. Check for legacy imports
python scripts/check_legacy_imports.py

# 6. Run pre-commit hooks
pre-commit run --all-files
```

### CI/CD Validation

**Pending**: `.github/workflows/code-quality.yml`

Will check on every PR:
- ✅ Code formatting (Black)
- ✅ Import sorting (isort)
- ✅ Linting (flake8)
- ✅ Type checking (mypy)
- ✅ No TODOs in production
- ✅ No legacy imports
- ✅ No hardcoded URLs
- ✅ Port conflicts
- ✅ Tests pass

---

## Development Guidelines

### Code Structure

**Python Services**:
```
src/
├── api/          # FastAPI routes
├── models/       # Data models
├── services/     # Business logic
├── clients/      # External service clients
├── config/       # Configuration
├── resilience/   # Resilience patterns (NEW)
└── utils/        # Utilities

_legacy/          # Archived code (excluded from production)
_experiments/     # Experimental code (excluded from production)
```

### Naming Conventions

- **Python files**: `lowercase_with_underscores.py`
- **Classes**: `PascalCase`
- **Functions**: `snake_case`
- **Constants**: `UPPER_CASE`
- **Directories (Python)**: `lowercase_with_underscores/`

### Configuration Hierarchy

1. **Environment variables** (highest priority)
2. `config/{environment}.yaml`
3. `config/default.yaml`
4. Code defaults (lowest priority)

### Adding Resilience Patterns

```python
from src.resilience import (
    CircuitBreaker,
    retry_with_backoff,
    timeout,
    Bulkhead,
    with_fallback
)

# Circuit breaker for external service
circuit = CircuitBreaker(failure_threshold=5, timeout=60, name="my-service")

async def call_external_service():
    try:
        result = await circuit.call(external_api.get_data)
        return result
    except CircuitBreakerOpenError:
        # Fallback to cached data
        return get_cached_data()
```

### Testing Requirements

- **Unit tests**: >80% coverage
- **Integration tests**: Key workflows
- **E2E tests**: User journeys
- **All tests pass** before merge

---

## Port Allocation

### Port Ranges

```
3000-3999: Frontend services
4000-4999: Backend APIs (user-facing)
5000-5999: Core orchestration engines
6000-6999: Reserved
7000-7999: Reserved
8000-8999: Infrastructure services
9000-9999: Internal microservices
10000+:    Development/testing
```

### Current Allocations

| Port | Service | Category | Public |
|------|---------|----------|--------|
| 3000 | grafana | monitoring | Yes |
| 4200 | frontend | frontend | Yes |
| 4001 | unified-bff | api | No |
| 5000 | maestro-engine | engine | No |
| 5432 | postgresql | infrastructure | No |
| 6379 | redis | infrastructure | No |
| 8000 | quality-fabric | infrastructure | No |
| 8002 | coordinator | infrastructure | No |
| 8004 | orchestration | infrastructure | No |
| 8080 | api-gateway | gateway | Yes |
| 9090 | prometheus | monitoring | No |
| 9600 | templates | microservices | No |
| 9800 | mcp | microservices | No |
| 9803 | rag | microservices | No |

**Full Registry**: `config/services.yaml`

---

## Configuration Examples

### Environment Variables

```bash
# Service
ENVIRONMENT=development
MAESTRO_SERVICE_PORT=5000

# Dependencies
REDIS_URL=redis://localhost:6379/0
TEMPLATE_SERVICE_URL=http://localhost:9600
QUALITY_FABRIC_URL=http://localhost:8000

# Security
JWT_SECRET=your-secret-here

# Orchestration
EXECUTION_MODE=parallel
MAX_PARALLEL_PERSONAS=4
ENABLE_MCP=true
```

### Service Configuration

```yaml
# config/default.yaml
service:
  name: maestro-engine
  port: ${PORT:5000}

dependencies:
  redis:
    url: ${REDIS_URL:redis://localhost:6379/0}
  template_service:
    url: ${TEMPLATE_SERVICE_URL:http://localhost:9600}

orchestration:
  execution_mode: ${EXECUTION_MODE:parallel}
  max_parallel_personas: ${MAX_PARALLEL_PERSONAS:4}

# Resilience patterns configuration
resilience:
  circuit_breakers:
    template_service:
      failure_threshold: 5
      success_threshold: 2
      timeout: 60
```

---

## Related Documentation

### Architecture Documents (This Directory)

- [ARCHITECTURE_PRINCIPLES_IMPLEMENTATION.md](./ARCHITECTURE_PRINCIPLES_IMPLEMENTATION.md) - Implementation status
- [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) - Historical implementation notes
- [MCP_CACHE_ARCHITECTURE.md](./MCP_CACHE_ARCHITECTURE.md) - MCP caching system
- [RAG_CODE_REVIEW_AND_INTEGRATION_PLAN.md](./RAG_CODE_REVIEW_AND_INTEGRATION_PLAN.md) - RAG integration
- [RAG_MCP_INTEGRATION_STATUS.md](./RAG_MCP_INTEGRATION_STATUS.md) - RAG/MCP status
- [TEAM_WORKFLOW_INTEGRATION.md](./TEAM_WORKFLOW_INTEGRATION.md) - Team workflow docs
- [ORIGINAL_ARCHITECTURE.md](./ORIGINAL_ARCHITECTURE.md) - Original design (historical)

### External References

- **maestro-frontend**: `../maestro-frontend/docs/architecture/` - Frontend architecture (source of ADR templates)
- **maestro-templates**: Template repository service
- **quality-fabric**: Testing platform

---

## Deployment

### Development (Local)

```bash
# Start infrastructure
docker-compose up -d redis postgresql

# Start backend
cd maestro-engine
poetry run uvicorn src.api.main:app --reload --port 5000 &
poetry run python src.bff/main.py &

# Environment variables from .env.development
export ENVIRONMENT=development
```

### Development (Docker Compose)

```bash
docker-compose -f docker-compose.dev.yml up
```

### Production (Docker)

```bash
docker-compose -f docker-compose.prod.yml up
```

### Production (Kubernetes)

```bash
kubectl apply -f kubernetes/
```

---

## Monitoring

### Metrics (Prometheus)

- Request rate/latency
- Error rates
- Persona execution time
- Quality scores
- Circuit breaker state
- Retry attempts
- Timeout occurrences

### Logs (Structured JSON)

```json
{
  "timestamp": "2025-10-04T10:30:00Z",
  "level": "INFO",
  "service": "maestro-engine",
  "event": "persona_execution_complete",
  "persona_id": "requirement_analyst_001",
  "duration_ms": 12500
}
```

### Dashboards

- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`

---

## Roadmap

### Phase 1: Foundation ✅ COMPLETE
- [x] Create ADRs
- [x] Setup validation scripts
- [x] Implement resilience patterns
- [x] Configure pre-commit hooks
- [x] Restructure directories

### Phase 2: CI/CD Integration (In Progress)
- [ ] Create GitHub Actions workflow
- [ ] Integrate all validation checks
- [ ] Automated testing on PR

### Phase 3: URL Remediation
- [ ] Fix 10 files with hardcoded URLs
- [ ] Migrate to dynaconf settings
- [ ] Validate with detection script

### Phase 4: Production Deployment
- [ ] Deploy with resilience patterns
- [ ] Comprehensive monitoring
- [ ] Performance optimization

---

## Success Metrics

### Before Architecture Principles

- ❌ No validation scripts
- ❌ Archived code in `src/archived/`
- ❌ No pre-commit hooks
- ❌ No resilience patterns
- ❌ Incomplete port registry
- ❌ No hierarchical configuration
- ❌ 10+ files with hardcoded URLs

### After Implementation

- ✅ 5 validation scripts operational
- ✅ Archived code in `_legacy/` (proper location)
- ✅ 15+ pre-commit hooks configured
- ✅ Full resilience module (5 patterns)
- ✅ Complete port registry (15 services)
- ✅ Hierarchical config (default, dev, prod)
- ✅ 4 ADRs documented
- ⏳ CI/CD workflow (pending)

---

## Support

### Resources

- **Documentation**: This directory
- **Scripts**: `scripts/` directory
- **Configuration**: `config/` directory
- **Code**: `src/` directory

### Getting Help

- **Issues**: GitHub Issues
- **Questions**: Team slack channel
- **Architecture Questions**: Review ADRs first

---

## FAQ

**Q: Where do I put new code?**
A: Production code → `src/`, Experiments → `_experiments/`, Reference → `_legacy/`

**Q: How do I add a new service?**
A: Follow ADR-004 for port allocation, ADR-001 for service discovery, ADR-007 for structure

**Q: Where do I put experimental code?**
A: `_experiments/` directory with README explaining purpose

**Q: How do I configure for production?**
A: Set environment variables, see `config/production.yaml` for required vars

**Q: What's the deployment process?**
A: Local → Docker Compose → Kubernetes

**Q: How do I use resilience patterns?**
A: See ADR-006 and `src/resilience/` module

**Q: Why did my commit fail?**
A: Pre-commit hooks detected an issue. Fix the violation and try again.

**Q: Can I skip pre-commit hooks?**
A: No - CI/CD runs the same checks. Fix the issues instead.

---

**Maintained by**: MAESTRO Architecture Team
**Last Review**: 2025-10-04
**Next Review**: 2025-11-04
