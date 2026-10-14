"""P235 batch 4 concepts (exact arithmetic): red-first, Fraction oracles."""
from __future__ import annotations

import math
import unittest
from decimal import Decimal
from fractions import Fraction

NAMES = ("fraction_median", "fraction_mean", "weighted_sum_exact",
         "clamp_bounds", "safe_ratio", "round_half_even_cents",
         "percent_change_exact", "gcd_pair", "lcm_pair", "integer_sqrt_floor")


class Batch4Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch4 as m
        self.m = m

    def test_fraction_median(self):
        r = self.m.fraction_median(["1/2", "1/3", "1/4"])
        oracle = sorted([Fraction(1, 2), Fraction(1, 3), Fraction(1, 4)])[1]
        self.assertEqual(r, oracle)
        r2 = self.m.fraction_median(["1/2", "1/4"])
        self.assertEqual(r2, (Fraction(1, 2) + Fraction(1, 4)) / 2)
        with self.assertRaises(ValueError):
            self.m.fraction_median([])
        with self.assertRaises(ValueError):
            self.m.fraction_median([0.5])

    def test_fraction_mean(self):
        r = self.m.fraction_mean(["1/3", "2/3", 2])
        oracle = (Fraction(1, 3) + Fraction(2, 3) + 2) / 3
        self.assertEqual(r, oracle)
        with self.assertRaises(ValueError):
            self.m.fraction_mean([])

    def test_weighted_sum_exact(self):
        r = self.m.weighted_sum_exact([["1/2", "2"], ["1/4", "4"]])
        oracle = Fraction(1, 2) * 2 + Fraction(1, 4) * 4
        self.assertEqual(r, oracle)
        with self.assertRaises(ValueError):
            self.m.weighted_sum_exact([["1/2"]])
        with self.assertRaises(ValueError):
            self.m.weighted_sum_exact([["1/0", "1"]])

    def test_clamp_bounds(self):
        self.assertEqual(self.m.clamp_bounds("5/2", "0", "2"), Fraction(2))
        self.assertEqual(self.m.clamp_bounds("-1", "0", "2"), Fraction(0))
        self.assertEqual(self.m.clamp_bounds("3/2", "0", "2"), Fraction(3, 2))
        with self.assertRaises(ValueError) as c:
            self.m.clamp_bounds("1", "2", "1")
        self.assertTrue(str(c.exception).startswith("P235:clamp_bounds:bad_value"))

    def test_safe_ratio(self):
        self.assertEqual(self.m.safe_ratio("1", "4"), Fraction(1, 4))
        with self.assertRaises(ValueError) as c:
            self.m.safe_ratio("1", "0")
        self.assertTrue(str(c.exception).startswith("P235:safe_ratio:zero_denominator"))

    def test_round_half_even_cents(self):
        self.assertEqual(self.m.round_half_even_cents("1.005"), Decimal("1.00"))
        self.assertEqual(self.m.round_half_even_cents("1.015"), Decimal("1.02"))
        self.assertEqual(self.m.round_half_even_cents("2.675"), Decimal("2.68"))
        oracle = Decimal("2.675").quantize(Decimal("0.01"))
        self.assertEqual(self.m.round_half_even_cents("2.675"), oracle)
        with self.assertRaises(ValueError):
            self.m.round_half_even_cents("abc")

    def test_percent_change_exact(self):
        r = self.m.percent_change_exact("200", "250")
        self.assertEqual(r, Fraction(25))
        oracle = (Fraction(250) - Fraction(200)) / Fraction(200) * 100
        self.assertEqual(r, oracle)
        with self.assertRaises(ValueError) as c:
            self.m.percent_change_exact("0", "5")
        self.assertTrue(str(c.exception).startswith("P235:percent_change_exact:zero_base"))

    def test_gcd_pair(self):
        self.assertEqual(self.m.gcd_pair(12, 18), math.gcd(12, 18))
        self.assertEqual(self.m.gcd_pair(0, 5), 5)
        with self.assertRaises(ValueError):
            self.m.gcd_pair(-1, 5)
        with self.assertRaises(ValueError):
            self.m.gcd_pair(True, 5)

    def test_lcm_pair(self):
        self.assertEqual(self.m.lcm_pair(4, 6), 12)
        self.assertEqual(self.m.lcm_pair(0, 7), 0)
        with self.assertRaises(ValueError):
            self.m.lcm_pair(-4, 6)

    def test_integer_sqrt_floor(self):
        big = 10**30 + 12345
        r = self.m.integer_sqrt_floor(big)
        self.assertEqual(r, math.isqrt(big))
        self.assertLess(r * r - big, 10**20)
        self.assertEqual(self.m.integer_sqrt_floor(0), 0)
        with self.assertRaises(ValueError):
            self.m.integer_sqrt_floor(-1)

    def test_registry_covers_batch4(self):
        from app.modules.instinct_doc import p235_concepts_registry as reg
        entries = {e["name"]: e for e in reg.ENTRIES if e["batch"] == 4}
        self.assertEqual(set(entries), set(NAMES))


    def test_safe_ratio_refuses_nonfinite_decimal(self):
        for bad in ("Infinity", "-Infinity", "NaN"):
            with self.assertRaises(ValueError) as c:
                self.m.safe_ratio(bad, 1)
            self.assertTrue(str(c.exception).startswith(
                "P235:safe_ratio:bad_value:"))

    def test_round_half_even_cents_bounds_exponent(self):
        with self.assertRaises(ValueError) as c:
            self.m.round_half_even_cents("1e100")
        self.assertEqual(str(c.exception),
                         "P235:round_half_even_cents:too_many:value")
        with self.assertRaises(ValueError):
            self.m.round_half_even_cents("9" * 40)
        self.assertEqual(self.m.round_half_even_cents("12.345"),
                         Decimal("12.34"))
        self.assertEqual(self.m.round_half_even_cents("12.355"),
                         Decimal("12.36"))

    def test_lcm_zero_cases(self):
        self.assertEqual(self.m.lcm_pair(0, 0), 0)
        self.assertEqual(self.m.lcm_pair(0, 5), 0)
        self.assertEqual(self.m.lcm_pair(5, 0), 0)
        self.assertEqual(self.m.lcm_pair(4, 6), 12)

if __name__ == "__main__":
    unittest.main()
