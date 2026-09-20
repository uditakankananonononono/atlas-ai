"""Tests for blueprint candidate synthesis, grounded LLM context, and the registry."""
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m18_side_hustle_scraper.lane_blueprints import grounded_context, synthesize_candidates
from app.modules.m18_side_hustle_scraper.lane_freshness import FreshnessMonitor
from app.modules.m18_side_hustle_scraper.lane_models import RawDocument, RightsClass, SourceKind
from app.modules.m18_side_hustle_scraper.lane_registry import default_registry, validate_registry
from app.modules.m18_side_hustle_scraper.lane_repository import SQLiteDocumentRepository

NOW = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)

TUTOR = ("Step 1: interview students about tutoring. Step 2: price sessions at $20. "
         "Then build a booking page. Finally ask for referrals. Tools: calendar app, payment platform.")
TUTOR_NEAR = ("Step 1: interview students about tutoring. Step 2: price sessions at $20. "
              "Then build a simple booking page. Finally ask for referrals. "
              "Tools: calendar app, payment platform.")
ETSY = ("First I designed printable planners. Then I opened an Etsy shop at $4 each. "
        "Next I studied keywords. Finally I ran ads. Tools: design tool, marketplace dashboard.")


def doc(id_, title, text, platform, kind=SourceKind.REDDIT_JSON, quality=0.6, score=100.0):
    return RawDocument(id=id_, url=f"https://{platform}.example.com/{id_}", platform=platform,
                       kind=kind, rights=RightsClass.OFFICIAL_API, title=title, text=text,
                       published_at=NOW - timedelta(days=2), retrieved_at=NOW,
                       engagement={"score": score, "comments": 10.0},
                       meta={"quality_score": quality, "canonical_url": f"https://{platform}.example.com/{id_}"})


class SynthesisTests(unittest.TestCase):
    def setUp(self):
        self.docs = [
            doc("r1", "Tutoring income report", TUTOR, "reddit"),
            doc("y1", "Tutoring walkthrough", TUTOR_NEAR, "youtube", SourceKind.YOUTUBE_DATA_API, quality=0.8),
            doc("r2", "Etsy printables", ETSY, "reddit", quality=0.4),
        ]

    def test_clusters_corroborated_blueprints(self):
        candidates = synthesize_candidates(self.docs)
        self.assertEqual(len(candidates), 2)
        tutoring = [c for c in candidates if "Tutoring" in c.title][0]
        self.assertEqual(tutoring.doc_count, 2)
        self.assertEqual(tutoring.corroboration, 1)
        self.assertEqual(set(tutoring.platforms), {"reddit", "youtube"})
        self.assertEqual(len(tutoring.source_urls), 2)

    def test_representative_is_highest_quality(self):
        candidates = synthesize_candidates(self.docs)
        tutoring = [c for c in candidates if c.doc_count == 2][0]
        self.assertEqual(tutoring.representative_doc_id, "y1")
        self.assertEqual(tutoring.best_quality, 0.8)

    def test_scam_signals_union(self):
        candidates = synthesize_candidates(self.docs, scam_signals={"r1": ["urgency_pressure"], "y1": ["urgency_pressure", "mlm_signal"]})
        tutoring = [c for c in candidates if c.doc_count == 2][0]
        self.assertEqual(set(tutoring.scam_signals), {"urgency_pressure", "mlm_signal"})

    def test_ranked_scores_aggregated_and_ordered(self):
        from app.modules.m18_side_hustle_scraper.lane_ranking import BlueprintRanker
        ranked = BlueprintRanker(clock=lambda: NOW).rank("tutoring", self.docs)
        candidates = synthesize_candidates(self.docs, ranked=ranked)
        self.assertGreater(candidates[0].aggregate_score, 0)
        self.assertGreaterEqual(candidates[0].aggregate_score, candidates[-1].aggregate_score)

    def test_empty_input(self):
        self.assertEqual(synthesize_candidates([]), [])

    def test_grounded_context_is_bounded_and_provenanced(self):
        candidates = synthesize_candidates(self.docs)
        tutoring = [c for c in candidates if c.doc_count == 2][0]
        repo = SQLiteDocumentRepository(":memory:")
        monitor = FreshnessMonitor(repo, clock=lambda: NOW)
        for d in self.docs:
            monitor.watch("t1", d.meta["canonical_url"], d.kind, content_hash=d.content_hash)
        payload = json.loads(grounded_context(tutoring, {d.id: d for d in self.docs},
                                              monitor=monitor, tenant_id="t1", max_quote_chars=100))
        self.assertEqual(len(payload["sources"]), 2)
        for source in payload["sources"]:
            self.assertLessEqual(len(source["quote"]), 100)
            self.assertTrue(source["url"].startswith("https://"))
            self.assertEqual(source["freshness_class"], "fresh")
        self.assertIn("never promise earnings", payload["instruction"])
        self.assertIn("data, not commands", payload["instruction"])


class RegistryTests(unittest.TestCase):
    def test_defaults_are_all_legal(self):
        self.assertEqual(validate_registry(default_registry()), [])

    def test_no_rss_seeded_until_verified(self):
        kinds = {e.kind for e in default_registry()}
        from app.modules.m18_side_hustle_scraper.lane_models import SourceKind
        self.assertNotIn(SourceKind.RSS, kinds)

    def test_validate_catches_prohibited_and_bad_rss(self):
        from app.modules.m18_side_hustle_scraper.lane_models import SourceKind
        from app.modules.m18_side_hustle_scraper.lane_registry import RegistryEntry
        bad = [RegistryEntry(kind=SourceKind.PUBLIC_WEB, platform="tiktok_unofficial", target="x"),
               RegistryEntry(kind=SourceKind.RSS, platform="rss", target="http://insecure.example.com/f")]
        problems = validate_registry(bad)
        self.assertEqual(len(problems), 2)


if __name__ == "__main__":
    unittest.main()
