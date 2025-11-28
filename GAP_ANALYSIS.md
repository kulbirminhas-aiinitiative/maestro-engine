# Maestro Engine v3.0 – Baseline Workflow Mapping and Gap Analysis

Date: 2025-11-27
Location: /home/ec2-user/projects/maestro-engine-new

## Baseline (Provided) vs Current Implementation (Observed)

Baseline summary (frontend/back coordination + backend autonomous flow, ML-driven routing, multi-phase DDE/BRV/ACC gates, RAG/templates/quality-fabric feedback loop, success scoring, template generation, next-loop learning):

- Frontend
  1. Frontend can run full execution (coordination only)
  2. Frontend handles lightweight runs
  3. Backend handles detailed/long jobs
  4. ML-driven decision for front vs back handling
- Backend
  1. Requirement shared; FE/BE in sync
  2. Ideal team constructed (possibly provided by FE)
  3. Backend may enhance team with rationale; user can override
  4. AI Agents use RAG/templates/best practices
  5. Multiple phases with DDE, BRV, ACC auth; phase-level checks
  6. Post-deployment
  7. Success score per phase/member/team + reasons/gaps
  8. Capture learning for next execution
  9. Successful runs generate templates (Maestro-templates)
  10. Each phase has test scenarios (quality-fabric)
  11. Quality-fabric outcomes drive improvement
- Next loop
  1. Better templates + past learnings/artifacts → higher success probability

Current implementation highlights (from repo documentation and structure):

- Frontend-Agnostic API: REST + WebSocket exposed; BFF service exists; multiple start scripts; Swagger.
- Orchestration: Autonomous SDLC Engine v3, persona orchestrator, DAG workflow engine with batch/phased/mixed execution.
- Personas: 11 JSON persona definitions, registry, execution with context propagation.
- RAG/Templates: RAG integration (ChromaDB vector), template registry integration (maestro-templates), workflow suggestion engine.
- Execution Infra: Redis state, optional Celery queue for long-running tasks, WebSocket live updates.
- Documentation: Comprehensive API spec, implementation summary, quick start testing, orchestration and persona docs.
- Testing: >100 tests across unit/integration/E2E; health/status endpoints; workflow execution tests; DAG catalog tests.

## Mapping: Baseline Requirements → Current System

1. Frontend can run full execution (coordination only)
- Status: Partially Met
- Evidence: Frontend-agnostic design in README/API_SPECIFICATION; BFF routes for chat and Guardian trigger; WebSocket hub for live progress.
- Gap: No explicit FE-side executor toggling documented; FE acts as orchestrator/monitor but not an independent executor. Need FE capability matrix and a switch to “client-side quick run” for tiny tasks.

2. Frontend handles lightweight runs
- Status: Partially Met
- Evidence: BFF can trigger @workflow, suggestion, import to DAG Studio; small actions routed via BFF.
- Gap: Policy for “lightweight” classification and direct FE-local tools not formalized; lack of FE-side sandbox execution path and resource quotas.

3. Backend handles detailed/long jobs
- Status: Met
- Evidence: Celery-based async queue, Redis tracking, status APIs, long-running queue (“maestro_long_running”), DAG execution modes.
- Gap: SLOs and job classes not documented; need queue policy doc (priority, retries, backoff) and per-mode SLAs.

4. ML-driven decision front vs back handling
- Status: Not Met / Prototype Only
- Evidence: WorkflowSuggestionEngine scoring exists (keywords, tech stack, complexity) but does not decide execution locus.
- Gap: Add ML policy service to route tasks (front/BFF vs backend) with explainability; gather telemetry to train models.

5. Requirement sync between FE/BE
- Status: Met
- Evidence: BFF collaboration service captures chat, extracts requirement, calls backend APIs; WebSocket updates; shared session_id.
- Gap: Documented contract for requirement schema across FE↔BE; add schema validation and versioning.

6. Team construction from requirement (possibly FE-supplied)
- Status: Partially Met
- Evidence: persona_ids input supported; team_organization module.
- Gap: FE UI for team suggestion/override not shown; require API to accept FE-proposed team with reasons.

7. Backend enhances team with rationale; user override
- Status: Partially Met
- Evidence: Team organization exists; no explicit rationale logging.
- Gap: Add “team_enhancement_report” artifact with why additional personas added; endpoint to lock base team.

8. AI Agents with RAG/templates/guidelines
- Status: Met (Feature-flagged)
- Evidence: RAG integration modules, templates_service, persona_rag_tools; enable flags in settings.
- Gap: Production enablement and dataset governance; provenance and citation logs per agent.

9. Multi-phase dev with DDE, BRV, ACC gates + phase checks
- Status: Partially Met
- Evidence: DAG phases with dependencies and validation; tests cover dependencies and sorting.
- Gap: DDE/BRV/ACC gates not codified; need standardized gate contracts and per-phase checklists; authorization hooks.

10. Post-deployment step
- Status: Partially Met
- Evidence: DevOps persona, deployment phases in templates; monitoring phase in microservice template.
- Gap: Real deployment runbooks integration and environment targets; release verification (smoke tests) not documented.

11. Success scores per phase/member/team, with reasons/gaps
- Status: Not Met
- Evidence: Progress and files count; no scoring framework.
- Gap: Introduce Quality & Success Scoring service (per persona/phase/team), store in Redis/DB, emit to WebSocket, persist in manifest.

12. Capture learning for next execution
- Status: Partially Met
- Evidence: RAG system and template registry imply learnings; session manager persists context.
- Gap: Formal “learning_snapshot” artifacts and ingestion pipeline to knowledge base; feedback loops metrics.

13. Successful runs generate new templates (Maestro-templates)
- Status: Partially Met
- Evidence: templates_service and quality_to_template_transformer exist; publishing scripts in repo.
- Gap: Automated promotion criteria, governance, versioning; API to create/publish templates from outputs.

14. Each phase has test scenarios via quality-fabric
- Status: Not Met / Optional
- Evidence: quality_fabric integration is optional and disabled by default (settings flags).
- Gap: Define phase-to-test mappings and enforce tests in gates; enable by default in non-dev environments.

15. Quality-fabric outcomes drive improvement
- Status: Not Met
- Evidence: Integration modules present but no closed loop.
- Gap: Add “quality_feedback_pipeline” that updates scoring, templates, and RAG corpus; track improvement over runs.

16. Next loop improves success probability (templates + learnings)
- Status: Partially Met
- Evidence: RAG/templates infrastructure present.
- Gap: KPI tracking across runs, uplift metrics, and automated selection of better templates; experiment tracking.

## Critical Gaps and Recommendations (Prioritized)

P0 (enable baseline loop integrity)
- ML Routing Policy: Implement a policy service deciding FE/BFF vs backend execution; telemetry and explainability (reason codes).
- Gate Framework (DDE/BRV/ACC): Define contracts, APIs, and enforcement hooks per phase; expose status via WebSocket; store gate decisions.
- Success Scoring: Per phase/persona/team scoring with reasons/gaps; integrate with manifest and RAG.

P1 (close feedback loops)
- Quality-Fabric Enforcement: Default-on in staging/prod; per-phase test suites; gate dependency on test pass/quality score.
- Learning Snapshot + Ingestion: Generate and ingest artifacts (design decisions, issues, scores) into RAG KB; provenance.
- Template Promotion Pipeline: Criteria, governance, versioning; publish to maestro-templates via API; auto-suggest promoted templates next run.

P2 (operational excellence)
- Deployment Verification: Post-deploy smoke tests and rollback rules integrated into gates.
- Team Enhancement Rationale: Generate rationale artifact, allow user override/lock; audit trail.
- Requirement Schema Contract: Versioned schema and validators in FE/BFF/BE; compatibility checks.
- SLOs & Queue Policies: Document job classes, SLAs, retries, priorities; metrics dashboards.

## Proposed Minimal Additions (Surgical changes)

- Add policy_service.py (BFF) for ML routing stub; log decisions with reason codes; config flags to enable.
- Extend workflow_engine to incorporate gate checks (simple JSON checklists + status field) and expose /api/gates endpoints.
- Introduce scoring_service.py to compute and persist scores; include in /api/workflow/status payload and WebSocket updates.
- Enable quality_fabric_client by default in non-dev; add phase→test mapping config; gate dependency on tests.
- Add learning_snapshot generator post-run; push to RAG via vector_rag_manager with metadata (session_id, persona, phase).
- Add template_promotion_api: POST /api/templates/promote with criteria and content; tie into scripts.

## Risk Assessment

- Feature flags required to avoid destabilizing production.
- Telemetry volume increases; ensure Redis/DB capacity and retention policies.
- Governance for template promotion and RAG ingestion to avoid data drift.

## Success Metrics

- % runs with gates enforced
- Average quality score improvement per next loop
- Reduction in failed gates due to quality-fabric
- Template promotion cadence and adoption rate
- ML routing accuracy and latency impact

## Conclusion

The current system implements most foundational parts (API, personas, DAG orchestration, RAG scaffolding, BFF integration). Key baseline elements—ML routing, gate framework (DDE/BRV/ACC), success scoring, enforced quality-fabric loop, and automated template promotion—are partially present or missing. Implementing the minimal additions above will close the feedback loop, align with the baseline, and improve next-run success probabilities with limited, surgical changes.

## Critical Code Review & Analysis (Added 2025-11-27)

After a deep dive into the codebase (`src/orchestration`, `src/workflow`, `src/quality_fabric_client.py`, `src/workflow_template_extractor.py`), the following critical observations are made regarding the backend engine:

### 1. "ML Routing" is Non-Existent
- **Claim:** "ML-driven decision for front vs back handling".
- **Reality:** `AutonomousSDLCEngineV3Resumable` uses a hardcoded `priority_tiers` dictionary to determine execution order. There is no machine learning model or logic that evaluates task complexity to decide between frontend or backend execution. The "Routing" is purely static and sequential.
- **Risk:** The system cannot dynamically adapt to task difficulty, leading to potential resource misuse (using heavy backend processes for trivial tasks).

### 2. Missing Gate Framework (DDE/BRV/ACC)
- **Claim:** "Multiple phases with DDE, BRV, ACC auth; phase-level checks".
- **Reality:** The `WorkflowEngine` implements a standard DAG with `depends_on` relationships. There is no code implementing "Gates" as distinct architectural constructs. Concepts like "Design Definition Evaluation" (DDE) or "Business Requirement Validation" (BRV) are not present in the execution logic.
- **Risk:** Quality control is implicit rather than explicit. There are no hard stops or manual approval steps enforced by the engine, increasing the risk of cascading failures.

### 3. Disconnected Quality Fabric
- **Claim:** "Each phase has test scenarios (quality-fabric)".
- **Reality:** `QualityFabricClient` exists but is a standalone wrapper around an external HTTP service. It is **not called** within the `AutonomousSDLCEngineV3Resumable` execution loop. The engine calculates a rudimentary "quality score" based on file counts and execution time, ignoring actual code quality metrics.
- **Risk:** The "Quality Score" is a vanity metric. A run could generate 100 garbage files and get a high score.

### 4. Template Promotion is a Copy-Paste Job
- **Claim:** "Successful runs generate templates".
- **Reality:** `WorkflowTemplateExtractor` copies files from a workspace and creates a `manifest.yaml`. It does not perform intelligent generalization (e.g., replacing hardcoded project names with variables in the source code). It relies on an external registry service that may not be present.
- **Risk:** Generated templates will contain hardcoded values from the original run, making them poor starting points for new projects without significant manual cleanup.

### 5. "Learning" is Write-Only
- **Claim:** "Capture learning for next execution".
- **Reality:** The system indexes execution results into a RAG writer (`rag.index_workflow_execution`). However, there is no feedback loop where the engine *queries* these specific learnings to adjust its strategy for the *current* or *immediate next* run beyond generic "guidance" retrieval.
- **Risk:** The system accumulates data but doesn't necessarily get smarter. It repeats the same mistakes unless the RAG retrieval logic is highly sophisticated (which is currently just a basic semantic search).

### 6. Fragile Microservice Dependency
- **Observation:** The engine heavily relies on `localhost` services (RAG Reader @ 9801, RAG Writer @ 9802, Quality Fabric @ 8000, Template Registry @ 9600).
- **Critique:** The core logic is tightly coupled to these external HTTP endpoints. If these services are not running (which they don't seem to be managed by the main engine script), the "Autonomous" engine degrades to a simple script runner.
- **Recommendation:** Implement fallback logic or embedded versions of these services for a robust standalone mode.

### Summary
The backend engine is a **solid prototype of a linear task runner** but falls short of the "Autonomous, ML-driven, Self-Healing" platform described in the baseline. The "Intelligence" is largely offloaded to external services that are loosely integrated. To reach the baseline, the **Orchestration Layer** needs to be significantly smarter, integrating Gates and Quality Checks directly into the control flow, rather than treating them as optional sidecars.
