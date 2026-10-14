"""P235 concepts, batch 17 (number theory, 161-170). Offline, stdlib only."""
from __future__ import annotations

import math
from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    check_int, make_fail)

MAX_HAPPY_N = 10 ** 12
MAX_ARMSTRONG_N = 10 ** 12
MAX_PERFECT_N = 10 ** 7
MAX_DIVISOR_N = 10 ** 12
MAX_TOTIENT_N = 10 ** 7
MAX_NEXT_PRIME_N = 10 ** 7
MAX_GOLDBACH_N = 10 ** 6
MAX_SERIES_TERMS = 10_000
MAX_MOD_VALUE = 10**18
MAX_COEFF = 10**18
MAX_RATIO_PART = 1_000
_MAX_HAPPY_STEPS = 1_000


def _positive(fail, n, cap, name="n"):
    check_int(fail, n, name)
    if n < 1:
        fail("bad_value:%s" % name)
    if n > cap:
        fail("too_many:%s" % name)
    return n


def _digit_square_sum(n):
    total = 0
    while n:
        n, d = divmod(n, 10)
        total += d * d
    return total


def happy_number(n):
    fail = make_fail("happy_number")
    _positive(fail, n, MAX_HAPPY_N)
    seen = set()
    steps = 0
    while n != 1:
        if n in seen:
            return False
        if steps >= _MAX_HAPPY_STEPS:
            fail("too_many:steps")
        seen.add(n)
        n = _digit_square_sum(n)
        steps += 1
    return True


def armstrong_check(n):
    fail = make_fail("armstrong_check")
    check_int(fail, n, "n")
    if n < 0:
        fail("bad_value:n")
    if n > MAX_ARMSTRONG_N:
        fail("too_many:n")
    digits = []
    m = n
    while m:
        m, d = divmod(m, 10)
        digits.append(d)
    if not digits:
        digits = [0]
    k = len(digits)
    return sum(d ** k for d in digits) == n


def perfect_number_check(n):
    fail = make_fail("perfect_number_check")
    _positive(fail, n, MAX_PERFECT_N)
    total = 1
    d = 2
    while d * d <= n:
        if n % d == 0:
            total += d
            other = n // d
            if other != d:
                total += other
        d += 1
    return n > 1 and total == n


def divisor_count(n):
    fail = make_fail("divisor_count")
    _positive(fail, n, MAX_DIVISOR_N)
    count = 0
    d = 1
    while d * d <= n:
        if n % d == 0:
            count += 1 if d * d == n else 2
        d += 1
    return count


def mod_inverse(a, m):
    fail = make_fail("mod_inverse")
    check_int(fail, a, "a")
    check_int(fail, m, "m")
    if abs(a) > MAX_MOD_VALUE:
        fail("too_big:a")
    if m < 2:
        fail("bad_value:m")
    if m > MAX_MOD_VALUE:
        fail("too_big:m")
    old_r, r = a % m, m
    old_s, s = 1, 0
    while r:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_s, s = s, old_s - q * s
    if old_r != 1:
        fail("no_inverse")
    return old_s % m


def euler_totient(n):
    fail = make_fail("euler_totient")
    _positive(fail, n, MAX_TOTIENT_N)
    result = n
    p = 2
    m = n
    while p * p <= m:
        if m % p == 0:
            result -= result // p
            while m % p == 0:
                m //= p
        p += 1
    if m > 1:
        result -= result // m
    return result


def _is_prime(n):
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    d = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2
    return True


def next_prime(n):
    fail = make_fail("next_prime")
    check_int(fail, n, "n")
    if n < 0:
        fail("bad_value:n")
    if n >= MAX_NEXT_PRIME_N:
        fail("too_many:n")
    candidate = n + 1
    while not _is_prime(candidate):
        candidate += 1
    return candidate


def goldbach_pair(n):
    fail = make_fail("goldbach_pair")
    check_int(fail, n, "n")
    if n < 4 or n % 2 != 0:
        fail("bad_value:n")
    if n > MAX_GOLDBACH_N:
        fail("too_many:n")
    for p in range(2, n // 2 + 1):
        if _is_prime(p) and _is_prime(n - p):
            return (p, n - p)
    fail("bad_value:n")


def quadratic_roots_exact(a, b, c):
    fail = make_fail("quadratic_roots_exact")
    check_int(fail, a, "a")
    check_int(fail, b, "b")
    check_int(fail, c, "c")
    for name, v in (("a", a), ("b", b), ("c", c)):
        if abs(v) > MAX_COEFF:
            fail("too_big:" + name)
    if a == 0:
        fail("bad_value:a")
    disc = b * b - 4 * a * c
    if disc < 0:
        fail("no_real_roots")
    root = math.isqrt(disc)
    if root * root != disc:
        fail("not_exact")
    two_a = 2 * a
    return (Fraction(-b + root, two_a), Fraction(-b - root, two_a))


def geometric_series_sum(a, r, n):
    fail = make_fail("geometric_series_sum")
    check_int(fail, a, "a")
    if abs(a) > MAX_COEFF:
        fail("too_big:a")
    if type(r) is not Fraction:
        fail("bad_type:r")
    if abs(r.numerator) > MAX_RATIO_PART or r.denominator > MAX_RATIO_PART:
        fail("too_big:r")
    check_int(fail, n, "n")
    if n < 0:
        fail("bad_value:n")
    if n > MAX_SERIES_TERMS:
        fail("too_many:n")
    if r == 1:
        return Fraction(a * n)
    return Fraction(a) * (1 - r ** n) / (1 - r)
