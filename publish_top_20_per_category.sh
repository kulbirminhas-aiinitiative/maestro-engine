#!/bin/bash
###############################################################################
# Publish Top 20 Templates Per Category
# Publishes top 20 templates from each category (82 total)
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
echo "  🚀 Publishing Top 20 Templates Per Category"
echo "============================================================================"
echo ""
echo "Strategy: Top 20 from each category (or all if less than 20)"
echo "Total: 82 templates"
echo ""
echo "Categories:"
echo "  - Backend (20 templates)"
echo "  - DevOps (20 templates)"
echo "  - Frontend (1 template)"
echo "  - Fullstack (11 templates)"
echo "  - Library (20 templates)"
echo "  - Utility (10 templates)"
echo ""
echo "GitHub Account: kulbirminhas-aiinitiative"
echo "Source: /home/ec2-user/projects/maestro-v2/enhanced_lean_output"
echo "Expected Duration: ~60-70 minutes (82 templates × ~50 seconds each)"
echo "============================================================================"
echo ""

# Create temporary directory with only selected templates
TEMP_DIR="/tmp/maestro_top20_templates_$(date +%s)"
mkdir -p "$TEMP_DIR"

echo "📋 Copying selected templates..."

# Backend (20)
for template in \
  ultimate_20250930_013156 ultimate_20250930_014703 ultimate_20250930_020432 \
  ultimate_20250930_021358 ultimate_20250930_024146 ultimate_20250930_030614 \
  ultimate_20250930_040204 ultimate_20250930_052210 ultimate_20250930_055038 \
  ultimate_20250930_060723 ultimate_20250930_064140 ultimate_20250930_082914 \
  ultimate_20250930_085209 ultimate_20250930_093002 ultimate_20250930_094032 \
  ultimate_20250930_095456 ultimate_20250930_103048 ultimate_20250930_111221 \
  ultimate_20250930_111751 ultimate_20250930_114320
do
  if [ -d "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/$template" ]; then
    cp -r "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/$template" "$TEMP_DIR/"
    echo "  ✅ Backend: $template"
  fi
done

# DevOps (20)
for template in \
  ultimate_20250930_041554 ultimate_20250930_070736 ultimate_20251001_063615 \
  ultimate_20251001_071050 ultimate_20250930_071852 ultimate_20250930_142300 \
  ultimate_20250930_161549 ultimate_20250930_065446 ultimate_20250930_085825 \
  ultimate_20250930_145722 ultimate_20250930_185822 ultimate_20251001_044509 \
  ultimate_20250930_101521 ultimate_20250930_045805 ultimate_20250930_210319 \
  ultimate_20250930_053119 ultimate_20250930_162943 ultimate_20251001_055352 \
  ultimate_20251001_073652 ultimate_20250930_051414
do
  if [ -d "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/$template" ]; then
    cp -r "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/$template" "$TEMP_DIR/"
    echo "  ✅ DevOps: $template"
  fi
done

# Frontend (1)
for template in utcp_20251001_095047
do
  if [ -d "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/$template" ]; then
    cp -r "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/$template" "$TEMP_DIR/"
    echo "  ✅ Frontend: $template"
  fi
done

# Fullstack (11)
for template in \
  ultimate_20250930_005040 ultimate_20250930_031519 ultimate_20250930_135517 \
  ultimate_20250930_184826 ultimate_20250930_210915 ultimate_20250930_212953 \
  ultimate_20250930_235427 ultimate_20250930_072307 ultimate_20250930_020910 \
  ultimate_20250930_011828 ultimate_20250930_084201
do
  if [ -d "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/$template" ]; then
    cp -r "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/$template" "$TEMP_DIR/"
    echo "  ✅ Fullstack: $template"
  fi
done

# Library (20)
for template in \
  ultimate_20250930_074224 ultimate_20250930_164403 ultimate_20250930_235842 \
  ultimate_20250930_205142 ultimate_20250930_022228 ultimate_20250930_122102 \
  ultimate_20250930_042943 ultimate_20250930_071307 ultimate_20250930_203733 \
  ultimate_20250930_215255 ultimate_20250930_171458 ultimate_20250930_211703 \
  ultimate_20251001_043633 ultimate_20250930_065844 ultimate_20250930_081201 \
  ultimate_20250930_095024 ultimate_20250930_105255 ultimate_20250930_121151 \
  ultimate_20251001_054010 ultimate_20250930_023250
do
  if [ -d "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/$template" ]; then
    cp -r "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/$template" "$TEMP_DIR/"
    echo "  ✅ Library: $template"
  fi
done

# Utility (10)
for template in \
  ultimate_20250930_034407 ultimate_20250930_044355 ultimate_20250930_154519 \
  ultimate_20250929_232716 ultimate_20250929_233314 ultimate_20250929_235205 \
  hot_20250930_091214 utcp_20250930_142000 ultimate_20250930_210913 \
  utcp_20251001_094413
do
  if [ -d "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/$template" ]; then
    cp -r "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/$template" "$TEMP_DIR/"
    echo "  ✅ Utility: $template"
  fi
done

echo ""
echo "📊 Templates prepared: $(ls -1 $TEMP_DIR | wc -l)"
echo ""
echo "============================================================================"
echo "  🚀 Starting Batch Publishing to GitHub"
echo "============================================================================"
echo ""

# Run batch publisher on the curated set
poetry run python batch_git_template_publisher.py \
  --source-dir "$TEMP_DIR" \
  --github-token "$GITHUB_TOKEN" \
  --admin-key "$MAESTRO_ADMIN_KEY" \
  --private

RESULT=$?

echo ""
echo "============================================================================"
echo "  ✅ Publishing Complete!"
echo "============================================================================"
echo ""
echo "Published: 82 templates"
echo ""
echo "Check results:"
echo "  - GitHub: https://github.com/kulbirminhas-aiinitiative?tab=repositories"
echo "  - Filter: maestro-template-*"
echo "  - Registry: curl http://localhost:9600/api/v1/templates | jq '.total'"
echo ""
echo "Stats: cat batch_git_publishing_stats.json | jq"
echo ""
echo "Cleanup temporary directory:"
echo "  rm -rf $TEMP_DIR"
echo ""

exit $RESULT
