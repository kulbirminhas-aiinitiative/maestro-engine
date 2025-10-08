#!/bin/bash
# MAESTRO Engine Cleanup Script
#
# Automated cleanup and validation script for code organization.
#
# Part of ADR-007: Code Organization and Cleanup Policy
#
# Usage:
#   scripts/cleanup.sh              # Report mode (dry run)
#   scripts/cleanup.sh --execute    # Execute cleanup actions

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

EXECUTE=false
if [ "$1" == "--execute" ]; then
    EXECUTE=true
fi

echo -e "${BLUE}🧹 MAESTRO Engine Cleanup Script${NC}"
echo "=================================="
echo ""

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}❌ Error: Must run from project root directory${NC}"
    exit 1
fi

# 1. Find duplicate output directories
echo -e "${BLUE}📊 Checking for output directories...${NC}"
OUTPUT_DIRS=$(find . -type d \( -name "*_output" -o -name "output_*" -o -name "deliverables" -o -name "claude_output" -o -name "maestro_output" \) -not -path "./.git/*" -not -path "./venv/*" 2>/dev/null || true)

if [ -n "$OUTPUT_DIRS" ]; then
    COUNT=$(echo "$OUTPUT_DIRS" | wc -l)
    echo -e "${YELLOW}⚠️  Found $COUNT output directory(ies):${NC}"
    echo "$OUTPUT_DIRS" | head -10

    if [ "$EXECUTE" == "true" ]; then
        echo -e "${YELLOW}   Removing output directories...${NC}"
        echo "$OUTPUT_DIRS" | xargs rm -rf
        echo -e "${GREEN}   ✓ Removed${NC}"
    else
        echo -e "${YELLOW}   (Run with --execute to remove)${NC}"
    fi
else
    echo -e "${GREEN}✅ No output directories found${NC}"
fi
echo ""

# 2. Find __pycache__ directories
echo -e "${BLUE}🗑️  Checking for __pycache__ directories...${NC}"
PYCACHE_DIRS=$(find . -type d -name "__pycache__" -not -path "./.git/*" -not -path "./venv/*" 2>/dev/null || true)

if [ -n "$PYCACHE_DIRS" ]; then
    COUNT=$(echo "$PYCACHE_DIRS" | wc -l)
    echo -e "${YELLOW}⚠️  Found $COUNT __pycache__ directory(ies)${NC}"

    if [ "$EXECUTE" == "true" ]; then
        echo -e "${YELLOW}   Removing __pycache__ directories...${NC}"
        echo "$PYCACHE_DIRS" | xargs rm -rf
        echo -e "${GREEN}   ✓ Removed${NC}"
    else
        echo -e "${YELLOW}   (Run with --execute to remove)${NC}"
    fi
else
    echo -e "${GREEN}✅ No __pycache__ directories (clean!)${NC}"
fi
echo ""

# 3. Find .pyc files
echo -e "${BLUE}🗑️  Checking for .pyc files...${NC}"
PYC_FILES=$(find . -type f -name "*.pyc" -not -path "./.git/*" -not -path "./venv/*" 2>/dev/null || true)

if [ -n "$PYC_FILES" ]; then
    COUNT=$(echo "$PYC_FILES" | wc -l)
    echo -e "${YELLOW}⚠️  Found $COUNT .pyc file(s)${NC}"

    if [ "$EXECUTE" == "true" ]; then
        echo -e "${YELLOW}   Removing .pyc files...${NC}"
        echo "$PYC_FILES" | xargs rm -f
        echo -e "${GREEN}   ✓ Removed${NC}"
    else
        echo -e "${YELLOW}   (Run with --execute to remove)${NC}"
    fi
else
    echo -e "${GREEN}✅ No .pyc files${NC}"
fi
echo ""

# 4. Check for TODO/FIXME in production code
echo -e "${BLUE}⚠️  Checking for TODO/FIXME in production code...${NC}"
TODOS=$(grep -r "TODO\|FIXME" src/ --include="*.py" 2>/dev/null || true)

if [ -n "$TODOS" ]; then
    COUNT=$(echo "$TODOS" | wc -l)
    echo -e "${YELLOW}⚠️  Found $COUNT TODO/FIXME comment(s):${NC}"
    echo "$TODOS" | head -10
    echo ""
    echo -e "${YELLOW}   Note: Production code should not contain TODO/FIXME${NC}"
else
    echo -e "${GREEN}✅ No TODO/FIXME in production code${NC}"
fi
echo ""

# 5. Check for large files (>10MB)
echo -e "${BLUE}📦 Checking for large files (>10MB)...${NC}"
LARGE_FILES=$(find . -type f -size +10M -not -path "./.git/*" -not -path "./venv/*" -not -path "./.venv/*" 2>/dev/null || true)

if [ -n "$LARGE_FILES" ]; then
    echo -e "${YELLOW}⚠️  Found large file(s):${NC}"
    echo "$LARGE_FILES" | while read file; do
        SIZE=$(du -h "$file" | cut -f1)
        echo "   $SIZE - $file"
    done
    echo ""
    echo -e "${YELLOW}   Consider adding to .gitignore or storing externally${NC}"
else
    echo -e "${GREEN}✅ No large files${NC}"
fi
echo ""

# 6. Find unused Python files
echo -e "${BLUE}🗑️  Finding unused Python files...${NC}"
if [ -f "scripts/find_unused_files.py" ]; then
    python scripts/find_unused_files.py 2>/dev/null || echo -e "${YELLOW}   (Script available but needs dependencies)${NC}"
else
    echo -e "${YELLOW}   (Script not yet created)${NC}"
fi
echo ""

# 7. Check for hardcoded URLs
echo -e "${BLUE}🔍 Checking for hardcoded URLs...${NC}"
if [ -f "scripts/detect_hardcoded_urls.py" ]; then
    python scripts/detect_hardcoded_urls.py 2>/dev/null || echo -e "${YELLOW}   Found hardcoded URLs - run script for details${NC}"
else
    echo -e "${YELLOW}   (Script not yet created)${NC}"
fi
echo ""

# 8. Disk usage report
echo -e "${BLUE}💾 Disk usage by directory:${NC}"
du -sh */ 2>/dev/null | sort -hr | head -10
echo ""

# 9. Check directory structure compliance
echo -e "${BLUE}📁 Checking directory structure...${NC}"

# Check for archived code in wrong location
if [ -d "src/archived" ]; then
    echo -e "${YELLOW}⚠️  Found src/archived/ - should be _legacy/ or _experiments/ at repo root${NC}"
else
    echo -e "${GREEN}✅ No src/archived/ directory${NC}"
fi

# Check for legacy/experiments at repo root
if [ -d "_legacy" ]; then
    LEGACY_COUNT=$(find _legacy -type f -name "*.py" 2>/dev/null | wc -l)
    echo -e "${GREEN}✓ _legacy/ directory exists ($LEGACY_COUNT files)${NC}"
else
    echo -e "${YELLOW}⚠️  No _legacy/ directory (recommended for archived code)${NC}"
fi

if [ -d "_experiments" ]; then
    EXP_COUNT=$(find _experiments -type f -name "*.py" 2>/dev/null | wc -l)
    echo -e "${GREEN}✓ _experiments/ directory exists ($EXP_COUNT files)${NC}"
else
    echo -e "${YELLOW}⚠️  No _experiments/ directory (recommended for experimental code)${NC}"
fi
echo ""

# Summary
echo "=================================="
echo -e "${BLUE}📊 Summary${NC}"
echo "=================================="

if [ "$EXECUTE" == "true" ]; then
    echo -e "${GREEN}✅ Cleanup executed${NC}"
else
    echo -e "${YELLOW}ℹ️  Dry run mode - no changes made${NC}"
    echo -e "${YELLOW}   Run with --execute to perform cleanup${NC}"
fi

echo ""
echo "🔗 For more info, see: docs/architecture/ADR-007-code-organization.md"
echo ""
