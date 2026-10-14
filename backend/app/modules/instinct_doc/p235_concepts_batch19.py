"""P235 concepts, batch 19 (statistics, 181-190). Offline, stdlib only."""
from __future__ import annotations

from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    check_int, check_items, make_fail)


def _int_list(fail, items, name="items", min_count=1):
    check_items(fail, items, name)
    if len(items) < min_count:
        fail("empty:%s" % name if min_count == 1 else "too_few:%s" % name)
    for i, v in enumerate(items):
        check_int(fail, v, "%s[%d]" % (name, i))
    return list(items)


def median_low(items):
    fail = make_fail("median_low")
    vals = _int_list(fail, items)
    return sorted(vals)[(len(vals) - 1) // 2]


def quantile_nearest_rank(items, percent):
    fail = make_fail("quantile_nearest_rank")
    vals = _int_list(fail, items)
    check_int(fail, percent, "percent")
    if percent < 1 or percent > 100:
        fail("bad_value:percent")
    n = len(vals)
    rank = -(-percent * n // 100)  # ceil
    return sorted(vals)[max(1, rank) - 1]


def covariance_exact(a, b):
    fail = make_fail("covariance_exact")
    xs = _int_list(fail, a, "a")
    ys = _int_list(fail, b, "b")
    if len(xs) != len(ys):
        fail("length_mismatch")
    n = len(xs)
    mean_x = Fraction(sum(xs), n)
    mean_y = Fraction(sum(ys), n)
    return sum((Fraction(x) - mean_x) * (Fraction(y) - mean_y)
               for x, y in zip(xs, ys)) / n


def iqr_nearest_rank(items):
    fail = make_fail("iqr_nearest_rank")
    vals = _int_list(fail, items, min_count=4)
    ordered = sorted(vals)
    n = len(vals)
    q1 = ordered[max(1, -(-25 * n // 100)) - 1]
    q3 = ordered[max(1, -(-75 * n // 100)) - 1]
    return q3 - q1


def mean_absolute_deviation_exact(items):
    fail = make_fail("mean_absolute_deviation_exact")
    vals = _int_list(fail, items)
    n = len(vals)
    mean = Fraction(sum(vals), n)
    return sum(abs(Fraction(v) - mean) for v in vals) / n


def trimmed_mean_exact(items, k):
    fail = make_fail("trimmed_mean_exact")
    vals = _int_list(fail, items)
    check_int(fail, k, "k")
    n = len(vals)
    if k < 0 or 2 * k >= n:
        fail("bad_value:k")
    kept = sorted(vals)[k:n - k]
    return Fraction(sum(kept), len(kept))


def percentile_rank_of(items, value):
    fail = make_fail("percentile_rank_of")
    vals = _int_list(fail, items)
    check_int(fail, value, "value")
    below = sum(1 for v in vals if v < value)
    return Fraction(below, len(vals))


def midrange_exact(items):
    fail = make_fail("midrange_exact")
    vals = _int_list(fail, items)
    return Fraction(min(vals) + max(vals), 2)


def harmonic_mean_exact(items):
    fail = make_fail("harmonic_mean_exact")
    vals = _int_list(fail, items)
    denom = Fraction(0)
    for v in vals:
        if v <= 0:
            fail("bad_value:items")
        denom += Fraction(1, v)
    return Fraction(len(vals)) / denom


def sample_variance_exact(items):
    fail = make_fail("sample_variance_exact")
    vals = _int_list(fail, items, min_count=2)
    n = len(vals)
    mean = Fraction(sum(vals), n)
    return sum((Fraction(v) - mean) ** 2 for v in vals) / (n - 1)
