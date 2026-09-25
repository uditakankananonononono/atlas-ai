"""Approval gates for feature activation.

Autonomy boundary: detection, planning, synthesis, and sandbox testing run
autonomously. Activation - new code becoming callable by a module - always
requires a human decision through an approval gate (Module 0 in production).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"
DECISIONS = (PENDING, APPROVED, REJECTED)


class ApprovalGate(Protocol):
    def request(self, *, module_id: int, module_slug: str, action_type: str,
                summary: str, payload: dict[str, Any]) -> str: ...
    def decision(self, approval_id: str) -> str: ...


class ManualApprovalGate:
    """File-backed gate for development, offline runs, and tests.

    Requests persist to approvals.json. A human decides by editing the file
    or calling decide(); nothing auto-approves unless explicitly constructed
    with auto_approve=True (used by tests and local demos).
    """

    def __init__(self, path: Path, *, auto_approve: bool = False) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._auto = auto_approve
        self._lock = threading.Lock()
        if not self._path.exists():
            self._path.write_text("{}", encoding="utf-8")

    def _load(self) -> dict[str, Any]:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, Any]) -> None:
        self._path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def request(self, *, module_id: int, module_slug: str, action_type: str,
                summary: str, payload: dict[str, Any]) -> str:
        approval_id = f"si-{uuid4().hex[:12]}"
        with self._lock:
            data = self._load()
            data[approval_id] = {
                "module_id": module_id, "module_slug": module_slug,
                "action_type": action_type, "summary": summary, "payload": payload,
                "status": APPROVED if self._auto else PENDING,
                "requested_at": time.time(), "decided_at": None,
            }
            self._save(data)
        return approval_id

    def decide(self, approval_id: str, decision: str, *, decided_by: str = "human") -> None:
        if decision not in (APPROVED, REJECTED):
            raise ValueError(f"decision must be approved or rejected, got {decision!r}")
        with self._lock:
            data = self._load()
            if approval_id not in data:
                raise KeyError(f"unknown approval {approval_id!r}")
            data[approval_id]["status"] = decision
            data[approval_id]["decided_at"] = time.time()
            data[approval_id]["decided_by"] = decided_by
            self._save(data)

    def decision(self, approval_id: str) -> str:
        with self._lock:
            data = self._load()
        if approval_id not in data:
            raise KeyError(f"unknown approval {approval_id!r}")
        return data[approval_id]["status"]


class M00ApprovalGate:
    """Adapter onto the production Human Approval Center (Module 0)."""

    def __init__(self) -> None:
        try:
            from app.modules.m00_approval_center import service as m00  # noqa: F401
        except Exception as exc:
            raise RuntimeError(
                "M00ApprovalGate requires the approval-center service and its "
                "database; use ManualApprovalGate for offline runs") from exc
        self._m00 = m00

    def request(self, *, module_id: int, module_slug: str, action_type: str,
                summary: str, payload: dict[str, Any]) -> str:
        view = self._m00.request_approval(
            module_id=module_id, action_type=action_type,
            payload={"module_slug": module_slug, "summary": summary, **payload},
        )
        return str(view["id"])

    def decision(self, approval_id: str) -> str:
        view = self._m00.default_service().get(approval_id)
        status = str(view.get("status", "pending")).lower()
        if status in ("approved",):
            return APPROVED
        if status in ("rejected", "denied", "expired"):
            return REJECTED
        return PENDING
