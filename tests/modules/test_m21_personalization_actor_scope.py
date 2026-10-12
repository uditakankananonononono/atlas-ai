"""Actor scoping of the base PersonalizationRepository and export/delete parity."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m21_claire.personalization import PersonalizationRepository, ScopedPersonalizationRepository


def _sessions(tmp_path):
    e = create_engine(f"sqlite:///{tmp_path/'s.db'}")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)


def test_base_repository_retrieve_does_not_return_another_actors_rows(tmp_path):
    s = _sessions(tmp_path)
    alice = PersonalizationRepository("t", s, actor_id="alice")
    bob = PersonalizationRepository("t", s, actor_id="bob")
    did = alice.add("decision", {"decision": "alice private", "reason": "r", "context": "c"}, [1, 0])
    alice.add("correction", {"original": "x", "correction": "y", "context": "c"}, [1, 0])
    alice.add("reasoning_note", {"title": "t", "owner_authored_note": "n"}, [1, 0])
    alice.add_decision_outcome(did, {"outcome": "o", "rating": "better", "lesson": "l"})
    assert len(alice.retrieve([1, 0])) == 3
    assert bob.retrieve([1, 0]) == []
    assert alice.retrieve([1, 0])[0]["content"]["outcomes"][0]["outcome"] == "o"


def test_base_repository_outcomes_and_history_are_actor_scoped(tmp_path):
    s = _sessions(tmp_path)
    alice = PersonalizationRepository("t", s, actor_id="alice")
    bob = PersonalizationRepository("t", s, actor_id="bob")
    did = alice.add("decision", {"decision": "d", "reason": "r", "context": "c"}, [1, 0])
    with pytest.raises(KeyError):
        bob.add_decision_outcome(did, {"outcome": "o", "rating": "worse", "lesson": "l"})
    with pytest.raises(KeyError):
        bob.decision_history(did)
    alice.add_decision_outcome(did, {"outcome": "o", "rating": "better", "lesson": "l"})
    assert [x["outcome"] for x in alice.decision_history(did)["outcomes"]] == ["o"]


def test_base_repository_writes_record_the_actor_and_scoped_class_reads_them(tmp_path):
    s = _sessions(tmp_path)
    base = PersonalizationRepository("t", s, actor_id="alice")
    base.add("decision", {"decision": "d", "reason": "r", "context": "c"}, [1, 0])
    base.add("decision", {"decision": "forged", "reason": "r", "context": "c", "actor_id": "bob"}, [1, 0])
    assert len(ScopedPersonalizationRepository("t", "alice", s).export_data()["records"]["m21_decisions"]) == 2
    assert ScopedPersonalizationRepository("t", "bob", s).export_data()["records"]["m21_decisions"] == []


def test_scoped_retrieve_is_actor_scoped_through_the_inherited_path(tmp_path):
    s = _sessions(tmp_path)
    ScopedPersonalizationRepository("t", "alice", s).add_decision("d", "r", "c", [1, 0])
    assert ScopedPersonalizationRepository("t", "bob", s).retrieve([1, 0]) == []
    assert len(ScopedPersonalizationRepository("t", "alice", s).retrieve([1, 0])) == 1


def test_export_includes_every_table_that_delete_removes(tmp_path):
    s = _sessions(tmp_path)
    r = ScopedPersonalizationRepository("t", "alice", s)
    did = r.add_decision("d", "r", "c", [1, 0])
    r.add_decision_outcome(did, {"outcome": "kept", "rating": "better", "lesson": "l"})
    exported = r.export_data()["records"]
    assert [x["outcome"] for x in exported["m21_decision_outcomes"]] == ["kept"]
    deleted = r.delete_data()["deleted"]
    assert deleted["m21_decision_outcomes"] == 1


def test_export_keys_cover_delete_keys(tmp_path):
    s = _sessions(tmp_path)
    r = ScopedPersonalizationRepository("t", "alice", s)
    deleted = r.delete_data()["deleted"]
    table_keys = set(deleted)
    assert table_keys and table_keys <= set(r.export_data()["records"])


def test_personalization_route_passes_authenticated_actor(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.modules.m21_claire import personalization_routes as pr
    s = _sessions(tmp_path)
    monkeypatch.setattr(pr, "PersonalizationRepository", lambda tenant_id, actor_id="owner": PersonalizationRepository(tenant_id, s, actor_id=actor_id))
    c = TestClient(app)
    h = lambda actor: {"x-atlas-tenant": "t", "x-atlas-actor": actor}
    assert c.post("/api/v1/claire/personalization/memories", headers=h("alice"), json={"kind": "decision", "data": {"decision": "d", "reason": "r", "context": "c"}, "embedding": [1, 0]}).status_code == 201
    assert len(c.post("/api/v1/claire/personalization/retrieve", headers=h("alice"), json={"query_embedding": [1, 0]}).json()) == 1
    assert c.post("/api/v1/claire/personalization/retrieve", headers=h("bob"), json={"query_embedding": [1, 0]}).json() == []
