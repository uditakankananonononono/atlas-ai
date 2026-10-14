"""P235 concepts batch 80: state-space search and expression evaluation.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
"""

from collections import deque
from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_N = 100_000
MAX_TEXT = 2_000
MAX_OUT = 100_000
MAX_WORD = 32
MAX_SIDE = 20
MAX_CELLS = 10_000
MAX_PAIRS = 1_000
MAX_NAME = 8
MAX_DIALER = 1_000


def _lower_word(fail, w, name):
    check_str(fail, w, name)
    if not w:
        fail("empty:%s" % name)
    if len(w) > MAX_WORD:
        fail("too_long:%s" % name)
    for c in w:
        if not ("a" <= c <= "z"):
            fail("bad_char:%s" % name)


def word_ladder_length(begin, end, word_list):
    """Shortest transformation chain from begin to end.

    Each step changes exactly one letter; every intermediate word
    must appear in word_list. Returns the chain length in words
    (begin counts as 1), or 0 when no chain exists. end itself must
    be in word_list.
    """
    fail = make_fail("word_ladder_length")
    _lower_word(fail, begin, "begin")
    _lower_word(fail, end, "end")
    if len(begin) != len(end):
        fail("mismatch:length")
    check_items(fail, word_list, "word_list")
    if not word_list:
        fail("empty:word_list")
    words = set()
    for i, w in enumerate(word_list):
        _lower_word(fail, w, "word_list[%d]" % i)
        if len(w) != len(begin):
            fail("mismatch:word_list[%d]" % i)
        words.add(w)
    if end not in words:
        return 0
    if begin == end:
        return 1
    patterns = {}
    for w in words:
        for j in range(len(w)):
            patterns.setdefault(w[:j] + " " + w[j + 1:], []).append(w)
    seen = {begin}
    queue = deque([(begin, 1)])
    while queue:
        word, depth = queue.popleft()
        for j in range(len(word)):
            for nxt in patterns.get(word[:j] + " " + word[j + 1:], ()):
                if nxt == end:
                    return depth + 1
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, depth + 1))
    return 0


def _digit4(fail, code, name):
    check_str(fail, code, name)
    if len(code) != 4:
        fail("bad_length:%s" % name)
    for c in code:
        if not ("0" <= c <= "9"):
            fail("bad_char:%s" % name)


def open_lock_min_turns(target, deadends):
    """Fewest wheel turns to reach target from "0000".

    Each turn rotates one of the four wheels by one click, up or
    down; dead-end combinations block the search, including the
    target itself: a dead target is unreachable. Returns -1 when
    the target cannot be reached.
    """
    fail = make_fail("open_lock_min_turns")
    _digit4(fail, target, "target")
    check_items(fail, deadends, "deadends")
    dead = set()
    for i, d in enumerate(deadends):
        _digit4(fail, d, "deadends[%d]" % i)
        dead.add(d)
    start = "0000"
    if start in dead:
        return -1
    if target == start:
        return 0
    if target in dead:
        return -1
    seen = {start} | dead
    queue = deque([(start, 0)])
    while queue:
        code, dist = queue.popleft()
        digits = [int(c) for c in code]
        for pos in range(4):
            for step in (1, 9):
                moved = digits[:]
                moved[pos] = (moved[pos] + step) % 10
                nxt = "".join(str(v) for v in moved)
                if nxt == target:
                    return dist + 1
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, dist + 1))
    return -1


_SLIDING_GOAL = (1, 2, 3, 4, 5, 0)
_SLIDING_MOVES = ((1, 3), (0, 2, 4), (1, 5), (0, 4), (1, 3, 5), (2, 4))


def sliding_puzzle_min_moves(board):
    """Fewest slides to solve a 2x3 sliding puzzle.

    board is two rows of three values holding each of 0..5 exactly
    once; 0 is the blank. The goal is [[1, 2, 3], [4, 5, 0]].
    Returns -1 when the board cannot be solved.
    """
    fail = make_fail("sliding_puzzle_min_moves")
    check_items(fail, board, "board")
    if len(board) != 2:
        fail("bad_shape:board")
    flat = []
    for r in range(2):
        row = board[r]
        if type(row) is not list or len(row) != 3:
            fail("bad_shape:board[%d]" % r)
        for c in range(3):
            v = row[c]
            check_int(fail, v, "board[%d][%d]" % (r, c))
            if v < 0 or v > 5:
                fail("out_of_range:board[%d][%d]" % (r, c))
            flat.append(v)
    if sorted(flat) != [0, 1, 2, 3, 4, 5]:
        fail("bad_value:tiles")
    start = tuple(flat)
    if start == _SLIDING_GOAL:
        return 0
    seen = {start}
    queue = deque([(start, 0)])
    while queue:
        state, dist = queue.popleft()
        blank = state.index(0)
        for dest in _SLIDING_MOVES[blank]:
            nxt = list(state)
            nxt[blank], nxt[dest] = nxt[dest], nxt[blank]
            nxt = tuple(nxt)
            if nxt == _SLIDING_GOAL:
                return dist + 1
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, dist + 1))
    return -1


def snakes_and_ladders_min_throws(squares):
    """Fewest dice throws to reach the last square exactly.

    squares is the flat board in label order: squares[i] is -1 when
    label i + 1 is plain, otherwise the label the piece must move to
    on landing (a snake or a ladder, taken at most once per throw,
    never to the square itself). Rolls that overshoot the last
    square are not available. Returns -1 when unreachable.
    """
    fail = make_fail("snakes_and_ladders_min_throws")
    check_items(fail, squares, "squares")
    n = 0
    while n * n < len(squares):
        n += 1
    if n * n != len(squares) or n < 2:
        fail("bad_shape:squares")
    if n > MAX_SIDE:
        fail("too_many:squares")
    last = n * n
    jump = [None] * (last + 1)
    for i, v in enumerate(squares):
        check_int(fail, v, "squares[%d]" % i)
        if v == -1:
            continue
        if v < 1 or v > last:
            fail("out_of_range:squares[%d]" % i)
        if v == i + 1:
            fail("bad_value:squares[%d]" % i)
        jump[i + 1] = v
    if last == 1:
        return 0
    seen = {1}
    queue = deque([(1, 0)])
    while queue:
        cur, dist = queue.popleft()
        for die in range(1, 7):
            nxt = cur + die
            if nxt > last:
                break
            if jump[nxt] is not None:
                nxt = jump[nxt]
            if nxt == last:
                return dist + 1
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, dist + 1))
    return -1


def shortest_path_collect_keys(grid):
    """Fewest steps to collect every key on a grid.

    Rows are strings: '.' floor, '#' wall, '@' start, 'a'-'f' keys,
    'A'-'F' locks that open only with the matching key. Exactly one
    start. A lock without its key anywhere on the grid is a refusal.
    Returns -1 when some key cannot be reached.
    """
    fail = make_fail("shortest_path_collect_keys")
    check_items(fail, grid, "grid")
    if not grid:
        fail("empty:grid")
    if len(grid) > 100:
        fail("too_many:rows")
    rows = []
    width = None
    for r, row in enumerate(grid):
        check_str(fail, row, "grid[%d]" % r)
        if width is None:
            width = len(row)
            if width == 0:
                fail("empty:grid[0]")
            if width > 100:
                fail("too_many:cols")
        elif len(row) != width:
            fail("ragged:grid[%d]" % r)
        rows.append(row)
    if len(rows) * width > MAX_CELLS:
        fail("too_many:cells")
    start = None
    keys = set()
    locks = set()
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch in ".#":
                continue
            if ch == "@":
                if start is not None:
                    fail("bad_value:multiple_start")
                start = (r, c)
            elif "a" <= ch <= "f":
                keys.add(ch)
            elif "A" <= ch <= "F":
                locks.add(ch)
            else:
                fail("bad_char:grid[%d]" % r)
    if start is None:
        fail("bad_value:no_start")
    for lock in locks:
        if lock.lower() not in keys:
            fail("bad_value:lock_without_key")
    total = len(keys)
    if total == 0:
        return 0
    seen = {(start[0], start[1], 0)}
    queue = deque([(start[0], start[1], 0, 0)])
    while queue:
        r, c, mask, dist = queue.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nr, nc = r + dr, c + dc
            if not (0 <= nr < len(rows) and 0 <= nc < width):
                continue
            ch = rows[nr][nc]
            if ch == "#":
                continue
            if "A" <= ch <= "F" and not (mask >> (ord(ch) - ord("A"))) & 1:
                continue
            nmask = mask
            if "a" <= ch <= "f":
                nmask = mask | (1 << (ord(ch) - ord("a")))
                if nmask.bit_count() == total:
                    return dist + 1
            state = (nr, nc, nmask)
            if state not in seen:
                seen.add(state)
                queue.append((nr, nc, nmask, dist + 1))
    return -1


_KNIGHT_DIAL = ((4, 6), (6, 8), (7, 9), (4, 8), (0, 3, 9), (),
                (0, 1, 7), (2, 6), (1, 3), (4, 2))


def knight_dialer_count(n):
    """Number of distinct length-n dial sequences a chess knight
    can hop on the phone keypad (digits 0-9 in the classic 3x3 plus
    bottom-row 0 layout). Exact integer, no modulus."""
    fail = make_fail("knight_dialer_count")
    check_int(fail, n, "n")
    if n < 1 or n > MAX_DIALER:
        fail("out_of_range:n")
    counts = [1] * 10
    for _ in range(n - 1):
        nxt = [0] * 10
        for d in range(10):
            for src in _KNIGHT_DIAL[d]:
                nxt[d] += counts[src]
        counts = nxt
    return sum(counts)


def _ratio_name(fail, name, label):
    check_str(fail, name, label)
    if not name:
        fail("empty:%s" % label)
    if len(name) > MAX_NAME:
        fail("too_long:%s" % label)
    for c in name:
        if not ("a" <= c <= "z"):
            fail("bad_char:%s" % label)


def evaluate_ratio_queries(pairs, queries):
    """Answers ratio queries over a web of exact exchange rates.

    pairs holds [a, b, [num, den]] meaning a / b = num / den with
    den > 0. Each query [c, d] answers c / d as an exact Fraction,
    or None when c or d is unknown or no chain of rates connects
    them. Rates may conflict; the first rate stated for a connected
    pair wins, later contradictory rates are refusals.
    """
    fail = make_fail("evaluate_ratio_queries")
    check_items(fail, pairs, "pairs")
    if len(pairs) > MAX_PAIRS:
        fail("too_many:pairs")
    parent = {}

    def find(x):
        chain = []
        while parent[x][0] != x:
            chain.append(x)
            x = parent[x][0]
        root = x
        acc = Fraction(1)
        for node in reversed(chain):
            acc *= parent[node][1]
            parent[node] = (root, acc)
        return root

    def weight_to_root(x):
        find(x)
        return parent[x][1]

    def union(a, b, ratio, idx):
        if a not in parent:
            parent[a] = (a, Fraction(1))
        if b not in parent:
            parent[b] = (b, Fraction(1))
        ra, rb = find(a), find(b)
        if ra == rb:
            implied = weight_to_root(a) / weight_to_root(b)
            if implied != ratio:
                fail("conflict:pairs[%d]" % idx)
            return
        wa = weight_to_root(a)
        wb = weight_to_root(b)
        parent[ra] = (rb, ratio * wb / wa)

    for i, pair in enumerate(pairs):
        if type(pair) is not list or len(pair) != 3:
            fail("bad_value:pairs[%d]" % i)
        a, b, value = pair
        _ratio_name(fail, a, "pairs[%d][0]" % i)
        _ratio_name(fail, b, "pairs[%d][1]" % i)
        if a == b:
            fail("bad_value:pairs[%d]" % i)
        if type(value) is not list or len(value) != 2:
            fail("bad_value:pairs[%d][2]" % i)
        check_int(fail, value[0], "pairs[%d][2][0]" % i)
        check_int(fail, value[1], "pairs[%d][2][1]" % i)
        if value[1] <= 0:
            fail("bad_value:pairs[%d][2][1]" % i)
        if value[0] == 0:
            fail("bad_value:pairs[%d][2][0]" % i)
        if abs(value[0]) > MAX_N or value[1] > MAX_N:
            fail("out_of_range:pairs[%d][2]" % i)
        union(a, b, Fraction(value[0], value[1]), i)

    check_items(fail, queries, "queries")
    if len(queries) > MAX_PAIRS:
        fail("too_many:queries")
    out = []
    for i, query in enumerate(queries):
        if type(query) is not list or len(query) != 2:
            fail("bad_value:queries[%d]" % i)
        c, d = query
        _ratio_name(fail, c, "queries[%d][0]" % i)
        _ratio_name(fail, d, "queries[%d][1]" % i)
        if c not in parent or d not in parent or find(c) != find(d):
            out.append(None)
        else:
            out.append(weight_to_root(c) / weight_to_root(d))
    return out


def decode_string_nested(text):
    """Expands a nested run-length string such as "3[a2[c]]".

    Counts are 1..300 and always precede a bracket group; letters
    are lowercase ASCII. The expanded output is capped."""
    fail = make_fail("decode_string_nested")
    check_str(fail, text, "text")
    if len(text) > MAX_TEXT:
        fail("too_long:text")
    stack = []
    pieces = []
    multiplier = 1
    level_len = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if "0" <= ch <= "9":
            j = i
            while j < len(text) and "0" <= text[j] <= "9":
                j += 1
            count = int(text[i:j])
            if count < 1 or count > 300:
                fail("out_of_range:count")
            if j >= len(text) or text[j] != "[":
                fail("bad_syntax:text")
            stack.append((pieces, multiplier, level_len))
            pieces = []
            multiplier = count
            level_len = 0
            i = j + 1
        elif "a" <= ch <= "z":
            pieces.append(ch)
            level_len += 1
            if level_len > MAX_OUT:
                fail("too_large:output")
            i += 1
        elif ch == "]":
            if not stack:
                fail("unbalanced:text")
            outer, outer_mult, outer_len = stack.pop()
            grown = outer_len + multiplier * level_len
            if grown > MAX_OUT:
                fail("too_large:output")
            segment = "".join(pieces)
            outer.append(segment * multiplier)
            pieces = outer
            multiplier = outer_mult
            level_len = grown
            i += 1
        else:
            fail("bad_char:text")
    if stack:
        fail("unbalanced:text")
    result = "".join(pieces)
    return result


def basic_calculator_eval(text):
    """Evaluates an infix arithmetic string.

    Non-negative integer literals, '+', '-', '*', '/', parentheses
    and spaces only; no unary operators. Division truncates toward
    zero. Precedence is the usual one; the result is an int.
    """
    fail = make_fail("basic_calculator_eval")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > MAX_TEXT:
        fail("too_long:text")
    tokens = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == " ":
            i += 1
            continue
        if "0" <= ch <= "9":
            j = i
            while j < len(text) and "0" <= text[j] <= "9":
                j += 1
            if j - i > 18:
                fail("too_long:literal")
            tokens.append(int(text[i:j]))
            i = j
            continue
        if ch in "+-*/()":
            tokens.append(ch)
            i += 1
            continue
        fail("bad_char:text")
    prec = {"+": 1, "-": 1, "*": 2, "/": 2}
    values = []
    ops = []

    def apply_top():
        y = values.pop()
        x = values.pop()
        op = ops.pop()
        if op == "+":
            values.append(x + y)
        elif op == "-":
            values.append(x - y)
        elif op == "*":
            values.append(x * y)
        else:
            if y == 0:
                fail("bad_value:division_by_zero")
            q = abs(x) // abs(y)
            values.append(q if (x < 0) == (y < 0) else -q)

    expect_operand = True
    for t in tokens:
        if type(t) is int:
            if not expect_operand:
                fail("bad_syntax:text")
            values.append(t)
            expect_operand = False
        elif t == "(":
            if not expect_operand:
                fail("bad_syntax:text")
            ops.append(t)
        elif t == ")":
            if expect_operand:
                fail("bad_syntax:text")
            while ops and ops[-1] != "(":
                apply_top()
            if not ops:
                fail("unbalanced:text")
            ops.pop()
            expect_operand = False
        else:
            if expect_operand:
                fail("bad_syntax:text")
            while (ops and ops[-1] != "("
                   and prec[ops[-1]] >= prec[t]):
                apply_top()
            ops.append(t)
            expect_operand = True
    if expect_operand:
        fail("bad_syntax:text")
    while ops:
        if ops[-1] == "(":
            fail("unbalanced:text")
        apply_top()
    if len(values) != 1:
        fail("bad_syntax:text")
    return values[0]


def task_scheduler_min_time(tasks, cooldown):
    """Least intervals to finish all tasks with a cooldown.

    tasks holds single uppercase ASCII letters; between two runs of
    the same task there must be exactly cooldown or more intervals
    of other work or idle (cooldown 2 reads as A _ _ A). Idle slots
    count. Returns the total schedule length."""
    fail = make_fail("task_scheduler_min_time")
    check_items(fail, tasks, "tasks")
    if not tasks:
        fail("empty:tasks")
    counts = {}
    for i, t in enumerate(tasks):
        check_str(fail, t, "tasks[%d]" % i)
        if len(t) != 1 or not ("A" <= t <= "Z"):
            fail("bad_value:tasks[%d]" % i)
        counts[t] = counts.get(t, 0) + 1
    check_int(fail, cooldown, "cooldown")
    if cooldown < 0 or cooldown > MAX_ITEMS:
        fail("out_of_range:cooldown")
    top = max(counts.values())
    n_top = sum(1 for v in counts.values() if v == top)
    return max(len(tasks), (top - 1) * (cooldown + 1) + n_top)
