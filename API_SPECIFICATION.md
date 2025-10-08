# Maestro Engine API Specification

This document defines the REST API that the Maestro Engine backend provides. Any frontend implementing the [Maestro Frontend API Contract](https://github.com/kulbirminhas-aiinitiative/maestro-frontend/blob/main/API_CONTRACT.md) can consume these endpoints.

## Overview

The Maestro Engine is a **swappable backend** that implements AI-powered workflow orchestration, persona-based task execution, and RAG (Retrieval-Augmented Generation) capabilities.

## Core Principle

**The backend is frontend-agnostic.** It exposes a standard REST API + WebSocket interface that ANY client can consume.

## Base URLs

Default local development:
- REST API: `http://localhost:8080/api`
- WebSocket: `ws://localhost:8080/ws`

Configure via environment variables:
- `API_PORT` - REST API port (default: 8080)
- `WS_PORT` - WebSocket port (default: 8080)

## Authentication

Optional API key authentication:
```
X-API-Key: <api_key>
```

Configure via environment variables:
- `API_KEY_ENABLED` - Enable API key auth (default: false)
- `API_KEY` - API key value

## API Endpoints

### 1. Health Check

```
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "rag_system": "healthy",
    "persona_registry": "healthy"
  },
  "uptime": 3600,
  "timestamp": "2025-10-08T10:00:00Z"
}
```

### 2. Workflows

#### List Workflows
```
GET /api/workflows
```

**Query Parameters:**
- `status` - Filter by status (pending, running, completed, failed)
- `limit` - Limit results (default: 50)
- `offset` - Offset for pagination (default: 0)

**Response:**
```json
{
  "workflows": [
    {
      "id": "wf_123",
      "name": "Build and Deploy",
      "description": "Full stack deployment workflow",
      "status": "running",
      "persona": "DevOps Engineer",
      "created_at": "2025-10-08T10:00:00Z",
      "updated_at": "2025-10-08T10:05:00Z",
      "metadata": {
        "project": "my-app",
        "environment": "production"
      }
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

#### Create Workflow
```
POST /api/workflows
Content-Type: application/json

{
  "name": "My Workflow",
  "description": "Workflow description",
  "persona": "Solution Architect",
  "steps": [
    {
      "type": "analyze",
      "config": {
        "analysis_depth": "comprehensive"
      }
    },
    {
      "type": "build",
      "config": {
        "framework": "react"
      }
    }
  ],
  "metadata": {
    "project": "my-app"
  }
}
```

**Response:**
```json
{
  "id": "wf_456",
  "name": "My Workflow",
  "status": "pending",
  "persona": "Solution Architect",
  "created_at": "2025-10-08T10:10:00Z",
  "steps": [
    {
      "id": "step_1",
      "type": "analyze",
      "status": "pending",
      "config": {
        "analysis_depth": "comprehensive"
      }
    }
  ]
}
```

#### Get Workflow
```
GET /api/workflows/:id
```

**Response:**
```json
{
  "id": "wf_123",
  "name": "Build and Deploy",
  "description": "Full stack deployment workflow",
  "status": "running",
  "persona": "DevOps Engineer",
  "steps": [
    {
      "id": "step_1",
      "type": "build",
      "status": "completed",
      "started_at": "2025-10-08T10:00:00Z",
      "completed_at": "2025-10-08T10:03:00Z",
      "result": {
        "artifacts": ["build/app.js"],
        "success": true
      }
    },
    {
      "id": "step_2",
      "type": "deploy",
      "status": "running",
      "started_at": "2025-10-08T10:03:00Z"
    }
  ],
  "created_at": "2025-10-08T10:00:00Z",
  "updated_at": "2025-10-08T10:05:00Z",
  "metadata": {
    "project": "my-app"
  }
}
```

#### Update Workflow
```
PATCH /api/workflows/:id
Content-Type: application/json

{
  "name": "Updated Workflow Name",
  "status": "paused"
}
```

#### Delete Workflow
```
DELETE /api/workflows/:id
```

**Response:**
```json
{
  "success": true,
  "message": "Workflow wf_123 deleted successfully"
}
```

### 3. Execution

#### Start Execution
```
POST /api/workflows/:id/execute
Content-Type: application/json

{
  "parameters": {
    "environment": "production",
    "deploy_strategy": "blue-green"
  }
}
```

**Response:**
```json
{
  "execution_id": "exec_789",
  "workflow_id": "wf_123",
  "status": "started",
  "started_at": "2025-10-08T10:10:00Z"
}
```

#### Get Execution Status
```
GET /api/executions/:id
```

**Response:**
```json
{
  "id": "exec_789",
  "workflow_id": "wf_123",
  "status": "running",
  "progress": 45,
  "current_step": {
    "id": "step_2",
    "name": "deploy",
    "status": "running"
  },
  "started_at": "2025-10-08T10:10:00Z",
  "logs": [
    {
      "timestamp": "2025-10-08T10:10:05Z",
      "level": "info",
      "message": "Starting deployment to production",
      "step_id": "step_2"
    },
    {
      "timestamp": "2025-10-08T10:10:15Z",
      "level": "info",
      "message": "Deploying to server 1 of 3",
      "step_id": "step_2"
    }
  ],
  "metadata": {
    "environment": "production"
  }
}
```

#### Stop Execution
```
POST /api/executions/:id/stop
```

**Response:**
```json
{
  "success": true,
  "execution_id": "exec_789",
  "status": "stopped",
  "stopped_at": "2025-10-08T10:15:00Z"
}
```

### 4. Personas

#### List Available Personas
```
GET /api/personas
```

**Response:**
```json
{
  "personas": [
    {
      "id": "solution_architect",
      "name": "Solution Architect",
      "description": "Designs system architecture and technical solutions",
      "capabilities": [
        "system_design",
        "architecture_review",
        "technology_selection"
      ],
      "model": "claude-sonnet-4-5"
    },
    {
      "id": "devops_engineer",
      "name": "DevOps Engineer",
      "description": "Manages deployment and infrastructure",
      "capabilities": [
        "deployment",
        "infrastructure",
        "monitoring"
      ],
      "model": "claude-sonnet-4-5"
    }
  ]
}
```

#### Get Persona Details
```
GET /api/personas/:id
```

**Response:**
```json
{
  "id": "solution_architect",
  "name": "Solution Architect",
  "description": "Designs system architecture and technical solutions",
  "capabilities": [
    "system_design",
    "architecture_review",
    "technology_selection"
  ],
  "model": "claude-sonnet-4-5",
  "system_prompt": "You are an expert solution architect...",
  "tools": [
    "diagram_generator",
    "technology_recommender"
  ]
}
```

### 5. RAG (Retrieval-Augmented Generation)

#### Search Knowledge Base
```
POST /api/rag/search
Content-Type: application/json

{
  "query": "How to implement authentication in React?",
  "persona": "frontend_developer",
  "limit": 10
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "doc_123",
      "title": "React Authentication Guide",
      "content": "To implement authentication in React...",
      "relevance_score": 0.95,
      "source": "templates/react-auth-template",
      "metadata": {
        "category": "authentication",
        "framework": "react"
      }
    }
  ],
  "total": 1,
  "query": "How to implement authentication in React?"
}
```

### 6. Templates

#### List Templates
```
GET /api/templates
```

**Query Parameters:**
- `category` - Filter by category
- `framework` - Filter by framework
- `limit` - Limit results
- `offset` - Offset for pagination

**Response:**
```json
{
  "templates": [
    {
      "id": "template_123",
      "name": "React Authentication Template",
      "description": "Complete authentication flow for React apps",
      "category": "frontend",
      "framework": "react",
      "version": "1.0.0",
      "created_at": "2025-10-08T10:00:00Z"
    }
  ],
  "total": 1
}
```

#### Get Template
```
GET /api/templates/:id
```

**Response:**
```json
{
  "id": "template_123",
  "name": "React Authentication Template",
  "description": "Complete authentication flow for React apps",
  "category": "frontend",
  "framework": "react",
  "version": "1.0.0",
  "content": {
    "files": [
      {
        "path": "src/auth/AuthContext.tsx",
        "content": "import React from 'react'..."
      }
    ],
    "dependencies": {
      "react": "^18.0.0",
      "react-router-dom": "^6.0.0"
    }
  },
  "metadata": {
    "tags": ["authentication", "react", "jwt"],
    "difficulty": "intermediate"
  }
}
```

### 7. Files (Optional)

#### List Files
```
GET /api/files?path=/
```

**Response:**
```json
{
  "files": [
    {
      "name": "README.md",
      "type": "file",
      "size": 1024,
      "path": "/README.md",
      "modified": "2025-10-08T10:00:00Z"
    },
    {
      "name": "src",
      "type": "directory",
      "path": "/src",
      "modified": "2025-10-08T10:00:00Z"
    }
  ],
  "path": "/"
}
```

#### Read File
```
GET /api/files/content?path=/README.md
```

**Response:**
```json
{
  "path": "/README.md",
  "content": "# My Project\n\nWelcome to my project...",
  "encoding": "utf-8",
  "size": 1024
}
```

## WebSocket Protocol

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');
```

### Authentication (Optional)

Send auth message after connection:
```json
{
  "type": "auth",
  "data": {
    "api_key": "your-api-key"
  }
}
```

### Message Format

All messages follow this structure:
```json
{
  "type": "message_type",
  "data": { /* type-specific data */ },
  "timestamp": "2025-10-08T10:00:00Z"
}
```

### Server → Client Messages

#### Workflow Update
```json
{
  "type": "workflow_update",
  "data": {
    "workflow_id": "wf_123",
    "status": "running",
    "progress": 65,
    "current_step": {
      "id": "step_2",
      "name": "deploy",
      "status": "running"
    }
  },
  "timestamp": "2025-10-08T10:05:00Z"
}
```

#### Execution Log
```json
{
  "type": "execution_log",
  "data": {
    "execution_id": "exec_789",
    "level": "info",
    "message": "Deployment successful to server 1",
    "step_id": "step_2"
  },
  "timestamp": "2025-10-08T10:05:00Z"
}
```

#### Persona Activity
```json
{
  "type": "persona_activity",
  "data": {
    "persona": "DevOps Engineer",
    "action": "deploying",
    "details": "Deploying to production environment",
    "workflow_id": "wf_123"
  },
  "timestamp": "2025-10-08T10:05:00Z"
}
```

#### System Event
```json
{
  "type": "system_event",
  "data": {
    "event": "service_status_change",
    "service": "rag_system",
    "status": "degraded",
    "reason": "High memory usage"
  },
  "timestamp": "2025-10-08T10:05:00Z"
}
```

### Client → Server Messages

#### Subscribe to Workflow
```json
{
  "type": "subscribe",
  "data": {
    "resource_type": "workflow",
    "resource_id": "wf_123"
  }
}
```

#### Unsubscribe from Workflow
```json
{
  "type": "unsubscribe",
  "data": {
    "resource_type": "workflow",
    "resource_id": "wf_123"
  }
}
```

## Error Handling

All errors follow this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "Additional context"
    },
    "timestamp": "2025-10-08T10:00:00Z"
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `NOT_FOUND` | 404 | Resource not found |
| `BAD_REQUEST` | 400 | Invalid request parameters |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Access denied |
| `CONFLICT` | 409 | Resource conflict (e.g., duplicate) |
| `INTERNAL_ERROR` | 500 | Internal server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |
| `WORKFLOW_NOT_FOUND` | 404 | Workflow not found |
| `EXECUTION_FAILED` | 500 | Workflow execution failed |
| `PERSONA_NOT_FOUND` | 404 | Persona not found |
| `TEMPLATE_NOT_FOUND` | 404 | Template not found |

## CORS Configuration

The backend supports CORS for browser-based frontends:

```python
# Configured via environment variables
CORS_ORIGINS=["http://localhost:4200", "https://maestro-frontend.com"]
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS=["*"]
```

## Rate Limiting

Default rate limits:
- 100 requests per minute per API key
- 1000 requests per hour per API key

Configure via environment variables:
- `RATE_LIMIT_PER_MINUTE` - Requests per minute
- `RATE_LIMIT_PER_HOUR` - Requests per hour

Rate limit headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1633024800
```

## OpenAPI/Swagger

Interactive API documentation available at:
- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`
- **OpenAPI JSON**: `http://localhost:8080/openapi.json`

## Testing Your Frontend

To test if your frontend is compatible with the Maestro Engine:

1. **Health Check**: `curl http://localhost:8080/api/health`
2. **List Workflows**: `curl http://localhost:8080/api/workflows`
3. **Create Workflow**:
```bash
curl -X POST http://localhost:8080/api/workflows \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Workflow","persona":"Solution Architect","steps":[]}'
```
4. **WebSocket**: Use a WebSocket client to connect to `ws://localhost:8080/ws`

## Version History

- **v1.0.0** (2025-10-08) - Initial API specification

## Questions?

If you're building a custom frontend for Maestro Engine:
1. Check the [Maestro Frontend](https://github.com/kulbirminhas-aiinitiative/maestro-frontend) as reference implementation
2. Review this specification for all available endpoints
3. Test your implementation with the Maestro Engine backend
4. Use the Swagger UI (`/docs`) for interactive API exploration
