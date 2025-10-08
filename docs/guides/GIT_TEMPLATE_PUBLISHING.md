# Git-Based Template Publishing Guide

**Date**: 2025-10-01
**Solution**: Option 3 - Git Repository per Project
**Status**: ✅ **READY TO USE**

## Overview

This guide shows you how to publish MAESTRO-generated projects as Git-based templates that integrate with the `maestro-templates` central registry.

### How It Works

```
Generated Project
    ↓
1. Initialize Git Repository
    ↓
2. Create Remote Repo (GitHub/GitLab)
    ↓
3. Push Code to Remote
    ↓
4. Register with maestro-templates API
    ↓
✅ Template Available in Registry
```

---

## Prerequisites

### 1. GitHub Personal Access Token

**Required Scopes**: `repo` (full control of private repositories)

#### Creating a GitHub Token

1. **Go to GitHub Settings**:
   ```
   https://github.com/settings/tokens
   ```

2. **Click "Generate new token (classic)"**

3. **Configure Token**:
   - **Note**: `MAESTRO Template Publishing`
   - **Expiration**: 90 days (or custom)
   - **Scopes**: Check `repo` (this includes):
     - ✅ repo:status
     - ✅ repo_deployment
     - ✅ public_repo
     - ✅ repo:invite
     - ✅ security_events

4. **Generate and Copy Token**

5. **Set Environment Variable**:
   ```bash
   export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```

6. **Persist** (add to `~/.bashrc` or `~/.zshrc`):
   ```bash
   echo 'export GITHUB_TOKEN="ghp_your_token_here"' >> ~/.bashrc
   source ~/.bashrc
   ```

---

### 2. MAESTRO Admin API Key

The `maestro-templates` service requires an admin key for template registration.

#### Finding the Admin Key

**Option 1**: Check `.env` file
```bash
cat /home/ec2-user/projects/maestro-templates/.env | grep ADMIN_KEY
```

**Option 2**: Check configuration
```bash
grep -r "ADMIN_KEY" /home/ec2-user/projects/maestro-templates/config/
```

**Option 3**: Use default (if set)
```bash
# Default admin key (check with maestro-templates team)
export MAESTRO_ADMIN_KEY="your_admin_key_here"
```

---

### 3. Verify Services Running

```bash
# Template Registry
curl -s http://localhost:9600/health | jq

# Quality Fabric
curl -s http://localhost:8000/api/health | jq

# MAESTRO Engine
curl -s http://localhost:8002/health | jq
```

All should return `"status": "healthy"`

---

## Single Project Publishing

### Basic Usage

```bash
cd /home/ec2-user/projects/maestro-engine

# Publish a single project
poetry run python git_template_publisher.py \
  --project-dir /home/ec2-user/projects/maestro-v2/enhanced_lean_output/utcp_20251001_095047 \
  --github-token "$GITHUB_TOKEN" \
  --admin-key "$MAESTRO_ADMIN_KEY"
```

### With Custom Options

```bash
poetry run python git_template_publisher.py \
  --project-dir /path/to/project \
  --repo-name "my-custom-template" \
  --github-token "$GITHUB_TOKEN" \
  --github-org "my-organization" \
  --private \
  --admin-key "$MAESTRO_ADMIN_KEY" \
  --organization "my-company"
```

### Example Output

```
📦 Publishing: utcp_20251001_095047
  📦 Initializing Git repository in utcp_20251001_095047
  ✅ Git initialized
  ✅ Files added to Git
  ✅ Initial commit created
  🐙 Creating GitHub repository: maestro-template-utcp-20251001-095047
  ✅ GitHub repository created: https://github.com/username/maestro-template-utcp-20251001-095047.git
  🚀 Pushing to remote: https://github.com/username/maestro-template-utcp-20251001-095047.git
  ✅ Pushed to remote successfully
  📋 Registering template with maestro-templates
  ✅ Template registered: a1b2c3d4-e5f6-7890-abcd-ef1234567890

✅ Successfully published: maestro-template-utcp-20251001-095047
   Git URL: https://github.com/username/maestro-template-utcp-20251001-095047.git
   Template ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## Batch Publishing (417 Projects)

### Dry Run First (Recommended)

```bash
cd /home/ec2-user/projects/maestro-engine

# Test on 5 projects
poetry run python batch_git_template_publisher.py \
  --limit 5 \
  --dry-run \
  --github-token "$GITHUB_TOKEN" \
  --admin-key "$MAESTRO_ADMIN_KEY"
```

**Output**:
```
🔍 Discovering projects in: /home/ec2-user/projects/maestro-v2/enhanced_lean_output
📦 Discovered 417 projects
⚙️  Limited to 5 projects

🚀 Starting batch Git template publishing
  Projects: 5
  Git Provider: github
  Dry Run: True

[1/5] ==================================================
📦 Project: utcp_20251001_095047
🏷️  Repo Name: maestro-template-utcp-20251001-095047
  🔍 [DRY RUN] Would publish as: maestro-template-utcp-20251001-095047
...
```

---

### Test on 10 Projects

```bash
poetry run python batch_git_template_publisher.py \
  --limit 10 \
  --github-token "$GITHUB_TOKEN" \
  --admin-key "$MAESTRO_ADMIN_KEY"
```

---

### Full Batch (417 Projects)

```bash
# Run in background with output logging
nohup poetry run python batch_git_template_publisher.py \
  --github-token "$GITHUB_TOKEN" \
  --admin-key "$MAESTRO_ADMIN_KEY" \
  --github-org "maestro-ai" \
  > batch_publishing.log 2>&1 &

# Check progress
tail -f batch_publishing.log
```

**Estimated Time**: ~2-4 hours (417 projects × 20-30s each)

**Expected Output**:
```
📊 BATCH PUBLISHING COMPLETE
  Total Projects: 417
  Processed: 417
  Successful: 400
  Failed: 17
  Templates Registered: 400
  Git Only (no template): 0
  Duration: 8342.5s
  Avg Time/Project: 20.0s
```

---

## Configuration Options

### Command-Line Arguments

```bash
--project-dir PATH         # Project directory to publish (single mode)
--source-dir PATH          # Source directory with projects (batch mode)
--repo-name NAME           # Repository name (optional, auto-generated)
--git-provider PROVIDER    # github, gitlab, or local (default: github)
--github-token TOKEN       # GitHub personal access token
--github-org ORG           # GitHub organization (optional)
--gitlab-token TOKEN       # GitLab personal access token
--private                  # Make repositories private (recommended)
--registry-url URL         # Template registry URL (default: http://localhost:9600)
--admin-key KEY            # Admin API key for template registry
--organization ORG         # Template organization name (default: maestro-generated)
--limit N                  # Process only N projects (batch mode)
--dry-run                  # Show what would be published without making changes
--verbose                  # Show detailed output
```

### Environment Variables

```bash
# Recommended: Set in ~/.bashrc or ~/.zshrc
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export GITHUB_ORG="maestro-ai"
export MAESTRO_ADMIN_KEY="your_admin_key_here"
```

---

## Integration with E2E Workflow

### Automatic Publishing After Code Generation

Update `src/mcp/enhanced_lean_ultimate_mega_team_utcp.py` to automatically publish:

```python
# Add at the end of execute_enhanced_workflow()

if result["success"] and len(result.get("files_generated", [])) > 0:
    # Publish as Git template
    try:
        from git_template_publisher import GitTemplatePublisher, GitConfig, TemplateRegistrationConfig
        import os

        git_config = GitConfig(
            git_provider="github",
            github_token=os.getenv("GITHUB_TOKEN", ""),
            github_org=os.getenv("GITHUB_ORG", ""),
            make_private=True
        )

        template_config = TemplateRegistrationConfig(
            registry_url="http://localhost:9600",
            admin_api_key=os.getenv("MAESTRO_ADMIN_KEY", ""),
            organization="maestro-generated"
        )

        async with GitTemplatePublisher(git_config, template_config) as publisher:
            publish_result = await publisher.publish_project(self.project_path)

            if publish_result["success"]:
                result["template_id"] = publish_result["template_id"]
                result["git_url"] = publish_result["git_url"]
                logging.info(f"✅ Template published: {publish_result['template_id']}")
            else:
                logging.warning(f"⚠️ Template publishing failed: {publish_result.get('error')}")

    except Exception as e:
        logging.warning(f"⚠️ Failed to publish template: {e}")
```

---

## Repository Naming Convention

### Auto-Generated Names

Projects are converted to repository names with this format:

```
maestro-template-{project-name}
```

**Examples**:
- `utcp_20251001_095047` → `maestro-template-utcp-20251001-095047`
- `simple_web_page` → `maestro-template-simple-web-page`
- `website-aiinitiative-co` → `maestro-template-website-aiinitiative-co`

### Custom Names

```bash
poetry run python git_template_publisher.py \
  --project-dir /path/to/project \
  --repo-name "my-custom-name"
```

---

## GitHub Organization Setup

### Using Personal Account

```bash
# No organization specified - uses personal account
poetry run python batch_git_template_publisher.py \
  --github-token "$GITHUB_TOKEN"
```

**Repositories created in**: `https://github.com/your-username/`

---

### Using Organization

```bash
# Specify organization
poetry run python batch_git_template_publisher.py \
  --github-token "$GITHUB_TOKEN" \
  --github-org "maestro-ai"
```

**Repositories created in**: `https://github.com/maestro-ai/`

**Requirements**:
- You must have admin access to the organization
- Organization must exist
- Token must have `repo` scope

---

## Troubleshooting

### Error: "GitHub token required"

**Solution**:
```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

Or pass directly:
```bash
--github-token "ghp_your_token_here"
```

---

### Error: "Admin key required"

**Solution**:
```bash
export MAESTRO_ADMIN_KEY="your_admin_key"
```

Or find it:
```bash
grep -r "ADMIN_KEY" /home/ec2-user/projects/maestro-templates/.env
```

---

### Error: "Repository already exists"

**Cause**: Repository name conflict

**Solution**:
1. Use custom name:
   ```bash
   --repo-name "unique-name-v2"
   ```

2. Or delete existing repository:
   ```bash
   # Via GitHub web interface or API
   ```

---

### Error: "Failed to push to remote"

**Possible causes**:
- Invalid GitHub token
- Token doesn't have `repo` scope
- Network issues

**Solution**:
1. Verify token:
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
   ```

2. Check scopes:
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" -I https://api.github.com/user | grep X-OAuth-Scopes
   ```

Should include `repo`

---

### Error: "Template registration failed"

**Possible causes**:
- maestro-templates service not running
- Invalid admin key
- Template already exists

**Solution**:
1. Check service health:
   ```bash
   curl http://localhost:9600/health
   ```

2. Verify admin key:
   ```bash
   curl -X POST http://localhost:9600/api/v1/admin/templates \
     -H "X-Admin-Key: $MAESTRO_ADMIN_KEY" \
     -H "Content-Type: application/json" \
     -d '{"git_url": "test"}'
   # Should NOT return 401 Unauthorized
   ```

---

## Verification

### Check GitHub Repositories

```bash
# List your repositories
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user/repos?per_page=100 | \
  jq '.[] | select(.name | startswith("maestro-template")) | .name'
```

---

### Check Template Registry

```bash
# Count templates
curl -s http://localhost:9600/api/v1/templates | jq '.total'

# Should increase from 18 to 418+ (18 + 400 from batch)
```

---

### View Template Details

```bash
# Search for specific template
curl -s "http://localhost:9600/api/v1/templates/search?query=utcp" | jq '.templates[0]'
```

---

## Performance Optimization

### Parallel Processing

Currently processes sequentially to avoid rate limiting. To speed up:

1. **Increase workers** (after testing):
   ```python
   # In batch_git_template_publisher.py
   # Add semaphore for parallel processing
   semaphore = asyncio.Semaphore(3)  # 3 concurrent
   ```

2. **Reduce delay**:
   ```python
   # Line: await asyncio.sleep(2)
   await asyncio.sleep(0.5)  # Reduce to 0.5s
   ```

**Warning**: May trigger GitHub rate limits (5000 requests/hour)

---

## Cost Considerations

### GitHub Limits

**Free Tier**:
- Unlimited public repositories
- Unlimited private repositories
- 5000 API requests/hour

**Pro/Team/Enterprise**:
- Increased API rate limits
- Advanced security features

**Recommendation**: Use **private repositories** for generated code

---

### Storage

**417 projects** × **~10 files/project** × **~5KB/file** = **~20MB total**

**Cost**: Free on GitHub (even for private repos)

---

## Security Best Practices

### Token Security

✅ **DO**:
- Use environment variables
- Set token expiration (90 days)
- Use minimal scopes (`repo` only)
- Rotate tokens periodically

❌ **DON'T**:
- Commit tokens to Git
- Share tokens
- Use tokens without expiration

---

### Repository Visibility

**Recommendation**: Use `--private` flag

**Rationale**:
- Generated code may contain sensitive logic
- Prevents public exposure
- Can be made public later if needed

---

## Next Steps

### Immediate Actions

1. **Set up GitHub token** (5 minutes)
2. **Get admin key** (2 minutes)
3. **Test single project** (5 minutes)
4. **Run batch on 10 projects** (10 minutes)
5. **Run full batch** (2-4 hours)

### Post-Publishing

1. **Verify template count** increased
2. **Test template retrieval** via API
3. **Monitor GitHub repositories**
4. **Clean up failed publishes** (if any)
5. **Update E2E workflow** to auto-publish

---

## Summary

✅ **Script Created**: `git_template_publisher.py` (single project)
✅ **Batch Script Created**: `batch_git_template_publisher.py` (multiple projects)
✅ **Documentation Complete**: This guide

**Ready to Use**: After setting `GITHUB_TOKEN` and `MAESTRO_ADMIN_KEY`

**Expected Result**: 417 projects → 400+ templates in registry

---

**Status**: ✅ **READY**
**Priority**: 🔴 **HIGH** (Unblock template extraction)
**ETA**: 2-4 hours (batch processing)
