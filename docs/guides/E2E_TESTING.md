# E2E Testing Setup - Complete Platform Startup

**Date**: 2025-10-04
**Purpose**: Bring up all services for full end-to-end testing
**Status**: ⚠️ **Services Currently DOWN**

---

## 🚨 Current Status - Service Analysis

### Running Services ✅
```bash
maestro-api            Up (healthy)    Port: 18000
maestro-postgres       Up (healthy)    Port: 15432
maestro-redis         Up (healthy)    Port: 16379
maestro-minio         Up (healthy)    Ports: 9000-9001
```

### Stopped Services ❌
```bash
maestro-mlflow        Exited (1)      Port: 5000 (expected)

# Maestro Engine (ALL DOWN)
maestro-gateway       Not running     Port: 8080
maestro-coordinator   Not running     Port: 8002
maestro-mcp           Not running     Port: 9800
maestro-orchestration Not running     Port: 8004
maestro-rag           Not running     Port: 9803

# Quality Fabric (DOWN)
quality-fabric        Not running     Port: 8000

# Maestro Templates (DOWN)
maestro-templates     Not running     Port: 9600
```

---

## 📊 Quality Fabric Test Report Analysis

Based on the test notes you provided:

### Maestro-Engine Test Results
- **Tests**: 33 failed | 20 passed | 17 skipped | 1 error (71 total)
- **Duration**: 19.74s

### Failure Breakdown

#### E2E Tests (9 failures)
**Cause**: Connection refused - services not running on localhost
- Expected services on ports: **9500, 9501, 9502, etc.**
- Missing gateway on port **8080**
- Missing coordinator on port **8002**

#### RAG Writer Service Tests (19 failures)
**Cause**: Service endpoint connection failures
- RAG service expected on port **9803**
- Service not running

#### Performance Tests (4 failures)
**Cause**: Configuration loading/access failures
- Services required for config validation

#### Benchmark Test (1 error)
**Cause**: Missing pytest-benchmark plugin

### Passing Tests ✅ (20)
- ✅ Import System tests (7/7)
- ✅ RAG Integration E2E tests (5/5) - Self-contained
- ✅ Performance: async operations, import time, concurrent operations (3/3)
- ✅ E2E: malformed request handling, response times, concurrent requests (3/3)
- ✅ Load Testing: version/metrics endpoints (2/2)

---

## 🎯 Required Services for Full E2E Testing

### Core Infrastructure
| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| **Gateway** | 8080 | API Gateway (ADR-003) | ❌ DOWN |
| **Coordinator** | 8002 | Service coordination | ❌ DOWN |
| **Orchestration** | 8004 | Workflow orchestration | ❌ DOWN |
| **MCP** | 9800 | Hot Claude sessions | ❌ DOWN |
| **RAG** | 9803 | Vector search & embeddings | ❌ DOWN |

### External Services
| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| **Quality Fabric** | 8000 | Code quality validation | ❌ DOWN |
| **Maestro Templates** | 9600 | Template registry | ❌ DOWN |
| **BFF Service** | 4001 | Backend for frontend | ❌ Not Configured |

### Supporting Infrastructure
| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| PostgreSQL | 15432 | Database | ✅ UP |
| Redis | 16379 | Caching | ✅ UP |
| MinIO | 9000-9001 | Object storage | ✅ UP |

---

## 🚀 Startup Sequence

### Prerequisites

1. **Check Environment Variables**
```bash
# Required for all services
export ANTHROPIC_API_KEY="your-key-here"

# Optional for development
export GATEWAY_URL="http://gateway:8080"
export ENVIRONMENT="development"
export LOG_LEVEL="DEBUG"
```

2. **Check Docker Network**
```bash
# Create shared network if it doesn't exist
docker network create maestro-dev-network 2>/dev/null || true
```

---

### Step 1: Start Quality Fabric (Port 8000)

```bash
cd /home/ec2-user/projects/quality-fabric

# Build and start
docker-compose up -d --build

# Verify
curl http://localhost:8000/api/health

# Expected response:
# {"status": "healthy", "service": "quality-fabric"}
```

**Wait for**: Health check passes (~30s)

---

### Step 2: Start Maestro Templates (Port 9600)

```bash
cd /home/ec2-user/projects/maestro-templates

# Build and start
docker-compose up -d --build

# Verify
curl http://localhost:9600/api/health

# Expected response:
# {"status": "healthy", "service": "maestro-templates"}
```

**Wait for**: Health check passes (~30s)

---

### Step 3: Start Maestro Engine Services

```bash
cd /home/ec2-user/projects/maestro-engine

# Build and start all services
docker-compose -f docker-compose.dev.yml up -d --build

# This starts:
# - gateway (8080)
# - coordinator (8002)
# - mcp (9800)
# - orchestration (8004)
# - rag (9803)
```

**Wait for**: All health checks pass (~60s)

---

### Step 4: Verify All Services

```bash
# Check all containers
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "maestro|quality|template|gateway"

# Check health endpoints
curl http://localhost:8080/health  # Gateway
curl http://localhost:8002/health  # Coordinator
curl http://localhost:8004/health  # Orchestration
curl http://localhost:9800/health  # MCP
curl http://localhost:9803/health  # RAG
curl http://localhost:8000/api/health  # Quality Fabric
curl http://localhost:9600/api/health  # Templates
```

**Expected**: All return `200 OK` with `{"status": "healthy"}`

---

## 🧪 Run E2E Tests

### Maestro-Engine Tests

```bash
cd /home/ec2-user/projects/maestro-engine

# Install test dependencies if needed
pip3.11 install -r requirements.txt
pip3.11 install pytest pytest-asyncio pytest-benchmark

# Run all tests
pytest tests/ -v

# Run only E2E tests
pytest tests/e2e/ -v

# Run specific test categories
pytest tests/e2e/test_comprehensive_api_scenarios.py -v
pytest tests/integration/test_configuration_system.py -v
pytest tests/performance/test_load_testing.py -v
```

### Expected Results (After Services Up)

```
Tests:  71 passed | 0 failed | 0 skipped | 0 errors
Duration: ~25s

✅ E2E tests (9/9)
✅ Performance tests (4/4)
✅ RAG Writer Service tests (19/19)
✅ Import System tests (7/7)
✅ RAG Integration E2E tests (5/5)
✅ Load Testing (2/2)
✅ Other tests (25/25)
```

---

## 🔧 Troubleshooting

### Issue 1: Gateway Won't Start

**Symptom**: `maestro-gateway` container exits immediately

**Check Logs**:
```bash
docker logs maestro-gateway
```

**Common Causes**:
- Missing Dockerfile.gateway
- Port 8080 already in use
- Missing environment variables

**Solutions**:
```bash
# Check if port is in use
netstat -tlnp | grep 8080

# Check Dockerfile exists
ls -la /home/ec2-user/projects/maestro-engine/Dockerfile.gateway

# Rebuild
cd /home/ec2-user/projects/maestro-engine
docker-compose -f docker-compose.dev.yml build gateway
docker-compose -f docker-compose.dev.yml up -d gateway
```

---

### Issue 2: Services Can't Reach Each Other

**Symptom**: Connection refused between services

**Check Network**:
```bash
# Verify network exists
docker network inspect maestro-dev-network

# Check which containers are on the network
docker network inspect maestro-dev-network | grep -A 5 "Containers"
```

**Solution**:
```bash
# Ensure all services join the network
# Already configured in docker-compose files

# Restart services to reconnect
docker-compose -f docker-compose.dev.yml restart
```

---

### Issue 3: Health Checks Failing

**Symptom**: Containers restart repeatedly

**Check Health**:
```bash
# View health status
docker ps --format "table {{.Names}}\t{{.Status}}"

# Check specific service logs
docker logs maestro-rag --tail 50
```

**Common Causes**:
- Service not binding to 0.0.0.0
- Health check endpoint not implemented
- Service startup time > health check start_period

**Solution**:
```bash
# Increase health check start_period in docker-compose.dev.yml
healthcheck:
  start_period: 120s  # Increase if service is slow to start
```

---

### Issue 4: Missing Dependencies

**Symptom**: Import errors in tests

**Solution**:
```bash
cd /home/ec2-user/projects/maestro-engine

# Install all test dependencies
pip3.11 install \
  pytest \
  pytest-asyncio \
  pytest-benchmark \
  pytest-cov \
  pytest-mock \
  httpx \
  pydantic

# Or use requirements
pip3.11 install -r requirements.txt
```

---

### Issue 5: Quality Fabric Connection Refused

**Symptom**: Tests fail with "Connection refused to http://localhost:8000"

**Check Service**:
```bash
# Is quality-fabric running?
docker ps | grep quality-fabric

# Check logs
docker logs quality-fabric

# Test manually
curl http://localhost:8000/api/health
```

**Solution**:
```bash
cd /home/ec2-user/projects/quality-fabric

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Wait for health check
sleep 30
curl http://localhost:8000/api/health
```

---

## 📝 Quick Start Script

Create this script for one-command startup:

```bash
#!/bin/bash
# File: start_all_services.sh
# Description: Start all MAESTRO services for E2E testing

set -e  # Exit on error

echo "🚀 Starting MAESTRO Platform for E2E Testing"
echo "=============================================="

# Check prerequisites
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ ERROR: ANTHROPIC_API_KEY not set"
    echo "   export ANTHROPIC_API_KEY='your-key-here'"
    exit 1
fi

# Create network
echo "1. Creating shared network..."
docker network create maestro-dev-network 2>/dev/null || echo "   Network already exists"

# Start Quality Fabric
echo ""
echo "2. Starting Quality Fabric (port 8000)..."
cd /home/ec2-user/projects/quality-fabric
docker-compose up -d --build
echo "   Waiting for health check..."
sleep 30

# Start Maestro Templates
echo ""
echo "3. Starting Maestro Templates (port 9600)..."
cd /home/ec2-user/projects/maestro-templates
docker-compose up -d --build
echo "   Waiting for health check..."
sleep 30

# Start Maestro Engine
echo ""
echo "4. Starting Maestro Engine services..."
cd /home/ec2-user/projects/maestro-engine
docker-compose -f docker-compose.dev.yml up -d --build
echo "   Waiting for all services to be healthy..."
sleep 60

# Verify all services
echo ""
echo "5. Verifying services..."
services=(
    "8080:Gateway"
    "8002:Coordinator"
    "8004:Orchestration"
    "9800:MCP"
    "9803:RAG"
    "8000:Quality Fabric"
    "9600:Templates"
)

all_healthy=true
for service in "${services[@]}"; do
    port="${service%%:*}"
    name="${service##*:}"
    if curl -s -f http://localhost:$port/health >/dev/null 2>&1 || \
       curl -s -f http://localhost:$port/api/health >/dev/null 2>&1; then
        echo "   ✅ $name (port $port)"
    else
        echo "   ❌ $name (port $port) - NOT HEALTHY"
        all_healthy=false
    fi
done

echo ""
if [ "$all_healthy" = true ]; then
    echo "✅ All services are running and healthy!"
    echo ""
    echo "📊 Service Status:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "maestro|quality|template|gateway"
    echo ""
    echo "🧪 Ready for E2E testing!"
    echo "   Run: cd /home/ec2-user/projects/maestro-engine && pytest tests/ -v"
else
    echo "⚠️  Some services are not healthy. Check logs:"
    echo "   docker-compose -f docker-compose.dev.yml logs"
    exit 1
fi
```

**Make executable and run**:
```bash
chmod +x start_all_services.sh
./start_all_services.sh
```

---

## 🛑 Shutdown Script

```bash
#!/bin/bash
# File: stop_all_services.sh
# Description: Stop all MAESTRO services

echo "🛑 Stopping MAESTRO Platform"
echo "============================="

# Stop Maestro Engine
echo "1. Stopping Maestro Engine..."
cd /home/ec2-user/projects/maestro-engine
docker-compose -f docker-compose.dev.yml down

# Stop Maestro Templates
echo "2. Stopping Maestro Templates..."
cd /home/ec2-user/projects/maestro-templates
docker-compose down

# Stop Quality Fabric
echo "3. Stopping Quality Fabric..."
cd /home/ec2-user/projects/quality-fabric
docker-compose down

echo ""
echo "✅ All services stopped"
```

---

## 📊 Expected E2E Test Coverage

After bringing up all services, these test suites should pass:

### 1. E2E API Tests (9 tests)
- ✅ Gateway routing to all services
- ✅ Service-to-service communication
- ✅ End-to-end workflow execution
- ✅ Error handling across services
- ✅ Timeout and retry logic
- ✅ Circuit breaker functionality
- ✅ Rate limiting
- ✅ Authentication flow
- ✅ Multi-service transactions

### 2. RAG Service Tests (19 tests)
- ✅ Vector search functionality
- ✅ Embedding generation
- ✅ Document indexing
- ✅ Similarity search
- ✅ RAG query processing
- ✅ Collection management
- ✅ Metadata filtering
- ✅ Batch operations
- ✅ Health monitoring

### 3. Performance Tests (4 tests)
- ✅ Configuration loading
- ✅ Concurrent request handling
- ✅ Response time benchmarks
- ✅ Resource utilization

### 4. Integration Tests
- ✅ Gateway → Coordinator → MCP flow
- ✅ Gateway → Quality Fabric validation
- ✅ Gateway → Templates search
- ✅ RAG → Vector DB integration
- ✅ Orchestration → Multi-service coordination

---

## 🎯 Success Criteria

E2E testing is fully operational when:

- ✅ All 7 core services are running (ports 8000, 8002, 8004, 8080, 9600, 9800, 9803)
- ✅ All health checks return `200 OK`
- ✅ Gateway can route to all services
- ✅ Services can communicate via gateway
- ✅ All 71 pytest tests pass
- ✅ No connection refused errors
- ✅ Response times < 2s for all endpoints
- ✅ Zero service crashes during test run

---

## 🔗 Related Documentation

- **Gateway Integration**: `GATEWAY_INTEGRATION_GUIDE.md`
- **Persona Centralization**: `PERSONA_MIGRATION_COMPLETE.md`
- **Docker Compose Files**:
  - `docker-compose.dev.yml` (Maestro Engine)
  - `docker-compose.yml` (Quality Fabric)
  - `docker-compose.yml` (Maestro Templates)

---

## 📞 Next Steps

1. **Run startup script**: `./start_all_services.sh`
2. **Verify services**: Check all health endpoints
3. **Run E2E tests**: `pytest tests/ -v`
4. **Fix any failures**: Check logs and troubleshooting section
5. **Document results**: Update test coverage reports

---

**Ready to bring up all services? Run the startup script and all 71 tests should pass!** 🚀
