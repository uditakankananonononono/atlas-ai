"""P235 concepts, batch 13 (data structures/streams, 121-130).
Offline, stdlib only."""
from __future__ import annotations

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, make_fail)

MAX_FLATTEN_DEPTH = 1_000


def flatten_nested_any(items):
    fail = make_fail("flatten_nested_any")
    check_items(fail, items, "items")
    nodes = 1  # the root list itself
    out = []
    stack = [(iter(items), 0)]
    while stack:
        it, depth = stack[-1]
        if depth >= MAX_FLATTEN_DEPTH:
            fail("too_many:depth")
        advanced = False
        for v in it:
            advanced = True
            nodes += 1
            if nodes > MAX_ITEMS:
                fail("too_many:nodes")
            if type(v) is list:
                stack.append((iter(v), depth + 1))
                break
            check_int(fail, v, "item")
            out.append(v)
        if not advanced:
            stack.pop()
    return out


def zip_longest_fill(a, b, fill):
    fail = make_fail("zip_longest_fill")
    check_items(fail, a, "a")
    check_items(fail, b, "b")
    for i, v in enumerate(a):
        check_int(fail, v, "a[%d]" % i)
    for i, v in enumerate(b):
        check_int(fail, v, "b[%d]" % i)
    n = max(len(a), len(b))
    return [[a[i] if i < len(a) else fill,
             b[i] if i < len(b) else fill] for i in range(n)]


def take_every_nth(items, n):
    fail = make_fail("take_every_nth")
    check_items(fail, items, "items")
    check_int(fail, n, "n")
    if n < 1:
        fail("bad_value:n")
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
    return items[::n]


def interleave_lists(a, b):
    fail = make_fail("interleave_lists")
    check_items(fail, a, "a")
    check_items(fail, b, "b")
    for i, v in enumerate(a):
        check_int(fail, v, "a[%d]" % i)
    for i, v in enumerate(b):
        check_int(fail, v, "b[%d]" % i)
    out = []
    for i in range(max(len(a), len(b))):
        if i < len(a):
            out.append(a[i])
        if i < len(b):
            out.append(b[i])
    return out


def first_index_of(items, target):
    fail = make_fail("first_index_of")
    check_items(fail, items, "items")
    check_int(fail, target, "target")
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
    for i, v in enumerate(items):
        if v == target:
            return i
    return -1


def last_occurrence_index(items, target):
    fail = make_fail("last_occurrence_index")
    check_items(fail, items, "items")
    check_int(fail, target, "target")
    found = -1
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        if v == target:
            found = i
    return found


def cumulative_product_exact(items):
    fail = make_fail("cumulative_product_exact")
    check_items(fail, items, "items")
    out = []
    acc = 1
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        acc *= v
        out.append(acc)
    return out


def max_min_difference(items):
    fail = make_fail("max_min_difference")
    check_items(fail, items, "items")
    if not items:
        fail("empty:items")
    lo = hi = None
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        lo = v if lo is None else min(lo, v)
        hi = v if hi is None else max(hi, v)
    return hi - lo


def rank_of_values(items):
    fail = make_fail("rank_of_values")
    check_items(fail, items, "items")
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
    ordered = sorted(items, reverse=True)
    first = {}
    for i, v in enumerate(ordered):
        if v not in first:
            first[v] = i + 1
    return [first[v] for v in items]


def matrix_vector_multiply(matrix, vector):
    fail = make_fail("matrix_vector_multiply")
    check_items(fail, matrix, "matrix")
    check_items(fail, vector, "vector")
    if not matrix or not vector:
        fail("empty:input")
    width = None
    cells = 0
    for i, row in enumerate(matrix):
        if type(row) is not list:
            fail("bad_type:matrix[%d]" % i)
        cells += len(row)
        if cells > MAX_ITEMS:
            fail("too_many:cells")
        if width is None:
            width = len(row)
        elif len(row) != width:
            fail("ragged:matrix")
        for j, v in enumerate(row):
            check_int(fail, v, "matrix[%d][%d]" % (i, j))
    for i, v in enumerate(vector):
        check_int(fail, v, "vector[%d]" % i)
    if width != len(vector):
        fail("dimension_mismatch")
    return [sum(row[j] * vector[j] for j in range(width)) for row in matrix]
