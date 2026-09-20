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
