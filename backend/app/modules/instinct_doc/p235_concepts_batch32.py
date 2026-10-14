"""P235 concepts batch 32 (concepts 311-320, number theory II) - ten new
small deterministic concepts. 311-320 of the doc's 1000 (anchor
P235|L184). Exact arithmetic; inputs bounded; refusal codes
P235:<name>:<code>.
"""
from __future__ import annotations

import math
from fractions import Fraction

from .p235_concepts_batch1 import check_int, check_str, make_fail

MAX_POWER_N = 10**12
MAX_CARMICHAEL_N = 10**12
MAX_LEGENDRE_P = 10**6
MAX_CF_VALUE = 10**12
MAX_CF_TERMS = 100
MAX_SQRT_CF_N = 10_000
MAX_LL_P = 607
MAX_FERMAT_N = 10**12
MAX_FERMAT_STEPS = 10**6
MAX_GAP_N = 10**6
MAX_COORD = 10**6


def _is_prime_trial(n):
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    p = 3
    while p * p <= n:
        if n % p == 0:
            return False
        p += 2
    return True


def perfect_power_check(n):
    """Whether n = a**b for some a >= 1 and b >= 2; 1 counts (1 = 1**2)."""
    fail = make_fail("perfect_power_check")
    check_int(fail, n, "n")
    if n < 1:
        fail("bad_value:n")
    if n > MAX_POWER_N:
        fail("too_big:n")
    if n == 1:
        return True
    b = 2
    while (1 << b) <= n:
        root = round(n ** (1.0 / b))
        for cand in (root - 1, root, root + 1):
            if cand >= 1 and cand ** b == n:
                return True
        b += 1
    return False


def carmichael_check(n):
    """Whether n is a Carmichael number (Korselt: composite, square-free,
    and p - 1 divides n - 1 for every prime p dividing n)."""
    fail = make_fail("carmichael_check")
    check_int(fail, n, "n")
    if n < 2:
        fail("bad_value:n")
    if n > MAX_CARMICHAEL_N:
        fail("too_big:n")
    m = n
    factors = []
    p = 2
    while p * p <= m:
        if m % p == 0:
            factors.append(p)
            m //= p
            if m % p == 0:
                return False
        p += 1 if p == 2 else 2
    if m > 1:
        factors.append(m)
    if len(factors) < 2:
        return False
    return all((n - 1) % (p - 1) == 0 for p in factors)


def legendre_symbol(a, p):
    """Euler's criterion: 1 when a is a nonzero quadratic residue mod the
    odd prime p, -1 when non-residue, 0 when p divides a."""
    fail = make_fail("legendre_symbol")
    check_int(fail, a, "a")
    if abs(a) > MAX_POWER_N:
        fail("too_big:a")
    check_int(fail, p, "p")
    if p < 3 or p > MAX_LEGENDRE_P or p % 2 == 0 \
            or not _is_prime_trial(p):
        fail("bad_value:p")
    value = pow(a % p, (p - 1) // 2, p)
    if value == 0:
        return 0
    return 1 if value == 1 else -1


def continued_fraction_of(p, q):
    """Canonical finite continued fraction terms of p/q (q >= 1); the
    last term is never 1 when there is more than one term."""
    fail = make_fail("continued_fraction_of")
    check_int(fail, p, "p")
    check_int(fail, q, "q")
    if abs(p) > MAX_CF_VALUE:
        fail("too_big:p")
    if q < 1 or q > MAX_CF_VALUE:
        fail("bad_value:q")
    terms = []
    while True:
        a = p // q
        terms.append(a)
        p, q = q, p - a * q
        if q == 0:
            break
        if len(terms) >= MAX_CF_TERMS:
            fail("too_many:terms")
    return terms


def continued_fraction_value(terms):
    """Exact value of a canonical finite continued fraction; terms after
    the first must be positive and the last may not be 1."""
    fail = make_fail("continued_fraction_value")
    if type(terms) is not list or not terms:
        fail("bad_value:terms")
    if len(terms) > MAX_CF_TERMS:
        fail("too_many:terms")
    for i, v in enumerate(terms):
        check_int(fail, v, "terms[%d]" % i)
        if abs(v) > MAX_CF_VALUE:
            fail("too_big:terms")
        if i > 0 and v < 1:
            fail("bad_value:terms")
    if len(terms) > 1 and terms[-1] == 1:
        fail("bad_value:terms")
    value = Fraction(terms[-1])
    for v in reversed(terms[:-1]):
        value = v + Fraction(1, value)
    return value


def sqrt_cf_period(n):
    """Period length of the continued fraction of sqrt(n); 0 for perfect
    squares."""
    fail = make_fail("sqrt_cf_period")
    check_int(fail, n, "n")
    if n < 1 or n > MAX_SQRT_CF_N:
        fail("bad_value:n")
    a0 = math.isqrt(n)
    if a0 * a0 == n:
        return 0
    m, d, a = 0, 1, a0
    period = 0
    while a != 2 * a0:
        m = d * a - m
        d = (n - m * m) // d
        a = (a0 + m) // d
        period += 1
    return period


def lucas_lehmer_check(p):
    """Whether 2**p - 1 is prime, for odd prime p up to 607, by the
    Lucas-Lehmer iteration."""
    fail = make_fail("lucas_lehmer_check")
    check_int(fail, p, "p")
    if p < 3 or p > MAX_LL_P or not _is_prime_trial(p):
        fail("bad_value:p")
    mersenne = (1 << p) - 1
    s = 4
    for _ in range(p - 2):
        s = (s * s - 2) % mersenne
    return s == 0


def fermat_factor(n):
    """A nontrivial factor pair (a, b) with a <= b and a * b == n for an
    odd composite n, by Fermat's difference-of-squares search; refuses
    when 1,000,000 iterations do not suffice."""
    fail = make_fail("fermat_factor")
    check_int(fail, n, "n")
    if n < 9 or n % 2 == 0 or _is_prime_trial(n):
        fail("bad_value:n")
    if n > MAX_FERMAT_N:
        fail("too_big:n")
    a = math.isqrt(n)
    if a * a == n:
        return (a, a)
    a += 1
    for _ in range(MAX_FERMAT_STEPS):
        b2 = a * a - n
        b = math.isqrt(b2)
        if b * b == b2:
            return (a - b, a + b)
        a += 1
    fail("too_hard:n")


def prime_gap_max_upto(n):
    """Largest gap between consecutive primes not exceeding n; 0 when
    fewer than two primes are in range."""
    fail = make_fail("prime_gap_max_upto")
    check_int(fail, n, "n")
    if n < 2:
        fail("bad_value:n")
    if n > MAX_GAP_N:
        fail("too_big:n")
    sieve = bytearray([1]) * (n + 1)
    sieve[0:2] = b"\x00\x00"
    for i in range(2, math.isqrt(n) + 1):
        if sieve[i]:
            sieve[i * i::i] = b"\x00" * (((n - i * i) // i) + 1)
    best = 0
    prev = None
    for i in range(2, n + 1):
        if sieve[i]:
            if prev is not None:
                best = max(best, i - prev)
            prev = i
    return best


def segments_intersect_check(p1, p2, p3, p4):
    """Whether two closed segments with int endpoints intersect
    (including touching and collinear overlap), by exact orientation."""
    fail = make_fail("segments_intersect_check")
    pts = []
    for name, point in (("p1", p1), ("p2", p2), ("p3", p3), ("p4", p4)):
        if type(point) not in (list, tuple) or len(point) != 2:
            fail("bad_type:" + name)
        for i, v in enumerate(point):
            check_int(fail, v, "%s[%d]" % (name, i))
            if abs(v) > MAX_COORD:
                fail("bad_value:" + name)
        pts.append((point[0], point[1]))

    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) \
            - (b[1] - a[1]) * (c[0] - a[0])

    def on_segment(a, b, c):
        return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) \
            and min(a[1], b[1]) <= c[1] <= max(a[1], b[1]) \
            and orient(a, b, c) == 0

    a, b, c, d = pts
    o1, o2 = orient(a, b, c), orient(a, b, d)
    o3, o4 = orient(c, d, a), orient(c, d, b)
    if (o1 > 0) != (o2 > 0) and o1 != 0 and o2 != 0 \
            and (o3 > 0) != (o4 > 0) and o3 != 0 and o4 != 0:
        return True
    return on_segment(a, b, c) or on_segment(a, b, d) \
        or on_segment(c, d, a) or on_segment(c, d, b)
