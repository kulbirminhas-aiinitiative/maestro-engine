# 🚀 Quick Test Guide - MAESTRO UTCP

## Quick Commands

### 1. Run All Tests
```bash
poetry run python test_utcp_wrapper.py
```

### 2. Test PDF Generation (Your Specific Request)
```bash
poetry run python test_utcp_wrapper.py --tests pdf
```

### 3. Test Quality-Fabric Integration
```bash
poetry run python test_utcp_wrapper.py --tests quality
```

### 4. Test Basic Workflow
```bash
poetry run python test_utcp_wrapper.py --tests basic
```

### 5. Run Multiple Specific Tests
```bash
poetry run python test_utcp_wrapper.py --tests pdf quality rag
```

---

## Available Test Types

| Test Name | What It Tests | Duration |
|-----------|--------------|----------|
| `basic` | Basic code generation | ~20s |
| `pdf` | **PDF document generation** | ~15s |
| `quality` | Quality-Fabric validation | ~30s |
| `rag` | RAG template retrieval | ~25s |
| `multi_persona` | Full team collaboration | ~60s |
| `utcp` | Distributed execution | ~30s |
| `template` | Template extraction | ~20s |

---

## Current UTCP Functionalities

### ✅ Working Now (No Extra Services Needed)

1. **Basic Code Generation** - Creates complete applications
2. **PDF Document Generation** - Generates PDF reports/documents
3. **Multi-Persona Workflows** - AI team collaboration
4. **Template Extraction** - Save projects as templates

### ⚠️ Requires Services

5. **Quality-Fabric** - Needs port 8000 (currently running ✅)
6. **RAG Templates** - Needs port 9600 (check availability)
7. **UTCP Distributed** - Needs port 8001 (check availability)

---

## Test Output Example

```bash
$ poetry run python test_utcp_wrapper.py --tests pdf

🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪
  MAESTRO UTCP Test Suite
🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪

================================================================================
  Test 0: Dependency Check
================================================================================
✅ PASS - Quality-Fabric
    http://localhost:8000
✅ PASS - Template Registry
    http://localhost:9600
✅ PASS - Backend API
    http://localhost:5000
✅ PASS - BFF Service
    http://localhost:4001

================================================================================
  Test 2: PDF Document Generation
================================================================================
✅ PASS - PDF Generation
    4 files in 18.23s - PDF: True
    Generated files:
      - generate_pdf.py
      - testing_report.pdf
      - requirements.txt
      - README.md

================================================================================
  TEST SUMMARY
================================================================================

Total Tests: 1
✅ Passed: 1
❌ Failed: 0
⏱️  Total Time: 18.23s
⏱️  Average Time: 18.23s

📊 Results saved to: test_results_1696780234.json
```

---

## Detailed Test Descriptions

### 1. PDF Generation Test (`--tests pdf`)

**What it does**:
- Creates a Python script that generates PDFs using reportlab
- Generates a sample PDF report about "Software Testing Best Practices"
- Includes headers, sections, tables, and formatting

**Expected Output**:
- `generate_pdf.py` - Python script
- `testing_report.pdf` - Generated PDF
- `requirements.txt` - Dependencies
- `README.md` - Instructions

**Example Generated Code**:
```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# Creates professional PDF with:
# - Title page
# - Table of contents
# - Formatted sections
# - Data tables
# - Page numbers
```

---

### 2. Quality-Fabric Test (`--tests quality`)

**What it does**:
- Creates a FastAPI application
- Includes authentication and validation
- Runs automated tests
- Validates code quality

**Quality Metrics**:
- Security score
- Code quality score
- Test coverage
- Performance metrics

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

### 3. RAG Template Test (`--tests rag`)

**What it does**:
- Searches template registry for relevant templates
- Uses templates to enhance code generation
- Applies best practice patterns

**Benefits**:
- Faster development
- Better code quality
- Consistent patterns
- Reusable components

---

### 4. Multi-Persona Test (`--tests multi_persona`)

**What it does**:
- Full AI team collaboration
- 6 specialized personas working together
- Complete full-stack application

**Team**:
1. Requirement Analyst - Analyzes requirements
2. Solution Architect - Designs architecture
3. Backend Developer - Creates server code
4. Frontend Developer - Builds UI
5. QA Engineer - Tests everything
6. DevOps Engineer - Handles deployment

---

## Custom Requirements

### Create Your Own Test

```python
# custom_test.py
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
        project_name="my_project"
    )

    result = await execute_enhanced_lean_workflow_utcp(
        requirement="""
        YOUR REQUIREMENT HERE:
        - What to build
        - Key features
        - Technologies to use
        """,
        config=config
    )

    print(f"✅ Success: {result['success']}")
    print(f"📁 Project: {result['project_path']}")
    print(f"📄 Files: {result.get('files_generated', [])}")

asyncio.run(main())
```

Run it:
```bash
poetry run python custom_test.py
```

---

## Example Requirements

### PDF Generation
```python
"""Create a Python script that generates a professional invoice PDF.

Requirements:
- Company header with logo placeholder
- Invoice details (number, date, customer)
- Itemized billing table
- Subtotal, tax, and total calculations
- Payment terms footer
- Use reportlab library
- Output: invoice_generator.py and sample_invoice.pdf
"""
```

### REST API
```python
"""Create a FastAPI REST API for a bookstore.

Endpoints:
- GET /books - List all books
- GET /books/{id} - Get book details
- POST /books - Add new book
- PUT /books/{id} - Update book
- DELETE /books/{id} - Delete book

Requirements:
- SQLite database
- Pydantic models for validation
- API documentation
- Unit tests
"""
```

### Full-Stack App
```python
"""Create a task management application.

Backend (FastAPI):
- Task CRUD operations
- User authentication
- Priority levels
- Due dates
- SQLite database

Frontend (HTML/CSS/JS):
- Task list with filters
- Add/edit task modal
- Mark complete functionality
- Responsive design
- Dark mode toggle

Testing:
- Backend unit tests
- API integration tests
"""
```

---

## View Results

After running tests, results are saved to `test_results_<timestamp>.json`:

```bash
# View latest results
cat test_results_*.json | tail -1 | python3 -m json.tool

# Or use jq for better formatting
cat test_results_*.json | tail -1 | jq '.'
```

---

## Troubleshooting

### Service Not Available

If a service is not available, the test will show:
```
⚠️  Quality-Fabric not available at http://localhost:8000: Connection refused
```

**Fix**: Start the service
```bash
# Quality-Fabric
cd /home/ec2-user/projects/quality-fabric
poetry run python3 run_server.py &

# Template Registry (if you have it)
# Check your template service start command
```

### Import Errors

If you get import errors:
```bash
# Make sure you're in the right directory
cd /home/ec2-user/projects/maestro-engine

# Make sure dependencies are installed
poetry install
```

### Slow Tests

Reduce complexity:
```python
config = EnhancedTeamConfig(
    selected_personas=["backend_developer"],  # Just one persona
    enable_rag=False  # Disable RAG for speed
)
```

---

## Next Steps

1. **Start Simple**: Run basic test first
   ```bash
   poetry run python test_utcp_wrapper.py --tests basic
   ```

2. **Test PDF**: Your specific requirement
   ```bash
   poetry run python test_utcp_wrapper.py --tests pdf
   ```

3. **Test Quality**: If service is running
   ```bash
   poetry run python test_utcp_wrapper.py --tests quality
   ```

4. **Run All**: Comprehensive test
   ```bash
   poetry run python test_utcp_wrapper.py
   ```

5. **Review Results**: Check generated files
   ```bash
   ls -la /home/ec2-user/projects/deployment/
   ```

---

## Full Documentation

For complete documentation, see:
- `UTCP_FUNCTIONALITY_GUIDE.md` - Detailed functionality guide
- `BFF_SERVICE_MIGRATION_COMPLETE.md` - BFF service documentation
- `FRONTEND_INTEGRATION_GUIDE.md` - API integration guide
