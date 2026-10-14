"""P235 concepts batch 95: ten concepts.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
Strings and lists are capped at MAX_ITEMS entries; tighter caps
(MAX_BC_NODES, MAX_SIMPLIFY_POINTS,
MAX_GRAPH_EDGES, MAX_GRAM_ROWS, MAX_HILBERT_ORDER,
MAX_POLY_DEGREE, MAX_SOLVE_N,
MAX_VITERBI_STATES, MAX_VITERBI_STEPS) are stated in the
docstrings of the functions that carry them. Length caps are
always checked before the elements they bound are inspected. Every function validates its whole input first:
type, range, and cap checks all run during the validation phase,
and the computation phase starts only after validation succeeds.
Exact arithmetic uses ints and Fractions only, except
betweenness_centrality (Fraction scores) and viterbi_decode,
which sums log probabilities as documented.
"""

from collections import deque
from fractions import Fraction
from math import log

NEG_INF = float("-inf")

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_BC_NODES = 200
MAX_GRAPH_EDGES = 200_000
MAX_HILBERT_ORDER = 31
MAX_SIMPLIFY_POINTS = 10_000
MAX_GRAM_ROWS = 20
MAX_POLY_DEGREE = 1_000
MAX_SOLVE_N = 50
MAX_VITERBI_STATES = 50
MAX_VITERBI_STEPS = 1_000
MAX_VAL = 10**9


def avl_insert_rotations(keys):
    """Rotation events from sequential AVL tree insertion.

    Inserts the keys one at a time into an initially empty AVL
    tree and returns the rebalancing events in the order they
    happen, each a two-item list [case, pivot]: case is "LL",
    "RR", "LR", or "RL" (the shape of the imbalance) and pivot is
    the key of the node at which the imbalance was repaired. "LR"
    and "RL" are double rotations recorded as one event. keys
    holds distinct ints, each at most MAX_VAL in absolute value;
    the list is capped at MAX_ITEMS entries. The walk is
    O(n log n); heights stay logarithmic by construction."""
    fail = make_fail("avl_insert_rotations")
    check_items(fail, keys, "keys")
    for i, k in enumerate(keys):
        check_int(fail, k, "keys[%d]" % i)
        if abs(k) > MAX_VAL:
            fail("too_big:keys[%d]" % i)
    if len(set(keys)) != len(keys):
        fail("duplicate:keys")
    events = []

    def height(t):
        return t[3] if t else 0

    def rotate_left(t):
        r = t[2]
        t[2] = r[1]
        r[1] = t
        t[3] = 1 + max(height(t[1]), height(t[2]))
        r[3] = 1 + max(height(r[1]), height(r[2]))
        return r

    def rotate_right(t):
        lft = t[1]
        t[1] = lft[2]
        lft[2] = t
        t[3] = 1 + max(height(t[1]), height(t[2]))
        lft[3] = 1 + max(height(lft[1]), height(lft[2]))
        return lft

    def rebalance(t):
        if height(t[1]) - height(t[2]) == 2:
            if height(t[1][1]) >= height(t[1][2]):
                events.append(["LL", t[0]])
                return rotate_right(t)
            events.append(["LR", t[0]])
            t[1] = rotate_left(t[1])
            return rotate_right(t)
        if height(t[2]) - height(t[1]) == 2:
            if height(t[2][2]) >= height(t[2][1]):
                events.append(["RR", t[0]])
                return rotate_left(t)
            events.append(["RL", t[0]])
            t[2] = rotate_right(t[2])
            return rotate_left(t)
        return t

    def insert(t, key):
        if t is None:
            return [key, None, None, 1]
        if key < t[0]:
            t[1] = insert(t[1], key)
        else:
            t[2] = insert(t[2], key)
        t[3] = 1 + max(height(t[1]), height(t[2]))
        return rebalance(t)

    root = None
    for k in keys:
        root = insert(root, k)
    return events


def _check_simple_graph(fail, adj, name):
    check_items(fail, adj, name)
    if not adj:
        fail("empty:%s" % name)
    n = len(adj)
    total = 0
    for i, outs in enumerate(adj):
        check_items(fail, outs, "%s[%d]" % (name, i))
        total += len(outs)
        if total > MAX_GRAPH_EDGES:
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


def chordal_check(adj):
    """Whether the undirected simple graph is chordal.

    Runs maximum cardinality search to produce an elimination
    ordering, then verifies it is perfect: each vertex's later
    neighbors in the ordering must form a clique. Both phases are
    an estimated O(n + e) work. adj must be symmetric with no self
    loops or duplicate neighbors and is capped at MAX_ITEMS
    nodes and MAX_GRAPH_EDGES total neighbor entries (checked
    before any entry is inspected)."""
    fail = make_fail("chordal_check")
    n = _check_simple_graph(fail, adj, "adj")
    weight = [0] * n
    numbered = [False] * n
    buckets = [set() for _ in range(n + 1)]
    for v in range(n):
        buckets[0].add(v)
    top = 0
    order = []
    for _ in range(n):
        while top > 0 and not buckets[top]:
            top -= 1
        pick = buckets[top].pop()
        numbered[pick] = True
        order.append(pick)
        for u in adj[pick]:
            if not numbered[u]:
                buckets[weight[u]].discard(u)
                weight[u] += 1
                buckets[weight[u]].add(u)
                if weight[u] > top:
                    top = weight[u]
    order.reverse()  # the elimination order is the reverse of selection
    position = [0] * n
    for idx, v in enumerate(order):
        position[v] = idx
    adj_sets = [set(outs) for outs in adj]
    for v in range(n):
        later = [u for u in adj[v] if position[u] > position[v]]
        if not later:
            continue
        parent = min(later, key=lambda u: position[u])
        for u in later:
            if u != parent and parent not in adj_sets[u]:
                return False
    return True


def betweenness_centrality(adj):
    """Brandes betweenness centrality of every node, as Fractions.

    Unnormalized scores: the sum over unordered source-target
    pairs of the fraction of shortest paths that pass through the
    node. Brandes accumulation counts every unordered pair once
    from each endpoint, so the raw sums are halved at the end.
    Undirected simple graph, capped at MAX_BC_NODES nodes (checked
    before any neighbor list is inspected); the algorithm is an
    estimated O(n * e) work."""
    fail = make_fail("betweenness_centrality")
    check_items(fail, adj, "adj")
    if len(adj) > MAX_BC_NODES:
        fail("too_many:adj")
    n = _check_simple_graph(fail, adj, "adj")
    cb = [Fraction(0)] * n
    for s in range(n):
        stack = []
        pred = [[] for _ in range(n)]
        sigma = [Fraction(0)] * n
        sigma[s] = Fraction(1)
        dist = [-1] * n
        dist[s] = 0
        queue = deque([s])
        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in adj[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = [Fraction(0)] * n
        while stack:
            w = stack.pop()
            for v in pred[w]:
                delta[v] += sigma[v] / sigma[w] * (1 + delta[w])
            if w != s:
                cb[w] += delta[w]
    return [c / 2 for c in cb]


def hilbert_curve_point(order, d):
    """Grid point at index d along the order-n Hilbert curve.

    The order-n curve fills a 2**n by 2**n integer grid, visiting
    every cell once; this returns the [x, y] coordinates of the
    cell visited at index d (0-based). Computed by the standard
    bit-interleaving walk over the base-4 digits of d, an
    estimated O(order) work with exact ints throughout. order is
    capped at MAX_HILBERT_ORDER and d must lie in
    [0, 4**order - 1]."""
    fail = make_fail("hilbert_curve_point")
    check_int(fail, order, "order")
    check_int(fail, d, "d")
    if order < 1 or order > MAX_HILBERT_ORDER:
        fail("out_of_range:order")
    if d < 0 or d >= 4 ** order:
        fail("out_of_range:d")
    x = y = 0
    t = d
    s = 1
    for _ in range(order):
        rx = 1 & (t // 2)
        ry = 1 & (t ^ rx)
        if ry == 0:
            if rx == 1:
                x = s - 1 - x
                y = s - 1 - y
            x, y = y, x
        x += s * rx
        y += s * ry
        t //= 4
        s *= 2
    return [x, y]


def polyline_simplify(points, epsilon):
    """Douglas-Peucker simplification of the polyline.

    Keeps endpoints and recursively splits at the farthest point
    whenever that distance exceeds epsilon, using an explicit stack
    and exact integer arithmetic, so no square roots are taken.
    Distances are measured to the segment, not the infinite line:
    a point whose projection falls outside the segment is measured
    against the nearer endpoint. points holds [x, y] int pairs
    capped at MAX_SIMPLIFY_POINTS entries and MAX_VAL in magnitude;
    epsilon is a non-negative int."""
    fail = make_fail("polyline_simplify")
    check_items(fail, points, "points")
    if not points:
        fail("empty:points")
    if len(points) > MAX_SIMPLIFY_POINTS:
        fail("too_many:points")
    for i, pt in enumerate(points):
        if type(pt) is not list or len(pt) != 2:
            fail("bad_point:points[%d]" % i)
        for j, v in enumerate(pt):
            check_int(fail, v, "points[%d][%d]" % (i, j))
            if v < -MAX_VAL or v > MAX_VAL:
                fail("out_of_range:points[%d][%d]" % (i, j))
    check_int(fail, epsilon, "epsilon")
    if epsilon < 0 or epsilon > MAX_VAL:
        fail("out_of_range:epsilon")
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        x1, y1 = points[a]
        x2, y2 = points[b]
        dx = x2 - x1
        dy = y2 - y1
        base2 = dx * dx + dy * dy
        best_num = -1
        best_den = 1
        far = -1
        for i in range(a + 1, b):
            xi, yi = points[i]
            dot = (xi - x1) * dx + (yi - y1) * dy
            if base2 == 0 or dot <= 0:
                num = (xi - x1) ** 2 + (yi - y1) ** 2
                den = 1
            elif dot >= base2:
                num = (xi - x2) ** 2 + (yi - y2) ** 2
                den = 1
            else:
                cross = abs(dx * (yi - y1) - dy * (xi - x1))
                num = cross * cross
                den = base2
            if num * best_den > best_num * den:
                best_num = num
                best_den = den
                far = i
        if best_num > epsilon * epsilon * best_den:
            keep[far] = True
            stack.append((a, far))
            stack.append((far, b))
    return [points[i] for i in range(len(points)) if keep[i]]


def gram_schmidt_orthogonal(rows):
    """Orthogonal basis of the row space via Gram-Schmidt.

    Each output row is an input row minus its projections onto the
    earlier output rows, kept in exact Fractions and left
    unnormalized so the results stay exact. Linearly dependent
    input rows project to the zero vector and are skipped. rows is
    capped at MAX_GRAM_ROWS rows and columns and MAX_VAL in
    magnitude."""
    fail = make_fail("gram_schmidt_orthogonal")
    check_items(fail, rows, "rows")
    if not rows:
        fail("empty:rows")
    if len(rows) > MAX_GRAM_ROWS:
        fail("too_many:rows")
    width = None
    for i, row in enumerate(rows):
        check_items(fail, row, "rows[%d]" % i)
        if not row:
            fail("empty:rows[%d]" % i)
        if len(row) > MAX_GRAM_ROWS:
            fail("too_many:rows[%d]" % i)
        if width is None:
            width = len(row)
        elif len(row) != width:
            fail("ragged:rows")
        for j, v in enumerate(row):
            check_int(fail, v, "rows[%d][%d]" % (i, j))
            if v < -MAX_VAL or v > MAX_VAL:
                fail("out_of_range:rows[%d][%d]" % (i, j))
    basis = []
    for row in rows:
        v = [Fraction(x) for x in row]
        for b in basis:
            bb = sum(x * x for x in b)
            coef = sum(x * y for x, y in zip(v, b)) / bb
            v = [x - coef * y for x, y in zip(v, b)]
        if any(x != 0 for x in v):
            basis.append(v)
    return basis


_CRIB_RANKS = "A23456789TJQK"


def _crib_card(fail, text, name):
    check_str(fail, text, name)
    if len(text) != 2 or text[0] not in _CRIB_RANKS \
            or text[1] not in "CDHS":
        fail("bad_card:%s" % name)
    return text


def cribbage_score(hand, starter):
    """Cribbage points of the four-card hand plus the starter.

    Cards are rank (A,2..9,T,J,Q,K) then suit (C,D,H,S). Scores
    every fifteen subset, pairs, maximal runs of three or more,
    the flush (four in hand for 4, five with the starter for 5),
    and nobs (the jack of the starter suit in hand). Cards must be
    distinct."""
    fail = make_fail("cribbage_score")
    check_items(fail, hand, "hand")
    if len(hand) != 4:
        fail("bad_count:hand")
    for i, c in enumerate(hand):
        _crib_card(fail, c, "hand[%d]" % i)
    _crib_card(fail, starter, "starter")
    if len(set(hand) | {starter}) != 5:
        fail("duplicate:hand,starter")
    ranks = [_CRIB_RANKS.index(c[0]) + 1 for c in hand]
    ranks.append(_CRIB_RANKS.index(starter[0]) + 1)
    values = [min(r, 10) for r in ranks]
    suits = [c[1] for c in hand] + [starter[1]]
    score = 0
    for mask in range(1, 32):
        total = 0
        for k in range(5):
            if mask >> k & 1:
                total += values[k]
        if total == 15:
            score += 2
    counts = [0] * 14
    for r in ranks:
        counts[r] += 1
    for c in counts:
        score += c * (c - 1)
    best = 0
    for lo in range(1, 12):
        run = 0
        mult = 1
        for r in range(lo, 14):
            if counts[r]:
                run += 1
                mult *= counts[r]
                if run >= 3 and run * mult > best:
                    best = run * mult
            else:
                break
    score += best
    if all(s == suits[0] for s in suits[:4]):
        score += 5 if suits[4] == suits[0] else 4
    for i, c in enumerate(hand):
        if c[0] == "J" and c[1] == starter[1]:
            score += 1
    return score


def polynomial_divmod_exact(dividend, divisor):
    """Exact quotient and remainder of polynomial division.

    Coefficient lists are in ascending order; trailing zeros are
    allowed and ignored. Returns [quotient, remainder] with
    Fraction coefficients and deg(remainder) < deg(divisor).
    Degrees are capped at MAX_POLY_DEGREE and coefficients at
    MAX_VAL in magnitude."""
    fail = make_fail("polynomial_divmod_exact")
    check_items(fail, dividend, "dividend")
    check_items(fail, divisor, "divisor")
    if not dividend:
        fail("empty:dividend")
    if not divisor:
        fail("empty:divisor")
    for name, poly in (("dividend", dividend), ("divisor", divisor)):
        if len(poly) > MAX_POLY_DEGREE + 1:
            fail("too_many:%s" % name)
        for i, c in enumerate(poly):
            check_int(fail, c, "%s[%d]" % (name, i))
            if c < -MAX_VAL or c > MAX_VAL:
                fail("out_of_range:%s[%d]" % (name, i))
    def trim(poly):
        end = len(poly)
        while end > 1 and poly[end - 1] == 0:
            end -= 1
        return poly[:end]
    rem = [Fraction(c) for c in trim(dividend)]
    div = [Fraction(c) for c in trim(divisor)]
    if all(c == 0 for c in div):
        fail("zero:divisor")
    if len(rem) < len(div):
        return [[Fraction(0)], rem]
    quo = [Fraction(0)] * (len(rem) - len(div) + 1)
    while len(rem) >= len(div) and not (len(rem) == 1 and rem[0] == 0):
        factor = rem[-1] / div[-1]
        shift = len(rem) - len(div)
        quo[shift] = factor
        for i in range(len(div)):
            rem[shift + i] -= factor * div[i]
        trim(rem)
        while len(rem) > 1 and rem[-1] == 0:
            rem.pop()
    return [quo, rem]


def gaussian_solve_exact(a, b):
    """Exact solution of the square linear system a x = b.

    Gaussian elimination with partial pivoting over exact
    Fractions; a singular matrix is refused. a is capped at
    MAX_SOLVE_N rows and columns and every entry at MAX_VAL in
    magnitude."""
    fail = make_fail("gaussian_solve_exact")
    check_items(fail, a, "a")
    if not a:
        fail("empty:a")
    if len(a) > MAX_SOLVE_N:
        fail("too_many:a")
    n = len(a)
    for i, row in enumerate(a):
        check_items(fail, row, "a[%d]" % i)
        if len(row) != n:
            fail("ragged:a")
        for j, v in enumerate(row):
            check_int(fail, v, "a[%d][%d]" % (i, j))
            if v < -MAX_VAL or v > MAX_VAL:
                fail("out_of_range:a[%d][%d]" % (i, j))
    check_items(fail, b, "b")
    if len(b) != n:
        fail("length_mismatch:a,b")
    for i, v in enumerate(b):
        check_int(fail, v, "b[%d]" % i)
        if v < -MAX_VAL or v > MAX_VAL:
            fail("out_of_range:b[%d]" % i)
    m = [[Fraction(v) for v in row] + [Fraction(b[i])]
         for i, row in enumerate(a)]
    for col in range(n):
        piv = -1
        for r in range(col, n):
            if m[r][col] != 0 and (piv < 0 or
                                   abs(m[r][col]) > abs(m[piv][col])):
                piv = r
        if piv < 0:
            fail("singular:a")
        m[col], m[piv] = m[piv], m[col]
        inv = 1 / m[col][col]
        m[col] = [v * inv for v in m[col]]
        for r in range(n):
            if r != col and m[r][col] != 0:
                factor = m[r][col]
                m[r] = [x - factor * y for x, y in zip(m[r], m[col])]
    return [m[i][n] for i in range(n)]


def viterbi_decode(start, trans, emit, observations):
    """Most likely hidden state sequence of an HMM (Viterbi).

    start, trans (state x state), and emit (state x emission) hold
    float probabilities; every row must be non-negative and sum to
    one within 1e-9. Scores are summed log probabilities, so no
    product can underflow; impossible transitions (probability
    zero) score minus infinity, and ties go to the lowest state
    index.
    States are capped at MAX_VITERBI_STATES and the observation
    sequence at MAX_VITERBI_STEPS."""
    fail = make_fail("viterbi_decode")
    def check_prob(v, name):
        if type(v) not in (int, float) or v != v:
            fail("bad_type:%s" % name)
        if v < 0 or v > 1:
            fail("out_of_range:%s" % name)
        return float(v)
    check_items(fail, start, "start")
    if not start:
        fail("empty:start")
    if len(start) > MAX_VITERBI_STATES:
        fail("too_many:start")
    n = len(start)
    probs_start = [check_prob(v, "start[%d]" % i)
                   for i, v in enumerate(start)]
    def check_matrix(mat, name, rows, cols):
        check_items(fail, mat, name)
        if len(mat) != rows:
            fail("bad_shape:%s" % name)
        out = []
        for i, row in enumerate(mat):
            check_items(fail, row, "%s[%d]" % (name, i))
            if len(row) != cols:
                fail("bad_shape:%s" % name)
            vals = [check_prob(v, "%s[%d][%d]" % (name, i, j))
                    for j, v in enumerate(row)]
            if abs(sum(vals) - 1.0) > 1e-9:
                fail("bad_row:%s[%d]" % (name, i))
            out.append(vals)
        return out
    if abs(sum(probs_start) - 1.0) > 1e-9:
        fail("bad_row:start")
    t = check_matrix(trans, "trans", n, n)
    check_items(fail, emit, "emit")
    if not emit:
        fail("empty:emit")
    check_items(fail, emit[0], "emit[0]")
    em = check_matrix(emit, "emit", n, len(emit[0]))
    check_items(fail, observations, "observations")
    if not observations:
        fail("empty:observations")
    if len(observations) > MAX_VITERBI_STEPS:
        fail("too_many:observations")
    for i, v in enumerate(observations):
        check_int(fail, v, "observations[%d]" % i)
        if v < 0 or v >= len(em[0]):
            fail("out_of_range:observations[%d]" % i)
    log_start = [log(v) if v > 0 else NEG_INF for v in probs_start]
    log_t = [[log(v) if v > 0 else NEG_INF for v in row]
             for row in t]
    log_em = [[log(v) if v > 0 else NEG_INF for v in row]
              for row in em]
    delta = [log_start[s] + log_em[s][observations[0]]
             for s in range(n)]
    back = []
    for obs in observations[1:]:
        nxt = []
        row_back = []
        for s in range(n):
            best = NEG_INF
            arg = 0
            for p in range(n):
                cand = delta[p] + log_t[p][s] + log_em[s][obs]
                if cand > best:
                    best = cand
                    arg = p
            row_back.append(arg)
            nxt.append(best)
        delta = nxt
        back.append(row_back)
    last = 0
    for s in range(1, n):
        if delta[s] > delta[last]:
            last = s
    path = [last]
    for row_back in reversed(back):
        last = row_back[last]
        path.append(last)
    return path[::-1]
