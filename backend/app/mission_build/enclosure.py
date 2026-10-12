"""Parametric open-top enclosure: closed manifold mesh and editable OpenSCAD.

This is CAD generation, not a manufactured or safety-certified device.
"""
import math
from collections import Counter


def generate(payload):
    dimensions = []
    for key in ('width_mm', 'depth_mm', 'height_mm', 'wall_mm'):
        value = payload.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 1000:
            raise ValueError('finite positive dimension <=1000mm required: ' + key)
        dimensions.append(float(value))
    w, d, h, t = dimensions
    if 2*t >= min(w, d) or t >= h:
        raise ValueError('wall leaves no interior')
    rings = [(0, 0, w, d, 0), (0, 0, w, d, h), (t, t, w-t, d-t, h), (t, t, w-t, d-t, t)]
    vertices = []
    for x0, y0, x1, y1, z in rings:
        vertices.extend([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)])
    quads = [(3, 2, 1, 0), (12, 13, 14, 15)]
    for a, b in [(0, 4), (4, 8), (8, 12)]:
        for i in range(4):
            j = (i+1) % 4
            quads.append((a+i, a+j, b+j, b+i))
    triangles = [(q[0], q[1], q[2]) for q in quads] + [(q[0], q[2], q[3]) for q in quads]
    edges = Counter(tuple(sorted((tri[i], tri[(i+1)%3]))) for tri in triangles for i in range(3))
    oriented = Counter((tri[i], tri[(i+1)%3]) for tri in triangles for i in range(3))
    manifold = all(n == 2 for n in edges.values()) and all(oriented[(b,a)] == n for (a,b), n in oriented.items())
    volume = 0.0
    for tri in triangles:
        a, b, c = [vertices[i] for i in tri]
        volume += (a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0]) + a[2]*(b[0]*c[1]-b[1]*c[0]))/6
    expected = w*d*h-(w-2*t)*(d-2*t)*(h-t)
    if not manifold or not math.isclose(volume, expected, rel_tol=1e-9, abs_tol=1e-7):
        raise ValueError('mesh integrity failure')
    obj = '# millimeters; open-top enclosure\n' + ''.join('v %g %g %g\n' % v for v in vertices)
    obj += ''.join('f %d %d %d\n' % tuple(i+1 for i in tri) for tri in triangles)
    scad = ('// Millimeters. Geometry only, engineer before fabrication.\n'
            'difference() { cube([%g,%g,%g]); translate([%g,%g,%g]) cube([%g,%g,%g]); }\n' % (w,d,h,t,t,t,w-2*t,d-2*t,h))
    return {'vertices_mm': vertices, 'triangles': triangles, 'obj': obj, 'openscad': scad,
            'manifold_closed_surface': manifold, 'material_volume_mm3': volume,
            'interior_mm': [w-2*t,d-2*t,h-t], 'manufactured': False,
            'verification': 'edge pairing, directed winding, analytic vs mesh signed volume',
            'unverified': ['material strength', 'fit tolerances', 'thermal/electrical safety', 'physical test']}
