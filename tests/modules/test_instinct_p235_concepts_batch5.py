"""P235 batch 5 concepts (logic/graph/misc): red-first, independent oracles."""
from __future__ import annotations

import unittest
from datetime import date
from fractions import Fraction

NAMES = ("all_pairs_distinct", "reachability_set", "dag_depth",
         "bracket_balance_check", "semver_compare", "bit_flags_decode",
         "vote_threshold_check", "interval_overlap_count",
         "date_ordinal_offset", "levenshtein_distance")


class Batch5Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch5 as m
        self.m = m

    def test_all_pairs_distinct(self):
        self.assertTrue(self.m.all_pairs_distinct(["a", "b", "c"]))
        self.assertFalse(self.m.all_pairs_distinct(["a", "b", "a"]))
        self.assertTrue(self.m.all_pairs_distinct([]))
        with self.assertRaises(ValueError):
            self.m.all_pairs_distinct([1])

    def test_reachability_set(self):
        adj = {"a": ["b", "c"], "b": ["d"], "c": [], "d": ["b"]}
        self.assertEqual(self.m.reachability_set(adj, "a"), ["a", "b", "c", "d"])
        self.assertEqual(self.m.reachability_set(adj, "c"), ["c"])
        # oracle: simple BFS written independently
        seen, queue = {"a"}, ["a"]
        while queue:
            n = queue.pop(0)
            for m2 in adj[n]:
                if m2 not in seen:
                    seen.add(m2)
                    queue.append(m2)
        self.assertEqual(set(self.m.reachability_set(adj, "a")), seen)
        with self.assertRaises(ValueError):
            self.m.reachability_set(adj, "zzz")
        with self.assertRaises(ValueError):
            self.m.reachability_set({"a": ["ghost"]}, "a")

    def test_dag_depth(self):
        self.assertEqual(self.m.dag_depth(["a", "b", "c"], [["a", "b"], ["b", "c"]]), 3)
        self.assertEqual(self.m.dag_depth(["a", "b"], []), 1)
        with self.assertRaises(ValueError) as c:
            self.m.dag_depth(["a", "b"], [["a", "b"], ["b", "a"]])
        self.assertTrue(str(c.exception).startswith("P235:dag_depth:cycle"))

    def test_bracket_balance_check(self):
        self.assertTrue(self.m.bracket_balance_check("({[]})"))
        self.assertFalse(self.m.bracket_balance_check("(]"))
        self.assertFalse(self.m.bracket_balance_check("((("))
        self.assertTrue(self.m.bracket_balance_check("no brackets"))
        with self.assertRaises(ValueError):
            self.m.bracket_balance_check(5)

    def test_semver_compare(self):
        self.assertEqual(self.m.semver_compare("1.2.3", "1.2.10"), -1)
        self.assertEqual(self.m.semver_compare("2.0.0", "2.0.0"), 0)
        self.assertEqual(self.m.semver_compare("1.10.0", "1.9.9"), 1)
        for bad in ("1.2", "1.2.3.4", "a.b.c", "1.-2.3", ""):
            with self.assertRaises(ValueError, msg=bad):
                self.m.semver_compare(bad, "1.0.0")

    def test_bit_flags_decode(self):
        r = self.m.bit_flags_decode(0b101, ["read", "write", "exec"])
        self.assertEqual(r, {"read": True, "write": False, "exec": True})
        with self.assertRaises(ValueError) as c:
            self.m.bit_flags_decode(8, ["read"])
        self.assertTrue(str(c.exception).startswith("P235:bit_flags_decode:excess_bits"))
        with self.assertRaises(ValueError):
            self.m.bit_flags_decode(-1, ["read"])
        with self.assertRaises(ValueError):
            self.m.bit_flags_decode(0, ["a"] * 65)

    def test_vote_threshold_check(self):
        r = self.m.vote_threshold_check(3, 1, "2/3")
        self.assertEqual(r, {"quorum_met": True, "passed": True,
                             "share": Fraction(3, 4), "threshold": Fraction(2, 3)})
        r2 = self.m.vote_threshold_check(1, 2, "2/3")
        self.assertFalse(r2["passed"])
        r3 = self.m.vote_threshold_check(0, 0, "1/2")
        self.assertFalse(r3["quorum_met"])
        with self.assertRaises(ValueError):
            self.m.vote_threshold_check(-1, 0, "1/2")
        with self.assertRaises(ValueError):
            self.m.vote_threshold_check(1, 0, "3/2")
        with self.assertRaises(ValueError):
            self.m.vote_threshold_check(True, 0, "1/2")

    def test_interval_overlap_count(self):
        iv = [[1, 3], [2, 4], [5, 6]]
        self.assertEqual(self.m.interval_overlap_count(iv), 1)
        self.assertEqual(self.m.interval_overlap_count([[1, 2], [3, 4]]), 0)
        # oracle: brute-force pair check
        n = 0
        for i in range(len(iv)):
            for j in range(i + 1, len(iv)):
                a, b = iv[i], iv[j]
                if a[0] <= b[1] and b[0] <= a[1]:
                    n += 1
        self.assertEqual(self.m.interval_overlap_count(iv), n)
        with self.assertRaises(ValueError):
            self.m.interval_overlap_count([[3, 1]])

    def test_date_ordinal_offset(self):
        r = self.m.date_ordinal_offset("2026-01-01", "2026-10-13")
        oracle = (date(2026, 10, 13) - date(2026, 1, 1)).days
        self.assertEqual(r, oracle)
        self.assertEqual(self.m.date_ordinal_offset("2026-10-13", "2026-01-01"), -oracle)
        with self.assertRaises(ValueError):
            self.m.date_ordinal_offset("13/10/2026", "2026-01-01")

    def test_levenshtein_distance(self):
        self.assertEqual(self.m.levenshtein_distance("kitten", "sitting"), 3)
        self.assertEqual(self.m.levenshtein_distance("", "abc"), 3)
        self.assertEqual(self.m.levenshtein_distance("same", "same"), 0)
        with self.assertRaises(ValueError):
            self.m.levenshtein_distance("x" * 1001, "y")
        with self.assertRaises(ValueError):
            self.m.levenshtein_distance(1, "y")

    def test_registry_covers_batch5(self):
        from app.modules.instinct_doc import p235_concepts_registry as reg
        entries = {e["name"]: e for e in reg.ENTRIES if e["batch"] == 5}
        self.assertEqual(set(entries), set(NAMES))


    def test_semver_two_digit_parts(self):
        self.assertEqual(self.m.semver_compare("0.0.0", "0.0.1"), -1)
        self.assertEqual(self.m.semver_compare("0.0.0", "0.0.0"), 0)
        self.assertEqual(self.m.semver_compare("10.20.30", "10.20.31"), -1)
        for bad in ("01.0.0", "1.02.3", "1.2.03"):
            with self.assertRaises(ValueError):
                self.m.semver_compare(bad, "0.0.0")

if __name__ == "__main__":
    unittest.main()
