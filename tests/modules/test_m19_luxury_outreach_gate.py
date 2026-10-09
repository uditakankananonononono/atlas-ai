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


def test_unreadable_audit_fails_closed(svc, monkeypatch):
    spy = Spy(); q = LuxuryOutreachQueue(svc, spy)
    r = q.enqueue(preview(), user_id=U)
    svc.decide(r["approval_id"], ApprovalStatus.APPROVED, decided_by="owner")
    monkeypatch.setattr(svc, "audit", lambda _id: (_ for _ in ()).throw(RuntimeError("db down")))
    with pytest.raises(OutreachRefused, match="unreadable"):
        q.send(r["approval_id"], preview(), user_id=U)
    assert spy.calls == []


def test_two_queue_instances_share_one_lock_and_second_send_is_refused(svc):
    spy = Spy(); q1 = LuxuryOutreachQueue(svc, spy); q2 = LuxuryOutreachQueue(svc, spy)
    r = q1.enqueue(preview(), user_id=U)
    svc.decide(r["approval_id"], ApprovalStatus.APPROVED, decided_by="owner")
    q1.send(r["approval_id"], preview(), user_id=U)
    with pytest.raises(OutreachRefused, match="already used"):
        q2.send(r["approval_id"], preview(), user_id=U)
    assert len(spy.calls) == 1


def test_concurrent_sends_on_separate_instances_deliver_exactly_once(svc):
    import threading
    spy = Spy()
    r = LuxuryOutreachQueue(svc, spy).enqueue(preview(), user_id=U)
    svc.decide(r["approval_id"], ApprovalStatus.APPROVED, decided_by="owner")
    barrier = threading.Barrier(4); results = []
    def go():
        q = LuxuryOutreachQueue(svc, spy); barrier.wait()
        try: q.send(r["approval_id"], preview(), user_id=U); results.append("sent")
        except OutreachRefused: results.append("refused")
    ts = [threading.Thread(target=go) for _ in range(4)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert results.count("sent") == 1 and len(spy.calls) == 1
