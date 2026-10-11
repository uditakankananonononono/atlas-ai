"""S2.9 / c32.psyche tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c32/psyche.py"
_spec = importlib.util.spec_from_file_location("c32_psyche", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c32_psyche"] = m
_spec.loader.exec_module(m)


class Psyche(unittest.TestCase):
    def test_tagging_and_dominance(self):
        out = m.tag("I am happy and excited, my goal is to win. My family matters.")
        self.assertEqual(out["emotions"]["joy"], 2)
        self.assertEqual(out["dominant_emotion"], "joy")
        self.assertEqual(out["motives"]["achievement"], 2)
        self.assertEqual(out["motives"]["affiliation"], 1)

    def test_non_joy_dominant_and_tiebreak(self):
        # Kills a dominant-pinned-to-joy mutant.
        out = m.tag("furious, rage, so mad and angry")
        self.assertEqual(out["dominant_emotion"], "anger")
        tie = m.tag("happy, trust")  # joy=1, trust=1: alphabetical tiebreak
        self.assertEqual(tie["dominant_emotion"], "joy")

    def test_no_text_cues_no_dominant(self):
        out = m.tag("The table is wooden.")
        self.assertIsNone(out["dominant_emotion"])
        self.assertEqual(out["emotion_total"], 0)

    def test_validity_limits_and_no_feeling_claim(self):
        out = m.tag("anything")
        self.assertEqual(out["claims_feeling"], False)
        self.assertIn("not measurement", out["validity_limits"])
        self.assertIn("feeling anything", out["scope"]["not_implemented"])

    def test_bad_input(self):
        with self.assertRaises(ValueError) as cm:
            m.tag("a\tb")
        self.assertEqual(str(cm.exception), "TREND_REFUSED_CONTROL_CHARS:text")

    def test_determinism(self):
        self.assertEqual(m.tag("sad day"), m.tag("sad day"))


if __name__ == "__main__":
    unittest.main()
