"""Native SQL concurrency, clock and append-only regression tests. No stubs."""
import multiprocessing as mp
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, func, text, event
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import (
    Service, ApprovalConflictError, ApprovalRequestRow, ApprovalEventRow,
    ApprovalIdempotencyRow, ApprovalEffectRow,
)

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
PARAMS = dict(module_id=5, action_type="send_email", payload={"to": "test.invalid"}, user_id="tenant-a")


@pytest.fixture(params=["sqlite", "postgresql"])
def env(request, tmp_path):
    schema = "m00_test_" + uuid4().hex
    if request.param == "postgresql":
        url = os.getenv("ATLAS_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("ATLAS_TEST_POSTGRES_URL required for real PostgreSQL")
        admin = create_engine(url)
        with admin.begin() as c:
            c.execute(text(f'CREATE SCHEMA "{schema}"'))
        url += ("&" if "?" in url else "?") + "options=-csearch_path%3D" + schema
    else:
        admin = None
        url = f"sqlite:///{tmp_path}/atomic.db"
    eng = create_engine(url, pool_size=12, max_overflow=12)
    Base.metadata.create_all(eng)
    sf = sessionmaker(eng, expire_on_commit=False)
    clock = [T0]
    s = Service(sf, clock=lambda: clock[0], approved_use_ttl_seconds=60)
    yield s, sf, eng, clock, url
    eng.dispose()
    if admin:
        with admin.begin() as c:
            c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def counts(sf):
    with sf() as db:
        return tuple(db.scalar(select(func.count()).select_from(model)) for model in
                     (ApprovalRequestRow, ApprovalIdempotencyRow, ApprovalEventRow, ApprovalEffectRow))


def process_gate(url, barrier, queue):
    eng = create_engine(url)
    s = Service(sessionmaker(eng, expire_on_commit=False))
    barrier.wait()
    try:
        queue.put(s.gate(**PARAMS, idempotency_key="process-key")["approval"]["id"])
    except Exception as exc:
        queue.put(type(exc).__name__)
    finally:
        eng.dispose()


def test_eight_process_gate_race(env):
    _, sf, _, _, url = env
    ctx = mp.get_context("spawn")
    barrier, queue = ctx.Barrier(8), ctx.Queue()
    workers = [ctx.Process(target=process_gate, args=(url, barrier, queue)) for _ in range(8)]
    for p in workers:
        p.start()
    results = [queue.get(timeout=40) for _ in workers]
    for p in workers:
        p.join(40)
        assert p.exitcode == 0
    assert len(set(results)) == 1, results
    assert len(results[0]) == 36, results
    assert counts(sf) == (1, 1, 1, 0)


def test_eight_thread_race_restart_cross_tenant_and_no_key(env):
    s, sf, _, _, _ = env
    barrier = threading.Barrier(8)
    def call(_):
        barrier.wait()
        return s.gate(**PARAMS, idempotency_key="thread-key")["approval"]["id"]
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(call, range(8)))
    assert len(set(results)) == 1
    assert counts(sf) == (1, 1, 1, 0)
    restarted = Service(sf)
    assert restarted.gate(**PARAMS, idempotency_key="thread-key")["approval"]["id"] == results[0]
    other = s.gate(**(PARAMS | {"user_id": "tenant-b"}), idempotency_key="thread-key")
    assert other["approval"]["id"] != results[0]
    a, b = s.gate(**PARAMS), s.gate(**PARAMS)
    assert a["approval"]["id"] != b["approval"]["id"]
    with pytest.raises(ApprovalConflictError):
        s.gate(**(PARAMS | {"payload": {"changed": True}}), idempotency_key="thread-key")
    assert counts(sf) == (4, 2, 4, 0)


def test_racing_mismatches_are_domain_conflicts(env):
    s, sf, _, _, _ = env
    barrier = threading.Barrier(12)
    def call(i):
        barrier.wait()
        try:
            return s.gate(**(PARAMS | {"payload": {"variant": i % 2}}), idempotency_key="mismatch")["approval"]["id"]
        except ApprovalConflictError:
            return "conflict"
    with ThreadPoolExecutor(12) as pool:
        results = list(pool.map(call, range(12)))
    assert results.count("conflict") == 6
    assert len(set(results) - {"conflict"}) == 1
    assert counts(sf) == (1, 1, 1, 0)


def test_gate_rollback_leaves_no_orphan_or_notification(env):
    s, sf, eng, _, _ = env
    subscriber = s.broadcaster.subscribe()
    def fail(conn, cursor, statement, params, context, executemany):
        if statement.startswith("INSERT INTO m00_approval_events"):
            raise RuntimeError("deliberate transaction failure")
    event.listen(eng, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError):
            s.gate(**PARAMS, idempotency_key="rollback")
    finally:
        event.remove(eng, "before_cursor_execute", fail)
    assert counts(sf) == (0, 0, 0, 0)
    assert subscriber.empty()
    s.gate(**PARAMS, idempotency_key="rollback")
    assert counts(sf) == (1, 1, 1, 0)


def approved(env):
    s, _, _, clock, _ = env
    a = s.submit(**PARAMS, ttl_seconds=5)
    clock[0] += timedelta(seconds=4)
    a = s.decide(a["id"], ApprovalStatus.APPROVED, "owner")
    assert a["expires_at"] == T0 + timedelta(seconds=5)
    assert a["approved_use_by"] == T0 + timedelta(seconds=64)
    return a


def consume(s, aid, effect="one"):
    return s.consume_effect(aid, **PARAMS, effect_id=effect, actor="worker")


def test_pending_ttl_separate_from_approved_deadline(env):
    s, sf, _, clock, _ = env
    a = approved(env)
    clock[0] = T0 + timedelta(seconds=6)
    assert consume(s, a["id"])["replayed"] is False
    clock[0] += timedelta(hours=1)
    assert consume(s, a["id"])["replayed"] is True  # receipt only, never fresh authority
    with pytest.raises(ApprovalConflictError, match="consumed"):
        consume(s, a["id"], "two")
    assert counts(sf)[3] == 1


@pytest.mark.parametrize("seconds", [64, 65, 3605])
def test_first_consumption_at_or_after_deadline_rejected(env, seconds):
    s, sf, _, clock, _ = env
    a = approved(env)
    clock[0] = T0 + timedelta(seconds=seconds)
    with pytest.raises(ApprovalConflictError, match="deadline"):
        consume(s, a["id"])
    assert counts(sf)[3] == 0
    assert [x["event"] for x in s.audit(a["id"])] == ["created", "approved"]


def test_clock_crosses_deadline_after_flush_rolls_back(env):
    s, sf, eng, clock, _ = env
    a = approved(env)
    clock[0] = T0 + timedelta(seconds=63)
    def cross(conn, cursor, statement, params, context, executemany):
        if statement.startswith("INSERT INTO m00_approval_effects"):
            clock[0] = T0 + timedelta(seconds=64)
    event.listen(eng, "after_cursor_execute", cross)
    try:
        with pytest.raises(ApprovalConflictError, match="deadline"):
            consume(s, a["id"])
    finally:
        event.remove(eng, "after_cursor_execute", cross)
    assert counts(sf)[3] == 0
    assert len(s.audit(a["id"])) == 2


def test_revocation_blocks_first_use_and_replay(env):
    s, sf, _, _, _ = env
    a = approved(env)
    s.revoke(a["id"], actor="owner")
    with pytest.raises(ApprovalConflictError, match="revoked"):
        consume(s, a["id"])
    assert counts(sf)[3] == 0
    b = s.submit(**PARAMS)
    s.decide(b["id"], ApprovalStatus.APPROVED, "owner")
    consume(s, b["id"])
    s.revoke(b["id"], actor="owner")
    with pytest.raises(ApprovalConflictError, match="revoked"):
        consume(s, b["id"])


def test_racing_consumers_issue_one_fresh_permit(env):
    s, sf, _, _, _ = env
    a = approved(env)
    barrier = threading.Barrier(8)
    def call(_):
        barrier.wait()
        return consume(s, a["id"])
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(call, range(8)))
    assert sum(not r["replayed"] for r in results) == 1
    assert counts(sf)[3] == 1


@pytest.mark.parametrize("sql", ["UPDATE m00_approval_events SET actor='tampered'", "DELETE FROM m00_approval_events"])
def test_raw_audit_mutation_rejected(env, sql):
    s, _, eng, _, _ = env
    a = approved(env)
    with pytest.raises(DBAPIError, match="append-only"):
        with eng.begin() as c:
            c.execute(text(sql))
    assert [e["event"] for e in s.audit(a["id"])] == ["created", "approved"]


def test_pg_runtime_role_is_nonowner_append_only(env):
    s, _, eng, _, _ = env
    if eng.dialect.name != "postgresql":
        pytest.skip("PostgreSQL role ACL test")
    a = approved(env)
    role = "m00_runtime_" + uuid4().hex
    with eng.begin() as c:
        schema = c.scalar(text("SELECT current_schema()"))
        c.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE'))
        c.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
        c.execute(text(f'GRANT SELECT, INSERT ON m00_approval_events TO "{role}"'))
        c.execute(text(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA "{schema}" TO "{role}"'))
    try:
        for sql in ("UPDATE m00_approval_events SET actor='tamper'", "DELETE FROM m00_approval_events", "TRUNCATE m00_approval_events", "ALTER TABLE m00_approval_events DISABLE TRIGGER ALL"):
            with pytest.raises(DBAPIError):
                with eng.begin() as c:
                    c.execute(text(f'SET LOCAL ROLE "{role}"'))
                    c.execute(text(sql))
        with eng.begin() as c:
            c.execute(text(f'SET LOCAL ROLE "{role}"'))
            c.execute(text("INSERT INTO m00_approval_events (approval_id,event,at) VALUES (:id,'runtime_append',:at)"), {"id": a["id"], "at": T0})
        assert len(s.audit(a["id"])) == 3
    finally:
        with eng.begin() as c:
            c.execute(text(f'DROP OWNED BY "{role}"'))
            c.execute(text(f'DROP ROLE "{role}"'))


def test_racing_distinct_effects_return_domain_conflicts(env):
    s, sf, _, _, _ = env
    a = approved(env)
    barrier = threading.Barrier(8)
    def call(i):
        barrier.wait()
        try:
            return consume(s, a["id"], "distinct-" + str(i))
        except ApprovalConflictError:
            return "conflict"
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(call, range(8)))
    assert results.count("conflict") == 7
    assert counts(sf)[3] == 1


def test_migration_preserves_history_and_installs_guards(env):
    """Run the real migration over the actual base schema, in each database."""
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import MetaData, Table, Column, String, DateTime, Integer
    _, _, eng, _, _ = env
    legacy = MetaData()
    Table("m00_approval_requests", legacy,
          Column("id", String(36), primary_key=True), Column("user_id", String(120)),
          Column("expires_at", DateTime(timezone=True)))
    Table("m00_approval_idempotency", legacy,
          Column("key", String(200), primary_key=True), Column("request_hash", String(64)),
          Column("approval_id", String(36), unique=True), Column("created_at", DateTime(timezone=True)))
    Table("m00_approval_events", legacy,
          Column("id", Integer, primary_key=True), Column("approval_id", String(36)),
          Column("event", String(40)), Column("actor", String(120)), Column("at", DateTime(timezone=True)))
    # Rebuild just the affected native tables to their pre-migration shape.
    with eng.begin() as c:
        for name in ("m00_approval_events", "m00_approval_idempotency", "m00_approval_requests"):
            c.execute(text(f"DROP TABLE {name}"))
        legacy.create_all(c)
        c.execute(text("INSERT INTO m00_approval_requests (id,user_id,expires_at) VALUES ('old','historical-tenant',:at)"), {"at": T0})
        c.execute(text("INSERT INTO m00_approval_idempotency (key,request_hash,approval_id,created_at) VALUES ('key',:hash,'old',:at)"), {"hash": "a" * 64, "at": T0})
        c.execute(text("INSERT INTO m00_approval_events (id,approval_id,event,at) VALUES (1,'old','created',:at)"), {"at": T0})
        path = Path(__file__).resolve().parents[2] / "migrations/versions/20261001_m00_atomic_permits.py"
        spec = importlib.util.spec_from_file_location("m00_security_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with Operations.context(MigrationContext.configure(c)):
            module.upgrade()
        assert c.execute(text("SELECT tenant_id,key,approval_id FROM m00_approval_idempotency")).one() == ("historical-tenant", "key", "old")
        historical = c.execute(text("SELECT expires_at,approved_use_by,revoked_at FROM m00_approval_requests")).one()
        assert historical[0] is not None and historical[1:] == (None, None)
    for sql in ("UPDATE m00_approval_events SET actor='bad'", "DELETE FROM m00_approval_events"):
        with pytest.raises(DBAPIError, match="append-only"):
            with eng.begin() as c:
                c.execute(text(sql))


def test_effect_id_collision_across_approvals_is_domain_conflict(env):
    s, sf, _, _, _ = env
    a = approved(env)
    b = s.submit(**PARAMS)
    s.decide(b["id"], ApprovalStatus.APPROVED, "owner")
    barrier = threading.Barrier(2)
    def call(aid):
        barrier.wait()
        try:
            return consume(s, aid, "global-effect")
        except ApprovalConflictError:
            return "conflict"
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(call, (a["id"], b["id"])))
    assert results.count("conflict") == 1
    assert counts(sf)[3] == 1
    with sf() as db:
        assert db.scalar(select(func.count()).select_from(ApprovalEventRow).where(ApprovalEventRow.event == "effect_consumed")) == 1


def test_expired_pending_stays_nonconsumable(env):
    s, sf, _, clock, _ = env
    a = s.submit(**PARAMS, ttl_seconds=1)
    clock[0] += timedelta(seconds=1)
    assert s.get(a["id"])["status"] == ApprovalStatus.EXPIRED
    with pytest.raises(ApprovalConflictError):
        s.decide(a["id"], ApprovalStatus.APPROVED, "owner")
    with pytest.raises(ApprovalConflictError):
        consume(s, a["id"])
    assert counts(sf)[3] == 0
