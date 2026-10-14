"""P235 concepts, batch 12 (text/algorithms, 111-120). Offline, stdlib only."""
from __future__ import annotations

from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_LPS_LEN = 1_000


def _int_square_matrix(fail, matrix, name):
    check_items(fail, matrix, name)
    cells = 0
    width = None
    for i, row in enumerate(matrix):
        if type(row) is not list:
            fail("bad_type:%s[%d]" % (name, i))
        cells += len(row)
        if cells > MAX_ITEMS:
            fail("too_many:cells")
        if width is None:
            width = len(row)
        elif len(row) != width:
            fail("ragged:matrix")
        for j, v in enumerate(row):
            check_int(fail, v, "%s[%d][%d]" % (name, i, j))
    return width or 0


def run_length_decode(runs):
    fail = make_fail("run_length_decode")
    check_items(fail, runs, "runs")
    out = []
    for i, pair in enumerate(runs):
        if type(pair) is not list or len(pair) != 2:
            fail("bad_value:runs[%d]" % i)
        value, count = pair
        check_str(fail, value, "runs[%d][0]" % i)
        check_int(fail, count, "runs[%d][1]" % i)
        if count < 1:
            fail("bad_value:count")
        if len(out) + count > MAX_ITEMS:
            fail("too_many:output")
        out.extend([value] * count)
    return out


def string_rotation_check(a, b):
    fail = make_fail("string_rotation_check")
    check_str(fail, a, "a")
    check_str(fail, b, "b")
    if len(a) > MAX_ITEMS or len(b) > MAX_ITEMS:
        fail("too_many:text")
    if len(a) != len(b):
        return False
    return b in (a + a)


def longest_palindromic_substring_length(text):
    fail = make_fail("longest_palindromic_substring_length")
    check_str(fail, text, "text")
    if len(text) > MAX_LPS_LEN:
        fail("too_many:text")
    best = 0
    n = len(text)
    for center in range(2 * n - 1):
        left = center // 2
        right = left + center % 2
        while left >= 0 and right < n and text[left] == text[right]:
            left -= 1
            right += 1
        best = max(best, right - left - 1)
    return best


def count_vowels(text):
    fail = make_fail("count_vowels")
    check_str(fail, text, "text")
    if len(text) > MAX_ITEMS:
        fail("too_many:text")
    return sum(1 for ch in text.lower() if ch in "aeiou")


def second_largest_distinct(items):
    fail = make_fail("second_largest_distinct")
    check_items(fail, items, "items")
    first = second = None
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        if first is None or v > first:
            first, second = v, first
        elif v < first and (second is None or v > second):
            second = v
    return second


def majority_element(items):
    fail = make_fail("majority_element")
    check_items(fail, items, "items")
    candidate = count = None
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        if not count:
            candidate, count = v, 1
        elif v == candidate:
            count += 1
        else:
            count -= 1
    if candidate is None:
        return None
    return candidate if items.count(candidate) > len(items) // 2 else None


def rotate_matrix_90(matrix):
    fail = make_fail("rotate_matrix_90")
    width = _int_square_matrix(fail, matrix, "matrix")
    if not matrix:
        return []
    if width != len(matrix):
        fail("not_square:matrix")
    n = len(matrix)
    return [[matrix[n - 1 - j][i] for j in range(n)] for i in range(n)]


def identity_matrix_check(matrix):
    fail = make_fail("identity_matrix_check")
    width = _int_square_matrix(fail, matrix, "matrix")
    if not matrix or width != len(matrix):
        return False
    for i in range(len(matrix)):
        for j in range(len(matrix)):
            if matrix[i][j] != (1 if i == j else 0):
                return False
    return True


def moving_average_exact(items, k):
    fail = make_fail("moving_average_exact")
    check_items(fail, items, "items")
    check_int(fail, k, "k")
    if k < 1 or k > len(items):
        fail("bad_value:k")
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
    window = sum(items[:k])
    out = [Fraction(window, k)]
    for i in range(k, len(items)):
        window += items[i] - items[i - k]
        out.append(Fraction(window, k))
    return out


def unique_char_first_index(text):
    fail = make_fail("unique_char_first_index")
    check_str(fail, text, "text")
    if len(text) > MAX_ITEMS:
        fail("too_many:text")
    counts = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    for i, ch in enumerate(text):
        if counts[ch] == 1:
            return i
    return -1
