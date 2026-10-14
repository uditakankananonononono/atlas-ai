"""P235 concepts batch 10 (91-100, number theory/combinatorics): red-first tests."""
from __future__ import annotations

import unittest


class Batch10Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch10 as m
        self.m = m

    def test_polygon_signed_area2(self):
        self.assertEqual(self.m.polygon_signed_area2([[0, 0], [4, 0], [4, 3], [0, 3]]), 24)
        self.assertEqual(self.m.polygon_signed_area2([[0, 0], [0, 3], [4, 3], [4, 0]]), -24)
        self.assertEqual(self.m.polygon_signed_area2([[0, 0], [2, 0], [1, 2]]), 4)
        with self.assertRaises(ValueError) as c:
            self.m.polygon_signed_area2([[0, 0], [1, 1]])
        self.assertEqual(str(c.exception),
                         "P235:polygon_signed_area2:too_few:points")
        with self.assertRaises(ValueError):
            self.m.polygon_signed_area2([[0, 0], [1, 1], [2, "x"]])
        with self.assertRaises(ValueError):
            self.m.polygon_signed_area2([[0, 0, 0], [1, 1], [2, 2]])

    def test_grid_path_count(self):
        self.assertEqual(self.m.grid_path_count(1, 1), 2)
        self.assertEqual(self.m.grid_path_count(2, 2), 6)
        self.assertEqual(self.m.grid_path_count(0, 5), 1)
        self.assertEqual(self.m.grid_path_count(3, 7), 120)
        with self.assertRaises(ValueError):
            self.m.grid_path_count(-1, 2)
        with self.assertRaises(ValueError) as c:
            self.m.grid_path_count(self.m.MAX_GRID_SIDE + 1, 1)
        self.assertEqual(str(c.exception),
                         "P235:grid_path_count:too_many:side")
        with self.assertRaises(ValueError):
            self.m.grid_path_count(2, True)

    def test_iso_weekday(self):
        self.assertEqual(self.m.iso_weekday("2026-10-14"), 2)  # Wednesday
        self.assertEqual(self.m.iso_weekday("2000-01-01"), 5)  # Saturday
        self.assertEqual(self.m.iso_weekday("2024-02-29"), 3)  # Thursday
        with self.assertRaises(ValueError) as c:
            self.m.iso_weekday("2023-02-29")
        self.assertEqual(str(c.exception),
                         "P235:iso_weekday:bad_value:date")
        with self.assertRaises(ValueError):
            self.m.iso_weekday("14-10-2026")
        with self.assertRaises(ValueError) as c2:
            self.m.iso_weekday("2026-01-05\n")
        self.assertEqual(str(c2.exception),
                         "P235:iso_weekday:bad_value:date")
        with self.assertRaises(ValueError):
            self.m.iso_weekday("٢٠٢٦-٠١-٠٥")
        with self.assertRaises(ValueError):
            self.m.iso_weekday(20261014)

    def test_leap_year_check(self):
        self.assertTrue(self.m.leap_year_check(2000))
        self.assertFalse(self.m.leap_year_check(1900))
        self.assertTrue(self.m.leap_year_check(2024))
        self.assertFalse(self.m.leap_year_check(2026))
        with self.assertRaises(ValueError):
            self.m.leap_year_check(0)
        with self.assertRaises(ValueError):
            self.m.leap_year_check(True)

    def test_roman_numeral_render(self):
        self.assertEqual(self.m.roman_numeral_render(1994), "MCMXCIV")
        self.assertEqual(self.m.roman_numeral_render(1), "I")
        self.assertEqual(self.m.roman_numeral_render(3999), "MMMCMXCIX")
        self.assertEqual(self.m.roman_numeral_render(58), "LVIII")
        with self.assertRaises(ValueError) as c:
            self.m.roman_numeral_render(4000)
        self.assertEqual(str(c.exception),
                         "P235:roman_numeral_render:too_many:n")
        with self.assertRaises(ValueError):
            self.m.roman_numeral_render(0)

    def test_power_mod(self):
        self.assertEqual(self.m.power_mod(2, 10, 1000), 24)
        self.assertEqual(self.m.power_mod(7, 0, 13), 1)
        self.assertEqual(self.m.power_mod(-3, 3, 7), 1)
        with self.assertRaises(ValueError) as c:
            self.m.power_mod(2, 3, 0)
        self.assertEqual(str(c.exception), "P235:power_mod:bad_value:m")
        with self.assertRaises(ValueError) as c2:
            self.m.power_mod(2, self.m.MAX_EXP + 1, 5)
        self.assertEqual(str(c2.exception), "P235:power_mod:too_many:exp")
        with self.assertRaises(ValueError):
            self.m.power_mod(2, -1, 5)

    def test_extended_gcd(self):
        self.assertEqual(self.m.extended_gcd(30, 12), (6, 1, -2))
        self.assertEqual(self.m.extended_gcd(0, 5), (5, 0, 1))
        self.assertEqual(self.m.extended_gcd(7, 0), (7, 1, 0))
        g, x, y = self.m.extended_gcd(99, 78)
        self.assertEqual((g, 99 * x + 78 * y), (3, 3))
        with self.assertRaises(ValueError):
            self.m.extended_gcd(-1, 5)
        with self.assertRaises(ValueError):
            self.m.extended_gcd(0, 0)
        with self.assertRaises(ValueError):
            self.m.extended_gcd(3, True)

    def test_prime_factors_trial(self):
        self.assertEqual(self.m.prime_factors_trial(360), [2, 2, 2, 3, 3, 5])
        self.assertEqual(self.m.prime_factors_trial(2), [2])
        self.assertEqual(self.m.prime_factors_trial(97), [97])
        with self.assertRaises(ValueError) as c:
            self.m.prime_factors_trial(1)
        self.assertEqual(str(c.exception),
                         "P235:prime_factors_trial:bad_value:n")
        with self.assertRaises(ValueError) as c2:
            self.m.prime_factors_trial(self.m.MAX_FACTOR_N + 1)
        self.assertEqual(str(c2.exception),
                         "P235:prime_factors_trial:too_many:n")

    def test_count_inversions(self):
        self.assertEqual(self.m.count_inversions([3, 1, 2]), 2)
        self.assertEqual(self.m.count_inversions([1, 2, 3]), 0)
        self.assertEqual(self.m.count_inversions([5, 4, 3, 2, 1]), 10)
        self.assertEqual(self.m.count_inversions([]), 0)
        self.assertEqual(self.m.count_inversions([2, 2]), 0)
        with self.assertRaises(ValueError):
            self.m.count_inversions([1, "x"])

    def test_kth_smallest(self):
        self.assertEqual(self.m.kth_smallest([7, 10, 4, 3, 20, 15], 3), 7)
        self.assertEqual(self.m.kth_smallest([5, 5, 5], 2), 5)
        self.assertEqual(self.m.kth_smallest([9], 1), 9)
        with self.assertRaises(ValueError) as c:
            self.m.kth_smallest([1, 2], 0)
        self.assertEqual(str(c.exception), "P235:kth_smallest:bad_value:k")
        with self.assertRaises(ValueError):
            self.m.kth_smallest([1, 2], 3)
        with self.assertRaises(ValueError):
            self.m.kth_smallest([], 1)
        with self.assertRaises(ValueError):
            self.m.kth_smallest([1, True], 1)


if __name__ == "__main__":
    unittest.main()
