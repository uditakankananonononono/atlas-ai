# ATLAS-M18-PACING-DURABILITY-01: PREP ONLY

Base: f37156c7fc7aec8cf7bec6ecbd0f8aa39ecb18fa.
Tests are authored, not run. The helper is not wired and is not a completed repair.
Existing lane_rate_limit.py and collection behavior are unchanged.

## Written interface

`encode_snapshot(tenant_id, states, now=aware_datetime, expires_at=aware_datetime)`
returns bounded UTF-8 JSON bytes. Input states are a mapping of exact limiter host
keys to objects implementing the six documented StateFields attributes.
`decode_snapshot(bytes, tenant_id=..., now=...)` returns a RestoredSnapshot with
immutable PacingState values and an immutable host mapping, or raises StateRejected.
`write_snapshot(Path, tenant_id, states, now=..., expires_at=...)` persists with a
0600 temporary file, file fsync, atomic replace, directory fsync and readback.
`read_snapshot(Path, tenant_id=..., now=...)` bounds reads and rejects symlinks and
nonregular files. These filesystem methods target Linux/POSIX. No PG or service.

Timestamps must be timezone aware and serialize in UTC. The existing limiter
honor_retry_after stores its deadline in circuit_open_until; that exact deadline
is retained without reset, truncation or conversion to a fresh relative wait.
interval, last_request_at and all counters persist alongside the circuit deadline.
An expired circuit deadline remains present; the caller evaluates it against time.
SHA-256 detects accidental corruption, not forgery by a writer with file access.
Schema is strict version 1, rejecting duplicate keys and unknown fields/versions.
Limits: 1 MiB serialized/read bytes, 1024 hosts, 253 characters per host key,
256 characters per tenant ID, signed-63-bit counters, 7-day interval and 30-day TTL.
Limits reject an entire snapshot; hosts are never evicted to make it fit.
TTL must cover both the pacing deadline and circuit/Retry-After deadline.
Missing, corrupt, expired, future-dated and tenant-mismatched records all raise.
No API interprets those errors as empty state or permission to fetch.

## Peer-owned integration decisions still required

- Authenticate tenant identity and choose a trusted private per-tenant directory
  and file path. Host keys must be passed unchanged (current collector uses netloc).
  No directory creation, path confinement, or hostile-parent-directory protection
  is claimed here. Callers must prevent path races and unauthorized directory access.
- Define first initialization separately from restore. Missing records deny;
  bootstrap must be explicitly permitted, never an automatic error fallback.
- Choose refresh cadence/TTL within limits, at least as long as every saved wait.
  Requests must stop when persistence/readback fails or the snapshot expires.
- Snapshot under the limiter's caller-owned lock; materialize real HostState
  instances from restored fields under that same lock. No helper mutates _states.
- Serialize all writes across threads/processes. This is a single-writer atomic
  file helper, not a transactional distributed limiter. Last writer wins if that
  precondition is violated. Lost updates or old valid snapshot replay are not
  detectable without a trusted external generation/revision authority.
- Choose persist-before-effect ordering and crash boundaries around request,
  success, failure, honor_retry_after and dispatch. A crash before persistence
  can still lose a deadline. This helper alone does not close that window.
- Existing record_success clears circuit_open_until; integration must decide
  when success may clear a restored Retry-After restriction. No source edits here.
- Test wall-clock behavior. Restores before saved_at deny clock rollback; a later
  wall-clock jump can consume a deadline early. No durable monotonic clock proof.
- Peer owns execution of these contracts and all regression/canary tests. No
  pytest, test imports, migrations, app startup, network fixtures or services ran
  during authoring. Stdlib source syntax inspection is not test execution.

## Integrator candidate binding

Added opt-in DurableHostRateLimiter, not default collector wiring. Existing
private directory and trusted tenant derive the hashed file identity; restore is
default, explicit bootstrap refuses existing state. Each begin_request validates
stored TTL/state and persists the request timestamp before returning permission
to fetch. Each mutation writes/readbacks before returning; failures block further
begin_request until explicit reconciliation. Future Retry-After cannot be cleared
by success. Tests now run by integrator; raw receipt supplied separately.
The in-instance RLock is NOT a cross-process lease. One live instance/writer per
tenant is required. Parent-directory races and old valid-file replay remain open.
The safe dispatcher must use begin_request, not check plus later request. No
claim that helper protects legacy collectors automatically. A crash before a
new failure/Retry-After is recorded remains a window; no remote effect recovery.
