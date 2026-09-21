"""Evidence-bound owner promise tracking without creating or sending follow-ups."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator

_OWNER_RE = re.compile(
    r"\b(?:i(?:'ll| will| can| am going to)|let me|we(?:'ll| will| can))\s+"
    r"(?P<commitment>[^.!?\n]{3,500})",
    re.IGNORECASE,
)


class MessageDirection(str, Enum):
    OWNER = "owner"
    OTHER = "other"


class ThreadMessage(BaseModel):
    message_id: str = Field(min_length=1, max_length=200)
    direction: MessageDirection
    sent_at: datetime
    body: str = Field(min_length=1, max_length=20000)


class PromiseStatus(str, Enum):
    OPEN = "open"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    NO_DEADLINE = "no_deadline"


class PromiseTrackerRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=300)
    messages: list[ThreadMessage] = Field(min_length=1, max_length=1000)
    as_of: datetime | None = None
    due_soon_hours: int = Field(default=48, ge=1, le=720)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [message.message_id for message in self.messages]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate message_id")
        return self


def _deadline(fragment: str, sent_at: datetime) -> tuple[datetime | None, str | None]:
    iso = re.search(r"\bby\s+(\d{4}-\d{2}-\d{2})(?:\b|T)", fragment, re.IGNORECASE)
    if iso:
        try:
            parsed = datetime.fromisoformat(iso.group(1)).replace(tzinfo=sent_at.tzinfo or timezone.utc)
            return parsed, iso.group(0)
        except ValueError:
            return None, iso.group(0)
    relative = re.search(r"\bby\s+(tomorrow|today)\b", fragment, re.IGNORECASE)
    if relative:
        from datetime import time, timedelta
        days = 1 if relative.group(1).casefold() == "tomorrow" else 0
        return datetime.combine(sent_at.date() + timedelta(days=days), time.max, sent_at.tzinfo or timezone.utc), relative.group(0)
    return None, None


def track_promises(request: PromiseTrackerRequest) -> dict:
    as_of = request.as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    as_of = as_of.astimezone(timezone.utc)
    promises = []
    for message in sorted(request.messages, key=lambda item: (item.sent_at, item.message_id)):
        if message.sent_at.tzinfo is None:
            raise ValueError(f"sent_at must be timezone-aware: {message.message_id}")
        if message.direction != MessageDirection.OWNER:
            continue
        for position, match in enumerate(_OWNER_RE.finditer(message.body)):
            commitment = " ".join(match.group("commitment").strip().split())
            deadline, deadline_text = _deadline(commitment, message.sent_at)
            if deadline is None:
                status = PromiseStatus.NO_DEADLINE
            elif deadline.astimezone(timezone.utc) < as_of:
                status = PromiseStatus.OVERDUE
            elif (deadline.astimezone(timezone.utc) - as_of).total_seconds() <= request.due_soon_hours * 3600:
                status = PromiseStatus.DUE_SOON
            else:
                status = PromiseStatus.OPEN
            identity = f"{request.thread_id}\0{message.message_id}\0{position}\0{commitment}".encode()
            promises.append({
                "promise_id": hashlib.sha256(identity).hexdigest(),
                "commitment": commitment,
                "source_message_id": message.message_id,
                "source_excerpt": match.group(0),
                "source_sent_at": message.sent_at.astimezone(timezone.utc).isoformat(),
                "deadline": deadline.astimezone(timezone.utc).isoformat() if deadline else None,
                "deadline_text": deadline_text,
                "status": status.value,
                "follow_up_proposed": status in {PromiseStatus.DUE_SOON, PromiseStatus.OVERDUE},
                "follow_up_requires_owner_approval": True,
            })
    canonical = json.dumps(promises, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {
        "thread_id": request.thread_id,
        "as_of": as_of.isoformat(),
        "promise_count": len(promises),
        "due_soon_count": sum(row["status"] == PromiseStatus.DUE_SOON for row in promises),
        "overdue_count": sum(row["status"] == PromiseStatus.OVERDUE for row in promises),
        "promises": promises,
        "tracker_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "boundary": "Atlas extracts proposed owner commitments from supplied thread text. It does not create tasks, reminders, drafts, or messages; every follow-up requires owner review and approval.",
    }
