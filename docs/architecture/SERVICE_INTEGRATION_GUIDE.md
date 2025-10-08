# Service Integration Guide - API Gateway

**Part of**: [ADR-003: API Gateway Pattern](./ADR-003-api-gateway.md)

---

## Overview

This guide shows how to integrate your service with the MAESTRO API Gateway for inter-service communication.

**Key Principle**: **ALL services communicate through the gateway. NEVER make direct service-to-service HTTP calls.**

---

## Quick Start

### 1. Install Gateway Client SDK

The gateway client is included in `maestro-engine`:

```python
from src.gateway.client import GatewayClient
```

Or use the singleton:

```python
from src.gateway.client import gateway
```

### 2. Configure Environment Variables

```bash
# .env or docker-compose environment
GATEWAY_URL=http://gateway:8080  # Gateway URL
SERVICE_NAME=my-service          # Your service name (for tracing)
```

### 3. Replace Direct HTTP Calls

**❌ OLD WAY (Direct calls - DON'T DO THIS)**:
```python
import requests

# Direct call to templates service
response = requests.get("http://templates:9600/api/search?q=auth")
```

**✅ NEW WAY (Via gateway)**:
```python
from src.gateway.client import gateway

# Call through gateway
response = gateway.call_sync(
    "templates",
    "/api/search",
    params={"q": "auth"}
)
```

---

## Service Examples

### Example 1: Quality Fabric → Templates Service

**Scenario**: Quality Fabric needs to search for test templates

**File**: `quality-fabric/src/services/template_service.py`

```python
"""
Quality Fabric - Template Service Integration

Uses API Gateway to communicate with maestro-templates service.
"""

from typing import List, Dict
from src.gateway.client import GatewayClient

class TemplateService:
    """Interface to Templates Service via API Gateway"""

    def __init__(self):
        self.gateway = GatewayClient(service_name="quality-fabric")

    def search_templates(self, query: str, category: str = "test") -> List[Dict]:
        """
        Search for templates

        Args:
            query: Search query
            category: Template category

        Returns:
            List of matching templates
        """
        response = self.gateway.call_sync(
            service="templates",
            path="/api/search",
            method="POST",
            json={
                "query": query,
                "category": category,
                "limit": 10
            }
        )

        if response.status_code == 200:
            return response.json().get("templates", [])
        else:
            # Gateway handles retries, circuit breaker, etc.
            # If we get here, all retries failed
            raise Exception(f"Template search failed: {response.status_code}")

    def get_template(self, template_id: str) -> Dict:
        """Get template by ID"""
        response = self.gateway.call_sync(
            service="templates",
            path=f"/api/templates/{template_id}",
            method="GET"
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise ValueError(f"Template not found: {template_id}")
        else:
            raise Exception(f"Template fetch failed: {response.status_code}")


# Usage in Quality Fabric
template_svc = TemplateService()
templates = template_svc.search_templates(query="authentication", category="test")
```

### Example 2: Maestro Engine → Quality Fabric

**Scenario**: Maestro Engine needs to run quality checks

**File**: `maestro-engine/src/services/quality_service.py`

```python
"""
Maestro Engine - Quality Fabric Integration

Uses API Gateway to communicate with quality-fabric service.
"""

from typing import Dict
from src.gateway.client import GatewayClient

class QualityService:
    """Interface to Quality Fabric via API Gateway"""

    def __init__(self):
        self.gateway = GatewayClient(service_name="maestro-engine")

    async def run_tests(self, code: str, language: str = "python") -> Dict:
        """
        Run tests on generated code

        Args:
            code: Source code to test
            language: Programming language

        Returns:
            Test results
        """
        response = await self.gateway.call(
            service="quality",
            path="/api/test",
            method="POST",
            json={
                "code": code,
                "language": language,
                "auto_heal": True
            }
        )

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Quality check failed: {response.status_code}")

    async def get_quality_score(self, project_id: str) -> float:
        """Get quality score for project"""
        response = await self.gateway.call(
            service="quality",
            path=f"/api/projects/{project_id}/score",
            method="GET"
        )

        if response.status_code == 200:
            return response.json().get("score", 0.0)
        else:
            return 0.0  # Default score on error


# Usage in Maestro Engine
quality_svc = QualityService()
results = await quality_svc.run_tests(code="def hello(): pass")
```

### Example 3: Templates Service → RAG Service

**Scenario**: Templates service needs semantic search via RAG

**File**: `maestro-templates/src/services/rag_service.py`

```python
"""
Templates Service - RAG Integration

Uses API Gateway to communicate with RAG service.
"""

from typing import List, Dict
from src.gateway.client import GatewayClient

class RAGService:
    """Interface to RAG Service via API Gateway"""

    def __init__(self):
        self.gateway = GatewayClient(service_name="maestro-templates")

    async def semantic_search(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Semantic search using RAG embeddings

        Args:
            query: Search query
            limit: Max results

        Returns:
            List of semantically similar documents
        """
        response = await self.gateway.call(
            service="rag",
            path="/api/search",
            method="POST",
            json={
                "query": query,
                "limit": limit,
                "collection": "templates"
            }
        )

        if response.status_code == 200:
            return response.json().get("results", [])
        else:
            # Fallback to empty results
            return []

    async def add_template_embedding(self, template_id: str, content: str):
        """Add template to RAG index"""
        response = await self.gateway.call(
            service="rag",
            path="/api/documents",
            method="POST",
            json={
                "id": template_id,
                "content": content,
                "collection": "templates",
                "metadata": {"type": "template"}
            }
        )

        return response.status_code == 201


# Usage in Templates Service
rag_svc = RAGService()
similar = await rag_svc.semantic_search(query="authentication patterns")
```

### Example 4: BFF Service → Multiple Services

**Scenario**: BFF needs to call multiple services

**File**: `unified-bff/src/services/orchestrator.py`

```python
"""
Unified BFF - Multi-Service Orchestration

Uses API Gateway to coordinate multiple services.
"""

import asyncio
from typing import Dict
from src.gateway.client import GatewayClient

class ServiceOrchestrator:
    """Orchestrates calls to multiple services via gateway"""

    def __init__(self):
        self.gateway = GatewayClient(service_name="unified-bff")

    async def create_project(self, project_data: Dict) -> Dict:
        """
        Create project across multiple services

        Coordinates:
        1. Create project in maestro-engine
        2. Initialize quality tracking in quality-fabric
        3. Create template workspace in templates service
        """
        # Parallel calls via gateway
        results = await asyncio.gather(
            # Create in maestro-engine
            self.gateway.call(
                "guardian",
                "/api/projects",
                method="POST",
                json=project_data
            ),
            # Initialize quality tracking
            self.gateway.call(
                "quality",
                "/api/projects",
                method="POST",
                json={"name": project_data["name"]}
            ),
            # Create template workspace
            self.gateway.call(
                "templates",
                "/api/workspaces",
                method="POST",
                json={"project_id": project_data["id"]}
            ),
            return_exceptions=True  # Don't fail if one service fails
        )

        # Check results
        project_response, quality_response, template_response = results

        return {
            "project_id": project_response.json()["id"] if hasattr(project_response, "json") else None,
            "quality_initialized": quality_response.status_code == 201 if hasattr(quality_response, "status_code") else False,
            "templates_ready": template_response.status_code == 201 if hasattr(template_response, "status_code") else False,
        }


# Usage
orchestrator = ServiceOrchestrator()
result = await orchestrator.create_project({
    "id": "proj-123",
    "name": "My Project",
    "type": "web_app"
})
```

---

## Configuration

### Environment Variables

Each service needs these environment variables:

```bash
# Gateway configuration
GATEWAY_URL=http://gateway:8080  # Gateway URL (required)
SERVICE_NAME=my-service          # Service name for tracing (optional)

# Example for docker-compose
services:
  quality-fabric:
    environment:
      - GATEWAY_URL=http://gateway:8080
      - SERVICE_NAME=quality-fabric

  maestro-templates:
    environment:
      - GATEWAY_URL=http://gateway:8080
      - SERVICE_NAME=maestro-templates
```

### Service Discovery

Services are discovered by name via gateway routes:

| Service Name | Gateway Route | Backend URL |
|--------------|---------------|-------------|
| `templates` | `/api/v1/templates/*` | `http://templates:9600` |
| `quality` | `/api/v1/quality/*` | `http://quality-fabric:8000` |
| `guardian` | `/api/v1/guardian/*` | `http://maestro-engine:5000` |
| `accelerator` | `/api/v1/accelerator/*` | `http://unified-bff:4001` |
| `rag` | `/api/v1/rag/*` | `http://rag:9803` |
| `mcp` | `/api/v1/mcp/*` | `http://mcp:9800` |

**Important**: Service calls use the service name, NOT the full route:

```python
# ✅ Correct
gateway.call("templates", "/api/search")
# Routes to: http://gateway:8080/api/v1/templates/api/search

# ❌ Wrong
gateway.call("/api/v1/templates", "/api/search")
```

---

## Migration Guide

### Step 1: Identify Direct Service Calls

Find all direct HTTP calls in your service:

```bash
# Search for hardcoded URLs
grep -r "http://.*:9600" .  # Templates
grep -r "http://.*:8000" .  # Quality Fabric
grep -r "http://.*:5000" .  # Maestro Engine

# Search for requests library usage
grep -r "requests.get\|requests.post" src/
```

### Step 2: Replace with Gateway Client

**Before**:
```python
import requests

def search_templates(query: str):
    url = "http://templates:9600/api/search"
    response = requests.post(url, json={"query": query})
    return response.json()
```

**After**:
```python
from src.gateway.client import gateway

def search_templates(query: str):
    response = gateway.call_sync(
        "templates",
        "/api/search",
        method="POST",
        json={"query": query}
    )
    return response.json()
```

### Step 3: Update Configuration

Add gateway environment variables:

```yaml
# docker-compose.yml
services:
  my-service:
    environment:
      - GATEWAY_URL=http://gateway:8080
      - SERVICE_NAME=my-service
```

### Step 4: Test

Test service communication through gateway:

```bash
# Start gateway
docker-compose up gateway

# Start your service
docker-compose up my-service

# Check logs for gateway calls
docker logs my-service | grep gateway_call
```

---

## Best Practices

### 1. Use Service Names, Not URLs

```python
# ✅ Good - service discovery via gateway
gateway.call("templates", "/api/search")

# ❌ Bad - hardcoded URL
requests.get("http://templates:9600/api/search")
```

### 2. Handle Errors Gracefully

```python
# Gateway handles retries and circuit breakers
# But you should still handle final failures

try:
    response = gateway.call_sync("templates", "/api/search")
    if response.status_code == 200:
        return response.json()
    else:
        # Use fallback data or cached results
        return get_cached_results()
except httpx.TimeoutException:
    # Gateway already retried - use fallback
    return []
```

### 3. Use Async When Possible

```python
# ✅ Better - non-blocking
async def get_data():
    response = await gateway.call("templates", "/api/data")
    return response.json()

# ⚠️  Acceptable - blocks thread
def get_data_sync():
    response = gateway.call_sync("templates", "/api/data")
    return response.json()
```

### 4. Set Service Name for Tracing

```python
# Helps with debugging and monitoring
gateway = GatewayClient(service_name="my-service")
```

### 5. Close Clients Properly

```python
# Async context manager
async with GatewayClient() as gateway:
    response = await gateway.call("templates", "/api/data")

# Sync context manager
with GatewayClient() as gateway:
    response = gateway.call_sync("templates", "/api/data")
```

---

## Troubleshooting

### Gateway Not Reachable

```python
# Error: Connection refused to http://gateway:8080
```

**Solutions**:
1. Check `GATEWAY_URL` environment variable
2. Ensure gateway service is running: `docker ps | grep gateway`
3. Check network connectivity: `docker exec my-service ping gateway`

### Service Not Found (404)

```python
# Error: 404 Not Found for /api/v1/templates/api/search
```

**Solutions**:
1. Check service name is correct (e.g., "templates" not "template")
2. Verify route exists in `config/gateway_routes.yaml`
3. Check gateway logs: `docker logs gateway | grep templates`

### Timeout Errors

```python
# Error: httpx.TimeoutException
```

**Solutions**:
1. Increase timeout: `GatewayClient(timeout=60.0)`
2. Check backend service is responding: `curl http://templates:9600/health`
3. Check gateway circuit breaker state: `curl http://gateway:8080/health/ready`

### Circuit Breaker Open (503)

```python
# Error: 503 Service Unavailable - Circuit breaker open
```

**Solutions**:
1. Check backend service health
2. Wait 60 seconds for circuit to attempt reset
3. Fix underlying issue in backend service

---

## Testing

### Unit Tests (Mock Gateway)

```python
import pytest
from unittest.mock import Mock, patch
from src.services.template_service import TemplateService

def test_search_templates():
    with patch('src.gateway.client.GatewayClient.call_sync') as mock_call:
        # Mock gateway response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "templates": [{"id": "t1", "name": "Test Template"}]
        }
        mock_call.return_value = mock_response

        # Test service
        svc = TemplateService()
        templates = svc.search_templates(query="test")

        assert len(templates) == 1
        assert templates[0]["name"] == "Test Template"
        mock_call.assert_called_once_with(
            service="templates",
            path="/api/search",
            method="POST",
            json={"query": "test", "category": "test", "limit": 10}
        )
```

### Integration Tests (Real Gateway)

```python
import pytest
from src.gateway.client import GatewayClient

@pytest.mark.integration
async def test_real_gateway():
    # Requires gateway and templates service running
    gateway = GatewayClient(gateway_url="http://localhost:8080")

    response = await gateway.call(
        "templates",
        "/api/search",
        method="POST",
        json={"query": "test"}
    )

    assert response.status_code == 200
    assert "templates" in response.json()
```

---

## Monitoring

### Logs

Gateway client emits structured logs:

```json
{
  "event": "gateway_call_success",
  "service": "templates",
  "method": "POST",
  "path": "/api/search",
  "status": 200
}
```

### Metrics to Track

1. **Call Volume**: Calls per service per minute
2. **Latency**: p50, p95, p99 response times
3. **Error Rate**: Failed calls / total calls
4. **Circuit Breaker**: Open circuit count

### Tracing

All gateway calls include `X-Service-Name` header for distributed tracing.

---

## Related Documentation

- [ADR-003: API Gateway Pattern](./ADR-003-api-gateway.md)
- [Gateway README](../../src/gateway/README.md)
- [Gateway Client API](../../src/gateway/client.py)

---

**Last Updated**: 2025-10-04
**Version**: 1.0.0
