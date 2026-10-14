"""Tests for P235 concepts batch 59 (doc 581-590)."""
import random
import unittest
from fractions import Fraction

from app.modules.instinct_doc import p235_concepts_batch59 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


def rand_matrix(rng, rows, cols, lo=-9, hi=9):
    return [[rng.randint(lo, hi) for _ in range(cols)]
            for _ in range(rows)]


class Batch59Test(unittest.TestCase):
    def test_transpose_graph(self):
        self.assertEqual(
            m.transpose_graph(["a", "b", "c"], [["a", "b"], ["b", "c"]]),
            [["b", "a"], ["c", "b"]])
        self.assertEqual(m.transpose_graph(["x"], []), [])
        # oracle: adjacency-map reversal rebuilt from scratch
        rng = random.Random(5901)
        for _ in range(50):
            n = rng.randint(1, 6)
            nodes = ["n%d" % i for i in range(n)]
            edges = [[rng.choice(nodes), rng.choice(nodes)]
                     for _ in range(rng.randint(0, 8))]
            rev = {}
            for u, v in edges:
                rev.setdefault(v, []).append(u)
            want = []
            for u, v in edges:
                want.append([v, u])
            got = m.transpose_graph(nodes, edges)
            self.assertEqual(got, want, edges)
            for a, b in got:
                self.assertIn(a, rev)
                self.assertIn(b, rev[a])
        with self.assertRaises(ValueError):
            m.transpose_graph(["a", "a"], [])
        with self.assertRaises(ValueError):
            m.transpose_graph(["a"], [["a", "zz"]])
        with self.assertRaises(ValueError):
            m.transpose_graph(["a"], [("a", "a")])
        # doc says ASCII names: non-ASCII refuses, ASCII accepts
        with self.assertRaises(ValueError) as ctx:
            m.transpose_graph(["\u00e9"], [])
        self.assertIn("bad_value:nodes[0]", str(ctx.exception))
        self.assertEqual(m.transpose_graph(["e"], []), [])
        with self.assertRaises(ValueError):
            m.transpose_graph(["ok", "\u00e9"], [])

    def test_matrix_minor_exact(self):
        self.assertEqual(
            m.matrix_minor_exact(
                [[1, 2, 3], [4, 5, 6], [7, 8, 9]], 1, 1),
            [[1, 3], [7, 9]])
        # oracle: rebuild via explicit index walk
        rng = random.Random(5902)
        for _ in range(50):
            rows = rng.randint(2, 5)
            cols = rng.randint(2, 5)
            mat = rand_matrix(rng, rows, cols)
            r = rng.randrange(rows)
            c = rng.randrange(cols)
            want = []
            for i in range(rows):
                if i == r:
                    continue
                row = []
                for j in range(cols):
                    if j != c:
                        row.append(mat[i][j])
                want.append(row)
            self.assertEqual(m.matrix_minor_exact(mat, r, c), want,
                             (mat, r, c))
        with self.assertRaises(ValueError):
            m.matrix_minor_exact([[5]], 0, 0)
        with self.assertRaises(ValueError):
            m.matrix_minor_exact([[1, 2], [3, 4]], 2, 0)
        with self.assertRaises(ValueError):
            m.matrix_minor_exact([[1, 2], [3, 4]], 0, -1)

    def test_matrix_add_exact(self):
        self.assertEqual(m.matrix_add_exact([[1, 2], [3, 4]],
                                            [[5, 6], [7, 8]]),
                         [[6, 8], [10, 12]])
        # oracle: accumulate into a zero grid by index
        rng = random.Random(5903)
        for _ in range(50):
            rows = rng.randint(1, 4)
            cols = rng.randint(1, 4)
            a = rand_matrix(rng, rows, cols)
            b = rand_matrix(rng, rows, cols)
            want = [[0] * cols for _ in range(rows)]
            for i in range(rows):
                for j in range(cols):
                    want[i][j] += a[i][j] + b[i][j]
            self.assertEqual(m.matrix_add_exact(a, b), want)
        with self.assertRaises(ValueError):
            m.matrix_add_exact([[1]], [[1], [2]])
        with self.assertRaises(ValueError):
            m.matrix_add_exact([[1, 2]], [[1]])

    def test_matrix_scale_exact(self):
        self.assertEqual(m.matrix_scale_exact([[1, 2], [3, 4]], 3),
                         [[3, 6], [9, 12]])
        # oracle: repeated addition of the original values
        rng = random.Random(5904)
        for _ in range(50):
            mat = rand_matrix(rng, rng.randint(1, 4), rng.randint(1, 4))
            k = rng.randint(-5, 5)
            want = []
            for row in mat:
                out_row = []
                for v in row:
                    total = 0
                    for _ in range(abs(k)):
                        total += v if k >= 0 else -v
                    out_row.append(total)
                want.append(out_row)
            self.assertEqual(m.matrix_scale_exact(mat, k), want)
        with self.assertRaises(ValueError):
            m.matrix_scale_exact([[1]], True)

    def test_markov_matrix_check(self):
        self.assertTrue(m.markov_matrix_check(
            [[Fraction(1, 2), Fraction(1, 2)], [0, 1]]))
        self.assertFalse(m.markov_matrix_check([[1, 0], [0, 2]]))
        self.assertTrue(m.markov_matrix_check([[1]]))
        # oracle: decimal-free row tally via Fraction
        rng = random.Random(5905)
        for _ in range(50):
            n = rng.randint(1, 4)
            mat = [[Fraction(rng.randint(0, 4), 5)
                    for _ in range(n)] for _ in range(n)]
            want = all(sum(row, Fraction(0)) == 1 for row in mat)
            self.assertEqual(m.markov_matrix_check(mat), want, mat)
        with self.assertRaises(ValueError):
            m.markov_matrix_check([[Fraction(-1), Fraction(2)]])
        with self.assertRaises(ValueError):
            m.markov_matrix_check([[1, 0, 0], [0, 1, 0]])
        with self.assertRaises(ValueError):
            m.markov_matrix_check([[True]])
        # whole-matrix validation before any row verdict: a bad cell
        # in a later row refuses instead of returning False early
        with self.assertRaises(ValueError) as ctx:
            m.markov_matrix_check([[0, 0], [True, 0]])
        self.assertIn("bad_type:matrix[1][0]", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.markov_matrix_check(
                [[0, 0], [Fraction(-1), Fraction(2)]])
        self.assertIn("bad_value:matrix[1][0]", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.markov_matrix_check([[0, 0], [1, "x"]])
        self.assertIn("bad_type:matrix[1][1]", str(ctx.exception))
        # honest False still works when every cell is valid
        self.assertFalse(m.markov_matrix_check([[0, 0], [0, 1]]))

    def test_symmetric_matrix_check(self):
        self.assertTrue(m.symmetric_matrix_check([[1, 2], [2, 1]]))
        self.assertFalse(m.symmetric_matrix_check([[1, 2], [3, 1]]))
        # oracle: compare against the zip transpose
        rng = random.Random(5906)
        for _ in range(50):
            n = rng.randint(1, 4)
            mat = rand_matrix(rng, n, n)
            want = [list(row) for row in zip(*mat)] == mat
            self.assertEqual(m.symmetric_matrix_check(mat), want, mat)
        with self.assertRaises(ValueError):
            m.symmetric_matrix_check([[1, 2, 3], [4, 5, 6]])

    def test_reflect_matrix_horizontal(self):
        self.assertEqual(m.reflect_matrix_horizontal([[1, 2, 3],
                                                      [4, 5, 6]]),
                         [[3, 2, 1], [6, 5, 4]])
        # oracle: negative-stride slice
        rng = random.Random(5907)
        for _ in range(50):
            mat = rand_matrix(rng, rng.randint(1, 4), rng.randint(1, 4))
            want = [row[::-1] for row in mat]
            self.assertEqual(m.reflect_matrix_horizontal(mat), want)

    def test_argmax_2d(self):
        self.assertEqual(m.argmax_2d([[1, 5], [3, 2]]), [0, 1])
        self.assertEqual(m.argmax_2d([[5, 5], [1, 2]]), [0, 0])
        # oracle: linear scan over the flattened row-major cells
        rng = random.Random(5908)
        for _ in range(50):
            mat = rand_matrix(rng, rng.randint(1, 4), rng.randint(1, 4))
            flat = [(v, i, j)
                    for i, row in enumerate(mat)
                    for j, v in enumerate(row)]
            top = flat[0][0]
            want = [flat[0][1], flat[0][2]]
            for v, i, j in flat[1:]:
                if v > top:
                    top = v
                    want = [i, j]
            self.assertEqual(m.argmax_2d(mat), want, mat)
        with self.assertRaises(ValueError):
            m.argmax_2d([])

    def test_skew_symmetric_matrix_check(self):
        self.assertTrue(m.skew_symmetric_matrix_check([[0, 1], [-1, 0]]))
        self.assertFalse(m.skew_symmetric_matrix_check([[0, 1], [1, 0]]))
        self.assertFalse(m.skew_symmetric_matrix_check([[1, 0], [0, 1]]))
        self.assertTrue(m.skew_symmetric_matrix_check([[0]]))
        # oracle: A + A^T is the zero matrix
        rng = random.Random(5909)
        for _ in range(50):
            n = rng.randint(1, 4)
            mat = rand_matrix(rng, n, n)
            want = all(mat[i][j] + mat[j][i] == 0
                       for i in range(n) for j in range(n))
            self.assertEqual(m.skew_symmetric_matrix_check(mat),
                             want, mat)

    def test_upper_triangular_check(self):
        self.assertTrue(m.upper_triangular_check([[1, 2], [0, 3]]))
        self.assertFalse(m.upper_triangular_check([[1, 0], [2, 3]]))
        self.assertTrue(m.upper_triangular_check([[7]]))
        # oracle: every below-diagonal cell vanishes
        rng = random.Random(5910)
        for _ in range(50):
            n = rng.randint(1, 4)
            mat = rand_matrix(rng, n, n)
            want = all(mat[i][j] == 0
                       for i in range(n) for j in range(n) if i > j)
            self.assertEqual(m.upper_triangular_check(mat), want, mat)
        with self.assertRaises(ValueError):
            m.upper_triangular_check([[1, 2, 3], [0, 4, 5]])

    def test_registry_knows_batch59(self):
        names = [e["name"] for e in reg.ENTRIES if e["batch"] == 59]
        self.assertEqual(len(names), 10)
        for name in ("transpose_graph", "matrix_minor_exact",
                     "matrix_add_exact", "matrix_scale_exact",
                     "markov_matrix_check", "symmetric_matrix_check",
                     "reflect_matrix_horizontal", "argmax_2d",
                     "skew_symmetric_matrix_check",
                     "upper_triangular_check"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
