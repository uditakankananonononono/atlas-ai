"""P235 concepts batch 59: graph transpose and matrix operations.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
"""

from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_DIM = 200
MAX_NODES = 10_000


def _matrix(fail, values, name="matrix"):
    check_items(fail, values, name)
    if not values:
        fail("empty:%s" % name)
    if len(values) > MAX_DIM:
        fail("too_many:%s" % name)
    width = None
    cells = 0
    for i, row in enumerate(values):
        if type(row) is not list:
            fail("bad_type:%s[%d]" % (name, i))
        if not row:
            fail("empty:%s[%d]" % (name, i))
        if len(row) > MAX_DIM:
            fail("too_many:%s[%d]" % (name, i))
        if width is None:
            width = len(row)
        elif len(row) != width:
            fail("not_rectangular:%s" % name)
        cells += len(row)
        if cells > MAX_ITEMS:
            fail("too_many:%s" % name)
    return width


def _int_matrix(fail, values, name="matrix"):
    width = _matrix(fail, values, name)
    for i, row in enumerate(values):
        for j, v in enumerate(row):
            check_int(fail, v, "%s[%d][%d]" % (name, i, j))
    return width


def _square(fail, values, width, name="matrix"):
    if width != len(values):
        fail("not_square:%s" % name)


def transpose_graph(nodes, edges):
    """Reverse every edge of a directed graph.

    nodes is a list of unique non-empty ASCII names; edges is a list
    of [from, to] name pairs. Returns the edges with each pair
    swapped, in the input order.
    """
    fail = make_fail("transpose_graph")
    check_items(fail, nodes, "nodes")
    if not nodes:
        fail("empty:nodes")
    if len(nodes) > MAX_NODES:
        fail("too_many:nodes")
    seen = set()
    for i, n in enumerate(nodes):
        check_str(fail, n, "nodes[%d]" % i)
        if not n:
            fail("empty:nodes[%d]" % i)
        if not n.isascii():
            fail("bad_value:nodes[%d]" % i)
        if n in seen:
            fail("duplicate_node:%s" % n)
        seen.add(n)
    check_items(fail, edges, "edges")
    if len(edges) > MAX_ITEMS:
        fail("too_many:edges")
    out = []
    for i, e in enumerate(edges):
        if type(e) is not list or len(e) != 2:
            fail("bad_type:edges[%d]" % i)
        check_str(fail, e[0], "edges[%d][0]" % i)
        check_str(fail, e[1], "edges[%d][1]" % i)
        if e[0] not in seen:
            fail("unknown_node:edges[%d][0]" % i)
        if e[1] not in seen:
            fail("unknown_node:edges[%d][1]" % i)
        out.append([e[1], e[0]])
    return out


def matrix_minor_exact(matrix, row, col):
    """Submatrix of an int matrix dropping one row and one column.

    Refuses a matrix whose remaining shape would be empty.
    """
    fail = make_fail("matrix_minor_exact")
    width = _int_matrix(fail, matrix)
    check_int(fail, row, "row")
    check_int(fail, col, "col")
    if row < 0 or row >= len(matrix):
        fail("out_of_range:row")
    if col < 0 or col >= width:
        fail("out_of_range:col")
    if len(matrix) < 2 or width < 2:
        fail("bad_value:degenerate_minor")
    return [[v for j, v in enumerate(r) if j != col]
            for i, r in enumerate(matrix) if i != row]


def matrix_add_exact(a, b):
    """Elementwise sum of two equal-shape int matrices."""
    fail = make_fail("matrix_add_exact")
    wa = _int_matrix(fail, a, "a")
    wb = _int_matrix(fail, b, "b")
    if len(a) != len(b) or wa != wb:
        fail("shape_mismatch")
    return [[x + y for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def matrix_scale_exact(matrix, k):
    """Scale every cell of an int matrix by an int factor."""
    fail = make_fail("matrix_scale_exact")
    _int_matrix(fail, matrix)
    check_int(fail, k, "k")
    return [[v * k for v in row] for row in matrix]


def markov_matrix_check(matrix):
    """Whether rows of non-negative exact numbers each sum to 1.

    Cells may be ints or Fractions; the matrix must be square.
    Every cell is validated (type and sign) before any row verdict
    is returned, so a bad cell is never masked by an early False.
    """
    fail = make_fail("markov_matrix_check")
    width = _matrix(fail, matrix)
    _square(fail, matrix, width)
    rows = []
    for i, row in enumerate(matrix):
        frow = []
        for j, v in enumerate(row):
            if type(v) is int:
                fv = Fraction(v)
            elif type(v) is Fraction:
                fv = v
            else:
                fail("bad_type:matrix[%d][%d]" % (i, j))
            if fv < 0:
                fail("bad_value:matrix[%d][%d]" % (i, j))
            frow.append(fv)
        rows.append(frow)
    for frow in rows:
        if sum(frow, Fraction(0)) != 1:
            return False
    return True


def symmetric_matrix_check(matrix):
    """Whether a square int matrix equals its transpose."""
    fail = make_fail("symmetric_matrix_check")
    width = _int_matrix(fail, matrix)
    _square(fail, matrix, width)
    n = len(matrix)
    for i in range(n):
        for j in range(i + 1, n):
            if matrix[i][j] != matrix[j][i]:
                return False
    return True


def reflect_matrix_horizontal(matrix):
    """Reverse every row of an int matrix (left-right flip)."""
    fail = make_fail("reflect_matrix_horizontal")
    _int_matrix(fail, matrix)
    return [list(reversed(row)) for row in matrix]


def argmax_2d(matrix):
    """[row, col] of the maximum cell, first in row-major order."""
    fail = make_fail("argmax_2d")
    _int_matrix(fail, matrix)
    best = [0, 0]
    for i, row in enumerate(matrix):
        for j, v in enumerate(row):
            if v > matrix[best[0]][best[1]]:
                best = [i, j]
    return best


def skew_symmetric_matrix_check(matrix):
    """Whether a square int matrix equals its negated transpose."""
    fail = make_fail("skew_symmetric_matrix_check")
    width = _int_matrix(fail, matrix)
    _square(fail, matrix, width)
    n = len(matrix)
    for i in range(n):
        if matrix[i][i] != 0:
            return False
        for j in range(i + 1, n):
            if matrix[i][j] != -matrix[j][i]:
                return False
    return True


def upper_triangular_check(matrix):
    """Whether a square int matrix is zero below the diagonal."""
    fail = make_fail("upper_triangular_check")
    width = _int_matrix(fail, matrix)
    _square(fail, matrix, width)
    n = len(matrix)
    for i in range(1, n):
        for j in range(i):
            if matrix[i][j] != 0:
                return False
    return True
