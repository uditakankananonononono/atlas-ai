"""Offline tests for the campaign draft/review/follow-up state machine."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.core.models import ApprovalRequest
from app.modules.m05_outreach_manager.campaigns import (
    CampaignService,
    CampaignStateError,
    InMemoryCampaignRepository,
    MessageNotFoundError,
)
from app.modules.m05_outreach_manager.schemas import ContactCreate
from app.modules.m05_outreach_manager.service import InMemoryContactRepository, Service


class ApprovalSpy:
    def __init__(self) -> None:
        self.items: list[ApprovalRequest] = []

    def put(self, item: ApprovalRequest, *, user_id=None) -> ApprovalRequest:
        self.items.append(item)
        return item


def make_service(now):
    contacts = InMemoryContactRepository()
    campaigns = InMemoryCampaignRepository()
    approvals = ApprovalSpy()
    service = CampaignService(campaigns, contacts, approvals, clock=lambda: now[0])
    return service, campaigns, contacts, approvals


def make_setup(now):
    service, campaigns, contacts, approvals = make_service(now)
    contact_service = Service(contacts, approvals, scholar=None)
    contact = contact_service.create_contact(
        ContactCreate(project_id="atlas", name="Dr. Rao", email="rao@example.edu")
    )
    campaign = service.create_campaign(
        project_id="atlas",
        name="Summer supervisors",
        goal="Find a summer research supervisor in spatial transcriptomics",
        follow_up_window_days=5,
        max_follow_ups=2,
    )
    return service, campaigns, approvals, contact, campaign


def test_full_review_flow_is_audited():
    now = [datetime(2026, 9, 20, tzinfo=timezone.utc)]
    service, campaigns, approvals, contact, campaign = make_setup(now)
    draft = service.add_draft(campaign.id, contact.id, subject="Hello", body="Body text")
    assert draft.status == "draft" and draft.sequence == 1

    approval = service.submit_for_approval(draft.id)
    assert approval.module_id == 5
    assert approval.action_type == "send_outreach_email"
    assert approval.payload["recipient"] == "rao@example.edu"
    assert approval.payload["message_id"] == draft.id
    assert campaigns.get_message(draft.id).status == "pending_approval"
    assert campaigns.get_message(draft.id).approval_id == approval.id

    service.record_decision(draft.id, approved=True, actor="udita")
    assert campaigns.get_message(draft.id).status == "approved"

    sent = service.mark_sent(draft.id, thread_id="thread-1", provider_message_id="pm-1")
    assert sent.status == "sent" and sent.thread_id == "thread-1" and sent.sent_at == now[0]

    events = [row.event for row in service.message_events(draft.id)]
    assert events == ["drafted", "submitted_for_approval", "approved", "sent"]


def test_denied_message_cannot_be_sent():
    now = [datetime(2026, 9, 20, tzinfo=timezone.utc)]
    service, campaigns, approvals, contact, campaign = make_setup(now)
    draft = service.add_draft(campaign.id, contact.id, subject="Hi", body="Body")
    service.submit_for_approval(draft.id)
    service.record_decision(draft.id, approved=False, actor="udita")
    assert campaigns.get_message(draft.id).status == "denied"
    with pytest.raises(CampaignStateError, match="denied to sent"):
        service.mark_sent(draft.id)


def test_unapproved_message_cannot_be_marked_sent():
    now = [datetime(2026, 9, 20, tzinfo=timezone.utc)]
    service, campaigns, approvals, contact, campaign = make_setup(now)
    draft = service.add_draft(campaign.id, contact.id, subject="Hi", body="Body")
    with pytest.raises(CampaignStateError, match="draft to sent"):
        service.mark_sent(draft.id)
    service.submit_for_approval(draft.id)
    with pytest.raises(CampaignStateError, match="pending_approval to sent"):
        service.mark_sent(draft.id)


def test_submit_requires_contact_email():
    now = [datetime(2026, 9, 20, tzinfo=timezone.utc)]
    service, campaigns, contacts, approvals = make_service(now)
    contact_service = Service(contacts, approvals, scholar=None)
    contact = contact_service.create_contact(ContactCreate(project_id="p", name="No Email"))
    campaign = service.create_campaign(project_id="p", name="C", goal="Goal here")
    draft = service.add_draft(campaign.id, contact.id, subject="Hi", body="Body")
    with pytest.raises(CampaignStateError, match="no verified email"):
        service.submit_for_approval(draft.id)
    assert approvals.items == []


def test_initial_message_is_unique_per_contact():
    now = [datetime(2026, 9, 20, tzinfo=timezone.utc)]
    service, campaigns, approvals, contact, campaign = make_setup(now)
    service.add_draft(campaign.id, contact.id, subject="Hi", body="Body")
    with pytest.raises(CampaignStateError, match="initial message already exists"):
        service.add_draft(campaign.id, contact.id, subject="Again", body="Body")


def test_reply_cancels_pending_follow_ups():
    now = [datetime(2026, 9, 20, tzinfo=timezone.utc)]
    service, campaigns, approvals, contact, campaign = make_setup(now)
    first = service.add_draft(campaign.id, contact.id, subject="Hi", body="Body")
    service.submit_for_approval(first.id)
    service.record_decision(first.id, approved=True)
    service.mark_sent(first.id, thread_id="t-1")
    now[0] = now[0] + timedelta(days=6)  # past the campaign follow-up window; cadence refuses earlier
    follow = service.add_draft(
        campaign.id, contact.id, subject="Following up", body="Gentle nudge", kind="follow_up"
    )
    service.submit_for_approval(follow.id)

    service.record_reply(first.id, thread_id="t-1", snippet="Thanks, happy to chat")

    assert campaigns.get_message(first.id).status == "replied"
    assert campaigns.get_message(follow.id).status == "cancelled"
    events = [row.event for row in service.message_events(follow.id)]
    assert events[-1] == "cancelled_after_reply"


def test_due_follow_up_after_window_and_drafting():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    now = [start]
    service, campaigns, approvals, contact, campaign = make_setup(now)
    first = service.add_draft(campaign.id, contact.id, subject="Hi", body="Original body")
    service.submit_for_approval(first.id)
    service.record_decision(first.id, approved=True)
    service.mark_sent(first.id, thread_id="t-1")

    now[0] = start + timedelta(days=3)
    assert service.due_follow_ups() == []

    now[0] = start + timedelta(days=6)
    due = service.due_follow_ups()
    assert [item.id for item in due] == [first.id]

    async def fake_generate(prompt, provider, model):
        assert "Days without a detected reply: 6" in prompt
        assert "Original subject: Hi" in prompt
        return model or "test-model", "Subject: Re: Hi\nJust checking in."

    follow = asyncio.run(service.draft_follow_up(first.id, fake_generate))
    assert follow.kind == "follow_up"
    assert follow.sequence == 2
    assert follow.status == "draft"
    assert follow.subject == "Re: Hi"

    assert service.due_follow_ups() == []


def test_follow_up_limit_is_enforced():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    now = [start]
    service, campaigns, approvals, contact, campaign = make_setup(now)
    first = service.add_draft(campaign.id, contact.id, subject="Hi", body="Body")
    service.submit_for_approval(first.id)
    service.record_decision(first.id, approved=True)
    service.mark_sent(first.id)
    second = service.add_draft(campaign.id, contact.id, subject="F1", body="B", kind="follow_up")
    third = service.add_draft(campaign.id, contact.id, subject="F2", body="B", kind="follow_up")
    assert second.sequence == 2 and third.sequence == 3
    with pytest.raises(CampaignStateError, match="follow-up limit"):
        service.add_draft(campaign.id, contact.id, subject="F3", body="B", kind="follow_up")


def test_due_follow_up_respects_reply_and_paused_campaign():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    now = [start]
    service, campaigns, approvals, contact, campaign = make_setup(now)
    first = service.add_draft(campaign.id, contact.id, subject="Hi", body="Body")
    service.submit_for_approval(first.id)
    service.record_decision(first.id, approved=True)
    service.mark_sent(first.id)
    now[0] = start + timedelta(days=30)

    service.set_campaign_status(campaign.id, "paused")
    assert service.due_follow_ups() == []
    service.set_campaign_status(campaign.id, "active")
    assert len(service.due_follow_ups()) == 1

    service.record_reply(first.id)
    assert service.due_follow_ups() == []


def test_not_due_message_cannot_draft_follow_up():
    now = [datetime(2026, 9, 20, tzinfo=timezone.utc)]
    service, campaigns, approvals, contact, campaign = make_setup(now)
    first = service.add_draft(campaign.id, contact.id, subject="Hi", body="Body")

    async def fake_generate(prompt, provider, model):
        raise AssertionError("must not be called")

    with pytest.raises(CampaignStateError, match="not due"):
        asyncio.run(service.draft_follow_up(first.id, fake_generate))


def test_unknown_message_raises():
    now = [datetime(2026, 9, 20, tzinfo=timezone.utc)]
    service, _, _, _ = make_service(now)
    with pytest.raises(MessageNotFoundError):
        service.record_decision("nope", approved=True)

class CallbackApprovalSpy(ApprovalSpy):
    def __init__(self):
        super().__init__()
        self.callbacks = {}

    def put(self, item, *, user_id=None):
        stored = item.model_copy(update={"id": "module-zero-id"})
        self.items.append(stored)
        return stored

    def register_callback(self, item_id, callback):
        self.callbacks[item_id] = callback


def test_module_zero_decision_callback_uses_stored_id_and_updates_message():
    now = [datetime(2026, 9, 20, tzinfo=timezone.utc)]
    contacts = InMemoryContactRepository()
    campaigns = InMemoryCampaignRepository()
    approvals = CallbackApprovalSpy()
    service = CampaignService(campaigns, contacts, approvals, clock=lambda: now[0])
    contact = Service(contacts, approvals, scholar=None).create_contact(
        ContactCreate(project_id="atlas", name="Dr. Rao", email="rao@example.edu")
    )
    campaign = service.create_campaign(project_id="atlas", name="C", goal="Find a supervisor")
    message = service.add_draft(campaign.id, contact.id, subject="Hi", body="Body")

    approval = service.submit_for_approval(message.id)
    assert approval.id == "module-zero-id"
    assert campaigns.get_message(message.id).approval_id == "module-zero-id"
    approvals.callbacks[approval.id]({"status": "approved", "approved_by": "udita"})
    assert campaigns.get_message(message.id).status == "approved"


def test_corrupt_sent_message_without_timestamp_fails_explicitly():
    """A damaged durable record must not become a TypeError or vanish under -O."""
    now = [datetime(2026, 9, 20, tzinfo=timezone.utc)]
    service, campaigns, approvals, contact, campaign = make_setup(now)
    first = service.add_draft(campaign.id, contact.id, subject="Hi", body="Body")
    service.submit_for_approval(first.id)
    service.record_decision(first.id, approved=True)
    service.mark_sent(first.id)
    campaigns._messages[first.id].sent_at = None
    with pytest.raises(CampaignStateError, match="has no sent_at timestamp"):
        service.due_follow_ups()
