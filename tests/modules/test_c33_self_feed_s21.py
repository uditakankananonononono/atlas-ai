"""S2.1 / c33.self_feed tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c33/self_feed.py"
_spec = importlib.util.spec_from_file_location("c33_self_feed", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c33_self_feed"] = m
_spec.loader.exec_module(m)

EXPORT = {"liked": [{"id": "l1", "text": "new lip gloss launch"},
                    {"id": "l2", "text": "my skincare routine"},
                    {"id": "l3", "text": "this app uses ai to study"}],
          "follows": [{"handle": "@maker"}, {"handle": "@studytok"}]}


class SelfFeed(unittest.TestCase):
    def test_clustering_and_briefs(self):
        out = m.analyze(EXPORT)
        self.assertEqual(out["theme_counts"]["beauty"], 2)
        self.assertEqual(out["theme_counts"]["tech"], 1)
        self.assertEqual(out["theme_counts"]["study"], 1)  # 'study' in l3 too
        self.assertEqual(out["top_themes"][0], "beauty")
        self.assertEqual(out["brief_count"], 3)
        self.assertIn("similar-but-better", out["briefs"][0]["draft"])
        self.assertEqual(out["follow_count"], 2)

    def test_no_export_refused(self):
        for bad in (None, True, "x", {}, {"liked": []}):
            with self.assertRaises(ValueError) as cm:
                m.analyze(bad)
            self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_NOEXPORT")

    def test_private_third_party_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.analyze({"liked": [], "follows": [{"handle": "@x", "private": True}]})
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_THIRDPARTYPRIVATE")

    def test_control_chars_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.analyze({"liked": [{"id": "l", "text": "a\nb"}], "follows": []})
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_CONTROL_CHARS:liked_text")

    def test_determinism_and_scope(self):
        self.assertEqual(m.analyze(EXPORT), m.analyze(EXPORT))
        out = m.analyze(EXPORT)
        self.assertIn("private third-party data", out["scope"]["not_implemented"])


class SelfFeedPins(unittest.TestCase):
    def test_oversize_pins(self):
        # auditor survivors self_feed-3/6: each side of the OR trips alone
        with self.assertRaises(ValueError) as cm:
            m.analyze({"liked": [{}] * (m.MAX_ITEMS + 1), "follows": []})
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_OVERSIZE")
        with self.assertRaises(ValueError) as cm:
            m.analyze({"liked": [], "follows": [{}] * (m.MAX_ITEMS + 1)})
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_OVERSIZE")

    def test_row_dict_pins(self):
        # auditor survivors self_feed-7/8
        with self.assertRaises(ValueError) as cm:
            m.analyze({"liked": ["x"], "follows": []})
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:liked")
        with self.assertRaises(ValueError) as cm:
            m.analyze({"liked": [], "follows": ["x"]})
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:follow")


if __name__ == "__main__":
    unittest.main()
