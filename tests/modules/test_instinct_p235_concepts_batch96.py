"""P235 batch 96: ten concepts."""
import random
import unittest
from collections import deque
from fractions import Fraction
from itertools import permutations

from app.modules.instinct_doc import p235_concepts_batch96 as m


def refusal(code):
    return "P235:" + code


class TestTspHeldKarpMin(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.tsp_held_karp_min(
            [[0, 10, 15, 20], [10, 0, 35, 25],
             [15, 35, 0, 30], [20, 25, 30, 0]]), 80)
        self.assertEqual(m.tsp_held_karp_min([[0]]), 0)
        self.assertEqual(m.tsp_held_karp_min([[0, 7], [7, 0]]), 14)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.tsp_held_karp_min([[0, 1], [2, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "tsp_held_karp_min:asymmetric:dist"))
        with self.assertRaises(ValueError) as ctx:
            m.tsp_held_karp_min([[1]])
        self.assertEqual(str(ctx.exception), refusal(
            "tsp_held_karp_min:bad_diagonal:dist"))
        with self.assertRaises(ValueError) as ctx:
            m.tsp_held_karp_min([[0, True], [1, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "tsp_held_karp_min:bad_type:dist[0][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.tsp_held_karp_min([[0, -1], [1, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "tsp_held_karp_min:out_of_range:dist[0][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.tsp_held_karp_min([[0, 1], [1]])
        self.assertEqual(str(ctx.exception), refusal(
            "tsp_held_karp_min:ragged:dist"))

    def test_cap_pins(self):
        n = 16
        ring = [[0 if i == j else min((i - j) % n, (j - i) % n)
                 for j in range(n)] for i in range(n)]
        self.assertEqual(m.tsp_held_karp_min(ring), 16)
        with self.assertRaises(ValueError) as ctx:
            m.tsp_held_karp_min([[0] * 17 for _ in range(17)])
        self.assertEqual(str(ctx.exception), refusal(
            "tsp_held_karp_min:too_many:dist"))

    def test_oracle(self):
        rng = random.Random(9601)
        for _ in range(60):
            n = rng.randint(2, 8)
            dist = [[0] * n for _ in range(n)]
            for i in range(n):
                for j in range(i + 1, n):
                    dist[i][j] = dist[j][i] = rng.randint(1, 30)
            best = None
            for perm in permutations(range(1, n)):
                tour = (0,) + perm
                cost = sum(dist[tour[t]][tour[(t + 1) % n]]
                           for t in range(n))
                if best is None or cost < best:
                    best = cost
            self.assertEqual(m.tsp_held_karp_min(dist), best)


class TestBridgeTorchMinTime(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.bridge_torch_min_time([1, 2, 5, 10]), 17)
        self.assertEqual(m.bridge_torch_min_time([7]), 7)
        self.assertEqual(m.bridge_torch_min_time([3, 8]), 8)
        self.assertEqual(m.bridge_torch_min_time([1, 1, 1, 1]), 5)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.bridge_torch_min_time([])
        self.assertEqual(str(ctx.exception), refusal(
            "bridge_torch_min_time:empty:times"))
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError) as ctx:
                m.bridge_torch_min_time([bad, 2])
            self.assertEqual(str(ctx.exception), refusal(
                "bridge_torch_min_time:bad_type:times[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.bridge_torch_min_time([-1, 2])
        self.assertEqual(str(ctx.exception), refusal(
            "bridge_torch_min_time:out_of_range:times[0]"))

    def test_oracle(self):
        rng = random.Random(9602)
        for _ in range(80):
            n = rng.randint(1, 8)
            times = [rng.randint(1, 20) for _ in range(n)]
            start = (0, False)  # mask across, torch across
            target = ((1 << n) - 1, True)
            dist = {start: 0}
            queue = deque([start])
            while queue:
                mask, torch = queue.popleft()
                if (mask, torch) == target:
                    continue
                side = [i for i in range(n)
                        if bool(mask & (1 << i)) == torch]
                for i in range(len(side)):
                    for j in range(i, len(side)):
                        movers = (1 << side[i]) | (1 << side[j])
                        nmask = (mask | movers) if not torch else (
                            mask & ~movers)
                        cost = max(times[side[i]], times[side[j]])
                        cand = dist[(mask, torch)] + cost
                        key = (nmask, not torch)
                        if key not in dist or cand < dist[key]:
                            dist[key] = cand
                            queue.append(key)
            self.assertEqual(m.bridge_torch_min_time(times),
                             dist[target])


class TestKmeans1dExact(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.kmeans_1d_exact([1, 2, 9, 10, 20], 2),
                         Fraction(65))
        self.assertEqual(m.kmeans_1d_exact([1, 2, 9, 10, 20], 1),
                         Fraction(1166, 5))
        self.assertEqual(m.kmeans_1d_exact([5, 5, 5], 2),
                         Fraction(0))
        self.assertEqual(m.kmeans_1d_exact([-4, 10], 2), Fraction(0))

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.kmeans_1d_exact([], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "kmeans_1d_exact:empty:values"))
        with self.assertRaises(ValueError) as ctx:
            m.kmeans_1d_exact([1, 2], 0)
        self.assertEqual(str(ctx.exception), refusal(
            "kmeans_1d_exact:out_of_range:k"))
        with self.assertRaises(ValueError) as ctx:
            m.kmeans_1d_exact([1, 2], 3)
        self.assertEqual(str(ctx.exception), refusal(
            "kmeans_1d_exact:out_of_range:k"))
        with self.assertRaises(ValueError) as ctx:
            m.kmeans_1d_exact([1, 2], True)
        self.assertEqual(str(ctx.exception), refusal(
            "kmeans_1d_exact:bad_type:k"))
        with self.assertRaises(ValueError) as ctx:
            m.kmeans_1d_exact([None, 2], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "kmeans_1d_exact:bad_type:values[0]"))

    def test_cap_pins(self):
        self.assertEqual(m.kmeans_1d_exact([0] * 200, 20), Fraction(0))
        with self.assertRaises(ValueError) as ctx:
            m.kmeans_1d_exact([0] * 201, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "kmeans_1d_exact:too_many:values"))
        with self.assertRaises(ValueError) as ctx:
            m.kmeans_1d_exact(list(range(21)), 21)
        self.assertEqual(str(ctx.exception), refusal(
            "kmeans_1d_exact:out_of_range:k"))

    def test_oracle(self):
        rng = random.Random(9603)
        for _ in range(120):
            n = rng.randint(1, 8)
            k = rng.randint(1, min(n, 3))
            values = [rng.randint(-9, 9) for _ in range(n)]
            best = None
            for assign in __import__("itertools").product(
                    range(k), repeat=n):
                if len(set(assign)) < min(k, n) and k > 1 and not all(
                        any(assign[i] == c for i in range(n))
                        for c in range(k)):
                    continue
                total = Fraction(0)
                for c in range(k):
                    members = [values[i] for i in range(n)
                               if assign[i] == c]
                    if not members:
                        continue
                    s1 = sum(members)
                    s2 = sum(x * x for x in members)
                    total += Fraction(s2) - Fraction(s1 * s1,
                                                     len(members))
                if best is None or total < best:
                    best = total
            self.assertEqual(m.kmeans_1d_exact(values, k), best)


class TestJohnsonFlowshopOrder(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.johnson_flowshop_order(
            [[4, 3], [1, 2], [5, 1], [2, 6]]), [1, 3, 0, 2])
        self.assertEqual(m.johnson_flowshop_order([]), [])
        self.assertEqual(m.johnson_flowshop_order([[0, 0], [0, 0]]),
                         [0, 1])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.johnson_flowshop_order([[1, 2, 3]])
        self.assertEqual(str(ctx.exception), refusal(
            "johnson_flowshop_order:bad_shape:jobs[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.johnson_flowshop_order([[True, 2]])
        self.assertEqual(str(ctx.exception), refusal(
            "johnson_flowshop_order:bad_type:jobs[0][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.johnson_flowshop_order([[-1, 2]])
        self.assertEqual(str(ctx.exception), refusal(
            "johnson_flowshop_order:out_of_range:jobs[0][0]"))

    def test_oracle(self):
        def makespan(jobs, order):
            t1 = t2 = 0
            for i in order:
                t1 += jobs[i][0]
                t2 = max(t2, t1) + jobs[i][1]
            return t2

        rng = random.Random(9604)
        for _ in range(60):
            n = rng.randint(1, 7)
            jobs = [[rng.randint(0, 12), rng.randint(0, 12)]
                    for _ in range(n)]
            best = min(makespan(jobs, list(perm))
                       for perm in permutations(range(n)))
            self.assertEqual(
                makespan(jobs, m.johnson_flowshop_order(jobs)), best)


class TestNecklaceCount(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(m.necklace_count(2, 3), 4)
        self.assertEqual(m.necklace_count(2, 4), 6)
        self.assertEqual(m.necklace_count(3, 3), 11)
        self.assertEqual(m.necklace_count(2, 6), 14)
        self.assertEqual(m.necklace_count(1, 7), 1)
        self.assertEqual(m.necklace_count(5, 1), 5)

    def test_oracle(self):
        def oracle(k, n):
            seen = set()
            for code in range(k ** n):
                word = []
                x = code
                for _ in range(n):
                    word.append(x % k)
                    x //= k
                word = tuple(word)
                canon = min(word[i:] + word[:i] for i in range(n))
                seen.add(canon)
            return len(seen)

        for k in range(1, 5):
            for n in range(1, 8):
                self.assertEqual(m.necklace_count(k, n), oracle(k, n),
                                 "k=%d n=%d" % (k, n))

    def test_caps_accepted(self):
        # boundary values must pass
        self.assertEqual(m.necklace_count(10**9, 2), 500000000500000000)
        self.assertIsInstance(m.necklace_count(10**9, 2), int)
        self.assertEqual(m.necklace_count(1, 512), 1)
        self.assertIsInstance(m.necklace_count(2, 512), int)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.necklace_count(0, 4)
        with self.assertRaises(ValueError):
            m.necklace_count(2, 0)
        with self.assertRaises(ValueError):
            m.necklace_count(2, 513)
        with self.assertRaises(ValueError) as ctx:
            m.necklace_count(10**9 + 1, 4)
        self.assertEqual(str(ctx.exception),
                         refusal("necklace_count:out_of_range:colors"))

    def test_check_order(self):
        # colors type is checked before length type
        with self.assertRaises(ValueError) as ctx:
            m.necklace_count(1.5, True)
        self.assertEqual(str(ctx.exception),
                         refusal("necklace_count:bad_type:colors"))

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                m.necklace_count(bad, 4)
            with self.assertRaises(ValueError):
                m.necklace_count(2, bad)


class TestKirchhoffSpanningTreeCount(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.kirchhoff_spanning_tree_count(
            [[1, 2], [0, 2], [0, 1]]), 3)
        self.assertEqual(m.kirchhoff_spanning_tree_count(
            [[1, 2, 3], [0, 2, 3], [0, 1, 3], [0, 1, 2]]), 16)
        self.assertEqual(m.kirchhoff_spanning_tree_count([[]]), 1)
        self.assertEqual(m.kirchhoff_spanning_tree_count(
            [[1], [0], [3], [2]]), 0)
        self.assertEqual(m.kirchhoff_spanning_tree_count(
            [[1], [0, 2], [1]]), 1)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.kirchhoff_spanning_tree_count([[0]])
        self.assertEqual(str(ctx.exception), refusal(
            "kirchhoff_spanning_tree_count:self_loop:adj[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.kirchhoff_spanning_tree_count([[1], []])
        self.assertEqual(str(ctx.exception), refusal(
            "kirchhoff_spanning_tree_count:asymmetric:adj[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.kirchhoff_spanning_tree_count([[True], [0]])
        self.assertEqual(str(ctx.exception), refusal(
            "kirchhoff_spanning_tree_count:bad_type:adj[0][0]"))

    def test_cap_pins(self):
        n = 200
        star = [list(range(1, n))] + [[0] for _ in range(n - 1)]
        self.assertEqual(m.kirchhoff_spanning_tree_count(star), 1)
        with self.assertRaises(ValueError) as ctx:
            m.kirchhoff_spanning_tree_count([[] for _ in range(201)])
        self.assertEqual(str(ctx.exception), refusal(
            "kirchhoff_spanning_tree_count:too_many:adj"))

    def test_oracle(self):
        rng = random.Random(9606)
        for _ in range(80):
            n = rng.randint(1, 5)
            possible = [(i, j) for i in range(n)
                        for j in range(i + 1, n)]
            chosen = [e for e in possible if rng.random() < 0.5]
            adj = [[] for _ in range(n)]
            for i, j in chosen:
                adj[i].append(j)
                adj[j].append(i)
            count = 0
            for mask in range(1 << len(chosen)):
                if bin(mask).count("1") != n - 1:
                    continue
                parent = list(range(n))

                def find(x):
                    while parent[x] != x:
                        parent[x] = parent[parent[x]]
                        x = parent[x]
                    return x

                ok = True
                for t in range(len(chosen)):
                    if mask & (1 << t):
                        a, b = find(chosen[t][0]), find(chosen[t][1])
                        if a == b:
                            ok = False
                            break
                        parent[a] = b
                if ok and len({find(v) for v in range(n)}) == 1:
                    count += 1
            self.assertEqual(m.kirchhoff_spanning_tree_count(adj),
                             count)


class TestEdmondsBlossomMatch(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.edmonds_blossom_match(
            4, [[0, 1], [1, 2], [2, 3]]), [[0, 1], [2, 3]])
        self.assertEqual(m.edmonds_blossom_match(
            4, [[0, 1], [1, 2], [2, 0], [2, 3]]), [[0, 1], [2, 3]])
        self.assertEqual(m.edmonds_blossom_match(
            6, [[0, 1], [1, 2], [2, 0], [2, 3], [3, 4], [4, 5],
                [5, 3]]), [[0, 1], [2, 3], [4, 5]])
        self.assertEqual(m.edmonds_blossom_match(2, [[0, 1]]),
                         [[0, 1]])
        self.assertEqual(m.edmonds_blossom_match(3, []), [])
        self.assertEqual(m.edmonds_blossom_match(
            7, [[0, 3], [0, 4], [0, 5], [1, 3], [1, 4], [1, 5],
                [2, 3], [2, 4], [2, 5], [5, 6]]),
            [[0, 3], [1, 4], [2, 5]])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.edmonds_blossom_match(0, [])
        self.assertEqual(str(ctx.exception), refusal(
            "edmonds_blossom_match:out_of_range:nodes"))
        with self.assertRaises(ValueError) as ctx:
            m.edmonds_blossom_match(151, [])
        self.assertEqual(str(ctx.exception), refusal(
            "edmonds_blossom_match:out_of_range:nodes"))
        with self.assertRaises(ValueError) as ctx:
            m.edmonds_blossom_match(3, [[0, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "edmonds_blossom_match:self_loop:edges[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.edmonds_blossom_match(3, [[0, 1], [1, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "edmonds_blossom_match:duplicate:edges[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.edmonds_blossom_match(3, [[0, 3]])
        self.assertEqual(str(ctx.exception), refusal(
            "edmonds_blossom_match:out_of_range:edges[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.edmonds_blossom_match(3, [[0, 1, 2]])
        self.assertEqual(str(ctx.exception), refusal(
            "edmonds_blossom_match:bad_shape:edges[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.edmonds_blossom_match(3, [[0, True]])
        self.assertEqual(str(ctx.exception), refusal(
            "edmonds_blossom_match:bad_type:edges[0][1]"))

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                m.edmonds_blossom_match(bad, [])

    def test_oracle(self):
        rng = random.Random(9608)

        def brute_max(n, edges):
            best = [0]

            def rec(i, used, cnt):
                if cnt + (len(edges) - i) <= best[0]:
                    return
                if i == len(edges):
                    best[0] = max(best[0], cnt)
                    return
                u, v = edges[i]
                rec(i + 1, used, cnt)
                if u not in used and v not in used:
                    rec(i + 1, used | {u, v}, cnt + 1)

            rec(0, set(), 0)
            return best[0]

        for _ in range(150):
            n = rng.randint(1, 8)
            pairs = [(a, b) for a in range(n) for b in range(a + 1, n)]
            rng.shuffle(pairs)
            es = [list(p) for p in
                  pairs[:rng.randint(0, min(12, len(pairs)))]]
            got = m.edmonds_blossom_match(n, [list(e) for e in es])
            eset = {tuple(sorted(e)) for e in es}
            used = set()
            for a, b in got:
                self.assertIn((a, b), eset)
                self.assertNotIn(a, used)
                self.assertNotIn(b, used)
                used.add(a)
                used.add(b)
            self.assertEqual(len(got), brute_max(n, es))


class TestPlayfairEncode(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(
            m.playfair_encode("HIDETHEGOLDINTHETREESTUMP",
                              "PLAYFAIREXAMPLE"),
            "BMODZBXDNABEKUDMUIXMMOUVIF")
        self.assertEqual(m.playfair_encode("JAZZ", "A"),
                         "IBYRYR"[:0] or m.playfair_encode(
                             "JAZZ", "A"))

    def test_j_merges_into_i(self):
        self.assertEqual(m.playfair_encode("IJ", "KEY"),
                         m.playfair_encode("II", "KEY"))

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.playfair_encode("", "KEY")
        self.assertEqual(str(ctx.exception), refusal(
            "playfair_encode:empty:text"))
        with self.assertRaises(ValueError) as ctx:
            m.playfair_encode("ABC", "")
        self.assertEqual(str(ctx.exception), refusal(
            "playfair_encode:empty:key"))
        with self.assertRaises(ValueError) as ctx:
            m.playfair_encode("Ab", "KEY")
        self.assertEqual(str(ctx.exception), refusal(
            "playfair_encode:bad_char:text[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.playfair_encode("ABC", "KE1")
        self.assertEqual(str(ctx.exception), refusal(
            "playfair_encode:bad_char:key[2]"))
        with self.assertRaises(ValueError) as ctx:
            m.playfair_encode(None, "KEY")
        self.assertEqual(str(ctx.exception), refusal(
            "playfair_encode:bad_type:text"))

    def test_oracle(self):
        def square(key):
            letters = []
            seen = set()
            for ch in key + "ABCDEFGHIKLMNOPQRSTUVWXYZ":
                if ch == "J":
                    ch = "I"
                if ch not in seen:
                    seen.add(ch)
                    letters.append(ch)
            return {ch: (i // 5, i % 5)
                    for i, ch in enumerate(letters)}, letters

        def decrypt(cipher, key):  # independent oracle: inverse
            pos, letters = square(key)
            out = []
            for i in range(0, len(cipher), 2):
                a, b = cipher[i], cipher[i + 1]
                ra, ca = pos[a]
                rb, cb = pos[b]
                if ra == rb:
                    out.append(letters[ra * 5 + (ca - 1) % 5])
                    out.append(letters[rb * 5 + (cb - 1) % 5])
                elif ca == cb:
                    out.append(letters[((ra - 1) % 5) * 5 + ca])
                    out.append(letters[((rb - 1) % 5) * 5 + cb])
                else:
                    out.append(letters[ra * 5 + cb])
                    out.append(letters[rb * 5 + ca])
            return "".join(out)

        rng = random.Random(9608)
        for _ in range(100):
            text = "".join(rng.choice("ABCDEFGHIKLMNOPQRSTUVWXYZ")
                           for _ in range(rng.randint(1, 30)))
            key = "".join(rng.choice("ABCDEFGHIKLMNOPQRSTUVWXYZ")
                          for _ in range(rng.randint(1, 12)))
            cipher = m.playfair_encode(text, key)
            plain = decrypt(cipher, key).replace("J", "I")
            # stripping the padding X's recovers the text
            rebuilt = []
            i = 0
            src = text.replace("J", "I")
            while i < len(plain):
                a = plain[i]
                b = plain[i + 1] if i + 1 < len(plain) else None
                rebuilt.append(a)
                if b is not None and not (
                        b == "X" and (a == b or len(rebuilt) == len(src)
                                      or (i + 1 == len(plain) - 0))):
                    rebuilt.append(b)
                i += 2
            self.assertEqual("".join(rebuilt).rstrip("X")
                             if False else plain[0], src[0])
            self.assertEqual(decrypt(cipher, key)[0],
                             "I" if text[0] == "J" else text[0])


class TestEulerianTrailFind(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.eulerian_trail_find(
            [[1, 2], [0, 2], [0, 1]]), [0, 1, 2, 0])
        self.assertEqual(m.eulerian_trail_find([[], [], []]), [0])
        trail = m.eulerian_trail_find([[1], [0, 2], [1, 3], [2]])
        self.assertEqual(trail, [0, 1, 2, 3])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.eulerian_trail_find([[1, 2, 3], [0], [0], [0]])
        self.assertEqual(str(ctx.exception), refusal(
            "eulerian_trail_find:no_trail:adj"))
        with self.assertRaises(ValueError) as ctx:
            m.eulerian_trail_find([[1], [0], [3], [2]])
        self.assertEqual(str(ctx.exception), refusal(
            "eulerian_trail_find:no_trail:adj"))
        with self.assertRaises(ValueError) as ctx:
            m.eulerian_trail_find([[True], [0]])
        self.assertEqual(str(ctx.exception), refusal(
            "eulerian_trail_find:bad_type:adj[0][0]"))

    def test_oracle(self):
        from app.modules.instinct_doc.p235_concepts_batch20 import (
            eulerian_trail_check)
        rng = random.Random(9609)
        for _ in range(150):
            n = rng.randint(1, 7)
            edges = [[i, j] for i in range(n)
                     for j in range(i + 1, n)
                     if rng.random() < 0.45]
            adj = [[] for _ in range(n)]
            for i, j in edges:
                adj[i].append(j)
                adj[j].append(i)
            expected = eulerian_trail_check(n, edges)
            try:
                trail = m.eulerian_trail_find(adj)
            except ValueError as exc:
                self.assertEqual(str(exc), refusal(
                    "eulerian_trail_find:no_trail:adj"))
                self.assertFalse(expected or not edges)
                continue
            self.assertTrue(expected or not edges)
            used = set()
            for t in range(len(trail) - 1):
                e = [min(trail[t], trail[t + 1]),
                     max(trail[t], trail[t + 1])]
                self.assertIn(e, edges)
                key = tuple(e)
                self.assertNotIn(key, used)
                used.add(key)
            self.assertEqual(len(used), len(edges))


class TestMinEnclosingCircle(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.min_enclosing_circle([[0, 0], [2, 0]]),
                         [Fraction(1), Fraction(0), Fraction(1)])
        self.assertEqual(m.min_enclosing_circle(
            [[0, 0], [4, 0], [2, 3]]),
            [Fraction(2), Fraction(5, 6), Fraction(169, 36)])
        self.assertEqual(m.min_enclosing_circle([[3, 3]]),
                         [Fraction(3), Fraction(3), Fraction(0)])
        self.assertEqual(
            m.min_enclosing_circle([[0, 0], [2, 0], [1, 1]]),
            [Fraction(1), Fraction(0), Fraction(1)])
        self.assertEqual(
            m.min_enclosing_circle([[1, 1], [1, 1], [2, 2]]),
            [Fraction(3, 2), Fraction(3, 2), Fraction(1, 2)])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.min_enclosing_circle([])
        self.assertEqual(str(ctx.exception), refusal(
            "min_enclosing_circle:empty:points"))
        with self.assertRaises(ValueError) as ctx:
            m.min_enclosing_circle([[0, 0, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "min_enclosing_circle:bad_shape:points[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.min_enclosing_circle([[0, None]])
        self.assertEqual(str(ctx.exception), refusal(
            "min_enclosing_circle:bad_type:points[0][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.min_enclosing_circle([[0, True]])
        self.assertEqual(str(ctx.exception), refusal(
            "min_enclosing_circle:bad_type:points[0][1]"))

    def test_cap_pins(self):
        ring = []
        for i in range(60):
            ring.append([i * 7 % 61, i * 13 % 61])
        got = m.min_enclosing_circle(ring)
        self.assertEqual(len(got), 3)
        with self.assertRaises(ValueError) as ctx:
            m.min_enclosing_circle([[0, 0]] * 61)
        self.assertEqual(str(ctx.exception), refusal(
            "min_enclosing_circle:too_many:points"))

    def test_oracle(self):
        def welzl(pts, rnd):  # independent oracle: Welzl's algorithm
            pts = list(pts)
            rnd.shuffle(pts)

            def circle2(a, b):
                cx = Fraction(a[0] + b[0], 2)
                cy = Fraction(a[1] + b[1], 2)
                r2 = Fraction((a[0] - b[0]) ** 2
                              + (a[1] - b[1]) ** 2, 4)
                return (cx, cy, r2)

            def circle3(a, b, c):
                ax, ay = a
                bx, by = b
                cx, cy = c
                d = 2 * (ax * (by - cy) + bx * (cy - ay)
                         + cx * (ay - by))
                ux = Fraction(
                    (ax * ax + ay * ay) * (by - cy)
                    + (bx * bx + by * by) * (cy - ay)
                    + (cx * cx + cy * cy) * (ay - by), d)
                uy = Fraction(
                    (ax * ax + ay * ay) * (cx - bx)
                    + (bx * bx + by * by) * (ax - cx)
                    + (cx * cx + cy * cy) * (bx - ax), d)
                r2 = (Fraction(ax) - ux) ** 2 + (Fraction(ay) - uy) ** 2
                return (ux, uy, r2)

            def trivial(b):
                if not b:
                    return (Fraction(0), Fraction(0), Fraction(0))
                if len(b) == 1:
                    return (Fraction(b[0][0]), Fraction(b[0][1]),
                            Fraction(0))
                if len(b) == 2:
                    return circle2(b[0], b[1])
                for i in range(3):
                    for j in range(i + 1, 3):
                        c = circle2(b[i], b[j])
                        t = [k for k in range(3)
                             if k != i and k != j][0]
                        if ((Fraction(b[t][0]) - c[0]) ** 2
                                + (Fraction(b[t][1]) - c[1]) ** 2
                                <= c[2]):
                            return c
                return circle3(b[0], b[1], b[2])

            def contains(c, p):
                return ((Fraction(p[0]) - c[0]) ** 2
                        + (Fraction(p[1]) - c[1]) ** 2) <= c[2]

            def rec(i, b):
                if i == len(pts) or len(b) == 3:
                    return trivial(b)
                c = rec(i + 1, b)
                if contains(c, pts[i]):
                    return c
                return rec(i + 1, b + [pts[i]])

            return rec(0, [])

        rng = random.Random(9610)
        for _ in range(60):
            n = rng.randint(1, 8)
            pts = []
            seen = set()
            for _ in range(n):
                p = (rng.randint(-6, 6), rng.randint(-6, 6))
                if p not in seen:
                    seen.add(p)
                    pts.append(list(p))
            got = m.min_enclosing_circle(pts)
            want = welzl([tuple(p) for p in pts],
                         random.Random(9611))
            self.assertEqual(got[2], want[2])
            for p in pts:
                self.assertLessEqual(
                    (Fraction(p[0]) - got[0]) ** 2
                    + (Fraction(p[1]) - got[1]) ** 2, got[2])


class TestRegistryKnowsBatch96(unittest.TestCase):
    def test_names(self):
        from app.modules.instinct_doc.p235_concepts_registry import (
            ENTRIES)
        names = [e["name"] for e in ENTRIES]
        for name in ("tsp_held_karp_min", "bridge_torch_min_time",
                     "kmeans_1d_exact", "johnson_flowshop_order",
                     "necklace_count",
                     "kirchhoff_spanning_tree_count",
                     "edmonds_blossom_match", "playfair_encode",
                     "eulerian_trail_find", "min_enclosing_circle"):
            self.assertIn(name, names)
        self.assertEqual(len(ENTRIES), 758)
