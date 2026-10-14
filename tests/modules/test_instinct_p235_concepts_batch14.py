"""P235 concepts batch 14 (131-140, geometry/time): red-first tests."""
from __future__ import annotations

import unittest
from fractions import Fraction


class Batch14Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch14 as m
        self.m = m

    def test_point_in_rect(self):
        self.assertTrue(self.m.point_in_rect([2, 3], [0, 0, 4, 4]))
        self.assertTrue(self.m.point_in_rect([0, 0], [0, 0, 4, 4]))
        self.assertFalse(self.m.point_in_rect([5, 5], [0, 0, 4, 4]))
        with self.assertRaises(ValueError) as c:
            self.m.point_in_rect([1, 2], [4, 0, 2, 4])
        self.assertEqual(str(c.exception), "P235:point_in_rect:bad_value:rect")
        with self.assertRaises(ValueError):
            self.m.point_in_rect([1], [0, 0, 1, 1])

    def test_distance_squared(self):
        self.assertEqual(self.m.distance_squared([0, 0], [3, 4]), 25)
        self.assertEqual(self.m.distance_squared([1, 1], [1, 1]), 0)
        self.assertEqual(self.m.distance_squared([-1, 2, 3], [2, 0, 3]), 13)
        with self.assertRaises(ValueError) as c:
            self.m.distance_squared([1, 2], [1, 2, 3])
        self.assertEqual(str(c.exception),
                         "P235:distance_squared:length_mismatch")

    def test_centroid_exact(self):
        self.assertEqual(self.m.centroid_exact([[0, 0], [2, 2], [4, 4]]),
                         (Fraction(2), Fraction(2)))
        self.assertEqual(self.m.centroid_exact([[0, 0], [3, 0]]),
                         (Fraction(3, 2), Fraction(0)))
        with self.assertRaises(ValueError) as c:
            self.m.centroid_exact([])
        self.assertEqual(str(c.exception), "P235:centroid_exact:empty:points")
        # total coordinate cells capped: exactly 10000 passes, 10002 refuses
        self.assertEqual(len(self.m.centroid_exact(
            [[0] * 5_000, [0] * 5_000])), 5_000)
        with self.assertRaises(ValueError) as c2:
            self.m.centroid_exact([[0] * 5_001, [0] * 5_001])
        self.assertEqual(str(c2.exception),
                         "P235:centroid_exact:too_many:cells")
        with self.assertRaises(ValueError):
            self.m.centroid_exact([[1, 2], [3]])

    def test_bounding_rect(self):
        self.assertEqual(self.m.bounding_rect([[1, 2], [5, -3], [0, 0]]),
                         [0, -3, 5, 2])
        self.assertEqual(self.m.bounding_rect([[7, 7]]), [7, 7, 7, 7])
        with self.assertRaises(ValueError) as c:
            self.m.bounding_rect([])
        self.assertEqual(str(c.exception), "P235:bounding_rect:empty:points")

    def test_gcd_list(self):
        self.assertEqual(self.m.gcd_list([12, 18, 24]), 6)
        self.assertEqual(self.m.gcd_list([7]), 7)
        self.assertEqual(self.m.gcd_list([0, 0]), 0)
        self.assertEqual(self.m.gcd_list([0, 5]), 5)
        with self.assertRaises(ValueError) as c:
            self.m.gcd_list([])
        self.assertEqual(str(c.exception), "P235:gcd_list:empty:items")
        with self.assertRaises(ValueError):
            self.m.gcd_list([-4, 2])

    def test_lcm_list(self):
        self.assertEqual(self.m.lcm_list([3, 4, 6]), 12)
        self.assertEqual(self.m.lcm_list([5]), 5)
        self.assertEqual(self.m.lcm_list([0, 5]), 0)
        with self.assertRaises(ValueError) as c:
            self.m.lcm_list([])
        self.assertEqual(str(c.exception), "P235:lcm_list:empty:items")
        with self.assertRaises(ValueError):
            self.m.lcm_list([2, -3])

    def test_days_in_month(self):
        self.assertEqual(self.m.days_in_month(2024, 2), 29)
        self.assertEqual(self.m.days_in_month(2026, 2), 28)
        self.assertEqual(self.m.days_in_month(2026, 4), 30)
        self.assertEqual(self.m.days_in_month(2026, 1), 31)
        with self.assertRaises(ValueError) as c:
            self.m.days_in_month(2026, 13)
        self.assertEqual(str(c.exception),
                         "P235:days_in_month:bad_value:month")
        with self.assertRaises(ValueError):
            self.m.days_in_month(0, 1)
        # December of year 9999 must not leak a year-10000 construction
        self.assertEqual(self.m.days_in_month(9999, 12), 31)

    def test_date_add_days(self):
        self.assertEqual(self.m.date_add_days("2026-10-14", 1), "2026-10-15")
        self.assertEqual(self.m.date_add_days("2026-12-31", 1), "2027-01-01")
        self.assertEqual(self.m.date_add_days("2026-01-01", -1), "2025-12-31")
        self.assertEqual(self.m.date_add_days("2024-02-28", 1), "2024-02-29")
        with self.assertRaises(ValueError) as c:
            self.m.date_add_days("2023-02-29", 1)
        self.assertEqual(str(c.exception),
                         "P235:date_add_days:bad_value:date")
        with self.assertRaises(ValueError) as c3:
            self.m.date_add_days("2026-10-14\n", 1)
        self.assertEqual(str(c3.exception),
                         "P235:date_add_days:bad_value:date")
        with self.assertRaises(ValueError) as c2:
            self.m.date_add_days("2026-10-14", self.m.MAX_DAY_SHIFT + 1)
        self.assertEqual(str(c2.exception),
                         "P235:date_add_days:too_many:days")

    def test_hms_to_seconds(self):
        self.assertEqual(self.m.hms_to_seconds(1, 0, 0), 3600)
        self.assertEqual(self.m.hms_to_seconds(23, 59, 59), 86399)
        self.assertEqual(self.m.hms_to_seconds(0, 0, 0), 0)
        with self.assertRaises(ValueError) as c:
            self.m.hms_to_seconds(0, 60, 0)
        self.assertEqual(str(c.exception),
                         "P235:hms_to_seconds:bad_value:minutes")
        with self.assertRaises(ValueError):
            self.m.hms_to_seconds(-1, 0, 0)
        with self.assertRaises(ValueError) as c2:
            self.m.hms_to_seconds(self.m.MAX_HOURS + 1, 0, 0)
        self.assertEqual(str(c2.exception),
                         "P235:hms_to_seconds:too_many:hours")
        # the pair is inverse at the largest allowed edge
        self.assertEqual(self.m.hms_to_seconds(10_000, 59, 59), 36_003_599)

    def test_seconds_to_hms(self):
        self.assertEqual(self.m.seconds_to_hms(86399), (23, 59, 59))
        self.assertEqual(self.m.seconds_to_hms(0), (0, 0, 0))
        self.assertEqual(self.m.seconds_to_hms(3661), (1, 1, 1))
        with self.assertRaises(ValueError):
            self.m.seconds_to_hms(-1)
        with self.assertRaises(ValueError) as c:
            self.m.seconds_to_hms(self.m.MAX_SECONDS + 1)
        self.assertEqual(str(c.exception),
                         "P235:seconds_to_hms:too_many:seconds")
        self.assertEqual(self.m.seconds_to_hms(36_003_599), (10_000, 59, 59))


if __name__ == "__main__":
    unittest.main()
