"""Campaign state machine: draft -> review -> send -> reply/follow-up.

Ledger rows CRM-135 (PR outreach planning's execution half), CRM-138
(approved drafting/sending state), CRM-139 (email outreach routing), and
the spec's Follow-up Automation: if no reply is detected inside a
configurable window, a follow-up is drafted and queued for approval.
Nothing here ever sends: messages move to ``sent`` only through an
explicit ``mark_sent`` call made by the approval-verified delivery layer,
and follow-ups come back as drafts that need their own approval.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.models import ApprovalRequest

from .service import ApprovalSink, ContactNotFoundError, ContactRepository

MODULE_ID = 5

CampaignStatus = Literal["active", "paused", "completed"]
MessageStatus = Literal[
    "draft",
    "pending_approval",
    "approved",
    "denied",
    "sent",
    "replied",
    "bounced",
    "failed",
    "cancelled",
]
MessageKind = Literal["initial", "follow_up", "survey", "proposal", "pr_pitch"]

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"pending_approval", "cancelled"},
    "pending_approval": {"approved", "denied", "cancelled"},
    "approved": {"sent", "cancelled", "failed"},
    "denied": set(),
    "sent": {"replied", "bounced", "failed"},
    "replied": set(),
    "bounced": set(),
    "failed": {"approved"},
    "cancelled": set(),
}

KIND_TO_ACTION_TYPE: dict[str, str] = {
    "initial": "send_outreach_email",
    "follow_up": "send_follow_up",
    "survey": "send_micro_survey",
    "proposal": "share_proposal",
    "pr_pitch": "send_pr_pitch",
}


class CampaignError(RuntimeError):
    """Base class for campaign failures."""


class CampaignNotFoundError(LookupError):
    """Raised when a campaign id does not exist."""


class MessageNotFoundError(LookupError):
    """Raised when a message id does not exist."""


class CampaignStateError(CampaignError):
    """Raised when a state transition is not allowed."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Campaign(BaseModel):
    """A scoped outreach effort over many contacts."""

    id: str
    project_id: str
    name: str = Field(min_length=1, max_length=200)
    goal: str = Field(min_length=3, max_length=2000)
    audience: str = Field(default="professor", max_length=40)
    status: CampaignStatus = "active"
    max_follow_ups: int = Field(default=2, ge=0, le=10)
    follow_up_window_days: int = Field(default=5, ge=1, le=90)
    created_at: datetime
    updated_at: datetime


class OutreachMessage(BaseModel):
    """One message in a campaign, with full review/delivery state."""

    id: str
    campaign_id: str
    contact_id: str
    sequence: int = Field(ge=1)
    kind: MessageKind = "initial"
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=20_000)
    status: MessageStatus = "draft"
    approval_id: str | None = None
    provider: str | None = None
    model: str | None = None
    thread_id: str | None = None
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    version: int = 1


class MessageEvent(BaseModel):
    """One append-only audit event on a message."""

    message_id: str
    event: str
    actor: str | None = None
    at: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class CampaignRepository(Protocol):
    """Storage boundary for campaigns, messages, and their audit events."""

    def save_campaign(self, campaign: Campaign) -> Campaign: ...
    def get_campaign(self, campaign_id: str) -> Campaign | None: ...
    def list_campaigns(self, project_id: str | None = None) -> list[Campaign]: ...
    def save_message(self, message: OutreachMessage, event: MessageEvent) -> OutreachMessage: ...
    def get_message(self, message_id: str) -> OutreachMessage | None: ...
    def list_messages(
        self,
        campaign_id: str | None = None,
        contact_id: str | None = None,
        status: MessageStatus | None = None,
    ) -> list[OutreachMessage]: ...
    def events(self, message_id: str) -> list[MessageEvent]: ...


class InMemoryCampaignRepository:
    """Small development repository; production injects SqlCampaignRepository."""

    def __init__(self) -> None:
        self._campaigns: dict[str, Campaign] = {}
        self._messages: dict[str, OutreachMessage] = {}
        self._events: dict[str, list[MessageEvent]] = {}

    def save_campaign(self, campaign: Campaign) -> Campaign:
        stored = campaign.model_copy(deep=True)
        self._campaigns[stored.id] = stored
        return stored.model_copy(deep=True)

    def get_campaign(self, campaign_id: str) -> Campaign | None:
        item = self._campaigns.get(campaign_id)
        return item.model_copy(deep=True) if item else None

    def list_campaigns(self, project_id: str | None = None) -> list[Campaign]:
        items = self._campaigns.values()
        if project_id is not None:
            items = [item for item in items if item.project_id == project_id]
        return [item.model_copy(deep=True) for item in items]

    def save_message(self, message: OutreachMessage, event: MessageEvent) -> OutreachMessage:
        stored = message.model_copy(deep=True)
        self._messages[stored.id] = stored
        self._events.setdefault(stored.id, []).append(event.model_copy(deep=True))
        return stored.model_copy(deep=True)

    def get_message(self, message_id: str) -> OutreachMessage | None:
        item = self._messages.get(message_id)
        return item.model_copy(deep=True) if item else None

    def list_messages(
        self,
        campaign_id: str | None = None,
        contact_id: str | None = None,
        status: MessageStatus | None = None,
    ) -> list[OutreachMessage]:
        items = self._messages.values()
        if campaign_id is not None:
            items = [item for item in items if item.campaign_id == campaign_id]
        if contact_id is not None:
            items = [item for item in items if item.contact_id == contact_id]
        if status is not None:
            items = [item for item in items if item.status == status]
        return [item.model_copy(deep=True) for item in items]

    def events(self, message_id: str) -> list[MessageEvent]:
        return [event.model_copy(deep=True) for event in self._events.get(message_id, [])]


GenerateFn = Callable[[str, str, str | None], Awaitable[tuple[str, str]]]


class CampaignService:
    """Drive campaigns through review, delivery, and follow-up states."""

    def __init__(
        self,
        campaigns: CampaignRepository,
        contacts: ContactRepository,
        approval_sink: ApprovalSink,
        clock: Callable[[], datetime] | None = None,
        tenant_id: str = "local",
    ) -> None:
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        self.tenant_id = tenant_id.strip()
        self.campaigns = campaigns
        self.contacts = contacts
        self.approval_sink = approval_sink
        self._clock = clock or _utcnow

    # --- campaign lifecycle -------------------------------------------------

    def create_campaign(
        self,
        *,
        project_id: str,
        name: str,
        goal: str,
        audience: str = "professor",
        max_follow_ups: int = 2,
        follow_up_window_days: int = 5,
    ) -> Campaign:
        now = self._clock()
        return self.campaigns.save_campaign(
            Campaign(
                id=str(uuid4()),
                project_id=project_id,
                name=name,
                goal=goal,
                audience=audience,
                status="active",
                max_follow_ups=max_follow_ups,
                follow_up_window_days=follow_up_window_days,
                created_at=now,
                updated_at=now,
            )
        )

    def get_campaign(self, campaign_id: str) -> Campaign:
        campaign = self.campaigns.get_campaign(campaign_id)
        if campaign is None:
            raise CampaignNotFoundError(campaign_id)
        return campaign

    def set_campaign_status(self, campaign_id: str, status: CampaignStatus) -> Campaign:
        campaign = self.get_campaign(campaign_id)
        return self.campaigns.save_campaign(
            campaign.model_copy(update={"status": status, "updated_at": self._clock()})
        )

    # --- message lifecycle --------------------------------------------------

    def add_draft(
        self,
        campaign_id: str,
        contact_id: str,
        *,
        subject: str,
        body: str,
        kind: MessageKind = "initial",
        provider: str | None = None,
        model: str | None = None,
    ) -> OutreachMessage:
        campaign = self.get_campaign(campaign_id)
        if campaign.status != "active":
            raise CampaignStateError(f"cannot add drafts to a {campaign.status} campaign")
        self._contact(contact_id)
        siblings = self.campaigns.list_messages(campaign_id=campaign_id, contact_id=contact_id)
        sequence = (max((item.sequence for item in siblings), default=0)) + 1
        if kind == "initial" and siblings:
            raise CampaignStateError("an initial message already exists for this contact")
        if kind == "follow_up" and sequence > campaign.max_follow_ups + 1:
            raise CampaignStateError("campaign follow-up limit reached")
        now = self._clock()
        message = OutreachMessage(
            id=str(uuid4()),
            campaign_id=campaign_id,
            contact_id=contact_id,
            sequence=sequence,
            kind=kind,
            subject=subject,
            body=body,
            status="draft",
            provider=provider,
            model=model,
            created_at=now,
            updated_at=now,
            version=1,
        )
        return self.campaigns.save_message(
            message, self._event(message, "drafted", {"sequence": sequence, "kind": kind})
        )

    def get_message(self, message_id: str) -> OutreachMessage:
        """Return one message or raise MessageNotFoundError."""
        return self._message(message_id)

    def submit_for_approval(self, message_id: str) -> ApprovalRequest:
        """Move a draft to pending_approval with a payload-bound Module 0 request."""
        message = self._message(message_id)
        contact = self._contact(message.contact_id)
        if not contact.email:
            raise CampaignStateError("contact has no verified email address")
        approval = ApprovalRequest(
            id=str(uuid4()),
            module_id=MODULE_ID,
            action_type=KIND_TO_ACTION_TYPE[message.kind],
            payload={
                "tenant_id": self.tenant_id,
                "message_id": message.id,
                "campaign_id": message.campaign_id,
                "contact_id": contact.id,
                "recipient": str(contact.email),
                "subject": message.subject,
                "body": message.body,
            },
        )
        if "pending_approval" not in _ALLOWED_TRANSITIONS[message.status]:
            raise CampaignStateError(f"cannot move message from {message.status} to pending_approval")
        approval = self.approval_sink.put(approval, user_id=self.tenant_id)
        register_callback = getattr(self.approval_sink, "register_callback", None)
        if register_callback is not None:
            def mirror_decision(view: dict[str, Any]) -> None:
                status = view["status"]
                status_value = status.value if hasattr(status, "value") else str(status)
                if status_value in {"approved", "denied"}:
                    self.record_decision(
                        message.id, status_value == "approved", actor=view.get("approved_by")
                    )
            register_callback(approval.id, mirror_decision)
        self.campaigns.save_message(
            message.model_copy(
                update={
                    "status": "pending_approval",
                    "approval_id": approval.id,
                    "updated_at": self._clock(),
                    "version": message.version + 1,
                }
            ),
            self._event(
                message,
                "submitted_for_approval",
                {"approval_id": approval.id, "action_type": approval.action_type},
            ),
        )
        return approval

    def record_decision(self, message_id: str, approved: bool, actor: str | None = None) -> OutreachMessage:
        """Mirror a Module 0 decision onto the message. Denial is terminal."""
        message = self._message(message_id)
        if approved:
            return self._transition(message, "approved", "approved", {}, actor=actor)
        return self._transition(message, "denied", "denied", {}, actor=actor)

    def mark_sent(
        self,
        message_id: str,
        *,
        thread_id: str | None = None,
        provider_message_id: str | None = None,
    ) -> OutreachMessage:
        """Record actual delivery. Only the delivery layer may call this,
        and only after it verified the bound approval; the state machine
        independently refuses anything that was never approved."""
        message = self._message(message_id)
        if "sent" not in _ALLOWED_TRANSITIONS[message.status]:
            raise CampaignStateError(f"cannot move message from {message.status} to sent")
        update: dict[str, Any] = {
            "status": "sent",
            "sent_at": self._clock(),
            "updated_at": self._clock(),
            "version": message.version + 1,
        }
        if thread_id:
            update["thread_id"] = thread_id
        return self.campaigns.save_message(
            message.model_copy(update=update),
            self._event(
                message,
                "sent",
                {"thread_id": thread_id, "provider_message_id": provider_message_id},
            ),
        )

    def record_reply(
        self,
        message_id: str,
        *,
        thread_id: str | None = None,
        snippet: str | None = None,
    ) -> OutreachMessage:
        """Record a detected reply and cancel pending follow-ups.

        Called by the Email Assistant's thread monitoring - provider
        thread metadata only, never tracking pixels.
        """
        message = self._message(message_id)
        replied = self._transition(
            message, "replied", "replied", {"thread_id": thread_id, "snippet": snippet}
        )
        for sibling in self.campaigns.list_messages(
            campaign_id=message.campaign_id, contact_id=message.contact_id
        ):
            if sibling.sequence > message.sequence and sibling.status in {
                "draft",
                "pending_approval",
                "approved",
            }:
                self._transition(
                    sibling,
                    "cancelled",
                    "cancelled_after_reply",
                    {"replied_message_id": message.id},
                )
        return replied

    def record_delivery_failure(self, message_id: str, *, reason: str, bounced: bool = False) -> OutreachMessage:
        message = self._message(message_id)
        status: MessageStatus = "bounced" if bounced else "failed"
        return self._transition(message, status, status, {"reason": reason})

    # --- follow-up automation -------------------------------------------------

    def due_follow_ups(self) -> list[OutreachMessage]:
        """Sent messages whose no-reply window elapsed and can still follow up."""
        now = self._clock()
        due: list[OutreachMessage] = []
        for message in self.campaigns.list_messages(status="sent"):
            campaign = self.get_campaign(message.campaign_id)
            if campaign.status != "active":
                continue
            if message.sequence > campaign.max_follow_ups:
                continue
            if message.sent_at is None:
                raise CampaignStateError(
                    f"sent message {message.id!r} has no sent_at timestamp"
                )
            sent_at = message.sent_at
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
            if sent_at + timedelta(days=campaign.follow_up_window_days) > now:
                continue
            later = [
                item
                for item in self.campaigns.list_messages(
                    campaign_id=message.campaign_id, contact_id=message.contact_id
                )
                if item.sequence > message.sequence and item.status != "cancelled"
            ]
            if later:
                continue
            due.append(message)
        return due

    async def draft_follow_up(
        self,
        message_id: str,
        llm_generate: GenerateFn,
        *,
        provider: str = "openai",
        model: str | None = None,
    ) -> OutreachMessage:
        """Draft the next follow-up for a due message. Returns a draft;
        it still needs its own submit_for_approval before anything sends."""
        message = self._message(message_id)
        if message not in self.due_follow_ups():
            raise CampaignStateError("message is not due for a follow-up")
        contact = self._contact(message.contact_id)
        campaign = self.get_campaign(message.campaign_id)
        if message.sent_at is None:
            raise CampaignStateError(
                f"sent message {message.id!r} has no sent_at timestamp"
            )
        sent_at = message.sent_at
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        days = (self._clock() - sent_at).days
        prompt = (
            "Draft a brief, respectful follow-up email. Do not invent facts. Return exactly "
            "'Subject: ...' followed by the body.\n"
            f"Campaign goal: {campaign.goal}\n"
            f"Recipient: {contact.name}\nOriginal subject: {message.subject}\n"
            f"Original email: {message.body}\n"
            f"Days without a detected reply: {days}"
        )
        used_model, text = await llm_generate(prompt, provider, model)
        subject, body = _parse_email(text)
        return self.add_draft(
            message.campaign_id,
            message.contact_id,
            subject=subject,
            body=body,
            kind="follow_up",
            provider=provider,
            model=used_model,
        )

    # --- audit ---------------------------------------------------------------

    def message_events(self, message_id: str) -> list[MessageEvent]:
        self._message(message_id)
        return self.campaigns.events(message_id)

    # --- internals -------------------------------------------------------------

    def _contact(self, contact_id: str):
        contact = self.contacts.get(contact_id)
        if contact is None:
            raise ContactNotFoundError(contact_id)
        return contact

    def _message(self, message_id: str) -> OutreachMessage:
        message = self.campaigns.get_message(message_id)
        if message is None:
            raise MessageNotFoundError(message_id)
        return message

    def _event(
        self,
        message: OutreachMessage,
        event: str,
        details: dict[str, Any] | None = None,
        actor: str | None = None,
    ) -> MessageEvent:
        return MessageEvent(
            message_id=message.id, event=event, actor=actor, at=self._clock(), details=details or {}
        )

    def _transition(
        self,
        message: OutreachMessage,
        target: MessageStatus,
        event: str,
        details: dict[str, Any] | None = None,
        actor: str | None = None,
    ) -> OutreachMessage:
        if target not in _ALLOWED_TRANSITIONS[message.status]:
            raise CampaignStateError(f"cannot move message from {message.status} to {target}")
        return self.campaigns.save_message(
            message.model_copy(
                update={
                    "status": target,
                    "updated_at": self._clock(),
                    "version": message.version + 1,
                }
            ),
            self._event(message, event, details, actor=actor),
        )


def _parse_email(text: str) -> tuple[str, str]:
    cleaned = text.strip()
    first, separator, rest = cleaned.partition("\n")
    if first.lower().startswith("subject:") and separator and rest.strip():
        return first.split(":", 1)[1].strip(), rest.strip()
    raise ValueError("model output must contain a Subject line followed by a body")
