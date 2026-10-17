"""Row 25 quantify_sacrifice input-validation repair tests (scoped repair of
reproduced defects: nan alternative value silently ranked as best_foregone
with opportunity_cost nan; bool value accepted; missing 'value' key crashed
with an uncoded KeyError). Guards require a finite numeric non-bool 'value'
on chosen and every alternative BEFORE ranking. Valid behavior, ranking
arithmetic, and empty-alternatives semantics (best_foregone None, cost 0.0)
are unchanged. Route boundary unchanged; a separate bounded option maps the
new ValueError to HTTP 422 on the currently except-less row-25 route."""
import unittest
from app.modules.m20_general_cognitive_worker.metacognition import quantify_sacrifice


class TestSacrificeValidation(unittest.TestCase):
    def test_nan_inf_values_refused(self):
        for bad in (float("nan"), float("inf"), float("-inf"), 10 ** 1000):
            with self.assertRaises(ValueError, msg=repr(bad)):
                quantify_sacrifice({"name": "x", "value": 1.0}, [{"name": "y", "value": bad}])
            with self.assertRaises(ValueError, msg=repr(bad)):
                quantify_sacrifice({"name": "x", "value": bad}, [])

    def test_bool_values_refused(self):
        with self.assertRaises(ValueError):
            quantify_sacrifice({"name": "x", "value": True}, [])
        with self.assertRaises(ValueError):
            quantify_sacrifice({"name": "x", "value": 1.0}, [{"name": "y", "value": False}])

    def test_missing_value_key_refused_coded(self):
        with self.assertRaises(ValueError):
            quantify_sacrifice({"name": "x", "value": 1.0}, [{"name": "y"}])
        with self.assertRaises(ValueError):
            quantify_sacrifice({"name": "x"}, [])

    def test_non_dict_entries_refused(self):
        with self.assertRaises(ValueError):
            quantify_sacrifice([("value", 1.0)], [])
        with self.assertRaises(ValueError):
            quantify_sacrifice({"name": "x", "value": 1.0}, "notalist")

    def test_derived_overflow_cost_refused(self):
        with self.assertRaises(ValueError):
            quantify_sacrifice({"name": "x", "value": -1e308}, [{"name": "y", "value": 1e308}])

    def test_valid_behavior_preserved(self):
        out = quantify_sacrifice({"name": "x", "value": 1.0},
                                 [{"name": "y", "value": 0.5}, {"name": "z", "value": 0.75}])
        self.assertEqual(out["best_foregone"]["name"], "z")
        self.assertEqual(out["opportunity_cost"], -0.25)
        empty = quantify_sacrifice({"name": "x", "value": 1.0}, [])
        self.assertIsNone(empty["best_foregone"])
        self.assertEqual(empty["opportunity_cost"], 0.0)


if __name__ == "__main__":
    unittest.main()
