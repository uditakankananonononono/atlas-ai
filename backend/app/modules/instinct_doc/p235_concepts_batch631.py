"""b631 bounded exact rectilinear union measure with certificates.

Intervals are half-open [a, b) with exact int endpoints a < b in
-C_MAX..C_MAX; rectangles are axis-aligned (x1, y1, x2, y2) with x1 < x2 and
y1 < y2, exact ints in -C_MAX..C_MAX (booleans, int subclasses, floats and
Fractions refused). Container arguments are tuples of at most SEQ_MAX
entries. Union measures are computed exactly by sorting endpoints and by
coordinate compression, so areas, perimeters, overlaps and containment are
integer-checkable. Adjacency disclosure: this is continuous rectilinear
measure, not the discrete lattice-point counting of b548 polytopes, and not
the humidity-exposure rectangle integrators of the m20 engine; general
polygon geometry (hulls, intersections) is not claimed. Validation order is
pinned: container arguments in global phases across ALL container arguments
(tuple types, then length caps, then element shapes, then element types,
then element ranges, then element well-formedness; positional within a
phase), then scalar arguments in positional order (type before value), then
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

SCOPE = ('PARTIAL bounded exact rectilinear union measure: half-open '
         'interval union length and merge certificates, axis-aligned '
         'rectangle union area and perimeter by coordinate compression, '
         'overlap witnesses, containment and point coverage up to bounded '
         'coordinates and sizes')
NOT_CLAIMED = ('AGI-like intelligence', 'general polygon or convex '
               'geometry', 'polytope or lattice-point theory', 'sweep-line '
               'algorithm family claims', 'asymptotic complexity claims',
               'production readiness')

C_MAX = 64
SEQ_MAX = 64


def _merge(ivs):
    out = []
    for a, b in sorted(ivs):
        if out and a <= out[-1][1]:
            if b > out[-1][1]:
                out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return tuple(out)


def _cells(rects):
    xs = sorted({r[0] for r in rects} | {r[2] for r in rects})
    ys = sorted({r[1] for r in rects} | {r[3] for r in rects})
    covered = {}
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            xa, xb, ya, yb = xs[i], xs[i + 1], ys[j], ys[j + 1]
            if any(r[0] <= xa and r[2] >= xb and r[1] <= ya and r[3] >= yb for r in rects):
                covered[(i, j)] = (xa, xb, ya, yb)
    return covered


def _ivs_type(f, label, ivs):
    if type(ivs) is not tuple:
        f('bad_type:' + label)
    return ivs


def _ivs_cap(f, label, ivs):
    if len(ivs) > SEQ_MAX:
        f('bad_value:' + label)
    return ivs


def _ivs_elem_shape(f, label, ivs):
    for v in ivs:
        if type(v) is not tuple or len(v) != 2:
            f('bad_type:' + label + ' element')
    return ivs


def _ivs_elem_type(f, label, ivs):
    for v in ivs:
        if type(v[0]) is not int or type(v[1]) is not int:
            f('bad_type:' + label + ' element')
    return ivs


def _ivs_elem_range(f, label, ivs):
    for v in ivs:
        if not -C_MAX <= v[0] <= C_MAX or not -C_MAX <= v[1] <= C_MAX:
            f('bad_value:' + label + ' element')
    return ivs


def _ivs_wf(f, label, ivs):
    for v in ivs:
        if not v[0] < v[1]:
            f('bad_value:' + label + ' element')
    return ivs


_IV_CERT_PHASES = (_ivs_type, _ivs_cap, _ivs_elem_shape,
                   _ivs_elem_type, _ivs_elem_range)
_IV_PHASES = _IV_CERT_PHASES + (_ivs_wf,)


def _ivs(f, label, ivs):
    for phase in _IV_PHASES:
        phase(f, label, ivs)
    return ivs


def _rects_type(f, label, rects):
    if type(rects) is not tuple:
        f('bad_type:' + label)
    return rects


def _rects_cap(f, label, rects):
    if len(rects) > SEQ_MAX:
        f('bad_value:' + label)
    return rects


def _rects_elem_shape(f, label, rects):
    for r in rects:
        if type(r) is not tuple or len(r) != 4:
            f('bad_type:' + label + ' element')
    return rects


def _rects_elem_type(f, label, rects):
    for r in rects:
        if type(r[0]) is not int or type(r[1]) is not int or type(r[2]) is not int or type(r[3]) is not int:
            f('bad_type:' + label + ' element')
    return rects


def _rects_elem_range(f, label, rects):
    for r in rects:
        for c in r:
            if not -C_MAX <= c <= C_MAX:
                f('bad_value:' + label + ' element')
    return rects


def _rects_wf(f, label, rects):
    for r in rects:
        if not (r[0] < r[2] and r[1] < r[3]):
            f('bad_value:' + label + ' element')
    return rects


_RECTS_PHASES = (_rects_type, _rects_cap, _rects_elem_shape,
                 _rects_elem_type, _rects_elem_range, _rects_wf)


def _rects(f, label, rects):
    for phase in _RECTS_PHASES:
        phase(f, label, rects)
    return rects


def _rect_shape(f, label, r):
    if type(r) is not tuple or len(r) != 4:
        f('bad_type:' + label)
    return r


def _rect_type(f, label, r):
    if type(r[0]) is not int or type(r[1]) is not int or type(r[2]) is not int or type(r[3]) is not int:
        f('bad_type:' + label)
    return r


def _rect_range(f, label, r):
    for c in r:
        if not -C_MAX <= c <= C_MAX:
            f('bad_value:' + label)
    return r


def _rect_wf(f, label, r):
    if not (r[0] < r[2] and r[1] < r[3]):
        f('bad_value:' + label)
    return r


_RECT_PHASES = (_rect_shape, _rect_type, _rect_range, _rect_wf)


def _rect(f, label, r):
    for phase in _RECT_PHASES:
        phase(f, label, r)
    return r


def interval_union(ivs):
    """The merged sorted tuple of disjoint half-open intervals with the
    same union."""
    f = make_fail('interval_union')
    _ivs(f, 'ivs', ivs)
    return _merge(ivs)


def interval_union_length(ivs):
    """The exact total length of the union of the half-open intervals."""
    f = make_fail('interval_union_length')
    _ivs(f, 'ivs', ivs)
    return sum(b - a for a, b in _merge(ivs))


def merge_check(ivs, cert):
    """cert is exactly the interval_union output for the same intervals."""
    f = make_fail('merge_check')
    for phase in _IV_CERT_PHASES:
        phase(f, 'ivs', ivs)
        phase(f, 'cert', cert)
    _ivs_wf(f, 'ivs', ivs)
    return cert == _merge(ivs)


def length_check(ivs, cert):
    """cert is exactly the interval_union_length output: an exact int."""
    f = make_fail('length_check')
    _ivs(f, 'ivs', ivs)
    if type(cert) is not int:
        f('bad_type:cert')
    if not 0 <= cert <= 2 * C_MAX:
        f('bad_value:cert')
    return cert == sum(b - a for a, b in _merge(ivs))


def is_covered(ivs, x):
    """True exactly when the exact int point x lies in the union."""
    f = make_fail('is_covered')
    _ivs(f, 'ivs', ivs)
    if type(x) is not int:
        f('bad_type:x')
    if not -C_MAX <= x <= C_MAX:
        f('bad_value:x')
    return any(a <= x < b for a, b in ivs)


def rect_union_area(rects):
    """The exact area of the union of the axis-aligned rectangles, by
    coordinate compression."""
    f = make_fail('rect_union_area')
    _rects(f, 'rects', rects)
    return sum((xb - xa) * (yb - ya) for xa, xb, ya, yb in _cells(rects).values())


def area_check(rects, cert):
    """cert is exactly the rect_union_area output: an exact int."""
    f = make_fail('area_check')
    _rects(f, 'rects', rects)
    if type(cert) is not int:
        f('bad_type:cert')
    if not 0 <= cert <= 4 * C_MAX * C_MAX:
        f('bad_value:cert')
    return cert == sum((xb - xa) * (yb - ya) for xa, xb, ya, yb in _cells(rects).values())


def rect_union_perimeter(rects):
    """The exact perimeter of the union of the axis-aligned rectangles."""
    f = make_fail('rect_union_perimeter')
    _rects(f, 'rects', rects)
    cov = _cells(rects)
    perim = 0
    for (i, j), (xa, xb, ya, yb) in cov.items():
        if (i, j - 1) not in cov:
            perim += xb - xa
        if (i, j + 1) not in cov:
            perim += xb - xa
        if (i - 1, j) not in cov:
            perim += yb - ya
        if (i + 1, j) not in cov:
            perim += yb - ya
    return perim


def rect_overlap(r, s):
    """The intersection rectangle of r and s as (x1, y1, x2, y2), or None
    when they do not overlap with positive area."""
    f = make_fail('rect_overlap')
    for phase in _RECT_PHASES:
        phase(f, 'r', r)
        phase(f, 's', s)
    x1, y1 = max(r[0], s[0]), max(r[1], s[1])
    x2, y2 = min(r[2], s[2]), min(r[3], s[3])
    if x1 < x2 and y1 < y2:
        return (x1, y1, x2, y2)
    return None


def rect_contained(r, s):
    """True exactly when the rectangle r is contained in the rectangle s."""
    f = make_fail('rect_contained')
    for phase in _RECT_PHASES:
        phase(f, 'r', r)
        phase(f, 's', s)
    return s[0] <= r[0] and s[1] <= r[1] and s[2] >= r[2] and s[3] >= r[3]


def point_covered(rects, x, y):
    """True exactly when the exact int point (x, y) lies in the union."""
    f = make_fail('point_covered')
    _rects(f, 'rects', rects)
    if type(x) is not int:
        f('bad_type:x')
    if type(y) is not int:
        f('bad_type:y')
    if not -C_MAX <= x <= C_MAX:
        f('bad_value:x')
    if not -C_MAX <= y <= C_MAX:
        f('bad_value:y')
    return any(r[0] <= x < r[2] and r[1] <= y < r[3] for r in rects)
