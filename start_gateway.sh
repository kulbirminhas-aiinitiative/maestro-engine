#!/bin/bash

# MAESTRO API Gateway Startup Script
# Part of ADR-003: API Gateway Pattern
#
# Usage:
#   ./start_gateway.sh              # Development mode
#   ./start_gateway.sh --reload     # Development mode with hot reload
#   ./start_gateway.sh --production # Production mode

set -e

# Configuration
GATEWAY_PORT=${GATEWAY_PORT:-8080}
GATEWAY_HOST=${GATEWAY_HOST:-0.0.0.0}
LOG_LEVEL=${LOG_LEVEL:-info}

# Default mode
MODE="development"
RELOAD_FLAG=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --reload)
      RELOAD_FLAG="--reload"
      shift
      ;;
    --production)
      MODE="production"
      LOG_LEVEL="warning"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--reload] [--production]"
      exit 1
      ;;
  esac
done

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}MAESTRO API Gateway${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Port:${NC} $GATEWAY_PORT"
echo -e "${GREEN}Host:${NC} $GATEWAY_HOST"
echo -e "${GREEN}Mode:${NC} $MODE"
echo -e "${GREEN}Log Level:${NC} $LOG_LEVEL"
echo -e "${BLUE}========================================${NC}"

# Check if config file exists
if [ ! -f "config/gateway_routes.yaml" ]; then
  echo -e "${YELLOW}Warning: config/gateway_routes.yaml not found${NC}"
  echo -e "${YELLOW}Using default configuration${NC}"
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
  echo "Error: python3 is required"
  exit 1
fi

# Check if uvicorn is installed
if ! python3 -c "import uvicorn" 2>/dev/null; then
  echo "Error: uvicorn is not installed"
  echo "Install dependencies: pip install -r requirements.txt"
  exit 1
fi

# Set environment variables for development
if [ "$MODE" = "development" ]; then
  export ENVIRONMENT=development
  export BFF_SERVICE_URL=${BFF_SERVICE_URL:-http://localhost:4001}
  export MAESTRO_ENGINE_URL=${MAESTRO_ENGINE_URL:-http://localhost:5000}
  export TEMPLATE_SERVICE_URL=${TEMPLATE_SERVICE_URL:-http://localhost:9600}
  export RAG_SERVICE_URL=${RAG_SERVICE_URL:-http://localhost:9803}
  export MCP_SERVICE_URL=${MCP_SERVICE_URL:-http://localhost:9800}
  export QUALITY_FABRIC_URL=${QUALITY_FABRIC_URL:-http://localhost:8000}
  export COORDINATOR_SERVICE_URL=${COORDINATOR_SERVICE_URL:-http://localhost:8002}
  export ORCHESTRATION_SERVICE_URL=${ORCHESTRATION_SERVICE_URL:-http://localhost:8004}
  export FRONTEND_URL=${FRONTEND_URL:-http://localhost:4200}
  export JWT_SECRET=${JWT_SECRET:-dev-secret-change-in-production}
fi

echo -e "${GREEN}Starting gateway...${NC}"
echo ""

# Start gateway
exec python3 -m uvicorn src.gateway.main:app \
  --host "$GATEWAY_HOST" \
  --port "$GATEWAY_PORT" \
  --log-level "$LOG_LEVEL" \
  $RELOAD_FLAG
