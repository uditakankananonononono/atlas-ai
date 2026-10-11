"""S1.5 / c31.lenses tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c31/lenses.py"
_spec = importlib.util.spec_from_file_location("c31_lenses", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c31_lenses"] = m
_spec.loader.exec_module(m)


class Lenses(unittest.TestCase):
    def test_all_lenses_with_disclaimer(self):
        out = m.apply("a glossy study planner")
        self.assertEqual(out["lens_count"], 6)
        self.assertEqual([a["lens"] for a in out["angles"]], sorted(m.LENSES))
        self.assertIn("not diagnoses", out["disclaimer"])
        self.assertIn("a glossy study planner", out["angles"][0]["angle"])

    def test_subset_and_order(self):
        out = m.apply("idea", lenses=["systemizing", "hyperfocus"])
        self.assertEqual([a["lens"] for a in out["angles"]], ["systemizing", "hyperfocus"])

    def test_clinical_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.apply("idea", diagnose=True)
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_CLINICAL")
        self.assertIn("clinical or medical claims", m.apply("idea")["scope"]["not_implemented"])

    def test_validation(self):
        with self.assertRaises(ValueError) as cm:
            m.apply("idea", lenses=["savant-mode"])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_LENS:savant-mode")
        with self.assertRaises(ValueError) as cm:
            m.apply("idea", lenses=["hyperfocus", "hyperfocus"])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_DUPLICATE:hyperfocus")
        with self.assertRaises(ValueError) as cm:
            m.apply("a\u2028b")
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_CONTROL_CHARS:idea")

    def test_survivor_pins_g2(self):
        # lenses-28/29: lenses must be a nonempty list/tuple
        for bad in ("x", 42, []):
            with self.assertRaises(ValueError) as cm:
                m.apply("idea", lenses=bad)
            self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:lenses")

    def test_determinism(self):
        self.assertEqual(m.apply("x"), m.apply("x"))


if __name__ == "__main__":
    unittest.main()
