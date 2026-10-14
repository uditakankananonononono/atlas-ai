"""Tests for p235 concepts batch 93."""

import random
import unittest
from collections import deque

from app.modules.instinct_doc import p235_concepts_registry as reg
from app.modules.instinct_doc import p235_concepts_batch93 as m


def refusal(code):
    return "P235:" + code


class TestPushDominoesFinal(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.push_dominoes_final("RR.L"), "RR.L")
        self.assertEqual(m.push_dominoes_final(".L.R...LR..L.."),
                         "LL.RR.LLRRLL..")
        self.assertEqual(m.push_dominoes_final("RL"), "RL")
        self.assertEqual(m.push_dominoes_final("."), ".")
        self.assertEqual(m.push_dominoes_final("R."), "RR")

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.push_dominoes_final("")
        self.assertEqual(str(ctx.exception),
                         refusal("push_dominoes_final:empty:dominoes"))
        with self.assertRaises(ValueError) as ctx:
            m.push_dominoes_final("R.X")
        self.assertEqual(str(ctx.exception), refusal(
            "push_dominoes_final:bad_form:dominoes[2]"))
        with self.assertRaises(ValueError) as ctx:
            m.push_dominoes_final(5)
        self.assertEqual(str(ctx.exception), refusal(
            "push_dominoes_final:bad_type:dominoes"))

    def test_cap_pins(self):
        row = "R" + "." * 9999
        self.assertEqual(m.push_dominoes_final(row), "R" * 10000)
        with self.assertRaises(ValueError) as ctx:
            m.push_dominoes_final("." * 10001)
        self.assertEqual(str(ctx.exception), refusal(
            "push_dominoes_final:too_many:dominoes"))

    def test_oracle(self):
        rng = random.Random(9301)
        for _ in range(80):
            row = "".join(rng.choice("LR....")
                          for _ in range(rng.randint(1, 12)))
            got = m.push_dominoes_final(row)
            # independent oracle: wave-by-wave simulation; a cell
            # pushed from both sides in the same wave stays up
            cur = list(row)
            blocked = set()
            while True:
                pushes = {}
                for i, ch in enumerate(cur):
                    if ch == "R" and i + 1 < len(cur) \
                            and cur[i + 1] == "." \
                            and i + 1 not in blocked:
                        pushes.setdefault(i + 1, []).append("R")
                    if ch == "L" and i - 1 >= 0 \
                            and cur[i - 1] == "." \
                            and i - 1 not in blocked:
                        pushes.setdefault(i - 1, []).append("L")
                if not pushes:
                    break
                for cell, dirs in pushes.items():
                    if len(set(dirs)) == 1:
                        cur[cell] = dirs[0]
                    else:
                        blocked.add(cell)
            self.assertEqual(got, "".join(cur))


class TestDebtSettleMinTransfers(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.debt_settle_min_transfers([5, -5]), 1)
        self.assertEqual(m.debt_settle_min_transfers([10, -10]), 1)
        self.assertEqual(m.debt_settle_min_transfers([1, 1, -2]), 2)
        self.assertEqual(m.debt_settle_min_transfers([0, 0]), 0)
        self.assertEqual(
            m.debt_settle_min_transfers([-2, 1, -5, 2, 4]), 3)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.debt_settle_min_transfers([])
        self.assertEqual(str(ctx.exception), refusal(
            "debt_settle_min_transfers:empty:balances"))
        with self.assertRaises(ValueError) as ctx:
            m.debt_settle_min_transfers([1, 2])
        self.assertEqual(str(ctx.exception), refusal(
            "debt_settle_min_transfers:inconsistent:balances"))
        with self.assertRaises(ValueError) as ctx:
            m.debt_settle_min_transfers([1000001, -1000001])
        self.assertEqual(str(ctx.exception), refusal(
            "debt_settle_min_transfers:out_of_range:balances[0]"))

    def test_cap_pins(self):
        self.assertEqual(
            m.debt_settle_min_transfers([1] * 11 + [-11]), 11)
        with self.assertRaises(ValueError) as ctx:
            m.debt_settle_min_transfers([1] * 12 + [-12])
        self.assertEqual(str(ctx.exception), refusal(
            "debt_settle_min_transfers:too_many:nonzero_balances"))
        self.assertEqual(m.debt_settle_min_transfers([0] * 10000), 0)
        with self.assertRaises(ValueError) as ctx:
            m.debt_settle_min_transfers([0] * 10001)
        self.assertEqual(str(ctx.exception), refusal(
            "debt_settle_min_transfers:too_many:balances"))

    def test_oracle(self):
        rng = random.Random(9302)
        for _ in range(50):
            n = rng.randint(1, 8)
            vals = [rng.randint(-9, 9) for _ in range(n - 1)]
            vals.append(-sum(vals))
            rng.shuffle(vals)
            got = m.debt_settle_min_transfers(vals)
            # independent oracle: breadth-first search over balance
            # states; the first all-zero level is the minimum
            start = tuple(sorted(v for v in vals if v != 0))
            seen = {start}
            queue = deque([(start, 0)])
            want = None
            while queue:
                state, depth = queue.popleft()
                if not state:
                    want = depth
                    break
                first = state[0]
                for i in range(1, len(state)):
                    if state[i] * first < 0:
                        rest = list(state)
                        rest[i] += first
                        nxt = tuple(sorted(
                            v for v in rest[1:] if v != 0))
                        if nxt not in seen:
                            seen.add(nxt)
                            queue.append((nxt, depth + 1))
            self.assertEqual(got, want)


class TestRegistryKnowsBatch93(unittest.TestCase):
    def test_registry_knows_batch93(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("push_dominoes_final",
                     "debt_settle_min_transfers",
                     "monotone_increasing_digits",
                     "pyramid_transition_possible",
                     "word_squares_list",
                     "broken_calculator_min_ops",
                     "cherry_pickup_grid",
                     "frog_jump_river",
                     "soup_servings_probability",
                     "largest_plus_sign_order"):
            self.assertIn(name, names)

    def test_registry_total(self):
        self.assertEqual(reg.IMPLEMENTED_SO_FAR, 758)
        self.assertEqual(len(reg.ENTRIES), 758)


if __name__ == "__main__":
    unittest.main()


class TestMonotoneIncreasingDigits(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.monotone_increasing_digits(332), 299)
        self.assertEqual(m.monotone_increasing_digits(10), 9)
        self.assertEqual(m.monotone_increasing_digits(1234), 1234)
        self.assertEqual(m.monotone_increasing_digits(9669), 8999)
        self.assertEqual(m.monotone_increasing_digits(100), 99)
        self.assertEqual(m.monotone_increasing_digits(0), 0)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.monotone_increasing_digits(-1)
        self.assertEqual(str(ctx.exception), refusal(
            "monotone_increasing_digits:out_of_range:n"))
        with self.assertRaises(ValueError) as ctx:
            m.monotone_increasing_digits(10 ** 18 + 1)
        self.assertEqual(str(ctx.exception), refusal(
            "monotone_increasing_digits:out_of_range:n"))
        self.assertEqual(m.monotone_increasing_digits(10 ** 18),
                         999999999999999999)

    def test_oracle(self):
        rng = random.Random(9310)
        for _ in range(60):
            n = rng.randint(0, 20000)
            got = m.monotone_increasing_digits(n)
            want = n
            while True:
                d = str(want)
                if all(d[i] <= d[i + 1] for i in range(len(d) - 1)):
                    break
                want -= 1
            self.assertEqual(got, want)


class TestPyramidTransitionPossible(unittest.TestCase):
    def test_canonical(self):
        self.assertTrue(m.pyramid_transition_possible("AB", ["ABC"]))
        self.assertTrue(m.pyramid_transition_possible(
            "BCD", ["BCC", "CDE", "CEA", "FFF"]))
        self.assertFalse(m.pyramid_transition_possible(
            "AABA", ["AAA", "AAB", "ABA", "ABB", "BAC"]))
        self.assertFalse(m.pyramid_transition_possible("AB", []))

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.pyramid_transition_possible("A", [])
        self.assertEqual(str(ctx.exception), refusal(
            "pyramid_transition_possible:out_of_range:bottom"))
        with self.assertRaises(ValueError) as ctx:
            m.pyramid_transition_possible("AAAAAAAA", [])
        self.assertEqual(str(ctx.exception), refusal(
            "pyramid_transition_possible:too_many:bottom"))
        self.assertFalse(m.pyramid_transition_possible("AAAAAAA", []))
        with self.assertRaises(ValueError) as ctx:
            m.pyramid_transition_possible("AH", [])
        self.assertEqual(str(ctx.exception), refusal(
            "pyramid_transition_possible:bad_form:bottom[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.pyramid_transition_possible("AB", ["AB"])
        self.assertEqual(str(ctx.exception), refusal(
            "pyramid_transition_possible:bad_form:allowed[0]"))

    def test_oracle(self):
        rng = random.Random(9311)
        for _ in range(40):
            bottom = "".join(rng.choice("ABC")
                             for _ in range(rng.randint(2, 6)))
            allowed = ["".join(rng.choice("ABC") for _ in range(3))
                       for _ in range(rng.randint(0, 8))]
            got = m.pyramid_transition_possible(bottom, allowed)
            # independent oracle: level-by-level reachable-row sets
            above = {}
            for t in allowed:
                above.setdefault(t[:2], set()).add(t[2])
            seen = {bottom}
            frontier = {bottom}
            want = False
            while frontier and not want:
                nxt = set()
                for row in frontier:
                    if len(row) == 1:
                        want = True
                        break
                    options = [above.get(row[i:i + 2], set())
                               for i in range(len(row) - 1)]
                    if not all(options):
                        continue
                    import itertools
                    for combo in itertools.product(
                            *[sorted(o) for o in options]):
                        cand = "".join(combo)
                        if cand not in seen:
                            seen.add(cand)
                            nxt.add(cand)
                frontier = nxt
            self.assertEqual(got, want)


class TestWordSquaresList(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.word_squares_list(["ab", "ba"]),
                         [["ab", "ba"], ["ba", "ab"]])
        self.assertEqual(
            m.word_squares_list(["area", "lead", "wall", "lady", "ball"]),
            [["ball", "area", "lead", "lady"],
             ["wall", "area", "lead", "lady"]])
        self.assertEqual(m.word_squares_list(["ab", "cd"]), [])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.word_squares_list([])
        self.assertEqual(str(ctx.exception),
                         refusal("word_squares_list:empty:words"))
        with self.assertRaises(ValueError) as ctx:
            m.word_squares_list(["ab", "abc"])
        self.assertEqual(str(ctx.exception), refusal(
            "word_squares_list:bad_shape:words[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.word_squares_list(["ab", "ab"])
        self.assertEqual(str(ctx.exception),
                         refusal("word_squares_list:bad_form:words"))
        with self.assertRaises(ValueError) as ctx:
            m.word_squares_list(["aB"])
        self.assertEqual(str(ctx.exception), refusal(
            "word_squares_list:bad_form:words[0][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.word_squares_list(["abcdef"])
        self.assertEqual(str(ctx.exception), refusal(
            "word_squares_list:too_many:word_length"))

    def test_cap_pins(self):
        dozen = [chr(ord("a") + i) for i in range(12)]
        self.assertEqual(len(m.word_squares_list(dozen)), 12)
        with self.assertRaises(ValueError) as ctx:
            m.word_squares_list(dozen + ["m"])
        self.assertEqual(str(ctx.exception),
                         refusal("word_squares_list:too_many:words"))

    def test_oracle(self):
        import itertools
        rng = random.Random(9312)
        for _ in range(40):
            side = rng.randint(1, 3)
            pool = set()
            while len(pool) < rng.randint(2, 5):
                pool.add("".join(rng.choice("abc")
                                 for _ in range(side)))
            words = sorted(pool)
            got = m.word_squares_list(words)
            want = []
            for combo in itertools.product(words, repeat=side):
                ok = True
                for i in range(side):
                    if combo[i] != "".join(row[i] for row in combo):
                        ok = False
                        break
                if ok:
                    want.append(list(combo))
            want.sort()
            self.assertEqual(got, want)


class TestBrokenCalculatorMinOps(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.broken_calculator_min_ops(2, 3), 2)
        self.assertEqual(m.broken_calculator_min_ops(5, 8), 2)
        self.assertEqual(m.broken_calculator_min_ops(3, 10), 3)
        self.assertEqual(m.broken_calculator_min_ops(7, 7), 0)
        self.assertEqual(m.broken_calculator_min_ops(9, 1), 8)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.broken_calculator_min_ops(0, 5)
        self.assertEqual(str(ctx.exception), refusal(
            "broken_calculator_min_ops:out_of_range:start"))
        with self.assertRaises(ValueError) as ctx:
            m.broken_calculator_min_ops(1, 1000001)
        self.assertEqual(str(ctx.exception), refusal(
            "broken_calculator_min_ops:out_of_range:target"))
        self.assertEqual(m.broken_calculator_min_ops(1, 1000000), 28)

    def test_oracle(self):
        rng = random.Random(9313)
        for _ in range(50):
            start = rng.randint(1, 40)
            target = rng.randint(1, 40)
            got = m.broken_calculator_min_ops(start, target)
            # independent oracle: bounded breadth-first search
            limit = 2 * max(start, target) + 2
            seen = {start}
            frontier = [start]
            want = None
            depth = 0
            while frontier and want is None:
                nxt = []
                for v in frontier:
                    if v == target:
                        want = depth
                        break
                    for w in (v * 2, v - 1):
                        if 1 <= w <= limit and w not in seen:
                            seen.add(w)
                            nxt.append(w)
                frontier = nxt
                depth += 1
            self.assertEqual(got, want)


class TestCherryPickupGrid(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(
            m.cherry_pickup_grid([[0, 1, -1], [1, 0, -1], [1, 1, 1]]),
            5)
        self.assertEqual(m.cherry_pickup_grid([[0, 1], [1, 0]]), 2)
        self.assertEqual(m.cherry_pickup_grid([[1]]), 1)
        self.assertEqual(m.cherry_pickup_grid([[-1]]), 0)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.cherry_pickup_grid([])
        self.assertEqual(str(ctx.exception),
                         refusal("cherry_pickup_grid:empty:grid"))
        with self.assertRaises(ValueError) as ctx:
            m.cherry_pickup_grid([[0, 1], [0]])
        self.assertEqual(str(ctx.exception), refusal(
            "cherry_pickup_grid:bad_shape:grid[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.cherry_pickup_grid([[2]])
        self.assertEqual(str(ctx.exception), refusal(
            "cherry_pickup_grid:out_of_range:grid[0][0]"))

    def test_cap_pins(self):
        self.assertEqual(m.cherry_pickup_grid([[0] * 50] * 50), 0)
        with self.assertRaises(ValueError) as ctx:
            m.cherry_pickup_grid([[0] * 51] * 51)
        self.assertEqual(str(ctx.exception),
                         refusal("cherry_pickup_grid:too_many:grid"))

    def test_oracle(self):
        rng = random.Random(9314)
        for _ in range(40):
            n = rng.randint(1, 4)
            grid = [[rng.choice([-1, 0, 0, 1]) for _ in range(n)]
                    for _ in range(n)]
            grid[0][0] = max(0, grid[0][0])
            got = m.cherry_pickup_grid(grid)
            # independent oracle: enumerate monotone right/down paths
            paths = []

            def walk(r, c, cells):
                if grid[r][c] == -1:
                    return
                cells = cells | {(r, c)}
                if r == n - 1 and c == n - 1:
                    paths.append(cells)
                    return
                if r + 1 < n:
                    walk(r + 1, c, cells)
                if c + 1 < n:
                    walk(r, c + 1, cells)

            walk(0, 0, set())
            want = 0
            cherries = {(r, c) for r in range(n) for c in range(n)
                        if grid[r][c] == 1}
            for i in range(len(paths)):
                for j in range(i, len(paths)):
                    got_cells = (paths[i] | paths[j]) & cherries
                    want = max(want, len(got_cells))
            self.assertEqual(got, want)


class TestFrogJumpRiver(unittest.TestCase):
    def test_canonical(self):
        self.assertTrue(m.frog_jump_river([0, 1, 3, 5, 6, 8, 12, 17]))
        self.assertFalse(m.frog_jump_river([0, 1, 2, 3, 4, 8, 9, 11]))
        self.assertTrue(m.frog_jump_river([0]))
        self.assertTrue(m.frog_jump_river([0, 1, 3]))

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.frog_jump_river([])
        self.assertEqual(str(ctx.exception),
                         refusal("frog_jump_river:empty:stones"))
        with self.assertRaises(ValueError) as ctx:
            m.frog_jump_river([1])
        self.assertEqual(str(ctx.exception),
                         refusal("frog_jump_river:bad_form:stones[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.frog_jump_river([0, 2])
        self.assertEqual(str(ctx.exception),
                         refusal("frog_jump_river:bad_form:stones[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.frog_jump_river([0, 1, 1])
        self.assertEqual(str(ctx.exception),
                         refusal("frog_jump_river:bad_form:stones[2]"))

    def test_cap_pins(self):
        self.assertTrue(m.frog_jump_river(list(range(1100))))
        with self.assertRaises(ValueError) as ctx:
            m.frog_jump_river(list(range(1101)))
        self.assertEqual(str(ctx.exception),
                         refusal("frog_jump_river:too_many:stones"))

    def test_oracle(self):
        rng = random.Random(9315)
        for _ in range(50):
            n = rng.randint(2, 12)
            stones = [0]
            while len(stones) < n:
                stones.append(stones[-1] + rng.randint(1, 5))
            if stones[1] != 1:
                stones.insert(1, 1)
                stones = stones[:n]
                for i in range(2, len(stones)):
                    if stones[i] <= stones[i - 1]:
                        stones[i] = stones[i - 1] + 1
            got = m.frog_jump_river(stones)
            # independent oracle: breadth-first reachability
            pos = {v: i for i, v in enumerate(stones)}
            seen = {(1, 1)}
            queue = deque([(1, 1)])
            want = False
            while queue:
                i, k = queue.popleft()
                if i == len(stones) - 1:
                    want = True
                    break
                for step in (k - 1, k, k + 1):
                    if step >= 1 and stones[i] + step in pos:
                        key = (pos[stones[i] + step], step)
                        if key not in seen:
                            seen.add(key)
                            queue.append(key)
            self.assertEqual(got, want)


class TestSoupServingsProbability(unittest.TestCase):
    def test_canonical(self):
        from fractions import Fraction
        self.assertEqual(m.soup_servings_probability(0), Fraction(1, 2))
        self.assertEqual(m.soup_servings_probability(50),
                         Fraction(5, 8))
        self.assertEqual(m.soup_servings_probability(100),
                         Fraction(23, 32))

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.soup_servings_probability(-25)
        self.assertEqual(str(ctx.exception), refusal(
            "soup_servings_probability:out_of_range:n_ml"))
        with self.assertRaises(ValueError) as ctx:
            m.soup_servings_probability(5025)
        self.assertEqual(str(ctx.exception), refusal(
            "soup_servings_probability:out_of_range:n_ml"))
        with self.assertRaises(ValueError) as ctx:
            m.soup_servings_probability(30)
        self.assertEqual(str(ctx.exception), refusal(
            "soup_servings_probability:bad_form:n_ml"))

    def test_cap_pins(self):
        from fractions import Fraction
        got = m.soup_servings_probability(5000)
        self.assertIsInstance(got, Fraction)
        self.assertGreater(got, Fraction(9, 10))

    def test_oracle(self):
        from fractions import Fraction
        for n in (0, 25, 50, 75, 100):
            got = m.soup_servings_probability(n)
            u = n // 25
            tab = {}
            serves = ((4, 0), (3, 1), (2, 2), (1, 3))
            for a in range(u + 1):
                for b in range(u + 1):
                    if a == 0 and b == 0:
                        tab[(a, b)] = Fraction(1, 2)
                    elif a == 0:
                        tab[(a, b)] = Fraction(1)
                    elif b == 0:
                        tab[(a, b)] = Fraction(0)
                    else:
                        tab[(a, b)] = sum(
                            tab[(max(0, a - da), max(0, b - db))]
                            for da, db in serves) / 4
            self.assertEqual(got, tab[(u, u)])


class TestLargestPlusSignOrder(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.largest_plus_sign_order(5, [[4, 2]]), 2)
        self.assertEqual(m.largest_plus_sign_order(1, [[0, 0]]), 0)
        self.assertEqual(m.largest_plus_sign_order(3, [[0, 0]]), 2)
        self.assertEqual(m.largest_plus_sign_order(2, []), 1)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.largest_plus_sign_order(0, [])
        self.assertEqual(str(ctx.exception), refusal(
            "largest_plus_sign_order:out_of_range:n"))
        with self.assertRaises(ValueError) as ctx:
            m.largest_plus_sign_order(31, [])
        self.assertEqual(str(ctx.exception), refusal(
            "largest_plus_sign_order:out_of_range:n"))
        with self.assertRaises(ValueError) as ctx:
            m.largest_plus_sign_order(3, [[1, 1], [1, 1]])
        self.assertEqual(str(ctx.exception), refusal(
            "largest_plus_sign_order:bad_form:mines[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.largest_plus_sign_order(3, [[3, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "largest_plus_sign_order:out_of_range:mines[0]"))

    def test_oracle(self):
        rng = random.Random(9316)
        for _ in range(40):
            n = rng.randint(1, 12)
            mines = list({(rng.randrange(n), rng.randrange(n))
                          for _ in range(rng.randint(0, n))})
            mines = [list(p) for p in mines]
            got = m.largest_plus_sign_order(n, mines)
            mined = {tuple(p) for p in mines}
            want = 0
            for r in range(n):
                for c in range(n):
                    if (r, c) in mined:
                        continue
                    arm = 0
                    while True:
                        cells = ((r - arm, c), (r + arm, c),
                                 (r, c - arm), (r, c + arm))
                        if any(not (0 <= x < n and 0 <= y < n)
                               or (x, y) in mined for x, y in cells):
                            break
                        arm += 1
                    want = max(want, arm)
            self.assertEqual(got, want)
