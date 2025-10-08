# MAESTRO Backend API - Frontend Integration Guide

## Overview

The MAESTRO Backend API exposes the `enhanced_lean_ultimate_mega_team_utcp` workflow via REST endpoints, allowing frontend applications to execute AI-powered development workflows.

## Architecture

```
Frontend (maestro_frontend_v2)
    ↓ HTTP POST
Backend API (maestro-engine:5001)
    ↓ imports
enhanced_lean_ultimate_mega_team_utcp.py
    ↓ HTTP calls (if UTCP enabled)
UTCP Services (maestro-v2:8001) [Optional]
    ↓ executes
Local Claude Tools (fallback)
```

## API Endpoints

### Base URL
```
http://localhost:5001
```

### 1. Health Check
**GET** `/health`

Check API health and dependency status.

**Response:**
```json
{
  "status": "healthy" | "degraded",
  "timestamp": "2025-10-01T12:32:52.543658",
  "version": "1.0.0",
  "features": {
    "utcp_distributed_execution": true,
    "rag_template_retrieval": true,
    "workflow_execution": true,
    "claude_sdk": true
  },
  "dependencies": {
    "utcp_workflow": true,
    "httpx": true,
    "chromadb": true,
    "claude_code_sdk": true
  }
}
```

### 2. Service Status
**GET** `/status`

Get execution statistics.

**Response:**
```json
{
  "total_executions": 10,
  "successful_executions": 8,
  "failed_executions": 2,
  "average_execution_time": 145.5,
  "utcp_enabled": true,
  "rag_enabled": true
}
```

### 3. Execute Workflow
**POST** `/api/workflow/execute`

Execute an AI development workflow.

**Request Body:**
```json
{
  "requirement": "Create a REST API for user management with FastAPI",
  "enable_utcp": true,
  "enable_rag": true,
  "enable_mcp": true,
  "selected_personas": null,
  "session_id": null,
  "project_path": null,
  "max_execution_time": 3600
}
```

**Parameters:**
- `requirement` (string, required): User requirement to execute
- `enable_utcp` (boolean, optional): Enable distributed UTCP execution (default: true)
- `enable_rag` (boolean, optional): Enable RAG template retrieval (default: true)
- `enable_mcp` (boolean, optional): Enable MCP context sharing (default: true)
- `selected_personas` (array, optional): Custom persona list
- `session_id` (string, optional): Custom session ID for tracking
- `project_path` (string, optional): Custom project path
- `max_execution_time` (integer, optional): Max execution time in seconds (default: 3600)

**Response:**
```json
{
  "success": true,
  "session_id": "api_session_1759321972",
  "requirement": "Create a REST API for user management",
  "execution_method": "local_claude_tools",
  "files_generated": [
    "/path/to/project/main.py",
    "/path/to/project/requirements.txt",
    "/path/to/project/README.md"
  ],
  "total_execution_time": 162.94,
  "project_path": "/path/to/project",
  "team_members": [
    "requirement_analyst",
    "backend_developer",
    "qa_engineer"
  ],
  "quality_validation": {
    "quality_score": 85.5,
    "security_score": 90.0,
    "test_coverage": 75.0,
    "test_results": {
      "total": 10,
      "passed": 8,
      "failed": 2
    }
  },
  "template_extraction": {
    "templates_created": 2,
    "template_ids": ["template_123", "template_456"]
  },
  "git_template_url": "https://github.com/org/template-repo"
}
```

### 4. Workflow Statistics
**GET** `/api/workflow/stats`

Get detailed workflow execution statistics.

**Response:**
```json
{
  "total_executions": 10,
  "successful_executions": 8,
  "failed_executions": 2,
  "success_rate": 80.0,
  "average_execution_time": 145.5,
  "total_execution_time": 1455.0,
  "utcp_available": true
}
```

## Frontend Integration Example

### JavaScript/TypeScript

```javascript
// Execute workflow
async function executeWorkflow(requirement) {
  try {
    const response = await fetch('http://localhost:5001/api/workflow/execute', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        requirement: requirement,
        enable_utcp: true,
        enable_rag: true,
        enable_mcp: true
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();

    if (result.success) {
      console.log('✅ Workflow completed successfully!');
      console.log(`Files generated: ${result.files_generated.length}`);
      console.log(`Execution time: ${result.total_execution_time}s`);
      console.log(`Quality score: ${result.quality_validation?.quality_score}`);
      return result;
    } else {
      console.error('❌ Workflow failed:', result.error);
      throw new Error(result.error);
    }
  } catch (error) {
    console.error('Request failed:', error);
    throw error;
  }
}

// Check API health
async function checkHealth() {
  const response = await fetch('http://localhost:5001/health');
  const health = await response.json();
  return health.status === 'healthy';
}

// Usage
const requirement = "Create a REST API for user management with FastAPI";
const result = await executeWorkflow(requirement);
```

### React Hook

```typescript
import { useState, useCallback } from 'react';

interface WorkflowResult {
  success: boolean;
  session_id: string;
  files_generated: string[];
  total_execution_time: number;
  quality_validation?: {
    quality_score: number;
    security_score: number;
  };
}

export function useWorkflowExecution() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<WorkflowResult | null>(null);

  const executeWorkflow = useCallback(async (requirement: string) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:5001/api/workflow/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirement,
          enable_utcp: true,
          enable_rag: true
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      setResult(data);
      return data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { executeWorkflow, loading, error, result };
}
```

## Error Handling

The API returns standard HTTP status codes:

- `200 OK`: Successful execution
- `400 Bad Request`: Invalid request payload
- `500 Internal Server Error`: Workflow execution failed
- `503 Service Unavailable`: UTCP workflow engine not available

**Error Response:**
```json
{
  "error": "Workflow execution failed",
  "message": "Detailed error message",
  "requirement": "Original requirement",
  "execution_time": 5.2
}
```

## Configuration

### Starting the Backend API

```bash
cd /home/ec2-user/projects/maestro-engine

# Start on default port (5000)
poetry run python start_backend_api.py

# Start on custom port
poetry run python start_backend_api.py --port 5001

# Start with auto-reload (development)
poetry run python start_backend_api.py --port 5001 --reload
```

### Environment Variables

The backend API can be configured via:
- `UTCP_ENABLED`: Enable/disable UTCP distributed execution
- `RAG_ENABLED`: Enable/disable RAG template retrieval
- `MCP_ENABLED`: Enable/disable MCP context sharing

## UTCP vs Local Execution

### UTCP Mode (Distributed)
When `enable_utcp: true`:
1. Backend calls UTCP service at `http://localhost:8001`
2. UTCP service executes workflow
3. Returns results to backend
4. Backend returns to frontend

**Pros**: Scalable, distributed, can handle many concurrent requests
**Cons**: Requires UTCP service running

### Local Mode (Fallback)
When `enable_utcp: false` or UTCP service unavailable:
1. Backend executes workflow locally
2. Uses `unified_claude_tools` directly
3. Returns results to frontend

**Pros**: No external dependencies
**Cons**: Limited concurrency, runs on same server

## Production Considerations

1. **CORS Configuration**: Update `allow_origins` in `main.py` to specific frontend URLs
2. **Authentication**: Add API key or OAuth authentication
3. **Rate Limiting**: Implement rate limiting for workflow execution
4. **Logging**: Configure structured logging for production
5. **Monitoring**: Set up health check monitoring and alerts
6. **Scaling**: Deploy behind load balancer for high availability

## Troubleshooting

### API Not Responding
```bash
# Check if server is running
curl http://localhost:5001/health

# Check logs
tail -f /tmp/backend_api.log
```

### Workflow Execution Fails
1. Check health endpoint for dependency status
2. Ensure `unified_claude_tools` is available
3. Check logs for detailed error messages
4. Verify UTCP services are running (if enabled)

### Port Already in Use
```bash
# Find process using port 5001
lsof -ti:5001

# Kill process
kill $(lsof -ti:5001)

# Or use different port
poetry run python start_backend_api.py --port 5002
```

## API Documentation

Interactive API documentation available at:
- Swagger UI: `http://localhost:5001/docs`
- ReDoc: `http://localhost:5001/redoc`
