# MAESTRO Persona System - Quick Start

## ✅ Completed Integration

The MAESTRO Persona System (Schema v3.0) is now fully integrated with the existing autonomous SDLC executor. All 11 personas are defined, validated, and ready to use.

## 🎯 What's New

- **11 Clean Personas**: No more `_enhanced_001` suffixes, just clean names
- **Schema v3.0**: Comprehensive Pydantic models with validation
- **Dependency Management**: Automatic execution ordering based on persona dependencies
- **Domain Intelligence**: Built-in platform recognition and complexity scoring
- **Backward Compatible**: Works with existing `autonomous_sdlc_engine_v3_resumable.py`

## 📦 Available Personas

1. **requirement_analyst** - Extracts and analyzes requirements
2. **solution_architect** - Designs system architecture
3. **ui_ux_designer** - Creates user experience designs
4. **frontend_developer** - Builds React/TypeScript frontends
5. **backend_developer** - Implements FastAPI/Python backends
6. **database_administrator** - Designs and optimizes databases
7. **devops_engineer** - Sets up CI/CD and infrastructure
8. **deployment_specialist** - Manages production releases
9. **qa_engineer** - Creates comprehensive test suites
10. **security_specialist** - Performs security audits
11. **technical_writer** - Creates documentation

## 🚀 Quick Start

### 1. View Persona Examples

```bash
cd /home/ec2-user/projects/maestro-engine
python3.11 example_persona_usage.py
```

### 2. Run Integration Tests

```bash
python3.11 test_integration_with_executor.py
```

Expected output: **5/5 tests passed** ✅

### 3. Run a Simple Workflow

```bash
# Single persona - requirement analysis only
python3.11 run_test_workflow.py requirement_analyst --example simple

# Multiple personas - requirements + architecture
python3.11 run_test_workflow.py requirement_analyst solution_architect --example webapp

# Full workflow with testing
python3.11 run_test_workflow.py \
  requirement_analyst \
  solution_architect \
  backend_developer \
  qa_engineer \
  --example api
```

### 4. Resume a Session

```bash
# List available sessions
python3.11 run_test_workflow.py --list-sessions

# Resume with specific personas
python3.11 run_test_workflow.py frontend_developer technical_writer --resume <session_id>

# Resume with all remaining personas
python3.11 run_test_workflow.py --resume <session_id>
```

## 📖 Usage Examples

### Example 1: Requirement Analysis

```bash
python3.11 run_test_workflow.py requirement_analyst \
  --requirement "Build a task management app with user authentication"
```

**Output**: Requirements document with functional/non-functional requirements

### Example 2: Design Phase

```bash
python3.11 run_test_workflow.py \
  requirement_analyst \
  solution_architect \
  ui_ux_designer \
  --example webapp
```

**Output**: Requirements + Architecture + UI/UX designs

### Example 3: Full Development Cycle

```bash
python3.11 run_test_workflow.py \
  requirement_analyst \
  solution_architect \
  ui_ux_designer \
  frontend_developer \
  backend_developer \
  database_administrator \
  --requirement "Create an e-commerce platform with inventory management" \
  --session-id ecommerce_v1
```

**Output**: Complete codebase with frontend, backend, and database

### Example 4: Testing & Documentation

```bash
# Resume previous session to add testing
python3.11 run_test_workflow.py qa_engineer technical_writer \
  --resume ecommerce_v1
```

**Output**: Test suites + comprehensive documentation

## 🧪 Validation Scripts

### Test Persona Loading
```bash
python3.11 test_persona_system.py
```

### Validate Naming Convention
```bash
python scripts/validate_persona_naming.py --path src/personas/definitions/
```

### Test Adapter
```bash
python3.11 src/personas/adapter.py
```

## 📁 File Structure

```
maestro-engine/
├── src/personas/
│   ├── definitions/              # 11 persona JSON files
│   │   ├── requirement_analyst.json
│   │   ├── solution_architect.json
│   │   └── ...
│   ├── models.py                 # Pydantic v2 models
│   ├── registry.py               # Persona loader
│   ├── adapter.py                # Legacy compatibility
│   └── __init__.py
├── test_persona_system.py        # Validation test
├── test_integration_with_executor.py  # Integration tests
├── example_persona_usage.py      # Usage examples
├── run_test_workflow.py          # Workflow runner
├── PERSONA_INTEGRATION_GUIDE.md  # Detailed guide
└── README_PERSONAS.md            # This file
```

## 🔧 Advanced Usage

### Using the Adapter Directly

```python
from maestro_engine.personas import get_adapter

# Get adapter instance
adapter = get_adapter()

# Get all personas in legacy format
personas = adapter.get_all_personas()

# Get execution order based on dependencies
order = adapter.get_execution_order([
    "frontend_developer",
    "backend_developer",
    "requirement_analyst"
])
# Result: ["requirement_analyst", "backend_developer", "frontend_developer"]
```

### Using the Registry

```python
from maestro_engine.personas import PersonaRegistry, PersonaCategory

# Create registry
registry = PersonaRegistry()
await registry.load_all()

# Get by category
dev_personas = registry.get_by_category(PersonaCategory.DEVELOPMENT)
# Returns: [frontend_developer, backend_developer, database_administrator]

# Get specific persona
analyst = registry.get("requirement_analyst")
print(f"Experience: {analyst.role.experience_level}/10")
print(f"Specializations: {analyst.role.specializations}")
```

### Domain Intelligence

```python
# Get domain-specific information
analyst = registry.get("requirement_analyst")

if analyst.intelligence:
    for domain_name, domain_info in analyst.intelligence.domains.items():
        print(f"{domain_name}:")
        print(f"  Platforms: {domain_info.platforms}")
        print(f"  Complexity: {domain_info.complexity_weight}")
```

## 📊 Test Results

All integration tests passing:

```
✅ PASS - Persona Loading
✅ PASS - Execution Order
✅ PASS - Session Compatibility
✅ PASS - Context Building
✅ PASS - Prompt Format

Results: 5/5 tests passed
```

## 🔍 Troubleshooting

### Issue: Import Error

```python
ImportError: No module named 'maestro_engine'
```

**Solution**: Ensure you're running from the correct directory:
```bash
cd /home/ec2-user/projects/maestro-engine
python3.11 <script_name>.py
```

### Issue: Dependency Error

```
ValueError: Persona 'frontend_developer' has missing dependencies: ui_ux_designer
```

**Solution**: Include all required dependencies in your persona list:
```bash
python3.11 run_test_workflow.py \
  requirement_analyst \
  solution_architect \
  ui_ux_designer \
  frontend_developer \
  --example webapp
```

### Issue: Session Not Found

```
Session not found: my_session_id
```

**Solution**: List available sessions:
```bash
python3.11 run_test_workflow.py --list-sessions
```

## 📚 Documentation

- **Integration Guide**: `PERSONA_INTEGRATION_GUIDE.md` - Comprehensive integration details
- **Schema Documentation**: `src/personas/models.py` - Pydantic model definitions
- **Naming Convention**: `/maestro-frontend/docs/architecture/PERSONA_NAMING_CONVENTION.md`

## 🎯 Next Steps

1. ✅ All personas created and validated
2. ✅ Integration tests passing
3. ✅ Example workflows working
4. ⏳ Run production workflow
5. ⏳ Monitor and optimize
6. ⏳ Add custom personas as needed

## 💡 Tips

- Start with `requirement_analyst` only to test quickly
- Use `--example` flag for predefined requirements
- Sessions are resumable - work incrementally
- Check `--list-sessions` to see previous runs
- Each persona has detailed system prompts optimized for its role

## 🆘 Support

For issues or questions:
1. Run validation: `python3.11 test_persona_system.py`
2. Run integration tests: `python3.11 test_integration_with_executor.py`
3. Check logs in the output directory
4. Review `PERSONA_INTEGRATION_GUIDE.md`

---

**Version**: Schema v3.0
**Status**: ✅ Production Ready
**Last Updated**: 2025-10-03
