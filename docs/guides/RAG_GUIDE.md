# RAG Integration - Quick Reference Card

## 🚀 Start Services

```bash
# Terminal 1: RAG Reader
poetry run python src/rag_reader/rag_reader_service.py

# Terminal 2: RAG Writer
poetry run python src/rag_writer/rag_writer_service.py

# Verify
curl http://localhost:9801/health  # RAG Reader
curl http://localhost:9802/health  # RAG Writer
```

## 📝 Enable RAG in Workflow

```python
from orchestration.autonomous_sdlc_engine_v3_resumable import AutonomousSDLCEngineV3Resumable

engine = AutonomousSDLCEngineV3Resumable(
    selected_personas=["backend_developer"],
    enable_rag=True  # <-- Enable RAG
)

result = await engine.execute(
    requirement="Build REST API with authentication"
)

# Check if indexed
print(f"RAG Indexed: {result.get('rag_indexed')}")
print(f"Quality Score: {result.get('quality_score')}")
```

## 🔍 Query Templates

```bash
curl -X POST http://localhost:9801/api/v1/query/templates \
  -H "X-API-Key: dev_rag_reader_key_12345" \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "backend_developer",
    "requirement": "REST API with CRUD",
    "top_k": 3
  }'
```

## 📥 Index Execution

```bash
curl -X POST http://localhost:9802/api/v1/index/execution \
  -H "X-API-Key: dev_rag_writer_key_98765" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "my_session",
    "requirement": "Build API",
    "personas": ["backend_developer"],
    "quality_score": 0.75,
    "success": true
  }'
```

## 📊 Check Statistics

```bash
curl http://localhost:9802/api/v1/stats \
  -H "X-API-Key: dev_rag_writer_key_98765"
```

## 🧪 Run Tests

```bash
# RAG Writer service tests
poetry run pytest tests/test_rag_writer_service.py -v

# End-to-end integration tests
poetry run python tests/test_rag_integration_e2e.py
```

## 🌱 Seed Templates

```bash
cd /home/ec2-user/projects/maestro-templates
python3.11 scripts/seed_templates.py
```

## 📈 Quality Score Guide

| Score | Description | Requirements |
|-------|-------------|--------------|
| 0.8-1.0 | Excellent | Success + 15+ files + 8+ personas + fast |
| 0.6-0.8 | Good | Success + 10+ files + 5+ personas |
| 0.5-0.6 | Acceptable | Success + 5+ files + 3+ personas |
| < 0.5 | Not Indexed | Below quality threshold |

## 🔧 Environment Variables

```bash
export RAG_INTEGRATION_ENABLED=true
export RAG_READER_URL=http://localhost:9801
export RAG_WRITER_URL=http://localhost:9802
export RAG_READER_API_KEY=dev_rag_reader_key_12345
export RAG_WRITER_API_KEY=dev_rag_writer_key_98765
export MAESTRO_TEMPLATES_PATH=/home/ec2-user/projects/maestro-templates/storage/templates

# Optional
export RAG_WRITER_WEBHOOK_URL=http://your-webhook
export RAG_WRITER_MAX_RETRIES=3
export RAG_WRITER_RETRY_DELAY=5
```

## 📚 Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/index/execution` | POST | Index workflow |
| `/api/v1/index/template` | POST | Index template |
| `/api/v1/index/batch` | POST | Batch index |
| `/api/v1/task/{id}` | GET | Task status |
| `/api/v1/tasks` | GET | List tasks |
| `/api/v1/stats` | GET | Statistics |

## 📁 Important Files

```
src/rag_writer/rag_writer_service.py          # RAG Writer service
src/orchestration/rag_integration.py          # Integration helpers
maestro-templates/storage/templates/          # Template repository
tests/test_rag_integration_e2e.py             # E2E tests
docs/RAG_IMPLEMENTATION_FINAL_REPORT.md       # Full documentation
```

## 🎯 Common Tasks

**Add a new template**:
```bash
cat > maestro-templates/storage/templates/backend_developer/my-template.json <<EOF
{
  "metadata": {
    "id": "$(uuidgen)",
    "name": "My Template",
    "category": "api",
    "language": "python",
    "framework": "fastapi",
    "tags": ["api"],
    "quality_score": 70.0,
    "status": "approved",
    "persona": "backend_developer"
  },
  "content": "# Your code here"
}
