"""Row 24 project_regret input-validation repair tests (scoped repair of a
reproduced defect: asymmetric scenario sets crashed with an uncoded KeyError
mid-computation). Guards refuse non-dict/empty payoff maps, bool/non-numeric/
non-finite payoffs, and mismatched scenario sets with ValueError BEFORE
computation. Valid behavior, the regret arithmetic, and the downstream
minimax_regret validation are unchanged. Route boundary unchanged."""
import unittest
from app.modules.m20_general_cognitive_worker.metacognition import project_regret


class TestRegretValidation(unittest.TestCase):
    def test_asymmetric_scenario_sets_refused(self):
        with self.assertRaises(ValueError):
            project_regret({"a": {"s1": 1.0, "s2": 2.0}, "b": {"s1": 0.5}})

    def test_non_dict_or_empty_payoffs_refused(self):
        for bad in ({"a": {"s1": 1.0}, "b": {}}, {"a": {"s1": 1.0}, "b": [("s1", 0.5)]}):
            with self.assertRaises(ValueError):
                project_regret(bad)

    def test_bool_nonnumeric_nonfinite_payoffs_refused(self):
        for bad in (True, "1", None, float("nan"), float("inf"), 10 ** 1000):
            with self.assertRaises(ValueError, msg=repr(bad)):
                project_regret({"a": {"s1": bad}, "b": {"s1": 0.5}})

    def test_top_level_non_dict_refused_coded(self):
        for bad in ([{"a": {"s": 1.0}}], "bad", 42, [1]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                project_regret(bad)

    def test_derived_overflow_regret_refused(self):
        with self.assertRaises(ValueError):
            project_regret({"a": {"s": 1e308}, "b": {"s": -1e308}})

    def test_huge_int_payoffs_accepted_no_arbitrary_cap(self):
        out = project_regret({"a": {"s": 10 ** 300}, "b": {"s": -(10 ** 300)}})
        self.assertEqual(out["regret_table"]["b"]["s"], 2 * 10 ** 300)

    def test_valid_behavior_preserved(self):
        out = project_regret({"a": {"s1": 1.0, "s2": 2.0}, "b": {"s1": 0.5, "s2": 3.0}})
        self.assertEqual(out["regret_table"]["a"], {"s1": 0.0, "s2": 1.0})
        self.assertEqual(out["max_regret"]["b"], 0.5)
        self.assertIn(out["minimax_choice"], ("a", "b"))
        with self.assertRaisesRegex(ValueError, "options required"):
            project_regret({})


if __name__ == "__main__":
    unittest.main()
