"""Persistence-agnostic monitoring orchestration for public collectors.

The application scheduler can call ``CollectorMonitor.run`` and persist the returned
result atomically.  This module performs no scheduling or database writes itself.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Protocol
from .freshness import ChangeSet, FreshnessPolicy, FreshnessState, SourceSnapshot, compare, freshness_state, snapshot
from .public_sources import CollectionPage, PublicRecord


class SnapshotStore(Protocol):
    async def load(self, source_id: str) -> SourceSnapshot | None: ...
    async def save(self, value: SourceSnapshot) -> None: ...


@dataclass(frozen=True, slots=True)
class MonitorResult:
    source_id: str
    started_at: datetime
    completed_at: datetime
    record_count: int
    pages_collected: int
    changes: ChangeSet
    previous_freshness: FreshnessState


class CollectorMonitor:
    def __init__(self, store: SnapshotStore, *, clock: Callable[[], datetime] | None = None) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def run(
        self, source_id: str, fetch_page: Callable[[str | None], Awaitable[CollectionPage]],
        *, freshness_policy: FreshnessPolicy, max_pages: int = 100,
    ) -> MonitorResult:
        if max_pages < 1:
            raise ValueError("max_pages must be positive")
        started_at = self._clock()
        previous = await self._store.load(source_id)
        prior_state = freshness_state(
            previous.collected_at if previous else None,
            now=started_at,
            policy=freshness_policy,
        )
        records: list[PublicRecord] = []
        seen_ids: set[str] = set()
        seen_cursors: set[str] = set()
        cursor: str | None = None
        pages = 0
        while True:
            page = await fetch_page(cursor)
            pages += 1
            for record in page.records:
                if record.external_id in seen_ids:
                    raise ValueError(f"collector returned duplicate record id: {record.external_id}")
                seen_ids.add(record.external_id)
                records.append(record)
            cursor = page.next_cursor
            if cursor is None:
                break
            if cursor in seen_cursors:
                raise ValueError(f"collector cursor loop detected: {cursor}")
            seen_cursors.add(cursor)
            if pages >= max_pages:
                raise RuntimeError(f"collector exceeded max_pages={max_pages}")
        completed_at = self._clock()
        current = snapshot(source_id, records, collected_at=completed_at)
        changes = compare(previous, current)
        await self._store.save(current)
        return MonitorResult(
            source_id=source_id, started_at=started_at, completed_at=completed_at,
            record_count=len(records), pages_collected=pages, changes=changes,
            previous_freshness=prior_state,
        )


@dataclass(frozen=True, slots=True)
class MonitorScheduleHint:
    interval: timedelta
    run_after: datetime


def next_run(*, last_completed_at: datetime, interval: timedelta, now: datetime) -> MonitorScheduleHint:
    """Return a scheduler hint without sleeping or mutating shared scheduler state."""
    if interval <= timedelta(0):
        raise ValueError("interval must be positive")
    if last_completed_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    due = last_completed_at + interval
    return MonitorScheduleHint(interval=interval, run_after=max(due, now))
