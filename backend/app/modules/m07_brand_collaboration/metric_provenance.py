"""Check media-kit / report metric claims against the partnership ledger.

Claims are only VERIFIED when metric-kind ledger events inside the inclusive UTC
reporting period sum to the claimed number. Everything else is labelled
pessimistically. Pure functions; no database, no network.
Ledger metric event shape: PartnershipEventIn(kind="metric", data={"metric": str, "value": number}).
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Mapping

VERIFIED, PARTIAL, UNSUPPORTED, INVALID = "VERIFIED", "PARTIAL", "UNSUPPORTED", "INVALID"


class PeriodError(ValueError):
    pass


@dataclass(frozen=True)
class MetricVerdict:
    metric: str
    claimed: float
    ledger_total: float | None
    event_count: int
    label: str
    reason: str


def utc_bounds(start: date, end: date, today: date | None = None) -> tuple[datetime, datetime]:
    """Inclusive date range -> [start 00:00 UTC, end+1day 00:00 UTC)."""
    if end < start:
        raise PeriodError("period_end precedes period_start")
    if today is not None and end > today:
        raise PeriodError("period_end is in the future")
    lo = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    hi = datetime(end.year, end.month, end.day, tzinfo=timezone.utc) + timedelta(days=1)
    return lo, hi


def _event_fields(ev):
    get = (lambda k: ev.get(k)) if isinstance(ev, Mapping) else (lambda k: getattr(ev, k, None))
    return get("kind"), get("occurred_at"), get("data")


def verify_metrics(claims: Mapping[str, float], events: Iterable, start: date, end: date,
                   today: date | None = None, rel_tol: float = 1e-9) -> list[MetricVerdict]:
    lo, hi = utc_bounds(start, end, today)
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for ev in events:
        kind, at, data = _event_fields(ev)
        if kind != "metric" or not isinstance(data, Mapping):
            continue
        if not isinstance(at, datetime) or at.tzinfo is None:
            continue  # naive timestamps cannot be placed in a UTC period
        name, val = data.get("metric"), data.get("value")
        if not isinstance(name, str) or isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
            continue
        if lo <= at.astimezone(timezone.utc) < hi:
            totals[name] = totals.get(name, 0.0) + float(val)
            counts[name] = counts.get(name, 0) + 1
    out = []
    for name in sorted(claims):
        c = claims[name]
        if not isinstance(c, (int, float)) or not math.isfinite(c) or c < 0:
            out.append(MetricVerdict(name, c, None, 0, INVALID, "claim must be a finite non-negative number"))
        elif name not in totals:
            out.append(MetricVerdict(name, c, None, 0, UNSUPPORTED, "no ledger metric events in period"))
        elif math.isclose(totals[name], c, rel_tol=rel_tol, abs_tol=1e-12):
            out.append(MetricVerdict(name, c, totals[name], counts[name], VERIFIED, "ledger total equals claim"))
        else:
            out.append(MetricVerdict(name, c, totals[name], counts[name], PARTIAL, "ledger total differs from claim"))
    return out


def summary(verdicts: Iterable[MetricVerdict]) -> dict[str, int]:
    s = {VERIFIED: 0, PARTIAL: 0, UNSUPPORTED: 0, INVALID: 0}
    for v in verdicts:
        s[v.label] += 1
    s["total"] = sum(s.values())
    return s
