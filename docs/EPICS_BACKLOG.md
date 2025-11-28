# Maestro Engine v3.0 — EPICs and Backlog (import-friendly)

Created: 2025-11-27T19:08:43.882Z
Owner: Maestro Platform Engineering
Labels: maestro-v3, baseline-alignment, quality-loop

Note: Each EPIC lists suggested child stories and concrete acceptance criteria. Use these as seeds for Jira imports.

EPIC-1: ML Routing Policy Service (Front vs Back execution)
- Summary: Decide and explain where a request runs (FE/BFF quick-run vs Backend long-run) using policy + ML signals.
- Business Value: Faster perceived latency for lightweight tasks; backend capacity savings (10–20%).
- Scope: Policy endpoint (BFF), feature flag, telemetry schema, decision reasons, fallback rules; FE quick-run toggle & quotas.
- Out of Scope: Training pipelines beyond baseline heuristic; FE sandbox executor implementation depth (stub only).
- Acceptance Criteria:
  1) POST /api/policy/route returns {locus: fe|backend, reason_code, features} in <50ms p50, <150ms p95.
  2) Decisions logged with request_id; WS event ws:routing:decision emitted.
  3) Override header X-Route-Locus respected; audit recorded.
- Metrics: Routing precision ≥85%; backend queue reduction ≥10% on pilot workloads.
- Dependencies: None (can ship alongside gates).
- Estimate: 2–3 weeks.
- Child Stories: policy endpoint; FE/BFF integration; telemetry; override; dashboards.

EPIC-2: Gate Framework (DDE/BRV/ACC) with Enforcement
- Summary: Introduce Design Decision Evidence (DDE), Business Review (BRV), Acceptance Criteria (ACC) gates per phase.
- Business Value: Reduce rework; increase predictability; compliance.
- Scope: Gate contracts, storage, APIs (/api/gates), WS updates, UI badges; per-template checklists; dry-run mode.
- Acceptance Criteria:
  1) Gates computed and stored per phase with status open/passed/failed and evidence URIs.
  2) Mixed-mode execution halts on failed mandatory gate unless override granted.
  3) WS updates broadcast gate changes; audit trail persists.
- Metrics: −30% gate-related failures; ≥90% gate evidence completeness.
- Dependencies: EPIC-4 (tests), EPIC-3 (scores) optional.
- Estimate: 3–4 weeks.
- Child Stories: contracts; persistence; APIs; WS; UI integration; dry-run; audits.

EPIC-3: Success Scoring Service (Phase/Persona/Team)
- Summary: Compute normalized scores per phase/persona/team with reasons and gaps, published to status APIs and WS.
- Business Value: Visibility and learnings; prioritization; automated improvements.
- Scope: scoring_service, schema, thresholds, manifest embedding, dashboards.
- Acceptance Criteria:
  1) Scores available in /api/workflow/status and ws:score:update with reasons.
  2) Scores persisted with session_id, persona, phase; queryable for trend charts.
  3) Configurable weights; default template provided.
- Metrics: +20% next-loop score uplift within 60 days.
- Dependencies: EPIC-2 (objects to score) helpful.
- Estimate: 2 weeks.
- Child Stories: model & weights; API/WS; persistence; dashboards.

EPIC-4: Quality-Fabric Enforcement & Phase Test Mapping
- Summary: Map phases→tests; enforce test results as gate inputs.
- Business Value: Early defect detection; consistent quality.
- Scope: quality_fabric integration on-by-default (staging/prod), mapping config, pass/fail thresholds.
- Acceptance Criteria:
  1) Each phase has at least one mapped test scenario; results tie to gates.
  2) Failing tests block gate unless waiver present; artifacts linked.
  3) Configurable thresholds (coverage, static analysis score) enforced.
- Metrics: −25% post-integration defects.
- Dependencies: EPIC-2.
- Estimate: 2–3 weeks.
- Child Stories: mapping config; runner integration; result ingestion; gate wiring.

EPIC-5: Learning Snapshot & RAG Ingestion Pipeline
- Summary: Generate post-run learning snapshots and ingest with provenance into RAG.
- Business Value: Improves reuse; speeds next runs; reduces duplicate work.
- Scope: learning_snapshot artifacts, vectorization, ingestion (vector_rag_manager), provenance & TTL.
- Acceptance Criteria:
  1) Snapshot JSON/MD produced per run covering decisions, scores, defects, templates used.
  2) Ingestion writes embeddings with metadata (session_id, persona, phase, version).
  3) RAG retrieval shows citations in agent outputs.
- Metrics: +15% suggestion accuracy; reduced time-to-first-correct-template.
- Dependencies: EPIC-3.
- Estimate: 2 weeks.
- Child Stories: artifact generator; ingestion; provenance; retrieval citations.

EPIC-6: Template Promotion Pipeline (Maestro-Templates)
- Summary: Automate promotion of high-quality outputs to template registry with governance.
- Business Value: Codifies best practices; scales quality.
- Scope: criteria (score thresholds, test pass), approvals, versioning, POST /api/templates/promote, scripts.
- Acceptance Criteria:
  1) Promotion requests validate criteria and record approvals.
  2) Templates published with semver and changelog.
  3) Auto-suggestion prefers promoted templates next loop.
- Metrics: ≥25% of runs use promoted templates within 90 days.
- Dependencies: EPIC-3, EPIC-4, EPIC-5.
- Estimate: 3 weeks.
- Child Stories: criteria; approvals; versioning; API; CLI/script wiring.

EPIC-7: Deployment Verification & Rollback Gates
- Summary: Post-deploy smoke tests, health checks, and rollback rules as enforceable gates.
- Business Value: Reduce production incidents; faster recovery.
- Scope: define checks, environment targets, rollback criteria, gate wiring.
- Acceptance Criteria:
  1) Deploy phase emits verification results; failure triggers rollback guideline.
  2) Gate passes only when checks succeed within SLO windows.
  3) Evidence stored and visible in status/WS.
- Metrics: −40% failed post-deploy incidents.
- Dependencies: EPIC-2, EPIC-4.
- Estimate: 2 weeks.
- Child Stories: check runners; gate integration; evidence persistence.

EPIC-8: Team Enhancement Rationale & Override
- Summary: Capture why backend adds personas; allow user lock/override with audit.
- Business Value: Transparency; control; governance.
- Scope: team_enhancement_report artifact; override flags; audits.
- Acceptance Criteria:
  1) Persona additions include rationale and confidence.
  2) Users can lock base team; backend respects lock.
  3) Audit logs include before/after diffs.
- Metrics: Improved trust (+20% satisfaction).
- Dependencies: None.
- Estimate: 1–2 weeks.
- Child Stories: artifact; lock flag; audits; UI badge.

EPIC-9: Requirement Schema Contract & Validation
- Summary: Versioned requirement schema shared across FE/BFF/BE.
- Business Value: Fewer integration errors; clearer contracts.
- Scope: schema repo/module, validators, compatibility matrix, CI check.
- Acceptance Criteria:
  1) Schemas versioned; incompatible changes blocked without migration notes.
  2) Validation errors returned with actionable messages.
  3) Contract doc published; examples covered by tests.
- Metrics: −50% schema-related defects.
- Dependencies: None.
- Estimate: 1–2 weeks.
- Child Stories: schema; validators; CI; docs; examples.

EPIC-10: SLOs, Queue Policies & Observability
- Summary: Define job classes, priorities, retries, SLAs; dashboards and alerts.
- Business Value: Predictability; reliability.
- Scope: policy docs, config, metrics, dashboards (latency, queue depth, failures), alerts.
- Acceptance Criteria:
  1) Job classes documented and enforced via config.
  2) Dashboards show p50/p95/p99 latencies and success rates by class.
  3) Alerts on SLO breaches with runbook links.
- Metrics: SLO attainment ≥95%.
- Dependencies: None.
- Estimate: 2 weeks.
- Child Stories: policy; metrics wiring; dashboards; alerts; runbooks.

Jira field recommendations (per Epic)
- Issue Type: Epic
- Epic Name: <as above>
- Components: backend, bff, orchestration, rag, quality, devops
- Labels: maestro-v3, baseline, gates, routing, scoring, templates
- Priority: P0/P1/P2 (aligns with roadmap)
- Target Start/End: per roadmap
- Stakeholders: Product, Architecture, Security
- Feature Flag: yes for EPIC-1..6

Rollout plan (all epics)
- Stage: dry-run gates, shadow ML routing, passive scoring
- Beta: enforce gates on staging; opt-in prod for selected teams
- GA: enforce gates; routing on by default with override; promotion enabled with governance

Success criteria (portfolio level)
- ≥20% cycle-time improvement by sprint 4
- ≥30% reduction in failed runs from gate/test issues
- ≥25% template reuse rate with promoted templates
