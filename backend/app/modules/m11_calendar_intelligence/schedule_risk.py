"""Read-only schedule risk analysis with explicit evidence and policy boundaries."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class CancellationTerms(BaseModel):
    free_cancel_until: datetime | None = None
    cancellation_fee: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    source_ref: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_money(self):
        if (self.cancellation_fee is None) != (self.currency is None):
            raise ValueError("cancellation_fee and currency must be supplied together")
        return self


class ScheduleItem(BaseModel):
    item_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    start: datetime
    end: datetime
    location: str | None = Field(default=None, max_length=500)
    travel_minutes_before: int = Field(default=0, ge=0, le=1440)
    prep_minutes: int = Field(default=0, ge=0, le=1440)
    depends_on: list[str] = Field(default_factory=list, max_length=100)
    cancellation: CancellationTerms | None = None

    @model_validator(mode="after")
    def valid_window(self):
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("start and end must be timezone-aware")
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class ScheduleRiskRequest(BaseModel):
    items: list[ScheduleItem] = Field(min_length=1, max_length=1000)
    completed_dependency_ids: set[str] = Field(default_factory=set)
    as_of: datetime | None = None

    @model_validator(mode="after")
    def unique_items(self):
        ids = [item.item_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate item_id")
        return self


def analyze_schedule_risk(request: ScheduleRiskRequest) -> dict:
    as_of = request.as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    as_of = as_of.astimezone(timezone.utc)
    by_id = {item.item_id: item for item in request.items}
    risks = []

    for item in sorted(request.items, key=lambda row: (row.start, row.item_id)):
        required_start = item.start - timedelta(minutes=item.travel_minutes_before + item.prep_minutes)
        previous = [row for row in request.items if row.item_id != item.item_id and row.end <= item.start]
        prior = max(previous, key=lambda row: row.end, default=None)
        if prior and prior.end > required_start:
            risks.append({
                "item_id": item.item_id, "kind": "insufficient_buffer", "severity": "high",
                "evidence": {"previous_item_id": prior.item_id, "previous_end": prior.end.isoformat(),
                             "required_ready_start": required_start.isoformat(),
                             "travel_minutes": item.travel_minutes_before, "prep_minutes": item.prep_minutes,
                             "shortfall_minutes": int((prior.end-required_start).total_seconds()//60)},
            })
        missing = sorted(dep for dep in item.depends_on if dep not in request.completed_dependency_ids)
        unknown = sorted(dep for dep in missing if dep not in by_id)
        if missing:
            risks.append({"item_id": item.item_id, "kind": "dependency_incomplete", "severity": "high",
                          "evidence": {"incomplete_dependency_ids": missing, "unknown_dependency_ids": unknown}})
        terms = item.cancellation
        if terms:
            if terms.free_cancel_until is not None and terms.free_cancel_until.tzinfo is None:
                raise ValueError(f"free_cancel_until must be timezone-aware: {item.item_id}")
            deadline = terms.free_cancel_until.astimezone(timezone.utc) if terms.free_cancel_until else None
            if deadline and deadline < as_of:
                state = "free_window_expired"
            elif deadline and deadline - as_of <= timedelta(hours=24):
                state = "free_window_closing"
            else:
                state = "terms_recorded"
            severity = "high" if state == "free_window_expired" and terms.cancellation_fee else "medium"
            risks.append({"item_id": item.item_id, "kind": "cancellation_exposure", "severity": severity,
                          "evidence": {"state": state, "free_cancel_until": deadline.isoformat() if deadline else None,
                                       "cancellation_fee": terms.cancellation_fee, "currency": terms.currency,
                                       "source_ref": terms.source_ref,
                                       "terms_unverified": terms.source_ref is None}})

    order = {"high": 0, "medium": 1, "low": 2}
    risks.sort(key=lambda row: (order[row["severity"]], row["item_id"], row["kind"]))
    canonical = json.dumps(risks, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {
        "as_of": as_of.isoformat(), "item_count": len(request.items), "risk_count": len(risks),
        "high_risk_count": sum(row["severity"] == "high" for row in risks), "risks": risks,
        "risk_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "boundary": "This is a read-only analysis of caller-supplied schedule and cancellation terms. Atlas does not verify travel time or vendor policy, change events, cancel bookings, or spend money.",
    }
