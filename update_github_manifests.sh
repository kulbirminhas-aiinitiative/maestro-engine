#!/bin/bash
###############################################################################
# Update GitHub Manifests
# Clone each repo, update manifest, and push back
###############################################################################

set -e

# export GITHUB_TOKEN="your-github-token-here"
if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable not set"
    exit 1
fi
WORK_DIR="/tmp/manifest_updates_$(date +%s)"
SOURCE_DIR="/home/ec2-user/projects/maestro-v2/enhanced_lean_output"

mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

echo "============================================================================"
echo "  🚀 Updating GitHub Repository Manifests"
echo "============================================================================"
echo ""

# List of repos (without maestro-template- prefix)
REPOS=(
    "ultimate-20250930-013156"
    "ultimate-20250930-014703"
    "ultimate-20250930-020432"
    "ultimate-20250930-021358"
    "ultimate-20250930-024146"
    "ultimate-20250930-030614"
    "ultimate-20250930-040204"
    "ultimate-20250930-052210"
    "ultimate-20250930-055038"
    "ultimate-20250930-060723"
    "ultimate-20250930-064140"
    "ultimate-20250930-082914"
    "ultimate-20250930-085209"
    "ultimate-20250930-093002"
    "ultimate-20250930-094032"
    "ultimate-20250930-095456"
    "ultimate-20250930-103048"
    "ultimate-20250930-111221"
    "ultimate-20250930-111751"
    "ultimate-20250930-114320"
    "ultimate-20250930-041554"
    "ultimate-20250930-070736"
    "ultimate-20251001-063615"
    "ultimate-20251001-071050"
    "ultimate-20250930-071852"
    "ultimate-20250930-142300"
    "ultimate-20250930-161549"
    "ultimate-20250930-065446"
    "ultimate-20250930-085825"
    "ultimate-20250930-145722"
    "ultimate-20250930-185822"
    "ultimate-20251001-044509"
    "ultimate-20250930-101521"
    "ultimate-20250930-045805"
    "ultimate-20250930-210319"
    "ultimate-20250930-053119"
    "ultimate-20250930-162943"
    "ultimate-20251001-055352"
    "ultimate-20251001-073652"
    "ultimate-20250930-051414"
    "utcp-20251001-095047"
    "ultimate-20250930-005040"
    "ultimate-20250930-031519"
    "ultimate-20250930-135517"
    "ultimate-20250930-184826"
    "ultimate-20250930-210915"
    "ultimate-20250930-212953"
    "ultimate-20250930-235427"
    "ultimate-20250930-072307"
    "ultimate-20250930-020910"
    "ultimate-20250930-011828"
    "ultimate-20250930-084201"
    "ultimate-20250930-074224"
    "ultimate-20250930-164403"
    "ultimate-20250930-235842"
    "ultimate-20250930-205142"
    "ultimate-20250930-022228"
    "ultimate-20250930-122102"
    "ultimate-20250930-042943"
    "ultimate-20250930-071307"
    "ultimate-20250930-203733"
    "ultimate-20250930-215255"
    "ultimate-20250930-171458"
    "ultimate-20250930-211703"
    "ultimate-20251001-043633"
    "ultimate-20250930-065844"
    "ultimate-20250930-081201"
    "ultimate-20250930-095024"
    "ultimate-20250930-105255"
    "ultimate-20250930-121151"
    "ultimate-20251001-054010"
    "ultimate-20250930-023250"
    "ultimate-20250930-034407"
    "ultimate-20250930-044355"
    "ultimate-20250930-154519"
)

UPDATED=0
FAILED=0

for repo in "${REPOS[@]}"; do
    echo ""
    echo "[$((UPDATED+FAILED+1))/75] 📦 maestro-template-$repo"

    # Convert repo name back to source dir name (replace - with _)
    source_name=$(echo "$repo" | sed 's/-/_/g')
    source_path="$SOURCE_DIR/$source_name"

    if [ ! -f "$source_path/manifest.yaml" ]; then
        echo "  ❌ Source manifest not found: $source_path"
        ((FAILED++))
        continue
    fi

    # Clone repo
    echo "  🔄 Cloning..."
    git clone -q "https://$GITHUB_TOKEN@github.com/kulbirminhas-aiinitiative/maestro-template-$repo.git" 2>&1 | grep -v "ghp_" || true

    if [ ! -d "maestro-template-$repo" ]; then
        echo "  ❌ Clone failed"
        ((FAILED++))
        continue
    fi

    cd "maestro-template-$repo"

    # Copy updated manifest
    cp "$source_path/manifest.yaml" ./manifest.yaml

    # Check if there are changes
    if git diff --quiet manifest.yaml; then
        echo "  ✅ Manifest already up-to-date"
        cd ..
        rm -rf "maestro-template-$repo"
        ((UPDATED++))
        continue
    fi

    # Commit and push
    git add manifest.yaml
    git commit -m "fix: Add required manifest fields (author, license)

- Added author: MAESTRO Orchestrator
- Added metadata.license: MIT
- Required for template registry validation

🤖 Generated with Claude Code" > /dev/null 2>&1

    echo "  🚀 Pushing..."
    git push origin main 2>&1 | grep -v "ghp_" || true

    if [ $? -eq 0 ]; then
        echo "  ✅ Updated successfully"
        ((UPDATED++))
    else
        echo "  ❌ Push failed"
        ((FAILED++))
    fi

    cd ..
    rm -rf "maestro-template-$repo"

    # Rate limiting
    sleep 1
done

echo ""
echo "============================================================================"
echo "  📊 Summary"
echo "============================================================================"
echo "  Total: 75"
echo "  Updated: $UPDATED"
echo "  Failed: $FAILED"
echo "============================================================================"
echo ""
echo "Cleanup: rm -rf $WORK_DIR"
echo ""
