"""P235 concepts batch 12 (111-120, text/algorithms): red-first tests."""
from __future__ import annotations

import unittest
from fractions import Fraction


class Batch12Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch12 as m
        self.m = m

    def test_run_length_decode(self):
        self.assertEqual(self.m.run_length_decode([["a", 3], ["b", 2]]),
                         ["a", "a", "a", "b", "b"])
        self.assertEqual(self.m.run_length_decode([]), [])
        self.assertEqual(self.m.run_length_decode([["x", 1]]), ["x"])
        with self.assertRaises(ValueError) as c:
            self.m.run_length_decode([["a", 0]])
        self.assertEqual(str(c.exception), "P235:run_length_decode:bad_value:count")
        with self.assertRaises(ValueError):
            self.m.run_length_decode([["a"]])
        with self.assertRaises(ValueError):
            self.m.run_length_decode([[1, 2]])
        with self.assertRaises(ValueError) as c2:
            self.m.run_length_decode([["a", 10_001]])
        self.assertEqual(str(c2.exception), "P235:run_length_decode:too_many:output")

    def test_string_rotation_check(self):
        self.assertTrue(self.m.string_rotation_check("abcde", "cdeab"))
        self.assertFalse(self.m.string_rotation_check("abc", "acb"))
        self.assertFalse(self.m.string_rotation_check("abc", "ab"))
        self.assertTrue(self.m.string_rotation_check("", ""))
        with self.assertRaises(ValueError):
            self.m.string_rotation_check("ab", 12)

    def test_longest_palindromic_substring_length(self):
        self.assertEqual(self.m.longest_palindromic_substring_length("babad"), 3)
        self.assertEqual(self.m.longest_palindromic_substring_length(""), 0)
        self.assertEqual(self.m.longest_palindromic_substring_length("abcd"), 1)
        self.assertEqual(self.m.longest_palindromic_substring_length("aaaa"), 4)
        with self.assertRaises(ValueError) as c:
            self.m.longest_palindromic_substring_length("x" * 1001)
        self.assertEqual(str(c.exception),
                         "P235:longest_palindromic_substring_length:too_many:text")

    def test_count_vowels(self):
        self.assertEqual(self.m.count_vowels("Hello World"), 3)
        self.assertEqual(self.m.count_vowels(""), 0)
        self.assertEqual(self.m.count_vowels("AEIOUaeiou"), 10)
        self.assertEqual(self.m.count_vowels("xyz"), 0)
        with self.assertRaises(ValueError):
            self.m.count_vowels(42)

    def test_second_largest_distinct(self):
        self.assertEqual(self.m.second_largest_distinct([1, 2, 2, 3]), 2)
        self.assertIsNone(self.m.second_largest_distinct([5, 5]))
        self.assertIsNone(self.m.second_largest_distinct([]))
        self.assertEqual(self.m.second_largest_distinct([-1, -2]), -2)
        with self.assertRaises(ValueError):
            self.m.second_largest_distinct([1, "x"])

    def test_majority_element(self):
        self.assertEqual(self.m.majority_element([3, 2, 3]), 3)
        self.assertIsNone(self.m.majority_element([1, 2, 3]))
        self.assertIsNone(self.m.majority_element([]))
        self.assertEqual(self.m.majority_element([7]), 7)
        with self.assertRaises(ValueError):
            self.m.majority_element([1, True])

    def test_rotate_matrix_90(self):
        self.assertEqual(self.m.rotate_matrix_90([[1, 2], [3, 4]]), [[3, 1], [4, 2]])
        self.assertEqual(self.m.rotate_matrix_90([[1]]), [[1]])
        self.assertEqual(self.m.rotate_matrix_90([]), [])
        with self.assertRaises(ValueError) as c:
            self.m.rotate_matrix_90([[1, 2]])
        self.assertEqual(str(c.exception), "P235:rotate_matrix_90:not_square:matrix")
        with self.assertRaises(ValueError):
            self.m.rotate_matrix_90([[1], [2, 3]])

    def test_identity_matrix_check(self):
        self.assertTrue(self.m.identity_matrix_check([[1, 0], [0, 1]]))
        self.assertFalse(self.m.identity_matrix_check([[1, 0, 0], [0, 1, 0]]))
        self.assertFalse(self.m.identity_matrix_check([[1, 1], [0, 1]]))
        self.assertFalse(self.m.identity_matrix_check([]))
        with self.assertRaises(ValueError):
            self.m.identity_matrix_check([[1], [0, 1]])

    def test_moving_average_exact(self):
        self.assertEqual(self.m.moving_average_exact([1, 2, 3, 4], 2),
                         [Fraction(3, 2), Fraction(5, 2), Fraction(7, 2)])
        self.assertEqual(self.m.moving_average_exact([6], 1), [Fraction(6)])
        with self.assertRaises(ValueError) as c:
            self.m.moving_average_exact([1, 2], 3)
        self.assertEqual(str(c.exception), "P235:moving_average_exact:bad_value:k")
        with self.assertRaises(ValueError):
            self.m.moving_average_exact([1, 2], 0)
        with self.assertRaises(ValueError):
            self.m.moving_average_exact([1, 1.5], 1)

    def test_unique_char_first_index(self):
        self.assertEqual(self.m.unique_char_first_index("leetcode"), 0)
        self.assertEqual(self.m.unique_char_first_index("loveleetcode"), 2)
        self.assertEqual(self.m.unique_char_first_index("aabb"), -1)
        self.assertEqual(self.m.unique_char_first_index(""), -1)
        with self.assertRaises(ValueError):
            self.m.unique_char_first_index(7)


if __name__ == "__main__":
    unittest.main()
