"""Scheduled re-run *proposals* for finished sandbox analyses.

A schedule never executes anything. When it is due it files
``rerun_sandboxed_analysis`` approvals through ``RerunService.propose`` -
exactly what a person clicking "re-run" would file - and each one waits in
the Human Approval Center until a human approves it and someone calls the
re-run execute route.

Scope is either one analysis (``scope="analysis"``, target = the original
approval id) or a project (``scope="project"``, target = a project tag;
every finished original analysis tagged with it is covered).

Rules:
* at most one open proposal per analysis: if the last filed proposal for an
  analysis is still pending (or approved but not yet executed) the tick
  skips it instead of piling up approvals;
* after a tick the next due time advances past ``now`` in whole intervals,
  so a scheduler that was down for weeks files one round, not a backlog;
* filings are idempotent per (schedule, analysis, due slot);
* everything is tenant-scoped: schedules, tags, filings, ticks and stats.

``stats()`` reports schedules, due-now schedules, and every filed proposal
by live Module 0 status, flagging *overdue* ones: pending longer than the
schedule's ``overdue_after_hours``, or approved but not executed within it.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import uuid4

from .approved_sandbox import ApprovedSandboxExecutor, ExecutionConflictError, ExecutionNotFoundError
from .rerun import FINISHED, RerunService

PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.:-]{0,119}$")


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class RerunScheduleService:
    def __init__(self, executor: ApprovedSandboxExecutor,
                 clock: Callable[[], datetime] | None = None) -> None:
        self.ex = executor
        self.tenant_id = executor.tenant_id
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.db_path = executor.store.root / "m04-rerun-schedules.sqlite"
        self._lock = threading.Lock()
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS schedules (id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, "
                       "scope TEXT NOT NULL, target TEXT NOT NULL, interval_hours INTEGER NOT NULL, "
                       "overdue_after_hours INTEGER NOT NULL, next_due_at TEXT NOT NULL, active INTEGER NOT NULL, "
                       "reason TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS project_tags (tenant_id TEXT NOT NULL, approval_id TEXT NOT NULL, "
                       "project TEXT NOT NULL, PRIMARY KEY (tenant_id, approval_id, project))")
            db.execute("CREATE TABLE IF NOT EXISTS filings (tenant_id TEXT NOT NULL, schedule_id TEXT NOT NULL, "
                       "original_approval_id TEXT NOT NULL, due_at TEXT NOT NULL, rerun_approval_id TEXT, "
                       "outcome TEXT NOT NULL, detail TEXT NOT NULL, filed_at TEXT NOT NULL, "
                       "PRIMARY KEY (tenant_id, schedule_id, original_approval_id, due_at))")

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    # ------------------------------------------------------------------ tags and schedules
    def tag(self, approval_id: str, project: str) -> dict[str, Any]:
        if not PROJECT_RE.match(project):
            raise ValueError("invalid project tag")
        original = self.ex.store.latest(self.tenant_id, approval_id)
        if original is None or original.get("kind") == "rerun":
            raise ExecutionNotFoundError(approval_id)
        with self._lock, self._db() as db:
            db.execute("INSERT OR IGNORE INTO project_tags VALUES (?,?,?)", (self.tenant_id, approval_id, project))
        return {"approval_id": approval_id, "project": project}

    def create(self, *, scope: str, target: str, interval_hours: int, overdue_after_hours: int = 72,
               first_due_at: datetime | None = None, reason: str = "") -> dict[str, Any]:
        if scope not in ("analysis", "project"):
            raise ValueError("scope must be analysis or project")
        if not 1 <= interval_hours <= 24 * 366:
            raise ValueError("interval_hours must be between 1 and 8784")
        if not 1 <= overdue_after_hours <= 24 * 366:
            raise ValueError("overdue_after_hours must be between 1 and 8784")
        if scope == "analysis":
            original = self.ex.store.latest(self.tenant_id, target)
            if original is None or original.get("kind") == "rerun":
                raise ExecutionNotFoundError(target)
        elif not PROJECT_RE.match(target):
            raise ValueError("invalid project tag")
        now = self.clock()
        row = {"id": str(uuid4()), "tenant_id": self.tenant_id, "scope": scope, "target": target,
               "interval_hours": interval_hours, "overdue_after_hours": overdue_after_hours,
               "next_due_at": _utc(first_due_at or now + timedelta(hours=interval_hours)).isoformat(),
               "active": 1, "reason": reason[:1000], "created_by": self.ex.actor_id, "created_at": now.isoformat()}
        with self._lock, self._db() as db:
            db.execute("INSERT INTO schedules VALUES (:id,:tenant_id,:scope,:target,:interval_hours,"
                       ":overdue_after_hours,:next_due_at,:active,:reason,:created_by,:created_at)", row)
        return self._view(row)

    def _view(self, row: Any) -> dict[str, Any]:
        d = dict(row)
        d["active"] = bool(d["active"])
        return d

    def list(self) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM schedules WHERE tenant_id=? ORDER BY created_at", (self.tenant_id,)).fetchall()
        return [self._view(r) for r in rows]

    def _get(self, schedule_id: str) -> dict[str, Any]:
        with self._db() as db:
            row = db.execute("SELECT * FROM schedules WHERE tenant_id=? AND id=?", (self.tenant_id, schedule_id)).fetchone()
        if row is None:
            raise ExecutionNotFoundError(schedule_id)
        return self._view(row)

    def set_active(self, schedule_id: str, active: bool) -> dict[str, Any]:
        self._get(schedule_id)
        with self._lock, self._db() as db:
            db.execute("UPDATE schedules SET active=? WHERE tenant_id=? AND id=?", (int(active), self.tenant_id, schedule_id))
        return self._get(schedule_id)

    # ------------------------------------------------------------------ ticking
    def _originals(self, schedule: dict[str, Any]) -> list[str]:
        if schedule["scope"] == "analysis":
            return [schedule["target"]]
        with self._db() as db:
            rows = db.execute("SELECT approval_id FROM project_tags WHERE tenant_id=? AND project=? ORDER BY approval_id",
                              (self.tenant_id, schedule["target"])).fetchall()
        return [r[0] for r in rows]

    def _open_proposal(self, original_approval_id: str) -> str | None:
        """Latest filed proposal for this analysis that is still waiting on a human or on execution."""
        with self._db() as db:
            rows = db.execute("SELECT rerun_approval_id FROM filings WHERE tenant_id=? AND original_approval_id=? "
                              "AND rerun_approval_id IS NOT NULL ORDER BY filed_at DESC",
                              (self.tenant_id, original_approval_id)).fetchall()
        for (rid,) in rows:
            state = self._proposal_state(rid)
            if state in ("pending", "approved_not_executed"):
                return rid
        return None

    def _proposal_state(self, rerun_approval_id: str) -> str:
        try:
            view = self.ex.center.get(rerun_approval_id)
        except KeyError:
            return "missing"
        status = getattr(view.get("status"), "value", view.get("status"))
        if status == "approved":
            receipt = self.ex.store.latest(self.tenant_id, rerun_approval_id)
            if receipt is None or receipt["state"] == "infra_failed":
                return "approved_not_executed"
            return "executed" if receipt["state"] in FINISHED else f"run_{receipt['state']}"
        return str(status)

    def tick(self) -> dict[str, Any]:
        """File proposals for this tenant's due schedules. Never executes anything."""
        now = self.clock()
        filed, skipped, errors = [], [], []
        for schedule in self.list():
            if not schedule["active"] or datetime.fromisoformat(schedule["next_due_at"]) > now:
                continue
            due_at = schedule["next_due_at"]
            for original in self._originals(schedule):
                outcome, rid, detail = "filed", None, ""
                open_rid = self._open_proposal(original)
                if open_rid:
                    outcome, detail = "skipped_open_proposal", open_rid
                else:
                    try:
                        reason = f"scheduled re-run ({schedule['scope']} {schedule['target']}, due {due_at})"
                        rid = RerunService(self.ex).propose(original, reason)["approval_id"]
                    except (ExecutionNotFoundError, ExecutionConflictError) as exc:
                        outcome, detail = "error", str(exc).strip("'")
                with self._lock, self._db() as db:
                    cur = db.execute("INSERT OR IGNORE INTO filings VALUES (?,?,?,?,?,?,?,?)",
                                     (self.tenant_id, schedule["id"], original, due_at, rid, outcome, detail, now.isoformat()))
                if cur.rowcount == 0:
                    continue  # this due slot was already handled by an earlier tick
                item = {"schedule_id": schedule["id"], "original_approval_id": original, "due_at": due_at}
                if outcome == "filed":
                    filed.append({**item, "rerun_approval_id": rid})
                elif outcome == "error":
                    errors.append({**item, "error": detail})
                else:
                    skipped.append({**item, "open_rerun_approval_id": detail})
            nxt = datetime.fromisoformat(due_at)
            step = timedelta(hours=schedule["interval_hours"])
            while nxt <= now:
                nxt += step
            with self._lock, self._db() as db:
                db.execute("UPDATE schedules SET next_due_at=? WHERE tenant_id=? AND id=?",
                           (nxt.isoformat(), self.tenant_id, schedule["id"]))
        return {"tenant_id": self.tenant_id, "ticked_at": now.isoformat(), "filed": filed,
                "skipped": skipped, "errors": errors, "executed": 0}

    # ------------------------------------------------------------------ stats
    def stats(self) -> dict[str, Any]:
        now = self.clock()
        schedules = self.list()
        by_id = {s["id"]: s for s in schedules}
        with self._db() as db:
            rows = db.execute("SELECT * FROM filings WHERE tenant_id=? AND rerun_approval_id IS NOT NULL ORDER BY filed_at",
                              (self.tenant_id,)).fetchall()
        proposals, counts, overdue = [], {}, []
        for r in rows:
            state = self._proposal_state(r["rerun_approval_id"])
            counts[state] = counts.get(state, 0) + 1
            limit = timedelta(hours=by_id.get(r["schedule_id"], {}).get("overdue_after_hours", 72))
            age = now - datetime.fromisoformat(r["filed_at"])
            is_overdue = state in ("pending", "approved_not_executed") and age > limit
            item = {"schedule_id": r["schedule_id"], "original_approval_id": r["original_approval_id"],
                    "rerun_approval_id": r["rerun_approval_id"], "due_at": r["due_at"], "filed_at": r["filed_at"],
                    "state": state, "age_hours": round(age.total_seconds() / 3600, 1), "overdue": is_overdue}
            if state == "executed":
                receipt = self.ex.store.latest(self.tenant_id, r["rerun_approval_id"]) or {}
                item["verdict"] = (receipt.get("comparison") or {}).get("verdict")
            proposals.append(item)
            if is_overdue:
                overdue.append(item)
        due_now = [s["id"] for s in schedules if s["active"] and datetime.fromisoformat(s["next_due_at"]) <= now]
        verdicts: dict[str, int] = {}
        for p in proposals:
            if p.get("verdict"):
                verdicts[p["verdict"]] = verdicts.get(p["verdict"], 0) + 1
        return {"tenant_id": self.tenant_id, "as_of": now.isoformat(),
                "schedules": {"total": len(schedules), "active": sum(s["active"] for s in schedules),
                              "due_now": due_now},
                "proposals": {"total": len(proposals), "by_state": counts, "overdue": len(overdue),
                              "verdicts": verdicts},
                "overdue": overdue, "recent": proposals[-20:][::-1]}


def tenants_with_schedules(root) -> list[str]:
    """Tenants that have schedules under a store root (for the beat task)."""
    from pathlib import Path
    path = Path(root) / "m04-rerun-schedules.sqlite"
    if not path.exists():
        return []
    with sqlite3.connect(path) as db:
        return [r[0] for r in db.execute("SELECT DISTINCT tenant_id FROM schedules WHERE active=1 ORDER BY tenant_id")]
