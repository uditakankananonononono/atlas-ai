"""Offline tests for approval-verified delivery and the delivery audit."""

import asyncio
from datetime import datetime, timezone
from email.message import EmailMessage

import pytest

from app.core.models import ApprovalRequest
from app.modules.m05_outreach_manager.campaigns import CampaignService, InMemoryCampaignRepository
from app.modules.m05_outreach_manager.delivery import (
    ApprovalView,
    DeliveryApprovalError,
    DeliveryReceipt,
    DeliverySendError,
    DeliveryService,
    SmtpMailSender,
)
from app.modules.m05_outreach_manager.schemas import ContactCreate
from app.modules.m05_outreach_manager.service import InMemoryContactRepository, Service


class ApprovalSpy:
    def __init__(self) -> None:
        self.items: list[ApprovalRequest] = []

    def put(self, item: ApprovalRequest) -> ApprovalRequest:
        self.items.append(item)
        return item


class FakeGate:
    def __init__(self, views: dict[str, ApprovalView]) -> None:
        self.views = views

    def get(self, approval_id: str) -> ApprovalView | None:
        return self.views.get(approval_id)


class FakeSender:
    name = "fake"

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[dict] = []
        self.fail = fail

    async def send(self, *, to, subject, body, from_account=None) -> DeliveryReceipt:
        self.calls.append({"to": to, "subject": subject, "body": body})
        if self.fail:
            raise DeliverySendError("SMTP send failed: SMTPRecipientsRefused")
        return DeliveryReceipt(provider_message_id="pm-1", thread_id="thread-1")


def make_world(now):
    contacts = InMemoryContactRepository()
    campaigns = InMemoryCampaignRepository()
    approvals = ApprovalSpy()
    service = CampaignService(campaigns, contacts, approvals, clock=lambda: now)
    contact_service = Service(contacts, approvals, scholar=None)
    contact = contact_service.create_contact(
        ContactCreate(project_id="atlas", name="Dr. Rao", email="rao@example.edu")
    )
    campaign = service.create_campaign(project_id="atlas", name="C", goal="Find supervisors")
    draft = service.add_draft(campaign.id, contact.id, subject="Hello", body="Body text")
    approval = service.submit_for_approval(draft.id)
    service.record_decision(draft.id, approved=True, actor="udita")
    return service, approvals, contact, campaign, draft, approval


def gate_for(approval, status="approved"):
    return FakeGate(
        {
            approval.id: ApprovalView(
                id=approval.id, status=status, action_type=approval.action_type, payload=approval.payload
            )
        }
    )


def test_approved_message_sends_and_audits_delivery():
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    service, approvals, contact, campaign, draft, approval = make_world(now)
    sender = FakeSender()
    delivery = DeliveryService(service, gate_for(approval), sender)

    sent = asyncio.run(delivery.send_approved(draft.id))

    assert sent.status == "sent" and sent.thread_id == "thread-1"
    assert sender.calls == [{"to": "rao@example.edu", "subject": "Hello", "body": "Body text"}]
    audit = delivery.delivery_audit(draft.id)
    assert [event.event for event in audit] == ["sent"]

    report = delivery.delivery_report(campaign.id)
    assert report["counts"] == {"sent": 1}
    assert report["messages"][0]["last_delivery_event"] == "sent"
    assert report["messages"][0]["sent_at"] is not None


def test_unapproved_module_zero_decision_blocks_send():
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    service, approvals, contact, campaign, draft, approval = make_world(now)
    sender = FakeSender()
    delivery = DeliveryService(service, gate_for(approval, status="denied"), sender)

    with pytest.raises(DeliveryApprovalError, match="denied"):
        asyncio.run(delivery.send_approved(draft.id))
    assert sender.calls == []
    assert service.get_message(draft.id).status == "approved"


def test_missing_approval_blocks_send():
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    service, approvals, contact, campaign, draft, approval = make_world(now)
    delivery = DeliveryService(service, FakeGate({}), FakeSender())
    with pytest.raises(DeliveryApprovalError, match="does not exist"):
        asyncio.run(delivery.send_approved(draft.id))


def test_content_changed_after_approval_is_blocked_and_audited():
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    service, approvals, contact, campaign, draft, approval = make_world(now)
    tampered = dict(approval.payload)
    tampered["body"] = "EDITED AFTER APPROVAL"
    gate = FakeGate(
        {approval.id: ApprovalView(id=approval.id, status="approved", action_type=approval.action_type, payload=tampered)}
    )
    sender = FakeSender()
    delivery = DeliveryService(service, gate, sender)

    with pytest.raises(DeliveryApprovalError, match="re-approval required"):
        asyncio.run(delivery.send_approved(draft.id))

    assert sender.calls == []
    assert service.get_message(draft.id).status == "approved"
    events = [event.event for event in delivery.delivery_audit(draft.id)]
    assert events == ["blocked_payload_mismatch"]


def test_recipient_changed_after_approval_is_blocked():
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    service, approvals, contact, campaign, draft, approval = make_world(now)
    tampered = dict(approval.payload)
    tampered["recipient"] = "someone-else@example.edu"
    gate = FakeGate(
        {approval.id: ApprovalView(id=approval.id, status="approved", action_type=approval.action_type, payload=tampered)}
    )
    delivery = DeliveryService(service, gate, FakeSender())
    with pytest.raises(DeliveryApprovalError, match="re-approval required"):
        asyncio.run(delivery.send_approved(draft.id))


def test_sender_failure_marks_failed_and_audits():
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    service, approvals, contact, campaign, draft, approval = make_world(now)
    delivery = DeliveryService(service, gate_for(approval), FakeSender(fail=True))

    with pytest.raises(DeliverySendError):
        asyncio.run(delivery.send_approved(draft.id))

    assert service.get_message(draft.id).status == "failed"
    assert [event.event for event in delivery.delivery_audit(draft.id)] == ["failed"]

    service.record_decision(draft.id, approved=True)
    sender = FakeSender()
    delivery = DeliveryService(service, gate_for(approval), sender)
    asyncio.run(delivery.send_approved(draft.id))
    assert service.get_message(draft.id).status == "sent"


def test_smtp_sender_builds_and_transmits_real_message():
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            sent.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            sent.append(("starttls",))

        def login(self, username, password):
            sent.append(("login", username))

        def send_message(self, message, from_addr, to_addrs):
            assert isinstance(message, EmailMessage)
            sent.append(("send", message["From"], to_addrs[0], message["Subject"], message.get_content().strip()))

    sender = SmtpMailSender(
        host="smtp.example.com",
        from_address="udita@example.com",
        username="udita",
        password="secret",
        smtp_factory=FakeSMTP,
    )
    receipt = asyncio.run(sender.send(to="rao@example.edu", subject="Hi", body="Body"))

    assert ("connect", "smtp.example.com", 587) in sent
    assert ("starttls",) in sent
    assert ("login", "udita") in sent
    assert ("send", "udita@example.com", "rao@example.edu", "Hi", "Body") in sent
    assert receipt.provider_message_id
    assert "secret" not in str(receipt)
