"""Tests for P235 concepts batch 80 (doc 791-800)."""
import ast
import heapq
import random
import unittest
from collections import deque
from fractions import Fraction

from app.modules.instinct_doc import p235_concepts_batch80 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class TestWordLadder(unittest.TestCase):
    def test_canonical(self):
        w = ["hot", "dot", "dog", "lot", "log", "cog"]
        self.assertEqual(m.word_ladder_length("hit", "cog", w), 5)
        self.assertEqual(m.word_ladder_length("hit", "cog", w[:-1]), 0)
        self.assertEqual(m.word_ladder_length("hit", "hit", ["hit"]), 1)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.word_ladder_length("HIT", "cog", ["cog"])
        with self.assertRaises(ValueError):
            m.word_ladder_length("hit", "cogs", ["cogs"])
        with self.assertRaises(ValueError):
            m.word_ladder_length("hit", "cog", ["hot", "long"])
        with self.assertRaises(ValueError):
            m.word_ladder_length("hit", "cog", tuple(["hot", "cog"]))
        with self.assertRaises(ValueError):
            m.word_ladder_length("hit", "cog", [])

    def test_oracle_exhaustive_small_alphabet(self):
        words = [a + b for a in "abc" for b in "abc"]
        def oracle(begin, end, pool):
            if end not in pool:
                return 0
            if begin == end:
                return 1
            seen = {begin}
            frontier = {begin}
            depth = 1
            while frontier:
                nxt = set()
                for w in frontier:
                    for cand in pool:
                        if cand in seen:
                            continue
                        if sum(x != y for x, y in zip(w, cand)) == 1:
                            if cand == end:
                                return depth + 1
                            nxt.add(cand)
                seen |= nxt
                frontier = nxt
                depth += 1
            return 0
        rng = random.Random(8001)
        for _ in range(300):
            pool = set(rng.sample(words, rng.randint(1, 9)))
            begin = rng.choice(words)
            end = rng.choice(words)
            self.assertEqual(
                m.word_ladder_length(begin, end, sorted(pool)),
                oracle(begin, end, pool))


class TestOpenLock(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.open_lock_min_turns(
            "0202", ["0201", "0101", "0102", "1212", "2002"]), 6)
        self.assertEqual(m.open_lock_min_turns("0000", []), 0)
        self.assertEqual(m.open_lock_min_turns("8888", ["0000"]), -1)
        self.assertEqual(m.open_lock_min_turns("0009", []), 1)
        # b80 v2: a dead target is unreachable.
        self.assertEqual(m.open_lock_min_turns("0001", ["0001"]), -1)
        self.assertEqual(m.open_lock_min_turns("0001", ["1001"]), 1)
        self.assertEqual(m.open_lock_min_turns(
            "0001",
            ["0002", "0011", "0091", "0101", "0901", "1001",
             "9001"]), 1)
        self.assertEqual(m.open_lock_min_turns(
            "0001",
            ["0000", "0002", "0011", "0091", "0101", "0901", "1001",
             "9001"]), -1)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.open_lock_min_turns("123", [])
        with self.assertRaises(ValueError):
            m.open_lock_min_turns("123a", [])
        with self.assertRaises(ValueError):
            m.open_lock_min_turns("1234", ["000"])
        with self.assertRaises(ValueError):
            m.open_lock_min_turns(1234, [])

    def test_oracle_integer_state_bfs(self):
        def oracle(target, deadends):
            dead = {int(d) for d in deadends}
            goal = int(target)
            if 0 in dead:
                return -1
            if goal in dead:
                return -1
            if goal == 0:
                return 0
            seen = dead | {0}
            queue = deque([(0, 0)])
            while queue:
                state, dist = queue.popleft()
                digits = [(state // 1000) % 10, (state // 100) % 10,
                          (state // 10) % 10, state % 10]
                for pos, place in ((0, 1000), (1, 100), (2, 10), (3, 1)):
                    for delta in (place, -place):
                        moved = digits[:]
                        moved[pos] = (moved[pos] +
                                      (1 if delta > 0 else 9)) % 10
                        nxt = (moved[0] * 1000 + moved[1] * 100 +
                               moved[2] * 10 + moved[3])
                        if nxt == goal:
                            return dist + 1
                        if nxt not in seen:
                            seen.add(nxt)
                            queue.append((nxt, dist + 1))
            return -1
        rng = random.Random(8002)
        for case in range(400):
            dead = {"%04d" % rng.randint(0, 9999)
                    for _ in range(rng.randint(0, 60))}
            target = "%04d" % rng.randint(0, 9999)
            if case % 3 == 0:
                dead.add(target)
            self.assertEqual(m.open_lock_min_turns(target, sorted(dead)),
                             oracle(target, dead))


class TestSlidingPuzzle(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.sliding_puzzle_min_moves([[1, 2, 3], [4, 0, 5]]), 1)
        self.assertEqual(m.sliding_puzzle_min_moves([[1, 2, 3], [4, 5, 0]]), 0)
        self.assertEqual(m.sliding_puzzle_min_moves([[4, 1, 2], [5, 0, 3]]), 5)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.sliding_puzzle_min_moves([[1, 2, 3, 4], [5, 6, 0, 7]])
        with self.assertRaises(ValueError):
            m.sliding_puzzle_min_moves([[1, 2, 3]])
        with self.assertRaises(ValueError):
            m.sliding_puzzle_min_moves([[1, 2, 3], [4, 5, 5]])
        with self.assertRaises(ValueError):
            m.sliding_puzzle_min_moves([[1, 2, 3], [4, 5, 6]])
        with self.assertRaises(ValueError):
            m.sliding_puzzle_min_moves([[1, 2, 3], [4, 5, True]])

    def test_oracle_all_720_boards(self):
        def neighbors(state):
            blank = state.index("0")
            r, c = divmod(blank, 3)
            out = []
            for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < 2 and 0 <= nc < 3:
                    dest = nr * 3 + nc
                    moved = list(state)
                    moved[blank], moved[dest] = moved[dest], moved[blank]
                    out.append("".join(moved))
            return out
        goal = "123450"
        dist = {goal: 0}
        queue = deque([goal])
        while queue:
            state = queue.popleft()
            for nxt in neighbors(state):
                if nxt not in dist:
                    dist[nxt] = dist[state] + 1
                    queue.append(nxt)
        self.assertEqual(len(dist), 360)
        import itertools
        for perm in itertools.permutations("123450"):
            board = [[int(perm[0]), int(perm[1]), int(perm[2])],
                     [int(perm[3]), int(perm[4]), int(perm[5])]]
            self.assertEqual(m.sliding_puzzle_min_moves(board),
                             dist.get("".join(perm), -1))


class TestSnakesAndLadders(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.snakes_and_ladders_min_throws(
            [-1, -1, -1, -1]), 1)
        self.assertEqual(m.snakes_and_ladders_min_throws(
            [-1, -1, -1, -1, -1, -1, -1, -1, -1]), 2)
        self.assertEqual(m.snakes_and_ladders_min_throws(
            [-1, 4, -1, -1]), 1)
        self.assertEqual(m.snakes_and_ladders_min_throws(
            [-1, 1, -1, 1]), -1)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.snakes_and_ladders_min_throws([-1, -1, -1])
        with self.assertRaises(ValueError):
            m.snakes_and_ladders_min_throws([-1] * (21 * 21))
        with self.assertRaises(ValueError):
            m.snakes_and_ladders_min_throws([-1, 5, -1, -1])
        with self.assertRaises(ValueError):
            m.snakes_and_ladders_min_throws([1, -1, -1, -1])
        with self.assertRaises(ValueError):
            m.snakes_and_ladders_min_throws([-1, 2.5, -1, -1])

    def test_oracle_exhaustive_n2_and_random_n3(self):
        import itertools
        def oracle(squares):
            n = int(len(squares) ** 0.5)
            last = n * n
            memo = {}
            def best(pos):
                if pos == last:
                    return 0
                if pos in memo:
                    return memo[pos]
                memo[pos] = None
                ans = None
                for die in range(1, 7):
                    nxt = pos + die
                    if nxt > last:
                        break
                    if squares[nxt - 1] != -1:
                        nxt = squares[nxt - 1]
                    if nxt == pos:
                        continue
                    sub = best(nxt)
                    if sub is not None:
                        cand = sub + 1
                        if ans is None or cand < ans:
                            ans = cand
                memo[pos] = ans
                return ans
            got = best(1)
            return -1 if got is None else got
        choices = [[-1] + [v for v in range(1, 5) if v != i + 1]
                   for i in range(4)]
        for combo in itertools.product(*choices):
            self.assertEqual(m.snakes_and_ladders_min_throws(list(combo)),
                             oracle(list(combo)))
        rng = random.Random(8004)
        for _ in range(200):
            board = []
            for i in range(9):
                pool = [-1] * 4 + [v for v in range(1, 10) if v != i + 1]
                board.append(rng.choice(pool))
            self.assertEqual(m.snakes_and_ladders_min_throws(board),
                             oracle(board))


class TestCollectKeys(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.shortest_path_collect_keys(
            ["@.a.#", "###.#", "b.A.B"]), 8)
        self.assertEqual(m.shortest_path_collect_keys(["@"]), 0)
        self.assertEqual(m.shortest_path_collect_keys(["@#a"]), -1)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.shortest_path_collect_keys(["abc"])
        with self.assertRaises(ValueError):
            m.shortest_path_collect_keys(["@@"])
        with self.assertRaises(ValueError):
            m.shortest_path_collect_keys(["@A"])
        with self.assertRaises(ValueError):
            m.shortest_path_collect_keys(["@?a"])
        with self.assertRaises(ValueError):
            m.shortest_path_collect_keys(["@ab", "ab"])
        with self.assertRaises(ValueError):
            m.shortest_path_collect_keys([])

    def test_oracle_dijkstra(self):
        def oracle(grid):
            rows = list(grid)
            start = keys = None
            keyset = set()
            for r, row in enumerate(rows):
                for c, ch in enumerate(row):
                    if ch == "@":
                        start = (r, c)
                    elif "a" <= ch <= "f":
                        keyset.add(ch)
            goal = (1 << len(keyset)) - 1

            def bit(ch):
                return ord(ch) - ord("a")
            heap = [(0, start[0], start[1], 0)]
            best = {}
            while heap:
                dist, r, c, mask = heapq.heappop(heap)
                if (r, c, mask) in best:
                    continue
                best[(r, c, mask)] = dist
                if mask == goal:
                    return dist
                for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                    nr, nc = r + dr, c + dc
                    if not (0 <= nr < len(rows) and 0 <= nc < len(rows[0])):
                        continue
                    ch = rows[nr][nc]
                    if ch == "#":
                        continue
                    if "A" <= ch <= "F" and not (mask >> bit(ch.lower())) & 1:
                        continue
                    nmask = mask | (1 << bit(ch)) if "a" <= ch <= "f" else mask
                    heapq.heappush(heap, (dist + 1, nr, nc, nmask))
            return -1
        rng = random.Random(8005)
        for _ in range(60):
            h, w = rng.randint(2, 5), rng.randint(2, 5)
            spots = list(range(h * w))
            rng.shuffle(spots)
            room = min(3, (h * w - 1) // 2)
            grid_keys = "abc"[:rng.randint(1, room)]
            layout = ["."] * (h * w)
            layout[spots[0]] = "@"
            idx = 1
            for k in grid_keys:
                layout[spots[idx]] = k
                idx += 1
                if rng.random() < 0.5:
                    layout[spots[idx]] = k.upper()
                    idx += 1
            for j in range(idx, len(spots)):
                if rng.random() < 0.25:
                    layout[spots[j]] = "#"
            grid = ["".join(layout[r * w:(r + 1) * w]) for r in range(h)]
            self.assertEqual(m.shortest_path_collect_keys(grid),
                             oracle(grid))


class TestKnightDialer(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.knight_dialer_count(1), 10)
        self.assertEqual(m.knight_dialer_count(2), 20)
        self.assertEqual(m.knight_dialer_count(3), 46)
        self.assertEqual(m.knight_dialer_count(4), 104)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.knight_dialer_count(0)
        with self.assertRaises(ValueError):
            m.knight_dialer_count(1001)
        with self.assertRaises(ValueError):
            m.knight_dialer_count(True)
        with self.assertRaises(ValueError):
            m.knight_dialer_count("3")

    def test_oracle_brute_force(self):
        jumps = {0: (4, 6), 1: (6, 8), 2: (7, 9), 3: (4, 8), 4: (0, 3, 9),
                 5: (), 6: (0, 1, 7), 7: (2, 6), 8: (1, 3), 9: (2, 4)}
        def oracle(n):
            count = 0
            stack = [(d, 1) for d in range(10)]
            while stack:
                digit, length = stack.pop()
                if length == n:
                    count += 1
                else:
                    for nxt in jumps[digit]:
                        stack.append((nxt, length + 1))
            return count
        for n in range(1, 7):
            self.assertEqual(m.knight_dialer_count(n), oracle(n))


class TestEvaluateRatioQueries(unittest.TestCase):
    def test_canonical(self):
        pairs = [["a", "b", [2, 1]], ["b", "c", [3, 1]]]
        self.assertEqual(
            m.evaluate_ratio_queries(pairs, [["a", "c"], ["b", "a"],
                                             ["x", "a"], ["a", "a"]]),
            [Fraction(6, 1), Fraction(1, 2), None, Fraction(1, 1)])

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.evaluate_ratio_queries(
                [["a", "b", [2, 1]], ["b", "a", [1, 3]]], [])
        with self.assertRaises(ValueError):
            m.evaluate_ratio_queries([["a", "a", [1, 1]]], [])
        with self.assertRaises(ValueError):
            m.evaluate_ratio_queries([["a", "b", [1, 0]]], [])
        with self.assertRaises(ValueError):
            m.evaluate_ratio_queries([["a", "b", [0, 1]]], [])
        with self.assertRaises(ValueError):
            m.evaluate_ratio_queries([["AB", "b", [1, 1]]], [])
        with self.assertRaises(ValueError):
            m.evaluate_ratio_queries([["a", "b", [2]]], [])

    def test_oracle_floyd(self):
        def oracle(pairs, queries):
            nodes = set()
            for a, b, (p, q) in pairs:
                nodes.add(a)
                nodes.add(b)
            nodes = sorted(nodes)
            idx = {v: i for i, v in enumerate(nodes)}
            n = len(nodes)
            table = [[None] * n for _ in range(n)]
            for i in range(n):
                table[i][i] = Fraction(1)
            for a, b, (p, q) in pairs:
                table[idx[a]][idx[b]] = Fraction(p, q)
                table[idx[b]][idx[a]] = Fraction(q, p)
            for k in range(n):
                for i in range(n):
                    if table[i][k] is None:
                        continue
                    for j in range(n):
                        if table[i][j] is None and table[k][j] is not None:
                            table[i][j] = table[i][k] * table[k][j]
            out = []
            for c, d in queries:
                if c not in idx or d not in idx:
                    out.append(None)
                else:
                    out.append(table[idx[c]][idx[d]])
            return out
        rng = random.Random(8007)
        names = list("abcdefgh")
        for _ in range(40):
            rng.shuffle(names)
            chosen = names[:rng.randint(2, 6)]
            split = rng.randint(1, len(chosen))
            groups = [chosen[:split], chosen[split:]]
            pairs = []
            for group in groups:
                for i in range(1, len(group)):
                    a = group[rng.randint(0, i - 1)]
                    b = group[i]
                    pairs.append([a, b, [rng.randint(1, 9),
                                         rng.randint(1, 9)]])
            queries = [[rng.choice(chosen + ["zz"]),
                        rng.choice(chosen + ["zz"])]
                       for _ in range(6)]
            got = m.evaluate_ratio_queries(pairs, queries)
            want = oracle(pairs, queries)
            self.assertEqual(got, want)


class TestDecodeStringNested(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.decode_string_nested("3[a]2[bc]"), "aaabcbc")
        self.assertEqual(m.decode_string_nested("3[a2[c]]"), "accaccacc")
        self.assertEqual(m.decode_string_nested("2[abc]3[cd]ef"),
                         "abcabccdcdcdef")
        self.assertEqual(m.decode_string_nested(""), "")
        self.assertEqual(m.decode_string_nested("abc"), "abc")
        self.assertEqual(m.decode_string_nested("1[]a"), "a")

    def test_cap_and_cap_plus_one(self):
        self.assertEqual(
            len(m.decode_string_nested("100[100[10[a]]]")), 100_000)
        with self.assertRaises(ValueError) as ctx:
            m.decode_string_nested("101[101[10[a]]]")
        self.assertIn("too_large:output", str(ctx.exception))

    def test_refusals(self):
        for bad in ("2[a", "a]", "a3b", "0[a]", "301[a]", "aB"):
            with self.assertRaises(ValueError):
                m.decode_string_nested(bad)
        with self.assertRaises(ValueError):
            m.decode_string_nested(["3[a]"])
        with self.assertRaises(ValueError):
            m.decode_string_nested("a" * 2001)

    def test_oracle_recursive_reference(self):
        def oracle(text):
            pos = [0]
            def parse():
                out = []
                while pos[0] < len(text) and text[pos[0]] != "]":
                    if text[pos[0]].isdigit():
                        j = pos[0]
                        while text[j].isdigit():
                            j += 1
                        count = int(text[pos[0]:j])
                        pos[0] = j + 1
                        inner = parse()
                        pos[0] += 1
                        out.append(inner * count)
                    else:
                        out.append(text[pos[0]])
                        pos[0] += 1
                return "".join(out)
            return parse()
        rng2 = random.Random(8008)

        def gen(depth):
            parts = []
            for _ in range(rng2.randint(1, 4)):
                if depth < 3 and rng2.random() < 0.5:
                    parts.append("%d[%s]" % (rng2.randint(1, 9),
                                             gen(depth + 1)))
                else:
                    parts.append("".join(
                        rng2.choice("abc")
                        for _ in range(rng2.randint(1, 5))))
            return "".join(parts)
        for _ in range(300):
            text = gen(0)
            self.assertEqual(m.decode_string_nested(text), oracle(text))


class TestBasicCalculator(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.basic_calculator_eval("2 * (3 + 4)"), 14)
        self.assertEqual(m.basic_calculator_eval("7 / 2"), 3)
        self.assertEqual(m.basic_calculator_eval("14 - 3 * 2 + 10 / 4"), 10)
        self.assertEqual(m.basic_calculator_eval(" 12 "), 12)
        self.assertEqual(m.basic_calculator_eval("100000 * 2"), 200000)

    def test_refusals(self):
        for bad in ("-3", "1 + + 2", "2(3)", "(2", "2)", "1 / 0", "1 & 2",
                    "1.5 + 2", "", "3 4"):
            with self.assertRaises(ValueError):
                m.basic_calculator_eval(bad)
        with self.assertRaises(ValueError):
            m.basic_calculator_eval("9" * 19)
        with self.assertRaises(ValueError):
            m.basic_calculator_eval(42)

    def test_oracle_python_ast(self):
        def oracle(text):
            tree = ast.parse(text, mode="eval")
            def walk(node):
                if isinstance(node, ast.Expression):
                    return walk(node.body)
                if isinstance(node, ast.Constant):
                    if type(node.value) is not int:
                        raise ValueError("literal")
                    return node.value
                if isinstance(node, ast.BinOp):
                    x, y = walk(node.left), walk(node.right)
                    if isinstance(node.op, ast.Add):
                        return x + y
                    if isinstance(node.op, ast.Sub):
                        return x - y
                    if isinstance(node.op, ast.Mult):
                        return x * y
                    if isinstance(node.op, ast.Div):
                        q = abs(x) // abs(y)
                        return q if (x < 0) == (y < 0) else -q
                    raise ValueError("op")
                raise ValueError("node")
            return walk(tree)
        rng = random.Random(8009)
        def gen(depth):
            if depth >= 4 or rng.random() < 0.4:
                return str(rng.randint(0, 99))
            op = rng.choice("+-*/")
            left = gen(depth + 1)
            right = gen(depth + 1)
            if rng.random() < 0.5:
                return "(%s %s %s)" % (left, op, right)
            return "%s %s %s" % (left, op, right)
        tried = 0
        while tried < 300:
            text = gen(0)
            try:
                want = oracle(text)
            except ZeroDivisionError:
                continue
            except ValueError:
                continue
            tried += 1
            self.assertEqual(m.basic_calculator_eval(text), want)


class TestTaskScheduler(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.task_scheduler_min_time(
            ["A", "A", "A", "B", "B", "B"], 2), 8)
        self.assertEqual(m.task_scheduler_min_time(
            ["A", "A", "A", "B", "B", "B"], 0), 6)
        self.assertEqual(m.task_scheduler_min_time(["A"], 5), 1)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.task_scheduler_min_time([], 2)
        with self.assertRaises(ValueError):
            m.task_scheduler_min_time(["a"], 2)
        with self.assertRaises(ValueError):
            m.task_scheduler_min_time(["AA"], 2)
        with self.assertRaises(ValueError):
            m.task_scheduler_min_time(["A"], -1)
        with self.assertRaises(ValueError):
            m.task_scheduler_min_time(["A"], 10001)

    def test_oracle_greedy_simulation(self):
        def oracle(tasks, cooldown):
            counts = {}
            for t in tasks:
                counts[t] = counts.get(t, 0) + 1
            heap = [(-c, t) for t, c in counts.items()]
            heapq.heapify(heap)
            waiting = deque()
            time = 0
            while heap or waiting:
                time += 1
                if heap:
                    neg, t = heapq.heappop(heap)
                    if neg + 1 < 0:
                        waiting.append((time + cooldown, neg + 1, t))
                while waiting and waiting[0][0] <= time:
                    _, neg, t = waiting.popleft()
                    heapq.heappush(heap, (neg, t))
            return time
        rng = random.Random(8010)
        for _ in range(200):
            tasks = [rng.choice("ABCD")
                     for _ in range(rng.randint(1, 30))]
            cooldown = rng.randint(0, 4)
            self.assertEqual(m.task_scheduler_min_time(tasks, cooldown),
                             oracle(tasks, cooldown))


class TestRegistryKnowsBatch80(unittest.TestCase):
    def test_registry_knows_batch80(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("word_ladder_length", "open_lock_min_turns",
                     "sliding_puzzle_min_moves",
                     "snakes_and_ladders_min_throws",
                     "shortest_path_collect_keys", "knight_dialer_count",
                     "evaluate_ratio_queries", "decode_string_nested",
                     "basic_calculator_eval", "task_scheduler_min_time"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
