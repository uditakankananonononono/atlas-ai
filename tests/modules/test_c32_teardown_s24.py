"""S2.4 / c32.teardown tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c32/teardown.py"
_spec = importlib.util.spec_from_file_location("c32_teardown", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c32_teardown"] = m
_spec.loader.exec_module(m)

DOC = {"brand": "Scentco", "text": ("Scentco is made of cedar and amber. "
       "The founder started it in 2019. It is marketed through influencer ads. "
       "It became a viral bestseller. The packaging could be better."),
       "sources": ["https://pinterest.example/pin/1"]}


class Teardown(unittest.TestCase):
    def test_dimensions_extracted_with_citations(self):
        out = m.teardown(DOC)
        self.assertEqual(out["brand"], "Scentco")
        self.assertEqual(out["dimension_count"], 6)
        self.assertEqual(out["dimensions_covered"], 6)  # packaging sentence hits improvement + appeal
        self.assertIn("cedar", out["dimensions"]["product_composition"][0])
        self.assertEqual(out["sources_count"], 1)

    def test_count_reported_not_millions(self):
        out = m.teardown({"brand": "B", "text": "Nothing relevant here."})
        self.assertEqual(out["dimensions_covered"], 0)
        self.assertEqual(out["dimension_count"], 6)
        self.assertIn("fixed-checklist", out["scope"]["implemented"][0])

    def test_affiliate_signup_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.teardown(dict(DOC, affiliate_signup=True))
        self.assertEqual(str(cm.exception), "TREND_REFUSED_AUTOSIGNUP")

    def test_determinism(self):
        self.assertEqual(m.teardown(DOC), m.teardown(DOC))

    def test_bad_inputs(self):
        with self.assertRaises(ValueError) as cm:
            m.teardown("x")
        self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:doc")
        with self.assertRaises(ValueError) as cm:
            m.teardown({"brand": "B\nC", "text": "t"})
        self.assertEqual(str(cm.exception), "TREND_REFUSED_CONTROL_CHARS:brand")
        with self.assertRaises(ValueError) as cm:
            m.teardown({"brand": "B", "text": "t", "sources": "x"})
        self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:sources")


class SentencePins(unittest.TestCase):
    def test_sentence_split_and_tail(self):
        # auditor survivors teardown-44/48
        self.assertEqual(m._sentences("one. two! three?"), ["one.", "two!", "three?"])
        self.assertEqual(m._sentences("no ending punctuation"), ["no ending punctuation"])
        self.assertEqual(m._sentences(""), [])


if __name__ == "__main__":
    unittest.main()
