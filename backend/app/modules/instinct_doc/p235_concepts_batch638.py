"""b638 bounded exact sums of two positive cubes with certificates.

For exact ints n in 1..N_MAX the module enumerates every representation
n = a^3 + b^3 with exact ints 1 <= a <= b, counts them, and finds the
smallest n with exactly k representations (the taxicab numbers Ta(k) when
they lie within the bound; Ta(3) = 87539319 exceeds N_MAX and reports None).
Cube roots and perfect-cube tests are exact integer binary searches - no
floats anywhere. Certificates are exact tuples re-checked by integer
arithmetic. Adjacency disclosure: this is cubic representation arithmetic,
not the quadratic norm forms of b536 (Gaussian/Eisenstein a^2+b^2,
a^2+ab+b^2), not the Pell/quadratic residue machinery of b513/b321, and not
divisor-sum arithmetic (Sugarcode b446), and not Waring-problem or
general diophantine representation theory (no sums of three or more
cubes, no higher powers, no asymptotic counts); the numbers 1729 and
4104 are classical and no novelty is claimed. Validation order is pinned: container
arguments in global phases (tuple types, then length caps, then element
shapes, then element types, then element ranges), then scalar argument
types in positional order, then scalar ranges in positional order, then
cross-argument constraints. Structural violations raise ValueError
P235:<name>:<code>; a well-formed but wrong certificate returns False.
Deterministic only; every value is exact.
"""
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

SCOPE = ('PARTIAL bounded exact sums of two positive cubes: representation '
         'enumeration and counts, perfect-cube and integer cube-root '
         'arithmetic, bounded taxicab witnesses, all with re-computable '
         'certificates')
NOT_CLAIMED = ('AGI-like intelligence', 'quadratic form or norm theory',
               'divisor-sum arithmetic', 'sums of three or more cubes or '
               'higher powers', 'Waring-problem generality', 'global '
               'novelty', 'production readiness')

N_MAX = 10 ** 6
B_MAX = 100          # b^3 <= N_MAX implies b <= 100
K_MAX = 4            # representation counts asked of taxicab()
SEQ_MAX = 64


def _itype(f, label, v):
    if type(v) is not int:
        f('bad_type:' + label)
    return v


def _irange(f, label, v, lo, hi):
    if not lo <= v <= hi:
        f('bad_value:' + label)
    return v


def _icbrt_floor(n):
    lo, hi = 0, min(n, B_MAX) + 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if mid ** 3 <= n:
            lo = mid
        else:
            hi = mid
    return lo


def _reps(n):
    out = []
    for a in range(1, _icbrt_floor(n // 2) + 1):
        b = _icbrt_floor(n - a ** 3)
        if b >= a and a ** 3 + b ** 3 == n:
            out.append((a, b))
    return tuple(out)


_REPMAP = None


def _repmap():
    global _REPMAP
    if _REPMAP is None:
        counts = {}
        for b in range(1, B_MAX + 1):
            for a in range(1, b + 1):
                s = a ** 3 + b ** 3
                if s > N_MAX:
                    break
                counts[s] = counts.get(s, 0) + 1
        _REPMAP = counts
    return _REPMAP


def icbrt_floor(n):
    """The largest exact int b with b^3 <= n, for n in 0..10**18."""
    f = make_fail('icbrt_floor')
    _itype(f, 'n', n)
    _irange(f, 'n', n, 0, 10 ** 18)
    lo, hi = 0, 10 ** 6 + 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if mid ** 3 <= n:
            lo = mid
        else:
            hi = mid
    return lo


def is_perfect_cube(n):
    """True exactly when n is the cube of an exact non-negative int."""
    f = make_fail('is_perfect_cube')
    _itype(f, 'n', n)
    _irange(f, 'n', n, 0, 10 ** 18)
    b = icbrt_floor(n)
    return b ** 3 == n


def representations(n):
    """The sorted tuple of (a, b) with 1 <= a <= b and a^3 + b^3 == n."""
    f = make_fail('representations')
    _itype(f, 'n', n)
    _irange(f, 'n', n, 1, N_MAX)
    return _reps(n)


def representation_count(n):
    """The exact number of representations of n as a^3 + b^3, 1 <= a <= b."""
    f = make_fail('representation_count')
    _itype(f, 'n', n)
    _irange(f, 'n', n, 1, N_MAX)
    return len(_reps(n))


def is_sum_of_two_cubes(n):
    """True exactly when n has at least one representation."""
    f = make_fail('is_sum_of_two_cubes')
    _itype(f, 'n', n)
    _irange(f, 'n', n, 1, N_MAX)
    return len(_reps(n)) > 0


def taxicab(k):
    """The smallest n in 1..N_MAX with exactly k representations, or None
    when no such n lies within the bound."""
    f = make_fail('taxicab')
    _itype(f, 'k', k)
    _irange(f, 'k', k, 1, K_MAX)
    for n in range(2, N_MAX + 1):
        if _repmap().get(n, 0) == k:
            return n
    return None


def representations_check(n, cert):
    """cert is exactly the representations output for the same n."""
    f = make_fail('representations_check')
    if type(cert) is not tuple:
        f('bad_type:cert')
    if len(cert) > SEQ_MAX:
        f('bad_value:cert')
    for v in cert:
        if type(v) is not tuple or len(v) != 2:
            f('bad_type:cert element')
    for v in cert:
        if type(v[0]) is not int or type(v[1]) is not int:
            f('bad_type:cert element')
    for v in cert:
        if not 1 <= v[0] <= B_MAX or not 1 <= v[1] <= B_MAX:
            f('bad_value:cert element')
    _itype(f, 'n', n)
    _irange(f, 'n', n, 1, N_MAX)
    return cert == _reps(n)


def count_check(n, cert):
    """cert is exactly the representation_count output for the same n."""
    f = make_fail('count_check')
    _itype(f, 'n', n)
    _itype(f, 'cert', cert)
    _irange(f, 'n', n, 1, N_MAX)
    _irange(f, 'cert', cert, 0, SEQ_MAX)
    return cert == len(_reps(n))


def taxicab_check(k, cert):
    """cert is exactly the taxicab output for the same k: an exact int n,
    or None within the bound."""
    f = make_fail('taxicab_check')
    _itype(f, 'k', k)
    if cert is not None:
        _itype(f, 'cert', cert)
    _irange(f, 'k', k, 1, K_MAX)
    if cert is None:
        return taxicab(k) is None
    _irange(f, 'cert', cert, 1, N_MAX)
    return cert == taxicab(k)
