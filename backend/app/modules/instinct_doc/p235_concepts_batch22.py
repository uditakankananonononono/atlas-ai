"""P235 concepts batch 22 (concepts 211-220, number theory/combinatorics) -
ten new small deterministic number concepts. 211-220 of the doc's 1000
(anchor P235|L184). Inputs bounded; exact integer oracles pinned in tests.
"""
from __future__ import annotations

from .p235_concepts_batch1 import MAX_ITEMS, check_int, check_items, make_fail

MAX_N = 1_000_000
MAX_SMALL = 100
MAX_LCM_RESULT = 10**18
MAX_VALUE = 10**18


def _check_n(fail, n, name, lo, hi):
    check_int(fail, n, name)
    if n < lo or n > hi:
        fail("bad_value:" + name)


def josephus_winner(n, k):
    """Zero-indexed winner of the n-person every-kth elimination circle."""
    fail = make_fail("josephus_winner")
    _check_n(fail, n, "n", 1, MAX_N)
    check_int(fail, k, "k")
    if k < 1 or k > MAX_VALUE:
        fail("bad_value:k")
    winner = 0
    for size in range(2, n + 1):
        winner = (winner + k) % size
    return winner


def zeckendorf_representation(n):
    """Greedy Zeckendorf representation: non-consecutive Fibonacci numbers
    (1, 2, 3, 5, ...) summing to n, largest first."""
    fail = make_fail("zeckendorf_representation")
    _check_n(fail, n, "n", 1, 10**12)
    fibs = [1, 2]
    while fibs[-1] <= n:
        fibs.append(fibs[-1] + fibs[-2])
    out = []
    for f in reversed(fibs):
        if f <= n:
            out.append(f)
            n -= f
    return out


def binomial_coefficient(n, k):
    fail = make_fail("binomial_coefficient")
    _check_n(fail, n, "n", 0, 200)
    check_int(fail, k, "k")
    if k < 0 or k > n:
        fail("bad_value:k")
    k = min(k, n - k)
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
    return result


def factorial_trailing_zeros(n):
    """Decimal trailing zeros of n factorial (the 5-adic valuation)."""
    fail = make_fail("factorial_trailing_zeros")
    _check_n(fail, n, "n", 0, MAX_VALUE)
    count = 0
    while n:
        n //= 5
        count += n
    return count


def sum_of_divisors(n):
    """Sum of all positive divisors of n by trial division."""
    fail = make_fail("sum_of_divisors")
    _check_n(fail, n, "n", 1, 10**12)
    total = 0
    i = 1
    while i * i <= n:
        if n % i == 0:
            total += i
            if i != n // i:
                total += n // i
        i += 1
    return total


def stirling2_count(n, k):
    fail = make_fail("stirling2_count")
    _check_n(fail, n, "n", 0, MAX_SMALL)
    check_int(fail, k, "k")
    if k < 0 or k > n:
        fail("bad_value:k")
    prev = [1] + [0] * k
    for i in range(1, n + 1):
        cur = [0] * (k + 1)
        for j in range(1, k + 1):
            cur[j] = j * prev[j] + prev[j - 1]
        prev = cur
    return prev[k] if n > 0 else (1 if k == 0 else 0)


def integer_partitions_count(n):
    fail = make_fail("integer_partitions_count")
    _check_n(fail, n, "n", 0, MAX_SMALL)
    ways = [1] + [0] * n
    for part in range(1, n + 1):
        for total in range(part, n + 1):
            ways[total] += ways[total - part]
    return ways[n]


def lagrange_square_count(n):
    """Minimum number of perfect squares summing to n (Lagrange/Legendre).
    1 if square, 4 iff n = 4^a(8b+7), else 2 or 3 by two-square search."""
    fail = make_fail("lagrange_square_count")
    _check_n(fail, n, "n", 1, 10**12)
    root = int(n**0.5)
    while (root + 1) * (root + 1) <= n:
        root += 1
    while root * root > n:
        root -= 1
    if root * root == n:
        return 1
    m = n
    while m % 4 == 0:
        m //= 4
    if m % 8 == 7:
        return 4
    a = 1
    while a * a <= n:
        rest = n - a * a
        b = int(rest**0.5)
        while (b + 1) * (b + 1) <= rest:
            b += 1
        while b * b > rest:
            b -= 1
        if b * b == rest:
            return 2
        a += 1
    return 3


def is_square_free(n):
    """Whether no square greater than one divides n, by trial division."""
    fail = make_fail("is_square_free")
    _check_n(fail, n, "n", 1, 10**12)
    i = 2
    while i * i <= n:
        if n % (i * i) == 0:
            return False
        i += 1
    return True


def pythagorean_triple_check(a, b, c):
    """Whether a*a + b*b == c*c exactly, positive sides only."""
    fail = make_fail("pythagorean_triple_check")
    for name, v in (("a", a), ("b", b), ("c", c)):
        check_int(fail, v, name)
        if v < 1 or v > MAX_VALUE:
            fail("bad_value:" + name)
    return a * a + b * b == c * c
