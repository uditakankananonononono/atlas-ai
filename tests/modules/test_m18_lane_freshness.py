"""Unit tests for Module 18 freshness monitoring."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m18_side_hustle_scraper.lane_freshness import (
    DEAD_FACTOR,
    FACTOR_FOR_CLASS,
    FreshnessClass,
    FreshnessConfig,
    FreshnessMonitor,
    SourceStatus,
)
from app.modules.m18_side_hustle_scraper.lane_models import SourceKind
from app.modules.m18_side_hustle_scraper.lane_repository import SQLiteDocumentRepository

T0 = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now

    def advance(self, **kw):
        self.now += timedelta(**kw)


class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.repo = SQLiteDocumentRepository(":memory:")
        self.monitor = FreshnessMonitor(self.repo, clock=self.clock)
        self.url = "https://blog.example.com/feed.xml"

    def test_watch_register_idempotent(self):
        w1 = self.monitor.watch("t1", self.url, SourceKind.RSS)
        w2 = self.monitor.watch("t1", self.url, SourceKind.RSS)
        self.assertEqual(w1.interval_seconds, w2.interval_seconds)
        self.assertEqual(len(self.repo.iter_watched("t1")), 1)

    def test_never_checked_source_is_due(self):
        self.monitor.watch("t1", self.url, SourceKind.RSS)
        self.assertEqual(len(self.monitor.due_sources("t1")), 1)

    def test_not_due_until_interval_passes(self):
        self.monitor.watch("t1", self.url, SourceKind.RSS)
        self.monitor.record_fetch("t1", self.url, status=200, content_hash="h1")
        self.assertEqual(len(self.monitor.due_sources("t1")), 0)
        self.clock.advance(hours=7)
        self.assertEqual(len(self.monitor.due_sources("t1")), 1)

    def test_change_detection_shrinks_interval(self):
        self.monitor.watch("t1", self.url, SourceKind.RSS)
        self.monitor.record_fetch("t1", self.url, status=200, content_hash="h1")
        base = self.repo.get_watched("t1", self.url).interval_seconds
        rec = self.monitor.record_fetch("t1", self.url, status=200, content_hash="h2")
        self.assertTrue(rec.change_detected)
        after = self.repo.get_watched("t1", self.url).interval_seconds
        self.assertLess(after, base)

    def test_unchanged_grows_interval_and_304_counts_unchanged(self):
        self.monitor.watch("t1", self.url, SourceKind.RSS)
        self.monitor.record_fetch("t1", self.url, status=200, content_hash="h1", etag="e1")
        base = self.repo.get_watched("t1", self.url).interval_seconds
        rec = self.monitor.record_fetch("t1", self.url, status=304, not_modified=True, etag="e1")
        self.assertFalse(rec.change_detected)
        after = self.repo.get_watched("t1", self.url).interval_seconds
        self.assertGreater(after, base)
        self.assertEqual(self.repo.get_watched("t1", self.url).consecutive_unchanged, 1)

    def test_etag_change_detected_without_hash_change(self):
        self.monitor.watch("t1", self.url, SourceKind.RSS)
        self.monitor.record_fetch("t1", self.url, status=200, etag="e1")
        rec = self.monitor.record_fetch("t1", self.url, status=200, etag="e2")
        self.assertTrue(rec.change_detected)

    def test_classification_by_evidence_age(self):
        self.monitor.watch("t1", self.url, SourceKind.RSS)  # ttl 12h
        self.monitor.record_fetch("t1", self.url, status=200, content_hash="h1")
        self.assertEqual(self.monitor.classification("t1", self.url), FreshnessClass.FRESH)
        self.clock.advance(hours=18)
        self.assertEqual(self.monitor.classification("t1", self.url), FreshnessClass.AGING)
        self.clock.advance(hours=12)
        self.assertEqual(self.monitor.classification("t1", self.url), FreshnessClass.STALE)
        self.clock.advance(hours=30)
        self.assertEqual(self.monitor.classification("t1", self.url), FreshnessClass.EXPIRED)

    def test_factor_decays_and_dead_source_floors(self):
        self.monitor.watch("t1", self.url, SourceKind.RSS)
        self.monitor.record_fetch("t1", self.url, status=200, content_hash="h1")
        self.assertEqual(self.monitor.factor("t1", self.url), 1.0)
        self.clock.advance(hours=18)
        self.assertEqual(self.monitor.factor("t1", self.url), FACTOR_FOR_CLASS[FreshnessClass.AGING])
        self.monitor.record_fetch("t1", self.url, status=404)
        self.assertEqual(self.monitor.factor("t1", self.url), DEAD_FACTOR)

    def test_404_kills_source_immediately_and_stops_due(self):
        self.monitor.watch("t1", self.url, SourceKind.RSS)
        self.monitor.record_fetch("t1", self.url, status=200, content_hash="h1")
        rec = self.monitor.record_fetch("t1", self.url, status=404)
        self.assertEqual(rec.status, SourceStatus.DEAD)
        self.assertEqual(len(self.monitor.due_sources("t1")), 0)
        events = [e for e in self.repo.events("t1") if e["kind"] == "freshness_source_dead"]
        self.assertEqual(len(events), 1)

    def test_repeated_errors_kill_source(self):
        cfg = FreshnessConfig(error_threshold=3)
        monitor = FreshnessMonitor(self.repo, cfg, clock=self.clock)
        monitor.watch("t1", self.url, SourceKind.RSS)
        for i in range(3):
            monitor.record_fetch("t1", self.url, error="timeout")
            self.clock.advance(hours=7)
        self.assertEqual(self.repo.get_watched("t1", self.url).status, SourceStatus.DEAD)

    def test_unwatch_marks_dead(self):
        self.monitor.watch("t1", self.url, SourceKind.RSS)
        self.assertTrue(self.monitor.unwatch("t1", self.url))
        self.assertFalse(self.monitor.unwatch("t1", "https://never.seen/"))
        self.assertEqual(len(self.monitor.due_sources("t1")), 0)

    def test_state_survives_monitor_restart_via_store(self):
        self.monitor.watch("t1", self.url, SourceKind.RSS)
        self.monitor.record_fetch("t1", self.url, status=200, content_hash="h1", etag="e9")
        rebooted = FreshnessMonitor(self.repo, clock=self.clock)
        source = self.repo.get_watched("t1", self.url)
        self.assertEqual(source.content_hash, "h1")
        self.assertEqual(source.etag, "e9")
        self.assertEqual(rebooted.classification("t1", self.url), FreshnessClass.FRESH)

    def test_report_aggregates(self):
        self.monitor.watch("t1", self.url, SourceKind.RSS)
        self.monitor.watch("t1", "https://x.example.com/f", SourceKind.PUBLIC_WEB)
        self.monitor.record_fetch("t1", self.url, status=200, content_hash="h1")
        self.monitor.record_fetch("t1", "https://x.example.com/f", status=410)
        report = self.monitor.report("t1")
        self.assertEqual(report["watched"], 2)
        self.assertEqual(report["dead"], 1)
        self.assertEqual(report["by_class"].get("fresh"), 1)

    def test_tenant_isolation(self):
        self.monitor.watch("t1", self.url, SourceKind.RSS)
        self.assertEqual(self.monitor.due_sources("t2"), [])
        self.assertEqual(self.monitor.report("t2")["watched"], 0)


if __name__ == "__main__":
    unittest.main()
