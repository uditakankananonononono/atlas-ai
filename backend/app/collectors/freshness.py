"""Pure freshness/change evaluation used by collector monitoring jobs."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Iterable, Mapping
from .public_sources import PublicRecord


class FreshnessState(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    NEVER_COLLECTED = "never_collected"
    CLOCK_SKEW = "clock_skew"


@dataclass(frozen=True, slots=True)
class FreshnessPolicy:
    max_age: timedelta
    clock_skew_tolerance: timedelta = timedelta(minutes=5)

    def __post_init__(self) -> None:
        if self.max_age <= timedelta(0):
            raise ValueError("max_age must be positive")
        if self.clock_skew_tolerance < timedelta(0):
            raise ValueError("clock_skew_tolerance cannot be negative")


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    source_id: str
    collected_at: datetime
    record_hashes: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ChangeSet:
    added: tuple[str, ...]
    changed: tuple[str, ...]
    removed: tuple[str, ...]
    unchanged: tuple[str, ...]


def freshness_state(
    collected_at: datetime | None, *, now: datetime, policy: FreshnessPolicy
) -> FreshnessState:
    if collected_at is None:
        return FreshnessState.NEVER_COLLECTED
    if collected_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("freshness timestamps must be timezone-aware")
    age = now - collected_at
    if age < -policy.clock_skew_tolerance:
        return FreshnessState.CLOCK_SKEW
    return FreshnessState.STALE if age > policy.max_age else FreshnessState.FRESH


def snapshot(source_id: str, records: Iterable[PublicRecord], *, collected_at: datetime) -> SourceSnapshot:
    hashes: dict[str, str] = {}
    for record in records:
        if record.provenance.source_id != source_id:
            raise ValueError(f"record {record.external_id} belongs to another source")
        if record.external_id in hashes:
            raise ValueError(f"duplicate record id: {record.external_id}")
        hashes[record.external_id] = record.content_hash
    return SourceSnapshot(source_id, collected_at, hashes)


def compare(previous: SourceSnapshot | None, current: SourceSnapshot) -> ChangeSet:
    old = previous.record_hashes if previous else {}
    new = current.record_hashes
    old_ids, new_ids = set(old), set(new)
    common = old_ids & new_ids
    return ChangeSet(
        added=tuple(sorted(new_ids - old_ids)),
        changed=tuple(sorted(key for key in common if old[key] != new[key])),
        removed=tuple(sorted(old_ids - new_ids)),
        unchanged=tuple(sorted(key for key in common if old[key] == new[key])),
    )
