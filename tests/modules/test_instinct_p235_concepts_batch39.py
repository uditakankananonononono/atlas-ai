"""Tests for P235 concepts batch 39 (381-390)."""
import random
import unittest
from collections import deque

from app.modules.instinct_doc import p235_concepts_batch39 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class Batch39Test(unittest.TestCase):
    def test_count_islands(self):
        self.assertEqual(m.count_islands([[1, 1, 0], [0, 0, 1], [1, 0, 1]]), 3)
        self.assertEqual(m.count_islands([[0]]), 0)
        self.assertEqual(m.count_islands([[1, 1], [1, 1]]), 1)
        # oracle: union-find built independently of the DFS under test
        rng = random.Random(3901)
        for _ in range(40):
            h = rng.randint(1, 8)
            w = rng.randint(1, 8)
            grid = [[rng.randint(0, 1) for _ in range(w)] for _ in range(h)]
            parent = {}

            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            for r in range(h):
                for c in range(w):
                    if grid[r][c] == 1:
                        parent[(r, c)] = (r, c)
            for r in range(h):
                for c in range(w):
                    if grid[r][c] == 1:
                        for dr, dc in ((1, 0), (0, 1)):
                            nr, nc = r + dr, c + dc
                            if (nr < h and nc < w
                                    and grid[nr][nc] == 1):
                                parent[find((r, c))] = find((nr, nc))
            want = len({find(p) for p in parent})
            self.assertEqual(m.count_islands(grid), want, grid)
        with self.assertRaises(ValueError):
            m.count_islands([[1, 2]])  # only 0/1 allowed
        with self.assertRaises(ValueError):
            m.count_islands([[1], [1, 0]])  # ragged
        with self.assertRaises(ValueError):
            m.count_islands([])

    def test_flood_fill_region_size(self):
        grid = [[1, 1, 0], [1, 0, 1], [0, 0, 1]]
        self.assertEqual(m.flood_fill_region_size(grid, 0, 0), 3)
        self.assertEqual(m.flood_fill_region_size(grid, 0, 2), 1)
        self.assertEqual(m.flood_fill_region_size(grid, 1, 1), 3)
        self.assertEqual(m.flood_fill_region_size([[7]], 0, 0), 1)
        # oracle: BFS with deque, a different traversal than the module
        rng = random.Random(3902)
        for _ in range(40):
            h = rng.randint(1, 7)
            w = rng.randint(1, 7)
            grid = [[rng.randint(0, 3) for _ in range(w)]
                    for _ in range(h)]
            sr, sc = rng.randrange(h), rng.randrange(w)
            target = grid[sr][sc]
            seen = {(sr, sc)}
            q = deque([(sr, sc)])
            while q:
                r, c = q.popleft()
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = r + dr, c + dc
                    if (0 <= nr < h and 0 <= nc < w
                            and grid[nr][nc] == target
                            and (nr, nc) not in seen):
                        seen.add((nr, nc))
                        q.append((nr, nc))
            self.assertEqual(
                m.flood_fill_region_size(grid, sr, sc), len(seen), grid)
        with self.assertRaises(ValueError):
            m.flood_fill_region_size([[1]], 1, 0)
        with self.assertRaises(ValueError):
            m.flood_fill_region_size([[1]], 0, -1)

    def test_jump_game_min_jumps(self):
        self.assertEqual(m.jump_game_min_jumps([2, 3, 1, 1, 4]), 2)
        self.assertEqual(m.jump_game_min_jumps([0]), 0)
        self.assertEqual(m.jump_game_min_jumps([3, 0, 0, 0]), 1)
        # oracle: O(n^2) DP, independent of the greedy scan
        rng = random.Random(3903)
        inf = float("inf")
        for _ in range(80):
            n = rng.randint(1, 12)
            steps = [rng.randint(0, 5) for _ in range(n)]
            dp = [inf] * n
            dp[0] = 0
            for i in range(n):
                if dp[i] == inf:
                    continue
                for j in range(i + 1, min(n, i + steps[i] + 1)):
                    dp[j] = min(dp[j], dp[i] + 1)
            if dp[-1] == inf:
                with self.assertRaises(ValueError, msg=steps):
                    m.jump_game_min_jumps(steps)
            else:
                self.assertEqual(m.jump_game_min_jumps(steps), dp[-1],
                                 steps)
        with self.assertRaises(ValueError):
            m.jump_game_min_jumps([1, 0, 1])
        with self.assertRaises(ValueError):
            m.jump_game_min_jumps([-1])
        with self.assertRaises(ValueError):
            m.jump_game_min_jumps([])

    def test_egg_drop_min_trials(self):
        self.assertEqual(m.egg_drop_min_trials(1, 10), 10)
        self.assertEqual(m.egg_drop_min_trials(2, 100), 14)
        self.assertEqual(m.egg_drop_min_trials(2, 6), 3)
        self.assertEqual(m.egg_drop_min_trials(5, 0), 0)
        # oracle: direct minimax DP on small instances
        def reference(eggs, floors):
            tab = [[0] * (floors + 1) for _ in range(eggs + 1)]
            for f in range(1, floors + 1):
                tab[1][f] = f
            for e in range(2, eggs + 1):
                for f in range(1, floors + 1):
                    tab[e][f] = 1 + min(
                        max(tab[e - 1][x - 1], tab[e][f - x])
                        for x in range(1, f + 1))
            return tab[eggs][floors]

        for e in range(1, 5):
            for f in range(0, 25):
                self.assertEqual(m.egg_drop_min_trials(e, f),
                                 reference(e, f), (e, f))
        with self.assertRaises(ValueError):
            m.egg_drop_min_trials(0, 5)
        with self.assertRaises(ValueError):
            m.egg_drop_min_trials(1, -1)

    def test_max_subarray_product(self):
        self.assertEqual(m.max_subarray_product([2, 3, -2, 4]), 6)
        self.assertEqual(m.max_subarray_product([-2, 0, -1]), 0)
        self.assertEqual(m.max_subarray_product([-3]), -3)
        # oracle: brute force over every contiguous subarray
        rng = random.Random(3905)
        for _ in range(60):
            n = rng.randint(1, 10)
            vals = [rng.randint(-4, 4) for _ in range(n)]
            want = max(
                __import__("math").prod(vals[i:j])
                for i in range(n) for j in range(i + 1, n + 1))
            self.assertEqual(m.max_subarray_product(vals), want, vals)
        with self.assertRaises(ValueError):
            m.max_subarray_product([])
        with self.assertRaises(ValueError):
            m.max_subarray_product([True, 2])

    def test_nth_ugly_number(self):
        first10 = [1, 2, 3, 4, 5, 6, 8, 9, 10, 12]
        for i, want in enumerate(first10, start=1):
            self.assertEqual(m.nth_ugly_number(i), want)
        # oracle: sequential scan with trial division
        def is_ugly(x):
            for p in (2, 3, 5):
                while x % p == 0:
                    x //= p
            return x == 1

        count = 0
        x = 0
        seq = []
        while count < 150:
            x += 1
            if is_ugly(x):
                count += 1
                seq.append(x)
        for n in (1, 7, 50, 100, 150):
            self.assertEqual(m.nth_ugly_number(n), seq[n - 1])
        with self.assertRaises(ValueError):
            m.nth_ugly_number(0)
        with self.assertRaises(ValueError):
            m.nth_ugly_number(m.MAX_NTH + 1)

    def test_peak_index_bitonic(self):
        self.assertEqual(m.peak_index_bitonic([1, 3, 8, 12, 4, 2]), 3)
        self.assertEqual(m.peak_index_bitonic([1, 2, 1]), 1)
        self.assertEqual(m.peak_index_bitonic([5, 9, 7]), 1)
        # property: result is the argmax of a strictly bitonic list
        rng = random.Random(3907)
        for _ in range(40):
            n = rng.randint(3, 15)
            peak = rng.randint(1, n - 2)
            up = sorted(random.Random(rng.random()).sample(
                range(10, 200), peak + 1))
            down = sorted(random.Random(rng.random()).sample(
                range(0, up[-1]), n - peak - 1), reverse=True)
            vals = up + down
            got = m.peak_index_bitonic(vals)
            self.assertEqual(vals[got], max(vals), vals)
            self.assertEqual(got, vals.index(max(vals)), vals)
        for bad in ([1, 2], [1, 2, 3], [3, 2, 1], [1, 1, 2],
                    [0, 1, 3, 2, 4], [1, 3, 2, 4, 1]):
            with self.assertRaises(ValueError, msg=bad):
                m.peak_index_bitonic(bad)

    def test_peak_index_bitonic_exhaustive_oracle(self):
        # every sequence over {1..4} of length 3..5: strict up-then-down
        from itertools import product

        def shape_ok(vals):
            n = len(vals)
            i = 0
            while i + 1 < n and vals[i] < vals[i + 1]:
                i += 1
            if i == 0 or i == n - 1:
                return None
            peak = i
            while i + 1 < n and vals[i] > vals[i + 1]:
                i += 1
            return peak if i == n - 1 else None

        for n in (3, 4, 5):
            for vals in product(range(1, 5), repeat=n):
                want = shape_ok(list(vals))
                if want is None:
                    with self.assertRaises(ValueError, msg=vals):
                        m.peak_index_bitonic(list(vals))
                else:
                    self.assertEqual(m.peak_index_bitonic(list(vals)),
                                     want, vals)

    def test_pivot_index_sum(self):
        self.assertEqual(m.pivot_index_sum([1, 7, 3, 6, 5, 6]), 3)
        self.assertEqual(m.pivot_index_sum([1, 2, 3]), -1)
        self.assertEqual(m.pivot_index_sum([2, 1, -1]), 0)
        self.assertEqual(m.pivot_index_sum([-1, -1, 0, 1, 1, 0]), 5)
        # oracle: brute prefix comparison, leftmost index
        rng = random.Random(3908)
        for _ in range(60):
            n = rng.randint(1, 12)
            vals = [rng.randint(-9, 9) for _ in range(n)]
            want = -1
            for i in range(n):
                if sum(vals[:i]) == sum(vals[i + 1:]):
                    want = i
                    break
            self.assertEqual(m.pivot_index_sum(vals), want, vals)
        with self.assertRaises(ValueError):
            m.pivot_index_sum([])

    def test_container_max_water(self):
        self.assertEqual(m.container_max_water([1, 8, 6, 2, 5, 4, 8, 3, 7]),
                         49)
        self.assertEqual(m.container_max_water([1, 1]), 1)
        self.assertEqual(m.container_max_water([4, 3, 2, 1, 4]), 16)
        # oracle: O(n^2) over all pairs
        rng = random.Random(3909)
        for _ in range(50):
            n = rng.randint(2, 12)
            vals = [rng.randint(0, 20) for _ in range(n)]
            want = max((j - i) * min(vals[i], vals[j])
                       for i in range(n) for j in range(i + 1, n))
            self.assertEqual(m.container_max_water(vals), want, vals)
        with self.assertRaises(ValueError):
            m.container_max_water([5])
        with self.assertRaises(ValueError):
            m.container_max_water([1, -1])

    def test_stock_max_profit_once(self):
        self.assertEqual(m.stock_max_profit_once([7, 1, 5, 3, 6, 4]), 5)
        self.assertEqual(m.stock_max_profit_once([7, 6, 4, 3, 1]), 0)
        self.assertEqual(m.stock_max_profit_once([2]), 0)
        # oracle: brute over buy/sell day pairs
        rng = random.Random(3910)
        for _ in range(60):
            n = rng.randint(1, 12)
            vals = [rng.randint(0, 30) for _ in range(n)]
            want = max([0] + [vals[j] - vals[i]
                              for i in range(n)
                              for j in range(i + 1, n)])
            self.assertEqual(m.stock_max_profit_once(vals), want, vals)
        with self.assertRaises(ValueError):
            m.stock_max_profit_once([])
        with self.assertRaises(ValueError):
            m.stock_max_profit_once([1, -2])

    def test_registry_knows_batch39(self):
        names = [e["name"] for e in reg.ENTRIES if e["batch"] == 39]
        self.assertEqual(len(names), 10)
        for name in ("count_islands", "flood_fill_region_size",
                     "jump_game_min_jumps", "egg_drop_min_trials",
                     "max_subarray_product", "nth_ugly_number",
                     "peak_index_bitonic", "pivot_index_sum",
                     "container_max_water", "stock_max_profit_once"):
            self.assertIn(name, names)

    def test_caps(self):
        with self.assertRaises(ValueError):
            m.jump_game_min_jumps([1] * (m.MAX_STEPS + 1))
        m.jump_game_min_jumps([1] * m.MAX_STEPS)
        with self.assertRaises(ValueError):
            m.stock_max_profit_once([0] * (m.MAX_PRICES + 1))
        m.stock_max_profit_once([0] * m.MAX_PRICES)


if __name__ == "__main__":
    unittest.main()
