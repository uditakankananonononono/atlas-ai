"""Tests for P235 concepts batch 98.

Every pin was read off a live run of the module. Randomized
checks compare against independent oracles: standard vectors
for SHA-256, subset enumeration for Stoer-Wagner, the
path-removal definition for dominators, common-simple-cycle
edge co-membership for biconnected blocks, re-traversal for
tree rebuild, repeated addition for elliptic scalar multiply,
first-empty-cell recursion for domino tilings, structural
coverage for de Bruijn, brute scan for the kd-tree, and
subset enumeration for the xor basis.
"""
import itertools
import random
import sys
import unittest
from functools import reduce

sys.path.insert(0, "backend")

from app.modules.instinct_doc import p235_concepts_batch98 as b98


def _trav(t):
    if t is None:
        return [], []
    left_pre, left_in = _trav(t[1])
    right_pre, right_in = _trav(t[2])
    return ([t[0]] + left_pre + right_pre,
            left_in + [t[0]] + right_in)


class TestSha256(unittest.TestCase):
    def test_vectors(self):
        self.assertEqual(
            b98.sha256_digest(""),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991"
            "b7852b855")
        self.assertEqual(
            b98.sha256_digest("abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410f"
            "f61f20015ad")
        self.assertEqual(
            b98.sha256_digest(
                "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomn"
                "opnopq"),
            "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd"
            "419db06c1")

    def test_nonbool(self):
        for bad in (True, 3.5, None, 7):
            with self.assertRaises(ValueError):
                b98.sha256_digest(bad)

    def test_cap_and_encoding(self):
        digest = b98.sha256_digest("a" * 10000)
        self.assertEqual(len(digest), 64)
        with self.assertRaises(ValueError) as ctx:
            b98.sha256_digest("a" * 10001)
        self.assertIn("sha256_digest:too_long:text", str(ctx.exception))
        for bad in ("\ud800", "ok\udc00tail", "\udfff" * 3):
            with self.assertRaises(ValueError) as ctx:
                b98.sha256_digest(bad)
            self.assertIn("sha256_digest:bad_char:text",
                          str(ctx.exception))

    def test_padding_boundaries(self):
        # Message lengths straddling the 56-byte padding point
        # and the 64-byte block size; digests read off the run.
        vectors = {
            55: "9f4390f8d30c2dd92ec9f095b65e2b9ae9b0a925a5258e24"
                "1c9f1e910f734318",
            56: "b35439a4ac6f0948b6d6f9e3c6af0f5f590ce20f1bde70"
                "90ef7970686ec6738a",
            57: "f13b2d724659eb3bf47f2dd6af1accc87b81f09f59f2b75e"
                "5c0bed6589dfe8c6",
            63: "7d3e74a05d7db15bce4ad9ec0658ea98e3f06eeecf16b4c6"
                "fff2da457ddc2f34",
            64: "ffe054fe7ae0cb6dc65c3af9b61d5209f439851db43d0ba5"
                "997337df154668eb",
            65: "635361c48bb9eab14198e76ea8ab7f1a41685d6ad62aa914"
                "6d301d4f17eb0ae0",
        }
        for n, want in vectors.items():
            self.assertEqual(b98.sha256_digest("a" * n), want)


class TestStoerWagner(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(
            b98.stoer_wagner_min_cut(
                4, [[0, 1, 2], [1, 2, 3], [2, 3, 1], [3, 0, 4],
                    [0, 2, 5]]), 5)
        self.assertEqual(b98.stoer_wagner_min_cut(2, [[0, 1, 7]]), 7)
        self.assertEqual(b98.stoer_wagner_min_cut(3, []), 0)

    def test_oracle(self):
        rng = random.Random(981)

        def oracle(n, edges):
            best = None
            for mask in range(0, 1 << (n - 1)):
                S = {0} | {i for i in range(1, n) if mask >> (i - 1) & 1}
                if len(S) == n:
                    continue
                w = sum(w for u, v, w in edges if (u in S) != (v in S))
                if best is None or w < best:
                    best = w
            return best

        for _ in range(100):
            n = rng.randint(2, 7)
            pairs = [(a, b) for a in range(n) for b in range(a + 1, n)]
            rng.shuffle(pairs)
            es = [[a, b, rng.randint(1, 9)]
                  for a, b in pairs[:rng.randint(0, min(10, len(pairs)))]]
            self.assertEqual(
                b98.stoer_wagner_min_cut(n, [list(e) for e in es]),
                oracle(n, es))

    def test_refusals(self):
        with self.assertRaises(ValueError):
            b98.stoer_wagner_min_cut(1, [])
        with self.assertRaises(ValueError):
            b98.stoer_wagner_min_cut(151, [])
        with self.assertRaises(ValueError):
            b98.stoer_wagner_min_cut(3, [[0, 0, 1]])
        with self.assertRaises(ValueError):
            b98.stoer_wagner_min_cut(3, [[0, 1, 1], [1, 0, 2]])
        with self.assertRaises(ValueError):
            b98.stoer_wagner_min_cut(3, [[0, 1, 0]])

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b98.stoer_wagner_min_cut(bad, [])


class TestStoerWagnerRefusals(unittest.TestCase):
    def assert_code(self, code, *args):
        with self.assertRaises(ValueError) as ctx:
            b98.stoer_wagner_min_cut(*args)
        self.assertIn("stoer_wagner_min_cut:" + code,
                      str(ctx.exception))

    def test_nodes_bounds(self):
        for bad in (True, 1.5, None):
            self.assert_code("bad_type:nodes", bad, [])
        self.assert_code("out_of_range:nodes", 1, [])
        self.assert_code("out_of_range:nodes", 151, [])
        self.assertEqual(b98.stoer_wagner_min_cut(2, []), 0)
        self.assertEqual(b98.stoer_wagner_min_cut(150, []), 0)

    def test_edge_rows(self):
        self.assert_code("bad_type:edges", 2, 7)
        self.assert_code("bad_type:edges[0]", 2, [7])
        self.assert_code("bad_shape:edges[0]", 2, [[0, 1]])
        self.assert_code("bad_shape:edges[0]", 2, [[0, 1, 2, 3]])
        self.assert_code("bad_type:edges[0][0]", 2, [[True, 1, 5]])
        self.assert_code("bad_type:edges[0][1]", 2, [[0, 2.5, 5]])
        self.assert_code("bad_type:edges[0][2]", 2, [[0, 1, None]])

    def test_endpoint_and_weight_ranges(self):
        self.assert_code("out_of_range:edges[0]", 2, [[-1, 1, 5]])
        self.assert_code("out_of_range:edges[0]", 2, [[2, 1, 5]])
        self.assert_code("out_of_range:edges[0]", 2, [[0, -1, 5]])
        self.assert_code("out_of_range:edges[0]", 2, [[0, 2, 5]])
        self.assert_code("self_loop:edges[0]", 3, [[1, 1, 5]])
        self.assert_code("out_of_range:edges[0]", 2, [[0, 1, 0]])
        self.assert_code("out_of_range:edges[0]", 2,
                         [[0, 1, 10**9 + 1]])
        self.assertEqual(
            b98.stoer_wagner_min_cut(2, [[0, 1, 10**9]]), 10**9)

    def test_duplicate(self):
        self.assert_code("duplicate:edges[1]", 3,
                         [[0, 1, 5], [1, 0, 7]])
        self.assert_code("duplicate:edges[1]", 3,
                         [[0, 1, 5], [0, 1, 7]])


class TestImmediateDominators(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(
            b98.immediate_dominators(3, [[0, 1], [1, 2]], 0),
            [0, 0, 1])
        self.assertEqual(
            b98.immediate_dominators(
                4, [[0, 1], [0, 2], [1, 3], [2, 3]], 0),
            [0, 0, 0, 0])
        self.assertEqual(
            b98.immediate_dominators(4, [[0, 1], [1, 2]], 3),
            [-1, -1, -1, 3])

    def test_oracle(self):
        rng = random.Random(982)

        def oracle(n, edges, s):
            adj = {}
            for u, v in edges:
                adj.setdefault(u, set()).add(v)

            def reaches(exclude, target):
                if s == exclude:
                    return False
                seen = {s}
                st = [s]
                while st:
                    u = st.pop()
                    for v in adj.get(u, ()):
                        if v != exclude and v not in seen:
                            seen.add(v)
                            st.append(v)
                return target in seen

            seen = {s}
            st = [s]
            while st:
                u = st.pop()
                for v in adj.get(u, ()):
                    if v not in seen:
                        seen.add(v)
                        st.append(v)
            reach = seen
            out = [-1] * n
            out[s] = s
            for b in reach:
                if b == s:
                    continue
                strict = [d for d in reach
                          if d != b and not reaches(d, b)]
                idom = [d for d in strict
                        if all(o == d or not reaches(o, d)
                               for o in strict)]
                out[b] = idom[0] if len(idom) == 1 else -99
            return out

        for _ in range(200):
            n = rng.randint(1, 8)
            es = [[rng.randrange(n), rng.randrange(n)]
                  for _ in range(rng.randint(0, 12))]
            s = rng.randrange(n)
            self.assertEqual(
                b98.immediate_dominators(n, [list(e) for e in es], s),
                oracle(n, es, s))

    def test_refusals(self):
        with self.assertRaises(ValueError):
            b98.immediate_dominators(0, [], 0)
        with self.assertRaises(ValueError):
            b98.immediate_dominators(3, [], 3)
        with self.assertRaises(ValueError):
            b98.immediate_dominators(3, [[0, 1, 2]], 0)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b98.immediate_dominators(bad, [], 0)


class TestImmediateDominatorsRefusals(unittest.TestCase):
    def assert_code(self, code, *args):
        with self.assertRaises(ValueError) as ctx:
            b98.immediate_dominators(*args)
        self.assertIn("immediate_dominators:" + code,
                      str(ctx.exception))

    def test_nodes_and_source_bounds(self):
        for bad in (True, 1.5, None):
            self.assert_code("bad_type:nodes", bad, [], 0)
        self.assert_code("out_of_range:nodes", 0, [], 0)
        self.assert_code("out_of_range:nodes", 201, [], 0)
        self.assertEqual(b98.immediate_dominators(1, [], 0), [0])
        self.assertEqual(b98.immediate_dominators(200, [], 0),
                         [0] + [-1] * 199)
        self.assert_code("bad_type:source", 2, [], True)
        self.assert_code("bad_type:source", 2, [], 0.5)
        self.assert_code("out_of_range:source", 2, [], -1)
        self.assert_code("out_of_range:source", 2, [], 2)

    def test_edge_rows(self):
        self.assert_code("bad_type:edges", 2, 7, 0)
        self.assert_code("bad_type:edges[0]", 2, [7], 0)
        self.assert_code("bad_shape:edges[0]", 2, [[0]], 0)
        self.assert_code("bad_shape:edges[0]", 2, [[0, 1, 2]], 0)
        self.assert_code("bad_type:edges[0][0]", 2, [[True, 1]], 0)
        self.assert_code("bad_type:edges[0][1]", 2, [[0, "1"]], 0)
        self.assert_code("out_of_range:edges[0]", 2, [[-1, 1]], 0)
        self.assert_code("out_of_range:edges[0]", 2, [[2, 1]], 0)
        self.assert_code("out_of_range:edges[0]", 2, [[0, -1]], 0)
        self.assert_code("out_of_range:edges[0]", 2, [[0, 2]], 0)

    def test_self_loops_and_parallels_dropped(self):
        self.assertEqual(
            b98.immediate_dominators(2, [[0, 0], [0, 1], [0, 1]],
                                     0), [0, 0])


class TestBiconnectedBlocks(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(
            b98.biconnected_blocks(4, [[0, 1], [1, 2], [2, 0], [2, 3]]),
            [[[0, 1], [0, 2], [1, 2]], [[2, 3]]])
        self.assertEqual(
            b98.biconnected_blocks(
                5, [[0, 1], [1, 2], [2, 0], [2, 3], [3, 4]]),
            [[[0, 1], [0, 2], [1, 2]], [[2, 3]], [[3, 4]]])
        self.assertEqual(b98.biconnected_blocks(3, []), [])

    def test_oracle(self):
        rng = random.Random(983)

        def oracle(n, edges):
            E = [tuple(sorted(e)) for e in edges]
            adj = {}
            for u, v in E:
                adj.setdefault(u, []).append(v)
                adj.setdefault(v, []).append(u)

            def common_cycle(e1, e2):
                found = [False]

                def paths(u, target, banned, path):
                    if found[0]:
                        return
                    if u == target:
                        seq = {tuple(sorted(x))
                               for x in zip(path, path[1:])}
                        if e2 in seq:
                            found[0] = True
                        return
                    for w in adj.get(u, []):
                        e = (min(u, w), max(u, w))
                        if e == banned or w in path:
                            continue
                        paths(w, target, banned, path + [w])

                paths(e1[0], e1[1], e1, [e1[0]])
                return found[0]

            parent = {e: e for e in E}

            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            for i, e1 in enumerate(E):
                for e2 in E[i + 1:]:
                    if common_cycle(e1, e2):
                        parent[find(e1)] = find(e2)
            groups = {}
            for e in E:
                groups.setdefault(find(e), []).append(list(e))
            return sorted(sorted(g) for g in groups.values())

        for _ in range(120):
            n = rng.randint(1, 7)
            pairs = [(a, b) for a in range(n) for b in range(a + 1, n)]
            rng.shuffle(pairs)
            es = [list(p) for p in
                  pairs[:rng.randint(0, min(9, len(pairs)))]]
            self.assertEqual(
                b98.biconnected_blocks(n, [list(e) for e in es]),
                oracle(n, es))

    def test_refusals(self):
        with self.assertRaises(ValueError):
            b98.biconnected_blocks(0, [])
        with self.assertRaises(ValueError):
            b98.biconnected_blocks(151, [])
        with self.assertRaises(ValueError):
            b98.biconnected_blocks(3, [[0, 0]])
        with self.assertRaises(ValueError):
            b98.biconnected_blocks(3, [[0, 1], [1, 0]])

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b98.biconnected_blocks(bad, [])


class TestRebuildTree(unittest.TestCase):
    def test_pin(self):
        self.assertEqual(
            b98.rebuild_tree_pre_in([3, 9, 20, 15, 7],
                                    [9, 3, 15, 20, 7]),
            [3, [9, None, None], [20, [15, None, None],
                                  [7, None, None]]])
        self.assertEqual(b98.rebuild_tree_pre_in([], []), None)

    def test_oracle(self):
        rng = random.Random(984)

        def trav(t):
            if t is None:
                return [], []
            l1, l2 = trav(t[1])
            r1, r2 = trav(t[2])
            return [t[0]] + l1 + r1, l2 + [t[0]] + r2

        for _ in range(150):
            n = rng.randint(0, 9)
            vals = rng.sample(range(100), n)
            rng.shuffle(vals)

            def rnd(vs):
                if not vs:
                    return None
                i = rng.randrange(len(vs))
                return [vs[i], rnd(vs[:i]), rnd(vs[i + 1:])]

            t = rnd(vals)
            pre, inorder = trav(t)
            self.assertEqual(b98.rebuild_tree_pre_in(pre, inorder), t)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            b98.rebuild_tree_pre_in([1, 2], [1])
        with self.assertRaises(ValueError):
            b98.rebuild_tree_pre_in([1, 2], [2, 2])
        with self.assertRaises(ValueError):
            b98.rebuild_tree_pre_in([1, 2], [1, 3])

    def test_nonbool(self):
        with self.assertRaises(ValueError):
            b98.rebuild_tree_pre_in(None, [])

    def test_inconsistent_refusal(self):
        with self.assertRaises(ValueError) as ctx:
            b98.rebuild_tree_pre_in([1, 2, 3], [3, 1, 2])
        self.assertIn("rebuild_tree_pre_in:mismatch:preorder,inorder",
                      str(ctx.exception))

    def test_inconsistent_sweep(self):
        # Every (preorder, inorder) permutation pair for n <= 5:
        # consistent pairs (n! * Catalan(n) = 5412 of 15018) must
        # rebuild a tree whose traversals match; the other 9606
        # must refuse with the coded ValueError.
        checked = refused = 0
        for n in range(6):
            perms = [list(p) for p in
                     itertools.permutations(range(n))]
            for pre in perms:
                for ino in perms:
                    try:
                        t = b98.rebuild_tree_pre_in(pre, ino)
                    except ValueError as exc:
                        self.assertIn("rebuild_tree_pre_in:",
                                      str(exc))
                        refused += 1
                        continue
                    self.assertEqual(_trav(t), (pre, ino))
                    checked += 1
        self.assertEqual(checked, 5412)
        self.assertEqual(refused, 9606)

    def test_skewed_no_recursion_limit(self):
        for n in (3000, 10000):
            vals = list(range(n))
            t = b98.rebuild_tree_pre_in(vals, list(vals))
            depth = 0
            while t is not None:
                self.assertIsNone(t[1])
                self.assertEqual(t[0], depth)
                depth += 1
                t = t[2]
            self.assertEqual(depth, n)


class TestBiconnectedRefusals(unittest.TestCase):
    def assert_code(self, code, *args):
        with self.assertRaises(ValueError) as ctx:
            b98.biconnected_blocks(*args)
        self.assertIn("biconnected_blocks:" + code,
                      str(ctx.exception))

    def test_nodes_bounds(self):
        for bad in (True, 1.5, None):
            self.assert_code("bad_type:nodes", bad, [])
        self.assert_code("out_of_range:nodes", 0, [])
        self.assert_code("out_of_range:nodes", 151, [])
        self.assertEqual(b98.biconnected_blocks(150, []), [])

    def test_edge_rows(self):
        self.assert_code("bad_type:edges", 2, 7)
        self.assert_code("bad_type:edges[0]", 2, [7])
        self.assert_code("bad_shape:edges[0]", 2, [[0]])
        self.assert_code("bad_shape:edges[0]", 2, [[0, 1, 2]])
        self.assert_code("bad_type:edges[0][0]", 2, [[True, 1]])
        self.assert_code("bad_type:edges[0][1]", 2, [[0, 1.5]])
        self.assert_code("out_of_range:edges[0]", 2, [[-1, 1]])
        self.assert_code("out_of_range:edges[0]", 2, [[2, 1]])
        self.assert_code("out_of_range:edges[0]", 2, [[0, -1]])
        self.assert_code("out_of_range:edges[0]", 2, [[0, 2]])
        self.assert_code("self_loop:edges[0]", 2, [[1, 1]])
        self.assert_code("duplicate:edges[1]", 3,
                         [[0, 1], [1, 0]])
        self.assert_code("duplicate:edges[1]", 3,
                         [[0, 1], [0, 1]])


class TestRebuildRefusalCodes(unittest.TestCase):
    def assert_code(self, code, pre, ino):
        with self.assertRaises(ValueError) as ctx:
            b98.rebuild_tree_pre_in(pre, ino)
        self.assertIn("rebuild_tree_pre_in:" + code,
                      str(ctx.exception))

    def test_codes(self):
        self.assert_code("bad_type:preorder", None, [])
        self.assert_code("bad_type:inorder", [], None)
        self.assert_code("bad_type:preorder[0]", [True], [True])
        self.assert_code("bad_type:inorder[0]", [1], [1.5])
        self.assert_code("mismatch:preorder,inorder", [1, 2], [1])
        self.assert_code("duplicate:inorder[1]", [1, 2], [2, 2])
        self.assert_code("mismatch:preorder,inorder", [1, 2],
                         [1, 3])
        self.assert_code("mismatch:preorder,inorder",
                         [1, 2, 3], [3, 1, 2])


class TestEcPointMultiply(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b98.ec_point_multiply(23, 1, 1, 3, 10, 2),
                         [7, 12])
        self.assertEqual(b98.ec_point_multiply(23, 1, 1, 3, 10, 21),
                         [11, 20])
        self.assertIsNone(b98.ec_point_multiply(23, 1, 1, 3, 10, 28))
        self.assertIsNone(b98.ec_point_multiply(23, 1, 1, 3, 10, 0))

    def test_oracle(self):
        def oracle(p, a, b, gx, gy, k):
            def add(p1, p2):
                if p1 is None:
                    return p2
                if p2 is None:
                    return p1
                x1, y1 = p1
                x2, y2 = p2
                if x1 == x2:
                    if (y1 + y2) % p == 0:
                        return None
                    lam = (3 * x1 * x1 + a) * pow(2 * y1 % p, p - 2, p) % p
                else:
                    lam = ((y2 - y1)
                           * pow((x2 - x1) % p, p - 2, p)) % p
                x3 = (lam * lam - x1 - x2) % p
                return (x3, (lam * (x1 - x3) - y1) % p)

            r = None
            for _ in range(k):
                r = add(r, (gx, gy))
            return None if r is None else [r[0], r[1]]

        for p, a, b, g in [(23, 1, 1, (3, 10)), (97, 2, 3, (3, 6)),
                           (17, 2, 2, (5, 1))]:
            for k in range(0, 30):
                self.assertEqual(b98.ec_point_multiply(p, a, b,
                                                       g[0], g[1], k),
                                 oracle(p, a, b, g[0], g[1], k))

    def test_refusals(self):
        with self.assertRaises(ValueError):
            b98.ec_point_multiply(4, 1, 1, 3, 10, 2)
        with self.assertRaises(ValueError):
            b98.ec_point_multiply(9, 1, 1, 3, 10, 2)
        with self.assertRaises(ValueError):
            b98.ec_point_multiply(17, 0, 0, 1, 1, 2)
        with self.assertRaises(ValueError):
            b98.ec_point_multiply(23, 1, 1, 0, 0, 2)
        with self.assertRaises(ValueError):
            b98.ec_point_multiply(23, 1, 1, 3, 10, -1)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b98.ec_point_multiply(bad, 1, 1, 3, 10, 2)


class TestDominoTiling(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b98.domino_tiling_count(2, 3), 3)
        self.assertEqual(b98.domino_tiling_count(4, 4), 36)
        self.assertEqual(b98.domino_tiling_count(8, 8), 12988816)
        self.assertEqual(b98.domino_tiling_count(3, 3), 0)
        self.assertEqual(b98.domino_tiling_count(1, 4), 1)

    def test_oracle(self):
        def oracle(r, c):
            from functools import lru_cache
            cells = r * c

            @lru_cache(maxsize=None)
            def rec(filled):
                if filled == (1 << cells) - 1:
                    return 1
                i = next(i for i in range(cells)
                         if not filled >> i & 1)
                total = 0
                x, y = i % c, i // c
                for dx, dy in ((1, 0), (0, 1)):
                    nx, ny = x + dx, y + dy
                    if nx < c and ny < r:
                        j = ny * c + nx
                        if not filled >> j & 1:
                            total += rec(filled | (1 << i) | (1 << j))
                return total

            return rec(0)

        for r in range(1, 5):
            for c in range(1, 5):
                self.assertEqual(b98.domino_tiling_count(r, c),
                                 oracle(r, c))

    def test_refusals(self):
        with self.assertRaises(ValueError):
            b98.domino_tiling_count(0, 4)
        with self.assertRaises(ValueError):
            b98.domino_tiling_count(9, 8)

    def test_transpose_and_odd(self):
        # Count is invariant under grid transposition and zero on
        # every odd-cell grid.
        self.assertEqual(b98.domino_tiling_count(3, 4),
                         b98.domino_tiling_count(4, 3))
        self.assertEqual(b98.domino_tiling_count(3, 4), 11)
        self.assertEqual(b98.domino_tiling_count(4, 5),
                         b98.domino_tiling_count(5, 4))
        self.assertEqual(b98.domino_tiling_count(4, 5), 95)
        for r, c in ((1, 1), (1, 3), (3, 5), (5, 3), (1, 7)):
            self.assertEqual(b98.domino_tiling_count(r, c), 0)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b98.domino_tiling_count(bad, 4)


class TestDeBruijn(unittest.TestCase):
    def test_pin(self):
        self.assertEqual(b98.de_bruijn_sequence(2, 3),
                         [0, 0, 0, 1, 0, 1, 1, 1])
        self.assertEqual(b98.de_bruijn_sequence(1, 4), [0])

    def test_oracle(self):
        for k, n in [(2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (3, 2),
                     (3, 3), (4, 2), (5, 2)]:
            s = b98.de_bruijn_sequence(k, n)
            self.assertEqual(len(s), k ** n)
            seen = set()
            for i in range(len(s)):
                seen.add(tuple(s[(i + j) % len(s)] for j in range(n)))
            self.assertEqual(len(seen), k ** n,
                             "coverage failed k=%d n=%d" % (k, n))

    def test_refusals(self):
        with self.assertRaises(ValueError):
            b98.de_bruijn_sequence(0, 3)
        with self.assertRaises(ValueError):
            b98.de_bruijn_sequence(2, 0)
        with self.assertRaises(ValueError):
            b98.de_bruijn_sequence(2, 14)

    def test_single_symbol(self):
        # Over one symbol the only Lyndon word is "0" of length 1,
        # which divides every n, so the sequence is always [0].
        for n in (1, 2, 7, 64):
            self.assertEqual(b98.de_bruijn_sequence(1, n), [0])

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b98.de_bruijn_sequence(bad, 3)


class TestBinPackingFfd(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b98.bin_packing_ffd([4, 8, 1, 4, 2, 1], 10), 2)
        self.assertEqual(b98.bin_packing_ffd([2, 5, 4, 7, 1, 3, 8], 10), 3)
        self.assertEqual(b98.bin_packing_ffd([], 7), 0)
        self.assertEqual(b98.bin_packing_ffd([5], 5), 1)
        # FFD is a heuristic; the pinned value is the FFD result.
        self.assertEqual(b98.bin_packing_ffd([4, 4, 3, 3, 2, 2], 8), 3)

    def test_oracle(self):
        def oracle(items, capacity):
            bins = []
            for v in sorted(items, reverse=True):
                for b in bins:
                    if sum(b) + v <= capacity:
                        b.append(v)
                        break
                else:
                    bins.append([v])
            return len(bins)

        rng = random.Random(986)
        for _ in range(300):
            cap = rng.randint(1, 30)
            items = [rng.randint(1, cap)
                     for _ in range(rng.randint(0, 20))]
            got = b98.bin_packing_ffd(list(items), cap)
            self.assertEqual(got, oracle(items, cap))
            need = -(-sum(items) // cap) if items else 0
            self.assertGreaterEqual(got, need)
            self.assertLessEqual(got, len(items))

    def test_refusals(self):
        with self.assertRaises(ValueError):
            b98.bin_packing_ffd([1], 0)
        with self.assertRaises(ValueError):
            b98.bin_packing_ffd([0], 5)
        with self.assertRaises(ValueError):
            b98.bin_packing_ffd([6], 5)
        with self.assertRaises(ValueError):
            b98.bin_packing_ffd([1], 10**9 + 1)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b98.bin_packing_ffd(bad, 5)
            with self.assertRaises(ValueError):
                b98.bin_packing_ffd([1], bad)


class TestXorBasisMax(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b98.xor_basis_max([3, 5, 6]), 6)
        self.assertEqual(b98.xor_basis_max([1, 2, 4]), 7)
        self.assertEqual(b98.xor_basis_max([]), 0)
        self.assertEqual(b98.xor_basis_max([0, 0]), 0)

    def test_oracle(self):
        rng = random.Random(986)
        for _ in range(200):
            vs = [rng.randint(0, 100)
                  for _ in range(rng.randint(0, 14))]
            want = 0
            for r in range(1, len(vs) + 1):
                for c in itertools.combinations(vs, r):
                    want = max(want, reduce(int.__xor__, c, 0))
            self.assertEqual(b98.xor_basis_max(list(vs)), want)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            b98.xor_basis_max([-1])
        with self.assertRaises(ValueError):
            b98.xor_basis_max([10**9 + 1])

    def test_nonbool(self):
        with self.assertRaises(ValueError):
            b98.xor_basis_max(None)


class TestB98V2Caps(unittest.TestCase):
    def test_de_bruijn_n_cap(self):
        with self.assertRaises(ValueError):
            b98.de_bruijn_sequence(1, 10**30)
        with self.assertRaises(ValueError):
            b98.de_bruijn_sequence(2, 65)
        with self.assertRaises(ValueError):
            b98.de_bruijn_sequence(2, 14)
        self.assertEqual(len(b98.de_bruijn_sequence(2, 13)), 8192)

    def test_ec_magnitude_caps(self):
        with self.assertRaises(ValueError):
            b98.ec_point_multiply(23, 10**9 + 1, 1, 3, 10, 2)
        with self.assertRaises(ValueError):
            b98.ec_point_multiply(23, 1, -(10**9 + 1), 3, 10, 2)
        with self.assertRaises(ValueError):
            b98.ec_point_multiply(23, 1, 1, 10**9 + 1, 10, 2)
        with self.assertRaises(ValueError):
            b98.ec_point_multiply(23, 1, 1, 3, -(10**9 + 1), 2)

    def test_tiling_dimension_caps(self):
        with self.assertRaises(ValueError):
            b98.domino_tiling_count(10**30, 10**30)
        with self.assertRaises(ValueError):
            b98.domino_tiling_count(65, 1)
        with self.assertRaises(ValueError):
            b98.domino_tiling_count(1, 65)
        self.assertEqual(b98.domino_tiling_count(64, 1), 1)




if __name__ == "__main__":
    unittest.main()
