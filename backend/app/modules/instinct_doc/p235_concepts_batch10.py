"""P235 concepts, batch 10 (number theory/combinatorics, 91-100).
Offline, stdlib only."""
from __future__ import annotations

import datetime
import math
import re

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_GRID_SIDE = 1_000
MAX_EXP = 10_000
MAX_MOD = 10 ** 12
MAX_BASE = 10 ** 12
MAX_FACTOR_N = 10_000_000
_ISO_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")


def polygon_signed_area2(points):
    fail = make_fail("polygon_signed_area2")
    check_items(fail, points, "points")
    if len(points) < 3:
        fail("too_few:points")
    pts = []
    for i, p in enumerate(points):
        if type(p) is not list or len(p) != 2:
            fail("bad_type:points[%d]" % i)
        check_int(fail, p[0], "points[%d][0]" % i)
        check_int(fail, p[1], "points[%d][1]" % i)
        pts.append((p[0], p[1]))
    total = 0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        total += x1 * y2 - x2 * y1
    return total


def grid_path_count(w, h):
    fail = make_fail("grid_path_count")
    check_int(fail, w, "w")
    check_int(fail, h, "h")
    if w < 0 or h < 0:
        fail("bad_value:side")
    if w > MAX_GRID_SIDE or h > MAX_GRID_SIDE:
        fail("too_many:side")
    return math.comb(w + h, w)


def iso_weekday(text):
    fail = make_fail("iso_weekday")
    check_str(fail, text, "date")
    m = _ISO_RE.fullmatch(text)
    if m is None:
        fail("bad_value:date")
    try:
        d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        fail("bad_value:date")
    return d.weekday()


def leap_year_check(year):
    fail = make_fail("leap_year_check")
    check_int(fail, year, "year")
    if year < 1 or year > 9999:
        fail("bad_value:year")
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def roman_numeral_render(n):
    fail = make_fail("roman_numeral_render")
    check_int(fail, n, "n")
    if n < 1:
        fail("bad_value:n")
    if n > 3999:
        fail("too_many:n")
    table = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
             (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
             (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
    out = []
    for value, glyph in table:
        q, n = divmod(n, value)
        out.append(glyph * q)
    return "".join(out)


def power_mod(base, exp, m):
    fail = make_fail("power_mod")
    check_int(fail, base, "base")
    check_int(fail, exp, "exp")
    check_int(fail, m, "m")
    if abs(base) > MAX_BASE:
        fail("too_many:base")
    if exp < 0:
        fail("bad_value:exp")
    if exp > MAX_EXP:
        fail("too_many:exp")
    if m < 1:
        fail("bad_value:m")
    if m > MAX_MOD:
        fail("too_many:m")
    return pow(base, exp, m)


def extended_gcd(a, b):
    fail = make_fail("extended_gcd")
    check_int(fail, a, "a")
    check_int(fail, b, "b")
    if a < 0 or b < 0:
        fail("bad_value:input")
    if a == 0 and b == 0:
        fail("bad_value:both_zero")
    old_r, r = a, b
    old_s, s = 1, 0
    old_t, t = 0, 1
    while r:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_s, s = s, old_s - q * s
        old_t, t = t, old_t - q * t
    return old_r, old_s, old_t


def prime_factors_trial(n):
    fail = make_fail("prime_factors_trial")
    check_int(fail, n, "n")
    if n < 2:
        fail("bad_value:n")
    if n > MAX_FACTOR_N:
        fail("too_many:n")
    factors = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1 if d == 2 else 2
    if n > 1:
        factors.append(n)
    return factors


def count_inversions(items):
    fail = make_fail("count_inversions")
    check_items(fail, items, "items")
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)

    def sort_count(seq):
        if len(seq) < 2:
            return seq, 0
        mid = len(seq) // 2
        left, lc = sort_count(seq[:mid])
        right, rc = sort_count(seq[mid:])
        merged = []
        i = j = 0
        cross = 0
        while i < len(left) and j < len(right):
            if left[i] <= right[j]:
                merged.append(left[i])
                i += 1
            else:
                merged.append(right[j])
                j += 1
                cross += len(left) - i
        merged.extend(left[i:])
        merged.extend(right[j:])
        return merged, lc + rc + cross

    return sort_count(list(items))[1]


def kth_smallest(items, k):
    fail = make_fail("kth_smallest")
    check_items(fail, items, "items")
    check_int(fail, k, "k")
    if not items:
        fail("empty:items")
    if k < 1 or k > len(items):
        fail("bad_value:k")
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
    return sorted(items)[k - 1]
