"""P235 concepts, batch 38 (simulation, compression, scheduling, 371-380).

Offline, stdlib only. Exact arithmetic; caps refuse before work.
"""
from __future__ import annotations

from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_OPS = 10_000
MAX_SYMBOLS = 200
MAX_JOBS = 1_000
MAX_DEADLINE = 10_000
MAX_PAIRS = 12
MAX_BRACKET_LEN = 10_000


def lru_cache_hits(ops, capacity):
    fail = make_fail("lru_cache_hits")
    check_items(fail, ops, "ops")
    if len(ops) > MAX_OPS:
        fail("too_many:ops")
    check_int(fail, capacity, "capacity")
    if capacity < 1 or capacity > 10_000:
        fail("bad_value:capacity")
    keys = []
    for i, v in enumerate(ops):
        check_int(fail, v, "ops[%d]" % i)
        keys.append(v)
    order = []  # most-recent at the end
    hits = 0
    for key in keys:
        if key in order:
            hits += 1
            order.remove(key)
            order.append(key)
            continue
        order.append(key)
        if len(order) > capacity:
            order.pop(0)
    return hits


def huffman_code_lengths(freqs):
    fail = make_fail("huffman_code_lengths")
    check_items(fail, freqs, "freqs")
    if not freqs:
        fail("empty:freqs")
    if len(freqs) > MAX_SYMBOLS:
        fail("too_many:freqs")
    vals = []
    for i, v in enumerate(freqs):
        check_int(fail, v, "freqs[%d]" % i)
        if v < 1:
            fail("bad_value:freqs[%d]" % i)
        vals.append(v)
    if len(vals) == 1:
        return [1]
    # heap items: (weight, smallest leaf index, node); node is an index
    # into the forest for deterministic tie-breaking
    import heapq
    depth = [0] * len(vals)
    heap = [(w, i, ("leaf", i)) for i, w in enumerate(vals)]
    heapq.heapify(heap)
    while len(heap) > 1:
        w1, _, n1 = heapq.heappop(heap)
        w2, _, n2 = heapq.heappop(heap)
        for node in (n1, n2):
            stack = [node]
            while stack:
                cur = stack.pop()
                if cur[0] == "leaf":
                    depth[cur[1]] += 1
                else:
                    stack.extend(cur[1:])
        lo = min(n1[1] if n1[0] == "leaf" else _min_leaf(n1),
                 n2[1] if n2[0] == "leaf" else _min_leaf(n2))
        heapq.heappush(heap, (w1 + w2, lo, ("node", n1, n2)))
    return depth


def _min_leaf(node):
    if node[0] == "leaf":
        return node[1]
    return min(_min_leaf(child) for child in node[1:])


def job_sequencing_max_profit(jobs):
    """Maximum profit scheduling unit jobs by deadline.

    Contract: scheduling is optional, so a job with profit <= 0 is
    never worth a slot and is skipped; deadlines above MAX_DEADLINE
    are refused before any allocation.
    """
    fail = make_fail("job_sequencing_max_profit")
    check_items(fail, jobs, "jobs")
    if len(jobs) > MAX_JOBS:
        fail("too_many:jobs")
    parsed = []
    for i, job in enumerate(jobs):
        if type(job) is not list or len(job) != 2:
            fail("bad_type:jobs[%d]" % i)
        check_int(fail, job[0], "jobs[%d][0]" % i)
        check_int(fail, job[1], "jobs[%d][1]" % i)
        if job[0] < 1 or job[0] > MAX_DEADLINE:
            fail("bad_value:jobs[%d]:deadline" % i)
        parsed.append((job[0], job[1]))
    # at most len(parsed) jobs can ever be scheduled
    slots = min(len(parsed), max((d for d, _p in parsed), default=0))
    slot = [False] * (slots + 1)
    total = 0
    for deadline, profit in sorted(parsed, key=lambda j: (-j[1], j[0])):
        if profit <= 0:
            continue
        for t in range(min(deadline, slots), 0, -1):
            if not slot[t]:
                slot[t] = True
                total += profit
                break
    return total


def generate_parentheses_list(n):
    fail = make_fail("generate_parentheses_list")
    check_int(fail, n, "n")
    if n < 0 or n > MAX_PAIRS:
        fail("bad_value:n")
    out = []

    def build(acc, opened, closed):
        if closed == n:
            out.append(acc)
            return
        if opened < n:
            build(acc + "(", opened + 1, closed)
        if closed < opened:
            build(acc + ")", opened, closed + 1)

    build("", 0, 0)
    return out


def bracket_max_nesting(text):
    fail = make_fail("bracket_max_nesting")
    check_str(fail, text, "text")
    if len(text) > MAX_BRACKET_LEN:
        fail("too_many:text")
    depth = 0
    best = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
            if depth > best:
                best = depth
        elif ch == ")":
            depth -= 1
            if depth < 0:
                fail("bad_value:unbalanced[%d]" % i)
        else:
            fail("bad_value:text[%d]" % i)
    if depth != 0:
        fail("bad_value:unbalanced")
    return best


def sliding_window_median_exact(items, k):
    fail = make_fail("sliding_window_median_exact")
    check_items(fail, items, "items")
    check_int(fail, k, "k")
    if k < 1:
        fail("bad_value:k")
    if len(items) > MAX_ITEMS:
        fail("too_many:items")
    if k > len(items):
        fail("bad_value:k_gt_len")
    vals = []
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        vals.append(v)
    out = []
    for start in range(len(vals) - k + 1):
        window = sorted(vals[start:start + k])
        mid = k // 2
        if k % 2 == 1:
            out.append(Fraction(window[mid]))
        else:
            out.append(Fraction(window[mid - 1] + window[mid], 2))
    return out


def clock_angle_exact(hour, minute):
    fail = make_fail("clock_angle_exact")
    check_int(fail, hour, "hour")
    check_int(fail, minute, "minute")
    if not (0 <= hour <= 23):
        fail("bad_value:hour")
    if not (0 <= minute <= 59):
        fail("bad_value:minute")
    h = hour % 12
    diff = abs(Fraction(30 * h) - Fraction(11 * minute, 2))
    return min(diff, Fraction(360) - diff)


def elevator_total_travel(start, requests):
    fail = make_fail("elevator_total_travel")
    check_int(fail, start, "start")
    if start < 0 or start > 10_000:
        fail("bad_value:start")
    check_items(fail, requests, "requests")
    if len(requests) > MAX_OPS:
        fail("too_many:requests")
    floors = []
    for i, v in enumerate(requests):
        check_int(fail, v, "requests[%d]" % i)
        if v < 0 or v > 10_000:
            fail("bad_value:requests[%d]" % i)
        floors.append(v)
    total = 0
    current = start
    for floor in floors:
        total += abs(floor - current)
        current = floor
    return total


def binary_watch_count(lit):
    fail = make_fail("binary_watch_count")
    check_int(fail, lit, "lit")
    if lit < 0 or lit > 10:
        fail("bad_value:lit")
    count = 0
    for hour in range(12):
        for minute in range(60):
            if bin(hour).count("1") + bin(minute).count("1") == lit:
                count += 1
    return count


def collatz_peak_value(n):
    fail = make_fail("collatz_peak_value")
    check_int(fail, n, "n")
    if n < 1 or n > 1_000_000:
        fail("bad_value:n")
    peak = n
    steps = 0
    while n != 1:
        if n % 2 == 0:
            n //= 2
        else:
            n = 3 * n + 1
        if n > peak:
            peak = n
        steps += 1
        if steps > 100_000:
            fail("too_many:steps")
    return peak
