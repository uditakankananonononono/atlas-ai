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
2. Bind production clients into `CognitiveWorkerService(...)`:
   - `executive_model` / `planner_model`: the shared model router (Module 12).
   - `approval_gate`: Module 0's durable center (must satisfy the
     `ApprovalGate` protocol: `request() -> id`, `decision(id)`).
   - `transcriber` (Whisper), `vision` (GPT-4o/CogVLM), `document_parser`.
   - `embedder`: text-embedding-3-large or Ollama bge-large behind the
     `EmbeddingProvider` protocol; default is the offline deterministic one.
   - `sandbox`: SandboxPolicy with the deployment's allowed hosts and the
     per-project filesystem root (network is OFF by default).
3. Persistence: create `GCWRepository(engine)` from the shared
   `ATLAS_DATABASE_URL` engine and call `create_schema()`. Tables are
   `m20_*`-prefixed. The service runs in-memory by default; sync points are
   `save_task` after each state change, `save_episode`/`save_trace` at
   episode close, `save_fact`/`save_skill` on write.
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
  reflections) are protocol-injected; offline they are deterministic
  heuristics. Reasoning quality depends on the bound model.
- `risk_of_ruin_ruin_probability` is the classic gambler's-ruin
  approximation, not a full stochastic model.
- Category 1 judgment rows ship as prompt-chain skill scaffolds; they guide
  the model, they are not standalone algorithms.

## Features-doc rows 10-34 (Executive Function & Meta-Cognition)

`metacognition.py` implements each row as an exact typed capability; routes
are mounted under `/api/modules/20/meta/*`; focused tests are
`tests/modules/test_m20_metacognition.py` (row logic, named test_rowNN_*)
and `tests/modules/test_m20_metacognition_routes.py` (mounted routes).

- Row 10 (recursive self-improvement) is bounded: it rewrites only versioned
  entries in `PromptRegistry`, only after approval through the approval
  gate. `ImprovementLoop.FORBIDDEN_TARGETS` blocks safety/tool/approval
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
