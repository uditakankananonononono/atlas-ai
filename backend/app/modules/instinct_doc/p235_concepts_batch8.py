"""P235 concepts, batch 8 (numeric/matrix, 71-80). Offline, stdlib only."""
from __future__ import annotations

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_FIB_N = 10_000
MAX_COLLATZ_N = 10_000_000
MAX_DIGITAL_ROOT_DIGITS = 1_000
MAX_BINARY_STRING_BITS = 10_000
_MAX_COLLATZ_STEPS = 10_000
_MAX_BINARY_LEN = MAX_ITEMS


def _int_matrix(fail, matrix):
    check_items(fail, matrix, "matrix")
    cells = 0
    width = None
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
    return width or 0


def transpose_matrix(matrix):
    fail = make_fail("transpose_matrix")
    _int_matrix(fail, matrix)
    if not matrix:
        return []
    return [[matrix[i][j] for i in range(len(matrix))]
            for j in range(len(matrix[0]))]


def diagonal_sum(matrix):
    fail = make_fail("diagonal_sum")
    if not matrix:
        fail("empty:matrix")
    width = _int_matrix(fail, matrix)
    if width != len(matrix):
        fail("not_square:matrix")
    return sum(matrix[i][i] for i in range(len(matrix)))


def fibonacci_term(n):
    fail = make_fail("fibonacci_term")
    check_int(fail, n, "n")
    if n < 0:
        fail("bad_value:n")
    if n > MAX_FIB_N:
        fail("too_many:n")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def collatz_steps(n):
    fail = make_fail("collatz_steps")
    check_int(fail, n, "n")
    if n < 1:
        fail("bad_value:n")
    if n > MAX_COLLATZ_N:
        fail("too_many:n")
    steps = 0
    while n != 1:
        if steps >= _MAX_COLLATZ_STEPS:
            fail("too_many:steps")
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        steps += 1
    return steps


def digital_root(n):
    fail = make_fail("digital_root")
    check_int(fail, n, "n")
    if n < 0:
        fail("bad_value:n")
    if n >= 10 ** MAX_DIGITAL_ROOT_DIGITS:
        fail("too_many:n")
    while n >= 10:
        n = sum(int(d) for d in str(n))
    return n


def is_power_of_two(n):
    fail = make_fail("is_power_of_two")
    check_int(fail, n, "n")
    if n < 1:
        fail("bad_value:n")
    return (n & (n - 1)) == 0


def binary_string_to_int(text):
    fail = make_fail("binary_string_to_int")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > _MAX_BINARY_LEN:
        fail("too_many:text")
    for i, ch in enumerate(text):
        if ch not in "01":
            fail("bad_value:text[%d]" % i)
    return int(text, 2)


def int_to_binary_string(n):
    fail = make_fail("int_to_binary_string")
    check_int(fail, n, "n")
    if n < 0:
        fail("bad_value:n")
    if n.bit_length() > MAX_BINARY_STRING_BITS:
        fail("too_many:n")
    return bin(n)[2:]


def pairwise_swap_adjacent(items):
    fail = make_fail("pairwise_swap_adjacent")
    check_items(fail, items)
    for i, v in enumerate(items):
        check_str(fail, v, "items[%d]" % i)
    out = list(items)
    for i in range(0, len(out) - 1, 2):
        out[i], out[i + 1] = out[i + 1], out[i]
    return out


def sum_of_squares_exact(items):
    fail = make_fail("sum_of_squares_exact")
    check_items(fail, items)
    total = 0
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        total += v * v
    return total
