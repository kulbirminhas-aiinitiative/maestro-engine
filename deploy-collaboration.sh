#!/bin/bash
#
# Deploy Multi-Agent Collaboration BFF Service
# Part of maestro-engine-new services
#

set -e

echo "🚀 Deploying Multi-Agent Collaboration BFF Service"
echo "===================================================="

cd "$(dirname "$0")"

# Check if maestro-dev-network exists
if ! docker network ls | grep -q "maestro-dev-network"; then
    echo "📡 Creating maestro-dev-network..."
    docker network create maestro-dev-network
fi

# Build and start only the collaboration service
echo "🐳 Building collaboration BFF service..."
docker-compose -f docker-compose.dev.yml build collaboration-bff

echo "🚀 Starting collaboration BFF service..."
docker-compose -f docker-compose.dev.yml up -d collaboration-bff

# Wait for service to be healthy
echo ""
echo "⏳ Waiting for service to be healthy..."
sleep 5

for i in {1..15}; do
    if curl -sf http://localhost:4002/health > /dev/null 2>&1; then
        echo ""
        echo "✅ Collaboration BFF Service is healthy!"
        echo ""
        echo "📊 Service Status:"
        curl -s http://localhost:4002/health | python3 -m json.tool || cat
        echo ""
        echo "🌐 Service endpoints:"
        echo "   WebSocket: ws://localhost:4002/ws/collaboration/{room_id}"
        echo "   Health:    http://localhost:4002/health"
        echo ""
        echo "📦 Container status:"
        docker ps | grep maestro-collaboration-bff
        echo ""
        echo "📝 To view logs:"
        echo "   docker logs -f maestro-collaboration-bff"
        echo ""
        echo "🛑 To stop:"
        echo "   docker-compose -f docker-compose.dev.yml stop collaboration-bff"
        exit 0
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "⚠️  Service health check timeout. Checking logs..."
docker logs maestro-collaboration-bff --tail 50
exit 1
