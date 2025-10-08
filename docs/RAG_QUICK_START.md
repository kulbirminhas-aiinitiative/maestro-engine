# RAG Integration - Quick Start Guide

## 🚀 Quick Setup (5 minutes)

### 1. Set Environment Variables

```bash
export RAG_INTEGRATION_ENABLED=true
export RAG_READER_URL=http://localhost:9801
export RAG_WRITER_URL=http://localhost:9802
export RAG_READER_API_KEY=dev_rag_reader_key_12345
export RAG_WRITER_API_KEY=dev_rag_writer_key_98765
export MAESTRO_TEMPLATES_PATH=/home/ec2-user/projects/maestro-templates/storage/templates
```

### 2. Start RAG Services

```bash
# Terminal 1: RAG Reader
cd /home/ec2-user/projects/maestro-engine
poetry run python src/rag_reader/rag_reader_service.py

# Terminal 2: RAG Writer
poetry run python src/rag_writer/rag_writer_service.py
```

### 3. Verify Services

```bash
# Check RAG Reader
curl http://localhost:9801/health

# Check RAG Writer
curl http://localhost:9802/health
```

### 4. Run Workflow with RAG

```python
from orchestration.autonomous_sdlc_engine_v3_resumable import AutonomousSDLCEngineV3Resumable

engine = AutonomousSDLCEngineV3Resumable(
    selected_personas=["backend_developer"],
    enable_rag=True
)

result = await engine.execute(
    requirement="Build a REST API with JWT authentication"
)

print(f"RAG Indexed: {result.get('rag_indexed')}")
print(f"Quality Score: {result.get('quality_score')}")
```

---

## 📚 Template Management

### View Templates

```bash
ls /home/ec2-user/projects/maestro-templates/storage/templates/backend_developer/
```

### Add New Template

```bash
cd /home/ec2-user/projects/maestro-templates

# Create template JSON
cat > storage/templates/backend_developer/my-new-template.json <<EOF
{
  "metadata": {
    "id": "$(uuidgen)",
    "name": "My Custom Template",
    "category": "api",
    "language": "python",
    "framework": "fastapi",
    "description": "Custom FastAPI template",
    "tags": ["api", "fastapi"],
    "quality_score": 50.0,
    "status": "approved",
    "created_at": "$(date -Iseconds)",
    "persona": "backend_developer"
  },
  "content": "from fastapi import FastAPI\n\napp = FastAPI()"
}
