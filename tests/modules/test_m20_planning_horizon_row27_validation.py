"""Row 27 horizon() input-validation repair tests (targeted scoped repair of
reproduced validation defects). Mechanism-level strictness for DIRECT/internal
callers: bool, non-finite, and non-numeric inputs are refused with ValueError
BEFORE the formula. The genuine policy, status labels, and the legacy
/meta/planning-horizon route are unchanged; HTTP-boundary coercion under real
pydantic (bool->1.0, numeric strings accepted) is a documented compatibility
choice and is NOT changed by this repair.
"""
import math
import unittest

from app.modules.m20_general_cognitive_worker.metacognition import PlanningHorizonController


class TestHorizonFiniteValidation(unittest.TestCase):
    def setUp(self):
        self.ctrl = PlanningHorizonController()

    def test_bool_inputs_refused_before_formula(self):
        for bad in (True, False):
            with self.assertRaises(ValueError):
                self.ctrl.horizon(uncertainty=bad, time_available_minutes=60)
            with self.assertRaises(ValueError):
                self.ctrl.horizon(uncertainty=0.5, time_available_minutes=bad)

    def test_non_finite_inputs_refused_before_formula(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError, msg=f"uncertainty={bad}"):
                self.ctrl.horizon(uncertainty=bad, time_available_minutes=60)
            with self.assertRaises(ValueError, msg=f"time={bad}"):
                self.ctrl.horizon(uncertainty=0.5, time_available_minutes=bad)

    def test_non_numeric_inputs_refused_with_valueerror_not_typeerror(self):
        for bad in ("30", None, [60], {"minutes": 60}):
            with self.assertRaises(ValueError):
                self.ctrl.horizon(uncertainty=0.5, time_available_minutes=bad)
            with self.assertRaises(ValueError):
                self.ctrl.horizon(uncertainty=bad, time_available_minutes=60)

    def test_out_of_range_finite_keeps_original_messages(self):
        with self.assertRaisesRegex(ValueError, r"uncertainty must be in \[0, 1\]"):
            self.ctrl.horizon(uncertainty=1.5, time_available_minutes=10)
        with self.assertRaisesRegex(ValueError, "time must be positive"):
            self.ctrl.horizon(uncertainty=0.5, time_available_minutes=0)

    def test_genuine_policy_unchanged_on_valid_inputs(self):
        shallow = self.ctrl.horizon(uncertainty=0.9, time_available_minutes=30)
        deep = self.ctrl.horizon(uncertainty=0.1, time_available_minutes=480)
        self.assertLess(shallow["max_depth"], deep["max_depth"])
        self.assertGreater(shallow["replan_interval_minutes"], deep["replan_interval_minutes"])
        mid = self.ctrl.horizon(uncertainty=0.2, time_available_minutes=480)
        self.assertEqual((mid["max_depth"], mid["max_steps"], mid["replan_interval_minutes"]), (4, 12, 66.0))
        for out in (shallow, deep, mid):
            self.assertEqual(out["status"], "hand_written_planning_policy")
            self.assertIs(out["capability_executed"], False)

    def test_huge_integer_refused_as_valueerror_not_overflowerror(self):
        huge = 10 ** 1000
        for bad in (huge, -huge):
            with self.assertRaises(ValueError):
                self.ctrl.horizon(uncertainty=bad, time_available_minutes=60)
            with self.assertRaises(ValueError):
                self.ctrl.horizon(uncertainty=0.5, time_available_minutes=bad)

    def test_edge_finite_values_accepted(self):
        # subnormal, near-max float, and large-but-convertible int all stay valid
        for u in (0, 5e-324, 0.5, 1):
            for t in (5e-324, 1e-300, 1e308, 10 ** 308):
                out = self.ctrl.horizon(uncertainty=u, time_available_minutes=t)
                depth = int(round(1 + 4 * (1 - u) * min(1.0, t / 240.0)))
                self.assertEqual(out["max_depth"], max(1, min(5, depth)))

    def test_int_inputs_accepted_as_finite_numbers(self):
        out = self.ctrl.horizon(uncertainty=0, time_available_minutes=240)
        self.assertEqual(out["max_depth"], 5)


if __name__ == "__main__":
    unittest.main()
