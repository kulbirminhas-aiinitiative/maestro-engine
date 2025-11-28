# MAESTRO Engine v3.0 - Quick Reference Guide

**Version:** 3.0.0 | **Status:** Production Ready (95%) | **Last Updated:** October 2025

---

## WHAT IS IT?

MAESTRO Engine is an **AI-powered code generation platform** that generates complete, production-ready software projects by orchestrating 11 specialized AI personas that work together to handle the entire SDLC (Software Development Lifecycle).

**Input:** Natural language requirement  
**Output:** Complete working project (100+ files)  
**Time:** 10-20 minutes for average project

---

## KEY FEATURES AT A GLANCE

| Feature | Details |
|---------|---------|
| **Code Generation** | ✅ 100% functional end-to-end projects |
| **AI Personas** | 11 specialized roles (analyst, architect, developers, QA, DevOps, etc.) |
| **Output Quality** | 95%+ code is immediately runnable, follows best practices |
| **Supported Stacks** | React/Vue/Angular + FastAPI/Django/Node.js + PostgreSQL/MongoDB |
| **Async Execution** | Non-blocking workflow queue (Celery + Redis) |
| **Real-time Updates** | WebSocket progress streaming |
| **Documentation** | Comprehensive auto-generated docs (README, API, guides) |
| **Testing** | 70-80% code coverage with generated tests |
| **CI/CD** | GitHub Actions/GitLab CI pipelines auto-generated |
| **Frontend-Agnostic** | Works with ANY frontend via REST API + WebSocket |

---

## QUICK START (5 MINUTES)

### 1. Start Services

```bash
# Redis (required)
redis-server

# Engine API (in new terminal)
cd /home/ec2-user/projects/maestro-engine-new
python3.11 src/maestro_engine_app.py

# BFF Service (in new terminal, optional but recommended)
python3.11 -m src.bff.unified_bff_service
```

### 2. Generate a Project

```bash
curl -X POST http://localhost:5000/api/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "requirement": "Build a todo app with user authentication and task management",
    "session_id": "todo_app_v1"
  }'
```

### 3. Check Progress

```bash
curl http://localhost:5000/api/workflow/status/{job_id}
```

### 4. Get Generated Project

```bash
ls -la /tmp/maestro_projects/guardian_todo_app_v1/
```

---

## API ENDPOINTS (MAIN)

### Health & Status
- `GET /health` - Service health
- `GET /api/workflow/health` - Workflow system health

### Workflow Execution
- `POST /api/workflow/execute` - Start project generation
- `GET /api/workflow/status/{job_id}` - Check progress

### Personas
- `GET /api/personas` - List all 11 personas
- `GET /api/personas/{id}` - Get persona details

### Documents
- `GET /api/documents` - List generated documents
- `GET /api/documents/{id}` - Get document content

### Swagger Documentation
- `http://localhost:5000/docs` - Interactive API explorer
- `http://localhost:5000/redoc` - API reference

---

## 11 PERSONAS EXPLAINED

Each persona is an AI expert that generates specific deliverables:

1. **Requirement Analyst** → requirements.md, user_stories.json
2. **Solution Architect** → architecture.md, tech_stack decisions
3. **UI/UX Designer** → wireframes, design_spec.md
4. **Frontend Developer** → React/Vue/Angular code
5. **Backend Developer** → API endpoints, business logic
6. **Database Admin** → schema.sql, migrations
7. **QA Engineer** → test suites (unit, integration, E2E)
8. **Security Specialist** → security_audit.md, encryption
9. **DevOps Engineer** → Docker, Kubernetes, CI/CD pipelines
10. **Deployment Specialist** → runbooks, deployment guides
11. **Technical Writer** → README, API docs, user guides

---

## GENERATED PROJECT STRUCTURE

```
Generated Project/
├── requirements/          ← Requirements & analysis docs
├── architecture/          ← System design & technical decisions
├── design/               ← UI/UX specs & wireframes
├── frontend/             ← React/Vue/Angular code
├── backend/              ← Python/Node.js/Go API
├── database/             ← SQL schemas & migrations
├── tests/                ← Unit, integration, E2E tests
├── devops/               ← Docker, K8s, CI/CD configs
├── docs/                 ← Comprehensive documentation
└── project_manifest.json ← Complete project metadata
```

---

## INTEGRATION WITH SUNDAY.COM

### Method 1: Simple HTTP Calls (Recommended)
```python
import requests

# Start workflow
response = requests.post(
    "http://maestro-engine:5000/api/workflow/execute",
    json={
        "requirement": user_requirement,
        "session_id": project_id
    }
)
job_id = response.json()["job_id"]

# Poll for completion
import time
while True:
    status = requests.get(
        f"http://maestro-engine:5000/api/workflow/status/{job_id}"
    ).json()
    
    if status["celery_state"] in ["SUCCESS", "FAILURE"]:
        # Project is ready at /tmp/maestro_projects/guardian_{project_id}/
        break
    time.sleep(5)
```

### Method 2: Docker Compose
```yaml
services:
  maestro-engine:
    image: maestro-engine:3.0
    ports: ["5000:5000"]
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      REDIS_URL: redis://redis:6379
  redis:
    image: redis:6.2-alpine
    ports: ["6379:6379"]
```

### Method 3: File Access
```python
from pathlib import Path

# Access generated files
project_dir = Path(f"/tmp/maestro_projects/guardian_{session_id}")
frontend = project_dir / "frontend"  # React code
backend = project_dir / "backend"    # FastAPI code
docs = project_dir / "docs"          # Documentation
```

---

## CONFIGURATION

**Environment Variables:**

```bash
# Anthropic API
ANTHROPIC_API_KEY=sk-ant-xxx

# Service Configuration
ENGINE_HOST=0.0.0.0
ENGINE_PORT=5000
BFF_PORT=4001

# Redis
REDIS_URL=redis://localhost:6379

# Workflow Settings
DEFAULT_EXECUTION_MODE=dag  # or parallel, sequential
WORKFLOW_TIMEOUT=3600
PERSONA_TIMEOUT=300

# Optional Features
RAG_ENABLED=false              # Vector search for templates
QUALITY_FABRIC_ENABLED=false   # Code quality checks
ENABLE_MCP=true                # AI context sharing

# Environment
ENVIRONMENT=production         # or development
LOG_LEVEL=INFO
DEBUG=false
```

---

## PERFORMANCE METRICS

| Metric | Value |
|--------|-------|
| **Project Generation Time** | 10-20 minutes (avg) |
| **Files Generated** | 50-150+ files |
| **Code Lines** | 5,000-15,000+ LOC |
| **API Endpoints** | 20-50+ endpoints |
| **Test Coverage** | 70-80% |
| **Documentation Pages** | 10-20+ pages |
| **Concurrent Projects** | 10+ simultaneous |
| **Memory Per Project** | ~500MB-2GB |
| **Disk Space Per Project** | 50-300MB |

---

## OUTPUT QUALITY CHECKLIST

Generated code includes:

- ✅ Proper error handling & validation
- ✅ Security best practices (OWASP Top 10)
- ✅ Authentication & authorization
- ✅ Comprehensive API documentation
- ✅ Database migrations & seeds
- ✅ Unit & integration tests
- ✅ E2E test scenarios
- ✅ CI/CD pipelines (GitHub Actions)
- ✅ Docker & docker-compose setup
- ✅ Environment configuration templates
- ✅ Logging & monitoring setup
- ✅ Performance optimizations
- ✅ Code style consistency
- ✅ Type hints (Python/TypeScript)
- ✅ README with setup instructions

---

## COMMON USE CASES

### 1. MVP (Minimum Viable Product)
```
Requirement: "Build a note-taking app with cloud sync"
Output: Full-stack web app ready to deploy
Time: ~15 minutes
```

### 2. Internal Tool
```
Requirement: "Create admin dashboard for user management"
Output: React frontend + FastAPI backend + PostgreSQL
Time: ~12 minutes
```

### 3. API Service
```
Requirement: "Build REST API for e-commerce"
Output: FastAPI service with 30+ endpoints
Time: ~10 minutes
```

### 4. Microservice
```
Requirement: "Payment processing microservice"
Output: Containerized service with tests & docs
Time: ~14 minutes
```

---

## TROUBLESHOOTING

### Problem: "QUEUED" Status Never Changes

**Solution:** Ensure Celery workers are running:
```bash
# In separate terminal
celery -A src.celery_config worker --loglevel=info
```

### Problem: Generated Code Won't Run

**Solution:** Check project manifest for dependencies:
```bash
cat /tmp/maestro_projects/guardian_<id>/project_manifest.json
```

### Problem: Large Projects Timeout

**Solution:** Increase timeout:
```bash
WORKFLOW_TIMEOUT=7200  # 2 hours
PERSONA_TIMEOUT=600    # 10 minutes
```

### Problem: Insufficient Disk Space

**Solution:** Check location and clean:
```bash
# Generated projects location
du -sh /tmp/maestro_projects/
rm -rf /tmp/maestro_projects/guardian_<old-id>/
```

---

## NEXT STEPS

1. ✅ Review [MAESTRO_ENGINE_COMPREHENSIVE_ANALYSIS.md](MAESTRO_ENGINE_COMPREHENSIVE_ANALYSIS.md) for detailed docs
2. ✅ Check [API_SPECIFICATION.md](API_SPECIFICATION.md) for full API reference
3. ✅ Explore generated projects in `/tmp/maestro_projects/`
4. ✅ Integrate with Sunday.com using examples above
5. ✅ Configure for your production environment

---

## SUPPORT RESOURCES

- **Full Documentation:** See `MAESTRO_ENGINE_COMPREHENSIVE_ANALYSIS.md`
- **API Reference:** See `API_SPECIFICATION.md`
- **Architecture:** See `docs/architecture/`
- **Examples:** See `examples/` directory
- **Tests:** See `tests/` directory

---

**Ready to generate your first project? Start with Step 1 in Quick Start above!**

Built with FastAPI + Claude AI + Pydantic v2
