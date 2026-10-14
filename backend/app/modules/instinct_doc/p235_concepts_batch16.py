"""P235 concepts, batch 16 (games/combinatorics, 151-160).
Offline, stdlib only."""
from __future__ import annotations

import math
from collections import deque
from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_FACTORIAL_N = 10_000
MAX_DERANGE_N = 10_000
MAX_CATALAN_N = 1_000
MAX_DICE = 100
_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6),
          (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))
_KNIGHT = ((1, 2), (2, 1), (-1, 2), (-2, 1),
           (1, -2), (2, -1), (-1, -2), (-2, -1))


def permutations_count(n):
    fail = make_fail("permutations_count")
    check_int(fail, n, "n")
    if n < 0:
        fail("bad_value:n")
    if n > MAX_FACTORIAL_N:
        fail("too_many:n")
    return math.factorial(n)


def derangement_count(n):
    fail = make_fail("derangement_count")
    check_int(fail, n, "n")
    if n < 0:
        fail("bad_value:n")
    if n > MAX_DERANGE_N:
        fail("too_many:n")
    d0, d1 = 1, 0
    if n == 0:
        return d0
    for k in range(2, n + 1):
        d0, d1 = d1, (k - 1) * (d0 + d1)
    return d1


def catalan_number(n):
    fail = make_fail("catalan_number")
    check_int(fail, n, "n")
    if n < 0:
        fail("bad_value:n")
    if n > MAX_CATALAN_N:
        fail("too_many:n")
    c = 1
    for k in range(n):
        c = c * (4 * k + 2) // (k + 2)
    return c


def tic_tac_toe_winner(board):
    fail = make_fail("tic_tac_toe_winner")
    check_items(fail, board, "board")
    if len(board) != 9:
        fail("bad_value:board")
    for i, v in enumerate(board):
        check_str(fail, v, "board[%d]" % i)
        if v not in ("X", "O", ""):
            fail("bad_value:board")
    for a, b, c in _LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return None


def nim_outcome(heaps):
    fail = make_fail("nim_outcome")
    check_items(fail, heaps, "heaps")
    x = 0
    for i, v in enumerate(heaps):
        check_int(fail, v, "heaps[%d]" % i)
        if v < 0:
            fail("bad_value:heaps")
        x ^= v
    return "losing" if x == 0 else "winning"


def knight_min_moves(start, target):
    fail = make_fail("knight_min_moves")

    def _square(sq, name):
        if type(sq) is not list or len(sq) != 2:
            fail("bad_value:square")
        check_int(fail, sq[0], "%s[0]" % name)
        check_int(fail, sq[1], "%s[1]" % name)
        if not (0 <= sq[0] <= 7 and 0 <= sq[1] <= 7):
            fail("bad_value:square")
        return tuple(sq)

    src = _square(start, "start")
    dst = _square(target, "target")
    if src == dst:
        return 0
    seen = {src}
    queue = deque([(src, 0)])
    while queue:
        (x, y), dist = queue.popleft()
        for dx, dy in _KNIGHT:
            nxt = (x + dx, y + dy)
            if nxt == dst:
                return dist + 1
            if 0 <= nxt[0] <= 7 and 0 <= nxt[1] <= 7 and nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, dist + 1))
    # Unreachable: the knight graph on the 8x8 board is connected, so the
    # BFS always finds dst before the queue empties (pinned exhaustively
    # by test_knight_exhaustive_all_pairs).
    return -1


def queens_no_attack(columns):
    fail = make_fail("queens_no_attack")
    check_items(fail, columns, "columns")
    cols = []
    for i, v in enumerate(columns):
        check_int(fail, v, "columns[%d]" % i)
        if v < 0:
            fail("bad_value:columns")
        cols.append(v)
    for r1 in range(len(cols)):
        for r2 in range(r1 + 1, len(cols)):
            if cols[r1] == cols[r2] or \
                    abs(cols[r1] - cols[r2]) == r2 - r1:
                return False
    return True


def dice_sum_probability_exact(dice, total):
    fail = make_fail("dice_sum_probability_exact")
    check_int(fail, dice, "dice")
    check_int(fail, total, "total")
    if dice < 1:
        fail("bad_value:dice")
    if dice > MAX_DICE:
        fail("too_many:dice")
    ways = {0: 1}
    for _ in range(dice):
        nxt = {}
        for s, w in ways.items():
            for face in range(1, 7):
                nxt[s + face] = nxt.get(s + face, 0) + w
        ways = nxt
    return Fraction(ways.get(total, 0), 6 ** dice)


def chess_square_color(square):
    fail = make_fail("chess_square_color")
    check_str(fail, square, "square")
    if len(square) != 2:
        fail("bad_value:square")
    file_ch, rank_ch = square[0], square[1]
    if file_ch < "a" or file_ch > "h" or not ("1" <= rank_ch <= "8"):
        fail("bad_value:square")
    file_i = ord(file_ch) - ord("a")
    rank_i = ord(rank_ch) - ord("1")
    return "dark" if (file_i + rank_i) % 2 == 0 else "light"


def magic_square_check(matrix):
    fail = make_fail("magic_square_check")
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
    n = len(rows)
    if n == 0 or width != n:
        return False
    flat = sorted(v for row in rows for v in row)
    if flat != list(range(1, n * n + 1)):
        return False
    target = n * (n * n + 1) // 2
    if any(sum(row) != target for row in rows):
        return False
    if any(sum(rows[i][j] for i in range(n)) != target for j in range(n)):
        return False
    if sum(rows[i][i] for i in range(n)) != target:
        return False
    if sum(rows[i][n - 1 - i] for i in range(n)) != target:
        return False
    return True
