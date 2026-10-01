# Effect ledger (reserve before invoke)

Non-READ tools in the M20 dispatcher are reserved in `m20_effect_ledger` (tenant-scoped, transactional) and marked
`invoking` before the handler runs. Effect identity = sha256(tenant, task, node, tool, canonical args, ignoring only the exact
`_expectation_claim_id` runtime bookkeeping key); same key with different args is refused. Crash after `invoking` and before the receipt => `indeterminate`:
never auto-retried, task goes BLOCKED, human calls `GCWRuntime.reconcile_effect(...)`. Retry exceptions no longer re-invoke;
handler-raised `ToolError` and `ApprovalPending` after mark-invoking are also indeterminate;
only `ToolNotExecuted` (provable no-effect) or `ToolSpec.provider_idempotent=True` allow retry.

Limits: not exactly-once across remote systems. A crash after `invoking` but before the real effect is indistinguishable
from after it, so it is also indeterminate (conservative). Liveness = lease (timeout+30s) plus same-host PID check
(PID reuse possible). A bare `ToolDispatcher()` gets a process-local in-memory ledger (not durable); `GCWRuntime` binds the
durable one. `service.py`'s own dispatcher uses that in-memory default (not changed). SQLite file DB tested only; Postgres untested.
The plan is now checkpointed after planning and after every step so node ids are stable across restarts.

`reconcile_effect` can be called directly after a crash: the ledger classifies a dead/expired
invocation using the same owner/PID/lease rule as reserve before applying the operator decision.
A live unexpired invocation and a reserved (not invoked) effect cannot be reconciled.
Effect hashing excludes `_expectation_claim_id` centrally for both dispatch and reconciliation;
other underscore-prefixed arguments, such as `_destination`, are part of identity.
The service/default-dispatcher restart gap and safe integration choices are spelled out in
`backend/app/modules/m20_general_cognitive_worker/INTEGRATION.md`.
