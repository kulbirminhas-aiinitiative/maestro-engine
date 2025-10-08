#!/bin/bash
###############################################################################
# Batch Publisher Runner
# Wrapper script to run enhanced batch publisher with proper environment
###############################################################################

set -e

cd /home/ec2-user/projects/maestro-engine

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set tokens if not already set
export GITHUB_TOKEN="${GITHUB_TOKEN:-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}"
export MAESTRO_ADMIN_KEY="${MAESTRO_ADMIN_KEY:-maestro-dev-admin-key-67890}"

echo "============================================================================"
echo "  🚀 MAESTRO Enhanced Batch Template Publisher"
echo "============================================================================"
echo ""
echo "Configuration:"
echo "  GitHub Token: ${GITHUB_TOKEN:0:7}...${GITHUB_TOKEN: -4}"
echo "  Admin Key: ${MAESTRO_ADMIN_KEY:0:10}..."
echo "  Registry: http://localhost:9600"
echo ""
echo "============================================================================"
echo ""

# Run with poetry
poetry run python batch_git_template_publisher_enhanced.py "$@"
