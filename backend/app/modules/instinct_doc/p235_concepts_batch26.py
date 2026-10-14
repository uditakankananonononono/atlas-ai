"""P235 concepts batch 26 (concepts 251-260, sequence aggregates) - ten new
small deterministic list concepts. 251-260 of the doc's 1000 (anchor
P235|L184). Bounded lists and values; exact arithmetic; oracles pinned.
"""
from __future__ import annotations

from fractions import Fraction

from .p235_concepts_batch1 import MAX_ITEMS, check_int, check_items, make_fail

MAX_VALUE = 10**18


def _check_int_items(fail, items, name):
    check_items(fail, items, name)
    for i, v in enumerate(items):
        check_int(fail, v, "%s[%d]" % (name, i))
        if abs(v) > MAX_VALUE:
            fail("too_big:%s[%d]" % (name, i))
    return items


def intersperse_value(items, value):
    fail = make_fail("intersperse_value")
    _check_int_items(fail, items, "intersperse_value")
    check_int(fail, value, "value")
    if abs(value) > MAX_VALUE:
        fail("too_big:value")
    out = []
    for i, v in enumerate(items):
        if i:
            out.append(value)
        out.append(v)
    return out


def list_cycle_first_n(items, n):
    fail = make_fail("list_cycle_first_n")
    _check_int_items(fail, items, "list_cycle_first_n")
    if not items:
        fail("empty:items")
    check_int(fail, n, "n")
    if n < 0:
        fail("bad_value:n")
    if n > MAX_ITEMS:
        fail("too_many:n")
    size = len(items)
    return [items[i % size] for i in range(n)]


def dedupe_adjacent(items):
    """Remove only consecutive duplicates; non-adjacent repeats stay."""
    fail = make_fail("dedupe_adjacent")
    _check_int_items(fail, items, "dedupe_adjacent")
    out = []
    for v in items:
        if not out or out[-1] != v:
            out.append(v)
    return out


def pairwise_ratios_exact(items):
    """Exact ratio items[i+1]/items[i] for each adjacent pair."""
    fail = make_fail("pairwise_ratios_exact")
    _check_int_items(fail, items, "pairwise_ratios_exact")
    out = []
    for a, b in zip(items, items[1:]):
        if a == 0:
            fail("bad_value:items")
        out.append(Fraction(b, a))
    return out


def outer_pair_sums(items):
    """Pair the outside in: items[i] + items[n-1-i] for i < n//2."""
    fail = make_fail("outer_pair_sums")
    _check_int_items(fail, items, "outer_pair_sums")
    n = len(items)
    return [items[i] + items[n - 1 - i] for i in range(n // 2)]


def count_in_range(items, lo, hi):
    fail = make_fail("count_in_range")
    _check_int_items(fail, items, "count_in_range")
    check_int(fail, lo, "lo")
    check_int(fail, hi, "hi")
    if lo > hi:
        fail("bad_value:range")
    return sum(1 for v in items if lo <= v <= hi)


def count_signs(items):
    """(negative, zero, positive) counts as a tuple."""
    fail = make_fail("count_signs")
    _check_int_items(fail, items, "count_signs")
    neg = zero = pos = 0
    for v in items:
        if v < 0:
            neg += 1
        elif v == 0:
            zero += 1
        else:
            pos += 1
    return (neg, zero, pos)


def alternating_sum(items):
    """items[0] - items[1] + items[2] - ... exact."""
    fail = make_fail("alternating_sum")
    _check_int_items(fail, items, "alternating_sum")
    total = 0
    for i, v in enumerate(items):
        total += v if i % 2 == 0 else -v
    return total


def max_gap_consecutive_sorted(items):
    """Largest gap between consecutive values after sorting."""
    fail = make_fail("max_gap_consecutive_sorted")
    _check_int_items(fail, items, "max_gap_consecutive_sorted")
    if len(items) < 2:
        fail("bad_value:items")
    ordered = sorted(items)
    return max(b - a for a, b in zip(ordered, ordered[1:]))


def first_duplicate_value(items):
    """First value (by scan order of its second appearance) seen twice."""
    fail = make_fail("first_duplicate_value")
    _check_int_items(fail, items, "first_duplicate_value")
    seen = set()
    for v in items:
        if v in seen:
            return v
        seen.add(v)
    return None
