# Alembic coverage for six formerly auto-provisioned M05/M10/M15 tables (PREP-NORUN)

Status: historical builder NOT RUN (no Alembic run, no database, no tests run by the
builder). The first submitted revision id (20261010_m05_m10_m15_uncovered_tables, 37
chars) was REJECTED: the peer observed a real StringDataRightTruncation on their old
head against Postgres alembic_version.version_num VARCHAR(32); SQLite hides it. That
original failure stays recorded here. The peer's narrow rename probe passed
upgrade/downgrade/re-upgrade; the new fix awaits re-audit - no PG pass is claimed for
the submitted head. Peer audits at runtime; this is not operational proof. PG/SQLite
type fidelity remains unverified. Schemas were transcribed by reading the ORM row
classes at base efa5649f7cbee5800e1cb38d0d38fbd3e5c55eca.

Provenance ruling (peer coordinator): m05 pair: INTEGRATION8 conversion intent
confirmed; m10/m15 four: no intentional-omission note found (absence is not
proof), strategy policy applied.

Base: efa5649f7cbee5800e1cb38d0d38fbd3e5c55eca (public main after M18 landed;
M18 added no migrations - beaf7002..efa5649f touches no module code in the
M00/M05/M10/M15/M24 bounds and no files under migrations/). Single Alembic
head at build time: 20261010_m14_sandbox_wave (down_revision chained, no fork).

Revision 20261010_m05_m10_m15_tables (28 chars; fits the Postgres
alembic_version.version_num VARCHAR(32) limit) creates, with downgrade:
- m05_cadence_policies (ORM: backend/app/modules/m05_outreach_manager/cadence.py:157)
- m05_delivery_claims (ORM: m05_outreach_manager/sql_repository.py:117)
- m10_promise_snapshots (ORM: m10_email_assistant/sql_repository.py:103)
- m10_promise_source_messages (ORM: m10_email_assistant/source_message_store.py:8)
- m15_provider_publication_receipts (ORM: m15_document_generator/publication_receipt_store.py:7)
- m15_publication_provider_keys (ORM: m15_document_generator/provider_key_registry.py:8)

Authoring choices for review: unique constraints are named explicitly (ORM
leaves them unnamed); explicit indexes only where the ORM sets index=True,
named ix_<table>_<column>; all non-Optional columns nullable=False, only
m15_publication_provider_keys.retired_at nullable. Constructor
Base.metadata.create_all calls are retained (dev/test only per
docs/DATABASE_STRATEGY.md).

Guard: tests/migrations/test_module_table_migration_coverage.py (AUTHORED,
NOT RUN) asserts every __tablename__ in the M00/M05/M10/M15/M24 module bounds
appears in migrations/versions text. Source-occurrence only; known limit:
metadata-import migrations (m22 PIPELINE_TABLES pattern) carry no literals
and are outside this guard's scope.

Out-of-bounds observation (reported, not acted on): the same literal-name
sweep flags tables in modules outside my bounds (claire_*, m06, m07, m08,
m11-m14, m16, m17) as uncovered; m22's tables ARE covered via the
metadata-import pattern despite having no literals. Other builders own those
partitions.
