#!/bin/bash
# MAESTRO Engine Deployment Script
# Usage: ./scripts/deploy.sh [environment]
# Environments: dev, staging, prod

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

ENVIRONMENT="${1:-dev}"
COMPOSE_FILE=""

case "$ENVIRONMENT" in
  dev|development)
    COMPOSE_FILE="docker-compose.dev.yml"
    echo "🚀 Deploying to DEVELOPMENT environment"
    ;;
  staging)
    COMPOSE_FILE="docker-compose.prod.yml"
    echo "🚀 Deploying to STAGING environment"
    ;;
  prod|production)
    COMPOSE_FILE="docker-compose.prod.yml"
    echo "🚀 Deploying to PRODUCTION environment"
    ;;
  *)
    echo "❌ Invalid environment: $ENVIRONMENT"
    echo "Usage: $0 [dev|staging|prod]"
    exit 1
    ;;
esac

cd "$PROJECT_ROOT"

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose not found. Please install Docker Compose."
    exit 1
fi

# Check .env file
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.template .env
    echo "⚠️  Please update .env with your configuration before deployment!"
    exit 1
fi

# Load environment variables
source .env

# Check required variables
if [ -z "$ANTHROPIC_API_KEY" ] || [ "$ANTHROPIC_API_KEY" = "your_api_key_here" ]; then
    echo "❌ ANTHROPIC_API_KEY not set in .env"
    exit 1
fi

# Build images
echo "🔨 Building Docker images..."
docker-compose -f "$COMPOSE_FILE" build

# Stop existing services
echo "🛑 Stopping existing services..."
docker-compose -f "$COMPOSE_FILE" down

# Start services
echo "▶️  Starting services..."
docker-compose -f "$COMPOSE_FILE" up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f http://localhost:8002/health &> /dev/null; then
        echo "✅ Coordinator service is healthy"
        break
    fi
    echo "⏳ Waiting for coordinator... ($((RETRY_COUNT+1))/$MAX_RETRIES)"
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT+1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ Services failed to become healthy"
    docker-compose -f "$COMPOSE_FILE" logs
    exit 1
fi

# Verify all services
echo "🔍 Verifying all services..."
SERVICES=("coordinator:8002" "mcp:9800" "orchestration:8004" "rag:9803")

for SERVICE in "${SERVICES[@]}"; do
    IFS=':' read -r NAME PORT <<< "$SERVICE"
    if curl -f "http://localhost:$PORT/health" &> /dev/null; then
        echo "✅ $NAME service is healthy"
    else
        echo "⚠️  $NAME service health check failed"
    fi
done

# Show running services
echo ""
echo "📊 Running services:"
docker-compose -f "$COMPOSE_FILE" ps

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Service endpoints:"
echo "  - Coordinator:    http://localhost:8002"
echo "  - MCP Service:    http://localhost:9800"
echo "  - Orchestration:  http://localhost:8004"
echo "  - RAG Service:    http://localhost:9803"
echo ""
echo "📚 API Documentation: http://localhost:8002/docs"
echo "📊 Health Check:      http://localhost:8002/health"
echo ""
echo "📝 To view logs:      docker-compose -f $COMPOSE_FILE logs -f"
echo "🛑 To stop services:  docker-compose -f $COMPOSE_FILE down"
