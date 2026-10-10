# Opt-in M22 discovery persistence

Basef37156c7. DurableDiscoveryService requires an explicitly provisioned store,
restores/checks before collector dispatch, serializes in one instance asyncio
lock, preflights source/query identities against no-eviction capacities. Refuses
missing/corrupt/cross-tenant state. Every attempted source outcome and completed
query digest snapshot commit before candidates return; failure latches discovery
and clears candidate cache. Restart checks cooldown absolute UTC deadlines and
keeps previous query identity even empty. Removed candidate names cannot be
rehydrated without persisting sensitive names: diff explicitly digest-only.
Counters reflect normalized pre-dedup source candidates. Existing plain Service
and route creation unchanged: deployment must opt in and enforce ONE live writer
per tenant/root; this is not a default route repair. No permission or M00 approval
is created by state. No collector credential/config/error/query/name goes to disk.

POSIX local private provisioned root, single live writer are trusted assumptions;
flock protects state mutations, not collector lifecycle leases across processes.
Crash/cancellation between collector result and persist remains a cooldown window.
Source/query commits are individual, not all-or-nothing query transactions. State
checksums detect corruption, not a malicious operator recomputing them or restoring
an old valid file. Clock rollback/future deadlines retained, no policy bypass claim.
Capacity oversize candidate stop occurs during stream, not before remote work.
Initial baseline run had3missingM00approval_events failures; later reviewer base
run passed them. STATE-DEPENDENT, not a stable baseline failure set. Cause
unisolated, shared temporary SQLite residue only a hypothesis.

## Independent review and narrowed latch
Initial reviewer107PASS1SKIP3FAIL and exactbase run failed same3missingM00table
nodes; later samebase passed, making these STATE-DEPENDENT, cause unisolated.
Delta reviewer111PASS1SKIP0FAIL, builder108PASS1SKIP3FAIL. Not caused by diff,
but not a stable pre-existing failure set. Fresh-temp cause isolation pending.
Pre-effect validation/capacity errors refuse without latching; existing admitted
query remains usable after capacity refusal. Only StateError in post-effect store
commit phase latches current instance. Fresh instance may load prior valid store
and redispatch: PER-INSTANCE only, not restart-safe failure reconciliation.
Non-StateError exceptions are not latched; no arbitrary injected method guarantee.
Real store OSError paths code-read: lock/read errors map storage_unavailable;
write/replace/fsync/readback OSError map commit_unverified; finally temporary
cleanup ignores OSError. Other unexpected non-StateError remains a scoped risk.
Times use time.time(), not injectable clock. Individual source/query commits,
not atomic whole-query transaction. Crash before outcome save/cooldown remains;
flock only state writes, checksum not authentication, noM00authority inferred.
