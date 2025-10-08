# 🚀 MAESTRO UTCP Functionality Guide

Complete guide to all available UTCP functionalities and how to test them.

---

## 📋 Table of Contents

1. [Available Functionalities](#available-functionalities)
2. [Quick Start](#quick-start)
3. [Test Scenarios](#test-scenarios)
4. [Configuration Options](#configuration-options)
5. [Integration Points](#integration-points)

---

## Available Functionalities

### 1. **Basic Code Generation**
Generate complete applications with AI-powered development team.

**Features**:
- Multi-language support (Python, JavaScript, Java, etc.)
- Full-stack applications
- Complete project structure
- README and documentation

**Test Command**:
```bash
poetry run python test_utcp_wrapper.py --tests basic
```

**Example Requirement**:
```python
"Create a simple calculator web app with HTML, CSS, and JavaScript"
```

---

### 2. **PDF Document Generation**
Create PDF documents programmatically using Python libraries.

**Features**:
- Professional report generation
- Tables, charts, and formatting
- Headers, footers, page numbers
- Custom styling and branding

**Test Command**:
```bash
poetry run python test_utcp_wrapper.py --tests pdf
```

**Example Requirement**:
```python
"""Create a Python script that generates a professional PDF report using reportlab.
Include title, sections, paragraphs, and tables about 'Software Testing Best Practices'.
Output: testing_report.pdf"""
```

---

### 3. **Quality-Fabric Integration**
Automated code quality validation and testing.

**Features**:
- Security scanning
- Code quality metrics
- Performance analysis
- Test coverage reporting
- Automated test execution

**Prerequisites**:
- Quality-Fabric service running on port 8000

**Test Command**:
```bash
poetry run python test_utcp_wrapper.py --tests quality
```

**Example Requirement**:
```python
"""Create a FastAPI application with:
- User registration endpoint
- Login with JWT authentication
- Protected user profile endpoint
- Pydantic validation
- Pytest unit tests"""
```

**Expected Output**:
```json
{
  "quality_score": 85.5,
  "security_score": 90.0,
  "test_coverage": 87.3,
  "test_results": {
    "passed": 15,
    "failed": 0
  }
}
```

---

### 4. **RAG Template Retrieval**
Retrieve and use existing templates to enhance code generation.

**Features**:
- Semantic template search
- Template-enhanced prompts
- Code reusability
- Best practice patterns

**Prerequisites**:
- Template Registry service running on port 9600

**Test Command**:
```bash
poetry run python test_utcp_wrapper.py --tests rag
```

**Example Requirement**:
```python
"Create a REST API for task management with CRUD operations"
```

**How It Works**:
1. Analyzes requirement keywords
2. Searches template registry for relevant templates
3. Enhances prompt with template context
4. Generates code using template patterns

---

### 5. **Multi-Persona Workflows**
Collaborative AI team with specialized roles.

**Available Personas**:
- `requirement_analyst` - Analyzes and documents requirements
- `solution_architect` - Designs system architecture
- `frontend_developer` - Creates UI/UX components
- `backend_developer` - Builds server-side logic
- `qa_engineer` - Tests and validates quality
- `devops_engineer` - Handles deployment and infrastructure

**Test Command**:
```bash
poetry run python test_utcp_wrapper.py --tests multi_persona
```

**Example Requirement**:
```python
"""Create a full-stack todo application:

Backend:
- FastAPI REST API
- SQLite database
- CRUD operations

Frontend:
- HTML/CSS/JavaScript UI
- Responsive design

DevOps:
- Docker configuration
- docker-compose.yml"""
```

**Team Collaboration Flow**:
```
Requirement Analyst → Solution Architect → Backend Dev
                                          ↓
QA Engineer ← Frontend Dev ← DevOps Engineer
```

---

### 6. **UTCP Distributed Execution**
Execute workflows across distributed UTCP services.

**Features**:
- Distributed processing
- Load balancing
- Service mesh integration
- Fallback to local execution

**Prerequisites**:
- UTCP service running on port 8001

**Test Command**:
```bash
poetry run python test_utcp_wrapper.py --tests utcp
```

**Configuration**:
```python
utcp_config = UTCPToolConfig(
    enabled=True,
    ultimate_team_url="http://localhost:8001/tools/ultimate_unified_mega_team/execute_workflow",
    orchestration_gateway_url="http://localhost:8002/api/orchestrate",
    timeout=600,
    retry_count=3,
    fallback_to_local=True
)
```

---

### 7. **Template Extraction**
Extract successful projects as reusable templates.

**Features**:
- Automatic template creation
- Metadata extraction
- Git publishing
- Template versioning

**Test Command**:
```bash
poetry run python test_utcp_wrapper.py --tests template
```

**Example Requirement**:
```python
"Create a reusable Python CLI template with Click library"
```

**Output**:
- Template ID
- Template metadata
- Git repository URL (if published)

---

### 8. **MCP Context Sharing**
Share context across personas using Model Context Protocol.

**Features**:
- Cross-persona state sharing
- Event emission
- Context caching
- Real-time updates

**Configuration**:
```python
config = EnhancedTeamConfig(
    enable_mcp=True,
    enable_event_emission=True
)
```

---

## Quick Start

### Run All Tests
```bash
poetry run python test_utcp_wrapper.py
```

### Run Specific Tests
```bash
# Run only PDF and Quality tests
poetry run python test_utcp_wrapper.py --tests pdf quality

# Run only basic workflow
poetry run python test_utcp_wrapper.py --tests basic
```

### Custom Requirement
```bash
# Create custom test
cat > my_test.py << 'EOF'
import asyncio
import sys
sys.path.insert(0, 'src')

from maestro_mcp.enhanced_lean_ultimate_mega_team_utcp import (
    execute_enhanced_lean_workflow_utcp,
    EnhancedTeamConfig
)

async def main():
    config = EnhancedTeamConfig(
        enable_utcp=False,
        enable_rag=True,
        enable_mcp=True,
        project_name="my_custom_project"
    )

    result = await execute_enhanced_lean_workflow_utcp(
        requirement="YOUR REQUIREMENT HERE",
        config=config
    )

    print(f"Success: {result['success']}")
    print(f"Project: {result.get('project_path')}")

asyncio.run(main())
EOF

poetry run python my_test.py
```

---

## Configuration Options

### EnhancedTeamConfig

```python
config = EnhancedTeamConfig(
    # Persona Selection
    selected_personas=[
        "requirement_analyst",
        "backend_developer",
        "qa_engineer"
    ],

    # Feature Flags
    enable_rag=True,              # Enable RAG template retrieval
    enable_mcp=True,              # Enable MCP context sharing
    enable_event_emission=True,   # Enable event broadcasting
    enable_utcp=False,            # Enable UTCP distributed execution

    # Project Settings
    project_name="my_project",    # Custom project folder name
    project_path="/custom/path",  # Custom output path
    session_id="custom_session",  # Custom session identifier

    # Performance
    max_execution_time=3600,      # Max execution time (seconds)
    cache_enabled=True,           # Enable caching
    async_operations=True,        # Enable async operations
    resource_cleanup=True,        # Clean up resources after execution

    # UTCP Configuration
    utcp_config=UTCPToolConfig(
        enabled=True,
        timeout=600,
        retry_count=3,
        fallback_to_local=True
    )
)
```

---

## Integration Points

### 1. Quality-Fabric Service
**Port**: 8000
**Endpoint**: `/api/execute`
**Purpose**: Code quality validation and testing

**Check Status**:
```bash
curl http://localhost:8000/health
```

**Test Integration**:
```bash
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{"project_path": "/path/to/project"}'
```

---

### 2. Template Registry
**Port**: 9600
**Endpoint**: `/api/v1/templates`
**Purpose**: Template storage and retrieval

**Check Status**:
```bash
curl http://localhost:9600/health
```

**List Templates**:
```bash
curl http://localhost:9600/api/v1/templates
```

---

### 3. UTCP Service
**Port**: 8001
**Endpoint**: `/tools/ultimate_unified_mega_team/execute_workflow`
**Purpose**: Distributed workflow execution

**Check Status**:
```bash
curl http://localhost:8001/health
```

---

### 4. Backend API
**Port**: 5000
**Endpoint**: `/api/workflow/execute`
**Purpose**: REST API for workflow execution

**Check Status**:
```bash
curl http://localhost:5000/health
```

**Execute via API**:
```bash
curl -X POST http://localhost:5000/api/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "requirement": "Create a simple todo app",
    "enable_utcp": false,
    "enable_rag": true
  }'
```

---

### 5. BFF Service
**Port**: 4001
**Endpoint**: `/ai/chat`
**Purpose**: Chat interface with preview

**Check Status**:
```bash
curl http://localhost:4001/health
```

---

## Test Results

Test results are saved to `test_results_<timestamp>.json` with the following structure:

```json
{
  "timestamp": "2025-10-01T13:45:00.000000",
  "summary": {
    "total": 7,
    "passed": 6,
    "failed": 1,
    "duration": 245.67
  },
  "results": [
    {
      "test": "basic_workflow",
      "success": true,
      "duration": 23.45,
      "files_count": 5,
      "project_path": "/home/ec2-user/projects/deployment/test_basic_calc"
    }
  ]
}
```

---

## Common Use Cases

### 1. Create REST API
```python
await execute_enhanced_lean_workflow_utcp(
    requirement="Create FastAPI REST API for blog with posts and comments",
    config=EnhancedTeamConfig(
        selected_personas=["backend_developer", "qa_engineer"],
        enable_rag=True
    )
)
```

### 2. Generate Documentation
```python
await execute_enhanced_lean_workflow_utcp(
    requirement="Create technical documentation in PDF format for API endpoints",
    config=EnhancedTeamConfig(
        selected_personas=["requirement_analyst"],
        enable_rag=False
    )
)
```

### 3. Full-Stack Application
```python
await execute_enhanced_lean_workflow_utcp(
    requirement="Create full-stack e-commerce app with React and FastAPI",
    config=EnhancedTeamConfig(
        selected_personas=[
            "solution_architect",
            "backend_developer",
            "frontend_developer",
            "qa_engineer"
        ],
        enable_rag=True,
        enable_mcp=True
    )
)
```

### 4. DevOps Infrastructure
```python
await execute_enhanced_lean_workflow_utcp(
    requirement="Create Kubernetes deployment with monitoring and logging",
    config=EnhancedTeamConfig(
        selected_personas=["devops_engineer", "solution_architect"],
        enable_rag=True
    )
)
```

---

## Troubleshooting

### Services Not Available
```bash
# Check all services
poetry run python test_utcp_wrapper.py --tests basic

# Output will show which services are missing
```

### Slow Execution
```python
# Reduce persona count
config = EnhancedTeamConfig(
    selected_personas=["backend_developer"],  # Only one persona
    async_operations=True
)
```

### Memory Issues
```python
# Enable resource cleanup
config = EnhancedTeamConfig(
    resource_cleanup=True,
    cache_enabled=False
)
```

---

## Advanced Features

### Custom Persona Configuration
```python
# Define custom persona behavior
custom_config = {
    "persona_type": "custom_developer",
    "expertise": ["Python", "FastAPI", "PostgreSQL"],
    "output_format": "structured"
}
```

### Event Emission
```python
# Subscribe to events
from maestro_mcp.mcp_cache_config import get_mcp_cache

cache = get_mcp_cache()
cache.subscribe("workflow_progress", callback_function)
```

### Template Publishing
```python
# Publish successful project as template
result = await execute_enhanced_lean_workflow_utcp(
    requirement="...",
    config=config
)

if result.get("success"):
    template_url = result.get("git_template_url")
    print(f"Template published: {template_url}")
```

---

## Performance Metrics

| Test | Avg Duration | File Count | Success Rate |
|------|-------------|------------|--------------|
| Basic Workflow | 20-30s | 3-5 | 95% |
| PDF Generation | 15-25s | 2-4 | 90% |
| Quality Validation | 30-45s | 5-10 | 85% |
| Multi-Persona | 60-90s | 10-20 | 80% |
| UTCP Distributed | 25-35s | 5-8 | 75% |

---

## Next Steps

1. ✅ Run basic tests to verify setup
2. ✅ Test PDF generation capability
3. ✅ Integrate Quality-Fabric for validation
4. ✅ Test RAG template retrieval
5. ✅ Experiment with multi-persona workflows
6. 🔄 Set up UTCP distributed services
7. 🔄 Create custom templates

---

For more information, see:
- [Backend API Documentation](http://localhost:5000/docs)
- [BFF Service Documentation](http://localhost:4001/docs)
- [Quality-Fabric API](http://localhost:8000/docs)
- [Template Registry](http://localhost:9600/docs)
