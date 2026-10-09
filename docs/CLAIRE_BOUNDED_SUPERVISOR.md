# In-process bounded database recovery

The configured read-only worker can be passed to supervise_read_only. Only SQLAlchemy
OperationalError and psycopg OperationalError are recovered. Defaults: 10 jobs,
3 database failures across the entire call. Return queue_empty, job_limit or
database_unavailable with goal IDs and a failure counter, never exception text.
This result is internal operational state, not a public response schema.

After a recoverable DB failure, dispose the pool and wait one full lease plus 0.2s
before another claim. Do not reset attempts, goals, approvals or effects. Existing
fencing and reconciliation decide what may resume. On failure-budget exhaustion or
disposal DB failure, return a visible terminal status. Cancellation and programming
bugs propagate. Do not wrap those bugs in success or retry them forever.

This is NOT an OS process supervisor, daemon or deployment installer. Counts bound
the loop, not wall time: sync DB calls may still block. Availability must return from
outside this function; it does not restart PostgreSQL. The configured factory remains
read-only; application callers own any injected objects. No public endpoint added.

Live model, service restart/kill testing, outbox delivery and production cutover remain
separate gates. This helper does not close acceptance A.
