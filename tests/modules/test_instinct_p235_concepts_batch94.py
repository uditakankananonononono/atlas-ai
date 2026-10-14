"""P235 batch 94: ten concepts."""
import random
import unittest
from collections import deque
from fractions import Fraction
from math import atan2, cos, radians, sin, sqrt

from app.modules.instinct_doc import p235_concepts_batch94 as m


def refusal(code):
    return "P235:" + code


class TestRobotBoundedCircle(unittest.TestCase):
    def test_canonical(self):
        self.assertTrue(m.robot_bounded_circle("GGLLGG"))
        self.assertTrue(m.robot_bounded_circle("GL"))
        self.assertTrue(m.robot_bounded_circle("R"))
        self.assertFalse(m.robot_bounded_circle("GG"))
        self.assertTrue(m.robot_bounded_circle("GGR"))

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.robot_bounded_circle("")
        self.assertEqual(str(ctx.exception), refusal(
            "robot_bounded_circle:empty:instructions"))
        with self.assertRaises(ValueError) as ctx:
            m.robot_bounded_circle("GGA")
        self.assertEqual(str(ctx.exception), refusal(
            "robot_bounded_circle:bad_char:instructions[2]"))

    def test_cap_pins(self):
        self.assertFalse(m.robot_bounded_circle("G" * 10000))
        with self.assertRaises(ValueError) as ctx:
            m.robot_bounded_circle("G" * 10001)
        self.assertEqual(str(ctx.exception), refusal(
            "robot_bounded_circle:too_long:instructions"))

    def test_oracle(self):
        rng = random.Random(9401)
        for _ in range(80):
            n = rng.randint(1, 30)
            prog = "".join(rng.choice("GLR") for _ in range(n))
            # independent oracle: run four full cycles; the orbit is
            # bounded exactly when the robot is home again
            x = y = d = 0
            for _ in range(4):
                for ch in prog:
                    if ch == "G":
                        x, y = (x, y + 1) if d == 0 else (
                            (x + 1, y) if d == 1 else
                            (x, y - 1) if d == 2 else (x - 1, y))
                    elif ch == "L":
                        d = (d - 1) % 4
                    else:
                        d = (d + 1) % 4
            self.assertEqual(m.robot_bounded_circle(prog),
                             (x, y) == (0, 0))


class TestWaterJugMinPours(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.water_jug_min_pours(3, 5, 4), 6)
        self.assertEqual(m.water_jug_min_pours(2, 6, 5), -1)
        self.assertEqual(m.water_jug_min_pours(1, 1, 1), 1)
        self.assertEqual(m.water_jug_min_pours(4, 3, 2), 4)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.water_jug_min_pours(0, 5, 4)
        self.assertEqual(str(ctx.exception), refusal(
            "water_jug_min_pours:out_of_range:cap_a"))
        with self.assertRaises(ValueError) as ctx:
            m.water_jug_min_pours(3, 5, 6)
        self.assertEqual(str(ctx.exception), refusal(
            "water_jug_min_pours:out_of_range:target"))

    def test_cap_pins(self):
        self.assertEqual(m.water_jug_min_pours(1000, 999, 998), 4)
        with self.assertRaises(ValueError) as ctx:
            m.water_jug_min_pours(1001, 1, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "water_jug_min_pours:out_of_range:cap_a"))

    def test_oracle(self):
        rng = random.Random(9402)
        for _ in range(40):
            a = rng.randint(1, 40)
            b = rng.randint(1, 40)
            t = rng.randint(0, max(a, b))
            # independent oracle: BFS with a distance dict and an
            # index-walked queue, transitions listed in another order
            dist = {(0, 0): 0}
            queue = deque([(0, 0)])
            want = -1
            while queue:
                x, y = queue.popleft()
                if x == t or y == t:
                    want = dist[(x, y)]
                    break
                pour_xy = min(x, b - y)
                pour_yx = min(y, a - x)
                for s in ((x, 0), (0, y), (x, b), (a, y),
                          (x + pour_yx, y - pour_yx),
                          (x - pour_xy, y + pour_xy)):
                    if s not in dist:
                        dist[s] = dist[(x, y)] + 1
                        queue.append(s)
            self.assertEqual(m.water_jug_min_pours(a, b, t), want)


class TestCarPoolingFeasible(unittest.TestCase):
    def test_canonical(self):
        self.assertFalse(m.car_pooling_feasible(
            [[2, 1, 5], [3, 3, 7]], 4))
        self.assertTrue(m.car_pooling_feasible(
            [[2, 1, 5], [3, 3, 7]], 5))
        self.assertTrue(m.car_pooling_feasible([[4, 0, 10]], 4))

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.car_pooling_feasible([], 4)
        self.assertEqual(str(ctx.exception), refusal(
            "car_pooling_feasible:empty:trips"))
        with self.assertRaises(ValueError) as ctx:
            m.car_pooling_feasible([[2, 5, 5]], 4)
        self.assertEqual(str(ctx.exception), refusal(
            "car_pooling_feasible:bad_trip:trips[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.car_pooling_feasible([[2, 1, 3]], 0)
        self.assertEqual(str(ctx.exception), refusal(
            "car_pooling_feasible:out_of_range:capacity"))

    def test_cap_pins(self):
        trips = [[1, i, i + 1] for i in range(10000)]
        self.assertTrue(m.car_pooling_feasible(trips, 1))
        with self.assertRaises(ValueError) as ctx:
            m.car_pooling_feasible(trips + [[1, 10000, 10001]], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "car_pooling_feasible:too_many:trips"))

    def test_oracle(self):
        rng = random.Random(9403)
        for _ in range(60):
            trips = []
            for _ in range(rng.randint(1, 10)):
                frm = rng.randint(0, 20)
                trips.append([rng.randint(1, 5), frm,
                              frm + rng.randint(1, 10)])
            cap = rng.randint(1, 8)
            # independent oracle: bucket deltas per location, then walk
            # the locations in sorted order
            delta = {}
            for n, frm, to in trips:
                delta[frm] = delta.get(frm, 0) + n
                delta[to] = delta.get(to, 0) - n
            load = 0
            ok = True
            for loc in sorted(delta):
                load += delta[loc]
                if load > cap:
                    ok = False
            self.assertEqual(m.car_pooling_feasible(trips, cap), ok)


class TestSparklineRender(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.sparkline_render([1, 8, 3, 5]), "▁█▃▅")
        self.assertEqual(m.sparkline_render([]), "")
        self.assertEqual(m.sparkline_render([7, 7, 7]), "▁▁▁")
        self.assertEqual(m.sparkline_render([0, 1]), "▁█")

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.sparkline_render([10**13])
        self.assertEqual(str(ctx.exception), refusal(
            "sparkline_render:out_of_range:values[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.sparkline_render([True])
        self.assertEqual(str(ctx.exception), refusal(
            "sparkline_render:bad_type:values[0]"))

    def test_cap_pins(self):
        self.assertEqual(len(m.sparkline_render([5] * 10000)), 10000)
        with self.assertRaises(ValueError) as ctx:
            m.sparkline_render([0] * 10001)
        self.assertEqual(str(ctx.exception), refusal(
            "sparkline_render:too_many:values"))

    def test_oracle(self):
        glyphs = "▁▂▃▄▅▆▇█"
        rng = random.Random(9404)
        for _ in range(60):
            xs = [rng.randint(-50, 50) for _ in range(rng.randint(1, 12))]
            # independent oracle: pick the level whose ideal value is
            # closest, ties broken to the lower level
            lo = min(xs)
            span = max(xs) - lo
            out = []
            for v in xs:
                if span == 0:
                    out.append(glyphs[0])
                    continue
                target = Fraction(v - lo, span)
                best = 0
                for k in range(8):
                    if abs(Fraction(k, 7) - target) <= abs(
                            Fraction(best, 7) - target):
                        best = k
                out.append(glyphs[best])
            self.assertEqual(m.sparkline_render(xs), "".join(out))


class TestPagerankIterate(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.pagerank_iterate([[1], [0]], 0.85, 1),
                         [0.5, 0.5])
        self.assertEqual(m.pagerank_iterate([[1], []], 0.85, 1),
                         [0.2875, 0.7124999999999999])
        got = m.pagerank_iterate([[1, 2], [2], [0]], 0.85, 5)
        for a, b in zip(got, (0.39489635416666663,
                              0.21783095052083332,
                              0.38727269531249997)):
            self.assertAlmostEqual(a, b, places=15)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.pagerank_iterate([[0]], True, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "pagerank_iterate:bad_type:damping"))
        with self.assertRaises(ValueError) as ctx:
            m.pagerank_iterate([[0]], "0.5", 1)
        self.assertEqual(str(ctx.exception), refusal(
            "pagerank_iterate:bad_type:damping"))
        with self.assertRaises(ValueError) as ctx:
            m.pagerank_iterate([[0]], 1.5, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "pagerank_iterate:out_of_range:damping"))
        with self.assertRaises(ValueError) as ctx:
            m.pagerank_iterate([[0]], 0.5, 2.5)
        self.assertEqual(str(ctx.exception), refusal(
            "pagerank_iterate:bad_type:rounds"))
        with self.assertRaises(ValueError) as ctx:
            m.pagerank_iterate([[0]], 0.5, True)
        self.assertEqual(str(ctx.exception), refusal(
            "pagerank_iterate:bad_type:rounds"))
        with self.assertRaises(ValueError) as ctx:
            m.pagerank_iterate([[0]], 0.5, 0)
        self.assertEqual(str(ctx.exception), refusal(
            "pagerank_iterate:out_of_range:rounds"))
        with self.assertRaises(ValueError) as ctx:
            m.pagerank_iterate([], 0.5, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "pagerank_iterate:empty:adj"))
        with self.assertRaises(ValueError) as ctx:
            m.pagerank_iterate([[2]], 0.5, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "pagerank_iterate:out_of_range:adj[0][0]"))

    def test_cap_pins(self):
        self.assertEqual(m.pagerank_iterate([[0]], 0.5, 10000), [1.0])
        with self.assertRaises(ValueError) as ctx:
            m.pagerank_iterate([[0]], 0.5, 10001)
        self.assertEqual(str(ctx.exception), refusal(
            "pagerank_iterate:out_of_range:rounds"))
        big = [[] for _ in range(10000)]
        self.assertEqual(len(m.pagerank_iterate(big, 0.5, 1)), 10000)
        with self.assertRaises(ValueError) as ctx:
            m.pagerank_iterate([[] for _ in range(10001)], 0.5, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "pagerank_iterate:too_many:adj"))

    def test_work_caps(self):
        n = 1000
        rng = random.Random(9420)
        adj = [[rng.randrange(n) for _ in range(100)]
               for _ in range(n)]
        # edges exactly at cap, work exactly at the 2e6 budget
        self.assertEqual(len(m.pagerank_iterate(adj, 0.85, 19)), n)
        with self.assertRaises(ValueError) as ctx:
            m.pagerank_iterate(adj, 0.85, 20)
        self.assertEqual(str(ctx.exception), refusal(
            "pagerank_iterate:too_much_work:adj,rounds"))
        dense = [[rng.randrange(n) for _ in range(101)]
                 for _ in range(n)]
        with self.assertRaises(ValueError) as ctx:
            m.pagerank_iterate(dense, 0.85, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "pagerank_iterate:too_many:edges"))

    def test_oracle(self):
        rng = random.Random(9410)
        for _ in range(40):
            n = rng.randint(1, 8)
            adj = [[rng.randrange(n)
                    for _ in range(rng.randint(0, n))]
                   for _ in range(n)]
            damp = rng.choice([0.15, 0.5, 0.85, 0.99])
            rounds = rng.randint(1, 20)
            # independent oracle: pull from explicitly transposed
            # in-edges instead of pushing along out-edges
            ins = [[] for _ in range(n)]
            for j, outs in enumerate(adj):
                for t in outs:
                    ins[t].append(j)
            pr = [1.0 / n] * n
            for _ in range(rounds):
                dangling = sum(pr[j] for j in range(n) if not adj[j])
                nxt = []
                for i in range(n):
                    v = (1.0 - damp) / n + damp * dangling / n
                    v += damp * sum(
                        pr[j] / len(adj[j]) for j in ins[i])
                    nxt.append(v)
                pr = nxt
            got = m.pagerank_iterate(adj, damp, rounds)
            for a, b in zip(got, pr):
                self.assertAlmostEqual(a, b, places=12)


class TestSpreadsheetEval(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(
            m.spreadsheet_eval([["A1", "1+2*3"], ["B2", "A1*2"],
                                ["C3", "(B2+4)/2"]]),
            [["A1", Fraction(7)], ["B2", Fraction(14)],
             ["C3", Fraction(9)]])
        self.assertEqual(m.spreadsheet_eval([["A1", "10/4"]]),
                         [["A1", Fraction(5, 2)]])
        self.assertEqual(m.spreadsheet_eval([["A1", "-3+1"]]),
                         [["A1", Fraction(-2)]])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval([["A1", "B2"], ["B2", "A1"]])
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:cyclic:A1"))
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval([["A1", "Z9+1"]])
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:unknown_ref:Z9"))
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval([["A1", "1"], ["A1", "2"]])
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:duplicate:cells[1][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval([["A1", "1/0"]])
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:div_zero:A1"))
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval([["A1", "1+"]])
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:bad_formula:A1"))
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval([["A1", "1&2"]])
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:bad_char:cells[0][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval([["a1", "1"]])
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:bad_name:cells[0][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval([["A1", 1.5]])
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:bad_type:cells[0][1]"))

    def test_cap_pins(self):
        cells = [["A%d" % (i + 1), "1"] for i in range(1000)]
        self.assertEqual(len(m.spreadsheet_eval(cells)), 1000)
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval(
                [["A%d" % (i + 1), "1"] for i in range(1001)])
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:too_many:cells"))
        self.assertEqual(m.spreadsheet_eval([["A1", "11" + "+1" * 99]]),
                         [["A1", Fraction(110)]])
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval([["A1", "111" + "+1" * 99]])
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:too_long:cells[0][1]"))

    def test_unicode_and_name_caps(self):
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval([["Ä1", "1"]])
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:bad_name:cells[0][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval([["A٤", "1"]])
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:bad_name:cells[0][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval([["A1", "²"]])
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:bad_char:cells[0][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval([["ABCDEFGHIJ1", "1"]])
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:too_long:cells[0][0]"))

    def test_squaring_chain_bit_budget(self):
        # repeated squaring explodes numerator bits; the budget must
        # refuse before the value is ever computed
        chain = [["A%d" % i, "2*A%d*A%d" % (i + 1, i + 1)]
                 for i in range(1, 40)] + [["A40", "2"]]
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval(chain)
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:too_big:A29"))
        ok = [["A%d" % i, "2*A%d*A%d" % (i + 1, i + 1)]
              for i in range(1, 11)] + [["A11", "2"]]
        self.assertEqual(m.spreadsheet_eval(ok)[0],
                         ["A1", Fraction(2 ** 2047)])
        over = [["A%d" % i, "2*A%d*A%d" % (i + 1, i + 1)]
                for i in range(1, 12)] + [["A12", "2"]]
        with self.assertRaises(ValueError) as ctx:
            m.spreadsheet_eval(over)
        self.assertEqual(str(ctx.exception), refusal(
            "spreadsheet_eval:too_big:A1"))

    def test_deep_chain_no_recursion(self):
        deep = [["A%d" % i, "A%d+1" % (i + 1)]
                for i in range(1, 1000)] + [["A1000", "1"]]
        got = m.spreadsheet_eval(deep)
        self.assertEqual(len(got), 1000)
        self.assertEqual(got[0], ["A1", Fraction(1000)])

    def test_oracle(self):
        rng = random.Random(9411)
        for _ in range(30):
            n = rng.randint(1, 8)
            names = ["A%d" % (i + 1) for i in range(n)]
            cells = []
            for i, name in enumerate(names):
                expr = str(rng.randint(0, 9))
                for _ in range(rng.randint(0, 3)):
                    op = rng.choice(["+", "-", "*"])
                    if rng.random() < 0.4 and i:
                        rhs = rng.choice(names[:i])
                    else:
                        rhs = str(rng.randint(0, 9))
                    expr = "%s%s%s" % (expr, op, rhs)
                cells.append([name, expr])
            # independent oracle: substitute resolved values as text
            # and evaluate with Python's own Fraction arithmetic
            pending = {name: expr for name, expr in cells}
            want = {}
            while pending:
                progress = False
                for name, expr in list(pending.items()):
                    if all(ch.isdigit() or ch in "+-*()"
                           for ch in expr):
                        want[name] = eval(
                            expr, {"__builtins__": {}}, {})
                        progress = True
                        del pending[name]
                        for other, e2 in pending.items():
                            pending[other] = e2.replace(
                                name, "(%d)" % want[name])
                if not progress:
                    break
            self.assertEqual(m.spreadsheet_eval(cells),
                             [[name, Fraction(want[name])]
                              for name, _ in cells])
        with self.assertRaises(ValueError):
            m.spreadsheet_eval([["A1", "A2*2"], ["A2", "A1+1"]])


class TestHaversineKm(unittest.TestCase):
    def test_canonical(self):
        self.assertAlmostEqual(m.haversine_km(0, 0, 0, 1),
                               111.1950802335329, places=9)
        self.assertEqual(m.haversine_km(0, 0, 0, 0), 0.0)
        self.assertAlmostEqual(m.haversine_km(90, 0, -90, 0),
                               20015.114442035923, places=9)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.haversine_km(91, 0, 0, 0)
        self.assertEqual(str(ctx.exception), refusal(
            "haversine_km:out_of_range:lat1"))
        with self.assertRaises(ValueError) as ctx:
            m.haversine_km(0, "x", 0, 0)
        self.assertEqual(str(ctx.exception), refusal(
            "haversine_km:bad_type:lon1"))

    def test_boundary_pins(self):
        self.assertAlmostEqual(m.haversine_km(90, 180, 90, -180), 0.0,
                               places=9)
        self.assertAlmostEqual(m.haversine_km(-90, -180, -90, 180), 0.0,
                               places=9)
        with self.assertRaises(ValueError) as ctx:
            m.haversine_km(0, 180.5, 0, 0)
        self.assertEqual(str(ctx.exception), refusal(
            "haversine_km:out_of_range:lon1"))

    def test_oracle(self):
        rng = random.Random(9407)
        for _ in range(60):
            p1 = rng.uniform(-90, 90)
            l1 = rng.uniform(-180, 180)
            p2 = rng.uniform(-90, 90)
            l2 = rng.uniform(-180, 180)
            # independent oracle: the atan2 form of the haversine law
            q1, q2 = radians(p1), radians(p2)
            h = (sin((q2 - q1) / 2) ** 2
                 + cos(q1) * cos(q2) * sin(radians(l2 - l1) / 2) ** 2)
            want = 2 * 6371.0088 * atan2(sqrt(h), sqrt(1 - h))
            self.assertAlmostEqual(m.haversine_km(p1, l1, p2, l2),
                                   want, places=9)


class TestHangmanState(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.hangman_state("banana", "anbx"),
                         ["banana", 5])
        self.assertEqual(m.hangman_state("abc", ""), ["___", 6])
        self.assertEqual(m.hangman_state("zzz", "abcdefgh"), ["___", 0])
        self.assertEqual(m.hangman_state("hi", "hihihi"), ["hi", 6])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.hangman_state("", "a")
        self.assertEqual(str(ctx.exception), refusal(
            "hangman_state:empty:secret"))
        with self.assertRaises(ValueError) as ctx:
            m.hangman_state("ABC", "a")
        self.assertEqual(str(ctx.exception), refusal(
            "hangman_state:bad_char:secret[0]"))

    def test_cap_pins(self):
        s = "q" * 100
        self.assertEqual(m.hangman_state(s, "q"), [s, 6])
        with self.assertRaises(ValueError) as ctx:
            m.hangman_state("q" * 101, "q")
        self.assertEqual(str(ctx.exception), refusal(
            "hangman_state:too_long:secret"))

    def test_oracle(self):
        rng = random.Random(9408)
        for _ in range(60):
            secret = "".join(rng.choice("abc") for _ in range(
                rng.randint(1, 15)))
            guesses = "".join(rng.choice("abcde") for _ in range(
                rng.randint(0, 20)))
            # independent oracle: set difference for misses, set
            # membership for the reveal
            missed = set(guesses) - set(secret)
            lives = max(0, 6 - len(missed))
            shown = "".join(c if c in set(guesses) else "_"
                            for c in secret)
            self.assertEqual(m.hangman_state(secret, guesses),
                             [shown, lives])


class TestBerlekampMasseyMod(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(
            m.berlekamp_massey_mod([1, 1, 2, 3, 5, 8, 13], 1009),
            [1, 1008, 1008])
        self.assertEqual(m.berlekamp_massey_mod([3, 3, 3, 3], 7),
                         [1, 6])
        self.assertEqual(m.berlekamp_massey_mod([0, 0, 0], 2), [1])
        self.assertEqual(
            m.berlekamp_massey_mod([1, 2, 4, 8, 16, 32], 1009),
            [1, 1007])
        self.assertEqual(m.berlekamp_massey_mod([1, 0, 1, 0, 1, 0], 5),
                         [1, 0, 4])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.berlekamp_massey_mod([1.5], 7)
        self.assertEqual(str(ctx.exception), refusal(
            "berlekamp_massey_mod:bad_type:seq[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.berlekamp_massey_mod([True], 7)
        self.assertEqual(str(ctx.exception), refusal(
            "berlekamp_massey_mod:bad_type:seq[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.berlekamp_massey_mod([], 7)
        self.assertEqual(str(ctx.exception), refusal(
            "berlekamp_massey_mod:empty:seq"))
        with self.assertRaises(ValueError) as ctx:
            m.berlekamp_massey_mod([1], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "berlekamp_massey_mod:out_of_range:p"))
        with self.assertRaises(ValueError) as ctx:
            m.berlekamp_massey_mod([1], 4)
        self.assertEqual(str(ctx.exception), refusal(
            "berlekamp_massey_mod:not_prime:p"))
        with self.assertRaises(ValueError) as ctx:
            m.berlekamp_massey_mod([1], 2000)
        self.assertEqual(str(ctx.exception), refusal(
            "berlekamp_massey_mod:out_of_range:p"))

    def test_cap_pins(self):
        self.assertEqual(m.berlekamp_massey_mod([0] * 1000, 1009), [1])
        with self.assertRaises(ValueError) as ctx:
            m.berlekamp_massey_mod([0] * 1001, 1009)
        self.assertEqual(str(ctx.exception), refusal(
            "berlekamp_massey_mod:too_many:seq"))

    def test_oracle(self):
        rng = random.Random(9412)

        def minimal_length(s, p):
            # independent solver: try each L from 0 up, solving the
            # recurrence system by Gaussian elimination mod p
            for L in range(0, len(s) + 1):
                if L == 0:
                    if all(v == 0 for v in s):
                        return 0
                    continue
                rows = []
                for n in range(L, len(s)):
                    rows.append([s[n - i] for i in range(1, L + 1)]
                                + [s[n] % p])
                a = [row[:] for row in rows]
                rank = 0
                piv = []
                for col in range(L):
                    sel = None
                    for r in range(rank, len(a)):
                        if a[r][col] % p:
                            sel = r
                            break
                    if sel is None:
                        continue
                    a[rank], a[sel] = a[sel], a[rank]
                    inv = pow(a[rank][col] % p, p - 2, p)
                    a[rank] = [(v * inv) % p for v in a[rank]]
                    for r in range(len(a)):
                        if r != rank and a[r][col] % p:
                            f = a[r][col] % p
                            a[r] = [(x - f * y) % p
                                    for x, y in zip(a[r], a[rank])]
                    piv.append(col)
                    rank += 1
                    if rank == L:
                        break
                if rank < L:
                    # underdetermined: accept only if it annihilates
                    continue
                coeffs = [a[i][L] % p for i in range(L)]
                ok = True
                for n in range(L, len(s)):
                    acc = s[n] % p
                    for i in range(1, L + 1):
                        acc = (acc - coeffs[i - 1] * s[n - i]) % p
                    if acc % p:
                        ok = False
                        break
                if ok:
                    return L
            return None

        for _ in range(30):
            p = rng.choice([2, 5, 7, 101, 1009])
            L0 = rng.randint(1, 3)
            seeds = [rng.randrange(p) for _ in range(L0)]
            coeffs = [rng.randrange(p) for _ in range(L0)]
            s = list(seeds)
            for _ in range(20 - L0):
                s.append(sum(c * v for c, v in zip(coeffs,
                                                   s[-L0:][::-1])) % p)
            got = m.berlekamp_massey_mod(s, p)
            for n in range(len(got) - 1, len(s)):
                acc = sum(got[i] * s[n - i] for i in range(len(got)))
                self.assertEqual(acc % p, 0)
            self.assertEqual(len(got) - 1, minimal_length(s, p))


class TestRegistryKnowsBatch94(unittest.TestCase):
    def test_names(self):
        from app.modules.instinct_doc.p235_concepts_registry import (
            ENTRIES)
        names = [e["name"] for e in ENTRIES]
        for name in ("robot_bounded_circle", "water_jug_min_pours",
                     "car_pooling_feasible", "sparkline_render",
                     "pagerank_iterate", "spreadsheet_eval",
                     "haversine_km", "hangman_state",
                     "berlekamp_massey_mod", "dragon_curve_turn"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
