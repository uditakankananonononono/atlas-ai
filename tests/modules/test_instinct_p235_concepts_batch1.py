"""P235 batch 1 concepts: red-first tests with independent oracles."""
from __future__ import annotations

import unittest
from fractions import Fraction

NAMES = ("topological_order", "stable_partition_parity", "run_length_encode",
         "sliding_window_max", "merge_sorted_streams", "dedupe_preserve_order",
         "rotate_left_k", "chunked_batching", "pairwise_deltas",
         "prefix_sums_fraction")


class Batch1Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch1 as m
        self.m = m

    def test_topological_order(self):
        m = self.m
        order = m.topological_order(["a", "b", "c"], [["a", "b"], ["b", "c"]])
        self.assertEqual(order, ["a", "b", "c"])
        # oracle: result is a permutation and every edge goes earlier -> later
        order2 = m.topological_order(["x", "y", "z"], [["z", "x"]])
        self.assertEqual(sorted(order2), ["x", "y", "z"])
        pos = {n: i for i, n in enumerate(order2)}
        self.assertLess(pos["z"], pos["x"])
        with self.assertRaises(ValueError) as c:
            m.topological_order(["a", "b"], [["a", "b"], ["b", "a"]])
        self.assertTrue(str(c.exception).startswith("P235:topological_order:cycle"))
        with self.assertRaises(ValueError) as c2:
            m.topological_order(["a", True], [])
        self.assertTrue(str(c2.exception).startswith("P235:topological_order:bad_type"))

    def test_stable_partition_parity(self):
        r = self.m.stable_partition_parity([5, 2, 7, 0, -3])
        self.assertEqual(r, {"evens": [2, 0], "odds": [5, 7, -3]})
        self.assertEqual(self.m.stable_partition_parity([]), {"evens": [], "odds": []})
        with self.assertRaises(ValueError):
            self.m.stable_partition_parity([True])
        with self.assertRaises(ValueError):
            self.m.stable_partition_parity([1.5])

    def test_run_length_encode(self):
        self.assertEqual(self.m.run_length_encode(["a", "a", "b", "a"]),
                         [["a", 2], ["b", 1], ["a", 1]])
        self.assertEqual(self.m.run_length_encode([]), [])
        with self.assertRaises(ValueError):
            self.m.run_length_encode([1])

    def test_sliding_window_max(self):
        self.assertEqual(self.m.sliding_window_max([1, 3, -1, 5], 2), [3, 3, 5])
        self.assertEqual(self.m.sliding_window_max([2], 1), [2])
        for bad_k in (0, -1, 5):
            with self.assertRaises(ValueError):
                self.m.sliding_window_max([1, 2], bad_k)
        with self.assertRaises(ValueError):
            self.m.sliding_window_max([1, float("nan")], 1)
        with self.assertRaises(ValueError):
            self.m.sliding_window_max([True], 1)

    def test_merge_sorted_streams(self):
        self.assertEqual(self.m.merge_sorted_streams([[1, 4], [2, 3], []]),
                         [1, 2, 3, 4])
        with self.assertRaises(ValueError) as c:
            self.m.merge_sorted_streams([[2, 1]])
        self.assertTrue(str(c.exception).startswith("P235:merge_sorted_streams:unsorted"))

    def test_dedupe_preserve_order(self):
        self.assertEqual(self.m.dedupe_preserve_order(["b", "a", "b", "c", "a"]),
                         ["b", "a", "c"])
        with self.assertRaises(ValueError):
            self.m.dedupe_preserve_order([None])

    def test_rotate_left_k(self):
        self.assertEqual(self.m.rotate_left_k([1, 2, 3, 4], 1), [2, 3, 4, 1])
        self.assertEqual(self.m.rotate_left_k([1, 2, 3, 4], 6), [3, 4, 1, 2])
        self.assertEqual(self.m.rotate_left_k([], 3), [])
        with self.assertRaises(ValueError):
            self.m.rotate_left_k([1], -1)

    def test_chunked_batching(self):
        self.assertEqual(self.m.chunked_batching([1, 2, 3, 4, 5], 2),
                         [[1, 2], [3, 4], [5]])
        self.assertEqual(self.m.chunked_batching([], 3), [])
        with self.assertRaises(ValueError):
            self.m.chunked_batching([1], 0)

    def test_pairwise_deltas(self):
        self.assertEqual(self.m.pairwise_deltas([1, 4, 2, 10]), [3, -2, 8])
        self.assertEqual(self.m.pairwise_deltas([7]), [])
        with self.assertRaises(ValueError):
            self.m.pairwise_deltas([1, "x"])

    def test_prefix_sums_fraction(self):
        r = self.m.prefix_sums_fraction(["1/2", "1/3", 1])
        oracle = [Fraction(1, 2), Fraction(1, 2) + Fraction(1, 3),
                  Fraction(1, 2) + Fraction(1, 3) + 1]
        self.assertEqual(r, oracle)
        self.assertTrue(all(isinstance(x, Fraction) for x in r))
        with self.assertRaises(ValueError):
            self.m.prefix_sums_fraction(["1/0"])
        with self.assertRaises(ValueError):
            self.m.prefix_sums_fraction(["abc"])
        with self.assertRaises(ValueError):
            self.m.prefix_sums_fraction([1.5])  # floats refused: exact only

    def test_caps(self):
        m = self.m
        with self.assertRaises(ValueError) as c:
            m.dedupe_preserve_order(["x%d" % i for i in range(m.MAX_ITEMS + 1)])
        self.assertTrue(str(c.exception).startswith("P235:dedupe_preserve_order:too_many"))

    def test_registry_covers_batch1(self):
        from app.modules.instinct_doc import p235_concepts_registry as reg
        entries = {e["name"]: e for e in reg.ENTRIES if e["batch"] == 1}
        self.assertEqual(set(entries), set(NAMES))
        for name in NAMES:
            self.assertTrue(callable(getattr(self.m, name)))


    def test_sliding_window_max_refuses_nonfinite(self):
        for bad in (float("inf"), float("-inf"), float("nan")):
            with self.assertRaises(ValueError) as c:
                self.m.sliding_window_max([1, bad], 1)
            self.assertTrue(str(c.exception).startswith(
                "P235:sliding_window_max:bad_value:"))
        self.assertEqual(self.m.sliding_window_max([1.5, 2.5, 1.0], 2),
                         [2.5, 2.5])

    def test_merge_sorted_streams_aggregate_cap(self):
        with self.assertRaises(ValueError) as c:
            self.m.merge_sorted_streams([[0] * 5001, [1] * 5001])
        self.assertEqual(str(c.exception),
                         "P235:merge_sorted_streams:too_many:aggregate")
        self.assertEqual(self.m.merge_sorted_streams([[1, 3], [2, 4], []]),
                         [1, 2, 3, 4])
        self.assertEqual(self.m.merge_sorted_streams([]), [])

    def test_to_fraction_bool_still_refused(self):
        with self.assertRaises(ValueError):
            self.m.prefix_sums_fraction([True])

if __name__ == "__main__":
    unittest.main()
