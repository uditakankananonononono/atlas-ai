"""P235 concepts, batch 39 (grids, jumps, classic DP, 381-390).

Offline, stdlib only. Exact arithmetic; caps refuse before work.
"""
from __future__ import annotations

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, make_fail)

MAX_GRID_CELLS = 40_000
MAX_STEPS = 10_000
MAX_EGGS = 100
MAX_FLOORS = 10_000
MAX_NTH = 1_000_000
MAX_HEIGHT = 10**9
MAX_PRICES = 10_000


def _check_grid(fail, grid, name):
    check_items(fail, grid, name)
    if not grid:
        fail("empty:%s" % name)
    rows = []
    width = None
    cells = 0
    for r, row in enumerate(grid):
        check_items(fail, row, "%s[%d]" % (name, r))
        if width is None:
            width = len(row)
            if width == 0:
                fail("bad_value:%s[%d]:empty_row" % (name, r))
        elif len(row) != width:
            fail("bad_value:%s[%d]:ragged" % (name, r))
        cells += len(row)
        if cells > MAX_GRID_CELLS:
            fail("too_many:%s" % name)
        rows.append(list(row))
    return rows, width


def count_islands(grid):
    """Number of 4-connected components of 1s in a 0/1 grid."""
    fail = make_fail("count_islands")
    rows, width = _check_grid(fail, grid, "grid")
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            check_int(fail, v, "grid[%d][%d]" % (r, c))
            if v not in (0, 1):
                fail("bad_value:grid[%d][%d]" % (r, c))
    seen = [[False] * width for _ in rows]
    islands = 0
    for r0 in range(len(rows)):
        for c0 in range(width):
            if rows[r0][c0] == 1 and not seen[r0][c0]:
                islands += 1
                stack = [(r0, c0)]
                seen[r0][c0] = True
                while stack:
                    r, c = stack.pop()
                    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nr, nc = r + dr, c + dc
                        if (0 <= nr < len(rows) and 0 <= nc < width
                                and rows[nr][nc] == 1
                                and not seen[nr][nc]):
                            seen[nr][nc] = True
                            stack.append((nr, nc))
    return islands


def flood_fill_region_size(grid, start_row, start_col):
    """Size of the 4-connected same-value region containing the start."""
    fail = make_fail("flood_fill_region_size")
    rows, width = _check_grid(fail, grid, "grid")
    check_int(fail, start_row, "start_row")
    check_int(fail, start_col, "start_col")
    if not (0 <= start_row < len(rows)):
        fail("bad_value:start_row")
    if not (0 <= start_col < width):
        fail("bad_value:start_col")
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            check_int(fail, v, "grid[%d][%d]" % (r, c))
    target = rows[start_row][start_col]
    seen = {(start_row, start_col)}
    stack = [(start_row, start_col)]
    while stack:
        r, c = stack.pop()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if (0 <= nr < len(rows) and 0 <= nc < width
                    and rows[nr][nc] == target
                    and (nr, nc) not in seen):
                seen.add((nr, nc))
                stack.append((nr, nc))
    return len(seen)


def jump_game_min_jumps(steps):
    """Minimum jumps to the last index; steps[i] is the max jump length."""
    fail = make_fail("jump_game_min_jumps")
    check_items(fail, steps, "steps")
    if not steps:
        fail("empty:steps")
    if len(steps) > MAX_STEPS:
        fail("too_many:steps")
    vals = []
    for i, v in enumerate(steps):
        check_int(fail, v, "steps[%d]" % i)
        if v < 0:
            fail("bad_value:steps[%d]" % i)
        vals.append(v)
    n = len(vals)
    if n == 1:
        return 0
    jumps = 0
    end = 0
    far = 0
    for i in range(n - 1):
        far = max(far, i + vals[i])
        if i == end:
            if far == end:
                fail("bad_value:unreachable")
            jumps += 1
            end = far
    return jumps


def egg_drop_min_trials(eggs, floors):
    """Worst-case trials that guarantee finding the critical floor."""
    fail = make_fail("egg_drop_min_trials")
    check_int(fail, eggs, "eggs")
    check_int(fail, floors, "floors")
    if eggs < 1 or eggs > MAX_EGGS:
        fail("bad_value:eggs")
    if floors < 0 or floors > MAX_FLOORS:
        fail("bad_value:floors")
    if floors == 0:
        return 0
    # dp[m] = max floors testable with m trials and the current eggs;
    # classic inversion: smallest m with dp[m] >= floors, capped eggs.
    k = min(eggs, floors)
    dp = [0] * (k + 1)
    m = 0
    while dp[k] < floors:
        m += 1
        for e in range(k, 0, -1):
            dp[e] = dp[e] + dp[e - 1] + 1
    return m


def max_subarray_product(values):
    """Maximum product over all non-empty contiguous subarrays."""
    fail = make_fail("max_subarray_product")
    check_items(fail, values, "values")
    if not values:
        fail("empty:values")
    if len(values) > MAX_ITEMS:
        fail("too_many:values")
    vals = []
    for i, v in enumerate(values):
        check_int(fail, v, "values[%d]" % i)
        vals.append(v)
    best = vals[0]
    hi = vals[0]
    lo = vals[0]
    for v in vals[1:]:
        cand = (v, hi * v, lo * v)
        hi = max(cand)
        lo = min(cand)
        best = max(best, hi)
    return best


def nth_ugly_number(n):
    """The n-th positive integer whose prime factors are only 2, 3, 5."""
    fail = make_fail("nth_ugly_number")
    check_int(fail, n, "n")
    if n < 1 or n > MAX_NTH:
        fail("bad_value:n")
    uglies = [1]
    i2 = i3 = i5 = 0
    while len(uglies) < n:
        nxt = min(uglies[i2] * 2, uglies[i3] * 3, uglies[i5] * 5)
        uglies.append(nxt)
        if nxt == uglies[i2] * 2:
            i2 += 1
        if nxt == uglies[i3] * 3:
            i3 += 1
        if nxt == uglies[i5] * 5:
            i5 += 1
    return uglies[-1]


def peak_index_bitonic(values):
    """Index of the maximum of a strictly bitonic list."""
    fail = make_fail("peak_index_bitonic")
    check_items(fail, values, "values")
    if len(values) < 3:
        fail("too_few:values")
    if len(values) > MAX_ITEMS:
        fail("too_many:values")
    vals = []
    for i, v in enumerate(values):
        check_int(fail, v, "values[%d]" % i)
        vals.append(v)
    # full strict up-then-strict-down validation: the index walk
    # must climb, crest exactly once, and descend to the end
    n = len(vals)
    i = 0
    while i + 1 < n and vals[i] < vals[i + 1]:
        i += 1
    if i == 0 or i == n - 1:
        fail("bad_value:not_bitonic")
    peak = i
    while i + 1 < n and vals[i] > vals[i + 1]:
        i += 1
    if i != n - 1:
        fail("bad_value:not_bitonic")
    return peak


def pivot_index_sum(values):
    """Leftmost index where left sum equals right sum, else -1."""
    fail = make_fail("pivot_index_sum")
    check_items(fail, values, "values")
    if not values:
        fail("empty:values")
    if len(values) > MAX_ITEMS:
        fail("too_many:values")
    vals = []
    for i, v in enumerate(values):
        check_int(fail, v, "values[%d]" % i)
        vals.append(v)
    total = sum(vals)
    left = 0
    for i, v in enumerate(vals):
        if left == total - left - v:
            return i
        left += v
    return -1


def container_max_water(heights):
    """Maximum water held between two lines of the height profile."""
    fail = make_fail("container_max_water")
    check_items(fail, heights, "heights")
    if len(heights) < 2:
        fail("too_few:heights")
    if len(heights) > MAX_ITEMS:
        fail("too_many:heights")
    vals = []
    for i, v in enumerate(heights):
        check_int(fail, v, "heights[%d]" % i)
        if v < 0 or v > MAX_HEIGHT:
            fail("bad_value:heights[%d]" % i)
        vals.append(v)
    lo, hi = 0, len(vals) - 1
    best = 0
    while lo < hi:
        area = (hi - lo) * min(vals[lo], vals[hi])
        if area > best:
            best = area
        if vals[lo] <= vals[hi]:
            lo += 1
        else:
            hi -= 1
    return best


def stock_max_profit_once(prices):
    """Best profit from one buy then later sell; 0 when none."""
    fail = make_fail("stock_max_profit_once")
    check_items(fail, prices, "prices")
    if not prices:
        fail("empty:prices")
    if len(prices) > MAX_PRICES:
        fail("too_many:prices")
    vals = []
    for i, v in enumerate(prices):
        check_int(fail, v, "prices[%d]" % i)
        if v < 0:
            fail("bad_value:prices[%d]" % i)
        vals.append(v)
    best = 0
    low = vals[0]
    for v in vals[1:]:
        if v - low > best:
            best = v - low
        if v < low:
            low = v
    return best
