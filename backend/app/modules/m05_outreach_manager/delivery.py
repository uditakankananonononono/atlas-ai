"""Delivery of approved outreach mail, with a full delivery audit.

Ledger row CRM-139 (Email outreach): every send routes through Module 0.
This layer is the only code in the module that can cause an external
effect, and it does so only after independently verifying that:

1. the message is in the ``approved`` state;
2. its bound Module 0 approval exists and is approved; and
3. the approval payload still matches the exact recipient, subject, and
   body being sent - content edited after approval is blocked, not sent.

Every attempt, success, failure, and block is written to the append-only
message event log, which is the module's delivery audit.
"""
from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Any, Protocol

from pydantic import BaseModel, Field

from .campaigns import CampaignService, MessageEvent, OutreachMessage


class DeliveryError(RuntimeError):
    """Base class for delivery failures."""


class DeliveryNotConfiguredError(DeliveryError):
    """Raised when no mail sender is configured."""


class DeliveryApprovalError(DeliveryError):
    """Raised when the Module 0 approval does not authorize this exact send."""


class DeliverySendError(DeliveryError):
    """Raised when the mail sender rejects or fails the transmission."""


class DeliveryReceipt(BaseModel):
    """What the sender reported after accepting the message."""

    provider_message_id: str | None = None
    thread_id: str | None = None
    status: str = "sent"
    detail: dict[str, Any] = Field(default_factory=dict)


class MailSender(Protocol):
    """Async boundary for real mail transmission."""

    name: str

    async def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        from_account: str | None = None,
    ) -> DeliveryReceipt: ...


class ApprovalView(BaseModel):
    """The parts of a Module 0 request delivery relies on."""

    id: str
    status: str
    action_type: str
    payload: dict[str, Any]


class ApprovalGate(Protocol):
    """Read boundary over the shared approval store."""

    def get(self, approval_id: str) -> ApprovalView | None: ...


class ModuleZeroApprovalGate:
    """ApprovalGate over the shared app.core.approvals facade.

    The facade exposes list() rather than get(id); scanning newest-first
    is correct and stays inside the existing shared API. A direct get on
    the facade is noted in INTEGRATION.md as an integration improvement.
    """

    def __init__(self, store: Any) -> None:
        self._store = store

    def get(self, approval_id: str) -> ApprovalView | None:
        for item in self._store.list():
            if item.id == approval_id:
                return ApprovalView(
                    id=item.id,
                    status=item.status.value if hasattr(item.status, "value") else str(item.status),
                    action_type=item.action_type,
                    payload=item.payload,
                )
        return None


@dataclass
class SmtpMailSender:
    """Real SMTP transmission via stdlib smtplib (STARTTLS by default).

    Credentials are injected (environment in routes, explicit arguments
    in tests) and never returned or logged. smtp_factory exists so tests
    can substitute a fake without any network.
    """

    host: str
    from_address: str
    port: int = 587
    username: str | None = None
    password: str | None = None
    use_starttls: bool = True
    timeout: float = 30.0
    smtp_factory: Any = None

    name: str = "smtp"

    async def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        from_account: str | None = None,
    ) -> DeliveryReceipt:
        sender = from_account or self.from_address
        message = EmailMessage()
        message["From"] = sender
        message["To"] = to
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=False)
        message["Message-ID"] = make_msgid()
        message.set_content(body)
        try:
            await asyncio.to_thread(self._send_sync, message, sender, to)
        except (smtplib.SMTPException, OSError) as exc:
            raise DeliverySendError(f"SMTP send failed: {exc.__class__.__name__}") from exc
        return DeliveryReceipt(provider_message_id=message["Message-ID"])

    def _send_sync(self, message: EmailMessage, sender: str, recipient: str) -> None:
        factory = self.smtp_factory or smtplib.SMTP
        with factory(self.host, self.port, timeout=self.timeout) as smtp:
            if self.use_starttls:
                smtp.starttls()
            if self.username:
                smtp.login(self.username, self.password or "")
            smtp.send_message(message, from_addr=sender, to_addrs=[recipient])


class DeliveryService:
    """Send only what Module 0 approved, exactly as approved, and audit it."""

    def __init__(
        self,
        campaigns: CampaignService,
        gate: ApprovalGate,
        sender: MailSender,
    ) -> None:
        self.campaigns = campaigns
        self.gate = gate
        self.sender = sender

    async def send_approved(self, message_id: str) -> OutreachMessage:
        message = self.campaigns.get_message(message_id)
        if message.status != "approved":
            raise DeliveryApprovalError(
                f"message is {message.status}; only approved messages can be sent"
            )
        if not message.approval_id:
            raise DeliveryApprovalError("message has no bound approval")
        approval = self.gate.get(message.approval_id)
        if approval is None:
            raise DeliveryApprovalError("bound approval does not exist")
        if approval.status != "approved":
            raise DeliveryApprovalError(f"bound approval is {approval.status}, not approved")
        contact = self.campaigns._contact(message.contact_id)
        mismatch = self._payload_mismatch(message, approval, recipient=str(contact.email))
        if mismatch:
            self._audit(message, "blocked_payload_mismatch", {"fields": mismatch})
            raise DeliveryApprovalError(
                "message content changed after approval; re-approval required"
            )
        try:
            receipt = await self.sender.send(
                to=str(contact.email),
                subject=message.subject,
                body=message.body,
            )
        except DeliverySendError as exc:
            self.campaigns.record_delivery_failure(message.id, reason=str(exc))
            raise
        sent = self.campaigns.mark_sent(
            message.id,
            thread_id=receipt.thread_id,
            provider_message_id=receipt.provider_message_id,
        )
        return sent

    def delivery_audit(self, message_id: str) -> list[MessageEvent]:
        """Every delivery-relevant audit event for one message."""
        relevant = {"sent", "failed", "bounced", "blocked_payload_mismatch"}
        return [
            event
            for event in self.campaigns.message_events(message_id)
            if event.event in relevant
        ]

    def delivery_report(self, campaign_id: str) -> dict[str, Any]:
        """Aggregate delivery state for a campaign: counts plus per-message
        latest delivery outcome. This is the campaign's delivery audit."""
        messages = self.campaigns.campaigns.list_messages(campaign_id=campaign_id)
        counts: dict[str, int] = {}
        rows = []
        for message in messages:
            counts[message.status] = counts.get(message.status, 0) + 1
            audit = self.delivery_audit(message.id)
            rows.append(
                {
                    "message_id": message.id,
                    "contact_id": message.contact_id,
                    "kind": message.kind,
                    "sequence": message.sequence,
                    "status": message.status,
                    "sent_at": message.sent_at.isoformat() if message.sent_at else None,
                    "last_delivery_event": audit[-1].event if audit else None,
                }
            )
        return {"campaign_id": campaign_id, "counts": counts, "messages": rows}

    # --- internals -----------------------------------------------------------

    def _audit(self, message: OutreachMessage, event: str, details: dict[str, Any]) -> None:
        self.campaigns.campaigns.save_message(
            message,
            MessageEvent(
                message_id=message.id,
                event=event,
                actor=None,
                at=self.campaigns._clock(),
                details=details,
            ),
        )

    @staticmethod
    def _payload_mismatch(
        message: OutreachMessage, approval: ApprovalView, recipient: str
    ) -> list[str]:
        expected = {
            "message_id": message.id,
            "recipient": recipient,
            "subject": message.subject,
            "body": message.body,
        }
        return [key for key, value in expected.items() if approval.payload.get(key) != value]
