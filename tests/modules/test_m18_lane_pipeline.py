"""End-to-end pipeline tests: collect -> validate -> persist -> rank -> refresh."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m18_side_hustle_scraper.lane_freshness import FreshnessConfig, FreshnessMonitor, SourceStatus
from app.modules.m18_side_hustle_scraper.lane_models import RawDocument, RightsClass, SourceKind
from app.modules.m18_side_hustle_scraper.lane_pipeline import CollectionPipeline
from app.modules.m18_side_hustle_scraper.lane_ranking import BlueprintRanker, RankUserContext
from app.modules.m18_side_hustle_scraper.lane_repository import SQLiteDocumentRepository
from app.modules.m18_side_hustle_scraper.lane_validation import DocumentValidator

NOW = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)

TUTOR = ("Step 1: interview students about tutoring. Step 2: price sessions at $20. "
         "Then build a booking page. Finally ask for referrals. Tools: calendar app, payment platform.")
ETSY = ("First I designed printable planners. Then I opened an Etsy shop at $4 each. "
        "Next I studied keywords. Finally I ran ads. Tools: design tool, marketplace dashboard.")
TUTOR_PARAPHRASE = ("Step 1: interview students about tutoring. Step 2: price sessions at $20. "
                    "Then build a simple booking page. Finally ask for referrals. "
                    "Tools: calendar app, payment platform.")
SCAM = "Guaranteed income! Double your crypto, risk free. DM me to join, only 3 spots left!"


class FakeCollector:
    def __init__(self, platform, docs):
        self.platform = platform
        self._docs = docs
        self.calls = []

    def collect(self, query, limit):
        self.calls.append((query, limit))
        return list(self._docs)[:limit], []


def make_doc(id_, title, text, platform, kind):
    return RawDocument(id=id_, url=f"https://{platform}.example.com/{id_}", platform=platform,
                       kind=kind, rights=RightsClass.OFFICIAL_API, title=title, text=text,
                       published_at=NOW - timedelta(days=3), retrieved_at=NOW,
                       engagement={"score": 100.0, "comments": 30.0})


def build_pipeline(repo=None):
    repo = repo or SQLiteDocumentRepository(":memory:")
    monitor = FreshnessMonitor(repo, clock=lambda: NOW)
    collectors = {
        "reddit": FakeCollector("reddit", [
            make_doc("r1", "Tutoring income report", TUTOR, "reddit", SourceKind.REDDIT_JSON),
            make_doc("r2", "Etsy printables journey", ETSY, "reddit", SourceKind.REDDIT_JSON),
            make_doc("r3", "Easy money system", SCAM, "reddit", SourceKind.REDDIT_JSON),
        ]),
        "youtube": FakeCollector("youtube", [
            make_doc("y1", "Tutoring business walkthrough", TUTOR_PARAPHRASE, "youtube", SourceKind.YOUTUBE_DATA_API),
        ]),
    }
    pipeline = CollectionPipeline(
        repository=repo,
        validator=DocumentValidator(),
        ranker=BlueprintRanker(clock=lambda: NOW),
        monitor=monitor,
        collectors=collectors,
    )
    return pipeline, repo, monitor


class CollectionRunTests(unittest.TestCase):
    def test_collect_filters_scam_and_persists_clean(self):
        pipeline, repo, _ = build_pipeline()
        report = pipeline.run_collection("t1", "tutoring business", ["reddit", "youtube"], 20)
        self.assertEqual(report.documents_found, 4)
        self.assertEqual(report.documents_new, 3)
        self.assertEqual(report.documents_rejected, 1)
        self.assertEqual(repo.count("t1"), 3)
        reddit = [p for p in report.platforms if p.platform == "reddit"][0]
        self.assertEqual(reddit.rejected, 1)
        self.assertTrue(any("scam" in r for r in reddit.rejection_reasons))

    def test_second_run_is_idempotent(self):
        pipeline, repo, _ = build_pipeline()
        pipeline.run_collection("t1", "tutoring", ["reddit", "youtube"], 20)
        report = pipeline.run_collection("t1", "tutoring", ["reddit", "youtube"], 20)
        self.assertEqual(report.documents_new, 0)
        self.assertGreaterEqual(report.documents_duplicate, 3)
        self.assertEqual(repo.count("t1"), 3)

    def test_unconfigured_collector_reported_not_raised(self):
        pipeline, _, _ = build_pipeline()
        report = pipeline.run_collection("t1", "tutoring", ["rss"], 20)
        self.assertIn("collector_not_configured", report.platforms[0].errors[0])

    def test_prohibited_platform_raises_loudly(self):
        pipeline, _, _ = build_pipeline()
        with self.assertRaises(ValueError):
            pipeline.run_collection("t1", "dance hacks", ["tiktok_unofficial"], 20)

    def test_collection_registers_freshness_watches(self):
        pipeline, repo, _ = build_pipeline()
        pipeline.run_collection("t1", "tutoring", ["reddit", "youtube"], 20)
        self.assertEqual(len(repo.iter_watched("t1")), 3)

    def test_empty_tenant_and_query_rejected(self):
        pipeline, _, _ = build_pipeline()
        with self.assertRaises(ValueError):
            pipeline.run_collection("", "q", ["reddit"], 5)
        with self.assertRaises(ValueError):
            pipeline.run_collection("t1", "  ", ["reddit"], 5)


class RankingIntegrationTests(unittest.TestCase):
    def test_ranked_returns_explainable_ordered_results(self):
        pipeline, _, _ = build_pipeline()
        pipeline.run_collection("t1", "tutoring", ["reddit", "youtube"], 20)
        ranked = pipeline.ranked("t1", "online tutoring")
        self.assertEqual(len(ranked), 3)
        scores = [r.score for r in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))
        top = ranked[0]
        self.assertTrue(top.breakdown)
        self.assertEqual(top.rank, 1)
        corroborated = [r for r in ranked if len(r.corroborating_platforms) > 1]
        self.assertTrue(corroborated, "tutoring docs should cluster across reddit+youtube")

    def test_user_context_shapes_order(self):
        pipeline, _, _ = build_pipeline()
        pipeline.run_collection("t1", "business", ["reddit", "youtube"], 20)
        ranked = pipeline.ranked("t1", "business ideas",
                                 user=RankUserContext(skills=("design",), excluded_categories=()))
        etsy = [r for r in ranked if "Etsy" in r.title][0]
        fit = [b for b in etsy.breakdown if b.signal == "user_fit"][0]
        self.assertGreater(fit.raw_value, 0.5)

    def test_stale_evidence_scores_lower(self):
        pipeline, repo, monitor = build_pipeline()
        pipeline.run_collection("t1", "tutoring", ["reddit", "youtube"], 20)
        fresh_scores = {r.doc_id: r.score for r in pipeline.ranked("t1", "tutoring")}
        # age every watched source far past its ttl by rewriting state
        for source in repo.iter_watched("t1"):
            source.last_changed_at = NOW - timedelta(days=30)
            repo.upsert_watched(source)
        stale_scores = {r.doc_id: r.score for r in pipeline.ranked("t1", "tutoring")}
        for doc_id in fresh_scores:
            self.assertLess(stale_scores[doc_id], fresh_scores[doc_id])


class RefreshTests(unittest.TestCase):
    def test_refresh_detects_change_and_updates_interval(self):
        pipeline, repo, monitor = build_pipeline()
        pipeline.run_collection("t1", "tutoring", ["reddit"], 20)
        due = monitor.due_sources("t1")
        self.assertEqual(len(due), 2)  # clean reddit docs, never checked -> due immediately
        url = due[0].url
        before = repo.get_watched("t1", url).interval_seconds

        def refetcher(u, kind):
            if u == url:
                return {"status": 200, "content_hash": "changed-hash"}
            return {"status": 304, "not_modified": True}

        report = pipeline.run_refresh("t1", refetcher)
        self.assertEqual(report.sources_checked, 2)
        self.assertEqual(report.changes_detected, 1)
        after = repo.get_watched("t1", url).interval_seconds
        self.assertLess(after, before)

    def test_refresh_marks_dead_sources(self):
        pipeline, repo, _ = build_pipeline()
        pipeline.run_collection("t1", "tutoring", ["reddit"], 20)
        url = repo.iter_watched("t1")[0].url

        def refetcher(u, kind):
            return {"status": 404 if u == url else 304, "not_modified": u != url}

        report = pipeline.run_refresh("t1", refetcher)
        self.assertIn(url, report.dead_sources)
        self.assertEqual(repo.get_watched("t1", url).status, SourceStatus.DEAD)

    def test_refresh_records_event(self):
        pipeline, repo, _ = build_pipeline()
        pipeline.run_collection("t1", "tutoring", ["reddit"], 20)
        pipeline.run_refresh("t1", lambda u, k: {"status": 304, "not_modified": True})
        kinds = [e["kind"] for e in repo.events("t1")]
        self.assertIn("freshness_refresh", kinds)


if __name__ == "__main__":
    unittest.main()
