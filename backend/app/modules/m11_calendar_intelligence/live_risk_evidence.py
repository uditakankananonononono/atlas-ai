"""Verify retrieved map estimates and vendor cancellation snapshots for schedule risk."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


class RetrievalMethod(str, Enum):
    OFFICIAL_API = "official_api"
    VENDOR_PAGE = "vendor_page"


class SourceSnapshot(BaseModel):
    source_uri: str = Field(min_length=1, max_length=2000)
    retrieved_at: datetime
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieval_method: RetrievalMethod
    snapshot_bytes_base64_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def aware_retrieval(self):
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return self


class TravelEstimate(BaseModel):
    estimate_id: str = Field(min_length=1, max_length=200)
    provider: str = Field(min_length=1, max_length=200)
    origin: str = Field(min_length=1, max_length=1000)
    destination: str = Field(min_length=1, max_length=1000)
    mode: str = Field(min_length=1, max_length=100)
    duration_minutes: int = Field(ge=0, le=10080)
    route_distance_meters: int | None = Field(default=None, ge=0)
    source: SourceSnapshot
    source_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CancellationPolicy(BaseModel):
    policy_id: str = Field(min_length=1, max_length=200)
    vendor: str = Field(min_length=1, max_length=300)
    booking_reference_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    free_cancel_until: datetime | None = None
    cancellation_fee: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    policy_text_excerpt: str = Field(min_length=1, max_length=5000)
    source: SourceSnapshot
    source_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def valid_policy(self):
        if (self.cancellation_fee is None) != (self.currency is None):
            raise ValueError("cancellation_fee and currency must be supplied together")
        if self.free_cancel_until is not None and self.free_cancel_until.tzinfo is None:
            raise ValueError("free_cancel_until must be timezone-aware")
        return self


class LiveRiskEvidenceRequest(BaseModel):
    as_of: datetime
    max_age_minutes: int = Field(default=60, ge=1, le=10080)
    travel_estimates: list[TravelEstimate] = Field(default_factory=list, max_length=1000)
    cancellation_policies: list[CancellationPolicy] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def unique_ids(self):
        if self.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        ids = [row.estimate_id for row in self.travel_estimates] + [row.policy_id for row in self.cancellation_policies]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate evidence id")
        if not ids:
            raise ValueError("at least one retrieved evidence record is required")
        return self


def _verify_record(row: TravelEstimate | CancellationPolicy, as_of: datetime, max_age: timedelta) -> dict:
    source = row.source
    retrieved = source.retrieved_at.astimezone(timezone.utc)
    if retrieved > as_of:
        raise ValueError(f"retrieval time is after as_of: {row.estimate_id if isinstance(row, TravelEstimate) else row.policy_id}")
    if as_of - retrieved > max_age:
        raise ValueError(f"retrieved evidence is stale: {row.estimate_id if isinstance(row, TravelEstimate) else row.policy_id}")
    payload = row.model_dump(mode="json", exclude={"source_record_sha256"})
    actual = _hash(payload)
    if actual != row.source_record_sha256:
        raise ValueError(f"source record hash mismatch: {row.estimate_id if isinstance(row, TravelEstimate) else row.policy_id}")
    # Caller provides both the normalized-content digest and independently captured byte digest.
    # Equality proves the normalized record was made from the captured snapshot, not that the remote is truthful.
    if source.content_sha256 != source.snapshot_bytes_base64_sha256:
        raise ValueError("source content and captured snapshot hashes differ")
    return {"record_sha256": actual, "retrieved_at": retrieved.isoformat(), "source_uri": source.source_uri}


def verify_live_risk_evidence(request: LiveRiskEvidenceRequest) -> dict:
    as_of = request.as_of.astimezone(timezone.utc)
    age = timedelta(minutes=request.max_age_minutes)
    travel = []
    policies = []
    for row in sorted(request.travel_estimates, key=lambda item: item.estimate_id):
        receipt = _verify_record(row, as_of, age)
        travel.append({**row.model_dump(mode="json"), "verification": receipt})
    for row in sorted(request.cancellation_policies, key=lambda item: item.policy_id):
        receipt = _verify_record(row, as_of, age)
        policies.append({**row.model_dump(mode="json"), "verification": receipt})
    artifact = {"as_of": as_of.isoformat(), "travel_estimates": travel, "cancellation_policies": policies}
    return {
        "valid": True,
        **artifact,
        "artifact_sha256": _hash(artifact),
        "boundary": (
            "Atlas verifies hashes, retrieval times, freshness, and required provenance for supplied mapping and vendor-policy snapshots. "
            "It does not fetch the remote sources in this endpoint, authenticate the provider, prove route conditions or policy truth, "
            "change calendar events, cancel bookings, or spend money."
        ),
    }
