# Module 16 integration

Provides a durable tenant-scoped executive snapshot, event cursor API plus resumable SSE live feed, consolidated approval review, and preview-first natural-language command bar. Read-only commands may execute once; mutations only create approval requests. Command previews expire and cannot be replayed. `critical_path` detects cycles and calculates the duration-weighted dependency path for the Gantt UI.

The host event bus should call `append_event` and update the materialized snapshot transactionally. SSE works now and is proxy-safe; a Redis-backed broadcaster can add WebSockets across replicas without changing the cursor/event contract. Register `spec` and mark catalog item 16 implemented.

Planning & measurement entities (feature rows 388-399, this batch):

- Durable tenant-bound tables: m16_work_items, m16_sprints, m16_ceremonies, m16_retrospectives, m16_experiments, m16_roadmaps (created via the existing Base.metadata.create_all; no shared edits needed).
- Routes mount under /executive-dashboard/planning/* (nested router included by the module router; integrator adds only the global /api/v1 prefix as usual). No new shared dependencies: statistics use math.erf and an in-module incomplete-gamma (no scipy).
- planning.py is pure domain logic; computed claims (prioritization scores, velocity, burndown, significance) always return their inputs and assumptions. Statistics are fixed-horizon frequentist: two-proportion z-test for A/B, chi-square homogeneity for multivariate, minimum-sample guards returning not-significant with reasons.
- Frontend views: frontend/components/PlanningBoard.tsx + executive-dashboard/planning-api.ts.

## Feature rows 1010-1034: tenant-bound analysis jobs
- `analysis.py`: bounded pure reference analytics (stdlib only; seeded RNG; no scipy/numpy). One method per row: predictive (OLS forecast), prescriptive (option ranking), descriptive, diagnostic (Pearson, no-causation caveat), EDA, confirmatory + hypothesis tests (normal approx), inference + confidence intervals, bootstrap percentile CI, permutation test, Mann-Whitney (normal approx), robust (median/MAD/trimmed mean), IQR outlier detection, mean imputation, multiple imputation (normal-draw, capped 20 datasets), normal MLE, 2-component Gaussian-mixture EM, random-walk Metropolis MCMC/MH, conjugate normal variational reference, Gibbs (mean+precision), 1D educational HMC, bootstrap particle filter (SMC + particle_filter). Every result carries inputs, assumptions, method_limits; draw caps enforced.
- `m16_analysis_jobs` table: tenant-scoped durable job records (status completed/failed, output JSON or error, seed, created/completed).
- Routes: `GET /executive-dashboard/analysis/methods` (25-method catalog), `POST /executive-dashboard/analysis/jobs` (201; 422 unknown method; validation failures stored as failed jobs), `GET /executive-dashboard/analysis/jobs[?method=]`, `GET /executive-dashboard/analysis/jobs/{id}` (404 cross-tenant).
- Frontend: `frontend/components/AnalysisPanel.tsx` + `frontend/components/executive-dashboard/analysis-api.ts` (method picker, JSON data/params entry, seed, result with assumptions/limits, recent-jobs table).
- Tests: `tests/modules/test_m16_analysis_1010_1034.py` (row-named 1010-1034 + persistence/catalog/failure/determinism/tenant-isolation; tenant isolation via real SqlDashboardRepository on sqlite).
