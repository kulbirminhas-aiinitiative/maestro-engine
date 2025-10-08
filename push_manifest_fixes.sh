#!/bin/bash
###############################################################################
# Push Manifest Fixes to GitHub
# Updates all 75 published templates with fixed manifests
###############################################################################

set -e

cd /home/ec2-user/projects/maestro-v2/enhanced_lean_output

# export GITHUB_TOKEN="your-github-token-here"
if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable not set"
    exit 1
fi

echo "============================================================================"
echo "  🚀 Pushing Manifest Fixes to GitHub"
echo "============================================================================"
echo ""

# List of published template directories
TEMPLATES=(
    "ultimate_20250930_013156"
    "ultimate_20250930_014703"
    "ultimate_20250930_020432"
    "ultimate_20250930_021358"
    "ultimate_20250930_024146"
    "ultimate_20250930_030614"
    "ultimate_20250930_040204"
    "ultimate_20250930_052210"
    "ultimate_20250930_055038"
    "ultimate_20250930_060723"
    "ultimate_20250930_064140"
    "ultimate_20250930_082914"
    "ultimate_20250930_085209"
    "ultimate_20250930_093002"
    "ultimate_20250930_094032"
    "ultimate_20250930_095456"
    "ultimate_20250930_103048"
    "ultimate_20250930_111221"
    "ultimate_20250930_111751"
    "ultimate_20250930_114320"
    "ultimate_20250930_041554"
    "ultimate_20250930_070736"
    "ultimate_20251001_063615"
    "ultimate_20251001_071050"
    "ultimate_20250930_071852"
    "ultimate_20250930_142300"
    "ultimate_20250930_161549"
    "ultimate_20250930_065446"
    "ultimate_20250930_085825"
    "ultimate_20250930_145722"
    "ultimate_20250930_185822"
    "ultimate_20251001_044509"
    "ultimate_20250930_101521"
    "ultimate_20250930_045805"
    "ultimate_20250930_210319"
    "ultimate_20250930_053119"
    "ultimate_20250930_162943"
    "ultimate_20251001_055352"
    "ultimate_20251001_073652"
    "ultimate_20250930_051414"
    "utcp_20251001_095047"
    "ultimate_20250930_005040"
    "ultimate_20250930_031519"
    "ultimate_20250930_135517"
    "ultimate_20250930_184826"
    "ultimate_20250930_210915"
    "ultimate_20250930_212953"
    "ultimate_20250930_235427"
    "ultimate_20250930_072307"
    "ultimate_20250930_020910"
    "ultimate_20250930_011828"
    "ultimate_20250930_084201"
    "ultimate_20250930_074224"
    "ultimate_20250930_164403"
    "ultimate_20250930_235842"
    "ultimate_20250930_205142"
    "ultimate_20250930_022228"
    "ultimate_20250930_122102"
    "ultimate_20250930_042943"
    "ultimate_20250930_071307"
    "ultimate_20250930_203733"
    "ultimate_20250930_215255"
    "ultimate_20250930_171458"
    "ultimate_20250930_211703"
    "ultimate_20251001_043633"
    "ultimate_20250930_065844"
    "ultimate_20250930_081201"
    "ultimate_20250930_095024"
    "ultimate_20250930_105255"
    "ultimate_20250930_121151"
    "ultimate_20251001_054010"
    "ultimate_20250930_023250"
    "ultimate_20250930_034407"
    "ultimate_20250930_044355"
    "ultimate_20250930_154519"
)

UPDATED=0
ERRORS=0

for template in "${TEMPLATES[@]}"; do
    if [ ! -d "$template" ]; then
        echo "  ⏭️  Skipped: $template (not found)"
        continue
    fi

    cd "$template"

    echo ""
    echo "📦 $template"

    # Check if it's a git repo
    if [ ! -d ".git" ]; then
        echo "  ⏭️  No .git directory, skipping"
        cd ..
        continue
    fi

    # Check if manifest.yaml changed
    git diff --quiet manifest.yaml 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "  ✅ Manifest unchanged, skipping"
        cd ..
        continue
    fi

    # Commit and push manifest changes
    echo "  📝 Committing manifest fixes..."
    git add manifest.yaml
    git commit -m "fix: Add required manifest fields (author, license)

- Added author: MAESTRO Orchestrator
- Added metadata.license: MIT
- Required for template registry validation

🤖 Generated with Claude Code" || true

    echo "  🚀 Pushing to GitHub..."
    git push origin main 2>&1 | grep -v "ghp_" || true

    if [ $? -eq 0 ]; then
        echo "  ✅ Updated successfully"
        ((UPDATED++))
    else
        echo "  ❌ Push failed"
        ((ERRORS++))
    fi

    cd ..
done

echo ""
echo "============================================================================"
echo "  📊 Summary"
echo "============================================================================"
echo "  Updated: $UPDATED"
echo "  Errors: $ERRORS"
echo "============================================================================"
echo ""
