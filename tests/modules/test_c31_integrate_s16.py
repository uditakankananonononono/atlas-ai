"""S1.6 / c31.integrate tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c31/integrate.py"
_spec = importlib.util.spec_from_file_location("c31_integrate", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c31_integrate"] = m
_spec.loader.exec_module(m)

TOOLS = [{"name": "alpha", "rating": 4.0, "privacy_tier": "good"},
         {"name": "beta", "rating": 4.5, "privacy_tier": "caution"}]


class Integrate(unittest.TestCase):
    def test_selection_and_artifacts(self):
        out = m.select("compress files", TOOLS)
        self.assertEqual(out["picked"], "alpha")  # 3+1.6+3 = 7.6 vs 3+1.8+2 = 6.8
        self.assertEqual([t["name"] for t in out["ranked"]], ["alpha", "beta"])
        self.assertIn("adapter stub for 'alpha'", out["adapter_stub"])  # repr literal
        self.assertIn("NotImplementedError", out["adapter_stub"])
        self.assertEqual(len(out["sandbox_test_plan"]), 3)

    def test_paid_refused_before_selection(self):
        with self.assertRaises(ValueError) as cm:
            m.select("x", [{"name": "pricy", "paid": True, "rating": 5, "privacy_tier": "good"}])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_SPEND:pricy")

    def test_ambiguous_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.select("x", [{"name": "b", "rating": 4.0, "privacy_tier": "good"},
                           {"name": "a", "rating": 4.0, "privacy_tier": "good"}])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_AMBIGUOUS:a|b")

    def test_validation(self):
        with self.assertRaises(ValueError) as cm:
            m.select("x", [{"name": "t", "rating": 9, "privacy_tier": "good"}])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:rating")
        with self.assertRaises(ValueError) as cm:
            m.select("x", [{"name": "t", "rating": 4.0, "privacy_tier": "shady"}])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:privacy_tier")
        with self.assertRaises(ValueError) as cm:
            m.select("x", [])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:tools")

    def test_survivor_pins_g2(self):
        # integrate-36: non-dict tool
        with self.assertRaises(ValueError) as cm:
            m.select("compress files", ["notadict"])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:tool")
        # integrate-41: cap enforced
        big = [dict(TOOLS[0], name="t%d" % i) for i in range(m.MAX_TOOLS + 1)]
        with self.assertRaises(ValueError) as cm:
            m.select("compress files", big)
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_OVERSIZE")

    def test_exact_numeric_score(self):
        # integrate-53: score = 3 + 2*(rating/5) + TIER_SCORE, exact float
        out = m.select("u", [{"name": "t1", "rating": 2.5, "privacy_tier": "caution"}])
        self.assertEqual(out["picked_score"], 3 + 2 * 0.5 + 2)
        out = m.select("u", [{"name": "t2", "rating": 5.0, "privacy_tier": "good"}])
        self.assertEqual(out["picked_score"], 3 + 2 * 1.0 + 3)
        out = m.select("u", [{"name": "t3", "rating": 0.0, "privacy_tier": "toxic"}])
        self.assertEqual(out["picked_score"], 3.0)

    def test_adapter_stub_injection_safe(self):
        # CORE: caller-controlled tool name embedded as repr-safe literal;
        # adversarial names compile to a valid NotImplementedError stub
        for evil in ("O'Reilly", "a'); import os; #", "back\\slash", "ünïcode-ツ"):
            out = m.select("u", [{"name": evil, "rating": 1.0, "privacy_tier": "good"}])
            stub = out["adapter_stub"]
            compile(stub, "<stub>", "exec")
            ns = {}
            exec(stub["stub"] if False else stub, ns)
            with self.assertRaises(NotImplementedError):
                ns["run"]({"x": 1})

    def test_determinism(self):
        self.assertEqual(m.select("compress files", TOOLS), m.select("compress files", TOOLS))


if __name__ == "__main__":
    unittest.main()
