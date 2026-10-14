"""P235 concepts, batch 9 (algorithms, 81-90). Offline, stdlib only."""
from __future__ import annotations

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_PRIME_N = 10_000_000
MAX_SIEVE_N = 100_000
MAX_LIS_N = 1_000
MAX_PASCAL_N = 1_000
_MAX_TEXT = MAX_ITEMS


def manhattan_distance(a, b):
    fail = make_fail("manhattan_distance")
    check_items(fail, a, "a")
    check_items(fail, b, "b")
    if len(a) != len(b):
        fail("length_mismatch")
    total = 0
    for i, (x, y) in enumerate(zip(a, b)):
        check_int(fail, x, "a[%d]" % i)
        check_int(fail, y, "b[%d]" % i)
        total += abs(x - y)
    return total


def prime_check_trial(n):
    fail = make_fail("prime_check_trial")
    check_int(fail, n, "n")
    if n < 0:
        fail("bad_value:n")
    if n > MAX_PRIME_N:
        fail("too_many:n")
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    d = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2
    return True


def sieve_primes_upto(n):
    fail = make_fail("sieve_primes_upto")
    check_int(fail, n, "n")
    if n < 0:
        fail("bad_value:n")
    if n > MAX_SIEVE_N:
        fail("too_many:n")
    if n < 2:
        return []
    sieve = bytearray([1]) * (n + 1)
    sieve[0] = sieve[1] = 0
    for p in range(2, int(n ** 0.5) + 1):
        if sieve[p]:
            sieve[p * p::p] = bytearray(len(sieve[p * p::p]))
    return [i for i in range(2, n + 1) if sieve[i]]


def merge_intervals(intervals):
    fail = make_fail("merge_intervals")
    check_items(fail, intervals, "intervals")
    spans = []
    for i, item in enumerate(intervals):
        if type(item) is not list or len(item) != 2:
            fail("bad_value:interval")
        lo, hi = item
        check_int(fail, lo, "intervals[%d][0]" % i)
        check_int(fail, hi, "intervals[%d][1]" % i)
        if lo > hi:
            fail("bad_value:interval")
        spans.append((lo, hi))
    spans.sort()
    merged = []
    for lo, hi in spans:
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return merged


def binary_search_index(items, target):
    fail = make_fail("binary_search_index")
    check_items(fail, items, "items")
    check_int(fail, target, "target")
    prev = None
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        if prev is not None and v < prev:
            fail("unsorted:items")
        prev = v
    lo, hi = 0, len(items)
    while lo < hi:
        mid = (lo + hi) // 2
        if items[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo if lo < len(items) and items[lo] == target else -1


def kadane_max_subarray(items):
    fail = make_fail("kadane_max_subarray")
    check_items(fail, items, "items")
    if not items:
        fail("empty:items")
    best = current = None
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        current = v if current is None else max(v, current + v)
        best = v if best is None else max(best, current)
    return best


def lis_length(items):
    fail = make_fail("lis_length")
    check_items(fail, items, "items")
    if len(items) > MAX_LIS_N:
        fail("too_many:items")
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
    best = []
    for i in range(len(items)):
        length = 1
        for j in range(i):
            if items[j] < items[i] and best[j] + 1 > length:
                length = best[j] + 1
        best.append(length)
    return max(best, default=0)


def hamming_distance(a, b):
    fail = make_fail("hamming_distance")
    check_str(fail, a, "a")
    check_str(fail, b, "b")
    if len(a) > _MAX_TEXT or len(b) > _MAX_TEXT:
        fail("too_many:text")
    if len(a) != len(b):
        fail("length_mismatch")
    return sum(1 for x, y in zip(a, b) if x != y)


def pascal_row(n):
    fail = make_fail("pascal_row")
    check_int(fail, n, "n")
    if n < 0:
        fail("bad_value:n")
    if n > MAX_PASCAL_N:
        fail("too_many:n")
    row = [1]
    for _ in range(n):
        row = [1] + [row[i] + row[i + 1] for i in range(len(row) - 1)] + [1]
    return row


def caesar_shift(text, k):
    fail = make_fail("caesar_shift")
    check_str(fail, text, "text")
    if len(text) > _MAX_TEXT:
        fail("too_many:text")
    check_int(fail, k, "k")
    k %= 26
    out = []
    for ch in text:
        o = ord(ch)
        if 97 <= o <= 122:
            out.append(chr(97 + (o - 97 + k) % 26))
        elif 65 <= o <= 90:
            out.append(chr(65 + (o - 65 + k) % 26))
        else:
            out.append(ch)
    return "".join(out)
