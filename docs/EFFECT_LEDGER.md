# Effect ledger (reserve before invoke)

Non-READ tools in the M20 dispatcher are reserved in `m20_effect_ledger` (tenant-scoped, transactional) and marked
`invoking` before the handler runs. Effect identity = sha256(JSON array of [tenant, task, node, tool, args-hash]) where the
args hash covers the canonical args ignoring only the exact `_expectation_claim_id` runtime bookkeeping key; same key with
different args is refused. The JSON-array encoding is unambiguous: components containing `|` cannot collide with a different
component split, which the previous `"|".join(...)` encoding allowed ((task='T|N', node='X') collided with
(task='T', node='N|X'), so the second effect silently replayed the first receipt).

Migration/compat for existing rows: rows reserved before the encoding fix keep their old `"|".joined` effect id. `reserve`
reads the legacy key first and treats a row found there as authoritative for its effect (replays its receipt, preserves its
state machine) ONLY if its stored task_id/node_id/tool/args_hash equal the request (tenant is already scoped); a row that
merely shares the ambiguous legacy hash (task='T|N', node='X' vs task='T', node='N|X') is ignored and the request is
reserved under the new id, never replayed; `GCWRuntime.reconcile_effect` falls back (via `EffectLedger.resolve_effect_id`) to the legacy id when no row exists under the new id and a matching legacy row exists. No data
rewrite is needed. Pre-fix rows whose tenant/task/node/tool contained `|` are potentially ambiguous - two logical effects
may share one legacy row - and should be reconciled manually instead of re-dispatched. New reservations always use the
new encoding. Crash after `invoking` and before the receipt => `indeterminate`:
never auto-retried, task goes BLOCKED, human calls `GCWRuntime.reconcile_effect(...)`. Retry exceptions no longer re-invoke;
handler-raised `ToolError` and `ApprovalPending` after mark-invoking are also indeterminate;
only `ToolNotExecuted` (provable no-effect) or `ToolSpec.provider_idempotent=True` allow retry.

Limits: not exactly-once across remote systems. A crash after `invoking` but before the real effect is indistinguishable
from after it, so it is also indeterminate (conservative). Liveness: a same-host owner process that is verifiably alive
(PID alive, not a zombie, and a matching /proc start-time token so PID reuse does not resurrect a dead owner) is never
treated as dead - even past its lease (timeout+30s). A handler that blocks the event loop outlives its lease while still
running; reconcile and retake are refused until the owner process actually exits. Cross-host owners cannot be PID-checked;
only the lease bounds them. Rows written before the liveness fix carry no start-time token and get PID-only liveness.
`owner_pid_start` is now `<boot6>.<pidns>:<start ticks>` (boot6 = first 6 hex of sha256(/proc/sys/kernel/random/boot_id), pidns =
inode of /proc/self/ns/pid). A different boot id means the owner is dead (reboot; start ticks restart at boot, so PID reuse
after reboot could otherwise match). Same boot but a different PID namespace cannot be checked, so only the lease decides.
Rows with a bare start-tick token (written before this change) are compared on start ticks alone, so they have NO reboot
protection; they age out as rows are retaken. A state-Z process whose /proc/PID/task has any non-zombie thread (main thread
called pthread_exit) is alive. Assumption, only partly handled: `owner_host` (hostname) identifies one machine. Two containers
or hosts sharing a hostname are distinguished only for new-format tokens, and only when they differ in boot id or PID namespace;
identical hostnames on different hosts with the same boot id and namespace (cloned images with a reused boot id) remain unsafe.
Dispatcher fail-safe: if `mark_invoking` raises after `reserve`, the dispatcher calls `EffectLedger.release`
(RESERVED or INVOKING, owner-scoped, to FAILED, handler provably never called) so a live owner does not strand the row as
`EffectInProgress`. If the ledger is unreachable at that moment the release itself fails and the row stays until the process
exits (then the normal dead-owner path applies) or, for a cross-host owner, until the lease expires. Token length is at most about 38 characters, which still fits the original VARCHAR(40) on existing tables (new tables use 64; the startup ALTER is unchanged).
SQLite file DB tested only; Postgres remains untested.
Handlers must not block the event loop with synchronous I/O or sleeps (use async I/O or an executor): wait_for cannot
cancel them, they run past their timeout/lease, and the dispatch call returns only after they yield.
The liveness fix adds a nullable-default `owner_pid_start` column; `EffectLedger` adds it to pre-existing tables with a
best-effort ALTER TABLE on startup. A bare `ToolDispatcher()` gets a process-local in-memory ledger (not durable); `GCWRuntime` binds the
durable one. `service.py`'s own dispatcher uses that in-memory default (not changed). SQLite file DB tested only; Postgres untested.
The plan is now checkpointed after planning and after every step so node ids are stable across restarts.

`reconcile_effect` can be called directly after a crash: the ledger classifies a dead/expired
invocation using the same owner/PID/lease rule as reserve before applying the operator decision.
A live unexpired invocation and a reserved (not invoked) effect cannot be reconciled.
Effect hashing excludes `_expectation_claim_id` centrally for both dispatch and reconciliation;
other underscore-prefixed arguments, such as `_destination`, are part of identity.
The service/default-dispatcher restart gap and safe integration choices are spelled out in
`backend/app/modules/m20_general_cognitive_worker/INTEGRATION.md`.
