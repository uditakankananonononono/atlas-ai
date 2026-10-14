"""Tests for P235 concepts batch 61 (doc 601-610)."""
import random
import unittest

from app.modules.instinct_doc import p235_concepts_batch61 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class Batch61Test(unittest.TestCase):
    def test_min_time_visiting_points(self):
        self.assertEqual(
            m.min_time_visiting_points([[1, 1], [3, 4], [-1, 0]]),
            7)
        self.assertEqual(m.min_time_visiting_points([[0, 0], [1, 0]]),
                         1)
        # oracle: per-leg Chebyshev via diagonal-then-straight split
        rng = random.Random(6101)
        for _ in range(50):
            pts = [[rng.randint(-20, 20), rng.randint(-20, 20)]
                   for _ in range(rng.randint(2, 8))]
            want = 0
            for i in range(1, len(pts)):
                dx = abs(pts[i][0] - pts[i - 1][0])
                dy = abs(pts[i][1] - pts[i - 1][1])
                want += min(dx, dy) + abs(dx - dy)
            self.assertEqual(m.min_time_visiting_points(pts),
                             want, pts)
        # coordinate cap: at the cap accepted, past it refused
        cap = m.MAX_COORD
        self.assertEqual(
            m.min_time_visiting_points([[0, 0], [cap, 0]]), cap)
        with self.assertRaises(ValueError) as ctx:
            m.min_time_visiting_points([[0, 0], [cap + 1, 0]])
        self.assertIn("out_of_range:points[1]", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.min_time_visiting_points([[0, 0]])
        with self.assertRaises(ValueError):
            m.min_time_visiting_points([[0, 0], [1, True]])

    def test_lucas_term(self):
        self.assertEqual([m.lucas_term(i) for i in range(7)],
                         [2, 1, 3, 4, 7, 11, 18])
        # oracle: L(n) = F(n-1) + F(n+1) from an independent fib walk
        rng = random.Random(6102)
        for _ in range(20):
            n = rng.randint(1, 60)
            x, y = 0, 1
            for _ in range(n + 1):
                x, y = y, x + y
            f_n1 = y
            f_nm1 = x if n > 0 else 1
            want = f_nm1 + f_n1 if n >= 1 else 2
            if n == 1:
                want = 1
            else:
                a, b = 0, 1
                for _ in range(n - 1):
                    a, b = b, a + b
                f_nm1 = a
                a, b = 0, 1
                for _ in range(n + 1):
                    a, b = b, a + b
                want = f_nm1 + a
            self.assertEqual(m.lucas_term(n), want, n)
        with self.assertRaises(ValueError):
            m.lucas_term(m.MAX_N + 1)

    def test_integer_break_max_product(self):
        self.assertEqual(m.integer_break_max_product(2), 1)
        self.assertEqual(m.integer_break_max_product(10), 36)
        self.assertEqual(m.integer_break_max_product(8), 18)
        # oracle: exhaustive first-cut recursion with memo by hand
        from functools import lru_cache

        @lru_cache(maxsize=None)
        def best(total):
            top = 0
            for cut in range(1, total):
                top = max(top, cut * (total - cut),
                          cut * best(total - cut))
            return top

        rng = random.Random(6103)
        for _ in range(15):
            n = rng.randint(2, 40)
            self.assertEqual(m.integer_break_max_product(n),
                             best(n), n)
        with self.assertRaises(ValueError):
            m.integer_break_max_product(1)

    def test_move_zeros_to_end(self):
        self.assertEqual(m.move_zeros_to_end([0, 1, 0, 3, 12]),
                         [1, 3, 12, 0, 0])
        self.assertEqual(m.move_zeros_to_end([0, 0]), [0, 0])
        # oracle: two-queue split rebuilt per element
        rng = random.Random(6104)
        for _ in range(60):
            vals = [rng.randint(0, 3)
                    for _ in range(rng.randint(1, 12))]
            front = []
            back = []
            for v in vals:
                (back if v == 0 else front).append(v)
            self.assertEqual(m.move_zeros_to_end(vals),
                             front + back, vals)
        with self.assertRaises(ValueError):
            m.move_zeros_to_end([0, "x"])

    def test_dutch_flag_partition(self):
        self.assertEqual(m.dutch_flag_partition([2, 0, 2, 1, 1, 0]),
                         [0, 0, 1, 1, 2, 2])
        # oracle: full sort
        rng = random.Random(6105)
        for _ in range(60):
            vals = [rng.randint(0, 2)
                    for _ in range(rng.randint(1, 15))]
            self.assertEqual(m.dutch_flag_partition(vals),
                             sorted(vals), vals)
        # whole-input validation: bad value late in the list refuses
        with self.assertRaises(ValueError) as ctx:
            m.dutch_flag_partition([2, 0, 1, 3])
        self.assertIn("bad_value:items[3]", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.dutch_flag_partition([True])
        with self.assertRaises(ValueError):
            m.dutch_flag_partition([-1])

    def test_max_consecutive_ones(self):
        self.assertEqual(m.max_consecutive_ones([1, 1, 0, 1, 1, 1]),
                         3)
        self.assertEqual(m.max_consecutive_ones([0, 0]), 0)
        # oracle: split on zeros and measure the parts
        rng = random.Random(6106)
        for _ in range(60):
            vals = [rng.randint(0, 1)
                    for _ in range(rng.randint(1, 15))]
            want = max((len(part) for part in
                        "".join(map(str, vals)).split("0")),
                       default=0)
            self.assertEqual(m.max_consecutive_ones(vals), want,
                             vals)
        with self.assertRaises(ValueError) as ctx:
            m.max_consecutive_ones([1, 1, 2, 1])
        self.assertIn("bad_value:items[2]", str(ctx.exception))

    def test_island_perimeter(self):
        self.assertEqual(m.island_perimeter(
            [[0, 1, 0, 0], [1, 1, 1, 0],
             [0, 1, 0, 0], [1, 1, 0, 0]]), 16)
        self.assertEqual(m.island_perimeter([[1]]), 4)
        self.assertEqual(m.island_perimeter([[0]]), 0)
        # oracle: 4 * land - 2 * shared edges, edges counted apart
        rng = random.Random(6107)
        for _ in range(50):
            rows = rng.randint(1, 5)
            cols = rng.randint(1, 5)
            grid = [[rng.randint(0, 1) for _ in range(cols)]
                    for _ in range(rows)]
            land = sum(sum(row) for row in grid)
            shared = 0
            for i in range(rows):
                for j in range(cols):
                    if grid[i][j] != 1:
                        continue
                    if i + 1 < rows and grid[i + 1][j] == 1:
                        shared += 1
                    if j + 1 < cols and grid[i][j + 1] == 1:
                        shared += 1
            self.assertEqual(m.island_perimeter(grid),
                             4 * land - 2 * shared, grid)
        with self.assertRaises(ValueError) as ctx:
            m.island_perimeter([[1, 0], [0, 2]])
        self.assertIn("bad_value:grid[1][1]", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.island_perimeter([[1], [0, 1]])

    def test_matrix_search_sorted(self):
        mat = [[1, 4, 7, 11], [2, 5, 8, 12],
               [3, 6, 9, 16], [10, 13, 14, 17]]
        self.assertTrue(m.matrix_search_sorted(mat, 5))
        self.assertFalse(m.matrix_search_sorted(mat, 15))
        # oracle: brute membership scan
        rng = random.Random(6108)
        for _ in range(50):
            rows = rng.randint(1, 4)
            cols = rng.randint(1, 4)
            base = sorted(rng.randint(-20, 40)
                          for _ in range(rows * cols))
            grid = [base[i * cols:(i + 1) * cols]
                    for i in range(rows)]
            # guarantee column order by construction
            grid = [[grid[r][c] for c in range(cols)]
                    for r in range(rows)]
            grid = [list(row) for row in zip(*sorted(zip(*grid)))]
            target = rng.randint(-20, 40)
            want = any(target in row for row in grid)
            self.assertEqual(m.matrix_search_sorted(grid, target),
                             want, (grid, target))
        # unsorted contract refuses before any search verdict
        with self.assertRaises(ValueError) as ctx:
            m.matrix_search_sorted([[2, 1], [3, 4]], 4)
        self.assertIn("not_sorted", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.matrix_search_sorted([[1, 2], [0, 4]], 4)

    def test_total_hamming_distance(self):
        self.assertEqual(m.total_hamming_distance([4, 14, 2]), 6)
        self.assertEqual(m.total_hamming_distance([7, 7]), 0)
        # oracle: pairwise popcount of xors
        rng = random.Random(6109)
        for _ in range(40):
            vals = [rng.randint(0, 2 ** 12)
                    for _ in range(rng.randint(1, 8))]
            want = 0
            for i in range(len(vals)):
                for j in range(i + 1, len(vals)):
                    want += bin(vals[i] ^ vals[j]).count("1")
            self.assertEqual(m.total_hamming_distance(vals), want,
                             vals)
        with self.assertRaises(ValueError):
            m.total_hamming_distance([1, -2])
        with self.assertRaises(ValueError) as ctx:
            m.total_hamming_distance([1 << m.MAX_BITS])
        self.assertIn("too_big:items[0]", str(ctx.exception))

    def test_summary_ranges(self):
        self.assertEqual(m.summary_ranges([0, 1, 2, 4, 5, 7]),
                         ["0->2", "4->5", "7"])
        self.assertEqual(m.summary_ranges([]), [])
        self.assertEqual(m.summary_ranges([3]), ["3"])
        # oracle: rebuild ranges by walk, render independently
        rng = random.Random(6110)
        for _ in range(60):
            start = rng.randint(-10, 10)
            vals = sorted(set(start + rng.randint(0, 30)
                              for _ in range(rng.randint(0, 10))))
            want = []
            k = 0
            while k < len(vals):
                lo = vals[k]
                hi = lo
                k += 1
                while k < len(vals) and vals[k] == hi + 1:
                    hi = vals[k]
                    k += 1
                want.append(str(lo) if lo == hi
                            else str(lo) + "->" + str(hi))
            self.assertEqual(m.summary_ranges(vals), want, vals)
        with self.assertRaises(ValueError) as ctx:
            m.summary_ranges([1, 3, 2])
        self.assertIn("not_sorted:items[2]", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.summary_ranges([2, 2])

    def test_registry_knows_batch61(self):
        names = [e["name"] for e in reg.ENTRIES if e["batch"] == 61]
        self.assertEqual(len(names), 10)
        for name in ("min_time_visiting_points", "lucas_term",
                     "integer_break_max_product",
                     "move_zeros_to_end", "dutch_flag_partition",
                     "max_consecutive_ones", "island_perimeter",
                     "matrix_search_sorted", "total_hamming_distance",
                     "summary_ranges"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
