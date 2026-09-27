from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest
from app.modules.m21_claire.owner_interview import InterviewStore, QUESTIONS


def stores(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'interview.db'}")
    sessions = sessionmaker(bind=engine)
    return (InterviewStore("one", "owner", sessions), InterviewStore("one", "other", sessions),
            InterviewStore("two", "owner", sessions))


def test_consent_first_durable_questioning_and_no_external_permission(tmp_path):
    owner, other, tenant = stores(tmp_path)
    assert owner.next_question()["status"] == "consent_required"
    with pytest.raises(PermissionError):
        owner.answer("evidence", "stop", "I prefer caution", "owner-msg-1")
    owner.consent(True)
    assert owner.next_question()["question"]["id"] == QUESTIONS[0]["id"]
    saved = owner.answer("evidence", "check_primary_source", "Verify the original", "owner-msg-1")
    with pytest.raises(ValueError, match="already answered"):
        owner.answer("evidence", "stop", "Try to overwrite", "owner-msg-2")
    assert owner.next_question()["question"]["id"] == QUESTIONS[1]["id"]
    assert owner.context()["preferences"][0]["source_reference"] == "owner-msg-1"
    assert owner.context()["external_action_permission"] is False
    assert other.context()["status"] == "consent_required"
    tenant.consent(True)
    assert tenant.context()["preferences"] == []
    assert not other.revoke(saved["id"])
    assert owner.revoke(saved["id"])
    assert owner.next_question()["question"]["id"] == "evidence"
    assert owner.context()["preferences"] == []
    owner.answer("evidence", "stop", "Updated reason", "owner-msg-3")
    owner.consent(False)
    assert owner.context()["preferences"] == []
    assert owner.delete_all() == 2  # revoked history is removed too
    owner.consent(True)
    assert owner.next_question()["answered"] == 0


def test_question_choices_validate_and_restart_persists(tmp_path):
    owner, _, _ = stores(tmp_path)
    owner.consent(True)
    with pytest.raises(ValueError):
        owner.answer("invented", "anything", "Why", "owner-msg")
    with pytest.raises(ValueError):
        owner.answer("evidence", "unknown", "Why", "owner-msg")
    with pytest.raises(ValueError):
        owner.answer("evidence", "stop", " ", "owner-msg")
    for q in QUESTIONS:
        owner.answer(q["id"], q["choices"][0], "Owner chose this", f"msg-{q['id']}")
    reopened, _, _ = stores(tmp_path)
    assert reopened.next_question()["status"] == "complete"
    assert reopened.next_question()["answered"] == len(QUESTIONS)


def test_authenticated_api_separates_actors_and_requires_consent(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.modules.m21_claire import owner_interview_routes as routes
    from app.core.database import SessionLocal
    engine = create_engine(f"sqlite:///{tmp_path/'api.db'}", connect_args={"check_same_thread": False})
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(routes, "SessionLocal", sessions)
    c = TestClient(app)
    url = "/api/v1/claire/interview"
    a = {"x-atlas-tenant": "t", "x-atlas-actor": "a"}
    b = {"x-atlas-tenant": "t", "x-atlas-actor": "b"}
    assert c.get(url + "/next", headers=a).json()["status"] == "consent_required"
    assert c.post(url + "/answers", headers=a, json={"question_id": "evidence", "choice": "stop", "reason": "caution", "source_reference": "msg"}).status_code == 403
    assert c.put(url + "/consent", headers=a, json={"enabled": True}).status_code == 200
    result = c.post(url + "/answers", headers=a, json={"question_id": "evidence", "choice": "stop", "reason": "caution", "source_reference": "msg"})
    assert result.status_code == 201
    assert c.get(url + "/context", headers=a).json()["preferences"][0]["choice"] == "stop"
    assert c.get(url + "/context", headers=b).json()["preferences"] == []
    assert c.delete(url + f"/answers/{result.json()['id']}", headers=b).status_code == 404
    assert c.delete(url + f"/answers/{result.json()['id']}", headers=a).status_code == 200
