# Independent scratch PostgreSQL evidence

Dependencies installed outside repository into /tmp/atlas-pg-oct8: pgserver 0.1.4, psycopg 3.3.6. Tests use actual bundled PostgreSQL processes and separate database connections, not mocked SQL. No production database or deployment was accessed.

Existing unknown-hold migration suite: SQLite and PostgreSQL 2 passed, 0 skipped. Covers upgrade, legacy row default, runtime persistence/restart retention of model uncertainty, downgrade refusal and retained hold/version after refusal.

New scratch PostgreSQL suite: 3 passed, 0 skipped. Covers ordinary reviewed-snapshot activation, stale durable replacement rejection, separate committed writer between hash check and guarded UPDATE rejection, and simultaneous risk-register revision writers with exactly one commit/one conflict and intact history.

These replace the earlier missing-pgserver independent-local-evidence limitation. They do not establish production migration/rollback operations, supported deployment configuration, generic cross-worker runtime serialization, reviewer authorization/provenance or live external-effect verification. Same-id divergent Alembic revision integration remains blocked. No product source change was required.
