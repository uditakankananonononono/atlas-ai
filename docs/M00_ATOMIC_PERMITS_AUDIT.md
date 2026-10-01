# M00 atomic creation, use deadlines and audit protections

The pending-review deadline (`expires_at`, populated from the existing TTL) still
applies only to pending requests. Human approval now sets a separate
`approved_use_by` deadline, defaulting to 3600 seconds after the decision. Service
constructors can configure a positive `approved_use_ttl_seconds`. Exact-bound
consumption checks the use deadline under the same write transaction as the
one-shot effect row. It checks again after flushing, immediately before commit.
The claim's linearization point is this final check; a wall-clock deadline can
pass during the database commit itself. This is a claim deadline, not a promise
that a remote external effect finishes before that time. No external effects
are performed by M00.

Existing approvals acquire no deadline automatically in the migration. They
fail closed for first consumption and require a new review. Migration does not
change existing pending deadlines or reinterpret historical pending TTLs.

Reservation uses `(tenant_id, key)` with an exact request hash. PostgreSQL
`INSERT ... ON CONFLICT DO NOTHING RETURNING` waits for the winning transaction;
SQLite uses `BEGIN IMMEDIATE`, including across processes. Reservation, request
and created event commit together. Payload mismatch raises a domain conflict,
not a raw uniqueness exception. No-key calls keep creating separate requests.
Allow/deny policy decisions still do not create reviews or reserve keys.

Consumption and revocation serialize on the approval row (SQLite writer lock or
PostgreSQL `FOR UPDATE`). One new claim returns `replayed=false`; a matching
replay returns `replayed=true` and the original receipt, never fresh execution
authority. `allowed=true` on a replay is kept for legacy receipt compatibility.
Callers must not execute an effect on replay. Revocation blocks first use and
replay. An unrelated effect-id collision becomes a domain conflict.

## Database audit boundary

SQLite UPDATE and DELETE triggers reject raw SQL mutations of approval events.
PostgreSQL statement triggers reject UPDATE, DELETE and TRUNCATE. Both fresh
metadata-created databases and migrated databases get these protections.
PostgreSQL production runtime must use a non-owner, non-superuser role with no
membership in a privileged role. Grant only SELECT and INSERT on the event
table, plus USAGE on the schema and event sequence. Migration revokes mutation
rights from PUBLIC; setting `ATLAS_M00_RUNTIME_ROLE` also revokes that role's
direct mutation grants and grants SELECT/INSERT. Role creation, database
credentials and inherited privileges remain deployment responsibilities.

These controls are append-only protections, **not tamper-proof or tamper-evident**.
A SQLite database-file owner can remove triggers or rewrite the file. A
PostgreSQL table owner/superuser can disable or drop triggers, change grants or
replace the database. There is no hash chain, external witness or signed log.
Keep schema ownership separate from the runtime role. The tests exercise raw
SQL and a real PostgreSQL restricted role, but do not certify a deployment's
role hierarchy or every effect-producing caller.

## Reproduction and testing

At base 313309be2a960a84b909d1834c3046f884e21a7e, a native SQLite eight-thread
same-key race produced eight approval requests and seven raw IntegrityErrors.
An approved request with pending TTL=1 second could be consumed an hour later.
Raw SQL updated eleven event rows. The existing M00 suite passed despite these.

Run:

```
ATLAS_TEST_POSTGRES_URL=postgresql+psycopg://... \
  python -m pytest tests/modules/test_m00_atomic_permits_audit.py -q
```

The PostgreSQL URL must point only to a disposable local test database. Tests
create/drop isolated schemas and a temporary NOLOGIN runtime role; tests need
schema and role creation permission. Eight spawned-process and eight-thread
races run independently on SQLite and PostgreSQL. PostgreSQL tests skip when
the URL is missing; the SQLite variant of the role-only test also skips.
