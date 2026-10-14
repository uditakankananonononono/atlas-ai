"""P235 concepts, batch 43 (sequences III, numbers IV, 421-430).

Offline, stdlib only. Exact arithmetic; caps refuse before work.
"""
from __future__ import annotations

import math

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, make_fail)

MAX_N = 10_000_000
MAX_DIM = 10_000
MAX_ABS = 10 ** 18


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


def wiggle_max_length(values):
    """Longest wiggle subsequence length (up-down alternation)."""
    fail = make_fail("wiggle_max_length")
    vals = _int_list(fail, values, "values")
    up = 1
    down = 1
    for i in range(1, len(vals)):
        if vals[i] > vals[i - 1]:
            up = down + 1
        elif vals[i] < vals[i - 1]:
            down = up + 1
    return max(up, down)


def longest_arithmetic_subseq(values):
    """Longest subsequence (by position) with constant difference."""
    fail = make_fail("longest_arithmetic_subseq")
    vals = _int_list(fail, values, "values")
    n = len(vals)
    if n <= 2:
        return n
    best = 2
    dp = []
    for i in range(n):
        row = {}
        for j in range(i):
            d = vals[i] - vals[j]
            row[d] = dp[j].get(d, 1) + 1
            if row[d] > best:
                best = row[d]
        dp.append(row)
    return best


def _pairs(fail, items, name):
    check_items(fail, items, name)
    if not items:
        fail("empty:%s" % name)
    if len(items) > MAX_ITEMS:
        fail("too_many:%s" % name)
    out = []
    for i, it in enumerate(items):
        if type(it) is not list or len(it) != 2:
            fail("bad_type:%s[%d]" % (name, i))
        check_int(fail, it[0], "%s[%d][0]" % (name, i))
        check_int(fail, it[1], "%s[%d][1]" % (name, i))
        if it[0] < 1 or it[1] < 1 or it[0] > MAX_DIM or it[1] > MAX_DIM:
            fail("bad_value:%s[%d]" % (name, i))
        out.append((it[0], it[1]))
    return out


def russian_doll_envelopes(envelopes):
    """Most envelopes nestable, both dimensions strictly smaller."""
    fail = make_fail("russian_doll_envelopes")
    pairs = _pairs(fail, envelopes, "envelopes")
    pairs.sort(key=lambda e: (e[0], -e[1]))
    tails = []
    for _w, h in pairs:
        lo, hi = 0, len(tails)
        while lo < hi:
            mid = (lo + hi) // 2
            if tails[mid] < h:
                lo = mid + 1
            else:
                hi = mid
        if lo == len(tails):
            tails.append(h)
        else:
            tails[lo] = h
    return len(tails)


def max_length_chain_pairs(pairs):
    """Longest chain where each pair's second is below the next first."""
    fail = make_fail("max_length_chain_pairs")
    items = _pairs(fail, pairs, "pairs")
    items.sort()
    best = 0
    dp = [1] * len(items)
    for i in range(len(items)):
        for j in range(i):
            if items[j][1] < items[i][0] and dp[j] + 1 > dp[i]:
                dp[i] = dp[j] + 1
        if dp[i] > best:
            best = dp[i]
    return best


def count_digit_one_upto(n):
    """How many times digit 1 appears across every integer 0..n."""
    fail = make_fail("count_digit_one_upto")
    check_int(fail, n, "n")
    if n < 0 or n > MAX_N:
        fail("bad_value:n")
    total = 0
    factor = 1
    while factor <= n:
        lower = n % factor
        cur = (n // factor) % 10
        higher = n // (factor * 10)
        if cur == 0:
            total += higher * factor
        elif cur == 1:
            total += higher * factor + lower + 1
        else:
            total += (higher + 1) * factor
        factor *= 10
    return total


def bulb_switcher_count(n):
    """Bulbs left on after n toggle rounds: the perfect squares."""
    fail = make_fail("bulb_switcher_count")
    check_int(fail, n, "n")
    if n < 0 or n > MAX_N:
        fail("bad_value:n")
    return math.isqrt(n)


def arrange_coins_rows(coins):
    """Complete staircase rows buildable with the given coins."""
    fail = make_fail("arrange_coins_rows")
    check_int(fail, coins, "coins")
    if coins < 0 or coins > MAX_N:
        fail("bad_value:coins")
    rows = 0
    need = 1
    while coins >= need:
        coins -= need
        rows += 1
        need += 1
    return rows


def self_dividing_count(lo, hi):
    """Count of self-dividing numbers in [lo, hi] inclusive."""
    fail = make_fail("self_dividing_count")
    check_int(fail, lo, "lo")
    check_int(fail, hi, "hi")
    if lo < 1 or hi > MAX_N or lo > hi:
        fail("bad_value:range")

    def self_dividing(x):
        y = x
        while y:
            d = y % 10
            if d == 0 or x % d != 0:
                return False
            y //= 10
        return True

    return sum(1 for x in range(lo, hi + 1) if self_dividing(x))


def h_index_citations(citations):
    """Largest h with at least h papers cited at least h times."""
    fail = make_fail("h_index_citations")
    vals = _int_list(fail, citations, "citations")
    for i, v in enumerate(vals):
        if v < 0:
            fail("bad_value:citations[%d]" % i)
    vals.sort(reverse=True)
    h = 0
    for i, v in enumerate(vals):
        if v >= i + 1:
            h = i + 1
        else:
            break
    return h


def reverse_int_capped(x):
    """Decimal digit reversal; 0 when it leaves the int32 range.

    Refuses |x| above MAX_ABS (10**18) before any digit work.
    """
    fail = make_fail("reverse_int_capped")
    check_int(fail, x, "x")
    if abs(x) > MAX_ABS:
        fail("out_of_range:x")
    sign = -1 if x < 0 else 1
    out = 0
    y = abs(x)
    while y:
        out = out * 10 + y % 10
        y //= 10
    out *= sign
    if out < -2 ** 31 or out > 2 ** 31 - 1:
        return 0
    return out
