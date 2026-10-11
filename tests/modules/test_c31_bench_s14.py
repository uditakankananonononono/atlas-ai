"""S1.4 / c31.bench tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c31/bench.py"
_spec = importlib.util.spec_from_file_location("c31_bench", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c31_bench"] = m
_spec.loader.exec_module(m)

RUNS = [{"run_id": "r1", "task": "reasoning", "score": 0.5, "pass_mark": 0.7},
        {"run_id": "r2", "task": "reasoning", "score": 0.8, "pass_mark": 0.7},
        {"run_id": "r3", "task": "planning", "score": 0.4, "pass_mark": 0.6},
        {"run_id": "r4", "task": "novelty", "score": 0.9, "pass_mark": 0.6}]


class Bench(unittest.TestCase):
    def test_board_aggregation(self):
        out = m.board(RUNS)
        self.assertEqual(out["tasks"]["reasoning"],
                         {"runs": 2, "latest_score": 0.8, "best_score": 0.8, "latest_passed": True})
        self.assertEqual(out["measured_ceiling"], 0.9)
        self.assertEqual(out["failures"], ["planning"])  # latest below pass mark
        self.assertEqual(out["run_count"], 4)

    def test_honesty_scope(self):
        out = m.board(RUNS)
        self.assertIn("superintelligence", out["scope"]["not_implemented"])
        self.assertEqual(out["scope"]["data_source"], "supplied measured scores")

    def test_boundary_scores(self):
        out = m.board([{"run_id": "a", "task": "reasoning", "score": 0.7, "pass_mark": 0.7}])
        self.assertEqual(out["tasks"]["reasoning"]["latest_passed"], True)  # >= passes
        for bad in (-0.1, 1.1, True, "high"):
            with self.assertRaises(ValueError) as cm:
                m.board([{"run_id": "a", "task": "reasoning", "score": bad, "pass_mark": 0.5}])
            self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:score")

    def test_unmeasured_task_counts_as_failure(self):
        out = m.board([{"run_id": "a", "task": "reasoning", "score": 0.7, "pass_mark": 0.7}])
        self.assertEqual(sorted(out["failures"]), ["novelty", "planning"])
        self.assertIsNone(out["tasks"]["planning"]["latest_score"])
        self.assertEqual(out["tasks"]["planning"]["runs"], 0)

    def test_validation(self):
        with self.assertRaises(ValueError) as cm:
            m.board([])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_EMPTY:runs")
        with self.assertRaises(ValueError) as cm:
            m.board([{"run_id": "a", "task": "vibes", "score": 0.5, "pass_mark": 0.5}])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TASK:vibes")
        with self.assertRaises(ValueError) as cm:
            m.board(RUNS + [dict(RUNS[0])])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_DUPLICATE:r1")
        with self.assertRaises(ValueError) as cm:
            m.board([{"run_id": "a\x00", "task": "reasoning", "score": 0.5, "pass_mark": 0.5}])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_CONTROL_CHARS:run_id")

    def test_survivor_pins_g2(self):
        # bench-1/3/4: runs typed non-bool list; cap
        for bad in (True, "x", 42):
            with self.assertRaises(ValueError) as cm:
                m.board(bad)
            self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:runs")
        big = [dict(RUNS[0], run_id="r%d" % i) for i in range(m.MAX_RUNS + 1)]
        with self.assertRaises(ValueError) as cm:
            m.board(big)
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_OVERSIZE")
        # bench-6: non-dict run
        with self.assertRaises(ValueError) as cm:
            m.board(["notadict"])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:run")
        # bench-10/16: pass_mark typed in [0,1]
        for bad in ("x", True, 1.5, -0.1):
            with self.assertRaises(ValueError) as cm:
                m.board([dict(RUNS[0], pass_mark=bad)])
            self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:pass_mark")

    def test_aggregate_only_disclosure(self):
        # S1.4 scope fix: aggregate-only output disclosed, no history claim
        out = m.board(RUNS)
        # no unqualified history claim; the disclosure names what is NOT returned
        self.assertNotIn("score history over runs", out["scope"]["implemented"])
        self.assertTrue(any("aggregate" in x for x in out["scope"]["implemented"]))

    def test_determinism(self):
        self.assertEqual(m.board(RUNS), m.board(RUNS))


if __name__ == "__main__":
    unittest.main()
