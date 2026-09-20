"""Unit tests for Module 18 explainable ranking."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m18_side_hustle_scraper.lane_models import RawDocument, RightsClass, SourceKind
from app.modules.m18_side_hustle_scraper.lane_ranking import (
    BlueprintRanker,
    RankUserContext,
    RankingConfig,
    bm25_score,
    cluster_documents,
)

NOW = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)


def doc(id_, title, text, platform="reddit", days_old=5, score=100.0, comments=20.0,
        kind=SourceKind.REDDIT_JSON, views=0.0):
    return RawDocument(
        id=id_, url=f"https://{platform}.example.com/{id_}", platform=platform, kind=kind,
        rights=RightsClass.OFFICIAL_API, title=title, text=text,
        published_at=NOW - timedelta(days=days_old), retrieved_at=NOW,
        engagement={"score": score, "comments": comments, "views": views},
    )


TUTOR = ("Step 1: interview students about tutoring. Step 2: set a price of $20 per session. "
         "Then build a calendar link. Finally ask for referrals. Tools: scheduling app, payment platform.")
ETSY = ("First I designed printable planners. Then I opened an Etsy shop and priced each at $4. "
        "Next I studied keywords. Finally I ran small ads. Tools: design platform, marketplace dashboard.")


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.ranker = BlueprintRanker(clock=lambda: NOW)

    def test_relevance_orders_results(self):
        on_topic = doc("a", "Online tutoring income report", TUTOR)
        off_topic = doc("b", "My cake recipe", "flour sugar eggs butter bake at 180 degrees cool then frost")
        ranked = self.ranker.rank("online tutoring business", [off_topic, on_topic])
        self.assertEqual(ranked[0].doc_id, "a")
        self.assertEqual(ranked[0].rank, 1)
        self.assertGreater(ranked[0].score, ranked[1].score)

    def test_recency_decay_prefers_fresh(self):
        fresh = doc("fresh", "Tutoring report", TUTOR, days_old=2)
        old = doc("old", "Tutoring report", TUTOR, days_old=360)
        ranked = self.ranker.rank("tutoring", [old, fresh])
        self.assertEqual(ranked[0].doc_id, "fresh")
        b = {p.signal: p for p in ranked[0].breakdown}
        self.assertAlmostEqual(b["recency"].raw_value, 0.5 ** (2 / 90.0), places=3)

    def test_score_is_explainable_and_bounded(self):
        ranked = self.ranker.rank("tutoring", [doc("a", "Tutoring", TUTOR)])
        self.assertEqual(len(ranked), 1)
        r = ranked[0]
        self.assertGreaterEqual(r.score, 0.0)
        self.assertLessEqual(r.score, 100.0)
        signals = {p.signal for p in r.breakdown}
        self.assertEqual(signals, {"relevance", "recency", "authority", "engagement",
                                   "quality", "corroboration", "user_fit"})
        positive = sum(p.contribution for p in r.breakdown)
        self.assertGreater(positive, 0)

    def test_corroboration_boosts_multi_platform_clusters(self):
        a = doc("a", "Tutoring blueprint", TUTOR, platform="reddit")
        b = doc("b", "Tutoring blueprint", TUTOR, platform="youtube", kind=SourceKind.YOUTUBE_DATA_API)
        c = doc("c", "Etsy printables", ETSY, platform="dev_to", kind=SourceKind.DEV_TO)
        ranked = self.ranker.rank("blueprint", [a, b, c], )
        by_id = {r.doc_id: r for r in ranked}
        self.assertEqual(by_id["a"].cluster_id, by_id["b"].cluster_id)
        self.assertNotEqual(by_id["a"].cluster_id, by_id["c"].cluster_id)
        self.assertEqual(set(by_id["a"].corroborating_platforms), {"reddit", "youtube"})
        corro_a = [p for p in by_id["a"].breakdown if p.signal == "corroboration"][0].raw_value
        corro_c = [p for p in by_id["c"].breakdown if p.signal == "corroboration"][0].raw_value
        self.assertGreater(corro_a, corro_c)

    def test_scam_penalty_subtracts_points(self):
        clean = doc("clean", "Tutoring", TUTOR)
        shady = doc("shady", "Tutoring", TUTOR)
        ranker = BlueprintRanker(clock=lambda: NOW,
                                 scam_signals={"shady": ["guaranteed_income", "urgency_pressure"]})
        ranked = ranker.rank("tutoring", [clean, shady])
        by_id = {r.doc_id: r for r in ranked}
        self.assertGreater(by_id["shady"].scam_penalty, 0)
        self.assertEqual(by_id["clean"].scam_penalty, 0)
        self.assertLess(by_id["shady"].score, by_id["clean"].score)

    def test_user_fit_excluded_category_sinks(self):
        d = doc("a", "Crypto trading bot tutoring", TUTOR + " crypto trading bot strategy")
        user = RankUserContext(skills=("teaching", "writing"), excluded_categories=("crypto",))
        ranked = self.ranker.rank("tutoring", [d], user=user)
        fit = [p for p in ranked[0].breakdown if p.signal == "user_fit"][0]
        self.assertEqual(fit.raw_value, 0.0)
        self.assertIn("excluded_category", fit.note)

    def test_user_fit_skill_overlap_boosts(self):
        d = doc("a", "Teaching writing online", "Step 1: teach writing workshops. Then charge $30. "
                "Tools: video platform. Finally get referrals from students you teach.")
        user = RankUserContext(skills=("teaching", "writing"))
        ranked = self.ranker.rank("writing workshops", [d], user=user)
        fit = [p for p in ranked[0].breakdown if p.signal == "user_fit"][0]
        self.assertGreater(fit.raw_value, 0.5)

    def test_freshness_factor_decays_scores(self):
        d = doc("a", "Tutoring", TUTOR)
        stale_ranker = BlueprintRanker(clock=lambda: NOW, freshness_factor=lambda doc: 0.5)
        fresh_score = self.ranker.rank("tutoring", [d])[0].score
        stale_score = stale_ranker.rank("tutoring", [d])[0].score
        self.assertAlmostEqual(stale_score, fresh_score * 0.5, places=1)

    def test_empty_and_single_doc(self):
        self.assertEqual(self.ranker.rank("x", []), [])
        ranked = self.ranker.rank("x", [doc("only", "x", "some body text about x and tools and $5")])
        self.assertEqual(ranked[0].rank, 1)

    def test_bm25_zero_on_empty(self):
        self.assertEqual(bm25_score([], ["a"], 1.0, {}, 1), 0.0)
        self.assertEqual(bm25_score(["a"], [], 1.0, {"a": 1}, 1), 0.0)

    def test_cluster_singletons(self):
        docs = [doc("a", "Tutoring", TUTOR), doc("b", "Etsy", ETSY)]
        clusters = cluster_documents(docs)
        self.assertNotEqual(clusters["a"], clusters["b"])


if __name__ == "__main__":
    unittest.main()
