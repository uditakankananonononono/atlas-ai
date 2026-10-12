"""Row 83 ledger tests. Hermetic temp tree."""
import importlib.util, os, pathlib, sys, tempfile, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/instinct_doc/concept_acceptance_ledger_r83.py"
_spec = importlib.util.spec_from_file_location("ledger_r83", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["ledger_r83"] = m
_spec.loader.exec_module(m)


def mk(d, rel, text):
    p = pathlib.Path(d, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


class Ledger(unittest.TestCase):
    def test_verdicts(self):
        with tempfile.TemporaryDirectory() as d:
            base = m.M20
            mk(d, base + "/alpha.py", "def a():\n    return 1\n")
            mk(d, base + "/beta.py", "def b():\n    return 1\n")
            mk(d, base + "/gamma.py", "def c():\n    return 1\n")
            mk(d, base + "/alpha_routes.py", "def r():\n    pass\n")
            mk(d, "tests/test_alpha.py", "# alpha\ndef test_x():\n    assert True\n")
            mk(d, "tests/test_beta.py", "# beta\ndef test_x():\n    assert False\n")
            static = m.build(d, run_tests=False, target=3)
            self.assertEqual(static["modules"], 3)
            self.assertEqual(static["verdict_counts"], {"TEST_REFERENCED_NOT_RUN": 2, "UNTESTED": 1})
            ran = m.build(d, run_tests=True, target=3)
            v = {r["module"]: r["verdict"] for r in ran["rows"]}
            self.assertEqual(v, {"alpha": "TEST_PASSED", "beta": "TEST_FAILED", "gamma": "UNTESTED"})
            self.assertEqual(ran["test_passed"], 1)
            self.assertEqual(ran["shortfall_vs_target"], 2)
            self.assertFalse(ran["complete"])

    def test_bad_args(self):
        with self.assertRaises(ValueError):
            m.build(".", run_tests="yes")


if __name__ == "__main__":
    unittest.main()
