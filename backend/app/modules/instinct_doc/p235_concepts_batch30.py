"""P235 concepts batch 30 (concepts 291-300, numeration/sequences) - ten
new small deterministic concepts. 291-300 of the doc's 1000 (anchor
P235|L184). Exact arithmetic; inputs bounded; refusal codes
P235:<name>:<code>.
"""
from __future__ import annotations

from .p235_concepts_batch1 import check_int, check_str, make_fail

MAX_PERM = 12
MAX_COLUMN = 18_278
MAX_TERNARY_ABS = (3**20 - 1) // 2
MAX_PISANO_M = 10_000
MAX_MOTZKIN_N = 500
MAX_DELANNOY = 100
MAX_EGYPT_Q = 10_000
MAX_EGYPT_TERMS = 20
MAX_EGYPT_DENOM = 10**12

_COLUMN_LETTERS = 26


def permutation_rank(perm):
    """Zero-based lexicographic rank of a permutation of range(len)."""
    fail = make_fail("permutation_rank")
    if type(perm) is not list:
        fail("bad_type:perm")
    if len(perm) > MAX_PERM:
        fail("too_many:perm")
    for i, v in enumerate(perm):
        check_int(fail, v, "perm[%d]" % i)
    n = len(perm)
    if sorted(perm) != list(range(n)):
        fail("bad_value:perm")
    rank = 0
    for i in range(n):
        smaller = sum(1 for v in perm[i + 1:] if v < perm[i])
        f = 1
        for j in range(2, n - i):
            f *= j
        rank += smaller * f
    return rank


def unrank_permutation(n, k):
    """The permutation of range(n) at zero-based lexicographic rank k."""
    fail = make_fail("unrank_permutation")
    check_int(fail, n, "n")
    check_int(fail, k, "k")
    if n < 1 or n > MAX_PERM:
        fail("bad_value:n")
    total = 1
    for j in range(2, n + 1):
        total *= j
    if k < 0 or k >= total:
        fail("bad_value:k")
    items = list(range(n))
    out = []
    for i in range(n):
        f = total // (n - i)
        idx, k = divmod(k, f)
        out.append(items.pop(idx))
        total = f
    return out


def column_index_to_name(n):
    """Bijective base-26 spreadsheet column name: 1->A, 26->Z, 27->AA,
    up to 18278->ZZZ."""
    fail = make_fail("column_index_to_name")
    check_int(fail, n, "n")
    if n < 1 or n > MAX_COLUMN:
        fail("bad_value:n")
    out = []
    while n:
        n, rem = divmod(n - 1, _COLUMN_LETTERS)
        out.append(chr(65 + rem))
    return "".join(reversed(out))


def column_name_to_index(name):
    """Inverse of column_index_to_name for one to three A-Z letters."""
    fail = make_fail("column_name_to_index")
    check_str(fail, name, "name")
    if not name or len(name) > 3 or not name.isascii() \
            or not name.isalpha() or name != name.upper():
        fail("bad_value:name")
    value = 0
    for ch in name:
        value = value * _COLUMN_LETTERS + (ord(ch) - 64)
    return value


def balanced_ternary_render(n):
    """Signed-digit base three: digits +, 0, - ; no leading zeros,
    zero renders as 0."""
    fail = make_fail("balanced_ternary_render")
    check_int(fail, n, "n")
    if abs(n) > MAX_TERNARY_ABS:
        fail("bad_value:n")
    if n == 0:
        return "0"
    out = []
    value = n
    while value:
        value, rem = divmod(value + 1, 3)
        rem -= 1
        out.append("0" if rem == 0 else "-0+"[rem + 1])
    return "".join(reversed(out))


def pisano_period(m):
    """Period length of the Fibonacci sequence modulo m, m >= 2."""
    fail = make_fail("pisano_period")
    check_int(fail, m, "m")
    if m < 2 or m > MAX_PISANO_M:
        fail("bad_value:m")
    a, b = 0, 1
    for steps in range(1, 6 * m + 1):
        a, b = b, (a + b) % m
        if (a, b) == (0, 1):
            return steps
    raise AssertionError("pisano period not found within 6m")


def kaprekar_steps(n):
    """Iterations of the 4-digit Kaprekar routine to reach 6174;
    repdigits refuse (they reach 0 instead)."""
    fail = make_fail("kaprekar_steps")
    check_int(fail, n, "n")
    if n < 1_000 or n > 9_999:
        fail("bad_value:n")
    if len(set("%04d" % n)) == 1:
        fail("bad_value:n")
    steps = 0
    while n != 6_174:
        digits = "%04d" % n
        high = int("".join(sorted(digits, reverse=True)))
        low = int("".join(sorted(digits)))
        n = high - low
        steps += 1
        if steps > 7:
            raise AssertionError("kaprekar routine did not converge")
    return steps


def motzkin_number(n):
    """Number of ways to draw non-intersecting chords between n points
    on a circle (Motzkin number M_n)."""
    fail = make_fail("motzkin_number")
    check_int(fail, n, "n")
    if n < 0:
        fail("bad_value:n")
    if n > MAX_MOTZKIN_N:
        fail("too_big:n")
    values = [1, 1]
    for k in range(2, n + 1):
        total = values[k - 1]
        for i in range(k - 1):
            total += values[i] * values[k - 2 - i]
        values.append(total)
    return values[n]


def delannoy_number(m, n):
    """Lattice paths from (0,0) to (m,n) with steps east, north, and
    northeast (Delannoy number D(m,n))."""
    fail = make_fail("delannoy_number")
    check_int(fail, m, "m")
    check_int(fail, n, "n")
    if m < 0:
        fail("bad_value:m")
    if n < 0:
        fail("bad_value:n")
    if m > MAX_DELANNOY:
        fail("too_big:m")
    if n > MAX_DELANNOY:
        fail("too_big:n")
    row = [1] * (n + 1)
    for _ in range(m):
        new = [1]
        for j in range(1, n + 1):
            new.append(new[j - 1] + row[j] + row[j - 1])
        row = new
    return row[n]


def egyptian_fraction(p, q):
    """Greedy decomposition of p/q (0 < p < q) into distinct unit
    fractions, returned as the list of denominators."""
    fail = make_fail("egyptian_fraction")
    check_int(fail, p, "p")
    check_int(fail, q, "q")
    if q < 1 or q > MAX_EGYPT_Q:
        fail("bad_value:q")
    if p < 1 or p >= q:
        fail("bad_value:p")
    out = []
    num, den = p, q
    while num:
        unit = -(-den // num)
        if unit > MAX_EGYPT_DENOM:
            fail("too_big:q")
        out.append(unit)
        if len(out) > MAX_EGYPT_TERMS:
            fail("too_many:terms")
        num, den = num * unit - den, den * unit
        g = _gcd(num, den)
        num, den = num // g, den // g
    return out


def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a
