# ADR-003: API Gateway Pattern

**Status**: Accepted ✅ **IMPLEMENTING NOW**
**Date**: 2025-10-04
**Decision Makers**: MAESTRO Architecture Team
**Stakeholders**: All service teams, frontend team, operations

---

## Context

The MAESTRO platform has **point-to-point service communication** with no unified interface:

**Current Architecture**:
```
Frontend (Port 4200)
    ↓ (direct connections)
    ├─→ Unified BFF (Port 4001) ────→ Accelerator Mode
    ├─→ Maestro Engine API (Port 5000) ──→ Guardian Mode
    ├─→ Template Registry (Port 9600) ──→ Templates
    └─→ Quality Fabric (Port 8000) ──→ Testing

Services (direct service-to-service calls)
    Quality Fabric (8000)
        ↓ (hardcoded: http://templates:9600)
        └─→ Templates Service

    Maestro Engine (5000)
        ↓ (hardcoded: http://quality-fabric:8000)
        └─→ Quality Fabric
```

**Current State - Point-to-Point Communication**:
```python
# quality-fabric calling templates directly
templates_url = "http://localhost:9600/api/templates"
response = requests.get(templates_url)

# maestro-engine calling quality-fabric directly
quality_url = "http://localhost:8000/api/test"
response = requests.post(quality_url)
```

**Problems**:
- ❌ **Services have hardcoded URLs to other services** (ADR-001 violation)
- ❌ **No service discovery** - services must know exact URLs/ports
- ❌ **No centralized resilience** - each service implements own retry/circuit breaker
- ❌ **No unified authentication** - auth duplicated across services
- ❌ **No rate limiting** - services can overwhelm each other
- ❌ **No unified logging** - hard to trace cross-service requests
- ❌ **CORS duplicated** - each service configures separately
- ❌ **No circuit breakers** - cascading failures possible
- ❌ **Difficult to monitor** - no centralized metrics
- ❌ **Hard to test** - must mock each service dependency

---

## Decision

**We will implement an API Gateway as a Service Mesh / Communication Framework for ALL inter-service communication.**

**Key Principle**: Services NEVER call each other directly. ALL communication goes through the gateway.

### 1. Gateway Architecture

```
┌─────────────────────────────────────────────────┐
│         External Clients                         │
│   (Frontend, Mobile, External APIs)             │
└──────────────┬───────────────────────────────────┘
               │ HTTPS (443) / HTTP (8080)
               ▼
┌──────────────────────────────────────────────────┐
│         API Gateway (Port 8080)                  │
│         maestro-engine/src/gateway/              │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │  Cross-Cutting Concerns                    │ │
│  │  - Service Discovery                       │ │
│  │  - Authentication (JWT validation)         │ │
│  │  - Rate Limiting (per client/endpoint)     │ │
│  │  - CORS (centralized)                      │ │
│  │  - Circuit Breaker (ADR-006)               │ │
│  │  - Request Logging & Tracing               │ │
│  │  - Response Caching                        │ │
│  │  - Retry with Backoff                      │ │
│  │  - Load Balancing                          │ │
│  │  - Metrics & Monitoring                    │ │
│  └────────────────────────────────────────────┘ │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │  Routing Rules (config/gateway_routes.yaml)│ │
│  │  /api/v1/accelerator/*  → BFF (4001)       │ │
│  │  /api/v1/guardian/*     → Engine (5000)    │ │
│  │  /api/v1/templates/*    → Templates (9600) │ │
│  │  /api/v1/quality/*      → Quality (8000)   │ │
│  │  /api/v1/rag/*          → RAG (9803)       │ │
│  │  /ws/*                  → WebSocket Proxy  │ │
│  └────────────────────────────────────────────┘ │
└──────┬──────────┬──────────┬──────────┬──────────┘
       │          │          │          │
       ▼          ▼          ▼          ▼
┌─────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐
│ Quality │ │Templates│ │ Maestro  │ │   BFF    │
│ Fabric  │ │ Service │ │  Engine  │ │ Service  │
│  :8000  │ │  :9600  │ │  :5000   │ │  :4001   │
│         │ │         │ │          │ │          │
│  Uses   │ │  Uses   │ │  Uses    │ │  Uses    │
│ Gateway │ │ Gateway │ │ Gateway  │ │ Gateway  │
│  Client │ │  Client │ │  Client  │ │  Client  │
└─────────┘ └─────────┘ └──────────┘ └──────────┘
     ▲                         │
     │ (via gateway)           │ (via gateway)
     └─────────────────────────┘

Example: Quality Fabric → Templates
  quality-fabric calls: gateway.call("templates", "/search")
    ↓
  Gateway routes to: http://templates:9600/search
    ↓
  Returns response with resilience (retry, circuit breaker, etc.)
```

### 2. Technology Choice

**Selected: FastAPI-based Gateway (Integrated in maestro-engine)**

**Rationale**:
- ✅ Already using FastAPI across the platform
- ✅ Python expertise in team
- ✅ Easy integration with existing services
- ✅ Full control over features
- ✅ Lightweight and performant
- ✅ Can reuse existing resilience patterns (ADR-006)
- ✅ No additional repository needed

**Alternatives Considered**:
- ❌ **Kong**: Too heavy, requires PostgreSQL, learning curve
- ❌ **Envoy**: Complex configuration, overkill for current scale
- ❌ **Separate Gateway Service**: Extra deployment complexity
- ✅ **Integrated in maestro-engine**: Simpler deployment, shared code

### 3. Implementation Structure

```
maestro-engine/
├── src/
│   ├── gateway/                    # NEW: API Gateway
│   │   ├── __init__.py
│   │   ├── main.py                # Gateway FastAPI app
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py           # JWT validation
│   │   │   ├── rate_limit.py     # Rate limiting
│   │   │   ├── cors.py           # CORS handling
│   │   │   ├── logging.py        # Request logging
│   │   │   └── cache.py          # Response caching
│   │   ├── routing/
│   │   │   ├── __init__.py
│   │   │   ├── router.py         # Dynamic routing
│   │   │   └── proxy.py          # HTTP/WebSocket proxy
│   │   └── models.py             # Gateway models
│   │
│   ├── resilience/                 # Reuse ADR-006 patterns
│   │   └── ...
│   │
│   ├── api/                        # Existing API (port 5000)
│   ├── bff/                        # Existing BFF (port 4001)
│   └── ...
│
└── config/
    ├── gateway_routes.yaml         # NEW: Route definitions
    └── ...
```

### 4. Route Configuration

**File**: `config/gateway_routes.yaml`

```yaml
# API Gateway Route Configuration
# Part of ADR-003: API Gateway Pattern

version: 1.0
gateway:
  port: 8080
  host: 0.0.0.0
  title: "MAESTRO API Gateway"
  version: "1.0.0"

routes:
  # Accelerator Mode (BFF Service)
  - path: /api/v1/accelerator/*
    methods: [GET, POST, PUT, DELETE, PATCH]
    backend: ${ACCELERATOR_SERVICE_URL:http://localhost:4001}
    strip_path: /api/v1/accelerator
    auth_required: true
    rate_limit: 100/minute
    timeout: 30
    circuit_breaker:
      enabled: true
      failure_threshold: 5

  # Guardian Mode (Engine API)
  - path: /api/v1/guardian/*
    methods: [GET, POST]
    backend: ${GUARDIAN_SERVICE_URL:http://localhost:5000}
    strip_path: /api/v1/guardian
    auth_required: true
    rate_limit: 20/minute  # Lower for expensive operations
    timeout: 300  # 5 minutes for workflows
    circuit_breaker:
      enabled: true
      failure_threshold: 3

  # Templates Service
  - path: /api/v1/templates/*
    methods: [GET, POST, PUT, DELETE]
    backend: ${TEMPLATE_SERVICE_URL:http://localhost:9600}
    strip_path: /api/v1/templates
    auth_required: true
    rate_limit: 200/minute
    timeout: 10
    cache:
      enabled: true
      ttl: 300  # 5 minutes for GET requests
    circuit_breaker:
      enabled: true
      failure_threshold: 5

  # Quality Fabric
  - path: /api/v1/quality/*
    methods: [GET, POST]
    backend: ${QUALITY_FABRIC_URL:http://localhost:8000}
    strip_path: /api/v1/quality
    auth_required: true
    rate_limit: 50/minute
    timeout: 120
    circuit_breaker:
      enabled: true
      failure_threshold: 3

  # Health Check (Public)
  - path: /api/v1/health
    methods: [GET]
    handler: health_check
    auth_required: false

  # API Documentation (Public)
  - path: /api/v1/docs
    methods: [GET]
    handler: api_docs
    auth_required: false

# WebSocket routes
websockets:
  - path: /ws/accelerator/{session_id}
    backend: ${ACCELERATOR_SERVICE_URL:http://localhost:4001}
    auth_required: true

# CORS configuration
cors:
  allow_origins:
    - http://localhost:4200  # Frontend dev
    - http://localhost:3000  # Grafana
  allow_credentials: true
  allow_methods: [GET, POST, PUT, DELETE, PATCH, OPTIONS]
  allow_headers: ["*"]

# Rate limiting
rate_limiting:
  storage: redis  # Use Redis for distributed rate limiting
  redis_url: ${REDIS_URL:redis://localhost:6379/1}
  default_limit: 100/minute
```

---

## Implementation

### Phase 1: Core Gateway ✅ IN PROGRESS

**Files Created**:
- `src/gateway/main.py` - FastAPI gateway application
- `src/gateway/middleware/` - Auth, rate limiting, CORS, logging
- `src/gateway/routing/` - Dynamic routing and proxying
- `config/gateway_routes.yaml` - Route configuration

**Startup**:
```bash
# Start API Gateway on port 8080
uvicorn src.gateway.main:app --port 8080 --reload
```

### Phase 2: Middleware Stack

**Order** (matters!):
1. **Logging** - Log all requests
2. **CORS** - Handle cross-origin requests
3. **Rate Limiting** - Prevent abuse
4. **Authentication** - JWT validation
5. **Circuit Breaker** - Fail fast for down services
6. **Caching** - Cache GET responses
7. **Routing** - Proxy to backend services

### Phase 3: Frontend Integration

**Before** (maestro-frontend):
```typescript
// src/config/api.ts
export const API_CONFIG = {
  ACCELERATOR_API: 'http://localhost:4001',
  MAESTRO_ENGINE_API: 'http://localhost:5000',
  GUARDIAN_API: 'http://localhost:5001',
  DASHBOARD_API: 'http://localhost:9900',
};
```

**After** (maestro-frontend):
```typescript
// src/config/api.ts
export const API_CONFIG = {
  GATEWAY_URL: import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8080',
};

// All API calls go through gateway
const baseURL = `${API_CONFIG.GATEWAY_URL}/api/v1`;

// Examples:
// GET ${baseURL}/accelerator/sessions
// POST ${baseURL}/guardian/workflows
// GET ${baseURL}/templates/search
```

**Frontend Environment**:
```bash
# .env.development
VITE_API_GATEWAY_URL=http://localhost:8080

# .env.production
VITE_API_GATEWAY_URL=https://api.maestro.com
```

---

## Consequences

### Positive ✅

- **Single Entry Point**: Frontend only needs one URL
- **Centralized Security**: Auth, CORS, rate limiting in one place
- **Service Abstraction**: Backend changes don't affect frontend
- **Easier Monitoring**: All traffic goes through one point
- **API Versioning**: Support v1, v2, etc.
- **Circuit Breaker**: Reuses ADR-006 resilience patterns
- **Response Caching**: Improves performance
- **Request Logging**: Better debugging
- **Production Ready**: Follows industry best practices

### Negative ⚠️

- **Single Point of Failure**: Requires HA setup in production
- **Additional Hop**: Slight latency increase (~2-5ms)
- **Resource Usage**: Gateway needs CPU/memory
- **Deployment Complexity**: One more component to manage

### Risks 🚨

**Risk**: Gateway down = entire platform down
**Mitigation**:
- Deploy 2+ gateway instances behind load balancer
- Aggressive health checks and auto-restart
- Frontend can temporarily fall back to direct URLs (feature flag)

**Risk**: Gateway becomes bottleneck
**Mitigation**:
- Horizontal scaling (multiple instances)
- Connection pooling
- Response caching
- Load testing before production

**Risk**: Breaking existing integrations
**Mitigation**:
- Gradual migration (feature flag in frontend)
- Both gateway and direct access work during transition
- 4-week migration timeline

---

## Migration Strategy

### Week 1: Development (Current)
- ✅ Create gateway implementation
- ✅ Configure routes
- ✅ Test locally with frontend
- Deploy to dev environment

### Week 2: Testing
- Integration testing
- Load testing (1000+ req/s)
- Security testing
- Frontend team validates

### Week 3: Gradual Rollout
- Deploy to staging
- Frontend feature flag: `USE_GATEWAY=true` (default: false)
- 10% of traffic → gateway
- Monitor metrics closely
- Rollback capability ready

### Week 4: Full Migration
- 100% of traffic → gateway
- Remove direct service URLs from frontend
- Update firewall rules (services only accept gateway traffic)
- Remove feature flag

### Rollback Plan

**Frontend Feature Flag**:
```typescript
// Temporary during migration
const USE_GATEWAY = import.meta.env.VITE_USE_GATEWAY === 'true';

const API_BASE = USE_GATEWAY
  ? 'http://localhost:8080/api/v1'
  : {
      accelerator: 'http://localhost:4001',
      guardian: 'http://localhost:5000',
      // ...
    };
```

---

## Deployment

### Docker Compose (Development)

```yaml
# docker-compose.dev.yml
services:
  # API Gateway (NEW)
  gateway:
    build:
      context: .
      dockerfile: Dockerfile.gateway
    ports:
      - "8080:8080"
    environment:
      - ACCELERATOR_SERVICE_URL=http://unified-bff:4001
      - GUARDIAN_SERVICE_URL=http://maestro-engine:5000
      - TEMPLATE_SERVICE_URL=http://templates:9600
      - QUALITY_FABRIC_URL=http://quality-fabric:8000
      - REDIS_URL=redis://redis:6379/1
    depends_on:
      - unified-bff
      - maestro-engine
      - redis
    networks:
      - maestro-network

  # Existing services...
  unified-bff:
    ports:
      - "4001:4001"  # Keep for direct access during migration
    networks:
      - maestro-network

  maestro-engine:
    ports:
      - "5000:5000"  # Keep for direct access during migration
    networks:
      - maestro-network
```

### Kubernetes (Production)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: maestro-gateway
spec:
  replicas: 3  # High availability
  selector:
    matchLabels:
      app: maestro-gateway
  template:
    metadata:
      labels:
        app: maestro-gateway
    spec:
      containers:
      - name: gateway
        image: maestro-gateway:1.0.0
        ports:
        - containerPort: 8080
        env:
        - name: ACCELERATOR_SERVICE_URL
          value: "http://unified-bff:4001"
        - name: GUARDIAN_SERVICE_URL
          value: "http://maestro-engine:5000"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: maestro-gateway
spec:
  type: LoadBalancer
  selector:
    app: maestro-gateway
  ports:
  - port: 443
    targetPort: 8080
    protocol: TCP
```

---

## Monitoring & Observability

### Metrics

```python
from prometheus_client import Counter, Histogram

# Request metrics
gateway_requests_total = Counter(
    'gateway_requests_total',
    'Total gateway requests',
    ['method', 'path', 'status']
)

gateway_request_duration = Histogram(
    'gateway_request_duration_seconds',
    'Gateway request duration',
    ['method', 'backend']
)

# Circuit breaker metrics (from ADR-006)
circuit_breaker_state = Gauge(
    'gateway_circuit_breaker_state',
    'Circuit breaker state',
    ['backend']
)
```

### Logging

```json
{
  "timestamp": "2025-10-04T10:30:00Z",
  "level": "INFO",
  "service": "maestro-gateway",
  "event": "request_proxied",
  "method": "POST",
  "path": "/api/v1/guardian/workflows",
  "backend": "http://maestro-engine:5000",
  "duration_ms": 145,
  "status": 200,
  "user_id": "user123"
}
```

---

## Validation

### Acceptance Criteria

- [ ] ✅ All API traffic can flow through gateway
- [ ] ✅ Authentication enforced on protected endpoints
- [ ] ✅ Rate limiting prevents abuse
- [ ] ✅ Circuit breaker prevents cascading failures
- [ ] ✅ WebSocket connections properly proxied
- [ ] ✅ Response times < 50ms overhead
- [ ] ✅ Gateway handles 1000+ req/s
- [ ] ✅ Frontend successfully integrates
- [ ] ✅ Health checks operational

### Testing

```bash
# Load test
k6 run scripts/load_test_gateway.js

# Integration test
pytest tests/gateway/test_integration.py

# Frontend integration
cd ../maestro-frontend
npm run test:gateway-integration
```

---

## Related ADRs

- **ADR-001**: Service Discovery (gateway uses env-based service URLs)
- **ADR-004**: Port Allocation (gateway on port 8080)
- **ADR-006**: Resilience Patterns (gateway uses circuit breaker, retry, timeout)
- **ADR-007**: Code Organization (gateway in src/gateway/)

---

## References

- [API Gateway Pattern](https://microservices.io/patterns/apigateway.html)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/deployment/)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Rate Limiting Strategies](https://cloud.google.com/architecture/rate-limiting-strategies-techniques)

---

**Implementation Status**: 🚧 **IN PROGRESS**
**Target Completion**: Week 1 (Core), Week 4 (Full Migration)
**Frontend Coordination**: Required for migration
**Next Steps**: Implement gateway code, test with frontend, deploy to dev
