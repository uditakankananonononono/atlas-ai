# A11: SQL-authoritative M20 Chroma semantic consumer

Explicit GCWRuntime semantic_backend=chroma requires PostgreSQL job storage, an explicit persistent Chroma path and stable model_id embedder. Collection identity hashes length-delimited tenant and model identity; tenants/models use different collections, not only filtered results. No default switch or automatic reindex occurs. Existing facts lacking the matching index job/hash/model fail binding. Migrated job table is required.

SQL fact plus pending index job commit together. Chroma is asynchronous, not falsely atomic with SQL. The explicit index worker locks current SQL fact/job, writes latest snapshot, verifies document/metadata/embedding readback, then marks completion. Chroma/network/readback/SQL-mark failure leaves fact durable and job pending. Crash after Chroma write before SQL mark is safe to retry via idempotent upsert; the test kills a real separate interpreter at the mark and retries in another fresh interpreter.

Recall distinguishes absence (empty hits) from pending index (FactIndexPending, HTTP409 status facts_pending_index). Any pending fact makes recall unavailable instead of silently returning an old index. Completed jobs/content/model and full Chroma collection identity/metadata set are checked before candidates hydrate authoritative SQL facts. Missing/extra/stale candidates fail. Semantic quality uses controlled fixture embeddings, not a model benchmark.

The registered atlas.m20.index_chroma_facts task requires an explicit tenant runtime binding in its worker bootstrap. It invokes the runtime's execution-locked index method; no beat schedule, automatic retry, provider/config bootstrap or automatic reindex is installed. New opted-in deployments must bind the same persistent path/provider/model in each intended worker. The actual existing loop uses Chroma semantic.query; fresh-process acceptance proves retrieved fact enters task working memory after durable restart.

## Evidence

227 tests passed across the first eight Chroma consumer checks plus pgvector/M20 memory/runtime regressions. Final scoped rerun also includes fresh-process WM and reversible-migration canaries. Real local PostgreSQL16.2, Chroma PersistentClient, fixture8D normalized provider. Tests pin pending-vs-absent response, index failure fact retention, SQL job failure fact rollback, readback mismatch pending, replacement pending, killed-before-mark retry, missing candidate errors, collection tenant/model separation, no old-fact reindex and explicit worker binding. No production services/data used.

## Boundaries

SQL+Chroma are not one transaction. Locks span Chroma network/disk operations. Pending state blocks all tenant semantic recall, which favors correctness over availability. Full-set validation is unoptimized and no ANN/scalability claim is made. No serializable cross-store query snapshot, signed vector provenance, provider semantic quality, hosted operation, OIDC deployment or malicious privileged-store resistance. Existing facts require a future explicit reindex unit. Downgrading jobs preserves facts but loses indexing state; rebinding then fails until explicitly repaired/reindexed. Chroma collections are not automatically deleted on downgrade. No periodic indexing or recovery scheduler supplied.
