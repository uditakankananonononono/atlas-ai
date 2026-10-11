"""Durable goals with atomic work leasing, ported from meemee `goals.py` (C4 meemee-merge).

Semantics preserved from meemee@50e7605: principal-scoped goal graph with
priorities, dependency gating, expiring leases, optimistic version checks and a
fixed transition table. This Claire port keeps the same rules in a hermetic
in-memory store with an injected clock; persistence belongs to the host journal.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Literal

GoalStatus = Literal["pending", "active", "blocked", "completed", "failed", "cancelled"]
_TERMINAL = {"completed", "failed", "cancelled"}
_TRANSITIONS = {
    "pending": {"active", "blocked", "cancelled"},
    "active": {"pending", "blocked", "completed", "failed", "cancelled"},
    "blocked": {"pending", "active", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


class GoalConflict(RuntimeError):
    """The requested mutation conflicts with current goal state."""


class GoalStore:
    """Principal-scoped goal graph with priorities, dependencies and expiring leases."""

    def __init__(self, clock: Callable[[], datetime] = _default_clock):
        self.clock = clock
        self.lock = threading.RLock()
        self._goals: dict[tuple[str, str], dict[str, Any]] = {}

    def _now(self) -> datetime:
        moment = self.clock()
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("goal clock must include a timezone")
        return moment.astimezone(timezone.utc)

    @staticmethod
    def _iso(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()

    def create(self, principal: str, description: str, *, priority: int = 0,
               parent_id: str | None = None, depends_on: list[str] | None = None,
               context: dict[str, Any] | None = None, goal_id: str | None = None) -> dict[str, Any]:
        if not principal.strip() or not description.strip():
            raise ValueError("principal and description are required")
        ident = goal_id or uuid.uuid4().hex
        dependencies = list(dict.fromkeys(depends_on or []))
        if ident in dependencies:
            raise ValueError("goal cannot depend on itself")
        with self.lock:
            if parent_id:
                self._owned(principal, parent_id)
            for dependency in dependencies:
                self._owned(principal, dependency)
            now = self._iso(self._now())
            self._goals[(principal, ident)] = {
                "id": ident, "principal": principal, "description": description.strip(),
                "status": "pending", "priority": priority, "parent_id": parent_id,
                "context": dict(context or {}), "outcome": None, "failure": None,
                "lease_owner": None, "lease_until": None, "version": 1,
                "created_at": now, "updated_at": now, "depends_on": dependencies,
            }
        return self.get(principal, ident)

    def _owned(self, principal: str, goal_id: str) -> dict[str, Any]:
        row = self._goals.get((principal, goal_id))
        if row is None:
            raise KeyError(goal_id)
        return row

    def get(self, principal: str, goal_id: str) -> dict[str, Any]:
        with self.lock:
            return dict(self._owned(principal, goal_id))

    def list(self, principal: str, status: GoalStatus | None = None) -> list[dict[str, Any]]:
        with self.lock:
            rows = [row for (owner, _), row in self._goals.items() if owner == principal]
            if status:
                rows = [row for row in rows if row["status"] == status]
            rows.sort(key=lambda row: (-row["priority"], row["created_at"], row["id"]))
            return [dict(row) for row in rows]

    def _claimable(self, principal: str, now: datetime) -> list[dict[str, Any]]:
        ready = []
        for (owner, _), row in self._goals.items():
            if owner != principal or row["status"] not in ("pending", "active"):
                continue
            lease_until = row["lease_until"]
            if lease_until is not None and datetime.fromisoformat(lease_until) > now:
                continue
            waiting = any(
                self._goals[(principal, dep)]["status"] != "completed" for dep in row["depends_on"]
            )
            if not waiting:
                ready.append(row)
        ready.sort(key=lambda row: (-row["priority"], row["created_at"], row["id"]))
        return ready

    def claim(self, principal: str, worker_id: str, *, lease_seconds: int = 300) -> dict[str, Any] | None:
        if not worker_id.strip() or lease_seconds <= 0:
            raise ValueError("worker and positive lease are required")
        with self.lock:
            now = self._now()
            ready = self._claimable(principal, now)
            if not ready:
                return None
            row = ready[0]
            row["status"] = "active"
            row["lease_owner"] = worker_id
            row["lease_until"] = self._iso(now + timedelta(seconds=lease_seconds))
            row["version"] += 1
            row["updated_at"] = self._iso(now)
            return dict(row)

    def renew(self, principal: str, goal_id: str, worker_id: str, lease_seconds: int = 300) -> dict[str, Any]:
        if lease_seconds <= 0:
            raise ValueError("positive lease is required")
        with self.lock:
            row = self._owned(principal, goal_id)
            now = self._now()
            live = (
                row["status"] == "active"
                and row["lease_owner"] == worker_id
                and row["lease_until"] is not None
                and datetime.fromisoformat(row["lease_until"]) > now
            )
            if not live:
                raise GoalConflict("goal has no live lease owned by worker")
            row["lease_until"] = self._iso(now + timedelta(seconds=lease_seconds))
            row["version"] += 1
            row["updated_at"] = self._iso(now)
            return dict(row)

    def transition(self, principal: str, goal_id: str, status: GoalStatus, *, worker_id: str | None = None,
                   expected_version: int | None = None, outcome: str | None = None,
                   failure: str | None = None) -> dict[str, Any]:
        with self.lock:
            row = self._owned(principal, goal_id)
            now = self._now()
            if status not in _TRANSITIONS[row["status"]]:
                raise GoalConflict(f"invalid transition {row['status']} -> {status}")
            if expected_version is not None and row["version"] != expected_version:
                raise GoalConflict(f"version conflict: expected {expected_version}, actual {row['version']}")
            if row["lease_owner"] and worker_id != row["lease_owner"]:
                raise GoalConflict("active lease is owned by another worker")
            if row["lease_owner"] and (
                not row["lease_until"] or datetime.fromisoformat(row["lease_until"]) <= now
            ):
                raise GoalConflict("worker lease has expired")
            if status == "completed":
                waiting = any(
                    self._goals[(principal, dep)]["status"] != "completed" for dep in row["depends_on"]
                )
                if waiting:
                    raise GoalConflict("dependencies are not complete")
            clear = status in _TERMINAL or status in {"pending", "blocked"}
            row["status"] = status
            row["outcome"] = outcome
            row["failure"] = failure
            if clear:
                row["lease_owner"] = None
                row["lease_until"] = None
            row["version"] += 1
            row["updated_at"] = self._iso(now)
            return dict(row)
