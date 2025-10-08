# MAESTRO API Gateway - Deployment Guide

**Version**: 1.0.0
**Last Updated**: 2025-10-04
**Status**: Production Ready

---

## Overview

This guide shows how to deploy the complete MAESTRO platform with the API Gateway integrating all services.

**Architecture**: All services communicate through the API Gateway (port 8080)

---

## Prerequisites

- Docker & Docker Compose installed
- Ports available: 8080 (gateway), 8000 (quality-fabric), 9600 (templates), 5000 (maestro-engine)
- Shared network: `maestro-dev-network`

---

## Quick Start

### 1. Create Shared Network

```bash
# Create shared network for all services
docker network create maestro-dev-network
```

### 2. Start API Gateway

```bash
cd /home/ec2-user/projects/maestro-engine

# Start gateway
docker-compose -f docker-compose.dev.yml up -d gateway

# Verify gateway is running
curl http://localhost:8080/health
# Expected: {"status":"healthy","service":"api-gateway","version":"1.0.0"}
```

### 3. Start Services

#### Start Quality Fabric

```bash
cd /home/ec2-user/projects/quality-fabric

# Start quality-fabric
docker-compose up -d quality-fabric

# Verify integration
docker exec quality-fabric curl http://gateway:8080/health
```

#### Start Maestro Templates

```bash
cd /home/ec2-user/projects/maestro-templates

# Start templates service
docker-compose up -d central-registry

# Verify integration
docker exec maestro-templates-registry curl http://gateway:8080/health
```

#### Start Maestro Engine

```bash
cd /home/ec2-user/projects/maestro-engine

# Start maestro engine
docker-compose -f docker-compose.dev.yml up -d orchestration mcp rag

# Verify
curl http://localhost:5000/health
```

### 4. Verify Gateway Routes

```bash
# List all registered routes
curl http://localhost:8080/routes

# Expected output:
{
  "routes": [
    {"path": "/api/v1/accelerator/*", "backend": "http://localhost:4001", "rate_limit": "100/minute"},
    {"path": "/api/v1/guardian/*", "backend": "http://localhost:5000", "rate_limit": "20/minute"},
    {"path": "/api/v1/templates/*", "backend": "http://templates:9600", "rate_limit": "200/minute"},
    {"path": "/api/v1/quality/*", "backend": "http://quality-fabric:8000", "rate_limit": "50/minute"},
    {"path": "/api/v1/rag/*", "backend": "http://rag:9803", "rate_limit": "100/minute"}
  ]
}
```

### 5. Test Service Communication

```bash
# Test quality-fabric via gateway
curl -X POST http://localhost:8080/api/v1/quality/api/validate \
  -H "Content-Type: application/json" \
  -d '{"code":"def test(): pass","language":"python"}'

# Test templates via gateway
curl -X POST http://localhost:8080/api/v1/templates/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"authentication","category":"test"}'

# Test RAG via gateway
curl -X POST http://localhost:8080/api/v1/rag/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"error handling","collection":"templates"}'
```

---

## Complete Deployment

### All-in-One Script

Create `start_maestro_platform.sh`:

```bash
#!/bin/bash

set -e

echo "🚀 Starting MAESTRO Platform with API Gateway..."

# 1. Create network
echo "1️⃣ Creating shared network..."
docker network create maestro-dev-network 2>/dev/null || echo "Network already exists"

# 2. Start Gateway
echo "2️⃣ Starting API Gateway..."
cd /home/ec2-user/projects/maestro-engine
docker-compose -f docker-compose.dev.yml up -d gateway
sleep 5

# Verify gateway
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Gateway is healthy"
else
    echo "❌ Gateway failed to start"
    exit 1
fi

# 3. Start Backend Services
echo "3️⃣ Starting backend services..."

# Start orchestration, MCP, RAG
docker-compose -f docker-compose.dev.yml up -d orchestration mcp rag

# 4. Start Quality Fabric
echo "4️⃣ Starting Quality Fabric..."
cd /home/ec2-user/projects/quality-fabric
docker-compose up -d quality-fabric
sleep 5

# 5. Start Maestro Templates
echo "5️⃣ Starting Maestro Templates..."
cd /home/ec2-user/projects/maestro-templates
docker-compose up -d postgres redis central-registry
sleep 5

# 6. Verify all services
echo "6️⃣ Verifying services..."

check_service() {
    local name=$1
    local url=$2

    if curl -f "$url" > /dev/null 2>&1; then
        echo "  ✅ $name is healthy"
    else
        echo "  ❌ $name is NOT healthy"
    fi
}

check_service "Gateway" "http://localhost:8080/health"
check_service "Quality Fabric (via gateway)" "http://localhost:8080/api/v1/quality/api/health"
check_service "Templates (via gateway)" "http://localhost:8080/api/v1/templates/health"
check_service "RAG (via gateway)" "http://localhost:8080/api/v1/rag/health"

echo ""
echo "🎉 MAESTRO Platform Started!"
echo ""
echo "📍 Gateway URL: http://localhost:8080"
echo "📍 Gateway Routes: http://localhost:8080/routes"
echo "📍 Gateway Health: http://localhost:8080/health/ready"
echo ""
echo "🔧 Direct Service URLs (for debugging only):"
echo "   Quality Fabric: http://localhost:8000"
echo "   Templates: http://localhost:9600"
echo "   Maestro Engine: http://localhost:5000"
echo ""
echo "💡 Use the gateway (port 8080) for all API calls"
```

Make it executable:
```bash
chmod +x start_maestro_platform.sh
./start_maestro_platform.sh
```

---

## Environment Configuration

### Gateway Environment Variables

The gateway needs these environment variables configured in `maestro-engine/docker-compose.dev.yml`:

```yaml
gateway:
  environment:
    - ENVIRONMENT=development
    - LOG_LEVEL=DEBUG
    - BFF_SERVICE_URL=http://host.docker.internal:4001
    - MAESTRO_ENGINE_URL=http://host.docker.internal:5000
    - TEMPLATE_SERVICE_URL=http://templates:9600         # ← Uses service name
    - RAG_SERVICE_URL=http://rag:9803                     # ← Uses service name
    - MCP_SERVICE_URL=http://mcp:9800                     # ← Uses service name
    - QUALITY_FABRIC_URL=http://quality-fabric:8000       # ← Uses service name
    - COORDINATOR_SERVICE_URL=http://coordinator:8002
    - ORCHESTRATION_SERVICE_URL=http://orchestration:8004
    - FRONTEND_URL=http://localhost:4200
    - JWT_SECRET=dev-secret-change-in-production
```

### Service Environment Variables

Each service needs:

```yaml
# quality-fabric/docker-compose.yml
quality-fabric:
  environment:
    - GATEWAY_URL=http://gateway:8080
    - SERVICE_NAME=quality-fabric

# maestro-templates/docker-compose.yml
central-registry:
  environment:
    - GATEWAY_URL=http://gateway:8080
    - SERVICE_NAME=maestro-templates
```

---

## Network Configuration

### Shared Network

All services must be on the shared `maestro-dev-network`:

```yaml
# In each docker-compose.yml
networks:
  maestro-dev-network:
    external: true
    name: maestro-dev-network

services:
  my-service:
    networks:
      - my-service-network  # Service-specific network
      - maestro-dev-network # Shared network with gateway
```

### Network Verification

```bash
# List networks
docker network ls | grep maestro

# Inspect network
docker network inspect maestro-dev-network

# Check which containers are connected
docker network inspect maestro-dev-network | jq '.[0].Containers'
```

---

## Health Checks

### Gateway Health

```bash
# Basic health
curl http://localhost:8080/health

# Readiness (checks all backends)
curl http://localhost:8080/health/ready
```

### Service Health (via Gateway)

```bash
# Quality Fabric
curl http://localhost:8080/api/v1/quality/api/health

# Templates
curl http://localhost:8080/api/v1/templates/health

# RAG
curl http://localhost:8080/api/v1/rag/health

# Maestro Engine
curl http://localhost:8080/api/v1/guardian/health
```

### Direct Service Health (Debugging)

```bash
# Quality Fabric (direct)
curl http://localhost:8000/api/health

# Templates (direct)
curl http://localhost:9600/health

# Maestro Engine (direct)
curl http://localhost:5000/health
```

---

## Monitoring

### Gateway Logs

```bash
# Follow gateway logs
docker logs -f gateway

# Filter by event type
docker logs gateway | grep "gateway_call"
docker logs gateway | grep "rate_limit_exceeded"
docker logs gateway | grep "circuit_breaker"
```

### Service Logs

```bash
# Quality Fabric logs
docker logs -f quality-fabric

# Templates logs
docker logs -f maestro-templates-registry

# Check for gateway client logs
docker logs quality-fabric | grep "Gateway call"
```

### Metrics

```bash
# Gateway metrics (if Prometheus enabled)
curl http://localhost:8080/metrics

# Service metrics
curl http://localhost:8000/metrics  # Quality Fabric
curl http://localhost:9600/metrics  # Templates
```

---

## Troubleshooting

### Gateway Not Starting

```bash
# Check gateway logs
docker logs gateway

# Common issues:
# 1. Port 8080 already in use
sudo lsof -i :8080

# 2. Config file missing
ls -la /home/ec2-user/projects/maestro-engine/config/gateway_routes.yaml

# 3. Python dependencies missing
docker exec gateway pip list | grep httpx
```

### Service Can't Reach Gateway

```bash
# From quality-fabric container
docker exec quality-fabric ping gateway

# Check DNS resolution
docker exec quality-fabric nslookup gateway

# Check network connectivity
docker exec quality-fabric curl http://gateway:8080/health
```

### Route Not Found (404)

```bash
# Check registered routes
curl http://localhost:8080/routes

# Check service name in URL
# ✅ Correct: /api/v1/quality/api/validate
# ❌ Wrong:   /api/v1/quality-fabric/api/validate
```

### Circuit Breaker Open (503)

```bash
# Check backend health
curl http://localhost:8080/health/ready

# Check which service is down
docker ps | grep -E "(quality|templates|rag)"

# Reset by restarting gateway
docker restart gateway
```

---

## Production Deployment

### Production Environment

Use `docker-compose.prod.yml`:

```bash
cd /home/ec2-user/projects/maestro-engine

# Start production gateway
docker-compose -f docker-compose.prod.yml up -d gateway
```

### Production Checklist

- [ ] Update `JWT_SECRET` to secure value
- [ ] Set `FRONTEND_URL` to production domain
- [ ] Configure SSL/TLS certificates
- [ ] Set appropriate rate limits
- [ ] Enable monitoring (Prometheus/Grafana)
- [ ] Configure log aggregation
- [ ] Set resource limits (CPU/memory)
- [ ] Test all routes
- [ ] Load test gateway

### Security

```bash
# Production security
- Change JWT_SECRET
- Enable HTTPS/TLS
- Set auth.permissive_mode: false
- Configure firewall rules
- Use secrets management
- Enable audit logging
```

---

## Shutdown

### Stop All Services

```bash
# Stop services in reverse order

# 1. Stop templates
cd /home/ec2-user/projects/maestro-templates
docker-compose down

# 2. Stop quality-fabric
cd /home/ec2-user/projects/quality-fabric
docker-compose down

# 3. Stop maestro-engine services
cd /home/ec2-user/projects/maestro-engine
docker-compose -f docker-compose.dev.yml down

# 4. Optional: Remove shared network
docker network rm maestro-dev-network
```

### Stop Gateway Only

```bash
cd /home/ec2-user/projects/maestro-engine
docker-compose -f docker-compose.dev.yml stop gateway
```

---

## Testing Integration

### End-to-End Test

```bash
# 1. Quality Fabric → Templates (via gateway)
curl -X POST http://localhost:8080/api/v1/quality/api/validate \
  -H "Content-Type: application/json" \
  -d '{
    "code": "def test(): pass",
    "language": "python"
  }'

# 2. Templates → RAG (via gateway)
curl -X POST http://localhost:8080/api/v1/templates/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication patterns"
  }'

# 3. Check gateway handled both calls
docker logs gateway | tail -20
```

---

## Next Steps

1. **Update Frontend**: Point frontend to `http://localhost:8080` instead of individual services
2. **Migrate Services**: Replace direct HTTP calls with gateway client
3. **Monitor**: Set up Prometheus/Grafana for metrics
4. **Scale**: Add more gateway instances behind load balancer

---

## Related Documentation

- [API Gateway README](../src/gateway/README.md)
- [Quality Fabric Integration Guide](../../quality-fabric/GATEWAY_INTEGRATION_GUIDE.md)
- [Templates Integration Guide](../../maestro-templates/GATEWAY_INTEGRATION_GUIDE.md)
- [ADR-003: API Gateway Pattern](./architecture/ADR-003-api-gateway.md)

---

**Support**: MAESTRO Architecture Team
**Last Updated**: 2025-10-04
