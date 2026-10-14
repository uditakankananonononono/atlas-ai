"""P235 concepts batch 19 (181-190, statistics): red-first tests."""
from __future__ import annotations

import unittest
from fractions import Fraction


class Batch19Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch19 as m
        self.m = m

    def test_median_low(self):
        self.assertEqual(self.m.median_low([1, 2, 3, 4]), 2)
        self.assertEqual(self.m.median_low([5]), 5)
        self.assertEqual(self.m.median_low([9, 1]), 1)
        with self.assertRaises(ValueError) as c:
            self.m.median_low([])
        self.assertEqual(str(c.exception), "P235:median_low:empty:items")

    def test_quantile_nearest_rank(self):
        self.assertEqual(self.m.quantile_nearest_rank(
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50), 5)
        self.assertEqual(self.m.quantile_nearest_rank([10, 20, 30], 100), 30)
        self.assertEqual(self.m.quantile_nearest_rank([10, 20, 30], 1), 10)
        with self.assertRaises(ValueError) as c:
            self.m.quantile_nearest_rank([1, 2], 0)
        self.assertEqual(str(c.exception),
                         "P235:quantile_nearest_rank:bad_value:percent")
        with self.assertRaises(ValueError):
            self.m.quantile_nearest_rank([1, 2], 101)

    def test_covariance_exact(self):
        self.assertEqual(self.m.covariance_exact([1, 2, 3], [1, 2, 3]),
                         Fraction(2, 3))
        self.assertEqual(self.m.covariance_exact([1, 2, 3], [3, 2, 1]),
                         Fraction(-2, 3))
        with self.assertRaises(ValueError) as c:
            self.m.covariance_exact([1, 2], [1])
        self.assertEqual(str(c.exception),
                         "P235:covariance_exact:length_mismatch")
        with self.assertRaises(ValueError):
            self.m.covariance_exact([], [])

    def test_iqr_nearest_rank(self):
        self.assertEqual(self.m.iqr_nearest_rank(
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]), 5)
        self.assertEqual(self.m.iqr_nearest_rank([1, 2, 3, 4]), 2)
        with self.assertRaises(ValueError) as c:
            self.m.iqr_nearest_rank([1, 2, 3])
        self.assertEqual(str(c.exception),
                         "P235:iqr_nearest_rank:too_few:items")

    def test_mean_absolute_deviation_exact(self):
        self.assertEqual(self.m.mean_absolute_deviation_exact([1, 2, 3]),
                         Fraction(2, 3))
        self.assertEqual(self.m.mean_absolute_deviation_exact([7]), Fraction(0))
        with self.assertRaises(ValueError):
            self.m.mean_absolute_deviation_exact([])

    def test_trimmed_mean_exact(self):
        self.assertEqual(self.m.trimmed_mean_exact([1, 2, 3, 4, 100], 1),
                         Fraction(3))
        self.assertEqual(self.m.trimmed_mean_exact([5, 6], 0), Fraction(11, 2))
        with self.assertRaises(ValueError) as c:
            self.m.trimmed_mean_exact([1, 2], 1)
        self.assertEqual(str(c.exception),
                         "P235:trimmed_mean_exact:bad_value:k")
        with self.assertRaises(ValueError):
            self.m.trimmed_mean_exact([], 0)

    def test_percentile_rank_of(self):
        self.assertEqual(self.m.percentile_rank_of([10, 20, 30, 40], 20),
                         Fraction(1, 4))
        self.assertEqual(self.m.percentile_rank_of([10, 20, 30, 40], 10),
                         Fraction(0))
        self.assertEqual(self.m.percentile_rank_of([5, 5, 9], 5), Fraction(0))
        with self.assertRaises(ValueError):
            self.m.percentile_rank_of([], 1)

    def test_midrange_exact(self):
        self.assertEqual(self.m.midrange_exact([1, 9]), Fraction(5))
        self.assertEqual(self.m.midrange_exact([1, 2]), Fraction(3, 2))
        self.assertEqual(self.m.midrange_exact([7]), Fraction(7))
        with self.assertRaises(ValueError):
            self.m.midrange_exact([])

    def test_harmonic_mean_exact(self):
        self.assertEqual(self.m.harmonic_mean_exact([1, 2, 4]),
                         Fraction(12, 7))
        self.assertEqual(self.m.harmonic_mean_exact([6]), Fraction(6))
        with self.assertRaises(ValueError) as c:
            self.m.harmonic_mean_exact([0, 1])
        self.assertEqual(str(c.exception),
                         "P235:harmonic_mean_exact:bad_value:items")
        with self.assertRaises(ValueError):
            self.m.harmonic_mean_exact([])

    def test_sample_variance_exact(self):
        self.assertEqual(self.m.sample_variance_exact([2, 4, 6]), Fraction(4))
        self.assertEqual(self.m.sample_variance_exact([5, 5]), Fraction(0))
        with self.assertRaises(ValueError) as c:
            self.m.sample_variance_exact([5])
        self.assertEqual(str(c.exception),
                         "P235:sample_variance_exact:too_few:items")


if __name__ == "__main__":
    unittest.main()
