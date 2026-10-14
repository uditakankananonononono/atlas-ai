"""P235 concepts, batch 44 (text checks, greedy sim, 431-440).

Offline, stdlib only. Exact arithmetic; caps refuse before work.
"""
from __future__ import annotations

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_TEXT = 10_000
MAX_WORD = 100
MAX_LISTS = 100


def _ascii_alpha(fail, text, name):
    if not text.isascii() or not text.isalpha():
        fail("bad_value:%s" % name)


def score_of_parentheses(text):
    """Score of a balanced paren string: ()=1, AB=A+B, (A)=2*A."""
    fail = make_fail("score_of_parentheses")
    check_str(fail, text, "text")
    if text == "":
        fail("empty:text")
    if len(text) > MAX_TEXT:
        fail("too_many:text")
    depth = 0
    total = 0
    prev = None
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                fail("bad_value:unbalanced[%d]" % i)
            if prev == "(":
                total += 2 ** (depth)
        else:
            fail("bad_value:char[%d]" % i)
        prev = ch
    if depth != 0:
        fail("bad_value:unbalanced")
    return total


def shortest_completing_word(license_plate, words):
    """Shortest word covering the plate's letters, ties by order.

    Refuses words longer than MAX_WORD (100) before any counting.
    """
    fail = make_fail("shortest_completing_word")
    check_str(fail, license_plate, "license_plate")
    if len(license_plate) > MAX_TEXT:
        fail("too_many:license_plate")
    need = {}
    for ch in license_plate.lower():
        if ch.isascii() and ch.isalpha():
            need[ch] = need.get(ch, 0) + 1
        elif ch.isascii() and (ch.isdigit() or ch == " "):
            continue
        else:
            fail("bad_value:license_plate")
    if not need:
        fail("empty:license_plate")
    check_items(fail, words, "words")
    if not words:
        fail("empty:words")
    if len(words) > MAX_ITEMS:
        fail("too_many:words")
    best = None
    for i, w in enumerate(words):
        check_str(fail, w, "words[%d]" % i)
        if w == "":
            fail("empty:words[%d]" % i)
        if len(w) > MAX_WORD:
            fail("too_long:words[%d]" % i)
        if not w.isascii() or not w.isalpha():
            fail("bad_value:words[%d]" % i)
        have = {}
        for ch in w.lower():
            have[ch] = have.get(ch, 0) + 1
        if all(have.get(c, 0) >= n for c, n in need.items()):
            if best is None or len(w) < len(best):
                best = w
    if best is None:
        fail("bad_value:no_match")
    return best


def palindrome_one_delete(text):
    """True when removing at most one char makes a palindrome."""
    fail = make_fail("palindrome_one_delete")
    check_str(fail, text, "text")
    if text == "":
        fail("empty:text")
    if len(text) > MAX_TEXT:
        fail("too_many:text")

    def is_pal(lo, hi):
        while lo < hi:
            if text[lo] != text[hi]:
                return False
            lo += 1
            hi -= 1
        return True

    lo, hi = 0, len(text) - 1
    while lo < hi:
        if text[lo] != text[hi]:
            return is_pal(lo + 1, hi) or is_pal(lo, hi - 1)
        lo += 1
        hi -= 1
    return True


def backspace_string_compare(a, b):
    """True when both texts are equal after # backspace processing."""
    fail = make_fail("backspace_string_compare")
    check_str(fail, a, "a")
    check_str(fail, b, "b")
    if len(a) > MAX_TEXT or len(b) > MAX_TEXT:
        fail("too_many:text")

    def build(text):
        out = []
        for ch in text:
            if ch == "#":
                if out:
                    out.pop()
            else:
                out.append(ch)
        return "".join(out)

    return build(a) == build(b)


def buddy_strings_check(a, b):
    """True when one swap of two chars in a turns it into b."""
    fail = make_fail("buddy_strings_check")
    check_str(fail, a, "a")
    check_str(fail, b, "b")
    if len(a) > MAX_TEXT or len(b) > MAX_TEXT:
        fail("too_many:text")
    if len(a) != len(b):
        return False
    diff = [i for i in range(len(a)) if a[i] != b[i]]
    if not diff:
        return len(set(a)) < len(a)
    if len(diff) != 2:
        return False
    i, j = diff
    return a[i] == b[j] and a[j] == b[i]


def reverse_only_letters(text):
    """Reverse the ASCII letters in place; everything else stays."""
    fail = make_fail("reverse_only_letters")
    check_str(fail, text, "text")
    if len(text) > MAX_TEXT:
        fail("too_many:text")
    chars = list(text)
    lo, hi = 0, len(chars) - 1
    while lo < hi:
        a_letter = chars[lo].isascii() and chars[lo].isalpha()
        b_letter = chars[hi].isascii() and chars[hi].isalpha()
        if not a_letter:
            lo += 1
        elif not b_letter:
            hi -= 1
        else:
            chars[lo], chars[hi] = chars[hi], chars[lo]
            lo += 1
            hi -= 1
    return "".join(chars)


def lemonade_change_possible(bills):
    """True when every customer can be given correct change.

    Every bill is validated (int in {5, 10, 20}) before the
    simulation runs, so a bad bill is never masked by an early
    False.
    """
    fail = make_fail("lemonade_change_possible")
    check_items(fail, bills, "bills")
    if not bills:
        fail("empty:bills")
    if len(bills) > MAX_ITEMS:
        fail("too_many:bills")
    # validate every bill before any change is simulated, so an
    # impossible queue cannot mask a bad bill later in the list
    for i, b in enumerate(bills):
        check_int(fail, b, "bills[%d]" % i)
        if b not in (5, 10, 20):
            fail("bad_value:bills[%d]" % i)
    five = 0
    ten = 0
    for b in bills:
        if b == 5:
            five += 1
        elif b == 10:
            if five < 1:
                return False
            five -= 1
            ten += 1
        else:
            if ten >= 1 and five >= 1:
                ten -= 1
                five -= 1
            elif five >= 3:
                five -= 3
            else:
                return False
    return True


def fair_candy_swap_sizes(alice, bob):
    """One exchanged pair equalizing both sums; smallest |a| then a."""
    fail = make_fail("fair_candy_swap_sizes")
    a_vals = []
    check_items(fail, alice, "alice")
    check_items(fail, bob, "bob")
    if not alice or not bob:
        fail("empty:input")
    if len(alice) > MAX_ITEMS or len(bob) > MAX_ITEMS:
        fail("too_many:input")
    for i, v in enumerate(alice):
        check_int(fail, v, "alice[%d]" % i)
        if v < 1:
            fail("bad_value:alice[%d]" % i)
        a_vals.append(v)
    b_set = set()
    b_sum = 0
    for i, v in enumerate(bob):
        check_int(fail, v, "bob[%d]" % i)
        if v < 1:
            fail("bad_value:bob[%d]" % i)
        b_set.add(v)
        b_sum += v
    diff = sum(a_vals) - b_sum
    if diff % 2 != 0:
        fail("bad_value:no_swap")
    half = diff // 2
    best = None
    for a in sorted(set(a_vals)):
        b = a - half
        if b in b_set:
            cand = [a, b]
            if best is None or (abs(a), a) < (abs(best[0]), best[0]):
                best = cand
    if best is None:
        fail("bad_value:no_swap")
    return best


def projection_area_3d(grid):
    """Area of the three orthographic projections of the cube stack."""
    fail = make_fail("projection_area_3d")
    check_items(fail, grid, "grid")
    if not grid:
        fail("empty:grid")
    rows = []
    width = None
    cells = 0
    for r, row in enumerate(grid):
        check_items(fail, row, "grid[%d]" % r)
        if width is None:
            width = len(row)
            if width == 0:
                fail("bad_value:grid[%d]:empty_row" % r)
        elif len(row) != width:
            fail("bad_value:grid[%d]:ragged" % r)
        cells += len(row)
        if cells > 40_000:
            fail("too_many:grid")
        vals = []
        for c, v in enumerate(row):
            check_int(fail, v, "grid[%d][%d]" % (r, c))
            if v < 0:
                fail("bad_value:grid[%d][%d]" % (r, c))
            vals.append(v)
        rows.append(vals)
    top = sum(1 for row in rows for v in row if v > 0)
    front = sum(max(col) for col in zip(*rows))
    side = sum(max(row) for row in rows)
    return top + front + side


def smallest_range_cover(lists):
    """Tightest [lo, hi] covering one value from each sorted list."""
    fail = make_fail("smallest_range_cover")
    check_items(fail, lists, "lists")
    if not lists:
        fail("empty:lists")
    if len(lists) > MAX_LISTS:
        fail("too_many:lists")
    import heapq
    heap = []
    hi = None
    total = 0
    for i, lst in enumerate(lists):
        check_items(fail, lst, "lists[%d]" % i)
        if not lst:
            fail("empty:lists[%d]" % i)
        if len(lst) > MAX_ITEMS:
            fail("too_many:lists[%d]" % i)
        total += len(lst)
        if total > 100_000:
            fail("too_many:lists")
        prev = None
        for j, v in enumerate(lst):
            check_int(fail, v, "lists[%d][%d]" % (i, j))
            if prev is not None and v < prev:
                fail("bad_value:lists[%d]:not_sorted" % i)
            prev = v
        heap.append((lst[0], i, 0))
        if hi is None or lst[0] > hi:
            hi = lst[0]
    heapq.heapify(heap)
    best = None
    while True:
        lo, i, j = heapq.heappop(heap)
        if best is None or hi - lo < best[1] - best[0]:
            best = [lo, hi]
        if j + 1 == len(lists[i]):
            return best
        nxt = lists[i][j + 1]
        if nxt > hi:
            hi = nxt
        heapq.heappush(heap, (nxt, i, j + 1))
