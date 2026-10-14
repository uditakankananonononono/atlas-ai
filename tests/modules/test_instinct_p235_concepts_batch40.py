"""Tests for P235 concepts batch 40 (391-400)."""
import random
import unittest
from collections import Counter
from itertools import combinations

from app.modules.instinct_doc import p235_concepts_batch40 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class Batch40Test(unittest.TestCase):
    def test_top_k_frequent_values(self):
        self.assertEqual(m.top_k_frequent_values([1, 1, 2, 2, 2, 3], 2),
                         [2, 1])
        # tie broken by smaller value first
        self.assertEqual(m.top_k_frequent_values([2, 2, 1, 1], 2), [1, 2])
        # oracle: Counter counts, same tie policy, independent ranking
        rng = random.Random(4001)
        for _ in range(50):
            vals = [rng.randint(0, 20)
                    for _ in range(rng.randint(1, 30))]
            k = rng.randint(1, 5)
            counts = Counter(vals)
            want = sorted(counts, key=lambda v: (-counts[v], v))[:k]
            self.assertEqual(m.top_k_frequent_values(vals, k), want, vals)
        with self.assertRaises(ValueError):
            m.top_k_frequent_values([], 1)
        with self.assertRaises(ValueError):
            m.top_k_frequent_values([1], 0)
        with self.assertRaises(ValueError):
            m.top_k_frequent_values([1], m.MAX_K + 1)

    def test_longest_consecutive_streak(self):
        self.assertEqual(
            m.longest_consecutive_streak([100, 4, 200, 1, 3, 2]), 4)
        self.assertEqual(m.longest_consecutive_streak([7]), 1)
        self.assertEqual(m.longest_consecutive_streak([1, 1, 1]), 1)
        # oracle: sort + scan for runs
        rng = random.Random(4002)
        for _ in range(60):
            vals = [rng.randint(-15, 15)
                    for _ in range(rng.randint(1, 25))]
            have = sorted(set(vals))
            want = 1
            run = 1
            for i in range(1, len(have)):
                if have[i] == have[i - 1] + 1:
                    run += 1
                    want = max(want, run)
                else:
                    run = 1
            self.assertEqual(m.longest_consecutive_streak(vals), want,
                             vals)
        with self.assertRaises(ValueError):
            m.longest_consecutive_streak([])

    def test_product_except_self(self):
        self.assertEqual(m.product_except_self([1, 2, 3, 4]),
                         [24, 12, 8, 6])
        self.assertEqual(m.product_except_self([0, 4]), [4, 0])
        self.assertEqual(m.product_except_self([5]), [1])
        # oracle: direct O(n^2) recomputation
        rng = random.Random(4003)
        for _ in range(50):
            n = rng.randint(1, 10)
            vals = [rng.randint(-5, 5) for _ in range(n)]
            want = []
            for i in range(n):
                prod = 1
                for j in range(n):
                    if j != i:
                        prod *= vals[j]
                want.append(prod)
            self.assertEqual(m.product_except_self(vals), want, vals)
        with self.assertRaises(ValueError):
            m.product_except_self([])
        with self.assertRaises(ValueError):
            m.product_except_self([True, 2])

    def test_first_missing_positive(self):
        self.assertEqual(m.first_missing_positive([3, 4, -1, 1]), 2)
        self.assertEqual(m.first_missing_positive([1, 2, 0]), 3)
        self.assertEqual(m.first_missing_positive([7, 8, 9]), 1)
        # oracle: direct scan over the positive integers
        rng = random.Random(4004)
        for _ in range(50):
            vals = [rng.randint(-5, 20)
                    for _ in range(rng.randint(1, 20))]
            have = set(vals)
            want = 1
            while want in have:
                want += 1
            self.assertEqual(m.first_missing_positive(vals), want, vals)
        with self.assertRaises(ValueError):
            m.first_missing_positive([])

    def test_max_product_of_three(self):
        self.assertEqual(m.max_product_of_three([-10, -10, 5, 2]), 500)
        self.assertEqual(m.max_product_of_three([1, 2, 3]), 6)
        self.assertEqual(m.max_product_of_three([-1, -2, -3]), -6)
        # oracle: exhaustive triples by position
        rng = random.Random(4005)
        for _ in range(60):
            n = rng.randint(3, 10)
            vals = [rng.randint(-9, 9) for _ in range(n)]
            want = max(vals[i] * vals[j] * vals[k]
                       for i, j, k in combinations(range(n), 3))
            self.assertEqual(m.max_product_of_three(vals), want, vals)
        with self.assertRaises(ValueError):
            m.max_product_of_three([1, 2])

    def test_count_bits_total_upto(self):
        self.assertEqual(m.count_bits_total_upto(0), 0)
        self.assertEqual(m.count_bits_total_upto(5), 7)
        # oracle: bin().count over the whole range
        rng = random.Random(4006)
        for _ in range(25):
            n = rng.randint(0, 500)
            want = sum(bin(x).count("1") for x in range(n + 1))
            self.assertEqual(m.count_bits_total_upto(n), want, n)
        with self.assertRaises(ValueError):
            m.count_bits_total_upto(-1)
        with self.assertRaises(ValueError):
            m.count_bits_total_upto(m.MAX_N + 1)
        m.count_bits_total_upto(m.MAX_N)

    def test_xor_range_total(self):
        self.assertEqual(m.xor_range_total(3, 9), 2)
        self.assertEqual(m.xor_range_total(0, 0), 0)
        self.assertEqual(m.xor_range_total(5, 5), 5)
        # oracle: direct XOR fold
        rng = random.Random(4007)
        for _ in range(40):
            lo = rng.randint(0, 200)
            hi = lo + rng.randint(0, 100)
            want = 0
            for x in range(lo, hi + 1):
                want ^= x
            self.assertEqual(m.xor_range_total(lo, hi), want, (lo, hi))
        with self.assertRaises(ValueError):
            m.xor_range_total(4, 2)
        with self.assertRaises(ValueError):
            m.xor_range_total(-1, 2)

    def test_gini_coefficient_exact(self):
        from fractions import Fraction
        self.assertEqual(m.gini_coefficient_exact([1, 1, 1, 1]), 0)
        self.assertEqual(m.gini_coefficient_exact([0, 0, 0, 10]),
                         Fraction(3, 4))
        self.assertEqual(m.gini_coefficient_exact([1, 2, 3]),
                         Fraction(2, 9))
        # oracle: definition over all ordered pairs, Fraction exact
        rng = random.Random(4011)
        for _ in range(40):
            n = rng.randint(1, 8)
            vals = [rng.randint(0, 30) for _ in range(n)]
            if sum(vals) == 0:
                continue
            num = sum(abs(vals[i] - vals[j])
                      for i in range(n) for j in range(n))
            want = Fraction(num, 2 * n * sum(vals))
            self.assertEqual(m.gini_coefficient_exact(vals), want, vals)
        with self.assertRaises(ValueError):
            m.gini_coefficient_exact([0, 0])
        with self.assertRaises(ValueError):
            m.gini_coefficient_exact([])
        # the negative guard fires before the total-zero guard, and the
        # refusal names the offending index
        for bad, code in (([-1, 1], "bad_value:values[0]"),
                          ([-1, 3], "bad_value:values[0]"),
                          ([5, -2, 0], "bad_value:values[1]"),
                          ([0, -1], "bad_value:values[1]"),
                          ([1, -1], "bad_value:values[1]")):
            with self.assertRaises(ValueError, msg=bad) as ctx:
                m.gini_coefficient_exact(bad)
            self.assertIn(code, str(ctx.exception), bad)

    def test_gas_station_start(self):
        self.assertEqual(m.gas_station_start([1, 2, 3, 4, 5],
                                             [3, 4, 5, 1, 2]), 3)
        self.assertEqual(m.gas_station_start([2, 3, 4], [3, 4, 3]), -1)
        self.assertEqual(m.gas_station_start([5], [4]), 0)
        # oracle: simulate every candidate start
        rng = random.Random(4009)
        for _ in range(50):
            n = rng.randint(1, 8)
            gas = [rng.randint(0, 10) for _ in range(n)]
            cost = [rng.randint(0, 10) for _ in range(n)]

            def completes(start):
                tank = 0
                for step in range(n):
                    i = (start + step) % n
                    tank += gas[i] - cost[i]
                    if tank < 0:
                        return False
                return True

            want = -1
            for s in range(n):
                if completes(s):
                    want = s
                    break
            self.assertEqual(m.gas_station_start(gas, cost), want,
                             (gas, cost))
        with self.assertRaises(ValueError):
            m.gas_station_start([1], [1, 2])
        with self.assertRaises(ValueError):
            m.gas_station_start([-1], [0])

    def test_candy_min_total(self):
        self.assertEqual(m.candy_min_total([1, 0, 2]), 5)
        self.assertEqual(m.candy_min_total([1, 2, 2]), 4)
        self.assertEqual(m.candy_min_total([3]), 1)
        self.assertEqual(m.candy_min_total([1, 3, 4, 5, 2]), 11)
        # oracle: exhaustive search over tiny bounded assignments
        rng = random.Random(4010)
        for _ in range(25):
            n = rng.randint(1, 5)
            ratings = [rng.randint(1, 3) for _ in range(n)]
            best = None
            cap = n + 2
            for assign in __import__("itertools").product(
                    range(1, cap + 1), repeat=n):
                ok = True
                for i in range(n - 1):
                    if ratings[i] < ratings[i + 1] and not (
                            assign[i] < assign[i + 1]):
                        ok = False
                        break
                    if ratings[i] > ratings[i + 1] and not (
                            assign[i] > assign[i + 1]):
                        ok = False
                        break
                if ok:
                    total = sum(assign)
                    if best is None or total < best:
                        best = total
            self.assertEqual(m.candy_min_total(ratings), best, ratings)
        with self.assertRaises(ValueError):
            m.candy_min_total([])
        with self.assertRaises(ValueError):
            m.candy_min_total([0] * (m.MAX_RATINGS + 1))
        m.candy_min_total([0] * m.MAX_RATINGS)

    def test_registry_knows_batch40(self):
        names = [e["name"] for e in reg.ENTRIES if e["batch"] == 40]
        self.assertEqual(len(names), 10)
        for name in ("top_k_frequent_values", "longest_consecutive_streak",
                     "product_except_self", "first_missing_positive",
                     "max_product_of_three", "count_bits_total_upto",
                     "xor_range_total", "gini_coefficient_exact",
                     "gas_station_start", "candy_min_total"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
