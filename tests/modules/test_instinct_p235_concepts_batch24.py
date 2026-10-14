"""P235 concepts batch 24 (231-240, exact geometry/misc): red-first tests."""
from __future__ import annotations

import unittest
from fractions import Fraction


class Batch24Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch24 as m
        self.m = m

    def test_slope_exact(self):
        self.assertEqual(self.m.slope_exact((0, 0), (3, 6)), Fraction(2))
        self.assertEqual(self.m.slope_exact((1, 1), (4, 1)), Fraction(0))
        self.assertEqual(self.m.slope_exact((2, 5), (0, 1)), Fraction(2))
        with self.assertRaises(ValueError) as c:
            self.m.slope_exact((2, 1), (2, 9))
        self.assertEqual(str(c.exception), "P235:slope_exact:vertical:points")
        with self.assertRaises(ValueError):
            self.m.slope_exact((3, 3), (3, 3))

    def test_reflect_point_exact(self):
        self.assertEqual(self.m.reflect_point_exact((0, 0), (3, 7)),
                         (6, 14))
        self.assertEqual(self.m.reflect_point_exact((-2, 4), (2, -4)),
                         (6, -12))
        self.assertEqual(self.m.reflect_point_exact((5, 5), (5, 5)),
                         (5, 5))

    def test_collinear_check(self):
        self.assertTrue(self.m.collinear_check((0, 0), (1, 1), (2, 2)))
        self.assertFalse(self.m.collinear_check((0, 0), (1, 1), (2, 3)))
        self.assertTrue(self.m.collinear_check((1, 1), (1, 1), (9, 9)))

    def test_circle_area_pi_coefficient(self):
        self.assertEqual(self.m.circle_area_pi_coefficient(3), 9)
        self.assertEqual(self.m.circle_area_pi_coefficient(0), 0)
        self.assertEqual(self.m.circle_area_pi_coefficient(10), 100)
        with self.assertRaises(ValueError):
            self.m.circle_area_pi_coefficient(-1)
        with self.assertRaises(ValueError):
            self.m.circle_area_pi_coefficient(10**9 + 1)

    def test_line_intersection_exact(self):
        self.assertEqual(self.m.line_intersection_exact(
            (1, 1, 3), (1, -1, 1)), (Fraction(2), Fraction(1)))
        self.assertEqual(self.m.line_intersection_exact(
            (2, 0, 6), (0, 3, 9)), (Fraction(3), Fraction(3)))
        with self.assertRaises(ValueError) as c:
            self.m.line_intersection_exact((1, 1, 3), (2, 2, 8))
        self.assertEqual(str(c.exception),
                         "P235:line_intersection_exact:parallel:lines")
        with self.assertRaises(ValueError):
            self.m.line_intersection_exact((0, 0, 1), (1, 1, 1))

    def test_convex_hull_vertices(self):
        pts = [[0, 0], [4, 0], [4, 4], [0, 4], [2, 2], [1, 1]]
        self.assertEqual(self.m.convex_hull_vertices(pts),
                         [[0, 0], [4, 0], [4, 4], [0, 4]])
        self.assertEqual(self.m.convex_hull_vertices(
            [[0, 0], [1, 1], [2, 2]]), [[0, 0], [2, 2]])
        self.assertEqual(self.m.convex_hull_vertices([[5, 5]]), [[5, 5]])
        self.assertEqual(self.m.convex_hull_vertices(
            [[0, 0], [2, 0], [1, 0]]), [[0, 0], [2, 0]])
        with self.assertRaises(ValueError) as c:
            self.m.convex_hull_vertices([[0, 0], [1, 1], [0, 0]])
        self.assertEqual(str(c.exception),
                         "P235:convex_hull_vertices:duplicate:points")
        with self.assertRaises(ValueError):
            self.m.convex_hull_vertices([])

    def test_ohms_law_voltage_exact(self):
        self.assertEqual(self.m.ohms_law_voltage_exact(2, 5), Fraction(10))
        self.assertEqual(self.m.ohms_law_voltage_exact(
            Fraction(1, 2), 7), Fraction(7, 2))
        self.assertEqual(self.m.ohms_law_voltage_exact(0, 5), Fraction(0))
        with self.assertRaises(ValueError):
            self.m.ohms_law_voltage_exact(-1, 5)
        with self.assertRaises(ValueError):
            self.m.ohms_law_voltage_exact(1, -5)

    def test_determinant_2x2_exact(self):
        self.assertEqual(self.m.determinant_2x2_exact((1, 2), (3, 4)), -2)
        self.assertEqual(self.m.determinant_2x2_exact((5, 0), (0, 5)), 25)
        self.assertEqual(self.m.determinant_2x2_exact((1, 2), (2, 4)), 0)

    def test_add_digit_strings(self):
        self.assertEqual(self.m.add_digit_strings("999", "1"), "1000")
        self.assertEqual(self.m.add_digit_strings("0", "0"), "0")
        self.assertEqual(self.m.add_digit_strings("123", "877"), "1000")
        self.assertEqual(self.m.add_digit_strings("9" * 10_000, "1"),
                         "1" + "0" * 10_000)
        # exact refusal codes for the digit-string guards
        for bad in ("007", "", "12a", "1 2"):
            with self.assertRaises(ValueError, msg=bad) as c:
                self.m.add_digit_strings(bad, "1")
            self.assertEqual(str(c.exception),
                             "P235:add_digit_strings:bad_value:a")
        # Unicode digits: int() would parse the Arabic-Indic nine and the
        # Devanagari five (both isdecimal); superscript two has isdigit()
        # True but isdecimal() False. All refuse with the same code.
        for uni in ("٩", "५", "²"):
            self.assertTrue(uni.isdigit(), uni)
            with self.assertRaises(ValueError, msg=uni) as c:
                self.m.add_digit_strings(uni, "1")
            self.assertEqual(str(c.exception),
                             "P235:add_digit_strings:bad_value:a")
        with self.assertRaises(ValueError) as c:
            self.m.add_digit_strings("1" * 10_001, "1")
        self.assertEqual(str(c.exception),
                         "P235:add_digit_strings:too_many:a")
        # carry predicate: a final carry becomes the new high digit
        self.assertEqual(self.m.add_digit_strings("9", "1"), "10")

    def test_polynomial_eval_exact(self):
        self.assertEqual(self.m.polynomial_eval_exact([1, 2, 3], 2), 17)
        self.assertEqual(self.m.polynomial_eval_exact([5], 99), 5)
        self.assertEqual(self.m.polynomial_eval_exact([1, 0, -1], 3), -8)
        self.assertEqual(self.m.polynomial_eval_exact([0] * 100, 10**6), 0)
        with self.assertRaises(ValueError):
            self.m.polynomial_eval_exact([], 1)
        # cap is 101 coefficients (degree 100): 101 passes, 102 refuses
        self.assertEqual(self.m.polynomial_eval_exact([1] * 101, 1), 101)
        with self.assertRaises(ValueError):
            self.m.polynomial_eval_exact([1] * 102, 1)
        with self.assertRaises(ValueError):
            self.m.polynomial_eval_exact([10**6 + 1], 1)
        with self.assertRaises(ValueError):
            self.m.polynomial_eval_exact([1], 10**6 + 1)


if __name__ == "__main__":
    unittest.main()
