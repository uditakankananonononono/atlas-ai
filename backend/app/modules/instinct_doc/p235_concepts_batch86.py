"""P235 concepts batch 86: range query structures.

Four small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals; six earlier entries
were replaced by batch 92 after auditor screens. No external
deps. Queries are inclusive [left, right] index pairs (triples
where a bound applies). Every query or op list is fully
validated before any structure is built. Items stay within
MAX_ITEMS and query lists too; the heaviest structure costs an
estimated O((n + q) log n) primitive operations (point updates
and prefix queries on 10_000 items)."""

from bisect import bisect_left, bisect_right

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_str, check_items, make_fail)

MAX_VAL = 10_000
INT32_MAX = 2 ** 31 - 1

def _int_list(fail, xs, name, lo=-MAX_VAL, hi=MAX_VAL):
    check_items(fail, xs, name)
    if not xs:
        fail("empty:%s" % name)
    for i, v in enumerate(xs):
        check_int(fail, v, "%s[%d]" % (name, i))
        if v < lo or v > hi:
            fail("out_of_range:%s[%d]" % (name, i))
    return xs

def max_sum_two_nonoverlap(values, first_len, second_len):
    """Largest combined sum of two non-overlapping windows.

    One window has length first_len, the other second_len, and
    either may sit left of the other. For each orientation a
    left pass keeps the best first-length window sum ending at
    or before each index and a right pass the best second-length
    window sum starting at or after it; the split maximizes the
    pair. Both lengths must fit inside values together."""
    fail = make_fail("max_sum_two_nonoverlap")
    _int_list(fail, values, "values")
    check_int(fail, first_len, "first_len")
    check_int(fail, second_len, "second_len")
    if not 1 <= first_len <= len(values):
        fail("out_of_range:first_len")
    if not 1 <= second_len <= len(values) - first_len:
        fail("out_of_range:second_len")
    prefix = [0]
    for v in values:
        prefix.append(prefix[-1] + v)

    def left_best(length):
        # best window sum of `length` ending at or before each index
        best = [None] * len(values)
        run = None
        for end in range(length - 1, len(values)):
            cur = prefix[end + 1] - prefix[end + 1 - length]
            run = cur if run is None else max(run, cur)
            best[end] = run
        return best

    def pair_max(len_a, len_b):
        left = left_best(len_a)
        best = None
        run = None
        for start in range(len(values) - len_b, len_a - 1, -1):
            cur = prefix[start + len_b] - prefix[start]
            run = cur if run is None else max(run, cur)
            if left[start - 1] is not None:
                cand = left[start - 1] + run
                best = cand if best is None else max(best, cand)
        return best

    return max(pair_max(first_len, second_len),
               pair_max(second_len, first_len))

def range_sum_point_updates(items, ops):
    """Query results over an array that point updates mutate.

    ops holds ["update", index, delta] or ["query", left, right]
    rows; the answer is the list of query results in order, each
    the inclusive sum at that moment."""
    fail = make_fail("range_sum_point_updates")
    _int_list(fail, items, "items")
    check_items(fail, ops, "ops")
    if not ops:
        fail("empty:ops")
    n = len(items)
    parsed = []
    for k, op in enumerate(ops):
        if type(op) is not list or not op:
            fail("bad_shape:ops[%d]" % k)
        if op[0] == "update":
            if len(op) != 3:
                fail("bad_shape:ops[%d]" % k)
            check_int(fail, op[1], "ops[%d][1]" % k)
            check_int(fail, op[2], "ops[%d][2]" % k)
            if op[1] < 0 or op[1] >= n:
                fail("out_of_range:ops[%d]" % k)
            if op[2] < -MAX_VAL or op[2] > MAX_VAL:
                fail("out_of_range:ops[%d]" % k)
            parsed.append(("update", op[1], op[2]))
        elif op[0] == "query":
            if len(op) != 3:
                fail("bad_shape:ops[%d]" % k)
            check_int(fail, op[1], "ops[%d][1]" % k)
            check_int(fail, op[2], "ops[%d][2]" % k)
            if op[1] < 0 or op[2] >= n or op[1] > op[2]:
                fail("out_of_range:ops[%d]" % k)
            parsed.append(("query", op[1], op[2]))
        else:
            fail("bad_value:ops[%d]" % k)
    tree = [0] * (n + 1)
    for i, v in enumerate(items):
        j = i + 1
        while j <= n:
            tree[j] += v
            j += j & -j

    def add(i, delta):
        j = i + 1
        while j <= n:
            tree[j] += delta
            j += j & -j

    def prefix(i):
        total = 0
        j = i + 1
        while j > 0:
            total += tree[j]
            j -= j & -j
        return total

    out = []
    for kind, a, b in parsed:
        if kind == "update":
            add(a, b)
        else:
            out.append(prefix(b) - prefix(a - 1))
    return out

def count_subarrays_bounded_max(values, lo, hi):
    """Subarrays whose maximum lies between lo and hi inclusive.

    Counts subarrays capped at hi minus those capped below lo; a
    single pass extends each streak while values stay under the
    cap. lo must not exceed hi, and both stay inside 32-bit
    range."""
    fail = make_fail("count_subarrays_bounded_max")
    _int_list(fail, values, "values")
    check_int(fail, lo, "lo")
    check_int(fail, hi, "hi")
    if lo < -INT32_MAX - 1 or lo > INT32_MAX:
        fail("out_of_range:lo")
    if hi < -INT32_MAX - 1 or hi > INT32_MAX:
        fail("out_of_range:hi")
    if lo > hi:
        fail("bad_value:hi")

    def at_most(cap):
        total = run = 0
        for v in values:
            run = run + 1 if v <= cap else 0
            total += run
        return total

    return at_most(hi) - at_most(lo - 1)

def stock_span_list(items):
    """Per index, the length of the run ending there of values at
    or below items[i], itself included: the number of consecutive
    positions back to (but not past) the previous greater value."""
    fail = make_fail("stock_span_list")
    _int_list(fail, items, "items")
    out = []
    stack = []  # (value, span) pairs, strictly decreasing values
    for v in items:
        span = 1
        while stack and stack[-1][0] <= v:
            span += stack.pop()[1]
        stack.append((v, span))
        out.append(span)
    return out
