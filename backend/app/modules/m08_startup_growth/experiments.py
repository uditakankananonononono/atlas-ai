"""Free-first growth experiment board (M08 enhancement).

Each experiment card records a hypothesis, one metric with a success
threshold, and a cap on time and effort using free tools only. Observed
results are appended as they come in, and every stop/continue decision is
recorded with its reason. The board derives the rest: conversion rate with a
Wilson interval, days and hours used against the cap, and a suggested call
(``success`` / ``fail`` / ``inconclusive``).

Free-first is enforced, not advised:

- a card cannot list a tool or channel with a cost, or one whose name says
  paid (ads, boosted, sponsored, promoted, paid ...) - it is refused;
- ``continue`` is refused once a cap is hit, unless the owner first extends
  the cap with a written reason;
- a paid idea can only be filed as a *proposal*: a Module 0 approval request
  that records the estimate and rationale. Even when approved it performs
  nothing - the board never spends, buys, boosts or connects a card. The
  owner acts herself if she chooses.

Tenant-scoped SQL, append-only events, no network.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine
from app.core.models import ApprovalRequest

MODULE_ID = 8
PAID_WORDS = re.compile(r"\b(ads?|adwords|boost(ed|ing)?|sponsor(ed|ship)?|promoted|paid|ppc|cpc|cpm|influencer fee|budget)\b", re.I)
DECISIONS = {"stop", "continue", "scale_free", "pivot"}


class ExperimentRow(Base):
    __tablename__ = "m08_experiment_cards"
    pk: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(Text)
    hypothesis: Mapped[str] = mapped_column(Text)
    metric: Mapped[str] = mapped_column(String(200))
    success_rate: Mapped[float] = mapped_column(Float)
    baseline_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_days: Mapped[int] = mapped_column(Integer)
    max_effort_hours: Mapped[float] = mapped_column(Float)
    tools: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExperimentEventRow(Base):
    __tablename__ = "m08_experiment_events"
    pk: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    experiment_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data: Mapped[dict] = mapped_column(JSON)


class ExperimentNotFound(LookupError):
    pass


class ExperimentRefused(ValueError):
    pass


def _aware(v: datetime) -> datetime:
    return v if v.tzinfo else v.replace(tzinfo=timezone.utc)


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 1.0
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def paid_reasons(tools: list[dict[str, Any]]) -> list[str]:
    out = []
    for t in tools:
        name = str(t.get("name", "")).strip()
        if float(t.get("cost_minor", 0) or 0) > 0:
            out.append(f"{name or 'tool'} has a cost")
        elif PAID_WORDS.search(name) or PAID_WORDS.search(str(t.get("note", ""))):
            out.append(f"{name} looks paid")
    return out


class ExperimentBoard:
    def __init__(self, tenant_id: str, *, approvals: Any, session_factory: sessionmaker = SessionLocal,
                 clock: Callable[[], datetime] | None = None):
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        self.tenant_id = tenant_id.strip()
        self.approvals = approvals
        self.sessions = session_factory
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        Base.metadata.create_all(engine)

    # -- writes -----------------------------------------------------------
    def create(self, *, title: str, hypothesis: str, metric: str, success_rate: float, max_days: int,
               max_effort_hours: float, tools: list[dict[str, Any]], baseline_rate: float | None = None) -> dict[str, Any]:
        if not hypothesis.strip() or not metric.strip():
            raise ExperimentRefused("hypothesis and metric are required")
        if not 0 < success_rate <= 1:
            raise ExperimentRefused("success_rate is a conversion rate between 0 and 1")
        if max_days < 1 or max_effort_hours <= 0:
            raise ExperimentRefused("a cap needs at least 1 day and some effort hours")
        if not tools:
            raise ExperimentRefused("list the free tools/channels the experiment uses")
        paid = paid_reasons(tools)
        if paid:
            raise ExperimentRefused("free tools only: " + "; ".join(paid) + ". File the paid idea as a proposal instead.")
        eid, now = str(uuid4()), self.clock()
        with self.sessions.begin() as db:
            db.add(ExperimentRow(tenant_id=self.tenant_id, id=eid, title=title, hypothesis=hypothesis.strip(),
                                 metric=metric.strip(), success_rate=success_rate, baseline_rate=baseline_rate,
                                 max_days=max_days, max_effort_hours=max_effort_hours,
                                 tools=[{"name": t["name"], "cost_minor": 0, "note": t.get("note", "")} for t in tools],
                                 created_at=now))
            db.add(self._ev(eid, "created", {}, now))
        return self.get(eid)

    def observe(self, experiment_id: str, *, exposures: int, conversions: int, effort_hours: float = 0.0,
                source: str = "", note: str = "") -> dict[str, Any]:
        if exposures < 0 or conversions < 0 or conversions > exposures:
            raise ExperimentRefused("need 0 <= conversions <= exposures")
        if effort_hours < 0:
            raise ExperimentRefused("effort_hours cannot be negative")
        card = self.get(experiment_id)
        if card["state"] == "stopped":
            raise ExperimentRefused("experiment is stopped; start a new card")
        return self._append(experiment_id, "observed", {"exposures": exposures, "conversions": conversions,
                                                        "effort_hours": effort_hours, "source": source, "note": note})

    def decide(self, experiment_id: str, *, decision: str, reason: str) -> dict[str, Any]:
        if decision not in DECISIONS:
            raise ExperimentRefused(f"decision must be one of {sorted(DECISIONS)}")
        if len(reason.strip()) < 3:
            raise ExperimentRefused("every decision needs a reason")
        card = self.get(experiment_id)
        if card["state"] == "stopped":
            raise ExperimentRefused("experiment is already stopped")
        if decision in {"continue", "scale_free"} and card["cap"]["hit"]:
            raise ExperimentRefused("cap reached (" + ", ".join(card["cap"]["hit"]) +
                                    "); extend the cap with a reason first, or stop")
        return self._append(experiment_id, "decided", {"decision": decision, "reason": reason.strip(),
                                                       "suggested": card["suggestion"]})

    def extend_cap(self, experiment_id: str, *, add_days: int = 0, add_effort_hours: float = 0.0,
                   reason: str) -> dict[str, Any]:
        if add_days < 0 or add_effort_hours < 0 or (add_days == 0 and add_effort_hours == 0):
            raise ExperimentRefused("extend by a positive number of days or hours")
        if len(reason.strip()) < 3:
            raise ExperimentRefused("extending a cap needs a reason")
        if self.get(experiment_id)["state"] == "stopped":
            raise ExperimentRefused("experiment is stopped")
        return self._append(experiment_id, "cap_extended", {"add_days": add_days, "add_effort_hours": add_effort_hours,
                                                            "reason": reason.strip()})

    def propose_paid(self, experiment_id: str, *, description: str, estimated_cost_minor: int, currency: str,
                     rationale: str) -> dict[str, Any]:
        """File a paid idea for the owner's decision. Never executes anything."""
        if estimated_cost_minor <= 0:
            raise ExperimentRefused("a paid proposal needs its estimated cost")
        card = self.get(experiment_id)
        payload = {"tenant_id": self.tenant_id, "experiment_id": experiment_id, "experiment": card["title"],
                   "description": description, "estimated_cost_minor": estimated_cost_minor, "currency": currency,
                   "rationale": rationale, "evidence": card["result"],
                   "execution": "none - Atlas records the owner's decision only; it never spends"}
        req = self.approvals.put(ApprovalRequest(id=str(uuid4()), module_id=MODULE_ID,
                                                 action_type="paid_experiment_proposal", payload=payload),
                                 user_id=self.tenant_id)
        self._append(experiment_id, "paid_proposed", {"approval_id": req.id, "description": description,
                                                      "estimated_cost_minor": estimated_cost_minor, "currency": currency})
        return {"approval_id": req.id, "status": "pending_owner_decision", "payload": payload}

    # -- reads ------------------------------------------------------------
    def get(self, experiment_id: str) -> dict[str, Any]:
        with self.sessions() as db:
            row = db.scalar(select(ExperimentRow).where(ExperimentRow.tenant_id == self.tenant_id,
                                                        ExperimentRow.id == experiment_id))
        if row is None:
            raise ExperimentNotFound(experiment_id)
        return self._derive(row, self._events(experiment_id))

    def board(self) -> dict[str, Any]:
        with self.sessions() as db:
            rows = list(db.scalars(select(ExperimentRow).where(ExperimentRow.tenant_id == self.tenant_id)
                                   .order_by(ExperimentRow.created_at)))
        cards = [self._derive(r, self._events(r.id)) for r in rows]
        columns: dict[str, list] = {"running": [], "needs_decision": [], "stopped": []}
        for c in cards:
            columns[c["state"]].append(c)
        return {"columns": columns, "total": len(cards), "spend_executed_minor": 0}

    # -- internals --------------------------------------------------------
    def _ev(self, eid: str, kind: str, data: dict[str, Any], at: datetime) -> ExperimentEventRow:
        return ExperimentEventRow(tenant_id=self.tenant_id, experiment_id=eid, kind=kind, at=at, data=data)

    def _append(self, eid: str, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        with self.sessions.begin() as db:
            db.add(self._ev(eid, kind, data, self.clock()))
        return self.get(eid)

    def _events(self, eid: str) -> list[ExperimentEventRow]:
        with self.sessions() as db:
            return list(db.scalars(select(ExperimentEventRow).where(
                ExperimentEventRow.tenant_id == self.tenant_id, ExperimentEventRow.experiment_id == eid)
                .order_by(ExperimentEventRow.at, ExperimentEventRow.pk)))

    def _derive(self, row: ExperimentRow, events: list[ExperimentEventRow]) -> dict[str, Any]:
        now = self.clock()
        obs = [e.data for e in events if e.kind == "observed"]
        exposures = sum(int(o["exposures"]) for o in obs)
        conversions = sum(int(o["conversions"]) for o in obs)
        effort = round(sum(float(o["effort_hours"]) for o in obs), 2)
        ext = [e.data for e in events if e.kind == "cap_extended"]
        max_days = row.max_days + sum(int(x["add_days"]) for x in ext)
        max_hours = row.max_effort_hours + sum(float(x["add_effort_hours"]) for x in ext)
        days = (now - _aware(row.created_at)).total_seconds() / 86400
        hit = []
        if days >= max_days:
            hit.append("time")
        if effort >= max_hours:
            hit.append("effort")
        lo, hi = wilson(conversions, exposures)
        if exposures == 0:
            suggestion = "no_data"
        elif lo >= row.success_rate:
            suggestion = "success"
        elif hi < row.success_rate:
            suggestion = "fail"
        else:
            suggestion = "inconclusive"
        if hit and suggestion in {"inconclusive", "no_data"}:
            suggestion = "stop_inconclusive"
        decisions = [dict(e.data, at=_aware(e.at).isoformat()) for e in events if e.kind == "decided"]
        last = decisions[-1]["decision"] if decisions else None
        if last == "stop":
            state = "stopped"
        elif hit or suggestion in {"success", "fail"}:
            state = "needs_decision"
        else:
            state = "running"
        return {
            "id": row.id, "title": row.title, "hypothesis": row.hypothesis,
            "metric": {"name": row.metric, "success_rate": row.success_rate, "baseline_rate": row.baseline_rate},
            "tools": row.tools,
            "cap": {"max_days": max_days, "max_effort_hours": max_hours, "days_used": round(days, 2),
                    "effort_hours_used": effort, "hit": hit, "extensions": ext},
            "result": {"exposures": exposures, "conversions": conversions,
                       "rate": round(conversions / exposures, 4) if exposures else None,
                       "ci95": [round(lo, 4), round(hi, 4)]},
            "suggestion": suggestion, "state": state, "decisions": decisions,
            "paid_proposals": [e.data for e in events if e.kind == "paid_proposed"],
            "observations": obs,
        }
