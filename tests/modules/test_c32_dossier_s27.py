"""S2.7 / c32.dossier tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c32/dossier.py"
_spec = importlib.util.spec_from_file_location("c32_dossier", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c32_dossier"] = m
_spec.loader.exec_module(m)

SRC = [{"url": "https://en.wikipedia.example/wiki/Ada",
        "text": ("Ada Lovelace was born in 1815. Ada Lovelace worked with Babbage. "
                 "Ada Lovelace founded nothing but launched the first algorithm. "
                 "Ada Lovelace received wide recognition posthumously. Unrelated sentence here.")}]


class Dossier(unittest.TestCase):
    def test_cited_facts_and_completeness(self):
        out = m.dossier("Ada Lovelace", SRC)
        self.assertEqual(out["dimension_count"], 5)
        self.assertEqual(out["dimensions_covered"], 4)
        self.assertEqual(out["completeness"], 0.8)
        self.assertEqual(out["citation_count"], 5)  # founded+launched sentence cites two dimensions
        self.assertEqual(out["dimensions"]["background"][0]["source"],
                         "https://en.wikipedia.example/wiki/Ada")
        self.assertNotIn("Unrelated", str(out["dimensions"]))

    def test_private_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.dossier("Ada Lovelace", SRC, include_private=True)
        self.assertEqual(str(cm.exception), "TREND_REFUSED_PRIVATE")

    def test_no_full_coverage_claim(self):
        out = m.dossier("Ada Lovelace", SRC)
        self.assertIn("every-single-thing coverage", out["scope"]["not_implemented"])

    def test_determinism(self):
        self.assertEqual(m.dossier("Ada Lovelace", SRC), m.dossier("Ada Lovelace", SRC))

    def test_bad_inputs(self):
        with self.assertRaises(ValueError) as cm:
            m.dossier("A", [])
        self.assertEqual(str(cm.exception), "TREND_REFUSED_EMPTY:sources")
        with self.assertRaises(ValueError) as cm:
            m.dossier("A\nB", SRC)
        self.assertEqual(str(cm.exception), "TREND_REFUSED_CONTROL_CHARS:subject")
        with self.assertRaises(ValueError) as cm:
            m.dossier("A", SRC * (m.MAX_SOURCES + 1))
        self.assertEqual(str(cm.exception), "TREND_REFUSED_OVERSIZE")


class DossierPins(unittest.TestCase):
    def test_sentence_split_and_tail(self):
        # auditor survivor dossier-18
        self.assertEqual(m._sentences("one. two! three?"), ["one.", "two!", "three?"])
        self.assertEqual(m._sentences("tail with no period"), ["tail with no period"])

    def test_sources_type_pins(self):
        # auditor survivors dossier-20/25/27
        for bad in (True, "x", 5):
            with self.assertRaises(ValueError) as cm:
                m.dossier("Jane Doe", bad)
            self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:sources")
        with self.assertRaises(ValueError) as cm:
            m.dossier("Jane Doe", ["x"])
        self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:source")

    def test_subject_mention_filter(self):
        # auditor survivor dossier-30: sentences not mentioning the subject excluded
        out = m.dossier("Jane Doe", [{"url": "u1",
                                      "text": "Jane Doe founded a company. The weather is nice this year."}])
        self.assertEqual(out["citation_count"], 2)  # career + ventures dims
        facts = [f["fact"] for d in out["dimensions"].values() for f in d]
        self.assertEqual(facts, ["Jane Doe founded a company.", "Jane Doe founded a company."])
        self.assertFalse(any("weather" in f for f in facts))


if __name__ == "__main__":
    unittest.main()
