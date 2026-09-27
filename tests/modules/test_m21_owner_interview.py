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
