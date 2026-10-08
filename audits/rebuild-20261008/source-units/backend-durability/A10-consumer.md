# A10: M20 pgvector semantic recall consumer

## Design and implementation

`GCWRuntime(..., semantic_backend="pgvector", embedder=provider)` explicitly binds the new PgVectorSemanticMemory. The default remains `sql`, unchanged. Binding requires PostgreSQL, installed vector extension/table, an explicit finite nonzero 1024D embedder with stable `model_id`, and correctly indexed existing facts. Unknown backend, missing infrastructure or unindexed/model-mismatched existing facts fail loudly. No mid-run fallback. Existing facts require an explicit future reindex workflow; this increment does not rewrite them on startup.

SQL FactRow remains the authority. `save_fact_with_embedding` writes the fact and MemoryEmbeddingRow snapshot in the same SQL transaction. Vector failures roll back new facts and replacements. Only after commit does the memory object update its local fact view. Tenant + reserved M20 namespace + stable tenant/fact-derived vector identity scope the snapshot. Content hash and model ID guard divergence. Query uses SQL cosine ordering over deterministic vector IDs and hydrates authoritative FactRow and returns authoritative provenance/confidence. It does not read vector-row text as fact authority.

The existing DeliberativeLoop semantic.query path is the actual consumer. Mounted memory POST/recall routes use the authenticated runtime dependency and accept no tenant selector. Added GCWRuntime methods use its existing execution lock. Routes reject unknown body fields and bound content/recall limits. Tests override the authenticated-principal dependency with explicit tenant principals, not a deployed OIDC provider.

## Acceptance

`PYTHONPATH=backend python -m pytest tests/modules/test_m20_pgvector_consumer.py tests/modules/test_m20_runtime_depth.py tests/modules/test_m20_long_term_memory.py`

Initial observed: 218 passed on local PostgreSQL 16.2 / vector 0.6.2 and existing regression fixtures. Real-PG journey stores a fact, reconstructs the runtime, submits a goal through the actual loop and checks that retrieved fact enters task-partition working memory and its persisted chunks, while the second tenant's canary does not. Other checks pin rollback of new/updated facts, finite-float64 extreme normalization and invalid-vector rollback, missing table/extension, unsupported backend/provider, changed embedding model, direct authoritative-content divergence, principal-scoped route writes/recall and cross-tenant ID overwrite refusal.

## Boundaries

No ANN index or quality/performance claim. Controlled fixture embeddings, not model-backed semantic quality. No hosted deployment, Supabase, production auth, crash-recovery, distributed concurrent cache coherence or Chroma consumer claim. Model ID is integrator-supplied; integration must change it when model/version/preprocessing changes. Local dict state used for get/link is not a distributed cache; query's facts come from SQL. No automatic tenant binding or infrastructure provisioning. SQL's existing memory_embeddings migration already creates the table; no schema change in this unit.


## Review repair

Independent review found float64-underflow to a zero float32 vector and an extra-vector-row duplicate loophole. The repaired embedding path scale-normalizes before float32 conversion and checks the resulting vector. Query rejects nonfinite scores and checks the entire tenant namespace's deterministic ID set, fact hashes and model IDs before ranking only those deterministic IDs. Missing/extra rows fail instead of silently changing recall. This full-set validation is deliberately unoptimized and is not an ANN/performance claim. Regression tests cover 1e-100 and 1e100 normalization, rejected zero-vector replacement, extra arbitrary-ID duplicates, and post-binding deleted vector rows. Real-PG consumer tests: 9 passed. Follow-up combined regression result is in the review report.
