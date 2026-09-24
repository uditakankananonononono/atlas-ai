"""M16 card for M04 scheduled re-run proposals.

Read-only view over M04's RerunScheduleService.stats(): it never files, approves,
pauses or executes anything. Missing or broken M04 degrades to available=False
so the rest of the dashboard still renders.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, Field

OVERDUE_LIMIT = 10
RECENT_LIMIT = 5
STATES = ("pending", "approved_not_executed", "executed", "denied", "expired")


class RerunProposalRow(BaseModel):
    schedule_id: str
    original_approval_id: str
    rerun_approval_id: str
    state: str
    filed_at: str
    age_hours: float
    overdue: bool = False
    verdict: str | None = None


class RerunScheduleCard(BaseModel):
    available: bool
    reason: str | None = None
    as_of: datetime
    schedules_total: int = 0
    schedules_active: int = 0
    schedules_due_now: int = 0
    proposals_total: int = 0
    by_state: dict[str, int] = Field(default_factory=dict)
    awaiting_approval: int = 0
    approved_not_executed: int = 0
    overdue_total: int = 0
    verdicts: dict[str, int] = Field(default_factory=dict)
    overdue: list[RerunProposalRow] = Field(default_factory=list)
    recent: list[RerunProposalRow] = Field(default_factory=list)


def _row(item: dict[str, Any]) -> RerunProposalRow:
    return RerunProposalRow(**{k: item.get(k) for k in RerunProposalRow.model_fields if k in item})


def build_card(stats: dict[str, Any]) -> RerunScheduleCard:
    schedules = stats.get("schedules") or {}
    proposals = stats.get("proposals") or {}
    by_state = {s: int((proposals.get("by_state") or {}).get(s, 0)) for s in STATES}
    for s, n in (proposals.get("by_state") or {}).items():
        by_state.setdefault(s, int(n))
    overdue = [_row(i) for i in stats.get("overdue") or []]
    overdue.sort(key=lambda r: r.age_hours, reverse=True)
    as_of = stats.get("as_of")
    return RerunScheduleCard(
        available=True,
        as_of=datetime.fromisoformat(as_of) if as_of else datetime.now(timezone.utc),
        schedules_total=int(schedules.get("total", 0)),
        schedules_active=int(schedules.get("active", 0)),
        schedules_due_now=len(schedules.get("due_now") or []),
        proposals_total=int(proposals.get("total", 0)),
        by_state=by_state,
        awaiting_approval=by_state["pending"],
        approved_not_executed=by_state["approved_not_executed"],
        overdue_total=int(proposals.get("overdue", len(overdue))),
        verdicts={k: int(v) for k, v in (proposals.get("verdicts") or {}).items()},
        overdue=overdue[:OVERDUE_LIMIT],
        recent=[_row(i) for i in (stats.get("recent") or [])[:RECENT_LIMIT]],
    )


def unavailable(reason: str) -> RerunScheduleCard:
    return RerunScheduleCard(available=False, reason=reason, as_of=datetime.now(timezone.utc))


def card_for(stats_source: Callable[[], dict[str, Any]] | None) -> RerunScheduleCard:
    if stats_source is None:
        return unavailable("M04 research scientist module is not installed")
    try:
        return build_card(stats_source())
    except Exception as exc:  # the card must never break the dashboard
        return unavailable(f"M04 re-run stats unavailable: {type(exc).__name__}")


def m04_stats_source(tenant) -> Callable[[], dict[str, Any]] | None:
    """Tenant-scoped reader over M04's schedule stats (same executor the M04 routes use)."""
    try:
        from app.modules.m04_research_scientist.routes import get_sandbox_executor
        from app.modules.m04_research_scientist.rerun_schedule import RerunScheduleService
    except ImportError:
        return None
    return lambda: RerunScheduleService(get_sandbox_executor(tenant)).stats()
