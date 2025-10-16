# API Gateway Integration Guide - Maestro Engine

**Status**: ✅ Configured
**Gateway Port**: 8080
**Service Name**: maestro-engine (coordinator, orchestration, mcp, rag)
**Last Updated**: 2025-10-04

---

## Overview

Maestro Engine services now integrate with the API Gateway for all inter-service communication. This includes:

- **Coordinator** (port 8002)
- **Orchestration** (port 8004)
- **MCP** (port 9800)
- **RAG** (port 9803)

**Key Change**: All calls to external services (templates, quality-fabric) now go through `gateway:8080`

---

## What Changed

### Before (❌ Direct Calls)

```python
import requests

# Direct call to quality-fabric
response = requests.post(
    "http://localhost:8000/api/validate",
    json={"code": "..."}
)

# Direct call to templates
response = requests.get(
    "http://localhost:9600/api/search",
    params={"query": "auth"}
)
```

### After (✅ Via Gateway)

```python
from src.integrations.quality_service import quality_service
from src.integrations.templates_service import templates_service

# Call quality-fabric via gateway
result = await quality_service.validate_code(
    code="def test(): pass",
    language="python"
)

# Call templates via gateway
templates = await templates_service.search_templates(
    query="authentication"
)
```

---

## Gateway Client SDK

### Location

The gateway client is available at:
```python
from src.gateway_client import gateway_client
```

### Integration Services

Pre-built integration clients are available:

```python
from src.integrations.quality_service import quality_service
from src.integrations.templates_service import templates_service
```

---

## Usage Examples

### 1. Quality Fabric Integration

```python
from src.integrations.quality_service import quality_service

# Validate code
result = await quality_service.validate_code(
    code="def hello():\n    print('Hello')",
    language="python",
    checks=["syntax", "security", "best_practices"]
)

if result["valid"]:
    print(f"Code is valid! Score: {result.get('score', 0)}")
else:
    print(f"Validation errors: {result.get('errors', [])}")

# Run tests
test_results = await quality_service.run_tests(
    code="def add(a, b): return a + b",
    test_cases=[
        {"name": "test_addition", "input": {"a": 2, "b": 3}, "expected": 5}
    ],
    auto_heal=True
)

# Get quality score for project
score = await quality_service.get_quality_score(project_id="proj-123")
```

### 2. Templates Integration

```python
from src.integrations.templates_service import templates_service

# Search for templates
templates = await templates_service.search_templates(
    query="authentication with JWT",
    category="web",
    language="python",
    limit=10
)

for template in templates:
    print(f"- {template['name']}: {template['description']}")

# Get specific template
template = await templates_service.get_template("tmpl-auth-001")
if template:
    print(f"Using template: {template['name']}")

# Get template recommendations
recommendations = await templates_service.get_template_recommendations(
    project_context={
        "type": "web_app",
        "tech_stack": ["python", "fastapi", "postgresql"]
    },
    limit=5
)

# Create new template
template_id = await templates_service.create_template({
    "name": "FastAPI CRUD Template",
    "category": "api",
    "language": "python",
    "content": "# Template content...",
    "tags": ["fastapi", "crud", "rest"]
})
```

### 3. Direct Gateway Calls

For services not yet having integration clients:

```python
from src.gateway_client import gateway_client

# Call any service via gateway
response = await gateway_client.call(
    service="rag",  # Service name
    path="/api/search",  # Endpoint path
    method="POST",
    json={
        "query": "machine learning patterns",
        "collection": "templates",
        "limit": 10
    }
)

if response.status_code == 200:
    results = response.json()
```

### 4. Synchronous Calls

```python
from src.integrations.quality_service import quality_service
from src.integrations.templates_service import templates_service

# Sync validation
result = quality_service.validate_code_sync(
    code="def test(): pass",
    language="python"
)

# Sync template search
templates = templates_service.search_templates_sync(
    query="authentication"
)
```

---

## Environment Configuration

### Docker Compose (Already Configured)

All maestro-engine services have been updated:

```yaml
# Coordinator
coordinator:
  environment:
    - GATEWAY_URL=http://gateway:8080
    - SERVICE_NAME=maestro-coordinator

# Orchestration
orchestration:
  environment:
    - GATEWAY_URL=http://gateway:8080
    - SERVICE_NAME=maestro-orchestration

# MCP
mcp:
  environment:
    - GATEWAY_URL=http://gateway:8080
    - SERVICE_NAME=maestro-mcp

# RAG
rag:
  environment:
    - GATEWAY_URL=http://gateway:8080
    - SERVICE_NAME=maestro-rag
```

### Local Development (.env)

Add to your `.env` file:

```bash
# API Gateway
GATEWAY_URL=http://localhost:8080
SERVICE_NAME=maestro-engine
```

---

## Migration Checklist

If you have existing code with direct HTTP calls:

- [ ] Find all `requests.get/post` to other services
- [ ] Replace with integration services (`quality_service`, `templates_service`)
- [ ] For other services, use `gateway_client.call()`
- [ ] Remove hardcoded service URLs
- [ ] Test with gateway running

### Finding Direct Calls

```bash
# Find hardcoded URLs
grep -r "http://.*:8000" src/  # Quality Fabric
grep -r "http://.*:9600" src/  # Templates
grep -r "http://.*:9803" src/  # RAG

# Find requests library usage
grep -r "requests\." src/

# Files found:
# - src/quality_fabric_client.py (line 22)
# - src/templates/maestro_templates_integration.py (line 29)
# - src/config/settings.py (lines 102, 106, 110)
```

### Replacing Direct Calls

**Example 1: Quality Fabric Client**

**File**: `src/quality_fabric_client.py`

**Before (line 22)**:
```python
class QualityFabricClient:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
```

**After**:
```python
# Import gateway integration instead
from src.integrations.quality_service import quality_service

# Use throughout codebase
result = await quality_service.validate_code(code, language)
```

**Example 2: Templates Integration**

**File**: `src/templates/maestro_templates_integration.py`

**Before (line 29)**:
```python
def __init__(self, registry_url: str = "http://localhost:9600"):
    self.registry_url = registry_url
```

**After**:
```python
# Import gateway integration instead
from src.integrations.templates_service import templates_service

# Use throughout codebase
templates = await templates_service.search_templates(query)
```

---

## Service Communication Patterns

### Pattern 1: Maestro Engine → Quality Fabric

```python
from src.integrations.quality_service import quality_service

async def validate_generated_code(code: str, language: str):
    """Validate code generated by personas"""
    result = await quality_service.validate_code(
        code=code,
        language=language,
        checks=["syntax", "security", "best_practices"]
    )

    return {
        "valid": result["valid"],
        "quality_score": result.get("score", 0.0),
        "issues": result.get("errors", [])
    }
```

### Pattern 2: Maestro Engine → Templates

```python
from src.integrations.templates_service import templates_service

async def get_project_templates(project_type: str, tech_stack: list):
    """Get recommended templates for project"""
    recommendations = await templates_service.get_template_recommendations(
        project_context={
            "type": project_type,
            "tech_stack": tech_stack
        },
        limit=5
    )

    return recommendations
```

### Pattern 3: Orchestrator → Multiple Services

```python
from src.integrations.quality_service import quality_service
from src.integrations.templates_service import templates_service
import asyncio

async def orchestrate_code_generation(project_spec: dict):
    """
    Complete workflow using multiple services via gateway
    """

    # 1. Get relevant templates
    templates = await templates_service.search_templates(
        query=project_spec["description"],
        category=project_spec["type"]
    )

    # 2. Generate code (using personas)
    generated_code = await generate_code_with_personas(templates)

    # 3. Validate code in parallel
    validation_tasks = [
        quality_service.validate_code(code, lang)
        for code, lang in generated_code.items()
    ]
    validations = await asyncio.gather(*validation_tasks)

    # 4. Run tests
    test_results = await quality_service.run_tests(
        code=generated_code["main"],
        test_cases=generated_code["tests"],
        auto_heal=True
    )

    return {
        "templates_used": len(templates),
        "code_generated": len(generated_code),
        "all_valid": all(v["valid"] for v in validations),
        "tests_passed": test_results["passed"]
    }
```

---

## Testing

### Unit Tests (Mock Gateway)

```python
import pytest
from unittest.mock import Mock, patch

@pytest.mark.asyncio
async def test_validate_code():
    with patch('src.gateway_client.GatewayClient.call') as mock:
        # Mock gateway response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "valid": True,
            "score": 0.95
        }
        mock.return_value = mock_response

        # Test
        from src.integrations.quality_service import quality_service
        result = await quality_service.validate_code("def test(): pass", "python")

        assert result["valid"] is True
        assert result["score"] == 0.95
        mock.assert_called_once()
```

### Integration Tests (Real Gateway)

```python
import pytest
from src.integrations.quality_service import quality_service
from src.integrations.templates_service import templates_service

@pytest.mark.integration
async def test_quality_integration():
    # Requires gateway and quality-fabric running
    result = await quality_service.validate_code(
        code="def hello():\n    return 'world'",
        language="python"
    )

    assert "valid" in result

@pytest.mark.integration
async def test_templates_integration():
    # Requires gateway and maestro-templates running
    templates = await templates_service.search_templates(
        query="authentication"
    )

    assert isinstance(templates, list)
```

---

## Troubleshooting

### Gateway Not Reachable

```bash
# Error: Connection refused to http://gateway:8080
```

**Solutions**:
1. Ensure gateway is running: `docker ps | grep gateway`
2. Check gateway health: `curl http://localhost:8080/health`
3. Verify network: `docker network inspect maestro-dev-network`

### Service Not Found (404)

```python
# Error: 404 Not Found for /api/v1/quality/api/validate
```

**Solutions**:
1. Check service name is correct (e.g., "quality" not "quality-fabric")
2. Verify gateway routes: `curl http://localhost:8080/routes`
3. Check gateway logs: `docker logs gateway | grep quality`

### Timeout Errors

```python
# Error: httpx.TimeoutException
```

**Solutions**:
1. Increase timeout:
   ```python
   from src.gateway_client import GatewayClient
   gateway = GatewayClient(timeout=60.0)
   ```
2. Check target service health
3. Check gateway circuit breaker state

---

## Benefits

✅ **Service Discovery** - Use service names, not hardcoded URLs
✅ **Automatic Retry** - Gateway handles retries with exponential backoff
✅ **Circuit Breaker** - Prevents cascading failures
✅ **Rate Limiting** - Protects services from overload
✅ **Centralized Logging** - All inter-service calls traced
✅ **Easy Testing** - Mock gateway instead of each service

---

## Next Steps

1. **Update Existing Code**: Replace direct HTTP calls with integration services
2. **Remove Old Clients**: Deprecate `QualityFabricClient` and `MaestroTemplatesIntegration`
3. **Test Integration**: Run integration tests with gateway
4. **Monitor**: Check gateway logs for service calls
5. **Deploy**: Deploy with gateway in production

---

## Related Documentation

- [Gateway Client SDK](src/gateway_client.py)
- [Quality Service Integration](src/integrations/quality_service.py)
- [Templates Service Integration](src/integrations/templates_service.py)
- [Gateway README](src/gateway/README.md)
- [ADR-003: API Gateway Pattern](docs/architecture/ADR-003-api-gateway.md)
- [Deployment Guide](docs/GATEWAY_DEPLOYMENT_GUIDE.md)

---

**All maestro-engine services are now configured to use the API Gateway! 🎉**
