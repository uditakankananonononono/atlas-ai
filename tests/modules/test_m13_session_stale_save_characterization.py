"""Detached session save regression for the fresh revision guard.

Previously both stores allowed newer status to be overwritten by a stale save.
It calls no browser, approval, device, authentication or submission path.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m13_browser_agent.application_flow import ApplicationSession, SessionRevisionConflict
from app.modules.m13_browser_agent.application_store import (
    InMemoryApplicationSessionStore, SQLApplicationSessionStore,
)


@pytest.mark.parametrize("kind", ["memory", "sql"])
def test_store_rejects_stale_detached_save(tmp_path, kind):
    engine = None
    if kind == "sql":
        engine = create_engine(f"sqlite:///{tmp_path / 'sessions.db'}")
        Base.metadata.create_all(engine)
        store = SQLApplicationSessionStore(sessionmaker(bind=engine))
    else:
        store = InMemoryApplicationSessionStore()
    try:
        original = ApplicationSession(tenant_id="a", session_id="s", actor_id="u",
                                      url="https://example.invalid")
        store.create(original)
        first = store.get("a", "s")
        stale = store.get("a", "s")
        assert first is not stale
        first.status = "inspected"
        store.save(first)
        stale.label = "stale detached writer"
        with pytest.raises(SessionRevisionConflict, match="session changed"):
            store.save(stale)
        persisted = store.get("a", "s")
        assert persisted.status == "inspected"
        assert persisted.label == original.label
        assert persisted.revision == 1 and stale.revision == 0
        with pytest.raises(SessionRevisionConflict):
            store.save(ApplicationSession(tenant_id="b", session_id="s", actor_id="u", url="https://example.invalid"))
        assert store.get("b", "s") is None
    finally:
        if engine:
            engine.dispose()


def test_memory_store_concurrent_detached_writers_have_one_winner():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    store = InMemoryApplicationSessionStore()
    store.create(ApplicationSession(tenant_id="a", session_id="s", actor_id="u", url="https://example.invalid"))
    barrier = Barrier(2)
    def write(label):
        candidate = store.get("a", "s")
        candidate.label = label
        barrier.wait(timeout=10)
        try:
            store.save(candidate)
            return True
        except SessionRevisionConflict:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, ["one", "two"])) == [False, True]
    assert store.get("a", "s").revision == 1


def test_flow_route_maps_session_revision_conflict_to_409():
    from app.modules.m02_competition_manager.application_routes import _flow_errors
    assert _flow_errors(SessionRevisionConflict("reload")).status_code == 409
