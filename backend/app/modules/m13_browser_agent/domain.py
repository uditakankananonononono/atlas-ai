from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RunStatus(str, Enum):
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETE = "complete"
    FAILED = "failed"


class ActionType(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    EXTRACT = "extract"
    SCREENSHOT = "screenshot"
    SCROLL = "scroll"
    SUBMIT = "submit"
    LOGIN = "login"
    READBACK = "readback"


@dataclass(frozen=True)
class AuditEvent:
    tenant_id: str
    run_id: str
    action: ActionType
    payload: dict[str, Any]
    occurred_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class StagedSubmission:
    tenant_id: str
    session_id: str
    selector: str
    values_digest: str
    page_url: str
    snapshot_path: str
    snapshot_digest: str


@dataclass
class ApprovalRequest:
    id: str
    tenant_id: str
    run_id: str
    action: ActionType
    target: str
    snapshot_path: str
    form_values: dict[str, str]
    digest: str
    status: str = "pending"

    @classmethod
    def pending(cls, **kwargs: Any) -> "ApprovalRequest":
        return cls(id=secrets.token_urlsafe(18), status="pending", **kwargs)
