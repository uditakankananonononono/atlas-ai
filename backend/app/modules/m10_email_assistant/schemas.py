"""API schemas for the Email Assistant module (module 10).

Spec reference: user directive, Module 10 - Email Assistant.
Categories are exactly the spec's seven labels; the action-item shape is the
spec's [{action, deadline, related_entity}] output schema.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class EmailCategory(str, Enum):
    OPPORTUNITY = "opportunity"
    PROFESSOR_REPLY = "professor_reply"
    COLLABORATION = "collaboration"
    NEWSLETTER = "newsletter"
    PERSONAL = "personal"
    SPAM = "spam"
    ACTION_REQUIRED = "action_required"


# Categories the spec treats as actionable: these get drafted replies.
ACTIONABLE_CATEGORIES = {
    EmailCategory.ACTION_REQUIRED,
    EmailCategory.PROFESSOR_REPLY,
    EmailCategory.COLLABORATION,
    EmailCategory.OPPORTUNITY,
}


class ActionItem(BaseModel):
    """Spec output schema: {action, deadline, related_entity}."""

    action: str = Field(min_length=1, max_length=1000)
    deadline: datetime | None = None
    related_entity: str | None = Field(default=None, max_length=300)


class ActionItemView(ActionItem):
    id: str
    message_id: str
    confidence: float = 0.0
    status: str = "open"


class GmailConnectRequest(BaseModel):
    auth_code: str = Field(min_length=1)
    redirect_uri: str = Field(min_length=1)


class GmailAccountView(BaseModel):
    id: str
    email_address: str
    history_id: str | None = None
    watch_expiration: datetime | None = None
    created_at: datetime


class EmailMessageView(BaseModel):
    id: str
    gmail_id: str
    thread_id: str | None = None
    subject: str
    sender: str
    recipients: list[str] = []
    snippet: str = ""
    received_at: datetime | None = None
    labels: list[str] = []
    category: EmailCategory | None = None
    category_confidence: float = 0.0
    unsubscribe_url: str | None = None


class EmailDraftView(BaseModel):
    id: str
    message_id: str
    approval_id: str
    to: str
    subject: str
    body: str
    model: str
    status: str = "pending_approval"
    created_at: datetime


class ProposedAction(BaseModel):
    """A reply draft that can only be sent through shared approval (module 0)."""

    approval_id: str
    action_type: Literal["send_email_reply"] = "send_email_reply"
    status: Literal["pending"] = "pending"
    payload: dict[str, Any]


class PubSubPush(BaseModel):
    """Google Cloud Pub/Sub push envelope delivered to the webhook."""

    message: dict[str, Any]
    subscription: str | None = None


class IngestResult(BaseModel):
    email_address: str
    history_id: str
    fetched: int = 0
    new_messages: int = 0
    drafts_proposed: int = 0


class WatchRenewalResult(BaseModel):
    renewed: list[str] = []
    skipped: list[str] = []


class PriorityMessage(BaseModel):
    message: EmailMessageView
    score: float
    reasons: list[str] = []
