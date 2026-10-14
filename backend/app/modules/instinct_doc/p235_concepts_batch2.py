"""P235 concepts, batch 2 (sets/maps). Offline, stdlib only. See batch 1
and the registry for the honest-scope contract."""
from __future__ import annotations

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)


def _str_list(fail, items, name="items"):
    check_items(fail, items, name)
    for i, v in enumerate(items):
        check_str(fail, v, "%s[%d]" % (name, i))
    return items


def set_disjoint_check(a, b):
    fail = make_fail("set_disjoint_check")
    _str_list(fail, a, "a")
    _str_list(fail, b, "b")
    return set(a).isdisjoint(b)


def frequency_table(items):
    fail = make_fail("frequency_table")
    _str_list(fail, items)
    counts = {}
    for v in items:
        counts[v] = counts.get(v, 0) + 1
    return {k: counts[k] for k in sorted(counts)}


def invert_mapping(mapping):
    fail = make_fail("invert_mapping")
    if type(mapping) is not dict:
        fail("bad_type:mapping")
    if len(mapping) > MAX_ITEMS:
        fail("too_many:mapping")
    out = {}
    for k, v in mapping.items():
        check_str(fail, k, "key")
        check_str(fail, v, "value[%s]" % k)
        if v in out:
            fail("not_injective:%s" % v)
        out[v] = k
    return out


def intersection_size(a, b):
    fail = make_fail("intersection_size")
    _str_list(fail, a, "a")
    _str_list(fail, b, "b")
    return len(set(a) & set(b))


def symmetric_difference_list(a, b):
    fail = make_fail("symmetric_difference_list")
    _str_list(fail, a, "a")
    _str_list(fail, b, "b")
    return sorted(set(a) ^ set(b))


def group_by_key(records, key):
    fail = make_fail("group_by_key")
    check_items(fail, records, "records")
    check_str(fail, key, "key")
    out = {}
    for i, r in enumerate(records):
        if type(r) is not dict:
            fail("bad_type:records[%d]" % i)
        if key not in r:
            fail("missing_key:records[%d]" % i)
        k = check_str(fail, r[key], "records[%d].%s" % (i, key))
        out.setdefault(k, []).append(r)
    return out


def count_distinct_casefold(items):
    fail = make_fail("count_distinct_casefold")
    _str_list(fail, items)
    return len({v.casefold() for v in items})


def first_duplicate(items):
    fail = make_fail("first_duplicate")
    _str_list(fail, items)
    seen = set()
    for v in items:
        if v in seen:
            return v
        seen.add(v)
    return None


def bucket_by_range(values, width):
    fail = make_fail("bucket_by_range")
    check_items(fail, values, "values")
    check_int(fail, width, "width")
    if width < 1:
        fail("bad_value:width")
    out = {}
    for i, v in enumerate(values):
        check_int(fail, v, "values[%d]" % i)
        out.setdefault(v // width, []).append(v)
    return out


def mode_exact(items):
    fail = make_fail("mode_exact")
    _str_list(fail, items)
    if not items:
        fail("empty:items")
    counts = {}
    for v in items:
        counts[v] = counts.get(v, 0) + 1
    top = max(counts.values())
    return {"modes": sorted(v for v, c in counts.items() if c == top),
            "count": top}
