# _experiments/ - Experimental Code

This directory contains experimental code and proof-of-concepts that are NOT production-ready.

**Purpose**: Research, prototyping, and exploration of new ideas

## Rules

Per **ADR-007: Code Organization and Cleanup Policy**:

1. **Not Production Code**: Code here is excluded from production builds and deployments
2. **No Production Imports**: Production code (`src/`) cannot import from `_experiments/`
3. **Excluded from CI/CD**: Tests and linting are skipped for experimental code
4. **Monthly Review**: Experiments reviewed monthly for:
   - Promotion to `src/` (if proven valuable)
   - Archival to `_legacy/` (if superseded)
   - Deletion (if no longer relevant)

## What Goes Here

✅ **Appropriate for _experiments/**:
- Proof-of-concept implementations
- Performance benchmarks
- Alternative approaches being evaluated
- Research code for future features
- Prototypes for architectural decisions

❌ **NOT appropriate** (use `src/` instead):
- Production-ready features
- Bug fixes
- Performance optimizations for existing code
- Security patches

## Structure

```
_experiments/
├── README.md (this file)
├── {experiment_name}/
│   ├── README.md           # What, why, status
│   ├── {code}.py
│   └── results.md          # Findings/conclusions
```

## Process

1. **Create**: Add experiment with descriptive README
2. **Iterate**: Develop and test freely
3. **Document**: Record findings and conclusions
4. **Decide**:
   - Promote to `src/` if successful
   - Archive to `_legacy/` if superseded
   - Delete if no longer needed

## Current Experiments

_None yet - this directory was just created._

## Reference

- **ADR-007**: docs/architecture/ADR-007-code-organization.md
