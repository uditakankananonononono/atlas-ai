"""P235 concepts batch 9 (81-90, algorithms): red-first tests."""
from __future__ import annotations

import unittest


class Batch9Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch9 as m
        self.m = m

    def test_manhattan_distance(self):
        self.assertEqual(self.m.manhattan_distance([1, 2], [4, 6]), 7)
        self.assertEqual(self.m.manhattan_distance([0], [0]), 0)
        self.assertEqual(self.m.manhattan_distance([-3, 5], [2, -1]), 11)
        with self.assertRaises(ValueError) as c:
            self.m.manhattan_distance([1], [1, 2])
        self.assertEqual(str(c.exception),
                         "P235:manhattan_distance:length_mismatch")
        with self.assertRaises(ValueError):
            self.m.manhattan_distance([True], [1])
        with self.assertRaises(ValueError):
            self.m.manhattan_distance("ab", "cd")

    def test_prime_check_trial(self):
        self.assertFalse(self.m.prime_check_trial(0))
        self.assertFalse(self.m.prime_check_trial(1))
        self.assertTrue(self.m.prime_check_trial(2))
        self.assertTrue(self.m.prime_check_trial(7919))
        self.assertFalse(self.m.prime_check_trial(7920))
        with self.assertRaises(ValueError):
            self.m.prime_check_trial(-7)
        with self.assertRaises(ValueError):
            self.m.prime_check_trial(True)
        with self.assertRaises(ValueError) as c:
            self.m.prime_check_trial(self.m.MAX_PRIME_N + 1)
        self.assertEqual(str(c.exception),
                         "P235:prime_check_trial:too_many:n")

    def test_sieve_primes_upto(self):
        self.assertEqual(self.m.sieve_primes_upto(1), [])
        self.assertEqual(self.m.sieve_primes_upto(2), [2])
        self.assertEqual(self.m.sieve_primes_upto(30),
                         [2, 3, 5, 7, 11, 13, 17, 19, 23, 29])
        with self.assertRaises(ValueError):
            self.m.sieve_primes_upto(-1)
        with self.assertRaises(ValueError) as c:
            self.m.sieve_primes_upto(self.m.MAX_SIEVE_N + 1)
        self.assertEqual(str(c.exception),
                         "P235:sieve_primes_upto:too_many:n")

    def test_merge_intervals(self):
        self.assertEqual(self.m.merge_intervals([[1, 3], [2, 6], [8, 10]]),
                         [[1, 6], [8, 10]])
        self.assertEqual(self.m.merge_intervals([]), [])
        self.assertEqual(self.m.merge_intervals([[5, 5], [1, 2]]),
                         [[1, 2], [5, 5]])
        self.assertEqual(self.m.merge_intervals([[1, 4], [4, 5]]), [[1, 5]])
        with self.assertRaises(ValueError) as c:
            self.m.merge_intervals([[3, 1]])
        self.assertEqual(str(c.exception),
                         "P235:merge_intervals:bad_value:interval")
        with self.assertRaises(ValueError):
            self.m.merge_intervals([[1, "x"]])
        with self.assertRaises(ValueError):
            self.m.merge_intervals([[1, 2, 3]])

    def test_binary_search_index(self):
        self.assertEqual(self.m.binary_search_index([1, 3, 5, 7], 5), 2)
        self.assertEqual(self.m.binary_search_index([1, 3, 5, 7], 4), -1)
        self.assertEqual(self.m.binary_search_index([2, 2, 2], 2), 0)
        self.assertEqual(self.m.binary_search_index([], 1), -1)
        with self.assertRaises(ValueError) as c:
            self.m.binary_search_index([3, 1, 2], 1)
        self.assertEqual(str(c.exception),
                         "P235:binary_search_index:unsorted:items")
        with self.assertRaises(ValueError):
            self.m.binary_search_index([1, "x"], 1)

    def test_kadane_max_subarray(self):
        self.assertEqual(self.m.kadane_max_subarray([-2, 1, -3, 4, -1, 2, 1, -5, 4]), 6)
        self.assertEqual(self.m.kadane_max_subarray([-5, -2]), -2)
        self.assertEqual(self.m.kadane_max_subarray([7]), 7)
        with self.assertRaises(ValueError) as c:
            self.m.kadane_max_subarray([])
        self.assertEqual(str(c.exception),
                         "P235:kadane_max_subarray:empty:items")
        with self.assertRaises(ValueError):
            self.m.kadane_max_subarray([1, 1.5])

    def test_lis_length(self):
        self.assertEqual(self.m.lis_length([10, 9, 2, 5, 3, 7, 101, 18]), 4)
        self.assertEqual(self.m.lis_length([]), 0)
        self.assertEqual(self.m.lis_length([7, 7, 7]), 1)
        self.assertEqual(self.m.lis_length([1, 2, 3]), 3)
        with self.assertRaises(ValueError) as c:
            self.m.lis_length([0] * (self.m.MAX_LIS_N + 1))
        self.assertEqual(str(c.exception), "P235:lis_length:too_many:items")
        with self.assertRaises(ValueError):
            self.m.lis_length([1, "x"])

    def test_hamming_distance(self):
        self.assertEqual(self.m.hamming_distance("karolin", "kathrin"), 3)
        self.assertEqual(self.m.hamming_distance("", ""), 0)
        self.assertEqual(self.m.hamming_distance("abc", "abc"), 0)
        with self.assertRaises(ValueError) as c:
            self.m.hamming_distance("ab", "abc")
        self.assertEqual(str(c.exception),
                         "P235:hamming_distance:length_mismatch")
        with self.assertRaises(ValueError) as c2:
            self.m.hamming_distance("x" * 10_001, "y" * 10_001)
        self.assertEqual(str(c2.exception),
                         "P235:hamming_distance:too_many:text")
        with self.assertRaises(ValueError):
            self.m.hamming_distance("ab", 12)

    def test_pascal_row(self):
        self.assertEqual(self.m.pascal_row(0), [1])
        self.assertEqual(self.m.pascal_row(4), [1, 4, 6, 4, 1])
        self.assertEqual(self.m.pascal_row(1), [1, 1])
        with self.assertRaises(ValueError):
            self.m.pascal_row(-1)
        with self.assertRaises(ValueError) as c:
            self.m.pascal_row(self.m.MAX_PASCAL_N + 1)
        self.assertEqual(str(c.exception), "P235:pascal_row:too_many:n")
        with self.assertRaises(ValueError):
            self.m.pascal_row(True)

    def test_caesar_shift(self):
        self.assertEqual(self.m.caesar_shift("abc XYZ!", 3), "def ABC!")
        self.assertEqual(self.m.caesar_shift("zZ", 1), "aA")
        self.assertEqual(self.m.caesar_shift("Hello", -1), "Gdkkn")
        self.assertEqual(self.m.caesar_shift("ab", 26), "ab")
        with self.assertRaises(ValueError):
            self.m.caesar_shift("ab", 1.0)
        with self.assertRaises(ValueError) as c:
            self.m.caesar_shift("x" * 10_001, 1)
        self.assertEqual(str(c.exception), "P235:caesar_shift:too_many:text")


if __name__ == "__main__":
    unittest.main()
