import random
import unittest
from fractions import Fraction

from app.modules.instinct_doc import p235_concepts_batch89 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


def refusal(code):
    return "P235:%s" % code


class TestAccountsMergeGroups(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.accounts_merge_groups(
            [["John", "j1@x", "j2@x"], ["John", "j3@x"],
             ["John", "j1@x"]]),
            [["John", "j1@x", "j2@x"], ["John", "j3@x"]])
        self.assertEqual(m.accounts_merge_groups(
            [["Bob", "b@x"], ["Ann", "a@x"]]),
            [["Ann", "a@x"], ["Bob", "b@x"]])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.accounts_merge_groups([])
        self.assertEqual(str(ctx.exception),
                         refusal("accounts_merge_groups:empty:accounts"))
        with self.assertRaises(ValueError) as ctx:
            m.accounts_merge_groups([["Ann", "a@x"], ["Bob", "a@x"]])
        self.assertEqual(str(ctx.exception), refusal(
            "accounts_merge_groups:conflict:accounts[1][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.accounts_merge_groups([["Ann"]])
        self.assertEqual(str(ctx.exception), refusal(
            "accounts_merge_groups:bad_shape:accounts[0]"))

    def test_oracle(self):
        def oracle(accounts):
            graph = {}
            for i, acc in enumerate(accounts):
                for e in acc[1:]:
                    graph.setdefault(e, []).append(i)
            seen = set()
            out = []
            for i in range(len(accounts)):
                if i in seen:
                    continue
                stack, comp, emails = [i], [], set()
                while stack:
                    node = stack.pop()
                    if node in comp:
                        continue
                    comp.append(node)
                    for e in accounts[node][1:]:
                        emails.add(e)
                        for j in graph[e]:
                            if j not in comp:
                                stack.append(j)
                seen.update(comp)
                out.append([accounts[comp[0]][0]] + sorted(emails))
            out.sort(key=lambda g: (g[0], g[1]))
            return out
        rng = random.Random(8901)
        for _ in range(60):
            n = rng.randint(1, 8)
            pool = ["e%d@x" % k for k in range(n + 3)]
            accounts = []
            for _ in range(n):
                k = rng.randint(1, 3)
                accounts.append(["N%d" % rng.randint(0, 2)]
                                + rng.sample(pool, k))
            # force name consistency per email for valid inputs
            owner = {}
            ok = True
            for acc in accounts:
                for e in acc[1:]:
                    if owner.setdefault(e, acc[0]) != acc[0]:
                        ok = False
            if not ok:
                continue
            self.assertEqual(m.accounts_merge_groups(accounts),
                             oracle(accounts))


class TestEquationsSatisfiableCheck(unittest.TestCase):
    def test_canonical(self):
        self.assertFalse(m.equations_satisfiable_check(
            ["a==b", "b==c", "a!=c"]))
        self.assertTrue(m.equations_satisfiable_check(
            ["a==b", "b!=c"]))
        self.assertFalse(m.equations_satisfiable_check(["a!=a"]))
        self.assertTrue(m.equations_satisfiable_check(
            ["a==b", "b==a"]))

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.equations_satisfiable_check([])
        self.assertEqual(str(ctx.exception), refusal(
            "equations_satisfiable_check:empty:equations"))
        with self.assertRaises(ValueError) as ctx:
            m.equations_satisfiable_check(["ab==c"])
        self.assertEqual(str(ctx.exception), refusal(
            "equations_satisfiable_check:bad_shape:equations[0]"))

    def test_oracle(self):
        def oracle(equations):
            adj = {}
            for e in equations:
                if e[1:3] == "==":
                    adj.setdefault(e[0], set()).add(e[3])
                    adj.setdefault(e[3], set()).add(e[0])
            comp = {}
            cid = 0
            for v in adj:
                if v in comp:
                    continue
                stack = [v]
                while stack:
                    x = stack.pop()
                    if x in comp:
                        continue
                    comp[x] = cid
                    stack.extend(adj.get(x, ()))
                cid += 1
            for e in equations:
                if e[1:3] == "!=":
                    if e[0] == e[3]:
                        return False
                    if (e[0] in comp and e[3] in comp
                            and comp[e[0]] == comp[e[3]]):
                        return False
            return True
        rng = random.Random(8902)
        letters = "abcd"
        for _ in range(60):
            eqs = []
            for _ in range(rng.randint(1, 8)):
                a, b = rng.choice(letters), rng.choice(letters)
                eqs.append("%s%s%s" % (a, rng.choice(["==", "!="]), b))
            self.assertEqual(m.equations_satisfiable_check(eqs),
                             oracle(eqs))


class TestEarliestFullyConnectedTime(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.earliest_fully_connected_time(
            3, [[1, 1, 2], [2, 2, 3]]), 2)
        self.assertEqual(m.earliest_fully_connected_time(
            3, [[1, 1, 2]]), -1)
        self.assertEqual(m.earliest_fully_connected_time(
            1, [[5, 1, 1]]), 0)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.earliest_fully_connected_time(0, [])
        self.assertEqual(str(ctx.exception), refusal(
            "earliest_fully_connected_time:out_of_range:n"))
        with self.assertRaises(ValueError) as ctx:
            m.earliest_fully_connected_time(
                3, [[3, 1, 2], [2, 2, 3]])
        self.assertEqual(str(ctx.exception), refusal(
            "earliest_fully_connected_time:bad_order:logs[1]"))

    def test_validation_before_early_return(self):
        # logs past the connection point still refuse
        with self.assertRaises(ValueError) as ctx:
            m.earliest_fully_connected_time(
                2, [[1, 1, 2], [0, 1, 2]])
        self.assertEqual(str(ctx.exception), refusal(
            "earliest_fully_connected_time:bad_order:logs[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.earliest_fully_connected_time(
                2, [[1, 1, 2], []])
        self.assertEqual(str(ctx.exception), refusal(
            "earliest_fully_connected_time:bad_shape:logs[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.earliest_fully_connected_time(
                2, [[1, 1, 2], [9, 1, 3]])
        self.assertEqual(str(ctx.exception), refusal(
            "earliest_fully_connected_time:bad_value:logs[1]"))

    def test_oracle(self):
        def oracle(n, logs):
            adj = [[] for _ in range(n + 1)]
            for t, a, b in logs:
                adj[a].append(b)
                adj[b].append(a)
                seen = {1}
                stack = [1]
                while stack:
                    x = stack.pop()
                    for y in adj[x]:
                        if y not in seen:
                            seen.add(y)
                            stack.append(y)
                if len(seen) == n:
                    return t
            return -1
        rng = random.Random(8903)
        for _ in range(60):
            n = rng.randint(2, 7)
            logs = []
            for t in range(1, rng.randint(3, 12)):
                a, b = rng.randrange(1, n + 1), rng.randrange(1, n + 1)
                if a != b:
                    logs.append([t, a, b])
            if not logs:
                logs = [[1, 1, 2]]
            self.assertEqual(m.earliest_fully_connected_time(n, logs),
                             oracle(n, logs))


class TestRestrictedFriendVerdicts(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.restricted_friend_verdicts(
            4, [[0, 1]], [[1, 2], [2, 3], [0, 2]]),
            [True, True, False])
        self.assertEqual(m.restricted_friend_verdicts(
            3, [], [[0, 1], [1, 2]]), [True, True])
        self.assertEqual(m.restricted_friend_verdicts(
            3, [[0, 2]], [[0, 1], [1, 2]]), [True, False])
        # already-linked request is a no-op approval
        self.assertEqual(m.restricted_friend_verdicts(
            2, [], [[0, 1], [0, 1]]), [True, True])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.restricted_friend_verdicts(
                3, [[0, 1]] * 301, [[0, 1]])
        self.assertEqual(str(ctx.exception), refusal(
            "restricted_friend_verdicts:too_many:restrictions"))
        with self.assertRaises(ValueError) as ctx:
            m.restricted_friend_verdicts(3, [[0, 3]], [])
        self.assertEqual(str(ctx.exception), refusal(
            "restricted_friend_verdicts:bad_value:restrictions[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.restricted_friend_verdicts(3, [], [[1, 1]])
        self.assertEqual(str(ctx.exception), refusal(
            "restricted_friend_verdicts:bad_value:requests[0]"))

    def test_oracle(self):
        def oracle(n, restrictions, requests):
            groups = [{i} for i in range(n)]

            def group_of(x):
                for g in groups:
                    if x in g:
                        return g
            out = []
            for u, v in requests:
                gu, gv = group_of(u), group_of(v)
                ok = gu is gv
                if not ok:
                    ok = not any(
                        (x in gu and y in gv) or (x in gv and y in gu)
                        for x, y in restrictions)
                if ok and gu is not gv:
                    gu |= gv
                    groups.remove(gv)
                out.append(ok)
            return out
        rng = random.Random(8911)
        for _ in range(60):
            n = rng.randint(2, 8)
            restrictions = []
            for _ in range(rng.randint(0, 4)):
                x, y = rng.sample(range(n), 2)
                restrictions.append([x, y])
            requests = []
            for _ in range(rng.randint(1, 10)):
                u, v = rng.sample(range(n), 2)
                requests.append([u, v])
            self.assertEqual(
                m.restricted_friend_verdicts(n, restrictions, requests),
                oracle(n, restrictions, requests))

class TestSmallestStringWithSwaps(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.smallest_string_with_swaps(
            "dcab", [[0, 3], [1, 2]]), "bacd")
        self.assertEqual(m.smallest_string_with_swaps(
            "cba", [[0, 2]]), "abc")
        self.assertEqual(m.smallest_string_with_swaps("ab", []), "ab")

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.smallest_string_with_swaps("", [])
        self.assertEqual(str(ctx.exception), refusal(
            "smallest_string_with_swaps:empty:text"))
        with self.assertRaises(ValueError) as ctx:
            m.smallest_string_with_swaps("ab", [[0, 2]])
        self.assertEqual(str(ctx.exception), refusal(
            "smallest_string_with_swaps:bad_value:pairs[0]"))

    def test_oracle(self):
        def oracle(text, pairs):
            n = len(text)
            adj = [[] for _ in range(n)]
            for a, b in pairs:
                adj[a].append(b)
                adj[b].append(a)
            comp = [None] * n
            cid = 0
            for i in range(n):
                if comp[i] is not None:
                    continue
                stack = [i]
                while stack:
                    x = stack.pop()
                    if comp[x] is not None:
                        continue
                    comp[x] = cid
                    stack.extend(adj[x])
                cid += 1
            buckets = {}
            for i, c in enumerate(comp):
                buckets.setdefault(c, []).append(i)
            out = list(text)
            for idxs in buckets.values():
                chars = sorted(out[i] for i in idxs)
                for i, ch in zip(sorted(idxs), chars):
                    out[i] = ch
            return "".join(out)
        rng = random.Random(8905)
        for _ in range(60):
            n = rng.randint(1, 10)
            text = "".join(rng.choice("abcdef") for _ in range(n))
            pairs = []
            for _ in range(rng.randint(0, 12)):
                a, b = rng.randrange(n), rng.randrange(n)
                if a != b:
                    pairs.append([a, b])
            self.assertEqual(m.smallest_string_with_swaps(text, pairs),
                             oracle(text, pairs))


class TestLexSmallestCharMap(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.lexicographically_smallest_char_map(
            ["ab"], "abc"), "aac")
        self.assertEqual(m.lexicographically_smallest_char_map(
            ["bc", "cd"], "dcb"), "bbb")
        self.assertEqual(m.lexicographically_smallest_char_map(
            [], "xyz"), "xyz")

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.lexicographically_smallest_char_map([], "")
        self.assertEqual(str(ctx.exception), refusal(
            "lexicographically_smallest_char_map:empty:text"))
        with self.assertRaises(ValueError) as ctx:
            m.lexicographically_smallest_char_map([], "abC")
        self.assertEqual(str(ctx.exception), refusal(
            "lexicographically_smallest_char_map:bad_char:text"))

    def test_oracle(self):
        def oracle(pairs, text):
            adj = {}
            for a, b in pairs:
                adj.setdefault(a, set()).add(b)
                adj.setdefault(b, set()).add(a)
            best = {}
            for start in adj:
                stack, comp = [start], {start}
                while stack:
                    x = stack.pop()
                    for y in adj[x]:
                        if y not in comp:
                            comp.add(y)
                            stack.append(y)
                for v in comp:
                    best[v] = min(comp)
            return "".join(best.get(c, c) for c in text)
        rng = random.Random(8906)
        for _ in range(60):
            letters = rng.sample("abcdefgh", rng.randint(2, 6))
            pairs = []
            for _ in range(rng.randint(0, 8)):
                a, b = rng.choice(letters), rng.choice(letters)
                if a != b:
                    pairs.append(a + b)
            text = "".join(rng.choice(letters) for _ in range(8))
            self.assertEqual(
                m.lexicographically_smallest_char_map(pairs, text),
                oracle(pairs, text))


class TestBricksFallingCounts(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.bricks_falling_counts(
            [[1], [1], [1]], [[0, 0]]), [2])
        self.assertEqual(m.bricks_falling_counts(
            [[1, 0, 1], [1, 1, 1]], [[0, 0], [0, 2]]), [0, 3])
        self.assertEqual(m.bricks_falling_counts(
            [[1], [1], [1]], [[1, 0]]), [1])
        # a top-row neighbour keeps its roof link: nothing falls
        self.assertEqual(m.bricks_falling_counts(
            [[1, 1]], [[0, 0]]), [0])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.bricks_falling_counts([[1]], [[0, 0], [0, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "bricks_falling_counts:duplicate:hits[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.bricks_falling_counts([[0, 1]], [[0, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "bricks_falling_counts:bad_value:hits[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.bricks_falling_counts([[1], [1, 0]], [])
        self.assertEqual(str(ctx.exception), refusal(
            "bricks_falling_counts:ragged:grid[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.bricks_falling_counts([[2]], [])
        self.assertEqual(str(ctx.exception), refusal(
            "bricks_falling_counts:bad_value:grid[0]"))
        # bools and floats are not builtin ints
        with self.assertRaises(ValueError) as ctx:
            m.bricks_falling_counts([[True]], [[0, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "bricks_falling_counts:bad_value:grid[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.bricks_falling_counts([[1.0]], [[0, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "bricks_falling_counts:bad_value:grid[0]"))

    def test_oracle(self):
        def oracle(grid, hits):
            rows, cols = len(grid), len(grid[0])
            alive = [[grid[r][c] == 1 for c in range(cols)]
                     for r in range(rows)]

            def standing():
                seen = set()
                stack = [(0, c) for c in range(cols) if alive[0][c]]
                while stack:
                    r, c = stack.pop()
                    if (r, c) in seen or not alive[r][c]:
                        continue
                    seen.add((r, c))
                    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            stack.append((nr, nc))
                return len(seen)
            out = []
            for r, c in hits:
                before = standing()
                alive[r][c] = False
                after = standing()
                out.append(max(0, before - 1 - after))
            return out
        rng = random.Random(8913)
        for _ in range(60):
            rows = rng.randint(1, 5)
            cols = rng.randint(1, 5)
            grid = [[rng.randint(0, 1) for _ in range(cols)]
                    for _ in range(rows)]
            cells = [(r, c) for r in range(rows) for c in range(cols)
                     if grid[r][c]]
            rng.shuffle(cells)
            hits = [list(h) for h in cells[:rng.randint(0, len(cells))]]
            self.assertEqual(m.bricks_falling_counts(grid, hits),
                             oracle(grid, hits))

class TestSimilarSentenceGroups(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.similar_sentence_groups(
            [["great", "fine"]],
            [[["great", "skills"], ["fine", "skills"]]]), [True])
        self.assertEqual(m.similar_sentence_groups(
            [["great", "fine"]],
            [[["great"], ["fine", "skills"]]]), [False])
        self.assertEqual(m.similar_sentence_groups(
            [], [[["a"], ["a"]]]), [True])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.similar_sentence_groups([["a"]], [])
        self.assertEqual(str(ctx.exception), refusal(
            "similar_sentence_groups:bad_shape:pairs[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.similar_sentence_groups([], [[["a"], ["a", ""]]])
        self.assertEqual(str(ctx.exception), refusal(
            "similar_sentence_groups:bad_value:queries[0]"))

    def test_oracle(self):
        def oracle(pairs, queries):
            adj = {}
            for a, b in pairs:
                adj.setdefault(a, set()).add(b)
                adj.setdefault(b, set()).add(a)
            comp = {}
            cid = 0
            for w in adj:
                if w in comp:
                    continue
                stack = [w]
                while stack:
                    x = stack.pop()
                    if x in comp:
                        continue
                    comp[x] = cid
                    stack.extend(adj[x])
                cid += 1

            def sim(a, b):
                return a == b or (a in comp and b in comp
                                  and comp[a] == comp[b])
            return [len(a) == len(b)
                    and all(sim(x, y) for x, y in zip(a, b))
                    for a, b in queries]
        rng = random.Random(8910)
        words = ["w%d" % k for k in range(8)]
        for _ in range(60):
            pairs = []
            for _ in range(rng.randint(0, 6)):
                a, b = rng.sample(words, 2)
                pairs.append([a, b])
            queries = []
            for _ in range(4):
                ka = rng.randint(1, 4)
                kb = ka if rng.random() < 0.7 else ka + 1
                queries.append([
                    [rng.choice(words) for _ in range(ka)],
                    [rng.choice(words) for _ in range(kb)]])
            self.assertEqual(m.similar_sentence_groups(pairs, queries),
                             oracle(pairs, queries))


class TestRegistryKnowsBatch89(unittest.TestCase):
    def test_registry_knows_batch89(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("accounts_merge_groups",
                     "equations_satisfiable_check",
                     "earliest_fully_connected_time",
                     "restricted_friend_verdicts",
                     "smallest_string_with_swaps",
                     "lexicographically_smallest_char_map",
                     "bricks_falling_counts",
                     "similar_sentence_groups"):
            self.assertIn(name, names)

    def test_registry_total(self):
        self.assertEqual(reg.IMPLEMENTED_SO_FAR, 758)
        self.assertEqual(len(reg.ENTRIES), 758)


if __name__ == "__main__":
    unittest.main()
