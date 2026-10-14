"""P235 concepts batch 31 (concepts 301-310, strings/DP classics) - ten
new small deterministic concepts. 301-310 of the doc's 1000 (anchor
P235|L184). Exact arithmetic; inputs bounded; refusal codes
P235:<name>:<code>.
"""
from __future__ import annotations

from fractions import Fraction

from .p235_concepts_batch1 import MAX_ITEMS, check_int, check_str, make_fail

MAX_TEXT = 1_000
MAX_DIM = 256
MAX_LEN = 1_000
MAX_HEIGHT = 10_000


def jaro_similarity_exact(a, b):
    """Exact Jaro similarity in [0, 1] as a Fraction; matches are
    characters equal within half the longer length, transpositions are
    matched characters out of order."""
    fail = make_fail("jaro_similarity_exact")
    check_str(fail, a, "a")
    check_str(fail, b, "b")
    if len(a) > MAX_TEXT:
        fail("too_many:a")
    if len(b) > MAX_TEXT:
        fail("too_many:b")
    if a == b:
        return Fraction(1)
    if not a or not b:
        return Fraction(0)
    window = max(len(a), len(b)) // 2 - 1
    window = max(window, 0)
    used_a = [False] * len(a)
    used_b = [False] * len(b)
    matches = 0
    for i, ch in enumerate(a):
        lo = max(0, i - window)
        hi = min(len(b), i + window + 1)
        for j in range(lo, hi):
            if not used_b[j] and b[j] == ch:
                used_a[i] = True
                used_b[j] = True
                matches += 1
                break
    if matches == 0:
        return Fraction(0)
    transposed = 0
    j = 0
    for i in range(len(a)):
        if used_a[i]:
            while not used_b[j]:
                j += 1
            if a[i] != b[j]:
                transposed += 1
            j += 1
    m = matches
    # exact: transpositions are half the out-of-order count, possibly a
    # half-integer, kept as a Fraction
    t = Fraction(transposed, 2)
    return Fraction(Fraction(m, len(a)) + Fraction(m, len(b))
                    + Fraction(m - t, m), 3)


def prefix_function(text):
    """KMP failure array: for each prefix end, the length of the longest
    proper prefix of the prefix that is also its suffix."""
    fail = make_fail("prefix_function")
    check_str(fail, text, "text")
    if not text:
        fail("bad_value:text")
    if len(text) > MAX_ITEMS:
        fail("too_many:text")
    pi = [0] * len(text)
    k = 0
    for i in range(1, len(text)):
        while k and text[i] != text[k]:
            k = pi[k - 1]
        if text[i] == text[k]:
            k += 1
        pi[i] = k
    return pi


def _check_matrix(fail, name, rows):
    if type(rows) is not list or not rows:
        fail("bad_value:" + name)
    if len(rows) > MAX_DIM:
        fail("too_many:" + name)
    width = None
    for i, row in enumerate(rows):
        if type(row) is not list or not row:
            fail("bad_value:%s[%d]" % (name, i))
        if len(row) > MAX_DIM:
            fail("too_many:%s[%d]" % (name, i))
        if width is None:
            width = len(row)
        elif len(row) != width:
            fail("bad_value:" + name)
        for j, v in enumerate(row):
            check_int(fail, v, "%s[%d][%d]" % (name, i, j))
    return width


def saddle_point_find(rows):
    """First [row, col] in row-major order that is the minimum of its
    row and the maximum of its column, or -1 when none exists."""
    fail = make_fail("saddle_point_find")
    width = _check_matrix(fail, "rows", rows)
    for i, row in enumerate(rows):
        low = min(row)
        for j in range(width):
            if row[j] == low and all(rows[r][j] <= low
                                     for r in range(len(rows))):
                return [i, j]
    return -1


def toeplitz_check(rows):
    """Whether every descending diagonal of a rectangular int matrix is
    constant."""
    fail = make_fail("toeplitz_check")
    width = _check_matrix(fail, "rows", rows)
    for i in range(1, len(rows)):
        for j in range(1, width):
            if rows[i][j] != rows[i - 1][j - 1]:
                return False
    return True


def _check_heights(fail, name, values, allow_empty):
    if type(values) is not list:
        fail("bad_type:" + name)
    if not values and not allow_empty:
        fail("empty:" + name)
    if len(values) > MAX_LEN:
        fail("too_many:" + name)
    for i, v in enumerate(values):
        check_int(fail, v, "%s[%d]" % (name, i))
        if v < 0 or v > MAX_HEIGHT:
            fail("bad_value:%s[%d]" % (name, i))


def histogram_largest_rect(heights):
    """Largest rectangle area inside the histogram of non-negative bar
    heights (monotonic stack)."""
    fail = make_fail("histogram_largest_rect")
    _check_heights(fail, "heights", heights, allow_empty=False)
    best = 0
    stack = []
    for i, h in enumerate(heights + [0]):
        while stack and heights[stack[-1]] > h:
            top = stack.pop()
            left = stack[-1] if stack else -1
            best = max(best, heights[top] * (i - left - 1))
        stack.append(i)
    return best


def trap_rain_water(heights):
    """Units of water trapped between bars after rain (two pointers)."""
    fail = make_fail("trap_rain_water")
    _check_heights(fail, "heights", heights, allow_empty=True)
    left, right = 0, len(heights) - 1
    max_left = max_right = 0
    total = 0
    while left < right:
        if heights[left] <= heights[right]:
            max_left = max(max_left, heights[left])
            total += max_left - heights[left]
            left += 1
        else:
            max_right = max(max_right, heights[right])
            total += max_right - heights[right]
            right -= 1
    return total


def next_greater_elements(values):
    """For each position, the nearest strictly greater value to its
    right, or -1 when none exists (monotonic stack)."""
    fail = make_fail("next_greater_elements")
    if type(values) is not list:
        fail("bad_type:values")
    if len(values) > MAX_LEN:
        fail("too_many:values")
    for i, v in enumerate(values):
        check_int(fail, v, "values[%d]" % i)
    out = [-1] * len(values)
    stack = []
    for i, v in enumerate(values):
        while stack and values[stack[-1]] < v:
            out[stack.pop()] = v
        stack.append(i)
    return out


def house_robber_max(values):
    """Maximum sum of a subset of non-negative values with no two
    adjacent positions."""
    fail = make_fail("house_robber_max")
    _check_heights(fail, "values", values, allow_empty=True)
    take = skip = 0
    for v in values:
        take, skip = skip + v, max(take, skip)
    return max(take, skip)


def shuffle_check(a, b, candidate):
    """Whether candidate is an interleaving of a and b: both appear as
    subsequences that together cover it exactly (dynamic programming)."""
    fail = make_fail("shuffle_check")
    check_str(fail, a, "a")
    check_str(fail, b, "b")
    check_str(fail, candidate, "candidate")
    if len(a) > MAX_ITEMS or len(b) > MAX_ITEMS \
            or len(candidate) > 2 * MAX_ITEMS:
        fail("too_many:candidate")
    if len(candidate) != len(a) + len(b):
        return False
    # dp[i][j]: candidate[:i+j] is an interleaving of a[:i] and b[:j]
    dp = [[False] * (len(b) + 1) for _ in range(len(a) + 1)]
    dp[0][0] = True
    for i in range(len(a) + 1):
        for j in range(len(b) + 1):
            k = i + j
            if i and dp[i - 1][j] and a[i - 1] == candidate[k - 1]:
                dp[i][j] = True
            if j and dp[i][j - 1] and b[j - 1] == candidate[k - 1]:
                dp[i][j] = True
    return dp[len(a)][len(b)]


def cyclic_shift_lex_min(text):
    """Lexicographically smallest rotation of text, by direct
    comparison of the n rotations."""
    fail = make_fail("cyclic_shift_lex_min")
    check_str(fail, text, "text")
    if not text:
        fail("bad_value:text")
    if len(text) > MAX_ITEMS:
        fail("too_many:text")
    best = text
    for i in range(1, len(text)):
        rotated = text[i:] + text[:i]
        if rotated < best:
            best = rotated
    return best
