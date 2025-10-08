# MAESTRO Configuration Guide

**Date**: 2025-10-03
**Version**: 3.0.0
**Status**: Complete

---

## Overview

MAESTRO v3.0 uses a comprehensive, centralized configuration system that eliminates hardcoded values and provides environment-specific settings management.

**Key Benefits**:
- ✅ No hardcoded ports, paths, or URLs
- ✅ Environment-specific configurations
- ✅ Centralized workflow definitions
- ✅ Easy deployment across environments
- ✅ Type-safe configuration with Pydantic

---

## Configuration Architecture

### Components

1. **`src/config/settings.py`** - Main configuration with environment variables
2. **`src/config/workflow_config.py`** - Workflow presets and persona lists
3. **`.env` files** - Environment-specific values

### Configuration Priority

```
Environment Variables > .env file > Default Values
```

---

## Configuration Files

### `.env` - Development (Default)

Located at `/home/ec2-user/projects/maestro-engine/.env`

```bash
# Load this file for development
ENVIRONMENT=development
ENGINE_PORT=5000
BFF_PORT=4001
# ... etc
```

### `.env.production` - Production

Use this configuration for production deployments:

```bash
# Load this file for production
ENVIRONMENT=production
ENGINE_PORT=5000
ENGINE_URL=https://maestro-api.your-domain.com
# ... etc
```

### `.env.test` - Testing/CI

Use this configuration for automated testing:

```bash
# Load this file for tests
ENVIRONMENT=test
ENGINE_PORT=15000
BFF_PORT=14001
# ... etc
```

### `.env.template` - Template

Copy this file to create custom environments.

---

## Configuration Categories

### 1. Service Configuration

**Ports and URLs** (no longer hardcoded!)

```bash
# MAESTRO Engine
ENGINE_HOST=0.0.0.0
ENGINE_PORT=5000
ENGINE_URL=http://localhost:5000

# Unified BFF Service
BFF_HOST=0.0.0.0
BFF_PORT=4001
BFF_URL=http://localhost:4001

# Frontend
FRONTEND_URL=http://localhost:4200
FRONTEND_PORT=4200

# Redis
REDIS_URL=redis://localhost:6379
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 2. File Paths

**Working Directories** (no longer hardcoded!)

```bash
# Project workspaces
PROJECTS_DIR=/tmp/maestro_projects

# Output files
OUTPUT_DIR=/tmp/maestro_output

# Temporary files
TEMP_DIR=/tmp/maestro_temp

# Log files
ENGINE_LOG_FILE=/tmp/maestro_engine.log
BFF_LOG_FILE=/tmp/bff_service.log

# PID files
ENGINE_PID_FILE=/tmp/maestro_engine.pid
BFF_PID_FILE=/tmp/bff_service.pid
```

### 3. Workflow Configuration

**Default Persona Lists** (no longer hardcoded!)

Previously hardcoded in code:
```python
# OLD - hardcoded in persona_workflow_api.py
personas = [
    "requirement_analyst",
    "solution_architect",
    "ui_ux_designer",
    # ... 7 more personas
]
```

Now configured via:
```python
# NEW - uses workflow config
from config import get_workflow_config
workflow_config = get_workflow_config()
personas = workflow_config.GUARDIAN_WORKFLOW.personas
```

**Available Presets**:
- `FULL_SDLC` - All 11 personas
- `GUARDIAN_WORKFLOW` - Supervised SDLC (default)
- `ACCELERATOR_WORKFLOW` - Fast autonomous execution
- `REQUIREMENTS_PHASE` - Requirements only
- `DESIGN_PHASE` - Architecture + UI/UX
- `IMPLEMENTATION_PHASE` - Development team
- `TESTING_PHASE` - QA + Security
- `DEPLOYMENT_PHASE` - DevOps + Docs
- Plus specialized workflows (frontend_only, backend_only, security_audit)

### 4. Security Settings

```bash
# JWT Configuration
JWT_SECRET_KEY=your_secret_key
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60

# CORS
CORS_ORIGINS=["*"]

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
```

### 5. Service Integration

```bash
# Quality Fabric
QUALITY_FABRIC_ENABLED=false
QUALITY_FABRIC_URL=http://localhost:8000

# Template Registry
TEMPLATE_REGISTRY_ENABLED=false
TEMPLATE_REGISTRY_URL=http://localhost:9600

# RAG Service
RAG_ENABLED=false
RAG_SERVICE_URL=http://localhost:9803
```

---

## Usage Examples

### 1. Access Configuration in Code

```python
from config import get_settings

# Get settings instance
settings = get_settings()

# Use configuration values
port = settings.engine_port
redis_url = settings.redis_url
project_dir = settings.get_project_dir(session_id)
```

### 2. Access Workflow Configuration

```python
from config import get_workflow_config

# Get workflow config
workflow_config = get_workflow_config()

# Get default personas
personas = workflow_config.GUARDIAN_WORKFLOW.personas

# Get specific preset
preset = workflow_config.get_preset("accelerator")
if preset:
    personas = preset.personas
    execution_mode = preset.execution_mode
```

### 3. Start Services with Different Environments

**Development** (default):
```bash
cd /home/ec2-user/projects/maestro-engine
python3.11 src/maestro_engine_app.py
```

**Production**:
```bash
# Method 1: Copy production config
cp .env.production .env
python3.11 src/maestro_engine_app.py

# Method 2: Set environment variable
export ENVIRONMENT=production
python3.11 src/maestro_engine_app.py
```

**Testing**:
```bash
# Method 1: Copy test config
cp .env.test .env
python3.11 src/maestro_engine_app.py

# Method 2: Override specific values
export ENGINE_PORT=15000
export BFF_PORT=14001
python3.11 src/maestro_engine_app.py
```

### 4. Override Specific Values

Environment variables take precedence over .env files:

```bash
# Override just the port
export ENGINE_PORT=6000
python3.11 src/maestro_engine_app.py

# Override multiple values
export ENGINE_PORT=6000
export REDIS_URL=redis://production-redis:6379
python3.11 src/maestro_engine_app.py
```

---

## Workflow Preset System

### Built-in Presets

#### Full SDLC
```python
workflow_config.FULL_SDLC.personas
# ["requirement_analyst", "solution_architect", ..., "technical_writer"]
```

#### Guardian Mode (Default)
```python
workflow_config.GUARDIAN_WORKFLOW.personas
# Supervised SDLC with checkpoints
```

#### Accelerator Mode
```python
workflow_config.ACCELERATOR_WORKFLOW.personas
# Fast, autonomous execution
```

### Custom Workflows

Create custom workflow configurations in YAML:

**File**: `config/custom_workflows.yaml`
```yaml
workflows:
  my_custom_workflow:
    description: "My custom workflow"
    personas:
      - requirement_analyst
      - frontend_developer
      - qa_engineer
    execution_mode: sequential
    enable_mcp: true
    enable_rag: false
    tags: ["custom", "minimal"]
```

Load in code:
```python
from pathlib import Path
from config import get_workflow_config

workflow_config = get_workflow_config()
custom_workflows = workflow_config.from_yaml(
    Path("config/custom_workflows.yaml")
)
```

---

## Configuration Reference

### Settings Class Properties

#### Service Configuration
- `engine_host` - Engine host (default: "0.0.0.0")
- `engine_port` - Engine port (default: 5000)
- `engine_url` - Engine URL (default: "http://localhost:5000")
- `bff_host` - BFF host (default: "0.0.0.0")
- `bff_port` - BFF port (default: 4001)
- `bff_url` - BFF URL (default: "http://localhost:4001")
- `redis_url` - Redis connection URL (default: "redis://localhost:6379")

#### File Paths
- `projects_dir` - Project workspaces (default: /tmp/maestro_projects)
- `output_dir` - Output files (default: /tmp/maestro_output)
- `temp_dir` - Temporary files (default: /tmp/maestro_temp)
- `engine_log_file` - Engine logs (default: /tmp/maestro_engine.log)
- `bff_log_file` - BFF logs (default: /tmp/bff_service.log)

#### Workflow Settings
- `default_execution_mode` - Default mode: dag, sequential, parallel (default: "dag")
- `workflow_timeout` - Workflow timeout in seconds (default: 3600)
- `persona_timeout` - Single persona timeout in seconds (default: 300)
- `max_concurrent_workflows` - Max concurrent executions (default: 10)

#### Security
- `jwt_secret_key` - JWT secret
- `cors_origins` - Allowed CORS origins
- `rate_limit_enabled` - Enable rate limiting
- `rate_limit_requests` - Max requests per window

#### Logging
- `log_level` - DEBUG, INFO, WARNING, ERROR, CRITICAL
- `log_format` - json or text
- `enable_structured_logging` - Enable structured logs

### Helper Methods

```python
settings = get_settings()

# Get project directory for session
project_dir = settings.get_project_dir("session_123")
# Returns: Path("/tmp/maestro_projects/guardian_session_123")

# Get Redis connection parameters
redis_params = settings.get_redis_connection_params()
# Returns: {"host": "localhost", "port": 6379, "db": 0, ...}

# Check environment
if settings.is_production:
    # Production-specific logic
    pass

if settings.is_development:
    # Development-specific logic
    pass

# Ensure directories exist
settings.ensure_directories()
```

---

## Migration from Hardcoded Values

### Before (Hardcoded)

```python
# OLD - maestro_engine_app.py
port = 5000
host = "0.0.0.0"

# OLD - persona_workflow_api.py
work_dir = Path(f"/tmp/maestro_projects/guardian_{session_id}")
personas = [
    "requirement_analyst",
    "solution_architect",
    # ... hardcoded list
]

# OLD - redis_state_manager.py
redis_url = "redis://localhost:6379"
```

### After (Configuration)

```python
# NEW - maestro_engine_app.py
from config import get_settings
settings = get_settings()
port = settings.engine_port
host = settings.engine_host

# NEW - persona_workflow_api.py
from config import get_settings, get_workflow_config
settings = get_settings()
workflow_config = get_workflow_config()
work_dir = settings.get_project_dir(session_id)
personas = workflow_config.GUARDIAN_WORKFLOW.personas

# NEW - redis_state_manager.py
from config import get_settings
settings = get_settings()
redis_url = settings.redis_url
```

---

## Environment-Specific Deployment

### Development

```bash
# Uses .env (already exists)
cd /home/ec2-user/projects/maestro-engine
python3.11 src/maestro_engine_app.py
```

### Staging

```bash
# Create .env.staging or set environment variables
export ENVIRONMENT=staging
export ENGINE_URL=https://maestro-staging.your-domain.com
export REDIS_URL=redis://staging-redis:6379
python3.11 src/maestro_engine_app.py
```

### Production

```bash
# Use .env.production or environment variables from secrets manager
export ENVIRONMENT=production
export ENGINE_URL=https://maestro.your-domain.com
export REDIS_URL=redis://prod-redis:6379
export JWT_SECRET_KEY=$(aws secretsmanager get-secret-value ...)
python3.11 src/maestro_engine_app.py
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt

# Use environment variables from docker-compose or k8s
CMD ["python3.11", "src/maestro_engine_app.py"]
```

```yaml
# docker-compose.yml
services:
  maestro-engine:
    build: .
    environment:
      - ENVIRONMENT=production
      - ENGINE_PORT=5000
      - REDIS_URL=redis://redis:6379
    env_file:
      - .env.production
```

---

## Best Practices

### 1. Never Commit Secrets

```bash
# .gitignore should include:
.env
.env.local
.env.*.local
```

Keep `.env.template` and `.env.production` (without secrets) in version control.

### 2. Use Secrets Manager in Production

```python
import boto3
from config import get_settings

# Load secrets from AWS Secrets Manager
secrets_client = boto3.client('secretsmanager')
secret = secrets_client.get_secret_value(SecretId='maestro/prod')

# Override settings
settings = get_settings()
settings.jwt_secret_key = secret['jwt_key']
settings.anthropic_api_key = secret['anthropic_key']
```

### 3. Validate Configuration on Startup

```python
from config import get_settings

settings = get_settings()

# Validate required settings
if not settings.anthropic_api_key:
    raise ValueError("ANTHROPIC_API_KEY is required")

if settings.is_production and settings.debug:
    raise ValueError("DEBUG must be false in production")
```

### 4. Environment-Specific Logging

```python
settings = get_settings()

if settings.is_production:
    logging.basicConfig(
        level=logging.WARNING,
        format='json'
    )
else:
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
```

---

## Troubleshooting

### Configuration Not Loading

**Problem**: Changes to .env not reflected

**Solution**:
```python
from config import reload_settings

# Reload configuration
settings = reload_settings()
```

Or restart the service.

### Wrong Environment

**Problem**: Running production config in development

**Solution**:
```bash
# Check current environment
echo $ENVIRONMENT

# Force development
export ENVIRONMENT=development
python3.11 src/maestro_engine_app.py
```

### Missing Configuration

**Problem**: `KeyError` or missing value

**Solution**:
1. Check .env file exists
2. Check variable name spelling
3. Check .env.template for reference
4. Provide default value in settings.py

---

## Configuration Checklist

### Before Deployment

- [ ] Copy appropriate .env file (.env.production for production)
- [ ] Set all required API keys (ANTHROPIC_API_KEY, etc.)
- [ ] Update service URLs for environment
- [ ] Set JWT_SECRET_KEY to secure random value
- [ ] Configure CORS_ORIGINS to allowed domains
- [ ] Set LOG_LEVEL appropriately (WARNING+ for production)
- [ ] Configure file paths for persistent storage
- [ ] Validate Redis connection
- [ ] Test health endpoints
- [ ] Verify workflow presets work correctly

### After Deployment

- [ ] Verify correct environment loaded (check /health endpoint)
- [ ] Test workflow execution
- [ ] Check logs location and format
- [ ] Verify Redis connectivity
- [ ] Test rate limiting
- [ ] Monitor metrics endpoint

---

## Related Documentation

- **Settings Module**: `src/config/settings.py`
- **Workflow Config**: `src/config/workflow_config.py`
- **Environment Files**: `.env`, `.env.template`, `.env.production`, `.env.test`
- **Phase 5 Documentation**: `docs/phases/PHASE_5_TASK_1_COMPLETE.md`

---

**Created**: 2025-10-03
**Version**: 1.0.0
**Status**: Complete
