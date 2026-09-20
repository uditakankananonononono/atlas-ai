# Module 16 integration

Provides a durable tenant-scoped executive snapshot, event cursor API plus resumable SSE live feed, consolidated approval review, and preview-first natural-language command bar. Read-only commands may execute once; mutations only create approval requests. Command previews expire and cannot be replayed. `critical_path` detects cycles and calculates the duration-weighted dependency path for the Gantt UI.

The host event bus should call `append_event` and update the materialized snapshot transactionally. SSE works now and is proxy-safe; a Redis-backed broadcaster can add WebSockets across replicas without changing the cursor/event contract. Register `spec` and mark catalog item 16 implemented.

Planning & measurement entities (feature rows 388-399, this batch):

- Durable tenant-bound tables: m16_work_items, m16_sprints, m16_ceremonies, m16_retrospectives, m16_experiments, m16_roadmaps (created via the existing Base.metadata.create_all; no shared edits needed).
- Routes mount under /executive-dashboard/planning/* (nested router included by the module router; integrator adds only the global /api/v1 prefix as usual). No new shared dependencies: statistics use math.erf and an in-module incomplete-gamma (no scipy).
- planning.py is pure domain logic; computed claims (prioritization scores, velocity, burndown, significance) always return their inputs and assumptions. Statistics are fixed-horizon frequentist: two-proportion z-test for A/B, chi-square homogeneity for multivariate, minimum-sample guards returning not-significant with reasons.
- Frontend views: frontend/components/PlanningBoard.tsx + executive-dashboard/planning-api.ts.
