"""P235 concepts batch 94: ten concepts.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
Strings and lists are capped at MAX_ITEMS entries; tighter caps
(MAX_JUG_SIDE, MAX_PAGERANK_ROUNDS, MAX_CELLS,
MAX_FORMULA_LEN, MAX_NAME_LEN, MAX_VALUE_BITS,
MAX_PAGERANK_EDGES, MAX_PAGERANK_WORK, MAX_BERLEKAMP_LEN,
MAX_BERLEKAMP_PRIME, MAX_DRAGON_N) are stated in the docstrings of the functions that
carry them. Every function validates its whole input first: type,
range, and cap checks all run during the validation phase, and the
computation phase starts only after validation succeeds. Exact
arithmetic uses ints and Fractions only.
"""

from collections import deque
from fractions import Fraction
from math import asin, cos, radians, sin, sqrt

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_JUG_SIDE = 1_000
MAX_PAGERANK_ROUNDS = 10_000
MAX_PAGERANK_EDGES = 100_000
MAX_PAGERANK_WORK = 2_000_000
MAX_CELLS = 1_000
MAX_FORMULA_LEN = 200
MAX_NAME_LEN = 10
MAX_VALUE_BITS = 4_096
MAX_BERLEKAMP_LEN = 1_000
MAX_BERLEKAMP_PRIME = 1_009
MAX_DRAGON_N = 10**18
EARTH_RADIUS_KM = 6371.0088


def robot_bounded_circle(instructions):
    """Whether a robot stuck looping the instructions stays bounded.

    The robot starts at the origin facing north. 'G' moves one unit,
    'L' and 'R' turn in place. The instruction string repeats
    forever; the orbit is bounded exactly when one cycle returns the
    robot to the origin or leaves it facing a direction other than
    north (so after four cycles it is back home). The string is
    capped at MAX_ITEMS characters."""
    fail = make_fail("robot_bounded_circle")
    check_str(fail, instructions, "instructions")
    if not instructions:
        fail("empty:instructions")
    if len(instructions) > MAX_ITEMS:
        fail("too_long:instructions")
    for i, ch in enumerate(instructions):
        if ch not in "GLR":
            fail("bad_char:instructions[%d]" % i)
    x = y = 0
    dx, dy = 0, 1
    for ch in instructions:
        if ch == "G":
            x += dx
            y += dy
        elif ch == "L":
            dx, dy = -dy, dx
        else:
            dx, dy = dy, -dx
    return (x, y) == (0, 0) or (dx, dy) != (0, 1)


def water_jug_min_pours(cap_a, cap_b, target):
    """Fewest jug operations to measure target, or -1 when impossible.

    Two jugs hold cap_a and cap_b; allowed operations are fill a jug,
    empty a jug, and pour one into the other until it is full or the
    source is empty. Breadth-first search over (a, b) states returns
    the fewest operations to reach any state holding target in either
    jug, or -1. Jug sizes are capped at MAX_JUG_SIDE, so the state
    space stays under about one million states."""
    fail = make_fail("water_jug_min_pours")
    check_int(fail, cap_a, "cap_a")
    check_int(fail, cap_b, "cap_b")
    check_int(fail, target, "target")
    for name, v in (("cap_a", cap_a), ("cap_b", cap_b)):
        if v < 1 or v > MAX_JUG_SIDE:
            fail("out_of_range:%s" % name)
    if target < 0 or target > max(cap_a, cap_b):
        fail("out_of_range:target")

    def gcd(x, y):
        while y:
            x, y = y, x % y
        return x

    if target and target % gcd(cap_a, cap_b):
        return -1
    seen = {(0, 0)}
    frontier = [(0, 0)]
    steps = 0
    while frontier:
        nxt = []
        for a, b in frontier:
            if a == target or b == target:
                return steps
            moves = ((cap_a, b), (a, cap_b), (0, b), (a, 0),
                     (a - min(a, cap_b - b), b + min(a, cap_b - b)),
                     (a + min(b, cap_a - a), b - min(b, cap_a - a)))
            for s in moves:
                if s not in seen:
                    seen.add(s)
                    nxt.append(s)
        frontier = nxt
        steps += 1
    return -1


def car_pooling_feasible(trips, capacity):
    """Whether the vehicle never exceeds capacity across the trips.

    Each trip is [passengers, start, end]; passengers board at start
    and leave at end. The run sums the deltas at every endpoint in
    order, an estimated O(n log n) work. The list is capped at
    MAX_ITEMS trips and each value at 10**9."""
    fail = make_fail("car_pooling_feasible")
    check_items(fail, trips, "trips")
    if not trips:
        fail("empty:trips")
    if len(trips) > MAX_ITEMS:
        fail("too_many:trips")
    check_int(fail, capacity, "capacity")
    if capacity < 1 or capacity > 10**9:
        fail("out_of_range:capacity")
    events = []
    for i, trip in enumerate(trips):
        if (type(trip) is not list or len(trip) != 3):
            fail("bad_trip:trips[%d]" % i)
        n, frm, to = trip
        for j, v in enumerate((n, frm, to)):
            check_int(fail, v, "trips[%d][%d]" % (i, j))
            if v < 0 or v > 10**9:
                fail("out_of_range:trips[%d][%d]" % (i, j))
        if n == 0 or frm >= to:
            fail("bad_trip:trips[%d]" % i)
        events.append((frm, n))
        events.append((to, -n))
    events.sort()
    load = 0
    for _, delta in events:
        load += delta
        if load > capacity:
            return False
    return True


def sparkline_render(values):
    """Unicode block sparkline of the int series.

    Each value maps to one of the eight glyphs ▁▂▃▄▅▆▇█ by linear
    scaling between the series minimum and maximum, rounding half up.
    An empty list renders as the empty string; a constant series
    renders as all ▁. The list is capped at MAX_ITEMS entries and
    each value at 10**12 in magnitude."""
    fail = make_fail("sparkline_render")
    check_items(fail, values, "values")
    if len(values) > MAX_ITEMS:
        fail("too_many:values")
    for i, v in enumerate(values):
        check_int(fail, v, "values[%d]" % i)
        if v < -10**12 or v > 10**12:
            fail("out_of_range:values[%d]" % i)
    if not values:
        return ""
    glyphs = "▁▂▃▄▅▆▇█"
    lo = min(values)
    span = max(values) - lo
    if span == 0:
        return glyphs[0] * len(values)
    out = []
    for v in values:
        num = (v - lo) * 7
        level = (2 * num + span) // (2 * span)
        out.append(glyphs[level])
    return "".join(out)


def pagerank_iterate(adj, damping, rounds):
    """PageRank scores after the given number of power iterations.

    adj lists, per node, the nodes it links to. Scores start uniform
    at 1/n; each round every node pushes damping * score / outdegree
    along its links, nodes with no links spread damping * score
    evenly, and every node keeps a (1 - damping) / n base. damping
    is a float strictly between 0 and 1. The graph is capped at
    MAX_ITEMS nodes and MAX_PAGERANK_EDGES total links, rounds is
    capped at MAX_PAGERANK_ROUNDS, and the product
    rounds * (nodes + links) is capped at MAX_PAGERANK_WORK, all
    checked after validation and before the first iteration."""
    fail = make_fail("pagerank_iterate")
    check_items(fail, adj, "adj")
    if not adj:
        fail("empty:adj")
    n = len(adj)
    for i, outs in enumerate(adj):
        check_items(fail, outs, "adj[%d]" % i)
        for j, v in enumerate(outs):
            check_int(fail, v, "adj[%d][%d]" % (i, j))
            if v < 0 or v >= n:
                fail("out_of_range:adj[%d][%d]" % (i, j))
    if type(damping) is not float or damping != damping or damping in (
            float("inf"), float("-inf")):
        fail("bad_type:damping")
    if damping <= 0.0 or damping >= 1.0:
        fail("out_of_range:damping")
    check_int(fail, rounds, "rounds")
    if rounds < 1 or rounds > MAX_PAGERANK_ROUNDS:
        fail("out_of_range:rounds")
    edges = 0
    for outs in adj:
        edges += len(outs)
    if edges > MAX_PAGERANK_EDGES:
        fail("too_many:edges")
    if rounds * (n + edges) > MAX_PAGERANK_WORK:
        fail("too_much_work:adj,rounds")
    pr = [1.0 / n] * n
    for _ in range(rounds):
        nxt = [(1.0 - damping) / n] * n
        dangling = 0.0
        for j in range(n):
            if not adj[j]:
                dangling += pr[j]
        share = damping * dangling / n
        for i in range(n):
            nxt[i] += share
        for j in range(n):
            if adj[j]:
                push = damping * pr[j] / len(adj[j])
                for t in adj[j]:
                    nxt[t] += push
        pr = nxt
    return pr


def spreadsheet_eval(cells):
    """Exact values of spreadsheet cells with cross references.

    cells is a list of [name, formula] pairs. Names are one ASCII
    letter A-Z followed by one or more ASCII digits, capped at
    MAX_NAME_LEN characters. Formulas use non-negative integers,
    cell references, the operators + - * /, and parentheses; / is
    exact rational division. Every name and formula is tokenized and
    validated, and the reference graph is checked for unknown
    references and cycles, before any evaluation. Cells are then
    evaluated in dependency order with an explicit queue, so
    dependency chains up to the cell cap cannot exhaust the call
    stack. Intermediate numerators and denominators are capped at
    MAX_VALUE_BITS bits: before each arithmetic step the worst-case
    bit length of the result is checked and too_big is refused
    instead of computing a value that large. Returns
    [name, Fraction] pairs in input order. Caps: MAX_CELLS cells
    and MAX_FORMULA_LEN characters per formula."""
    fail = make_fail("spreadsheet_eval")
    check_items(fail, cells, "cells")
    if not cells:
        fail("empty:cells")
    if len(cells) > MAX_CELLS:
        fail("too_many:cells")
    formulas = {}
    order = []
    for i, pair in enumerate(cells):
        if type(pair) is not list or len(pair) != 2:
            fail("bad_cell:cells[%d]" % i)
        name, expr = pair
        check_str(fail, name, "cells[%d][0]" % i)
        check_str(fail, expr, "cells[%d][1]" % i)
        if len(name) > MAX_NAME_LEN:
            fail("too_long:cells[%d][0]" % i)
        if (len(name) < 2 or not ("A" <= name[0] <= "Z")
                or not all("0" <= ch <= "9" for ch in name[1:])):
            fail("bad_name:cells[%d][0]" % i)
        if name in formulas:
            fail("duplicate:cells[%d][0]" % i)
        if not expr:
            fail("empty:cells[%d][1]" % i)
        if len(expr) > MAX_FORMULA_LEN:
            fail("too_long:cells[%d][1]" % i)
        tokens = []
        k = 0
        while k < len(expr):
            ch = expr[k]
            if "0" <= ch <= "9":
                j = k
                while j < len(expr) and "0" <= expr[j] <= "9":
                    j += 1
                tokens.append(("num", int(expr[k:j])))
                k = j
            elif "A" <= ch <= "Z":
                j = k + 1
                while j < len(expr) and "0" <= expr[j] <= "9":
                    j += 1
                if j == k + 1:
                    fail("bad_token:cells[%d][1]" % i)
                tokens.append(("ref", expr[k:j]))
                k = j
            elif ch in "+-*/()":
                tokens.append(("op", ch))
                k += 1
            else:
                fail("bad_char:cells[%d][1]" % i)
        if not tokens:
            fail("empty:cells[%d][1]" % i)
        formulas[name] = tokens
        order.append(name)
    deps = {}
    dependents = {}
    for i, name in enumerate(order):
        refs = []
        seen = set()
        for tok in formulas[name]:
            if tok[0] == "ref" and tok[1] not in seen:
                seen.add(tok[1])
                refs.append(tok[1])
        for ref in refs:
            if ref not in formulas:
                fail("unknown_ref:%s" % ref)
            dependents.setdefault(ref, []).append(name)
        deps[name] = refs
    ready = [name for name in order if not deps[name]]
    values = {}
    head = 0
    while head < len(ready):
        name = ready[head]
        head += 1
        tokens = formulas[name]
        pos = [0]

        def peek():
            return tokens[pos[0]] if pos[0] < len(tokens) else None

        def take():
            tok = tokens[pos[0]]
            pos[0] += 1
            return tok

        def bits(x):
            return (x.numerator.bit_length(),
                    x.denominator.bit_length())

        def checked_mul(a, b):
            an, ad = bits(a)
            bn, bd = bits(b)
            if an + bn > MAX_VALUE_BITS or ad + bd > MAX_VALUE_BITS:
                fail("too_big:%s" % name)
            return a * b

        def checked_div(a, b):
            if b == 0:
                fail("div_zero:%s" % name)
            an, ad = bits(a)
            bn, bd = bits(b)
            if an + bd > MAX_VALUE_BITS or ad + bn > MAX_VALUE_BITS:
                fail("too_big:%s" % name)
            return a / b

        def checked_add(a, b, sign):
            an, ad = bits(a)
            bn, bd = bits(b)
            if (max(an + bd, bn + ad) + 1 > MAX_VALUE_BITS
                    or ad + bd > MAX_VALUE_BITS):
                fail("too_big:%s" % name)
            return a + b if sign > 0 else a - b

        def parse_expr():
            value = parse_term()
            while peek() == ("op", "+") or peek() == ("op", "-"):
                op = take()[1]
                rhs = parse_term()
                value = checked_add(value, rhs, 1 if op == "+" else -1)
            return value

        def parse_term():
            value = parse_factor()
            while peek() == ("op", "*") or peek() == ("op", "/"):
                op = take()[1]
                rhs = parse_factor()
                value = (checked_mul(value, rhs) if op == "*"
                         else checked_div(value, rhs))
            return value

        def parse_factor():
            tok = peek()
            if tok is None:
                fail("bad_formula:%s" % name)
            if tok == ("op", "-"):
                take()
                return -parse_factor()
            if tok[0] == "num":
                take()
                if tok[1].bit_length() > MAX_VALUE_BITS:
                    fail("too_big:%s" % name)
                return Fraction(tok[1])
            if tok[0] == "ref":
                take()
                return values[tok[1]]
            if tok == ("op", "("):
                take()
                value = parse_expr()
                if peek() != ("op", ")"):
                    fail("bad_formula:%s" % name)
                take()
                return value
            fail("bad_formula:%s" % name)

        result = parse_expr()
        if pos[0] != len(tokens):
            fail("bad_formula:%s" % name)
        values[name] = result
        for dependent in dependents.get(name, []):
            still = [r for r in deps[dependent] if r not in values]
            if not still:
                ready.append(dependent)
    if len(values) != len(order):
        for name in order:
            if name not in values:
                fail("cyclic:%s" % name)
    return [[name, values[name]] for name in order]


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two points, mean-Earth model.

    Inputs are decimal degrees; latitudes in [-90, 90], longitudes in
    [-180, 180]. The radius is the IUGG mean Earth radius
    EARTH_RADIUS_KM. This is a smooth-sphere model: altitude, the
    ellipsoidal flattening, and geodesic (Vincenty/Karney)
    corrections are excluded."""
    fail = make_fail("haversine_km")
    vals = (("lat1", lat1, 90), ("lon1", lon1, 180),
            ("lat2", lat2, 90), ("lon2", lon2, 180))
    nums = []
    for name, v, bound in vals:
        if type(v) not in (int, float) or v != v or v in (
                float("inf"), float("-inf")):
            fail("bad_type:%s" % name)
        if v < -bound or v > bound:
            fail("out_of_range:%s" % name)
        nums.append(float(v))
    p1, l1, p2, l2 = (radians(v) for v in nums)
    dlat = p2 - p1
    dlon = l2 - l1
    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def hangman_state(secret, guesses):
    """Hangman display and remaining lives after the guesses.

    secret is lowercase a-z, length 1..100; guesses is a string of
    guessed letters (a-z), capped at 100 characters. The display
    shows each secret letter that has been guessed and '_' for the
    rest. Lives start at 6; the first occurrence of each guessed
    letter that is absent from the secret costs one life, repeated
    guesses cost nothing, and lives never drop below 0."""
    fail = make_fail("hangman_state")
    check_str(fail, secret, "secret")
    if not secret:
        fail("empty:secret")
    if len(secret) > 100:
        fail("too_long:secret")
    for i, ch in enumerate(secret):
        if ch < "a" or ch > "z":
            fail("bad_char:secret[%d]" % i)
    check_str(fail, guesses, "guesses")
    if len(guesses) > 100:
        fail("too_long:guesses")
    for i, ch in enumerate(guesses):
        if ch < "a" or ch > "z":
            fail("bad_char:guesses[%d]" % i)
    letters = set(secret)
    tried = set()
    lives = 6
    for ch in guesses:
        if ch not in tried:
            tried.add(ch)
            if ch not in letters:
                lives = max(0, lives - 1)
    display = "".join(ch if ch in tried else "_" for ch in secret)
    return [display, lives]


def berlekamp_massey_mod(seq, p):
    """A minimal-length linear recurrence of the sequence over GF(p).

    Runs Berlekamp-Massey in the prime field GF(p) and returns a
    deterministic minimal-length coefficient list c with
    c[0] == 1 such that
    (c[0]*seq[n] + c[1]*seq[n-1] + ... + c[L]*seq[n-L]) % p == 0
    for every n >= L, where L = len(c) - 1. Several minimal
    recurrences can fit the same finite prefix; this returns the one
    the algorithm's update order selects. The all-zero sequence
    yields [1]. p must be prime and is capped at
    MAX_BERLEKAMP_PRIME; seq entries are reduced mod p after range
    validation, and seq is capped at MAX_BERLEKAMP_LEN."""
    fail = make_fail("berlekamp_massey_mod")
    check_items(fail, seq, "seq")
    if not seq:
        fail("empty:seq")
    if len(seq) > MAX_BERLEKAMP_LEN:
        fail("too_many:seq")
    for i, v in enumerate(seq):
        check_int(fail, v, "seq[%d]" % i)
        if v < -10**9 or v > 10**9:
            fail("out_of_range:seq[%d]" % i)
    check_int(fail, p, "p")
    if p < 2 or p > MAX_BERLEKAMP_PRIME:
        fail("out_of_range:p")
    for d in range(2, int(p**0.5) + 1):
        if p % d == 0:
            fail("not_prime:p")
    s = [v % p for v in seq]
    c = [1]
    b = [1]
    length = 0
    m = 1
    bb = 1
    for n in range(len(s)):
        d = s[n]
        for i in range(1, length + 1):
            d = (d + c[i] * s[n - i]) % p
        if d == 0:
            m += 1
        elif 2 * length <= n:
            t = c[:]
            coef = d * pow(bb, p - 2, p) % p
            while len(c) < len(b) + m:
                c.append(0)
            for i in range(len(b)):
                c[i + m] = (c[i + m] - coef * b[i]) % p
            length = n + 1 - length
            b = t
            bb = d
            m = 1
        else:
            coef = d * pow(bb, p - 2, p) % p
            while len(c) < len(b) + m:
                c.append(0)
            for i in range(len(b)):
                c[i + m] = (c[i + m] - coef * b[i]) % p
            m += 1
    return c


def dragon_curve_turn(n):
    """Direction of the nth turn of the dragon curve, 1-indexed.

    Folding a strip repeatedly produces the turn sequence
    L, L, R, L, L, R, R, ... The nth turn (n >= 1) is 1 for left
    and -1 for right, given by whether the bit above the lowest set
    bit of n is clear. n is capped at MAX_DRAGON_N."""
    fail = make_fail("dragon_curve_turn")
    check_int(fail, n, "n")
    if n < 1 or n > MAX_DRAGON_N:
        fail("out_of_range:n")
    low = n & -n
    return -1 if n & (low << 1) else 1
