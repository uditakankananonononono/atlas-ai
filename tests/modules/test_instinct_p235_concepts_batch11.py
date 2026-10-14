"""P235 concepts batch 11 (101-110, validation/DP): red-first tests."""
from __future__ import annotations

import unittest


class Batch11Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch11 as m
        self.m = m

    def test_luhn_check(self):
        self.assertTrue(self.m.luhn_check("79927398713"))
        self.assertFalse(self.m.luhn_check("79927398710"))
        self.assertTrue(self.m.luhn_check("0"))
        with self.assertRaises(ValueError) as c:
            self.m.luhn_check("7992a398713")
        self.assertEqual(str(c.exception), "P235:luhn_check:bad_value:digits")
        with self.assertRaises(ValueError):
            self.m.luhn_check("")
        with self.assertRaises(ValueError):
            self.m.luhn_check(79927398713)
        with self.assertRaises(ValueError) as c3:
            self.m.luhn_check("٩٩٢٧٣٩٨٧١٣")
        self.assertEqual(str(c3.exception), "P235:luhn_check:bad_value:digits")
        with self.assertRaises(ValueError) as c4:
            self.m.luhn_check("７９９２７３９８７１３")
        self.assertEqual(str(c4.exception), "P235:luhn_check:bad_value:digits")
        with self.assertRaises(ValueError) as c2:
            self.m.luhn_check("1" * 10_001)
        self.assertEqual(str(c2.exception), "P235:luhn_check:too_many:digits")

    def test_isbn10_check(self):
        self.assertTrue(self.m.isbn10_check("0306406152"))
        self.assertTrue(self.m.isbn10_check("080442957X"))
        self.assertFalse(self.m.isbn10_check("0306406153"))
        with self.assertRaises(ValueError) as c:
            self.m.isbn10_check("030640615")
        self.assertEqual(str(c.exception), "P235:isbn10_check:bad_value:isbn")
        self.assertFalse(self.m.isbn10_check("030640615X"))
        with self.assertRaises(ValueError):
            self.m.isbn10_check("030640615A")
        with self.assertRaises(ValueError) as c2:
            self.m.isbn10_check("０３０６４０６１５２")
        self.assertEqual(str(c2.exception), "P235:isbn10_check:bad_value:isbn")
        with self.assertRaises(ValueError):
            self.m.isbn10_check("٠٣٠٦٤٠٦١٥٢")

    def test_triangle_type(self):
        self.assertEqual(self.m.triangle_type(3, 4, 5), "scalene")
        self.assertEqual(self.m.triangle_type(2, 2, 2), "equilateral")
        self.assertEqual(self.m.triangle_type(2, 2, 3), "isosceles")
        with self.assertRaises(ValueError) as c:
            self.m.triangle_type(1, 2, 3)
        self.assertEqual(str(c.exception),
                         "P235:triangle_type:bad_value:sides")
        with self.assertRaises(ValueError):
            self.m.triangle_type(0, 1, 1)
        with self.assertRaises(ValueError):
            self.m.triangle_type(3, 4, True)

    def test_rect_overlap_area(self):
        self.assertEqual(self.m.rect_overlap_area([0, 0, 4, 4], [2, 2, 6, 6]), 4)
        self.assertEqual(self.m.rect_overlap_area([0, 0, 1, 1], [2, 2, 3, 3]), 0)
        self.assertEqual(self.m.rect_overlap_area([0, 0, 5, 5], [1, 1, 2, 2]), 1)
        with self.assertRaises(ValueError) as c:
            self.m.rect_overlap_area([4, 0, 2, 4], [0, 0, 1, 1])
        self.assertEqual(str(c.exception),
                         "P235:rect_overlap_area:bad_value:rect")
        with self.assertRaises(ValueError):
            self.m.rect_overlap_area([0, 0, 1], [0, 0, 1, 1])

    def test_spiral_matrix_order(self):
        self.assertEqual(self.m.spiral_matrix_order(
            [[1, 2, 3], [4, 5, 6], [7, 8, 9]]),
            [1, 2, 3, 6, 9, 8, 7, 4, 5])
        self.assertEqual(self.m.spiral_matrix_order([[1, 2], [3, 4]]), [1, 2, 4, 3])
        self.assertEqual(self.m.spiral_matrix_order([]), [])
        self.assertEqual(self.m.spiral_matrix_order([[5]]), [5])
        with self.assertRaises(ValueError):
            self.m.spiral_matrix_order([[1], [2, 3]])

    def test_subset_sum_exists(self):
        self.assertTrue(self.m.subset_sum_exists([3, 34, 4, 12, 5, 2], 9))
        self.assertFalse(self.m.subset_sum_exists([1, 2, 5], 4))
        self.assertTrue(self.m.subset_sum_exists([], 0))
        self.assertFalse(self.m.subset_sum_exists([], 3))
        with self.assertRaises(ValueError) as c:
            self.m.subset_sum_exists([1, 2], -1)
        self.assertEqual(str(c.exception), "P235:subset_sum_exists:bad_value:target")
        with self.assertRaises(ValueError):
            self.m.subset_sum_exists([-1, 2], 2)
        with self.assertRaises(ValueError) as c2:
            self.m.subset_sum_exists([1], self.m.MAX_TARGET + 1)
        self.assertEqual(str(c2.exception), "P235:subset_sum_exists:too_many:target")

    def test_coin_change_count(self):
        self.assertEqual(self.m.coin_change_count([1, 2, 5], 5), 4)
        self.assertEqual(self.m.coin_change_count([2], 3), 0)
        self.assertEqual(self.m.coin_change_count([1], 0), 1)
        with self.assertRaises(ValueError):
            self.m.coin_change_count([], 5)
        with self.assertRaises(ValueError):
            self.m.coin_change_count([0, 1], 2)
        with self.assertRaises(ValueError) as c2:
            self.m.coin_change_count([2, 2], 4)
        self.assertEqual(str(c2.exception),
                         "P235:coin_change_count:duplicate:coins")
        with self.assertRaises(ValueError) as c:
            self.m.coin_change_count([1], self.m.MAX_AMOUNT + 1)
        self.assertEqual(str(c.exception), "P235:coin_change_count:too_many:amount")

    def test_lcs_length(self):
        self.assertEqual(self.m.lcs_length("ABCBDAB", "BDCABA"), 4)
        self.assertEqual(self.m.lcs_length("", "abc"), 0)
        self.assertEqual(self.m.lcs_length("abc", "abc"), 3)
        with self.assertRaises(ValueError) as c:
            self.m.lcs_length("x" * 1001, "y")
        self.assertEqual(str(c.exception), "P235:lcs_length:too_many:text")
        with self.assertRaises(ValueError):
            self.m.lcs_length("ab", 12)

    def test_missing_number(self):
        self.assertEqual(self.m.missing_number([3, 0, 1]), 2)
        self.assertEqual(self.m.missing_number([0, 1]), 2)
        self.assertEqual(self.m.missing_number([1]), 0)
        self.assertEqual(self.m.missing_number([9, 6, 4, 2, 3, 5, 7, 0, 1]), 8)
        with self.assertRaises(ValueError) as c:
            self.m.missing_number([0, 0])
        self.assertEqual(str(c.exception), "P235:missing_number:bad_value:items")
        with self.assertRaises(ValueError):
            self.m.missing_number([0, 5])
        with self.assertRaises(ValueError):
            self.m.missing_number([0, True])

    def test_two_sum_indices(self):
        self.assertEqual(self.m.two_sum_indices([2, 7, 11, 15], 9), (0, 1))
        self.assertEqual(self.m.two_sum_indices([3, 3], 6), (0, 1))
        self.assertIsNone(self.m.two_sum_indices([1, 2, 3], 10))
        with self.assertRaises(ValueError):
            self.m.two_sum_indices([1, "x"], 3)
        with self.assertRaises(ValueError):
            self.m.two_sum_indices([1, 2], "3")

    def test_subset_sum_prune_bound(self):
        # The s+v <= target filter keeps the state set at target+1 entries
        # or fewer. With the filter forced True this input enumerates the
        # ~50 million reachable subset sums of 1..10,000 and blows up.
        items = list(range(1, 10_001))
        self.assertTrue(self.m.subset_sum_exists(items, 10_000))
        # small target keeps the state tiny even with many items
        self.assertTrue(self.m.subset_sum_exists(items, 1))
        # odd target unreachable from even items, bounded scan
        self.assertFalse(self.m.subset_sum_exists([2] * 5_000, 9_999))


if __name__ == "__main__":
    unittest.main()
