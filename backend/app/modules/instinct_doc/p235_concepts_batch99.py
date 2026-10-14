"""P235 concepts batch 99: ten concepts.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
Lists are capped at MAX_ITEMS entries; tighter caps
(MAX_CONVEX_POINTS, MAX_HENSEL_DEGREE, MAX_HENSEL_PRIME,
MAX_HENSEL_K, MAX_ROOT_DEGREE, MAX_ROOT_COEFF, MAX_LP_ROWS,
MAX_MCM_NODES, MAX_GEOHASH_LEN, MAX_PELL_D,
MAX_NONOGRAM_CLUES, MAX_NONOGRAM_WIDTH) are stated in the docstrings of
the functions that carry them. Every function validates its
whole input first: length and magnitude caps are checked before
the elements they bound are inspected and before any
arithmetic that could build big ints, then type, range, and
shape checks run during the validation phase, and the
computation phase starts only after validation succeeds. Exact
arithmetic uses ints and Fractions only.
"""

from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_CONVEX_POINTS = 64
MAX_HENSEL_DEGREE = 64
MAX_HENSEL_PRIME = 10**6
MAX_HENSEL_K = 32
MAX_ROOT_DEGREE = 8
MAX_ROOT_COEFF = 10**6
MAX_LP_ROWS = 32
MAX_MCM_NODES = 64
MAX_GEOHASH_LEN = 12
MAX_PELL_D = 2000
MAX_NONOGRAM_CLUES = 64
MAX_NONOGRAM_WIDTH = 128
MAX_NONOGRAM_NODES = 200000
MAX_VAL = 10**9


def _check_convex_ccw(fail, poly, name):
    check_items(fail, poly, name)
    if len(poly) < 3:
        fail("too_few:" + name)
    if len(poly) > MAX_CONVEX_POINTS:
        fail("too_many:" + name)
    pts = []
    for i, row in enumerate(poly):
        check_items(fail, row, "%s[%d]" % (name, i))
        if len(row) != 2:
            fail("bad_shape:%s[%d]" % (name, i))
        for j, v in enumerate(row):
            check_int(fail, v, "%s[%d][%d]" % (name, i, j))
            if v < -MAX_VAL or v > MAX_VAL:
                fail("out_of_range:%s[%d]" % (name, i))
        pts.append((row[0], row[1]))
    if len(set(pts)) != len(pts):
        fail("duplicate:%s" % name)
    n = len(pts)
    area2 = 0
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        c = pts[(i + 2) % n]
        cross = ((b[0] - a[0]) * (c[1] - b[1])
                 - (b[1] - a[1]) * (c[0] - b[0]))
        if cross < 0:
            fail("not_convex:%s" % name)
        area2 += a[0] * b[1] - a[1] * b[0]
    if area2 <= 0:
        fail("not_ccw:%s" % name)
    # global simplicity: every vertex must lie weakly left of
    # every edge it is not an endpoint of; a positive-turn
    # self-crossing like a pentagram fails this.
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        for j in range(n):
            if j == i or j == (i + 1) % n:
                continue
            v = pts[j]
            if ((b[0] - a[0]) * (v[1] - a[1])
                    - (b[1] - a[1]) * (v[0] - a[0])) < 0:
                fail("not_convex:%s" % name)
    return pts


def nonogram_line_solve(clues, cells):
    """Cells forced by a nonogram line's clues and known cells.

    clues lists the run lengths as ints from 1 to the line
    width, capped at MAX_NONOGRAM_CLUES entries (each clue is
    range-checked before any sum is taken), and may be empty
    (the line must be all blank). cells lists the line as
    ints: 1 for a known filled cell, 2 for a known blank, 0
    for unknown; the width is 1 to MAX_NONOGRAM_WIDTH. Every
    placement of the clue runs that respects the known cells
    is enumerated, and the search is capped at
    MAX_NONOGRAM_NODES visited placement nodes, refusing
    too_complex past that. A cell is forced when every
    placement agrees on it. Returns one int per cell: 1 when
    every placement fills it, 2 when every placement leaves
    it blank, 0 when placements disagree. Refuses
    inconsistent when no placement respects the known cells.
    Deterministic; an estimated O(nodes * width) work."""
    fail = make_fail("nonogram_line_solve")
    check_items(fail, clues, "clues")
    if len(clues) > MAX_NONOGRAM_CLUES:
        fail("too_many:clues")
    check_items(fail, cells, "cells")
    if not cells:
        fail("empty:cells")
    if len(cells) > MAX_NONOGRAM_WIDTH:
        fail("too_many:cells")
    width = len(cells)
    known = []
    for i, v in enumerate(cells):
        check_int(fail, v, "cells[%d]" % i)
        if v not in (0, 1, 2):
            fail("out_of_range:cells[%d]" % i)
        known.append(v)
    runs = []
    for i, v in enumerate(clues):
        check_int(fail, v, "clues[%d]" % i)
        if v < 1 or v > width:
            fail("out_of_range:clues[%d]" % i)
        runs.append(v)
    if runs and sum(runs) + len(runs) - 1 > width:
        fail("bad_shape:clues")

    fill = [0] * width
    total = [0]
    nodes = [0]

    def place(idx, pos, marks, last_end):
        nodes[0] += 1
        if nodes[0] > MAX_NONOGRAM_NODES:
            fail("too_complex:clues,cells")
        if idx == len(runs):
            for j in range(last_end, width):
                if known[j] == 1:
                    return
            total[0] += 1
            for j in range(width):
                if marks[j]:
                    fill[j] += 1
            return
        run = runs[idx]
        tail = sum(runs[idx + 1:]) + len(runs) - idx - 1
        start = pos
        while start + run + tail <= width:
            ok = True
            for j in range(start, start + run):
                if known[j] == 2:
                    ok = False
                    break
            if ok:
                for j in range(last_end, start):
                    if known[j] == 1:
                        ok = False
                        break
            if ok:
                marks2 = marks[:]
                for j in range(start, start + run):
                    marks2[j] = 1
                place(idx + 1, start + run + 1, marks2,
                      start + run)
            start += 1

    if not runs:
        if any(v == 1 for v in known):
            fail("inconsistent:cells")
        return [2] * width
    place(0, 0, [0] * width, 0)
    if total[0] == 0:
        fail("inconsistent:cells")
    out = []
    for j in range(width):
        if fill[j] == total[0]:
            out.append(1)
        elif fill[j] == 0:
            out.append(2)
        else:
            out.append(0)
    return out


def hensel_lift_root(coeffs, p, k, root):
    """Lift a simple mod-p root of a polynomial to a mod-p^k root.

    coeffs holds the integer coefficients of f in ascending
    order (coeffs[i] multiplies x**i), degree 1 to
    MAX_HENSEL_DEGREE with a nonzero leading coefficient and
    each coefficient from -MAX_VAL to MAX_VAL. p is a prime
    from 2 to MAX_HENSEL_PRIME (trial-divided) and k an int
    from 1 to MAX_HENSEL_K. root is an int from -MAX_VAL to
    MAX_VAL, reduced mod p after validation; it must satisfy
    f(root) === 0 (mod p) with f'(root) nonzero mod p,
    otherwise this refuses. Newton lifting with the fixed
    inverse of f'(root) mod p then doubles the modulus one p
    at a time up to p**k. Returns the unique lift in
    [0, p**k). Deterministic; an estimated
    O(k * degree) modular evaluations."""
    fail = make_fail("hensel_lift_root")
    check_items(fail, coeffs, "coeffs")
    if len(coeffs) < 2:
        fail("too_few:coeffs")
    if len(coeffs) - 1 > MAX_HENSEL_DEGREE:
        fail("too_many:coeffs")
    check_int(fail, p, "p")
    check_int(fail, k, "k")
    check_int(fail, root, "root")
    if p < 2 or p > MAX_HENSEL_PRIME:
        fail("out_of_range:p")
    if k < 1 or k > MAX_HENSEL_K:
        fail("out_of_range:k")
    if root < -MAX_VAL or root > MAX_VAL:
        fail("out_of_range:root")
    cs = []
    for i, v in enumerate(coeffs):
        check_int(fail, v, "coeffs[%d]" % i)
        if v < -MAX_VAL or v > MAX_VAL:
            fail("out_of_range:coeffs[%d]" % i)
        cs.append(v)
    while len(cs) > 1 and cs[-1] == 0:
        fail("bad_shape:coeffs")
    for v in range(2, int(p ** 0.5) + 1):
        if p % v == 0:
            fail("not_prime:p")

    def ev(poly, x, m):
        acc = 0
        for c in reversed(poly):
            acc = (acc * x + c) % m
        return acc

    r = root % p
    if ev(cs, r, p) != 0:
        fail("not_root:root")
    derv = [i * cs[i] for i in range(1, len(cs))]
    dv = ev(derv, r, p)
    if dv == 0:
        fail("not_simple:root")
    inv = pow(dv, p - 2, p)
    m = p
    for _ in range(1, k):
        m *= p
        r = (r - ev(cs, r, m) * inv) % m
    if ev(cs, r, m) != 0:
        fail("not_root:root")
    return r


def rational_roots_list(coeffs):
    """All rational roots of an integer polynomial.

    coeffs holds the coefficients in ascending order
    (coeffs[i] multiplies x**i), degree 1 to MAX_ROOT_DEGREE
    with a nonzero leading coefficient and each coefficient
    from -MAX_ROOT_COEFF to MAX_ROOT_COEFF. Every rational root
    p / q in lowest terms has p dividing the constant term and
    q dividing the leading coefficient; all candidates are
    checked with exact integer evaluation, and 0 is included
    whenever the constant term is 0. Returns the distinct
    roots as a list of Fractions sorted ascending.
    Deterministic; an estimated O(divisors^2 * degree) work."""
    fail = make_fail("rational_roots_list")
    check_items(fail, coeffs, "coeffs")
    if len(coeffs) < 2:
        fail("too_few:coeffs")
    if len(coeffs) - 1 > MAX_ROOT_DEGREE:
        fail("too_many:coeffs")
    cs = []
    for i, v in enumerate(coeffs):
        check_int(fail, v, "coeffs[%d]" % i)
        if v < -MAX_ROOT_COEFF or v > MAX_ROOT_COEFF:
            fail("out_of_range:coeffs[%d]" % i)
        cs.append(v)
    if cs[-1] == 0:
        fail("bad_shape:coeffs")
    zero_root = cs[0] == 0
    while cs[0] == 0:
        cs = cs[1:]

    def divisors(x):
        x = abs(x)
        out = []
        i = 1
        while i * i <= x:
            if x % i == 0:
                out.append(i)
                if i * i != x:
                    out.append(x // i)
            i += 1
        return out

    ps = divisors(cs[0])
    qs = divisors(cs[-1])
    deg = len(cs) - 1
    from math import gcd
    roots = set()
    for q in qs:
        for p_ in ps:
            for sign in (1, -1):
                num = sign * p_
                # exact value of f(num / q) * q**deg
                val = 0
                pow_n = 1
                for i, c in enumerate(cs):
                    val += c * pow_n * q ** (deg - i)
                    pow_n *= num
                if val == 0:
                    g = gcd(abs(num), q)
                    roots.add(Fraction(num // g, q // g))
    if zero_root:
        roots.add(Fraction(0))
    return sorted(roots)


def move_to_front_transform(data):
    """Move-to-front transform of a byte sequence.

    data holds ints from 0 to 255, capped at MAX_ITEMS
    entries, and may be empty. The table starts as
    [0, 1, ..., 255]; each symbol emits its current index and
    then moves to the front. Returns the emitted indices as a
    list of ints. Deterministic; an estimated O(n * 256)
    work."""
    fail = make_fail("move_to_front_transform")
    check_items(fail, data, "data")
    vals = []
    for i, v in enumerate(data):
        check_int(fail, v, "data[%d]" % i)
        if v < 0 or v > 255:
            fail("out_of_range:data[%d]" % i)
        vals.append(v)
    table = list(range(256))
    out = []
    for v in vals:
        idx = table.index(v)
        out.append(idx)
        table.insert(0, table.pop(idx))
    return out


def convex_polygon_intersection_area2(poly_a, poly_b):
    """Twice the area of the intersection of two convex polygons.

    poly_a and poly_b follow the same contract as
    minkowski_sum_convex (convex, counterclockwise, 3 to
    MAX_CONVEX_POINTS vertices, coordinates from -MAX_VAL to
    MAX_VAL). Clips poly_a by every edge half-plane of poly_b
    (Sutherland-Hodgman with exact Fraction coordinates) and
    returns twice the area of the surviving polygon as a
    Fraction, 0 when the polygons are disjoint or touch on a
    boundary. Deterministic; an estimated O(n * m) work."""
    fail = make_fail("convex_polygon_intersection_area2")
    a = _check_convex_ccw(fail, poly_a, "poly_a")
    b = _check_convex_ccw(fail, poly_b, "poly_b")

    def cross(o, p, q):
        return ((p[0] - o[0]) * (q[1] - o[1])
                - (p[1] - o[1]) * (q[0] - o[0]))

    def clip(poly, e0, e1):
        out = []
        n = len(poly)
        for i in range(n):
            s = poly[i]
            t = poly[(i + 1) % n]
            cs = cross(e0, e1, s)
            ct = cross(e0, e1, t)
            if cs >= 0:
                out.append(s)
            if (cs > 0) != (ct > 0):
                num_s = cross(e0, e1, s)
                num_t = cross(e0, e1, t)
                f = Fraction(num_s, num_s - num_t)
                out.append((s[0] + f * (t[0] - s[0]),
                            s[1] + f * (t[1] - s[1])))
        return out

    poly = [(Fraction(x), Fraction(y)) for x, y in a]
    m = len(b)
    for i in range(m):
        poly = clip(poly, b[i], b[(i + 1) % m])
        if not poly:
            return Fraction(0)
    area2 = Fraction(0)
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        area2 += x1 * y2 - y1 * x2
    return area2 if area2 > 0 else -area2


def lp_2var_max_exact(c, rows, lower, upper):
    """Exact maximum of a two-variable linear program.

    Maximizes c[0] * x + c[1] * y over the box lower <= x, y
    <= upper and the constraint rows [a, b, r] with
    a * x + b * y <= r. c holds two ints, lower and upper are
    ints with lower <= upper, and rows is capped at
    MAX_LP_ROWS with each entry from -MAX_VAL to MAX_VAL; all
    five ints of c, lower, upper are bounded by MAX_VAL in
    absolute value. The optimum over a bounded feasible box is
    attained at a box corner, a box-constraint crossing, or a
    constraint-pair intersection; all such candidates are
    enumerated with exact Fraction arithmetic. Returns
    [value, x, y] as Fractions; ties break to the
    lexicographically smallest [x, y]. Refuses infeasible
    when no point satisfies every constraint."""
    fail = make_fail("lp_2var_max_exact")
    check_items(fail, c, "c")
    if len(c) != 2:
        fail("bad_shape:c")
    for j, v in enumerate(c):
        check_int(fail, v, "c[%d]" % j)
        if v < -MAX_VAL or v > MAX_VAL:
            fail("out_of_range:c[%d]" % j)
    check_int(fail, lower, "lower")
    check_int(fail, upper, "upper")
    if lower < -MAX_VAL or upper > MAX_VAL or lower > upper:
        fail("out_of_range:lower,upper")
    check_items(fail, rows, "rows")
    if len(rows) > MAX_LP_ROWS:
        fail("too_many:rows")
    cons = []
    for i, row in enumerate(rows):
        check_items(fail, row, "rows[%d]" % i)
        if len(row) != 3:
            fail("bad_shape:rows[%d]" % i)
        for j, v in enumerate(row):
            check_int(fail, v, "rows[%d][%d]" % (i, j))
            if v < -MAX_VAL or v > MAX_VAL:
                fail("out_of_range:rows[%d][%d]" % (i, j))
        if row[0] == 0 and row[1] == 0:
            if row[2] < 0:
                fail("infeasible:rows")
            continue
        cons.append(row)
    lo = Fraction(lower)
    up = Fraction(upper)
    cands = [(lo, lo), (lo, up), (up, lo), (up, up)]

    def line_intersect(a1, b1, r1, a2, b2, r2):
        det = a1 * b2 - a2 * b1
        if det == 0:
            return None
        x = Fraction(r1 * b2 - r2 * b1, det)
        y = Fraction(a1 * r2 - a2 * r1, det)
        return (x, y)

    for i in range(len(cons)):
        a1, b1, r1 = cons[i]
        if b1 != 0:
            for xv in (lo, up):
                cands.append((xv, Fraction(r1 - a1 * xv, b1)))
        if a1 != 0:
            for yv in (lo, up):
                cands.append((Fraction(r1 - b1 * yv, a1), yv))
        for j in range(i + 1, len(cons)):
            a2, b2, r2 = cons[j]
            pt = line_intersect(a1, b1, r1, a2, b2, r2)
            if pt is not None:
                cands.append(pt)

    def feasible(pt):
        x, y = pt
        if x < lo or x > up or y < lo or y > up:
            return False
        for a1, b1, r1 in cons:
            if a1 * x + b1 * y > r1:
                return False
        return True

    best = None
    best_pt = None
    for pt in cands:
        if not feasible(pt):
            continue
        val = c[0] * pt[0] + c[1] * pt[1]
        if (best is None or val > best
                or (val == best and pt < best_pt)):
            best = val
            best_pt = pt
    if best is None:
        fail("infeasible:rows")
    return [best, best_pt[0], best_pt[1]]


def maximum_cycle_mean(nodes, edges):
    """Maximum mean weight over the directed cycles of a graph.

    nodes is an int from 1 to MAX_MCM_NODES; edges holds
    [u, v, weight] rows with endpoints in range and int
    weights from -MAX_VAL to MAX_VAL, capped at MAX_ITEMS
    entries, and parallel rows are allowed. Karp's algorithm
    runs O(nodes * edges) dynamic programming over walk
    lengths. Returns the maximum cycle mean as a Fraction.
    Refuses no_cycle when the graph has no directed cycle."""
    fail = make_fail("maximum_cycle_mean")
    check_int(fail, nodes, "nodes")
    if nodes < 1 or nodes > MAX_MCM_NODES:
        fail("out_of_range:nodes")
    check_items(fail, edges, "edges")
    adj = [[] for _ in range(nodes)]
    for i, e in enumerate(edges):
        check_items(fail, e, "edges[%d]" % i)
        if len(e) != 3:
            fail("bad_shape:edges[%d]" % i)
        for j, v in enumerate(e):
            check_int(fail, v, "edges[%d][%d]" % (i, j))
        u, v, w = e
        if not (0 <= u < nodes) or not (0 <= v < nodes):
            fail("out_of_range:edges[%d]" % i)
        if w < -MAX_VAL or w > MAX_VAL:
            fail("out_of_range:edges[%d][2]" % i)
        adj[u].append((v, w))
    # dp[k][v]: best weight of a walk of exactly k edges ending
    # at v.
    dp = [[None] * nodes for _ in range(nodes + 1)]
    dp[0] = [0] * nodes
    for k in range(1, nodes + 1):
        for u in range(nodes):
            base = dp[k - 1][u]
            if base is None:
                continue
            for v, w in adj[u]:
                cand = base + w
                if dp[k][v] is None or cand > dp[k][v]:
                    dp[k][v] = cand
    best = None
    for v in range(nodes):
        dn = dp[nodes][v]
        if dn is None:
            continue
        worst = None
        for k in range(nodes):
            dk = dp[k][v]
            if dk is None:
                continue
            cand = Fraction(dn - dk, nodes - k)
            if worst is None or cand < worst:
                worst = cand
        if worst is not None and (best is None or worst > best):
            best = worst
    if best is None:
        fail("no_cycle:edges")
    return best


def tree_centroid_find(nodes, edges):
    """Centroid nodes of a tree.

    nodes is an int from 1 to MAX_ITEMS and edges holds
    exactly nodes - 1 undirected [u, v] rows with endpoints in
    range, no loop, and no repeated pair; the graph must be a
    single tree. A centroid minimizes the largest component
    left when the node is removed. Returns the one or two
    centroid nodes sorted ascending. Deterministic; an
    estimated O(nodes) work after validation."""
    fail = make_fail("tree_centroid_find")
    check_int(fail, nodes, "nodes")
    if nodes < 1 or nodes > MAX_ITEMS:
        fail("out_of_range:nodes")
    check_items(fail, edges, "edges")
    if len(edges) != nodes - 1:
        fail("bad_shape:edges")
    adj = [[] for _ in range(nodes)]
    seen = set()
    for i, e in enumerate(edges):
        check_items(fail, e, "edges[%d]" % i)
        if len(e) != 2:
            fail("bad_shape:edges[%d]" % i)
        for j, v in enumerate(e):
            check_int(fail, v, "edges[%d][%d]" % (i, j))
        u, v = e
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
    if nodes == 1:
        return [0]
    parent = [-1] * nodes
    order = [0]
    for v in order:
        for w in adj[v]:
            if w != parent[v]:
                if parent[w] != -1 or w == 0 and v != 0:
                    pass
                if parent[w] == -1:
                    parent[w] = v
                    order.append(w)
    if len(order) != nodes:
        fail("not_tree:edges")
    size = [1] * nodes
    best_big = [0] * nodes
    for v in reversed(order[1:]):
        p = parent[v]
        size[p] += size[v]
    out = []
    best = None
    for v in range(nodes):
        big = nodes - size[v]
        for w in adj[v]:
            if parent[w] == v:
                if size[w] > big:
                    big = size[w]
        if best is None or big < best:
            best = big
            out = [v]
        elif big == best:
            out.append(v)
    return sorted(out)


_GEOHASH_ALPHABET = "0123456789bcdefghjkmnpqrstuvwxyz"


def geohash_encode(lat_e6, lon_e6, length):
    """Geohash of a coordinate pair at the given precision.

    lat_e6 and lon_e6 are the latitude and longitude in
    microdegrees as ints, latitude from -90000000 to 90000000
    and longitude from -180000000 to 180000000; length is an
    int from 1 to MAX_GEOHASH_LEN. Bisects the longitude and
    latitude ranges alternately (longitude first), five bits
    per character over the geohash base-32 alphabet. Returns
    the geohash string. Deterministic; an estimated
    O(length) work."""
    fail = make_fail("geohash_encode")
    check_int(fail, lat_e6, "lat_e6")
    check_int(fail, lon_e6, "lon_e6")
    check_int(fail, length, "length")
    if lat_e6 < -90000000 or lat_e6 > 90000000:
        fail("out_of_range:lat_e6")
    if lon_e6 < -180000000 or lon_e6 > 180000000:
        fail("out_of_range:lon_e6")
    if length < 1 or length > MAX_GEOHASH_LEN:
        fail("out_of_range:length")
    lat = [Fraction(-90), Fraction(90)]
    lon = [Fraction(-180), Fraction(180)]
    latf = Fraction(lat_e6, 10**6)
    lonf = Fraction(lon_e6, 10**6)
    out = []
    bit = 0
    ch = 0
    even = True
    while len(out) < length:
        if even:
            mid = (lon[0] + lon[1]) / 2
            if lonf >= mid:
                ch = ch * 2 + 1
                lon[0] = mid
            else:
                ch = ch * 2
                lon[1] = mid
        else:
            mid = (lat[0] + lat[1]) / 2
            if latf >= mid:
                ch = ch * 2 + 1
                lat[0] = mid
            else:
                ch = ch * 2
                lat[1] = mid
        even = not even
        bit += 1
        if bit == 5:
            out.append(_GEOHASH_ALPHABET[ch])
            bit = 0
            ch = 0
    return "".join(out)


def pell_equation_min(d):
    """Minimal positive solution of the Pell equation x^2 - d y^2 = 1.

    d is a positive int at most MAX_PELL_D that is not a perfect
    square (a square d admits no solution with y > 0 and
    refuses). Expands the continued fraction of sqrt(d) until
    the period closes, then walks the convergents to the first
    (x, y) with x^2 - d * y^2 == 1, all in exact ints. Returns
    [x, y]; the values can be enormous, which the docstring
    coverage treats as exact output, not a resource risk: the
    period of sqrt(d) for d <= MAX_PELL_D is far below any
    cap. Deterministic; an estimated O(period) work."""
    fail = make_fail("pell_equation_min")
    check_int(fail, d, "d")
    if d < 1 or d > MAX_PELL_D:
        fail("out_of_range:d")
    from math import isqrt
    a0 = isqrt(d)
    if a0 * a0 == d:
        fail("square:d")
    m, dn, a = 0, 1, a0
    frac = []
    seen = {}
    while True:
        m = dn * a - m
        dn = (d - m * m) // dn
        a = (a0 + m) // dn
        state = (m, dn)
        if state in seen:
            break
        seen[state] = len(frac)
        frac.append(a)
    p_, q_ = a0, 1
    pp, pq = 1, 0
    if p_ * p_ - d * q_ * q_ == 1:
        return [p_, q_]
    i = 0
    while True:
        ai = frac[i % len(frac)]
        p_, q_, pp, pq = ai * p_ + pp, ai * q_ + pq, p_, q_
        if p_ * p_ - d * q_ * q_ == 1:
            return [p_, q_]
        i += 1
