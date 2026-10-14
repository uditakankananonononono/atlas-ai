"""Tests for P235 concepts batch 67 (doc 661-670)."""
import random
import unittest
from collections import deque

from app.modules.instinct_doc import p235_concepts_batch67 as m
from app.modules.instinct_doc import p235_concepts_registry as reg
from app.modules.instinct_doc.p235_concepts_batch11 import (
    spiral_matrix_order)


def _rand_grid(rng, r, c, ones=0.5):
    return [[1 if rng.random() < ones else 0 for _ in range(c)]
            for _ in range(r)]


class Batch67Test(unittest.TestCase):
    def test_shortest_path_binary_matrix(self):
        self.assertEqual(m.shortest_path_binary_matrix(
            [[0, 0, 0], [1, 1, 0], [1, 1, 0]]), 4)
        self.assertEqual(m.shortest_path_binary_matrix(
            [[0, 1], [1, 0]]), 2)
        self.assertEqual(m.shortest_path_binary_matrix(
            [[1, 0], [0, 0]]), -1)
        self.assertEqual(m.shortest_path_binary_matrix([[0]]), 1)
        self.assertEqual(m.shortest_path_binary_matrix(
            [[0, 0], [1, 1]]), -1)
        # oracle: Dijkstra-style expansion with a distance map
        rng = random.Random(6701)
        for _ in range(80):
            n = rng.randint(1, 6)
            grid = _rand_grid(rng, n, n, 0.65)
            dist = {(0, 0): 1} if grid[0][0] == 0 else {}
            q = deque(dist)
            while q:
                r, c = q.popleft()
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        nr, nc = r + dr, c + dc
                        if (0 <= nr < n and 0 <= nc < n
                                and grid[nr][nc] == 0
                                and (nr, nc) not in dist):
                            dist[(nr, nc)] = dist[(r, c)] + 1
                            q.append((nr, nc))
            want = dist.get((n - 1, n - 1), -1)
            self.assertEqual(m.shortest_path_binary_matrix(grid),
                             want, grid)
        with self.assertRaises(ValueError):
            m.shortest_path_binary_matrix([[0, 0, 0], [0, 0, 0]])
        with self.assertRaises(ValueError):
            m.shortest_path_binary_matrix([[0, 2], [0, 0]])

    def test_number_of_enclaves(self):
        self.assertEqual(m.number_of_enclaves(
            [[1, 1, 1], [1, 1, 1], [1, 1, 1]]), 0)
        self.assertEqual(m.number_of_enclaves(
            [[0, 0, 0, 0], [1, 0, 1, 0], [0, 1, 1, 0],
             [0, 0, 0, 0]]), 3)
        # oracle: DFS flood from the boundary, then count leftovers
        rng = random.Random(6702)
        for _ in range(60):
            rows = rng.randint(1, 6)
            cols = rng.randint(1, 6)
            grid = _rand_grid(rng, rows, cols)
            seen = set()

            def dfs(r, c):
                if (not (0 <= r < rows and 0 <= c < cols)
                        or grid[r][c] == 0 or (r, c) in seen):
                    return
                seen.add((r, c))
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    dfs(r + dr, c + dc)
            for r in range(rows):
                for c in (0, cols - 1):
                    dfs(r, c)
            for c in range(cols):
                for r in (0, rows - 1):
                    dfs(r, c)
            want = sum(1 for r in range(rows) for c in range(cols)
                       if grid[r][c] == 1 and (r, c) not in seen)
            self.assertEqual(m.number_of_enclaves(grid), want, grid)
        with self.assertRaises(ValueError):
            m.number_of_enclaves([[1, 2]])

    def test_matrix_nearest_zero_distance(self):
        self.assertEqual(m.matrix_nearest_zero_distance(
            [[0, 1], [1, 1]]), [[0, 1], [1, 2]])
        self.assertEqual(m.matrix_nearest_zero_distance(
            [[0, 0, 0], [0, 1, 0], [1, 1, 1]]),
            [[0, 0, 0], [0, 1, 0], [1, 2, 1]])
        # oracle: per-cell BFS from scratch
        rng = random.Random(6703)
        for _ in range(40):
            rows = rng.randint(1, 5)
            cols = rng.randint(1, 5)
            grid = _rand_grid(rng, rows, cols, 0.7)
            grid[rng.randrange(rows)][rng.randrange(cols)] = 0
            want = []
            for r in range(rows):
                line = []
                for c in range(cols):
                    seen = {(r, c)}
                    q = deque([(r, c, 0)])
                    d = None
                    while q:
                        x, y, dd = q.popleft()
                        if grid[x][y] == 0:
                            d = dd
                            break
                        for dx, dy in ((1, 0), (-1, 0), (0, 1),
                                       (0, -1)):
                            nx, ny = x + dx, y + dy
                            if (0 <= nx < rows and 0 <= ny < cols
                                    and (nx, ny) not in seen):
                                seen.add((nx, ny))
                                q.append((nx, ny, dd + 1))
                    line.append(d)
                want.append(line)
            self.assertEqual(m.matrix_nearest_zero_distance(grid),
                             want, grid)
        with self.assertRaises(ValueError):
            m.matrix_nearest_zero_distance([[1, 1], [1, 1]])

    def test_pacific_atlantic_cells(self):
        self.assertEqual(m.pacific_atlantic_cells([[1, 2], [2, 1]]),
                         [[0, 1], [1, 0]])
        self.assertEqual(m.pacific_atlantic_cells([[1]]), [[0, 0]])
        # oracle: per-cell forward-flow DFS to both edge sets
        rng = random.Random(6704)
        for _ in range(40):
            rows = rng.randint(1, 5)
            cols = rng.randint(1, 5)
            h = [[rng.randint(0, 9) for _ in range(cols)]
                 for _ in range(rows)]

            def flows(r, c):
                seen = {(r, c)}
                stack = [(r, c)]
                pac = atl = False
                while stack:
                    x, y = stack.pop()
                    if x == 0 or y == 0:
                        pac = True
                    if x == rows - 1 or y == cols - 1:
                        atl = True
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = x + dx, y + dy
                        if (0 <= nx < rows and 0 <= ny < cols
                                and h[nx][ny] <= h[x][y]
                                and (nx, ny) not in seen):
                            seen.add((nx, ny))
                            stack.append((nx, ny))
                return pac and atl
            want = sorted([[r, c] for r in range(rows)
                           for c in range(cols) if flows(r, c)])
            self.assertEqual(m.pacific_atlantic_cells(h), want, h)
        with self.assertRaises(ValueError):
            m.pacific_atlantic_cells([[1, -2]])

    def test_spiral_matrix_generate(self):
        self.assertEqual(m.spiral_matrix_generate(3),
                         [[1, 2, 3], [8, 9, 4], [7, 6, 5]])
        self.assertEqual(m.spiral_matrix_generate(1), [[1]])
        self.assertEqual(m.spiral_matrix_generate(2),
                         [[1, 2], [4, 3]])
        # round-trip property: reading the spiral back is 1..n*n
        for n in range(1, 12):
            self.assertEqual(
                spiral_matrix_order(m.spiral_matrix_generate(n)),
                list(range(1, n * n + 1)), n)
        # oracle: ring-by-ring fill
        for n in (4, 5, 7):
            out = [[0] * n for _ in range(n)]
            v = 1
            for ring in range((n + 1) // 2):
                lo, hi = ring, n - 1 - ring
                for c in range(lo, hi + 1):
                    out[lo][c] = v
                    v += 1
                for r in range(lo + 1, hi + 1):
                    out[r][hi] = v
                    v += 1
                for c in range(hi - 1, lo - 1, -1):
                    if hi > lo:
                        out[hi][c] = v
                        v += 1
                for r in range(hi - 1, lo, -1):
                    if hi > lo:
                        out[r][lo] = v
                        v += 1
            self.assertEqual(m.spiral_matrix_generate(n), out, n)
        with self.assertRaises(ValueError):
            m.spiral_matrix_generate(0)

    def test_diagonal_sort_matrix(self):
        self.assertEqual(m.diagonal_sort_matrix(
            [[3, 3, 1], [2, 2, 1], [1, 1, 2]]),
            [[2, 1, 1], [1, 2, 3], [1, 2, 3]])
        # property oracle: each diagonal sorted, same multiset kept
        rng = random.Random(6706)
        for _ in range(60):
            rows = rng.randint(1, 6)
            cols = rng.randint(1, 6)
            mat = [[rng.randint(-9, 9) for _ in range(cols)]
                   for _ in range(rows)]
            got = m.diagonal_sort_matrix(mat)
            keys = {r - c for r in range(rows) for c in range(cols)}
            for k in keys:
                before = sorted(mat[r][c] for r in range(rows)
                                for c in range(cols) if r - c == k)
                after = [got[r][c] for r in range(rows)
                         for c in range(cols) if r - c == k]
                self.assertEqual(after, before, (mat, k))
        with self.assertRaises(ValueError):
            m.diagonal_sort_matrix([[1, 2], [3]])

    def test_valid_sudoku_check(self):
        base = [[5, 3, 4, 6, 7, 8, 9, 1, 2],
                [6, 7, 2, 1, 9, 5, 3, 4, 8],
                [1, 9, 8, 3, 4, 2, 5, 6, 7],
                [8, 5, 9, 7, 6, 1, 4, 2, 3],
                [4, 2, 6, 8, 5, 3, 7, 9, 1],
                [7, 1, 3, 9, 2, 4, 8, 5, 6],
                [9, 6, 1, 5, 3, 7, 2, 8, 4],
                [2, 8, 7, 4, 1, 9, 6, 3, 5],
                [3, 4, 5, 2, 8, 6, 1, 7, 9]]
        self.assertTrue(m.valid_sudoku_check(base))
        bad = [row[:] for row in base]
        bad[0][0] = bad[0][1]
        self.assertFalse(m.valid_sudoku_check(bad))
        blank = [[0] * 9 for _ in range(9)]
        self.assertTrue(m.valid_sudoku_check(blank))
        # oracle: validity preserved by band row swaps and relabel
        rng = random.Random(6707)
        for _ in range(30):
            b = [row[:] for row in base]
            for band in (0, 3, 6):
                i, j = rng.sample(range(band, band + 3), 2)
                b[i], b[j] = b[j], b[i]
            perm = list(range(1, 10))
            rng.shuffle(perm)
            b = [[0 if v == 0 else perm[v - 1] for v in row]
                 for row in b]
            self.assertTrue(m.valid_sudoku_check(b))
            r, c = rng.randrange(9), rng.randrange(9)
            b[r][c] = b[r][(c + 1) % 9]
            self.assertFalse(m.valid_sudoku_check(b))
        with self.assertRaises(ValueError):
            m.valid_sudoku_check([[0] * 9 for _ in range(8)])
        with self.assertRaises(ValueError):
            m.valid_sudoku_check([[10] * 9 for _ in range(9)])

    def test_maximal_rectangle_ones(self):
        self.assertEqual(m.maximal_rectangle_ones(
            [[1, 1, 1], [1, 1, 1]]), 6)
        self.assertEqual(m.maximal_rectangle_ones(
            [[1, 0, 1, 0, 0], [1, 0, 1, 1, 1], [1, 1, 1, 1, 1],
             [1, 0, 0, 1, 0]]), 6)
        self.assertEqual(m.maximal_rectangle_ones([[0]]), 0)
        # oracle: brute force over every rectangle
        rng = random.Random(6708)
        for _ in range(50):
            rows = rng.randint(1, 5)
            cols = rng.randint(1, 5)
            mat = _rand_grid(rng, rows, cols)
            best = 0
            for r1 in range(rows):
                for r2 in range(r1, rows):
                    for c1 in range(cols):
                        for c2 in range(c1, cols):
                            if all(mat[r][c] == 1
                                   for r in range(r1, r2 + 1)
                                   for c in range(c1, c2 + 1)):
                                best = max(best, (r2 - r1 + 1)
                                           * (c2 - c1 + 1))
            self.assertEqual(m.maximal_rectangle_ones(mat), best,
                             mat)
        with self.assertRaises(ValueError):
            m.maximal_rectangle_ones([[1, 0], [1]])

    def test_longest_increasing_path_matrix(self):
        self.assertEqual(m.longest_increasing_path_matrix(
            [[9, 9, 4], [6, 6, 8], [2, 1, 1]]), 4)
        self.assertEqual(m.longest_increasing_path_matrix(
            [[3, 4, 5], [3, 2, 6], [2, 2, 1]]), 4)
        self.assertEqual(m.longest_increasing_path_matrix([[7]]), 1)
        # oracle: plain recursion without memo on small matrices
        rng = random.Random(6709)
        for _ in range(50):
            rows = rng.randint(1, 4)
            cols = rng.randint(1, 4)
            mat = [[rng.randint(0, 12) for _ in range(cols)]
                   for _ in range(rows)]

            def dfs(r, c):
                best = 1
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = r + dx, c + dy
                    if (0 <= nr < rows and 0 <= nc < cols
                            and mat[nr][nc] > mat[r][c]):
                        best = max(best, 1 + dfs(nr, nc))
                return best
            want = max(dfs(r, c) for r in range(rows)
                       for c in range(cols))
            self.assertEqual(m.longest_increasing_path_matrix(mat),
                             want, mat)
        with self.assertRaises(ValueError):
            m.longest_increasing_path_matrix([[]])

    def test_lip_leaves_recursion_limit_untouched(self):
        import sys
        before = sys.getrecursionlimit()
        grid = [[r * 200 + c for c in range(200)]
                for r in range(50)]
        m.longest_increasing_path_matrix(grid)
        self.assertEqual(sys.getrecursionlimit(), before)

    def test_grid_total_cell_cap(self):
        # 100x100 = 10000 cells accepted at the cap (heaviest two)
        full = [[1] * 100 for _ in range(100)]
        self.assertEqual(m.count_submatrices_all_ones(full),
                         100 * 101 * 100 * 101 // 4)
        self.assertEqual(m.maximal_rectangle_ones(full), 10_000)
        # cap+1 refused with the exact code
        over = [[1] * 101 for _ in range(100)]
        with self.assertRaises(ValueError) as ctx:
            m.count_submatrices_all_ones(over)
        self.assertIn("too_many_cells:mat", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.number_of_enclaves(over)
        self.assertIn("too_many_cells:grid", str(ctx.exception))

    def test_count_submatrices_all_ones(self):
        self.assertEqual(m.count_submatrices_all_ones(
            [[1, 0, 1], [1, 1, 0]]), 6)
        self.assertEqual(m.count_submatrices_all_ones(
            [[1, 1, 1]]), 6)
        self.assertEqual(m.count_submatrices_all_ones([[0]]), 0)
        # oracle: brute force over every submatrix
        rng = random.Random(6710)
        for _ in range(50):
            rows = rng.randint(1, 4)
            cols = rng.randint(1, 4)
            mat = _rand_grid(rng, rows, cols)
            want = 0
            for r1 in range(rows):
                for r2 in range(r1, rows):
                    for c1 in range(cols):
                        for c2 in range(c1, cols):
                            if all(mat[r][c] == 1
                                   for r in range(r1, r2 + 1)
                                   for c in range(c1, c2 + 1)):
                                want += 1
            self.assertEqual(m.count_submatrices_all_ones(mat),
                             want, mat)
        with self.assertRaises(ValueError):
            m.count_submatrices_all_ones([[2]])

    def test_registry_knows_batch67(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("shortest_path_binary_matrix",
                     "number_of_enclaves",
                     "matrix_nearest_zero_distance",
                     "pacific_atlantic_cells", "spiral_matrix_generate",
                     "diagonal_sort_matrix", "valid_sudoku_check",
                     "maximal_rectangle_ones",
                     "longest_increasing_path_matrix",
                     "count_submatrices_all_ones"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
