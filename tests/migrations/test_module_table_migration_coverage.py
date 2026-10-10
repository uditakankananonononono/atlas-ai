"""Guard: every module-owned table in the M00/M05/M10/M15/M24 bounds has an Alembic revision.

Also guards the Postgres alembic_version.version_num VARCHAR(32) limit: revision
20261010_m05_m10_m15_tables (28 chars) replaced the rejected 37-char id
20261010_m05_m10_m15_uncovered_tables after the peer observed a real
StringDataRightTruncation on PG. Historical builder NOT RUN; peer observed the old head
fail on PG; peer's narrow rename probe passed upgrade/downgrade/re-upgrade; the new fix
awaits re-audit. At authoring time this is the only revision id over 32 chars and it is
replaced, so the length guard below covers every revision in the chain.

AUTHORED, NOT RUN. Source-occurrence check only: it greps __tablename__ literals
against migrations/versions text. This is NOT operational proof - it never runs
Alembic, never compares columns or types, and PG/SQLite fidelity is unverified.
Known limit: migrations that create tables from imported module metadata (the
m22 PIPELINE_TABLES pattern in 20260924_m22_install_pipeline.py) contain no
table-name literals; modules using that pattern need a metadata-aware check and
are outside this guard's M00/M05/M10/M15/M24 scope.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOUNDED_MODULES = ("m00_approval_center", "m05_outreach_manager", "m10_email_assistant",
                   "m15_document_generator", "m24_billing")
TABLE_RE = re.compile(r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]")


def _module_tables():
    tables = {}
    for module in BOUNDED_MODULES:
        for source in (ROOT / "backend" / "app" / "modules" / module).rglob("*.py"):
            for name in TABLE_RE.findall(source.read_text()):
                tables[name] = source.relative_to(ROOT).as_posix()
    return tables


def _migration_text():
    return "\n".join(path.read_text() for path in (ROOT / "migrations" / "versions").glob("*.py"))


def test_every_bounded_module_table_has_a_migration():
    missing = {name: origin for name, origin in _module_tables().items() if name not in _migration_text()}
    assert not missing, f"module tables without an Alembic revision: {missing}"


def test_six_formerly_uncovered_tables_are_covered():
    text = _migration_text()
    for name in ("m05_cadence_policies", "m05_delivery_claims", "m10_promise_snapshots",
                 "m10_promise_source_messages", "m15_provider_publication_receipts",
                 "m15_publication_provider_keys"):
        assert name in text, f"{name} still lacks an Alembic revision"


def test_revision_ids_fit_postgres_alembic_version_varchar32():
    revisions = {}
    for path in (ROOT / "migrations" / "versions").glob("*.py"):
        match = re.search(r"^revision\s*=\s*['\"]([^'\"]+)", path.read_text(), re.M)
        if match:
            revisions[match.group(1)] = path.name
    too_long = {rev: name for rev, name in revisions.items() if len(rev) > 32}
    assert not too_long, f"revision ids exceeding PG alembic_version.version_num VARCHAR(32): {too_long}"


def test_short_revision_id_is_chained_on_the_single_head():
    text = (ROOT / "migrations" / "versions" / "20261010_m05_m10_m15_tables.py").read_text()
    assert "revision='20261010_m05_m10_m15_tables'" in text
    assert len("20261010_m05_m10_m15_tables") <= 32
    assert "down_revision='20261010_m14_sandbox_wave'" in text
