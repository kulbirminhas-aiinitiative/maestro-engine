#!/bin/bash
# Restart a specific MAESTRO Engine service
# Usage: ./scripts/restart_service.sh [service] [dev|prod]

set -e

SERVICE="${1}"
ENVIRONMENT="${2:-dev}"
COMPOSE_FILE="docker-compose.dev.yml"

if [ "$ENVIRONMENT" = "prod" ] || [ "$ENVIRONMENT" = "production" ]; then
    COMPOSE_FILE="docker-compose.prod.yml"
fi

if [ -z "$SERVICE" ]; then
    echo "❌ Service name required"
    echo "Usage: $0 [coordinator|mcp|orchestration|rag] [dev|prod]"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

echo "🔄 Restarting $SERVICE service ($ENVIRONMENT)..."

docker-compose -f "$COMPOSE_FILE" restart "$SERVICE"

echo "✅ Service restarted"
echo ""
docker-compose -f "$COMPOSE_FILE" ps "$SERVICE"
