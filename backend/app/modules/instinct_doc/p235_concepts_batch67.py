"""P235 concepts batch 67: grid and matrix algorithms.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.

Grid caps: at most MAX_DIM (200) rows and columns each, and at
most MAX_CELLS (10000) cells in total.
"""

from collections import deque

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, make_fail)

MAX_DIM = 200
MAX_CELLS = 10_000
MAX_H = 100_000
MAX_N = 100


def _grid(fail, grid, name="grid", binary=False, square=False):
    check_items(fail, grid, name)
    if not grid:
        fail("empty:%s" % name)
    if len(grid) > MAX_DIM:
        fail("too_many:%s" % name)
    width = None
    for r, row in enumerate(grid):
        check_items(fail, row, "%s[%d]" % (name, r))
        if not row:
            fail("empty:%s[%d]" % (name, r))
        if len(row) > MAX_DIM:
            fail("too_many:%s[%d]" % (name, r))
        if width is None:
            width = len(row)
        elif len(row) != width:
            fail("ragged:%s[%d]" % (name, r))
        for c, v in enumerate(row):
            check_int(fail, v, "%s[%d][%d]" % (name, r, c))
            if binary and v not in (0, 1):
                fail("bad_value:%s[%d][%d]" % (name, r, c))
    if square and len(grid) != width:
        fail("not_square:%s" % name)
    if len(grid) * width > MAX_CELLS:
        fail("too_many_cells:%s" % name)
    return len(grid), width


def shortest_path_binary_matrix(grid):
    """Shortest 8-directional clear path length, corner to corner.

    Cells with value 0 are clear. The path runs from the top-left
    to the bottom-right corner of the square grid and its length
    counts the cells visited. Returns -1 when either corner is
    blocked or no path exists.
    """
    fail = make_fail("shortest_path_binary_matrix")
    n, _ = _grid(fail, grid, binary=True, square=True)
    if grid[0][0] == 1 or grid[n - 1][n - 1] == 1:
        return -1
    seen = {(0, 0)}
    q = deque([(0, 0, 1)])
    while q:
        r, c, d = q.popleft()
        if r == n - 1 and c == n - 1:
            return d
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr, nc = r + dr, c + dc
                if (0 <= nr < n and 0 <= nc < n
                        and grid[nr][nc] == 0
                        and (nr, nc) not in seen):
                    seen.add((nr, nc))
                    q.append((nr, nc, d + 1))
    return -1


def number_of_enclaves(grid):
    """Ones that cannot walk off the boundary moving 4-directionally."""
    fail = make_fail("number_of_enclaves")
    rows, cols = _grid(fail, grid, binary=True)
    seeds = [(r, c) for r in range(rows) for c in range(cols)
             if grid[r][c] == 1
             and (r in (0, rows - 1) or c in (0, cols - 1))]
    seen = set(seeds)
    q = deque(seeds)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (0 <= nx < rows and 0 <= ny < cols
                    and grid[nx][ny] == 1 and (nx, ny) not in seen):
                seen.add((nx, ny))
                q.append((nx, ny))
    return sum(1 for r in range(rows) for c in range(cols)
               if grid[r][c] == 1 and (r, c) not in seen)


def matrix_nearest_zero_distance(mat):
    """Per-cell Manhattan distance to the nearest zero cell.

    Refuses a matrix with no zero cell, where distance is
    undefined.
    """
    fail = make_fail("matrix_nearest_zero_distance")
    rows, cols = _grid(fail, mat, "mat", binary=True)
    dist = [[None] * cols for _ in range(rows)]
    q = deque()
    for r in range(rows):
        for c in range(cols):
            if mat[r][c] == 0:
                dist[r][c] = 0
                q.append((r, c))
    if not q:
        fail("no_zero:mat")
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (0 <= nx < rows and 0 <= ny < cols
                    and dist[nx][ny] is None):
                dist[nx][ny] = dist[x][y] + 1
                q.append((nx, ny))
    return dist


def pacific_atlantic_cells(heights):
    """Sorted [row, col] cells whose rain reaches both ocean sides.

    Water flows from a cell to a neighbor of equal or lower height;
    the top and left edges drain to one side, the bottom and right
    edges to the other.
    """
    fail = make_fail("pacific_atlantic_cells")
    rows, cols = _grid(fail, heights, "heights")
    for r in range(rows):
        for c in range(cols):
            if heights[r][c] < 0 or heights[r][c] > MAX_H:
                fail("out_of_range:heights[%d][%d]" % (r, c))

    def reach(seeds):
        seen = set(seeds)
        q = deque(seeds)
        while q:
            x, y = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if (0 <= nx < rows and 0 <= ny < cols
                        and (nx, ny) not in seen
                        and heights[nx][ny] >= heights[x][y]):
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return seen

    pac = reach([(0, c) for c in range(cols)]
                + [(r, 0) for r in range(rows)])
    atl = reach([(rows - 1, c) for c in range(cols)]
                + [(r, cols - 1) for r in range(rows)])
    return sorted([list(p) for p in pac & atl])


def spiral_matrix_generate(n):
    """The n by n matrix filled with 1..n*n in clockwise spiral."""
    fail = make_fail("spiral_matrix_generate")
    check_int(fail, n, "n")
    if n < 1 or n > MAX_N:
        fail("out_of_range:n")
    out = [[0] * n for _ in range(n)]
    dirs = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    r = c = d = 0
    for v in range(1, n * n + 1):
        out[r][c] = v
        nr, nc = r + dirs[d][0], c + dirs[d][1]
        if not (0 <= nr < n and 0 <= nc < n) or out[nr][nc]:
            d = (d + 1) % 4
            nr, nc = r + dirs[d][0], c + dirs[d][1]
        r, c = nr, nc
    return out


def diagonal_sort_matrix(mat):
    """The matrix with every top-left to bottom-right diagonal sorted.

    Diagonals are the cells sharing (row - column); each is sorted
    ascending and written back in place order.
    """
    fail = make_fail("diagonal_sort_matrix")
    rows, cols = _grid(fail, mat, "mat")
    groups = {}
    for r in range(rows):
        for c in range(cols):
            groups.setdefault(r - c, []).append((r, c))
    out = [row[:] for row in mat]
    for cells in groups.values():
        vals = sorted(mat[r][c] for r, c in cells)
        for (r, c), v in zip(cells, vals):
            out[r][c] = v
    return out


def valid_sudoku_check(board):
    """True when no row, column, or 3x3 box repeats a nonzero digit.

    The board must be 9 by 9 with entries 0..9; 0 marks a blank.
    """
    fail = make_fail("valid_sudoku_check")
    check_items(fail, board, "board")
    if len(board) != 9:
        fail("bad_length:board")
    for r, row in enumerate(board):
        check_items(fail, row, "board[%d]" % r)
        if len(row) != 9:
            fail("bad_length:board[%d]" % r)
        for c, v in enumerate(row):
            check_int(fail, v, "board[%d][%d]" % (r, c))
            if v < 0 or v > 9:
                fail("out_of_range:board[%d][%d]" % (r, c))
    for i in range(9):
        row = [v for v in board[i] if v]
        col = [board[j][i] for j in range(9) if board[j][i]]
        if len(row) != len(set(row)) or len(col) != len(set(col)):
            return False
    for br in range(0, 9, 3):
        for bc in range(0, 9, 3):
            box = [board[r][c] for r in range(br, br + 3)
                   for c in range(bc, bc + 3) if board[r][c]]
            if len(box) != len(set(box)):
                return False
    return True


def maximal_rectangle_ones(mat):
    """Largest area of an all-ones rectangle inside a binary matrix."""
    fail = make_fail("maximal_rectangle_ones")
    rows, cols = _grid(fail, mat, "mat", binary=True)
    heights = [0] * cols
    best = 0
    for r in range(rows):
        for c in range(cols):
            heights[c] = heights[c] + 1 if mat[r][c] == 1 else 0
        stack = []
        row_h = heights + [0]
        for i, v in enumerate(row_h):
            while stack and row_h[stack[-1]] > v:
                h = row_h[stack.pop()]
                w = i if not stack else i - stack[-1] - 1
                if h * w > best:
                    best = h * w
            stack.append(i)
    return best


def longest_increasing_path_matrix(mat):
    """Longest strictly increasing 4-directional path length.

    Computed iteratively: cells are processed from the highest
    value down, so every strictly higher neighbor is already
    scored. No recursion, no process-global state touched.
    """
    fail = make_fail("longest_increasing_path_matrix")
    rows, cols = _grid(fail, mat, "mat")
    cells = sorted(((mat[r][c], r, c) for r in range(rows)
                    for c in range(cols)), reverse=True)
    score = {}
    best = 1
    for v, r, c in cells:
        top = 1
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dx, c + dy
            if (0 <= nr < rows and 0 <= nc < cols
                    and mat[nr][nc] > v
                    and score[(nr, nc)] + 1 > top):
                top = score[(nr, nc)] + 1
        score[(r, c)] = top
        if top > best:
            best = top
    return best


def count_submatrices_all_ones(mat):
    """Count of axis-aligned submatrices made entirely of ones."""
    fail = make_fail("count_submatrices_all_ones")
    rows, cols = _grid(fail, mat, "mat", binary=True)
    total = 0
    for r1 in range(rows):
        run = [True] * cols
        for r2 in range(r1, rows):
            streak = 0
            for c in range(cols):
                run[c] = run[c] and mat[r2][c] == 1
                if run[c]:
                    streak += 1
                    total += streak
                else:
                    streak = 0
    return total
