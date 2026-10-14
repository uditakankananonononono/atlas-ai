"""P235 concepts, batch 33 (graph algorithms II, 321-330).

Offline, stdlib only. Integer-vertex graphs (0..nodes-1), edges as
[u, v] lists, no self-loops or duplicates, matching the batch-20 graph
conventions. Exact counts; caps refuse before work.
"""
from __future__ import annotations

from collections import deque

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, make_fail)

MAX_NODES = 1_000
MAX_BRUTE_EDGES = 500
MAX_TOPO_COUNT_NODES = 18
MAX_DIAMETER_NODES = 300


def _check_nodes(fail, nodes):
    check_int(fail, nodes, "nodes")
    if nodes < 1 or nodes > MAX_NODES:
        fail("bad_value:nodes")


def _graph_undirected(fail, nodes, edges):
    _check_nodes(fail, nodes)
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
        key = (min(u, v), max(u, v))
        if key in seen:
            fail("duplicate:edge")
        seen.add(key)
        adj[u].append(v)
        adj[v].append(u)
    return adj


def _graph_directed(fail, nodes, edges):
    _check_nodes(fail, nodes)
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
        if (u, v) in seen:
            fail("duplicate:edge")
        seen.add((u, v))
        adj[u].append(v)
    return adj


def _components(adj, skip=-1):
    count = 0
    seen = [False] * len(adj)
    if 0 <= skip < len(adj):
        seen[skip] = True
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


def articulation_points_count(nodes, edges):
    fail = make_fail("articulation_points_count")
    if type(edges) is list and len(edges) > MAX_BRUTE_EDGES:
        fail("too_many:edges")
    adj = _graph_undirected(fail, nodes, edges)
    base = _components(adj)
    count = 0
    for v in range(nodes):
        if _components(adj, skip=v) > base:
            count += 1
    return count


def strongly_connected_count(nodes, edges):
    fail = make_fail("strongly_connected_count")
    adj = _graph_directed(fail, nodes, edges)
    radj = [[] for _ in range(nodes)]
    for u in range(nodes):
        for v in adj[u]:
            radj[v].append(u)
    seen = [False] * nodes
    order = []
    for s in range(nodes):
        if seen[s]:
            continue
        seen[s] = True
        stack = [(s, 0)]
        while stack:
            u, idx = stack[-1]
            if idx < len(adj[u]):
                v = adj[u][idx]
                stack[-1] = (u, idx + 1)
                if not seen[v]:
                    seen[v] = True
                    stack.append((v, 0))
            else:
                order.append(u)
                stack.pop()
    count = 0
    seen = [False] * nodes
    for s in reversed(order):
        if seen[s]:
            continue
        count += 1
        seen[s] = True
        stack = [s]
        while stack:
            u = stack.pop()
            for v in radj[u]:
                if not seen[v]:
                    seen[v] = True
                    stack.append(v)
    return count


def triangle_count(nodes, edges):
    fail = make_fail("triangle_count")
    adj = _graph_undirected(fail, nodes, edges)
    sets = [set(a) for a in adj]
    count = 0
    for u in range(nodes):
        for v in adj[u]:
            if v > u:
                count += sum(1 for w in sets[u] & sets[v] if w > v)
    return count


def topological_sort_count(nodes, edges):
    fail = make_fail("topological_sort_count")
    adj = _graph_directed(fail, nodes, edges)
    if nodes > MAX_TOPO_COUNT_NODES:
        fail("too_many:nodes")
    preds = [0] * nodes
    for u in range(nodes):
        for v in adj[u]:
            preds[v] |= 1 << u
    size = 1 << nodes
    dp = [0] * size
    dp[0] = 1
    for mask in range(size):
        if dp[mask] == 0:
            continue
        for v in range(nodes):
            bit = 1 << v
            if not mask & bit and preds[v] & ~mask == 0:
                dp[mask | bit] += dp[mask]
    return dp[size - 1]


def max_flow_value(nodes, edges, source, sink):
    fail = make_fail("max_flow_value")
    _check_nodes(fail, nodes)
    check_items(fail, edges, "edges")
    check_int(fail, source, "source")
    check_int(fail, sink, "sink")
    if not (0 <= source < nodes) or not (0 <= sink < nodes):
        fail("bad_value:source")
    if source == sink:
        fail("bad_value:source_equals_sink")
    caps = [[] for _ in range(nodes)]
    seen = set()
    for i, e in enumerate(edges):
        if type(e) is not list or len(e) != 3:
            fail("bad_value:edge")
        u, v, c = e
        check_int(fail, u, "edges[%d][0]" % i)
        check_int(fail, v, "edges[%d][1]" % i)
        check_int(fail, c, "edges[%d][2]" % i)
        if u == v or not (0 <= u < nodes) or not (0 <= v < nodes) or c < 1:
            fail("bad_value:edge")
        if (u, v) in seen:
            fail("duplicate:edge")
        seen.add((u, v))
        caps[u].append((v, len(caps[v])))
        caps[v].append((u, len(caps[u]) - 1, True))
    # residual capacities stored alongside
    residual = [[] for _ in range(nodes)]
    rev = [[] for _ in range(nodes)]
    for u in range(nodes):
        for item in caps[u]:
            if len(item) == 2:
                v, _ = item
                c = next(c2 for u2, v2, c2 in edges if u2 == u and v2 == v)
                rev[u].append(len(residual[v]))
                rev[v].append(len(residual[u]))
                residual[u].append([v, c])
                residual[v].append([u, 0])
    total = 0
    while True:
        parent = [None] * nodes
        parent[source] = (source, -1)
        queue = deque([source])
        while queue and parent[sink] is None:
            u = queue.popleft()
            for i, (v, cap) in enumerate(residual[u]):
                if cap > 0 and parent[v] is None:
                    parent[v] = (u, i)
                    queue.append(v)
        if parent[sink] is None:
            return total
        pushed = None
        v = sink
        while v != source:
            u, i = parent[v]
            cap = residual[u][i][1]
            pushed = cap if pushed is None else min(pushed, cap)
            v = u
        total += pushed
        v = sink
        while v != source:
            u, i = parent[v]
            residual[u][i][1] -= pushed
            residual[v][rev[u][i]][1] += pushed
            v = u


def graph_diameter(nodes, edges):
    fail = make_fail("graph_diameter")
    adj = _graph_undirected(fail, nodes, edges)
    if nodes > MAX_DIAMETER_NODES:
        fail("too_many:nodes")
    if _components(adj) != 1:
        fail("disconnected:graph")
    best = 0
    for s in range(nodes):
        dist = [-1] * nodes
        dist[s] = 0
        queue = deque([s])
        while queue:
            u = queue.popleft()
            for v in adj[u]:
                if dist[v] == -1:
                    dist[v] = dist[u] + 1
                    queue.append(v)
        best = max(best, max(dist))
    return best


def shortest_path_count(nodes, edges, start, target):
    fail = make_fail("shortest_path_count")
    adj = _graph_undirected(fail, nodes, edges)
    check_int(fail, start, "start")
    check_int(fail, target, "target")
    if not (0 <= start < nodes) or not (0 <= target < nodes):
        fail("bad_value:start")
    dist = [-1] * nodes
    count = [0] * nodes
    dist[start] = 0
    count[start] = 1
    queue = deque([start])
    while queue:
        u = queue.popleft()
        for v in adj[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                count[v] = count[u]
                queue.append(v)
            elif dist[v] == dist[u] + 1:
                count[v] += count[u]
    return 0 if dist[target] == -1 else count[target]


def bipartite_max_matching_size(nodes, edges):
    fail = make_fail("bipartite_max_matching_size")
    adj = _graph_undirected(fail, nodes, edges)
    color = [-1] * nodes
    for s in range(nodes):
        if color[s] != -1:
            continue
        color[s] = 0
        queue = deque([s])
        while queue:
            u = queue.popleft()
            for v in adj[u]:
                if color[v] == -1:
                    color[v] = 1 - color[u]
                    queue.append(v)
                elif color[v] == color[u]:
                    fail("not_bipartite:graph")
    match_to = [-1] * nodes  # right-side vertex -> left-side match

    def augment(u, seen):
        for v in adj[u]:
            if color[v] != 1 or seen[v]:
                continue
            seen[v] = True
            if match_to[v] == -1 or augment(match_to[v], seen):
                match_to[v] = u
                return True
        return False

    size = 0
    for u in range(nodes):
        if color[u] == 0:
            if augment(u, [False] * nodes):
                size += 1
    return size


def has_directed_cycle(nodes, edges):
    fail = make_fail("has_directed_cycle")
    adj = _graph_directed(fail, nodes, edges)
    state = [0] * nodes  # 0 unvisited, 1 in stack, 2 done
    for s in range(nodes):
        if state[s] != 0:
            continue
        state[s] = 1
        stack = [(s, 0)]
        while stack:
            u, idx = stack[-1]
            if idx < len(adj[u]):
                v = adj[u][idx]
                stack[-1] = (u, idx + 1)
                if state[v] == 1:
                    return True
                if state[v] == 0:
                    state[v] = 1
                    stack.append((v, 0))
            else:
                state[u] = 2
                stack.pop()
    return False


def complete_graph_check(nodes, edges):
    fail = make_fail("complete_graph_check")
    _graph_undirected(fail, nodes, edges)
    return len(edges) * 2 == nodes * (nodes - 1)
