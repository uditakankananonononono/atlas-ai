"""P235 concepts batch 93: replacements and additions after screens.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
push_dominoes_final and debt_settle_min_transfers replace the
two screened-out batch-89 weighted-graph entries; the other
eight are additions: digit monotonicity, pyramid transition,
word squares, broken calculator, cherry pickup, frog jump,
soup servings, and largest plus sign. Strings and lists are
capped at MAX_ITEMS entries; tighter declared caps
(MAX_DEBTORS, MAX_MONO_N, MAX_PYRAMID_BOTTOM,
MAX_SQUARE_WORDS, MAX_SQUARE_SIDE, MAX_CHERRY_N,
MAX_FROG_STONES, MAX_SOUP_UNITS, MAX_PLUS_N) are stated in
their docstrings.
"""

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_VAL = 1_000_000
MAX_DEBTORS = 12


def _int_list(fail, xs, name, lo, hi):
    check_items(fail, xs, name)
    if not xs:
        fail("empty:%s" % name)
    for i, v in enumerate(xs):
        check_int(fail, v, "%s[%d]" % (name, i))
        if v < lo or v > hi:
            fail("out_of_range:%s[%d]" % (name, i))
    return xs


def push_dominoes_final(dominoes):
    """Settled state of a row of dominoes.

    Each character is "L", "R", or "."; a pushed domino topples
    the standing neighbor next to it each second, and a standing
    domino pushed from both sides in the same second stays up.
    Already fallen dominoes never move again. The force from an
    "R" travels right and the force from an "L" travels left;
    equal arrival times cancel. Work is an estimated O(n); the
    string is capped at MAX_ITEMS characters."""
    fail = make_fail("push_dominoes_final")
    check_str(fail, dominoes, "dominoes")
    if not dominoes:
        fail("empty:dominoes")
    if len(dominoes) > MAX_ITEMS:
        fail("too_many:dominoes")
    for i, ch in enumerate(dominoes):
        if ch not in ("L", "R", "."):
            fail("bad_form:dominoes[%d]" % i)
    n = len(dominoes)
    force = [0] * n
    f = 0
    for i, ch in enumerate(dominoes):
        if ch == "R":
            f = n
        elif ch == "L":
            f = 0
        else:
            f = max(f - 1, 0)
        force[i] += f
    f = 0
    for i in range(n - 1, -1, -1):
        ch = dominoes[i]
        if ch == "L":
            f = n
        elif ch == "R":
            f = 0
        else:
            f = max(f - 1, 0)
        force[i] -= f
    return "".join(
        "R" if v > 0 else "L" if v < 0 else "." for v in force)


def debt_settle_min_transfers(balances):
    """Minimum transfers that settle every balance to zero.

    Each entry is one person's net balance (positive is owed,
    negative owes) and the entries must sum to zero, otherwise
    the input refuses. One transfer moves an amount from one
    person to another; the search settles one nonzero balance
    per transfer and backtracks over the counterparty choices,
    so its cost is exponential in the number of nonzero
    balances - that count is capped at MAX_DEBTORS and the
    list itself at MAX_ITEMS. Zero balances never take part."""
    fail = make_fail("debt_settle_min_transfers")
    xs = _int_list(fail, balances, "balances", -MAX_VAL, MAX_VAL)
    if sum(xs) != 0:
        fail("inconsistent:balances")
    active = tuple(sorted(v for v in xs if v != 0))
    if len(active) > MAX_DEBTORS:
        fail("too_many:nonzero_balances")
    memo = {}

    def settle(state):
        if not state:
            return 0
        if state in memo:
            return memo[state]
        first = state[0]
        best = len(state)
        for i in range(1, len(state)):
            if state[i] * first < 0:
                rest = list(state)
                rest[i] += first
                nxt = tuple(sorted(v for v in rest[1:] if v != 0))
                cand = 1 + settle(nxt)
                if cand < best:
                    best = cand
        memo[state] = best
        return best

    return settle(active)

MAX_MONO_N = 10 ** 18
MAX_PYRAMID_BOTTOM = 7
MAX_SQUARE_WORDS = 12
MAX_SQUARE_SIDE = 5
MAX_CHERRY_N = 50
MAX_FROG_STONES = 1_100
MAX_SOUP_UNITS = 200
MAX_PLUS_N = 30


def monotone_increasing_digits(n):
    """Largest number not exceeding n whose digits never decrease.

    n is an int in 0..MAX_MONO_N. The greedy walks to the first
    descent, steps the prefix down, and fills the suffix with
    9s, an estimated O(digits) work."""
    fail = make_fail("monotone_increasing_digits")
    check_int(fail, n, "n")
    if n < 0 or n > MAX_MONO_N:
        fail("out_of_range:n")
    d = [int(c) for c in str(n)]
    i = 1
    while i < len(d) and d[i - 1] <= d[i]:
        i += 1
    while 0 < i < len(d) and d[i - 1] > d[i]:
        d[i - 1] -= 1
        i -= 1
    for j in range(i + 1, len(d)):
        d[j] = 9
    return int("".join(map(str, d)))


def pyramid_transition_possible(bottom, allowed):
    """Whether a pyramid can rise from bottom using allowed triples.

    bottom is a string of 2..MAX_PYRAMID_BOTTOM blocks from
    "ABCDEFG"; each triple in allowed lists two supporting
    blocks followed by the block that may rest on them. The
    search tries every compatible next row depth-first; the
    branching is exponential in the bottom length, hence the
    declared cap. allowed is capped at MAX_ITEMS entries."""
    fail = make_fail("pyramid_transition_possible")
    check_str(fail, bottom, "bottom")
    if len(bottom) < 2:
        fail("out_of_range:bottom")
    if len(bottom) > MAX_PYRAMID_BOTTOM:
        fail("too_many:bottom")
    for i, ch in enumerate(bottom):
        if ch < "A" or ch > "G":
            fail("bad_form:bottom[%d]" % i)
    check_items(fail, allowed, "allowed")
    for i, t in enumerate(allowed):
        check_str(fail, t, "allowed[%d]" % i)
        if len(t) != 3 or any(c < "A" or c > "G" for c in t):
            fail("bad_form:allowed[%d]" % i)
    above = {}
    for t in allowed:
        above.setdefault(t[:2], set()).add(t[2])

    def build(row):
        if len(row) == 1:
            return True
        options = []
        for i in range(len(row) - 1):
            choices = above.get(row[i:i + 2])
            if not choices:
                return False
            options.append(sorted(choices))

        def place(i, cur):
            if i == len(options):
                return build("".join(cur))
            for ch in options[i]:
                cur.append(ch)
                if place(i + 1, cur):
                    return True
                cur.pop()
            return False

        return place(0, [])

    return build(bottom)


def word_squares_list(words):
    """All word squares buildable from the given words, sorted.

    Every word must share one length k of at most
    MAX_SQUARE_SIDE, lowercase a-z only, with no duplicates; a
    square is k words where row i and column i read the same
    for every i.
    Words may be reused within a square. The list is capped at
    MAX_SQUARE_WORDS entries; the backtracking is exponential
    in the worst case, hence both declared caps. Squares come
    back sorted lexicographically by their row tuple."""
    fail = make_fail("word_squares_list")
    check_items(fail, words, "words")
    if not words:
        fail("empty:words")
    if len(words) > MAX_SQUARE_WORDS:
        fail("too_many:words")
    side = None
    for i, w in enumerate(words):
        check_str(fail, w, "words[%d]" % i)
        if not w:
            fail("empty:words[%d]" % i)
        if side is None:
            side = len(w)
            if side > MAX_SQUARE_SIDE:
                fail("too_many:word_length")
        elif len(w) != side:
            fail("bad_shape:words[%d]" % i)
        for j, ch in enumerate(w):
            if ch < "a" or ch > "z":
                fail("bad_form:words[%d][%d]" % (i, j))
    if len(set(words)) != len(words):
        fail("bad_form:words")
    prefixes = set()
    for w in words:
        for cut in range(1, side + 1):
            prefixes.add(w[:cut])
    out = []
    square = []

    def backtrack():
        if len(square) == side:
            out.append(tuple(square))
            return
        need = "".join(square[r][len(square)] for r in range(len(square)))
        for w in words:
            if not w.startswith(need):
                continue
            square.append(w)
            ok = True
            for c in range(side):
                col = "".join(square[r][c] for r in range(len(square)))
                if col not in prefixes:
                    ok = False
                    break
            if ok:
                backtrack()
            square.pop()

    backtrack()
    return [list(sq) for sq in sorted(out)]


def broken_calculator_min_ops(start, target):
    """Minimum operations to turn start into target.

    Each operation either doubles the display or subtracts 1.
    Both values are ints in 1..MAX_VAL. The greedy runs the
    target backwards: halve when even and above start, add 1
    when odd, then walk the remaining gap down one by one; an
    estimated O(log target) work."""
    fail = make_fail("broken_calculator_min_ops")
    check_int(fail, start, "start")
    check_int(fail, target, "target")
    if start < 1 or start > MAX_VAL:
        fail("out_of_range:start")
    if target < 1 or target > MAX_VAL:
        fail("out_of_range:target")
    ops = 0
    while target > start:
        if target % 2:
            target += 1
        else:
            target //= 2
        ops += 1
    return ops + start - target


def cherry_pickup_grid(grid):
    """Most cherries collectible there and back through a grid.

    grid is an n by n list of cells, each -1 (thorn), 0, or 1
    (cherry), with 1 <= n <= MAX_CHERRY_N. The round trip is
    solved as two simultaneous right/down walks with a shared
    step count, an estimated O(n^3) work, so n is capped."""
    fail = make_fail("cherry_pickup_grid")
    check_items(fail, grid, "grid")
    if not grid:
        fail("empty:grid")
    n = len(grid)
    if n > MAX_CHERRY_N:
        fail("too_many:grid")
    for i, row in enumerate(grid):
        check_items(fail, row, "grid[%d]" % i)
        if len(row) != n:
            fail("bad_shape:grid[%d]" % i)
        for j, v in enumerate(row):
            check_int(fail, v, "grid[%d][%d]" % (i, j))
            if v < -1 or v > 1:
                fail("out_of_range:grid[%d][%d]" % (i, j))
    neg = -1
    dp = [[neg] * n for _ in range(n)]
    dp[0][0] = grid[0][0]
    for steps in range(1, 2 * n - 1):
        nxt = [[neg] * n for _ in range(n)]
        for r1 in range(max(0, steps - n + 1), min(steps, n - 1) + 1):
            c1 = steps - r1
            if grid[r1][c1] == -1:
                continue
            for r2 in range(max(0, steps - n + 1),
                            min(steps, n - 1) + 1):
                c2 = steps - r2
                if grid[r2][c2] == -1:
                    continue
                best = neg
                for pr1 in (r1 - 1, r1):
                    pc1 = steps - 1 - pr1
                    if pr1 < 0 or pc1 < 0 or pc1 >= n:
                        continue
                    for pr2 in (r2 - 1, r2):
                        pc2 = steps - 1 - pr2
                        if pr2 < 0 or pc2 < 0 or pc2 >= n:
                            continue
                        if dp[pr1][pr2] != neg and dp[pr1][pr2] > best:
                            best = dp[pr1][pr2]
                if best == neg:
                    continue
                gain = grid[r1][c1]
                if r1 != r2:
                    gain += grid[r2][c2]
                nxt[r1][r2] = best + gain
        dp = nxt
    return max(0, dp[n - 1][n - 1])


def frog_jump_river(stones):
    """Whether the frog can reach the last stone.

    stones is a strictly increasing list of ints starting at 0,
    capped at MAX_FROG_STONES entries. The first jump is exactly
    1, so a second stone must sit at position 1; every later
    jump may differ from the previous one by at most 1. The
    search marks reachable (stone, last jump) pairs, an
    estimated O(n^2) work."""
    fail = make_fail("frog_jump_river")
    check_items(fail, stones, "stones")
    if not stones:
        fail("empty:stones")
    if len(stones) > MAX_FROG_STONES:
        fail("too_many:stones")
    for i, v in enumerate(stones):
        check_int(fail, v, "stones[%d]" % i)
        if v < 0 or v > MAX_VAL:
            fail("out_of_range:stones[%d]" % i)
        if i and v <= stones[i - 1]:
            fail("bad_form:stones[%d]" % i)
    if stones[0] != 0:
        fail("bad_form:stones[0]")
    if len(stones) == 1:
        return True
    if stones[1] != 1:
        fail("bad_form:stones[1]")
    index = {v: i for i, v in enumerate(stones)}
    seen = set()
    stack = [(1, 1)]
    last = len(stones) - 1
    while stack:
        i, k = stack.pop()
        if i == last:
            return True
        if (i, k) in seen:
            continue
        seen.add((i, k))
        for step in (k - 1, k, k + 1):
            if step >= 1 and stones[i] + step in index:
                stack.append((index[stones[i] + step], step))
    return False


def soup_servings_probability(n_ml):
    """Exact probability that soup A empties first, ties split.

    n_ml is a multiple of 25 in 0..MAX_SOUP_UNITS * 25. Each
    second one of four serves happens with equal probability:
    (100, 0), (75, 25), (50, 50), (25, 75) ml from (A, B).
    The recursion is memoized and exact with Fractions; the
    declared cap keeps the state space bounded."""
    from fractions import Fraction
    fail = make_fail("soup_servings_probability")
    check_int(fail, n_ml, "n_ml")
    if n_ml < 0 or n_ml > MAX_SOUP_UNITS * 25:
        fail("out_of_range:n_ml")
    if n_ml % 25 != 0:
        fail("bad_form:n_ml")
    memo = {}

    def f(a, b):
        if a <= 0 and b <= 0:
            return Fraction(1, 2)
        if a <= 0:
            return Fraction(1)
        if b <= 0:
            return Fraction(0)
        key = (a, b)
        if key not in memo:
            memo[key] = (f(a - 100, b) + f(a - 75, b - 25)
                         + f(a - 50, b - 50)
                         + f(a - 25, b - 75)) / 4
        return memo[key]

    return f(n_ml, n_ml)


def largest_plus_sign_order(n, mines):
    """Order of the largest plus of 1s avoiding the mined cells.

    The grid is n by n with 1 <= n <= MAX_PLUS_N; mines is a
    list of unique [row, col] pairs inside the grid, capped at
    MAX_ITEMS entries. Arms are counted directionally, an
    estimated O(n^2) work; an empty answer (every cell mined)
    is 0."""
    fail = make_fail("largest_plus_sign_order")
    check_int(fail, n, "n")
    if n < 1 or n > MAX_PLUS_N:
        fail("out_of_range:n")
    check_items(fail, mines, "mines")
    mined = set()
    for i, pair in enumerate(mines):
        if type(pair) is not list or len(pair) != 2:
            fail("bad_shape:mines[%d]" % i)
        check_int(fail, pair[0], "mines[%d][0]" % i)
        check_int(fail, pair[1], "mines[%d][1]" % i)
        if not (0 <= pair[0] < n) or not (0 <= pair[1] < n):
            fail("out_of_range:mines[%d]" % i)
        key = (pair[0], pair[1])
        if key in mined:
            fail("bad_form:mines[%d]" % i)
        mined.add(key)
    arms = [[0] * n for _ in range(n)]
    for r in range(n):
        run = 0
        for c in range(n):
            run = 0 if (r, c) in mined else run + 1
            arms[r][c] = run
        run = 0
        for c in range(n - 1, -1, -1):
            run = 0 if (r, c) in mined else run + 1
            if run < arms[r][c]:
                arms[r][c] = run
    best = 0
    for c in range(n):
        run = 0
        for r in range(n):
            run = 0 if (r, c) in mined else run + 1
            if run < arms[r][c]:
                arms[r][c] = run
        run = 0
        for r in range(n - 1, -1, -1):
            run = 0 if (r, c) in mined else run + 1
            if run < arms[r][c]:
                arms[r][c] = run
            if arms[r][c] > best:
                best = arms[r][c]
    return best
