# Test Findings & Action Plan

**Date**: 2025-10-01
**Status**: Analysis Complete - Actions Identified

## Executive Summary

Found that **test suite contains tests for old maestro-v2 microservices architecture** that don't apply to the new maestro-engine monolithic backend. Tests need to be updated or removed.

## Architecture Understanding

### maestro-engine (Current - NEW)
```
maestro-engine/
├── src/
│   ├── mcp/              # MCP/UTCP orchestration (integrated)
│   ├── orchestration/    # Workflow coordination (integrated)
│   ├── rag/              # RAG integration (integrated)
│   ├── templates/        # Template integration (integrated)
│   ├── registry/         # Service registry (NEW)
│   └── api/              # API routes (NEW)
└── run_engine.py         # Monolithic entry point
```

**Architecture**: Monolithic backend that integrates with external services
- **Internal**: MCP, orchestration, RAG, templates as integrated modules
- **External**: Quality Fabric (:8000), Template Registry (:8001)

### maestro-v2 (OLD - Not Migrated)
```
maestro-v2/
├── services/
│   ├── orchestration_gateway/
│   │   └── shared/
│   │       ├── orchestration/multi_phase_engine.py
│   │       ├── intelligence/phase_complexity_analyzer.py
│   │       ├── autonomy/dynamic_boundary_manager.py
│   │       └── models/orchestration_node.py
│   ├── intelligence-service/
│   └── template-registry-service/
└── maestro_config.py
```

**Architecture**: Microservices (NOT migrated to maestro-engine)

## Test Analysis Results

### ✅ Category 1: Working Tests (12 passing)
**Status**: ✅ Keep as-is

Tests that work correctly:
- `test_malformed_request_handling`
- `test_response_time_check`
- `test_concurrent_request_handling`
- `test_import_resolution_without_path_manipulation`
- `test_no_hardcoded_paths_in_imports`
- `test_poetry_package_structure`
- `test_relative_import_patterns`
- `test_async_operations_performance`
- `test_component_lifecycle_complete`

**Action**: ✅ None - these tests are valid

### ⚠️ Category 2: Old Architecture References (9 failing tests)
**Status**: ❌ Need to delete or rewrite

Tests that reference maestro-v2 modules that don't exist in maestro-engine:

1. **`test_coherent_system_imports`** (`test_import_system.py:18-50`)
   - Imports: `services.orchestration_gateway.shared.orchestration.multi_phase_engine`
   - Imports: `services.orchestration_gateway.shared.intelligence.phase_complexity_analyzer`
   - Imports: `services.orchestration_gateway.shared.autonomy.rule_based_spawner`
   - Imports: `services.orchestration_gateway.shared.autonomy.dynamic_boundary_manager`
   - Imports: `services.orchestration_gateway.shared.communication.hive_communication`
   - **Issue**: These are Phase 4/5 microservices components NOT in maestro-engine

2. **`test_coherent_domain_system_imports`** (`test_import_system.py:52-77`)
   - Imports: `enhanced_coherent_with_ai_coordination.AIEnhancedCoherentDomainSystem`
   - Imports: `stigmergy_engine.StigmergyEngine`
   - Imports: `digital_blackboard_system.DigitalBlackboardSystem`
   - Imports: `coherent_domain_system.CoherentDomainSystem`
   - **Issue**: Phase 5 features NOT in maestro-engine

3. **`test_configuration_imports`** (`test_import_system.py:79-87`)
   - Imports: `maestro_config.get_config`, `MaestroConfig`
   - **Issue**: maestro_config.py is in maestro-v2, not maestro-engine

4. **`test_shared_components_imports`** (`test_import_system.py:89-102`)
   - Imports: `shared.models.orchestration_node.OrchestrationNode`
   - Imports: `shared.intelligence.complexity_analyzer.ComplexityAnalyzer`
   - **Issue**: Old `shared/` directory structure from maestro-v2

5. **`test_no_import_errors_on_basic_components`** (`test_import_system.py:164-182`)
   - Imports: `enhanced_orchestration_system`
   - Imports: `enhanced_workflow_with_deployment`
   - Imports: `coherent_blackboard_integration`
   - **Issue**: These are root-level modules from maestro-v2

**Performance Tests** (4 tests with same issue):
- `test_orchestration_latency`
- `test_workflow_throughput`
- `test_service_scaling_performance`
- `test_concurrent_workflow_execution`
- **Issue**: All reference `maestro_config` and `services` modules

### ⚠️ Category 3: E2E Tests Requiring External Services (12 tests)
**Status**: ⏸️ Expected failures when services not running

Tests that need external services:
- `test_health_endpoints_compliance` - Expects Quality Fabric on :8000
- `test_workflow_orchestration` - Expects orchestration service
- `test_rag_integration` - Expects RAG service endpoints
- Others...

**Action**: ✅ Keep - these are valid E2E tests, just need services running

### ⚠️ Category 4: Missing Dependency (1 error)
**Status**: ⚠️ Minor - Add if needed

- `test_performance/test_benchmarks.py` - Missing `pytest-benchmark`

**Action**: Add dependency if benchmarking is needed

## Detailed Actions Required

### Action 1: Delete or Update Invalid Import Tests ❌ HIGH PRIORITY

**File**: `tests/integration/test_import_system.py`

**Option A - Delete Invalid Tests** (RECOMMENDED):
```bash
# Remove these test methods from test_import_system.py:
- test_coherent_system_imports (lines 18-50)
- test_coherent_domain_system_imports (lines 52-77)
- test_configuration_imports (lines 79-87)
- test_shared_components_imports (lines 89-102)
- test_no_import_errors_on_basic_components (lines 164-182)
```

**Option B - Rewrite for maestro-engine Architecture**:
```python
def test_maestro_engine_core_imports(self):
    """Test maestro-engine core module imports"""
    # Test new architecture
    from src.mcp import hot_claude_live_backend_sdk
    from src.orchestration import maestro_unified_orchestration_gateway
    from src.rag import maestro_rag_system
    from src.templates import enterprise_template_repository
    from src.registry import ServiceRegistry
    from src.api import registry_routes
```

### Action 2: Fix Performance Tests ⚠️ MEDIUM PRIORITY

**Files**:
- `tests/performance/test_coherent_system_performance.py`
- `tests/performance/test_load_testing.py`

**Issue**: Reference `maestro_config` and `services` modules

**Fix**: Update imports to use maestro-engine endpoints:
```python
# OLD (maestro-v2)
from maestro_config import get_config
from services.orchestration_gateway import OrchestrationType

# NEW (maestro-engine)
# Use direct API calls instead
import httpx
async with httpx.AsyncClient() as client:
    response = await client.get("http://localhost:8002/health")
```

### Action 3: Add pytest-benchmark (Optional) ⏸️ LOW PRIORITY

```bash
poetry add --group dev pytest-benchmark
```

### Action 4: Document Test Categories 📝 MEDIUM PRIORITY

Create test markers in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
    "unit: Unit tests (fast, no external dependencies)",
    "integration: Integration tests (require internal components)",
    "e2e: End-to-end tests (require external services)",
    "performance: Performance and load tests",
]
```

## Recommended Immediate Actions

### Phase 1: Cleanup Invalid Tests (This Week)

1. **Delete invalid import tests** from `test_import_system.py`:
   ```bash
   # Edit tests/integration/test_import_system.py
   # Remove methods testing maestro-v2 imports
   ```

2. **Update performance tests** to use HTTP API instead of module imports:
   ```bash
   # Edit tests/performance/*.py
   # Replace maestro_config imports with httpx API calls
   ```

3. **Add pytest markers** to categorize tests:
   ```bash
   # Update pyproject.toml with test markers
   ```

### Phase 2: Create maestro-engine Specific Tests (Next Week)

1. **Service Registry Tests**:
   - Test service registration
   - Test health checking
   - Test service discovery

2. **API Integration Tests**:
   - Test /registry/* endpoints
   - Test coordinator endpoints
   - Test error handling

3. **Module Import Tests**:
   - Test src.mcp imports
   - Test src.orchestration imports
   - Test src.rag imports
   - Test src.templates imports

## File-by-File Action Plan

### tests/integration/test_import_system.py
**Action**: Delete or rewrite 5 test methods
**Priority**: HIGH
**Reason**: Tests reference non-existent maestro-v2 modules

**Tests to remove/rewrite**:
- Lines 18-50: `test_coherent_system_imports`
- Lines 52-77: `test_coherent_domain_system_imports`
- Lines 79-87: `test_configuration_imports`
- Lines 89-102: `test_shared_components_imports`
- Lines 164-182: `test_no_import_errors_on_basic_components`

**Tests to keep**:
- Lines 104-115: `test_no_hardcoded_paths_in_imports` ✅
- Lines 117-137: `test_import_resolution_without_path_manipulation` ✅
- Lines 139-149: `test_relative_import_patterns` ✅
- Lines 151-162: `test_poetry_package_structure` ✅

### tests/performance/test_coherent_system_performance.py
**Action**: Update imports to use HTTP API
**Priority**: MEDIUM
**Reason**: Tests reference maestro_config module

### tests/performance/test_load_testing.py
**Action**: Update imports to use HTTP API
**Priority**: MEDIUM
**Reason**: Tests reference maestro_config and services modules

### tests/e2e/test_comprehensive_api_scenarios.py
**Action**: None - expected failures
**Priority**: LOW
**Reason**: Tests correctly fail when external services not running

### tests/performance/test_benchmarks.py
**Action**: Add pytest-benchmark dependency
**Priority**: LOW
**Reason**: Minor missing dependency

## Test Success Criteria

After fixes, we should have:
- ✅ ~12 passing unit/integration tests (currently passing)
- ✅ 0 failing tests due to old architecture references (after cleanup)
- ⏸️ ~12 skipped/expected failures for E2E tests (without external services)
- ✅ New service registry tests (to be added)

## Summary of Required Changes

| File | Tests Affected | Action | Priority |
|------|----------------|--------|----------|
| `test_import_system.py` | 5 methods | Delete or rewrite | HIGH |
| `test_coherent_system_performance.py` | Multiple | Update imports | MEDIUM |
| `test_load_testing.py` | Multiple | Update imports | MEDIUM |
| `test_benchmarks.py` | 1 test | Add dependency | LOW |
| New file needed | N/A | Add registry tests | MEDIUM |

## Quick Fix Script

```bash
#!/bin/bash
# Quick fix for maestro-engine tests

cd /home/ec2-user/projects/maestro-engine

# Backup current test file
cp tests/integration/test_import_system.py tests/integration/test_import_system.py.backup

# Create fixed version (remove invalid tests, keep valid ones)
# This would be a Python script to surgically remove the failing test methods

# Run tests to verify
poetry run pytest tests/integration/test_import_system.py -v

# If successful, commit changes
git add tests/integration/test_import_system.py
git commit -m "fix: Remove tests for non-existent maestro-v2 modules"
```

## Next Steps

1. **Immediate** (Today):
   - Review this analysis
   - Decide: Delete invalid tests OR rewrite for new architecture
   - Apply changes to `test_import_system.py`

2. **This Week**:
   - Update performance tests to use HTTP API
   - Add pytest markers
   - Run full test suite
   - Document test categories

3. **Next Week**:
   - Write service registry tests
   - Write API integration tests
   - Add module import tests for new architecture

---

**Status**: Analysis Complete ✅
**Critical Action**: Remove/rewrite 5 test methods in test_import_system.py
**Estimated Time**: 1-2 hours to fix all issues
