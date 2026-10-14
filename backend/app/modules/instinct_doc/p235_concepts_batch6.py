"""P235 concepts, batch 6 (data/validation, 51-60). Offline, stdlib only."""
from __future__ import annotations

from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)
from app.modules.instinct_doc.p235_concepts_batch4 import _frac


def flatten_one_level(lists):
    fail = make_fail("flatten_one_level")
    check_items(fail, lists, "lists")
    total = 0
    for i, sub in enumerate(lists):
        if type(sub) is not list:
            fail("bad_type:lists[%d]" % i)
        total += len(sub)
        if total > MAX_ITEMS:
            fail("too_many:flattened")
    out = []
    for i, sub in enumerate(lists):
        for j, v in enumerate(sub):
            check_int(fail, v, "lists[%d][%d]" % (i, j))
            out.append(v)
    return out


def zip_strict_equal(a, b):
    fail = make_fail("zip_strict_equal")
    check_items(fail, a, "a")
    check_items(fail, b, "b")
    if len(a) != len(b):
        fail("length_mismatch:%d!=%d" % (len(a), len(b)))
    return [[x, y] for x, y in zip(a, b)]


def dict_get_path(mapping, path):
    fail = make_fail("dict_get_path")
    if type(mapping) is not dict:
        fail("bad_type:mapping")
    check_items(fail, path, "path")
    if not path:
        fail("empty:path")
    node = mapping
    for i, key in enumerate(path):
        check_str(fail, key, "path[%d]" % i)
        if type(node) is not dict:
            fail("missing_path:path[%d] descends into non-dict" % i)
        if key not in node:
            fail("missing_path:%s" % key)
        node = node[key]
    return node


def sort_by_key_stable(records, key):
    fail = make_fail("sort_by_key_stable")
    check_items(fail, records, "records")
    check_str(fail, key, "key")
    for i, r in enumerate(records):
        if type(r) is not dict:
            fail("bad_type:records[%d]" % i)
        if key not in r:
            fail("missing_key:records[%d]" % i)
        check_str(fail, r[key], "records[%d].%s" % (i, key))
    return sorted(records, key=lambda r: r[key])


_PREDICATES = {
    "even": lambda v: v % 2 == 0,
    "odd": lambda v: v % 2 == 1,
    "positive": lambda v: v > 0,
    "negative": lambda v: v < 0,
    "zero": lambda v: v == 0,
}


def count_where_closed(items, predicate):
    fail = make_fail("count_where_closed")
    check_items(fail, items)
    check_str(fail, predicate, "predicate")
    if predicate not in _PREDICATES:
        fail("bad_value:predicate")
    pred = _PREDICATES[predicate]
    count = 0
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        if pred(v):
            count += 1
    return count


def _finite_numbers(fail, items):
    check_items(fail, items)
    out = []
    for i, v in enumerate(items):
        if type(v) is bool or type(v) not in (int, float):
            fail("bad_type:items[%d]" % i)
        if type(v) is float and (v != v or v in (float("inf"), float("-inf"))):
            fail("bad_value:items[%d]" % i)
        out.append(v)
    return out


def running_max(items):
    fail = make_fail("running_max")
    values = _finite_numbers(fail, items)
    out = []
    for v in values:
        out.append(v if not out else max(out[-1], v))
    return out


def argmax_index(items):
    fail = make_fail("argmax_index")
    values = _finite_numbers(fail, items)
    if not values:
        fail("empty:items")
    best = 0
    for i, v in enumerate(values):
        if v > values[best]:
            best = i
    return best


def split_at_index(items, index):
    fail = make_fail("split_at_index")
    check_items(fail, items)
    check_int(fail, index, "index")
    if index < 0 or index > len(items):
        fail("bad_value:index")
    return list(items[:index]), list(items[index:])


def sum_exact_ints(items):
    fail = make_fail("sum_exact_ints")
    check_items(fail, items)
    total = 0
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        total += v
    return total


def variance_exact(values):
    fail = make_fail("variance_exact")
    check_items(fail, values)
    if not values:
        fail("empty:values")
    fracs = [_frac(fail, v, "values[%d]" % i) for i, v in enumerate(values)]
    mean = sum(fracs, Fraction(0)) / len(fracs)
    return sum((v - mean) ** 2 for v in fracs) / len(fracs)
