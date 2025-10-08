# Parallel Execution Guide

## Dynamic Teams & Parallel Execution in MAESTRO

### Current Implementation: Sequential Execution

```
Timeline: ────────────────────────────────────────────────────►

Tier 1: [requirement_analyst]           (30s)
        ────────────────────────►

Tier 2:                          [solution_architect]  (40s)
                                 ────────────────────────►

Tier 3:                                                  [security_specialist] (20s)
                                                         ──────────────►

Tier 4:                                                                        [backend_dev] (60s)
                                                                               ──────────────────────────────►

Tier 4:                                                                                                      [database_spec] (40s)
                                                                                                             ────────────────────────►

Total Time: 30 + 40 + 20 + 60 + 40 = 190 seconds
```

**Problem**: `backend_developer` and `database_specialist` have the same priority (4) but run sequentially!

---

### Enhanced Implementation: True Parallel Execution

```
Timeline: ────────────────────────────────────────────────────►

Tier 1: [requirement_analyst]           (30s)
        ────────────────────────►

Tier 2:                          [solution_architect]  (40s)
                                 ────────────────────────►

Tier 3:                                                  [security_specialist] (20s)
                                                         ──────────────►

Tier 4:                                                                        [backend_dev]    (60s)
        (PARALLEL)                                                             ──────────────────────────────►
                                                                               [database_spec]  (40s)
                                                                               ────────────────────────►

Total Time: 30 + 40 + 20 + 60 = 150 seconds (40s saved!)
```

**Benefit**: Same-priority personas run in parallel, reducing total execution time!

---

## Feature Comparison

| Feature | Current System | Enhanced Parallel System |
|---------|---------------|--------------------------|
| **Dynamic Teams** | ✅ Yes - Select any personas | ✅ Yes - Select any personas |
| **Resumable Sessions** | ✅ Yes - Add personas later | ✅ Yes - Add personas later |
| **Priority Tiers** | ✅ Yes - 9 tiers defined | ✅ Yes - 9 tiers defined |
| **Parallel Execution** | ❌ No - Sequential only | ✅ Yes - Within same tier |
| **Execution Time** | Slower (sequential) | Faster (parallel) |

---

## Dynamic Team Examples

### Example 1: Minimal Backend Team

```python
# Just backend development - no frontend, no testing
engine = AutonomousSDLCEngineV3Resumable(
    selected_personas=[
        "backend_developer",
        "database_specialist"
    ]
)

# Execution:
# Tier 4: backend_developer → database_specialist (sequential)
# Total: 2 personas
```

### Example 2: Full-Stack Team

```python
# Complete application team
engine = AutonomousSDLCEngineV3Resumable(
    selected_personas=[
        "requirement_analyst",
        "solution_architect",
        "backend_developer",
        "database_specialist",
        "frontend_developer",
        "ui_ux_designer",
        "devops_engineer"
    ]
)

# Execution (current):
# Tier 1: requirement_analyst
# Tier 2: solution_architect
# Tier 4: backend_developer → database_specialist (sequential)
# Tier 5: frontend_developer → ui_ux_designer (sequential)
# Tier 8: devops_engineer

# Execution (parallel):
# Tier 1: requirement_analyst
# Tier 2: solution_architect
# Tier 4: backend_developer ⚡ database_specialist (PARALLEL)
# Tier 5: frontend_developer ⚡ ui_ux_designer (PARALLEL)
# Tier 8: devops_engineer
```

### Example 3: Testing-Only Team

```python
# Just run tests on existing code
engine = AutonomousSDLCEngineV3Resumable(
    selected_personas=[
        "unit_tester",
        "integration_tester"
    ]
)

# Execution:
# Tier 6: unit_tester
# Tier 7: integration_tester
# Total: 2 personas
```

### Example 4: Incremental Development (Resumable)

```python
# Day 1: Requirements and architecture
engine = AutonomousSDLCEngineV3Resumable(
    selected_personas=["requirement_analyst", "solution_architect"]
)
result1 = await engine.execute(
    requirement="Build e-commerce platform",
    session_id="ecommerce_v1"
)

# Day 2: Add backend development
engine = AutonomousSDLCEngineV3Resumable(
    selected_personas=["backend_developer", "database_specialist"]
)
result2 = await engine.execute(
    requirement="",
    resume_session_id="ecommerce_v1"  # Continues from Day 1
)

# Day 3: Add frontend
engine = AutonomousSDLCEngineV3Resumable(
    selected_personas=["frontend_developer", "ui_ux_designer"]
)
result3 = await engine.execute(
    requirement="",
    resume_session_id="ecommerce_v1"  # Continues from Day 2
)

# Result: All personas' work is accumulated in session "ecommerce_v1"
```

---

## How Parallel Execution Works

### Grouping by Priority

```python
def _group_by_priority(personas):
    # Input: ["backend_developer", "database_specialist", "frontend_developer"]

    # Output:
    {
        4: ["backend_developer", "database_specialist"],  # Same tier
        5: ["frontend_developer"]
    }
```

### Executing Each Tier

```python
for priority, personas_in_tier in priority_groups.items():
    # Execute ALL personas in this tier IN PARALLEL
    tasks = [
        execute_persona(persona_id)
        for persona_id in personas_in_tier
    ]

    # Wait for ALL to complete before moving to next tier
    results = await asyncio.gather(*tasks)

    # Save results and move to next tier
```

---

## Coordination Mechanisms

### 1. Shared Session State

```python
# All personas in a tier share:
- Same session context (what was done before)
- Same output directory
- Same requirement
- Same RAG guidance

# Each persona creates:
- Its own files
- Its own deliverables
- Its own execution record
```

### 2. File System Locking

```
backend_developer creates:
  ├── src/main.py
  ├── src/api/
  └── src/models.py

database_specialist creates (in parallel):
  ├── migrations/
  ├── schema.sql
  └── seeds/

No conflicts because they work on different parts!
```

### 3. Session Context for Next Tier

```python
After Tier 4 completes (both personas):

Session Context for Tier 5:
  Completed Personas: requirement_analyst, solution_architect,
                     backend_developer, database_specialist

  Files Created:
    - backend_developer: src/main.py, src/api/routes.py (5 files)
    - database_specialist: migrations/001_init.sql, schema.sql (3 files)

  frontend_developer and ui_ux_designer see ALL of this!
```

---

## Performance Comparison

### Sequential Execution Time

```
Tier 1: requirement_analyst (30s)
Tier 2: solution_architect (40s)
Tier 4: backend_developer (60s) + database_specialist (40s) = 100s
Tier 5: frontend_developer (70s) + ui_ux_designer (50s) = 120s
Tier 8: devops_engineer (30s)

Total: 30 + 40 + 100 + 120 + 30 = 320 seconds (5.3 minutes)
```

### Parallel Execution Time

```
Tier 1: requirement_analyst (30s)
Tier 2: solution_architect (40s)
Tier 4: max(backend_developer 60s, database_specialist 40s) = 60s ⚡
Tier 5: max(frontend_developer 70s, ui_ux_designer 50s) = 70s ⚡
Tier 8: devops_engineer (30s)

Total: 30 + 40 + 60 + 70 + 30 = 230 seconds (3.8 minutes)

SAVINGS: 90 seconds (28% faster!) ⚡
```

---

## Usage

### Current System (Sequential)

```python
engine = AutonomousSDLCEngineV3Resumable(
    selected_personas=[
        "backend_developer",
        "database_specialist"
    ]
)

result = await engine.execute(
    requirement="Build API with database"
)

# Executes: backend_developer → database_specialist (sequential)
```

### Enhanced System (Parallel)

```python
from orchestration.parallel_execution_enhancement import ParallelExecutionMixin

class ParallelEngine(ParallelExecutionMixin, AutonomousSDLCEngineV3Resumable):
    pass

engine = ParallelEngine(
    selected_personas=[
        "backend_developer",
        "database_specialist"
    ]
)

result = await engine.execute_with_parallelism(
    requirement="Build API with database"
)

# Executes: backend_developer ⚡ database_specialist (PARALLEL)
```

---

## Summary

**Dynamic Teams** ✅:
- Select any subset of 11 personas
- Add personas incrementally via resumable sessions
- Each persona contributes to shared project

**Parallel Execution** (Enhanced) ⚡:
- Same-priority personas run in parallel
- Reduces total execution time
- Safe coordination via session manager
- All personas see accumulated context

**Key Insight**:
Personas don't "talk" to each other directly. Instead:
- They execute in priority tiers
- Within a tier, they can run in parallel
- After each tier, results are accumulated in session
- Next tier sees all previous work via session context

---

**Version**: 1.0
**Last Updated**: 2025-10-03
**Implementation**: `src/orchestration/parallel_execution_enhancement.py`
