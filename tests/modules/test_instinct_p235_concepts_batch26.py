"""P235 concepts batch 26 (251-260, sequence aggregates): red-first tests."""
from __future__ import annotations

import unittest
from fractions import Fraction


class Batch26Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch26 as m
        self.m = m

    def test_intersperse_value(self):
        self.assertEqual(self.m.intersperse_value([1, 2, 3], 0),
                         [1, 0, 2, 0, 3])
        self.assertEqual(self.m.intersperse_value([], 0), [])
        self.assertEqual(self.m.intersperse_value([7], 0), [7])

    def test_list_cycle_first_n(self):
        self.assertEqual(self.m.list_cycle_first_n([1, 2, 3], 7),
                         [1, 2, 3, 1, 2, 3, 1])
        self.assertEqual(self.m.list_cycle_first_n([9], 3), [9, 9, 9])
        self.assertEqual(self.m.list_cycle_first_n([1, 2], 0), [])
        with self.assertRaises(ValueError):
            self.m.list_cycle_first_n([], 3)
        with self.assertRaises(ValueError):
            self.m.list_cycle_first_n([1], -1)
        with self.assertRaises(ValueError):
            self.m.list_cycle_first_n([1], 10_001)

    def test_dedupe_adjacent(self):
        self.assertEqual(self.m.dedupe_adjacent([1, 1, 2, 2, 2, 3]),
                         [1, 2, 3])
        # non-adjacent repeats stay - distinct from dedupe_preserve_order
        self.assertEqual(self.m.dedupe_adjacent([1, 2, 1]), [1, 2, 1])
        self.assertEqual(self.m.dedupe_adjacent([]), [])
        self.assertEqual(self.m.dedupe_adjacent([5, 5]), [5])

    def test_pairwise_ratios_exact(self):
        self.assertEqual(self.m.pairwise_ratios_exact([2, 4, 8]),
                         [Fraction(2), Fraction(2)])
        self.assertEqual(self.m.pairwise_ratios_exact([5]), [])
        self.assertEqual(self.m.pairwise_ratios_exact([-2, 4]),
                         [Fraction(-2)])
        self.assertEqual(self.m.pairwise_ratios_exact([1, 3]),
                         [Fraction(3, 1)])
        self.assertEqual(self.m.pairwise_ratios_exact([2, 3]),
                         [Fraction(3, 2)])
        with self.assertRaises(ValueError):
            self.m.pairwise_ratios_exact([0, 5])

    def test_outer_pair_sums(self):
        self.assertEqual(self.m.outer_pair_sums([1, 2, 3, 10]), [11, 5])
        self.assertEqual(self.m.outer_pair_sums([1, 2, 3]), [4])
        self.assertEqual(self.m.outer_pair_sums([]), [])
        self.assertEqual(self.m.outer_pair_sums([7]), [])

    def test_count_in_range(self):
        self.assertEqual(self.m.count_in_range([1, 5, 7, 9], 5, 8), 2)
        self.assertEqual(self.m.count_in_range([], 0, 10), 0)
        self.assertEqual(self.m.count_in_range([5], 5, 5), 1)
        with self.assertRaises(ValueError):
            self.m.count_in_range([1], 8, 5)

    def test_count_signs(self):
        self.assertEqual(self.m.count_signs([-2, 0, 3, -1, 7]), (2, 1, 2))
        self.assertEqual(self.m.count_signs([]), (0, 0, 0))
        self.assertEqual(self.m.count_signs([0, 0]), (0, 2, 0))

    def test_alternating_sum(self):
        self.assertEqual(self.m.alternating_sum([5, 3, 1, 1]), 2)
        self.assertEqual(self.m.alternating_sum([]), 0)
        self.assertEqual(self.m.alternating_sum([7]), 7)
        self.assertEqual(self.m.alternating_sum([1, 2]), -1)

    def test_max_gap_consecutive_sorted(self):
        self.assertEqual(self.m.max_gap_consecutive_sorted([1, 4, 9, 10]), 5)
        self.assertEqual(self.m.max_gap_consecutive_sorted([10, 1, 9, 4]), 5)
        self.assertEqual(self.m.max_gap_consecutive_sorted([3, 3, 3]), 0)
        with self.assertRaises(ValueError):
            self.m.max_gap_consecutive_sorted([7])
        with self.assertRaises(ValueError):
            self.m.max_gap_consecutive_sorted([])

    def test_first_duplicate_value(self):
        self.assertEqual(self.m.first_duplicate_value([5, 3, 5, 3]), 5)
        self.assertIsNone(self.m.first_duplicate_value([1, 2, 3]))
        self.assertIsNone(self.m.first_duplicate_value([]))
        self.assertEqual(self.m.first_duplicate_value([2, 2]), 2)


if __name__ == "__main__":
    unittest.main()
