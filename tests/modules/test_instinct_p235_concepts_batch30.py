"""P235 concepts batch 30 tests - red-first."""
from __future__ import annotations

import unittest
from fractions import Fraction


class Batch30Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch30 as m
        self.m = m

    def test_permutation_rank(self):
        self.assertEqual(self.m.permutation_rank([0, 1, 2]), 0)
        self.assertEqual(self.m.permutation_rank([2, 1, 0]), 5)
        self.assertEqual(self.m.permutation_rank([1, 0, 2]), 2)
        self.assertEqual(self.m.permutation_rank([0]), 0)
        self.assertEqual(self.m.permutation_rank([3, 1, 2, 0]), 21)
        for bad, code in (([0, 0], "bad_value:perm"),
                          ([0, 2], "bad_value:perm"),
                          ([0, 1, 3], "bad_value:perm")):
            with self.assertRaises(ValueError, msg=bad) as c:
                self.m.permutation_rank(bad)
            self.assertEqual(str(c.exception),
                             "P235:permutation_rank:" + code)
        with self.assertRaises(ValueError) as c:
            self.m.permutation_rank(list(range(13)))
        self.assertEqual(str(c.exception),
                         "P235:permutation_rank:too_many:perm")
        with self.assertRaises(ValueError) as c:
            self.m.permutation_rank([True])
        self.assertEqual(str(c.exception),
                         "P235:permutation_rank:bad_type:perm[0]")

    def test_unrank_permutation(self):
        self.assertEqual(self.m.unrank_permutation(3, 0), [0, 1, 2])
        self.assertEqual(self.m.unrank_permutation(3, 5), [2, 1, 0])
        self.assertEqual(self.m.unrank_permutation(4, 21), [3, 1, 2, 0])
        for perm in ([0, 1, 2], [2, 1, 0], [3, 1, 2, 0], [1, 0]):
            self.assertEqual(
                self.m.unrank_permutation(
                    len(perm), self.m.permutation_rank(perm)), perm, perm)
        for k in (0, 1, 23, 119):
            n = 4 if k < 24 else 5
            self.assertEqual(
                self.m.permutation_rank(self.m.unrank_permutation(n, k)),
                k, k)
        with self.assertRaises(ValueError) as c:
            self.m.unrank_permutation(3, 6)
        self.assertEqual(str(c.exception),
                         "P235:unrank_permutation:bad_value:k")
        with self.assertRaises(ValueError) as c:
            self.m.unrank_permutation(0, 0)
        self.assertEqual(str(c.exception),
                         "P235:unrank_permutation:bad_value:n")

    def test_column_index_to_name(self):
        self.assertEqual(self.m.column_index_to_name(1), "A")
        self.assertEqual(self.m.column_index_to_name(26), "Z")
        self.assertEqual(self.m.column_index_to_name(27), "AA")
        self.assertEqual(self.m.column_index_to_name(28), "AB")
        self.assertEqual(self.m.column_index_to_name(702), "ZZ")
        self.assertEqual(self.m.column_index_to_name(703), "AAA")
        self.assertEqual(self.m.column_index_to_name(18_278), "ZZZ")
        for bad in (0, -1, 18_279):
            with self.assertRaises(ValueError, msg=bad) as c:
                self.m.column_index_to_name(bad)
            self.assertEqual(str(c.exception),
                             "P235:column_index_to_name:bad_value:n")
        with self.assertRaises(ValueError) as c:
            self.m.column_index_to_name(True)
        self.assertEqual(str(c.exception),
                         "P235:column_index_to_name:bad_type:n")

    def test_column_name_to_index(self):
        self.assertEqual(self.m.column_name_to_index("A"), 1)
        self.assertEqual(self.m.column_name_to_index("Z"), 26)
        self.assertEqual(self.m.column_name_to_index("AA"), 27)
        self.assertEqual(self.m.column_name_to_index("ZZZ"), 18_278)
        for name in ("A", "AZ", "ZZ", "AAA", "XFD", "ZZZ"):
            self.assertEqual(
                self.m.column_name_to_index(
                    self.m.column_index_to_name(
                        self.m.column_name_to_index(name))),
                self.m.column_name_to_index(name), name)
        for bad in ("a", "A1", "", "AAAA", "A A"):
            with self.assertRaises(ValueError, msg=bad) as c:
                self.m.column_name_to_index(bad)
            self.assertEqual(str(c.exception),
                             "P235:column_name_to_index:bad_value:name")

    def test_balanced_ternary_render(self):
        self.assertEqual(self.m.balanced_ternary_render(0), "0")
        self.assertEqual(self.m.balanced_ternary_render(1), "+")
        self.assertEqual(self.m.balanced_ternary_render(2), "+-")
        self.assertEqual(self.m.balanced_ternary_render(4), "++")
        self.assertEqual(self.m.balanced_ternary_render(5), "+--")
        self.assertEqual(self.m.balanced_ternary_render(-5), "-++")
        self.assertEqual(self.m.balanced_ternary_render(13), "+++")
        self.assertEqual(self.m.balanced_ternary_render(1_162_261_467),
                         "+" + "0" * 19)
        self.assertEqual(self.m.balanced_ternary_render(1_743_392_200),
                         "+" * 20)
        for bad in (1_743_392_201, -1_743_392_201):
            with self.assertRaises(ValueError, msg=bad) as c:
                self.m.balanced_ternary_render(bad)
            self.assertEqual(str(c.exception),
                             "P235:balanced_ternary_render:bad_value:n")

    def test_pisano_period(self):
        self.assertEqual(self.m.pisano_period(2), 3)
        self.assertEqual(self.m.pisano_period(3), 8)
        self.assertEqual(self.m.pisano_period(6), 24)
        self.assertEqual(self.m.pisano_period(10), 60)
        self.assertEqual(self.m.pisano_period(10_000), 15_000)
        for bad in (0, 1, 10_001):
            with self.assertRaises(ValueError, msg=bad) as c:
                self.m.pisano_period(bad)
            self.assertEqual(str(c.exception),
                             "P235:pisano_period:bad_value:m")

    def test_kaprekar_steps(self):
        self.assertEqual(self.m.kaprekar_steps(6174), 0)
        self.assertEqual(self.m.kaprekar_steps(3524), 3)
        self.assertEqual(self.m.kaprekar_steps(1000), 5)
        self.assertEqual(self.m.kaprekar_steps(2111), 5)
        for bad in (999, 10_000, 1111, 7777, 0, -5):
            with self.assertRaises(ValueError, msg=bad) as c:
                self.m.kaprekar_steps(bad)
            self.assertEqual(str(c.exception),
                             "P235:kaprekar_steps:bad_value:n")

    def test_motzkin_number(self):
        for n, want in ((0, 1), (1, 1), (2, 2), (3, 4), (4, 9), (5, 21),
                        (6, 51)):
            self.assertEqual(self.m.motzkin_number(n), want, n)
        with self.assertRaises(ValueError) as c:
            self.m.motzkin_number(501)
        self.assertEqual(str(c.exception),
                         "P235:motzkin_number:too_big:n")
        with self.assertRaises(ValueError) as c:
            self.m.motzkin_number(-1)
        self.assertEqual(str(c.exception),
                         "P235:motzkin_number:bad_value:n")

    def test_delannoy_number(self):
        self.assertEqual(self.m.delannoy_number(0, 0), 1)
        self.assertEqual(self.m.delannoy_number(1, 1), 3)
        self.assertEqual(self.m.delannoy_number(2, 2), 13)
        self.assertEqual(self.m.delannoy_number(3, 3), 63)
        self.assertEqual(self.m.delannoy_number(2, 1), 5)
        with self.assertRaises(ValueError) as c:
            self.m.delannoy_number(101, 0)
        self.assertEqual(str(c.exception),
                         "P235:delannoy_number:too_big:m")
        with self.assertRaises(ValueError) as c:
            self.m.delannoy_number(0, -1)
        self.assertEqual(str(c.exception),
                         "P235:delannoy_number:bad_value:n")

    def test_egyptian_fraction(self):
        self.assertEqual(self.m.egyptian_fraction(1, 7), [7])
        self.assertEqual(self.m.egyptian_fraction(2, 3), [2, 6])
        self.assertEqual(self.m.egyptian_fraction(3, 7), [3, 11, 231])
        self.assertEqual(self.m.egyptian_fraction(5, 6), [2, 3])
        # oracle: the denominators always sum back to the input fraction
        for p, q in ((3, 7), (5, 6), (7, 11), (2, 45), (9, 13)):
            terms = self.m.egyptian_fraction(p, q)
            self.assertEqual(sum(Fraction(1, d) for d in terms),
                             Fraction(p, q), (p, q))
            self.assertEqual(len(set(terms)), len(terms))
        for bad, code in (((0, 7), "bad_value:p"), ((7, 7), "bad_value:p"),
                          ((8, 7), "bad_value:p"),
                          ((3, 0), "bad_value:q"),
                          ((3, 10_001), "bad_value:q")):
            with self.assertRaises(ValueError, msg=bad) as c:
                self.m.egyptian_fraction(*bad)
            self.assertEqual(str(c.exception),
                             "P235:egyptian_fraction:" + code)


if __name__ == "__main__":
    unittest.main()
