"""P235 concepts batch 61: numbers and list transforms.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
"""

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, make_fail)

MAX_BITS = 10_000
MAX_N = 1_000
MAX_COORD = 1_000_000
MAX_DIM = 1_000


def _int_list(fail, values, name="items", allow_empty=False):
    check_items(fail, values, name)
    if not values and not allow_empty:
        fail("empty:%s" % name)
    if len(values) > MAX_ITEMS:
        fail("too_many:%s" % name)
    for i, v in enumerate(values):
        check_int(fail, v, "%s[%d]" % (name, i))


def min_time_visiting_points(points):
    """Least seconds to visit the points in the given order.

    Each second moves one step in any of the eight directions, so a
    leg costs the Chebyshev distance max(|dx|, |dy|). Coordinates
    beyond MAX_COORD refuse before any leg is timed.
    """
    fail = make_fail("min_time_visiting_points")
    check_items(fail, points, "points")
    if len(points) < 2:
        fail("too_few:points")
    if len(points) > MAX_ITEMS:
        fail("too_many:points")
    total = 0
    prev = None
    for i, p in enumerate(points):
        if type(p) is not list or len(p) != 2:
            fail("bad_type:points[%d]" % i)
        check_int(fail, p[0], "points[%d][0]" % i)
        check_int(fail, p[1], "points[%d][1]" % i)
        if abs(p[0]) > MAX_COORD or abs(p[1]) > MAX_COORD:
            fail("out_of_range:points[%d]" % i)
        if prev is not None:
            total += max(abs(p[0] - prev[0]), abs(p[1] - prev[1]))
        prev = p
    return total


def lucas_term(n):
    """Nth Lucas number: L(0)=2, L(1)=1, L(n)=L(n-1)+L(n-2)."""
    fail = make_fail("lucas_term")
    check_int(fail, n, "n")
    if n < 0 or n > MAX_N:
        fail("out_of_range:n")
    a, b = 2, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def integer_break_max_product(n):
    """Max product of splitting n into at least two positive ints."""
    fail = make_fail("integer_break_max_product")
    check_int(fail, n, "n")
    if n < 2 or n > MAX_N:
        fail("out_of_range:n")
    best = [0] * (n + 1)
    best[1] = 1
    for total in range(2, n + 1):
        top = 0
        for cut in range(1, total):
            cand = max(cut * (total - cut), cut * best[total - cut])
            if cand > top:
                top = cand
        best[total] = top
    return best[n]


def move_zeros_to_end(items):
    """Copy of an int list with zeros moved to the end, stable."""
    fail = make_fail("move_zeros_to_end")
    _int_list(fail, items)
    nonzero = [v for v in items if v != 0]
    return nonzero + [0] * (len(items) - len(nonzero))


def dutch_flag_partition(items):
    """Order a list of 0s, 1s, and 2s as all 0s, then 1s, then 2s.

    Every value is validated before the ordered list is built.
    """
    fail = make_fail("dutch_flag_partition")
    check_items(fail, items)
    if not items:
        fail("empty:items")
    if len(items) > MAX_ITEMS:
        fail("too_many:items")
    counts = [0, 0, 0]
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        if v < 0 or v > 2:
            fail("bad_value:items[%d]" % i)
        counts[v] += 1
    return [0] * counts[0] + [1] * counts[1] + [2] * counts[2]


def max_consecutive_ones(items):
    """Longest run of 1s in a binary (0/1) int list.

    Every value is validated before the run scan begins.
    """
    fail = make_fail("max_consecutive_ones")
    _int_list(fail, items)
    for i, v in enumerate(items):
        if v not in (0, 1):
            fail("bad_value:items[%d]" % i)
    best = 0
    run = 0
    for v in items:
        run = run + 1 if v else 0
        if run > best:
            best = run
    return best


def island_perimeter(grid):
    """Exposed edges of the 1-cells in a rectangular 0/1 grid.

    Water borders the grid. Every cell is validated before the
    perimeter is counted.
    """
    fail = make_fail("island_perimeter")
    check_items(fail, grid, "grid")
    if not grid:
        fail("empty:grid")
    if len(grid) > MAX_DIM:
        fail("too_many:grid")
    width = None
    cells = 0
    for i, row in enumerate(grid):
        if type(row) is not list:
            fail("bad_type:grid[%d]" % i)
        if not row:
            fail("empty:grid[%d]" % i)
        if len(row) > MAX_DIM:
            fail("too_many:grid[%d]" % i)
        if width is None:
            width = len(row)
        elif len(row) != width:
            fail("not_rectangular:grid")
        cells += len(row)
        if cells > MAX_ITEMS:
            fail("too_many:grid")
        for j, v in enumerate(row):
            check_int(fail, v, "grid[%d][%d]" % (i, j))
            if v not in (0, 1):
                fail("bad_value:grid[%d][%d]" % (i, j))
    perimeter = 0
    for i, row in enumerate(grid):
        for j, v in enumerate(row):
            if v != 1:
                continue
            perimeter += 4
            if i and grid[i - 1][j] == 1:
                perimeter -= 1
            if j and grid[i][j - 1] == 1:
                perimeter -= 1
            if i + 1 < len(grid) and grid[i + 1][j] == 1:
                perimeter -= 1
            if j + 1 < width and grid[i][j + 1] == 1:
                perimeter -= 1
    return perimeter


def matrix_search_sorted(matrix, target):
    """Whether target is in a row- and column-sorted int matrix.

    The sorted contract is validated for the whole matrix before
    the staircase search runs.
    """
    fail = make_fail("matrix_search_sorted")
    check_int(fail, target, "target")
    check_items(fail, matrix, "matrix")
    if not matrix:
        fail("empty:matrix")
    if len(matrix) > MAX_DIM:
        fail("too_many:matrix")
    width = None
    cells = 0
    for i, row in enumerate(matrix):
        if type(row) is not list:
            fail("bad_type:matrix[%d]" % i)
        if not row:
            fail("empty:matrix[%d]" % i)
        if len(row) > MAX_DIM:
            fail("too_many:matrix[%d]" % i)
        if width is None:
            width = len(row)
        elif len(row) != width:
            fail("not_rectangular:matrix")
        cells += len(row)
        if cells > MAX_ITEMS:
            fail("too_many:matrix")
        for j, v in enumerate(row):
            check_int(fail, v, "matrix[%d][%d]" % (i, j))
    for i, row in enumerate(matrix):
        for j in range(1, len(row)):
            if row[j] < row[j - 1]:
                fail("not_sorted:matrix[%d]" % i)
    for j in range(width):
        for i in range(1, len(matrix)):
            if matrix[i][j] < matrix[i - 1][j]:
                fail("not_sorted:matrix[*][%d]" % j)
    i = 0
    j = width - 1
    while i < len(matrix) and j >= 0:
        v = matrix[i][j]
        if v == target:
            return True
        if v < target:
            i += 1
        else:
            j -= 1
    return False


def total_hamming_distance(items):
    """Sum of bit mismatches over all unordered pairs of ints.

    Refuses negative values and bit-lengths above MAX_BITS before
    any counting.
    """
    fail = make_fail("total_hamming_distance")
    _int_list(fail, items)
    top = 0
    for i, v in enumerate(items):
        if v < 0:
            fail("bad_value:items[%d]" % i)
        if v.bit_length() > MAX_BITS:
            fail("too_big:items[%d]" % i)
        if v.bit_length() > top:
            top = v.bit_length()
    total = 0
    for b in range(top):
        ones = sum(1 for v in items if (v >> b) & 1)
        total += ones * (len(items) - ones)
    return total


def summary_ranges(items):
    """Compact a strictly increasing int list into range strings.

    Returns entries like "3->5" for runs and "7" for singletons;
    an empty input gives an empty list.
    """
    fail = make_fail("summary_ranges")
    _int_list(fail, items, allow_empty=True)
    for i in range(1, len(items)):
        if items[i] <= items[i - 1]:
            fail("not_sorted:items[%d]" % i)
    out = []
    i = 0
    while i < len(items):
        j = i
        while j + 1 < len(items) and items[j + 1] == items[j] + 1:
            j += 1
        if j == i:
            out.append(str(items[i]))
        else:
            out.append("%d->%d" % (items[i], items[j]))
        i = j + 1
    return out
