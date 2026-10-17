"""Row 26 sunk_cost_choice input-validation repair tests (scoped repair of
reproduced defects: nan forward_value silently produced a confident wrong
recommendation; bool forward_value accepted; missing keys crashed with an
uncoded KeyError). Guards require 'name' and a finite numeric non-bool
'forward_value' on every option, and validate 'past_investment' when present,
BEFORE the max() computations. Valid behavior and the forward-vs-naive
comparison are unchanged. Route boundary unchanged."""
import unittest
from app.modules.m20_general_cognitive_worker.metacognition import sunk_cost_choice


class TestSunkCostValidation(unittest.TestCase):
    def test_nan_inf_forward_value_refused(self):
        for bad in (float("nan"), float("inf"), float("-inf"), 10 ** 1000):
            with self.assertRaises(ValueError, msg=repr(bad)):
                sunk_cost_choice([{"name": "a", "forward_value": bad}, {"name": "b", "forward_value": 1.0}])

    def test_bool_forward_value_refused(self):
        with self.assertRaises(ValueError):
            sunk_cost_choice([{"name": "a", "forward_value": True}, {"name": "b", "forward_value": 0.5}])

    def test_missing_keys_refused_coded(self):
        with self.assertRaises(ValueError):
            sunk_cost_choice([{"name": "a"}])
        with self.assertRaises(ValueError):
            sunk_cost_choice([{"forward_value": 1.0}])

    def test_past_investment_validated_when_present(self):
        for bad in (float("nan"), True, "100"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                sunk_cost_choice([{"name": "a", "forward_value": 1.0, "past_investment": bad}])

    def test_overflow_comparison_does_not_invent_influence(self):
        out = sunk_cost_choice([{"name": "a", "forward_value": 1e308, "past_investment": 1e308},
                                {"name": "b", "forward_value": 1.5e308, "past_investment": 1.5e308}])
        self.assertEqual(out["recommended"], "b")
        self.assertIs(out["sunk_cost_influenced"], False)

    def test_exact_tie_keeps_first_wins(self):
        out = sunk_cost_choice([{"name": "a", "forward_value": 1, "past_investment": 1},
                                {"name": "b", "forward_value": 0, "past_investment": 2}])
        self.assertEqual(out["recommended"], "a")  # forward best; naive tie 2 == 2 keeps first
        self.assertIs(out["sunk_cost_influenced"], False)

    def test_valid_behavior_preserved(self):
        out = sunk_cost_choice([{"name": "a", "forward_value": 3.0, "past_investment": 100.0},
                                {"name": "b", "forward_value": 2.0}])
        self.assertEqual(out["recommended"], "a")
        self.assertIs(out["sunk_cost_influenced"], False)
        influenced = sunk_cost_choice([{"name": "a", "forward_value": 1.0, "past_investment": 100.0},
                                       {"name": "b", "forward_value": 2.0, "past_investment": 0.0}])
        self.assertEqual(influenced["recommended"], "b")
        self.assertIs(influenced["sunk_cost_influenced"], True)
        with self.assertRaisesRegex(ValueError, "options required"):
            sunk_cost_choice([])


if __name__ == "__main__":
    unittest.main()
