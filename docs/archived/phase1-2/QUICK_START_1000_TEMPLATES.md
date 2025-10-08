# Quick Start: Publishing 1000 Templates

**Last Updated:** 2025-10-01
**Tool:** `batch_git_template_publisher_enhanced.py` ⭐ NEW

---

## 🚀 One-Command Solution

The enhanced publisher does **everything** in a single command:
- Auto-classifies projects (language, framework, category)
- Calculates quality scores
- Filters by quality gate
- Deduplicates similar templates
- Applies category limits
- Assigns quality tiers
- Publishes to GitHub + Template Registry

---

## 📋 Prerequisites (5 minutes)

### 1. Set GitHub Token
```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

**Get token:** https://github.com/settings/tokens
- Scope: `repo` (full control)

### 2. Set Admin Key
```bash
export MAESTRO_ADMIN_KEY="maestro-dev-admin-key-67890"
```

### 3. Verify Services Running
```bash
# Template Registry (port 9600)
curl -s http://localhost:9600/health | jq

# Should return: "status": "healthy"
```

---

## 🎯 Recommended: Publish Top 100-150 (2-3 hours)

### Step 1: Dry Run (Preview Only)

```bash
cd /home/ec2-user/projects/maestro-engine

poetry run python batch_git_template_publisher_enhanced.py \
  --source-dir /path/to/1000-projects \
  --quality-gate 80 \
  --max-templates 150 \
  --max-per-category 20 \
  --deduplicate \
  --tier-auto-assign \
  --dry-run
```

**Review output:**
- How many passed quality gate?
- Category distribution balanced?
- Tier assignment correct?

---

### Step 2: Actual Publishing

```bash
nohup poetry run python batch_git_template_publisher_enhanced.py \
  --source-dir /path/to/1000-projects \
  --quality-gate 80 \
  --max-templates 150 \
  --max-per-category 20 \
  --deduplicate \
  --tier-auto-assign \
  --github-token "$GITHUB_TOKEN" \
  --admin-key "$MAESTRO_ADMIN_KEY" \
  --private \
  > batch_publishing.log 2>&1 &

# Monitor progress
tail -f batch_publishing.log
```

---

## 📊 Expected Results

### Pipeline Output:
```
📊 CURATED PUBLISHING COMPLETE

📈 Pipeline Summary:
   Total Discovered: 1000
   Classified: 985
   Passed Quality Gate (≥80): 165
   After Deduplication: 140
   After Category Limits: 130
   Published: 130

🏅 Templates by Tier:
   🥇 Gold (≥90): 35
   🥈 Silver (80-89): 95

📂 Templates by Category:
   backend: 20
   frontend: 20
   fullstack: 18
   api: 20
   utility: 20
   database: 12
   devops: 10

⏱️  Duration: 6,500s (1.8 hours)
```

---

## 🎛️ Adjust Curation Settings

### More Templates (200-300)
```bash
# Lower quality gate to 70
poetry run python batch_git_template_publisher_enhanced.py \
  --source-dir /path/to/1000-projects \
  --quality-gate 70 \
  --max-templates 300 \
  --max-per-category 40 \
  --deduplicate \
  --tier-auto-assign \
  --github-token "$GITHUB_TOKEN" \
  --admin-key "$MAESTRO_ADMIN_KEY" \
  --private
```

### All Templates (NOT Recommended)
```bash
# No filtering
poetry run python batch_git_template_publisher_enhanced.py \
  --source-dir /path/to/1000-projects \
  --quality-gate 0 \
  --github-token "$GITHUB_TOKEN" \
  --admin-key "$MAESTRO_ADMIN_KEY" \
  --private
```

---

## 🔍 Parameter Reference

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `--source-dir` | Project directory | `/path/to/1000-projects` |
| `--quality-gate` | Min quality score (0-100) | `80` = top quality only |
| `--max-templates` | Total template limit | `150` = max 150 templates |
| `--max-per-category` | Per-category limit | `20` = max 20 per category |
| `--deduplicate` | Remove similar templates | Flag (no value) |
| `--tier-auto-assign` | Assign Gold/Silver/Bronze | Flag (no value) |
| `--github-token` | GitHub auth | `$GITHUB_TOKEN` |
| `--admin-key` | Registry auth | `$MAESTRO_ADMIN_KEY` |
| `--private` | Make repos private | Flag (recommended) |
| `--dry-run` | Preview only | Flag (test first) |

---

## ✅ Post-Publishing Verification

### 1. Check GitHub Repos
```bash
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user/repos?per_page=100 | \
  jq '.[] | select(.name | startswith("maestro-template")) | .name' | wc -l

# Should show ~130-150 repos
```

### 2. Check Template Registry
```bash
# Total templates
curl -s http://localhost:9600/api/v1/templates | jq '.total'

# By category
curl -s "http://localhost:9600/api/v1/templates?category=backend" | jq '.total'

# Pinned (Gold/Silver)
curl -s "http://localhost:9600/api/v1/templates?pinned=true" | jq '.templates[] | {name, quality_tier}'
```

---

## 🐛 Troubleshooting

### "GitHub token invalid"
```bash
# Test token
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user

# Should return your GitHub user info
```

### "Admin key unauthorized"
```bash
# Verify key
curl -X POST http://localhost:9600/api/v1/admin/test \
  -H "X-Admin-Key: $MAESTRO_ADMIN_KEY"

# Should NOT return 401
```

### "Classification failed"
```bash
# Check classifier works
cd /home/ec2-user/projects/maestro-engine
poetry run python template_auto_classifier.py single \
  --project-dir /path/to/test-project

# Should output classification JSON
```

---

## 📈 Quality Score Breakdown

Quality scores (0-100) calculated from:

1. **Code Completeness (30 points)**
   - README.md: 10 points
   - manifest.yaml: 10 points
   - File count ≥5: 10 points

2. **Documentation Quality (25 points)**
   - README length >500 chars: 10 points
   - Usage/Installation sections: 8 points
   - Examples section: 7 points

3. **Code Quality (25 points)**
   - Total lines >100: 10 points
   - Recognized framework: 10 points
   - Has tests: 5 points

4. **Features (20 points)**
   - 4 points per detected feature (max 20)

**Tier Assignment:**
- 🥇 Gold (≥90): Pinned, top tier
- 🥈 Silver (80-89): Pinned, high quality
- 🥉 Bronze (70-79): Available, not pinned
- 📄 Standard (<70): Available, not pinned

---

## 📝 Summary

**Recommended Workflow:**
1. ✅ Set `GITHUB_TOKEN` and `MAESTRO_ADMIN_KEY`
2. ✅ Run dry-run to preview
3. ✅ Execute actual publishing
4. ✅ Verify results in GitHub and Registry

**Time Estimate:** 2-3 hours for top 150 templates

**Result:** Clean, curated registry with discoverable high-quality templates!

---

**Tool Location:** `/home/ec2-user/projects/maestro-engine/batch_git_template_publisher_enhanced.py`
**Full Guide:** `/home/ec2-user/projects/maestro-templates/docs/FINAL_1000_TEMPLATES_WORKFLOW.md`
