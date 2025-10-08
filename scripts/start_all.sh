#!/bin/bash
# Start all MAESTRO Engine services
# Usage: ./scripts/start_all.sh [dev|prod]

set -e

ENVIRONMENT="${1:-dev}"
COMPOSE_FILE="docker-compose.dev.yml"

if [ "$ENVIRONMENT" = "prod" ] || [ "$ENVIRONMENT" = "production" ]; then
    COMPOSE_FILE="docker-compose.prod.yml"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

echo "🚀 Starting MAESTRO Engine services ($ENVIRONMENT)..."

docker-compose -f "$COMPOSE_FILE" up -d

echo "✅ Services started"
echo ""
docker-compose -f "$COMPOSE_FILE" ps
