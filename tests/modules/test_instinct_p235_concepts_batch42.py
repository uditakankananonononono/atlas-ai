"""Tests for P235 concepts batch 42 (411-420)."""
import random
import unittest
from collections import deque

from app.modules.instinct_doc import p235_concepts_batch42 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class Batch42Test(unittest.TestCase):
    def test_triangle_min_path_sum(self):
        self.assertEqual(
            m.triangle_min_path_sum([[2], [3, 4], [6, 5, 7], [4, 1, 8, 3]]),
            11)
        self.assertEqual(m.triangle_min_path_sum([[-10]]), -10)
        # oracle: exhaustive enumeration of every path
        rng = random.Random(4201)
        for _ in range(40):
            h = rng.randint(1, 6)
            tri = [[rng.randint(-9, 9) for _ in range(r + 1)]
                   for r in range(h)]

            def best(r, c):
                if r == h - 1:
                    return tri[r][c]
                return tri[r][c] + min(best(r + 1, c), best(r + 1, c + 1))

            self.assertEqual(m.triangle_min_path_sum(tri), best(0, 0), tri)
        for bad in ([[1], [2]], [[1], [2, 3, 4]]):
            with self.assertRaises(ValueError, msg=bad):
                m.triangle_min_path_sum(bad)
        with self.assertRaises(ValueError):
            m.triangle_min_path_sum([])

    def test_min_path_sum_grid(self):
        self.assertEqual(m.min_path_sum_grid(
            [[1, 3, 1], [1, 5, 1], [4, 2, 1]]), 7)
        self.assertEqual(m.min_path_sum_grid([[5]]), 5)
        # oracle: recursion over the two legal predecessors
        rng = random.Random(4202)
        for _ in range(30):
            h = rng.randint(1, 5)
            w = rng.randint(1, 5)
            grid = [[rng.randint(0, 20) for _ in range(w)]
                    for _ in range(h)]

            def best(r, c):
                if r == 0 and c == 0:
                    return grid[0][0]
                cand = []
                if r > 0:
                    cand.append(best(r - 1, c))
                if c > 0:
                    cand.append(best(r, c - 1))
                return grid[r][c] + min(cand)

            self.assertEqual(m.min_path_sum_grid(grid),
                             best(h - 1, w - 1), grid)
        with self.assertRaises(ValueError):
            m.min_path_sum_grid([[1], [2, 3]])

    def test_unique_paths_with_obstacles(self):
        self.assertEqual(m.unique_paths_with_obstacles(
            [[0, 0, 0], [0, 1, 0], [0, 0, 0]]), 2)
        self.assertEqual(m.unique_paths_with_obstacles([[1]]), 0)
        self.assertEqual(m.unique_paths_with_obstacles([[0, 1]]), 0)
        # oracle: full 2D DP recomputation
        rng = random.Random(4203)
        for _ in range(40):
            h = rng.randint(1, 6)
            w = rng.randint(1, 6)
            grid = [[1 if rng.random() < 0.25 else 0 for _ in range(w)]
                    for _ in range(h)]
            dp = [[0] * w for _ in range(h)]
            for r in range(h):
                for c in range(w):
                    if grid[r][c] == 1:
                        continue
                    if r == 0 and c == 0:
                        dp[r][c] = 1
                    else:
                        dp[r][c] = ((dp[r - 1][c] if r > 0 else 0)
                                    + (dp[r][c - 1] if c > 0 else 0))
            self.assertEqual(m.unique_paths_with_obstacles(grid),
                             dp[-1][-1], grid)
        with self.assertRaises(ValueError):
            m.unique_paths_with_obstacles([[0, 2]])

    def test_max_square_submatrix(self):
        grid = [[1, 0, 1, 0, 0],
                [1, 0, 1, 1, 1],
                [1, 1, 1, 1, 1],
                [1, 0, 0, 1, 0]]
        self.assertEqual(m.max_square_submatrix(grid), 2)
        self.assertEqual(m.max_square_submatrix([[0, 0], [0, 0]]), 0)
        self.assertEqual(m.max_square_submatrix([[1]]), 1)
        # oracle: brute force over every candidate square
        rng = random.Random(4204)
        for _ in range(40):
            h = rng.randint(1, 6)
            w = rng.randint(1, 6)
            g = [[rng.randint(0, 1) for _ in range(w)] for _ in range(h)]
            want = 0
            for side in range(1, min(h, w) + 1):
                ok = False
                for r in range(h - side + 1):
                    for c in range(w - side + 1):
                        if all(g[r + i][c + j] == 1
                               for i in range(side)
                               for j in range(side)):
                            ok = True
                if ok:
                    want = side
            self.assertEqual(m.max_square_submatrix(g), want, g)
        with self.assertRaises(ValueError):
            m.max_square_submatrix([[1, 2]])

    def test_matrix_reshape(self):
        self.assertEqual(m.matrix_reshape([1, 2, 3, 4, 5, 6], 2, 3),
                         [[1, 2, 3], [4, 5, 6]])
        self.assertEqual(m.matrix_reshape([], 0, 0) if False else
                         m.matrix_reshape([7], 1, 1), [[7]])
        # oracle: nested index arithmetic
        rng = random.Random(4205)
        for _ in range(40):
            r = rng.randint(1, 6)
            c = rng.randint(1, 6)
            flat = [rng.randint(-20, 20) for _ in range(r * c)]
            want = [[flat[i * c + j] for j in range(c)]
                    for i in range(r)]
            self.assertEqual(m.matrix_reshape(flat, r, c), want, flat)
        for bad_args in (([1, 2, 3], 2, 2), ([1, 2], 0, 2), ([1], -1, 1)):
            with self.assertRaises(ValueError, msg=bad_args):
                m.matrix_reshape(*bad_args)

    def test_diagonal_traverse_order(self):
        self.assertEqual(m.diagonal_traverse_order(
            [[1, 2, 3], [4, 5, 6], [7, 8, 9]]),
            [1, 2, 4, 7, 5, 3, 6, 8, 9])
        self.assertEqual(m.diagonal_traverse_order([[1, 2], [3, 4]]),
                         [1, 2, 3, 4])
        # oracle: enumerate cells by anti-diagonal, alternate direction
        rng = random.Random(4206)
        for _ in range(40):
            h = rng.randint(1, 5)
            w = rng.randint(1, 5)
            g = [[rng.randint(0, 99) for _ in range(w)] for _ in range(h)]
            want = []
            for s in range(h + w - 1):
                cells = [(r, s - r) for r in range(h)
                         if 0 <= s - r < w]
                if s % 2 == 0:
                    cells.reverse()
                want.extend(g[r][c] for r, c in cells)
            self.assertEqual(m.diagonal_traverse_order(g), want, g)
        with self.assertRaises(ValueError):
            m.diagonal_traverse_order([[1], [1, 2]])

    def test_set_matrix_zeroes(self):
        self.assertEqual(m.set_matrix_zeroes(
            [[1, 1, 1], [1, 0, 1], [1, 1, 1]]),
            [[1, 0, 1], [0, 0, 0], [1, 0, 1]])
        self.assertEqual(m.set_matrix_zeroes([[0]]), [[0]])
        self.assertEqual(m.set_matrix_zeroes(
            [[0, 1, 2, 0], [3, 4, 5, 2], [1, 3, 1, 5]]),
            [[0, 0, 0, 0], [0, 4, 5, 0], [0, 3, 1, 0]])
        # oracle: mark then rebuild, independently coded
        rng = random.Random(4207)
        for _ in range(40):
            h = rng.randint(1, 5)
            w = rng.randint(1, 5)
            g = [[rng.randint(0, 5) for _ in range(w)] for _ in range(h)]
            zrows = {r for r in range(h) if 0 in g[r]}
            zcols = {c for c in range(w)
                     if any(g[r][c] == 0 for r in range(h))}
            want = [[0 if r in zrows or c in zcols else g[r][c]
                     for c in range(w)] for r in range(h)]
            self.assertEqual(m.set_matrix_zeroes(g), want, g)
        with self.assertRaises(ValueError):
            m.set_matrix_zeroes([])

    def test_word_search_exists(self):
        board = [["A", "B", "C", "E"],
                 ["S", "F", "C", "S"],
                 ["A", "D", "E", "E"]]
        self.assertTrue(m.word_search_exists(board, "ABCCED"))
        self.assertTrue(m.word_search_exists(board, "SEE"))
        self.assertFalse(m.word_search_exists(board, "ABCB"))
        self.assertTrue(m.word_search_exists([["a"]], "a"))
        # oracle: independent recursive search with an explicit visited set
        rng = random.Random(4208)
        alpha = "abc"
        for _ in range(40):
            h = rng.randint(1, 4)
            w = rng.randint(1, 4)
            g = [[rng.choice(alpha) for _ in range(w)] for _ in range(h)]
            word = "".join(rng.choice(alpha)
                           for _ in range(rng.randint(1, 5)))

            def find(r, c, i, seen):
                if i == len(word):
                    return True
                if not (0 <= r < h and 0 <= c < w):
                    return False
                if (r, c) in seen or g[r][c] != word[i]:
                    return False
                nxt = seen | {(r, c)}
                return (find(r + 1, c, i + 1, nxt)
                        or find(r - 1, c, i + 1, nxt)
                        or find(r, c + 1, i + 1, nxt)
                        or find(r, c - 1, i + 1, nxt))

            want = any(find(r, c, 0, frozenset())
                       for r in range(h) for c in range(w))
            self.assertEqual(m.word_search_exists(g, word), want,
                             (g, word))
        with self.assertRaises(ValueError):
            m.word_search_exists([["a"]], "")
        with self.assertRaises(ValueError):
            m.word_search_exists([["ab"]], "a")
        # NUL is refused in both word and grid cells (no sentinel
        # tricks: visited cells are tracked in a real set)
        with self.assertRaises(ValueError):
            m.word_search_exists([["a"]], "\x00")
        with self.assertRaises(ValueError):
            m.word_search_exists([["\x00"]], "a")

    def test_word_search_iterative_at_cap(self):
        # a 1000-cell straight word at the cap: the DFS is iterative,
        # so this must not touch the recursion limit
        row = ["a"] * m.MAX_WORD
        self.assertTrue(m.word_search_exists([row], "a" * m.MAX_WORD))
        snake = [["a" if (r // 1) % 2 == 0 else "a"
                  for _ in range(50)] for r in range(20)]
        self.assertTrue(m.word_search_exists(snake, "a" * m.MAX_WORD))
        with self.assertRaises(ValueError):
            m.word_search_exists(row, "a" * (m.MAX_WORD + 1))

    def test_rotting_oranges_time(self):
        self.assertEqual(m.rotting_oranges_time(
            [[2, 1, 1], [1, 1, 0], [0, 1, 1]]), 4)
        self.assertEqual(m.rotting_oranges_time(
            [[2, 1, 1], [0, 1, 1], [1, 0, 1]]), -1)
        self.assertEqual(m.rotting_oranges_time([[0, 2]]), 0)
        # oracle: multi-source BFS with deque and distance grid
        rng = random.Random(4209)
        for _ in range(40):
            h = rng.randint(1, 5)
            w = rng.randint(1, 5)
            g = [[rng.choice([0, 1, 1, 2]) for _ in range(w)]
                 for _ in range(h)]
            dist = [[-1] * w for _ in range(h)]
            q = deque()
            for r in range(h):
                for c in range(w):
                    if g[r][c] == 2:
                        dist[r][c] = 0
                        q.append((r, c))
            while q:
                r, c = q.popleft()
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = r + dr, c + dc
                    if (0 <= nr < h and 0 <= nc < w
                            and g[nr][nc] == 1 and dist[nr][nc] == -1):
                        dist[nr][nc] = dist[r][c] + 1
                        q.append((nr, nc))
            times = [dist[r][c] for r in range(h) for c in range(w)
                     if g[r][c] == 1]
            want = max(times) if times else 0
            if -1 in times:
                want = -1
            self.assertEqual(m.rotting_oranges_time(g), want, g)
        with self.assertRaises(ValueError):
            m.rotting_oranges_time([[1, 3]])

    def test_dungeon_min_health(self):
        self.assertEqual(m.dungeon_min_health(
            [[-2, -3, 3], [-5, -10, 1], [10, 30, -5]]), 7)
        self.assertEqual(m.dungeon_min_health([[5]]), 1)
        self.assertEqual(m.dungeon_min_health([[0]]), 1)
        # oracle: forward recursion with health tracking on small grids
        rng = random.Random(4210)
        for _ in range(30):
            h = rng.randint(1, 4)
            w = rng.randint(1, 4)
            g = [[rng.randint(-10, 10) for _ in range(w)]
                 for _ in range(h)]
            # binary search the least starting health that survives
            def survives(start):
                best = [[None] * w for _ in range(h)]
                best[0][0] = start + g[0][0]
                if best[0][0] <= 0:
                    return False
                for r in range(h):
                    for c in range(w):
                        if r == 0 and c == 0:
                            continue
                        cand = []
                        if r > 0 and best[r - 1][c] is not None:
                            cand.append(best[r - 1][c])
                        if c > 0 and best[r][c - 1] is not None:
                            cand.append(best[r][c - 1])
                        if not cand:
                            continue
                        hp = max(cand) + g[r][c]
                        if hp > 0:
                            best[r][c] = hp
                return best[-1][-1] is not None

            lo, hi = 1, 1
            while not survives(hi):
                hi *= 2
            while lo < hi:
                mid = (lo + hi) // 2
                if survives(mid):
                    hi = mid
                else:
                    lo = mid + 1
            self.assertEqual(m.dungeon_min_health(g), lo, g)
        with self.assertRaises(ValueError):
            m.dungeon_min_health([[1], [2, 3]])

    def test_registry_knows_batch42(self):
        names = [e["name"] for e in reg.ENTRIES if e["batch"] == 42]
        self.assertEqual(len(names), 10)
        for name in ("triangle_min_path_sum", "min_path_sum_grid",
                     "unique_paths_with_obstacles", "max_square_submatrix",
                     "matrix_reshape", "diagonal_traverse_order",
                     "set_matrix_zeroes", "word_search_exists",
                     "rotting_oranges_time", "dungeon_min_health"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
