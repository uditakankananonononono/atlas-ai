"""b625 bounded exact Farey sequences and Stern-Brocot certificates.

The Farey sequence of order n is the reduced fractions in [0, 1] with
denominator at most n, in increasing order, stored as exact (num, den) int
pairs. The Stern-Brocot tree reaches every positive reduced a/b from 1/1 by
left/right descent; the path is an exact string of 'L'/'R'. Orders n are
exact ints 1..N_MAX, fraction numerators and denominators are exact ints
0..N_MAX and 1..N_MAX (booleans, int subclasses and floats refused),
Stern-Brocot targets are exact ints 1..SB_MAX and paths are strings of at
most PATH_MAX characters. Adjacency certificates use the exact determinant
test b*c - a*d == 1 with b + d > n. Adjacency disclosure: Farey neighbors
and Stern-Brocot descents are adjacent to the continued-fraction
Euclidean algorithm and to b621 Beatty/Rayleigh floor sequences; no
novelty is claimed for those connections, and neither continued fractions
nor Beatty sequences are implemented here. Validation order is pinned:
container arguments in global phases across ALL container arguments
(tuple types, then length caps and shapes, then element types, then
element ranges; positional within a phase), then scalar arguments in
positional order (type before value), then cross-argument constraints.
Structural violations raise ValueError P235:<name>:<code>; a well-formed
but wrong certificate returns False. Deterministic only; every value is
exact.
"""
from fractions import Fraction
from importlib.util import find_spec
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:
        raise
    def make_fail(name):
        def fail(code):
            raise ValueError('P235:%s:%s' % (name, code))
        return fail

SCOPE = ('PARTIAL bounded exact Farey sequences and Stern-Brocot paths: '
         'orders, counts, terms, ranks, mediants, determinant adjacency '
         'certificates and Stern-Brocot descent certificates up to bounded '
         'orders and depths')
NOT_CLAIMED = ('AGI-like intelligence', 'continued-fraction theory or '
               'approximation guarantees', 'irrational or transcendental '
               'targets', 'asymptotic density or equidistribution claims',
               'production readiness')

N_MAX = 512
SB_MAX = 4096
PATH_MAX = 8192
SEQ_MAX = 100000


def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a


def _nat(f, label, v, lo, hi):
    if type(v) is not int:
        f('bad_type:' + label)
    if not lo <= v <= hi:
        f('bad_value:' + label)
    return v


def _farey_frac(f, label, a, b):
    _nat(f, label + ' num', a, 0, N_MAX)
    _nat(f, label + ' den', b, 1, N_MAX)
    if a > b:
        f('bad_value:' + label)
    if _gcd(a, b) != 1:
        f('bad_value:' + label)
    return a, b


def _sb_target(f, a, b):
    _nat(f, 'a', a, 1, SB_MAX)
    _nat(f, 'b', b, 1, SB_MAX)
    if _gcd(a, b) != 1:
        f('bad_value:target')
    return a, b


def _phi_count(n):
    phi = list(range(n + 1))
    for i in range(2, n + 1):
        if phi[i] == i:
            for j in range(i, n + 1, i):
                phi[j] -= phi[j] // i
    return 1 + sum(phi)


def _terms(n):
    out = [(0, 1)]
    a, b, c, d = 0, 1, 1, n
    while (c, d) != (1, 1):
        out.append((c, d))
        k = (n + b) // d
        a, b, c, d = c, d, k * c - a, k * d - b
    out.append((1, 1))
    return out


def farey_count(n):
    """Exact number of Farey terms of order n: 1 + sum of totients 1..n."""
    f = make_fail('farey_count')
    _nat(f, 'n', n, 1, N_MAX)
    return _phi_count(n)


def farey_sum(n):
    """Exact sum of all Farey terms of order n, as a Fraction."""
    f = make_fail('farey_sum')
    _nat(f, 'n', n, 1, N_MAX)
    return Fraction(_phi_count(n), 2)


def farey_term(n, k):
    """The k-th term (0-based) of the Farey sequence of order n."""
    f = make_fail('farey_term')
    _nat(f, 'n', n, 1, N_MAX)
    _nat(f, 'k', k, 0, _phi_count(n) - 1)
    return _terms(n)[k]


def farey_seq(n):
    """The full Farey sequence of order n as a tuple of (num, den) pairs."""
    f = make_fail('farey_seq')
    _nat(f, 'n', n, 1, N_MAX)
    return tuple(_terms(n))


def seq_check(n, cert):
    """cert is exactly the farey_seq output for the same order n."""
    f = make_fail('seq_check')
    if type(cert) is not tuple:
        f('bad_type:cert')
    if len(cert) > SEQ_MAX:
        f('bad_value:cert')
    for x in cert:
        if type(x) is not tuple or len(x) != 2:
            f('bad_type:cert element')
    for x in cert:
        if type(x[0]) is not int or type(x[1]) is not int:
            f('bad_type:cert element')
    for x in cert:
        if not 0 <= x[0] <= N_MAX or not 1 <= x[1] <= N_MAX:
            f('bad_value:cert element')
    _nat(f, 'n', n, 1, N_MAX)
    if len(cert) != _phi_count(n):
        f('bad_shape:cert')
    return cert == tuple(_terms(n))


def farey_rank(n, a, b):
    """The 0-based index of a/b in the Farey sequence of order n, or None
    when a/b is not a member (not reduced, above 1, or denominator > n)."""
    f = make_fail('farey_rank')
    _nat(f, 'n', n, 1, N_MAX)
    _nat(f, 'a', a, 0, N_MAX)
    _nat(f, 'b', b, 1, N_MAX)
    if a > b or b > n or _gcd(a, b) != 1:
        return None
    for i, t in enumerate(_terms(n)):
        if t == (a, b):
            return i
    return None


def mediant(a, b, c, d):
    """The mediant (a+c, b+d) of two reduced fractions in [0, 1]."""
    f = make_fail('mediant')
    _farey_frac(f, 'first', a, b)
    _farey_frac(f, 'second', c, d)
    return (a + c, b + d)


def mediant_between(a, b, c, d):
    """True exactly when a/b < c/d, equivalently when the mediant lies
    strictly between them."""
    f = make_fail('mediant_between')
    _farey_frac(f, 'first', a, b)
    _farey_frac(f, 'second', c, d)
    return a * d < c * b


def neighbor_check(n, a, b, c, d):
    """True exactly when a/b < c/d are adjacent terms of the Farey sequence
    of order n: both members, b*c - a*d == 1 and b + d > n."""
    f = make_fail('neighbor_check')
    _nat(f, 'n', n, 1, N_MAX)
    _farey_frac(f, 'first', a, b)
    _farey_frac(f, 'second', c, d)
    if b > n or d > n:
        return False
    return b * c - a * d == 1 and b + d > n


def mediant_witness(n, a, b, c, d):
    """The smallest order m > n at which a term appears strictly between
    the adjacent Farey terms a/b and c/d, or None when they are not
    adjacent in order n. That order is exactly b + d."""
    f = make_fail('mediant_witness')
    _nat(f, 'n', n, 1, N_MAX)
    _farey_frac(f, 'first', a, b)
    _farey_frac(f, 'second', c, d)
    if b > n or d > n:
        return None
    if b * c - a * d != 1 or b + d <= n:
        return None
    return b + d


def stern_brocot_path(a, b):
    """The exact L/R descent path from 1/1 to the reduced positive a/b in
    the Stern-Brocot tree ('' for 1/1 itself)."""
    f = make_fail('stern_brocot_path')
    _sb_target(f, a, b)
    lo_a, lo_b, hi_a, hi_b = 0, 1, 1, 0
    p, q = 1, 1
    out = []
    while (p, q) != (a, b):
        if a * q < p * b:
            hi_a, hi_b = p, q
            out.append('L')
        else:
            lo_a, lo_b = p, q
            out.append('R')
        p, q = lo_a + hi_a, lo_b + hi_b
    return ''.join(out)


def stern_brocot_depth(a, b):
    """The exact depth of the reduced positive a/b in the Stern-Brocot
    tree (0 for 1/1)."""
    f = make_fail('stern_brocot_depth')
    _sb_target(f, a, b)
    lo_a, lo_b, hi_a, hi_b = 0, 1, 1, 0
    p, q = 1, 1
    depth = 0
    while (p, q) != (a, b):
        if a * q < p * b:
            hi_a, hi_b = p, q
        else:
            lo_a, lo_b = p, q
        p, q = lo_a + hi_a, lo_b + hi_b
        depth += 1
    return depth


def stern_brocot_check(a, b, cert):
    """cert is exactly the stern_brocot_path output for the same target."""
    f = make_fail('stern_brocot_check')
    if type(cert) is not str:
        f('bad_type:cert')
    if len(cert) > PATH_MAX:
        f('bad_value:cert')
    for ch in cert:
        if ch not in 'LR':
            f('bad_value:cert element')
    _sb_target(f, a, b)
    lo_a, lo_b, hi_a, hi_b = 0, 1, 1, 0
    p, q = 1, 1
    out = []
    while (p, q) != (a, b):
        if a * q < p * b:
            hi_a, hi_b = p, q
            out.append('L')
        else:
            lo_a, lo_b = p, q
            out.append('R')
        p, q = lo_a + hi_a, lo_b + hi_b
    return cert == ''.join(out)
