"""P235 concepts batch 81: games, ciphers and voting.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
"""

import heapq

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_N = 100_000
MAX_TEXT = 10_000
MAX_CELLS = 10_000
MAX_SIDE = 100
MAX_CANDIDATES = 20
MAX_NAME = 16
MAX_POINTS = 1_000_000_000


def n_queens_count(n):
    """Number of distinct ways to place n non-attacking queens on
    an n x n board."""
    fail = make_fail("n_queens_count")
    check_int(fail, n, "n")
    if n < 1 or n > 12:
        fail("out_of_range:n")
    full = (1 << n) - 1
    count = 0
    stack = [(0, 0, 0)]
    while stack:
        cols, diag1, diag2 = stack.pop()
        if cols == full:
            count += 1
            continue
        free = full & ~(cols | diag1 | diag2)
        while free:
            bit = free & (-free)
            free -= bit
            stack.append((cols | bit, (diag1 | bit) << 1 & full,
                          (diag2 | bit) >> 1))
    return count


def _check_fence(fail, text, rails):
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > MAX_TEXT:
        fail("too_long:text")
    for c in text:
        if not (" " <= c <= "~"):
            fail("bad_char:text")
    check_int(fail, rails, "rails")
    if rails < 2 or rails > 100:
        fail("out_of_range:rails")


def rail_fence_encode(text, rails):
    """Writes text in a zigzag across the given number of rails and
    reads it back row by row."""
    fail = make_fail("rail_fence_encode")
    _check_fence(fail, text, rails)
    if rails >= len(text):
        return text
    rows = [[] for _ in range(rails)]
    rail, step = 0, 1
    for c in text:
        rows[rail].append(c)
        if rail == 0:
            step = 1
        elif rail == rails - 1:
            step = -1
        rail += step
    return "".join("".join(row) for row in rows)


def rail_fence_decode(text, rails):
    """Inverse of the zigzag rail-fence transposition."""
    fail = make_fail("rail_fence_decode")
    _check_fence(fail, text, rails)
    if rails >= len(text):
        return text
    pattern = []
    rail, step = 0, 1
    for _ in text:
        pattern.append(rail)
        if rail == 0:
            step = 1
        elif rail == rails - 1:
            step = -1
        rail += step
    counts = [pattern.count(r) for r in range(rails)]
    lanes = []
    pos = 0
    for count in counts:
        lanes.append(text[pos:pos + count])
        pos += count
    heads = [0] * rails
    out = []
    for r in pattern:
        out.append(lanes[r][heads[r]])
        heads[r] += 1
    return "".join(out)


def _check_ballots(fail, ballots):
    check_items(fail, ballots, "ballots")
    if not ballots:
        fail("empty:ballots")
    if len(ballots) > MAX_ITEMS:
        fail("too_many:ballots")
    candidates = None
    for i, ballot in enumerate(ballots):
        if type(ballot) is not list:
            fail("bad_type:ballots[%d]" % i)
        if not ballot:
            fail("empty:ballots[%d]" % i)
        if len(ballot) > MAX_CANDIDATES:
            fail("too_many:ballots[%d]" % i)
        for j, name in enumerate(ballot):
            check_str(fail, name, "ballots[%d][%d]" % (i, j))
            if not name:
                fail("empty:ballots[%d][%d]" % (i, j))
            if len(name) > MAX_NAME:
                fail("too_long:ballots[%d][%d]" % (i, j))
            if any(not ("a" <= c <= "z") for c in name):
                fail("bad_char:ballots[%d][%d]" % (i, j))
        if len(set(ballot)) != len(ballot):
            fail("bad_value:ballots[%d]" % i)
        if candidates is None:
            candidates = set(ballot)
        elif set(ballot) != candidates:
            fail("mismatch:ballots[%d]" % i)
    return candidates


def borda_count_winner(ballots):
    """Borda winner over full rankings: a candidate ranked first of
    k scores k-1 points, last scores 0. Returns the unique top
    scorer, or None on a tie."""
    fail = make_fail("borda_count_winner")
    candidates = _check_ballots(fail, ballots)
    k = len(candidates)
    scores = {name: 0 for name in candidates}
    for ballot in ballots:
        for rank, name in enumerate(ballot):
            scores[name] += k - 1 - rank
    top = max(scores.values())
    winners = [name for name, value in scores.items() if value == top]
    return winners[0] if len(winners) == 1 else None


def condorcet_winner(ballots):
    """Candidate that beats every other in pairwise head-to-head
    majority, or None when no such candidate exists."""
    fail = make_fail("condorcet_winner")
    candidates = _check_ballots(fail, ballots)
    for hopeful in candidates:
        beats_all = True
        for rival in candidates:
            if rival == hopeful:
                continue
            ahead = sum(1 for ballot in ballots
                        if ballot.index(hopeful) < ballot.index(rival))
            if ahead * 2 <= len(ballots):
                beats_all = False
                break
        if beats_all:
            return hopeful
    return None


_RANKS = "23456789TJQKA"
_SUITS = "CDHS"


def poker_hand_category(cards):
    """Category of a five-card poker hand.

    Cards are two-character strings: rank 2-9, T, J, Q, K or A,
    then suit C, D, H or S. The wheel A-2-3-4-5 counts as a
    five-high straight. Returns one of: straight_flush,
    four_of_a_kind, full_house, flush, straight, three_of_a_kind,
    two_pair, one_pair, high_card."""
    fail = make_fail("poker_hand_category")
    check_items(fail, cards, "cards")
    if len(cards) != 5:
        fail("bad_value:cards")
    ranks = []
    suits = []
    for i, card in enumerate(cards):
        check_str(fail, card, "cards[%d]" % i)
        if len(card) != 2:
            fail("bad_length:cards[%d]" % i)
        if card[0] not in _RANKS:
            fail("bad_value:cards[%d]" % i)
        if card[1] not in _SUITS:
            fail("bad_value:cards[%d]" % i)
        ranks.append(_RANKS.index(card[0]))
        suits.append(card[1])
    if len(set(cards)) != 5:
        fail("bad_value:duplicate")
    counts = sorted((ranks.count(r) for r in set(ranks)), reverse=True)
    flush = len(set(suits)) == 1
    ordered = sorted(set(ranks))
    wheel = ordered == [0, 1, 2, 3, 12]
    straight = len(ordered) == 5 and (
        ordered[4] - ordered[0] == 4 or wheel)
    if straight and flush:
        return "straight_flush"
    if counts[0] == 4:
        return "four_of_a_kind"
    if counts[0] == 3 and counts[1] == 2:
        return "full_house"
    if flush:
        return "flush"
    if straight:
        return "straight"
    if counts[0] == 3:
        return "three_of_a_kind"
    if counts[0] == 2 and counts[1] == 2:
        return "two_pair"
    if counts[0] == 2:
        return "one_pair"
    return "high_card"


def connect_four_winner(grid):
    """Winner on a 6x7 connect-four grid, or None.

    Rows are strings of 'X', 'O' and '.'; gravity must hold (no
    floating pieces) and at most one side may have a line. Returns
    'X', 'O' or None."""
    fail = make_fail("connect_four_winner")
    check_items(fail, grid, "grid")
    if len(grid) != 6:
        fail("bad_shape:grid")
    for r, row in enumerate(grid):
        check_str(fail, row, "grid[%d]" % r)
        if len(row) != 7:
            fail("bad_shape:grid[%d]" % r)
        for c in row:
            if c not in "XO.":
                fail("bad_char:grid")
    for col in range(7):
        seen_empty = False
        for r in range(5, -1, -1):
            cell = grid[r][col]
            if cell == ".":
                seen_empty = True
            elif seen_empty:
                fail("bad_value:gravity")
    winners = set()
    for r in range(6):
        for c in range(7):
            piece = grid[r][c]
            if piece == ".":
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                cells = [(r + i * dr, c + i * dc) for i in range(4)]
                if all(0 <= nr < 6 and 0 <= nc < 7
                       and grid[nr][nc] == piece for nr, nc in cells):
                    winners.add(piece)
    if len(winners) > 1:
        fail("bad_value:position")
    return winners.pop() if winners else None


def minesweeper_reveal(board, click):
    """Reveals a minesweeper board from one click.

    board rows hold 'M' (mine) and '.' (hidden safe cell). Returns
    a new board of strings: clicking a mine reveals only it as 'X';
    clicking a safe cell reveals the flood of zero-count cells and
    their numbered border as digits '0'-'8'; everything else stays
    hidden ('.', or 'M' for mines)."""
    fail = make_fail("minesweeper_reveal")
    check_items(fail, board, "board")
    if not board:
        fail("empty:board")
    if len(board) > MAX_SIDE:
        fail("too_many:rows")
    width = None
    for r, row in enumerate(board):
        check_str(fail, row, "board[%d]" % r)
        if width is None:
            width = len(row)
            if width == 0:
                fail("empty:board[0]")
            if width > MAX_SIDE:
                fail("too_many:cols")
        elif len(row) != width:
            fail("ragged:board[%d]" % r)
        for c in row:
            if c not in "M.":
                fail("bad_char:board")
    if len(board) * width > MAX_CELLS:
        fail("too_many:cells")
    if type(click) is not list or len(click) != 2:
        fail("bad_value:click")
    check_int(fail, click[0], "click[0]")
    check_int(fail, click[1], "click[1]")
    if not (0 <= click[0] < len(board) and 0 <= click[1] < width):
        fail("out_of_range:click")
    rows = [list(row) for row in board]
    cr, cc = click
    if rows[cr][cc] == "M":
        rows[cr][cc] = "X"
        return ["".join(row) for row in rows]

    def count_mines(r, c):
        total = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if (0 <= nr < len(board) and 0 <= nc < width
                        and board[nr][nc] == "M"):
                    total += 1
        return total

    if count_mines(cr, cc) > 0:
        rows[cr][cc] = str(count_mines(cr, cc))
        return ["".join(row) for row in rows]
    seen = {(cr, cc)}
    queue = [(cr, cc)]
    while queue:
        r, c = queue.pop()
        total = count_mines(r, c)
        rows[r][c] = str(total)
        if total == 0:
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if (0 <= nr < len(board) and 0 <= nc < width
                            and board[nr][nc] == "."
                            and (nr, nc) not in seen):
                        seen.add((nr, nc))
                        queue.append((nr, nc))
    return ["".join(row) for row in rows]


def k_closest_points_origin(points, k):
    """The k points nearest the origin, ordered by squared distance
    then input order."""
    fail = make_fail("k_closest_points_origin")
    check_items(fail, points, "points")
    for i, point in enumerate(points):
        if type(point) is not list or len(point) != 2:
            fail("bad_value:points[%d]" % i)
        check_int(fail, point[0], "points[%d][0]" % i)
        check_int(fail, point[1], "points[%d][1]" % i)
        if abs(point[0]) > MAX_POINTS or abs(point[1]) > MAX_POINTS:
            fail("out_of_range:points[%d]" % i)
    check_int(fail, k, "k")
    if k < 0 or k > len(points):
        fail("out_of_range:k")
    keyed = [(x * x + y * y, i, [x, y])
             for i, (x, y) in enumerate(points)]
    return [item[2] for item in heapq.nsmallest(k, keyed)]


def elementary_cellular_step(rule, state):
    """One step of a 1D elementary cellular automaton.

    rule is 0..255 (Wolfram code); state is a list of 0/1 cells.
    The grid wraps around: the left and right ends are neighbors.
    Returns the next state as a new list."""
    fail = make_fail("elementary_cellular_step")
    check_int(fail, rule, "rule")
    if rule < 0 or rule > 255:
        fail("out_of_range:rule")
    check_items(fail, state, "state")
    if not state:
        fail("empty:state")
    for i, v in enumerate(state):
        check_int(fail, v, "state[%d]" % i)
        if v not in (0, 1):
            fail("bad_value:state[%d]" % i)
    n = len(state)
    out = []
    for i in range(n):
        hood = (state[(i - 1) % n] << 2) | (state[i] << 1) | \
            state[(i + 1) % n]
        out.append((rule >> hood) & 1)
    return out
