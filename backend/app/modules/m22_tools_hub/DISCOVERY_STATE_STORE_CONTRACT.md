# ATLAS-M22-DISCOVERY-STATE-01: PREP ONLY

Base: f37156c7fc7aec8cf7bec6ecbd0f8aa39ecb18fa. New standalone helper only.
No integration, test execution, migration, main write, or runtime verdict.
Tests in `tests/modules/test_m22_discovery_state_store_prep.py` are authored-not-run.

## Written interface

`DiscoveryStateStore(private_root, tenant_id)` uses caller-supplied root and
verified tenant identity. It does not read environment variables or credentials.
The caller provisions a private local POSIX directory. Filename and payload use
namespace-separated SHA-256 identity fingerprints. Each tenant has its own lock
and data file. Hashes are not encryption and low-entropy values can be guessed.

- `provision()`: explicit new-tenant creation only. Refuses existing state,
  including corrupt state. NEVER call this to recover missing state at restart.
- `read()`: validated copy of the version-1 state. Missing, corrupt, unsupported,
  swapped-tenant or oversized state is refused, not treated as empty.
- `is_cooling(source, now=epoch)`: compare stored absolute UTC epoch deadline.
  Equality expires cooldown. Pass the same stable collector.name on every run.
- `record_source(source, success=bool, candidates=int, latency_ms=number,
  cooldown_until=epoch)`: atomically accumulate outcome counters. Failed outcomes
  must have zero candidates. Existing cooldown is never shortened. No error
  string argument. Status is only `ok` or `error`.
- `record_query(query, candidate_keys, at=epoch, kinds=None)`: exact query text
  identity matches Service's current behavior, but only its hash is stored.
  Candidate keys must be Service._key lowercase SHA-256 digests. Returns
  `{first_run, added, removed}` with digest lists. First run returns empty lists,
  matching the pinned service. Empty prior snapshots still count as prior runs.

State contains schema_version, tenant fingerprint, revision, sources, queries,
and history. Source keys and query keys are fingerprints. Sources contain runs,
failures, candidates, last_latency_ms, last_status, cooldown_until. Queries
contain sorted snapshot digests, latest diff, runs, at and enumerated kinds.
History contains query_key, epoch, kinds and count. Arbitrary fields are refused.
No candidate names, URLs, query/source text, error strings, configuration, or
Service object serialization. No approvals/install state is touched.

Every update locks, reads current disk state (no stale in-memory overwrite),
validates, writes a unique mode-0600 same-directory temporary file, flushes/fsyncs,
replaces atomically, fsyncs the directory, and validates readback for equality.
Duplicate JSON keys, invalid types, non-finite values, unknown fields, invalid
checksums, versions and identities fail closed. Errors are fixed codes; original
OS/parser messages are not included. OS failures during writes return
`commit_unverified`: replacement may already have landed; read and reconcile,
never blindly replay a counter increment. Checksum detects accidental damage,
not malicious edits, authorized rollback of an old file, or cryptographic origin.

Hard bounds: 128 sources, 200 distinct queries, 200 history rows, 1,000 unique
candidate digests per snapshot, 4 MiB file. Capacity refuses writes; it does NOT
evict cooling sources or seen-query identities. Effective byte capacity can be
hit before the count bounds. Existing admitted queries can continue while row
capacity is full, but may still hit byte capacity. No reset/clear API is supplied.

## Required integration decisions, owned by peer

1. Supply trusted tenant identity and a private durable root. No identity fallback.
   First-run provisioning needs an external durable new-tenant decision: file
   absence alone cannot distinguish new tenant from lost state.
2. Restore/check cooldown before scheduling ANY collector. Save failed source
   deadlines before acknowledging its outcome. Persist query snapshot/history
   before reporting success. Any StateError must block affected discovery, not
   silently fall back to memory. Capacity admission should be checked before
   work starts; helper record calls alone cannot prevent pre-save external work.
3. Restore source_stats and translate hashed source/query IDs using known inputs.
   This helper deliberately does not mutate Service or invent an adapter binding.
   Display-name diffs need a separately approved rehydration strategy; digest-only
   diff survives restart, but removed display names are NOT retained here.
4. Serialize same-tenant discovery orchestration. File updates are locked; a
   check-then-collect sequence is NOT a distributed source execution lease.
   Two concurrent workers could both pass is_cooling before either records a
   failure. Query snapshot ordering is commit order, not query-start order.
5. Interrupted in-flight work before record_source is not an outcome record.
   Pending execution leases/checkpoints, if needed, are separate work. Trustworthy
   wall clock is required; no claim of protection from malicious clock jumps,
   deletion, old-state rollback, NFS lock behavior, or hostile directory writes.
6. Migrations/version policy, recovery operations, display-name history, service
   wiring, test execution and independent restart/regression verdict remain open.
   The helper existing is not a completed repair or evidence of working discovery.

## Superseding integration status
Opt-in DurableDiscoveryService and helper/service tests now executed. See
docs/M22_DURABLE_DISCOVERY_INTEGRATION_20261010.md (repository docs).
Plain Service default unchanged. Historical PREP text records original scope only.
