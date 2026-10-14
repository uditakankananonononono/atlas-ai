"""Tests for P235 concepts batch 43 (421-430)."""
import random
import unittest
from itertools import combinations

from app.modules.instinct_doc import p235_concepts_batch43 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class Batch43Test(unittest.TestCase):
    def test_wiggle_max_length(self):
        self.assertEqual(m.wiggle_max_length([1, 7, 4, 9, 2, 5]), 6)
        self.assertEqual(m.wiggle_max_length([1, 1, 1]), 1)
        self.assertEqual(m.wiggle_max_length([1, 2]), 2)
        self.assertEqual(m.wiggle_max_length([5]), 1)
        # oracle: DP tracking both ending directions, independently
        rng = random.Random(4301)
        for _ in range(50):
            vals = [rng.randint(0, 9)
                    for _ in range(rng.randint(1, 15))]
            best = 1
            up = [1] * len(vals)
            down = [1] * len(vals)
            for i in range(len(vals)):
                for j in range(i):
                    if vals[i] > vals[j]:
                        up[i] = max(up[i], down[j] + 1)
                    elif vals[i] < vals[j]:
                        down[i] = max(down[i], up[j] + 1)
                best = max(best, up[i], down[i])
            self.assertEqual(m.wiggle_max_length(vals), best, vals)
        with self.assertRaises(ValueError):
            m.wiggle_max_length([])

    def test_longest_arithmetic_subseq(self):
        self.assertEqual(m.longest_arithmetic_subseq([9, 4, 7, 2, 10]), 3)
        self.assertEqual(m.longest_arithmetic_subseq([3, 6, 9, 12]), 4)
        self.assertEqual(m.longest_arithmetic_subseq([5, 5]), 2)
        self.assertEqual(m.longest_arithmetic_subseq([8]), 1)
        # oracle: brute force over small inputs via position subsets
        rng = random.Random(4302)
        for _ in range(30):
            n = rng.randint(1, 8)
            vals = [rng.randint(0, 9) for _ in range(n)]
            best = min(n, 2) if n else 0
            for r in range(3, n + 1):
                for combo in combinations(range(n), r):
                    diffs = {vals[combo[k + 1]] - vals[combo[k]]
                             for k in range(r - 1)}
                    if len(diffs) == 1:
                        best = r
                        break
                if best == n:
                    break
            self.assertEqual(m.longest_arithmetic_subseq(vals), best,
                             vals)
        with self.assertRaises(ValueError):
            m.longest_arithmetic_subseq([])

    def test_russian_doll_envelopes(self):
        self.assertEqual(m.russian_doll_envelopes(
            [[5, 4], [6, 4], [6, 7], [2, 3]]), 3)
        self.assertEqual(m.russian_doll_envelopes([[1, 1], [1, 1]]), 1)
        # oracle: O(n^2) longest-chain DP on the sorted pairs
        rng = random.Random(4303)
        for _ in range(40):
            n = rng.randint(1, 9)
            env = [[rng.randint(1, 8), rng.randint(1, 8)]
                   for _ in range(n)]
            seq = sorted(env)
            dp = [1] * n
            best = 1
            for i in range(n):
                for j in range(i):
                    if (seq[j][0] < seq[i][0]
                            and seq[j][1] < seq[i][1]):
                        dp[i] = max(dp[i], dp[j] + 1)
                best = max(best, dp[i])
            self.assertEqual(m.russian_doll_envelopes(env), best, env)
        with self.assertRaises(ValueError):
            m.russian_doll_envelopes([])
        with self.assertRaises(ValueError):
            m.russian_doll_envelopes([[0, 2]])

    def test_max_length_chain_pairs(self):
        self.assertEqual(m.max_length_chain_pairs(
            [[1, 2], [2, 3], [3, 4]]), 2)
        self.assertEqual(m.max_length_chain_pairs(
            [[5, 6], [1, 2], [2, 3]]), 2)
        # oracle: exhaustive increasing subsequence check, tiny inputs
        rng = random.Random(4304)
        for _ in range(30):
            n = rng.randint(1, 7)
            pairs = [[rng.randint(1, 8), rng.randint(1, 8)]
                     for _ in range(n)]
            best = 1
            for r in range(2, n + 1):
                found = False
                for combo in combinations(range(n), r):
                    seq = sorted((pairs[i] for i in combo))
                    if all(seq[k][1] < seq[k + 1][0]
                           for k in range(r - 1)):
                        found = True
                        break
                if found:
                    best = r
            self.assertEqual(m.max_length_chain_pairs(pairs), best,
                             pairs)
        with self.assertRaises(ValueError):
            m.max_length_chain_pairs([[2, 0]])

    def test_count_digit_one_upto(self):
        self.assertEqual(m.count_digit_one_upto(13), 6)
        self.assertEqual(m.count_digit_one_upto(0), 0)
        self.assertEqual(m.count_digit_one_upto(1), 1)
        # oracle: direct string count over the range
        rng = random.Random(4305)
        for _ in range(25):
            n = rng.randint(0, 3000)
            want = sum(str(x).count("1") for x in range(n + 1))
            self.assertEqual(m.count_digit_one_upto(n), want, n)
        with self.assertRaises(ValueError):
            m.count_digit_one_upto(-1)

    def test_bulb_switcher_count(self):
        self.assertEqual(m.bulb_switcher_count(0), 0)
        self.assertEqual(m.bulb_switcher_count(3), 1)
        self.assertEqual(m.bulb_switcher_count(8), 2)
        # oracle: simulate the toggle rounds for small n
        for n in range(0, 60):
            bulbs = [False] * n
            for round_ in range(1, n + 1):
                for i in range(round_ - 1, n, round_):
                    bulbs[i] = not bulbs[i]
            self.assertEqual(m.bulb_switcher_count(n), sum(bulbs), n)
        with self.assertRaises(ValueError):
            m.bulb_switcher_count(-1)

    def test_arrange_coins_rows(self):
        self.assertEqual(m.arrange_coins_rows(8), 3)
        self.assertEqual(m.arrange_coins_rows(0), 0)
        self.assertEqual(m.arrange_coins_rows(1), 1)
        self.assertEqual(m.arrange_coins_rows(10), 4)
        # oracle: closed-form triangular bound
        rng = random.Random(4307)
        for _ in range(40):
            coins = rng.randint(0, 100000)
            k = 0
            while (k + 1) * (k + 2) // 2 <= coins:
                k += 1
            self.assertEqual(m.arrange_coins_rows(coins), k, coins)
        with self.assertRaises(ValueError):
            m.arrange_coins_rows(-5)

    def test_self_dividing_count(self):
        self.assertEqual(m.self_dividing_count(1, 22), 13)
        self.assertEqual(m.self_dividing_count(47, 85), 4)
        # oracle: direct per-number digit check
        rng = random.Random(4308)
        for _ in range(30):
            lo = rng.randint(1, 500)
            hi = lo + rng.randint(0, 300)

            def ok(x):
                for ch in str(x):
                    d = int(ch)
                    if d == 0 or x % d != 0:
                        return False
                return True

            want = sum(1 for x in range(lo, hi + 1) if ok(x))
            self.assertEqual(m.self_dividing_count(lo, hi), want,
                             (lo, hi))
        with self.assertRaises(ValueError):
            m.self_dividing_count(0, 5)
        with self.assertRaises(ValueError):
            m.self_dividing_count(9, 3)

    def test_h_index_citations(self):
        self.assertEqual(m.h_index_citations([3, 0, 6, 1, 5]), 3)
        self.assertEqual(m.h_index_citations([1, 3, 1]), 1)
        self.assertEqual(m.h_index_citations([100]), 1)
        self.assertEqual(m.h_index_citations([0, 0]), 0)
        # oracle: count-based definition over all h
        rng = random.Random(4309)
        for _ in range(50):
            vals = [rng.randint(0, 12)
                    for _ in range(rng.randint(1, 12))]
            want = max((h for h in range(len(vals) + 1)
                        if sum(1 for v in vals if v >= h) >= h),
                        default=0)
            self.assertEqual(m.h_index_citations(vals), want, vals)
        with self.assertRaises(ValueError):
            m.h_index_citations([-1])
        with self.assertRaises(ValueError):
            m.h_index_citations([])

    def test_reverse_int_capped(self):
        self.assertEqual(m.reverse_int_capped(123), 321)
        self.assertEqual(m.reverse_int_capped(-120), -21)
        self.assertEqual(m.reverse_int_capped(0), 0)
        self.assertEqual(m.reverse_int_capped(1534236469), 0)
        self.assertEqual(m.reverse_int_capped(-2 ** 31), 0)
        # oracle: string reversal + range check
        rng = random.Random(4310)
        for _ in range(50):
            x = rng.randint(-10 ** 10, 10 ** 10)
            s = str(abs(x))[::-1].lstrip("0") or "0"
            v = int(s) * (-1 if x < 0 else 1)
            want = v if -2 ** 31 <= v <= 2 ** 31 - 1 else 0
            self.assertEqual(m.reverse_int_capped(x), want, x)
        # input magnitude cap: at the cap and just past it, both signs
        cap = m.MAX_ABS
        # 10**18 reverses to 1 (leading zeros dropped): inside int32
        self.assertEqual(m.reverse_int_capped(cap), 1)
        self.assertEqual(m.reverse_int_capped(-cap), -1)
        # cap - 1 is a palindrome far outside int32
        self.assertEqual(m.reverse_int_capped(10 ** 18 - 1), 0)
        with self.assertRaises(ValueError) as ctx:
            m.reverse_int_capped(cap + 1)
        self.assertIn("out_of_range:x", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.reverse_int_capped(-(cap + 1))
        self.assertIn("out_of_range:x", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.reverse_int_capped(True)

    def test_registry_knows_batch43(self):
        names = [e["name"] for e in reg.ENTRIES if e["batch"] == 43]
        self.assertEqual(len(names), 10)
        for name in ("wiggle_max_length", "longest_arithmetic_subseq",
                     "russian_doll_envelopes", "max_length_chain_pairs",
                     "count_digit_one_upto", "bulb_switcher_count",
                     "arrange_coins_rows", "self_dividing_count",
                     "h_index_citations", "reverse_int_capped"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
