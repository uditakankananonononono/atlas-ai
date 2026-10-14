"""P235 concepts, batch 36 (classic utilities IV, 351-360)."""
from __future__ import annotations

import random
import unittest
from fractions import Fraction

from app.modules.instinct_doc import p235_concepts_batch36 as m


class Batch36Test(unittest.TestCase):
    def test_evaluate_rpn(self):
        self.assertEqual(m.evaluate_rpn([2, 3, "+", 4, "*"]), 20)
        self.assertEqual(m.evaluate_rpn([7, 2, "/"]), Fraction(7, 2))
        self.assertEqual(m.evaluate_rpn([42]), 42)
        with self.assertRaises(ValueError) as ctx:
            m.evaluate_rpn([1, 0, "/"])
        self.assertIn("division_by_zero", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.evaluate_rpn([1, 2, 3, "+"])
        self.assertIn("trailing", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.evaluate_rpn(["+"])
        self.assertIn("underflow", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.evaluate_rpn([1, True, "+"])

    def test_infix_to_postfix(self):
        self.assertEqual(m.infix_to_postfix([2, "+", 3, "*", 4]),
                         [2, 3, 4, "*", "+"])
        self.assertEqual(m.infix_to_postfix(["(", 2, "+", 3, ")", "*", 4]),
                         [2, 3, "+", 4, "*"])
        self.assertEqual(m.infix_to_postfix([1, "-", 2, "-", 3]),
                         [1, 2, "-", 3, "-"])
        with self.assertRaises(ValueError) as ctx:
            m.infix_to_postfix([1, "+", ")"])
        self.assertIn("syntax", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.infix_to_postfix([1, "+", 2, ")"])
        self.assertIn("paren", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.infix_to_postfix(["(", 1, "+", 2])
        self.assertIn("paren", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.infix_to_postfix([1, "+", 2, 3])
        self.assertIn("syntax", str(ctx.exception))

    def test_rpn_infix_crosscheck_oracle(self):
        # independent evaluator: recursive descent over the infix token
        # list; the RPN of the shunting-yard output must agree with it
        def parse(tokens):
            pos = [0]

            def expr():
                val = term()
                while pos[0] < len(tokens) and tokens[pos[0]] in ("+", "-"):
                    op = tokens[pos[0]]
                    pos[0] += 1
                    rhs = term()
                    val = val + rhs if op == "+" else val - rhs
                return val

            def term():
                val = atom()
                while pos[0] < len(tokens) and tokens[pos[0]] in ("*", "/"):
                    op = tokens[pos[0]]
                    pos[0] += 1
                    rhs = atom()
                    val = val * rhs if op == "*" else Fraction(val, rhs)
                return val

            def atom():
                t = tokens[pos[0]]
                pos[0] += 1
                if t == "(":
                    val = expr()
                    assert tokens[pos[0]] == ")"
                    pos[0] += 1
                    return val
                return t

            return expr()

        rng = random.Random(36)
        for _ in range(150):
            depth_tokens = []

            def gen(depth):
                if depth == 0 or rng.random() < 0.4:
                    depth_tokens.append(rng.randint(1, 9))
                    return
                if rng.random() < 0.3:
                    depth_tokens.append("(")
                    gen(depth - 1)
                    depth_tokens.append(")")
                else:
                    gen(depth - 1)
                depth_tokens.append(rng.choice("+-*/"))
                gen(depth - 1)

            gen(3)
            toks = depth_tokens
            try:
                want = parse(toks)
            except ZeroDivisionError:
                continue
            postfix = m.infix_to_postfix(toks)
            got = m.evaluate_rpn(postfix)
            self.assertEqual(got, want, toks)

    def test_activity_selection_count(self):
        self.assertEqual(m.activity_selection_count(
            [[1, 4], [3, 5], [0, 6], [5, 7], [3, 9], [5, 9], [6, 10],
             [8, 11], [8, 12], [2, 14], [12, 16]]), 4)
        self.assertEqual(m.activity_selection_count([[1, 2]]), 1)
        self.assertEqual(m.activity_selection_count([]), 0)
        with self.assertRaises(ValueError) as ctx:
            m.activity_selection_count([[2, 2]])
        self.assertIn("bad_value", str(ctx.exception))

    def test_activity_bruteforce_oracle(self):
        from itertools import combinations
        rng = random.Random(5)
        for _ in range(60):
            n = rng.randint(0, 9)
            ivs = []
            for _ in range(n):
                a = rng.randint(0, 12)
                ivs.append([a, a + rng.randint(1, 5)])
            best = 0
            for r in range(n + 1):
                for combo in combinations(range(n), r):
                    chosen = sorted((ivs[i] for i in combo),
                                    key=lambda iv: iv[0])
                    if all(chosen[i][1] <= chosen[i + 1][0]
                           for i in range(len(chosen) - 1)):
                        best = max(best, r)
            self.assertEqual(m.activity_selection_count(ivs), best, ivs)

    def test_interval_partition_min_rooms(self):
        self.assertEqual(m.interval_partition_min_rooms(
            [[0, 30], [5, 10], [15, 20]]), 2)
        self.assertEqual(m.interval_partition_min_rooms(
            [[0, 5], [5, 10]]), 1)  # half-open: back-to-back shares
        self.assertEqual(m.interval_partition_min_rooms([]), 0)

    def test_min_rooms_sample_oracle(self):
        # independent: sample every interval start point and count
        # simultaneous intervals there; the max concurrent count equals
        # the room lower bound, and the sweep attains it
        rng = random.Random(9)
        for _ in range(80):
            n = rng.randint(0, 10)
            ivs = []
            for _ in range(n):
                a = rng.randint(0, 15)
                ivs.append([a, a + rng.randint(1, 6)])
            want = 0
            for s, _e in ivs:
                want = max(want, sum(1 for a, b in ivs if a <= s < b))
            self.assertEqual(m.interval_partition_min_rooms(ivs), want,
                             ivs)

    def test_next_permutation_step(self):
        self.assertEqual(m.next_permutation_step([1, 2, 3]), [1, 3, 2])
        self.assertIsNone(m.next_permutation_step([3, 2, 1]))
        self.assertEqual(m.next_permutation_step([1, 1, 5]), [1, 5, 1])
        self.assertIsNone(m.next_permutation_step([7]))
        with self.assertRaises(ValueError):
            m.next_permutation_step([1, "2"])

    def test_next_permutation_bruteforce_oracle(self):
        from itertools import permutations
        rng = random.Random(13)
        for _ in range(60):
            vals = [rng.randint(0, 3) for _ in range(rng.randint(2, 6))]
            all_perms = sorted(set(permutations(vals)))
            cur = tuple(vals)
            idx = all_perms.index(cur)
            want = (list(all_perms[idx + 1])
                    if idx + 1 < len(all_perms) else None)
            self.assertEqual(m.next_permutation_step(vals), want, vals)

    def test_gray_code_render(self):
        self.assertEqual(m.gray_code_render(1), ["0", "1"])
        self.assertEqual(m.gray_code_render(2), ["00", "01", "11", "10"])
        self.assertEqual(len(m.gray_code_render(4)), 16)
        with self.assertRaises(ValueError) as ctx:
            m.gray_code_render(17)
        self.assertIn("bad_value:bits", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.gray_code_render(True)

    def test_gray_code_formula_oracle(self):
        # independent route: g(i) = i ^ (i >> 1), zero-padded
        for bits in range(1, 9):
            want = [format(i ^ (i >> 1), "0%db" % bits)
                    for i in range(1 << bits)]
            self.assertEqual(m.gray_code_render(bits), want, bits)
        # unit-distance property
        for bits in (3, 5):
            codes = m.gray_code_render(bits)
            for a, b in zip(codes, codes[1:] + codes[:1]):
                self.assertEqual(sum(x != y for x, y in zip(a, b)), 1)

    def test_multiply_digit_strings(self):
        self.assertEqual(m.multiply_digit_strings("123", "45"), "5535")
        self.assertEqual(m.multiply_digit_strings("999", "999"), "998001")
        self.assertEqual(m.multiply_digit_strings("0", "12345"), "0")
        self.assertEqual(m.multiply_digit_strings("1", "1"), "1")
        with self.assertRaises(ValueError) as ctx:
            m.multiply_digit_strings("01", "2")
        self.assertIn("leading_zero", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.multiply_digit_strings("12a", "3")
        with self.assertRaises(ValueError):
            m.multiply_digit_strings("", "3")

    def test_multiply_int_oracle(self):
        rng = random.Random(21)
        for _ in range(80):
            a = rng.randint(0, 10 ** 12)
            b = rng.randint(0, 10 ** 12)
            self.assertEqual(m.multiply_digit_strings(str(a), str(b)),
                             str(a * b))

    def test_game_of_life_step(self):
        blinker = [[0, 0, 0], [1, 1, 1], [0, 0, 0]]
        self.assertEqual(m.game_of_life_step(blinker),
                         [[0, 1, 0], [0, 1, 0], [0, 1, 0]])
        self.assertEqual(m.game_of_life_step(
            m.game_of_life_step(blinker)), blinker)
        block = [[1, 1], [1, 1]]
        self.assertEqual(m.game_of_life_step(block), block)
        with self.assertRaises(ValueError) as ctx:
            m.game_of_life_step([[0, 1, 2]])
        self.assertIn("bad_value", str(ctx.exception))

    def test_game_of_life_oracle(self):
        # independent: neighbor counts via row-shift summation
        rng = random.Random(2)
        for _ in range(40):
            h, w = rng.randint(1, 6), rng.randint(1, 6)
            grid = [[rng.randint(0, 1) for _ in range(w)]
                    for _ in range(h)]

            def counts(g):
                h2, w2 = len(g), len(g[0])
                cnt = [[0] * w2 for _ in range(h2)]
                for r in range(h2):
                    for c in range(w2):
                        if g[r][c]:
                            for dr in (-1, 0, 1):
                                for dc in (-1, 0, 1):
                                    if dr == dc == 0:
                                        continue
                                    rr, cc = r + dr, c + dc
                                    if 0 <= rr < h2 and 0 <= cc < w2:
                                        cnt[rr][cc] += 1
                return cnt

            cnt = counts(grid)
            want = [[1 if (cnt[r][c] == 3 or
                           (grid[r][c] and cnt[r][c] == 2)) else 0
                     for c in range(w)] for r in range(h)]
            self.assertEqual(m.game_of_life_step(grid), want, grid)

    def test_max_subarray_circular(self):
        self.assertEqual(m.max_subarray_circular([-2, 4, -1, 4, -2]), 7)
        self.assertEqual(m.max_subarray_circular([5, -3, 5]), 10)
        self.assertEqual(m.max_subarray_circular([-3, -2, -3]), -2)
        self.assertEqual(m.max_subarray_circular([3]), 3)
        with self.assertRaises(ValueError):
            m.max_subarray_circular([])

    def test_circular_kadane_oracle(self):
        # independent: max over every nonempty arc of the doubled array
        # with length at most n
        rng = random.Random(17)
        for _ in range(100):
            n = rng.randint(1, 10)
            vals = [rng.randint(-9, 9) for _ in range(n)]
            best = None
            for start in range(n):
                total = 0
                for length in range(1, n + 1):
                    total += vals[(start + length - 1) % n]
                    if best is None or total > best:
                        best = total
            self.assertEqual(m.max_subarray_circular(vals), best, vals)

    def test_three_way_partition(self):
        self.assertEqual(m.three_way_partition([5, 1, 9, 3, 9, 2], 5),
                         [1, 3, 2, 5, 9, 9])
        self.assertEqual(m.three_way_partition([], 5), [])
        self.assertEqual(m.three_way_partition([5, 5, 5], 5), [5, 5, 5])
        with self.assertRaises(ValueError):
            m.three_way_partition([1, 2], "5")

    def test_partition_property_oracle(self):
        rng = random.Random(25)
        for _ in range(100):
            vals = [rng.randint(-6, 6) for _ in range(rng.randint(0, 12))]
            pivot = rng.randint(-6, 6)
            got = m.three_way_partition(vals, pivot)
            self.assertEqual(sorted(got), sorted(vals))  # permutation
            groups = [0 if v < pivot else (1 if v == pivot else 2)
                      for v in got]
            self.assertEqual(groups, sorted(groups))  # grouped
            # stability within groups
            for key, pred in (("less", lambda v: v < pivot),
                              ("eq", lambda v: v == pivot),
                              ("gt", lambda v: v > pivot)):
                self.assertEqual([v for v in got if pred(v)],
                                 [v for v in vals if pred(v)])

    def test_registry_knows_batch36(self):
        from app.modules.instinct_doc import p235_concepts_registry as reg
        own = [e for e in reg.ENTRIES if e["batch"] == 36]
        self.assertEqual(len(own), 10)
        names = [e["name"] for e in own]
        for name in ("evaluate_rpn", "infix_to_postfix",
                     "activity_selection_count",
                     "interval_partition_min_rooms",
                     "next_permutation_step", "gray_code_render",
                     "multiply_digit_strings", "game_of_life_step",
                     "max_subarray_circular", "three_way_partition"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
