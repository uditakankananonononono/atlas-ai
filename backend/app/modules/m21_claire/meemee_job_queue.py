"""Failure-surviving job queue, ported from meemee `jobs.py`/`worker.py` (C4 meemee-merge).

Semantics preserved from meemee@50e7605: queued -> running -> done/failed/cancelled,
attempt counting with bounded retries, cooperative cancellation for running jobs,
and an ordered per-job event log. Hermetic in-memory port with an injected clock.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

_TERMINAL = {"done", "failed", "cancelled"}


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


class JobQueue:
    """Principal-aware job queue with bounded attempts and cooperative cancellation."""

    def __init__(self, clock: Callable[[], datetime] = _default_clock):
        self.clock = clock
        self.lock = threading.RLock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._events: dict[str, list[dict[str, Any]]] = {}

    def _now(self) -> datetime:
        moment = self.clock()
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("job clock must include a timezone")
        return moment.astimezone(timezone.utc)

    def _record(self, ident: str, kind: str, payload: dict[str, Any]) -> None:
        self._events.setdefault(ident, []).append(
            {"job_id": ident, "kind": kind, "payload": payload, "at": self._now().isoformat()}
        )

    def enqueue(self, goal: str, run_at: datetime | None = None, max_attempts: int = 3,
                principal: str | None = None) -> str:
        if not goal.strip():
            raise ValueError("goal is required")
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        if principal is not None and not principal.strip():
            raise ValueError("principal must be non-empty when supplied")
        due = (run_at or self._now()).astimezone(timezone.utc)
        now = self._now().isoformat()
        ident = uuid.uuid4().hex
        with self.lock:
            self._jobs[ident] = {
                "id": ident, "goal": goal, "run_at": due.isoformat(), "status": "queued",
                "attempts": 0, "max_attempts": max_attempts, "principal": principal,
                "result": None, "error": None, "cancel_requested": False,
                "created_at": now, "updated_at": now,
            }
            self._record(ident, "enqueued", {"goal": goal})
        return ident

    def claim(self) -> dict[str, Any] | None:
        with self.lock:
            now = self._now()
            due = [job for job in self._jobs.values()
                   if job["status"] == "queued" and datetime.fromisoformat(job["run_at"]) <= now]
            if not due:
                return None
            due.sort(key=lambda job: (job["run_at"], job["created_at"], job["id"]))
            job = due[0]
            job["status"] = "running"
            job["attempts"] += 1
            job["updated_at"] = now.isoformat()
            self._record(job["id"], "running", {"attempt": job["attempts"]})
            return dict(job)

    def _settle(self, ident: str, target: str, result: dict[str, Any] | None, error: str | None) -> bool:
        with self.lock:
            job = self._jobs.get(ident)
            if job is None or job["status"] != "running":
                return False
            if target == "retry":
                job["status"] = "queued" if job["attempts"] < job["max_attempts"] else "failed"
            else:
                job["status"] = target
            job["result"] = result
            job["error"] = error
            job["updated_at"] = self._now().isoformat()
            self._record(ident, job["status"], {"error": error} if error else {})
            return True

    def finish(self, ident: str, result: dict[str, Any]) -> bool:
        return self._settle(ident, "done", result, None)

    def fail(self, ident: str, error: str) -> bool:
        return self._settle(ident, "retry", None, error)

    def request_cancel(self, ident: str) -> str | None:
        with self.lock:
            job = self._jobs.get(ident)
            if job is None or job["status"] in _TERMINAL:
                return None
            if job["status"] == "queued":
                return "queued"
            job["cancel_requested"] = True
            self._record(ident, "cancel_requested", {})
            return "cancel_requested"

    def cancel_running(self, ident: str) -> bool:
        with self.lock:
            job = self._jobs.get(ident)
            if job is None or job["status"] != "running" or not job["cancel_requested"]:
                return False
            job["status"] = "cancelled"
            job["updated_at"] = self._now().isoformat()
            self._record(ident, "cancelled", {})
            return True

    def cancel(self, ident: str) -> bool:
        with self.lock:
            job = self._jobs.get(ident)
            if job is None or job["status"] != "queued":
                return False
            job["status"] = "cancelled"
            job["updated_at"] = self._now().isoformat()
            self._record(ident, "cancelled", {})
            return True

    def events(self, ident: str, after: int = 0) -> list[dict[str, Any]]:
        with self.lock:
            if ident not in self._jobs:
                raise KeyError(ident)
            return [dict(event) for event in self._events.get(ident, [])][after:]

    def list_for_principal(self, principal: str) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(job) for job in self._jobs.values() if job["principal"] == principal]

    def get_owned(self, ident: str, principal: str) -> dict[str, Any] | None:
        with self.lock:
            job = self._jobs.get(ident)
            return dict(job) if job and job["principal"] == principal else None

    def get(self, ident: str) -> dict[str, Any] | None:
        with self.lock:
            job = self._jobs.get(ident)
            return dict(job) if job else None
