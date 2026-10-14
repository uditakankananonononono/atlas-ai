"""P235 concepts batch 101: five concepts.

Five small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
Lists are capped at MAX_ITEMS entries; tighter caps
(MAX_INTERP_POINTS, MAX_BF_PROGRAM, MAX_BF_CELLS,
MAX_BF_STEPS, MAX_BF_INPUT, MAX_ANT_STEPS, MAX_TS_P) are
stated in the docstrings of the functions that carry them.
Every function validates its whole input first: length caps are
checked before the elements they bound are inspected, then
type, range, and shape checks run during the validation phase,
and the computation phase starts only after validation
succeeds. Exact arithmetic uses ints and Fractions only.
"""

from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_INTERP_POINTS = 16
MAX_BF_PROGRAM = MAX_ITEMS
MAX_BF_CELLS = 4096
MAX_BF_STEPS = 10**6
MAX_BF_INPUT = 1024
MAX_ANT_STEPS = 20000
MAX_TS_P = 10**6
MAX_VAL = 10**9


def lagrange_interpolate(points, x):
    """Value at x of the unique polynomial through the points.

    points holds 1..MAX_INTERP_POINTS rows [xi, yi] of ints
    with absolute value at most MAX_VAL and distinct xi values.
    x is an int with absolute value at most MAX_VAL. Evaluates
    the Lagrange basis directly: sum over i of y_i times the
    product over j != i of (x - x_j) / (x_i - x_j). Returns an
    exact Fraction (an int-valued result still returns a
    Fraction with denominator 1). Deterministic; an estimated
    O(n^2) work for n points."""
    fail = make_fail("lagrange_interpolate")
    check_items(fail, points, "points")
    if not points:
        fail("empty:points")
    if len(points) > MAX_INTERP_POINTS:
        fail("too_many:points")
    seen = set()
    for i, pt in enumerate(points):
        check_items(fail, pt, "points[%d]" % i)
        if len(pt) != 2:
            fail("bad_shape:points[%d]" % i)
        for j, v in enumerate(pt):
            check_int(fail, v, "points[%d][%d]" % (i, j))
            if v < -MAX_VAL or v > MAX_VAL:
                fail("out_of_range:points[%d][%d]" % (i, j))
        if pt[0] in seen:
            fail("duplicate:points[%d]" % i)
        seen.add(pt[0])
    check_int(fail, x, "x")
    if x < -MAX_VAL or x > MAX_VAL:
        fail("out_of_range:x")
    total = Fraction(0)
    n = len(points)
    for i in range(n):
        xi, yi = points[i]
        term = Fraction(yi)
        for j in range(n):
            if j != i:
                term *= Fraction(x - points[j][0],
                                 xi - points[j][0])
        total += term
    return total


_BF_COMMANDS = set("><+-.,[]")


def brainfuck_interpret(program, input_text):
    """Output bytes of a Brainfuck program.

    program is capped at MAX_BF_PROGRAM characters; only the
    eight command characters ><+-.,[] execute and every other
    character is ignored, but brackets must balance. The tape
    has MAX_BF_CELLS cells holding wrapping bytes 0..255 and
    starts zeroed; moving the pointer outside the tape refuses.
    input_text (capped at MAX_BF_INPUT characters) is consumed
    by ',' as UTF-8 bytes, and reads past its end yield 0.
    Output bytes from '.' are returned as a list of ints
    0..255. At most MAX_BF_STEPS commands execute before a
    too_complex refusal."""
    fail = make_fail("brainfuck_interpret")
    check_str(fail, program, "program")
    if len(program) > MAX_BF_PROGRAM:
        fail("too_long:program")
    check_str(fail, input_text, "input_text")
    if len(input_text) > MAX_BF_INPUT:
        fail("too_long:input_text")
    try:
        data_in = input_text.encode("utf-8")
    except UnicodeEncodeError:
        fail("bad_char:input_text")
    code = [ch for ch in program if ch in _BF_COMMANDS]
    jump = {}
    stack = []
    for i, ch in enumerate(code):
        if ch == "[":
            stack.append(i)
        elif ch == "]":
            if not stack:
                fail("unmatched:program")
            open_i = stack.pop()
            jump[open_i] = i
            jump[i] = open_i
    if stack:
        fail("unmatched:program")
    tape = [0] * MAX_BF_CELLS
    ptr = 0
    read = 0
    out = []
    pc = 0
    steps = 0
    n = len(code)
    while pc < n:
        if steps >= MAX_BF_STEPS:
            fail("too_complex:program")
        steps += 1
        ch = code[pc]
        if ch == ">":
            ptr += 1
            if ptr >= MAX_BF_CELLS:
                fail("out_of_tape:program")
        elif ch == "<":
            ptr -= 1
            if ptr < 0:
                fail("out_of_tape:program")
        elif ch == "+":
            tape[ptr] = (tape[ptr] + 1) & 255
        elif ch == "-":
            tape[ptr] = (tape[ptr] - 1) & 255
        elif ch == ".":
            out.append(tape[ptr])
        elif ch == ",":
            tape[ptr] = data_in[read] if read < len(data_in) else 0
            read += 1
        elif ch == "[":
            if tape[ptr] == 0:
                pc = jump[pc]
        elif ch == "]":
            if tape[ptr] != 0:
                pc = jump[pc]
        pc += 1
    return out


def langtons_ant(steps):
    """State of Langton's ant after the given number of steps.

    steps is a non-negative int capped at MAX_ANT_STEPS. The
    ant starts at (0, 0) facing north (direction 0; 1 east,
    2 south, 3 west) on an unbounded white grid. Each step: on
    white turn right, on black turn left, flip the cell, move
    one cell. Returns [x, y, direction, black_cells] with x
    growing east and y growing north. Deterministic; exactly
    steps iterations."""
    fail = make_fail("langtons_ant")
    check_int(fail, steps, "steps")
    if steps < 0 or steps > MAX_ANT_STEPS:
        fail("out_of_range:steps")
    black = set()
    x = y = 0
    direction = 0
    dx = (0, 1, 0, -1)
    dy = (1, 0, -1, 0)
    for _ in range(steps):
        pos = (x, y)
        if pos in black:
            direction = (direction - 1) & 3
            black.discard(pos)
        else:
            direction = (direction + 1) & 3
            black.add(pos)
        x += dx[direction]
        y += dy[direction]
    return [x, y, direction, len(black)]


def tonelli_shanks(n, p):
    """Square root of n modulo the prime p, or None.

    p is a prime 3..MAX_TS_P (trial-divided); n is an int with
    absolute value at most MAX_VAL, reduced to [0, p). Returns
    the smaller root r with r * r === n (mod p) when n is a
    quadratic residue (0 maps to 0), or None for a non-residue.
    Uses the Tonelli-Shanks algorithm after an Euler-criterion
    check. Deterministic; an estimated O(log^2 p) modular
    operations."""
    fail = make_fail("tonelli_shanks")
    check_int(fail, p, "p")
    if p < 3 or p > MAX_TS_P:
        fail("out_of_range:p")
    check_int(fail, n, "n")
    if n < -MAX_VAL or n > MAX_VAL:
        fail("out_of_range:n")
    for d in range(2, int(p ** 0.5) + 1):
        if p % d == 0:
            fail("not_prime:p")
    n %= p
    if n == 0:
        return 0
    if pow(n, (p - 1) // 2, p) != 1:
        return None
    q = p - 1
    s = 0
    while q % 2 == 0:
        s += 1
        q //= 2
    z = 2
    while pow(z, (p - 1) // 2, p) != p - 1:
        z += 1
    m = s
    c = pow(z, q, p)
    t = pow(n, q, p)
    r = pow(n, (q + 1) // 2, p)
    while t != 1:
        i = 1
        t2 = t * t % p
        while t2 != 1:
            t2 = t2 * t2 % p
            i += 1
        b = pow(c, 1 << (m - i - 1), p)
        m = i
        c = b * b % p
        t = t * c % p
        r = r * b % p
    return min(r, p - r)


def hamming74_decode(code):
    """Correct a Hamming(7,4) codeword and report the syndrome.

    code is an int 0..127 whose bit i-1 is position i of the
    codeword (positions 1, 2, 4 are parity bits covering
    positions whose index has that bit set). The syndrome is
    the position (1..7) of a single-bit error, or 0 for a clean
    codeword; the returned codeword has that bit flipped back.
    Returns [corrected_code, syndrome]. Multiple-bit errors
    are outside the contract (they correct to the wrong
    codeword). Deterministic; three parity sums."""
    fail = make_fail("hamming74_decode")
    check_int(fail, code, "code")
    if code < 0 or code > 127:
        fail("out_of_range:code")
    syndrome = 0
    for par in (1, 2, 4):
        total = 0
        for pos in range(1, 8):
            if pos & par:
                total ^= (code >> (pos - 1)) & 1
        if total:
            syndrome |= par
    if syndrome:
        code ^= 1 << (syndrome - 1)
    return [code, syndrome]
