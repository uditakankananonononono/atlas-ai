"""Tests for P235 concepts batch 86 (range query structures)."""

import random
import unittest

from app.modules.instinct_doc import p235_concepts_batch86 as m
from app.modules.instinct_doc import p235_concepts_registry as reg

MAX_ITEMS = reg.MAX_ITEMS

def refusal(code):
    return "P235:" + code

def rand_queries(rng, n, count, arity=2, v_lo=-20, v_hi=20):
    out = []
    for _ in range(count):
        l = rng.randrange(n)
        r = rng.randrange(l, n)
        row = [l, r]
        if arity == 3:
            row.append(rng.randint(v_lo, v_hi))
        out.append(row)
    return out

class TestMaxSumTwoNonoverlap(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.max_sum_two_nonoverlap([3, 0, 1, 4], 1, 1), 7)
        self.assertEqual(m.max_sum_two_nonoverlap(
            [0, 6, 5, 2, 2, 5, 1, 9, 4], 1, 2), 20)
        self.assertEqual(m.max_sum_two_nonoverlap([1, 2], 1, 1), 3)
        self.assertEqual(m.max_sum_two_nonoverlap([-5, -2, -9], 1, 1), -7)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.max_sum_two_nonoverlap([1, 2], 0, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "max_sum_two_nonoverlap:out_of_range:first_len"))
        with self.assertRaises(ValueError) as ctx:
            m.max_sum_two_nonoverlap([1, 2], 3, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "max_sum_two_nonoverlap:out_of_range:first_len"))
        with self.assertRaises(ValueError) as ctx:
            m.max_sum_two_nonoverlap([1, 2, 3], 2, 2)
        self.assertEqual(str(ctx.exception), refusal(
            "max_sum_two_nonoverlap:out_of_range:second_len"))
        with self.assertRaises(ValueError) as ctx:
            m.max_sum_two_nonoverlap([1] * (MAX_ITEMS + 1), 1, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "max_sum_two_nonoverlap:too_many:values"))

    def test_oracle(self):
        def oracle(values, a, b):
            n = len(values)
            prefix = [0]
            for v in values:
                prefix.append(prefix[-1] + v)
            best = None
            for i in range(n - a + 1):
                sa = prefix[i + a] - prefix[i]
                for j in range(i + a, n - b + 1):
                    sb = prefix[j + b] - prefix[j]
                    best = sa + sb if best is None else max(best, sa + sb)
                for j in range(0, i - b + 1):
                    sb = prefix[j + b] - prefix[j]
                    best = sa + sb if best is None else max(best, sa + sb)
            return best
        rng = random.Random(8601)
        for _ in range(60):
            n = rng.randint(2, 12)
            values = [rng.randint(-9, 9) for _ in range(n)]
            a = rng.randint(1, n - 1)
            b = rng.randint(1, n - a)
            self.assertEqual(m.max_sum_two_nonoverlap(values, a, b),
                             oracle(values, a, b))

class TestRangeSumPointUpdates(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.range_sum_point_updates(
            [1, 2, 3, 4],
            [["query", 0, 3], ["update", 1, 10], ["query", 0, 3],
             ["query", 2, 2]]), [10, 20, 3])

    def test_multi_update_sequence(self):
        self.assertEqual(m.range_sum_point_updates(
            [1, 2, 3, 4],
            [["update", 1, 10], ["update", 1, -3], ["query", 0, 3],
             ["query", 1, 1], ["update", 0, -1], ["query", 0, 1]]),
            [17, 9, 9])

    def test_delta_endpoints(self):
        self.assertEqual(m.range_sum_point_updates(
            [0, 0],
            [["update", 0, 10000], ["update", 1, -10000],
             ["query", 0, 0], ["query", 1, 1]]), [10000, -10000])
        self.assertEqual(m.range_sum_point_updates(
            [7, 8], [["query", 1, 1]]), [8])
        for bad in (10001, -10001):
            with self.assertRaises(ValueError) as ctx:
                m.range_sum_point_updates([1, 2], [["update", 0, bad]])
            self.assertEqual(str(ctx.exception), refusal(
                "range_sum_point_updates:out_of_range:ops[0]"))

    def test_boundary_updates(self):
        self.assertEqual(m.range_sum_point_updates(
            [5, 5, 5],
            [["update", 0, 1], ["update", 2, 2], ["query", 0, 0],
             ["query", 2, 2], ["query", 0, 2]]), [6, 7, 18])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.range_sum_point_updates([1], [])
        self.assertEqual(str(ctx.exception),
                         refusal("range_sum_point_updates:empty:ops"))
        with self.assertRaises(ValueError) as ctx:
            m.range_sum_point_updates([1], [["poke", 0, 1]])
        self.assertEqual(str(ctx.exception),
                         refusal("range_sum_point_updates:bad_value:ops[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.range_sum_point_updates([1], [["update", 5, 1]])
        self.assertEqual(str(ctx.exception),
                         refusal("range_sum_point_updates:out_of_range:ops[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.range_sum_point_updates([1], [["query", 0, 3]])
        self.assertEqual(str(ctx.exception),
                         refusal("range_sum_point_updates:out_of_range:ops[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.range_sum_point_updates([1], [["update", 0]])
        self.assertEqual(str(ctx.exception),
                         refusal("range_sum_point_updates:bad_shape:ops[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.range_sum_point_updates(
                [1, 2, 3],
                [["update", 0, 5], ["query", 0, 2], ["update", 3, 1]])
        self.assertEqual(str(ctx.exception),
                         refusal("range_sum_point_updates:out_of_range:ops[2]"))
        with self.assertRaises(ValueError) as ctx:
            m.range_sum_point_updates([1, 2], [["update", 0, 10001]])
        self.assertEqual(str(ctx.exception),
                         refusal("range_sum_point_updates:out_of_range:ops[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.range_sum_point_updates([1, 2], [["query", 1, 0]])
        self.assertEqual(str(ctx.exception),
                         refusal("range_sum_point_updates:out_of_range:ops[0]"))

    def test_oracle(self):
        def oracle(items, ops):
            data = list(items)
            out = []
            for op in ops:
                if op[0] == "update":
                    data[op[1]] += op[2]
                else:
                    out.append(sum(data[op[1]:op[2] + 1]))
            return out
        rng = random.Random(8603)
        for _ in range(60):
            n = rng.randint(1, 20)
            items = [rng.randint(-30, 30) for _ in range(n)]
            ops = []
            for _ in range(rng.randint(1, 12)):
                if rng.random() < 0.5:
                    ops.append(["update", rng.randrange(n),
                                rng.randint(-10, 10)])
                else:
                    l = rng.randrange(n)
                    ops.append(["query", l, rng.randrange(l, n)])
            self.assertEqual(m.range_sum_point_updates(items, ops),
                             oracle(items, ops))

class TestCountSubarraysBoundedMax(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.count_subarrays_bounded_max([1, 2, 3], 1, 2), 3)
        self.assertEqual(m.count_subarrays_bounded_max(
            [2, 1, 4, 3], 2, 3), 3)
        self.assertEqual(m.count_subarrays_bounded_max([5, 5, 5], 1, 4), 0)
        self.assertEqual(m.count_subarrays_bounded_max([5, 5, 5], 5, 5), 6)
        self.assertEqual(m.count_subarrays_bounded_max([-2, -1], -2, -1), 3)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.count_subarrays_bounded_max([1], 3, 2)
        self.assertEqual(str(ctx.exception), refusal(
            "count_subarrays_bounded_max:bad_value:hi"))
        with self.assertRaises(ValueError) as ctx:
            m.count_subarrays_bounded_max([1], 0, 2 ** 31)
        self.assertEqual(str(ctx.exception), refusal(
            "count_subarrays_bounded_max:out_of_range:hi"))
        with self.assertRaises(ValueError) as ctx:
            m.count_subarrays_bounded_max([1], "a", 2)
        self.assertEqual(str(ctx.exception), refusal(
            "count_subarrays_bounded_max:bad_type:lo"))

    def test_oracle(self):
        def oracle(values, lo, hi):
            total = 0
            for i in range(len(values)):
                peak = values[i]
                for j in range(i, len(values)):
                    peak = max(peak, values[j])
                    if lo <= peak <= hi:
                        total += 1
            return total
        rng = random.Random(8604)
        for _ in range(60):
            n = rng.randint(1, 12)
            values = [rng.randint(-9, 9) for _ in range(n)]
            lo = rng.randint(-9, 9)
            hi = rng.randint(lo, 12)
            self.assertEqual(m.count_subarrays_bounded_max(values, lo, hi),
                             oracle(values, lo, hi))

class TestStockSpanList(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(
            m.stock_span_list([100, 80, 60, 70, 60, 75, 85]),
            [1, 1, 1, 2, 1, 4, 6])
        self.assertEqual(m.stock_span_list([5, 5, 5]), [1, 2, 3])
        self.assertEqual(m.stock_span_list([3, 1, 2]), [1, 1, 2])
        self.assertEqual(m.stock_span_list([-2, -3]), [1, 1])

    def test_oracle(self):
        def oracle(items):
            out = []
            for i in range(len(items)):
                c = 1
                j = i - 1
                while j >= 0 and items[j] <= items[i]:
                    c += 1
                    j -= 1
                out.append(c)
            return out
        rng = random.Random(8615)
        for _ in range(60):
            n = rng.randint(1, 25)
            items = [rng.randint(-10, 10) for _ in range(n)]
            self.assertEqual(m.stock_span_list(items), oracle(items))

class TestCapsAtLimit(unittest.TestCase):
    def test_nonoverlap_at_cap(self):
        self.assertEqual(m.max_sum_two_nonoverlap(
            [1] * MAX_ITEMS, 1, 1), 2)

class TestRegistryKnowsBatch86(unittest.TestCase):
    def test_registry_knows_batch86(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("max_sum_two_nonoverlap", "range_sum_point_updates",
                     "count_subarrays_bounded_max", "stock_span_list"):
            self.assertIn(name, names)

if __name__ == "__main__":
    unittest.main()
