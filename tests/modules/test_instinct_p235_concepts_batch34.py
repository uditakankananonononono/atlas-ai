"""P235 concepts, batch 34 (algebra and geometry II, 331-340). Offline."""
from __future__ import annotations

import random
import unittest
from fractions import Fraction

from app.modules.instinct_doc import p235_concepts_batch34 as m


class Batch34Test(unittest.TestCase):
    def test_matrix_multiply_exact(self):
        self.assertEqual(m.matrix_multiply_exact(
            [[1, 2], [3, 4]], [[5, 6], [7, 8]]), [[19, 22], [43, 50]])
        self.assertEqual(m.matrix_multiply_exact(
            [[1, 2, 3]], [[4], [5], [6]]), [[32]])
        with self.assertRaises(ValueError) as ctx:
            m.matrix_multiply_exact([[1, 2]], [[1, 2]])
        self.assertIn("shape:", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.matrix_multiply_exact([[1], [True]], [[1]])
        with self.assertRaises(ValueError) as ctx:
            m.matrix_multiply_exact([[1, 2], [3]], [[1], [2]])
        self.assertIn("ragged:", str(ctx.exception))

    def test_matrix_multiply_oracle(self):
        rng = random.Random(34)
        for _ in range(50):
            r, k, c = (rng.randint(1, 4) for _ in range(3))
            a = [[rng.randint(-5, 5) for _ in range(k)] for _ in range(r)]
            b = [[rng.randint(-5, 5) for _ in range(c)] for _ in range(k)]
            want = [[sum(x * y for x, y in zip(row, col))
                     for col in zip(*b)] for row in a]
            self.assertEqual(m.matrix_multiply_exact(a, b), want)

    def test_matrix_rank_exact(self):
        self.assertEqual(m.matrix_rank_exact([[1, 2], [2, 4]]), 1)
        self.assertEqual(m.matrix_rank_exact([[1, 2], [3, 4]]), 2)
        self.assertEqual(m.matrix_rank_exact([[0, 0], [0, 0]]), 0)
        self.assertEqual(m.matrix_rank_exact([[1, 0, 5], [0, 1, 6]]), 2)
        with self.assertRaises(ValueError):
            m.matrix_rank_exact([])

    def test_matrix_rank_oracle_leibniz(self):
        from itertools import permutations, combinations

        def det(mat):
            n = len(mat)
            total = 0
            for perm in permutations(range(n)):
                inv = sum(1 for i in range(n)
                          for j in range(i + 1, n) if perm[i] > perm[j])
                prod = 1
                for i in range(n):
                    prod *= mat[i][perm[i]]
                total += prod if inv % 2 == 0 else -prod
            return total

        def oracle(a):
            rows, cols = len(a), len(a[0])
            for k in range(min(rows, cols), 0, -1):
                for rs in combinations(range(rows), k):
                    for cs in combinations(range(cols), k):
                        sub = [[a[i][j] for j in cs] for i in rs]
                        if det(sub) != 0:
                            return k
            return 0

        rng = random.Random(7)
        for _ in range(60):
            r, c = rng.randint(1, 4), rng.randint(1, 4)
            a = [[rng.randint(-3, 3) for _ in range(c)] for _ in range(r)]
            self.assertEqual(m.matrix_rank_exact(a), oracle(a), a)

    def test_closest_pair_distance2(self):
        self.assertEqual(
            m.closest_pair_distance2([[0, 0], [3, 4], [1, 1]]), 2)
        self.assertEqual(m.closest_pair_distance2([[0, 0], [0, 0]]), 0)
        with self.assertRaises(ValueError) as ctx:
            m.closest_pair_distance2([[0, 0]])
        self.assertIn("too_few:points", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.closest_pair_distance2([[0, 0], [1, True]])

    def test_closest_pair_oracle(self):
        from itertools import combinations
        rng = random.Random(3)
        for _ in range(40):
            n = rng.randint(2, 12)
            pts = [[rng.randint(-20, 20), rng.randint(-20, 20)]
                   for _ in range(n)]
            want = min((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
                       for a, b in combinations(pts, 2))
            self.assertEqual(m.closest_pair_distance2(pts), want)

    def test_point_line_distance2_exact(self):
        self.assertEqual(
            m.point_line_distance2_exact([0, 1], [0, 0], [2, 0]), 1)
        # 3-4-5 triangle: distance from origin to line x/4+y/3=1 is 12/5
        self.assertEqual(
            m.point_line_distance2_exact([0, 0], [4, 0], [0, 3]),
            Fraction(144, 25))
        self.assertEqual(
            m.point_line_distance2_exact([3, 3], [0, 0], [6, 6]), 0)
        with self.assertRaises(ValueError) as ctx:
            m.point_line_distance2_exact([0, 0], [1, 1], [1, 1])
        self.assertIn("degenerate:", str(ctx.exception))

    def test_circumcircle_center_exact(self):
        self.assertEqual(m.circumcircle_center_exact(
            [0, 0], [2, 0], [0, 2]), (Fraction(1), Fraction(1)))
        self.assertEqual(m.circumcircle_center_exact(
            [0, 0], [4, 0], [0, 4]), (Fraction(2), Fraction(2)))
        with self.assertRaises(ValueError) as ctx:
            m.circumcircle_center_exact([0, 0], [1, 1], [2, 2])
        self.assertIn("collinear:", str(ctx.exception))

    def test_circumcircle_equidistance_oracle(self):
        rng = random.Random(11)
        tested = 0
        while tested < 60:
            pts = [[rng.randint(-10, 10), rng.randint(-10, 10)]
                   for _ in range(3)]
            p1, p2, p3 = pts
            if (p2[0] - p1[0]) * (p3[1] - p1[1]) == \
                    (p2[1] - p1[1]) * (p3[0] - p1[0]):
                continue
            cx, cy = m.circumcircle_center_exact(p1, p2, p3)
            d2 = [(Fraction(x) - cx) ** 2 + (Fraction(y) - cy) ** 2
                  for x, y in pts]
            self.assertEqual(d2[0], d2[1], pts)
            self.assertEqual(d2[1], d2[2], pts)
            tested += 1

    def test_angle_classification(self):
        self.assertEqual(
            m.angle_classification([1, 0], [0, 0], [0, 1]), "right")
        self.assertEqual(
            m.angle_classification([2, 0], [0, 0], [1, 0]), "acute")
        self.assertEqual(
            m.angle_classification([-1, 0], [0, 0], [1, 1]), "obtuse")
        with self.assertRaises(ValueError) as ctx:
            m.angle_classification([0, 0], [0, 0], [1, 1])
        self.assertIn("degenerate:", str(ctx.exception))

    def test_angle_classification_cosine_oracle(self):
        # law of cosines: angle at b is acute/right/obtuse iff
        # |ac|^2 is </=/> |ab|^2 + |bc|^2 - a different formula
        rng = random.Random(5)
        for _ in range(200):
            a = [rng.randint(-9, 9), rng.randint(-9, 9)]
            b = [rng.randint(-9, 9), rng.randint(-9, 9)]
            c = [rng.randint(-9, 9), rng.randint(-9, 9)]
            if a == b or c == b:
                continue
            ab2 = (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
            bc2 = (c[0] - b[0]) ** 2 + (c[1] - b[1]) ** 2
            ac2 = (a[0] - c[0]) ** 2 + (a[1] - c[1]) ** 2
            if ac2 < ab2 + bc2:
                want = "acute"
            elif ac2 > ab2 + bc2:
                want = "obtuse"
            else:
                want = "right"
            self.assertEqual(m.angle_classification(a, b, c), want,
                             (a, b, c))

    def test_polygon_is_convex_check(self):
        self.assertTrue(m.polygon_is_convex_check(
            [[0, 0], [4, 0], [4, 4], [0, 4]]))
        self.assertFalse(m.polygon_is_convex_check(
            [[0, 0], [4, 0], [4, 4], [2, 2], [0, 4]]))
        self.assertTrue(m.polygon_is_convex_check(
            [[0, 0], [0, 4], [4, 4], [4, 0]]))  # clockwise
        # audit: a self-crossing star has all equal turn signs but is not
        # a simple polygon; it must be refused, not called convex
        with self.assertRaises(ValueError) as ctx:
            m.polygon_is_convex_check(
                [[0, 3], [2, -3], [-3, 1], [3, 1], [-2, -3]])
        self.assertIn("self_intersecting", str(ctx.exception))
        # touching non-adjacent edges are also not simple
        with self.assertRaises(ValueError) as ctx:
            m.polygon_is_convex_check(
                [[0, 0], [4, 0], [4, 4], [2, 0], [0, 4]])
        self.assertIn("self_intersecting", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.polygon_is_convex_check([[0, 0], [1, 1]])
        self.assertIn("too_few:", str(ctx.exception))

    def test_polygon_convex_halfplane_oracle(self):
        # independent: convex iff every edge has all other vertices on
        # one side (works on the simple radial polygons generated here)
        import math

        def oracle(pts):
            n = len(pts)
            for i in range(n):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % n]
                sides = set()
                for j in range(n):
                    if j in (i, (i + 1) % n):
                        continue
                    cross = ((x2 - x1) * (pts[j][1] - y1)
                             - (y2 - y1) * (pts[j][0] - x1))
                    sides.add(0 if cross == 0 else
                              (1 if cross > 0 else -1))
                if 1 in sides and -1 in sides:
                    return False
            return True

        rng = random.Random(19)
        for _ in range(80):
            cx, cy = rng.randint(-5, 5), rng.randint(-5, 5)
            n = rng.randint(3, 8)
            seen = set()
            pts = []
            tries = 0
            while len(pts) < n and tries < 200:
                tries += 1
                x, y = rng.randint(-15, 15), rng.randint(-15, 15)
                if (x, y) == (cx, cy):
                    continue
                ang = math.atan2(y - cy, x - cx)
                if ang in seen:
                    continue
                seen.add(ang)
                pts.append((ang, [x, y]))
            if len(pts) < n:
                continue
            poly = [p for _a, p in sorted(pts)]
            try:
                got = m.polygon_is_convex_check(poly)
            except ValueError:
                continue  # refused non-simple polygons are pinned above
            self.assertEqual(got, oracle(poly), poly)

    def test_perpendicular_check(self):
        self.assertTrue(m.perpendicular_check(
            [0, 0], [1, 1], [0, 0], [1, -1]))
        self.assertFalse(m.perpendicular_check(
            [0, 0], [1, 1], [0, 0], [2, 2]))
        with self.assertRaises(ValueError) as ctx:
            m.perpendicular_check([0, 0], [0, 0], [0, 0], [1, 0])
        self.assertIn("degenerate:", str(ctx.exception))

    def test_perpendicular_vs_angle_classification(self):
        rng = random.Random(23)
        for _ in range(100):
            o = [rng.randint(-5, 5) for _ in range(2)]
            a = [rng.randint(-5, 5) for _ in range(2)]
            b = [rng.randint(-5, 5) for _ in range(2)]
            if a == o or b == o:
                continue
            self.assertEqual(m.perpendicular_check(o, a, o, b),
                             m.angle_classification(a, o, b) == "right")

    def test_parallelogram_check(self):
        self.assertTrue(m.parallelogram_check(
            [0, 0], [2, 0], [3, 1], [1, 1]))
        self.assertFalse(m.parallelogram_check(
            [0, 0], [2, 0], [3, 1], [0, 1]))
        self.assertFalse(m.parallelogram_check(
            [0, 0], [1, 0], [2, 0], [3, 0]))
        with self.assertRaises(ValueError) as ctx:
            m.parallelogram_check([0, 0], [0, 0], [1, 0], [0, 1])
        self.assertIn("degenerate:", str(ctx.exception))

    def test_parallelogram_constructive_oracle(self):
        rng = random.Random(29)
        for _ in range(100):
            p = [rng.randint(-9, 9), rng.randint(-9, 9)]
            u = [rng.randint(-9, 9), rng.randint(-9, 9)]
            v = [rng.randint(-9, 9), rng.randint(-9, 9)]
            if u[0] * v[1] == u[1] * v[0]:
                continue
            quad = [p, [p[0] + u[0], p[1] + u[1]],
                    [p[0] + u[0] + v[0], p[1] + u[1] + v[1]],
                    [p[0] + v[0], p[1] + v[1]]]
            rng.shuffle(quad)
            self.assertTrue(m.parallelogram_check(*quad), quad)

    def test_max_points_on_line(self):
        self.assertEqual(
            m.max_points_on_line([[0, 0], [1, 1], [2, 2], [0, 1]]), 3)
        # audit: duplicate points must not fake a "line" through a zero
        # direction
        self.assertEqual(
            m.max_points_on_line([[0, 0], [0, 0], [1, 0], [0, 1]]), 3)
        self.assertEqual(
            m.max_points_on_line([[5, 5], [5, 5], [5, 5]]), 3)
        self.assertEqual(
            m.max_points_on_line([[1, 1], [1, 1], [2, 2], [3, 3]]), 4)
        self.assertEqual(m.max_points_on_line([[0, 0], [1, 0]]), 2)
        self.assertEqual(m.max_points_on_line([]), 0)
        self.assertEqual(m.max_points_on_line([[5, 5]]), 1)
        with self.assertRaises(ValueError) as ctx:
            m.max_points_on_line([[i, 0] for i in range(201)])
        self.assertIn("too_many:points", str(ctx.exception))

    def test_max_points_on_line_oracle(self):
        # independent: group points by the normalized line through each
        # pair, keyed as a reduced (A, B, C) triple for Ax+By=C
        from math import gcd

        def oracle(pts):
            counts = {}
            for p in pts:
                key = (p[0], p[1])
                counts[key] = counts.get(key, 0) + 1
            uniq = sorted(counts)
            if len(uniq) <= 1:
                return len(pts)
            best = 0
            for i in range(len(uniq)):
                for j in range(i + 1, len(uniq)):
                    x1, y1 = uniq[i]
                    x2, y2 = uniq[j]
                    a = y2 - y1
                    b = x1 - x2
                    c = a * x1 + b * y1
                    g = gcd(gcd(abs(a), abs(b)), abs(c))
                    if g:
                        a, b, c = a // g, b // g, c // g
                    if a < 0 or (a == 0 and b < 0):
                        a, b, c = -a, -b, -c
                    count = sum(mult for (x, y), mult in counts.items()
                                if a * x + b * y == c)
                    best = max(best, count)
            return best

        rng = random.Random(31)
        for _ in range(120):
            # duplicate-heavy: tiny coordinate range, repeats likely
            n = rng.randint(0, 18)
            pts = [[rng.randint(-2, 2), rng.randint(-2, 2)]
                   for _ in range(n)]
            self.assertEqual(m.max_points_on_line(pts), oracle(pts), pts)

    def test_registry_knows_batch34(self):
        from app.modules.instinct_doc import p235_concepts_registry as reg
        names = [e["name"] for e in reg.ENTRIES]
        for name in ("matrix_multiply_exact", "matrix_rank_exact",
                     "closest_pair_distance2", "point_line_distance2_exact",
                     "circumcircle_center_exact", "angle_classification",
                     "polygon_is_convex_check", "perpendicular_check",
                     "parallelogram_check", "max_points_on_line"):
            self.assertIn(name, names)
        own = [e for e in reg.ENTRIES if e["batch"] == 34]
        self.assertEqual(len(own), 10)
        for name in ("matrix_multiply_exact", "matrix_rank_exact",
                     "closest_pair_distance2", "point_line_distance2_exact",
                     "circumcircle_center_exact", "angle_classification",
                     "polygon_is_convex_check", "perpendicular_check",
                     "parallelogram_check", "max_points_on_line"):
            self.assertIn(name, [e["name"] for e in own])


if __name__ == "__main__":
    unittest.main()
