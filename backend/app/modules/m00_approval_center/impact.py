"""Approval impact preview (M00 enhancement).

Before an approved effect is consumed, compare the exact effect payload with
the *current* external state, and with the state the reviewer saw when they
decided. If the external state moved since review (a thread got a new reply, a
price changed, a document was edited), the permit is refused until a human
re-reviews. Nothing here performs the effect.

- A module registers a state probe for an action pattern: a callable that
  reads the live external state an effect depends on (read-only).
- `capture_review_state` stores what the reviewer saw (hash + JSON), normally
  called when the approval card is rendered or at submit time.
- `impact_preview` re-reads live state and returns the effect payload, the
  reviewed state, the current state and a dotted-path drift list.
- `consume_effect_checked` runs the preview and only then calls the existing
  atomic `consume_effect`; drift blocks it and writes an audit event.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import threading
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import JSON, DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.m00_approval_center.service import (
    ApprovalConflictError,
    ApprovalEventRow,
    Service,
    _aware,
)

StateProbe = Callable[[dict[str, Any]], dict[str, Any]]


class ApprovalReviewStateRow(Base):
    """What the reviewer saw. One row per approval; overwritten only while pending."""

    __tablename__ = "m00_approval_review_states"

    approval_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    state_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[dict[str, Any]] = mapped_column(JSON)
    probe: Mapped[str] = mapped_column(String(200))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StateDriftError(ApprovalConflictError):
    """External state changed since the reviewer decided."""

    def __init__(self, approval_id: str, drift: list[dict[str, Any]]) -> None:
        self.approval_id, self.drift = approval_id, drift
        paths = ", ".join(d["path"] for d in drift[:8])
        super().__init__(f"external state changed since review ({paths}); re-review required")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def state_hash(state: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(state).encode()).hexdigest()


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key in sorted(value):
            out.update(_flatten(value[key], f"{prefix}.{key}" if prefix else str(key)))
        return out or {prefix: {}}
    if isinstance(value, list):
        out = {}
        for i, item in enumerate(value):
            out.update(_flatten(item, f"{prefix}[{i}]"))
        return out or {prefix: []}
    return {prefix: value}


def diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    a, b = _flatten(before), _flatten(after)
    changes = []
    for path in sorted(set(a) | set(b)):
        if path not in a:
            changes.append({"path": path, "change": "added", "after": b[path]})
        elif path not in b:
            changes.append({"path": path, "change": "removed", "before": a[path]})
        elif a[path] != b[path]:
            changes.append({"path": path, "change": "changed", "before": a[path], "after": b[path]})
    return changes


class ProbeRegistry:
    def __init__(self) -> None:
        self._probes: list[tuple[str, int | None, StateProbe]] = []
        self._lock = threading.Lock()

    def register(self, action_pattern: str, probe: StateProbe, *, module_id: int | None = None) -> None:
        with self._lock:
            self._probes.append((action_pattern, module_id, probe))

    def find(self, module_id: int, action_type: str) -> tuple[str, StateProbe] | None:
        with self._lock:
            probes = list(self._probes)
        # Most specific wins: exact module + longest literal pattern.
        matches = [(p, m, f) for p, m, f in probes
                   if (m is None or m == module_id) and fnmatch.fnmatchcase(action_type, p)]
        if not matches:
            return None
        pattern, module, probe = max(matches, key=lambda x: (x[1] is not None, len(x[0].replace("*", ""))))
        return f"{module if module is not None else '*'}:{pattern}", probe


PROBES = ProbeRegistry()


def _status(view: dict[str, Any]) -> str:
    raw = view["status"]
    return str(getattr(raw, "value", raw))


def _read_probe(registry: ProbeRegistry, view: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    found = registry.find(view["module_id"], view["action_type"])
    if found is None:
        return None
    name, probe = found
    state = probe(dict(view["payload"]))
    if not isinstance(state, dict):
        raise TypeError(f"state probe {name} must return a dict")
    return name, state


def capture_review_state(service: Service, approval_id: str, *, registry: ProbeRegistry = PROBES,
                         state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Store the state the reviewer is shown. Only allowed while the approval is pending."""
    view = service.get(approval_id)
    if _status(view) != "pending":
        raise ApprovalConflictError(f"approval is {_status(view)}; review state is frozen")
    probe_name = "explicit"
    if state is None:
        read = _read_probe(registry, view)
        if read is None:
            raise LookupError(f"no state probe registered for module {view['module_id']} action {view['action_type']!r}")
        probe_name, state = read
    now = service._clock()
    digest = state_hash(state)
    with service._sessions.begin() as db:
        row = db.get(ApprovalReviewStateRow, approval_id)
        if row is None:
            row = ApprovalReviewStateRow(approval_id=approval_id)
            db.add(row)
        row.state_hash, row.state, row.probe, row.captured_at = digest, state, probe_name, now
        db.add(ApprovalEventRow(approval_id=approval_id, event="review_state_captured", actor=None, at=now))
    return {"approval_id": approval_id, "state_hash": digest, "probe": probe_name, "captured_at": now}


def impact_preview(service: Service, approval_id: str, *, registry: ProbeRegistry = PROBES) -> dict[str, Any]:
    view = service.get(approval_id)
    with service._sessions() as db:
        reviewed = db.get(ApprovalReviewStateRow, approval_id)
        reviewed = None if reviewed is None else {
            "state": reviewed.state, "state_hash": reviewed.state_hash,
            "probe": reviewed.probe, "captured_at": _aware(reviewed.captured_at)}
    read = _read_probe(registry, view)
    current = None if read is None else {"probe": read[0], "state": read[1], "state_hash": state_hash(read[1])}
    if reviewed is None:
        drift, verdict = [], "no_review_snapshot"
    elif current is None:
        drift, verdict = [], "no_probe"
    else:
        drift = diff(reviewed["state"], current["state"])
        verdict = "drifted" if drift else "unchanged"
    return {
        "approval_id": approval_id, "status": _status(view),
        "module_id": view["module_id"], "action_type": view["action_type"],
        "effect": view["payload"], "reviewed": reviewed, "current": current,
        "drift": drift, "verdict": verdict,
        "safe_to_consume": _status(view) == "approved" and verdict in {"unchanged", "no_review_snapshot"},
        "checked_at": service._clock(),
    }


def consume_effect_checked(service: Service, approval_id: str, *, module_id: int, action_type: str,
                           payload: dict[str, Any], user_id: str, effect_id: str, actor: str,
                           registry: ProbeRegistry = PROBES) -> dict[str, Any]:
    """Consume only if the live state still matches what the reviewer saw.

    A reviewed approval whose probe is no longer registered fails closed: the
    worker can't prove the state is unchanged.
    """
    preview = impact_preview(service, approval_id, registry=registry)
    if preview["verdict"] == "drifted":
        now = service._clock()
        with service._sessions.begin() as db:
            db.add(ApprovalEventRow(approval_id=approval_id, event="effect_blocked_drift", actor=actor, at=now))
        raise StateDriftError(approval_id, preview["drift"])
    if preview["verdict"] == "no_probe":
        raise ApprovalConflictError("review snapshot exists but no state probe is registered; cannot verify state")
    permit = service.consume_effect(approval_id, module_id=module_id, action_type=action_type,
                                    payload=payload, user_id=user_id, effect_id=effect_id, actor=actor)
    return {**permit, "state_verdict": preview["verdict"],
            "state_hash": (preview["current"] or {}).get("state_hash")}
