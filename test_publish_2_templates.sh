#!/bin/bash
###############################################################################
# Test Publishing - 2 Templates
# Quick test to verify GitHub publishing works
###############################################################################

set -e

cd /home/ec2-user/projects/maestro-engine

# Set tokens (use environment variables)
# export GITHUB_TOKEN="your-github-token-here"
# export MAESTRO_ADMIN_KEY="your-admin-key-here"
if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable not set"
    exit 1
fi
if [ -z "$MAESTRO_ADMIN_KEY" ]; then
    echo "Error: MAESTRO_ADMIN_KEY environment variable not set"
    exit 1
fi

echo "============================================================================"
echo "  🧪 Testing Template Publishing (2 templates)"
echo "============================================================================"
echo ""
echo "GitHub Account: kulbirminhas-aiinitiative"
echo "Source: /home/ec2-user/projects/maestro-v2/enhanced_lean_output"
echo "Limit: 2 templates"
echo ""
echo "============================================================================"
echo ""

# Run with poetry
poetry run python batch_git_template_publisher.py \
  --source-dir /home/ec2-user/projects/maestro-v2/enhanced_lean_output \
  --limit 2 \
  --github-token "$GITHUB_TOKEN" \
  --admin-key "$MAESTRO_ADMIN_KEY" \
  --private

echo ""
echo "============================================================================"
echo "  ✅ Test Complete!"
echo "============================================================================"
echo ""
echo "Check results:"
echo "  - GitHub: https://github.com/kulbirminhas-aiinitiative?tab=repositories"
echo "  - Registry: curl http://localhost:9600/api/v1/templates | jq '.total'"
echo ""
