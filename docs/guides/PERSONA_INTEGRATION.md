# MAESTRO Persona System Integration Guide

## Overview

This guide explains how to integrate the new MAESTRO Persona System (Schema v3.0) with the existing autonomous SDLC executor in `shared/claude_team_sdk/examples/sdlc_team/autonomous_sdlc_engine_v3_resumable.py`.

## Architecture

### New Persona System (maestro-engine)
- **Location**: `maestro-engine/src/personas/`
- **Format**: Clean JSON definitions with Pydantic v2 validation
- **Schema**: v3.0 with comprehensive metadata, dependencies, and intelligence
- **Files**: 11 persona JSON files in `definitions/` directory

### Existing Executor (shared/claude_team_sdk)
- **Location**: `shared/claude_team_sdk/examples/sdlc_team/autonomous_sdlc_engine_v3_resumable.py`
- **Format**: Dictionary-based persona definitions
- **Integration**: Expects `SDLCPersonas.get_all_personas()` method

## Integration Strategy

We created an **Adapter Pattern** implementation that bridges the new and old systems without modifying the executor.

### Components

1. **MaestroPersonaAdapter** (`src/personas/adapter.py`)
   - Loads JSON personas using PersonaRegistry
   - Converts Pydantic models to legacy dictionary format
   - Maintains backward compatibility

2. **MaestroPersonasCompat** (`src/personas/adapter.py`)
   - Drop-in replacement for `SDLCPersonas` class
   - Exposes `get_all_personas()` method in legacy format

## Usage

### Option 1: Use Adapter Directly (Recommended)

```python
from maestro_engine.personas import MaestroPersonaAdapter

# Load new personas
adapter = MaestroPersonaAdapter()
await adapter.load_personas()

# Get in legacy format for executor
legacy_personas = adapter.get_all_personas()

# Use with autonomous executor
engine = AutonomousSDLCEngineV3Resumable(
    selected_personas=["requirement_analyst", "solution_architect"],
    output_dir="./output"
)
```

### Option 2: Replace SDLCPersonas Import

In `autonomous_sdlc_engine_v3_resumable.py`:

```python
# OLD:
# from personas import SDLCPersonas

# NEW:
from maestro_engine.personas import MaestroPersonasCompat as SDLCPersonas
```

This requires no other changes to the executor code!

### Option 3: Synchronous Usage

For scripts that can't use async:

```python
from maestro_engine.personas import get_adapter

adapter = get_adapter()
personas = adapter.get_all_personas()  # Auto-loads synchronously
```

## Persona Mapping

The adapter automatically maps new schema v3.0 fields to legacy format:

| New Schema v3.0 | Legacy Format |
|-----------------|---------------|
| `persona_id` | `id` |
| `display_name` | `name` |
| `metadata.category` | `phase`, `role_id` |
| `capabilities.core` | `expertise`, `responsibilities` |
| `prompts.system_prompt` | `system_prompt` |
| `quality_metrics` | `key_metrics` |
| `execution.priority` | Used for execution ordering |
| `dependencies.depends_on` | Used for topological sort |

## Advanced Features

### Execution Order with Dependencies

The new system supports dependency-based execution ordering:

```python
adapter = get_adapter()

# Get optimal execution order based on dependencies
personas_to_run = [
    "frontend_developer",
    "backend_developer",
    "solution_architect",
    "requirement_analyst"
]

ordered = adapter.get_execution_order(personas_to_run)
# Result: ["requirement_analyst", "solution_architect", "backend_developer", "frontend_developer"]
```

### Category-Based Selection

```python
from maestro_engine.personas import PersonaRegistry, PersonaCategory

registry = PersonaRegistry()
await registry.load_all()

# Get all development personas
dev_personas = registry.get_by_category(PersonaCategory.DEVELOPMENT)
# Returns: [frontend_developer, backend_developer, database_administrator]
```

## Testing Integration

### Test Adapter Conversion

```bash
cd /home/ec2-user/projects/maestro-engine
python3.11 src/personas/adapter.py
```

Expected output:
```
🧪 Testing Persona Adapter
================================================================================
✅ Loaded 11 personas in legacy format

🤖 Requirement Analyst (requirement_analyst)
   Phase: requirements
   Role ID: analyst
   ...
================================================================================
✅ Adapter test completed successfully!
```

### Test with Autonomous Executor

```bash
cd /home/ec2-user/projects/shared/claude_team_sdk/examples/sdlc_team

# Create test script that imports new personas
python3.11 -c "
from maestro_engine.personas import MaestroPersonasCompat as SDLCPersonas
personas = SDLCPersonas.get_all_personas()
print(f'Loaded {len(personas)} personas')
for pid in personas:
    print(f'  - {personas[pid][\"name\"]}')
"
```

## Migration Path

### Phase 1: Parallel Operation (Current)
- ✅ New personas defined in JSON (11 personas complete)
- ✅ Adapter bridges to legacy executor
- ✅ No changes to existing executor required
- ✅ Both systems work independently

### Phase 2: Gradual Adoption (Next)
- Update `autonomous_sdlc_engine_v3_resumable.py` to import `MaestroPersonasCompat`
- Test all workflows with new personas
- Verify session persistence works correctly
- Validate all 11 personas execute properly

### Phase 3: Native Integration (Future)
- Build new executor that uses Pydantic models directly
- Leverage advanced features (intelligence, domain detection)
- Remove legacy adapter layer
- Archive old persona definitions

## Benefits of New System

1. **Type Safety**: Pydantic v2 validation prevents invalid persona definitions
2. **Clean Naming**: No more `_enhanced_001` suffixes
3. **Dependency Management**: Automatic execution ordering via topological sort
4. **Intelligence**: Domain-specific knowledge and platform recognition
5. **Validation**: Pre-deployment validation of all persona configs
6. **Documentation**: Self-documenting JSON schema with clear structure
7. **Version Control**: Semantic versioning for each persona
8. **Extensibility**: Easy to add new personas or modify existing ones

## File Structure

```
maestro-engine/
├── src/
│   └── personas/
│       ├── definitions/          # 11 clean persona JSON files
│       │   ├── requirement_analyst.json
│       │   ├── solution_architect.json
│       │   ├── ui_ux_designer.json
│       │   ├── frontend_developer.json
│       │   ├── backend_developer.json
│       │   ├── database_administrator.json
│       │   ├── devops_engineer.json
│       │   ├── deployment_specialist.json
│       │   ├── qa_engineer.json
│       │   ├── security_specialist.json
│       │   └── technical_writer.json
│       ├── models.py              # Pydantic v2 models
│       ├── registry.py            # Persona loader with dependency resolution
│       ├── adapter.py             # ✨ NEW: Legacy compatibility adapter
│       └── __init__.py            # Module exports
├── test_persona_system.py         # Validation test
└── PERSONA_INTEGRATION_GUIDE.md   # This file
```

## Troubleshooting

### Issue: Import Error
```python
ImportError: No module named 'maestro_engine'
```

**Solution**: Add maestro-engine to Python path:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path('/home/ec2-user/projects/maestro-engine')))
```

### Issue: Async/Await Required
```python
TypeError: object PersonaRegistry can't be used in 'await' expression
```

**Solution**: Use synchronous adapter methods:
```python
from maestro_engine.personas import get_adapter
adapter = get_adapter()
personas = adapter.get_all_personas()  # Auto-loads
```

### Issue: Persona Not Found
```python
KeyError: 'persona_not_found'
```

**Solution**: Check available personas:
```python
adapter = get_adapter()
available = list(adapter.get_all_personas().keys())
print(f"Available: {available}")
```

## Next Steps

1. ✅ All 11 personas created and validated
2. ✅ Adapter created and tested
3. ⏳ **Update executor imports** (next task)
4. ⏳ End-to-end testing with autonomous executor
5. ⏳ Create sample workflow using new personas
6. ⏳ Documentation updates for user-facing guides

## Support

For issues or questions:
1. Validate personas: `python3.11 test_persona_system.py`
2. Test adapter: `python3.11 src/personas/adapter.py`
3. Check naming: `python scripts/validate_persona_naming.py`
4. Review persona schema: `src/personas/models.py`

## References

- **Persona Naming Convention**: `/maestro-frontend/docs/architecture/PERSONA_NAMING_CONVENTION.md`
- **Schema v3.0 Models**: `/maestro-engine/src/personas/models.py`
- **Existing Executor**: `/shared/claude_team_sdk/examples/sdlc_team/autonomous_sdlc_engine_v3_resumable.py`
- **Team Organization**: `/shared/claude_team_sdk/examples/sdlc_team/team_organization.py`
