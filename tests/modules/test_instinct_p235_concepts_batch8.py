"""P235 concepts batch 8 (71-80, numeric/matrix): red-first tests."""
from __future__ import annotations

import unittest


class Batch8Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch8 as m
        self.m = m

    def test_transpose_matrix(self):
        self.assertEqual(self.m.transpose_matrix([[1, 2], [3, 4]]),
                         [[1, 3], [2, 4]])
        self.assertEqual(self.m.transpose_matrix([[1, 2, 3]]), [[1], [2], [3]])
        self.assertEqual(self.m.transpose_matrix([]), [])
        with self.assertRaises(ValueError) as c:
            self.m.transpose_matrix([[1], [2, 3]])
        self.assertEqual(str(c.exception), "P235:transpose_matrix:ragged:matrix")
        with self.assertRaises(ValueError):
            self.m.transpose_matrix([[True]])
        with self.assertRaises(ValueError):
            self.m.transpose_matrix([1, 2])
        with self.assertRaises(ValueError) as c2:
            self.m.transpose_matrix([[0] * 5001, [0] * 5001])
        self.assertEqual(str(c2.exception),
                         "P235:transpose_matrix:too_many:cells")

    def test_diagonal_sum(self):
        self.assertEqual(self.m.diagonal_sum([[1, 2], [3, 4]]), 5)
        self.assertEqual(self.m.diagonal_sum([[7]]), 7)
        with self.assertRaises(ValueError) as c:
            self.m.diagonal_sum([[1, 2]])
        self.assertEqual(str(c.exception), "P235:diagonal_sum:not_square:matrix")
        with self.assertRaises(ValueError):
            self.m.diagonal_sum([[1], [2, 3]])
        with self.assertRaises(ValueError):
            self.m.diagonal_sum([])

    def test_fibonacci_term(self):
        self.assertEqual(self.m.fibonacci_term(0), 0)
        self.assertEqual(self.m.fibonacci_term(1), 1)
        self.assertEqual(self.m.fibonacci_term(10), 55)
        self.assertEqual(self.m.fibonacci_term(50), 12586269025)
        with self.assertRaises(ValueError):
            self.m.fibonacci_term(-1)
        with self.assertRaises(ValueError):
            self.m.fibonacci_term(True)
        with self.assertRaises(ValueError) as c:
            self.m.fibonacci_term(self.m.MAX_FIB_N + 1)
        self.assertEqual(str(c.exception), "P235:fibonacci_term:too_many:n")

    def test_collatz_steps(self):
        self.assertEqual(self.m.collatz_steps(1), 0)
        self.assertEqual(self.m.collatz_steps(6), 8)
        self.assertEqual(self.m.collatz_steps(27), 111)
        with self.assertRaises(ValueError):
            self.m.collatz_steps(0)
        with self.assertRaises(ValueError):
            self.m.collatz_steps(True)
        with self.assertRaises(ValueError) as c:
            self.m.collatz_steps(self.m.MAX_COLLATZ_N + 1)
        self.assertEqual(str(c.exception), "P235:collatz_steps:too_many:n")

    def test_digital_root(self):
        self.assertEqual(self.m.digital_root(0), 0)
        self.assertEqual(self.m.digital_root(9875), 2)
        self.assertEqual(self.m.digital_root(9), 9)
        with self.assertRaises(ValueError):
            self.m.digital_root(-5)
        with self.assertRaises(ValueError):
            self.m.digital_root(True)

    def test_is_power_of_two(self):
        self.assertTrue(self.m.is_power_of_two(1))
        self.assertTrue(self.m.is_power_of_two(1024))
        self.assertFalse(self.m.is_power_of_two(3))
        self.assertFalse(self.m.is_power_of_two(0) if False else self.m.is_power_of_two(6))
        with self.assertRaises(ValueError):
            self.m.is_power_of_two(0)
        with self.assertRaises(ValueError):
            self.m.is_power_of_two(-2)

    def test_binary_string_to_int(self):
        self.assertEqual(self.m.binary_string_to_int("0"), 0)
        self.assertEqual(self.m.binary_string_to_int("1010"), 10)
        with self.assertRaises(ValueError):
            self.m.binary_string_to_int("")
        with self.assertRaises(ValueError):
            self.m.binary_string_to_int("102")
        with self.assertRaises(ValueError):
            self.m.binary_string_to_int(1010)
        with self.assertRaises(ValueError) as c:
            self.m.binary_string_to_int("1" * 10001)
        self.assertEqual(str(c.exception),
                         "P235:binary_string_to_int:too_many:text")

    def test_int_to_binary_string(self):
        self.assertEqual(self.m.int_to_binary_string(0), "0")
        self.assertEqual(self.m.int_to_binary_string(10), "1010")
        with self.assertRaises(ValueError):
            self.m.int_to_binary_string(-1)
        with self.assertRaises(ValueError):
            self.m.int_to_binary_string(True)

    def test_pairwise_swap_adjacent(self):
        self.assertEqual(self.m.pairwise_swap_adjacent(["a", "b", "c", "d"]),
                         ["b", "a", "d", "c"])
        self.assertEqual(self.m.pairwise_swap_adjacent(["a", "b", "c"]),
                         ["b", "a", "c"])
        self.assertEqual(self.m.pairwise_swap_adjacent([]), [])
        with self.assertRaises(ValueError):
            self.m.pairwise_swap_adjacent(["a", 1])

    def test_sum_of_squares_exact(self):
        self.assertEqual(self.m.sum_of_squares_exact([1, 2, 3]), 14)
        self.assertEqual(self.m.sum_of_squares_exact([]), 0)
        self.assertEqual(self.m.sum_of_squares_exact([10 ** 20]), 10 ** 40)
        with self.assertRaises(ValueError):
            self.m.sum_of_squares_exact([True])


    def test_digital_root_digit_cap(self):
        self.assertEqual(self.m.digital_root(10 ** 999), 1)
        self.assertEqual(self.m.digital_root((10 ** 999) - 1), 9)
        with self.assertRaises(ValueError) as c:
            self.m.digital_root(10 ** 1000)
        self.assertEqual(str(c.exception), "P235:digital_root:too_many:n")

    def test_int_to_binary_string_bit_cap(self):
        self.assertEqual(self.m.int_to_binary_string(2 ** 9999),
                         "1" + "0" * 9999)
        with self.assertRaises(ValueError) as c:
            self.m.int_to_binary_string(2 ** 10000)
        self.assertEqual(str(c.exception),
                         "P235:int_to_binary_string:too_many:n")

    def test_empty_width_transpose_pins(self):
        self.assertEqual(self.m.transpose_matrix([]), [])
        self.assertEqual(self.m.transpose_matrix([[], []]), [])
        with self.assertRaises(ValueError) as c:
            self.m.diagonal_sum([[], []])
        self.assertEqual(str(c.exception),
                         "P235:diagonal_sum:not_square:matrix")

    def test_resource_guards_at_cap_and_over(self):
        # At-cap inputs are accepted; cap+1 refuses with the named code.
        self.assertEqual(
            self.m.fibonacci_term(self.m.MAX_FIB_N),
            self.m.fibonacci_term(self.m.MAX_FIB_N - 1)
            + self.m.fibonacci_term(self.m.MAX_FIB_N - 2))
        self.assertGreater(self.m.collatz_steps(self.m.MAX_COLLATZ_N), 0)
        self.assertEqual(self.m.binary_string_to_int("1" * 10000),
                         2 ** 10000 - 1)
        self.assertEqual(len(self.m.transpose_matrix([[0] * 10000])), 10000)


if __name__ == "__main__":
    unittest.main()
