"""P235 concepts, batch 5 (logic/graph/misc). Offline, stdlib only."""
from __future__ import annotations

from datetime import date
from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)


def all_pairs_distinct(items):
    fail = make_fail("all_pairs_distinct")
    check_items(fail, items)
    for i, v in enumerate(items):
        check_str(fail, v, "items[%d]" % i)
    return len(set(items)) == len(items)


def _check_graph(fail, nodes, edges, prefix):
    check_items(fail, nodes, "nodes")
    check_items(fail, edges, "edges")
    names = []
    for i, n in enumerate(nodes):
        check_str(fail, n, "nodes[%d]" % i)
        if n in names:
            fail("duplicate_node:%s" % n)
        names.append(n)
    succ = {n: [] for n in names}
    for i, e in enumerate(edges):
        if type(e) not in (list, tuple) or len(e) != 2:
            fail("bad_type:edges[%d]" % i)
        a, b = e
        if a not in succ or b not in succ:
            fail("unknown_node:edges[%d]" % i)
        succ[a].append(b)
    return names, succ


def _topo(fail, names, succ):
    indeg = {n: 0 for n in names}
    for n in names:
        for m in succ[n]:
            indeg[m] += 1
    ready = [n for n in names if indeg[n] == 0]
    order = []
    while ready:
        n = ready.pop(0)
        order.append(n)
        for m in succ[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
    if len(order) != len(names):
        fail("cycle:graph has a cycle")
    return order


def reachability_set(adjacency, start):
    fail = make_fail("reachability_set")
    if type(adjacency) is not dict:
        fail("bad_type:adjacency")
    if len(adjacency) > MAX_ITEMS:
        fail("too_many:adjacency")
    check_str(fail, start, "start")
    if start not in adjacency:
        fail("unknown_start:%s" % start)
    for node, targets in adjacency.items():
        check_str(fail, node, "node")
        check_items(fail, targets, "adjacency[%s]" % node)
        for t in targets:
            check_str(fail, t, "target")
            if t not in adjacency:
                fail("unknown_node:%s" % t)
    seen = {start}
    queue = [start]
    while queue:
        n = queue.pop(0)
        for t in adjacency[n]:
            if t not in seen:
                seen.add(t)
                queue.append(t)
    return sorted(seen)


def dag_depth(nodes, edges):
    fail = make_fail("dag_depth")
    names, succ = _check_graph(fail, nodes, edges, "dag_depth")
    if not names:
        fail("empty:nodes")
    order = _topo(fail, names, succ)
    depth = {n: 1 for n in names}
    for n in order:
        for m in succ[n]:
            depth[m] = max(depth[m], depth[n] + 1)
    return max(depth.values())


def bracket_balance_check(text):
    fail = make_fail("bracket_balance_check")
    check_str(fail, text, "text")
    if len(text) > MAX_ITEMS * 10:
        fail("too_many:text")
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    for ch in text:
        if ch in "([{":
            stack.append(ch)
        elif ch in pairs:
            if not stack or stack.pop() != pairs[ch]:
                return False
    return not stack


def _parse_semver(fail, version, name):
    check_str(fail, version, name)
    parts = version.split(".")
    if len(parts) != 3:
        fail("bad_value:%s" % name)
    nums = []
    for p in parts:
        if not p.isdigit() or (len(p) > 1 and p.startswith("0")):
            fail("bad_value:%s" % name)
        nums.append(int(p))
    return tuple(nums)


def semver_compare(a, b):
    fail = make_fail("semver_compare")
    ta = _parse_semver(fail, a, "a")
    tb = _parse_semver(fail, b, "b")
    return (ta > tb) - (ta < tb)


def bit_flags_decode(value, names):
    fail = make_fail("bit_flags_decode")
    check_int(fail, value, "value")
    check_items(fail, names, "names")
    if not names:
        fail("empty:names")
    if len(names) > 64:
        fail("too_many:names")
    if value < 0:
        fail("bad_value:value")
    clean = []
    for i, n in enumerate(names):
        check_str(fail, n, "names[%d]" % i)
        if n in clean:
            fail("duplicate_name:%s" % n)
        clean.append(n)
    if value >= (1 << len(clean)):
        fail("excess_bits:value sets bits beyond the named flags")
    return {name: bool(value & (1 << i)) for i, name in enumerate(clean)}


def vote_threshold_check(yes, no, threshold):
    fail = make_fail("vote_threshold_check")
    check_int(fail, yes, "yes")
    check_int(fail, no, "no")
    if yes < 0 or no < 0:
        fail("bad_value:negative_count")
    check_str(fail, threshold, "threshold")
    try:
        thr = Fraction(threshold.strip())
    except (ValueError, ZeroDivisionError):
        fail("bad_value:threshold")
    if thr < 0 or thr > 1:
        fail("bad_value:threshold")
    total = yes + no
    if total == 0:
        return {"quorum_met": False, "passed": False,
                "share": Fraction(0), "threshold": thr}
    share = Fraction(yes, total)
    return {"quorum_met": True, "passed": share >= thr,
            "share": share, "threshold": thr}


def interval_overlap_count(intervals):
    fail = make_fail("interval_overlap_count")
    check_items(fail, intervals, "intervals")
    cleaned = []
    for i, iv in enumerate(intervals):
        if type(iv) not in (list, tuple) or len(iv) != 2:
            fail("bad_type:intervals[%d]" % i)
        a, b = iv
        check_int(fail, a, "intervals[%d][0]" % i)
        check_int(fail, b, "intervals[%d][1]" % i)
        if a > b:
            fail("bad_value:intervals[%d]" % i)
        cleaned.append((a, b))
    count = 0
    for i in range(len(cleaned)):
        for j in range(i + 1, len(cleaned)):
            (a1, b1), (a2, b2) = cleaned[i], cleaned[j]
            if a1 <= b2 and a2 <= b1:
                count += 1
    return count


def _parse_date(fail, text, name):
    check_str(fail, text, name)
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        fail("bad_value:%s" % name)


def date_ordinal_offset(date_a, date_b):
    fail = make_fail("date_ordinal_offset")
    a = _parse_date(fail, date_a, "date_a")
    b = _parse_date(fail, date_b, "date_b")
    return (b - a).days


def levenshtein_distance(a, b):
    fail = make_fail("levenshtein_distance")
    check_str(fail, a, "a")
    check_str(fail, b, "b")
    if len(a) > 1000 or len(b) > 1000:
        fail("too_many:length")
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]
