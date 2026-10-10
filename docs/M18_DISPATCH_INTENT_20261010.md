# M18 opt-in dispatch intent

Base02a75fbd. Explicit separately provisioned private POSIX WAL and pacing store,
one live writer per tenant. begin_request validates both, commits pending intent
before saving/readback of request timestamp, clears exact intent only after pacing
commit, then returns permission. Missing/corrupt/pending WAL denies dispatch.
Pending survives restart and never auto-clears, even on TTL expiry. No legacy
collector wiring; record_request refuses so dispatcher must use begin_request.

Operator acknowledges exact pending intent only with explicit inspected boolean;
this is trusted-caller intent, NOT authenticated human-role enforcement. API itself
never retries a fetch or grants the old permission. Reconciliation/restart can
permit future new requests only after independent operator inspection. Failure
before confirmed WAL write returns no permission. Snapshot failure leaves pending;
completion failure may leave pending (conservative denial) or cleared afterreplace
but snapshot timestamp is already persisted, so no lost-save pacing bypass.

Limits: conservative stuck-pending after crash; recovery acknowledgment authority
is external caller duty; two-file journal/snapshot ordering relies on fsync and
weak filesystem semantics remain excluded. Snapshot TTL requires refresh; old
pending intents retained indefinitely until inspected, no eviction/reset API.
No hostile-admin/oldfile-replay proof, cross-process lease, or remote exactly-once.
Unseen RetryAfter and record_failure write-ahead OUT OF SCOPE. Crash can occur after
clearing WAL before caller dispatch, then request pacing remains conservatively
consumed. Pending host/timestamp stored in private file; no credentials/errors.
No network/training/payment. Tests simulate phase boundaries, not powerloss proof.
