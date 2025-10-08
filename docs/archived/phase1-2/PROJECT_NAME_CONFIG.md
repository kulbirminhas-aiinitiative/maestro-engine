# Project Name Configuration Guide

**Date**: 2025-10-01
**Feature**: Configurable project output directory with auto-naming

## Overview

The MAESTRO Engine E2E workflow now supports flexible project naming and directory configuration.

**Default Output Path**: `/home/ec2-user/projects/deployment/{project_name}/`

## How It Works

### 1. **Auto-Generated Project Names** (Default)

The system extracts a project name from your requirement automatically:

```bash
poetry run python src/mcp/enhanced_lean_ultimate_mega_team_utcp.py \
  "Create a website like aiinitiative.co.uk, mapping all features"
```

**Output Directory**: `/home/ec2-user/projects/deployment/website-aiinitiative-co/`

**Extraction Logic**:
- Extracts alphabetic words from requirement
- Skips common words (create, build, make, the, a, for, with, and, or)
- Takes first 3 meaningful words
- Joins with hyphens

**Examples**:

| Requirement | Generated Project Name |
|-------------|----------------------|
| "Create a website like aiinitiative.co.uk..." | `website-aiinitiative-co` |
| "Create a simple web page with a header" | `simple-web-page` |
| "Build a todo list application" | `todo-list-application` |
| "Make an e-commerce platform" | `e-commerce-platform` |

---

### 2. **Custom Project Name** (Recommended)

Specify a custom project name via config:

```python
from mcp.enhanced_lean_ultimate_mega_team_utcp import (
    execute_enhanced_lean_workflow_utcp,
    EnhancedTeamConfig
)

config = EnhancedTeamConfig(
    enable_utcp=True,
    project_name="ai-initiative-platform"  # Custom name
)

result = await execute_enhanced_lean_workflow_utcp(
    "Create a website like aiinitiative.co.uk...",
    config
)
```

**Output Directory**: `/home/ec2-user/projects/deployment/ai-initiative-platform/`

---

### 3. **Full Custom Path** (Advanced)

Override the entire path:

```python
config = EnhancedTeamConfig(
    enable_utcp=True,
    project_path="/home/ec2-user/custom/location/my-project"
)

result = await execute_enhanced_lean_workflow_utcp(requirement, config)
```

**Output Directory**: `/home/ec2-user/custom/location/my-project/`

---

## Configuration Options

### EnhancedTeamConfig Parameters

```python
@dataclass
class EnhancedTeamConfig:
    # Project location options (use ONE of these):
    project_name: str = ""       # Just the folder name (recommended)
    project_path: str = ""       # Full absolute path (overrides project_name)

    # Other config...
    enable_utcp: bool = True
    enable_rag: bool = True
    enable_mcp: bool = True
    selected_personas: List[str] = None
```

**Priority**:
1. If `project_path` is set → use full path as-is
2. Else if `project_name` is set → use `/home/ec2-user/projects/deployment/{project_name}/`
3. Else → auto-generate from requirement

---

## Usage Examples

### Example 1: Auto-Generated Name (Simple)

```bash
cd /home/ec2-user/projects/maestro-engine
poetry run python src/mcp/enhanced_lean_ultimate_mega_team_utcp.py \
  "Create a todo list web application"
```

**Output**: `/home/ec2-user/projects/deployment/todo-list-web/`

---

### Example 2: Custom Project Name (Python Script)

```python
#!/usr/bin/env python3
import asyncio
from mcp.enhanced_lean_ultimate_mega_team_utcp import (
    execute_enhanced_lean_workflow_utcp,
    EnhancedTeamConfig
)

async def main():
    config = EnhancedTeamConfig(
        enable_utcp=True,
        project_name="client-portal-v2"  # Custom name
    )

    result = await execute_enhanced_lean_workflow_utcp(
        "Create a client portal with user authentication and dashboard",
        config
    )

    print(f"Project created at: {result.get('project_path')}")
    print(f"Files generated: {len(result.get('files_generated', []))}")

if __name__ == "__main__":
    asyncio.run(main())
```

**Output**: `/home/ec2-user/projects/deployment/client-portal-v2/`

---

### Example 3: Complex Website (Current Test)

```bash
poetry run python src/mcp/enhanced_lean_ultimate_mega_team_utcp.py \
  "Create a website like aiinitiative.co.uk, mapping all the features, user login and backend api for user management"
```

**Auto-Generated Name**: `website-aiinitiative-co`
**Output**: `/home/ec2-user/projects/deployment/website-aiinitiative-co/`

---

### Example 4: Command-Line with Custom Config (Future Enhancement)

```bash
# Could add command-line args support:
poetry run python src/mcp/enhanced_lean_ultimate_mega_team_utcp.py \
  --project-name "ai-platform-2024" \
  "Create a website..."
```

**Output**: `/home/ec2-user/projects/deployment/ai-platform-2024/`

*(Note: Command-line arg parsing not yet implemented - use Python script for now)*

---

## Directory Structure

After running a workflow, your output will be:

```
/home/ec2-user/projects/deployment/
├── website-aiinitiative-co/          # Auto-generated from requirement
│   ├── ai-initiative-platform/       # Project files
│   │   ├── backend/
│   │   │   ├── src/
│   │   │   ├── package.json
│   │   │   └── .env.example
│   │   ├── frontend/
│   │   │   ├── src/
│   │   │   ├── package.json
│   │   │   └── index.html
│   │   ├── docker-compose.yml
│   │   └── README.md
│   └── audit_logs/                   # MCP audit trail
│
├── simple-web-page/                  # Another project
│   ├── index.html
│   ├── styles.css
│   └── script.js
│
└── custom-project-name/              # User-specified name
    └── ...
```

---

## Best Practices

### ✅ Recommended

1. **Use `project_name` for cleaner organization**:
   ```python
   config = EnhancedTeamConfig(project_name="meaningful-name")
   ```

2. **Use naming conventions**:
   - Lowercase with hyphens: `ai-platform-v2`
   - Include version if iterating: `client-portal-v1`, `client-portal-v2`
   - Use descriptive names: `user-auth-api` not `project1`

3. **Auto-generation for quick tests**:
   - Let the system extract names from requirements
   - Good for rapid prototyping

### ❌ Avoid

1. **Don't hardcode full paths in code** - use `project_name` instead
2. **Don't use spaces** in project names - use hyphens
3. **Don't use special characters** - stick to `a-z`, `0-9`, `-`, `_`

---

## Migration from Old Path

**Old Default**: `/home/ec2-user/projects/maestro-v2/enhanced_lean_output/utcp_{timestamp}/`
**New Default**: `/home/ec2-user/projects/deployment/{project_name}/`

### For Existing Projects

If you have existing projects in the old location:

```bash
# Move to new location
mv /home/ec2-user/projects/maestro-v2/enhanced_lean_output/utcp_20251001_095047 \
   /home/ec2-user/projects/deployment/simple-web-page
```

---

## Troubleshooting

### Issue: Directory Already Exists

If a project name already exists, the workflow will **use the existing directory** and add/update files.

**Solution**: Use a unique project name or add version suffix:

```python
config = EnhancedTeamConfig(project_name="my-project-v2")
```

### Issue: Permission Denied

**Solution**: Ensure `/home/ec2-user/projects/deployment/` is writable:

```bash
mkdir -p /home/ec2-user/projects/deployment
chmod 755 /home/ec2-user/projects/deployment
```

### Issue: Project Name Too Long

Auto-generated names are limited to 3 words. If you need more specific names, use custom `project_name`:

```python
config = EnhancedTeamConfig(
    project_name="ai-initiative-website-clone-with-user-management"
)
```

---

## Future Enhancements

- [ ] Add command-line argument: `--project-name`
- [ ] Add timestamp suffix option: `project-name-20251001`
- [ ] Add validation for project name format
- [ ] Add conflict resolution (auto-increment: `project-v1`, `project-v2`)
- [ ] Support environment variable: `MAESTRO_DEPLOYMENT_PATH`

---

## Summary

**Default Behavior**: Auto-extract project name from requirement
**Recommended Usage**: Set `project_name` in config
**Advanced Usage**: Set full `project_path` for custom locations

**Standard Path**: Always `/home/ec2-user/projects/deployment/`
**Configurable**: Only the project folder name

---

**Status**: ✅ **Implemented and Ready**
**Next Run**: Will automatically use new deployment directory structure
