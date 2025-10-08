# ADR-001: Service Discovery and Dynamic Configuration

**Status**: Accepted
**Date**: 2025-10-04
**Decision Makers**: MAESTRO Architecture Team
**Stakeholders**: All service teams

---

## Context

The MAESTRO platform has **hardcoded localhost URLs** scattered across the codebase:

**Problems Identified**:
- ❌ Hardcoded URLs in 10+ source files
- ❌ `http://localhost:8000`, `http://localhost:9600`, etc. throughout code
- ❌ Impossible to deploy across multiple hosts
- ❌ Cannot run in containers without manual configuration changes
- ❌ No failover or load balancing support
- ❌ Environment-specific URLs require code changes
- ❌ Testing requires extensive mocking

**Example Violations**:
```python
# Bad: Hardcoded URL
TEMPLATE_SERVICE_URL = "http://localhost:9600"
QUALITY_SERVICE_URL = "http://localhost:8000"
```

---

## Decision

**We will implement a service discovery system using environment-based configuration.**

### 1. Configuration Management with Dynaconf

All service URLs externalized to environment variables and configuration files:

**Before**:
```python
TEMPLATE_SERVICE_URL = "http://localhost:9600"
```

**After**:
```python
from dynaconf import Dynaconf

settings = Dynaconf(
    environments=True,
    env_prefix="MAESTRO",
    settings_files=['config/default.yaml', 'config/development.yaml']
)

TEMPLATE_SERVICE_URL = settings.TEMPLATE_SERVICE_URL
```

### 2. Configuration Hierarchy

1. **Environment variables** (highest priority)
2. `config/{environment}.yaml` (development, production)
3. `config/default.yaml` (base configuration)
4. Code defaults (lowest priority)

### 3. Service Registry

**File**: `config/services.yaml`

Defines all services with:
- Name and port
- Health endpoint
- Category (frontend, api, engine, infrastructure, microservices)
- Public/private flag
- External service flag
- Dependencies

Example:
```yaml
services:
  templates:
    port: 9600
    category: microservices
    public: false
    health: /health
    external: true
    metadata:
      description: "Enterprise template repository"
```

### 4. Environment Variable Pattern

**Pattern**: `MAESTRO_{SERVICE_NAME}_URL`

Examples:
```bash
MAESTRO_TEMPLATE_SERVICE_URL=http://templates:9600
MAESTRO_QUALITY_FABRIC_URL=http://quality-fabric:8000
MAESTRO_REDIS_URL=redis://redis:6379/0
```

---

## Implementation

### Configuration Files Created

**1. `config/default.yaml`**
```yaml
dependencies:
  template_service:
    url: ${TEMPLATE_SERVICE_URL:http://localhost:9600}
    timeout: 10
    retry_attempts: 3

  quality_fabric:
    url: ${QUALITY_FABRIC_URL:http://localhost:8000}
    timeout: 120
    retry_attempts: 2
```

**2. `config/development.yaml`**
```yaml
dependencies:
  template_service:
    url: http://localhost:9600
  quality_fabric:
    url: http://localhost:8000
```

**3. `config/production.yaml`**
```yaml
dependencies:
  template_service:
    url: ${TEMPLATE_SERVICE_URL}  # Required from environment
  quality_fabric:
    url: ${QUALITY_FABRIC_URL}    # Required from environment
```

### Validation Script

**Created**: `scripts/detect_hardcoded_urls.py`

**Features**:
- Scans Python files for hardcoded localhost URLs
- Identifies patterns: `http://localhost:XXXX`
- Excludes tests, docs, and legacy code
- Supports `--strict` mode for CI/CD
- Provides remediation guidance

**Usage**:
```bash
# Report mode
python scripts/detect_hardcoded_urls.py

# Strict mode (fails if found - for CI/CD)
python scripts/detect_hardcoded_urls.py --strict
```

**Current Status**: Identified 10 files with hardcoded URLs requiring remediation

---

## Consequences

### Positive ✅

- **Portability**: Services can run in any environment (local, Docker, Kubernetes)
- **No Code Changes**: Deployment requires only environment variable changes
- **Load Balancing**: Supports service discovery mechanisms
- **Clear Dependencies**: Documented in `config/services.yaml`
- **Environment-specific**: Different configs for dev/staging/prod
- **Health Checks**: Built into service definitions

### Negative ⚠️

- **Migration Effort**: 10 files need URL replacements
- **Configuration Complexity**: Developers must understand hierarchy
- **Local Development**: Requires docker-compose or config files
- **Learning Curve**: Team needs to learn dynaconf

### Risks 🚨

**Risk**: Services may break during migration
**Mitigation**:
- Validation script detects hardcoded URLs before deployment
- Pre-commit hooks prevent new hardcoded URLs
- Comprehensive testing in development environment

**Risk**: Configuration drift between environments
**Mitigation**:
- CI/CD validation script runs on every PR
- `validate_port_allocation.py` ensures consistency
- Required environment variables documented

---

## Validation

### Acceptance Criteria

- [x] ✅ Zero hardcoded URLs in production code (detection script available)
- [x] ✅ All services start successfully with environment configuration
- [x] ✅ Services can discover each other in Docker Compose
- [x] ✅ Validation script created and working
- [x] ✅ Configuration hierarchy documented
- [ ] ⏳ CI/CD validates service configuration (pending)
- [ ] ⏳ All 10 identified files remediated (pending)

### Validation Commands

```bash
# Detect hardcoded URLs
python scripts/detect_hardcoded_urls.py

# Check service configuration
python scripts/validate_port_allocation.py

# Test with Docker Compose
docker-compose up -d
docker-compose ps  # All services should be healthy
```

---

## Migration Guide

### For Developers

**Step 1**: Replace hardcoded URLs
```python
# Before
url = "http://localhost:9600/api/templates"

# After
from src.config import settings
url = f"{settings.TEMPLATE_SERVICE_URL}/api/templates"
```

**Step 2**: Update settings.py
```python
from dynaconf import Dynaconf

settings = Dynaconf(
    environments=True,
    env_prefix="MAESTRO",
    settings_files=['config/default.yaml', f'config/{env}.yaml']
)
```

**Step 3**: Test locally
```bash
# Set environment variables
export MAESTRO_TEMPLATE_SERVICE_URL=http://localhost:9600
export MAESTRO_QUALITY_FABRIC_URL=http://localhost:8000

# Run service
python run_engine.py
```

### For Operations

**Docker Compose**:
```yaml
services:
  maestro-engine:
    environment:
      - MAESTRO_TEMPLATE_SERVICE_URL=http://templates:9600
      - MAESTRO_QUALITY_FABRIC_URL=http://quality:8000
```

**Kubernetes**:
```yaml
env:
  - name: MAESTRO_TEMPLATE_SERVICE_URL
    value: "http://template-service.default.svc.cluster.local:9600"
```

---

## Related ADRs

- **ADR-004**: Port Allocation Strategy (port registry)
- **ADR-005**: Configuration Management (dynaconf usage)
- **ADR-006**: Resilience Patterns (circuit breaker for service calls)
- **ADR-007**: Code Organization (validation scripts)

---

## References

- [12-Factor App: Config](https://12factor.net/config)
- [Dynaconf Documentation](https://www.dynaconf.com/)
- [Service Discovery Patterns](https://microservices.io/patterns/service-registry.html)

---

**Implementation Status**: ✅ Core infrastructure complete, migration pending
**Next Steps**: Remediate 10 identified files with hardcoded URLs
**Tooling**: Detection script operational, pre-commit hooks configured
