"""Growth planning and cohort measurement workflows for module 08."""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from statistics import median
from typing import Iterable


class PlanningValidationError(ValueError):
    pass


class InitiativeStatus(str, Enum):
    BACKLOG = "backlog"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class GrowthInitiative:
    id: str
    title: str
    expected_impact: float
    confidence: float
    effort: float
    reach: int
    evidence_ids: tuple[str, ...] = ()
    owner: str | None = None
    status: InitiativeStatus = InitiativeStatus.BACKLOG
    dependencies: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.id or not self.title.strip():
            raise PlanningValidationError("initiative id and title are required")
        if self.reach < 0 or self.effort <= 0 or self.expected_impact < 0:
            raise PlanningValidationError("reach and impact cannot be negative; effort must be positive")
        if not 0 <= self.confidence <= 1:
            raise PlanningValidationError("confidence must be between 0 and 1")

    @property
    def rice_score(self) -> float:
        return self.reach * self.expected_impact * self.confidence / self.effort


class InitiativePortfolio:
    """Prioritize initiatives while preserving evidence and dependency constraints."""

    def __init__(self) -> None:
        self._items: dict[str, GrowthInitiative] = {}

    def add(self, item: GrowthInitiative) -> GrowthInitiative:
        if item.id in self._items:
            raise PlanningValidationError(f"initiative {item.id!r} already exists")
        if item.id in item.dependencies:
            raise PlanningValidationError("initiative cannot depend on itself")
        self._items[item.id] = item
        return item

    def ranked(self, *, require_evidence: bool = False, owner: str | None = None,
               statuses: set[InitiativeStatus] | None = None) -> list[dict]:
        rows = list(self._items.values())
        if require_evidence:
            rows = [row for row in rows if row.evidence_ids]
        if owner is not None:
            rows = [row for row in rows if row.owner == owner]
        if statuses is not None:
            rows = [row for row in rows if row.status in statuses]
        rows.sort(key=lambda row: (-row.rice_score, row.created_at, row.id))
        return [{"id": row.id, "title": row.title, "rice_score": row.rice_score,
                 "evidence_ids": list(row.evidence_ids), "owner": row.owner,
                 "status": row.status.value, "blocked_by": [d for d in row.dependencies
                 if d not in self._items or self._items[d].status != InitiativeStatus.DONE]}
                for row in rows]

    def ready(self) -> list[GrowthInitiative]:
        """Return planned work whose known dependencies are complete.

        Unknown dependency IDs remain blockers rather than silently being ignored.
        """
        result = []
        for item in self._items.values():
            if item.status not in {InitiativeStatus.BACKLOG, InitiativeStatus.PLANNED}:
                continue
            if all(d in self._items and self._items[d].status == InitiativeStatus.DONE
                   for d in item.dependencies):
                result.append(item)
        return sorted(result, key=lambda item: (-item.rice_score, item.id))


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    event_id: str
    subject_id: str
    occurred_at: datetime
    name: str
    value: float = 1.0
    segment: dict[str, str] = field(default_factory=dict)


class RetentionAnalyzer:
    """Build acquisition cohorts and measure period-N retained users.

    Acquisition is the first `acquisition_event`. A subject is retained in a period when
    it emits at least one `activity_event` during that exact half-open period. Events
    before acquisition are ignored. This produces classic non-cumulative retention.
    """

    def __init__(self, events: Iterable[LifecycleEvent]) -> None:
        event_list = list(events)
        ids = [event.event_id for event in event_list]
        if len(ids) != len(set(ids)):
            raise PlanningValidationError("lifecycle event ids must be unique")
        self.events = sorted(event_list, key=lambda e: (e.occurred_at, e.event_id))

    def cohorts(self, *, acquisition_event: str, activity_event: str,
                period_days: int = 7, periods: int = 8,
                segment: dict[str, str] | None = None) -> list[dict]:
        if period_days <= 0 or periods <= 0:
            raise PlanningValidationError("period_days and periods must be positive")
        selected = self.events
        if segment:
            selected = [e for e in selected if all(e.segment.get(k) == v for k, v in segment.items())]
        acquisitions: dict[str, datetime] = {}
        activity: dict[str, list[datetime]] = defaultdict(list)
        for event in selected:
            if event.name == acquisition_event:
                acquisitions.setdefault(event.subject_id, event.occurred_at)
            if event.name == activity_event:
                activity[event.subject_id].append(event.occurred_at)
        grouped: dict[date, list[tuple[str, datetime]]] = defaultdict(list)
        epoch = date(1970, 1, 5)  # Monday: stable week boundaries.
        for subject, acquired_at in acquisitions.items():
            days = (acquired_at.date() - epoch).days
            start = epoch + timedelta(days=(days // period_days) * period_days)
            grouped[start].append((subject, acquired_at))
        output = []
        for cohort_start in sorted(grouped):
            members = grouped[cohort_start]
            cells = []
            for period in range(periods):
                retained = 0
                for subject, acquired_at in members:
                    start = acquired_at + timedelta(days=period * period_days)
                    end = start + timedelta(days=period_days)
                    if any(start <= stamp < end for stamp in activity[subject]):
                        retained += 1
                cells.append({"period": period, "retained": retained,
                              "rate": retained / len(members)})
            output.append({"cohort_start": cohort_start.isoformat(), "size": len(members),
                           "period_days": period_days, "retention": cells})
        return output


@dataclass(frozen=True, slots=True)
class GrowthSnapshot:
    period: date
    acquired: int
    activated: int
    retained: int
    referred: int
    revenue: float
    active_users: int

    def __post_init__(self) -> None:
        values = (self.acquired, self.activated, self.retained, self.referred, self.active_users)
        if any(value < 0 for value in values) or self.revenue < 0:
            raise PlanningValidationError("snapshot values cannot be negative")
        if self.activated > self.acquired:
            raise PlanningValidationError("activated cannot exceed acquired")
        if self.retained > self.active_users:
            raise PlanningValidationError("retained cannot exceed active users")


class GrowthMeasurementWorkflow:
    """Produce AARRR metrics, trends, and anomaly signals from trusted snapshots."""

    @staticmethod
    def _divide(numerator: float, denominator: float) -> float | None:
        return numerator / denominator if denominator else None

    def scorecard(self, snapshots: Iterable[GrowthSnapshot]) -> dict:
        rows = sorted(snapshots, key=lambda row: row.period)
        if not rows:
            raise PlanningValidationError("at least one snapshot is required")
        if len({row.period for row in rows}) != len(rows):
            raise PlanningValidationError("only one snapshot is allowed per period")
        metrics = []
        for row in rows:
            metrics.append({
                "period": row.period.isoformat(), "acquisition": row.acquired,
                "activation_rate": self._divide(row.activated, row.acquired),
                "retention_rate": self._divide(row.retained, row.active_users),
                "referral_rate": self._divide(row.referred, row.active_users),
                "revenue_per_active_user": self._divide(row.revenue, row.active_users),
            })
        current = metrics[-1]
        previous = metrics[-2] if len(metrics) > 1 else None
        deltas = {}
        for key in ("acquisition", "activation_rate", "retention_rate", "referral_rate", "revenue_per_active_user"):
            old = previous[key] if previous else None
            new = current[key]
            deltas[key] = None if old in (None, 0) or new is None else (new - old) / abs(old)
        return {"periods": metrics, "current": current, "relative_change": deltas}

    def anomalies(self, snapshots: Iterable[GrowthSnapshot], *, z_threshold: float = 3.0) -> list[dict]:
        if z_threshold <= 0:
            raise PlanningValidationError("z_threshold must be positive")
        scorecard = self.scorecard(snapshots)["periods"]
        if len(scorecard) < 4:
            return []
        alerts = []
        keys = ("acquisition", "activation_rate", "retention_rate", "referral_rate", "revenue_per_active_user")
        for key in keys:
            history: list[float] = []
            for row in scorecard:
                value = row[key]
                if value is None:
                    continue
                if len(history) >= 3:
                    center = median(history)
                    deviations = [abs(x - center) for x in history]
                    mad = median(deviations)
                    # 0.6745 scales MAD to a normal-distribution z score.
                    z = 0.6745 * (value - center) / mad if mad else (math.inf if value != center else 0.0)
                    if abs(z) >= z_threshold:
                        alerts.append({"period": row["period"], "metric": key, "value": value,
                                       "baseline_median": center, "robust_z": z})
                history.append(float(value))
        return alerts
