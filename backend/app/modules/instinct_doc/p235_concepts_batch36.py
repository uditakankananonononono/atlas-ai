"""P235 concepts, batch 36 (classic utilities IV, 351-360).

Offline, stdlib only. Exact arithmetic (int / Fraction); caps refuse
before work.
"""
from __future__ import annotations

from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_TOKENS = 1_000
MAX_INTERVALS = 1_000
MAX_GRID = 10_000
OPS = ("+", "-", "*", "/")


def _check_tokens(fail, tokens, name):
    check_items(fail, tokens, name)
    if len(tokens) > MAX_TOKENS:
        fail("too_many:%s" % name)
    for i, t in enumerate(tokens):
        if type(t) is bool or not isinstance(t, (int, str)):
            fail("bad_type:%s[%d]" % (name, i))


def _apply(fail, op, x, y):
    if op == "+":
        return x + y
    if op == "-":
        return x - y
    if op == "*":
        return x * y
    if y == 0:
        fail("bad_value:division_by_zero")
    return Fraction(x, y)


def evaluate_rpn(tokens):
    fail = make_fail("evaluate_rpn")
    _check_tokens(fail, tokens, "tokens")
    if not tokens:
        fail("empty:tokens")
    stack = []
    for i, t in enumerate(tokens):
        if type(t) is int:
            stack.append(t)
            continue
        if type(t) is not str or t not in OPS:
            fail("bad_value:tokens[%d]" % i)
        if len(stack) < 2:
            fail("bad_value:underflow")
        y = stack.pop()
        x = stack.pop()
        stack.append(_apply(fail, t, x, y))
    if len(stack) != 1:
        fail("bad_value:trailing")
    return stack[0] if type(stack[0]) is int else stack[0]


def infix_to_postfix(tokens):
    fail = make_fail("infix_to_postfix")
    _check_tokens(fail, tokens, "tokens")
    if not tokens:
        fail("empty:tokens")
    prec = {"+": 1, "-": 1, "*": 2, "/": 2}
    out = []
    stack = []
    expect_operand = True
    for i, t in enumerate(tokens):
        if type(t) is int:
            if not expect_operand:
                fail("bad_value:syntax")
            out.append(t)
            expect_operand = False
        elif t == "(":
            if not expect_operand:
                fail("bad_value:syntax")
            stack.append(t)
        elif t == ")":
            if expect_operand:
                fail("bad_value:syntax")
            while stack and stack[-1] != "(":
                out.append(stack.pop())
            if not stack:
                fail("bad_value:paren")
            stack.pop()
            expect_operand = False
        elif type(t) is str and t in OPS:
            if expect_operand:
                fail("bad_value:syntax")
            while (stack and stack[-1] != "("
                   and prec[stack[-1]] >= prec[t]):
                out.append(stack.pop())
            stack.append(t)
            expect_operand = True
        else:
            fail("bad_value:tokens[%d]" % i)
    if expect_operand:
        fail("bad_value:syntax")
    while stack:
        top = stack.pop()
        if top == "(":
            fail("bad_value:paren")
        out.append(top)
    return out


def _check_intervals(fail, intervals):
    check_items(fail, intervals, "intervals")
    if len(intervals) > MAX_INTERVALS:
        fail("too_many:intervals")
    out = []
    for i, iv in enumerate(intervals):
        if type(iv) is not list or len(iv) != 2:
            fail("bad_type:intervals[%d]" % i)
        check_int(fail, iv[0], "intervals[%d][0]" % i)
        check_int(fail, iv[1], "intervals[%d][1]" % i)
        if iv[0] >= iv[1]:
            fail("bad_value:intervals[%d]" % i)
        out.append((iv[0], iv[1]))
    return out


def activity_selection_count(intervals):
    fail = make_fail("activity_selection_count")
    ivs = _check_intervals(fail, intervals)
    count = 0
    last_end = None
    for start, end in sorted(ivs, key=lambda iv: (iv[1], iv[0])):
        if last_end is None or start >= last_end:
            count += 1
            last_end = end
    return count


def interval_partition_min_rooms(intervals):
    fail = make_fail("interval_partition_min_rooms")
    ivs = _check_intervals(fail, intervals)
    events = []
    for start, end in ivs:
        events.append((start, 1))
        events.append((end, -1))
    events.sort(key=lambda e: (e[0], e[1]))
    best = 0
    current = 0
    for _when, delta in events:
        current += delta
        if current > best:
            best = current
    return best


def next_permutation_step(items):
    fail = make_fail("next_permutation_step")
    check_items(fail, items, "items")
    if len(items) > MAX_ITEMS:
        fail("too_many:items")
    vals = []
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        vals.append(v)
    n = len(vals)
    if n < 2:
        return None
    i = n - 2
    while i >= 0 and vals[i] >= vals[i + 1]:
        i -= 1
    if i < 0:
        return None
    j = n - 1
    while vals[j] <= vals[i]:
        j -= 1
    out = vals[:]
    out[i], out[j] = out[j], out[i]
    out[i + 1:] = reversed(out[i + 1:])
    return out


def gray_code_render(bits):
    fail = make_fail("gray_code_render")
    check_int(fail, bits, "bits")
    if bits < 1 or bits > 16:
        fail("bad_value:bits")
    codes = ["0", "1"]
    for _ in range(1, bits):
        codes = (["0" + c for c in codes]
                 + ["1" + c for c in reversed(codes)])
    return codes


def multiply_digit_strings(a, b):
    fail = make_fail("multiply_digit_strings")
    check_str(fail, a, "a")
    check_str(fail, b, "b")
    for name, s in (("a", a), ("b", b)):
        if not s or not s.isascii() or not all(
                "0" <= ch <= "9" for ch in s):
            fail("bad_value:%s" % name)
        if len(s) > 1 and s[0] == "0":
            fail("bad_value:%s:leading_zero" % name)
        if len(s) > MAX_TOKENS:
            fail("too_many:%s" % name)
    da = [ord(c) - 48 for c in a]
    db = [ord(c) - 48 for c in b]
    acc = [0] * (len(da) + len(db))
    for i in range(len(da) - 1, -1, -1):
        for j in range(len(db) - 1, -1, -1):
            acc[i + j + 1] += da[i] * db[j]
    for k in range(len(acc) - 1, 0, -1):
        acc[k - 1] += acc[k] // 10
        acc[k] %= 10
    text = "".join(str(d) for d in acc).lstrip("0")
    return text if text else "0"


def game_of_life_step(grid):
    fail = make_fail("game_of_life_step")
    check_items(fail, grid, "grid")
    if not grid:
        fail("empty:grid")
    width = None
    cells = 0
    rows = []
    for i, row in enumerate(grid):
        check_items(fail, row, "grid[%d]" % i)
        if not row:
            fail("empty:grid[%d]" % i)
        if width is None:
            width = len(row)
        elif len(row) != width:
            fail("ragged:grid")
        cells += len(row)
        if cells > MAX_GRID:
            fail("too_many:grid")
        vals = []
        for j, v in enumerate(row):
            check_int(fail, v, "grid[%d][%d]" % (i, j))
            if v not in (0, 1):
                fail("bad_value:grid[%d][%d]" % (i, j))
            vals.append(v)
        rows.append(vals)
    h, w = len(rows), width
    out = []
    for r in range(h):
        new_row = []
        for c in range(w):
            live = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < h and 0 <= cc < w:
                        live += rows[rr][cc]
            if rows[r][c] == 1:
                new_row.append(1 if live in (2, 3) else 0)
            else:
                new_row.append(1 if live == 3 else 0)
        out.append(new_row)
    return out


def max_subarray_circular(items):
    fail = make_fail("max_subarray_circular")
    check_items(fail, items, "items")
    if not items:
        fail("empty:items")
    if len(items) > MAX_ITEMS:
        fail("too_many:items")
    vals = []
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        vals.append(v)
    best_straight = vals[0]
    run = 0
    for v in vals:
        run = max(run + v, v)
        best_straight = max(best_straight, run)
    total = sum(vals)
    worst_straight = vals[0]
    run = 0
    for v in vals:
        run = min(run + v, v)
        worst_straight = min(worst_straight, run)
    if worst_straight == total:
        return best_straight
    return max(best_straight, total - worst_straight)


def three_way_partition(items, pivot):
    fail = make_fail("three_way_partition")
    check_items(fail, items, "items")
    if len(items) > MAX_ITEMS:
        fail("too_many:items")
    check_int(fail, pivot, "pivot")
    vals = []
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        vals.append(v)
    less = []
    equal = []
    greater = []
    for v in vals:
        if v < pivot:
            less.append(v)
        elif v > pivot:
            greater.append(v)
        else:
            equal.append(v)
    return less + equal + greater
