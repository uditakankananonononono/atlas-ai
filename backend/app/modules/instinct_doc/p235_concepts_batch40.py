"""P235 concepts, batch 40 (selection, streaks, simulation II, 391-400).

Offline, stdlib only. Exact arithmetic; caps refuse before work.
"""
from __future__ import annotations

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, make_fail)

MAX_N = 10_000_000
MAX_K = 1_000
MAX_RATINGS = 10_000


def _int_list(fail, values, name, cap=MAX_ITEMS):
    check_items(fail, values, name)
    if not values:
        fail("empty:%s" % name)
    if len(values) > cap:
        fail("too_many:%s" % name)
    out = []
    for i, v in enumerate(values):
        check_int(fail, v, "%s[%d]" % (name, i))
        out.append(v)
    return out


def top_k_frequent_values(values, k):
    """The k most frequent values; ties broken by smaller value first."""
    fail = make_fail("top_k_frequent_values")
    vals = _int_list(fail, values, "values")
    check_int(fail, k, "k")
    if k < 1 or k > MAX_K:
        fail("bad_value:k")
    counts = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    ranked = sorted(counts, key=lambda v: (-counts[v], v))
    return ranked[:k]


def longest_consecutive_streak(values):
    """Length of the longest run of consecutive integers present."""
    fail = make_fail("longest_consecutive_streak")
    vals = _int_list(fail, values, "values")
    have = set(vals)
    best = 0
    for v in have:
        if v - 1 not in have:
            run = 1
            while v + run in have:
                run += 1
            if run > best:
                best = run
    return best


def product_except_self(values):
    """products[i] is the product of every element except values[i]."""
    fail = make_fail("product_except_self")
    vals = _int_list(fail, values, "values")
    n = len(vals)
    out = [1] * n
    run = 1
    for i in range(n):
        out[i] = run
        run *= vals[i]
    run = 1
    for i in range(n - 1, -1, -1):
        out[i] *= run
        run *= vals[i]
    return out


def first_missing_positive(values):
    """Smallest positive integer absent from the list."""
    fail = make_fail("first_missing_positive")
    vals = _int_list(fail, values, "values")
    have = set(vals)
    x = 1
    while x in have:
        x += 1
    return x


def max_product_of_three(values):
    """Maximum product of any three elements (by position)."""
    fail = make_fail("max_product_of_three")
    vals = _int_list(fail, values, "values")
    if len(vals) < 3:
        fail("too_few:values")
    top1 = top2 = top3 = None
    low1 = low2 = None
    for v in vals:
        if top1 is None or v > top1:
            top1, top2, top3 = v, top1, top2
        elif top2 is None or v > top2:
            top2, top3 = v, top2
        elif top3 is None or v > top3:
            top3 = v
        if low1 is None or v < low1:
            low1, low2 = v, low1
        elif low2 is None or v < low2:
            low2 = v
    return max(top1 * top2 * top3, top1 * low1 * low2)


def count_bits_total_upto(n):
    """Total number of set bits across every integer from 0 to n."""
    fail = make_fail("count_bits_total_upto")
    check_int(fail, n, "n")
    if n < 0 or n > MAX_N:
        fail("bad_value:n")
    total = 0
    bit = 1
    while bit <= n:
        cycle = bit * 2
        full = (n + 1) // cycle
        total += full * bit
        rem = (n + 1) - full * cycle
        total += max(0, rem - bit)
        bit *= 2
    return total


def xor_range_total(lo, hi):
    """XOR of every integer from lo to hi inclusive."""
    fail = make_fail("xor_range_total")
    check_int(fail, lo, "lo")
    check_int(fail, hi, "hi")
    if lo < 0 or hi < 0 or lo > hi:
        fail("bad_value:range")
    if hi > MAX_N:
        fail("too_many:hi")

    def prefix(x):
        if x < 0:
            return 0
        rem = x % 4
        if rem == 0:
            return x
        if rem == 1:
            return 1
        if rem == 2:
            return x + 1
        return 0

    return prefix(hi) ^ prefix(lo - 1)


def gini_coefficient_exact(values):
    """Gini inequality coefficient of the values, as an exact Fraction."""
    from fractions import Fraction
    fail = make_fail("gini_coefficient_exact")
    vals = _int_list(fail, values, "values")
    for i, v in enumerate(vals):
        if v < 0:
            fail("bad_value:values[%d]" % i)
    total = sum(vals)
    if total == 0:
        fail("bad_value:all_zero")
    n = len(vals)
    diff = 0
    for i in range(n):
        for j in range(i + 1, n):
            diff += abs(vals[i] - vals[j])
    return Fraction(diff, n * total)



def gas_station_start(gas, cost):
    """Start index completing the circuit, or -1 when impossible."""
    fail = make_fail("gas_station_start")
    g = _int_list(fail, gas, "gas")
    c = _int_list(fail, cost, "cost")
    if len(g) != len(c):
        fail("bad_value:length_mismatch")
    for i, v in enumerate(g):
        if v < 0:
            fail("bad_value:gas[%d]" % i)
    for i, v in enumerate(c):
        if v < 0:
            fail("bad_value:cost[%d]" % i)
    tank = 0
    total = 0
    start = 0
    for i in range(len(g)):
        diff = g[i] - c[i]
        tank += diff
        total += diff
        if tank < 0:
            start = i + 1
            tank = 0
    if total < 0 or start == len(g):
        return -1
    return start


def candy_min_total(ratings):
    """Minimum candies; a higher-rated neighbor always gets more."""
    fail = make_fail("candy_min_total")
    vals = _int_list(fail, ratings, "ratings", MAX_RATINGS)
    n = len(vals)
    left = [1] * n
    for i in range(1, n):
        if vals[i] > vals[i - 1]:
            left[i] = left[i - 1] + 1
    total = 0
    run = 1
    for i in range(n - 1, -1, -1):
        if i + 1 < n and vals[i] > vals[i + 1]:
            run += 1
        else:
            run = 1
        total += max(left[i], run)
    return total
