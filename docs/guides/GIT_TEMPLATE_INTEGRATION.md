# E2E Workflow Git Template Integration

**Date**: 2025-10-01
**Status**: ✅ **INTEGRATED AND READY**

## Overview

The MAESTRO Engine E2E workflow now automatically publishes generated projects as Git-based templates after successful code generation and quality validation.

### How It Works

```
User Requirement
    ↓
Generate Code (via Claude SDK)
    ↓
Quality Validation (Quality Fabric)
    ↓
✨ Git Template Publishing (NEW!) ✨
    ↓
Template Registered in Template Registry
```

---

## Features

✅ **Automatic Publishing**: No manual steps required after code generation
✅ **Conditional Activation**: Only runs when credentials are provided
✅ **Non-Blocking**: Failures don't prevent workflow completion
✅ **Full Logging**: Detailed events and logging for troubleshooting
✅ **Private Repositories**: Creates private GitHub repositories by default
✅ **Configurable**: Control via environment variables

---

## Setup

### 1. Set Environment Variables

```bash
# Required: GitHub Personal Access Token
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Required: MAESTRO Admin API Key
export MAESTRO_ADMIN_KEY="your_admin_key_here"

# Optional: GitHub Organization (defaults to personal account)
export GITHUB_ORG="your-github-org"

# Optional: Template Registry URL (defaults to http://localhost:9600)
export MAESTRO_TEMPLATE_REGISTRY_URL="http://localhost:9600"
```

### 2. Persist Environment Variables

Add to `~/.bashrc` or `~/.zshrc`:

```bash
echo 'export GITHUB_TOKEN="ghp_your_token_here"' >> ~/.bashrc
echo 'export MAESTRO_ADMIN_KEY="your_admin_key_here"' >> ~/.bashrc
source ~/.bashrc
```

---

## Usage

### Basic E2E Workflow (With Auto-Publishing)

```bash
cd /home/ec2-user/projects/maestro-engine

# Run E2E workflow - template will be automatically published
poetry run python src/mcp/enhanced_lean_ultimate_mega_team_utcp.py \
  "Create a REST API for user management"
```

**Output**:
```
📋 Requirement: Create a REST API for user management
🔗 Using UTCP-enabled workflow
⚙️  Generating code...
✅ Code generated: 8 files in 35.2s
🔍 Running quality validation...
✅ Quality validation complete: 85.5/100
📦 Publishing Git template...
  📦 Initializing Git repository in rest-api-user-management
  ✅ Git initialized
  🐙 Creating GitHub repository: maestro-template-rest-api-user-management
  ✅ GitHub repository created: https://github.com/username/maestro-template-rest-api-user-management.git
  🚀 Pushing to remote...
  ✅ Pushed to remote successfully
  📋 Registering template with maestro-templates
  ✅ Template registered: a1b2c3d4-e5f6-7890-abcd-ef1234567890

✅ Success: True
🔧 Method: local_claude_tools
📁 Files: 8
🏷️  Template ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
🔗 Git URL: https://github.com/username/maestro-template-rest-api-user-management.git
⏱️  Time: 45.8s
```

---

### Without Auto-Publishing (No Credentials)

If credentials are not set, the workflow continues normally without publishing:

```bash
# No GITHUB_TOKEN or MAESTRO_ADMIN_KEY set
poetry run python src/mcp/enhanced_lean_ultimate_mega_team_utcp.py \
  "Create a simple web page"
```

**Output**:
```
📋 Requirement: Create a simple web page
🔗 Using UTCP-enabled workflow
⚙️  Generating code...
✅ Code generated: 5 files in 28.3s
🔍 Running quality validation...
✅ Quality validation complete: 78.2/100
⏭️  Git template publishing skipped (missing GITHUB_TOKEN or MAESTRO_ADMIN_KEY)

✅ Success: True
🔧 Method: local_claude_tools
📁 Files: 5
⏱️  Time: 32.1s
```

---

## Configuration Options

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITHUB_TOKEN` | Yes* | - | GitHub personal access token with `repo` scope |
| `MAESTRO_ADMIN_KEY` | Yes* | - | Admin API key for template registry |
| `GITHUB_ORG` | No | Personal account | GitHub organization name |
| `MAESTRO_TEMPLATE_REGISTRY_URL` | No | `http://localhost:9600` | Template registry URL |

*Required for automatic Git template publishing

### Repository Configuration

- **Visibility**: Private by default (configurable in code)
- **Repository Name**: Auto-generated as `maestro-template-{project-name}`
- **Branch**: `main` (default)
- **Organization**: `maestro-generated` (template registry organization)

---

## How It Works Internally

### Code Integration Points

**File**: `src/mcp/enhanced_lean_ultimate_mega_team_utcp.py`

#### 1. New Method: `_publish_git_template()` (lines 762-830)

```python
async def _publish_git_template(self, result: Dict[str, Any]):
    """Publish generated project as Git-based template"""
    # Check environment variables
    github_token = os.getenv("GITHUB_TOKEN", "")
    admin_key = os.getenv("MAESTRO_ADMIN_KEY", "")

    if not github_token or not admin_key:
        logging.debug("⏭️ Git template publishing skipped")
        return

    # Import git_template_publisher
    from git_template_publisher import GitTemplatePublisher, GitConfig, TemplateRegistrationConfig

    # Configure
    git_config = GitConfig(
        git_provider="github",
        github_token=github_token,
        github_org=os.getenv("GITHUB_ORG", ""),
        make_private=True
    )

    template_config = TemplateRegistrationConfig(
        registry_url=os.getenv("MAESTRO_TEMPLATE_REGISTRY_URL", "http://localhost:9600"),
        admin_api_key=admin_key,
        organization="maestro-generated"
    )

    # Publish
    async with GitTemplatePublisher(git_config, template_config) as publisher:
        publish_result = await publisher.publish_project(self.project_path)

        if publish_result["success"]:
            result["git_template_published"] = True
            result["git_url"] = publish_result["git_url"]
            result["template_id"] = publish_result["template_id"]
```

#### 2. Workflow Integration (lines 427-432)

```python
# Post-completion quality validation with Quality-Fabric
if result["success"]:
    await self._run_quality_validation(result)

    # Publish as Git-based template (if credentials provided)
    await self._publish_git_template(result)
```

### Event Emission

The integration emits these events for monitoring:

```python
# Started
{"type": "git_template_publishing_started", "project_path": "/path/to/project"}

# Success
{"type": "git_template_published", "git_url": "...", "template_id": "..."}

# Failure
{"type": "git_template_publish_failed", "error": "..."}

# Exception
{"type": "git_template_publish_exception", "error": "..."}
```

---

## Verification

### 1. Check GitHub Repositories

```bash
# List your repositories
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user/repos?per_page=100 | \
  jq '.[] | select(.name | startswith("maestro-template")) | {name, url: .html_url, created: .created_at}'
```

### 2. Check Template Registry

```bash
# Count templates
curl -s http://localhost:9600/api/v1/templates | jq '.total'

# Search for specific template
curl -s "http://localhost:9600/api/v1/templates/search?query=user-management" | \
  jq '.templates[] | {id, name, git_url, organization, created_at}'
```

### 3. View Template Details

```bash
# Get template by ID
curl -s "http://localhost:9600/api/v1/templates/{template_id}" | jq
```

---

## Troubleshooting

### Issue: Template Publishing Skipped

**Symptom**:
```
⏭️ Git template publishing skipped (missing GITHUB_TOKEN or MAESTRO_ADMIN_KEY)
```

**Solution**:
```bash
# Verify environment variables are set
echo $GITHUB_TOKEN
echo $MAESTRO_ADMIN_KEY

# If not set, export them
export GITHUB_TOKEN="ghp_your_token_here"
export MAESTRO_ADMIN_KEY="your_admin_key_here"
```

---

### Issue: GitHub API Error

**Symptom**:
```
⚠️ Template publishing failed: Failed to create GitHub repository
```

**Solution**:
1. Verify token is valid:
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
   ```

2. Check token scopes:
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" -I https://api.github.com/user | grep X-OAuth-Scopes
   ```
   Should include: `repo`

3. Verify rate limits:
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit
   ```

---

### Issue: Template Registration Failed

**Symptom**:
```
⚠️ Template publishing failed: Failed to register template
```

**Solution**:
1. Check Template Registry is running:
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

3. Check logs:
   ```bash
   tail -f /home/ec2-user/projects/maestro-templates/logs/app.log
   ```

---

### Issue: Repository Already Exists

**Symptom**:
```
⚠️ Repository maestro-template-xxx already exists
```

**Solution**:
The publisher will attempt to use the existing repository. If this fails:

1. Delete the existing repository via GitHub UI
2. Or use a different project name
3. Or specify custom repo name (requires code modification)

---

## Benefits

### 1. Zero Manual Work
- No need to manually run `git_template_publisher.py`
- No need to track which projects have been published
- Automatic repository creation and template registration

### 2. Consistent Templates
- Every successful project automatically becomes a reusable template
- Templates include quality scores and validation results
- Git history preserved for all generated code

### 3. Immediate Availability
- Templates available in registry within seconds
- Can be used for future projects immediately
- Searchable via Template Registry API

### 4. Fail-Safe Design
- Publishing failures don't affect workflow completion
- Missing credentials gracefully skip publishing
- All errors logged for troubleshooting

---

## Advanced Usage

### Custom Repository Naming

To customize repository names, modify `git_template_publisher.py`:

```python
def generate_repo_name(self, project_path: Path) -> str:
    """Generate custom repository name"""
    # Your custom logic here
    return f"my-custom-prefix-{project_path.name}"
```

### Custom Template Metadata

To add custom metadata to templates, modify the `register_template` call in `git_template_publisher.py`:

```python
data = {
    "git_url": git_url,
    "git_branch": "main",
    "organization": self.template_config.organization,
    "auto_validate": self.template_config.auto_validate,
    "metadata": {
        "custom_field": "custom_value",
        "tags": ["tag1", "tag2"]
    }
}
```

### Disable Auto-Publishing

To temporarily disable auto-publishing:

```bash
# Unset environment variables
unset GITHUB_TOKEN
unset MAESTRO_ADMIN_KEY
```

Or modify the code to add a config flag:

```python
# In EnhancedTeamConfig dataclass
enable_git_publishing: bool = True

# In _publish_git_template method
if not self.config.enable_git_publishing:
    return
```

---

## Performance Impact

### Additional Time per Workflow

- **Git initialization**: ~1-2s
- **GitHub repository creation**: ~2-3s
- **Git push**: ~3-5s
- **Template registration**: ~1-2s
- **Total overhead**: ~7-12s

### Rate Limits

- **GitHub API**: 5000 requests/hour (authenticated)
- **Template Registry**: No hard limits (local service)

With proper credentials, you can publish ~400 templates/hour.

---

## Migration from Manual Publishing

If you have existing projects that weren't auto-published, use the batch script:

```bash
cd /home/ec2-user/projects/maestro-engine

# Publish all 417 existing projects
poetry run python batch_git_template_publisher.py \
  --source-dir /home/ec2-user/projects/maestro-v2/enhanced_lean_output \
  --github-token "$GITHUB_TOKEN" \
  --admin-key "$MAESTRO_ADMIN_KEY"
```

See `GIT_TEMPLATE_PUBLISHING_GUIDE.md` for details.

---

## Next Steps

### Immediate Actions

1. **Set up credentials**: Export `GITHUB_TOKEN` and `MAESTRO_ADMIN_KEY`
2. **Test workflow**: Run E2E workflow with a simple requirement
3. **Verify template**: Check GitHub and Template Registry
4. **Batch publish existing projects**: Run `batch_git_template_publisher.py`

### Future Enhancements

1. **Template versioning**: Track versions of published templates
2. **Template analytics**: Monitor template usage and popularity
3. **Template updates**: Re-publish updated templates
4. **Template categories**: Auto-categorize based on detected patterns
5. **Template quality gates**: Only publish templates above quality threshold

---

## Summary

✅ **Integrated**: Git template publishing now built into E2E workflow
✅ **Automatic**: No manual steps required
✅ **Optional**: Only runs when credentials provided
✅ **Fail-Safe**: Errors don't block workflow completion
✅ **Production-Ready**: Ready for immediate use

**Next**: Set up credentials and run your first auto-published workflow!

---

**Documentation Complete** ✅
**Status**: ✅ **READY TO USE**
**Priority**: 🟢 **ENHANCEMENT COMPLETE**
