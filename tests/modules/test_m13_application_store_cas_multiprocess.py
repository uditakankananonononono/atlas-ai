"""Claim atomicity across separate OS processes, each with its own engine (file SQLite, and real PG if available)."""
import multiprocessing as mp
import os
import time

import pytest

from app.modules.m13_browser_agent import application_flow as af
from app.modules.m13_browser_agent.application_flow import ApplicationSession, WorkflowStatus


def _record(**kw):
    base = dict(session_id="s1", tenant_id="t1", actor_id="u1", url="https://example.com/a")
    base.update(kw)
    return ApplicationSession(**base)


def _worker(url, who, barrier, out):
    # widen the old read-check-write window: any JSON decode inside the store's transaction sleeps
    orig = ApplicationSession.from_dict.__func__

    def slow(cls, data):
        time.sleep(0.7)
        return orig(cls, data)
    ApplicationSession.from_dict = classmethod(slow)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.modules.m13_browser_agent.application_store import SQLApplicationSessionStore
    engine = create_engine(url)
    store = SQLApplicationSessionStore(sessionmaker(bind=engine, expire_on_commit=False))
    rec = store.get("t1", "s1")
    rec.status = WorkflowStatus.SUBMIT_ATTEMPTING.value
    rec.attempt_id = who
    rec.outcome_uncertain = True
    barrier.wait(20)
    try:
        ok = store.compare_and_save(rec, WorkflowStatus.AWAITING_SUBMIT_APPROVAL.value, "")
    except Exception as error:  # a stale/conflict refusal is a correct loser outcome
        ok = False
    out.put((who, bool(ok)))


def _backends(tmp_path):
    yield "sqlite-file", f"sqlite:///{tmp_path/'cas.db'}", None
    try:
        import pgserver
        srv = pgserver.get_server(tmp_path / "pg", cleanup_mode="stop")
        yield "pg", srv.get_uri().replace("postgresql://", "postgresql+psycopg2://"), srv
    except Exception as error:  # PG backend unavailable: reported as skipped, not as a pass
        yield f"pg-unavailable:{type(error).__name__}", None, None


@pytest.mark.parametrize("which", ["sqlite-file", "pg"])
def test_exactly_one_process_wins_the_attempt_claim(tmp_path, which):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    from app.modules.m13_browser_agent.application_store import SQLApplicationSessionStore
    url = None
    for name, u, _srv in _backends(tmp_path):
        if name == which:
            url = u
        elif name.startswith("pg-unavailable") and which == "pg":
            pytest.skip(name)
    if url is None:
        pytest.skip("backend unavailable")
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    store = SQLApplicationSessionStore(sessionmaker(bind=engine, expire_on_commit=False))
    store.create(_record(status=WorkflowStatus.AWAITING_SUBMIT_APPROVAL.value))
    engine.dispose()
    ctx = mp.get_context("fork")
    barrier, out = ctx.Barrier(2), ctx.Queue()
    procs = [ctx.Process(target=_worker, args=(url, who, barrier, out)) for who in ("A", "B")]
    [p.start() for p in procs]
    [p.join(60) for p in procs]
    results = dict(out.get(timeout=5) for _ in procs)
    assert sorted(results.values()) == [False, True], results
    winner = next(k for k, v in results.items() if v)
    final = SQLApplicationSessionStore(sessionmaker(bind=create_engine(url))).get("t1", "s1")
    assert final.attempt_id == winner and final.status == WorkflowStatus.SUBMIT_ATTEMPTING.value


def _stores(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    from app.modules.m13_browser_agent.application_store import (
        InMemoryApplicationSessionStore, SQLApplicationSessionStore)
    engine = create_engine(f"sqlite:///{tmp_path/'s.db'}")
    Base.metadata.create_all(engine)
    return [InMemoryApplicationSessionStore(), SQLApplicationSessionStore(sessionmaker(bind=engine, expire_on_commit=False))]


def test_stale_copy_cannot_overwrite_a_newer_write_on_either_store(tmp_path):
    # characterization added WITH the fix (not failing-first): plain saves are revision-guarded too
    for store in _stores(tmp_path):
        store.create(_record(status=WorkflowStatus.AWAITING_SUBMIT_APPROVAL.value))
        a, b = store.get("t1", "s1"), store.get("t1", "s1")
        a.status = WorkflowStatus.SUBMIT_DISPATCHED.value
        store.save(a)
        b.status = WorkflowStatus.AWAITING_SUBMIT_APPROVAL.value
        with pytest.raises(af.StaleSessionError):
            store.save(b)
        assert store.get("t1", "s1").status == WorkflowStatus.SUBMIT_DISPATCHED.value
