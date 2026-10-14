"""P235 concepts batch 20 (191-200, small graphs): red-first tests."""
from __future__ import annotations

import unittest
from fractions import Fraction


class Batch20Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch20 as m
        self.m = m

    def test_graph_degree_list(self):
        self.assertEqual(self.m.graph_degree_list(3, [[0, 1], [1, 2]]),
                         [1, 2, 1])
        self.assertEqual(self.m.graph_degree_list(3, []), [0, 0, 0])
        with self.assertRaises(ValueError) as c:
            self.m.graph_degree_list(2, [[0, 0]])
        self.assertEqual(str(c.exception),
                         "P235:graph_degree_list:bad_value:edge")
        with self.assertRaises(ValueError):
            self.m.graph_degree_list(2, [[0, 5]])
        with self.assertRaises(ValueError):
            self.m.graph_degree_list(2, [[0, 1], [0, 1]])

    def test_has_cycle_undirected(self):
        self.assertTrue(self.m.has_cycle_undirected(3, [[0, 1], [1, 2], [2, 0]]))
        self.assertFalse(self.m.has_cycle_undirected(3, [[0, 1], [1, 2]]))
        self.assertFalse(self.m.has_cycle_undirected(1, []))

    def test_has_cycle_undirected_iterative_chain(self):
        # a 1,000-node chain exceeds the default recursion limit: the DFS
        # must be iterative
        chain = [[i, i + 1] for i in range(999)]
        self.assertFalse(self.m.has_cycle_undirected(1_000, chain))
        closed = chain + [[999, 0]]
        self.assertTrue(self.m.has_cycle_undirected(1_000, closed))

    def test_dag_sources_accepts_cyclic(self):
        # not a DAG validator: cyclic input is accepted, only the
        # zero-in-degree nodes come back
        self.assertEqual(self.m.dag_sources(
            3, [[0, 1], [1, 0]]), [2])
        self.assertEqual(self.m.dag_sources(
            2, [[0, 1], [1, 0]]), [])

    def test_connected_components_count(self):
        self.assertEqual(self.m.connected_components_count(4, [[0, 1], [2, 3]]), 2)
        self.assertEqual(self.m.connected_components_count(3, []), 3)
        self.assertEqual(self.m.connected_components_count(3, [[0, 1], [1, 2]]), 1)

    def test_bipartite_check(self):
        self.assertTrue(self.m.bipartite_check(4, [[0, 1], [1, 2], [2, 3]]))
        self.assertFalse(self.m.bipartite_check(3, [[0, 1], [1, 2], [2, 0]]))
        self.assertTrue(self.m.bipartite_check(2, []))

    def test_shortest_path_length(self):
        self.assertEqual(self.m.shortest_path_length(
            4, [[0, 1], [1, 2], [2, 3]], 0, 3), 3)
        self.assertEqual(self.m.shortest_path_length(3, [], 0, 2), -1)
        self.assertEqual(self.m.shortest_path_length(3, [], 1, 1), 0)
        with self.assertRaises(ValueError) as c:
            self.m.shortest_path_length(3, [], 0, 7)
        self.assertEqual(str(c.exception),
                         "P235:shortest_path_length:bad_value:node")

    def test_eulerian_trail_check(self):
        self.assertTrue(self.m.eulerian_trail_check(3, [[0, 1], [1, 2], [2, 0]]))
        self.assertTrue(self.m.eulerian_trail_check(4, [[0, 1], [1, 2]]))
        self.assertFalse(self.m.eulerian_trail_check(
            5, [[0, 1], [1, 2], [2, 0], [3, 4]]))
        self.assertFalse(self.m.eulerian_trail_check(4, [[0, 1], [0, 2], [0, 3]]))
        self.assertTrue(self.m.eulerian_trail_check(1, []))

    def test_dag_sources(self):
        self.assertEqual(self.m.dag_sources(3, [[0, 1], [0, 2]]), [0])
        self.assertEqual(self.m.dag_sources(2, [[0, 1], [1, 0]]), [])
        self.assertEqual(self.m.dag_sources(3, []), [0, 1, 2])

    def test_graph_density_exact(self):
        self.assertEqual(self.m.graph_density_exact(3, [[0, 1], [1, 2]]),
                         Fraction(2, 3))
        self.assertEqual(self.m.graph_density_exact(1, []), Fraction(0))
        self.assertEqual(self.m.graph_density_exact(4, []), Fraction(0))

    def test_tree_check(self):
        self.assertTrue(self.m.tree_check(3, [[0, 1], [1, 2]]))
        self.assertFalse(self.m.tree_check(3, [[0, 1], [1, 2], [2, 0]]))
        self.assertFalse(self.m.tree_check(4, [[0, 1]]))
        self.assertTrue(self.m.tree_check(1, []))

    def test_bridge_count(self):
        self.assertEqual(self.m.bridge_count(3, [[0, 1], [1, 2], [2, 0]]), 0)
        self.assertEqual(self.m.bridge_count(3, [[0, 1], [1, 2]]), 2)
        self.assertEqual(self.m.bridge_count(2, [[0, 1]]), 1)
        self.assertEqual(self.m.bridge_count(
            4, [[0, 1], [1, 2], [2, 3], [3, 0], [1, 3]]), 0)
        self.assertEqual(self.m.bridge_count(
            501, [[i, i + 1] for i in range(500)]), 500)
        with self.assertRaises(ValueError) as c:
            self.m.bridge_count(502, [[i, i + 1] for i in range(501)])
        self.assertEqual(str(c.exception),
                         "P235:bridge_count:too_many:edges")


if __name__ == "__main__":
    unittest.main()
