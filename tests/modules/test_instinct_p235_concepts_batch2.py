"""P235 batch 2 concepts: red-first tests with independent oracles."""
from __future__ import annotations

import unittest

NAMES = ("set_disjoint_check", "frequency_table", "invert_mapping",
         "intersection_size", "symmetric_difference_list", "group_by_key",
         "count_distinct_casefold", "first_duplicate", "bucket_by_range",
         "mode_exact")


class Batch2Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch2 as m
        self.m = m

    def test_set_disjoint_check(self):
        self.assertTrue(self.m.set_disjoint_check(["a", "b"], ["c", "d"]))
        self.assertFalse(self.m.set_disjoint_check(["a", "b"], ["b", "c"]))
        self.assertTrue(self.m.set_disjoint_check([], []))
        with self.assertRaises(ValueError):
            self.m.set_disjoint_check([True], ["a"])
        with self.assertRaises(ValueError):
            self.m.set_disjoint_check([1], ["a"])

    def test_frequency_table(self):
        r = self.m.frequency_table(["b", "a", "b"])
        self.assertEqual(r, {"a": 1, "b": 2})
        self.assertEqual(list(r), sorted(r))  # deterministic key order
        oracle = {}
        for x in ["b", "a", "b"]:
            oracle[x] = oracle.get(x, 0) + 1
        self.assertEqual(dict(r), oracle)
        with self.assertRaises(ValueError):
            self.m.frequency_table([1])

    def test_invert_mapping(self):
        self.assertEqual(self.m.invert_mapping({"a": "1", "b": "2"}),
                         {"1": "a", "2": "b"})
        with self.assertRaises(ValueError) as c:
            self.m.invert_mapping({"a": "1", "b": "1"})
        self.assertTrue(str(c.exception).startswith("P235:invert_mapping:not_injective"))
        with self.assertRaises(ValueError):
            self.m.invert_mapping({"a": 1})

    def test_intersection_size(self):
        self.assertEqual(self.m.intersection_size(["a", "b", "c"], ["b", "c", "d"]), 2)
        self.assertEqual(self.m.intersection_size([], ["a"]), 0)
        with self.assertRaises(ValueError):
            self.m.intersection_size([1], ["1"])

    def test_symmetric_difference_list(self):
        self.assertEqual(self.m.symmetric_difference_list(["a", "b"], ["b", "c"]),
                         ["a", "c"])
        self.assertEqual(self.m.symmetric_difference_list(["a"], ["a"]), [])

    def test_group_by_key(self):
        recs = [{"k": "x", "v": 1}, {"k": "y", "v": 2}, {"k": "x", "v": 3}]
        r = self.m.group_by_key(recs, "k")
        self.assertEqual([x["v"] for x in r["x"]], [1, 3])
        self.assertEqual([x["v"] for x in r["y"]], [2])
        with self.assertRaises(ValueError):
            self.m.group_by_key([{"v": 1}], "k")
        with self.assertRaises(ValueError):
            self.m.group_by_key([["notdict"]], "k")

    def test_count_distinct_casefold(self):
        self.assertEqual(self.m.count_distinct_casefold(["AdmitSee", "admitsee", "X"]), 2)
        self.assertEqual(self.m.count_distinct_casefold([]), 0)
        with self.assertRaises(ValueError):
            self.m.count_distinct_casefold([b"bytes"])

    def test_first_duplicate(self):
        self.assertEqual(self.m.first_duplicate(["a", "b", "a", "b"]), "a")
        self.assertIsNone(self.m.first_duplicate(["a", "b"]))

    def test_bucket_by_range(self):
        r = self.m.bucket_by_range([0, 1, 5, 9, 10, -1], 5)
        self.assertEqual(r, {0: [0, 1], 1: [5, 9], 2: [10], -1: [-1]})
        with self.assertRaises(ValueError):
            self.m.bucket_by_range([1], 0)
        with self.assertRaises(ValueError):
            self.m.bucket_by_range([1.5], 5)

    def test_mode_exact(self):
        r = self.m.mode_exact(["a", "b", "a", "b", "c"])
        self.assertEqual(r, {"modes": ["a", "b"], "count": 2})
        r2 = self.m.mode_exact(["x"])
        self.assertEqual(r2, {"modes": ["x"], "count": 1})
        with self.assertRaises(ValueError):
            self.m.mode_exact([])

    def test_registry_covers_batch2(self):
        from app.modules.instinct_doc import p235_concepts_registry as reg
        entries = {e["name"]: e for e in reg.ENTRIES if e["batch"] == 2}
        self.assertEqual(set(entries), set(NAMES))


if __name__ == "__main__":
    unittest.main()
