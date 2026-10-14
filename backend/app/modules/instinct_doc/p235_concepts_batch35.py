"""P235 concepts, batch 35 (sequences and strings III, 341-350).

Offline, stdlib only. Exact integer arithmetic; caps refuse before work.
"""
from __future__ import annotations

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_SEQUENCE_INDEX = 1_000
MAX_COMBINATORIAL_N = 200
MAX_STRING_LEN = 1_000


def _check_n(fail, n, cap, name="n"):
    check_int(fail, n, name)
    if n < 0:
        fail("bad_value:%s" % name)
    if n > cap:
        fail("too_many:%s" % name)


def z_function(s):
    fail = make_fail("z_function")
    check_str(fail, s, "s")
    if len(s) > MAX_STRING_LEN:
        fail("too_many:s")
    n = len(s)
    z = [0] * n
    left = right = 0
    for i in range(1, n):
        if i < right:
            z[i] = min(right - i, z[i - left])
        while i + z[i] < n and s[z[i]] == s[i + z[i]]:
            z[i] += 1
        if i + z[i] > right:
            left, right = i, i + z[i]
    if n:
        z[0] = n
    return z


def bell_number(n):
    fail = make_fail("bell_number")
    _check_n(fail, n, MAX_COMBINATORIAL_N)
    triangle = [[1]]
    for i in range(1, n + 1):
        row = [triangle[-1][-1]]
        for j in range(i):
            row.append(row[-1] + triangle[-1][j])
        triangle.append(row)
    return triangle[n][0]


def eulerian_number(n, k):
    fail = make_fail("eulerian_number")
    _check_n(fail, n, MAX_COMBINATORIAL_N)
    _check_n(fail, k, MAX_COMBINATORIAL_N, "k")
    if k >= n and n > 0:
        return 0
    if n == 0:
        return 1 if k == 0 else 0
    row = [1]
    for size in range(2, n + 1):
        nxt = [0] * size
        for j in range(size):
            keep = (j + 1) * row[j] if j < len(row) else 0
            open_new = (size - j) * row[j - 1] if j >= 1 else 0
            nxt[j] = keep + open_new
        row = nxt
    return row[k]


def schroder_number(n):
    fail = make_fail("schroder_number")
    _check_n(fail, n, MAX_COMBINATORIAL_N)
    s = [1, 2]
    for i in range(2, n + 1):
        s.append(s[-1] + sum(s[k] * s[i - 1 - k]
                             for k in range(i)))
    return s[n]


def narayana_number(n, k):
    fail = make_fail("narayana_number")
    check_int(fail, n, "n")
    check_int(fail, k, "k")
    if n < 1 or n > MAX_COMBINATORIAL_N:
        fail("bad_value:n")
    if k < 1 or k > n:
        fail("bad_value:k")
    from math import comb
    return comb(n, k) * comb(n, k - 1) // n


def tribonacci_term(n):
    fail = make_fail("tribonacci_term")
    _check_n(fail, n, MAX_SEQUENCE_INDEX)
    a, b, c = 0, 0, 1
    for _ in range(n):
        a, b, c = b, c, a + b + c
    return a


def pell_number(n):
    fail = make_fail("pell_number")
    _check_n(fail, n, MAX_SEQUENCE_INDEX)
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + 2 * b
    return a


def longest_common_substring_length(a, b):
    fail = make_fail("longest_common_substring_length")
    check_str(fail, a, "a")
    check_str(fail, b, "b")
    if len(a) > MAX_STRING_LEN or len(b) > MAX_STRING_LEN:
        fail("too_many:input")
    prev = [0] * (len(b) + 1)
    best = 0
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


def zigzag_check(items):
    fail = make_fail("zigzag_check")
    check_items(fail, items, "items")
    if len(items) > MAX_ITEMS:
        fail("too_many:items")
    vals = []
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        vals.append(v)
    if len(vals) < 3:
        return True
    for i in range(1, len(vals) - 1):
        lo = vals[i] < vals[i - 1] and vals[i] < vals[i + 1]
        hi = vals[i] > vals[i - 1] and vals[i] > vals[i + 1]
        if not (lo or hi):
            return False
    return True


def longest_bitonic_length(items):
    fail = make_fail("longest_bitonic_length")
    check_items(fail, items, "items")
    if len(items) > MAX_ITEMS:
        fail("too_many:items")
    vals = []
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        vals.append(v)
    n = len(vals)
    if n == 0:
        return 0
    inc = [1] * n
    for i in range(n):
        for j in range(i):
            if vals[j] < vals[i] and inc[j] + 1 > inc[i]:
                inc[i] = inc[j] + 1
    dec = [1] * n
    for i in range(n - 1, -1, -1):
        for j in range(n - 1, i, -1):
            if vals[j] < vals[i] and dec[j] + 1 > dec[i]:
                dec[i] = dec[j] + 1
    return max(inc[i] + dec[i] - 1 for i in range(n))
