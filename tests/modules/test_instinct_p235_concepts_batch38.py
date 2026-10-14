"""P235 concepts, batch 38 (simulation, compression, scheduling, 371-380)."""
from __future__ import annotations

import random
import unittest
from fractions import Fraction

from app.modules.instinct_doc import p235_concepts_batch38 as m


class Batch38Test(unittest.TestCase):
    def test_lru_cache_hits(self):
        self.assertEqual(m.lru_cache_hits([1, 2, 3, 1, 4, 2, 1], 2), 0)
        self.assertEqual(m.lru_cache_hits([1, 2, 1, 3, 1], 2), 2)
        self.assertEqual(m.lru_cache_hits([], 3), 0)
        self.assertEqual(m.lru_cache_hits([7, 7, 7], 1), 2)
        with self.assertRaises(ValueError) as ctx:
            m.lru_cache_hits([1], 0)
        self.assertIn("bad_value:capacity", str(ctx.exception))

    def test_lru_naive_oracle(self):
        rng = random.Random(38)
        for _ in range(120):
            cap = rng.randint(1, 5)
            ops = [rng.randint(1, 8) for _ in range(rng.randint(0, 30))]
            cache = []
            want = 0
            for key in ops:
                if key in cache:
                    want += 1
                    cache = [k for k in cache if k != key]
                cache.append(key)
                if len(cache) > cap:
                    cache = cache[1:]
            self.assertEqual(m.lru_cache_hits(ops, cap), want,
                             (ops, cap))

    def test_huffman_code_lengths(self):
        self.assertEqual(m.huffman_code_lengths([1]), [1])
        self.assertEqual(sorted(m.huffman_code_lengths([1, 1, 1, 1])),
                         [2, 2, 2, 2])
        depths = m.huffman_code_lengths([5, 9, 12, 13, 16, 45])
        self.assertEqual(
            sum(f * l for f, l in zip([5, 9, 12, 13, 16, 45], depths)),
            224)
        with self.assertRaises(ValueError) as ctx:
            m.huffman_code_lengths([1, 0])
        self.assertIn("bad_value", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.huffman_code_lengths([])

    def test_huffman_kraft_and_optimality_oracle(self):
        # Kraft equality (full tree) plus optimality of the expected
        # length, the latter by brute force over integer length
        # assignments satisfying the Kraft inequality - the relaxation
        # whose optimum the Huffman code attains
        def best_expected(freqs):
            n = len(freqs)
            if n == 1:
                return freqs[0]
            best = [None]

            def search(i, used, current):
                if best[0] is not None and current >= best[0]:
                    return
                if i == n:
                    if used == 1:
                        best[0] = current
                    return
                for length in range(1, n + 1):
                    cost = used + Fraction(1, 2 ** length)
                    if cost > 1:
                        continue
                    search(i + 1, cost, current + freqs[i] * length)

            search(0, Fraction(0), 0)
            return best[0]

        rng = random.Random(41)
        for _ in range(25):
            n = rng.randint(2, 6)
            freqs = [rng.randint(1, 20) for _ in range(n)]
            depths = m.huffman_code_lengths(freqs)
            self.assertEqual(sum(Fraction(1, 2 ** l) for l in depths), 1,
                             (freqs, depths))
            got = sum(f * l for f, l in zip(freqs, depths))
            self.assertEqual(got, best_expected(freqs), (freqs, depths))

    def test_job_sequencing_max_profit(self):
        jobs = [[2, 100], [1, 19], [2, 27], [1, 25], [3, 15]]
        self.assertEqual(m.job_sequencing_max_profit(jobs), 142)
        self.assertEqual(m.job_sequencing_max_profit([]), 0)
        self.assertEqual(m.job_sequencing_max_profit([[1, 5]]), 5)
        with self.assertRaises(ValueError) as ctx:
            m.job_sequencing_max_profit([[0, 5]])
        self.assertIn("bad_value", str(ctx.exception))

    def test_job_sequencing_bruteforce_oracle(self):
        from itertools import combinations
        rng = random.Random(43)
        for _ in range(50):
            n = rng.randint(0, 9)
            jobs = [[rng.randint(1, 5), rng.randint(1, 30)]
                    for _ in range(n)]
            best = 0
            for r in range(n + 1):
                for combo in combinations(range(n), r):
                    subset = sorted((jobs[i] for i in combo),
                                    key=lambda j: j[0])
                    if all(subset[pos][0] >= pos + 1
                           for pos in range(len(subset))):
                        best = max(best, sum(j[1] for j in subset))
            self.assertEqual(m.job_sequencing_max_profit(jobs), best,
                             jobs)

    def test_job_sequencing_contract_repair(self):
        # nonpositive profits are never scheduled (skipping is free)
        self.assertEqual(m.job_sequencing_max_profit([[1, -1]]), 0)
        self.assertEqual(m.job_sequencing_max_profit([[1, 0]]), 0)
        self.assertEqual(m.job_sequencing_max_profit(
            [[1, -5], [1, 3], [2, 4]]), 7)
        # deadlines above the cap are refused before allocation
        with self.assertRaises(ValueError) as ctx:
            m.job_sequencing_max_profit([[m.MAX_DEADLINE + 1, 1]])
        self.assertIn("deadline", str(ctx.exception))
        self.assertEqual(m.job_sequencing_max_profit(
            [[m.MAX_DEADLINE, 7]]), 7)

    def test_job_sequencing_oracle_negatives(self):
        from itertools import combinations
        rng = random.Random(380)
        for _ in range(60):
            n = rng.randint(0, 8)
            jobs = [[rng.randint(1, 4), rng.randint(-10, 25)]
                    for _ in range(n)]
            best = 0
            for r in range(n + 1):
                for combo in combinations(range(n), r):
                    subset = sorted((jobs[i] for i in combo),
                                    key=lambda j: j[0])
                    if all(subset[pos][0] >= pos + 1
                           for pos in range(len(subset))):
                        best = max(best, sum(j[1] for j in subset))
            self.assertEqual(m.job_sequencing_max_profit(jobs), best,
                             jobs)

    def test_generate_parentheses_list(self):
        self.assertEqual(m.generate_parentheses_list(0), [""])
        self.assertEqual(m.generate_parentheses_list(2), ["(())", "()()"])
        self.assertEqual(len(m.generate_parentheses_list(4)), 14)
        with self.assertRaises(ValueError) as ctx:
            m.generate_parentheses_list(13)
        self.assertIn("bad_value:n", str(ctx.exception))

    def test_parentheses_bruteforce_oracle(self):
        from itertools import product
        for n in range(1, 6):
            want = set()
            for combo in product("()", repeat=2 * n):
                s = "".join(combo)
                depth = 0
                ok = True
                for ch in s:
                    depth += 1 if ch == "(" else -1
                    if depth < 0:
                        ok = False
                        break
                if ok and depth == 0:
                    want.add(s)
            self.assertEqual(set(m.generate_parentheses_list(n)), want, n)
            # cross-check against the landed Catalan concept
            from app.modules.instinct_doc import (
                p235_concepts_batch16 as b16)
            self.assertEqual(len(m.generate_parentheses_list(n)),
                             b16.catalan_number(n), n)

    def test_bracket_max_nesting(self):
        self.assertEqual(m.bracket_max_nesting("((()))"), 3)
        self.assertEqual(m.bracket_max_nesting("(()())"), 2)
        self.assertEqual(m.bracket_max_nesting(""), 0)
        with self.assertRaises(ValueError) as ctx:
            m.bracket_max_nesting("(()")
        self.assertIn("unbalanced", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.bracket_max_nesting("())(")
        self.assertIn("unbalanced", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.bracket_max_nesting("(a)")
        self.assertIn("bad_value:text", str(ctx.exception))

    def test_bracket_nesting_balance_oracle(self):
        # cross-check: nesting depth is the peak of the running balance;
        # the oracle derives it from a reduction trace instead
        rng = random.Random(47)
        for _ in range(150):
            n = rng.randint(0, 12)
            s = "".join(rng.choice("()") for _ in range(n))
            bal = 0
            ok = True
            peak = 0
            for ch in s:
                bal += 1 if ch == "(" else -1
                peak = max(peak, bal)
                if bal < 0:
                    ok = False
            if not ok or bal != 0:
                with self.assertRaises(ValueError):
                    m.bracket_max_nesting(s)
            else:
                self.assertEqual(m.bracket_max_nesting(s), peak, s)

    def test_sliding_window_median_exact(self):
        self.assertEqual(m.sliding_window_median_exact([1, 3, 2, 4], 3),
                         [Fraction(2), Fraction(3)])
        self.assertEqual(m.sliding_window_median_exact([1, 2, 3, 4], 2),
                         [Fraction(3, 2), Fraction(5, 2), Fraction(7, 2)])
        self.assertEqual(m.sliding_window_median_exact([5], 1),
                         [Fraction(5)])
        with self.assertRaises(ValueError) as ctx:
            m.sliding_window_median_exact([1, 2], 3)
        self.assertIn("k_gt_len", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.sliding_window_median_exact([1, 2], 0)

    def test_sliding_window_median_oracle(self):
        rng = random.Random(53)
        for _ in range(100):
            n = rng.randint(1, 12)
            k = rng.randint(1, n)
            vals = [rng.randint(-9, 9) for _ in range(n)]
            want = []
            for start in range(n - k + 1):
                window = sorted(vals[start:start + k])
                if k % 2:
                    want.append(Fraction(window[k // 2]))
                else:
                    want.append(
                        Fraction(window[k // 2 - 1] + window[k // 2], 2))
            self.assertEqual(m.sliding_window_median_exact(vals, k),
                             want, (vals, k))

    def test_clock_angle_exact(self):
        self.assertEqual(m.clock_angle_exact(3, 0), 90)
        self.assertEqual(m.clock_angle_exact(12, 0), 0)
        self.assertEqual(m.clock_angle_exact(6, 30), 15)
        self.assertEqual(m.clock_angle_exact(15, 30), 75)
        self.assertEqual(m.clock_angle_exact(0, 0), 0)
        with self.assertRaises(ValueError):
            m.clock_angle_exact(24, 0)
        with self.assertRaises(ValueError):
            m.clock_angle_exact(3, 60)

    def test_clock_angle_oracle(self):
        # independent: simulate hand positions in minute ticks from
        # midnight and measure the smaller arc in Fraction degrees
        rng = random.Random(59)
        for _ in range(100):
            hour = rng.randint(0, 23)
            minute = rng.randint(0, 59)
            ticks = (hour % 12) * 60 + minute
            hour_pos = Fraction(ticks, 2)  # 0.5 deg per minute
            minute_pos = Fraction(6 * minute)
            diff = abs(hour_pos - minute_pos)
            want = min(diff, Fraction(360) - diff)
            self.assertEqual(m.clock_angle_exact(hour, minute), want,
                             (hour, minute))

    def test_elevator_total_travel(self):
        self.assertEqual(m.elevator_total_travel(0, [3, 5, 2]), 8)
        self.assertEqual(m.elevator_total_travel(4, []), 0)
        self.assertEqual(m.elevator_total_travel(2, [2, 2]), 0)
        with self.assertRaises(ValueError):
            m.elevator_total_travel(-1, [2])

    def test_elevator_oracle(self):
        rng = random.Random(61)
        for _ in range(80):
            start = rng.randint(0, 20)
            reqs = [rng.randint(0, 20) for _ in range(rng.randint(0, 15))]
            want = 0
            at = start
            for floor in reqs:
                want += max(floor - at, at - floor)
                at = floor
            self.assertEqual(m.elevator_total_travel(start, reqs), want)

    def test_binary_watch_count(self):
        self.assertEqual(m.binary_watch_count(0), 1)
        self.assertEqual(m.binary_watch_count(1), 10)
        with self.assertRaises(ValueError) as ctx:
            m.binary_watch_count(11)
        self.assertIn("bad_value:lit", str(ctx.exception))

    def test_binary_watch_oracle(self):
        def popcount(v):
            count = 0
            while v:
                count += v & 1
                v >>= 1
            return count

        for lit in range(0, 9):
            want = sum(1 for h in range(12) for mnt in range(60)
                       if popcount(h) + popcount(mnt) == lit)
            self.assertEqual(m.binary_watch_count(lit), want, lit)

    def test_collatz_peak_value(self):
        self.assertEqual(m.collatz_peak_value(1), 1)
        self.assertEqual(m.collatz_peak_value(27), 9232)
        self.assertEqual(m.collatz_peak_value(6), 16)
        with self.assertRaises(ValueError):
            m.collatz_peak_value(0)

    def test_collatz_peak_oracle(self):
        def oracle(n):
            peak = n
            while n != 1:
                n = n // 2 if n % 2 == 0 else 3 * n + 1
                peak = max(peak, n)
            return peak

        rng = random.Random(67)
        for _ in range(60):
            n = rng.randint(1, 5000)
            self.assertEqual(m.collatz_peak_value(n), oracle(n), n)

    def test_registry_knows_batch38(self):
        from app.modules.instinct_doc import p235_concepts_registry as reg
        own = [e for e in reg.ENTRIES if e["batch"] == 38]
        self.assertEqual(len(own), 10)
        names = [e["name"] for e in own]
        for name in ("lru_cache_hits", "huffman_code_lengths",
                     "job_sequencing_max_profit",
                     "generate_parentheses_list", "bracket_max_nesting",
                     "sliding_window_median_exact", "clock_angle_exact",
                     "elevator_total_travel", "binary_watch_count",
                     "collatz_peak_value"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
