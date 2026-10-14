"""P235 concepts, batch 33 (graph algorithms II, 321-330). Offline."""
from __future__ import annotations

import unittest

from app.modules.instinct_doc import p235_concepts_batch33 as m


def _all_undirected(n):
    pairs = [(u, v) for u in range(n) for v in range(u + 1, n)]
    for mask in range(1 << len(pairs)):
        yield [list(pairs[i]) for i in range(len(pairs)) if mask >> i & 1]


def _all_directed(n):
    pairs = [(u, v) for u in range(n) for v in range(n) if u != v]
    for mask in range(1 << len(pairs)):
        yield [list(pairs[i]) for i in range(len(pairs)) if mask >> i & 1]


class Batch33Test(unittest.TestCase):
    def test_articulation_points_count(self):
        self.assertEqual(m.articulation_points_count(3, [[0, 1], [1, 2]]), 1)
        self.assertEqual(
            m.articulation_points_count(3, [[0, 1], [1, 2], [0, 2]]), 0)
        self.assertEqual(
            m.articulation_points_count(4, [[0, 1], [0, 2], [0, 3]]), 1)
        # bowtie: two triangles sharing vertex 2
        self.assertEqual(m.articulation_points_count(
            5, [[0, 1], [1, 2], [0, 2], [2, 3], [3, 4], [2, 4]]), 1)
        # disconnected: path 0-1-2 plus edge 3-4
        self.assertEqual(
            m.articulation_points_count(5, [[0, 1], [1, 2], [3, 4]]), 1)
        self.assertEqual(m.articulation_points_count(1, []), 0)
        self.assertEqual(m.articulation_points_count(2, [[0, 1]]), 0)

    def test_articulation_points_oracle_lowlink(self):
        def oracle(n, edges):
            adj = [[] for _ in range(n)]
            for u, v in edges:
                adj[u].append(v)
                adj[v].append(u)
            disc = [-1] * n
            low = [0] * n
            aps = set()
            timer = [0]

            def dfs(root):
                stack = [(root, -1, 0)]
                disc[root] = low[root] = timer[0]
                timer[0] += 1
                children = 0
                while stack:
                    u, parent, idx = stack[-1]
                    if idx < len(adj[u]):
                        v = adj[u][idx]
                        stack[-1] = (u, parent, idx + 1)
                        if disc[v] == -1:
                            disc[v] = low[v] = timer[0]
                            timer[0] += 1
                            if parent == -1:
                                children += 1
                            stack.append((v, u, 0))
                        elif v != parent:
                            low[u] = min(low[u], disc[v])
                    else:
                        stack.pop()
                        if parent != -1:
                            low[parent] = min(low[parent], low[u])
                            if parent != root and low[u] >= disc[parent]:
                                aps.add(parent)
                if children > 1:
                    aps.add(root)

            for s in range(n):
                if disc[s] == -1:
                    dfs(s)
            return len(aps)

        for n in (3, 4):
            for edges in _all_undirected(n):
                self.assertEqual(m.articulation_points_count(n, edges),
                                 oracle(n, edges), (n, edges))

    def test_articulation_points_validation(self):
        with self.assertRaises(ValueError) as ctx:
            m.articulation_points_count(0, [])
        self.assertIn("bad_value:nodes", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.articulation_points_count(True, [])
        with self.assertRaises(ValueError) as ctx:
            m.articulation_points_count(2, [[0, 0]])
        self.assertIn("bad_value:edge", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.articulation_points_count(2, [[0, 1], [1, 0]])
        self.assertIn("duplicate:edge", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.articulation_points_count(3, [[0, 1]] * 0 + [[0, 9]])
        self.assertIn("bad_value:edge", str(ctx.exception))
        big = [[i, (i + 1) % 502] for i in range(501)]
        with self.assertRaises(ValueError) as ctx:
            m.articulation_points_count(502, big)
        self.assertIn("too_many:edges", str(ctx.exception))

    def test_strongly_connected_count(self):
        self.assertEqual(m.strongly_connected_count(3, [[0, 1], [1, 2]]), 3)
        self.assertEqual(
            m.strongly_connected_count(3, [[0, 1], [1, 2], [2, 0]]), 1)
        self.assertEqual(m.strongly_connected_count(
            4, [[0, 1], [1, 0], [2, 3], [3, 2], [1, 2]]), 2)
        self.assertEqual(m.strongly_connected_count(1, []), 1)

    def test_strongly_connected_oracle(self):
        def oracle(n, edges):
            reach = [[u == v for v in range(n)] for u in range(n)]
            for u, v in edges:
                reach[u][v] = True
            for k in range(n):
                for i in range(n):
                    if reach[i][k]:
                        for j in range(n):
                            reach[i][j] = reach[i][j] or reach[k][j]
            seen = [False] * n
            count = 0
            for u in range(n):
                if seen[u]:
                    continue
                count += 1
                for v in range(n):
                    if reach[u][v] and reach[v][u]:
                        seen[v] = True
            return count

        for edges in _all_directed(3):
            self.assertEqual(m.strongly_connected_count(3, edges),
                             oracle(3, edges), edges)

    def test_triangle_count(self):
        self.assertEqual(m.triangle_count(3, [[0, 1], [1, 2], [0, 2]]), 1)
        self.assertEqual(m.triangle_count(
            4, [[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]]), 4)
        self.assertEqual(m.triangle_count(3, [[0, 1], [1, 2]]), 0)

    def test_triangle_count_oracle(self):
        from itertools import combinations
        for n in (4,):
            for edges in _all_undirected(n):
                es = {tuple(sorted(e)) for e in edges}
                want = sum(
                    1 for a, b, c in combinations(range(n), 3)
                    if (a, b) in es and (b, c) in es and (a, c) in es)
                self.assertEqual(m.triangle_count(n, edges), want, edges)

    def test_topological_sort_count(self):
        self.assertEqual(m.topological_sort_count(3, []), 6)
        self.assertEqual(m.topological_sort_count(3, [[0, 1], [1, 2]]), 1)
        self.assertEqual(m.topological_sort_count(3, [[0, 2], [1, 2]]), 2)
        self.assertEqual(m.topological_sort_count(2, [[0, 1], [1, 0]]), 0)
        self.assertEqual(m.topological_sort_count(1, []), 1)
        with self.assertRaises(ValueError) as ctx:
            m.topological_sort_count(19, [])
        self.assertIn("too_many:nodes", str(ctx.exception))

    def test_topological_sort_count_oracle(self):
        from itertools import permutations

        def oracle(n, edges):
            count = 0
            for perm in permutations(range(n)):
                pos = {v: i for i, v in enumerate(perm)}
                if all(pos[u] < pos[v] for u, v in edges):
                    count += 1
            return count

        import random
        rng = random.Random(33)
        for trial in range(60):
            n = rng.randint(1, 6)
            order = list(range(n))
            rng.shuffle(order)
            edges = []
            for i in range(n):
                for j in range(i + 1, n):
                    if rng.random() < 0.35:
                        edges.append([order[i], order[j]])
            self.assertEqual(m.topological_sort_count(n, edges),
                             oracle(n, edges), (n, edges))

    def test_max_flow_value(self):
        edges = [[0, 1, 3], [0, 2, 2], [1, 2, 1], [1, 3, 2], [2, 3, 4]]
        self.assertEqual(m.max_flow_value(4, edges, 0, 3), 5)
        self.assertEqual(m.max_flow_value(2, [[0, 1, 7]], 0, 1), 7)
        self.assertEqual(m.max_flow_value(3, [[0, 1, 5]], 0, 2), 0)
        with self.assertRaises(ValueError) as ctx:
            m.max_flow_value(2, [[0, 1, 1]], 1, 1)
        self.assertIn("bad_value", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.max_flow_value(2, [[0, 1, 0]], 0, 1)
        self.assertIn("bad_value:edge", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.max_flow_value(2, [[0, 1, True]], 0, 1)

    def test_max_flow_min_cut_oracle(self):
        # independent check: max flow equals the min s-t cut, found by
        # enumerating every vertex subset
        graphs = [
            (4, [[0, 1, 3], [0, 2, 2], [1, 2, 1], [1, 3, 2], [2, 3, 4]],
             0, 3),
            (4, [[0, 1, 1], [0, 2, 1], [1, 3, 1], [2, 3, 1], [1, 2, 1]],
             0, 3),
            (5, [[0, 1, 2], [1, 2, 3], [2, 3, 1], [0, 4, 5], [4, 3, 5],
                 [1, 4, 1]], 0, 3),
        ]
        for n, edges, s, t in graphs:
            best = None
            for mask in range(1 << n):
                if not (mask >> s & 1) or (mask >> t & 1):
                    continue
                cut = sum(c for u, v, c in edges
                          if (mask >> u & 1) and not (mask >> v & 1))
                best = cut if best is None else min(best, cut)
            self.assertEqual(m.max_flow_value(n, edges, s, t), best)

    def test_graph_diameter(self):
        self.assertEqual(m.graph_diameter(4, [[0, 1], [1, 2], [2, 3]]), 3)
        self.assertEqual(m.graph_diameter(1, []), 0)
        self.assertEqual(m.graph_diameter(3, [[0, 1], [1, 2], [0, 2]]), 1)
        with self.assertRaises(ValueError) as ctx:
            m.graph_diameter(2, [])
        self.assertIn("disconnected", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.graph_diameter(301, [])
        self.assertIn("too_many:nodes", str(ctx.exception))

    def test_graph_diameter_oracle(self):
        def oracle(n, edges):
            inf = float("inf")
            dist = [[0 if u == v else inf for v in range(n)]
                    for u in range(n)]
            for u, v in edges:
                dist[u][v] = dist[v][u] = 1
            for k in range(n):
                for i in range(n):
                    for j in range(n):
                        if dist[i][k] + dist[k][j] < dist[i][j]:
                            dist[i][j] = dist[i][k] + dist[k][j]
            return max(dist[u][v] for u in range(n) for v in range(n))

        for edges in _all_undirected(4):
            try:
                got = m.graph_diameter(4, edges)
            except ValueError:
                continue
            self.assertEqual(got, oracle(4, edges), edges)

    def test_shortest_path_count(self):
        edges = [[0, 1], [0, 2], [1, 3], [2, 3]]
        self.assertEqual(m.shortest_path_count(4, edges, 0, 3), 2)
        edges2 = [[0, 1], [0, 2], [0, 3], [1, 4], [2, 4], [3, 4]]
        self.assertEqual(m.shortest_path_count(5, edges2, 0, 4), 3)
        self.assertEqual(m.shortest_path_count(2, [[0, 1]], 0, 0), 1)
        self.assertEqual(m.shortest_path_count(2, [], 0, 1), 0)
        with self.assertRaises(ValueError):
            m.shortest_path_count(2, [[0, 1]], 0, True)

    def test_shortest_path_count_oracle(self):
        from itertools import combinations

        def oracle(n, edges, s, t):
            adj = [[] for _ in range(n)]
            for u, v in edges:
                adj[u].append(v)
                adj[v].append(u)
            best = [None]
            count = [0]

            def walk(u, seen, depth):
                if best[0] is not None and depth > best[0]:
                    return
                if u == t:
                    if best[0] is None or depth < best[0]:
                        best[0] = depth
                        count[0] = 1
                    elif depth == best[0]:
                        count[0] += 1
                    return
                for v in adj[u]:
                    if v not in seen:
                        walk(v, seen | {v}, depth + 1)

            walk(s, {s}, 0)
            return count[0]

        for edges in _all_undirected(4):
            self.assertEqual(m.shortest_path_count(4, edges, 0, 3),
                             oracle(4, edges, 0, 3), edges)

    def test_bipartite_max_matching_size(self):
        self.assertEqual(
            m.bipartite_max_matching_size(4, [[0, 1], [1, 2], [2, 3]]), 2)
        self.assertEqual(
            m.bipartite_max_matching_size(4, [[0, 1], [0, 2], [0, 3]]), 1)
        k33 = [[u, v] for u in range(3) for v in range(3, 6)]
        self.assertEqual(m.bipartite_max_matching_size(6, k33), 3)
        with self.assertRaises(ValueError) as ctx:
            m.bipartite_max_matching_size(3, [[0, 1], [1, 2], [0, 2]])
        self.assertIn("not_bipartite", str(ctx.exception))

    def test_bipartite_max_matching_oracle(self):
        # independent: largest set of pairwise vertex-disjoint edges,
        # found by recursive enumeration
        def oracle(n, edges):
            best = [0]

            def pick(i, used, size):
                if size + (len(edges) - i) <= best[0]:
                    return
                if i == len(edges):
                    best[0] = max(best[0], size)
                    return
                u, v = edges[i]
                if u not in used and v not in used:
                    pick(i + 1, used | {u, v}, size + 1)
                pick(i + 1, used, size)

            pick(0, set(), 0)
            return best[0]

        import random
        rng = random.Random(7)
        for trial in range(40):
            n = rng.randint(2, 8)
            left = list(range(n))
            rng.shuffle(left)
            left = left[:rng.randint(1, n - 1)]
            edges = []
            for u in left:
                for v in range(n):
                    if v not in left and rng.random() < 0.4:
                        edges.append([u, v])
            if len(edges) <= 20:
                self.assertEqual(m.bipartite_max_matching_size(n, edges),
                                 oracle(n, edges), (n, edges))

    def test_has_directed_cycle(self):
        self.assertTrue(m.has_directed_cycle(2, [[0, 1], [1, 0]]))
        self.assertFalse(m.has_directed_cycle(3, [[0, 1], [1, 2]]))
        self.assertTrue(
            m.has_directed_cycle(3, [[0, 1], [1, 2], [2, 0]]))
        self.assertFalse(m.has_directed_cycle(1, []))

    def test_has_directed_cycle_oracle(self):
        def oracle(n, edges):
            reach = [[False] * n for _ in range(n)]
            for u, v in edges:
                reach[u][v] = True
            for k in range(n):
                for i in range(n):
                    if reach[i][k]:
                        for j in range(n):
                            reach[i][j] = reach[i][j] or reach[k][j]
            return any(reach[v][v] for v in range(n))

        for edges in _all_directed(3):
            self.assertEqual(m.has_directed_cycle(3, edges),
                             oracle(3, edges), edges)

    def test_complete_graph_check(self):
        self.assertTrue(
            m.complete_graph_check(3, [[0, 1], [1, 2], [0, 2]]))
        self.assertFalse(m.complete_graph_check(3, [[0, 1]]))
        self.assertTrue(m.complete_graph_check(1, []))
        self.assertFalse(
            m.complete_graph_check(4, [[0, 1], [0, 2], [0, 3], [1, 2],
                                       [1, 3]]))

    def test_registry_knows_batch33(self):
        from app.modules.instinct_doc import p235_concepts_registry as reg
        names = [e["name"] for e in reg.ENTRIES]
        for name in ("articulation_points_count", "strongly_connected_count",
                     "triangle_count", "topological_sort_count",
                     "max_flow_value", "graph_diameter",
                     "shortest_path_count", "bipartite_max_matching_size",
                     "has_directed_cycle", "complete_graph_check"):
            self.assertIn(name, names)
        own = [e for e in reg.ENTRIES if e["batch"] == 33]
        self.assertEqual(len(own), 10)
        for name in ("articulation_points_count",
                     "strongly_connected_count", "triangle_count",
                     "topological_sort_count", "max_flow_value",
                     "graph_diameter", "shortest_path_count",
                     "bipartite_max_matching_size", "has_directed_cycle",
                     "complete_graph_check"):
            self.assertIn(name, [e["name"] for e in own])


if __name__ == "__main__":
    unittest.main()
