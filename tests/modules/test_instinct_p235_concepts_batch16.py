"""P235 concepts batch 16 (151-160, games/combinatorics): red-first tests."""
from __future__ import annotations

import unittest
from fractions import Fraction


class Batch16Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch16 as m
        self.m = m

    def test_permutations_count(self):
        self.assertEqual(self.m.permutations_count(5), 120)
        self.assertEqual(self.m.permutations_count(0), 1)
        self.assertEqual(self.m.permutations_count(1), 1)
        with self.assertRaises(ValueError):
            self.m.permutations_count(-1)
        with self.assertRaises(ValueError) as c:
            self.m.permutations_count(self.m.MAX_FACTORIAL_N + 1)
        self.assertEqual(str(c.exception),
                         "P235:permutations_count:too_many:n")

    def test_derangement_count(self):
        self.assertEqual(self.m.derangement_count(4), 9)
        self.assertEqual(self.m.derangement_count(1), 0)
        self.assertEqual(self.m.derangement_count(0), 1)
        self.assertEqual(self.m.derangement_count(2), 1)
        with self.assertRaises(ValueError):
            self.m.derangement_count(-3)
        with self.assertRaises(ValueError) as c:
            self.m.derangement_count(self.m.MAX_DERANGE_N + 1)
        self.assertEqual(str(c.exception),
                         "P235:derangement_count:too_many:n")

    def test_catalan_number(self):
        self.assertEqual(self.m.catalan_number(4), 14)
        self.assertEqual(self.m.catalan_number(0), 1)
        self.assertEqual(self.m.catalan_number(3), 5)
        with self.assertRaises(ValueError):
            self.m.catalan_number(-1)
        with self.assertRaises(ValueError) as c:
            self.m.catalan_number(self.m.MAX_CATALAN_N + 1)
        self.assertEqual(str(c.exception),
                         "P235:catalan_number:too_many:n")

    def test_tic_tac_toe_winner(self):
        self.assertEqual(self.m.tic_tac_toe_winner(
            ["X", "X", "X", "", "", "", "", "", ""]), "X")
        self.assertIsNone(self.m.tic_tac_toe_winner(
            ["X", "O", "X", "O", "X", "O", "O", "X", "O"]))
        self.assertEqual(self.m.tic_tac_toe_winner(
            ["O", "", "", "O", "", "", "O", "", ""]), "O")
        with self.assertRaises(ValueError) as c:
            self.m.tic_tac_toe_winner(["X"] * 8)
        self.assertEqual(str(c.exception),
                         "P235:tic_tac_toe_winner:bad_value:board")
        with self.assertRaises(ValueError):
            self.m.tic_tac_toe_winner(["Z"] * 9)

    def test_nim_outcome(self):
        self.assertEqual(self.m.nim_outcome([1, 2, 3]), "losing")
        self.assertEqual(self.m.nim_outcome([1, 2, 4]), "winning")
        self.assertEqual(self.m.nim_outcome([0, 0]), "losing")
        self.assertEqual(self.m.nim_outcome([]), "losing")
        with self.assertRaises(ValueError):
            self.m.nim_outcome([1, -2])

    def test_knight_min_moves(self):
        self.assertEqual(self.m.knight_min_moves([0, 0], [1, 2]), 1)
        self.assertEqual(self.m.knight_min_moves([0, 0], [0, 0]), 0)
        self.assertEqual(self.m.knight_min_moves([0, 0], [7, 7]), 6)
        with self.assertRaises(ValueError) as c:
            self.m.knight_min_moves([0, 0], [8, 0])
        self.assertEqual(str(c.exception),
                         "P235:knight_min_moves:bad_value:square")
        with self.assertRaises(ValueError):
            self.m.knight_min_moves([0], [0, 0])

    def test_queens_no_attack(self):
        self.assertTrue(self.m.queens_no_attack([0, 4, 7, 5, 2, 6, 1, 3]))
        self.assertFalse(self.m.queens_no_attack([0, 1]))
        self.assertTrue(self.m.queens_no_attack([0]))
        self.assertFalse(self.m.queens_no_attack([0, 2, 1]))
        self.assertFalse(self.m.queens_no_attack([0, 0]))
        with self.assertRaises(ValueError):
            self.m.queens_no_attack([0, "x"])

    def test_dice_sum_probability_exact(self):
        self.assertEqual(self.m.dice_sum_probability_exact(2, 7), Fraction(1, 6))
        self.assertEqual(self.m.dice_sum_probability_exact(2, 13), Fraction(0))
        self.assertEqual(self.m.dice_sum_probability_exact(1, 6), Fraction(1, 6))
        with self.assertRaises(ValueError):
            self.m.dice_sum_probability_exact(0, 3)
        with self.assertRaises(ValueError) as c:
            self.m.dice_sum_probability_exact(self.m.MAX_DICE + 1, 7)
        self.assertEqual(str(c.exception),
                         "P235:dice_sum_probability_exact:too_many:dice")

    def test_chess_square_color(self):
        self.assertEqual(self.m.chess_square_color("a1"), "dark")
        self.assertEqual(self.m.chess_square_color("e4"), "light")
        self.assertEqual(self.m.chess_square_color("h8"), "dark")
        with self.assertRaises(ValueError) as c:
            self.m.chess_square_color("i9")
        self.assertEqual(str(c.exception),
                         "P235:chess_square_color:bad_value:square")
        with self.assertRaises(ValueError):
            self.m.chess_square_color("e4 ")

    def test_magic_square_check(self):
        self.assertTrue(self.m.magic_square_check(
            [[2, 7, 6], [9, 5, 1], [4, 3, 8]]))
        self.assertFalse(self.m.magic_square_check([[1, 2], [3, 4]]))
        self.assertFalse(self.m.magic_square_check(
            [[2, 7, 6], [9, 5, 1], [4, 3, 9]]))
        self.assertFalse(self.m.magic_square_check([[1, 2, 3]]))
        with self.assertRaises(ValueError):
            self.m.magic_square_check([[1], [2, 3]])

    def test_tic_tac_toe_impossible_boards(self):
        # the function is a line detector in fixed _LINES order, not a
        # plausibility judge; these pins hold that documented behavior.
        # both players hold lines: the top row wins by scan order
        self.assertEqual(self.m.tic_tac_toe_winner(
            ["X", "X", "X", "O", "O", "O", "", "", ""]), "X")
        # O row above X row: O wins by scan order
        self.assertEqual(self.m.tic_tac_toe_winner(
            ["O", "O", "O", "X", "X", "X", "", "", ""]), "O")
        # implausible counts still scan: X line with eight X and one O
        self.assertEqual(self.m.tic_tac_toe_winner(
            ["X", "O", "X", "X", "X", "X", "X", "X", "X"]), "X")
        # full board with no line
        self.assertIsNone(self.m.tic_tac_toe_winner(
            ["X", "O", "X", "X", "O", "O", "O", "X", "X"]))
        # column, both diagonals
        self.assertEqual(self.m.tic_tac_toe_winner(
            ["X", "", "", "X", "", "", "X", "", ""]), "X")
        self.assertEqual(self.m.tic_tac_toe_winner(
            ["X", "", "", "", "X", "", "", "", "X"]), "X")
        self.assertEqual(self.m.tic_tac_toe_winner(
            ["", "", "O", "", "O", "", "O", "", ""]), "O")

    def test_magic_square_edges(self):
        # 1x1 is a trivial magic square
        self.assertTrue(self.m.magic_square_check([[1]]))
        # Duerer 4x4
        self.assertTrue(self.m.magic_square_check(
            [[16, 3, 2, 13], [5, 10, 11, 8],
             [9, 6, 7, 12], [4, 15, 14, 1]]))
        # rows all sum 15 but columns do not
        self.assertFalse(self.m.magic_square_check(
            [[1, 5, 9], [2, 6, 7], [3, 4, 8]]))
        # valid shape and range but one row broken by a swap
        self.assertFalse(self.m.magic_square_check(
            [[9, 7, 6], [2, 5, 1], [4, 3, 8]]))
        # duplicate value breaks the 1..n*n range requirement
        self.assertFalse(self.m.magic_square_check(
            [[2, 7, 6], [9, 5, 1], [4, 3, 7]]))
        # out-of-range value refuses nothing; it is simply not magic
        self.assertFalse(self.m.magic_square_check(
            [[0, 7, 6], [9, 5, 1], [4, 3, 8]]))
        self.assertFalse(self.m.magic_square_check(
            [[10, 7, 6], [9, 5, 1], [4, 3, 8]]))
        # zero-by-zero and rectangular shapes are not magic
        self.assertFalse(self.m.magic_square_check([]))
        self.assertFalse(self.m.magic_square_check([[1, 2], [3, 4], [5, 6]]))

    def test_knight_boundary_squares(self):
        # distances verified against an independent BFS
        self.assertEqual(self.m.knight_min_moves([7, 7], [0, 0]), 6)
        self.assertEqual(self.m.knight_min_moves([0, 7], [7, 0]), 6)
        self.assertEqual(self.m.knight_min_moves([0, 0], [7, 0]), 5)
        self.assertEqual(self.m.knight_min_moves([0, 0], [0, 7]), 5)
        self.assertEqual(self.m.knight_min_moves([7, 7], [7, 6]), 3)
        self.assertEqual(self.m.knight_min_moves([0, 1], [0, 0]), 3)
        self.assertEqual(self.m.knight_min_moves([0, 0], [1, 1]), 4)
        self.assertEqual(self.m.knight_min_moves([7, 0], [7, 7]), 5)
        self.assertEqual(self.m.knight_min_moves([3, 3], [0, 0]), 2)

    def test_knight_exhaustive_all_pairs(self):
        # All 4,096 (start, target) pairs: every square is reachable
        # (so the exhausted-queue branch can never fire) and the maximum
        # distance on the 8x8 board is 6. This is also the visited-guard
        # resource pin: without the seen-check this suite revisits states
        # exponentially and does not finish.
        for sx in range(8):
            for sy in range(8):
                for tx in range(8):
                    for ty in range(8):
                        d = self.m.knight_min_moves([sx, sy], [tx, ty])
                        self.assertIsInstance(d, int)
                        self.assertGreaterEqual(d, 0)
                        self.assertLessEqual(d, 6)
                        if (sx, sy) == (tx, ty):
                            self.assertEqual(d, 0)

    def test_magic_square_n4_and_n5(self):
        # 4x4 with rows and columns magic but the main diagonal broken
        # (columns of the Duerer square swapped) is not magic
        self.assertFalse(self.m.magic_square_check(
            [[3, 16, 2, 13], [10, 5, 11, 8],
             [6, 9, 7, 12], [15, 4, 14, 1]]))
        # Siamese 5x5
        self.assertTrue(self.m.magic_square_check(
            [[17, 24, 1, 8, 15], [23, 5, 7, 14, 16],
             [4, 6, 13, 20, 22], [10, 12, 19, 21, 3],
             [11, 18, 25, 2, 9]]))
        # 5x5 with one cell swapped out of the 1..25 range is not magic
        broken = [[17, 24, 1, 8, 15], [23, 5, 7, 14, 16],
                  [4, 6, 13, 20, 22], [10, 12, 19, 21, 3],
                  [11, 18, 25, 2, 26]]
        self.assertFalse(self.m.magic_square_check(broken))


if __name__ == "__main__":
    unittest.main()
