"""P235 batch 6 concepts (51-60): red-first, independent oracles."""
from __future__ import annotations

import unittest
from fractions import Fraction

NAMES = ("flatten_one_level", "zip_strict_equal", "dict_get_path",
         "sort_by_key_stable", "count_where_closed", "running_max",
         "argmax_index", "split_at_index", "sum_exact_ints", "variance_exact")


class Batch6Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch6 as m
        self.m = m

    def test_flatten_one_level(self):
        self.assertEqual(self.m.flatten_one_level([[1, 2], [3], []]), [1, 2, 3])
        self.assertEqual(self.m.flatten_one_level([]), [])
        with self.assertRaises(ValueError):
            self.m.flatten_one_level([1, [2]])
        with self.assertRaises(ValueError):
            self.m.flatten_one_level([[True]])

    def test_zip_strict_equal(self):
        self.assertEqual(self.m.zip_strict_equal([1, 2], ["a", "b"]),
                         [[1, "a"], [2, "b"]])
        with self.assertRaises(ValueError) as c:
            self.m.zip_strict_equal([1], [1, 2])
        self.assertTrue(str(c.exception).startswith("P235:zip_strict_equal:length_mismatch"))

    def test_dict_get_path(self):
        d = {"a": {"b": {"c": 7}}}
        self.assertEqual(self.m.dict_get_path(d, ["a", "b", "c"]), 7)
        with self.assertRaises(ValueError) as c:
            self.m.dict_get_path(d, ["a", "x"])
        self.assertTrue(str(c.exception).startswith("P235:dict_get_path:missing_path"))
        with self.assertRaises(ValueError):
            self.m.dict_get_path(d, [])
        with self.assertRaises(ValueError):
            self.m.dict_get_path({"a": 1}, ["a", "b"])

    def test_sort_by_key_stable(self):
        recs = [{"k": "b", "n": 1}, {"k": "a", "n": 2}, {"k": "b", "n": 3}]
        r = self.m.sort_by_key_stable(recs, "k")
        self.assertEqual([(x["k"], x["n"]) for x in r],
                         [("a", 2), ("b", 1), ("b", 3)])
        with self.assertRaises(ValueError):
            self.m.sort_by_key_stable([{"n": 1}], "k")

    def test_count_where_closed(self):
        self.assertEqual(self.m.count_where_closed([1, 2, 3, 4], "even"), 2)
        self.assertEqual(self.m.count_where_closed([1, 2, 3, 4], "odd"), 2)
        self.assertEqual(self.m.count_where_closed([-1, 0, 2], "positive"), 1)
        self.assertEqual(self.m.count_where_closed([-1, 0, 2], "negative"), 1)
        self.assertEqual(self.m.count_where_closed([-1, 0, 2], "zero"), 1)
        with self.assertRaises(ValueError) as c:
            self.m.count_where_closed([1], "lambda x: True")
        self.assertTrue(str(c.exception).startswith("P235:count_where_closed:bad_value"))

    def test_running_max(self):
        self.assertEqual(self.m.running_max([3, 1, 4, 1, 5]), [3, 3, 4, 4, 5])
        self.assertEqual(self.m.running_max([]), [])
        with self.assertRaises(ValueError):
            self.m.running_max([float("nan")])

    def test_argmax_index(self):
        self.assertEqual(self.m.argmax_index([1, 9, 9, 2]), 1)
        with self.assertRaises(ValueError):
            self.m.argmax_index([])

    def test_split_at_index(self):
        self.assertEqual(self.m.split_at_index([1, 2, 3], 1), ([1], [2, 3]))
        self.assertEqual(self.m.split_at_index([1, 2, 3], 0), ([], [1, 2, 3]))
        self.assertEqual(self.m.split_at_index([1, 2, 3], 3), ([1, 2, 3], []))
        with self.assertRaises(ValueError):
            self.m.split_at_index([1], 2)

    def test_sum_exact_ints(self):
        self.assertEqual(self.m.sum_exact_ints([10**20, 1, -2]), 10**20 - 1)
        self.assertEqual(self.m.sum_exact_ints([]), 0)
        with self.assertRaises(ValueError):
            self.m.sum_exact_ints([1.0])

    def test_variance_exact(self):
        r = self.m.variance_exact(["1", "2", "3", "4"])
        vals = [Fraction(1), Fraction(2), Fraction(3), Fraction(4)]
        mean = sum(vals) / 4
        oracle = sum((v - mean) ** 2 for v in vals) / 4
        self.assertEqual(r, oracle)
        self.assertIsInstance(r, Fraction)
        with self.assertRaises(ValueError):
            self.m.variance_exact([])
        with self.assertRaises(ValueError):
            self.m.variance_exact([1.5])

    def test_registry_covers_batch6(self):
        from app.modules.instinct_doc import p235_concepts_registry as reg
        entries = {e["name"]: e for e in reg.ENTRIES if e["batch"] == 6}
        self.assertEqual(set(entries), set(NAMES))
        self.assertGreaterEqual(reg.IMPLEMENTED_SO_FAR, len(reg.ENTRIES))


    def test_flatten_preflight_aggregate_cap(self):
        with self.assertRaises(ValueError) as c:
            self.m.flatten_one_level([[0] * 6000, [0] * 6000])
        self.assertEqual(str(c.exception),
                         "P235:flatten_one_level:too_many:flattened")
        # Cap trips during preflight, before any element is validated or
        # materialized: the bad int in the over-cap region is never read.
        with self.assertRaises(ValueError) as c2:
            self.m.flatten_one_level([[0] * 6000, [True] * 6000])
        self.assertEqual(str(c2.exception),
                         "P235:flatten_one_level:too_many:flattened")
        self.assertEqual(self.m.flatten_one_level([[0] * 9999, [1]]),
                         [0] * 9999 + [1])

if __name__ == "__main__":
    unittest.main()
