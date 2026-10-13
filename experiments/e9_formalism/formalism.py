"""Atlas bounded formalism discovery over prime-field scalar observations.

This induces a task-specific recurrence and executable quotient-ring algebra.
It does not invent the recurrence hypothesis class, and prefix agreement is
not a proof that a future environment obeys the inferred law.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product

P = 1009  # fixed prime, not a user-supplied primality claim


def solve_unique(rows, rhs, width):
    a = [[x % P for x in row] + [y % P] for row, y in zip(rows, rhs)]
    pivots = []
    r = 0
    for c in range(width):
        pivot = next((i for i in range(r, len(a)) if a[i][c]), None)
        if pivot is None:
            continue
        a[r], a[pivot] = a[pivot], a[r]
        inv = pow(a[r][c], P - 2, P)
        a[r] = [(x * inv) % P for x in a[r]]
        for i in range(len(a)):
            if i != r and a[i][c]:
                scale = a[i][c]
                a[i] = [(x - scale*y) % P for x, y in zip(a[i], a[r])]
        pivots.append(c)
        r += 1
    if any(not any(row[:width]) and row[-1] for row in a):
        return None
    if len(pivots) != width:
        return None  # ambiguous operators must not silently earn confidence
    out = [0] * width
    for i, c in enumerate(pivots):
        out[c] = a[i][-1]
    return tuple(out)


def fits(seq, coeff):
    d = len(coeff)
    return all(seq[t] % P == sum(coeff[j]*seq[t-d+j] for j in range(d)) % P
               for t in range(d, len(seq)))


@dataclass(frozen=True)
class Operator:
    """x^d = sum_j coeff[j] x^j in F_1009[x]/(q)."""
    coeff: tuple[int, ...]
    initial: tuple[int, ...]

    def __post_init__(self):
        if not self.coeff or len(self.coeff) != len(self.initial):
            raise ValueError('positive matching order required')
        if any(type(x) is not int or not 0 <= x < P for x in self.coeff+self.initial):
            raise ValueError('canonical fixed-field integers required')

    def compose(self, left, right):
        d = len(self.coeff)
        if len(left) != d or len(right) != d:
            raise ValueError('elements must match quotient dimension')
        tmp = [0] * (2*d-1)
        for i, a in enumerate(left):
            for j, b in enumerate(right):
                tmp[i+j] = (tmp[i+j] + a*b) % P
        for k in range(2*d-2, d-1, -1):
            for j, c in enumerate(self.coeff):
                tmp[k-d+j] = (tmp[k-d+j] + tmp[k]*c) % P
        return tuple(tmp[:d])

    def power(self, n):
        if type(n) is not int or n < 0:
            raise ValueError('nonnegative exact index required')
        d = len(self.coeff)
        out = (1,) + (0,)*(d-1)
        base = (0, 1) + (0,)*(d-2) if d > 1 else self.coeff
        while n:
            if n & 1:
                out = self.compose(out, base)
            base = self.compose(base, base)
            n //= 2
        return out

    def predict(self, n):
        return sum(a*b for a, b in zip(self.power(n), self.initial)) % P

    def definition(self):
        return {'field': P, 'order': len(self.coeff), 'coefficients_ascending': self.coeff,
                'initial': self.initial,
                'math': 'F_1009[x]/(x^d - sum_j c_j*x^j); a_n = <x^n mod q, initial>',
                'applicability': 'stationary exact homogeneous linear recurrence over F_1009',
                'proof_boundary': 'finite prefix fit and independent suffix validation, not global law proof'}


def discover(prefix, max_order=8, validation=8):
    """Search minimal uniquely fitted recurrence; never fit on validation suffix."""
    if type(max_order) is not int or not 1 <= max_order <= 32:
        raise ValueError('max_order outside 1..32')
    if type(validation) is not int or validation < 1 or len(prefix)-validation < 2*max_order:
        raise ValueError('need 2*max_order fitting observations plus validation')
    if any(type(x) is not int or not 0 <= x < P for x in prefix):
        raise ValueError('canonical observations required')
    fitting, reserved = prefix[:-validation], prefix[-validation:]
    for d in range(1, max_order+1):
        coeff = solve_unique([fitting[t-d:t] for t in range(d, len(fitting))],
                             fitting[d:], d)
        if coeff is not None and fits(prefix, coeff):
            return Operator(coeff, tuple(prefix[:d]))
    return None


def berlekamp_massey(seq):
    """Strong known-algorithm baseline, independently fitted on same prefix."""
    C, B = [1], [1]
    L, m, b = 0, 1, 1
    for n in range(len(seq)):
        discrepancy = (seq[n] + sum(C[i]*seq[n-i] for i in range(1, L+1))) % P
        if discrepancy == 0:
            m += 1
            continue
        old = C[:]
        scale = discrepancy * pow(b, P-2, P) % P
        C.extend([0]*max(0, len(B)+m-len(C)))
        for j, v in enumerate(B):
            C[j+m] = (C[j+m]-scale*v) % P
        if 2*L <= n:
            L, B, b, m = n+1-L, old, discrepancy, 1
        else:
            m += 1
    return tuple((-C[L-j]) % P for j in range(L))


def bounded_synthesis(seq, max_order=8, budget=20000):
    """Plain enumerative recurrence-program synthesis with explicit DSL and cap.

    This baseline is deliberately bounded, not representative of all synthesis.
    It includes +, -, and coefficients 0,1,2 in any position. Order then lexical
    enumeration means budget exhaustion is returned, not labelled impossibility.
    """
    tested = 0
    for d in range(1, max_order+1):
        for raw in product((-2, -1, 0, 1, 2), repeat=d):
            if tested == budget:
                return None, tested, 'budget_exhausted'
            tested += 1
            coeff = tuple(x % P for x in raw)
            if fits(seq, coeff):
                return Operator(coeff, tuple(seq[:d])), tested, 'fit'
    return None, tested, 'grammar_exhausted'
