"""P235 concepts batch 29 tests - red-first."""
from __future__ import annotations

import unittest
from fractions import Fraction


class Batch29Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch29 as m
        self.m = m

    def test_multinomial_coefficient(self):
        self.assertEqual(self.m.multinomial_coefficient([2, 1]), 3)
        self.assertEqual(self.m.multinomial_coefficient([1, 1, 1]), 6)
        self.assertEqual(self.m.multinomial_coefficient([4, 2, 1]), 105)
        self.assertEqual(self.m.multinomial_coefficient([0, 0]), 1)
        self.assertEqual(self.m.multinomial_coefficient([10_000]), 1)
        with self.assertRaises(ValueError) as c:
            self.m.multinomial_coefficient([10_001])
        self.assertEqual(str(c.exception),
                         "P235:multinomial_coefficient:too_big:groups")
        with self.assertRaises(ValueError) as c:
            self.m.multinomial_coefficient([1] * 101)
        self.assertEqual(str(c.exception),
                         "P235:multinomial_coefficient:too_many:groups")
        with self.assertRaises(ValueError) as c:
            self.m.multinomial_coefficient([])
        self.assertEqual(str(c.exception),
                         "P235:multinomial_coefficient:empty:groups")
        with self.assertRaises(ValueError) as c:
            self.m.multinomial_coefficient([-1])
        self.assertEqual(str(c.exception),
                         "P235:multinomial_coefficient:bad_value:groups[0]")
        with self.assertRaises(ValueError) as c:
            self.m.multinomial_coefficient([True])
        self.assertEqual(str(c.exception),
                         "P235:multinomial_coefficient:bad_type:groups[0]")

    def test_subsets_with_sum_count(self):
        self.assertEqual(self.m.subsets_with_sum_count([1, 2, 3], 3), 2)
        self.assertEqual(self.m.subsets_with_sum_count([1, 1], 1), 2)
        self.assertEqual(self.m.subsets_with_sum_count([0], 0), 2)
        self.assertEqual(self.m.subsets_with_sum_count([0], 1), 0)
        self.assertEqual(self.m.subsets_with_sum_count([], 0), 1)
        self.assertEqual(self.m.subsets_with_sum_count([], 5), 0)
        self.assertEqual(self.m.subsets_with_sum_count([2, 2, 2], 2), 3)
        with self.assertRaises(ValueError) as c:
            self.m.subsets_with_sum_count([0] * 257, 0)
        self.assertEqual(str(c.exception),
                         "P235:subsets_with_sum_count:too_many:values")
        with self.assertRaises(ValueError) as c:
            self.m.subsets_with_sum_count([10_001], 0)
        self.assertEqual(str(c.exception),
                         "P235:subsets_with_sum_count:bad_value:values[0]")
        with self.assertRaises(ValueError) as c:
            self.m.subsets_with_sum_count([-1], 0)
        self.assertEqual(str(c.exception),
                         "P235:subsets_with_sum_count:bad_value:values[0]")
        with self.assertRaises(ValueError) as c:
            self.m.subsets_with_sum_count([1], 10_001)
        self.assertEqual(str(c.exception),
                         "P235:subsets_with_sum_count:bad_value:target")
        with self.assertRaises(ValueError) as c:
            self.m.subsets_with_sum_count([1], True)
        self.assertEqual(str(c.exception),
                         "P235:subsets_with_sum_count:bad_type:target")

    def test_chinese_remainder_pair(self):
        self.assertEqual(self.m.chinese_remainder_pair(2, 3, 3, 5), 8)
        self.assertEqual(self.m.chinese_remainder_pair(1, 2, 2, 3), 5)
        self.assertEqual(self.m.chinese_remainder_pair(0, 3, 0, 5), 0)
        self.assertEqual(self.m.chinese_remainder_pair(3, 7, 2, 11), 24)
        with self.assertRaises(ValueError) as c:
            self.m.chinese_remainder_pair(1, 2, 3, 4)
        self.assertEqual(str(c.exception),
                         "P235:chinese_remainder_pair:bad_value:moduli")
        with self.assertRaises(ValueError) as c:
            self.m.chinese_remainder_pair(3, 3, 0, 5)
        self.assertEqual(str(c.exception),
                         "P235:chinese_remainder_pair:bad_value:a1")
        with self.assertRaises(ValueError) as c:
            self.m.chinese_remainder_pair(0, 3, 0, 1)
        self.assertEqual(str(c.exception),
                         "P235:chinese_remainder_pair:bad_value:m2")
        with self.assertRaises(ValueError) as c:
            self.m.chinese_remainder_pair(0, 2_000_003, 0, 2_000_033)
        self.assertEqual(str(c.exception),
                         "P235:chinese_remainder_pair:too_big:moduli")
        with self.assertRaises(ValueError) as c:
            self.m.chinese_remainder_pair(True, 3, 0, 5)
        self.assertEqual(str(c.exception),
                         "P235:chinese_remainder_pair:bad_type:a1")

    def test_damerau_osa_distance(self):
        self.assertEqual(self.m.damerau_osa_distance("ca", "ac"), 1)
        self.assertEqual(self.m.damerau_osa_distance("abc", "acb"), 1)
        self.assertEqual(self.m.damerau_osa_distance("kitten", "sitting"),
                         3)
        self.assertEqual(self.m.damerau_osa_distance("", "abc"), 3)
        self.assertEqual(self.m.damerau_osa_distance("abc", "abc"), 0)
        self.assertEqual(self.m.damerau_osa_distance("a", "b"), 1)
        with self.assertRaises(ValueError) as c:
            self.m.damerau_osa_distance("a" * 1_001, "b")
        self.assertEqual(str(c.exception),
                         "P235:damerau_osa_distance:too_many:a")
        with self.assertRaises(ValueError) as c:
            self.m.damerau_osa_distance(True, "b")
        self.assertEqual(str(c.exception),
                         "P235:damerau_osa_distance:bad_type:a")

    def test_substring_first_index(self):
        self.assertEqual(self.m.substring_first_index("hello", "ll"), 2)
        self.assertEqual(self.m.substring_first_index("aaa", "aa"), 0)
        self.assertEqual(self.m.substring_first_index("abc", "x"), -1)
        self.assertEqual(self.m.substring_first_index("abc", "abc"), 0)
        with self.assertRaises(ValueError) as c:
            self.m.substring_first_index("abc", "")
        self.assertEqual(str(c.exception),
                         "P235:substring_first_index:bad_value:sub")
        with self.assertRaises(ValueError) as c:
            self.m.substring_first_index("x" * 10_001, "y")
        self.assertEqual(str(c.exception),
                         "P235:substring_first_index:too_many:text")
        with self.assertRaises(ValueError) as c:
            self.m.substring_first_index(True, "y")
        self.assertEqual(str(c.exception),
                         "P235:substring_first_index:bad_type:text")

    def test_easter_date_western(self):
        for year, month, day in ((2019, 4, 21), (2020, 4, 12),
                                 (2021, 4, 4), (2022, 4, 17),
                                 (2023, 4, 9), (2024, 3, 31),
                                 (2025, 4, 20), (2026, 4, 5),
                                 (2000, 4, 23), (2038, 4, 25)):
            self.assertEqual(self.m.easter_date_western(year),
                             (year, month, day), year)
        for bad in (1582, 10_000):
            with self.assertRaises(ValueError, msg=bad) as c:
                self.m.easter_date_western(bad)
            self.assertEqual(str(c.exception),
                             "P235:easter_date_western:bad_value:year")
        with self.assertRaises(ValueError) as c:
            self.m.easter_date_western(True)
        self.assertEqual(str(c.exception),
                         "P235:easter_date_western:bad_type:year")

    def test_point_in_polygon_raycast(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertTrue(self.m.point_in_polygon_raycast(square, [5, 5]))
        self.assertFalse(self.m.point_in_polygon_raycast(square, [15, 5]))
        # boundary counts as inside (documented)
        self.assertTrue(self.m.point_in_polygon_raycast(square, [0, 5]))
        self.assertTrue(self.m.point_in_polygon_raycast(square, [0, 0]))
        tri = [(0, 0), (4, 0), (0, 4)]
        self.assertFalse(self.m.point_in_polygon_raycast(tri, [3, 3]))
        self.assertTrue(self.m.point_in_polygon_raycast(tri, [1, 1]))
        self.assertTrue(self.m.point_in_polygon_raycast(tri, [2, 2]))
        ell = [(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)]
        self.assertFalse(self.m.point_in_polygon_raycast(ell, [3, 3]))
        self.assertTrue(self.m.point_in_polygon_raycast(ell, [1, 3]))
        self.assertTrue(self.m.point_in_polygon_raycast(ell, [3, 1]))
        with self.assertRaises(ValueError) as c:
            self.m.point_in_polygon_raycast([(0, 0), (1, 1)], [0, 0])
        self.assertEqual(
            str(c.exception),
            "P235:point_in_polygon_raycast:bad_value:points")
        with self.assertRaises(ValueError) as c:
            self.m.point_in_polygon_raycast(square, [True, 0])
        self.assertEqual(
            str(c.exception),
            "P235:point_in_polygon_raycast:bad_type:point[0]")

    def test_jaccard_index_exact(self):
        self.assertEqual(self.m.jaccard_index_exact([1, 2], [2, 3]),
                         Fraction(1, 3))
        self.assertEqual(self.m.jaccard_index_exact([1], [1]), Fraction(1))
        self.assertEqual(self.m.jaccard_index_exact([1], [2]), Fraction(0))
        self.assertEqual(self.m.jaccard_index_exact([1, 1, 2], [2, 3]),
                         Fraction(1, 3))
        self.assertEqual(self.m.jaccard_index_exact(["a", "b"], ["b", "c"]),
                         Fraction(1, 3))
        self.assertEqual(self.m.jaccard_index_exact([1, "a"], ["a", 2]),
                         Fraction(1, 3))
        with self.assertRaises(ValueError) as c:
            self.m.jaccard_index_exact([], [])
        self.assertEqual(str(c.exception),
                         "P235:jaccard_index_exact:bad_value:empty")
        with self.assertRaises(ValueError) as c:
            self.m.jaccard_index_exact([True], [1])
        self.assertEqual(str(c.exception),
                         "P235:jaccard_index_exact:bad_type:a[0]")

    def test_min_spanning_tree_weight(self):
        self.assertEqual(self.m.min_spanning_tree_weight(
            3, [(0, 1, 1), (1, 2, 1), (0, 2, 5)]), 2)
        self.assertEqual(self.m.min_spanning_tree_weight(
            4, [(0, 1, 1), (1, 2, 2), (2, 3, 3), (0, 3, 10)]), 6)
        self.assertEqual(self.m.min_spanning_tree_weight(
            2, [(0, 1, -5)]), -5)
        self.assertEqual(self.m.min_spanning_tree_weight(1, []), 0)
        with self.assertRaises(ValueError) as c:
            self.m.min_spanning_tree_weight(3, [(0, 1, 1)])
        self.assertEqual(
            str(c.exception),
            "P235:min_spanning_tree_weight:bad_value:disconnected")
        with self.assertRaises(ValueError) as c:
            self.m.min_spanning_tree_weight(0, [])
        self.assertEqual(str(c.exception),
                         "P235:min_spanning_tree_weight:bad_value:n")
        with self.assertRaises(ValueError) as c:
            self.m.min_spanning_tree_weight(257, [])
        self.assertEqual(str(c.exception),
                         "P235:min_spanning_tree_weight:too_many:n")
        with self.assertRaises(ValueError) as c:
            self.m.min_spanning_tree_weight(2, [(0, 2, 1)])
        self.assertEqual(
            str(c.exception),
            "P235:min_spanning_tree_weight:bad_value:edges[0]")
        with self.assertRaises(ValueError) as c:
            self.m.min_spanning_tree_weight(2, [(0, 1, 1_000_001)])
        self.assertEqual(
            str(c.exception),
            "P235:min_spanning_tree_weight:bad_value:edges[0]")
        with self.assertRaises(ValueError) as c:
            self.m.min_spanning_tree_weight(True, [])
        self.assertEqual(str(c.exception),
                         "P235:min_spanning_tree_weight:bad_type:n")

    def test_birthday_collision_exact(self):
        self.assertEqual(self.m.birthday_collision_exact(0), Fraction(0))
        self.assertEqual(self.m.birthday_collision_exact(1), Fraction(0))
        self.assertEqual(self.m.birthday_collision_exact(2),
                         Fraction(1, 365))
        self.assertEqual(self.m.birthday_collision_exact(3),
                         Fraction(1093, 133225))
        self.assertAlmostEqual(
            float(self.m.birthday_collision_exact(23)),
            0.5072972343239854, delta=1e-15)
        self.assertEqual(self.m.birthday_collision_exact(366), Fraction(1))
        self.assertEqual(self.m.birthday_collision_exact(10_000),
                         Fraction(1))
        for bad in (-1, 10_001):
            with self.assertRaises(ValueError, msg=bad) as c:
                self.m.birthday_collision_exact(bad)
            self.assertEqual(
                str(c.exception),
                "P235:birthday_collision_exact:bad_value:n")
        with self.assertRaises(ValueError) as c:
            self.m.birthday_collision_exact(True)
        self.assertEqual(str(c.exception),
                         "P235:birthday_collision_exact:bad_type:n")


if __name__ == "__main__":
    unittest.main()
