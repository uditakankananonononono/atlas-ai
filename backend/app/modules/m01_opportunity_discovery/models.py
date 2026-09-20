"""Canonical types for opportunity discovery.

The module deliberately keeps source payloads out of the business model. Every
record carries enough provenance to reproduce the source fetch and explain each
transformation.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Any, Mapping, Sequence


class OpportunityKind(str, Enum):
    GRANT = "grant"
    PROCUREMENT = "procurement"
    FELLOWSHIP = "fellowship"
    PRIZE = "prize"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class Provenance:
    source: str
    source_id: str
    source_url: str
    fetched_at: datetime
    raw_sha256: str
    adapter_version: str = "1"

    def __post_init__(self) -> None:
        if self.fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
        if not self.source or not self.source_id or not self.source_url:
            raise ValueError("source, source_id and source_url are required")


@dataclass(frozen=True, slots=True)
class Opportunity:
    id: str
    title: str
    description: str
    kind: OpportunityKind
    sponsor: str
    source_status: str
    open_date: date | None
    close_date: date | None
    amount_min: int | None
    amount_max: int | None
    currency: str | None
    countries: tuple[str, ...]
    eligibility: tuple[str, ...]
    tags: tuple[str, ...]
    canonical_url: str
    provenance: tuple[Provenance, ...]
    updated_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self) -> None:
        if not self.id or not self.title.strip() or not self.canonical_url:
            raise ValueError("id, title, and canonical_url are required")
        if self.amount_min is not None and self.amount_min < 0:
            raise ValueError("amount_min cannot be negative")
        if self.amount_max is not None and self.amount_max < 0:
            raise ValueError("amount_max cannot be negative")
        if self.amount_min is not None and self.amount_max is not None and self.amount_min > self.amount_max:
            raise ValueError("amount_min cannot exceed amount_max")
        if not self.provenance:
            raise ValueError("at least one provenance record is required")

    @property
    def is_open(self) -> bool:
        today = datetime.now(timezone.utc).date()
        return (self.open_date is None or self.open_date <= today) and (self.close_date is None or self.close_date >= today)

    def with_provenance(self, items: Sequence[Provenance]) -> "Opportunity":
        return replace(self, provenance=tuple(items))


@dataclass(frozen=True, slots=True)
class SearchQuery:
    text: str
    kinds: tuple[OpportunityKind, ...] = ()
    countries: tuple[str, ...] = ()
    eligibility: tuple[str, ...] = ()
    min_amount: int | None = None
    closes_after: date | None = None
    limit: int = 50

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("text is required")
        if not 1 <= self.limit <= 500:
            raise ValueError("limit must be between 1 and 500")


@dataclass(frozen=True, slots=True)
class RankedOpportunity:
    opportunity: Opportunity
    score: float
    reasons: tuple[str, ...]


def stable_digest(value: Any) -> str:
    import json
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
