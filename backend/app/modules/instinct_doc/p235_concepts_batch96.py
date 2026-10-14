"""P235 concepts batch 96: ten concepts.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
Lists are capped at MAX_ITEMS entries; tighter caps
(MAX_TSP_CITIES, MAX_KMEANS_POINTS, MAX_KMEANS_K,
MAX_NECKLACE_LEN, MAX_KIRCHHOFF_NODES,
MAX_BLOSSOM_NODES,
MAX_EULER_EDGES, MAX_MEC_POINTS) are stated in the docstrings of the functions
that carry them. Every function validates its whole input first:
length caps are checked before the elements they bound are
inspected, then type, range, and shape checks run during the
validation phase, and the computation phase starts only after
validation succeeds. Exact arithmetic uses ints and Fractions
only.
"""

from collections import deque
from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_TSP_CITIES = 16
MAX_KMEANS_POINTS = 200
MAX_KMEANS_K = 20
MAX_NECKLACE_LEN = 512
MAX_KIRCHHOFF_NODES = 200
MAX_BLOSSOM_NODES = 150
MAX_EULER_EDGES = 200_000
MAX_MEC_POINTS = 60
MAX_VAL = 10**9


def tsp_held_karp_min(dist):
    """Minimum traveling salesman tour cost via Held-Karp.

    dist is an n by n symmetric matrix of non-negative int
    distances with a zero diagonal; n is capped at
    MAX_TSP_CITIES. Returns the smallest total cost of a tour
    that starts and ends at city 0 and visits every city exactly
    once (0 when n is 1), by dynamic programming over subsets,
    an estimated O(n^2 * 2^n) work."""
    fail = make_fail("tsp_held_karp_min")
    check_items(fail, dist, "dist")
    if not dist:
        fail("empty:dist")
    if len(dist) > MAX_TSP_CITIES:
        fail("too_many:dist")
    n = len(dist)
    for i, row in enumerate(dist):
        check_items(fail, row, "dist[%d]" % i)
        if len(row) != n:
            fail("ragged:dist")
        for j, v in enumerate(row):
            check_int(fail, v, "dist[%d][%d]" % (i, j))
            if v < 0 or v > MAX_VAL:
                fail("out_of_range:dist[%d][%d]" % (i, j))
    for i in range(n):
        if dist[i][i] != 0:
            fail("bad_diagonal:dist")
        for j in range(i + 1, n):
            if dist[i][j] != dist[j][i]:
                fail("asymmetric:dist")
    if n == 1:
        return 0
    size = 1 << (n - 1)
    inf = (MAX_VAL + 1) * MAX_TSP_CITIES
    dp = [[inf] * n for _ in range(size)]
    dp[0][0] = 0
    for mask in range(size):
        for i in range(n):
            cur = dp[mask][i]
            if cur == inf:
                continue
            for j in range(1, n):
                bit = 1 << (j - 1)
                if mask & bit:
                    continue
                cand = cur + dist[i][j]
                if cand < dp[mask | bit][j]:
                    dp[mask | bit][j] = cand
    full = size - 1
    return min(dp[full][i] + dist[i][0] for i in range(1, n))


def bridge_torch_min_time(times):
    """Least total time for a group to cross a bridge at night.

    At most two people cross at once, they need the torch on
    every crossing, and a pair moves at the slower person's time.
    times holds non-negative int crossing times capped at
    MAX_ITEMS entries and MAX_VAL each. Returns the minimum total
    time, computed from the sorted times by the classic two-
    strategy reduction, an estimated O(n log n) work."""
    fail = make_fail("bridge_torch_min_time")
    check_items(fail, times, "times")
    if not times:
        fail("empty:times")
    for i, v in enumerate(times):
        check_int(fail, v, "times[%d]" % i)
        if v < 0 or v > MAX_VAL:
            fail("out_of_range:times[%d]" % i)
    a = sorted(times)
    total = 0
    n = len(a)
    while n > 3:
        escort = 2 * a[0] + a[n - 1] + a[n - 2]
        shuttle = 2 * a[1] + a[0] + a[n - 1]
        total += min(escort, shuttle)
        n -= 2
    if n == 3:
        total += a[0] + a[1] + a[2]
    elif n == 2:
        total += a[1]
    else:
        total += a[0]
    return total


def kmeans_1d_exact(values, k):
    """Exact 1D k-means cost as a Fraction.

    values holds at most MAX_KMEANS_POINTS ints of magnitude at
    most MAX_VAL; k is between 1 and min(len(values),
    MAX_KMEANS_K). Returns the smallest possible total within-
    cluster squared deviation over all partitions of the sorted
    values into k contiguous clusters, by dynamic programming
    over prefix sums, an estimated O(k * n^2) work. The result is
    exact: each cluster's cost is its sum of squares minus its
    squared sum over its size."""
    fail = make_fail("kmeans_1d_exact")
    check_items(fail, values, "values")
    if not values:
        fail("empty:values")
    if len(values) > MAX_KMEANS_POINTS:
        fail("too_many:values")
    check_int(fail, k, "k")
    for i, v in enumerate(values):
        check_int(fail, v, "values[%d]" % i)
        if v < -MAX_VAL or v > MAX_VAL:
            fail("out_of_range:values[%d]" % i)
    n = len(values)
    if k < 1 or k > min(n, MAX_KMEANS_K):
        fail("out_of_range:k")
    xs = sorted(values)
    ps = [0] * (n + 1)
    ps2 = [0] * (n + 1)
    for i, x in enumerate(xs):
        ps[i + 1] = ps[i] + x
        ps2[i + 1] = ps2[i] + x * x

    def cost(lo, hi):  # cluster xs[lo:hi]
        cnt = hi - lo
        s1 = ps[hi] - ps[lo]
        s2 = ps2[hi] - ps2[lo]
        return Fraction(s2) - Fraction(s1 * s1, cnt)

    inf = None
    prev = [Fraction(0)] + [inf] * n
    for _ in range(k):
        cur = [inf] * (n + 1)
        for i in range(1, n + 1):
            best = None
            for t in range(i):
                if prev[t] is None:
                    continue
                cand = prev[t] + cost(t, i)
                if best is None or cand < best:
                    best = cand
            cur[i] = best
        prev = cur
    return prev[n]


def johnson_flowshop_order(jobs):
    """Job order that minimizes two-machine flow shop makespan.

    Each job is [a, b] with non-negative int processing times on
    machines 1 and 2, capped at MAX_ITEMS jobs and MAX_VAL per
    time. Johnson's rule: jobs with a <= b go first in ascending
    a order, the rest follow in descending b order; ties break by
    original index so the returned order of job indices is
    deterministic, an estimated O(n log n) work."""
    fail = make_fail("johnson_flowshop_order")
    check_items(fail, jobs, "jobs")
    for i, job in enumerate(jobs):
        check_items(fail, job, "jobs[%d]" % i)
        if len(job) != 2:
            fail("bad_shape:jobs[%d]" % i)
        for j, v in enumerate(job):
            check_int(fail, v, "jobs[%d][%d]" % (i, j))
            if v < 0 or v > MAX_VAL:
                fail("out_of_range:jobs[%d][%d]" % (i, j))
    early = [i for i, (a, b) in enumerate(jobs) if a <= b]
    late = [i for i, (a, b) in enumerate(jobs) if a > b]
    early.sort(key=lambda i: (jobs[i][0], i))
    late.sort(key=lambda i: (-jobs[i][1], i))
    return early + late


def necklace_count(colors, length):
    """Number of distinct necklaces under rotation, by Burnside.

    colors is an int from 1 to MAX_VAL and length an int from 1
    to MAX_NECKLACE_LEN. Two length-n words over the given
    number of colors form the same necklace when one rotates
    into the other; Burnside's lemma counts the classes as
    (1 / n) * sum of colors ** gcd(i, n) for i in [0, n),
    computed with exact ints. Deterministic; the work is n
    big-int powers colors ** gcd(i, n) with n at most 512."""
    fail = make_fail("necklace_count")
    check_int(fail, colors, "colors")
    check_int(fail, length, "length")
    if colors < 1 or colors > MAX_VAL:
        fail("out_of_range:colors")
    if length < 1 or length > MAX_NECKLACE_LEN:
        fail("out_of_range:length")
    from math import gcd
    total = 0
    for i in range(length):
        total += colors ** gcd(i, length)
    return total // length


def _check_simple_graph(fail, adj, name, max_edges):
    check_items(fail, adj, name)
    if not adj:
        fail("empty:%s" % name)
    n = len(adj)
    total = 0
    for i, outs in enumerate(adj):
        check_items(fail, outs, "%s[%d]" % (name, i))
        total += len(outs)
        if total > max_edges:
            fail("too_many_edges:%s" % name)
    for i, outs in enumerate(adj):
        seen = set()
        for j, v in enumerate(outs):
            check_int(fail, v, "%s[%d][%d]" % (name, i, j))
            if v < 0 or v >= n:
                fail("out_of_range:%s[%d][%d]" % (name, i, j))
            if v == i:
                fail("self_loop:%s[%d]" % (name, i))
            if v in seen:
                fail("duplicate:%s[%d]" % (name, i))
            seen.add(v)
    adj_sets = [set(outs) for outs in adj]
    for i, outs in enumerate(adj):
        for v in outs:
            if i not in adj_sets[v]:
                fail("asymmetric:%s[%d]" % (name, i))
    return n


def kirchhoff_spanning_tree_count(adj):
    """Number of spanning trees of an undirected simple graph.

    Applies Kirchhoff's matrix-tree theorem: the determinant of
    any cofactor of the Laplacian, evaluated exactly with the
    fraction-free Bareiss algorithm, an estimated O(n^3) work.
    Returns 0 for a disconnected graph and 1 for a single node.
    adj is capped at MAX_KIRCHHOFF_NODES nodes (checked before
    any neighbor list is inspected)."""
    fail = make_fail("kirchhoff_spanning_tree_count")
    check_items(fail, adj, "adj")
    if len(adj) > MAX_KIRCHHOFF_NODES:
        fail("too_many:adj")
    n = _check_simple_graph(fail, adj, "adj",
                            MAX_KIRCHHOFF_NODES * (MAX_KIRCHHOFF_NODES - 1))
    if n == 1:
        return 1
    lap = [[0] * n for _ in range(n)]
    for i in range(n):
        for v in adj[i]:
            if v > i:
                lap[i][i] += 1
                lap[v][v] += 1
                lap[i][v] = -1
                lap[v][i] = -1
    m = [row[1:] for row in lap[1:]]
    size = n - 1
    sign = 1
    prev = 1
    for k in range(size - 1):
        if m[k][k] == 0:
            swap = None
            for r in range(k + 1, size):
                if m[r][k] != 0:
                    swap = r
                    break
            if swap is None:
                return 0
            m[k], m[swap] = m[swap], m[k]
            sign = -sign
        for i in range(k + 1, size):
            for j in range(k + 1, size):
                m[i][j] = (m[i][j] * m[k][k] - m[i][k] * m[k][j]) // prev
        prev = m[k][k]
    return sign * m[size - 1][size - 1]


def edmonds_blossom_match(nodes, edges):
    """Maximum-cardinality matching of a general graph.

    nodes is a positive int capped at MAX_BLOSSOM_NODES; edges
    holds [u, v] rows of distinct in-range endpoints with no
    self loops and no repeated unordered pair. Runs Edmonds'
    blossom algorithm: BFS for augmenting paths with odd-cycle
    contraction, an estimated O(nodes^3) work. Returns the
    matched pairs as sorted [u, v] rows sorted lexicographically.
    The matching is deterministic: augmenting-path searches start
    from unmatched vertices in increasing order and every
    adjacency list is sorted. Unlike bipartite matchings, odd
    cycles are handled by blossom contraction."""
    fail = make_fail("edmonds_blossom_match")
    check_int(fail, nodes, "nodes")
    if nodes < 1 or nodes > MAX_BLOSSOM_NODES:
        fail("out_of_range:nodes")
    check_items(fail, edges, "edges")
    seen = set()
    adj = [[] for _ in range(nodes)]
    for i, e in enumerate(edges):
        check_items(fail, e, "edges[%d]" % i)
        if len(e) != 2:
            fail("bad_shape:edges[%d]" % i)
        u, v = e
        check_int(fail, u, "edges[%d][0]" % i)
        check_int(fail, v, "edges[%d][1]" % i)
        if not (0 <= u < nodes) or not (0 <= v < nodes):
            fail("out_of_range:edges[%d]" % i)
        if u == v:
            fail("self_loop:edges[%d]" % i)
        key = (min(u, v), max(u, v))
        if key in seen:
            fail("duplicate:edges[%d]" % i)
        seen.add(key)
        adj[u].append(v)
        adj[v].append(u)
    for a in adj:
        a.sort()
    match = [-1] * nodes

    def lca(a, b, base, p):
        seen_l = [False] * nodes
        while True:
            a = base[a]
            seen_l[a] = True
            if match[a] == -1:
                break
            a = p[match[a]]
        while True:
            b = base[b]
            if seen_l[b]:
                return b
            b = p[match[b]]

    def mark_path(v, b, children, base, p, blossom):
        while base[v] != b:
            blossom[base[v]] = True
            blossom[base[match[v]]] = True
            p[v] = children
            children = match[v]
            v = p[match[v]]

    def find_path(root):
        used = [False] * nodes
        p = [-1] * nodes
        base = list(range(nodes))
        used[root] = True
        queue = deque([root])
        while queue:
            v = queue.popleft()
            for to in adj[v]:
                if base[v] == base[to] or match[v] == to:
                    continue
                if to == root or (match[to] != -1
                                  and p[match[to]] != -1):
                    cur = lca(v, to, base, p)
                    blossom = [False] * nodes
                    mark_path(v, cur, to, base, p, blossom)
                    mark_path(to, cur, v, base, p, blossom)
                    for i in range(nodes):
                        if blossom[base[i]]:
                            base[i] = cur
                            if not used[i]:
                                used[i] = True
                                queue.append(i)
                elif p[to] == -1:
                    p[to] = v
                    if match[to] == -1:
                        cur = to
                        while cur != -1:
                            pv = p[cur]
                            nxt = match[pv] if pv != -1 else -1
                            match[cur] = pv
                            if pv != -1:
                                match[pv] = cur
                            cur = nxt
                        return True
                    used[match[to]] = True
                    queue.append(match[to])
        return False

    for v in range(nodes):
        if match[v] == -1:
            find_path(v)
    return [[v, match[v]] for v in range(nodes)
            if match[v] != -1 and v < match[v]]


_ALPHABET = "ABCDEFGHIKLMNOPQRSTUVWXYZ"  # J merges into I


def playfair_encode(text, key):
    """Playfair cipher encryption over a 5 by 5 square.

    text and key are non-empty ASCII strings of letters A-Z; the
    letter J is treated as I everywhere. The square holds the
    key's letters (first occurrence) followed by the remaining
    alphabet. The text is split into digraphs left to right,
    inserting X between equal letters and padding an odd tail
    with X. The degenerate X/XX case: a repeated X (and a lone
    trailing X) pairs with the X filler, so the digraph is
    (X, X) itself, and the same-row rule maps each (X, X)
    digraph to two copies of X's right neighbor; input XX
    creates two such digraphs, producing four copies. Same-row
    pairs shift right, same-column
    pairs shift down, and rectangle pairs swap columns.
    Returns the ciphertext. text and key are capped at MAX_ITEMS
    characters."""
    fail = make_fail("playfair_encode")
    check_str(fail, text, "text")
    check_str(fail, key, "key")
    if not text:
        fail("empty:text")
    if not key:
        fail("empty:key")
    if len(text) > MAX_ITEMS:
        fail("too_long:text")
    if len(key) > MAX_ITEMS:
        fail("too_long:key")
    for name, s in (("text", text), ("key", key)):
        for i, ch in enumerate(s):
            if ch < "A" or ch > "Z":
                fail("bad_char:%s[%d]" % (name, i))
    letters = []
    seen = set()
    for ch in key + _ALPHABET:
        if ch == "J":
            ch = "I"
        if ch not in seen:
            seen.add(ch)
            letters.append(ch)
    pos = {ch: (i // 5, i % 5) for i, ch in enumerate(letters)}
    chars = ["I" if ch == "J" else ch for ch in text]
    pairs = []
    i = 0
    while i < len(chars):
        a = chars[i]
        b = chars[i + 1] if i + 1 < len(chars) else None
        if b is None:
            pairs.append((a, "X"))
            i += 1
        elif a == b:
            pairs.append((a, "X"))
            i += 1
        else:
            pairs.append((a, b))
            i += 2
    out = []
    for a, b in pairs:
        ra, ca = pos[a]
        rb, cb = pos[b]
        if ra == rb:
            out.append(letters[ra * 5 + (ca + 1) % 5])
            out.append(letters[rb * 5 + (cb + 1) % 5])
        elif ca == cb:
            out.append(letters[((ra + 1) % 5) * 5 + ca])
            out.append(letters[((rb + 1) % 5) * 5 + cb])
        else:
            out.append(letters[ra * 5 + cb])
            out.append(letters[rb * 5 + ca])
    return "".join(out)


def eulerian_trail_find(adj):
    """An Eulerian trail of an undirected simple graph, as vertices.

    Returns a list of len(edges) + 1 vertices that walks every
    edge exactly once: a circuit when every degree is even, an
    open trail when exactly two degrees are odd. A graph with no
    edges returns [0]. Otherwise refuses no_trail. The graph is
    capped at MAX_ITEMS nodes and MAX_EULER_EDGES total neighbor
    entries (checked before any entry is inspected). Hierholzer's
    algorithm walks adjacency lists in ascending neighbor order
    so the result is deterministic, an estimated
    O(n + sum over vertices of deg log deg) work from the
    per-vertex neighbor sorts."""
    fail = make_fail("eulerian_trail_find")
    n = _check_simple_graph(fail, adj, "adj", MAX_EULER_EDGES)
    edges = sum(len(o) for o in adj) // 2
    if edges == 0:
        return [0]
    odd = [v for v in range(n) if len(adj[v]) % 2 == 1]
    if len(odd) not in (0, 2):
        fail("no_trail:adj")
    start = odd[0] if odd else next(v for v in range(n) if adj[v])
    seen = {start}
    stack = [start]
    while stack:
        v = stack.pop()
        for w in adj[v]:
            if w not in seen:
                seen.add(w)
                stack.append(w)
    if any(adj[v] and v not in seen for v in range(n)):
        fail("no_trail:adj")
    used = set()
    ptr = [0] * n
    sorted_adj = [sorted(o) for o in adj]
    path = []
    walk = [start]
    while walk:
        v = walk[-1]
        row = sorted_adj[v]
        while ptr[v] < len(row) and (min(v, row[ptr[v]]),
                                     max(v, row[ptr[v]])) in used:
            ptr[v] += 1
        if ptr[v] == len(row):
            path.append(walk.pop())
        else:
            w = row[ptr[v]]
            used.add((min(v, w), max(v, w)))
            walk.append(w)
    return path[::-1]


def min_enclosing_circle(points):
    """Smallest circle covering every point, as exact Fractions.

    Returns [cx, cy, r2]: the center coordinates and the squared
    radius of the minimum enclosing circle. Duplicate points are
    ignored; a single distinct point yields radius squared 0.
    Every pair defines a diameter circle and every non-collinear
    triple defines a circumcircle; the smallest candidate that
    contains all points wins, an estimated O(n^4) work. points
    holds [x, y] int pairs capped at MAX_MEC_POINTS entries and
    MAX_VAL in magnitude."""
    fail = make_fail("min_enclosing_circle")
    check_items(fail, points, "points")
    if not points:
        fail("empty:points")
    if len(points) > MAX_MEC_POINTS:
        fail("too_many:points")
    for i, pt in enumerate(points):
        check_items(fail, pt, "points[%d]" % i)
        if len(pt) != 2:
            fail("bad_shape:points[%d]" % i)
        for j, v in enumerate(pt):
            check_int(fail, v, "points[%d][%d]" % (i, j))
            if v < -MAX_VAL or v > MAX_VAL:
                fail("out_of_range:points[%d][%d]" % (i, j))
    pts = []
    seen = set()
    for x, y in points:
        if (x, y) not in seen:
            seen.add((x, y))
            pts.append((x, y))
    if len(pts) == 1:
        return [Fraction(pts[0][0]), Fraction(pts[0][1]), Fraction(0)]

    def dist2(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    def circum(a, b, c):
        ax, ay = a
        bx, by = b
        cx, cy = c
        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if d == 0:
            return None
        aa = ax * ax + ay * ay
        bb = bx * bx + by * by
        cc = cx * cx + cy * cy
        ux = Fraction(aa * (by - cy) + bb * (cy - ay)
                      + cc * (ay - by), d)
        uy = Fraction(aa * (cx - bx) + bb * (ax - cx)
                      + cc * (bx - ax), d)
        r2 = (Fraction(ax) - ux) ** 2 + (Fraction(ay) - uy) ** 2
        return (ux, uy, r2)

    candidates = []
    m = len(pts)
    for i in range(m):
        for j in range(i + 1, m):
            cx = Fraction(pts[i][0] + pts[j][0], 2)
            cy = Fraction(pts[i][1] + pts[j][1], 2)
            r2 = Fraction(dist2(pts[i], pts[j]), 4)
            candidates.append((cx, cy, r2))
    for i in range(m):
        for j in range(i + 1, m):
            for t in range(j + 1, m):
                circ = circum(pts[i], pts[j], pts[t])
                if circ is not None:
                    candidates.append(circ)
    best = None
    for cx, cy, r2 in candidates:
        if best is not None and r2 >= best[2]:
            continue
        ok = True
        for x, y in pts:
            if (Fraction(x) - cx) ** 2 + (Fraction(y) - cy) ** 2 > r2:
                ok = False
                break
        if ok:
            best = (cx, cy, r2)
    return [best[0], best[1], best[2]]
