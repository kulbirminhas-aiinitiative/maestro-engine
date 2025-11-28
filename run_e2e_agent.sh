#!/bin/bash
#
# E2E Development & QA Agent Runner
# Usage: ./run_e2e_agent.sh [EPIC_KEY]
#

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     E2E Development & QA Agent with JIRA Integration           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if JWT_TOKEN is set
if [ -z "$JWT_TOKEN" ]; then
    echo -e "${RED}❌ ERROR: JWT_TOKEN environment variable not set${NC}"
    echo ""
    echo "Generate a JWT token:"
    echo ""
    echo "  cd ~/projects/maestro-frontend-production/backend"
    echo "  node -e \""
    echo "  const jwt = require('jsonwebtoken');"
    echo "  const token = jwt.sign("
    echo "    { sub: '2ZPhoXxter4L9sjFQbqLv', email: 'test@maestro.ai', role: 'admin' },"
    echo "    'maestro-production-secret-change-in-production-2024',"
    echo "    { expiresIn: '24h' }"
    echo "  );"
    echo "  console.log(token);"
    echo "  \""
    echo ""
    echo "Then run:"
    echo "  export JWT_TOKEN='<generated_token>'"
    echo "  ./run_e2e_agent.sh"
    exit 1
fi

# Set optional EPIC_KEY from argument
if [ -n "$1" ]; then
    export EPIC_KEY="$1"
    echo -e "${GREEN}✅ Using specified Epic: $EPIC_KEY${NC}"
else
    echo -e "${YELLOW}ℹ️  No Epic specified - will fetch first 'To Do' epic${NC}"
fi

# Set API URLs
export MAESTRO_API_URL="${MAESTRO_API_URL:-http://localhost:3100/api}"
export QF_API_URL="${QF_API_URL:-http://localhost:8000}"

echo -e "${BLUE}ℹ️  Configuration:${NC}"
echo "  Maestro API: $MAESTRO_API_URL"
echo "  Quality-Fabric API: $QF_API_URL"
echo "  Output: /tmp/e2e_agent_output/"
echo ""

# Check if services are running
echo -e "${BLUE}🔍 Checking services...${NC}"

if ! curl -s "$MAESTRO_API_URL/health" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  WARNING: Maestro API not responding at $MAESTRO_API_URL${NC}"
    echo "  Start the service:"
    echo "    cd ~/projects/maestro-frontend-production/backend && npm run dev"
fi

if ! curl -s "$QF_API_URL/api/health" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  WARNING: Quality-Fabric API not responding at $QF_API_URL${NC}"
    echo "  Start the service if needed"
fi

echo ""

# Run the agent
echo -e "${GREEN}🚀 Starting E2E Development & QA Agent...${NC}"
echo ""

cd "$(dirname "$0")"
python3 e2e_dev_qa_agent.py

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Workflow completed successfully!${NC}"
else
    echo -e "${RED}❌ Workflow completed with failures (exit code: $EXIT_CODE)${NC}"
fi

echo ""
echo -e "${BLUE}📁 Output files saved to: /tmp/e2e_agent_output/${NC}"
ls -lh /tmp/e2e_agent_output/ 2>/dev/null || echo "  (no files generated)"

exit $EXIT_CODE
