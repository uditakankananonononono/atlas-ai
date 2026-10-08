# A12: M20 SQL checkpoint outbox and Redis Streams delivery

## Product path

Opt-in `GCWRepository(..., enable_event_outbox=True)` adds a minimal task-state checkpoint event in the same transaction as `save_execution`'s task/action/trace writes. Production/local binding explicitly reads ATLAS_M20_EVENT_OUTBOX; without it the behavior stays unchanged. Enabled binding fails if PostgreSQL or the migrated outbox table is absent. Task creation before an execution checkpoint is not itself an event.

Event identity is SHA256 of tenant ID, task ID, task state and sorted unique action IDs. Replaying that same logical checkpoint has the same ID and one SQL row; state/action changes get a distinct ID. Repeated equal-state checkpoints with no new actions intentionally coalesce, not a separate tick stream. Event payload is exactly event_id, tenant_id, task_id, state, action_ids. It excludes goal, memory text, action arguments/results, traces and provider output. Tests pin the exact key set.

The registered `atlas.m20.drain_runtime_events` Celery task requires explicit ATLAS_M20_EVENT_OUTBOX=1, uses the product engine and RedisStreamBus, and publishes to a tenant-hashed internal stream. It has no automatic beat schedule. PostgreSQL row locks with SKIP LOCKED avoid two drainers publishing the same pending row at once. Redis publish occurs before SQL delivered mark, so a crash or failed SQL mark can cause duplicates with the same event_id. This is at-least-once, not exactly-once. Receiver code must deduplicate by event_id. The authenticated `/runtime/events` route reads only its bound tenant's SQL notifications; no arbitrary stream selector or external notification is exposed.

Additive Alembic migration creates only m20_runtime_event_outbox and tenant index; downgrade removes only that new table/index. It is mechanically reversible, but downgrading deletes its event history and should not be done during active delivery.

## Acceptance

`PYTHONPATH=backend ATLAS_ACCEPTANCE_REDIS_URL=redis://127.0.0.1:16412/0 python -m pytest tests/modules/test_m20_event_outbox.py tests/modules/test_m20_pgvector_consumer.py tests/modules/test_m20_runtime_depth.py tests/test_workers.py tests/test_worker_module_tasks.py`

Observed 208 passed. Real PostgreSQL16.2, source-built Redis8.10.2: actual runtime goal checkpoint creates event, replay dedups, event-write failure rolls back task state, unavailable transport leaves pending, publish-success/SQL-mark-failure retry duplicates same event ID, subsequent drain empty. Exact payload keys/absence of private canary text pinned. Concurrent SQL drainers show skip-locked single publish. Tenant-principal seam route is isolated. Migration upgrade/downgrade/re-upgrade preserves unrelated canary table. Local temporary Redis/server processes stopped. Task registry regression passes; the integration test calls drain_events directly, not a Celery scheduler journey.

## Boundaries

No deployed service consumer, automatic drain scheduling, Redis consumer groups/acks/retention, delivery retry scheduler, production auth, hosted service or throughput claim. SQL event route orders by ID with bounded results, not a full cursor-based history feed. Outbox history is unbounded; this increment adds no purge/retention policy. Atomicity covers SQL checkpoint/event only, not external task effects or Redis delivery. Redis stream maxlen behavior belongs to the existing adapter; delayed recipients may miss trimmed messages. Privileged drain can see all tenants' minimal metadata; public route stays tenant-scoped. No claim that all M20 state mutation methods emit events, only save_execution checkpoints. Opt-in does not automatically bind authenticated production tenants.
