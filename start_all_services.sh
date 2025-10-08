#!/bin/bash
# Start all MAESTRO services for E2E testing

set -e

echo "🚀 Starting MAESTRO Platform for E2E Testing"
echo "=============================================="

# Check prerequisites
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  WARNING: ANTHROPIC_API_KEY not set"
    echo "   Some services may not work without it"
    echo "   export ANTHROPIC_API_KEY='your-key-here'"
fi

# Create network
echo ""
echo "1. Creating shared network..."
docker network create maestro-dev-network 2>/dev/null && echo "   ✅ Network created" || echo "   ℹ️  Network already exists"

# Start Quality Fabric
echo ""
echo "2. Starting Quality Fabric (port 8000)..."
cd /home/ec2-user/projects/quality-fabric
docker-compose up -d --build
echo "   Waiting for health check (30s)..."
sleep 30

# Start Maestro Templates
echo ""
echo "3. Starting Maestro Templates (port 9600)..."
cd /home/ec2-user/projects/maestro-templates
docker-compose up -d --build
echo "   Waiting for health check (30s)..."
sleep 30

# Start Maestro Engine
echo ""
echo "4. Starting Maestro Engine services..."
cd /home/ec2-user/projects/maestro-engine
docker-compose -f docker-compose.dev.yml up -d --build
echo "   Waiting for all services to be healthy (60s)..."
sleep 60

# Verify all services
echo ""
echo "5. Verifying services..."
services=(
    "8080:Gateway:/health"
    "8002:Coordinator:/health"
    "8004:Orchestration:/health"
    "9800:MCP:/health"
    "9803:RAG:/health"
    "8000:Quality-Fabric:/api/health"
    "9600:Templates:/api/health"
)

all_healthy=true
for service in "${services[@]}"; do
    port="${service%%:*}"
    rest="${service#*:}"
    name="${rest%%:*}"
    path="${rest#*:}"

    if curl -s -f http://localhost:$port$path >/dev/null 2>&1; then
        echo "   ✅ $name (port $port)"
    else
        echo "   ❌ $name (port $port) - NOT HEALTHY"
        all_healthy=false
    fi
done

echo ""
echo "📊 Service Status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -1
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "maestro|quality|template" | grep -v "postgres\|redis\|minio\|mlflow" || true

echo ""
if [ "$all_healthy" = true ]; then
    echo "✅ All services are running and healthy!"
    echo ""
    echo "🧪 Ready for E2E testing!"
    echo "   Run: cd /home/ec2-user/projects/maestro-engine && pytest tests/ -v"
else
    echo "⚠️  Some services are not healthy."
    echo ""
    echo "🔍 Check logs:"
    echo "   cd /home/ec2-user/projects/maestro-engine"
    echo "   docker-compose -f docker-compose.dev.yml logs [service-name]"
    echo ""
    echo "🔧 Common issues:"
    echo "   - Missing Dockerfiles (check if all Dockerfile.* exist)"
    echo "   - Port conflicts (check: netstat -tlnp | grep <port>)"
    echo "   - Missing environment variables"
    exit 1
fi
