"""P235 batch 95: ten concepts."""
import random
import unittest
from collections import deque
from fractions import Fraction
from itertools import combinations

from app.modules.instinct_doc import p235_concepts_batch95 as m


def refusal(code):
    return "P235:" + code


class TestAvlInsertRotations(unittest.TestCase):
    def test_hand_pins(self):
        self.assertEqual(m.avl_insert_rotations([10, 20, 30]),
                         [["RR", 10]])
        self.assertEqual(m.avl_insert_rotations([30, 20, 10]),
                         [["LL", 30]])
        self.assertEqual(m.avl_insert_rotations([30, 10, 20]),
                         [["LR", 30]])
        self.assertEqual(m.avl_insert_rotations([10, 30, 20]),
                         [["RL", 10]])
        self.assertEqual(m.avl_insert_rotations([1, 2, 3, 4, 5, 6, 7]),
                         [["RR", 1], ["RR", 3], ["RR", 2], ["RR", 5]])
        self.assertEqual(m.avl_insert_rotations([]), [])
        self.assertEqual(m.avl_insert_rotations([5]), [])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.avl_insert_rotations([1, 2, 1])
        self.assertEqual(str(ctx.exception), refusal(
            "avl_insert_rotations:duplicate:keys"))
        with self.assertRaises(ValueError) as ctx:
            m.avl_insert_rotations([True, 2])
        self.assertEqual(str(ctx.exception), refusal(
            "avl_insert_rotations:bad_type:keys[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.avl_insert_rotations([3.5, 2])
        self.assertEqual(str(ctx.exception), refusal(
            "avl_insert_rotations:bad_type:keys[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.avl_insert_rotations([None, 2])
        self.assertEqual(str(ctx.exception), refusal(
            "avl_insert_rotations:bad_type:keys[0]"))

    def test_cap_pins(self):
        self.assertEqual(m.avl_insert_rotations(
            list(range(10000)))[-1], ["RR", 9967])
        with self.assertRaises(ValueError) as ctx:
            m.avl_insert_rotations(list(range(10001)))
        self.assertEqual(str(ctx.exception), refusal(
            "avl_insert_rotations:too_many:keys"))
        self.assertEqual(m.avl_insert_rotations([10**9, -10**9]), [])
        with self.assertRaises(ValueError) as ctx:
            m.avl_insert_rotations([10**9 + 1, 0])
        self.assertEqual(str(ctx.exception), refusal(
            "avl_insert_rotations:too_big:keys[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.avl_insert_rotations([-10**9 - 1, 0])
        self.assertEqual(str(ctx.exception), refusal(
            "avl_insert_rotations:too_big:keys[0]"))

    def test_oracle(self):
        def height(t):
            return 0 if t is None else 1 + max(height(t[1]),
                                             height(t[2]))

        def rot_left(t):
            k, l, r = t
            rk, rl, rr = r
            return (rk, (k, l, rl), rr)

        def rot_right(t):
            k, l, r = t
            lk, ll, lr = l
            return (lk, ll, (k, lr, r))

        def oracle(keys):  # independent oracle: immutable tuples,
            events = []    # heights recomputed from scratch

            def rebalance(t):
                if height(t[1]) - height(t[2]) == 2:
                    if height(t[1][1]) >= height(t[1][2]):
                        events.append(["LL", t[0]])
                        return rot_right(t)
                    events.append(["LR", t[0]])
                    return rot_right((t[0], rot_left(t[1]), t[2]))
                if height(t[2]) - height(t[1]) == 2:
                    if height(t[2][2]) >= height(t[2][1]):
                        events.append(["RR", t[0]])
                        return rot_left(t)
                    events.append(["RL", t[0]])
                    return rot_left((t[0], t[1], rot_right(t[2])))
                return t

            def insert(t, k):
                if t is None:
                    return (k, None, None)
                if k < t[0]:
                    return rebalance((t[0], insert(t[1], k), t[2]))
                return rebalance((t[0], t[1], insert(t[2], k)))

            root = None
            for k in keys:
                root = insert(root, k)
            return events

        rng = random.Random(9502)
        for _ in range(200):
            keys = rng.sample(range(-40, 40), rng.randint(0, 14))
            self.assertEqual(m.avl_insert_rotations(keys),
                             oracle(keys))


class TestChordalCheck(unittest.TestCase):
    def test_canonical(self):
        self.assertTrue(m.chordal_check([[1, 2], [0, 2], [0, 1]]))
        self.assertFalse(m.chordal_check([[1, 2], [0, 3], [0, 3], [1, 2]]))
        self.assertTrue(m.chordal_check([[1], [0, 2], [1]]))
        self.assertTrue(m.chordal_check([[], [], []]))
        self.assertTrue(m.chordal_check([[]]))

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.chordal_check([])
        self.assertEqual(str(ctx.exception), refusal(
            "chordal_check:empty:adj"))
        with self.assertRaises(ValueError) as ctx:
            m.chordal_check([[1], [0, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "chordal_check:duplicate:adj[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.chordal_check([[0]])
        self.assertEqual(str(ctx.exception), refusal(
            "chordal_check:self_loop:adj[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.chordal_check([[1], []])
        self.assertEqual(str(ctx.exception), refusal(
            "chordal_check:asymmetric:adj[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.chordal_check([[1.5], [0]])
        self.assertEqual(str(ctx.exception), refusal(
            "chordal_check:bad_type:adj[0][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.chordal_check("ab")
        self.assertEqual(str(ctx.exception), refusal(
            "chordal_check:bad_type:adj"))

    def test_cap_pins(self):
        self.assertTrue(m.chordal_check([[] for _ in range(10000)]))
        with self.assertRaises(ValueError) as ctx:
            m.chordal_check([[] for _ in range(10001)])
        self.assertEqual(str(ctx.exception), refusal(
            "chordal_check:too_many:adj"))
        full = [[j for j in range(447) if j != i] for i in range(447)]
        self.assertTrue(m.chordal_check(full))  # 199362 entries, at cap
        with self.assertRaises(ValueError) as ctx:
            m.chordal_check([[1] * 10000 for _ in range(21)])
        self.assertEqual(str(ctx.exception), refusal(
            "chordal_check:too_many_edges:adj"))

    def test_oracle(self):
        from itertools import permutations

        def brute_peo(adj):
            # independent oracle: exhaustive search for a perfect
            # elimination ordering
            n = len(adj)
            for perm in permutations(range(n)):
                pos = [0] * n
                for i, v in enumerate(perm):
                    pos[v] = i
                ok = True
                for v in range(n):
                    later = [u for u in adj[v] if pos[u] > pos[v]]
                    for x, u in enumerate(later):
                        for w in later[x + 1:]:
                            if w not in adj[u]:
                                ok = False
                if ok:
                    return True
            return False
        rng = random.Random(9502)
        for _ in range(120):
            n = rng.randint(1, 7)
            adj = [[] for _ in range(n)]
            for a in range(n):
                for b in range(a + 1, n):
                    if rng.random() < 0.4:
                        adj[a].append(b)
                        adj[b].append(a)
            self.assertEqual(m.chordal_check(adj), brute_peo(adj))


class TestBetweennessCentrality(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.betweenness_centrality([[1, 2], [0, 2], [0, 1]]),
                         [Fraction(0)] * 3)
        self.assertEqual(m.betweenness_centrality([[1], [0, 2], [1]]),
                         [Fraction(0), Fraction(1), Fraction(0)])
        self.assertEqual(
            m.betweenness_centrality([[1, 2, 3], [0], [0], [0]]),
            [Fraction(3), Fraction(0), Fraction(0), Fraction(0)])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.betweenness_centrality([[1], []])
        self.assertEqual(str(ctx.exception), refusal(
            "betweenness_centrality:asymmetric:adj[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.betweenness_centrality([[True], [0]])
        self.assertEqual(str(ctx.exception), refusal(
            "betweenness_centrality:bad_type:adj[0][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.betweenness_centrality([[2], [0]])
        self.assertEqual(str(ctx.exception), refusal(
            "betweenness_centrality:out_of_range:adj[0][0]"))

    def test_cap_pins(self):
        star = [list(range(1, 200))] + [[0] for _ in range(199)]
        got = m.betweenness_centrality(star)
        self.assertEqual(got[0], Fraction(199 * 198, 2))
        with self.assertRaises(ValueError) as ctx:
            m.betweenness_centrality([[] for _ in range(201)])
        self.assertEqual(str(ctx.exception), refusal(
            "betweenness_centrality:too_many:adj"))
        with self.assertRaises(ValueError) as ctx:
            # cap fires before any neighbor entry is inspected
            m.betweenness_centrality([[0]] * 201)
        self.assertEqual(str(ctx.exception), refusal(
            "betweenness_centrality:too_many:adj"))

    def test_oracle(self):
        def brute(adj):
            # independent oracle: enumerate shortest paths on the BFS DAG
            # for every ordered pair and count the ones through each node
            n = len(adj)
            cb = [Fraction(0)] * n
            for s in range(n):
                dist = [-1] * n
                dist[s] = 0
                queue = deque([s])
                while queue:
                    v = queue.popleft()
                    for w in adj[v]:
                        if dist[w] < 0:
                            dist[w] = dist[v] + 1
                            queue.append(w)
                for t in range(n):
                    if t == s or dist[t] < 0:
                        continue
                    total = [0]
                    through = [0] * n
                    stack = [(s, 0)]
                    while stack:
                        v, mask = stack.pop()
                        if v == t:
                            total[0] += 1
                            for k in range(n):
                                if mask >> k & 1:
                                    through[k] += 1
                            continue
                        for w in adj[v]:
                            if dist[w] == dist[v] + 1 and \
                                    dist[w] <= dist[t]:
                                stack.append((w, mask | (1 << v)))
                    for k in range(n):
                        if k != s and k != t:
                            cb[k] += Fraction(through[k], total[0])
            return [c / 2 for c in cb]
        rng = random.Random(9503)
        for _ in range(50):
            n = rng.randint(2, 7)
            adj = [[] for _ in range(n)]
            for a in range(n):
                for b in range(a + 1, n):
                    if rng.random() < 0.45:
                        adj[a].append(b)
                        adj[b].append(a)
            self.assertEqual(m.betweenness_centrality(adj), brute(adj))


class TestHilbertCurvePoint(unittest.TestCase):
    def test_hand_pins(self):
        self.assertEqual([m.hilbert_curve_point(1, d) for d in range(4)],
                         [[0, 0], [0, 1], [1, 1], [1, 0]])
        self.assertEqual(m.hilbert_curve_point(2, 0), [0, 0])
        self.assertEqual(m.hilbert_curve_point(2, 5), [0, 3])
        self.assertEqual(m.hilbert_curve_point(2, 15), [3, 0])
        self.assertEqual(m.hilbert_curve_point(5, 1000), [30, 6])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.hilbert_curve_point(True, 0)
        self.assertEqual(str(ctx.exception), refusal(
            "hilbert_curve_point:bad_type:order"))
        with self.assertRaises(ValueError) as ctx:
            m.hilbert_curve_point(3.5, 0)
        self.assertEqual(str(ctx.exception), refusal(
            "hilbert_curve_point:bad_type:order"))
        with self.assertRaises(ValueError) as ctx:
            m.hilbert_curve_point(2, None)
        self.assertEqual(str(ctx.exception), refusal(
            "hilbert_curve_point:bad_type:d"))
        with self.assertRaises(ValueError) as ctx:
            m.hilbert_curve_point(0, 0)
        self.assertEqual(str(ctx.exception), refusal(
            "hilbert_curve_point:out_of_range:order"))
        with self.assertRaises(ValueError) as ctx:
            m.hilbert_curve_point(2, -1)
        self.assertEqual(str(ctx.exception), refusal(
            "hilbert_curve_point:out_of_range:d"))
        with self.assertRaises(ValueError) as ctx:
            m.hilbert_curve_point(2, 16)
        self.assertEqual(str(ctx.exception), refusal(
            "hilbert_curve_point:out_of_range:d"))

    def test_cap_pins(self):
        self.assertEqual(m.hilbert_curve_point(31, 4 ** 31 - 1),
                         [2 ** 31 - 1, 0])
        with self.assertRaises(ValueError) as ctx:
            m.hilbert_curve_point(32, 0)
        self.assertEqual(str(ctx.exception), refusal(
            "hilbert_curve_point:out_of_range:order"))

    def test_oracle(self):
        def xy2d(order, x, y):  # independent oracle: inverse walk
            d = 0
            s = 2 ** (order - 1)
            while s > 0:
                rx = 1 if (x & s) else 0
                ry = 1 if (y & s) else 0
                d += s * s * ((3 * rx) ^ ry)
                if ry == 0:
                    if rx == 1:
                        x = s - 1 - x
                        y = s - 1 - y
                    x, y = y, x
                s //= 2
            return d

        for order in range(1, 6):
            seen = set()
            for d in range(4 ** order):
                x, y = m.hilbert_curve_point(order, d)
                self.assertEqual(xy2d(order, x, y), d)
                seen.add((x, y))
            self.assertEqual(len(seen), 4 ** order)
        rng = random.Random(9503)
        for _ in range(200):  # consecutive indices are unit steps
            order = rng.randint(1, 8)
            d = rng.randrange(4 ** order - 1)
            x1, y1 = m.hilbert_curve_point(order, d)
            x2, y2 = m.hilbert_curve_point(order, d + 1)
            self.assertEqual(abs(x1 - x2) + abs(y1 - y2), 1)


class TestPolylineSimplify(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.polyline_simplify(
            [[0, 0], [1, 0], [2, 0], [3, 1]], 0),
            [[0, 0], [2, 0], [3, 1]])
        self.assertEqual(m.polyline_simplify(
            [[0, 0], [1, 0], [2, 0], [3, 1]], 1), [[0, 0], [3, 1]])
        self.assertEqual(m.polyline_simplify([[1, 1], [9, 9], [1, 1]], 0),
                         [[1, 1], [9, 9], [1, 1]])
        self.assertEqual(m.polyline_simplify([[0, 0], [4, 4]], 0),
                         [[0, 0], [4, 4]])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.polyline_simplify([], 0)
        self.assertEqual(str(ctx.exception), refusal(
            "polyline_simplify:empty:points"))
        with self.assertRaises(ValueError) as ctx:
            m.polyline_simplify([[0, 0], [1]], 0)
        self.assertEqual(str(ctx.exception), refusal(
            "polyline_simplify:bad_point:points[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.polyline_simplify([[0, 0], [1, 2.5]], 0)
        self.assertEqual(str(ctx.exception), refusal(
            "polyline_simplify:bad_type:points[1][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.polyline_simplify([[0, 0]], -1)
        self.assertEqual(str(ctx.exception), refusal(
            "polyline_simplify:out_of_range:epsilon"))
        with self.assertRaises(ValueError) as ctx:
            m.polyline_simplify([[0, 0]], "0")
        self.assertEqual(str(ctx.exception), refusal(
            "polyline_simplify:bad_type:epsilon"))

    def test_cap_pins(self):
        pts = [[i, 0] for i in range(10000)]
        self.assertEqual(m.polyline_simplify(pts, 0), [[0, 0], [9999, 0]])
        with self.assertRaises(ValueError) as ctx:
            m.polyline_simplify([[0, 0]] * 10001, 0)
        self.assertEqual(str(ctx.exception), refusal(
            "polyline_simplify:too_many:points"))

    def test_oracle(self):
        def within(pts, kept, eps):
            # independent oracle: every dropped point must lie within
            # epsilon of some kept segment, endpoints must be kept
            if kept[0] != pts[0] or kept[-1] != pts[-1]:
                return False
            kept_ids = {id(p) for p in kept}
            idx = [i for i, p in enumerate(pts) if id(p) in kept_ids]
            for a, b in zip(idx, idx[1:]):
                x1, y1 = pts[a]
                x2, y2 = pts[b]
                dx = x2 - x1
                dy = y2 - y1
                base2 = dx * dx + dy * dy
                for i in range(a + 1, b):
                    xi, yi = pts[i]
                    if base2 == 0:
                        d2 = (xi - x1) ** 2 + (yi - y1) ** 2
                        if d2 > eps * eps:
                            return False
                    else:
                        cross = abs(dx * (yi - y1) - dy * (xi - x1))
                        if cross * cross > eps * eps * base2:
                            return False
            return True
        rng = random.Random(9505)
        for _ in range(80):
            n = rng.randint(2, 25)
            pts = [[rng.randint(-20, 20), rng.randint(-20, 20)]
                   for _ in range(n)]
            eps = rng.randint(0, 8)
            got = m.polyline_simplify(pts, eps)
            self.assertTrue(within(pts, got, eps))
            self.assertEqual(got, m.polyline_simplify(pts, eps))


class TestGramSchmidtOrthogonal(unittest.TestCase):
    def test_canonical(self):
        got = m.gram_schmidt_orthogonal([[1, 1, 0], [1, 0, 1], [0, 1, 1]])
        self.assertEqual(got, [
            [Fraction(1), Fraction(1), Fraction(0)],
            [Fraction(1, 2), Fraction(-1, 2), Fraction(1)],
            [Fraction(-2, 3), Fraction(2, 3), Fraction(2, 3)]])
        self.assertEqual(m.gram_schmidt_orthogonal(
            [[1, 0], [2, 0], [0, 1]]),
            [[Fraction(1), Fraction(0)], [Fraction(0), Fraction(1)]])
        self.assertEqual(m.gram_schmidt_orthogonal([[0, 0], [3, 4]]),
                         [[Fraction(3), Fraction(4)]])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.gram_schmidt_orthogonal([[1, 2], [3]])
        self.assertEqual(str(ctx.exception), refusal(
            "gram_schmidt_orthogonal:ragged:rows"))
        with self.assertRaises(ValueError) as ctx:
            m.gram_schmidt_orthogonal([[1, None]])
        self.assertEqual(str(ctx.exception), refusal(
            "gram_schmidt_orthogonal:bad_type:rows[0][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.gram_schmidt_orthogonal([])
        self.assertEqual(str(ctx.exception), refusal(
            "gram_schmidt_orthogonal:empty:rows"))

    def test_cap_pins(self):
        ok = [[0] * i + [1] + [0] * (19 - i) for i in range(20)]
        self.assertEqual(len(m.gram_schmidt_orthogonal(ok)), 20)
        with self.assertRaises(ValueError) as ctx:
            m.gram_schmidt_orthogonal([[1]] * 21)
        self.assertEqual(str(ctx.exception), refusal(
            "gram_schmidt_orthogonal:too_many:rows"))
        with self.assertRaises(ValueError) as ctx:
            m.gram_schmidt_orthogonal([[0] * 21])
        self.assertEqual(str(ctx.exception), refusal(
            "gram_schmidt_orthogonal:too_many:rows[0]"))

    def test_oracle(self):
        def rank(rows):
            # independent rank by fraction-free-ish Gaussian elimination
            rows = [[Fraction(v) for v in r] for r in rows]
            rank = 0
            col = 0
            while col < len(rows[0]) and rank < len(rows):
                piv = next((r for r in range(rank, len(rows))
                            if rows[r][col] != 0), None)
                if piv is None:
                    col += 1
                    continue
                rows[rank], rows[piv] = rows[piv], rows[rank]
                for r in range(len(rows)):
                    if r != rank and rows[r][col] != 0:
                        factor = rows[r][col] / rows[rank][col]
                        rows[r] = [x - factor * y
                                   for x, y in zip(rows[r], rows[rank])]
                rank += 1
                col += 1
            return rank
        rng = random.Random(9506)
        for _ in range(60):
            nr = rng.randint(1, 6)
            nc = rng.randint(1, 6)
            rows = [[rng.randint(-5, 5) for _ in range(nc)]
                    for _ in range(nr)]
            basis = m.gram_schmidt_orthogonal(rows)
            for i, u in enumerate(basis):  # pairwise orthogonal
                for v in basis[i + 1:]:
                    self.assertEqual(sum(x * y for x, y in zip(u, v)), 0)
            self.assertEqual(len(basis), rank(rows))
            for row in rows:  # every input row lies in the basis span
                aug = [list(col) for col in zip(*basis)]
                for j, v in enumerate(row):
                    aug[j].append(v)
                self.assertEqual(rank(aug), len(basis))


class TestCribbageScore(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.cribbage_score(["5H", "5C", "5S", "JD"], "5D"),
                         29)
        self.assertEqual(m.cribbage_score(["4H", "5H", "6H", "7H"], "8H"),
                         14)
        self.assertEqual(m.cribbage_score(["AH", "2D", "3C", "9S"], "KC"),
                         7)
        self.assertEqual(m.cribbage_score(["AC", "AD", "AH", "AS"], "KC"),
                         12)
        self.assertEqual(m.cribbage_score(["JH", "5C", "6D", "7S"], "8H"),
                         9)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.cribbage_score(["5H", "5C", "5S"], "5D")
        self.assertEqual(str(ctx.exception), refusal(
            "cribbage_score:bad_count:hand"))
        with self.assertRaises(ValueError) as ctx:
            m.cribbage_score(["5H", "5C", "5S", "JD"], "5H")
        self.assertEqual(str(ctx.exception), refusal(
            "cribbage_score:duplicate:hand,starter"))
        with self.assertRaises(ValueError) as ctx:
            m.cribbage_score(["5H", "5C", "5S", "1D"], "5D")
        self.assertEqual(str(ctx.exception), refusal(
            "cribbage_score:bad_card:hand[3]"))
        with self.assertRaises(ValueError) as ctx:
            m.cribbage_score(["5H", "5C", "5S", True], "5D")
        self.assertEqual(str(ctx.exception), refusal(
            "cribbage_score:bad_type:hand[3]"))
        with self.assertRaises(ValueError) as ctx:
            m.cribbage_score(["5H", "5C", "5S", "JD"], 11)
        self.assertEqual(str(ctx.exception), refusal(
            "cribbage_score:bad_type:starter"))

    def test_oracle(self):
        def brute(hand, starter):
            # independent oracle: exhaustive combination counting
            cards = list(hand) + [starter]
            order = "A23456789TJQK"
            ranks = [order.index(c[0]) + 1 for c in cards]
            values = [min(r, 10) for r in ranks]
            score = 0
            for r in range(2, 6):
                for combo in combinations(values, r):
                    if sum(combo) == 15:
                        score += 2
            for a, b in combinations(ranks, 2):
                if a == b:
                    score += 2
            best = 0
            for r in range(5, 2, -1):
                for combo in combinations(range(5), r):
                    rs = sorted(ranks[i] for i in combo)
                    if rs[-1] - rs[0] == r - 1 and len(set(rs)) == r:
                        # a run only scores when no longer run contains it
                        longer = False
                        for r2 in range(r + 1, 6):
                            for sup in combinations(range(5), r2):
                                if set(combo) < set(sup):
                                    ss = sorted(ranks[i] for i in sup)
                                    if ss[-1] - ss[0] == r2 - 1 and \
                                            len(set(ss)) == r2:
                                        longer = True
                        if not longer:
                            best += r
            score += best
            if len({c[1] for c in hand}) == 1:
                score += 5 if starter[1] == hand[0][1] else 4
            for c in hand:
                if c[0] == "J" and c[1] == starter[1]:
                    score += 1
            return score
        deck = [r + s for r in "A23456789TJQK" for s in "CDHS"]
        rng = random.Random(9507)
        for _ in range(150):
            pick = rng.sample(deck, 5)
            self.assertEqual(m.cribbage_score(pick[:4], pick[4]),
                             brute(pick[:4], pick[4]))


class TestPolynomialDivmodExact(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.polynomial_divmod_exact([1, 0, 0, -1], [-1, 1]),
                         [[Fraction(-1)] * 3, [Fraction(0)]])
        self.assertEqual(m.polynomial_divmod_exact([1, 2, 1], [1, 1]),
                         [[Fraction(1), Fraction(1)], [Fraction(0)]])
        self.assertEqual(m.polynomial_divmod_exact([1, 0, 1], [1, 1]),
                         [[Fraction(-1), Fraction(1)], [Fraction(2)]])
        self.assertEqual(m.polynomial_divmod_exact([3], [1, 1]),
                         [[Fraction(0)], [Fraction(3)]])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.polynomial_divmod_exact([1, 2], [0, 0])
        self.assertEqual(str(ctx.exception), refusal(
            "polynomial_divmod_exact:zero:divisor"))
        with self.assertRaises(ValueError) as ctx:
            m.polynomial_divmod_exact([], [1])
        self.assertEqual(str(ctx.exception), refusal(
            "polynomial_divmod_exact:empty:dividend"))
        with self.assertRaises(ValueError) as ctx:
            m.polynomial_divmod_exact([1, 2.5], [1])
        self.assertEqual(str(ctx.exception), refusal(
            "polynomial_divmod_exact:bad_type:dividend[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.polynomial_divmod_exact([1], [True])
        self.assertEqual(str(ctx.exception), refusal(
            "polynomial_divmod_exact:bad_type:divisor[0]"))

    def test_cap_pins(self):
        big = [0] * 1000 + [1]
        q, r = m.polynomial_divmod_exact(big, [1])
        self.assertEqual(q[-1], 1)
        with self.assertRaises(ValueError) as ctx:
            m.polynomial_divmod_exact([0] * 1001 + [1], [1])
        self.assertEqual(str(ctx.exception), refusal(
            "polynomial_divmod_exact:too_many:dividend"))

    def test_oracle(self):
        def mul(p, q):
            # independent convolution
            out = [Fraction(0)] * (len(p) + len(q) - 1)
            for i, a in enumerate(p):
                for j, b in enumerate(q):
                    out[i + j] += a * b
            while len(out) > 1 and out[-1] == 0:
                out.pop()
            return out
        rng = random.Random(9508)
        for _ in range(60):
            d1 = [rng.randint(-5, 5) for _ in range(rng.randint(1, 8))]
            d2 = [rng.randint(-5, 5) for _ in range(rng.randint(2, 5))]
            if d2[-1] == 0:
                d2[-1] = 1
            q, r = m.polynomial_divmod_exact(d1, d2)
            back = [a + b for a, b in
                    zip(mul(q, [Fraction(c) for c in d2]) + [Fraction(0)] * 9,
                        r + [Fraction(0)] * 9)]
            while len(back) > 1 and back[-1] == 0:
                back.pop()
            want = [Fraction(c) for c in d1]
            while len(want) > 1 and want[-1] == 0:
                want.pop()
            while len(back) < len(want):
                back.append(Fraction(0))
            self.assertEqual(back[:len(want)], want)
            self.assertLess(len(r), len([c for c in d2] ))


class TestGaussianSolveExact(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.gaussian_solve_exact([[2, 1], [1, 3]], [1, 2]),
                         [Fraction(1, 5), Fraction(3, 5)])
        self.assertEqual(m.gaussian_solve_exact([[4]], [8]), [Fraction(2)])
        self.assertEqual(
            m.gaussian_solve_exact([[1, 1, 1], [0, 2, 5], [2, 5, -1]],
                                   [6, -4, 27]),
            [Fraction(5), Fraction(3), Fraction(-2)])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.gaussian_solve_exact([[1, 2], [2, 4]], [1, 2])
        self.assertEqual(str(ctx.exception), refusal(
            "gaussian_solve_exact:singular:a"))
        with self.assertRaises(ValueError) as ctx:
            m.gaussian_solve_exact([[1, 2], [3, 4]], [1])
        self.assertEqual(str(ctx.exception), refusal(
            "gaussian_solve_exact:length_mismatch:a,b"))
        with self.assertRaises(ValueError) as ctx:
            m.gaussian_solve_exact([[1, 2]], [1, 2])
        self.assertEqual(str(ctx.exception), refusal(
            "gaussian_solve_exact:ragged:a"))
        with self.assertRaises(ValueError) as ctx:
            m.gaussian_solve_exact([[3.5]], [1])
        self.assertEqual(str(ctx.exception), refusal(
            "gaussian_solve_exact:bad_type:a[0][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.gaussian_solve_exact([[1]], [None])
        self.assertEqual(str(ctx.exception), refusal(
            "gaussian_solve_exact:bad_type:b[0]"))

    def test_cap_pins(self):
        ident = [[1 if i == j else 0 for j in range(50)]
                 for i in range(50)]
        self.assertEqual(m.gaussian_solve_exact(ident, list(range(50)))[-1],
                         Fraction(49))
        with self.assertRaises(ValueError) as ctx:
            m.gaussian_solve_exact([[0]] * 51, [0] * 51)
        self.assertEqual(str(ctx.exception), refusal(
            "gaussian_solve_exact:too_many:a"))

    def test_oracle(self):
        def rank(a):
            # independent rank by exact Fraction elimination
            rows = [[Fraction(v) for v in row] for row in a]
            n = len(rows)
            rank = 0
            for col in range(n):
                piv = next((r for r in range(rank, n)
                            if rows[r][col] != 0), None)
                if piv is None:
                    continue
                rows[rank], rows[piv] = rows[piv], rows[rank]
                for r in range(n):
                    if r != rank and rows[r][col] != 0:
                        factor = rows[r][col] / rows[rank][col]
                        rows[r] = [x - factor * y
                                   for x, y in zip(rows[r], rows[rank])]
                rank += 1
            return rank
        rng = random.Random(9509)
        for _ in range(50):
            n = rng.randint(1, 5)
            while True:
                a = [[rng.randint(-6, 6) for _ in range(n)]
                     for _ in range(n)]
                if rank(a) == n:  # nonsingular: the solution is unique
                    break
            b = [rng.randint(-6, 6) for _ in range(n)]
            got = m.gaussian_solve_exact(a, b)
            for i in range(n):
                self.assertEqual(
                    sum(Fraction(a[i][j]) * got[j] for j in range(n)),
                    Fraction(b[i]))


class TestViterbiDecode(unittest.TestCase):
    START = [0.6, 0.4]
    TRANS = [[0.7, 0.3], [0.4, 0.6]]
    EMIT = [[0.5, 0.5], [0.1, 0.9]]

    def test_canonical(self):
        self.assertEqual(m.viterbi_decode(self.START, self.TRANS,
                                          self.EMIT, [0, 1, 1]), [0, 1, 1])
        self.assertEqual(m.viterbi_decode([0.5, 0.5], self.TRANS,
                                          self.EMIT, [1]), [1])
        self.assertEqual(m.viterbi_decode([1.0, 0.0],
                                          [[0.5, 0.5], [0.5, 0.5]],
                                          [[1.0, 0.0], [0.0, 1.0]],
                                          [0, 0]), [0, 0])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.viterbi_decode([0.6, 0.5], self.TRANS, self.EMIT, [0])
        self.assertEqual(str(ctx.exception), refusal(
            "viterbi_decode:bad_row:start"))
        with self.assertRaises(ValueError) as ctx:
            m.viterbi_decode(self.START, [[0.7, 0.3]], self.EMIT, [0])
        self.assertEqual(str(ctx.exception), refusal(
            "viterbi_decode:bad_shape:trans"))
        with self.assertRaises(ValueError) as ctx:
            m.viterbi_decode(self.START, [[0.7, 0.4], [0.4, 0.6]],
                             self.EMIT, [0])
        self.assertEqual(str(ctx.exception), refusal(
            "viterbi_decode:bad_row:trans[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.viterbi_decode(self.START, self.TRANS, self.EMIT, [])
        self.assertEqual(str(ctx.exception), refusal(
            "viterbi_decode:empty:observations"))
        with self.assertRaises(ValueError) as ctx:
            m.viterbi_decode(self.START, self.TRANS, self.EMIT, [2])
        self.assertEqual(str(ctx.exception), refusal(
            "viterbi_decode:out_of_range:observations[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.viterbi_decode(self.START, self.TRANS, self.EMIT, [True])
        self.assertEqual(str(ctx.exception), refusal(
            "viterbi_decode:bad_type:observations[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.viterbi_decode(self.START, self.TRANS, self.EMIT, [0.5])
        self.assertEqual(str(ctx.exception), refusal(
            "viterbi_decode:bad_type:observations[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.viterbi_decode([1.2, -0.2], self.TRANS, self.EMIT, [0])
        self.assertEqual(str(ctx.exception), refusal(
            "viterbi_decode:out_of_range:start[0]"))

    def test_cap_pins(self):
        n = 50
        start = [1.0 / n] * n
        trans = [[1.0 / n] * n for _ in range(n)]
        emit = [[1.0, 0.0] for _ in range(n)]
        got = m.viterbi_decode(start, trans, emit, [0] * 1000)
        self.assertEqual(len(got), 1000)
        with self.assertRaises(ValueError) as ctx:
            m.viterbi_decode([1.0] * 51,
                             [[1.0]] * 51, [[1.0]] * 51, [0])
        self.assertEqual(str(ctx.exception), refusal(
            "viterbi_decode:too_many:start"))
        with self.assertRaises(ValueError) as ctx:
            m.viterbi_decode([1.0], [[1.0]], [[1.0]], [0] * 1001)
        self.assertEqual(str(ctx.exception), refusal(
            "viterbi_decode:too_many:observations"))

    def test_oracle(self):
        def brute(start, trans, emit, obs):
            # independent oracle: exact-arithmetic dynamic program
            # carrying full paths, ties kept on the lowest state index
            n = len(start)
            best = [(Fraction(start[s]) * Fraction(emit[s][obs[0]]), [s])
                    for s in range(n)]
            for o in obs[1:]:
                nxt = []
                for s in range(n):
                    score = None
                    path = None
                    for p in range(n):
                        cand = (best[p][0] * Fraction(trans[p][s])
                                * Fraction(emit[s][o]))
                        if score is None or cand > score:
                            score = cand
                            path = best[p][1] + [s]
                    nxt.append((score, path))
                best = nxt
            top = 0
            for s in range(1, n):
                if best[s][0] > best[top][0]:
                    top = s
            return best[top][1]
        rng = random.Random(9510)
        for _ in range(60):
            n = rng.randint(1, 4)
            e = rng.randint(1, 3)
            def row():
                vals = [rng.randint(0, 20) for _ in range(n)]
                if not any(vals):
                    vals[0] = 1
                total = sum(vals)
                return [v / total for v in vals]
            start = row()
            trans = [row() for _ in range(n)]
            def erow():
                vals = [rng.randint(0, 20) for _ in range(e)]
                if not any(vals):
                    vals[0] = 1
                total = sum(vals)
                return [v / total for v in vals]
            emit = [erow() for _ in range(n)]
            obs = [rng.randrange(e) for _ in range(rng.randint(1, 6))]
            self.assertEqual(m.viterbi_decode(start, trans, emit, obs),
                             brute(start, trans, emit, obs))


class TestRegistryKnowsBatch95(unittest.TestCase):
    def test_names(self):
        from app.modules.instinct_doc.p235_concepts_registry import (
            ENTRIES)
        names = [e["name"] for e in ENTRIES]
        for name in ("avl_insert_rotations", "chordal_check",
                     "betweenness_centrality", "hilbert_curve_point",
                     "polyline_simplify", "gram_schmidt_orthogonal",
                     "cribbage_score", "polynomial_divmod_exact",
                     "gaussian_solve_exact", "viterbi_decode"):
            self.assertIn(name, names)
        self.assertEqual(len(ENTRIES), 758)


if __name__ == "__main__":
    unittest.main()
