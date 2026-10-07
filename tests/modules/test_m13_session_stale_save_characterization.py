"""Current session persistence gap, not acceptance of CAS or safe submission.

Two detached readers can overwrite each other. This deliberately describes the
pinned reconstruction implementation and must change when a CAS fix lands.
It calls no browser, approval, device, authentication or submission path.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m13_browser_agent.application_flow import ApplicationSession
from app.modules.m13_browser_agent.application_store import (
    InMemoryApplicationSessionStore, SQLApplicationSessionStore,
)


@pytest.mark.parametrize("kind", ["memory", "sql"])
def test_current_store_accepts_stale_detached_save(tmp_path, kind):
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
        store.save(stale)
        persisted = store.get("a", "s")
        assert persisted.status == original.status  # the newer state is lost
        assert persisted.label == "stale detached writer"
        assert store.get("b", "s") is None
    finally:
        if engine:
            engine.dispose()
