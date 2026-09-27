from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.modules.m21_claire.persistent_journal import PersistentJournal, lexical_vector
from app.modules.m21_claire import persistent_journal_routes


def test_durable_actor_isolated_retrieval_and_correction(tmp_path):
    sessions = sessionmaker(bind=create_engine(f"sqlite:///{tmp_path/'journal.db'}"))
    a = PersistentJournal("tenant", "owner", sessions)
    b = PersistentJournal("tenant", "other", sessions)
    first = a.capture("Choose competition", "Mission fit", "scholarships", "owner-msg-123")
    a.capture("Write an essay", "Writing practice", "admissions", "owner-msg-124")
    assert a.retrieve("competition mission")[0]["id"] == first["id"]
    assert a.retrieve("competition mission")[0]["retrieval"] == "lexical_not_semantic"
    assert b.retrieve("competition") == []
    assert not b.delete(first["id"])
    correction = a.correction("formal email", "short direct email", "outreach", "owner-msg-125")
    assert correction["external_action_permission"] is False
    reopened = PersistentJournal("tenant", "owner", sessions)
    assert reopened.retrieve("competition")[0]["source_reference"] == "owner-msg-123"
    assert reopened.delete(first["id"])
    assert reopened.retrieve("competition") == []
    assert reopened.delete_all() == 2
    assert not any(lexical_vector(""))


def test_auth_routes_and_invalid_reason(tmp_path, monkeypatch):
    sessions = sessionmaker(bind=create_engine(f"sqlite:///{tmp_path/'api.db'}", connect_args={"check_same_thread": False}))
    monkeypatch.setattr(persistent_journal_routes, "SessionLocal", sessions)
    client = TestClient(app)
    url = "/api/v1/claire/journal"
    a = {"x-atlas-tenant": "t", "x-atlas-actor": "a"}
    b = {"x-atlas-tenant": "t", "x-atlas-actor": "b"}
    bad = client.post(url + "/decisions", headers=a, json={"decision": "A", "reason": "two\nlines", "source_reference": "m"})
    assert bad.status_code == 422
    saved = client.post(url + "/decisions", headers=a, json={"decision": "A grant", "reason": "fits", "source_reference": "owner-msg"})
    assert saved.status_code == 201 and saved.json()["external_action_permission"] is False
    assert client.get(url + "/decisions?query=grant", headers=b).json()["hits"] == []
    assert client.get(url + "/decisions?query=grant", headers=a).json()["hits"][0]["id"] == saved.json()["id"]
    assert client.delete(url + f"/entries/{saved.json()['id']}", headers=b).status_code == 404
    assert client.delete(url + f"/entries/{saved.json()['id']}", headers=a).status_code == 200
