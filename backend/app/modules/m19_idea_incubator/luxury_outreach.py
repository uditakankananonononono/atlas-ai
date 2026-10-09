"""Approval-gated outreach queue for the luxury venture lane.

Nothing leaves this module unless a human has approved the exact message in
Module 0 and a one-shot permit is consumed for that exact payload. The send
adapter is injected by the caller. The default adapter refuses, so importing or
calling this module cannot contact anyone. The queue never sends as the user's
own mailbox; the adapter decides the channel and is outside this module.
"""
from __future__ import annotations

import threading
from typing import Any, Protocol

from app.modules.m00_approval_center.service import ApprovalConflictError, ApprovalNotFoundError, Service, default_service

MODULE_ID = 19
ACTION_TYPE = "luxury_venture.outreach.send"


_LOCK = threading.Lock()  # process-wide: separate queue instances share it


class OutreachRefused(RuntimeError):
    """Raised when a send is refused. The sender was not called."""


class Sender(Protocol):
    def __call__(self, message: dict[str, Any]) -> dict[str, Any]: ...


def refuse_sender(message: dict[str, Any]) -> dict[str, Any]:
    raise OutreachRefused("no send adapter configured; outreach stays a reviewed draft")


def _payload(preview: dict[str, Any]) -> dict[str, Any]:
    need = ("concept_id", "recipient_organization", "recipient_role", "channel", "subject", "body", "evidence_refs")
    missing = [k for k in need if k not in preview]
    if missing:
        raise ValueError("outreach preview missing: " + ", ".join(missing))
    if preview.get("status") != "pending_approval":
        raise ValueError("only validated previews (status pending_approval) can be queued")
    return {k: preview[k] for k in need}


class LuxuryOutreachQueue:
    def __init__(self, service: Service | None = None, sender: Sender = refuse_sender) -> None:
        self._service = service
        self._sender = sender

    @property
    def service(self) -> Service:
        return self._service or default_service()

    def enqueue(self, preview: dict[str, Any], *, user_id: str, ttl_seconds: int | None = 7 * 86400) -> dict[str, Any]:
        """Always creates a PENDING approval. Policy cannot auto-allow outreach."""
        view = self.service.submit(module_id=MODULE_ID, action_type=ACTION_TYPE, payload=_payload(preview),
                                   user_id=user_id, ttl_seconds=ttl_seconds)
        return {"approval_id": view["id"], "status": view["status"], "sent": False}

    def send(self, approval_id: str, message: dict[str, Any], *, user_id: str, actor: str = "luxury-outreach") -> dict[str, Any]:
        """Send only if approved and the message equals the approved payload.

        The permit is consumed before the adapter runs, so a crash or provider
        failure never reopens it: at most one attempt per approval within this
        process (a lock plus the Module 0 audit trail). Cross-process races rely
        on consume_effect's unique constraints for the permit, not for the adapter call.
        """
        payload = _payload(message)
        with _LOCK:
            return self._send_locked(approval_id, payload, user_id, actor)

    def _send_locked(self, approval_id: str, payload: dict[str, Any], user_id: str, actor: str) -> dict[str, Any]:
        try:
            if any(e["event"] == "effect_consumed" for e in self.service.audit(approval_id)):
                raise OutreachRefused("approval already used for a send attempt")
        except OutreachRefused:
            raise
        except ApprovalNotFoundError:
            pass  # unknown id: consume_effect below refuses
        except Exception as error:  # fail closed: an unreadable audit trail must not allow a send
            raise OutreachRefused("audit trail unreadable: " + type(error).__name__) from error
        try:
            self.service.consume_effect(approval_id, module_id=MODULE_ID, action_type=ACTION_TYPE, payload=payload,
                                        user_id=user_id, effect_id="luxury-outreach:" + approval_id, actor=actor)
        except ApprovalConflictError as error:
            raise OutreachRefused(str(error)) from error
        except Exception as error:  # unknown approval id, wrong tenant, malformed input
            raise OutreachRefused("approval could not be verified: " + type(error).__name__) from error
        receipt = self._sender(payload)
        return {"approval_id": approval_id, "sent": True, "adapter_receipt": receipt}
