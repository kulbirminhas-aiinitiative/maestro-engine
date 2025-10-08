# MAESTRO API Gateway

**Version**: 1.0.0
**Status**: Active
**Part of**: [ADR-003: API Gateway Pattern](../../docs/architecture/ADR-003-api-gateway.md)

---

## Overview

The MAESTRO API Gateway is a **Service Mesh / Communication Framework** for ALL inter-service communication in the MAESTRO platform.

**Key Principle**: **Services NEVER call each other directly. ALL communication goes through the gateway.**

### Purpose

1. **External Client Entry Point** - Single entry for frontend, mobile, external APIs
2. **Service Mesh** - Framework for inter-service communication
3. **Centralized Resilience** - Circuit breakers, retries, timeouts for all services

### Features

The gateway provides:

- **Centralized Authentication** - JWT validation
- **Rate Limiting** - Per client/endpoint token bucket algorithm
- **CORS Handling** - Configurable cross-origin policies
- **Circuit Breaker** - Prevent cascading failures
- **Request/Response Logging** - Structured JSON logging
- **Response Caching** - Reduce backend load
- **Dynamic Routing** - Route to backend services
- **WebSocket Proxying** - Real-time communication support

---

## Quick Start

### Local Development

```bash
# Start gateway with hot reload
./start_gateway.sh --reload

# Gateway will be available at:
# http://localhost:8080
```

### Docker

```bash
# Development
docker-compose -f docker-compose.dev.yml up gateway

# Production
docker-compose -f docker-compose.prod.yml up -d gateway
```

### Direct Python

```bash
# Install dependencies
pip install -r requirements.txt

# Run gateway
python -m uvicorn src.gateway.main:app --port 8080 --host 0.0.0.0
```

---

## Service-to-Service Communication

**All services must use the Gateway Client SDK for inter-service communication.**

### Gateway Client SDK

```python
from src.gateway.client import GatewayClient

# Initialize client
gateway = GatewayClient(service_name="my-service")

# Call another service (async)
response = await gateway.call(
    service="templates",
    path="/api/search",
    method="POST",
    json={"query": "authentication"}
)

# Call another service (sync)
response = gateway.call_sync(
    service="quality",
    path="/api/test",
    method="POST",
    json={"code": "..."}
)
```

### Example: Quality Fabric → Templates

```python
# quality-fabric/src/services/template_service.py
from src.gateway.client import GatewayClient

class TemplateService:
    def __init__(self):
        self.gateway = GatewayClient(service_name="quality-fabric")

    def search_templates(self, query: str):
        # ✅ Via gateway (correct)
        response = self.gateway.call_sync(
            "templates",
            "/api/search",
            method="POST",
            json={"query": query}
        )
        return response.json()

    # ❌ NEVER do this:
    # requests.get("http://templates:9600/api/search")
```

### Service Integration Examples

See complete examples:
- [Quality Fabric Integration](../../examples/gateway_integration_quality_fabric.py)
- [Templates Service Integration](../../examples/gateway_integration_templates.py)
- [Service Integration Guide](../../docs/architecture/SERVICE_INTEGRATION_GUIDE.md)

---

## Architecture

### Middleware Stack

Requests flow through middleware in this order:

```
Request
  ↓
1. LoggingMiddleware      - Log request details
  ↓
2. CORSMiddleware         - Handle CORS headers
  ↓
3. RateLimitMiddleware    - Check rate limits
  ↓
4. AuthMiddleware         - Validate JWT (if required)
  ↓
5. CircuitBreakerMiddleware - Check backend health
  ↓
6. CacheMiddleware        - Check cache (GET only)
  ↓
7. ProxyRouter            - Forward to backend
  ↓
Response
```

### Directory Structure

```
src/gateway/
├── __init__.py              # Module initialization
├── main.py                  # FastAPI application
├── middleware/              # Middleware components
│   ├── __init__.py
│   ├── auth.py              # JWT authentication
│   ├── cache.py             # Response caching
│   ├── circuit_breaker.py   # Circuit breaker pattern
│   ├── logging.py           # Structured logging
│   └── rate_limit.py        # Token bucket rate limiting
└── routing/                 # Routing components
    ├── __init__.py
    ├── proxy.py             # HTTP/WebSocket proxy
    └── router.py            # Route matching
```

---

## Configuration

### Gateway Routes (`config/gateway_routes.yaml`)

```yaml
routes:
  - path: /api/v1/accelerator/*
    backend: http://localhost:4001
    rate_limit: 100/minute
    requires_auth: false
    cache_ttl: 0

  - path: /api/v1/guardian/*
    backend: http://localhost:5000
    rate_limit: 20/minute
    requires_auth: false
    cache_ttl: 0

  # ... more routes
```

**Route Configuration**:
- `path`: URL path pattern (supports `*` wildcard)
- `backend`: Backend service URL (supports environment variables)
- `rate_limit`: Rate limit (format: `count/unit`)
- `requires_auth`: Whether JWT token is required
- `cache_ttl`: Cache TTL in seconds (0 = no cache)

### Environment Variables

```bash
# Backend service URLs
BFF_SERVICE_URL=http://localhost:4001
MAESTRO_ENGINE_URL=http://localhost:5000
TEMPLATE_SERVICE_URL=http://localhost:9600
RAG_SERVICE_URL=http://localhost:9803
MCP_SERVICE_URL=http://localhost:9800
QUALITY_FABRIC_URL=http://localhost:8000
COORDINATOR_SERVICE_URL=http://localhost:8002
ORCHESTRATION_SERVICE_URL=http://localhost:8004

# Frontend configuration
FRONTEND_URL=http://localhost:4200

# Security
JWT_SECRET=your-secret-here

# Gateway configuration
GATEWAY_PORT=8080
GATEWAY_HOST=0.0.0.0
LOG_LEVEL=info
```

---

## Usage Examples

### Frontend Integration

```typescript
// Configure base URL to gateway
const API_BASE_URL = 'http://localhost:8080';

// Accelerator Mode API calls
fetch(`${API_BASE_URL}/api/v1/accelerator/projects`, {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json',
  }
});

// Guardian Mode API calls
fetch(`${API_BASE_URL}/api/v1/guardian/workflows`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer your-jwt-token',  // If auth required
  },
  body: JSON.stringify({ workflow: 'full_sdlc' })
});

// WebSocket connections
const ws = new WebSocket(`ws://localhost:8080/ws/guardian/status`);
```

### Health Checks

```bash
# Basic health check
curl http://localhost:8080/health
# Response: {"status":"healthy","service":"api-gateway","version":"1.0.0"}

# Readiness check (checks all backends)
curl http://localhost:8080/health/ready
# Response: {"status":"ready","backends":{...}}

# List registered routes
curl http://localhost:8080/routes
# Response: {"routes":[...]}
```

---

## Features

### 1. Authentication (`middleware/auth.py`)

- JWT token validation
- Permissive mode for gradual rollout
- Configurable protected paths

```yaml
# config/gateway_routes.yaml
auth:
  jwt_secret: ${JWT_SECRET}
  permissive_mode: true  # Allow requests without auth
  protected_paths:
    - /api/v1/admin/*
```

### 2. Rate Limiting (`middleware/rate_limit.py`)

- Token bucket algorithm
- Per client IP + endpoint path
- Configurable limits per route

**Rate Limit Formats**:
- `100/second`
- `100/minute`
- `1000/hour`
- `10000/day`

**Headers**:
- `X-RateLimit-Limit`: Total limit
- `X-RateLimit-Remaining`: Remaining tokens
- `Retry-After`: Seconds to wait (on 429)

### 3. Circuit Breaker (`middleware/circuit_breaker.py`)

- Per-backend circuit breaker
- States: CLOSED, OPEN, HALF_OPEN
- Automatic recovery detection

**Configuration** (per backend):
- `failure_threshold`: 5 failures → OPEN
- `success_threshold`: 2 successes → CLOSED
- `timeout`: 60 seconds before retry

### 4. Response Caching (`middleware/cache.py`)

- GET requests only
- Configurable TTL per route
- In-memory cache with LRU eviction
- Cache headers: `X-Cache`, `X-Cache-Age`

### 5. Structured Logging (`middleware/logging.py`)

**JSON format**:
```json
{
  "timestamp": "2025-10-04T10:30:00Z",
  "level": "INFO",
  "service": "api-gateway",
  "event": "request_completed",
  "method": "POST",
  "path": "/api/v1/accelerator/chat",
  "status": 200,
  "duration_ms": 245,
  "client_ip": "192.168.1.100"
}
```

**Response headers**:
- `X-Response-Time`: Request duration

### 6. CORS Handling

**Default configuration**:
```yaml
cors:
  allow_origins:
    - http://localhost:4200
  allow_methods:
    - GET
    - POST
    - PUT
    - DELETE
    - PATCH
  allow_headers: ["*"]
  allow_credentials: true
```

---

## Monitoring

### Metrics

Track these metrics for monitoring:

1. **Request Rate**
   - Total requests/second
   - Requests per backend
   - 2xx/4xx/5xx responses

2. **Latency**
   - p50, p95, p99 response times
   - Per route latency

3. **Rate Limiting**
   - Rate limit hits (429 responses)
   - Top rate-limited clients

4. **Circuit Breaker**
   - Circuit breaker state changes
   - OPEN circuit count
   - Backend failure rates

5. **Cache**
   - Cache hit/miss ratio
   - Cache size
   - Eviction rate

### Logs

View structured logs:

```bash
# Follow gateway logs
tail -f logs/gateway.log

# Filter by event type
cat logs/gateway.log | jq 'select(.event=="request_failed")'

# Check rate limit events
cat logs/gateway.log | jq 'select(.event=="rate_limit_exceeded")'
```

---

## Troubleshooting

### Common Issues

**1. Backend connection refused (502)**

```bash
# Check backend is running
curl http://localhost:4001/health  # BFF
curl http://localhost:5000/health  # Guardian

# Check environment variables
echo $BFF_SERVICE_URL
```

**2. Rate limit exceeded (429)**

```bash
# Check rate limit configuration
cat config/gateway_routes.yaml | grep rate_limit

# Increase limit for testing
# Edit config/gateway_routes.yaml, then restart gateway
```

**3. CORS errors in browser**

```bash
# Check CORS configuration
cat config/gateway_routes.yaml | grep -A 5 cors

# Ensure frontend URL is in allow_origins
```

**4. Circuit breaker open (503)**

```bash
# Check backend health
curl http://localhost:8080/health/ready

# Wait 60 seconds for circuit to attempt reset
# Or restart gateway to reset all circuits
```

---

## Development

### Running Tests

```bash
# Unit tests
pytest tests/gateway/

# Integration tests (requires backends running)
pytest tests/integration/test_gateway.py
```

### Adding a New Route

1. **Update configuration** (`config/gateway_routes.yaml`):

```yaml
routes:
  - path: /api/v1/newservice/*
    backend: ${NEW_SERVICE_URL:http://localhost:9900}
    rate_limit: 50/minute
    requires_auth: false
    cache_ttl: 60
```

2. **Update services registry** (`config/services.yaml`):

```yaml
services:
  new_service:
    port: 9900
    category: microservices
    health: /health
```

3. **Update docker-compose** (if needed):

```yaml
environment:
  - NEW_SERVICE_URL=http://newservice:9900
```

4. **Restart gateway**:

```bash
./start_gateway.sh --reload
```

### Adding Middleware

1. Create middleware file in `src/gateway/middleware/`:

```python
# src/gateway/middleware/custom.py
from starlette.middleware.base import BaseHTTPMiddleware

class CustomMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Pre-processing
        response = await call_next(request)
        # Post-processing
        return response
```

2. Register in `main.py`:

```python
from src.gateway.middleware.custom import CustomMiddleware

app.add_middleware(CustomMiddleware)
```

---

## Production Deployment

### Prerequisites

- Python 3.11+
- All backend services running and healthy
- Environment variables configured
- SSL/TLS certificates (for HTTPS)

### Deployment Checklist

- [ ] Update `JWT_SECRET` to production value
- [ ] Configure `auth.permissive_mode: false` (strict auth)
- [ ] Set appropriate rate limits
- [ ] Configure CORS for production frontend URL
- [ ] Enable HTTPS/TLS
- [ ] Configure monitoring and alerting
- [ ] Set up log aggregation
- [ ] Configure resource limits (CPU/memory)
- [ ] Test all routes with production backends
- [ ] Load test gateway under production load

### Resource Requirements

**Recommended**:
- CPU: 1-2 cores
- Memory: 512MB - 1GB
- Network: Low latency to backends

**Scaling**:
- Gateway is stateless (except in-memory cache)
- Can run multiple instances behind load balancer
- Use Redis for shared cache (future enhancement)

---

## Security

### Authentication

Currently in **permissive mode** (auth optional). To enable strict auth:

```yaml
# config/gateway_routes.yaml
auth:
  permissive_mode: false  # Reject requests without valid JWT
```

### Protected Routes

Add paths that require authentication:

```yaml
auth:
  protected_paths:
    - /api/v1/admin/*
    - /api/v1/guardian/*
```

### Rate Limiting

Prevents abuse and DDoS attacks. Adjust limits based on expected traffic.

### Circuit Breaker

Protects backends from overload and prevents cascading failures.

---

## Migration Guide

### Phase 1: Parallel Deployment (Current)

Frontend connects to **both** gateway and direct services:
- Development/testing via gateway (port 8080)
- Production traffic direct to services (4001, 5000, etc.)

### Phase 2: Gradual Migration

1. **Week 1**: 10% of traffic through gateway
2. **Week 2**: 50% of traffic through gateway
3. **Week 3**: 90% of traffic through gateway
4. **Week 4**: 100% of traffic through gateway

### Phase 3: Enforcement

1. Close direct ports (4001, 5000, etc.) to external traffic
2. Only gateway (8080) exposed publicly
3. Backends accessible only via internal network

---

## Related Documentation

- [ADR-003: API Gateway Pattern](../../docs/architecture/ADR-003-api-gateway.md)
- [ADR-001: Service Discovery](../../docs/architecture/ADR-001-service-discovery.md)
- [ADR-006: Resilience Patterns](../../docs/architecture/ADR-006-resilience-patterns.md)
- [Architecture README](../../docs/architecture/README.md)

---

## Support

### Issues

Report issues at: [GitHub Issues](https://github.com/maestro/maestro-engine/issues)

### Questions

Contact: MAESTRO Architecture Team

---

**Last Updated**: 2025-10-04
**Version**: 1.0.0
**Status**: Production Ready
