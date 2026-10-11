"""S2.10 / c33.niches tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c33/niches.py"
_spec = importlib.util.spec_from_file_location("c33_niches", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c33_niches"] = m
_spec.loader.exec_module(m)


class Niches(unittest.TestCase):
    def test_enumeration_and_ranking(self):
        out = m.generate(["candle", "planner"], ["teens"], ["app", "kit"],
                         scores={"candle": {"trend": 8, "competition": 3},
                                 "planner": {"trend": 5, "competition": 5}})
        self.assertEqual(out["niche_count"], 4)
        self.assertEqual(out["niches"][0]["niche"], "candle for teens as app")
        self.assertEqual(out["niches"][0]["score"], 5)
        self.assertEqual([n["score"] for n in out["niches"]], [5, 5, 0, 0])
        # tie broken by name
        self.assertEqual([n["niche"] for n in out["niches"][:2]],
                         ["candle for teens as app", "candle for teens as kit"])

    def test_count_computed_not_claimed(self):
        out = m.generate(["a", "b", "c"], ["x"], ["f"])
        self.assertEqual(out["niche_count"], 3)
        self.assertIn("millions of live niches", out["scope"]["not_implemented"])

    def test_oversize_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.generate(["t%d" % i for i in range(21)], ["a%d" % i for i in range(21)],
                       ["f%d" % i for i in range(24)])  # 21*21*24 = 10584 > 10000
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_OVERSIZE")

    def test_vocab_validation(self):
        with self.assertRaises(ValueError) as cm:
            m.generate([], ["x"], ["f"])
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_EMPTY:taxonomy")
        with self.assertRaises(ValueError) as cm:
            m.generate(["a", "a"], ["x"], ["f"])
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_DUPLICATE:taxonomy")
        with self.assertRaises(ValueError) as cm:
            m.generate(["a\nb"], ["x"], ["f"])
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_CONTROL_CHARS:taxonomy")

    def test_bad_scores(self):
        with self.assertRaises(ValueError) as cm:
            m.generate(["a"], ["x"], ["f"], scores={"a": {"trend": True}})
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:trend")

    def test_determinism(self):
        a = m.generate(["b", "a"], ["x"], ["f"], scores={"a": {"trend": 1}})
        self.assertEqual(a, m.generate(["b", "a"], ["x"], ["f"], scores={"a": {"trend": 1}}))


class NichesPins(unittest.TestCase):
    V = ["a", "b"]

    def test_vocab_type_pins(self):
        # auditor survivors niches-27/29/33/40: per-name exact refusal codes
        for bad in (True, "x", 5, {"a": 1}):
            for name, kw in (("taxonomy", {"taxonomy": bad}),
                             ("audiences", {"audiences": bad}),
                             ("formats", {"formats": bad})):
                args = {"taxonomy": self.V, "audiences": self.V, "formats": self.V}
                args.update(kw)
                with self.assertRaises(ValueError) as cm:
                    m.generate(args["taxonomy"], args["audiences"], args["formats"])
                self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:" + name)
        with self.assertRaises(ValueError) as cm:
            m.generate(["t%d" % i for i in range(m.MAX_VOCAB + 1)], self.V, self.V)
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_OVERSIZE")

    def test_scores_type_pins(self):
        # auditor survivors niches-38/39
        for bad in ("x", 5, ["a"], True):
            with self.assertRaises(ValueError) as cm:
                m.generate(self.V, self.V, self.V, scores=bad)
            self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:scores")
        for bad in ("x", 5, ["a"], True):
            with self.assertRaises(ValueError) as cm:
                m.generate(self.V, self.V, self.V, scores={"a": bad})
            self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:score")


if __name__ == "__main__":
    unittest.main()
