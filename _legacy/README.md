# _legacy/ - Archived Code

This directory contains archived code that has been replaced by newer implementations.

**Date Archived**: 2025-10-04
**Reason**: Consolidating to production-ready code per ADR-007: Code Organization

## What's Here

### maestro_mcp_original/
- Original MCP/UTCP implementation
- Replaced by: `src/orchestration/` and `src/personas/`
- Contains: Hot Claude sessions, MCP caching, workflow management

### orchestration_unused/
- Deprecated orchestration implementations
- Replaced by: Unified orchestrator in `src/orchestration/`
- Variants: parallel, adaptive, unified gateway

## Policy

Per **ADR-007: Code Organization and Cleanup Policy**:

1. **No Production Imports**: Code in `_legacy/` must NOT be imported by production code (`src/`)
2. **Pre-commit Hook**: Automatically blocks legacy imports during commits
3. **CI/CD Validation**: GitHub Actions checks for legacy imports on every PR
4. **Retention**: Can be deleted after 2 releases (reference only)

## Migration

If you need functionality from legacy code:

1. Review the archived implementation
2. Extract the concept/pattern needed
3. Rebuild cleanly in `src/` with modern best practices
4. Add tests and documentation
5. Submit for code review

**Do not copy-paste from legacy code** - rebuild thoughtfully.

## Reference

- **ADR-007**: docs/architecture/ADR-007-code-organization.md
- **Simplified Architecture**: docs/architecture/SIMPLIFIED_ARCHITECTURE.md
