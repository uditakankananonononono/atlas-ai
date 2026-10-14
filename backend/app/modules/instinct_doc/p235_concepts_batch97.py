"""P235 concepts batch 97: ten concepts.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
Lists and strings are capped at MAX_ITEMS entries; tighter caps
(MAX_FLOW_NODES, MAX_STEINER_NODES, MAX_STEINER_TERMINALS,
MAX_POLYGON_POINTS, MAX_JSON_DEPTH, MAX_JSON_DIGITS, MAX_JSON_EXPONENT,
MAX_SAM_CHARS,
MAX_CHT_ITEMS, MAX_GO_BOARD) are stated in the docstrings of the
functions that carry them. Every function validates its whole
input first: length caps are checked before the elements they
bound are inspected, then type, range, and shape checks run
during the validation phase, and the computation phase starts
only after validation succeeds. Exact arithmetic uses ints and
Fractions only.
"""

from fractions import Fraction
import heapq

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_FLOW_NODES = 200
MAX_STEINER_NODES = 200
MAX_STEINER_TERMINALS = 8
MAX_POLYGON_POINTS = 500
MAX_JSON_DEPTH = 64
MAX_JSON_DIGITS = 1024
MAX_JSON_EXPONENT = 4096
MAX_SAM_CHARS = 10_000
MAX_CHT_ITEMS = 10_000
MAX_GO_BOARD = 19
MAX_VAL = 10**9


def min_cost_flow_value(nodes, edges, source, sink, amount):
    """Minimum cost to send amount units of s-t flow.

    edges holds [u, v, capacity, cost] rows with non-negative int
    capacities and costs, each at most MAX_VAL; parallel rows and
    either direction are allowed. nodes is capped at
    MAX_FLOW_NODES. Returns the least total cost of exactly
    amount units from source to sink, by successive shortest
    augmenting paths with Dijkstra and potentials, an estimated
    O(amount * (e log n)) work. Refuses short_flow when the
    network cannot carry amount units."""
    fail = make_fail("min_cost_flow_value")
    check_int(fail, nodes, "nodes")
    if nodes < 1 or nodes > MAX_FLOW_NODES:
        fail("out_of_range:nodes")
    check_int(fail, source, "source")
    check_int(fail, sink, "sink")
    if not (0 <= source < nodes) or not (0 <= sink < nodes):
        fail("out_of_range:source,sink")
    if source == sink:
        fail("same_endpoints:source,sink")
    check_int(fail, amount, "amount")
    if amount < 0 or amount > MAX_VAL:
        fail("out_of_range:amount")
    check_items(fail, edges, "edges")
    for i, e in enumerate(edges):
        check_items(fail, e, "edges[%d]" % i)
        if len(e) != 4:
            fail("bad_shape:edges[%d]" % i)
        for j, v in enumerate(e):
            check_int(fail, v, "edges[%d][%d]" % (i, j))
        u, v, cap, cost = e
        if not (0 <= u < nodes) or not (0 <= v < nodes):
            fail("out_of_range:edges[%d]" % i)
        if u == v:
            fail("self_loop:edges[%d]" % i)
        if cap < 0 or cap > MAX_VAL or cost < 0 or cost > MAX_VAL:
            fail("out_of_range:edges[%d]" % i)
    if amount == 0:
        return 0
    graph = [[] for _ in range(nodes)]
    for u, v, cap, cost in edges:
        fwd = [v, cap, cost, None]
        rev = [u, 0, -cost, fwd]
        fwd[3] = rev
        graph[u].append(fwd)
        graph[v].append(rev)
    potential = [0] * nodes
    total = 0
    sent = 0
    while sent < amount:
        dist = [None] * nodes
        dist[source] = 0
        prev = [None] * nodes
        heap = [(0, source)]
        while heap:
            d, u = heapq.heappop(heap)
            if d != dist[u]:
                continue
            for e in graph[u]:
                if e[1] <= 0:
                    continue
                w = e[2] + potential[u] - potential[e[0]]
                cand = d + w
                if dist[e[0]] is None or cand < dist[e[0]]:
                    dist[e[0]] = cand
                    prev[e[0]] = (u, e)
                    heapq.heappush(heap, (cand, e[0]))
        if dist[sink] is None:
            fail("short_flow:amount")
        for v in range(nodes):
            if dist[v] is not None:
                potential[v] += dist[v]
        add = amount - sent
        v = sink
        while v != source:
            u, e = prev[v]
            add = min(add, e[1])
            v = u
        v = sink
        while v != source:
            u, e = prev[v]
            e[1] -= add
            e[3][1] += add
            total += add * e[2]
            v = u
        sent += add
    return total


def steiner_tree_min(nodes, edges, terminals):
    """Minimum weight of a tree connecting every terminal.

    edges holds [u, v, weight] rows with positive int weights at
    most MAX_VAL, undirected and simple (no parallel pair or
    loop). nodes is capped at MAX_STEINER_NODES and terminals at
    MAX_STEINER_TERMINALS distinct nodes. Returns the weight of
    the lightest subtree containing all terminals, by subset
    dynamic programming over the terminals with Dijkstra
    relaxation per subset, an estimated
    O(2^t * (e log n) + 3^t) work. Refuses unreachable when no
    connected subgraph holds every terminal."""
    fail = make_fail("steiner_tree_min")
    check_int(fail, nodes, "nodes")
    if nodes < 1 or nodes > MAX_STEINER_NODES:
        fail("out_of_range:nodes")
    check_items(fail, edges, "edges")
    seen = set()
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
        if u == v:
            fail("self_loop:edges[%d]" % i)
        if w < 1 or w > MAX_VAL:
            fail("out_of_range:edges[%d][2]" % i)
        key = (min(u, v), max(u, v))
        if key in seen:
            fail("duplicate:edges[%d]" % i)
        seen.add(key)
        adj[u].append((v, w))
        adj[v].append((u, w))
    check_items(fail, terminals, "terminals")
    if not terminals:
        fail("empty:terminals")
    if len(terminals) > MAX_STEINER_TERMINALS:
        fail("too_many:terminals")
    for i, v in enumerate(terminals):
        check_int(fail, v, "terminals[%d]" % i)
        if not (0 <= v < nodes):
            fail("out_of_range:terminals[%d]" % i)
    if len(set(terminals)) != len(terminals):
        fail("duplicate:terminals")

    def dijkstra(starts, dist):
        heap = [(dist[v], v) for v in starts]
        heapq.heapify(heap)
        while heap:
            d, u = heapq.heappop(heap)
            if d != dist[u]:
                continue
            for w, c in adj[u]:
                cand = d + c
                if dist[w] is None or cand < dist[w]:
                    dist[w] = cand
                    heapq.heappush(heap, (cand, w))

    t = len(terminals)
    if t == 1:
        return 0
    inf = None
    dp = [None] * (1 << t)
    base = [[inf] * nodes for _ in range(t)]
    for i, s in enumerate(terminals):
        dist = [None] * nodes
        dist[s] = 0
        dijkstra([s], dist)
        base[i] = dist
    dp[0] = [0] * nodes
    for mask in range(1, 1 << t):
        low = mask & (-mask)
        if low == mask:
            i = low.bit_length() - 1
            dp[mask] = base[i]
            continue
        best = [None] * nodes
        sub = (mask - 1) & mask
        while sub:
            other = mask ^ sub
            if other and sub < other:
                a, b = dp[sub], dp[other]
                for v in range(nodes):
                    if a[v] is not None and b[v] is not None:
                        cand = a[v] + b[v]
                        if best[v] is None or cand < best[v]:
                            best[v] = cand
            sub = (sub - 1) & mask
        dijkstra([v for v in range(nodes) if best[v] is not None],
                 best)
        dp[mask] = best
    full = (1 << t) - 1
    if all(v is None for v in dp[full]):
        fail("unreachable:terminals")
    return min(v for v in dp[full] if v is not None)


def ear_clipping_triangulation(points):
    """Ear-clipping triangulation of a simple polygon.

    points lists the vertices of a simple (non-self-intersecting)
    polygon as [x, y] int pairs in boundary order, capped at
    MAX_POLYGON_POINTS entries and MAX_VAL in magnitude, with at
    least 3 distinct vertices and a nonzero signed area. Returns
    the n - 2 triangles as index triples [i, j, k] in boundary
    order, choosing the lowest-indexed ear at each step so the
    result is deterministic, an estimated O(n^2) work after the
    O(n^2) simplicity check."""
    fail = make_fail("ear_clipping_triangulation")
    check_items(fail, points, "points")
    if len(points) < 3:
        fail("too_few:points")
    if len(points) > MAX_POLYGON_POINTS:
        fail("too_many:points")
    for i, pt in enumerate(points):
        check_items(fail, pt, "points[%d]" % i)
        if len(pt) != 2:
            fail("bad_shape:points[%d]" % i)
        for j, v in enumerate(pt):
            check_int(fail, v, "points[%d][%d]" % (i, j))
            if v < -MAX_VAL or v > MAX_VAL:
                fail("out_of_range:points[%d][%d]" % (i, j))
    n = len(points)
    for i in range(n):
        if points[i] == points[(i + 1) % n]:
            fail("duplicate:points[%d]" % i)

    def cross(o, a, b):
        return ((a[0] - o[0]) * (b[1] - o[1])
                - (a[1] - o[1]) * (b[0] - o[0]))

    def on_segment(a, b, p):
        return (cross(a, b, p) == 0
                and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
                and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))

    def segments_cross(a, b, c, d):
        d1 = cross(c, d, a)
        d2 = cross(c, d, b)
        d3 = cross(a, b, c)
        d4 = cross(a, b, d)
        if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
            return True
        return (on_segment(c, d, a) or on_segment(c, d, b)
                or on_segment(a, b, c) or on_segment(a, b, d))

    edges = [(points[i], points[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if (i + 1) % n == j or (j + 1) % n == i:
                continue
            if segments_cross(*edges[i], *edges[j]):
                fail("not_simple:points")
    area2 = 0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area2 += x1 * y2 - x2 * y1
    if area2 == 0:
        fail("degenerate:points")
    ccw = area2 > 0
    remaining = list(range(n))
    triangles = []

    def is_convex(a, b, c):
        turn = cross(points[a], points[b], points[c])
        return turn > 0 if ccw else turn < 0

    def in_triangle(p, a, b, c):
        pa, pb, pc = points[a], points[b], points[c]
        d1 = cross(pa, pb, p)
        d2 = cross(pb, pc, p)
        d3 = cross(pc, pa, p)
        if ccw:
            return d1 >= 0 and d2 >= 0 and d3 >= 0
        return d1 <= 0 and d2 <= 0 and d3 <= 0

    while len(remaining) > 3:
        ear = None
        m = len(remaining)
        for pos in range(m):
            a = remaining[(pos - 1) % m]
            b = remaining[pos]
            c = remaining[(pos + 1) % m]
            if not is_convex(a, b, c):
                continue
            if any(in_triangle(points[q], a, b, c)
                   for q in remaining if q not in (a, b, c)):
                continue
            ear = pos
            break
        if ear is None:
            fail("not_simple:points")
        m = len(remaining)
        triangles.append([remaining[(ear - 1) % m], remaining[ear],
                          remaining[(ear + 1) % m]])
        remaining.pop(ear)
    triangles.append(list(remaining))
    return triangles


_JSON_ESCAPES = {'"': '"', "\\": "\\", "/": "/",
                 "b": "\b", "f": "\f", "n": "\n",
                 "r": "\r", "t": "\t"}


def json_parse_value(text):
    """Strict JSON text parsed to Python values.

    Objects and arrays become dicts and lists, strings are
    unescaped (the six short forms plus \\uXXXX), true/false/null
    become True/False/None, integers become ints, and numbers
    with a fraction or exponent become exact Fractions. Duplicate
    object keys keep the last value. The text is capped at
    MAX_ITEMS characters, nesting at MAX_JSON_DEPTH levels, the
    digit count of any number's mantissa at MAX_JSON_DIGITS, and
    any exponent's magnitude at MAX_JSON_EXPONENT; anything
    outside the JSON grammar refuses."""
    fail = make_fail("json_parse_value")
    check_str(fail, text, "text")
    if len(text) > MAX_ITEMS:
        fail("too_long:text")
    n = len(text)
    pos = [0]

    def err():
        fail("bad_json:text")

    def peek():
        return text[pos[0]] if pos[0] < n else ""

    def skip_ws():
        while pos[0] < n and text[pos[0]] in " \t\n\r":
            pos[0] += 1

    def parse_string():
        out = []
        pos[0] += 1
        while True:
            if pos[0] >= n:
                err()
            ch = text[pos[0]]
            if ch == '"':
                pos[0] += 1
                return "".join(out)
            if ch == "\\":
                pos[0] += 1
                if pos[0] >= n:
                    err()
                esc = text[pos[0]]
                if esc in _JSON_ESCAPES:
                    out.append(_JSON_ESCAPES[esc])
                    pos[0] += 1
                elif esc == "u":
                    digits = text[pos[0] + 1:pos[0] + 5]
                    if len(digits) != 4 or any(
                            c not in "0123456789abcdefABCDEF"
                            for c in digits):
                        err()
                    out.append(chr(int(digits, 16)))
                    pos[0] += 5
                else:
                    err()
            elif ord(ch) < 0x20:
                err()
            else:
                out.append(ch)
                pos[0] += 1

    def parse_number():
        start = pos[0]
        if peek() == "-":
            pos[0] += 1
        if peek() == "0":
            pos[0] += 1
        elif peek().isdigit() and peek() != "0":
            while peek().isdigit():
                pos[0] += 1
        else:
            err()
        frac = False
        if peek() == ".":
            frac = True
            pos[0] += 1
            if not peek().isdigit():
                err()
            while peek().isdigit():
                pos[0] += 1
        if peek() and peek() in "eE":
            frac = True
            pos[0] += 1
            if peek() and peek() in "+-":
                pos[0] += 1
            if not peek().isdigit():
                err()
            while peek().isdigit():
                pos[0] += 1
        token = text[start:pos[0]]
        body = token.lower()
        if "e" in body:
            mant, exp_digits = body.split("e")
        else:
            mant, exp_digits = body, None
        if sum(c.isdigit() for c in mant) > MAX_JSON_DIGITS:
            fail("too_many_digits:number")
        if exp_digits is not None:
            digits_part = exp_digits.lstrip("+-")
            if len(digits_part) > 16:
                fail("out_of_range:exponent")
            sig = digits_part.lstrip("0") or "0"
            if len(sig) > len(str(MAX_JSON_EXPONENT)):
                fail("out_of_range:exponent")
            if abs(int(exp_digits)) > MAX_JSON_EXPONENT:
                fail("out_of_range:exponent")
        if not frac:
            return int(token)
        if "e" in token or "E" in token:
            mant, exp = token.lower().split("e")
            value = Fraction(mant) if "." in mant else Fraction(
                int(mant))
            return value * Fraction(10) ** int(exp)
        return Fraction(token)

    def parse(depth):
        if depth > MAX_JSON_DEPTH:
            fail("too_deep:text")
        skip_ws()
        ch = peek()
        if ch == "{":
            pos[0] += 1
            out = {}
            skip_ws()
            if peek() == "}":
                pos[0] += 1
                return out
            while True:
                skip_ws()
                if peek() != '"':
                    err()
                key = parse_string()
                skip_ws()
                if peek() != ":":
                    err()
                pos[0] += 1
                out[key] = parse(depth + 1)
                skip_ws()
                if peek() == ",":
                    pos[0] += 1
                    continue
                if peek() == "}":
                    pos[0] += 1
                    return out
                err()
        if ch == "[":
            pos[0] += 1
            out = []
            skip_ws()
            if peek() == "]":
                pos[0] += 1
                return out
            while True:
                out.append(parse(depth + 1))
                skip_ws()
                if peek() == ",":
                    pos[0] += 1
                    continue
                if peek() == "]":
                    pos[0] += 1
                    return out
                err()
        if ch == '"':
            return parse_string()
        if ch == "-" or ch.isdigit():
            return parse_number()
        if text.startswith("true", pos[0]):
            pos[0] += 4
            return True
        if text.startswith("false", pos[0]):
            pos[0] += 5
            return False
        if text.startswith("null", pos[0]):
            pos[0] += 4
            return None
        err()

    value = parse(1)
    skip_ws()
    if pos[0] != n:
        err()
    return value


def ini_parse_sections(text):
    """INI text parsed to a nested dict of sections.

    Blank lines and lines starting with ; or # are ignored.
    [name] starts a section (names are stripped); anything
    before the first section header belongs to the empty-section
    key "". key=value lines store the stripped key and value;
    keys must be non-empty, and a line that is neither a comment,
    header, nor assignment refuses. Later assignments to the
    same key overwrite earlier ones, and repeated section headers
    merge. Returns {section: {key: value}} in first-use order.
    The text is capped at MAX_ITEMS characters and lines."""
    fail = make_fail("ini_parse_sections")
    check_str(fail, text, "text")
    if len(text) > MAX_ITEMS:
        fail("too_long:text")
    lines = text.split("\n")
    if len(lines) > MAX_ITEMS:
        fail("too_many:text")
    out = {}
    section = ""
    out[section] = {}
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line or line[0] in ";#":
            continue
        if line.startswith("["):
            if not line.endswith("]") or len(line) < 3:
                fail("bad_line:text[%d]" % i)
            section = line[1:-1].strip()
            if not section:
                fail("bad_line:text[%d]" % i)
            if section not in out:
                out[section] = {}
            continue
        if "=" not in line:
            fail("bad_line:text[%d]" % i)
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            fail("bad_line:text[%d]" % i)
        out[section][key] = value.strip()
    if not out[""]:
        del out[""]
    return out


def rational_reconstruction(x, m):
    """Recover a rational p/q congruent to x modulo m.

    Wang's bound: when some p'/q' satisfies p' === x * q' (mod m)
    with |p'| <= floor of sqrt(m / 2) and 0 < q' <= floor of
    sqrt(m / 2) and m >= 3, that rational is unique, and this
    returns it in lowest terms as [p, q] with q > 0 (the bound
    and congruence hold for a representative that may be a
    multiple of the lowest terms). At m = 2 the bound still
    admits both 1/1 and -1/1 when x = 1; the deterministic
    extended-Euclid pass then returns [1, 1]. Uses the extended
    Euclidean algorithm and refuses no_rational when no such
    rational exists (m = 1 admits none). m is a positive int at
    most MAX_VAL and x is reduced to [0, m) after validation."""
    fail = make_fail("rational_reconstruction")
    check_int(fail, x, "x")
    check_int(fail, m, "m")
    if m < 1 or m > MAX_VAL:
        fail("out_of_range:m")
    import math
    bound = math.isqrt(m // 2)
    if bound < 1:
        fail("no_rational:x")
    x %= m
    a, b = m, x
    old_t, t = 0, 1
    while b != 0 and b > bound:
        q = a // b
        a, b = b, a - q * b
        old_t, t = t, old_t - q * t
    q_den = t
    p_num = b
    if q_den < 0:
        q_den, p_num = -q_den, -p_num
    if q_den == 0 or q_den > bound:
        fail("no_rational:x")
    if (p_num - x * q_den) % m != 0:
        fail("no_rational:x")
    import math as _math
    g = _math.gcd(p_num, q_den)
    return [p_num // g, q_den // g]


def suffix_automaton_states(text):
    """Number of states in the suffix automaton of the text.

    Builds the automaton with the standard online algorithm and
    returns its state count (between len(text) + 1 and
    2 * len(text) - 1 for a non-empty text). The text is capped
    at MAX_SAM_CHARS characters."""
    fail = make_fail("suffix_automaton_states")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > MAX_SAM_CHARS:
        fail("too_long:text")
    link = [-1]
    length = [0]
    trans = [{}]
    last = 0
    for ch in text:
        cur = len(length)
        length.append(length[last] + 1)
        link.append(0)
        trans.append({})
        p = last
        while p != -1 and ch not in trans[p]:
            trans[p][ch] = cur
            p = link[p]
        if p == -1:
            link[cur] = 0
        else:
            q = trans[p][ch]
            if length[p] + 1 == length[q]:
                link[cur] = q
            else:
                clone = len(length)
                length.append(length[p] + 1)
                link.append(link[q])
                trans.append(dict(trans[q]))
                while p != -1 and trans[p].get(ch) == q:
                    trans[p][ch] = clone
                    p = link[p]
                link[q] = link[cur] = clone
        last = cur
    return len(length)


def convex_hull_trick_min(lines, queries):
    """Minimum of m * x + b over the given lines at each query.

    lines holds [m, b] int pairs and queries holds int x values,
    both capped at MAX_CHT_ITEMS entries and MAX_VAL in
    magnitude. Returns one minimum per query, in query order,
    from the lower envelope of the lines (slopes sorted,
    envelope intersections kept as exact Fractions, one binary
    search per query), an estimated O((n + q) log n) work."""
    fail = make_fail("convex_hull_trick_min")
    check_items(fail, lines, "lines")
    if not lines:
        fail("empty:lines")
    if len(lines) > MAX_CHT_ITEMS:
        fail("too_many:lines")
    check_items(fail, queries, "queries")
    if len(queries) > MAX_CHT_ITEMS:
        fail("too_many:queries")
    for i, ln in enumerate(lines):
        check_items(fail, ln, "lines[%d]" % i)
        if len(ln) != 2:
            fail("bad_shape:lines[%d]" % i)
        for j, v in enumerate(ln):
            check_int(fail, v, "lines[%d][%d]" % (i, j))
            if v < -MAX_VAL or v > MAX_VAL:
                fail("out_of_range:lines[%d][%d]" % (i, j))
    for i, v in enumerate(queries):
        check_int(fail, v, "queries[%d]" % i)
        if v < -MAX_VAL or v > MAX_VAL:
            fail("out_of_range:queries[%d]" % i)
    ordered = sorted(((m_, b_) for m_, b_ in lines),
                     key=lambda p: (-p[0], p[1]))
    env = []
    cuts = []
    for m_, b_ in ordered:
        if env and env[-1][0] == m_:
            if b_ >= env[-1][1]:
                continue
            env.pop()
            cuts.pop()
        while env:
            m0, b0 = env[-1]
            cut = Fraction(b0 - b_, m_ - m0)
            if not cuts or cut > cuts[-1]:
                env.append((m_, b_))
                cuts.append(cut)
                break
            env.pop()
            cuts.pop()
        else:
            env.append((m_, b_))
            cuts.append(Fraction(-10**30))
    import bisect
    out = []
    for x in queries:
        idx = bisect.bisect_right(cuts, Fraction(x)) - 1
        if idx < 0:
            idx = 0
        m_, b_ = env[idx]
        out.append(m_ * x + b_)
    return out


def go_capture_count(board, move):
    """Stones captured by placing a stone on a Go board.

    board is a square grid (side 1..MAX_GO_BOARD) of ints: 0
    empty, 1 black, 2 white. move is [row, col, color] placing a
    black (1) or white (2) stone on an empty point. The move
    removes every opponent group left without liberties and
    returns the number of stones removed; a move that captures
    nothing while having no liberties of its own (suicide)
    refuses, as does an occupied point. The board is not
    modified."""
    fail = make_fail("go_capture_count")
    check_items(fail, board, "board")
    if not board:
        fail("empty:board")
    if len(board) > MAX_GO_BOARD:
        fail("too_many:board")
    side = len(board)
    for i, row in enumerate(board):
        check_items(fail, row, "board[%d]" % i)
        if len(row) != side:
            fail("ragged:board")
        for j, v in enumerate(row):
            check_int(fail, v, "board[%d][%d]" % (i, j))
            if v not in (0, 1, 2):
                fail("bad_value:board[%d][%d]" % (i, j))
    check_items(fail, move, "move")
    if len(move) != 3:
        fail("bad_shape:move")
    for j, v in enumerate(move):
        check_int(fail, v, "move[%d]" % j)
    r, c, color = move
    if not (0 <= r < side) or not (0 <= c < side):
        fail("out_of_range:move")
    if color not in (1, 2):
        fail("bad_value:move[2]")
    if board[r][c] != 0:
        fail("occupied:move")
    grid = [list(row) for row in board]
    grid[r][c] = color
    foe = 3 - color

    def group_and_liberties(sr, sc):
        seen = {(sr, sc)}
        stack = [(sr, sc)]
        libs = set()
        col = grid[sr][sc]
        while stack:
            x, y = stack.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < side and 0 <= ny < side):
                    continue
                if grid[nx][ny] == 0:
                    libs.add((nx, ny))
                elif grid[nx][ny] == col and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    stack.append((nx, ny))
        return seen, libs

    captured = 0
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = r + dx, c + dy
        if (0 <= nx < side and 0 <= ny < side
                and grid[nx][ny] == foe):
            stones, libs = group_and_liberties(nx, ny)
            if not libs:
                captured += len(stones)
                for x, y in stones:
                    grid[x][y] = 0
    if captured == 0:
        _, libs = group_and_liberties(r, c)
        if not libs:
            fail("suicide:move")
    return captured


def stable_roommates_match(prefs):
    """Stable roommates matching via Irving's two-phase algorithm.

    prefs has n rows (n even, n <= MAX_ITEMS) where row i ranks
    every other person exactly once, most preferred first. Phase
    one runs rounds of proposals; phase two eliminates
    all-or-nothing cycles. Returns the stable pairing as sorted
    [a, b] rows sorted by first element. Refuses odd_pool for an
    odd pool, bad_pref for out-of-range, self, repeated, or
    missing entries, and no_stable when the instance admits no
    stable matching. Deterministic; an estimated O(n^2) work."""
    fail = make_fail("stable_roommates_match")
    check_items(fail, prefs, "prefs")
    n = len(prefs)
    if n == 0:
        return []
    if n % 2 == 1:
        fail("odd_pool:prefs")
    ranks = []
    for ri in range(n):
        row = prefs[ri]
        check_items(fail, row, "prefs[%d]" % ri)
        seen = set()
        rank = {}
        for v in row:
            check_int(fail, v, "pref")
            if v < 0 or v >= n or v == ri:
                fail("bad_pref:prefs")
            if v in seen:
                fail("duplicate_pref:prefs")
            seen.add(v)
            rank[v] = len(rank)
        if len(seen) != n - 1:
            fail("bad_pref:prefs")
        ranks.append(rank)
    hold = [None] * n
    nxt = [0] * n
    for start in range(n):
        p = start
        while True:
            if nxt[p] >= len(prefs[p]):
                fail("no_stable:prefs")
            q = prefs[p][nxt[p]]
            nxt[p] += 1
            cur = hold[q]
            if cur is None or ranks[q][p] < ranks[q][cur]:
                hold[q] = p
                if cur is None:
                    break
                p = cur
    if any(h is None for h in hold):
        fail("no_stable:prefs")
    lists = []
    for i in range(n):
        h = hold[i]
        lst = [q for q in prefs[i] if ranks[i][q] <= ranks[i][h]]
        lst = [q for q in lst if ranks[q][i] <= ranks[q][hold[q]]]
        if not lst:
            fail("no_stable:prefs")
        lists.append(lst)

    def drop(a, b):
        if a in lists[b]:
            lists[b].remove(a)
        if b in lists[a]:
            lists[a].remove(b)
        if not lists[a] or not lists[b]:
            fail("no_stable:prefs")

    while any(len(lst) > 1 for lst in lists):
        p0 = next(i for i in range(n) if len(lists[i]) > 1)
        trail = [p0]
        while True:
            p = trail[-1]
            if len(lists[p]) < 2:
                fail("no_stable:prefs")
            q = lists[p][1]
            r = lists[q][-1]
            if r in trail:
                cycle = trail[trail.index(r):]
                break
            trail.append(r)
        ops = []
        for i in range(len(cycle)):
            a = cycle[i]
            y = lists[a][1]
            ops.extend(
                (z, y) for z in lists[y][lists[y].index(a) + 1:])
        for b, q in ops:
            drop(b, q)
        for i in range(n):
            if not lists[i]:
                fail("no_stable:prefs")
    seen = set()
    out = []
    for i in range(n):
        j = lists[i][0]
        key = (min(i, j), max(i, j))
        if key not in seen:
            seen.add(key)
            out.append([key[0], key[1]])
    if len(out) != n // 2:
        fail("no_stable:prefs")
    return sorted(out)
