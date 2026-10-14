"""P235 concepts batch 32 tests - red-first."""
from __future__ import annotations

import unittest
from fractions import Fraction


class Batch32Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch32 as m
        self.m = m

    def test_perfect_power_check(self):
        self.assertTrue(self.m.perfect_power_check(36))
        self.assertTrue(self.m.perfect_power_check(8))
        self.assertTrue(self.m.perfect_power_check(1))
        self.assertFalse(self.m.perfect_power_check(12))
        self.assertFalse(self.m.perfect_power_check(2))
        self.assertTrue(self.m.perfect_power_check(10**12))
        self.assertFalse(self.m.perfect_power_check(10**12 - 1))
        with self.assertRaises(ValueError) as c:
            self.m.perfect_power_check(0)
        self.assertEqual(str(c.exception),
                         "P235:perfect_power_check:bad_value:n")
        with self.assertRaises(ValueError) as c:
            self.m.perfect_power_check(10**12 + 1)
        self.assertEqual(str(c.exception),
                         "P235:perfect_power_check:too_big:n")

    def test_carmichael_check(self):
        self.assertTrue(self.m.carmichael_check(561))
        self.assertTrue(self.m.carmichael_check(41041))
        self.assertFalse(self.m.carmichael_check(15))
        self.assertFalse(self.m.carmichael_check(7))
        self.assertFalse(self.m.carmichael_check(4))
        with self.assertRaises(ValueError) as c:
            self.m.carmichael_check(10**12 + 1)
        self.assertEqual(str(c.exception),
                         "P235:carmichael_check:too_big:n")

    def test_legendre_symbol(self):
        self.assertEqual(self.m.legendre_symbol(2, 7), 1)
        self.assertEqual(self.m.legendre_symbol(3, 7), -1)
        self.assertEqual(self.m.legendre_symbol(0, 7), 0)
        self.assertEqual(self.m.legendre_symbol(14, 7), 0)
        self.assertEqual(self.m.legendre_symbol(-1, 7), -1)
        self.assertEqual(self.m.legendre_symbol(-1, 5), 1)
        self.assertEqual(self.m.legendre_symbol(4, 11), 1)
        for bad in (4, 9, 1, 2):
            with self.assertRaises(ValueError, msg=bad) as c:
                self.m.legendre_symbol(2, bad)
            self.assertEqual(str(c.exception),
                             "P235:legendre_symbol:bad_value:p")

    def test_continued_fraction_of(self):
        self.assertEqual(self.m.continued_fraction_of(7, 3), [2, 3])
        self.assertEqual(self.m.continued_fraction_of(415, 93),
                         [4, 2, 6, 7])
        self.assertEqual(self.m.continued_fraction_of(1, 1), [1])
        self.assertEqual(self.m.continued_fraction_of(-3, 4), [-1, 4])
        with self.assertRaises(ValueError) as c:
            self.m.continued_fraction_of(1, 0)
        self.assertEqual(str(c.exception),
                         "P235:continued_fraction_of:bad_value:q")

    def test_continued_fraction_value(self):
        self.assertEqual(self.m.continued_fraction_value([2, 3]),
                         Fraction(7, 3))
        self.assertEqual(self.m.continued_fraction_value([4, 2, 6, 7]),
                         Fraction(415, 93))
        self.assertEqual(self.m.continued_fraction_value([1]), Fraction(1))
        for terms in ([0, 1], [1, 0], [1, 2, 0]):
            with self.assertRaises(ValueError, msg=terms) as c:
                self.m.continued_fraction_value(terms)
            self.assertEqual(
                str(c.exception),
                "P235:continued_fraction_value:bad_value:terms")
        for p, q in ((7, 3), (415, 93), (-3, 4), (1, 97)):
            self.assertEqual(
                self.m.continued_fraction_value(
                    self.m.continued_fraction_of(p, q)),
                Fraction(p, q), (p, q))

    def test_sqrt_cf_period(self):
        self.assertEqual(self.m.sqrt_cf_period(2), 1)
        self.assertEqual(self.m.sqrt_cf_period(3), 2)
        self.assertEqual(self.m.sqrt_cf_period(7), 4)
        self.assertEqual(self.m.sqrt_cf_period(23), 4)
        self.assertEqual(self.m.sqrt_cf_period(16), 0)
        self.assertEqual(self.m.sqrt_cf_period(13), 5)
        for bad in (0, -1, 10_001):
            with self.assertRaises(ValueError, msg=bad) as c:
                self.m.sqrt_cf_period(bad)
            self.assertEqual(str(c.exception),
                             "P235:sqrt_cf_period:bad_value:n")

    def test_lucas_lehmer_check(self):
        self.assertTrue(self.m.lucas_lehmer_check(3))
        self.assertTrue(self.m.lucas_lehmer_check(5))
        self.assertTrue(self.m.lucas_lehmer_check(13))
        self.assertFalse(self.m.lucas_lehmer_check(11))
        self.assertFalse(self.m.lucas_lehmer_check(23))
        for bad in (1, 4, 608, 9):
            with self.assertRaises(ValueError, msg=bad) as c:
                self.m.lucas_lehmer_check(bad)
            self.assertEqual(str(c.exception),
                             "P235:lucas_lehmer_check:bad_value:p")

    def test_fermat_factor(self):
        self.assertEqual(self.m.fermat_factor(91), (7, 13))
        self.assertEqual(self.m.fermat_factor(8051), (83, 97))
        self.assertEqual(self.m.fermat_factor(9), (3, 3))
        self.assertEqual(self.m.fermat_factor(15), (3, 5))
        for bad, code in ((4, "bad_value:n"), (17, "bad_value:n"),
                          (1, "bad_value:n"),
                          (10**12 + 1, "too_big:n")):
            with self.assertRaises(ValueError, msg=bad) as c:
                self.m.fermat_factor(bad)
            self.assertEqual(str(c.exception),
                             "P235:fermat_factor:" + code)

    def test_prime_gap_max_upto(self):
        self.assertEqual(self.m.prime_gap_max_upto(20), 4)
        self.assertEqual(self.m.prime_gap_max_upto(2), 0)
        self.assertEqual(self.m.prime_gap_max_upto(10), 2)
        self.assertEqual(self.m.prime_gap_max_upto(100), 8)
        with self.assertRaises(ValueError) as c:
            self.m.prime_gap_max_upto(1)
        self.assertEqual(str(c.exception),
                         "P235:prime_gap_max_upto:bad_value:n")
        with self.assertRaises(ValueError) as c:
            self.m.prime_gap_max_upto(1_000_001)
        self.assertEqual(str(c.exception),
                         "P235:prime_gap_max_upto:too_big:n")

    def test_segments_intersect_check(self):
        self.assertTrue(self.m.segments_intersect_check(
            (0, 0), (1, 1), (0, 1), (1, 0)))
        self.assertFalse(self.m.segments_intersect_check(
            (0, 0), (1, 0), (2, 1), (3, 1)))
        # collinear overlapping segments count as intersecting
        self.assertTrue(self.m.segments_intersect_check(
            (0, 0), (2, 0), (1, 0), (3, 0)))
        self.assertFalse(self.m.segments_intersect_check(
            (0, 0), (1, 0), (2, 0), (3, 0)))
        # shared endpoint
        self.assertTrue(self.m.segments_intersect_check(
            (0, 0), (1, 1), (1, 1), (2, 0)))
        with self.assertRaises(ValueError) as c:
            self.m.segments_intersect_check((0, 0), (10**7, 0),
                                            (0, 1), (1, 1))
        self.assertEqual(
            str(c.exception),
            "P235:segments_intersect_check:bad_value:p2")


if __name__ == "__main__":
    unittest.main()
