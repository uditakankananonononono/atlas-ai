"""Tests for P235 concepts batch 97.

Every pin was read off a live run of the module. Randomized
checks compare against independent oracles: Bellman-Ford SSP for
min-cost flow, edge-subset enumeration for Steiner, bounded
brute force for rational reconstruction, distinct endpos sets
for the suffix automaton, the naive line sweep for the convex
hull trick, an empty-flood liberty oracle for Go, exhaustive
matching enumeration for stable roommates, and an area-sum
identity for ear clipping.
"""
import random
import sys
import unittest
from collections import deque
from fractions import Fraction

sys.path.insert(0, "backend")

from app.modules.instinct_doc import p235_concepts_batch97 as b97


def flow_oracle(nodes, edges, s, t, need):
    adj = [[] for _ in range(nodes)]
    for u, v, c, w in edges:
        adj[u].append([v, c, w, len(adj[v])])
        adj[v].append([u, 0, -w, len(adj[u]) - 1])
    sent = 0
    cost = 0
    inf = float("inf")
    while sent < need:
        dist = [inf] * nodes
        dist[s] = 0
        prev = [None] * nodes
        inq = [False] * nodes
        dq = deque([s])
        inq[s] = True
        while dq:
            u = dq.popleft()
            inq[u] = False
            for ei, e in enumerate(adj[u]):
                v, c, w, rev = e
                if c > 0 and dist[u] + w < dist[v]:
                    dist[v] = dist[u] + w
                    prev[v] = (u, ei)
                    if not inq[v]:
                        inq[v] = True
                        dq.append(v)
        if prev[t] is None:
            return "short"
        f = need - sent
        v = t
        while v != s:
            u, ei = prev[v]
            f = min(f, adj[u][ei][1])
            v = u
        v = t
        while v != s:
            u, ei = prev[v]
            adj[u][ei][1] -= f
            adj[v][adj[u][ei][3]][1] += f
            cost += f * adj[u][ei][2]
            v = u
        sent += f
    return cost


def steiner_oracle(nodes, edges, terminals):
    best = [None]
    termset = set(terminals)

    def search(chosen, start):
        seen = {terminals[0]}
        stack = [terminals[0]]
        adj = {}
        for a, b, w in chosen:
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        while stack:
            u = stack.pop()
            for v in adj.get(u, []):
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        if termset <= seen:
            total = sum(w for _, _, w in chosen)
            if best[0] is None or total < best[0]:
                best[0] = total
        for i in range(start, len(edges)):
            search(chosen + [edges[i]], i + 1)

    search([], 0)
    return best[0]


class TestMinCostFlow(unittest.TestCase):
    def test_pin(self):
        self.assertEqual(
            b97.min_cost_flow_value(
                4, [[0, 1, 3, 2], [0, 2, 2, 5], [1, 2, 1, 1],
                    [1, 3, 2, 3], [2, 3, 4, 2]], 0, 3, 5), 29)

    def test_short_flow_refuses(self):
        with self.assertRaises(ValueError):
            b97.min_cost_flow_value(2, [[0, 1, 3, 2]], 0, 1, 5)

    def test_oracle(self):
        rng = random.Random(991)
        for _ in range(60):
            n = rng.randint(2, 7)
            m = rng.randint(1, 10)
            edges = [[rng.randrange(n), rng.randrange(n),
                      rng.randint(1, 6), rng.randint(0, 9)]
                     for _ in range(m)]
            edges = [e for e in edges if e[0] != e[1]]
            if not edges:
                continue
            s, t = 0, n - 1
            need = rng.randint(1, 8)
            want = flow_oracle(n, [list(e) for e in edges], s, t, need)
            if want == "short":
                with self.assertRaises(ValueError):
                    b97.min_cost_flow_value(n, [list(e) for e in edges],
                                            s, t, need)
            else:
                self.assertEqual(
                    b97.min_cost_flow_value(n, [list(e) for e in edges],
                                            s, t, need), want)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b97.min_cost_flow_value(bad, [[0, 1, 1, 1]], 0, 1, 1)

    def test_cap(self):
        with self.assertRaises(ValueError):
            b97.min_cost_flow_value(201, [[0, 1, 1, 1]], 0, 1, 1)


class TestSteinerTree(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(
            b97.steiner_tree_min(3, [[0, 1, 5], [1, 2, 5], [0, 2, 9]],
                                 [0, 1, 2]), 10)
        self.assertEqual(
            b97.steiner_tree_min(4, [[0, 1, 1], [1, 2, 1], [2, 3, 1],
                                     [0, 3, 10]], [0, 2]), 2)

    def test_unreachable_refuses(self):
        with self.assertRaises(ValueError):
            b97.steiner_tree_min(4, [[0, 1, 1], [2, 3, 1]], [0, 2])

    def test_oracle(self):
        rng = random.Random(992)
        for _ in range(40):
            n = rng.randint(2, 6)
            edges = []
            used = set()
            for _ in range(rng.randint(1, 9)):
                a, b = rng.randrange(n), rng.randrange(n)
                key = (min(a, b), max(a, b))
                if a != b and key not in used:
                    used.add(key)
                    edges.append([a, b, rng.randint(1, 9)])
            if not edges:
                continue
            t = rng.randint(1, min(3, n))
            terms = rng.sample(range(n), t)
            want = steiner_oracle(n, edges, terms)
            if want is None:
                with self.assertRaises(ValueError):
                    b97.steiner_tree_min(n, [list(e) for e in edges],
                                         list(terms))
            else:
                self.assertEqual(
                    b97.steiner_tree_min(n, [list(e) for e in edges],
                                         list(terms)), want)

    def test_cap_terminals(self):
        with self.assertRaises(ValueError):
            b97.steiner_tree_min(20, [[0, 1, 1]], list(range(13)))

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b97.steiner_tree_min(bad, [[0, 1, 1]], [0, 1])


class TestEarClipping(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(
            b97.ear_clipping_triangulation(
                [[0, 0], [4, 0], [4, 4], [0, 4]]),
            [[3, 0, 1], [1, 2, 3]])
        self.assertEqual(
            b97.ear_clipping_triangulation(
                [[0, 0], [4, 0], [4, 4], [2, 2], [0, 4]]),
            [[1, 2, 3], [0, 1, 3], [0, 3, 4]])

    def test_area_identity(self):
        import math
        rng = random.Random(993)

        def area2(poly):
            s = 0
            for i in range(len(poly)):
                x1, y1 = poly[i]
                x2, y2 = poly[(i + 1) % len(poly)]
                s += x1 * y2 - x2 * y1
            return s

        for _ in range(40):
            n = rng.randint(3, 9)
            angs = sorted(rng.uniform(0, 6.283) for _ in range(n))
            pts = []
            for a in angs:
                p = [int(50 + 40 * math.cos(a)),
                     int(50 + 40 * math.sin(a))]
                if p not in pts:
                    pts.append(p)
            if len(pts) < 3:
                continue
            tris = b97.ear_clipping_triangulation([list(p) for p in pts])
            self.assertEqual(len(tris), len(pts) - 2)
            total = 0
            for a, b, c in tris:
                total += abs(area2([pts[a], pts[b], pts[c]]))
            self.assertEqual(total, abs(area2(pts)))

    def test_cap(self):
        with self.assertRaises(ValueError):
            b97.ear_clipping_triangulation([[0, 0]] * 501)

    def test_nonbool(self):
        with self.assertRaises(ValueError):
            b97.ear_clipping_triangulation(None)


class TestJsonParse(unittest.TestCase):
    def test_pin(self):
        self.assertEqual(
            b97.json_parse_value('{"a": [1, 2.5, null, true], "b": "x"}'),
            {"a": [1, Fraction(5, 2), None, True], "b": "x"})

    def test_bad_text_refuses(self):
        for bad in ("[1,]", '{"a":1,}', "01", "+1", "1.", ".5", "tru",
                    "[1", '"a', '"a\\x"', '{"a" 1}', "[1 2]", "nan",
                    "1e", "1e+", "-", ""):
            with self.assertRaises(ValueError, msg=repr(bad)):
                b97.json_parse_value(bad)

    def test_stdlib_oracle(self):
        import json
        rng = random.Random(994)

        def gen(d):
            if d == 0 or rng.random() < 0.4:
                return rng.choice([None, True, False,
                                   rng.randint(-99, 99), "x y\n", 'A"\\',
                                   0.5, -2.25, 1e3])
            if rng.random() < 0.5:
                return [gen(d - 1) for _ in range(rng.randint(0, 3))]
            return {"k%d" % i: gen(d - 1)
                    for i in range(rng.randint(0, 3))}

        def conv(o):
            if isinstance(o, float):
                return Fraction(o)
            if isinstance(o, list):
                return [conv(x) for x in o]
            if isinstance(o, dict):
                return {k: conv(v) for k, v in o.items()}
            return o

        for _ in range(150):
            obj = gen(rng.randint(0, 3))
            self.assertEqual(b97.json_parse_value(json.dumps(obj)),
                             conv(obj))

    def test_depth_cap(self):
        with self.assertRaises(ValueError):
            b97.json_parse_value("[" * 65 + "]" * 65)

    def test_nonbool(self):
        for bad in (True, 3.5, None, 7):
            with self.assertRaises(ValueError):
                b97.json_parse_value(bad)


class TestIniParse(unittest.TestCase):
    def test_pin(self):
        self.assertEqual(
            b97.ini_parse_sections("a=1\nb = 2\n[s]\na=3\n[s]\nc=4\n[t]\nx="),
            {"": {"a": "1", "b": "2"}, "s": {"a": "3", "c": "4"},
             "t": {"x": ""}})

    def test_comment_and_dup_key(self):
        out = b97.ini_parse_sections("; hi\n# there\nk=1\nk=2\n")
        self.assertEqual(out, {"": {"k": "2"}})

    def test_bad_line_refuses(self):
        with self.assertRaises(ValueError):
            b97.ini_parse_sections("not a line\n")
        with self.assertRaises(ValueError):
            b97.ini_parse_sections("[unclosed\n")

    def test_nonbool(self):
        for bad in (True, 3.5, None, 7):
            with self.assertRaises(ValueError):
                b97.ini_parse_sections(bad)


class TestRationalReconstruction(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b97.rational_reconstruction(7, 13), [1, 2])
        self.assertEqual(b97.rational_reconstruction(5, 11), [-1, 2])
        self.assertEqual(b97.rational_reconstruction(0, 74), [0, 1])
        self.assertEqual(b97.rational_reconstruction(8, 16), [0, 1])
        self.assertEqual(b97.rational_reconstruction(0, 97), [0, 1])

    def test_oracle(self):
        rng = random.Random(996)

        def brute(x, m):
            q = int((m // 2) ** 0.5)
            while (q + 1) * (q + 1) <= m // 2:
                q += 1
            while q * q > m // 2:
                q -= 1
            found = []
            for a in range(-q, q + 1):
                for b in range(1, q + 1):
                    if 2 * a * b > m:
                        continue
                    if (x * b - a) % m == 0:
                        found.append((a, b))
            return found

        for _ in range(300):
            m = rng.randint(2, 200)
            x = rng.randrange(m)
            found = brute(x, m)
            try:
                got = b97.rational_reconstruction(x, m)
            except ValueError:
                self.assertEqual(found, [], "false refuse x=%d m=%d" % (x, m))
                continue
            self.assertTrue(found, "accepted x=%d m=%d with no witness"
                            % (x, m))
            a, b = got
            # the contract returns lowest terms; the congruence and
            # bounds hold for an unreduced representative, so compare
            # rationals against the brute witnesses
            self.assertTrue(any(Fraction(aa, bb) == Fraction(a, b)
                                for aa, bb in found))

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b97.rational_reconstruction(bad, 11)


class TestSuffixAutomaton(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b97.suffix_automaton_states("abbc"), 6)
        self.assertEqual(b97.suffix_automaton_states("aaaa"), 5)
        self.assertEqual(b97.suffix_automaton_states("abc"), 4)

    def test_endpos_oracle(self):
        # number of distinct endpos sets over all substrings plus the
        # empty-string class equals the DAWG state count
        for n in range(1, 9):
            for bits in range(2 ** n):
                s = "".join("ab"[(bits >> i) & 1] for i in range(n))
                endpos = set()
                for i in range(len(s)):
                    for j in range(i + 1, len(s) + 1):
                        ep = tuple(k for k in range(len(s))
                                   if s.startswith(s[i:j], k - (j - i) + 1)
                                   and k >= j - 1)
                        ends = tuple(k for k in range(len(s))
                                     if k - (j - i) + 1 >= 0 and
                                     s[k - (j - i) + 1:k + 1] == s[i:j])
                        endpos.add(ends)
                self.assertEqual(b97.suffix_automaton_states(s),
                                 len(endpos) + 1, "s=%r" % s)

    def test_empty_refuses(self):
        with self.assertRaises(ValueError):
            b97.suffix_automaton_states("")

    def test_cap(self):
        with self.assertRaises(ValueError):
            b97.suffix_automaton_states("a" * 10001)

    def test_nonbool(self):
        for bad in (True, 3.5, None, 7):
            with self.assertRaises(ValueError):
                b97.suffix_automaton_states(bad)


class TestConvexHullTrick(unittest.TestCase):
    def test_pin(self):
        self.assertEqual(
            b97.convex_hull_trick_min([[1, 0], [-1, 10], [0, 5]],
                                      [-10, 0, 10]), [-10, 0, 0])

    def test_naive_oracle(self):
        rng = random.Random(997)
        for _ in range(200):
            k = rng.randint(1, 6)
            lines = [[rng.randint(-5, 5), rng.randint(-9, 9)]
                     for _ in range(k)]
            qs = [rng.randint(-20, 20) for _ in range(rng.randint(1, 5))]
            want = [min(a * x + b for a, b in lines) for x in qs]
            self.assertEqual(
                b97.convex_hull_trick_min([list(l) for l in lines],
                                          list(qs)), want)

    def test_cap(self):
        with self.assertRaises(ValueError):
            b97.convex_hull_trick_min([[1, 0]] * 10001, [1])

    def test_nonbool(self):
        with self.assertRaises(ValueError):
            b97.convex_hull_trick_min(None, [1])


class TestGoCapture(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(
            b97.go_capture_count([[0, 0, 0], [2, 1, 2], [0, 2, 0]],
                                 [0, 1, 2]), 1)
        self.assertEqual(
            b97.go_capture_count([[0, 2, 0], [2, 1, 0], [0, 0, 0]],
                                 [2, 1, 2]), 0)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            b97.go_capture_count([[0, 0, 0], [2, 1, 2], [0, 0, 0]],
                                 [1, 0, 2])
        with self.assertRaises(ValueError):
            b97.go_capture_count([[0, 1, 0], [1, 0, 1], [0, 1, 0]],
                                 [1, 1, 2])

    def test_flood_oracle(self):
        rng = random.Random(998)

        def oracle(board, move):
            side = len(board)
            r, c, color = move
            if board[r][c] != 0:
                return "occupied"
            b = [row[:] for row in board]
            b[r][c] = color

            def alive(bd):
                out = set()
                stack = []
                for i in range(side):
                    for j in range(side):
                        if bd[i][j] == 0:
                            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                                i2, j2 = i + di, j + dj
                                if (0 <= i2 < side and 0 <= j2 < side
                                        and bd[i2][j2] != 0
                                        and (i2, j2) not in out):
                                    out.add((i2, j2))
                                    stack.append((i2, j2))
                while stack:
                    i, j = stack.pop()
                    col = bd[i][j]
                    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        i2, j2 = i + di, j + dj
                        if (0 <= i2 < side and 0 <= j2 < side
                                and bd[i2][j2] == col
                                and (i2, j2) not in out):
                            out.add((i2, j2))
                            stack.append((i2, j2))
                return out

            foe = 3 - color
            cap = [(i, j) for i in range(side) for j in range(side)
                   if b[i][j] == foe and (i, j) not in alive(b)]
            for i, j in cap:
                b[i][j] = 0
            if (r, c) not in alive(b):
                return "suicide"
            return len(cap)

        for _ in range(120):
            side = rng.randint(2, 5)
            board = [[rng.choice([0, 0, 1, 2]) for _ in range(side)]
                     for _ in range(side)]
            move = [rng.randrange(side), rng.randrange(side),
                    rng.choice([1, 2])]
            want = oracle(board, move)
            if want in ("occupied", "suicide"):
                with self.assertRaises(ValueError):
                    b97.go_capture_count([list(r2) for r2 in board],
                                         list(move))
            else:
                self.assertEqual(
                    b97.go_capture_count([list(r2) for r2 in board],
                                         list(move)), want)

    def test_cap(self):
        with self.assertRaises(ValueError):
            b97.go_capture_count([[0] * 20 for _ in range(20)], [0, 0, 1])

    def test_nonbool(self):
        with self.assertRaises(ValueError):
            b97.go_capture_count(None, [0, 0, 1])


class TestStableRoommates(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(
            b97.stable_roommates_match(
                [[1, 2, 3], [0, 2, 3], [0, 1, 3], [0, 1, 2]]),
            [[0, 1], [2, 3]])
        self.assertEqual(
            b97.stable_roommates_match(
                [[1, 2, 3, 4, 5], [0, 2, 3, 4, 5], [0, 1, 3, 4, 5],
                 [0, 1, 2, 4, 5], [0, 1, 2, 3, 5], [0, 1, 2, 3, 4]]),
            [[0, 1], [2, 3], [4, 5]])

    def test_refusals(self):
        with self.assertRaises(ValueError):
            b97.stable_roommates_match(
                [[1, 2, 3], [2, 0, 3], [0, 1, 3], [0, 1, 2]])
        with self.assertRaises(ValueError):
            b97.stable_roommates_match([[1, 2], [0, 2], [0, 1]])

    def test_brute_oracle(self):
        rng = random.Random(995)

        def brute(prefs):
            n = len(prefs)

            def matchings(people):
                if not people:
                    yield []
                    return
                f = people[0]
                for i in range(1, len(people)):
                    for rest in matchings(people[1:i] + people[i + 1:]):
                        yield [(f, people[i])] + rest

            for mm in matchings(list(range(n))):
                d = {}
                for a, b in mm:
                    d[a] = b
                    d[b] = a
                ok = True
                for a in range(n):
                    for b in prefs[a]:
                        if b == d[a]:
                            break
                        if prefs[b].index(a) < prefs[b].index(d[b]):
                            ok = False
                            break
                    if not ok:
                        break
                if ok:
                    return mm
            return None

        def verify(prefs, pairs):
            d = {}
            for a, b in pairs:
                d[a] = b
                d[b] = a
            if sorted(d) != list(range(len(prefs))):
                return False
            for a in range(len(prefs)):
                for b in prefs[a]:
                    if b == d[a]:
                        break
                    if prefs[b].index(a) < prefs[b].index(d[b]):
                        return False
            return True

        for _ in range(1200):
            n = rng.choice([2, 4, 6, 8])
            prefs = []
            for i in range(n):
                others = [x for x in range(n) if x != i]
                rng.shuffle(others)
                prefs.append(others)
            try:
                got = b97.stable_roommates_match([list(r) for r in prefs])
            except ValueError:
                self.assertIsNone(brute(prefs), "false refuse: %s" % prefs)
                continue
            self.assertTrue(verify(prefs, got), "unstable: %s" % prefs)

    def test_nonbool(self):
        with self.assertRaises(ValueError):
            b97.stable_roommates_match(None)


class TestB97V2Repairs(unittest.TestCase):
    def test_roommates_rotation_regression(self):
        # Regression for the rotation-elimination bug: it dropped only the
        # last entry of each y_i list; Irving drops every entry after
        # x_i. This instance falsely refused before the fix.
        prefs = [[5, 2, 1, 3, 4], [4, 5, 3, 0, 2], [1, 5, 0, 3, 4],
                 [0, 2, 4, 1, 5], [2, 1, 0, 3, 5], [3, 0, 4, 1, 2]]
        self.assertEqual(
            b97.stable_roommates_match([list(r) for r in prefs]),
            [[0, 2], [1, 4], [3, 5]])

    def test_roommates_no_stable_pins(self):
        # Brute-force-verified unsolvable instances (enumeration over
        # all perfect matchings finds none stable).
        unsolvable = [
            [[3, 1, 2], [0, 3, 2], [3, 0, 1], [1, 0, 2]],
            [[3, 5, 2, 4, 1], [5, 0, 3, 2, 4], [1, 5, 0, 4, 3],
             [0, 1, 4, 2, 5], [3, 5, 2, 0, 1], [3, 2, 1, 0, 4]],
        ]
        for prefs in unsolvable:
            with self.assertRaises(ValueError, msg=str(prefs)):
                b97.stable_roommates_match([list(r) for r in prefs])

    def test_roommates_validation(self):
        self.assertEqual(b97.stable_roommates_match([]), [])
        with self.assertRaises(ValueError):  # out-of-range entry
            b97.stable_roommates_match([[1, 4], [0, 1]])
        with self.assertRaises(ValueError):  # self entry
            b97.stable_roommates_match([[1, 0], [0, 1]])
        with self.assertRaises(ValueError):  # repeated entry
            b97.stable_roommates_match([[1, 1], [0, 0]])
        with self.assertRaises(ValueError):  # missing entry
            b97.stable_roommates_match([[1, 2, 3], [0, 2, 3], [0, 1, 3],
                                        [0, 1]])
        with self.assertRaises(ValueError):  # row not a list
            b97.stable_roommates_match([[1, 2, 3], None, [0, 1, 3],
                                        [0, 1, 2]])

    def test_json_number_caps(self):
        # Exponent magnitude capped before Fraction(10) ** exp.
        with self.assertRaises(ValueError):
            b97.json_parse_value("1e9999999")
        with self.assertRaises(ValueError):
            b97.json_parse_value("1e4097")
        with self.assertRaises(ValueError):
            b97.json_parse_value("-2.5e-4097")
        with self.assertRaises(ValueError):
            b97.json_parse_value("1e" + "9" * 5000)
        with self.assertRaises(ValueError):
            b97.json_parse_value("1e" + "0" * 5000 + "1")
        self.assertEqual(b97.json_parse_value("1e4096"),
                         Fraction(10) ** 4096)
        self.assertEqual(b97.json_parse_value("1e0004096"),
                         Fraction(10) ** 4096)
        self.assertEqual(b97.json_parse_value("1e-4096"),
                         Fraction(1, 10) ** 4096)
        # Mantissa digit count capped before int()/Fraction.
        with self.assertRaises(ValueError):
            b97.json_parse_value("1" * 5000)
        with self.assertRaises(ValueError):
            b97.json_parse_value("1" * 1025)
        with self.assertRaises(ValueError):
            b97.json_parse_value("0." + "1" * 1024)
        self.assertEqual(b97.json_parse_value("1" * 1024),
                         int("1" * 1024))
        self.assertEqual(b97.json_parse_value("0." + "1" * 1023),
                         Fraction(int("1" * 1023), 10 ** 1023))

    def test_steiner_new_cap(self):
        edges = [[i, i + 1, 1] for i in range(19)]
        # 8 terminals accepted at the new cap.
        self.assertEqual(
            b97.steiner_tree_min(20, [list(e) for e in edges],
                                 list(range(8))), 7)
        # 9 refuses at the new cap (was 12).
        with self.assertRaises(ValueError):
            b97.steiner_tree_min(20, [list(e) for e in edges],
                                 list(range(9)))

    def test_steiner_validation(self):
        base = [[0, 1, 1], [1, 2, 1]]
        with self.assertRaises(ValueError):  # nodes zero
            b97.steiner_tree_min(0, base, [0, 1])
        with self.assertRaises(ValueError):  # nodes over cap
            b97.steiner_tree_min(201, base, [0, 1])
        with self.assertRaises(ValueError):  # terminal out of range
            b97.steiner_tree_min(3, base, [0, 3])
        with self.assertRaises(ValueError):  # duplicate terminal
            b97.steiner_tree_min(3, base, [0, 0])
        with self.assertRaises(ValueError):  # duplicate edge
            b97.steiner_tree_min(3, base + [[1, 0, 2]], [0, 2])
        with self.assertRaises(ValueError):  # self loop
            b97.steiner_tree_min(3, base + [[1, 1, 2]], [0, 2])
        with self.assertRaises(ValueError):  # zero weight
            b97.steiner_tree_min(3, base + [[0, 2, 0]], [0, 2])
        with self.assertRaises(ValueError):  # weight over MAX_VAL
            b97.steiner_tree_min(3, base + [[0, 2, 10**9 + 1]], [0, 2])
        with self.assertRaises(ValueError):  # bad row shape
            b97.steiner_tree_min(3, base + [[0, 2]], [0, 2])
        with self.assertRaises(ValueError):  # edge endpoint range
            b97.steiner_tree_min(3, base + [[0, 3, 1]], [0, 2])

    def test_rational_reconstruction_m_boundaries(self):
        self.assertEqual(b97.rational_reconstruction(1, 2), [1, 1])
        self.assertEqual(b97.rational_reconstruction(0, 2), [0, 1])
        with self.assertRaises(ValueError):  # m = 1 admits no rational
            b97.rational_reconstruction(0, 1)


if __name__ == "__main__":
    unittest.main()
def _area2(pts):
    n = len(pts)
    return sum(pts[i][0] * pts[(i + 1) % n][1]
               - pts[(i + 1) % n][0] * pts[i][1]
               for i in range(n))


def _tri_area2(pts, tri):
    (a, b, c) = [pts[i] for i in tri]
    return abs((b[0] - a[0]) * (c[1] - a[1])
               - (b[1] - a[1]) * (c[0] - a[0]))


class TestB97V4MustKill(unittest.TestCase):
    def assert_code(self, code, fn, *args):
        with self.assertRaises(ValueError) as ctx:
            fn(*args)
        self.assertIn(code, str(ctx.exception))

    # ear_clipping_triangulation
    PENT = [[0, 0], [6, 0], [6, 6], [3, 2], [0, 6]]

    def test_ear_coordinate_bounds(self):
        f = b97.ear_clipping_triangulation
        self.assert_code("out_of_range:points[1][0]", f,
                         [[0, 0], [10**9 + 1, 0], [0, 1]])
        self.assert_code("out_of_range:points[1][1]", f,
                         [[0, 0], [0, -(10**9 + 1)], [1, 0]])
        self.assert_code("out_of_range:points[0][0]", f,
                         [[-(10**9 + 1), 0], [1, 0], [0, 1]])
        self.assertEqual(f([[0, 0], [10**9, 0], [0, 10**9]]),
                         [[0, 1, 2]])
        self.assertEqual(f([[0, 0], [-10**9, 0], [0, -10**9]]),
                         [[0, 1, 2]])

    def test_ear_area_cover_clockwise_and_reflex(self):
        f = b97.ear_clipping_triangulation
        for pts in (self.PENT,
                    [[0, 0], [0, 6], [3, 2], [6, 6], [6, 0]]):
            tris = f(pts)
            self.assertEqual(len(tris), len(pts) - 2)
            self.assertEqual(
                sum(_tri_area2(pts, t) for t in tris),
                abs(_area2(pts)))

    def test_ear_rejects_hidden_vertex(self):
        # Vertex 0 is the lowest-index convex vertex, but vertex
        # 3 sits strictly inside its ear triangle [4, 0, 1]; the
        # ear test must reject it (and vertex 1, same reason).
        tris = b97.ear_clipping_triangulation(self.PENT)
        self.assertNotIn([4, 0, 1], tris)
        self.assertNotIn([0, 1, 2], tris)
        self.assertEqual(tris, [[1, 2, 3], [0, 1, 3], [0, 3, 4]])

    def test_ear_reflex_guard(self):
        # Vertex 0 is reflex; its neighbors would form a
        # would-be ear [4, 0, 1] that the is_convex guard must
        # reject. The first clipped ear is vertex 1.
        tris = b97.ear_clipping_triangulation(
            [[3, 2], [0, 0], [6, 0], [6, 6], [0, 6]])
        self.assertEqual(tris[0], [0, 1, 2])
        self.assertEqual(tris, [[0, 1, 2], [4, 0, 2], [2, 3, 4]])

    def test_ear_boundary_vertex_rejected(self):
        # Vertex 3 lies exactly on the hypotenuse of vertex 0's
        # ear triangle [4, 0, 1]; inclusive point-in-triangle
        # must reject that ear.
        tris = b97.ear_clipping_triangulation(
            [[0, 0], [6, 0], [6, 6], [3, 3], [0, 6]])
        self.assertNotIn([4, 0, 1], tris)
        self.assertEqual(tris, [[1, 2, 3], [0, 1, 3], [0, 3, 4]])

    def test_ear_unit_triangle(self):
        self.assertEqual(
            b97.ear_clipping_triangulation(
                [[0, 0], [1, 0], [0, 1]]), [[0, 1, 2]])

    def test_ear_not_simple_codes(self):
        f = b97.ear_clipping_triangulation
        # proper crossing (bowtie)
        self.assert_code("ear_clipping_triangulation:not_simple:"
                         "points", f,
                         [[0, 0], [2, 2], [2, 0], [0, 2]])
        # T-touch: endpoint of a non-adjacent edge lands on the
        # interior of the bottom edge
        self.assert_code("ear_clipping_triangulation:not_simple:"
                         "points", f,
                         [[0, 0], [4, 0], [4, 4], [0, 4], [2, 0]])
        # collinear overlap of non-adjacent edges
        self.assert_code("ear_clipping_triangulation:not_simple:"
                         "points", f,
                         [[0, 0], [4, 0], [4, 4], [3, 4],
                          [3, 0], [1, 0], [1, 4], [0, 4]])
        # zero-area collinear polygon
        self.assert_code("ear_clipping_triangulation:degenerate:"
                         "points", f,
                         [[0, 0], [1, 1], [2, 2]])

    # ini_parse_sections
    def test_ini_bad_lines(self):
        f = b97.ini_parse_sections
        self.assert_code("ini_parse_sections:bad_line:text[0]",
                         f, "[]")
        self.assert_code("ini_parse_sections:bad_line:text[0]",
                         f, "[ ]")
        self.assert_code("ini_parse_sections:bad_line:text[0]",
                         f, "=v")
        self.assert_code("ini_parse_sections:bad_line:text[0]",
                         f, "[a")
        self.assert_code("ini_parse_sections:bad_line:text[1]",
                         f, "ok=1\n[]")
        self.assert_code("ini_parse_sections:bad_line:text[2]",
                         f, "[a]\nx=1\n=y")

    def test_ini_leading_entries_vs_comments(self):
        self.assertEqual(
            b97.ini_parse_sections("k=v\n[a]\nx=y"),
            {"": {"k": "v"}, "a": {"x": "y"}})
        self.assertEqual(b97.ini_parse_sections("; c\n# d"), {})

    # rational_reconstruction
    def test_rational_m_bounds(self):
        for bad_m in (0, -1):
            with self.assertRaises(ValueError) as ctx:
                b97.rational_reconstruction(1, bad_m)
            self.assertEqual(
                str(ctx.exception),
                "P235:rational_reconstruction:out_of_range:m")

    # suffix_automaton_states
    def test_sam_cap(self):
        self.assertEqual(
            b97.suffix_automaton_states("a" * 10000), 10001)
        self.assert_code("suffix_automaton_states:too_long:text",
                         b97.suffix_automaton_states,
                         "a" * 10001)

    def test_sam_clone_chains(self):
        # Counts verified against two independent
        # endpos-equivalence brute forces (distinct endpos sets
        # over all substrings + 1) and a second, fresh SAM
        # implementation. abcbc (2 clones), aabab (1) and
        # abcbcabcbc (2) exercise clone creation and kill the
        # never-clone branch mutant; abcabcabc and abababab
        # build zero clones and kill the always-clone and
        # off-by-one branch mutants.
        self.assertEqual(b97.suffix_automaton_states("abcbc"), 8)
        self.assertEqual(b97.suffix_automaton_states("aabab"), 7)
        self.assertEqual(
            b97.suffix_automaton_states("abcabcabc"), 10)
        self.assertEqual(
            b97.suffix_automaton_states("abababab"), 9)
        self.assertEqual(
            b97.suffix_automaton_states("abcbcabcbc"), 13)

    # convex_hull_trick_min
    def test_cht_bounds(self):
        f = b97.convex_hull_trick_min
        self.assert_code("convex_hull_trick_min:empty:lines",
                         f, [], [0])
        self.assert_code("convex_hull_trick_min:out_of_range:"
                         "lines[0][0]", f, [[10**9 + 1, 0]], [0])
        self.assert_code("convex_hull_trick_min:out_of_range:"
                         "lines[0][1]", f,
                         [[0, -(10**9 + 1)]], [0])
        self.assert_code("convex_hull_trick_min:out_of_range:"
                         "queries[0]", f, [[1, 0]], [10**9 + 1])
        self.assert_code("convex_hull_trick_min:out_of_range:"
                         "queries[0]", f, [[1, 0]],
                         [-(10**9 + 1)])
        self.assertEqual(f([[10**9, -10**9]],
                           [10**9, -10**9]),
                         [999999999000000000,
                          -1000000001000000000])

    # go_capture_count
    def test_go_move_bounds(self):
        f = b97.go_capture_count
        board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        for mv in ([-1, 1, 1], [3, 1, 1], [1, -1, 1],
                   [1, 3, 1]):
            self.assert_code("go_capture_count:out_of_range:"
                             "move", f, board, mv)

    def test_go_capture_all_four_directions(self):
        board = [[1, 2, 1], [2, 0, 2], [1, 2, 1]]
        self.assertEqual(b97.go_capture_count(board, [1, 1, 1]),
                         4)

    # min_cost_flow_value boundary pins (not credit-blocking)
    def assert_flow_code(self, code, *args):
        with self.assertRaises(ValueError) as ctx:
            b97.min_cost_flow_value(*args)
        self.assertEqual(str(ctx.exception),
                         "P235:min_cost_flow_value:" + code)

    def test_flow_boundaries(self):
        f = b97.min_cost_flow_value
        self.assert_flow_code("out_of_range:nodes",
                              0, [], 0, 1, 1)
        self.assert_flow_code("out_of_range:nodes",
                              201, [], 0, 1, 1)
        self.assert_flow_code("out_of_range:source,sink",
                              2, [], 2, 1, 1)
        self.assert_flow_code("out_of_range:source,sink",
                              2, [], 0, 2, 1)
        self.assert_flow_code("out_of_range:source,sink",
                              2, [], -1, 1, 1)
        self.assert_flow_code("out_of_range:source,sink",
                              2, [], 0, -1, 1)
        self.assert_flow_code("same_endpoints:source,sink",
                              2, [], 1, 1, 1)
        self.assert_flow_code("out_of_range:amount",
                              2, [], 0, 1, -1)
        self.assert_flow_code("out_of_range:amount",
                              2, [], 0, 1, 10**9 + 1)
        self.assert_flow_code("out_of_range:edges[0]",
                              2, [[0, 2, 1, 1]], 0, 1, 1)
        self.assert_flow_code("out_of_range:edges[0]",
                              2, [[2, 0, 1, 1]], 0, 1, 1)
        self.assert_flow_code("bad_shape:edges[0]",
                              2, [[0, 1, 1]], 0, 1, 1)
        self.assert_flow_code("self_loop:edges[0]",
                              2, [[1, 1, 1, 1]], 0, 1, 1)
        self.assert_flow_code("out_of_range:edges[0]",
                              2, [[0, 1, -1, 1]], 0, 1, 1)
        self.assert_flow_code("out_of_range:edges[0]",
                              2, [[0, 1, 1, -1]], 0, 1, 1)
        self.assert_flow_code("out_of_range:edges[0]",
                              2, [[0, 1, 10**9 + 1, 1]], 0, 1, 1)
        self.assert_flow_code("out_of_range:edges[0]",
                              2, [[0, 1, 1, 10**9 + 1]], 0, 1, 1)
        # amount 0 short-circuits even with an unreachable sink
        self.assertEqual(f(3, [], 0, 2, 0), 0)

    def test_flow_parallel_cheapest(self):
        # parallel cost-0 and cost-5 (2+3) paths: the zero-cost
        # path serves the first unit, the cost-5 path the second
        edges = [[0, 1, 1, 0], [1, 2, 1, 0],
                 [0, 1, 1, 2], [1, 2, 1, 3]]
        self.assertEqual(b97.min_cost_flow_value(3, edges, 0, 2,
                                                 1), 0)
        self.assertEqual(b97.min_cost_flow_value(3, edges, 0, 2,
                                                 2), 5)
class TestB97V6SamRedirect(unittest.TestCase):
    def test_redirect_loop_killers(self):
        # Correction to the v5 report: the claim that redirect-
        # loop mutants are unobservable through the state count
        # was wrong. Redirected transitions are read again by
        # later clone decisions, and these two strings kill the
        # drop-loop, flipped-condition and redirect-to-q
        # mutants (each mutant returns 8 and 16 respectively;
        # the redirect-once mutant returns 15 on the second).
        # Both counts match an endpos-equivalence oracle.
        self.assertEqual(b97.suffix_automaton_states("abbcb"), 7)
        self.assertEqual(
            b97.suffix_automaton_states("aababbbcbb"), 14)
