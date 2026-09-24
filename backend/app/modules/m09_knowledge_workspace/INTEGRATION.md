# Module 9 integration

The graph is a real tenant-scoped SQL adjacency list. Node creation computes an embedding through an injected provider and proposes similarity and NER links; it never silently accepts a link. Hierarchical and dependency relationships reject cycles. Optimistic versions prevent lost edits. Audit rows record graph mutations. `/planner-context` exports bounded graph context without exposing another tenant.

For production, inject Atlas's embedding and NER services in `get_service`; the offline default intentionally produces no speculative links. PostgreSQL can later add a pgvector HNSW column/index without changing the service boundary. Register `spec` in `modules/registry.py` and mark catalog item 9 implemented.

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
