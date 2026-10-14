"""P235 concepts batch 29 (concepts 281-290, combinatorics/graphs/metrics) -
ten new small deterministic concepts. 281-290 of the doc's 1000 (anchor
P235|L184). Exact arithmetic throughout; inputs bounded; refusal codes
P235:<name>:<code>.
"""
from __future__ import annotations

from fractions import Fraction

from .p235_concepts_batch1 import MAX_ITEMS, check_int, check_str, make_fail

MAX_GROUPS = 100
MAX_MULTI_SUM = 10_000
MAX_VALUES = 256
MAX_TARGET = 10_000
MAX_MODULI_PRODUCT = 10**12
MAX_TEXT = 1_000
MAX_VERTICES = 256
MAX_EDGES = 4_096
MAX_COORD = 10**6
MAX_WEIGHT = 10**6
MAX_PEOPLE = 10_000


def _choose(n, k):
    if k < 0 or k > n:
        return 0
    k = min(k, n - k)
    out = 1
    for i in range(k):
        out = out * (n - i) // (i + 1)
    return out


def multinomial_coefficient(groups):
    """n! / (k1! ... km!) for group sizes ki summing to n; the count of
    ways to split n distinct items into m labeled groups of those sizes."""
    fail = make_fail("multinomial_coefficient")
    if type(groups) is not list:
        fail("bad_type:groups")
    if not groups:
        fail("empty:groups")
    if len(groups) > MAX_GROUPS:
        fail("too_many:groups")
    total = 0
    for i, g in enumerate(groups):
        check_int(fail, g, "groups[%d]" % i)
        if g < 0:
            fail("bad_value:groups[%d]" % i)
        total += g
    if total > MAX_MULTI_SUM:
        fail("too_big:groups")
    result = 1
    remaining = total
    for g in groups:
        result *= _choose(remaining, g)
        remaining -= g
    return result


def subsets_with_sum_count(values, target):
    """Number of index-subsets of the non-negative int list whose values
    sum to target; repeated values count as distinct positions."""
    fail = make_fail("subsets_with_sum_count")
    if type(values) is not list:
        fail("bad_type:values")
    if len(values) > MAX_VALUES:
        fail("too_many:values")
    for i, v in enumerate(values):
        check_int(fail, v, "values[%d]" % i)
        if v < 0 or v > MAX_TARGET:
            fail("bad_value:values[%d]" % i)
    check_int(fail, target, "target")
    if target < 0 or target > MAX_TARGET:
        fail("bad_value:target")
    ways = [0] * (target + 1)
    ways[0] = 1
    for v in values:
        for t in range(target, v - 1, -1):
            ways[t] += ways[t - v]
    return ways[target]


def chinese_remainder_pair(a1, m1, a2, m2):
    """The unique x in [0, m1*m2) with x == a1 (mod m1) and x == a2
    (mod m2) for coprime moduli; non-coprime refuses."""
    fail = make_fail("chinese_remainder_pair")
    check_int(fail, a1, "a1")
    check_int(fail, m1, "m1")
    check_int(fail, a2, "a2")
    check_int(fail, m2, "m2")
    if m1 < 2:
        fail("bad_value:m1")
    if m2 < 2:
        fail("bad_value:m2")
    if not 0 <= a1 < m1:
        fail("bad_value:a1")
    if not 0 <= a2 < m2:
        fail("bad_value:a2")
    if m1 * m2 > MAX_MODULI_PRODUCT:
        fail("too_big:moduli")
    g, x, _y = _extended_gcd(m1, m2)
    if g != 1:
        fail("bad_value:moduli")
    step = (a2 - a1) * x % m2
    return (a1 + m1 * step) % (m1 * m2)


def _extended_gcd(a, b):
    old_r, r = a, b
    old_s, s = 1, 0
    old_t, t = 0, 1
    while r:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_s, s = s, old_s - q * s
        old_t, t = t, old_t - q * t
    return old_r, old_s, old_t


def damerau_osa_distance(a, b):
    """Optimal string alignment distance: insertions, deletions,
    substitutions, and adjacent transpositions each cost 1."""
    fail = make_fail("damerau_osa_distance")
    check_str(fail, a, "a")
    check_str(fail, b, "b")
    if len(a) > MAX_TEXT:
        fail("too_many:a")
    if len(b) > MAX_TEXT:
        fail("too_many:b")
    la, lb = len(a), len(b)
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            best = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                       d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] \
                    and a[i - 2] == b[j - 1]:
                best = min(best, d[i - 2][j - 2] + 1)
            d[i][j] = best
    return d[la][lb]


def substring_first_index(text, sub):
    """First index of sub in text, or -1 when absent; empty sub refuses."""
    fail = make_fail("substring_first_index")
    check_str(fail, text, "text")
    check_str(fail, sub, "sub")
    if len(text) > MAX_ITEMS:
        fail("too_many:text")
    if len(sub) > MAX_TEXT:
        fail("too_many:sub")
    if not sub:
        fail("bad_value:sub")
    return text.find(sub)


def easter_date_western(year):
    """Gregorian Easter Sunday for 1583..9999 as (year, month, day),
    by the anonymous Gregorian computus."""
    fail = make_fail("easter_date_western")
    check_int(fail, year, "year")
    if year < 1583 or year > 9_999:
        fail("bad_value:year")
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    mm = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * mm + 114) // 31
    day = ((h + l - 7 * mm + 114) % 31) + 1
    return (year, month, day)


def point_in_polygon_raycast(points, point):
    """Whether an int point lies inside a simple polygon (vertices in
    order) by exact ray casting; boundary counts as inside."""
    fail = make_fail("point_in_polygon_raycast")
    if type(points) is not list or len(points) < 3:
        fail("bad_value:points")
    if len(points) > MAX_VERTICES:
        fail("too_many:points")
    for i, p in enumerate(points):
        if type(p) not in (list, tuple) or len(p) != 2:
            fail("bad_type:points[%d]" % i)
        for j, v in enumerate(p):
            check_int(fail, v, "points[%d][%d]" % (i, j))
            if abs(v) > MAX_COORD:
                fail("bad_value:points[%d][%d]" % (i, j))
    if type(point) is not list or len(point) != 2:
        fail("bad_type:point")
    check_int(fail, point[0], "point[0]")
    check_int(fail, point[1], "point[1]")
    if abs(point[0]) > MAX_COORD or abs(point[1]) > MAX_COORD:
        fail("bad_value:point")
    px, py = point
    inside = False
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        cross = (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)
        if cross == 0 and min(x1, x2) <= px <= max(x1, x2) \
                and min(y1, y2) <= py <= max(y1, y2):
            return True
        if (y1 > py) != (y2 > py):
            lhs = (x2 - x1) * (py - y1)
            rhs = (px - x1) * (y2 - y1)
            hit = lhs > rhs if y2 > y1 else lhs < rhs
            if hit:
                inside = not inside
    return inside


def jaccard_index_exact(a, b):
    """Exact |A intersect B| / |A union B| over the deduplicated
    elements of two lists of ints and strings."""
    fail = make_fail("jaccard_index_exact")
    for name, values in (("a", a), ("b", b)):
        if type(values) is not list:
            fail("bad_type:" + name)
        if len(values) > MAX_ITEMS:
            fail("too_many:" + name)
        for i, v in enumerate(values):
            if type(v) not in (str, int):
                fail("bad_type:%s[%d]" % (name, i))
    union = set(a) | set(b)
    if not union:
        fail("bad_value:empty")
    return Fraction(len(set(a) & set(b)), len(union))


def min_spanning_tree_weight(n, edges):
    """Total weight of a minimum spanning tree of the undirected
    weighted graph on vertices 0..n-1 (Kruskal); a disconnected graph
    refuses."""
    fail = make_fail("min_spanning_tree_weight")
    check_int(fail, n, "n")
    if n < 1:
        fail("bad_value:n")
    if n > MAX_VERTICES:
        fail("too_many:n")
    if type(edges) is not list:
        fail("bad_type:edges")
    if len(edges) > MAX_EDGES:
        fail("too_many:edges")
    checked = []
    for i, e in enumerate(edges):
        if type(e) not in (list, tuple) or len(e) != 3:
            fail("bad_type:edges[%d]" % i)
        u, v, w = e
        check_int(fail, u, "edges[%d][0]" % i)
        check_int(fail, v, "edges[%d][1]" % i)
        check_int(fail, w, "edges[%d][2]" % i)
        if not 0 <= u < n or not 0 <= v < n:
            fail("bad_value:edges[%d]" % i)
        if abs(w) > MAX_WEIGHT:
            fail("bad_value:edges[%d]" % i)
        checked.append((w, u, v))
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    total = 0
    merged = 0
    for w, u, v in sorted(checked):
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
            total += w
            merged += 1
    if merged != n - 1:
        fail("bad_value:disconnected")
    return total


def birthday_collision_exact(n):
    """Exact probability that at least two of n people share a birthday
    (365 equally likely days, no February 29)."""
    fail = make_fail("birthday_collision_exact")
    check_int(fail, n, "n")
    if n < 0 or n > MAX_PEOPLE:
        fail("bad_value:n")
    if n <= 1:
        return Fraction(0)
    if n > 365:
        return Fraction(1)
    no_collision = Fraction(1)
    for i in range(n):
        no_collision *= Fraction(365 - i, 365)
    return 1 - no_collision
