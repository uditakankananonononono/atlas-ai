"""P235 concepts, batch 35 (sequences and strings III, 341-350)."""
from __future__ import annotations

import random
import unittest

from app.modules.instinct_doc import p235_concepts_batch35 as m


class Batch35Test(unittest.TestCase):
    def test_z_function(self):
        self.assertEqual(m.z_function("aabxaab"), [7, 1, 0, 0, 3, 1, 0])
        self.assertEqual(m.z_function("aaaa"), [4, 3, 2, 1])
        self.assertEqual(m.z_function(""), [])
        self.assertEqual(m.z_function("a"), [1])
        with self.assertRaises(ValueError) as ctx:
            m.z_function("a" * 1001)
        self.assertIn("too_many:s", str(ctx.exception))

    def test_z_function_naive_oracle(self):
        rng = random.Random(35)
        for _ in range(120):
            n = rng.randint(0, 30)
            s = "".join(rng.choice("ab") for _ in range(n))
            want = [0] * n
            for i in range(1, n):
                k = 0
                while i + k < n and s[k] == s[i + k]:
                    k += 1
                want[i] = k
            if n:
                want[0] = n
            self.assertEqual(m.z_function(s), want, s)

    def test_bell_number(self):
        self.assertEqual([m.bell_number(i) for i in range(7)],
                         [1, 1, 2, 5, 15, 52, 203])
        with self.assertRaises(ValueError):
            m.bell_number(True)
        with self.assertRaises(ValueError) as ctx:
            m.bell_number(201)
        self.assertIn("too_many:n", str(ctx.exception))

    def test_bell_stirling_oracle(self):
        # bell(n) equals the row sum of Stirling seconds, computed here
        # from their own recurrence - an independent route
        def stirling2(n, k):
            if n == k == 0:
                return 1
            if n == 0 or k == 0 or k > n:
                return 0
            return k * stirling2(n - 1, k) + stirling2(n - 1, k - 1)

        for n in range(9):
            self.assertEqual(m.bell_number(n),
                             sum(stirling2(n, k) for k in range(n + 1)), n)

    def test_eulerian_number(self):
        self.assertEqual([m.eulerian_number(3, k) for k in range(3)],
                         [1, 4, 1])
        self.assertEqual([m.eulerian_number(4, k) for k in range(4)],
                         [1, 11, 11, 1])
        self.assertEqual(m.eulerian_number(3, 3), 0)
        self.assertEqual(m.eulerian_number(0, 0), 1)

    def test_eulerian_permutation_oracle(self):
        from itertools import permutations
        for n in range(1, 7):
            counts = {}
            for perm in permutations(range(n)):
                desc = sum(1 for i in range(n - 1) if perm[i] > perm[i + 1])
                counts[desc] = counts.get(desc, 0) + 1
            for k, want in counts.items():
                self.assertEqual(m.eulerian_number(n, k), want, (n, k))

    def test_schroder_number(self):
        self.assertEqual([m.schroder_number(i) for i in range(6)],
                         [1, 2, 6, 22, 90, 394])
        with self.assertRaises(ValueError):
            m.schroder_number(-1)

    def test_schroder_linear_recurrence_oracle(self):
        # independent route: (n+1) S(n) = (6n-3) S(n-1) - (n-2) S(n-2)
        s = [1, 2]
        for n in range(2, 15):
            num = (6 * n - 3) * s[-1] - (n - 2) * s[-2]
            self.assertEqual(num % (n + 1), 0)
            s.append(num // (n + 1))
        for n in range(15):
            self.assertEqual(m.schroder_number(n), s[n], n)

    def test_narayana_number(self):
        self.assertEqual([m.narayana_number(3, k) for k in (1, 2, 3)],
                         [1, 3, 1])
        self.assertEqual([m.narayana_number(4, k) for k in (1, 2, 3, 4)],
                         [1, 6, 6, 1])
        with self.assertRaises(ValueError) as ctx:
            m.narayana_number(3, 0)
        self.assertIn("bad_value:k", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.narayana_number(3, 4)
        self.assertIn("bad_value:k", str(ctx.exception))

    def test_narayana_dp_oracle(self):
        # independent route: N(n,k) = N(n-1,k) + N(n-1,k-1)
        #   + sum convolution-free triangle built from its own DP:
        # N(n,k) counts 213-avoiding... use the standard DP:
        # N(n,k) = sum over splits of the Catalan convolution is heavy;
        # instead verify against the peak-counting definition
        from itertools import permutations

        def oracle(n, k):
            # Narayana: Dyck paths of semilength n with exactly k peaks,
            # generated directly with a never-negative balance
            count = 0

            def paths(ups, dns, balance, peaks, last_up):
                nonlocal count
                if ups == n and dns == n:
                    if last_up:
                        peaks += 1
                    if peaks == k:
                        count += 1
                    return
                if ups < n:
                    paths(ups + 1, dns, balance + 1, peaks, True)
                if dns < ups and balance > 0:
                    paths(ups, dns + 1, balance - 1,
                          peaks + (1 if last_up else 0), False)

            paths(0, 0, 0, 0, False)
            return count

        for n in range(1, 6):
            for k in range(1, n + 1):
                self.assertEqual(m.narayana_number(n, k), oracle(n, k),
                                 (n, k))

    def test_tribonacci_term(self):
        self.assertEqual([m.tribonacci_term(i) for i in range(8)],
                         [0, 0, 1, 1, 2, 4, 7, 13])
        with self.assertRaises(ValueError):
            m.tribonacci_term(True)

    def test_pell_number(self):
        self.assertEqual([m.pell_number(i) for i in range(8)],
                         [0, 1, 2, 5, 12, 29, 70, 169])
        with self.assertRaises(ValueError) as ctx:
            m.pell_number(1001)
        self.assertIn("too_many:n", str(ctx.exception))

    def test_recurrences_matrix_oracle(self):
        # independent route for both: 3x3 / 2x2 matrix exponentiation
        def mat_pow(base, e):
            n = len(base)
            out = [[1 if i == j else 0 for j in range(n)]
                   for i in range(n)]
            b = [row[:] for row in base]
            while e:
                if e & 1:
                    out = [[sum(x * y for x, y in zip(r, c))
                            for c in zip(*b)] for r in out]
                b = [[sum(x * y for x, y in zip(r, c))
                      for c in zip(*b)] for r in b]
                e >>= 1
            return out

        for n in (0, 1, 2, 5, 17, 60):
            t = mat_pow([[1, 1, 1], [1, 0, 0], [0, 1, 0]], n)
            got_trib = t[2][0]  # T(n) with T0=0,T1=0,T2=1
            self.assertEqual(m.tribonacci_term(n), got_trib, n)
            p = mat_pow([[2, 1], [1, 0]], n)
            self.assertEqual(m.pell_number(n), p[1][0] * 1 + p[0][0] * 0
                             if False else p[1][0], n)

    def test_longest_common_substring_length(self):
        self.assertEqual(m.longest_common_substring_length("abxc", "abyc"),
                         2)
        self.assertEqual(m.longest_common_substring_length("", "abc"), 0)
        self.assertEqual(m.longest_common_substring_length("aaa", "aa"), 2)
        with self.assertRaises(ValueError):
            m.longest_common_substring_length(5, "a")

    def test_lcs_substring_oracle(self):
        rng = random.Random(8)
        for _ in range(100):
            a = "".join(rng.choice("ab") for _ in range(rng.randint(0, 12)))
            b = "".join(rng.choice("ab") for _ in range(rng.randint(0, 12)))
            subs = {a[i:i + l] for i in range(len(a))
                    for l in range(1, len(a) - i + 1)}
            want = 0
            for i in range(len(b)):
                for l in range(1, len(b) - i + 1):
                    if b[i:i + l] in subs:
                        want = max(want, l)
            self.assertEqual(m.longest_common_substring_length(a, b),
                             want, (a, b))

    def test_zigzag_check(self):
        self.assertTrue(m.zigzag_check([1, 3, 2, 4, 3]))
        self.assertTrue(m.zigzag_check([5, 1, 4, 2, 3]))
        self.assertFalse(m.zigzag_check([1, 2, 3]))
        self.assertFalse(m.zigzag_check([1, 3, 3, 1]))
        self.assertTrue(m.zigzag_check([7]))
        self.assertTrue(m.zigzag_check([]))
        with self.assertRaises(ValueError):
            m.zigzag_check([1, "2", 3])

    def test_zigzag_sign_oracle(self):
        rng = random.Random(12)
        for _ in range(150):
            vals = [rng.randint(-9, 9) for _ in range(rng.randint(0, 12))]
            diffs = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
            want = all(d != 0 for d in diffs) and all(
                (d < 0) != (e < 0) for d, e in zip(diffs, diffs[1:]))
            self.assertEqual(m.zigzag_check(vals), want, vals)

    def test_longest_bitonic_length(self):
        self.assertEqual(m.longest_bitonic_length([1, 3, 2]), 3)
        self.assertEqual(m.longest_bitonic_length([1, 2, 3, 4]), 4)
        self.assertEqual(m.longest_bitonic_length(
            [1, 11, 2, 10, 4, 5, 2, 1]), 6)
        self.assertEqual(m.longest_bitonic_length([]), 0)
        with self.assertRaises(ValueError):
            m.longest_bitonic_length([1, 2.5, 3])

    def test_bitonic_bruteforce_oracle(self):
        from itertools import combinations
        rng = random.Random(4)
        for _ in range(80):
            vals = [rng.randint(0, 9) for _ in range(rng.randint(0, 8))]
            n = len(vals)
            best = 0
            for size in range(1, n + 1):
                for idxs in combinations(range(n), size):
                    seq = [vals[i] for i in idxs]
                    ok = False
                    for peak in range(len(seq) + 1):
                        up = all(seq[i] < seq[i + 1]
                                 for i in range(min(peak, len(seq) - 1)))
                        down = all(seq[i] > seq[i + 1]
                                   for i in range(peak, len(seq) - 1))
                        if up and down:
                            ok = True
                    if ok:
                        best = max(best, size)
            self.assertEqual(m.longest_bitonic_length(vals), best, vals)

    def test_registry_knows_batch35(self):
        from app.modules.instinct_doc import p235_concepts_registry as reg
        names = [e["name"] for e in reg.ENTRIES]
        for name in ("z_function", "bell_number", "eulerian_number",
                     "schroder_number", "narayana_number", "tribonacci_term",
                     "pell_number", "longest_common_substring_length",
                     "zigzag_check", "longest_bitonic_length"):
            self.assertIn(name, names)
        own = [e for e in reg.ENTRIES if e["batch"] == 35]
        self.assertEqual(len(own), 10)
        for name in ("z_function", "bell_number", "eulerian_number",
                     "schroder_number", "narayana_number",
                     "tribonacci_term", "pell_number",
                     "longest_common_substring_length", "zigzag_check",
                     "longest_bitonic_length"):
            self.assertIn(name, [e["name"] for e in own])


if __name__ == "__main__":
    unittest.main()
