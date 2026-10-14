"""P235 concepts batch 88: combinatorial enumeration outputs.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
Every function returns the full list of a combinatorial family in
a documented order. Most families pre-count their output before
materialization (powerset size, factorial, dynamic-programming
counts for sums and palindrome cuts, exact powers for masks,
memoized factorization counts, closed-form strobogrammatic and
Fibonacci counts) and refuse beyond MAX_ITEMS entries; the rest
carry a static output bound instead (restore_ip_addresses builds
at most 81 dotted candidates from a 12-digit input). Recursion
depth, where used, stays within a declared cap; the deep
enumerations run from an explicit stack.

The factorization_lists output cap is a defensive guard: under
the n <= 10000 input cap the real maximum is 662 factorization
lists (at n = 8640), so the too_many:output refusal is
unreachable in contract.
"""

from math import factorial

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_VAL = 10_000
MAX_WORK = 2_000_000


def _distinct_ints(fail, items, name="items"):
    check_items(fail, items, name)
    if not items:
        fail("empty:%s" % name)
    for i, v in enumerate(items):
        check_int(fail, v, "%s[%d]" % (name, i))
        if v < -MAX_VAL or v > MAX_VAL:
            fail("out_of_range:%s[%d]" % (name, i))
    if len(set(items)) != len(items):
        fail("duplicate:%s" % name)
    return items


def subsets_list(items):
    """Every subset of the distinct values, each ascending,
    ordered by subset length then lexicographic."""
    fail = make_fail("subsets_list")
    _distinct_ints(fail, items)
    if 2 ** len(items) > MAX_ITEMS:
        fail("too_many:items")
    ordered = sorted(items)
    out = [[]]
    for v in ordered:
        out.extend(prefix + [v] for prefix in
                   [s for s in out])
        out.sort(key=lambda s: (len(s), s))
    return out


def permutations_list(items):
    """Every permutation of the distinct values in lexicographic
    order over the ascending values."""
    fail = make_fail("permutations_list")
    _distinct_ints(fail, items)
    if factorial(len(items)) > MAX_ITEMS:
        fail("too_many:items")
    ordered = sorted(items)
    out = []

    def walk(remaining, picked):
        if not remaining:
            out.append(list(picked))
            return
        for i, v in enumerate(remaining):
            walk(remaining[:i] + remaining[i + 1:], picked + [v])
    walk(ordered, [])
    return out


def combination_sum_lists(candidates, target):
    """Every multiset of candidates (reuse allowed) summing to
    target, each ascending, in lexicographic order.

    The counting pass is bounded by len(candidates) * (target + 1)
    and refuses too_much:work past a declared budget. The walk
    skips remainders unreachable using all candidates; this does
    not exclude every dead-end prefix under the
    nondecreasing-candidate restriction. MAX_WORK bounds the
    counting pass, not the enumeration walk."""
    fail = make_fail("combination_sum_lists")
    _distinct_ints(fail, candidates, "candidates")
    for i, v in enumerate(candidates):
        if v < 1:
            fail("out_of_range:candidates[%d]" % i)
    check_int(fail, target, "target")
    if target < 1 or target > MAX_VAL:
        fail("out_of_range:target")
    ordered = sorted(candidates)
    if len(ordered) * (target + 1) > MAX_WORK:
        fail("too_much:work")
    count = [0] * (target + 1)
    count[0] = 1
    for v in ordered:
        for t in range(v, target + 1):
            count[t] = min(count[t] + count[t - v], MAX_ITEMS + 1)
    if count[target] > MAX_ITEMS:
        fail("too_many:output")
    if count[target] == 0:
        return []
    out = []
    picked = []
    stack = [(0, target, False)]
    while stack:
        i, remaining, appended = stack[-1]
        if remaining == 0:
            out.append(list(picked))
            stack.pop()
            if appended:
                picked.pop()
            continue
        if i >= len(ordered) or ordered[i] > remaining:
            stack.pop()
            if appended:
                picked.pop()
            continue
        v = ordered[i]
        stack[-1] = (i + 1, remaining, appended)
        nv = remaining - v
        if nv == 0 or count[nv] > 0:
            picked.append(v)
            stack.append((i, nv, True))
    return out


def partition_palindrome_lists(text):
    """Every way to cut text into palindrome parts, lexicographic
    by parts. Case and punctuation are significant."""
    fail = make_fail("partition_palindrome_lists")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > 16:
        fail("too_long:text")
    n = len(text)
    pal = [[False] * (n + 1) for _ in range(n + 1)]
    for i in range(n):
        pal[i][i + 1] = True
    for span in range(2, n + 1):
        for i in range(n - span + 1):
            j = i + span
            pal[i][j] = (text[i] == text[j - 1]
                         and (span == 2 or pal[i + 1][j - 1]))
    ways = [0] * (n + 1)
    ways[0] = 1
    for j in range(1, n + 1):
        for i in range(j):
            if pal[i][j]:
                ways[j] = min(ways[j] + ways[i], MAX_ITEMS + 1)
    if ways[n] > MAX_ITEMS:
        fail("too_many:output")
    out = []

    def walk(start, parts):
        if start == n:
            out.append(list(parts))
            return
        for end in range(start + 1, n + 1):
            if pal[start][end]:
                parts.append(text[start:end])
                walk(end, parts)
                parts.pop()
    walk(0, [])
    out.sort()
    return out


def restore_ip_addresses(digits):
    """Every valid IPv4 dotted form of the digit string, in
    lexicographic order. No part may exceed 255 or carry a
    leading zero."""
    fail = make_fail("restore_ip_addresses")
    check_str(fail, digits, "digits")
    if not digits or not all("0" <= c <= "9" for c in digits):
        fail("bad_value:digits")
    if len(digits) < 4 or len(digits) > 12:
        fail("bad_length:digits")
    out = []

    def walk(start, parts):
        if len(parts) == 4:
            if start == len(digits):
                out.append(".".join(parts))
            return
        for span in (1, 2, 3):
            part = digits[start:start + span]
            if len(part) != span:
                break
            if span > 1 and part[0] == "0":
                continue
            if int(part) > 255:
                continue
            walk(start + span, parts + [part])
    walk(0, [])
    out.sort()
    return out


def brace_expand_list(text):
    """Every string the brace pattern expands to, lexicographic.

    The pattern is a run of atoms: a lowercase letter, or a brace
    group of one or more comma-separated lowercase letters. The
    expansion is the left-to-right product of the options."""
    fail = make_fail("brace_expand_list")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > 200:
        fail("too_long:text")
    groups = []
    i = 0
    while i < len(text):
        c = text[i]
        if "a" <= c <= "z":
            groups.append([c])
            i += 1
        elif c == "{":
            end = text.find("}", i + 1)
            if end == -1:
                fail("bad_value:text")
            body = text[i + 1:end]
            options = body.split(",")
            for opt in options:
                if len(opt) != 1 or not ("a" <= opt <= "z"):
                    fail("bad_value:text")
            groups.append(sorted(set(options)))
            i = end + 1
        else:
            fail("bad_value:text")
    total = 1
    for g in groups:
        total *= len(g)
        if total > MAX_ITEMS:
            fail("too_many:output")
    out = [""]
    for g in groups:
        out = [prefix + opt for prefix in out for opt in g]
    out.sort()
    return out


def tower_of_hanoi_moves(n):
    """The move sequence shifting n disks from peg A to peg C with
    spare peg B, as [from, to] pairs."""
    fail = make_fail("tower_of_hanoi_moves")
    check_int(fail, n, "n")
    if n < 1:
        fail("out_of_range:n")
    # static gate: 2**13 - 1 = 8191 fits, 2**14 - 1 does not; the
    # magnitude check must precede any exponent work.
    if n > 13:
        fail("too_many:n")
    out = []

    def walk(count, src, dst, spare):
        if count == 0:
            return
        walk(count - 1, src, spare, dst)
        out.append([src, dst])
        walk(count - 1, spare, dst, src)
    walk(n, "A", "C", "B")
    return out


def factorization_lists(n):
    """Every factorization of n into factors >= 2, n alone
    included, each factorization nondecreasing and the list in
    lexicographic order. The count is computed (memoized by
    remaining/start) before any factorization is built."""
    fail = make_fail("factorization_lists")
    check_int(fail, n, "n")
    if n < 2 or n > MAX_VAL:
        fail("out_of_range:n")
    memo = {}

    def count_ways(remaining, start):
        key = (remaining, start)
        if key in memo:
            return memo[key]
        total = 1  # [remaining] alone
        d = start
        while d * d <= remaining:
            if remaining % d == 0:
                total += count_ways(remaining // d, d)
                if total > MAX_ITEMS:
                    memo[key] = total
                    return total
            d += 1
        memo[key] = total
        return total

    if count_ways(n, 2) > MAX_ITEMS:
        fail("too_many:output")
    out = []

    def walk(remaining, start, picked):
        out.append(picked + [remaining])
        d = start
        while d * d <= remaining:
            if remaining % d == 0:
                walk(remaining // d, d, picked + [d])
            d += 1
    walk(n, 2, [])
    out.sort()
    return out


def strobogrammatic_list(n):
    """Every n-digit strobogrammatic string: identical when
    rotated 180 degrees. Longer strings never start with 0; the
    list is in lexicographic order."""
    fail = make_fail("strobogrammatic_list")
    check_int(fail, n, "n")
    if n < 1:
        fail("out_of_range:n")
    # static magnitude gate: the closed-form count stays within
    # MAX_ITEMS only for n <= 11; it must precede any power work.
    if n > 11:
        fail("too_many:n")
    if n == 1:
        total = 3
    elif n % 2 == 0:
        total = 4 * 5 ** (n // 2 - 1)
    else:
        total = 12 * 5 ** (n // 2 - 1)
    if total > MAX_ITEMS:
        fail("too_many:output")
    mirror = {"0": "0", "1": "1", "6": "9", "8": "8", "9": "6"}
    digits = "01689"
    half = n // 2
    halves = [""]
    for pos in range(half):
        halves = [h + d for h in halves for d in digits
                  if pos > 0 or d != "0"]
    middles = ("0", "1", "8") if n % 2 else ("",)
    out = []
    for h in halves:
        tail = "".join(mirror[c] for c in reversed(h))
        for mid in middles:
            out.append(h + mid + tail)
    out.sort()
    return out


def binary_strings_no_consecutive(n):
    """Every n-bit string without adjacent 1s, in lexicographic
    order. The Fibonacci count is computed with an early stop at
    the output cap, so no oversized string is ever built."""
    fail = make_fail("binary_strings_no_consecutive")
    check_int(fail, n, "n")
    if n < 1:
        fail("out_of_range:n")
    a, b = 1, 1
    for _ in range(n + 1):
        a, b = b, a + b
        if a > MAX_ITEMS:
            fail("too_many:n")
    out = [""]
    for _ in range(n):
        nxt = []
        for s in out:
            nxt.append(s + "0")
            if not s.endswith("1"):
                nxt.append(s + "1")
        out = nxt
    out.sort()
    return out
