"""S2.6 / c32.ideate tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c32/ideate.py"
_spec = importlib.util.spec_from_file_location("c32_ideate", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c32_ideate"] = m
_spec.loader.exec_module(m)


class Ideate(unittest.TestCase):
    def test_combinations_and_counts(self):
        out = m.ideate(["candle", "playlist", "terrarium"])
        self.assertEqual(out["concept_count"], 3)
        self.assertEqual(out["idea_count"], 3 * 6)  # pairs x ops
        self.assertEqual(out["prior_art_count"], 0)
        for idea in out["ideas"]:
            self.assertEqual(idea["novelty"], 1.0)  # no prior art

    def test_novelty_drops_against_prior_art(self):
        out = m.ideate(["candle", "playlist"], prior_art=["combine: candle x playlist"])
        novelties = {i["idea"]: i["novelty"] for i in out["ideas"]}
        self.assertEqual(novelties["combine: candle x playlist"], 0.0)  # exact prior-art match
        self.assertEqual(novelties["reverse: candle x playlist"], 0.4)  # 1 - 3/5 jaccard
        fresh = m.ideate(["candle", "playlist"], prior_art=["unrelated words entirely"])
        self.assertTrue(all(i["novelty"] == 1.0 for i in fresh["ideas"]))

    def test_ranking_deterministic(self):
        a = m.ideate(["b", "a", "c"], prior_art=["combine: a x b"])
        self.assertEqual(a, m.ideate(["b", "a", "c"], prior_art=["combine: a x b"]))
        ns = [i["novelty"] for i in a["ideas"]]
        self.assertEqual(ns, sorted(ns, reverse=True))

    def test_training_refused_via_guard(self):
        # Removing the guard call must fail this test.
        with self.assertRaises(ValueError) as cm:
            m.ideate(["a", "b"], train=True)
        self.assertEqual(str(cm.exception), "TREND_REFUSED_SPEND")

    def test_bounds(self):
        with self.assertRaises(ValueError) as cm:
            m.ideate(["only-one"])
        self.assertEqual(str(cm.exception), "TREND_REFUSED_TOO_FEW:concepts")
        with self.assertRaises(ValueError) as cm:
            m.ideate(["c%d" % i for i in range(m.MAX_CONCEPTS + 1)])
        self.assertEqual(str(cm.exception), "TREND_REFUSED_OVERSIZE")
        self.assertEqual(m.ideate(["c%d" % i for i in range(m.MAX_CONCEPTS)])["concept_count"],
                         m.MAX_CONCEPTS)

    def test_bad_inputs(self):
        with self.assertRaises(ValueError) as cm:
            m.ideate("ab")
        self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:concepts")
        with self.assertRaises(ValueError) as cm:
            m.ideate(["a\nc", "b"])
        self.assertEqual(str(cm.exception), "TREND_REFUSED_CONTROL_CHARS:concept")


class IdeatePins(unittest.TestCase):
    def test_prior_art_type_pins(self):
        # auditor survivors ideate-13/14
        for bad in (True, "x", 5, {"a": 1}):
            with self.assertRaises(ValueError) as cm:
                m.ideate(["a", "b"], prior_art=bad)
            self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:prior_art")
        with self.assertRaises(ValueError) as cm:
            m.ideate(["a", "b"], prior_art=["p"] * (m.MAX_PRIOR_ART + 1))
        self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:prior_art")
        out = m.ideate(["a", "b"], prior_art=["p"] * m.MAX_PRIOR_ART)  # limit passes
        self.assertIn("ideas", out)

    def test_jaccard_empty_pair(self):
        # auditor survivors ideate-1/7 (guard simplified; behavior pinned)
        self.assertEqual(m._jaccard(frozenset(), frozenset()), 0.0)
        self.assertEqual(m._jaccard(frozenset(), frozenset({"x"})), 0.0)
        self.assertEqual(m._jaccard(frozenset({"x"}), frozenset({"x"})), 1.0)


if __name__ == "__main__":
    unittest.main()
