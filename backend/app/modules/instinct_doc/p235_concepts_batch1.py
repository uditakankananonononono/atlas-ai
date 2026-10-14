"""P235 concepts, batch 1 (order/sequences). Offline, stdlib only.

Each concept is a pure function with typed validation (P235:<name>: refusal
codes), size caps before materialization, and no I/O. No concept claims any
intelligence; each is a small, honest, testable computation. Exact-arithmetic
concepts use Fraction and refuse floats.
"""
from __future__ import annotations

from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)


def topological_order(nodes, edges):
    fail = make_fail("topological_order")
    check_items(fail, nodes, "nodes")
    check_items(fail, edges, "edges")
    names = []
    for i, n in enumerate(nodes):
        check_str(fail, n, "nodes[%d]" % i)
        if not n:
            fail("empty:nodes[%d]" % i)
        if n in names:
            fail("duplicate_node:%s" % n)
        names.append(n)
    succ = {n: [] for n in names}
    indeg = {n: 0 for n in names}
    for i, e in enumerate(edges):
        if type(e) not in (list, tuple) or len(e) != 2:
            fail("bad_type:edges[%d]" % i)
        a, b = e
        if a not in succ or b not in succ:
            fail("unknown_node:edges[%d]" % i)
        succ[a].append(b)
        indeg[b] += 1
    position = {n: i for i, n in enumerate(names)}
    ready = sorted((n for n in names if indeg[n] == 0), key=position.get)
    out = []
    while ready:
        n = ready.pop(0)
        out.append(n)
        for m in succ[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
                ready.sort(key=position.get)
    if len(out) != len(names):
        fail("cycle:graph has a cycle")
    return out


def stable_partition_parity(items):
    fail = make_fail("stable_partition_parity")
    check_items(fail, items)
    evens, odds = [], []
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        (evens if v % 2 == 0 else odds).append(v)
    return {"evens": evens, "odds": odds}


def run_length_encode(items):
    fail = make_fail("run_length_encode")
    check_items(fail, items)
    out = []
    for i, v in enumerate(items):
        check_str(fail, v, "items[%d]" % i)
        if out and out[-1][0] == v:
            out[-1][1] += 1
        else:
            out.append([v, 1])
    return out


def sliding_window_max(items, k):
    fail = make_fail("sliding_window_max")
    check_items(fail, items)
    check_int(fail, k, "k")
    if k < 1 or k > len(items):
        fail("bad_value:k")
    cleaned = []
    for i, v in enumerate(items):
        if type(v) is bool or type(v) not in (int, float):
            fail("bad_type:items[%d]" % i)
        if type(v) is float and (v != v or v in (float("inf"), float("-inf"))):  # non-finite
            fail("bad_value:items[%d]" % i)
        cleaned.append(v)
    return [max(cleaned[j:j + k]) for j in range(len(cleaned) - k + 1)]


def merge_sorted_streams(streams):
    fail = make_fail("merge_sorted_streams")
    check_items(fail, streams, "streams")
    total = 0
    for si, s in enumerate(streams):
        check_items(fail, s, "streams[%d]" % si)
        total += len(s)
        if total > MAX_ITEMS:
            fail("too_many:aggregate")
        prev = None
        for i, v in enumerate(s):
            check_int(fail, v, "streams[%d][%d]" % (si, i))
            if prev is not None and v < prev:
                fail("unsorted:streams[%d]" % si)
            prev = v
    merged = []
    heads = [0] * len(streams)
    while True:
        best = None
        for si, s in enumerate(streams):
            if heads[si] < len(s) and (best is None or s[heads[si]] < best[0]):
                best = (s[heads[si]], si)
        if best is None:
            return merged
        merged.append(best[0])
        heads[best[1]] += 1


def dedupe_preserve_order(items):
    fail = make_fail("dedupe_preserve_order")
    check_items(fail, items)
    seen = set()
    out = []
    for i, v in enumerate(items):
        check_str(fail, v, "items[%d]" % i)
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def rotate_left_k(items, k):
    fail = make_fail("rotate_left_k")
    check_items(fail, items)
    check_int(fail, k, "k")
    if k < 0:
        fail("bad_value:k")
    if not items:
        return []
    k %= len(items)
    return list(items[k:]) + list(items[:k])


def chunked_batching(items, size):
    fail = make_fail("chunked_batching")
    check_items(fail, items)
    check_int(fail, size, "size")
    if size < 1:
        fail("bad_value:size")
    return [list(items[i:i + size]) for i in range(0, len(items), size)]


def pairwise_deltas(items):
    fail = make_fail("pairwise_deltas")
    check_items(fail, items)
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
    return [items[i + 1] - items[i] for i in range(len(items) - 1)]


def _to_fraction(fail, v, name):
    if type(v) is int:
        return Fraction(v)
    if type(v) is str:
        parts = v.strip().split("/")
        try:
            if len(parts) == 1:
                return Fraction(int(parts[0]))
            if len(parts) == 2:
                num, den = int(parts[0]), int(parts[1])
                if den == 0:
                    fail("bad_value:%s" % name)
                return Fraction(num, den)
        except ValueError:
            fail("bad_value:%s" % name)
    fail("bad_type:%s" % name)


def prefix_sums_fraction(items):
    fail = make_fail("prefix_sums_fraction")
    check_items(fail, items)
    total = Fraction(0)
    out = []
    for i, v in enumerate(items):
        total += _to_fraction(fail, v, "items[%d]" % i)
        out.append(total)
    return out
