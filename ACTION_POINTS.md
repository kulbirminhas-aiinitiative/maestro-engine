# Action Points — Maestro Engine Baseline Alignment
Timestamp: 2025-11-27T19:08:43.882Z

P0 (Implement first)
- ML Routing Policy: add BFF policy_service with /api/policy/route; log reason codes; wire FE quick-run toggle.
- Gate Framework: add /api/gates endpoints; enforce DDE/BRV/ACC per phase; broadcast ws:gates:update.
- Success Scoring: add scoring_service; expose /api/scores and ws:score:update; persist per phase/persona/team.

P1
- Quality-Fabric Enforcement: map phases→tests; block gates on failing thresholds; enable QF in staging/prod.
- Learning Snapshots: generate post-run artifacts; ingest into RAG with provenance; expose retrieval citations.
- Template Promotion: implement /api/templates/promote; criteria; governance approvals; semver.

P2
- Deployment Verification Gates: smoke/health checks + rollback rules.
- Team Enhancement Rationale: produce team_enhancement_report with override/lock.
- Requirement Schema Contract: versioned schema + validators; CI check.
- SLOs & Queue Policies: job classes, latency targets, dashboards.

Reference scripts
- quality-fabric/scripts/run_phase_tests.sh — phase test run + gate evaluate.
- quality-fabric/scripts/promote_template.py — promotion request example.
- quality-fabric/scripts/route_decision_example.py — routing decision call.
- maestro-templates/scripts/promote_from_output.py — promote artifact as template.
- maestro-templates/scripts/validate_template.py — trigger QF validation.
- maestro-templates/scripts/recommend_templates.py — get template recommendations.

Next steps
- Approve P0 epics in docs/EPICS_BACKLOG.md and schedule Wave 1.
- Enable feature flags in non-prod; start dry-run gates and passive scoring.
- Create dashboards for gates, routing, and scores.
