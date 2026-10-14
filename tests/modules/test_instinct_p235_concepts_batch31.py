"""P235 concepts batch 31 tests - red-first."""
from __future__ import annotations

import unittest
from fractions import Fraction


class Batch31Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch31 as m
        self.m = m

    def test_jaro_similarity_exact(self):
        self.assertEqual(self.m.jaro_similarity_exact("abc", "abc"),
                         Fraction(1))
        self.assertEqual(self.m.jaro_similarity_exact("", ""), Fraction(1))
        self.assertEqual(self.m.jaro_similarity_exact("abc", ""), Fraction(0))
        self.assertEqual(self.m.jaro_similarity_exact("MARTHA", "MARHTA"),
                         Fraction(17, 18))
        self.assertEqual(self.m.jaro_similarity_exact("DIXON", "DICKSONX"),
                         Fraction(23, 30))
        self.assertEqual(self.m.jaro_similarity_exact("abc", "xyz"),
                         Fraction(0))
        with self.assertRaises(ValueError) as c:
            self.m.jaro_similarity_exact("a" * 1_001, "b")
        self.assertEqual(str(c.exception),
                         "P235:jaro_similarity_exact:too_many:a")
        with self.assertRaises(ValueError) as c:
            self.m.jaro_similarity_exact(True, "b")
        self.assertEqual(str(c.exception),
                         "P235:jaro_similarity_exact:bad_type:a")

    def test_jaro_similarity_reference_oracle(self):
        # independent reference: same greedy matching definition, written
        # separately, exact Fraction transpositions (t may be a
        # half-integer)
        def reference(a, b):
            if a == b:
                return Fraction(1)
            if not a or not b:
                return Fraction(0)
            window = max(max(len(a), len(b)) // 2 - 1, 0)
            used_b = [False] * len(b)
            pairs = []
            for i, ch in enumerate(a):
                for j in range(max(0, i - window),
                               min(len(b), i + window + 1)):
                    if not used_b[j] and b[j] == ch:
                        used_b[j] = True
                        pairs.append((i, j))
                        break
            m = len(pairs)
            if m == 0:
                return Fraction(0)
            seq_a = [a[i] for i, _j in pairs]
            seq_b = [b[j] for _i, j in sorted(pairs,
                                              key=lambda p: p[1])]
            mismatches = sum(1 for x, y in zip(seq_a, seq_b) if x != y)
            t = Fraction(mismatches, 2)
            return Fraction(Fraction(m, len(a)) + Fraction(m, len(b))
                            + Fraction(m - t, m), 3)

        words = []
        for n in range(1, 5):
            for mask in range(2 ** n):
                words.append("".join("ab"[(mask >> k) & 1]
                                     for k in range(n)))
        for a in words:
            for b in words:
                self.assertEqual(self.m.jaro_similarity_exact(a, b),
                                 reference(a, b), (a, b))

    def test_jaro_similarity_transposition_parity(self):
        # even transpositions: textbook values
        self.assertEqual(self.m.jaro_similarity_exact("MARTHA", "MARHTA"),
                         Fraction(17, 18))
        # odd out-of-order count (3): t is the half-integer 3/2, so the
        # exact value is 11/12, not the floored 17/18
        self.assertEqual(self.m.jaro_similarity_exact("aaaabc", "aaabca"),
                         Fraction(11, 12))

    def test_shuffle_check_backtrack(self):
        # greedy two pointers cannot decide which string the first "a"
        # came from; the DP accepts the valid interleaving
        self.assertTrue(self.m.shuffle_check("a", "ab", "aba"))
        self.assertTrue(self.m.shuffle_check("ab", "a", "aba"))

    def test_shuffle_check_bruteforce_oracle(self):
        from itertools import product

        def interleavings(a, b):
            out = set()

            def rec(i, j, acc):
                if i == len(a) and j == len(b):
                    out.add(acc)
                    return
                if i < len(a):
                    rec(i + 1, j, acc + a[i])
                if j < len(b):
                    rec(i, j + 1, acc + b[j])
            rec(0, 0, "")
            return out

        words = [""]
        for n in range(1, 4):
            for tup in product("ab", repeat=n):
                words.append("".join(tup))
        for a in words:
            for b in words:
                valid = interleavings(a, b)
                for cand in valid | {
                        "".join(t) for t in product(
                            "ab", repeat=len(a) + len(b))}:
                    self.assertEqual(self.m.shuffle_check(a, b, cand),
                                     cand in valid, (a, b, cand))

    def test_prefix_function(self):
        self.assertEqual(self.m.prefix_function("abcabcd"), [0, 0, 0, 1, 2, 3, 0])
        self.assertEqual(self.m.prefix_function("aaaa"), [0, 1, 2, 3])
        self.assertEqual(self.m.prefix_function("ab"), [0, 0])
        self.assertEqual(self.m.prefix_function("a"), [0])
        with self.assertRaises(ValueError) as c:
            self.m.prefix_function("")
        self.assertEqual(str(c.exception),
                         "P235:prefix_function:bad_value:text")
        with self.assertRaises(ValueError) as c:
            self.m.prefix_function("a" * 10_001)
        self.assertEqual(str(c.exception),
                         "P235:prefix_function:too_many:text")

    def test_saddle_point_find(self):
        self.assertEqual(self.m.saddle_point_find([[1, 3], [4, 2]]), -1)
        # 7 is the row-3 minimum and the column-1 maximum
        self.assertEqual(self.m.saddle_point_find(
            [[1, 2, 3], [4, 5, 6], [7, 8, 9]]), [2, 0])
        self.assertEqual(self.m.saddle_point_find(
            [[3, 2, 3], [2, 1, 2], [3, 2, 3]]), [0, 1])
        self.assertEqual(self.m.saddle_point_find([[7]]), [0, 0])
        with self.assertRaises(ValueError) as c:
            self.m.saddle_point_find([])
        self.assertEqual(str(c.exception),
                         "P235:saddle_point_find:bad_value:rows")
        with self.assertRaises(ValueError) as c:
            self.m.saddle_point_find([[1, 2], [3]])
        self.assertEqual(str(c.exception),
                         "P235:saddle_point_find:bad_value:rows")

    def test_toeplitz_check(self):
        self.assertTrue(self.m.toeplitz_check(
            [[1, 2, 3], [4, 1, 2], [5, 4, 1]]))
        self.assertFalse(self.m.toeplitz_check(
            [[1, 2], [2, 2]]))
        self.assertTrue(self.m.toeplitz_check([[7]]))
        self.assertTrue(self.m.toeplitz_check([[1, 2, 3]]))
        self.assertTrue(self.m.toeplitz_check(
            [[1, 2], [3, 1], [4, 3]]))
        with self.assertRaises(ValueError) as c:
            self.m.toeplitz_check([[1, 2], [3]])
        self.assertEqual(str(c.exception),
                         "P235:toeplitz_check:bad_value:rows")

    def test_histogram_largest_rect(self):
        self.assertEqual(self.m.histogram_largest_rect([2, 1, 5, 6, 2, 3]),
                         10)
        self.assertEqual(self.m.histogram_largest_rect([2, 1, 2]), 3)
        self.assertEqual(self.m.histogram_largest_rect([4]), 4)
        self.assertEqual(self.m.histogram_largest_rect([0, 0]), 0)
        with self.assertRaises(ValueError) as c:
            self.m.histogram_largest_rect([])
        self.assertEqual(str(c.exception),
                         "P235:histogram_largest_rect:empty:heights")
        with self.assertRaises(ValueError) as c:
            self.m.histogram_largest_rect([10_001])
        self.assertEqual(str(c.exception),
                         "P235:histogram_largest_rect:bad_value:heights[0]")

    def test_trap_rain_water(self):
        self.assertEqual(self.m.trap_rain_water(
            [0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1]), 6)
        self.assertEqual(self.m.trap_rain_water([3, 0, 3]), 3)
        self.assertEqual(self.m.trap_rain_water([1, 2, 3]), 0)
        self.assertEqual(self.m.trap_rain_water([]), 0)
        with self.assertRaises(ValueError) as c:
            self.m.trap_rain_water([10_001])
        self.assertEqual(str(c.exception),
                         "P235:trap_rain_water:bad_value:heights[0]")

    def test_next_greater_elements(self):
        self.assertEqual(self.m.next_greater_elements([1, 3, 2]),
                         [3, -1, -1])
        self.assertEqual(self.m.next_greater_elements([4, 3, 2, 1]),
                         [-1, -1, -1, -1])
        self.assertEqual(self.m.next_greater_elements([1, 1, 2]),
                         [2, 2, -1])
        self.assertEqual(self.m.next_greater_elements([]), [])
        with self.assertRaises(ValueError) as c:
            self.m.next_greater_elements([True])
        self.assertEqual(
            str(c.exception),
            "P235:next_greater_elements:bad_type:values[0]")

    def test_house_robber_max(self):
        self.assertEqual(self.m.house_robber_max([1, 2, 3, 1]), 4)
        self.assertEqual(self.m.house_robber_max([2, 7, 9, 3, 1]), 12)
        self.assertEqual(self.m.house_robber_max([2, 1, 1, 2]), 4)
        self.assertEqual(self.m.house_robber_max([]), 0)
        self.assertEqual(self.m.house_robber_max([5]), 5)
        with self.assertRaises(ValueError) as c:
            self.m.house_robber_max([-1])
        self.assertEqual(str(c.exception),
                         "P235:house_robber_max:bad_value:values[0]")

    def test_shuffle_check(self):
        self.assertTrue(self.m.shuffle_check("ab", "cd", "acbd"))
        self.assertTrue(self.m.shuffle_check("ab", "cd", "cdab"))
        self.assertTrue(self.m.shuffle_check("ab", "cd", "acdb"))
        self.assertFalse(self.m.shuffle_check("ab", "cd", "abdc"))
        self.assertTrue(self.m.shuffle_check("", "cd", "cd"))
        self.assertTrue(self.m.shuffle_check("aab", "abc", "aababc"))
        self.assertFalse(self.m.shuffle_check("ab", "cd", "abd"))
        with self.assertRaises(ValueError) as c:
            self.m.shuffle_check(True, "cd", "cd")
        self.assertEqual(str(c.exception),
                         "P235:shuffle_check:bad_type:a")

    def test_cyclic_shift_lex_min(self):
        self.assertEqual(self.m.cyclic_shift_lex_min("baca"), "abac")
        self.assertEqual(self.m.cyclic_shift_lex_min("cba"), "acb")
        self.assertEqual(self.m.cyclic_shift_lex_min("aaaa"), "aaaa")
        self.assertEqual(self.m.cyclic_shift_lex_min("z"), "z")
        self.assertEqual(self.m.cyclic_shift_lex_min("bcabca"), "abcabc")
        with self.assertRaises(ValueError) as c:
            self.m.cyclic_shift_lex_min("")
        self.assertEqual(str(c.exception),
                         "P235:cyclic_shift_lex_min:bad_value:text")
        with self.assertRaises(ValueError) as c:
            self.m.cyclic_shift_lex_min("a" * 10_001)
        self.assertEqual(str(c.exception),
                         "P235:cyclic_shift_lex_min:too_many:text")


if __name__ == "__main__":
    unittest.main()
