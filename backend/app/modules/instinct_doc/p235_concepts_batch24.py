"""P235 concepts batch 24 (concepts 231-240, exact geometry/misc) - ten new
small deterministic concepts. 231-240 of the doc's 1000 (anchor P235|L184).
Exact Fraction/int arithmetic; inputs bounded; oracles pinned in tests.
"""
from __future__ import annotations

from fractions import Fraction

from .p235_concepts_batch1 import MAX_ITEMS, check_int, check_items, make_fail

MAX_COORD = 10**9
MAX_COEFF = 10**6
MAX_DEGREE = 100


def _check_point(fail, p, name):
    if type(p) is not tuple or len(p) != 2:
        fail("bad_type:" + name)
    for i, v in enumerate(p):
        check_int(fail, v, "%s[%d]" % (name, i))
        if abs(v) > MAX_COORD:
            fail("bad_value:%s[%d]" % (name, i))
    return p


def slope_exact(p1, p2):
    fail = make_fail("slope_exact")
    _check_point(fail, p1, "p1")
    _check_point(fail, p2, "p2")
    if p1 == p2:
        fail("same:points")
    if p1[0] == p2[0]:
        fail("vertical:points")
    return Fraction(p2[1] - p1[1], p2[0] - p1[0])


def reflect_point_exact(point, center):
    """Exact reflection of a point through a center point: 2*center - point
    per coordinate (the half-turn image)."""
    fail = make_fail("reflect_point_exact")
    _check_point(fail, point, "point")
    _check_point(fail, center, "center")
    return (2 * center[0] - point[0], 2 * center[1] - point[1])


def collinear_check(p1, p2, p3):
    fail = make_fail("collinear_check")
    _check_point(fail, p1, "p1")
    _check_point(fail, p2, "p2")
    _check_point(fail, p3, "p3")
    cross = ((p2[0] - p1[0]) * (p3[1] - p1[1])
             - (p2[1] - p1[1]) * (p3[0] - p1[0]))
    return cross == 0


def circle_area_pi_coefficient(radius):
    """Exact circle area as the coefficient of pi (pi is irrational)."""
    fail = make_fail("circle_area_pi_coefficient")
    check_int(fail, radius, "radius")
    if radius < 0 or radius > MAX_COORD:
        fail("bad_value:radius")
    return radius * radius


def line_intersection_exact(line1, line2):
    """Intersection of a1*x + b1*y = c1 and a2*x + b2*y = c2."""
    fail = make_fail("line_intersection_exact")
    for name, line in (("line1", line1), ("line2", line2)):
        if type(line) is not tuple or len(line) != 3:
            fail("bad_type:" + name)
        for i, v in enumerate(line):
            check_int(fail, v, "%s[%d]" % (name, i))
            if abs(v) > MAX_COORD:
                fail("bad_value:%s[%d]" % (name, i))
    a1, b1, c1 = line1
    a2, b2, c2 = line2
    if a1 == 0 and b1 == 0:
        fail("bad_value:line1")
    if a2 == 0 and b2 == 0:
        fail("bad_value:line2")
    det = a1 * b2 - a2 * b1
    if det == 0:
        fail("parallel:lines")
    x = Fraction(c1 * b2 - c2 * b1, det)
    y = Fraction(a1 * c2 - a2 * c1, det)
    return (x, y)


def _cross(o, a, b):
    return ((a[0] - o[0]) * (b[1] - o[1])
            - (a[1] - o[1]) * (b[0] - o[0]))


def convex_hull_vertices(points):
    """Monotonic-chain hull, CCW from the lexicographically smallest point;
    collinear boundary points are excluded, duplicates refuse."""
    fail = make_fail("convex_hull_vertices")
    check_items(fail, points, "convex_hull_vertices")
    if not points:
        fail("empty:points")
    seen = set()
    pts = []
    for i, p in enumerate(points):
        if type(p) is not list or len(p) != 2:
            fail("bad_type:points[%d]" % i)
        for j, v in enumerate(p):
            check_int(fail, v, "points[%d][%d]" % (i, j))
            if abs(v) > MAX_COORD:
                fail("bad_value:points[%d][%d]" % (i, j))
        key = (p[0], p[1])
        if key in seen:
            fail("duplicate:points")
        seen.add(key)
        pts.append(key)
    pts.sort()
    if len(pts) <= 2:
        return [list(p) for p in pts]
    lower = []
    for p in pts:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    return [list(p) for p in hull]


def ohms_law_voltage_exact(current, resistance):
    fail = make_fail("ohms_law_voltage_exact")
    for name, v in (("current", current), ("resistance", resistance)):
        if type(v) is not int and type(v) is not Fraction:
            fail("bad_type:" + name)
        if v < 0 or v > MAX_COORD:
            fail("bad_value:" + name)
    return Fraction(current) * Fraction(resistance)


def determinant_2x2_exact(row1, row2):
    fail = make_fail("determinant_2x2_exact")
    for name, row in (("row1", row1), ("row2", row2)):
        if type(row) is not tuple or len(row) != 2:
            fail("bad_type:" + name)
        for i, v in enumerate(row):
            check_int(fail, v, "%s[%d]" % (name, i))
            if abs(v) > MAX_COORD:
                fail("bad_value:%s[%d]" % (name, i))
    return row1[0] * row2[1] - row1[1] * row2[0]


def _check_digit_string(fail, s, name):
    if type(s) is not str:
        fail("bad_type:" + name)
    if not s or not s.isascii() or not s.isdigit():
        fail("bad_value:" + name)
    if len(s) > MAX_ITEMS:
        fail("too_many:" + name)
    if len(s) > 1 and s[0] == "0":
        fail("bad_value:" + name)
    return s


def add_digit_strings(a, b):
    """Manual addition of two non-negative integers given as digit strings;
    no leading zeros except the literal "0"."""
    fail = make_fail("add_digit_strings")
    a = _check_digit_string(fail, a, "a")
    b = _check_digit_string(fail, b, "b")
    ia, ib = len(a) - 1, len(b) - 1
    carry = 0
    out = []
    while ia >= 0 or ib >= 0 or carry:
        total = carry
        if ia >= 0:
            total += ord(a[ia]) - 48
            ia -= 1
        if ib >= 0:
            total += ord(b[ib]) - 48
            ib -= 1
        out.append(chr(48 + total % 10))
        carry = total // 10
    return "".join(reversed(out))


def polynomial_eval_exact(coeffs, x):
    """coeffs[0] + coeffs[1]*x + ... evaluated by Horner's rule."""
    fail = make_fail("polynomial_eval_exact")
    check_items(fail, coeffs, "polynomial_eval_exact")
    if not coeffs:
        fail("empty:coeffs")
    if len(coeffs) > MAX_DEGREE + 1:
        fail("too_many:coeffs")
    for i, v in enumerate(coeffs):
        check_int(fail, v, "coeffs[%d]" % i)
        if abs(v) > MAX_COEFF:
            fail("bad_value:coeffs[%d]" % i)
    check_int(fail, x, "x")
    if abs(x) > MAX_COEFF:
        fail("bad_value:x")
    result = 0
    for c in reversed(coeffs):
        result = result * x + c
    return result
