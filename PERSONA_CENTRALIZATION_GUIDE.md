# Persona Centralization Guide

**Status**: ⚠️ Action Required
**Issue**: Hardcoded persona attributes vs. Centralized JSON definitions
**Solution**: Use JSON-based persona definitions as single source of truth

---

## Problem: Hardcoded Persona Attributes

### Current State

**1. Shared Folder Personas** (❌ Hardcoded)

Location: `/home/ec2-user/projects/shared/claude_team_sdk/examples/sdlc_team/personas.py`

```python
@staticmethod
def technical_writer() -> Dict[str, Any]:
    """Technical Writer - Creates documentation"""
    return {
        "id": "technical_writer",
        "name": "Technical Writer",
        "role_id": "writer",
        "phase": "documentation",

        # ❌ HARDCODED - Should reference JSON
        "expertise": [
            "Technical documentation writing",
            "API documentation (OpenAPI, Swagger)",
            "User guides and tutorials",
            "Architecture documentation",
            "Video and screenshot creation",
            "Documentation as Code (Docs-as-Code)",
            "Information architecture",
            "Content management systems"
        ],

        # ❌ HARDCODED - Should reference JSON
        "responsibilities": [
            "Create user documentation",
            "Write API documentation",
            "Document system architecture",
            "Create tutorials and how-to guides",
            "Maintain knowledge base",
            "Create release notes",
            "Review documentation for accuracy",
            "Organize documentation structure"
        ],

        # ... more hardcoded data
    }
```

**Issues with this approach**:
- ❌ Duplicate definitions across projects
- ❌ Hard to maintain consistency
- ❌ Changes require code updates in multiple places
- ❌ No validation or schema enforcement
- ❌ Expertise and deliverables drift out of sync

---

## Solution: Centralized JSON Definitions

### Centralized Persona Definitions (✅ Single Source of Truth)

Location: `src/personas/definitions/*.json`

**Example**: `src/personas/definitions/technical_writer.json`

```json
{
  "persona_id": "technical_writer",
  "schema_version": "3.0",
  "version": "1.0.0",
  "display_name": "Technical Writer",

  "role": {
    "primary_role": "technical_writer",
    "experience_level": 7,
    "autonomy_level": 7,
    "specializations": [
      "api_documentation",
      "user_guides",
      "developer_documentation",
      "tutorial_creation",
      "documentation_systems",
      "technical_communication"
    ]
  },

  "capabilities": {
    "core": [
      "readme_creation",
      "api_documentation",
      "user_guide_writing",
      "tutorial_development",
      "code_commenting",
      "documentation_structure"
    ],
    "tools": [
      "markdown",
      "openapi_swagger",
      "docusaurus",
      "readme_generators"
    ]
  },

  "contracts": {
    "output": {
      "required": [
        "readme",
        "user_guide",
        "api_documentation",
        "setup_instructions"
      ],
      "optional": [
        "developer_guide",
        "architecture_documentation",
        "tutorials",
        "faq",
        "troubleshooting_guide"
      ]
    }
  }
}
```

**Benefits**:
- ✅ Single source of truth
- ✅ Pydantic validation ensures consistency
- ✅ Easy to update (change JSON, not code)
- ✅ Structured schema (Schema v3.0)
- ✅ Reusable across all services

---

## Architecture: How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                  CENTRALIZED PERSONA SYSTEM                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. JSON Definitions (Single Source of Truth)                   │
│     src/personas/definitions/*.json                             │
│     ├── technical_writer.json                                   │
│     ├── backend_developer.json                                  │
│     ├── solution_architect.json                                 │
│     └── ... (11 personas)                                       │
│                                                                  │
│  2. Pydantic Models (Validation)                                │
│     src/personas/models.py                                      │
│     └── PersonaDefinition - validates all JSON files            │
│                                                                  │
│  3. Registry (Loading & Access)                                 │
│     src/personas/registry.py                                    │
│     └── PersonaRegistry - loads and manages personas            │
│                                                                  │
│  4. Adapter (Legacy Compatibility)                              │
│     src/personas/adapter.py                                     │
│     └── Converts JSON → legacy dict format                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    CONSUMERS (No Hardcoding)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ✅ Orchestration Engine                                        │
│     → Uses adapter to get persona definitions                   │
│     → No hardcoded expertise or deliverables                    │
│                                                                  │
│  ✅ Workflow API                                                │
│     → References personas by ID                                 │
│     → Gets attributes from registry                             │
│                                                                  │
│  ✅ Legacy Systems                                              │
│     → Adapter provides backward-compatible format               │
│     → No code changes needed                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## How to Use Centralized Personas

### 1. Load Persona Definitions (Async)

```python
from src.personas import PersonaRegistry, get_registry

# Load all persona definitions
registry = await get_registry()

# Get specific persona
technical_writer = registry.get("technical_writer")

# Access attributes from JSON
print(f"Name: {technical_writer.display_name}")
print(f"Specializations: {technical_writer.role.specializations}")
print(f"Core Capabilities: {technical_writer.capabilities.core}")
print(f"Expected Outputs: {technical_writer.contracts.output.required}")
```

### 2. Use Adapter for Legacy Compatibility

```python
from src.personas import get_adapter

# Get adapter instance
adapter = get_adapter()
await adapter.load_personas()

# Get in legacy format (compatible with old code)
legacy_personas = adapter.get_all_personas()

technical_writer = legacy_personas["technical_writer"]
print(f"Expertise: {technical_writer['expertise']}")
# Expertise is dynamically built from:
# - capabilities.core (first 8 items)
# - role.specializations (up to 3 items)
```

### 3. Create New Personas (No Hardcoding!)

**Bad (Old Way - Hardcoded)**:
```python
def __init__(self, coordination_server):
    super().__init__(
        persona_id="technical_writer",
        coordination_server=coordination_server,
        role=AgentRole.DEVELOPER,
        persona_name="Technical Writer",
        expertise=[                           # ❌ Hardcoded!
            "Technical documentation",
            "User guides",
            "API documentation",
            "README creation",
            "Documentation standards"
        ],
        expected_deliverables=[               # ❌ Hardcoded!
            "README.md - Project README",
            "docs/USER_GUIDE.md - User guide",
            "docs/DEVELOPER_GUIDE.md - Developer guide",
            "CHANGELOG.md - Change log"
        ]
    )
```

**Good (New Way - Reference JSON)**:
```python
from src.personas import get_registry

async def create_technical_writer_persona(coordination_server):
    # Load persona definition from JSON
    registry = await get_registry()
    persona_def = registry.get("technical_writer")

    # Use attributes from JSON (no hardcoding!)
    return TechnicalWriterPersona(
        persona_id=persona_def.persona_id,
        coordination_server=coordination_server,
        role=AgentRole.DEVELOPER,
        persona_name=persona_def.display_name,
        expertise=persona_def.role.specializations + persona_def.capabilities.core,
        expected_deliverables=persona_def.contracts.output.required
    )
```

**Even Better (Use Adapter)**:
```python
from src.personas import get_adapter

async def create_persona_from_registry(persona_id: str, coordination_server):
    adapter = get_adapter()
    await adapter.ensure_loaded()

    # Get persona in legacy format (expertise, responsibilities auto-populated)
    persona_dict = adapter.get_persona(persona_id)

    return PersonaClass(
        persona_id=persona_dict["id"],
        coordination_server=coordination_server,
        role=AgentRole.from_string(persona_dict["role_id"]),
        persona_name=persona_dict["name"],
        expertise=persona_dict["expertise"],              # ✅ From JSON
        expected_deliverables=persona_dict["responsibilities"]  # ✅ From JSON
    )
```

---

## Migration Strategy

### Phase 1: Inventory Hardcoded Personas ✅ (Completed)

**Found**:
- `shared/claude_team_sdk/examples/sdlc_team/personas.py` - 11 personas hardcoded
- Test files referencing old persona classes

### Phase 2: Verify JSON Definitions ✅ (Completed)

**Status**: All 11 personas have JSON definitions in `src/personas/definitions/`:
- ✅ requirement_analyst.json
- ✅ solution_architect.json
- ✅ ui_ux_designer.json
- ✅ frontend_developer.json
- ✅ backend_developer.json
- ✅ database_administrator.json
- ✅ devops_engineer.json
- ✅ deployment_specialist.json
- ✅ qa_engineer.json
- ✅ security_specialist.json
- ✅ technical_writer.json

### Phase 3: Update Shared Folder Personas (⚠️ Action Required)

**Option A: Deprecate Shared Folder Personas**
```python
# shared/claude_team_sdk/examples/sdlc_team/personas.py

import sys
from pathlib import Path

# Add maestro-engine to path
sys.path.insert(0, "/home/ec2-user/projects/maestro-engine")

from src.personas import get_adapter

class SDLCPersonas:
    """
    DEPRECATED: This class now references maestro-engine JSON personas.

    All persona definitions are centralized in:
    /home/ec2-user/projects/maestro-engine/src/personas/definitions/
    """

    @staticmethod
    def get_all_personas():
        """Get all personas from centralized JSON definitions"""
        import asyncio
        adapter = get_adapter()

        # Load if not already loaded
        if not adapter._loaded:
            asyncio.run(adapter.load_personas())

        return adapter.get_all_personas()

    @staticmethod
    def technical_writer():
        """Technical Writer persona - references JSON definition"""
        return SDLCPersonas.get_all_personas()["technical_writer"]

    # ... repeat for all personas
```

**Option B: Mirror JSON in Shared Folder**
```bash
# Sync JSON definitions to shared folder
cp -r /home/ec2-user/projects/maestro-engine/src/personas/definitions \
      /home/ec2-user/projects/shared/persona_definitions/

# Update shared personas.py to load from JSON
```

### Phase 4: Update All References (⚠️ Action Required)

**Files to Update**:
1. `run_test_workflow.py` - Use maestro-engine personas
2. `test_integration_with_executor.py` - Use maestro-engine personas
3. Shared folder executor - Reference JSON definitions

---

## Mapping: Hardcoded → JSON

| Hardcoded Attribute | JSON Location | Notes |
|-------------------|---------------|-------|
| `expertise[]` | `capabilities.core + role.specializations` | Adapter combines both |
| `responsibilities[]` | `contracts.output.required` | Expected deliverables |
| `name` | `display_name` | Human-readable name |
| `role_id` | Inferred from `metadata.category` | Adapter maps category→role |
| `phase` | Inferred from `metadata.category` | Adapter maps category→phase |
| `system_prompt` | `prompts.system_prompt` | Direct mapping |
| `tools_allowed` | Hardcoded in adapter | Same for all personas |
| `key_metrics` | `quality_metrics.expected_output_quality` | Converted to array |

---

## Example: Technical Writer Mapping

### Before (Hardcoded)
```python
{
    "expertise": [
        "Technical documentation writing",
        "API documentation (OpenAPI, Swagger)",
        ...
    ],
    "responsibilities": [
        "Create user documentation",
        "Write API documentation",
        ...
    ]
}
```

### After (From JSON)
```python
# From technical_writer.json:
{
    "capabilities": {
        "core": [
            "readme_creation",           # → expertise
            "api_documentation",         # → expertise
            "user_guide_writing",        # → expertise
            ...
        ]
    },
    "role": {
        "specializations": [
            "api_documentation",         # → expertise
            "user_guides",              # → expertise
            ...
        ]
    },
    "contracts": {
        "output": {
            "required": [
                "readme",               # → responsibilities
                "user_guide",           # → responsibilities
                "api_documentation",    # → responsibilities
                ...
            ]
        }
    }
}
```

### Adapter Conversion (Automatic)
```python
# adapter.py automatically builds:
expertise = (
    persona.capabilities.core[:8] +  # First 8 core capabilities
    persona.role.specializations[:3]  # Up to 3 specializations
)
# Result: ["readme_creation", "api_documentation", ..., "api_documentation", "user_guides", ...]

responsibilities = [
    f"Deliver {cap.replace('_', ' ')}"
    for cap in persona.capabilities.core[:8]
]
# Result: ["Deliver readme creation", "Deliver api documentation", ...]
```

---

## Testing the Migration

### 1. Verify JSON Loading
```bash
cd /home/ec2-user/projects/maestro-engine
python3 -c "
import asyncio
from src.personas import get_registry

async def test():
    registry = await get_registry()
    tw = registry.get('technical_writer')
    print(f'✅ Loaded: {tw.display_name}')
    print(f'   Capabilities: {len(tw.capabilities.core)} items')
    print(f'   Specializations: {len(tw.role.specializations)} items')
    print(f'   Deliverables: {len(tw.contracts.output.required)} items')

asyncio.run(test())
"
```

### 2. Test Legacy Compatibility
```bash
python3 -c "
import asyncio
from src.personas import get_adapter

async def test():
    adapter = get_adapter()
    await adapter.load_personas()

    legacy = adapter.get_all_personas()
    tw = legacy['technical_writer']

    print(f'✅ Legacy Format:')
    print(f'   Name: {tw[\"name\"]}')
    print(f'   Expertise: {len(tw[\"expertise\"])} items')
    print(f'   Responsibilities: {len(tw[\"responsibilities\"])} items')
    print(f'   Phase: {tw[\"phase\"]}')

asyncio.run(test())
"
```

### 3. Test Adapter in Executor
```bash
python3 run_test_workflow.py technical_writer --example simple
```

---

## Action Items

### Immediate (High Priority)
- [ ] **Update shared folder personas.py** to reference maestro-engine JSON definitions
- [ ] **Update run_test_workflow.py** to use maestro-engine personas directly
- [ ] **Update test files** to use JSON-based personas

### Short-term (Medium Priority)
- [ ] **Deprecate hardcoded persona classes** in shared folder
- [ ] **Add validation** that personas match JSON definitions
- [ ] **Update documentation** to reference centralized personas

### Long-term (Low Priority)
- [ ] **Consolidate all persona definitions** to single project
- [ ] **Create persona versioning** system
- [ ] **Build persona editor UI** for non-developers

---

## Benefits Summary

### Before (Hardcoded)
- ❌ Duplicate definitions in 3+ places
- ❌ No schema validation
- ❌ Hard to maintain consistency
- ❌ Code changes required for updates
- ❌ Expertise/deliverables drift

### After (JSON Definitions)
- ✅ Single source of truth
- ✅ Pydantic schema validation
- ✅ Easy updates (edit JSON, no code)
- ✅ Consistent across all services
- ✅ Backward compatible via adapter

---

## Related Files

- **JSON Definitions**: `src/personas/definitions/*.json`
- **Pydantic Models**: `src/personas/models.py`
- **Registry**: `src/personas/registry.py`
- **Adapter**: `src/personas/adapter.py`
- **Shared Personas (Deprecated)**: `shared/claude_team_sdk/examples/sdlc_team/personas.py`
- **Integration Guide**: `GATEWAY_INTEGRATION_GUIDE.md`

---

**Next Step**: Update shared folder to reference centralized JSON definitions instead of hardcoding persona attributes.
