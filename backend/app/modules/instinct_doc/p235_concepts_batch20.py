"""P235 concepts, batch 20 (small graphs, 191-200). Offline, stdlib only."""
from __future__ import annotations

from collections import deque
from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, make_fail)

MAX_NODES = 1_000
MAX_BRIDGE_EDGES = 500


def _graph(fail, nodes, edges, name, directed=False):
    check_int(fail, nodes, "nodes")
    if nodes < 1 or nodes > MAX_NODES:
        fail("bad_value:nodes")
    check_items(fail, edges, "edges")
    adj = [[] for _ in range(nodes)]
    seen = set()
    for i, e in enumerate(edges):
        if type(e) is not list or len(e) != 2:
            fail("bad_value:edge")
        u, v = e
        check_int(fail, u, "edges[%d][0]" % i)
        check_int(fail, v, "edges[%d][1]" % i)
        if u == v or not (0 <= u < nodes) or not (0 <= v < nodes):
            fail("bad_value:edge")
        key = (u, v) if directed else (min(u, v), max(u, v))
        if key in seen:
            fail("duplicate:edge")
        seen.add(key)
        adj[u].append(v)
        if not directed:
            adj[v].append(u)
    return adj


def _components(adj):
    count = 0
    seen = [False] * len(adj)
    for s in range(len(adj)):
        if seen[s]:
            continue
        count += 1
        seen[s] = True
        queue = deque([s])
        while queue:
            u = queue.popleft()
            for v in adj[u]:
                if not seen[v]:
                    seen[v] = True
                    queue.append(v)
    return count


def graph_degree_list(nodes, edges):
    fail = make_fail("graph_degree_list")
    adj = _graph(fail, nodes, edges, "graph_degree_list")
    return [len(adj[u]) for u in range(nodes)]


def has_cycle_undirected(nodes, edges):
    fail = make_fail("has_cycle_undirected")
    adj = _graph(fail, nodes, edges, "has_cycle_undirected")
    seen = [False] * nodes
    for start in range(nodes):
        if seen[start]:
            continue
        stack = [(start, -1, iter(adj[start]))]
        seen[start] = True
        while stack:
            u, parent, it = stack[-1]
            advanced = False
            for v in it:
                if not seen[v]:
                    seen[v] = True
                    stack.append((v, u, iter(adj[v])))
                    advanced = True
                    break
                if v != parent:
                    return True
            if not advanced:
                stack.pop()
    return False


def connected_components_count(nodes, edges):
    fail = make_fail("connected_components_count")
    adj = _graph(fail, nodes, edges, "connected_components_count")
    return _components(adj)


def bipartite_check(nodes, edges):
    fail = make_fail("bipartite_check")
    adj = _graph(fail, nodes, edges, "bipartite_check")
    color = [None] * nodes
    for s in range(nodes):
        if color[s] is not None:
            continue
        color[s] = 0
        queue = deque([s])
        while queue:
            u = queue.popleft()
            for v in adj[u]:
                if color[v] is None:
                    color[v] = 1 - color[u]
                    queue.append(v)
                elif color[v] == color[u]:
                    return False
    return True


def shortest_path_length(nodes, edges, start, target):
    fail = make_fail("shortest_path_length")
    adj = _graph(fail, nodes, edges, "shortest_path_length")
    check_int(fail, start, "start")
    check_int(fail, target, "target")
    if not (0 <= start < nodes) or not (0 <= target < nodes):
        fail("bad_value:node")
    if start == target:
        return 0
    seen = {start}
    queue = deque([(start, 0)])
    while queue:
        u, dist = queue.popleft()
        for v in adj[u]:
            if v == target:
                return dist + 1
            if v not in seen:
                seen.add(v)
                queue.append((v, dist + 1))
    return -1


def eulerian_trail_check(nodes, edges):
    fail = make_fail("eulerian_trail_check")
    adj = _graph(fail, nodes, edges, "eulerian_trail_check")
    active = [u for u in range(nodes) if adj[u]]
    if not active:
        return True
    seen = set()
    queue = deque([active[0]])
    seen.add(active[0])
    while queue:
        u = queue.popleft()
        for v in adj[u]:
            if v not in seen:
                seen.add(v)
                queue.append(v)
    if any(u not in seen for u in active):
        return False
    odd = sum(1 for u in active if len(adj[u]) % 2 == 1)
    return odd in (0, 2)


def dag_sources(nodes, edges):
    """Zero-in-degree nodes of a directed edge list. The graph is NOT
    required to be acyclic: cyclic inputs are accepted and their
    zero-in-degree nodes (if any) are returned."""
    fail = make_fail("dag_sources")
    check_int(fail, nodes, "nodes")
    if nodes < 1 or nodes > MAX_NODES:
        fail("bad_value:nodes")
    check_items(fail, edges, "edges")
    indegree = [0] * nodes
    seen = set()
    for i, e in enumerate(edges):
        if type(e) is not list or len(e) != 2:
            fail("bad_value:edge")
        u, v = e
        check_int(fail, u, "edges[%d][0]" % i)
        check_int(fail, v, "edges[%d][1]" % i)
        if u == v or not (0 <= u < nodes) or not (0 <= v < nodes):
            fail("bad_value:edge")
        if (u, v) in seen:
            fail("duplicate:edge")
        seen.add((u, v))
        indegree[v] += 1
    return [u for u in range(nodes) if indegree[u] == 0]


def graph_density_exact(nodes, edges):
    fail = make_fail("graph_density_exact")
    adj = _graph(fail, nodes, edges, "graph_density_exact")
    if nodes < 2:
        return Fraction(0)
    m = sum(len(adj[u]) for u in range(nodes)) // 2
    return Fraction(2 * m, nodes * (nodes - 1))


def tree_check(nodes, edges):
    fail = make_fail("tree_check")
    adj = _graph(fail, nodes, edges, "tree_check")
    m = sum(len(adj[u]) for u in range(nodes)) // 2
    return m == nodes - 1 and _components(adj) == 1


def bridge_count(nodes, edges):
    fail = make_fail("bridge_count")
    if type(edges) is list and len(edges) > MAX_BRIDGE_EDGES:
        fail("too_many:edges")
    _graph(fail, nodes, edges, "bridge_count")
    base = _components(_graph(fail, nodes, edges, "bridge_count"))
    count = 0
    for skip in range(len(edges)):
        kept = [e for i, e in enumerate(edges) if i != skip]
        if _components(_graph(fail, nodes, kept, "bridge_count")) > base:
            count += 1
    return count
