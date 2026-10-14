"""P235 concepts batch 17 (161-170, number theory): red-first tests."""
from __future__ import annotations

import unittest
from fractions import Fraction


class Batch17Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch17 as m
        self.m = m

    def test_happy_number(self):
        self.assertTrue(self.m.happy_number(19))
        self.assertFalse(self.m.happy_number(4))
        self.assertTrue(self.m.happy_number(1))
        with self.assertRaises(ValueError):
            self.m.happy_number(0)
        with self.assertRaises(ValueError) as c:
            self.m.happy_number(self.m.MAX_HAPPY_N + 1)
        self.assertEqual(str(c.exception), "P235:happy_number:too_many:n")

    def test_armstrong_check(self):
        self.assertTrue(self.m.armstrong_check(153))
        self.assertTrue(self.m.armstrong_check(370))
        self.assertFalse(self.m.armstrong_check(10))
        self.assertTrue(self.m.armstrong_check(0))
        with self.assertRaises(ValueError):
            self.m.armstrong_check(-1)

    def test_perfect_number_check(self):
        self.assertTrue(self.m.perfect_number_check(6))
        self.assertTrue(self.m.perfect_number_check(28))
        self.assertFalse(self.m.perfect_number_check(12))
        self.assertFalse(self.m.perfect_number_check(1))
        with self.assertRaises(ValueError):
            self.m.perfect_number_check(0)

    def test_divisor_count(self):
        self.assertEqual(self.m.divisor_count(12), 6)
        self.assertEqual(self.m.divisor_count(1), 1)
        self.assertEqual(self.m.divisor_count(13), 2)
        with self.assertRaises(ValueError):
            self.m.divisor_count(0)
        with self.assertRaises(ValueError) as c:
            self.m.divisor_count(self.m.MAX_DIVISOR_N + 1)
        self.assertEqual(str(c.exception), "P235:divisor_count:too_many:n")

    def test_mod_inverse(self):
        self.assertEqual(self.m.mod_inverse(3, 7), 5)
        self.assertEqual(self.m.mod_inverse(1, 2), 1)
        with self.assertRaises(ValueError) as c:
            self.m.mod_inverse(2, 4)
        self.assertEqual(str(c.exception), "P235:mod_inverse:no_inverse")
        with self.assertRaises(ValueError):
            self.m.mod_inverse(3, 1)

    def test_euler_totient(self):
        self.assertEqual(self.m.euler_totient(9), 6)
        self.assertEqual(self.m.euler_totient(1), 1)
        self.assertEqual(self.m.euler_totient(36), 12)
        with self.assertRaises(ValueError):
            self.m.euler_totient(0)

    def test_next_prime(self):
        self.assertEqual(self.m.next_prime(13), 17)
        self.assertEqual(self.m.next_prime(2), 3)
        self.assertEqual(self.m.next_prime(0), 2)
        with self.assertRaises(ValueError):
            self.m.next_prime(-5)
        with self.assertRaises(ValueError) as c:
            self.m.next_prime(self.m.MAX_NEXT_PRIME_N)
        self.assertEqual(str(c.exception), "P235:next_prime:too_many:n")

    def test_goldbach_pair(self):
        self.assertEqual(self.m.goldbach_pair(28), (5, 23))
        self.assertEqual(self.m.goldbach_pair(10), (3, 7))
        self.assertEqual(self.m.goldbach_pair(4), (2, 2))
        with self.assertRaises(ValueError) as c:
            self.m.goldbach_pair(7)
        self.assertEqual(str(c.exception), "P235:goldbach_pair:bad_value:n")
        with self.assertRaises(ValueError) as c2:
            self.m.goldbach_pair(self.m.MAX_GOLDBACH_N + 2)
        self.assertEqual(str(c2.exception), "P235:goldbach_pair:too_many:n")

    def test_quadratic_roots_exact(self):
        self.assertEqual(self.m.quadratic_roots_exact(1, -3, 2),
                         (Fraction(2), Fraction(1)))
        self.assertEqual(self.m.quadratic_roots_exact(1, 2, 1),
                         (Fraction(-1), Fraction(-1)))
        with self.assertRaises(ValueError) as c:
            self.m.quadratic_roots_exact(0, 1, 1)
        self.assertEqual(str(c.exception),
                         "P235:quadratic_roots_exact:bad_value:a")
        with self.assertRaises(ValueError) as c2:
            self.m.quadratic_roots_exact(1, 0, 1)
        self.assertEqual(str(c2.exception),
                         "P235:quadratic_roots_exact:no_real_roots")
        with self.assertRaises(ValueError) as c3:
            self.m.quadratic_roots_exact(1, 1, 1)
        self.assertEqual(str(c3.exception),
                         "P235:quadratic_roots_exact:no_real_roots")

    def test_geometric_series_sum(self):
        self.assertEqual(self.m.geometric_series_sum(1, Fraction(1, 2), 10),
                         Fraction(1023, 512))
        self.assertEqual(self.m.geometric_series_sum(5, Fraction(1), 4),
                         Fraction(20))
        self.assertEqual(self.m.geometric_series_sum(2, Fraction(3), 3),
                         Fraction(26))
        with self.assertRaises(ValueError):
            self.m.geometric_series_sum(1, Fraction(1), -1)
        with self.assertRaises(ValueError):
            self.m.geometric_series_sum(1, 2, 3)

    def test_bit_size_caps(self):
        # mod_inverse: values are bit-size capped, not just step bounded
        self.assertEqual(self.m.mod_inverse(3, 11), 4)
        with self.assertRaises(ValueError):
            self.m.mod_inverse(1, 10**18 + 1)
        with self.assertRaises(ValueError):
            self.m.mod_inverse(10**18 + 1, 11)
        # quadratic coefficients capped
        with self.assertRaises(ValueError):
            self.m.quadratic_roots_exact(10**18 + 1, 0, -1)
        # geometric ratio parts capped; at-cap values still compute
        from fractions import Fraction
        self.assertEqual(self.m.geometric_series_sum(
            1, Fraction(1_000), 2), Fraction(1_001))
        with self.assertRaises(ValueError):
            self.m.geometric_series_sum(1, Fraction(1_001), 2)
        with self.assertRaises(ValueError):
            self.m.geometric_series_sum(10**18 + 1, Fraction(1), 2)


if __name__ == "__main__":
    unittest.main()
