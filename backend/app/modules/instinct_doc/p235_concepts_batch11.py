"""P235 concepts, batch 11 (validation/DP, 101-110). Offline, stdlib only."""
from __future__ import annotations

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_TARGET = 10_000
MAX_AMOUNT = 1_000
MAX_LCS_LEN = 1_000
MAX_COINS = 100
_MAX_DIGITS = MAX_ITEMS


def luhn_check(digits):
    fail = make_fail("luhn_check")
    check_str(fail, digits, "digits")
    if not digits:
        fail("bad_value:digits")
    if len(digits) > _MAX_DIGITS:
        fail("too_many:digits")
    if not (digits.isascii() and digits.isdigit()):
        fail("bad_value:digits")
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = ord(ch) - 48
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def isbn10_check(isbn):
    fail = make_fail("isbn10_check")
    check_str(fail, isbn, "isbn")
    if len(isbn) != 10:
        fail("bad_value:isbn")
    total = 0
    for i, ch in enumerate(isbn):
        if "0" <= ch <= "9":
            d = ord(ch) - 48
        elif ch == "X" and i == 9:
            d = 10
        else:
            fail("bad_value:isbn")
        total += d * (10 - i)
    return total % 11 == 0


def triangle_type(a, b, c):
    fail = make_fail("triangle_type")
    check_int(fail, a, "a")
    check_int(fail, b, "b")
    check_int(fail, c, "c")
    sides = sorted((a, b, c))
    if sides[0] <= 0 or sides[0] + sides[1] <= sides[2]:
        fail("bad_value:sides")
    if a == b == c:
        return "equilateral"
    if a == b or b == c or a == c:
        return "isosceles"
    return "scalene"


def rect_overlap_area(r1, r2):
    fail = make_fail("rect_overlap_area")

    def _rect(rect, name):
        if type(rect) is not list or len(rect) != 4:
            fail("bad_value:rect")
        for i, v in enumerate(rect):
            check_int(fail, v, "%s[%d]" % (name, i))
        if rect[0] > rect[2] or rect[1] > rect[3]:
            fail("bad_value:rect")
        return rect

    _rect(r1, "r1")
    _rect(r2, "r2")
    width = min(r1[2], r2[2]) - max(r1[0], r2[0])
    height = min(r1[3], r2[3]) - max(r1[1], r2[1])
    if width <= 0 or height <= 0:
        return 0
    return width * height


def spiral_matrix_order(matrix):
    fail = make_fail("spiral_matrix_order")
    check_items(fail, matrix, "matrix")
    cells = 0
    width = None
    rows = []
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
        rows.append(list(row))
    out = []
    top, bottom, left, right = 0, len(rows) - 1, 0, (width or 0) - 1
    while top <= bottom and left <= right:
        out.extend(rows[top][left:right + 1])
        top += 1
        for r in range(top, bottom + 1):
            out.append(rows[r][right])
        right -= 1
        if top <= bottom:
            out.extend(reversed(rows[bottom][left:right + 1]))
            bottom -= 1
        if left <= right:
            for r in range(bottom, top - 1, -1):
                out.append(rows[r][left])
            left += 1
    return out


def subset_sum_exists(items, target):
    fail = make_fail("subset_sum_exists")
    check_items(fail, items, "items")
    check_int(fail, target, "target")
    if target < 0:
        fail("bad_value:target")
    if target > MAX_TARGET:
        fail("too_many:target")
    possible = {0}
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        if v < 0:
            fail("bad_value:items")
        if v > MAX_TARGET:
            fail("too_many:items")
        possible |= {s + v for s in possible if s + v <= target}
    return target in possible


def coin_change_count(coins, amount):
    fail = make_fail("coin_change_count")
    check_items(fail, coins, "coins")
    check_int(fail, amount, "amount")
    if not coins:
        fail("empty:coins")
    if len(coins) > MAX_COINS:
        fail("too_many:coins")
    if amount < 0:
        fail("bad_value:amount")
    if amount > MAX_AMOUNT:
        fail("too_many:amount")
    seen = set()
    for i, v in enumerate(coins):
        check_int(fail, v, "coins[%d]" % i)
        if v <= 0:
            fail("bad_value:coins")
        if v in seen:
            fail("duplicate:coins")
        seen.add(v)
    ways = [0] * (amount + 1)
    ways[0] = 1
    for coin in coins:
        for x in range(coin, amount + 1):
            ways[x] += ways[x - coin]
    return ways[amount]


def lcs_length(a, b):
    fail = make_fail("lcs_length")
    check_str(fail, a, "a")
    check_str(fail, b, "b")
    if len(a) > MAX_LCS_LEN or len(b) > MAX_LCS_LEN:
        fail("too_many:text")
    prev = [0] * (len(b) + 1)
    for ca in a:
        cur = [0]
        for j, cb in enumerate(b):
            cur.append(prev[j] + 1 if ca == cb else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]


def missing_number(items):
    fail = make_fail("missing_number")
    check_items(fail, items, "items")
    n = len(items)
    seen = set()
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        if v < 0 or v > n or v in seen:
            fail("bad_value:items")
        seen.add(v)
    return n * (n + 1) // 2 - sum(seen)


def two_sum_indices(items, target):
    fail = make_fail("two_sum_indices")
    check_items(fail, items, "items")
    check_int(fail, target, "target")
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
    seen = {}
    for j, v in enumerate(items):
        need = target - v
        if need in seen:
            return (seen[need], j)
        if v not in seen:
            seen[v] = j
    return None
