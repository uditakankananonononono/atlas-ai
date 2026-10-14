"""Tests for P235 concepts batch 60 (doc 591-600)."""
import random
import unittest
from fractions import Fraction

from app.modules.instinct_doc import p235_concepts_batch60 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class Batch60Test(unittest.TestCase):
    def test_mean_pairwise_abs_diff(self):
        self.assertEqual(m.mean_pairwise_abs_diff([1, 4, 3, 2]),
                         Fraction(5, 3))
        self.assertEqual(m.mean_pairwise_abs_diff([7, 7]), 0)
        # oracle: sorted-spacing identity sum_j (2j - n - 1) * x_j
        rng = random.Random(6001)
        for _ in range(60):
            vals = [rng.randint(-20, 20)
                    for _ in range(rng.randint(2, 9))]
            s = sorted(vals)
            n = len(s)
            total = sum((2 * j - n + 1) * s[j] for j in range(n))
            want = Fraction(total, n * (n - 1) // 2)
            self.assertEqual(m.mean_pairwise_abs_diff(vals), want,
                             vals)
        with self.assertRaises(ValueError):
            m.mean_pairwise_abs_diff([5])

    def test_binomial_probability_exact(self):
        self.assertEqual(m.binomial_probability_exact(
            4, 2, Fraction(1, 2)), Fraction(3, 8))
        self.assertEqual(m.binomial_probability_exact(5, 0, 0), 1)
        self.assertEqual(m.binomial_probability_exact(5, 3, 1), 0)
        # oracle: falling-factorial coefficient times p powers
        rng = random.Random(6002)
        for _ in range(50):
            n = rng.randint(0, 12)
            k = rng.randint(0, n)
            p = Fraction(rng.randint(0, 4), 4)
            coeff = Fraction(1)
            for i in range(k):
                coeff *= (n - i)
                coeff /= (i + 1)
            want = coeff * p ** k * (1 - p) ** (n - k)
            self.assertEqual(m.binomial_probability_exact(n, k, p),
                             want, (n, k, p))
        with self.assertRaises(ValueError):
            m.binomial_probability_exact(2, 3, Fraction(1, 2))
        with self.assertRaises(ValueError):
            m.binomial_probability_exact(2, 1, Fraction(3, 2))
        with self.assertRaises(ValueError):
            m.binomial_probability_exact(2, 1, 0.5)

    def test_standard_score_exact(self):
        self.assertEqual(m.standard_score_exact(5, 1, 2), 2)
        self.assertEqual(
            m.standard_score_exact(Fraction(1, 2), 1,
                                   Fraction(1, 4)), -2)
        # oracle: cross-multiplied comparison against a long division
        rng = random.Random(6003)
        for _ in range(50):
            v = Fraction(rng.randint(-20, 20),
                         rng.randint(1, 5))
            mu = Fraction(rng.randint(-9, 9), rng.randint(1, 4))
            sd = Fraction(rng.randint(1, 9), rng.randint(1, 4))
            want = Fraction(v - mu, sd)
            self.assertEqual(m.standard_score_exact(v, mu, sd),
                             want)
        with self.assertRaises(ValueError):
            m.standard_score_exact(1, 1, 0)
        with self.assertRaises(ValueError):
            m.standard_score_exact(1, 1, True)

    def test_mann_whitney_u(self):
        self.assertEqual(m.mann_whitney_u([1, 3], [2]), 1)
        self.assertEqual(m.mann_whitney_u([1], [1]), Fraction(1, 2))
        self.assertEqual(m.mann_whitney_u([5, 6], [1, 2]), 4)
        # oracle: rank-sum identity U = n1*n2 + n1(n1+1)/2 - R1
        rng = random.Random(6004)
        for _ in range(50):
            xs = [rng.randint(0, 6)
                  for _ in range(rng.randint(1, 6))]
            ys = [rng.randint(0, 6)
                  for _ in range(rng.randint(1, 6))]
            combined = sorted(xs + ys)
            ranks = {}
            i = 0
            while i < len(combined):
                j = i
                while j < len(combined) and combined[j] == combined[i]:
                    j += 1
                ranks[combined[i]] = Fraction(i + 1 + j, 2)
                i = j
            r1 = sum(ranks[x] for x in xs)
            n1 = len(xs)
            want = r1 - Fraction(n1 * (n1 + 1), 2)
            self.assertEqual(m.mann_whitney_u(xs, ys), want, (xs, ys))
        with self.assertRaises(ValueError):
            m.mann_whitney_u([], [1])

    def test_runs_count(self):
        self.assertEqual(m.runs_count([1, -2, 3, 0, 4]), 5)
        self.assertEqual(m.runs_count([1, 2, 3]), 1)
        self.assertEqual(m.runs_count([0, 0]), 1)
        # oracle: one plus the number of sign changes
        rng = random.Random(6005)
        for _ in range(60):
            vals = [rng.randint(-4, 4)
                    for _ in range(rng.randint(1, 12))]
            signs = [(v > 0) - (v < 0) for v in vals]
            want = 1 + sum(1 for i in range(1, len(signs))
                           if signs[i] != signs[i - 1])
            self.assertEqual(m.runs_count(vals), want, vals)
        with self.assertRaises(ValueError):
            m.runs_count([])

    def test_matrix_row_sums(self):
        self.assertEqual(m.matrix_row_sums([[1, 2], [3, 4]]), [3, 7])
        # oracle: reduce per row
        rng = random.Random(6006)
        for _ in range(50):
            rows = rng.randint(1, 4)
            cols = rng.randint(1, 4)
            mat = [[rng.randint(-9, 9) for _ in range(cols)]
                   for _ in range(rows)]
            want = [sum(row) for row in mat]
            self.assertEqual(m.matrix_row_sums(mat), want)
        with self.assertRaises(ValueError):
            m.matrix_row_sums([[1], [2, 3]])
        with self.assertRaises(ValueError):
            m.matrix_row_sums([[True]])

    def test_chi_square_statistic_exact(self):
        self.assertEqual(m.chi_square_statistic_exact([1, 2], [2, 4]),
                         Fraction(3, 2))
        self.assertEqual(m.chi_square_statistic_exact([3, 3], [3, 3]),
                         0)
        # oracle: expand (o-e)^2/e term by term with Fractions
        rng = random.Random(6007)
        for _ in range(50):
            n = rng.randint(1, 6)
            obs = [rng.randint(0, 9) for _ in range(n)]
            exp = [rng.randint(1, 9) for _ in range(n)]
            want = sum(Fraction((o - e) * (o - e), e)
                       for o, e in zip(obs, exp))
            self.assertEqual(
                m.chi_square_statistic_exact(obs, exp), want)
        with self.assertRaises(ValueError):
            m.chi_square_statistic_exact([1, 2], [1])
        with self.assertRaises(ValueError):
            m.chi_square_statistic_exact([1], [0])
        with self.assertRaises(ValueError):
            m.chi_square_statistic_exact([-1], [2])

    def test_third_central_moment_exact(self):
        self.assertEqual(m.third_central_moment_exact([1, 2, 4]),
                         Fraction(20, 27))
        self.assertEqual(m.third_central_moment_exact([2, 2]), 0)
        # oracle: moment identity m3 = E[x^3] - 3 E[x] E[x^2] + 2 E[x]^3
        rng = random.Random(6008)
        for _ in range(50):
            vals = [rng.randint(-6, 6)
                    for _ in range(rng.randint(1, 8))]
            n = len(vals)
            e1 = Fraction(sum(vals), n)
            e2 = Fraction(sum(v * v for v in vals), n)
            e3 = Fraction(sum(v ** 3 for v in vals), n)
            want = e3 - 3 * e1 * e2 + 2 * e1 ** 3
            self.assertEqual(m.third_central_moment_exact(vals),
                             want, vals)
        with self.assertRaises(ValueError):
            m.third_central_moment_exact([1.5, 2])

    def test_mean_of_squares_exact(self):
        self.assertEqual(m.mean_of_squares_exact([1, 2, 3]),
                         Fraction(14, 3))
        self.assertEqual(m.mean_of_squares_exact([-2, 2]), 4)
        # oracle: incremental average of squares
        rng = random.Random(6009)
        for _ in range(50):
            vals = [rng.randint(-9, 9)
                    for _ in range(rng.randint(1, 8))]
            total = Fraction(0)
            for v in vals:
                total += v * v
            want = total / len(vals)
            self.assertEqual(m.mean_of_squares_exact(vals), want,
                             vals)
        with self.assertRaises(ValueError):
            m.mean_of_squares_exact([])

    def test_min_max_normalize_exact(self):
        self.assertEqual(m.min_max_normalize_exact([3, 1, 2]),
                         [1, 0, Fraction(1, 2)])
        # oracle: rank-free recompute via sorted endpoints
        rng = random.Random(6010)
        for _ in range(50):
            vals = [rng.randint(0, 12)
                    for _ in range(rng.randint(2, 9))]
            if len(set(vals)) == 1:
                continue
            lo = sorted(vals)[0]
            hi = sorted(vals)[-1]
            want = [Fraction(v - lo, hi - lo) for v in vals]
            self.assertEqual(m.min_max_normalize_exact(vals), want,
                             vals)
        with self.assertRaises(ValueError):
            m.min_max_normalize_exact([4, 4, 4])
        with self.assertRaises(ValueError):
            m.min_max_normalize_exact([1, "a"])

    def test_registry_knows_batch60(self):
        names = [e["name"] for e in reg.ENTRIES if e["batch"] == 60]
        self.assertEqual(len(names), 10)
        for name in ("mean_pairwise_abs_diff",
                     "binomial_probability_exact",
                     "standard_score_exact", "mann_whitney_u",
                     "runs_count", "matrix_row_sums",
                     "chi_square_statistic_exact",
                     "third_central_moment_exact",
                     "mean_of_squares_exact",
                     "min_max_normalize_exact"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
