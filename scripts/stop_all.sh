#!/bin/bash
# Stop all MAESTRO Engine services
# Usage: ./scripts/stop_all.sh [dev|prod]

set -e

ENVIRONMENT="${1:-dev}"
COMPOSE_FILE="docker-compose.dev.yml"

if [ "$ENVIRONMENT" = "prod" ] || [ "$ENVIRONMENT" = "production" ]; then
    COMPOSE_FILE="docker-compose.prod.yml"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

echo "🛑 Stopping MAESTRO Engine services ($ENVIRONMENT)..."

docker-compose -f "$COMPOSE_FILE" down

echo "✅ Services stopped"
