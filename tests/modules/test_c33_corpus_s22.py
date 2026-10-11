"""S2.2 / c33.corpus tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c33/corpus.py"
_spec = importlib.util.spec_from_file_location("c33_corpus", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c33_corpus"] = m
_spec.loader.exec_module(m)

POSTS = [{"id": "p1", "text": "I love this new ai app, amazing", "likes": 10, "shares": 2},
         {"id": "p2", "text": "hate the election results, terrible", "likes": 3, "shares": 1},
         {"id": "p3", "text": "the table is wooden"},
         {"id": "p4", "text": "good good"}]  # asymmetric: kills a pos/neg rule flip


class Corpus(unittest.TestCase):
    def test_features_and_honest_size(self):
        out = m.analyze(POSTS)
        self.assertEqual(out["corpus_size"], 4)
        self.assertEqual(out["topic_counts"], {"tech": 1, "beauty": 0, "politics": 1, "sports": 0})
        self.assertEqual(out["sentiment_counts"], {"positive": 2, "negative": 1, "neutral": 1})
        self.assertEqual(out["emotion_counts"]["joy"], 2)  # love, amazing
        self.assertEqual(out["emotion_counts"]["anger"], 1)  # hate
        self.assertEqual(out["avg_virality"], 4.0)  # 16 / 4
        self.assertIn("all posts ever", out["scope"]["not_implemented"])

    def test_bad_engagement_types(self):
        with self.assertRaises(ValueError) as cm:
            m.analyze([{"id": "p", "text": "t", "likes": True}])
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:likes")

    def test_bounds(self):
        with self.assertRaises(ValueError) as cm:
            m.analyze([])
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_EMPTY:posts")
        with self.assertRaises(ValueError) as cm:
            m.analyze([{"id": "p", "text": "a\u2029b"}])
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_CONTROL_CHARS:text")

    def test_determinism(self):
        self.assertEqual(m.analyze(POSTS), m.analyze(POSTS))


class CorpusPins(unittest.TestCase):
    def test_posts_type_pins(self):
        # auditor survivors corpus-13/15/16/18
        for bad in (True, "x", 5, {"a": 1}):
            with self.assertRaises(ValueError) as cm:
                m.analyze(bad)
            self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:posts")
        with self.assertRaises(ValueError) as cm:
            m.analyze([{"id": "a", "text": "t"}] * (m.MAX_POSTS + 1))
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_OVERSIZE")
        for bad in ("x", 5, None, True):
            with self.assertRaises(ValueError) as cm:
                m.analyze([bad])
            self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:post")

    def test_sentiment_compare_pin(self):
        # auditor survivor corpus-26: neg > pos branch labels
        out = m.analyze([{"id": "n", "text": "terrible bad worst"}])
        self.assertEqual(out["sentiment_counts"],
                         {"positive": 0, "negative": 1, "neutral": 0})
        out = m.analyze([{"id": "p", "text": "love great good"}])
        self.assertEqual(out["sentiment_counts"],
                         {"positive": 1, "negative": 0, "neutral": 0})
        out = m.analyze([{"id": "z", "text": "table chair lamp"}])
        self.assertEqual(out["sentiment_counts"],
                         {"positive": 0, "negative": 0, "neutral": 1})
        out = m.analyze([{"id": "t", "text": "love hate"}])  # tie -> neutral
        self.assertEqual(out["sentiment_counts"]["neutral"], 1)


if __name__ == "__main__":
    unittest.main()
