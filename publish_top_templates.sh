#!/bin/bash
###############################################################################
# Publish Top Templates - Conservative Approach
# Publishes top 3 templates from each category (16 total)
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
echo "  🚀 Publishing Top Templates (Conservative Approach)"
echo "============================================================================"
echo ""
echo "Strategy: Top 3 from each of 6 categories"
echo "Total: 16 templates"
echo ""
echo "Categories:"
echo "  - Backend (3 templates)"
echo "  - DevOps (3 templates)"
echo "  - Frontend (1 template)"
echo "  - Fullstack (3 templates)"
echo "  - Library (3 templates)"
echo "  - Utility (3 templates)"
echo ""
echo "GitHub Account: kulbirminhas-aiinitiative"
echo "Source: /home/ec2-user/projects/maestro-v2/enhanced_lean_output"
echo "============================================================================"
echo ""

# Create temporary directory with only selected templates
TEMP_DIR="/tmp/maestro_top_templates_$(date +%s)"
mkdir -p "$TEMP_DIR"

echo "📋 Copying selected templates..."
cat <<EOF | while read template; do
ultimate_20250930_013156
ultimate_20250930_014703
ultimate_20250930_020432
ultimate_20250930_041554
ultimate_20250930_070736
ultimate_20251001_063615
utcp_20251001_095047
ultimate_20250930_005040
ultimate_20250930_031519
ultimate_20250930_135517
ultimate_20250930_074224
ultimate_20250930_164403
ultimate_20250930_235842
ultimate_20250930_034407
ultimate_20250930_044355
ultimate_20250930_154519
EOF
  if [ -d "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/$template" ]; then
    cp -r "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/$template" "$TEMP_DIR/"
    echo "  ✅ $template"
  fi
done

echo ""
echo "📊 Templates prepared: $(ls -1 $TEMP_DIR | wc -l)"
echo ""
echo "============================================================================"
echo "  🚀 Starting Batch Publishing"
echo "============================================================================"
echo ""

# Run batch publisher on the curated set
poetry run python batch_git_template_publisher.py \
  --source-dir "$TEMP_DIR" \
  --github-token "$GITHUB_TOKEN" \
  --admin-key "$MAESTRO_ADMIN_KEY" \
  --private

echo ""
echo "============================================================================"
echo "  ✅ Publishing Complete!"
echo "============================================================================"
echo ""
echo "Published: 16 templates"
echo ""
echo "Check results:"
echo "  - GitHub: https://github.com/kulbirminhas-aiinitiative?tab=repositories"
echo "  - Filter: maestro-template-*"
echo ""
echo "Cleanup temporary directory: rm -rf $TEMP_DIR"
echo ""
