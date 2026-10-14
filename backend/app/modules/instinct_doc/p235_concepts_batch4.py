"""P235 concepts, batch 4 (exact arithmetic). Offline, stdlib only.

All arithmetic is exact: Fraction for rationals, Decimal for cents, math
gcd/isqrt for big ints. Floats are refused at the boundary - exactness is
the contract, and silent float rounding would break it.
"""
from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, make_fail)


def _frac(fail, v, name):
    """Parse an exact numeric input: int, or 'a' / 'a/b' string. No floats."""
    if type(v) is int:
        return Fraction(v)
    if type(v) is str:
        text = v.strip()
        try:
            if "/" in text:
                num_s, den_s = text.split("/", 1)
                num, den = int(num_s), int(den_s)
                if den == 0:
                    fail("bad_value:%s" % name)
                return Fraction(num, den)
            dec = Decimal(text)
            if not dec.is_finite():
                fail("bad_value:%s" % name)
            return Fraction(dec)
        except (ValueError, InvalidOperation):
            fail("bad_value:%s" % name)
    fail("bad_type:%s" % name)


def _frac_list(fail, values, name="values"):
    check_items(fail, values, name)
    if not values:
        fail("empty:" + name)
    return [_frac(fail, v, "%s[%d]" % (name, i)) for i, v in enumerate(values)]


def fraction_median(values):
    fail = make_fail("fraction_median")
    fracs = sorted(_frac_list(fail, values))
    n = len(fracs)
    if n % 2 == 1:
        return fracs[n // 2]
    return (fracs[n // 2 - 1] + fracs[n // 2]) / 2


def fraction_mean(values):
    fail = make_fail("fraction_mean")
    fracs = _frac_list(fail, values)
    return sum(fracs, Fraction(0)) / len(fracs)


def weighted_sum_exact(pairs):
    fail = make_fail("weighted_sum_exact")
    check_items(fail, pairs, "pairs")
    if not pairs:
        fail("empty:pairs")
    total = Fraction(0)
    for i, pair in enumerate(pairs):
        if type(pair) not in (list, tuple) or len(pair) != 2:
            fail("bad_type:pairs[%d]" % i)
        total += _frac(fail, pair[0], "pairs[%d][0]" % i) * \
            _frac(fail, pair[1], "pairs[%d][1]" % i)
    return total


def clamp_bounds(value, low, high):
    fail = make_fail("clamp_bounds")
    v = _frac(fail, value, "value")
    lo = _frac(fail, low, "low")
    hi = _frac(fail, high, "high")
    if lo > hi:
        fail("bad_value:low_above_high")
    return min(max(v, lo), hi)


def safe_ratio(numerator, denominator):
    fail = make_fail("safe_ratio")
    num = _frac(fail, numerator, "numerator")
    den = _frac(fail, denominator, "denominator")
    if den == 0:
        fail("zero_denominator")
    return num / den


def round_half_even_cents(value):
    fail = make_fail("round_half_even_cents")
    if type(value) is not str:
        fail("bad_type:value")
    try:
        cents = Decimal(value.strip())
    except InvalidOperation:
        fail("bad_value:value")
    if not cents.is_finite():
        fail("bad_value:value")
    if cents.adjusted() > 24:
        fail("too_many:value")
    try:
        return cents.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    except InvalidOperation:
        fail("bad_value:value")


def percent_change_exact(old, new):
    fail = make_fail("percent_change_exact")
    base = _frac(fail, old, "old")
    current = _frac(fail, new, "new")
    if base == 0:
        fail("zero_base")
    return (current - base) / base * 100


def _nat(fail, v, name):
    check_int(fail, v, name)
    if v < 0:
        fail("bad_value:%s" % name)
    return v


def gcd_pair(a, b):
    fail = make_fail("gcd_pair")
    return math.gcd(_nat(fail, a, "a"), _nat(fail, b, "b"))


def lcm_pair(a, b):
    fail = make_fail("lcm_pair")
    x = _nat(fail, a, "a")
    y = _nat(fail, b, "b")
    if y == 0:
        return 0
    return x // math.gcd(x, y) * y


def integer_sqrt_floor(n):
    fail = make_fail("integer_sqrt_floor")
    return math.isqrt(_nat(fail, n, "n"))
