"""Refusal receipts: nothing is sent without a recorded, exact human approval."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import ApprovalBroadcaster, Service
from app.modules.m19_idea_incubator.luxury_outreach import LuxuryOutreachQueue, OutreachRefused, refuse_sender

U = "tenant-a"


def preview(**kw):
    p = {"concept_id": "provenance_storytelling", "recipient_organization": "Example Maison", "recipient_role": "Head of Digital",
         "channel": "email", "subject": "A provenance idea for your atelier", "body": "We drafted a concept grounded in public filings. Happy to share.",
         "evidence_refs": ["s1"], "status": "pending_approval"}
    p.update(kw)
    return p


@pytest.fixture
def svc(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/g.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return Service(session_factory=sessionmaker(bind=engine, expire_on_commit=False), broadcaster=ApprovalBroadcaster())


class Spy:
    def __init__(self): self.calls = []
    def __call__(self, m): self.calls.append(m); return {"ok": True}


def test_pending_approval_refuses_and_sender_not_called(svc):
    spy = Spy(); q = LuxuryOutreachQueue(svc, spy)
    r = q.enqueue(preview(), user_id=U)
    assert r["status"] == "pending" and r["sent"] is False
    with pytest.raises(OutreachRefused, match="pending"):
        q.send(r["approval_id"], preview(), user_id=U)
    assert spy.calls == []


def test_denied_approval_refuses(svc):
    spy = Spy(); q = LuxuryOutreachQueue(svc, spy)
    r = q.enqueue(preview(), user_id=U)
    svc.decide(r["approval_id"], ApprovalStatus.DENIED, decided_by="owner")
    with pytest.raises(OutreachRefused):
        q.send(r["approval_id"], preview(), user_id=U)
    assert spy.calls == []


def test_edit_after_approval_refuses(svc):
    spy = Spy(); q = LuxuryOutreachQueue(svc, spy)
    r = q.enqueue(preview(), user_id=U)
    svc.decide(r["approval_id"], ApprovalStatus.APPROVED, decided_by="owner")
    for field, val in (("body", "A different body that was never reviewed by anyone."), ("recipient_organization", "Other Co"), ("subject", "Changed subject line")):
        with pytest.raises(OutreachRefused, match="does not match"):
            q.send(r["approval_id"], preview(**{field: val}), user_id=U)
    assert spy.calls == []


def test_approved_exact_message_sends_once_only(svc):
    spy = Spy(); q = LuxuryOutreachQueue(svc, spy)
    r = q.enqueue(preview(), user_id=U)
    svc.decide(r["approval_id"], ApprovalStatus.APPROVED, decided_by="owner")
    out = q.send(r["approval_id"], preview(), user_id=U)
    assert out["sent"] is True and len(spy.calls) == 1
    with pytest.raises(OutreachRefused, match="already used"):
        q.send(r["approval_id"], preview(), user_id=U)
    assert len(spy.calls) == 1
    with pytest.raises(OutreachRefused):
        q.send(r["approval_id"], preview(body="Something else entirely, never approved at all."), user_id=U)


def test_wrong_tenant_and_unknown_id_refuse(svc):
    spy = Spy(); q = LuxuryOutreachQueue(svc, spy)
    r = q.enqueue(preview(), user_id=U)
    svc.decide(r["approval_id"], ApprovalStatus.APPROVED, decided_by="owner")
    with pytest.raises(OutreachRefused):
        q.send(r["approval_id"], preview(), user_id="tenant-b")
    with pytest.raises(OutreachRefused):
        q.send("00000000-0000-0000-0000-000000000000", preview(), user_id=U)
    assert spy.calls == []


def test_default_adapter_refuses_even_when_approved(svc):
    q = LuxuryOutreachQueue(svc)
    r = q.enqueue(preview(), user_id=U)
    svc.decide(r["approval_id"], ApprovalStatus.APPROVED, decided_by="owner")
    with pytest.raises(OutreachRefused, match="no send adapter"):
        q.send(r["approval_id"], preview(), user_id=U)


def test_unvalidated_preview_cannot_be_queued(svc):
    q = LuxuryOutreachQueue(svc)
    with pytest.raises(ValueError):
        q.enqueue(preview(status="draft"), user_id=U)
    with pytest.raises(ValueError):
        q.enqueue({"subject": "x"}, user_id=U)
