from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


class TriageLabel(str, Enum):
    URGENT = "urgent"
    ACTION = "action"
    WAITING = "waiting"
    FYI = "fyi"
    NEWSLETTER = "newsletter"
    SPAM = "spam"


class DraftStatus(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    FAILED = "failed"


class FollowUpStatus(str, Enum):
    OPEN = "open"
    DUE = "due"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class MailboxRef:
    tenant_id: str
    mailbox_id: str
    address: str
    provider: str

    def __post_init__(self) -> None:
        for name in ("tenant_id", "mailbox_id", "address", "provider"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} is required")


@dataclass(frozen=True)
class ProviderMessage:
    provider_id: str
    thread_id: str
    sender: str
    recipients: tuple[str, ...]
    subject: str
    body_text: str
    received_at: datetime
    headers: Mapping[str, str] = field(default_factory=dict)
    in_reply_to: str | None = None


@dataclass(frozen=True)
class EmailMessage:
    id: str
    tenant_id: str
    mailbox_id: str
    provider_id: str
    thread_id: str
    sender: str
    recipients: tuple[str, ...]
    subject: str
    body_text: str
    received_at: datetime
    headers: Mapping[str, str]
    in_reply_to: str | None = None


@dataclass(frozen=True)
class TriageDecision:
    message_id: str
    label: TriageLabel
    score: float
    reasons: tuple[str, ...]
    needs_reply: bool
    due_at: datetime | None = None


@dataclass(frozen=True)
class Draft:
    id: str
    tenant_id: str
    mailbox_id: str
    thread_id: str
    to: tuple[str, ...]
    cc: tuple[str, ...]
    subject: str
    body_text: str
    status: DraftStatus
    revision: int
    created_at: datetime
    updated_at: datetime
    source_message_id: str | None = None
    provider_message_id: str | None = None


@dataclass(frozen=True)
class Approval:
    id: str
    tenant_id: str
    draft_id: str
    requested_by: str
    status: str
    created_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None
    reason: str | None = None
    draft_revision: int = 1


@dataclass(frozen=True)
class FollowUp:
    id: str
    tenant_id: str
    mailbox_id: str
    thread_id: str
    due_at: datetime
    status: FollowUpStatus
    reason: str
    created_at: datetime
    source_message_id: str | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class SyncResult:
    imported: int
    updated: int
    cursor: str | None
    message_ids: tuple[str, ...]


@dataclass(frozen=True)
class SendResult:
    provider_message_id: str
    sent_at: datetime
    raw: Mapping[str, Any] = field(default_factory=dict)
