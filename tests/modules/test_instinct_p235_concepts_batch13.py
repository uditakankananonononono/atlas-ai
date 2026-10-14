"""P235 concepts batch 13 (121-130, data structures/streams): red-first tests."""
from __future__ import annotations

import unittest


class Batch13Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch13 as m
        self.m = m

    def test_flatten_nested_any(self):
        self.assertEqual(self.m.flatten_nested_any([1, [2, [3, [4]]], 5]),
                         [1, 2, 3, 4, 5])
        self.assertEqual(self.m.flatten_nested_any([]), [])
        self.assertEqual(self.m.flatten_nested_any([[[7]]]), [7])
        with self.assertRaises(ValueError):
            self.m.flatten_nested_any([1, [2, "x"]])
        # 1 root + 99 lists + 9900 ints = exactly the node cap: passes
        self.assertEqual(len(self.m.flatten_nested_any(
            [[0] * 100 for _ in range(99)])), 9_900)
        # 1 root + 100 lists + 10000 ints = cap + 1: refuses
        with self.assertRaises(ValueError) as c:
            self.m.flatten_nested_any([[0] * 100 for _ in range(100)])
        self.assertEqual(str(c.exception),
                         "P235:flatten_nested_any:too_many:nodes")
        # internal empty lists count as visited nodes too
        with self.assertRaises(ValueError) as c2:
            self.m.flatten_nested_any(
                [[[] for _ in range(100)] for _ in range(100)])
        self.assertEqual(str(c2.exception),
                         "P235:flatten_nested_any:too_many:nodes")

    def test_zip_longest_fill(self):
        self.assertEqual(self.m.zip_longest_fill([1, 2, 3], [10], 0),
                         [[1, 10], [2, 0], [3, 0]])
        self.assertEqual(self.m.zip_longest_fill([], [], 9), [])
        self.assertEqual(self.m.zip_longest_fill([1], [2, 3], None),
                         [[1, 2], [None, 3]])
        with self.assertRaises(ValueError):
            self.m.zip_longest_fill([1, "x"], [1], 0)

    def test_take_every_nth(self):
        self.assertEqual(self.m.take_every_nth([1, 2, 3, 4, 5, 6], 2), [1, 3, 5])
        self.assertEqual(self.m.take_every_nth([], 3), [])
        self.assertEqual(self.m.take_every_nth([7, 8], 5), [7])
        with self.assertRaises(ValueError) as c:
            self.m.take_every_nth([1, 2], 0)
        self.assertEqual(str(c.exception), "P235:take_every_nth:bad_value:n")

    def test_interleave_lists(self):
        self.assertEqual(self.m.interleave_lists([1, 3, 5], [2, 4]),
                         [1, 2, 3, 4, 5])
        self.assertEqual(self.m.interleave_lists([], []), [])
        self.assertEqual(self.m.interleave_lists([], [7, 8]), [7, 8])
        with self.assertRaises(ValueError):
            self.m.interleave_lists([1, "x"], [2])

    def test_first_index_of(self):
        self.assertEqual(self.m.first_index_of([5, 3, 5], 5), 0)
        self.assertEqual(self.m.first_index_of([1, 2], 9), -1)
        self.assertEqual(self.m.first_index_of([], 1), -1)
        with self.assertRaises(ValueError):
            self.m.first_index_of([1, 1.0], 1)

    def test_last_occurrence_index(self):
        self.assertEqual(self.m.last_occurrence_index([5, 3, 5], 5), 2)
        self.assertEqual(self.m.last_occurrence_index([1, 2], 9), -1)
        self.assertEqual(self.m.last_occurrence_index([], 1), -1)
        with self.assertRaises(ValueError):
            self.m.last_occurrence_index([1, "x"], 1)

    def test_cumulative_product_exact(self):
        self.assertEqual(self.m.cumulative_product_exact([2, 3, 4]), [2, 6, 24])
        self.assertEqual(self.m.cumulative_product_exact([]), [])
        self.assertEqual(self.m.cumulative_product_exact([5]), [5])
        self.assertEqual(self.m.cumulative_product_exact([0, 9]), [0, 0])
        with self.assertRaises(ValueError):
            self.m.cumulative_product_exact([1, True])

    def test_max_min_difference(self):
        self.assertEqual(self.m.max_min_difference([3, 1, 4, 1, 5]), 4)
        self.assertEqual(self.m.max_min_difference([7]), 0)
        self.assertEqual(self.m.max_min_difference([-2, -8]), 6)
        with self.assertRaises(ValueError) as c:
            self.m.max_min_difference([])
        self.assertEqual(str(c.exception),
                         "P235:max_min_difference:empty:items")

    def test_rank_of_values(self):
        self.assertEqual(self.m.rank_of_values([40, 10, 30, 30]), [1, 4, 2, 2])
        self.assertEqual(self.m.rank_of_values([]), [])
        self.assertEqual(self.m.rank_of_values([5]), [1])
        with self.assertRaises(ValueError):
            self.m.rank_of_values([1, "x"])

    def test_matrix_vector_multiply(self):
        self.assertEqual(self.m.matrix_vector_multiply(
            [[1, 2], [3, 4]], [5, 6]), [17, 39])
        self.assertEqual(self.m.matrix_vector_multiply([[7]], [2]), [14])
        with self.assertRaises(ValueError) as c:
            self.m.matrix_vector_multiply([[1, 2]], [1])
        self.assertEqual(str(c.exception),
                         "P235:matrix_vector_multiply:dimension_mismatch")
        with self.assertRaises(ValueError):
            self.m.matrix_vector_multiply([], [])
        with self.assertRaises(ValueError):
            self.m.matrix_vector_multiply([[1], [2, 3]], [1, 1])
        # 100 x 100 = exactly the cell cap: passes
        self.assertEqual(self.m.matrix_vector_multiply(
            [[0] * 100 for _ in range(100)], [0] * 100), [0] * 100)
        with self.assertRaises(ValueError) as c2:
            self.m.matrix_vector_multiply([[0] * 100 for _ in range(101)],
                                          [0] * 100)
        self.assertEqual(str(c2.exception),
                         "P235:matrix_vector_multiply:too_many:cells")


if __name__ == "__main__":
    unittest.main()
