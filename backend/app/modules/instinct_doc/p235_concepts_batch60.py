"""P235 concepts batch 60: exact statistics.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. Exact Fraction
arithmetic only; no external deps.
"""

from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, make_fail)

MAX_N = 1_000


def _frac(fail, v, name):
    if type(v) is int:
        return Fraction(v)
    if type(v) is Fraction:
        return v
    fail("bad_type:%s" % name)


def _int_list(fail, values, name="items", allow_empty=False):
    check_items(fail, values, name)
    if not values and not allow_empty:
        fail("empty:%s" % name)
    if len(values) > MAX_ITEMS:
        fail("too_many:%s" % name)
    for i, v in enumerate(values):
        check_int(fail, v, "%s[%d]" % (name, i))


def mean_pairwise_abs_diff(items):
    """Mean of |xi - xj| over all unordered pairs, as a Fraction."""
    fail = make_fail("mean_pairwise_abs_diff")
    _int_list(fail, items)
    if len(items) < 2:
        fail("too_few:items")
    total = Fraction(0)
    pairs = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            total += abs(items[i] - items[j])
            pairs += 1
    return total / pairs


def binomial_probability_exact(n, k, p):
    """C(n, k) p^k (1-p)^(n-k) as an exact Fraction.

    p is an int or Fraction in [0, 1]; 0 <= k <= n <= MAX_N.
    """
    fail = make_fail("binomial_probability_exact")
    check_int(fail, n, "n")
    check_int(fail, k, "k")
    if n < 0 or n > MAX_N:
        fail("out_of_range:n")
    if k < 0 or k > n:
        fail("out_of_range:k")
    fp = _frac(fail, p, "p")
    if fp < 0 or fp > 1:
        fail("bad_value:p")
    from math import comb
    return Fraction(comb(n, k)) * fp ** k * (1 - fp) ** (n - k)


def standard_score_exact(value, mean, sd):
    """(value - mean) / sd as a Fraction; sd must be positive."""
    fail = make_fail("standard_score_exact")
    fv = _frac(fail, value, "value")
    fm = _frac(fail, mean, "mean")
    fs = _frac(fail, sd, "sd")
    if fs <= 0:
        fail("bad_value:sd")
    return (fv - fm) / fs


def mann_whitney_u(xs, ys):
    """Mann-Whitney U of two samples, tie-averaged ranks, Fraction.

    U counts (x, y) pairs with x > y plus half the ties.
    """
    fail = make_fail("mann_whitney_u")
    _int_list(fail, xs, "xs")
    _int_list(fail, ys, "ys")
    total = Fraction(0)
    for x in xs:
        for y in ys:
            if x > y:
                total += 1
            elif x == y:
                total += Fraction(1, 2)
    return total


def runs_count(items):
    """Number of maximal equal-sign runs in an int list.

    Sign is -1, 0, or +1 per item; a new run starts whenever the
    sign changes.
    """
    fail = make_fail("runs_count")
    _int_list(fail, items)
    runs = 1
    prev = (items[0] > 0) - (items[0] < 0)
    for v in items[1:]:
        s = (v > 0) - (v < 0)
        if s != prev:
            runs += 1
            prev = s
    return runs


def matrix_row_sums(matrix):
    """Per-row sums of an int matrix as a list of ints."""
    fail = make_fail("matrix_row_sums")
    check_items(fail, matrix, "matrix")
    if not matrix:
        fail("empty:matrix")
    width = None
    cells = 0
    for i, row in enumerate(matrix):
        if type(row) is not list:
            fail("bad_type:matrix[%d]" % i)
        if not row:
            fail("empty:matrix[%d]" % i)
        if width is None:
            width = len(row)
        elif len(row) != width:
            fail("not_rectangular:matrix")
        cells += len(row)
        if cells > MAX_ITEMS:
            fail("too_many:matrix")
    out = []
    for i, row in enumerate(matrix):
        total = 0
        for j, v in enumerate(row):
            check_int(fail, v, "matrix[%d][%d]" % (i, j))
            total += v
        out.append(total)
    return out


def chi_square_statistic_exact(observed, expected):
    """Sum of (o - e)^2 / e over paired bins, as a Fraction.

    expected must be positive in every bin; observed non-negative.
    """
    fail = make_fail("chi_square_statistic_exact")
    _int_list(fail, observed, "observed")
    _int_list(fail, expected, "expected")
    if len(observed) != len(expected):
        fail("length_mismatch")
    total = Fraction(0)
    for i, (o, e) in enumerate(zip(observed, expected)):
        if o < 0:
            fail("bad_value:observed[%d]" % i)
        if e <= 0:
            fail("bad_value:expected[%d]" % i)
        total += Fraction((o - e) ** 2, e)
    return total


def third_central_moment_exact(items):
    """Mean of (x - mean)^3 over an int list, as a Fraction."""
    fail = make_fail("third_central_moment_exact")
    _int_list(fail, items)
    mean = Fraction(sum(items), len(items))
    total = Fraction(0)
    for v in items:
        total += (Fraction(v) - mean) ** 3
    return total / len(items)


def mean_of_squares_exact(items):
    """Mean of the squared values of an int list, as a Fraction."""
    fail = make_fail("mean_of_squares_exact")
    _int_list(fail, items)
    return Fraction(sum(v * v for v in items), len(items))


def min_max_normalize_exact(items):
    """Scale an int list to [0, 1] as Fractions; min maps to 0.

    Refuses a constant list (no range to normalize by).
    """
    fail = make_fail("min_max_normalize_exact")
    _int_list(fail, items)
    lo = min(items)
    hi = max(items)
    if hi == lo:
        fail("bad_value:constant")
    span = hi - lo
    return [Fraction(v - lo, span) for v in items]
