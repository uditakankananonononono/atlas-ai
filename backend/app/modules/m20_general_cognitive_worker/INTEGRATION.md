# Module 20: General Cognitive Worker - integration notes

## What this package is
The GCW (spec section 4): sensory ingestion, working memory + attention,
episodic/semantic/procedural LTM, HTN planning, the deliberative
sense-plan-act loop, tool registry/dispatcher, multitasking scheduler,
reflection (scratchpad/ideation/retrospective/emotion/uncertainty),
constitutional safety with Module 0 approval gating, durable SQL
persistence, and the FastAPI surface.

## Wiring checklist for the integrator
1. `from app.modules.m20_general_cognitive_worker import router, bind_service, CognitiveWorkerService`
   and `app.include_router(router)` (prefix is `/api/modules/20`). Add
   `MODULE_REGISTRY_ENTRY` to the module catalog.
2. Create a separate `CognitiveWorkerService(...)` for each authenticated tenant.
   Bind with `bind_service(service, tenant_id="actual-tenant-id")`. Reusing the
   same mutable service for two tenants is rejected. Unknown tenants fail503;
   no automatic local fallback in authenticated mode. Bind tenant-scoped
   persistence, tools, approval gates and clients too. Binding rejects a shared
   top-level service instance, but cannot detect separate service instances sharing
   a mutable backend store/DB namespace. Integrators must enforce tenant-keyed
   reads/writes and isolation within every backing store and tool client. The default `local`
   binding is only for explicitly opted-in insecure local development.
   Bind production clients into `CognitiveWorkerService(...)`:
   - `executive_model` / `planner_model`: the shared model router (Module 12).
   - `approval_gate`: Module 0's durable center (must satisfy the
     `ApprovalGate` protocol: `request() -> id`, `decision(id)`).
   - `transcriber` (Whisper), `vision` (GPT-4o/CogVLM), `document_parser`.
   - `embedder`: text-embedding-3-large or Ollama bge-large behind the
     `EmbeddingProvider` protocol; default is the offline deterministic one.
   - `sandbox`: SandboxPolicy with the deployment's allowed hosts and the
     per-project filesystem root (network is OFF by default).
3. Persistence is a separate `GCWRuntime` binding, not an automatic
   conversion of `CognitiveWorkerService` stores. Create
   `GCWRepository(engine, tenant_id="actual-tenant-id")`, then `GCWRuntime(repo, ...)`
   and `bind_runtime(runtime)`. Alembic owns production schema changes;
   `create_schema()` is for explicit local tests/development only. Existing
   databases need the Oct7 action-record/task-metadata migrations before this
   runtime. They have local SQLite tests, not a production rollout.
   Normal context persistence writes task, reported action records and traces;
   these are separate commits, not atomic effect receipts. Memory stores write
   through separately. Clean restart is tested, crash-complete or exactly-once
   effects are not. The action journal is unbounded in SQL, but runtime startup no longer hydrates all tenant action payloads. Episode completion reads only that task's retained actions and merges current-run records. Other memory/task hydration remains unbounded.
4. Celery: a beat task calling `service.tick()` runs the time-sliced
   scheduler; a daily task posts `service.standup()` to the Executive
   Dashboard (spec 4.3). Resume waiting tasks from Module 0 webhooks via
   `POST /api/modules/20/tasks/{id}/resume`.
5. ChromaDB swap: `EpisodicMemory`/`SemanticMemory`/`RetrospectiveEngine`
   accept any `EmbeddingProvider`; to back them with Chroma, subclass and
   replace the dict stores - the retrieval contracts are already similarity-
   based.

## Honest boundaries
- LLM-driven steps (de novo planning, attention scoring in production,
  reflections) are protocol-injected. Missing planning/reasoning fails closed;
  no template is substituted as successful reasoning. Candidate ranking,
  attention and idle ordering have explicitly heuristic implementations.
  Configured model routes do not prove model availability/privacy/quality.
  The bounded actual tiny Qwen CPU trial loaded weights and generated text,
  but all sampled planner/executive responses failed intended schema.
- `risk_of_ruin_ruin_probability` is the classic gambler's-ruin
  approximation, not a full stochastic model.
- Category 1 judgment rows ship as prompt-chain skill scaffolds; they guide
  the model, they are not standalone algorithms.

## Features-doc rows 10-34 (Executive Function & Meta-Cognition)

`metacognition.py` exposes typed request/result operators, not proof that
all named cognitive capabilities are implemented at original spec depth. It
mixes supplied-data arithmetic, heuristics, counters and templates; routes
are mounted under `/api/modules/20/meta/*`; focused tests are
`tests/modules/test_m20_metacognition.py` (row logic, named test_rowNN_*)
and `tests/modules/test_m20_metacognition_routes.py` (mounted routes).

- Row 10 (recursive self-improvement) is bounded: it rewrites only versioned
  entries in `PromptRegistry`, only after approval through the approval
  gate. This versions supplied prompt strings, not trained model improvement.
  Review snapshots/locks/consumption are process-local, not durable distributed
  approvals. `ImprovementLoop.FORBIDDEN_TARGETS` blocks safety/tool/approval
  targets. No deployed code is self-modified.
- Row 13 calibration, row 21 world models, row 32 epistemic calendar, and
  row 34 gap counters are in-memory in this package; add `m20_meta_*` tables
  via `GCWRepository` when durability is required.
- Rows 14/15/24-27 reuse the tested operators in `reasoning.py`.
- All engines are deterministic and offline; production model assistance
  (e.g. richer devil's-advocate attacks) should be injected behind new
  protocols without changing the typed contracts.

## Rows 35-59: simulation, forecasting and decision analysis (foresight.py)

- `foresight.py` adds 25 typed engines, instantiated on the service and
  mounted under `/api/modules/20/meta/*`. Engines are deterministic and
  offline; rows 56-59 return an explicit decision-support caveat and never
  make investment-advice claims.
- Serendipity (35) composes with the row-34 curiosity gaps and semantic
  memory; it returns suggestions only - execution still goes through the
  service's normal approval gates.
- Insight capture (36), simulation fidelity (37), hypotheses (38),
  reference-class cases (42), planning history (44) and optimism records
  (45) are in-memory in this lane; a `m20_foresight_*` durability
  follow-up (SQL repository) is the same shape as the earlier meta
  durability note.
- Second-order tracing (49) propagates through an explicit rule table that
  is returned in the response (`rules_used`) so the inference is
  inspectable - no hidden reasoning is captured or stored.
- Systems model (50) and leverage ranking (51) are constructed per request
  from caller-supplied links; nothing persists between calls.
- Risk of ruin (58) uses the closed-form gambler's ruin for even-money
  bets and a seeded Monte Carlo otherwise; the method used is returned.
- Kelly sizing (59) clamps no-edge positions to zero and recommends a
  fractional, capped size by default.

## Rows 60-84: strategic and quantitative decision aids (strategy.py)

- `strategy.py` adds 25 typed engines over the runtime; 24 are
  instantiated on the service and mounted under `/api/modules/20/meta/*`
  (SystemsModel continues to be built per request; the TOC manager keeps
  snapshot history for bottleneck-migration reporting).
- Rows 72-75, 77 and 80 reuse the existing computable operators in
  `reasoning.py` (littles_law, critical_path, monte_carlo_simulation,
  sensitivity_analysis, evaluate_decision_tree, nash_equilibria_2x2)
  rather than re-implementing them; row 64 builds on the row-50
  SystemsModel.
- Rows 75/76 evaluate caller-supplied model expressions through a
  whitelisted AST evaluator: arithmetic over named parameters only - no
  imports, calls, or attribute access; anything else is rejected with 422.
- Valuation-shaped rows (63, 65, 66, 68, 78, 79, 80, 82, 84) return an
  explicit decision-support caveat; none claim business certainty.
- Mechanism design (81) now solves bounded unit-demand assignment for
  up to64agents/items and recomputes externality payments on optimal
  leave-one-out assignments. Missing/zero valuations may stay unallocated.
  Float arithmetic/tie behavior and nonnegative finite valuation bounds are
  explicit.96 small reported-valuation fixtures match independent exhaustive
  assignment/externality enumeration. This is not general combinatorial
  mechanism design or empirical incentive/truthfulness verification.
- Row 70 is the ongoing TOC management loop (release pacing, WIP cap,
  migration), distinct from row 52's one-shot bottleneck analysis.

## Current binding deployment boundary

Production does not auto-provision per-tenant service/runtime bindings. An
integrator must bind each authenticated tenant and its tenant-keyed stores;
unbound real tenants return503. The initial local runtime is development-only.
The reserved tenant name local is rejected for authenticated GCW access, even
with a valid OIDC token. A configured temporary multi-tenant test is not evidence
that this deployment integration is live.

### Supplied hypothesis ranking scope correction

Row38's independent binary odds updates followed by normalization are a
ranking heuristic, not categorical Bayesian inference. The fixed retirement
threshold does not prove a hypothesis false. Supplied statements, priors and
likelihood ratios are not discovered or independently verified. The API now
states this scope. Validation of a complete update batch precedes local
mutation, and row39's binary update uses finite log odds with absorbing0/1
boundaries. This repairs arithmetic/validation only, not full row38 cognition.

###2x2 Nash scope correction

Row80 enumerates pure equilibria and computes a nondegenerate interior
candidate from supplied2x2 matrices. It does not enumerate degenerate mixed
families or establish stability, general-game equilibria or actual opponent
behavior. Both matrices now require finite numeric payoffs; player scaling
avoids direct overflow, but rounding may still omit ill-conditioned candidates.

### Retraction: row40 causal assessment

Historical labels "causal_supported", "plausible_unproven" and
"correlational_only" came from caller flags, not data or effect analysis.
The route now always says unverified/causality_verifiedfalse and reports only
checklist coverage. Even all flags true require actual study/data/design and
effect/uncertainty inspection. This is not implemented causal assessment or
correlation analysis; the original feature remains incomplete.

### Row57 expectation semantics correction

Historical expectation normalized incomplete mass and sensitivity renormalized
an added weight, overstating both. Now sum(p*v), missing mass explicitly
zero-valued; one first-best index shifts up to10pp with other mass proportional.
A certain selected outcome's shifted-away mass is assigned zero. This convention
is not an empirical fact about omitted outcomes. Caller probabilities/values
remain unverified and no actual financial decision is taken.

## Optional pgvector semantic recall

Bind `GCWRuntime(repo, semantic_backend="pgvector", embedder=provider)` with an explicit 1024D synchronous EmbeddingProvider and stable `provider.model_id`. PostgreSQL, vector extension and migrated memory_embeddings must exist. Fact and vector writes commit atomically. Existing unindexed facts or a changed model ID require explicit reindexing before binding; no automatic rewriting or silent fallback occurs. The default SQL-backed semantic memory is unchanged. Runtime memory POST/recall routes use the bound authenticated tenant, not a body tenant. The loop now consumes database-ranked semantic recall when opted in. Local real-PG tests cover recall entering working memory and vector-error rollback, not deployed auth, model quality, ANN/index performance or concurrent cache coherence.

## Optional checkpoint event outbox

After applying the additive 20261008_m20_event_outbox migration, bind a PostgreSQL GCWRepository with enable_event_outbox=True. ATLAS_M20_EVENT_OUTBOX=1 opts the explicit local binding and registered drain task in; authenticated production tenants still need explicit runtime binding. Each save_execution transaction records minimal IDs/state, never memory/goal/action bodies. Invoke atlas.m20.drain_runtime_events explicitly or supply a separately reviewed scheduler; no beat entry is installed. Redis delivery is at-least-once: recipients must deduplicate event_id. Failed delivery leaves the SQL row pending. The principal-scoped events route reads SQL metadata, not a deployment of a Redis subscriber. No consumer groups, retention, cursor feed, external notifications or production operation are claimed.

M16's explicit consume_m20_status task is the first internal subscriber. It verifies Redis refresh signals against SQL outbox authority, deduplicates per consumer/tenant/event ID and projects current SQL task state/action IDs. The read-only M16 task-status endpoint is tenant-scoped. It has no automatic scheduling or poison retry. Invalid events stop with unchanged cursor; an authorized operator must inspect and repair the exact stream entry before rerunning. Projection is current at last unique-event consumption, not guaranteed continuously current. No stream-trimming recovery or retention policy is supplied.
