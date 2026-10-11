"""S2.12 / c33.persona tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c33/persona.py"
_spec = importlib.util.spec_from_file_location("c33_persona", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c33_persona"] = m
_spec.loader.exec_module(m)


class Persona(unittest.TestCase):
    def test_profile_features(self):
        out = m.profile("beauty", ["I love gloss. Gloss is my thing, yeah kinda literally.",
                                   "Skincare first. Then gloss, always gloss."])
        v = out["voice"]
        self.assertEqual(v["avg_sentence_length"], round(16 / 4, 6))
        self.assertEqual(v["tone"], "informal")  # yeah, kinda, literally
        self.assertEqual(v["top_words"][0], "gloss")  # 4 occurrences
        self.assertEqual(out["sample_count"], 2)
        self.assertIn("not impersonation", out["guidance"])

    def test_formal_tone(self):
        out = m.profile("academic", ["Therefore we conclude. However, the data holds. Furthermore, it replicates."])
        self.assertEqual(out["voice"]["tone"], "formal")

    def test_real_person_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.profile("beauty", ["sample"], real_person="Some Celebrity")
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_IMPERSONATE")

    def test_bounds(self):
        with self.assertRaises(ValueError) as cm:
            m.profile("f", [])
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_EMPTY:samples")
        with self.assertRaises(ValueError) as cm:
            m.profile("f\n", ["s"])
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_CONTROL_CHARS:field")

    def test_determinism(self):
        self.assertEqual(m.profile("f", ["a b c."]), m.profile("f", ["a b c."]))


class PersonaPins(unittest.TestCase):
    def test_samples_type_pins(self):
        # auditor survivors persona-66/68/70
        for bad in (True, "x", 5, {"a": 1}):
            with self.assertRaises(ValueError) as cm:
                m.profile("f", bad)
            self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:samples")
        with self.assertRaises(ValueError) as cm:
            m.profile("f", ["s"] * (m.MAX_SAMPLES + 1))
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_OVERSIZE")
        out = m.profile("f", ["s"] * m.MAX_SAMPLES)  # limit passes
        self.assertIn("scope", out)


if __name__ == "__main__":
    unittest.main()
