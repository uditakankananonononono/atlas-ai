import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from app.collectors.freshness import FreshnessPolicy, FreshnessState
from app.collectors.monitoring import CollectorMonitor, next_run
from app.collectors.public_sources import CollectionPage, Provenance, PublicRecord

NOW = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)


class Store:
    def __init__(self): self.value = None
    async def load(self, source_id): return self.value
    async def save(self, value): self.value = value


def rec(n, title=None):
    p = Provenance("source", "Source", "https://example.org", f"https://example.org/{n}", NOW)
    return PublicRecord(f"source:{n}", "grant", title or f"Title {n}", None, None, None,
                        None, None, None, f"https://example.org/{n}", p)


def run(coro): return asyncio.run(coro)


def test_monitor_consumes_pages_persists_snapshot_and_reports_changes():
    store = Store()
    ticks = iter([NOW, NOW + timedelta(seconds=2)])
    monitor = CollectorMonitor(store, clock=lambda: next(ticks))
    async def fetch(cursor):
        return CollectionPage((rec(1),), NOW, "next", 1) if cursor is None else CollectionPage((rec(2),), NOW, None, 1)
    result = run(monitor.run("source", fetch, freshness_policy=FreshnessPolicy(timedelta(hours=1))))
    assert result.pages_collected == 2
    assert result.record_count == 2
    assert result.changes.added == ("source:1", "source:2")
    assert result.previous_freshness is FreshnessState.NEVER_COLLECTED
    assert set(store.value.record_hashes) == {"source:1", "source:2"}


def test_monitor_does_not_save_partial_snapshot_on_duplicate_or_cursor_loop():
    store = Store()
    monitor = CollectorMonitor(store, clock=lambda: NOW)
    async def duplicate(cursor):
        return CollectionPage((rec(1),), NOW, "next", 1) if cursor is None else CollectionPage((rec(1),), NOW, None, 1)
    with pytest.raises(ValueError, match="duplicate"):
        run(monitor.run("source", duplicate, freshness_policy=FreshnessPolicy(timedelta(hours=1))))
    assert store.value is None
    async def loop(cursor): return CollectionPage((), NOW, "same", 0)
    with pytest.raises(ValueError, match="cursor loop"):
        run(monitor.run("source", loop, freshness_policy=FreshnessPolicy(timedelta(hours=1))))
    assert store.value is None


def test_monitor_applies_page_cap_before_persisting():
    store = Store()
    monitor = CollectorMonitor(store, clock=lambda: NOW)
    async def endless(cursor): return CollectionPage((), NOW, str(int(cursor or "0") + 1), 0)
    with pytest.raises(RuntimeError, match="max_pages"):
        run(monitor.run("source", endless, freshness_policy=FreshnessPolicy(timedelta(hours=1)), max_pages=2))
    assert store.value is None


def test_next_run_returns_due_time_or_now_for_overdue_work():
    interval = timedelta(hours=6)
    assert next_run(last_completed_at=NOW, interval=interval, now=NOW).run_after == NOW + interval
    later = NOW + timedelta(hours=8)
    assert next_run(last_completed_at=NOW, interval=interval, now=later).run_after == later
