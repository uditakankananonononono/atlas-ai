"""P235 concepts batch 22 (211-220, number theory/combinatorics): red-first."""
from __future__ import annotations

import unittest


class Batch22Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch22 as m
        self.m = m

    def test_josephus_winner(self):
        self.assertEqual(self.m.josephus_winner(5, 2), 2)
        self.assertEqual(self.m.josephus_winner(7, 3), 3)
        self.assertEqual(self.m.josephus_winner(1, 9), 0)
        self.assertEqual(self.m.josephus_winner(41, 2), 18)
        with self.assertRaises(ValueError):
            self.m.josephus_winner(0, 2)
        with self.assertRaises(ValueError):
            self.m.josephus_winner(5, 0)
        with self.assertRaises(ValueError):
            self.m.josephus_winner(1_000_001, 2)

    def test_zeckendorf_representation(self):
        self.assertEqual(self.m.zeckendorf_representation(10), [8, 2])
        self.assertEqual(self.m.zeckendorf_representation(100),
                         [89, 8, 3])
        self.assertEqual(self.m.zeckendorf_representation(1), [1])
        self.assertEqual(self.m.zeckendorf_representation(54),
                         [34, 13, 5, 2])
        with self.assertRaises(ValueError):
            self.m.zeckendorf_representation(0)

    def test_binomial_coefficient(self):
        self.assertEqual(self.m.binomial_coefficient(5, 2), 10)
        self.assertEqual(self.m.binomial_coefficient(10, 3), 120)
        self.assertEqual(self.m.binomial_coefficient(200, 2), 19900)
        with self.assertRaises(ValueError):
            self.m.binomial_coefficient(5, 6)
        with self.assertRaises(ValueError):
            self.m.binomial_coefficient(201, 1)
        with self.assertRaises(ValueError):
            self.m.binomial_coefficient(-1, 0)

    def test_factorial_trailing_zeros(self):
        self.assertEqual(self.m.factorial_trailing_zeros(0), 0)
        self.assertEqual(self.m.factorial_trailing_zeros(5), 1)
        self.assertEqual(self.m.factorial_trailing_zeros(25), 6)
        self.assertEqual(self.m.factorial_trailing_zeros(100), 24)
        self.assertEqual(self.m.factorial_trailing_zeros(10**18),
                         249_999_999_999_999_995)
        with self.assertRaises(ValueError):
            self.m.factorial_trailing_zeros(-1)

    def test_sum_of_divisors(self):
        self.assertEqual(self.m.sum_of_divisors(6), 12)
        self.assertEqual(self.m.sum_of_divisors(1), 1)
        self.assertEqual(self.m.sum_of_divisors(28), 56)
        self.assertEqual(self.m.sum_of_divisors(10**12), 2_499_694_822_171)
        with self.assertRaises(ValueError):
            self.m.sum_of_divisors(0)

    def test_lagrange_square_count(self):
        self.assertEqual(self.m.lagrange_square_count(1), 1)
        self.assertEqual(self.m.lagrange_square_count(2), 2)
        self.assertEqual(self.m.lagrange_square_count(3), 3)
        self.assertEqual(self.m.lagrange_square_count(7), 4)
        self.assertEqual(self.m.lagrange_square_count(12), 3)
        self.assertEqual(self.m.lagrange_square_count(23), 4)
        self.assertEqual(self.m.lagrange_square_count(25), 1)
        self.assertEqual(self.m.lagrange_square_count(63), 4)
        with self.assertRaises(ValueError):
            self.m.lagrange_square_count(0)

    def test_is_square_free(self):
        self.assertTrue(self.m.is_square_free(1))
        self.assertTrue(self.m.is_square_free(30))
        self.assertFalse(self.m.is_square_free(12))
        self.assertTrue(self.m.is_square_free(999_983))
        self.assertFalse(self.m.is_square_free(4))
        with self.assertRaises(ValueError):
            self.m.is_square_free(0)

    def test_stirling2_count(self):
        self.assertEqual(self.m.stirling2_count(5, 2), 15)
        self.assertEqual(self.m.stirling2_count(4, 1), 1)
        self.assertEqual(self.m.stirling2_count(4, 4), 1)
        self.assertEqual(self.m.stirling2_count(0, 0), 1)
        self.assertEqual(self.m.stirling2_count(3, 0), 0)
        with self.assertRaises(ValueError):
            self.m.stirling2_count(3, 4)
        with self.assertRaises(ValueError):
            self.m.stirling2_count(101, 2)

    def test_integer_partitions_count(self):
        self.assertEqual(self.m.integer_partitions_count(0), 1)
        self.assertEqual(self.m.integer_partitions_count(4), 5)
        self.assertEqual(self.m.integer_partitions_count(5), 7)
        self.assertEqual(self.m.integer_partitions_count(10), 42)
        self.assertEqual(self.m.integer_partitions_count(100), 190569292)
        with self.assertRaises(ValueError):
            self.m.integer_partitions_count(-1)
        with self.assertRaises(ValueError):
            self.m.integer_partitions_count(101)


    def test_pythagorean_triple_check(self):
        self.assertTrue(self.m.pythagorean_triple_check(3, 4, 5))
        self.assertTrue(self.m.pythagorean_triple_check(5, 12, 13))
        self.assertFalse(self.m.pythagorean_triple_check(1, 2, 3))
        self.assertFalse(self.m.pythagorean_triple_check(3, 4, 6))
        with self.assertRaises(ValueError):
            self.m.pythagorean_triple_check(0, 4, 5)
        with self.assertRaises(ValueError):
            self.m.pythagorean_triple_check(3, 4, -5)


if __name__ == "__main__":
    unittest.main()
