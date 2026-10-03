# Module 9 integration

The graph is a real tenant-scoped SQL adjacency list. Node creation computes an embedding through an injected provider and proposes similarity and NER links; it never silently accepts a link. Hierarchical and dependency relationships reject cycles. Optimistic versions prevent lost edits. Audit rows record graph mutations. `/planner-context` exports bounded graph context without exposing another tenant.

The old silent no-op default has been removed. The production `get_service` uses the free in-process M09 runtime on writes. Install `pip install -e '.[m09-local]'` (Python >=3.12). First embedding use downloads public model weights; spaCy weights are installed by the extra. No account or API key is required. Subsequent inference runs locally on CPU. Read-only graph paths do not load models.

M09 owns these settings independently of core OpenAI/Ollama defaults:
- `ATLAS_M09_EMBEDDING_PROVIDER=fastembed` (the only supported provider here)
- `ATLAS_M09_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5`
- `ATLAS_M09_SPACY_MODEL=en_core_web_sm` (only the allowlisted package 3.8.0 with matching full-pipeline and NER weight hashes is accepted; arbitrary paths/models are rejected)
- `ATLAS_M09_MODEL_CACHE` (optional writable model cache)
- `ATLAS_M09_CPU_THREADS=2` (1-32)

`GET /knowledge-workspace/nlp-status` loads the runtime and returns model identities, vector dimension, artifact hashes and limits, or HTTP 503. Node create/update returns 503 if models are missing, load fails, vectors are invalid or inference fails. Both embedding and entity inference finish before the node is saved; there is no token/hash/empty fallback. Node, audit and suggestion writes share one SQL transaction. A storage exception rolls back all of them.

`metadata._atlas_m09_nlp` is server-owned and overwritten at each node write. Similarity requires equal identity, including ONNX/tokenizer hashes, version and dimension. Legacy/unversioned or differently embedded nodes are skipped and counted in the new node's metadata; update them to regenerate embeddings. This is conservative compatibility, not automatic migration. Vector validity is checked before comparison. Suggestions remain pending until explicit review. `related_to` uses the existing 0.78 cosine threshold, unchanged and not calibrated as a probability. `mentions` means a trained NER span exactly matches another node title, case-insensitively; its score 1.0 is an exact-match indicator, not NER confidence. Duplicate titles may generate multiple suggestions.

Limits: English-only small models, 512-token embedding truncation, NER misses/mislabels, exact-title-only mentions, first 500 repository nodes, and existing optimistic-update/concurrency behavior. This repair does not verify semantic/paraphrase accuracy, add ANN search, train a model, or certify all of M09. PostgreSQL/Windows/owner-PC validation is separate. Core embeddings and M25 are not changed to this runtime; M25's default is now explicitly labelled 16-bin SHA-256 token hashing plus lexical overlap, not learned semantic retrieval.

Frontend dependency: `@xyflow/react`. The included component uses the actual React Flow canvas, MiniMap, controls, type filters and double-click selection.

## Contradiction-revision actor keys (governed)
Routes under `/knowledge-workspace/contradiction-revisions/keys`:
- `POST /keys` `{public_key_b64, proof_signature_b64, actor_id?}` enrolls a key. The caller must be that actor or an `atlas-admin`. `proof_signature_b64` is the new key's Ed25519 signature over `enrollment_statement(tenant, actor, key_id)` (canonical JSON, purpose `atlas-m09-actor-key-enrollment`; `key_id` = first 32 hex of SHA-256 of the raw key). A second key while one is active returns 409, so use rotate.
- `POST /keys/rotate` `{new_public_key_b64, proof_signature_b64, endorsement_signature_b64?, actor_id?, reason?}`: the current key signs `rotation_statement(tenant, actor, old_key_id, new_key_id)`. Without an endorsement, only an admin may rotate, and that is recorded as `recovery`.
- `POST /keys/{key_id}/retire` `{reason, effective_from?, actor_id?}`: `effective_from` defaults to now. Set it earlier if the key may have leaked; it is clamped to between enrollment and now. Retiring again can only move the time earlier.
- `GET /keys?actor_id=` and `GET /keys/events?actor_id=`: key list and the append-only event log (enrolled, retired, refused attempts, effective_from moves).

Rules: a retired key never signs a new revision. If all of an actor's keys are retired, signing is still required, so they must enroll a new key. When `GET /chain` re-checks history, each revision shows a `signature_status`: `active_key`, `retired_key_stored_before_cutoff`, `retired_key_after_cutoff` (listed as a problem, so the chain is not valid), `invalid` or `unsigned`. The before/after decision uses the server-set `stored_at` on the revision row. That is database time, not a trusted third-party timestamp, so someone who can write the database directly could move it. Keys enrolled before governance keep working and are marked `enrolled_by = legacy-no-proof`.

## Stored source bytes
`POST /verify-sources` now keeps every fetched source whose SHA-256 equals the captured snapshot hash. They go in `m09_source_blobs`: tenant-scoped, keyed by hash, written once, never updated, 20 MB cap. Bytes that don't match are never stored. If a URL is unreachable or not supplied, the source is checked against the stored copy, which is re-hashed on every read: status `stored_match`, with `live_status` and the `stored_copy` metadata (`first_uri`, `stored_at`). `all_match` still means every source matched live. `all_verified` also counts `stored_match`. On a live `mismatch`, the stored copy is reported alongside so you can see what changed. `GET /source-bytes/{sha256}` downloads the stored bytes. If the stored copy was altered in the database it returns 409, and verify-sources reports `corrupt`.


## Graph mutation safety repair

SQL updates include the expected version in the UPDATE predicate and require exactly one affected row. SQLite graph mutations use BEGIN IMMEDIATE; PostgreSQL uses a per-tenant transaction advisory lock (coded, not run in this acceptance). Model inference happens before opening the write transaction. Node persistence, audit and proposals commit together or roll back together. Suggestions capture both endpoint versions in their reasons. Every node update invalidates pending proposals touching either endpoint. Regenerated proposals receive a new ID; the old approval cannot accept a replacement. A target version changed during pre-write inference causes that candidate to be skipped, not saved.

SQL review checks pending status and both versions inside the same graph mutation transaction, then commits edge+audit+review together. Stale, legacy-unversioned, already-reviewed or duplicate-edge proposals return HTTP 409. Rejection is also version-bound. Previously accepted edges are explicit user decisions and are not automatically removed after node edits. These protections cover the SQL-backed API paths; injected in-memory adapters are contract-test conveniences, not production transaction guarantees. Direct database edits or clients bypassing these paths are outside these guarantees. Cycle checks for manual structural edge creation remain the prior behavior, not concurrency-certified by this repair.
