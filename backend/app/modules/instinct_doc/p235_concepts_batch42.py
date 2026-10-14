"""P235 concepts, batch 42 (grids II, path DP, 411-420).

Offline, stdlib only. Exact arithmetic; caps refuse before work.
"""
from __future__ import annotations

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_CELLS = 40_000
MAX_ROWS = 200
MAX_WORD = 1_000


def _int_grid(fail, grid, name, allow_ragged=False):
    check_items(fail, grid, name)
    if not grid:
        fail("empty:%s" % name)
    rows = []
    width = None
    cells = 0
    for r, row in enumerate(grid):
        check_items(fail, row, "%s[%d]" % (name, r))
        if not row:
            fail("bad_value:%s[%d]:empty_row" % (name, r))
        if not allow_ragged:
            if width is None:
                width = len(row)
            elif len(row) != width:
                fail("bad_value:%s[%d]:ragged" % (name, r))
        cells += len(row)
        if cells > MAX_CELLS:
            fail("too_many:%s" % name)
        vals = []
        for c, v in enumerate(row):
            check_int(fail, v, "%s[%d][%d]" % (name, r, c))
            vals.append(v)
        rows.append(vals)
    return rows


def triangle_min_path_sum(triangle):
    """Minimum top-to-bottom path sum in an int triangle."""
    fail = make_fail("triangle_min_path_sum")
    check_items(fail, triangle, "triangle")
    if not triangle:
        fail("empty:triangle")
    if len(triangle) > MAX_ROWS:
        fail("too_many:triangle")
    rows = []
    for r, row in enumerate(triangle):
        check_items(fail, row, "triangle[%d]" % r)
        if len(row) != r + 1:
            fail("bad_value:triangle[%d]:shape" % r)
        vals = []
        for c, v in enumerate(row):
            check_int(fail, v, "triangle[%d][%d]" % (r, c))
            vals.append(v)
        rows.append(vals)
    dp = rows[-1][:]
    for r in range(len(rows) - 2, -1, -1):
        dp = [rows[r][c] + min(dp[c], dp[c + 1])
              for c in range(len(rows[r]))]
    return dp[0]


def min_path_sum_grid(grid):
    """Minimum right/down path sum from corner to corner."""
    fail = make_fail("min_path_sum_grid")
    rows = _int_grid(fail, grid, "grid")
    h, w = len(rows), len(rows[0])
    dp = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            if r == 0 and c == 0:
                dp[r][c] = rows[0][0]
            else:
                best = None
                if r > 0:
                    best = dp[r - 1][c]
                if c > 0 and (best is None or dp[r][c - 1] < best):
                    best = dp[r][c - 1]
                dp[r][c] = rows[r][c] + best
    return dp[-1][-1]


def unique_paths_with_obstacles(grid):
    """Right/down paths from corner to corner avoiding 1-cells."""
    fail = make_fail("unique_paths_with_obstacles")
    rows = _int_grid(fail, grid, "grid")
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            if v not in (0, 1):
                fail("bad_value:grid[%d][%d]" % (r, c))
    if rows[0][0] == 1 or rows[-1][-1] == 1:
        return 0
    h, w = len(rows), len(rows[0])
    dp = [0] * w
    dp[0] = 1
    for r in range(h):
        for c in range(w):
            if rows[r][c] == 1:
                dp[c] = 0
            elif c > 0:
                dp[c] += dp[c - 1]
    return dp[-1]


def max_square_submatrix(grid):
    """Side length of the largest all-1 square in a 0/1 grid."""
    fail = make_fail("max_square_submatrix")
    rows = _int_grid(fail, grid, "grid")
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            if v not in (0, 1):
                fail("bad_value:grid[%d][%d]" % (r, c))
    h, w = len(rows), len(rows[0])
    best = 0
    prev = [0] * (w + 1)
    for r in range(h):
        cur = [0] * (w + 1)
        for c in range(1, w + 1):
            if rows[r][c - 1] == 1:
                cur[c] = 1 + min(prev[c], cur[c - 1], prev[c - 1])
                if cur[c] > best:
                    best = cur[c]
        prev = cur
    return best


def matrix_reshape(flat, rows, cols):
    """Reshape a flat list into a rows x cols matrix, row-major."""
    fail = make_fail("matrix_reshape")
    check_items(fail, flat, "flat")
    if len(flat) > MAX_CELLS:
        fail("too_many:flat")
    check_int(fail, rows, "rows")
    check_int(fail, cols, "cols")
    if rows < 1 or cols < 1 or rows > MAX_ROWS or cols > MAX_ROWS:
        fail("bad_value:shape")
    if rows * cols != len(flat):
        fail("bad_value:size_mismatch")
    vals = []
    for i, v in enumerate(flat):
        check_int(fail, v, "flat[%d]" % i)
        vals.append(v)
    return [vals[r * cols:(r + 1) * cols] for r in range(rows)]



def diagonal_traverse_order(matrix):
    """Values in up/down diagonal (zigzag) traversal order."""
    fail = make_fail("diagonal_traverse_order")
    rows = _int_grid(fail, matrix, "matrix")
    h, w = len(rows), len(rows[0])
    out = []
    for s in range(h + w - 1):
        cells = []
        for r in range(h):
            c = s - r
            if 0 <= c < w:
                cells.append(rows[r][c])
        if s % 2 == 0:
            cells.reverse()
        out.extend(cells)
    return out


def set_matrix_zeroes(matrix):
    """Zero the row and column of every 0; returns a new matrix."""
    fail = make_fail("set_matrix_zeroes")
    rows = _int_grid(fail, matrix, "matrix")
    h, w = len(rows), len(rows[0])
    zero_r = set()
    zero_c = set()
    for r in range(h):
        for c in range(w):
            if rows[r][c] == 0:
                zero_r.add(r)
                zero_c.add(c)
    return [[0 if (r in zero_r or c in zero_c) else rows[r][c]
             for c in range(w)] for r in range(h)]


def word_search_exists(grid, word):
    """True when word traces 4-connected cells, each used once."""
    fail = make_fail("word_search_exists")
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
        if cells > MAX_CELLS:
            fail("too_many:grid")
        vals = []
        for c, v in enumerate(row):
            check_str(fail, v, "grid[%d][%d]" % (r, c))
            if len(v) != 1 or v == "\x00":
                fail("bad_value:grid[%d][%d]" % (r, c))
            vals.append(v)
        rows.append(vals)
    check_str(fail, word, "word")
    if word == "":
        fail("empty:word")
    if len(word) > MAX_WORD:
        fail("too_many:word")
    if "\x00" in word:
        fail("bad_value:word")
    if len(word) > cells:
        return False
    h, w = len(rows), width
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))

    def found(r0, c0):
        if rows[r0][c0] != word[0]:
            return False
        if len(word) == 1:
            return True
        visited = {(r0, c0)}
        # explicit stack frames [r, c, matched_upto, next_dir]: the
        # word cap can exceed the Python recursion limit, so no
        # recursion here
        stack = [[r0, c0, 0, 0]]
        while stack:
            r, c, upto, d = stack[-1]
            if d == 4:
                stack.pop()
                visited.discard((r, c))
                continue
            stack[-1][3] += 1
            dr, dc = dirs[d]
            nr, nc = r + dr, c + dc
            if (0 <= nr < h and 0 <= nc < w
                    and (nr, nc) not in visited
                    and rows[nr][nc] == word[upto + 1]):
                if upto + 1 == len(word) - 1:
                    return True
                visited.add((nr, nc))
                stack.append([nr, nc, upto + 1, 0])
        return False

    for r0 in range(h):
        for c0 in range(w):
            if found(r0, c0):
                return True
    return False



def rotting_oranges_time(grid):
    """Minutes until all fresh oranges rot; -1 when impossible."""
    fail = make_fail("rotting_oranges_time")
    rows = _int_grid(fail, grid, "grid")
    h, w = len(rows), len(rows[0])
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            if v not in (0, 1, 2):
                fail("bad_value:grid[%d][%d]" % (r, c))
    fresh = 0
    queue = []
    for r in range(h):
        for c in range(w):
            if rows[r][c] == 2:
                queue.append((r, c, 0))
            elif rows[r][c] == 1:
                fresh += 1
    minutes = 0
    head = 0
    while head < len(queue):
        r, c, t = queue[head]
        head += 1
        minutes = t
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if (0 <= nr < h and 0 <= nc < w
                    and rows[nr][nc] == 1):
                rows[nr][nc] = 2
                fresh -= 1
                queue.append((nr, nc, t + 1))
    if fresh:
        return -1
    return minutes


def dungeon_min_health(grid):
    """Minimum initial health to reach the bottom-right alive."""
    fail = make_fail("dungeon_min_health")
    rows = _int_grid(fail, grid, "grid")
    h, w = len(rows), len(rows[0])
    inf = float("inf")
    need = [[inf] * (w + 1) for _ in range(h + 1)]
    need[h][w - 1] = 1
    need[h - 1][w] = 1
    for r in range(h - 1, -1, -1):
        for c in range(w - 1, -1, -1):
            req = min(need[r + 1][c], need[r][c + 1]) - rows[r][c]
            need[r][c] = max(1, req)
    return need[0][0]
