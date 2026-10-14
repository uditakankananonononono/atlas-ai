"""P235 concepts, batch 34 (algebra and geometry II, 331-340).

Offline, stdlib only. Exact arithmetic throughout: integer matrices and
points, Fraction where division appears. Caps refuse before work.
"""
from __future__ import annotations

from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, make_fail)

MAX_MATRIX_CELLS = 10_000
MAX_PAIR_POINTS = 1_000
MAX_LINE_POINTS = 200
MAX_POLYGON_VERTICES = 1_000


def _check_matrix(fail, a, name):
    check_items(fail, a, name)
    if not a:
        fail("empty:%s" % name)
    width = None
    cells = 0
    for i, row in enumerate(a):
        check_items(fail, row, "%s[%d]" % (name, i))
        if not row:
            fail("empty:%s[%d]" % (name, i))
        if width is None:
            width = len(row)
        elif len(row) != width:
            fail("ragged:%s" % name)
        cells += len(row)
        if cells > MAX_MATRIX_CELLS:
            fail("too_many:%s" % name)
        for j, v in enumerate(row):
            check_int(fail, v, "%s[%d][%d]" % (name, i, j))
    return len(a), width


def _check_point(fail, p, name):
    if type(p) is not list or len(p) != 2:
        fail("bad_type:%s" % name)
    check_int(fail, p[0], "%s[0]" % name)
    check_int(fail, p[1], "%s[1]" % name)
    return p[0], p[1]


def matrix_multiply_exact(a, b):
    fail = make_fail("matrix_multiply_exact")
    rows_a, cols_a = _check_matrix(fail, a, "a")
    rows_b, cols_b = _check_matrix(fail, b, "b")
    if cols_a != rows_b:
        fail("shape:a_cols!=b_rows")
    out = []
    for i in range(rows_a):
        row = []
        for j in range(cols_b):
            total = 0
            for k in range(cols_a):
                total += a[i][k] * b[k][j]
            row.append(total)
        out.append(row)
    return out


def matrix_rank_exact(a):
    fail = make_fail("matrix_rank_exact")
    rows, cols = _check_matrix(fail, a, "a")
    grid = [[Fraction(v) for v in row] for row in a]
    rank = 0
    col = 0
    for col in range(cols):
        pivot = None
        for r in range(rank, rows):
            if grid[r][col] != 0:
                pivot = r
                break
        if pivot is None:
            continue
        grid[rank], grid[pivot] = grid[pivot], grid[rank]
        pv = grid[rank][col]
        for r in range(rows):
            if r != rank and grid[r][col] != 0:
                factor = grid[r][col] / pv
                grid[r] = [v - factor * w for v, w in
                           zip(grid[r], grid[rank])]
        rank += 1
        if rank == rows:
            break
    return rank


def closest_pair_distance2(points):
    fail = make_fail("closest_pair_distance2")
    check_items(fail, points, "points")
    if len(points) < 2:
        fail("too_few:points")
    if len(points) > MAX_PAIR_POINTS:
        fail("too_many:points")
    coords = [_check_point(fail, p, "points[%d]" % i)
              for i, p in enumerate(points)]
    best = None
    for i in range(len(coords)):
        x1, y1 = coords[i]
        for j in range(i + 1, len(coords)):
            x2, y2 = coords[j]
            d2 = (x1 - x2) ** 2 + (y1 - y2) ** 2
            if best is None or d2 < best:
                best = d2
    return best


def point_line_distance2_exact(point, a, b):
    fail = make_fail("point_line_distance2_exact")
    px, py = _check_point(fail, point, "point")
    ax, ay = _check_point(fail, a, "a")
    bx, by = _check_point(fail, b, "b")
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        fail("degenerate:a_equals_b")
    cross = (px - ax) * dy - (py - ay) * dx
    return Fraction(cross * cross, dx * dx + dy * dy)


def circumcircle_center_exact(p1, p2, p3):
    fail = make_fail("circumcircle_center_exact")
    x1, y1 = _check_point(fail, p1, "p1")
    x2, y2 = _check_point(fail, p2, "p2")
    x3, y3 = _check_point(fail, p3, "p3")
    # 2*(p2-p1) . c = |p2|^2 - |p1|^2 ; 2*(p3-p1) . c = |p3|^2 - |p1|^2
    a1, b1 = 2 * (x2 - x1), 2 * (y2 - y1)
    a2, b2 = 2 * (x3 - x1), 2 * (y3 - y1)
    r1 = x2 * x2 + y2 * y2 - x1 * x1 - y1 * y1
    r2 = x3 * x3 + y3 * y3 - x1 * x1 - y1 * y1
    det = a1 * b2 - a2 * b1
    if det == 0:
        fail("collinear:points")
    cx = Fraction(r1 * b2 - r2 * b1, det)
    cy = Fraction(a1 * r2 - a2 * r1, det)
    return (cx, cy)


def angle_classification(a, b, c):
    fail = make_fail("angle_classification")
    ax, ay = _check_point(fail, a, "a")
    bx, by = _check_point(fail, b, "b")
    cx, cy = _check_point(fail, c, "c")
    ux, uy = ax - bx, ay - by
    vx, vy = cx - bx, cy - by
    if (ux == 0 and uy == 0) or (vx == 0 and vy == 0):
        fail("degenerate:coincident_point")
    dot = ux * vx + uy * vy
    if dot > 0:
        return "acute"
    if dot < 0:
        return "obtuse"
    return "right"


def polygon_is_convex_check(vertices):
    fail = make_fail("polygon_is_convex_check")
    check_items(fail, vertices, "vertices")
    if len(vertices) < 3:
        fail("too_few:vertices")
    if len(vertices) > MAX_POLYGON_VERTICES:
        fail("too_many:vertices")
    pts = [_check_point(fail, p, "vertices[%d]" % i)
           for i, p in enumerate(vertices)]
    for i in range(len(pts)):
        if pts[i] == pts[(i + 1) % len(pts)]:
            fail("degenerate:consecutive_duplicate")
    n = len(pts)

    def _orient(a, b, c):
        return ((b[0] - a[0]) * (c[1] - a[1])
                - (b[1] - a[1]) * (c[0] - a[0]))

    def _on_segment(a, b, c):
        return (min(a[0], b[0]) <= c[0] <= max(a[0], b[0])
                and min(a[1], b[1]) <= c[1] <= max(a[1], b[1]))

    def _segments_touch(a, b, c, d):
        o1 = _orient(a, b, c)
        o2 = _orient(a, b, d)
        o3 = _orient(c, d, a)
        o4 = _orient(c, d, b)
        if ((o1 > 0) != (o2 > 0)) and ((o3 > 0) != (o4 > 0)) \
                and o1 != 0 and o2 != 0 and o3 != 0 and o4 != 0:
            return True
        for o, p, q, r in ((o1, a, b, c), (o2, a, b, d),
                           (o3, c, d, a), (o4, c, d, b)):
            if o == 0 and _on_segment(p, q, r):
                return True
        return False

    edges = [(pts[i], pts[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if j == i or (j == (i + 1) % n) or (i == (j + 1) % n):
                continue
            if _segments_touch(edges[i][0], edges[i][1],
                               edges[j][0], edges[j][1]):
                fail("self_intersecting:polygon")
    sign = 0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        x3, y3 = pts[(i + 2) % n]
        cross = ((x2 - x1) * (y3 - y2) - (y2 - y1) * (x3 - x2))
        if cross == 0:
            continue
        s = 1 if cross > 0 else -1
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    return True


def perpendicular_check(a1, a2, b1, b2):
    fail = make_fail("perpendicular_check")
    ax1, ay1 = _check_point(fail, a1, "a1")
    ax2, ay2 = _check_point(fail, a2, "a2")
    bx1, by1 = _check_point(fail, b1, "b1")
    bx2, by2 = _check_point(fail, b2, "b2")
    dx1, dy1 = ax2 - ax1, ay2 - ay1
    dx2, dy2 = bx2 - bx1, by2 - by1
    if (dx1 == 0 and dy1 == 0) or (dx2 == 0 and dy2 == 0):
        fail("degenerate:zero_length")
    return dx1 * dx2 + dy1 * dy2 == 0


def parallelogram_check(p1, p2, p3, p4):
    fail = make_fail("parallelogram_check")
    pts = [_check_point(fail, p, "p%d" % (i + 1))
           for i, p in enumerate((p1, p2, p3, p4))]
    if len(set(pts)) != 4:
        fail("degenerate:duplicate_point")
    collinear_all = ((pts[1][0] - pts[0][0]) * (pts[2][1] - pts[0][1])
                     == (pts[1][1] - pts[0][1]) * (pts[2][0] - pts[0][0])
                     and (pts[1][0] - pts[0][0]) * (pts[3][1] - pts[0][1])
                     == (pts[1][1] - pts[0][1]) * (pts[3][0] - pts[0][0]))
    if collinear_all:
        return False
    # equal diagonal midpoints for some pairing of the four points
    for i, j, k, l in ((0, 1, 2, 3), (0, 2, 1, 3), (0, 3, 1, 2)):
        if (pts[i][0] + pts[j][0] == pts[k][0] + pts[l][0]
                and pts[i][1] + pts[j][1] == pts[k][1] + pts[l][1]):
            return True
    return False


def max_points_on_line(points):
    fail = make_fail("max_points_on_line")
    check_items(fail, points, "points")
    if len(points) > MAX_LINE_POINTS:
        fail("too_many:points")
    pts = [_check_point(fail, p, "points[%d]" % i)
           for i, p in enumerate(points)]
    counts = {}
    for p in pts:
        counts[p] = counts.get(p, 0) + 1
    uniq = sorted(counts)
    if len(uniq) == 1:
        return counts[uniq[0]]
    best = 0
    for i in range(len(uniq)):
        for j in range(i + 1, len(uniq)):
            x1, y1 = uniq[i]
            x2, y2 = uniq[j]
            total = 0
            for (x3, y3), mult in counts.items():
                if (x2 - x1) * (y3 - y1) == (y2 - y1) * (x3 - x1):
                    total += mult
            if total > best:
                best = total
    return best
