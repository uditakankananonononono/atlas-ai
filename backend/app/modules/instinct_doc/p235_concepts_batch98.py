"""P235 concepts batch 98: ten concepts.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
Lists are capped at MAX_ITEMS entries; tighter caps
(MAX_CUT_NODES, MAX_DOM_NODES, MAX_BICONN_NODES, MAX_EC_P,
MAX_TILING_CELLS, MAX_DB_LEN, MAX_DB_N) are stated in the
docstrings of the functions that carry them. Every function
validates its whole input first: length caps are checked before
the elements they bound are inspected, then type, range, and
shape checks run during the validation phase, and the
computation phase starts only after validation succeeds. Exact
arithmetic uses ints only.
"""

from collections import deque

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_CUT_NODES = 150
MAX_DOM_NODES = 200
MAX_BICONN_NODES = 150
MAX_EC_P = 10**6
MAX_TILING_CELLS = 64
MAX_DB_LEN = 10_000
MAX_DB_N = 64
MAX_VAL = 10**9
_MASK = (1 << 32) - 1


def _primes_first(n):
    out = []
    cand = 2
    while len(out) < n:
        for p in out:
            if p * p > cand:
                break
            if cand % p == 0:
                break
        else:
            out.append(cand)
            cand += 1
            continue
        if any(cand % p == 0 for p in out if p * p <= cand):
            cand += 1
            continue
        if not out or cand > out[-1]:
            if all(cand % p for p in out if p * p <= cand):
                out.append(cand)
        cand += 1
    return out


def _icuberoot(n):
    x = 1 << ((n.bit_length() + 2) // 3)
    while True:
        y = (2 * x + n // (x * x)) // 3
        if y >= x:
            return x if x ** 3 <= n else x - 1
        x = y


def _isqrt(n):
    x = 1 << ((n.bit_length() + 1) // 2)
    while True:
        y = (x + n // x) // 2
        if y >= x:
            return x if x * x <= n else x - 1
        x = y


def _sha_round_constants():
    primes = _primes_first(64)
    return [_icuberoot(p << 96) & _MASK for p in primes]


def _sha_initial_state():
    primes = _primes_first(8)
    return [_isqrt(p << 64) & _MASK for p in primes]


def sha256_digest(text):
    """SHA-256 digest of the UTF-8 encoding of text as hex.

    text is capped at MAX_ITEMS characters. The round constants
    and initial state are derived from scratch (fractional parts
    of prime cube and square roots by exact integer Newton
    iteration); the message is padded per spec and run through
    the 64-round compression. Returns 64 lowercase hex
    characters. Deterministic; an estimated O(len(text)) work."""
    fail = make_fail("sha256_digest")
    check_str(fail, text, "text")
    if len(text) > MAX_ITEMS:
        fail("too_long:text")
    try:
        data = text.encode("utf-8")
    except UnicodeEncodeError:
        fail("bad_char:text")
    msg = bytearray(data)
    bit_len = len(msg) * 8
    msg.append(0x80)
    while len(msg) % 64 != 56:
        msg.append(0)
    msg += bit_len.to_bytes(8, "big")
    k = _sha_round_constants()
    h = _sha_initial_state()
    for off in range(0, len(msg), 64):
        w = [int.from_bytes(msg[off + 4 * i:off + 4 * i + 4], "big")
             for i in range(16)]
        for i in range(16, 64):
            s0 = (((w[i - 15] >> 7) | (w[i - 15] << 25)) & _MASK) ^ \
                 (((w[i - 15] >> 18) | (w[i - 15] << 14)) & _MASK) ^ \
                 (w[i - 15] >> 3)
            s1 = (((w[i - 2] >> 17) | (w[i - 2] << 15)) & _MASK) ^ \
                 (((w[i - 2] >> 19) | (w[i - 2] << 13)) & _MASK) ^ \
                 (w[i - 2] >> 10)
            w.append((w[i - 16] + s0 + w[i - 7] + s1) & _MASK)
        a, b, c, d, e, f, g, hh = h
        for i in range(64):
            s1 = (((e >> 6) | (e << 26)) & _MASK) ^ \
                 (((e >> 11) | (e << 21)) & _MASK) ^ \
                 (((e >> 25) | (e << 7)) & _MASK)
            ch = (e & f) ^ (~e & g & _MASK)
            t1 = (hh + s1 + ch + k[i] + w[i]) & _MASK
            s0 = (((a >> 2) | (a << 30)) & _MASK) ^ \
                 (((a >> 13) | (a << 19)) & _MASK) ^ \
                 (((a >> 22) | (a << 10)) & _MASK)
            maj = (a & b) ^ (a & c) ^ (b & c)
            t2 = (s0 + maj) & _MASK
            hh, g, f, e, d, c, b, a = (
                g, f, e, (d + t1) & _MASK, c, b, a,
                (t1 + t2) & _MASK)
        h = [(x + y) & _MASK for x, y in
             zip(h, [a, b, c, d, e, f, g, hh])]
    return "".join("%08x" % v for v in h)


def stoer_wagner_min_cut(nodes, edges):
    """Global minimum cut weight of an undirected weighted graph.

    nodes is an int from 2 to MAX_CUT_NODES; edges holds
    [u, v, w] rows with distinct endpoints, no repeated
    unordered pair, and positive int weights at most MAX_VAL.
    Runs the Stoer-Wagner algorithm: n - 1 phases each adding
    the most tightly connected vertex, the phase cut being the
    connection weight of the last vertex added; the last two
    vertices are merged. Returns the minimum phase cut weight,
    which is 0 for a disconnected graph. Deterministic: ties
    break to the lowest vertex index. An estimated O(n^3)
    work."""
    fail = make_fail("stoer_wagner_min_cut")
    check_int(fail, nodes, "nodes")
    if nodes < 2 or nodes > MAX_CUT_NODES:
        fail("out_of_range:nodes")
    check_items(fail, edges, "edges")
    seen = set()
    weights = [[0] * nodes for _ in range(nodes)]
    for i, e in enumerate(edges):
        check_items(fail, e, "edges[%d]" % i)
        if len(e) != 3:
            fail("bad_shape:edges[%d]" % i)
        u, v, w = e
        check_int(fail, u, "edges[%d][0]" % i)
        check_int(fail, v, "edges[%d][1]" % i)
        check_int(fail, w, "edges[%d][2]" % i)
        if not (0 <= u < nodes) or not (0 <= v < nodes):
            fail("out_of_range:edges[%d]" % i)
        if u == v:
            fail("self_loop:edges[%d]" % i)
        if w < 1 or w > MAX_VAL:
            fail("out_of_range:edges[%d]" % i)
        key = (min(u, v), max(u, v))
        if key in seen:
            fail("duplicate:edges[%d]" % i)
        seen.add(key)
        weights[u][v] += w
        weights[v][u] += w
    verts = list(range(nodes))
    best = None
    while len(verts) > 1:
        used = [False] * nodes
        conn = [0] * nodes
        prev = -1
        sel = verts[0]
        for _ in range(len(verts)):
            cand = [v for v in verts if not used[v]]
            sel = min(cand, key=lambda v: (-conn[v], v))
            used[sel] = True
            if _ == len(verts) - 1:
                cut = conn[sel]
                if best is None or cut < best:
                    best = cut
                for v in verts:
                    weights[prev][v] += weights[sel][v]
                    weights[v][prev] = weights[prev][v]
                verts.remove(sel)
            else:
                prev = sel
                for v in verts:
                    if not used[v]:
                        conn[v] += weights[sel][v]
    return best


def immediate_dominators(nodes, edges, source):
    """Immediate dominator of every reachable node in a digraph.

    nodes is an int from 1 to MAX_DOM_NODES; edges holds [u, v]
    rows of distinct in-range endpoints (parallel rows and self
    loops are dropped); source is a valid node. Dominators are
    computed by iterative dataflow over the reachable subgraph:
    dom(source) is {source}, every other reachable node starts
    at the full reachable set and is refined to itself plus the
    intersection of its predecessors' sets until a fixpoint.
    The immediate dominator of a node is the member of its
    strict dominator set dominated by every other member.
    Returns a list of length nodes: idom per node, with the
    source mapped to itself and unreachable nodes to -1.
    Deterministic; an estimated O(n * e * r) work for r
    reachable nodes."""
    fail = make_fail("immediate_dominators")
    check_int(fail, nodes, "nodes")
    if nodes < 1 or nodes > MAX_DOM_NODES:
        fail("out_of_range:nodes")
    check_int(fail, source, "source")
    if not (0 <= source < nodes):
        fail("out_of_range:source")
    check_items(fail, edges, "edges")
    succ = [set() for _ in range(nodes)]
    pred = [set() for _ in range(nodes)]
    for i, e in enumerate(edges):
        check_items(fail, e, "edges[%d]" % i)
        if len(e) != 2:
            fail("bad_shape:edges[%d]" % i)
        u, v = e
        check_int(fail, u, "edges[%d][0]" % i)
        check_int(fail, v, "edges[%d][1]" % i)
        if not (0 <= u < nodes) or not (0 <= v < nodes):
            fail("out_of_range:edges[%d]" % i)
        succ[u].add(v)
        pred[v].add(u)
    reach = set()
    stack = [source]
    while stack:
        u = stack.pop()
        if u in reach:
            continue
        reach.add(u)
        stack.extend(succ[u])
    dom = {n: set(reach) for n in reach}
    dom[source] = {source}
    changed = True
    while changed:
        changed = False
        for n in sorted(reach):
            if n == source:
                continue
            ps = [p for p in pred[n] if p in reach]
            if ps:
                new = set(dom[ps[0]])
                for p in ps[1:]:
                    new &= dom[p]
            else:
                new = set()
            new.add(n)
            if new != dom[n]:
                dom[n] = new
                changed = True
    out = [-1] * nodes
    out[source] = source
    for n in sorted(reach):
        if n == source:
            continue
        strict = dom[n] - {n}
        for d in sorted(strict):
            if all(d == o or o in dom[d] for o in strict):
                out[n] = d
                break
    return out


def biconnected_blocks(nodes, edges):
    """Biconnected components (blocks) of an undirected graph.

    nodes is an int from 1 to MAX_BICONN_NODES; edges holds
    [u, v] rows of distinct in-range endpoints with no repeated
    unordered pair. Blocks are the edge partition in which two
    edges share a block exactly when some simple cycle contains
    both; every bridge is its own block. Computed by iterative
    Tarjan low-link depth-first search with an edge stack.
    Returns each block as a sorted list of sorted [u, v] rows,
    blocks sorted lexicographically; isolated vertices produce
    no blocks. Deterministic; an estimated O(n + e) work."""
    fail = make_fail("biconnected_blocks")
    check_int(fail, nodes, "nodes")
    if nodes < 1 or nodes > MAX_BICONN_NODES:
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
    disc = [-1] * nodes
    low = [0] * nodes
    clock = [0]
    estack = []
    blocks = []
    for root in range(nodes):
        if disc[root] != -1:
            continue
        work = [(root, -1, iter(adj[root]))]
        disc[root] = low[root] = clock[0]
        clock[0] += 1
        while work:
            u, parent, it = work[-1]
            advanced = False
            for v in it:
                if v == parent:
                    continue
                if disc[v] == -1:
                    estack.append((min(u, v), max(u, v)))
                    disc[v] = low[v] = clock[0]
                    clock[0] += 1
                    work.append((v, u, iter(adj[v])))
                    advanced = True
                    break
                if disc[v] < disc[u]:
                    estack.append((min(u, v), max(u, v)))
                    low[u] = min(low[u], disc[v])
            if not advanced:
                work.pop()
                if work:
                    pu = work[-1][0]
                    low[pu] = min(low[pu], low[u])
                    if low[u] >= disc[pu]:
                        block = []
                        edge = (min(pu, u), max(pu, u))
                        while True:
                            x = estack.pop()
                            block.append([x[0], x[1]])
                            if x == edge:
                                break
                        blocks.append(sorted(block))
    return sorted(blocks)


def rebuild_tree_pre_in(preorder, inorder):
    """Rebuild the unique binary tree from its traversals.

    preorder and inorder are lists of distinct ints, capped at
    MAX_ITEMS entries, holding the same values; any mismatch or
    repeated value refuses. Returns the tree in the nested
    [value, left, right] representation with None for the empty
    child, the same shape other tree concepts consume. Runs the
    standard first-root-then-split descent with an inorder index
    map on an explicit stack (no recursion, so skewed inputs of
    any capped size work); any preorder value that cannot head
    its inorder segment refuses. An estimated O(n) work after
    validation."""
    fail = make_fail("rebuild_tree_pre_in")
    check_items(fail, preorder, "preorder")
    check_items(fail, inorder, "inorder")
    for i, v in enumerate(preorder):
        check_int(fail, v, "preorder[%d]" % i)
    for i, v in enumerate(inorder):
        check_int(fail, v, "inorder[%d]" % i)
    if len(preorder) != len(inorder):
        fail("mismatch:preorder,inorder")
    pos = {}
    for i, v in enumerate(inorder):
        if v in pos:
            fail("duplicate:inorder[%d]" % i)
        pos[v] = i
    if set(preorder) != set(pos):
        fail("mismatch:preorder,inorder")
    n = len(inorder)
    if n == 0:
        return None
    pre_idx = 0
    root = None
    stack = [(0, n - 1, None, 0)]
    while stack:
        lo, hi, parent, slot = stack.pop()
        if lo > hi:
            node = None
        else:
            if pre_idx >= n:
                fail("mismatch:preorder,inorder")
            v = preorder[pre_idx]
            mid = pos[v]
            if mid < lo or mid > hi:
                fail("mismatch:preorder,inorder")
            pre_idx += 1
            node = [v, None, None]
            stack.append((mid + 1, hi, node, 2))
            stack.append((lo, mid - 1, node, 1))
        if parent is None:
            root = node
        else:
            parent[slot] = node
    if pre_idx != n:
        fail("mismatch:preorder,inorder")
    return root


def ec_point_multiply(p, a, b, gx, gy, k):
    """Scalar multiple k * G on a short Weierstrass curve mod p.

    p is a prime with 5 <= p <= MAX_EC_P (trial-divided); a, b,
    gx, gy are ints with absolute value at most MAX_VAL, reduced
    to [0, p) after validation, and the curve
    y^2 = x^3 + a x + b must be nonsingular (4 a^3 + 27 b^2
    nonzero mod p); G = (gx, gy) must lie on the curve; k is a
    non-negative int at most MAX_VAL. Runs double-and-add in
    affine coordinates with exact modular inverses. Returns
    [x, y] or None for the point at infinity. Deterministic; an
    estimated O(log k) point operations."""
    fail = make_fail("ec_point_multiply")
    check_int(fail, p, "p")
    if p < 5 or p > MAX_EC_P:
        fail("out_of_range:p")
    check_int(fail, a, "a")
    check_int(fail, b, "b")
    check_int(fail, gx, "gx")
    check_int(fail, gy, "gy")
    check_int(fail, k, "k")
    for name, v in (("a", a), ("b", b), ("gx", gx), ("gy", gy)):
        if abs(v) > MAX_VAL:
            fail("out_of_range:" + name)
    if k < 0 or k > MAX_VAL:
        fail("out_of_range:k")
    for v in range(2, int(p ** 0.5) + 1):
        if p % v == 0:
            fail("not_prime:p")
    a %= p
    b %= p
    gx %= p
    gy %= p
    if (4 * a ** 3 + 27 * b ** 2) % p == 0:
        fail("singular:a,b")
    if (gy * gy - (gx ** 3 + a * gx + b)) % p != 0:
        fail("off_curve:g")

    def add(p1, p2):
        if p1 is None:
            return p2
        if p2 is None:
            return p1
        x1, y1 = p1
        x2, y2 = p2
        if x1 == x2:
            if (y1 + y2) % p == 0:
                return None
            lam = (3 * x1 * x1 + a) * pow(2 * y1 % p, p - 2, p) % p
        else:
            lam = (y2 - y1) * pow((x2 - x1) % p, p - 2, p) % p
        x3 = (lam * lam - x1 - x2) % p
        y3 = (lam * (x1 - x3) - y1) % p
        return (x3, y3)

    result = None
    cur = (gx, gy)
    while k:
        if k & 1:
            result = add(result, cur)
        cur = add(cur, cur)
        k >>= 1
    return None if result is None else [result[0], result[1]]


def domino_tiling_count(rows, cols):
    """Number of perfect domino tilings of a rows x cols grid.

    rows and cols are positive ints, each at most
    MAX_TILING_CELLS (checked before their product is taken),
    whose product is at most MAX_TILING_CELLS; an odd cell count
    answers 0 without search. Runs broken-profile
    dynamic programming cell by cell: a width-bit mask tracks
    cells already filled from above, and each empty cell tries a
    horizontal and a vertical placement. Returns the exact
    count as an int. Deterministic; an estimated
    O(cells * 2^min(rows, cols)) work."""
    fail = make_fail("domino_tiling_count")
    check_int(fail, rows, "rows")
    check_int(fail, cols, "cols")
    if rows < 1 or cols < 1:
        fail("out_of_range:rows,cols")
    if rows > MAX_TILING_CELLS or cols > MAX_TILING_CELLS:
        fail("too_many:rows,cols")
    if rows * cols > MAX_TILING_CELLS:
        fail("too_many:rows,cols")
    if (rows * cols) % 2 == 1:
        return 0
    h, w = (rows, cols) if rows >= cols else (cols, rows)
    dp = {0: 1}
    for _i in range(h):
        for j in range(w):
            nd = {}
            for mask, cnt in dp.items():
                if mask >> j & 1:
                    nm = mask & ~(1 << j)
                    nd[nm] = nd.get(nm, 0) + cnt
                else:
                    if j + 1 < w and not (mask >> (j + 1) & 1):
                        nm = mask | (1 << (j + 1))
                        nd[nm] = nd.get(nm, 0) + cnt
                    nm = mask | (1 << j)
                    nd[nm] = nd.get(nm, 0) + cnt
            dp = nd
    return dp.get(0, 0)


def de_bruijn_sequence(k, n):
    """A de Bruijn cyclic sequence over k symbols for n-words.

    k is an int from 1 and n a positive int at most MAX_DB_N
    with k ** n at most MAX_DB_LEN (both bounds are checked
    before the sequence is built); k == 1 answers [0] without
    building anything. Generates the lexicographically smallest de Bruijn
    sequence B(k, n) by the FKM construction: the concatenation
    of every Lyndon word over {0, ..., k - 1} whose length
    divides n, in lexicographic order (Duval's generation).
    Returns the sequence as a list of ints; read cyclically it
    holds every length-n word exactly once. Deterministic; an
    estimated O(k^n) work."""
    fail = make_fail("de_bruijn_sequence")
    check_int(fail, k, "k")
    check_int(fail, n, "n")
    if k < 1 or n < 1:
        fail("out_of_range:k,n")
    if n > MAX_DB_N:
        fail("too_many:n")
    if k == 1:
        return [0]
    total = 1
    for _ in range(n):
        total *= k
        if total > MAX_DB_LEN:
            fail("too_many:k,n")
    a = [0] * (n + 1)
    out = []

    def gen(t, p):
        if t > n:
            if n % p == 0:
                out.extend(a[1:p + 1])
            return
        a[t] = a[t - p]
        gen(t + 1, p)
        for j in range(a[t - p] + 1, k):
            a[t] = j
            gen(t + 1, t)

    gen(1, 1)
    return out


def bin_packing_ffd(items, capacity):
    """Bin count under first-fit decreasing packing.

    capacity is a positive int at most MAX_VAL; items holds
    ints from 1 to capacity, capped at MAX_ITEMS entries, and
    may be empty (zero bins used). Sorts the items descending
    (equal sizes pack identically regardless of order), then
    places each into the first open bin with enough remaining
    room, opening a new bin when none fits. Returns the number
    of bins used. Deterministic; an estimated O(n^2) work."""
    fail = make_fail("bin_packing_ffd")
    check_int(fail, capacity, "capacity")
    if capacity < 1 or capacity > MAX_VAL:
        fail("out_of_range:capacity")
    check_items(fail, items, "items")
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        if v < 1 or v > capacity:
            fail("out_of_range:items[%d]" % i)
    remaining = []
    for v in sorted(items, reverse=True):
        placed = False
        for j, rem in enumerate(remaining):
            if rem >= v:
                remaining[j] = rem - v
                placed = True
                break
        if not placed:
            remaining.append(capacity - v)
    return len(remaining)


def xor_basis_max(values):
    """Maximum xor of any subset of values via a linear basis.

    values is a list of ints from 0 to MAX_VAL, capped at
    MAX_ITEMS entries; an empty list answers 0. Builds a
    row-echelon xor basis over the values' bits, then greedily
    maximizes the running xor from the top bit down. Returns
    the maximum as an int. Deterministic; an estimated
    O(len(values) * 63) work."""
    fail = make_fail("xor_basis_max")
    check_items(fail, values, "values")
    for i, v in enumerate(values):
        check_int(fail, v, "values[%d]" % i)
        if v < 0 or v > MAX_VAL:
            fail("out_of_range:values[%d]" % i)
    basis = [0] * 63
    for v in values:
        x = v
        for b in range(62, -1, -1):
            if not (x >> b) & 1:
                continue
            if basis[b]:
                x ^= basis[b]
            else:
                basis[b] = x
                break
    ans = 0
    for b in range(62, -1, -1):
        if (ans ^ basis[b]) > ans:
            ans ^= basis[b]
    return ans
