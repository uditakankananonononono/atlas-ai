"""P235 concepts, batch 14 (geometry/time, 131-140). Offline, stdlib only."""
from __future__ import annotations

import datetime
import math
import re
from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_DAY_SHIFT = 100_000
MAX_HOURS = 10_000
MAX_SECONDS = MAX_HOURS * 3600 + 3599
_ISO_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")


def _int_points(fail, points, name="points", min_count=1):
    check_items(fail, points, name)
    if len(points) < min_count:
        fail("empty:%s" % name)
    pts = []
    cells = 0
    for i, p in enumerate(points):
        if type(p) is not list or not p:
            fail("bad_type:%s[%d]" % (name, i))
        cells += len(p)
        if cells > MAX_ITEMS:
            fail("too_many:cells")
        for j, v in enumerate(p):
            check_int(fail, v, "%s[%d][%d]" % (name, i, j))
        pts.append(list(p))
    return pts


def _check_rect(fail, rect):
    if type(rect) is not list or len(rect) != 4:
        fail("bad_value:rect")
    for i, v in enumerate(rect):
        check_int(fail, v, "rect[%d]" % i)
    if rect[0] > rect[2] or rect[1] > rect[3]:
        fail("bad_value:rect")


def _parse_iso(fail, text):
    check_str(fail, text, "date")
    m = _ISO_RE.fullmatch(text)
    if m is None:
        fail("bad_value:date")
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        fail("bad_value:date")


def point_in_rect(point, rect):
    fail = make_fail("point_in_rect")
    if type(point) is not list or len(point) != 2:
        fail("bad_type:point")
    check_int(fail, point[0], "point[0]")
    check_int(fail, point[1], "point[1]")
    _check_rect(fail, rect)
    return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]


def distance_squared(a, b):
    fail = make_fail("distance_squared")
    check_items(fail, a, "a")
    check_items(fail, b, "b")
    if len(a) != len(b):
        fail("length_mismatch")
    total = 0
    for i, (x, y) in enumerate(zip(a, b)):
        check_int(fail, x, "a[%d]" % i)
        check_int(fail, y, "b[%d]" % i)
        total += (x - y) ** 2
    return total


def centroid_exact(points):
    fail = make_fail("centroid_exact")
    pts = _int_points(fail, points)
    dims = {len(p) for p in pts}
    if len(dims) != 1:
        fail("dimension_mismatch")
    n = len(pts)
    sums = [Fraction(0)] * dims.pop()
    for p in pts:
        for j, v in enumerate(p):
            sums[j] += v
    return tuple(s / n for s in sums)


def bounding_rect(points):
    fail = make_fail("bounding_rect")
    pts = _int_points(fail, points)
    for i, p in enumerate(pts):
        if len(p) != 2:
            fail("bad_value:points[%d]" % i)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return [min(xs), min(ys), max(xs), max(ys)]


def gcd_list(items):
    fail = make_fail("gcd_list")
    check_items(fail, items, "items")
    if not items:
        fail("empty:items")
    g = 0
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        if v < 0:
            fail("bad_value:items")
        g = math.gcd(g, v)
    return g


def lcm_list(items):
    fail = make_fail("lcm_list")
    check_items(fail, items, "items")
    if not items:
        fail("empty:items")
    l = 1
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        if v < 0:
            fail("bad_value:items")
        l = math.lcm(l, v)
    return l


def days_in_month(year, month):
    fail = make_fail("days_in_month")
    check_int(fail, year, "year")
    check_int(fail, month, "month")
    if year < 1 or year > 9999:
        fail("bad_value:year")
    if month < 1 or month > 12:
        fail("bad_value:month")
    common = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if leap else 28
    return common[month - 1]


def date_add_days(text, days):
    fail = make_fail("date_add_days")
    d = _parse_iso(fail, text)
    check_int(fail, days, "days")
    if abs(days) > MAX_DAY_SHIFT:
        fail("too_many:days")
    try:
        return (d + datetime.timedelta(days=days)).isoformat()
    except OverflowError:
        fail("too_many:days")


def hms_to_seconds(hours, minutes, seconds):
    fail = make_fail("hms_to_seconds")
    check_int(fail, hours, "hours")
    check_int(fail, minutes, "minutes")
    check_int(fail, seconds, "seconds")
    if hours < 0:
        fail("bad_value:hours")
    if hours > MAX_HOURS:
        fail("too_many:hours")
    if minutes < 0 or minutes > 59:
        fail("bad_value:minutes")
    if seconds < 0 or seconds > 59:
        fail("bad_value:seconds")
    return hours * 3600 + minutes * 60 + seconds


def seconds_to_hms(seconds):
    fail = make_fail("seconds_to_hms")
    check_int(fail, seconds, "seconds")
    if seconds < 0:
        fail("bad_value:seconds")
    if seconds > MAX_SECONDS:
        fail("too_many:seconds")
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return hours, minutes, secs
