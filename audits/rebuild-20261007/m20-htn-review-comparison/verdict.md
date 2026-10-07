# HTN reviewed-payload activation TOCTOU

Original canary failed: runtime A reviewed its cached method, runtime B replaced the durable method payload under the same id, then A activated B's unreviewed replacement. Runtime instance locking cannot prevent this cross-instance stale-cache case.

Fix: activation passes the expected reviewed hash into the repository. The repository hashes the current durable payload before activation and rejects a mismatch. The UPDATE itself also predicates on the exact serialized JSON snapshot, so a payload change between the read/check and UPDATE causes a revision conflict instead of activation. Status and payload review status update together. Failure never publishes active status in runtime memory.

Two new canaries pass: actual separate-runtime replacement before activation; injected replacement between repository read/hash check and guarded UPDATE. SQLite local CAS is verified. This is not proof of multi-writer PostgreSQL behavior; JSON serialization/cast equality and concurrent transaction behavior require PostgreSQL testing. No published Alembic revision changed.

Affected runtime suite: 199 passed, 0 failed before the second injected race canary was added. Both dedicated CAS canaries pass. Fresh full regression receipts are in this directory; final totals must be read from its summary rather than inferred here.
