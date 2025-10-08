#!/bin/bash
# Stop all MAESTRO services

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
echo ""
echo "ℹ️  Note: Shared network 'maestro-dev-network' is preserved"
echo "   To remove: docker network rm maestro-dev-network"
