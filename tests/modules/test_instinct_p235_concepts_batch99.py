"""Tests for P235 concepts batch 99.

Every pin was read off a live run of the module. Randomized
checks compare against independent oracles: brute pairwise
sums plus hull for Minkowski, congruence verification for
Hensel lifting, divisor-candidate evaluation for rational
roots, naive simulation for move-to-front, candidate-vertex
enumeration plus hull for polygon intersection, independent
vertex enumeration for the LP, simple-cycle enumeration for
maximum cycle mean, brute node removal for tree centroids,
cell-decode containment for geohash, and direct search for
Pell minimality.
"""
import random
import sys
import unittest
from fractions import Fraction

sys.path.insert(0, "backend")

from app.modules.instinct_doc import p235_concepts_batch99 as b99


def _hull(points):
    # monotone chain over sorted distinct points; works for ints
    # and Fractions alike; returns CCW hull without the closing
    # duplicate.
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return ((a[0] - o[0]) * (b[1] - o[1])
                - (a[1] - o[1]) * (b[0] - o[0]))

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


class TestNonogramLineSolve(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b99.nonogram_line_solve([3], [0] * 5),
                         [0, 0, 1, 0, 0])
        self.assertEqual(b99.nonogram_line_solve([1, 1], [0] * 5),
                         [0, 0, 0, 0, 0])
        self.assertEqual(b99.nonogram_line_solve([2], [0, 2, 0, 0]),
                         [2, 2, 1, 1])
        self.assertEqual(b99.nonogram_line_solve([], [0, 2, 0]),
                         [2, 2, 2])
        self.assertEqual(b99.nonogram_line_solve([1], [0, 1]),
                         [2, 1])
        self.assertEqual(b99.nonogram_line_solve([5], [0] * 5),
                         [1, 1, 1, 1, 1])
        # known-filled cell two gaps before a later run: only the
        # covering placement survives
        self.assertEqual(b99.nonogram_line_solve([1], [1, 0, 0]),
                         [1, 2, 2])
        # separator cell known filled: no placement
        # (refusal pinned in test_refusals)

    def test_oracle(self):
        def brute(clues, cells):
            w = len(cells)
            valids = 0
            fill = [0] * w
            for mask in range(1 << w):
                bits = [(mask >> j) & 1 for j in range(w)]
                runs = []
                cur = 0
                for b in bits:
                    if b:
                        cur += 1
                    elif cur:
                        runs.append(cur)
                        cur = 0
                if cur:
                    runs.append(cur)
                if runs != clues:
                    continue
                if any(c == 1 and not b
                       for c, b in zip(cells, bits)):
                    continue
                if any(c == 2 and b
                       for c, b in zip(cells, bits)):
                    continue
                valids += 1
                for j, b in enumerate(bits):
                    fill[j] += b
            if valids == 0:
                return None
            return [1 if f == valids else (2 if f == 0 else 0)
                    for f in fill]

        rng = random.Random(991)
        for _ in range(400):
            w = rng.randint(1, 11)
            clues = []
            left = w
            while left > 0 and rng.random() < 0.5:
                r = rng.randint(1, max(1, left))
                clues.append(r)
                left -= r + 1
            if sum(clues) + max(0, len(clues) - 1) > w:
                continue
            cells = [rng.choice([0, 0, 0, 1, 2]) for _ in range(w)]
            want = brute(clues, cells)
            if want is None:
                with self.assertRaises(ValueError):
                    b99.nonogram_line_solve(list(clues), list(cells))
            else:
                self.assertEqual(
                    b99.nonogram_line_solve(list(clues), list(cells)),
                    want)

    def test_refusals(self):
        with self.assertRaises(ValueError):  # inconsistent
            b99.nonogram_line_solve([1, 1], [0, 1, 0])
        with self.assertRaises(ValueError):  # runs too long
            b99.nonogram_line_solve([4], [0, 0, 0])
        with self.assertRaises(ValueError):  # empty line
            b99.nonogram_line_solve([1], [])
        with self.assertRaises(ValueError):  # zero clue
            b99.nonogram_line_solve([0], [0, 0])
        with self.assertRaises(ValueError):  # bad cell value
            b99.nonogram_line_solve([1], [0, 3])
        with self.assertRaises(ValueError):  # fill under empty clues
            b99.nonogram_line_solve([], [1, 0])
        with self.assertRaises(ValueError):  # clue above width
            b99.nonogram_line_solve([10**400], [0] * 5)

    def test_resource_caps(self):
        # inconsistent line with known blanks everywhere: refuses
        # fast by pruning, not by the node cap
        with self.assertRaises(ValueError):
            b99.nonogram_line_solve([1] * 10, [2] * 59 + [0])
        # underconstrained line: valid placements number in the
        # trillions; the visited-node cap must refuse quickly
        with self.assertRaises(ValueError):
            b99.nonogram_line_solve([1] * 15, [0] * 128)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b99.nonogram_line_solve(bad, [0, 0])
            with self.assertRaises(ValueError):
                b99.nonogram_line_solve([1], bad)


class TestHenselLiftRoot(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b99.hensel_lift_root([-1, 0, 1], 5, 3, 1), 1)
        self.assertEqual(b99.hensel_lift_root([-1, 0, 1], 5, 3, 4), 124)
        self.assertEqual(b99.hensel_lift_root([-2, 1], 7, 4, 2), 2)

    def test_oracle(self):
        rng = random.Random(992)
        primes = [2, 3, 5, 7, 11, 13, 97, 101]
        checked = 0
        for _ in range(120):
            p = rng.choice(primes)
            deg = rng.randint(1, 4)
            cs = [rng.randint(-9, 9) for _ in range(deg + 1)]
            while cs[-1] == 0:
                cs[-1] = rng.randint(-9, 9)
            roots = [r for r in range(p) if
                     sum(c * r ** i for i, c in enumerate(cs)) % p == 0]
            if not roots:
                continue
            root = rng.choice(roots)
            drv = sum(i * cs[i] * root ** (i - 1)
                      for i in range(1, len(cs))) % p
            k = rng.randint(1, 5)
            if drv == 0:
                with self.assertRaises(ValueError):
                    b99.hensel_lift_root(list(cs), p, k, root)
                continue
            got = b99.hensel_lift_root(list(cs), p, k, root)
            m = p ** k
            self.assertEqual(sum(c * got ** i
                                 for i, c in enumerate(cs)) % m, 0)
            self.assertEqual(got % p, root % p)
            checked += 1
        self.assertGreater(checked, 60)

    def test_refusals(self):
        with self.assertRaises(ValueError):  # not a root
            b99.hensel_lift_root([-1, 0, 1], 5, 2, 2)
        with self.assertRaises(ValueError):  # non-simple root
            b99.hensel_lift_root([-4, 4, -1, 0, 0, 0, 0, 0, 0, 0][:3],
                                 2, 2, 0)
        with self.assertRaises(ValueError):  # composite p
            b99.hensel_lift_root([-1, 0, 1], 9, 2, 1)
        with self.assertRaises(ValueError):  # k over cap
            b99.hensel_lift_root([-1, 0, 1], 5, 33, 1)
        with self.assertRaises(ValueError):  # zero leading coeff
            b99.hensel_lift_root([-1, 0, 1, 0], 5, 2, 1)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b99.hensel_lift_root(bad, 5, 2, 1)
            with self.assertRaises(ValueError):
                b99.hensel_lift_root([-1, 0, 1], bad, 2, 1)


class TestRationalRootsList(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b99.rational_roots_list([-6, 11, -6, 1]),
                         [Fraction(1), Fraction(2), Fraction(3)])
        self.assertEqual(b99.rational_roots_list([-1, 0, 2]), [])
        self.assertEqual(b99.rational_roots_list([4, -4, 1]),
                         [Fraction(2)])
        self.assertEqual(b99.rational_roots_list([0, -1, 2]),
                         [Fraction(0), Fraction(1, 2)])
        self.assertEqual(b99.rational_roots_list([-1, 2]),
                         [Fraction(1, 2)])

    def test_oracle(self):
        rng = random.Random(993)
        for _ in range(150):
            deg = rng.randint(1, 4)
            cs = [rng.randint(-6, 6) for _ in range(deg + 1)]
            while cs[-1] == 0:
                cs[-1] = rng.randint(-6, 6)
            got = b99.rational_roots_list(list(cs))
            # every returned value is a root
            for r in got:
                self.assertEqual(
                    sum(c * r ** i for i, c in enumerate(cs)), 0)
            # every candidate from the theorem that is a root is
            # returned
            cc = list(cs)
            zero_root = cc[0] == 0
            while cc[0] == 0:
                cc = cc[1:]

            def divisors(x):
                x = abs(x)
                return [d for d in range(1, x + 1) if x % d == 0]

            want = set()
            for q in divisors(cc[-1]):
                for p_ in divisors(cc[0]):
                    for sgn in (1, -1):
                        r = Fraction(sgn * p_, q)
                        if sum(c * r ** i
                               for i, c in enumerate(cc)) == 0:
                            want.add(r)
            if zero_root:
                want.add(Fraction(0))
            self.assertEqual(got, sorted(want))

    def test_refusals(self):
        with self.assertRaises(ValueError):  # zero leading coeff
            b99.rational_roots_list([1, 2, 0])
        with self.assertRaises(ValueError):  # degree over cap
            b99.rational_roots_list([1] * 10)
        with self.assertRaises(ValueError):  # coeff over cap
            b99.rational_roots_list([10**6 + 1, 1])
        with self.assertRaises(ValueError):  # too few
            b99.rational_roots_list([5])

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b99.rational_roots_list(bad)
        with self.assertRaises(ValueError):
            b99.rational_roots_list([1, True])


class TestMoveToFrontTransform(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b99.move_to_front_transform([0, 0, 1, 0, 255]),
                         [0, 0, 1, 1, 255])
        self.assertEqual(b99.move_to_front_transform([]), [])
        self.assertEqual(b99.move_to_front_transform([5, 4, 3, 2, 1]),
                         [5, 5, 5, 5, 5])

    def test_oracle(self):
        def oracle(data):
            table = list(range(256))
            out = []
            for v in data:
                i = 0
                while table[i] != v:
                    i += 1
                out.append(i)
                table = [v] + table[:i] + table[i + 1:]
            return out

        rng = random.Random(994)
        for _ in range(200):
            data = [rng.randrange(256)
                    for _ in range(rng.randint(0, 30))]
            self.assertEqual(b99.move_to_front_transform(list(data)),
                             oracle(data))

    def test_inverse_roundtrip(self):
        rng = random.Random(995)
        for _ in range(50):
            data = [rng.randrange(6) for _ in range(40)]
            coded = b99.move_to_front_transform(list(data))
            table = list(range(256))
            back = []
            for idx in coded:
                back.append(table[idx])
                table.insert(0, table.pop(idx))
            self.assertEqual(back, data)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            b99.move_to_front_transform([-1])
        with self.assertRaises(ValueError):
            b99.move_to_front_transform([256])

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b99.move_to_front_transform(bad)
        with self.assertRaises(ValueError):
            b99.move_to_front_transform([True])


class TestConvexPolygonIntersectionArea2(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(
            b99.convex_polygon_intersection_area2(
                [[0, 0], [4, 0], [4, 4], [0, 4]],
                [[2, 2], [6, 2], [6, 6], [2, 6]]), Fraction(8))
        self.assertEqual(
            b99.convex_polygon_intersection_area2(
                [[0, 0], [1, 0], [0, 1]], [[5, 5], [6, 5], [5, 6]]),
            Fraction(0))
        # identical triangles: twice area 1
        self.assertEqual(
            b99.convex_polygon_intersection_area2(
                [[0, 0], [1, 0], [0, 1]], [[0, 0], [1, 0], [0, 1]]),
            Fraction(1))

    def test_oracle(self):
        rng = random.Random(996)

        def cross(o, a, b):
            return ((a[0] - o[0]) * (b[1] - o[1])
                    - (a[1] - o[1]) * (b[0] - o[0]))

        def inside(pt, poly):
            return all(cross(poly[i], poly[(i + 1) % len(poly)], pt)
                       >= 0 for i in range(len(poly)))

        def seg_inter(s1, s2, t1, t2):
            d = ((s2[0] - s1[0]) * (t2[1] - t1[1])
                 - (s2[1] - s1[1]) * (t2[0] - t1[0]))
            if d == 0:
                return None
            f = Fraction((t1[0] - s1[0]) * (t2[1] - t1[1])
                         - (t1[1] - s1[1]) * (t2[0] - t1[0]), d)
            g = Fraction((t1[0] - s1[0]) * (s2[1] - s1[1])
                         - (t1[1] - s1[1]) * (s2[0] - s1[0]), d)
            if 0 <= f <= 1 and 0 <= g <= 1:
                return (s1[0] + f * (s2[0] - s1[0]),
                        s1[1] + f * (s2[1] - s1[1]))
            return None

        for _ in range(40):
            def gen(cx, cy):
                pts = set()
                import math
                for a in sorted(rng.uniform(0, 6.28318)
                                for _ in range(rng.randint(3, 6))):
                    r = rng.randint(1, 6)
                    pts.add((cx + int(r * math.cos(a)),
                             cy + int(r * math.sin(a))))
                h = _hull(pts)
                return h if len(h) >= 3 else None

            a = gen(0, 0)
            b = gen(rng.randint(-4, 4), rng.randint(-4, 4))
            if a is None or b is None:
                continue
            cands = ([p for p in a if inside(p, b)]
                     + [p for p in b if inside(p, a)])
            for i in range(len(a)):
                for j in range(len(b)):
                    pt = seg_inter(a[i], a[(i + 1) % len(a)],
                                   b[j], b[(j + 1) % len(b)])
                    if pt is not None:
                        cands.append(pt)
            hull = _hull(cands) if cands else []
            area2 = Fraction(0)
            for i in range(len(hull)):
                x1, y1 = hull[i]
                x2, y2 = hull[(i + 1) % len(hull)]
                area2 += x1 * y2 - y1 * x2
            want = abs(area2)
            got = b99.convex_polygon_intersection_area2(
                [list(p) for p in a], [list(p) for p in b])
            self.assertEqual(got, want)

    def test_refusals(self):
        tri = [[0, 0], [1, 0], [0, 1]]
        with self.assertRaises(ValueError):
            b99.convex_polygon_intersection_area2(
                [[0, 0], [0, 1], [1, 0]], tri)
        with self.assertRaises(ValueError):
            b99.convex_polygon_intersection_area2(tri, [[0, 0]])

    def test_self_crossing_refuses(self):
        # positive-turn pentagram: local turns and area pass, but
        # the global simplicity check must refuse it
        star = [[0, 3], [-2, -3], [3, 1], [-3, 1], [2, -3]]
        tri = [[0, 0], [10, 0], [0, 10]]
        with self.assertRaises(ValueError):
            b99.convex_polygon_intersection_area2(star, tri)
        with self.assertRaises(ValueError):
            b99.convex_polygon_intersection_area2(tri, star)
        # a second self-crossing: shifted copy of the same star
        star2 = [[x + 20, y + 20] for x, y in star]
        with self.assertRaises(ValueError):
            b99.convex_polygon_intersection_area2(star2, tri)
        # control: a valid convex pentagon still works
        self.assertEqual(
            b99.convex_polygon_intersection_area2(
                [[0, 0], [4, 0], [4, 4], [0, 4]],
                [[1, 1], [3, 1], [4, 2], [3, 3], [1, 3]]),
            Fraction(10))

    def test_nonbool(self):
        tri = [[0, 0], [1, 0], [0, 1]]
        with self.assertRaises(ValueError):
            b99.convex_polygon_intersection_area2(None, tri)


class TestLp2VarMaxExact(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(
            b99.lp_2var_max_exact([1, 1], [[1, 2, 4], [4, 2, 12]], 0,
                                  10),
            [Fraction(10, 3), Fraction(8, 3), Fraction(2, 3)])
        self.assertEqual(
            b99.lp_2var_max_exact([1, 0], [], -2, 5),
            [Fraction(5), Fraction(5), Fraction(-2)])
        self.assertEqual(
            b99.lp_2var_max_exact([2, 1], [[1, 1, 10]], 0, 3),
            [Fraction(9), Fraction(3), Fraction(3)])

    def test_oracle(self):
        rng = random.Random(997)
        for _ in range(100):
            n_rows = rng.randint(0, 4)
            rows = [[rng.randint(-4, 4), rng.randint(-4, 4),
                     rng.randint(-9, 9)] for _ in range(n_rows)]
            for r in rows:
                if r[0] == 0 and r[1] == 0:
                    r[0] = 1
            lo = rng.randint(-4, 0)
            up = rng.randint(1, 5)
            c = [rng.randint(-4, 4), rng.randint(-4, 4)]

            def feas(x, y):
                return all(a * x + bb * y <= r
                           for a, bb, r in rows)

            cands = [(Fraction(lo), Fraction(lo)),
                     (Fraction(lo), Fraction(up)),
                     (Fraction(up), Fraction(lo)),
                     (Fraction(up), Fraction(up))]
            for i in range(len(rows)):
                a1, b1, r1 = rows[i]
                for j in range(i + 1, len(rows)):
                    a2, b2, r2 = rows[j]
                    det = a1 * b2 - a2 * b1
                    if det == 0:
                        continue
                    cands.append((
                        Fraction(r1 * b2 - r2 * b1, det),
                        Fraction(a1 * r2 - a2 * r1, det)))
                if b1 != 0:
                    for xv in (Fraction(lo), Fraction(up)):
                        cands.append((xv, Fraction(r1 - a1 * xv, b1)))
                if a1 != 0:
                    for yv in (Fraction(lo), Fraction(up)):
                        cands.append((Fraction(r1 - b1 * yv, a1), yv))
            best = None
            for x, y in cands:
                if not (Fraction(lo) <= x <= Fraction(up)
                        and Fraction(lo) <= y <= Fraction(up)):
                    continue
                if not feas(x, y):
                    continue
                val = c[0] * x + c[1] * y
                if best is None or val > best[0] or (
                        val == best[0] and (x, y) < (best[1], best[2])):
                    best = (val, x, y)
            if best is None:
                with self.assertRaises(ValueError):
                    b99.lp_2var_max_exact(list(c),
                                          [list(r) for r in rows],
                                          lo, up)
            else:
                got = b99.lp_2var_max_exact(list(c),
                                            [list(r) for r in rows],
                                            lo, up)
                self.assertEqual(got, list(best))
                self.assertTrue(feas(got[1], got[2]))

    def test_refusals(self):
        with self.assertRaises(ValueError):  # infeasible
            b99.lp_2var_max_exact([1, 1], [[1, 0, -1]], 0, 5)
        with self.assertRaises(ValueError):  # lower > upper
            b99.lp_2var_max_exact([1, 1], [], 6, 5)
        with self.assertRaises(ValueError):  # rows over cap
            b99.lp_2var_max_exact([1, 1], [[1, 1, 1]] * 33, 0, 5)
        with self.assertRaises(ValueError):  # bad c shape
            b99.lp_2var_max_exact([1, 1, 1], [], 0, 5)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b99.lp_2var_max_exact(bad, [], 0, 5)


class TestMaximumCycleMean(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(
            b99.maximum_cycle_mean(3, [[0, 1, 1], [1, 2, 2],
                                       [2, 0, 3]]), Fraction(2))
        self.assertEqual(b99.maximum_cycle_mean(2, [[0, 0, 7],
                                                    [0, 1, 1]]),
                         Fraction(7))
        self.assertEqual(
            b99.maximum_cycle_mean(4, [[0, 1, 2], [1, 0, 2], [2, 3, 1],
                                       [3, 2, 5], [1, 2, 0]]),
            Fraction(3))
        self.assertEqual(
            b99.maximum_cycle_mean(2, [[0, 1, 1], [1, 0, 5]]),
            Fraction(3))

    def test_oracle(self):
        rng = random.Random(998)

        def oracle(n, edges):
            adj = [[] for _ in range(n)]
            for u, v, w in edges:
                adj[u].append((v, w))
            best = None

            def dfs(start, cur, total, length, seen):
                nonlocal best
                for v, w in adj[cur]:
                    if v == start:
                        cand = Fraction(total + w, length + 1)
                        if best is None or cand > best:
                            best = cand
                    elif v not in seen and length < n:
                        dfs(start, v, total + w, length + 1,
                            seen | {v})

            for s in range(n):
                dfs(s, s, 0, 0, {s})
            return best

        for _ in range(80):
            n = rng.randint(1, 6)
            edges = []
            for _ in range(rng.randint(0, 8)):
                u, v = rng.randrange(n), rng.randrange(n)
                edges.append([u, v, rng.randint(-9, 9)])
            want = oracle(n, edges)
            if want is None:
                with self.assertRaises(ValueError):
                    b99.maximum_cycle_mean(n, [list(e) for e in edges])
            else:
                self.assertEqual(
                    b99.maximum_cycle_mean(n, [list(e) for e in edges]),
                    want)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            b99.maximum_cycle_mean(3, [[0, 1, 1], [1, 2, 1]])
        with self.assertRaises(ValueError):
            b99.maximum_cycle_mean(65, [])
        with self.assertRaises(ValueError):
            b99.maximum_cycle_mean(2, [[0, 2, 1]])

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b99.maximum_cycle_mean(bad, [])


class TestTreeCentroidFind(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b99.tree_centroid_find(4, [[0, 1], [1, 2],
                                                    [2, 3]]), [1, 2])
        self.assertEqual(
            b99.tree_centroid_find(5, [[0, 1], [0, 2], [0, 3],
                                       [0, 4]]), [0])
        self.assertEqual(b99.tree_centroid_find(1, []), [0])
        self.assertEqual(b99.tree_centroid_find(2, [[0, 1]]), [0, 1])

    def test_oracle(self):
        rng = random.Random(999)

        def oracle(n, edges):
            adj = [[] for _ in range(n)]
            for u, v in edges:
                adj[u].append(v)
                adj[v].append(u)
            best = None
            out = []
            for rm in range(n):
                big = 0
                seen = {rm}
                for s in range(n):
                    if s in seen:
                        continue
                    seen.add(s)
                    stack = [s]
                    comp = 0
                    while stack:
                        x = stack.pop()
                        comp += 1
                        for y in adj[x]:
                            if y not in seen:
                                seen.add(y)
                                stack.append(y)
                    big = max(big, comp)
                if best is None or big < best:
                    best = big
                    out = [rm]
                elif big == best:
                    out.append(rm)
            return out

        for _ in range(100):
            n = rng.randint(1, 12)
            edges = []
            for v in range(1, n):
                edges.append([rng.randrange(v), v])
            rng.shuffle(edges)
            self.assertEqual(
                b99.tree_centroid_find(n, [list(e) for e in edges]),
                oracle(n, edges))

    def test_refusals(self):
        with self.assertRaises(ValueError):  # wrong edge count
            b99.tree_centroid_find(3, [[0, 1]])
        with self.assertRaises(ValueError):  # cycle
            b99.tree_centroid_find(3, [[0, 1], [1, 2], [2, 0]])
        with self.assertRaises(ValueError):  # duplicate edge
            b99.tree_centroid_find(3, [[0, 1], [1, 0], [1, 2]])
        with self.assertRaises(ValueError):  # self loop
            b99.tree_centroid_find(2, [[0, 0]])
        with self.assertRaises(ValueError):  # disconnected
            b99.tree_centroid_find(4, [[0, 1], [1, 2], [3, 3]])
        with self.assertRaises(ValueError):  # out of range
            b99.tree_centroid_find(2, [[0, 5]])

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b99.tree_centroid_find(bad, [])


class TestGeohashEncode(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b99.geohash_encode(42600000, -5600000, 5),
                         "ezs42")
        self.assertEqual(
            b99.geohash_encode(57649110, 10407440, 11), "u4pruydqqvj")
        self.assertEqual(b99.geohash_encode(0, 0, 1), "s")
        self.assertEqual(b99.geohash_encode(0, 0, 12),
                         "s00000000000")

    def test_oracle(self):
        alpha = "0123456789bcdefghjkmnpqrstuvwxyz"

        def decode_cells(hash_):
            lat = [Fraction(-90), Fraction(90)]
            lon = [Fraction(-180), Fraction(180)]
            even = True
            for ch in hash_:
                bits = alpha.index(ch)
                for b in range(4, -1, -1):
                    one = (bits >> b) & 1
                    if even:
                        mid = (lon[0] + lon[1]) / 2
                        lon[one ^ 1] = mid
                    else:
                        mid = (lat[0] + lat[1]) / 2
                        lat[one ^ 1] = mid
                    even = not even
            return lat, lon

        rng = random.Random(1000)
        for _ in range(120):
            lat = rng.randint(-90000000, 90000000)
            lon = rng.randint(-180000000, 180000000)
            ln = rng.randint(1, 12)
            h = b99.geohash_encode(lat, lon, ln)
            self.assertEqual(len(h), ln)
            latc, lonc = decode_cells(h)
            latf = Fraction(lat, 10**6)
            lonf = Fraction(lon, 10**6)
            self.assertTrue(latc[0] <= latf <= latc[1], h)
            self.assertTrue(lonc[0] <= lonf <= lonc[1], h)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            b99.geohash_encode(90000001, 0, 5)
        with self.assertRaises(ValueError):
            b99.geohash_encode(0, -180000001, 5)
        with self.assertRaises(ValueError):
            b99.geohash_encode(0, 0, 13)
        with self.assertRaises(ValueError):
            b99.geohash_encode(0, 0, 0)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b99.geohash_encode(bad, 0, 5)
            with self.assertRaises(ValueError):
                b99.geohash_encode(0, bad, 5)


class TestPellEquationMin(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b99.pell_equation_min(2), [3, 2])
        self.assertEqual(b99.pell_equation_min(3), [2, 1])
        self.assertEqual(b99.pell_equation_min(61),
                         [1766319049, 226153980])
        self.assertEqual(b99.pell_equation_min(109),
                         [158070671986249, 15140424455100])
        self.assertEqual(b99.pell_equation_min(5), [9, 4])

    def test_oracle(self):
        from math import isqrt
        # direct y search confirms minimality for small d
        for d in range(2, 60):
            if isqrt(d) ** 2 == d:
                continue
            x, y = b99.pell_equation_min(d)
            self.assertEqual(x * x - d * y * y, 1)
            yy = 1
            while yy < y:
                xx = isqrt(d * yy * yy + 1)
                self.assertNotEqual(xx * xx, d * yy * yy + 1)
                yy += 1
        # larger d: verify the equation only
        for d in (61, 109, 661, 1021, 1999):
            if isqrt(d) ** 2 == d:
                continue
            x, y = b99.pell_equation_min(d)
            self.assertEqual(x * x - d * y * y, 1)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            b99.pell_equation_min(4)
        with self.assertRaises(ValueError):
            b99.pell_equation_min(0)
        with self.assertRaises(ValueError):
            b99.pell_equation_min(2001)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b99.pell_equation_min(bad)


class TestRegistryKnowsBatch99(unittest.TestCase):
    def test_names(self):
        from app.modules.instinct_doc.p235_concepts_registry import (
            ENTRIES)
        names = [e["name"] for e in ENTRIES]
        for name in ("nonogram_line_solve", "hensel_lift_root",
                     "rational_roots_list", "move_to_front_transform",
                     "convex_polygon_intersection_area2",
                     "lp_2var_max_exact", "maximum_cycle_mean",
                     "tree_centroid_find", "geohash_encode",
                     "pell_equation_min"):
            self.assertIn(name, names)

    def test_count(self):
        from app.modules.instinct_doc.p235_concepts_registry import (
            ENTRIES, IMPLEMENTED_SO_FAR)
        self.assertEqual(len(ENTRIES), 758)
        self.assertEqual(IMPLEMENTED_SO_FAR, 758)


if __name__ == "__main__":
    unittest.main()
