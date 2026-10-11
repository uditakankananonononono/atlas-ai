"""Row 1512: bounded, supplied 1D linear-elastic axial bar computation only."""
from __future__ import annotations
import math

MODEL = '1d_axial_linear_elastic'
UNITS = {'length': 'm', 'force': 'N', 'modulus': 'Pa', 'area': 'm^2'}
MAX_NODES = 64
MAX_ELEMENTS = 128


def _fail(kind):
    raise ValueError('FEA1512_' + kind)


def _number(value, kind, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(kind)
    try:
        value = float(value)
    except (OverflowError, ValueError):
        _fail(kind)
    if not math.isfinite(value) or abs(value) > 1e100 or (positive and value <= 0):
        _fail(kind)
    return value


def _identifier(value, kind):
    if not isinstance(value, str) or not value or len(value) > 128:
        _fail(kind)
    return value


def _system(matrix, rhs):
    """Scaled partial pivoting; reject unstable small systems, never regularize."""
    n = len(rhs)
    if not n:
        return []
    a = [list(row) + [b] for row, b in zip(matrix, rhs)]
    scales = [max(map(abs, row)) for row in matrix]
    for col in range(n):
        pivot = max(range(col, n), key=lambda i: abs(a[i][col])/scales[i] if scales[i] else 0)
        if not scales[pivot] or abs(a[pivot][col]) <= 1e-12 * scales[pivot]:
            _fail('SINGULAR')
        a[col], a[pivot] = a[pivot], a[col]
        scales[col], scales[pivot] = scales[pivot], scales[col]
        for i in range(col + 1, n):
            ratio = a[i][col] / a[col][col]
            a[i][col] = 0.0
            for j in range(col + 1, n + 1):
                a[i][j] -= ratio * a[col][j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (a[i][n] - math.fsum(a[i][j]*x[j] for j in range(i+1, n))) / a[i][i]
    if not all(math.isfinite(v) for v in x):
        _fail('NUMERICAL')
    return x


def _solve_axial_bar(data: dict) -> dict:
    """Solve K u = f on free nodes; reactions are K u - f at restrained nodes.

    Nodes and elements use unique string IDs. Output is sorted by ID, not caller
    insertion order. Every disconnected component needs a prescribed displacement.
    No body-force inference, unit conversion, geometric or material nonlinearity.
    """
    if not isinstance(data, dict) or set(data) - {'model','units','nodes','elements','loads','displacements','source_refs'}:
        _fail('INPUT')
    if data.get('model') != MODEL:
        _fail('MODEL')
    if data.get('units') != UNITS:
        _fail('UNITS')
    nodes = data.get('nodes')
    elements = data.get('elements')
    if (not isinstance(nodes, list) or not 2 <= len(nodes) <= MAX_NODES
            or not isinstance(elements, list) or not 1 <= len(elements) <= MAX_ELEMENTS):
        _fail('BOUNDS')
    coords = {}
    for node in nodes:
        if not isinstance(node, dict):
            _fail('NODE')
        key = _identifier(node.get('id'), 'NODE')
        if key in coords:
            _fail('NODE')
        coords[key] = _number(node.get('x'), 'NODE')
    ids = sorted(coords)
    index = {key: i for i, key in enumerate(ids)}
    n = len(ids)
    k = [[0.0]*n for _ in ids]
    checked = []
    seen = set()
    adjacent = {key: set() for key in ids}
    for el in elements:
        if not isinstance(el, dict):
            _fail('ELEMENT')
        eid = _identifier(el.get('id'), 'ELEMENT')
        ends = el.get('nodes')
        if eid in seen or not isinstance(ends, list) or len(ends) != 2:
            _fail('ELEMENT')
        seen.add(eid)
        if any(not isinstance(v, str) or v not in coords for v in ends) or ends[0] == ends[1]:
            _fail('ELEMENT')
        left, right = sorted(ends, key=lambda key: (coords[key], key))
        length = coords[right] - coords[left]
        if length <= 0:
            _fail('ELEMENT')
        young = _number(el.get('E'), 'MATERIAL', True)
        area = _number(el.get('A'), 'MATERIAL', True)
        try:
            stiffness = young * area / length
        except (OverflowError, ZeroDivisionError):
            _fail('NUMERICAL')
        if not math.isfinite(stiffness) or stiffness <= 0:
            _fail('NUMERICAL')
        checked.append((eid, left, right, length, young, area, stiffness))
        adjacent[left].add(right)
        adjacent[right].add(left)
    # Sort before assembly to make sums reproducible for unsorted input.
    checked.sort()
    for _, left, right, _, _, _, stiffness in checked:
        i, j = index[left], index[right]
        k[i][i] += stiffness
        k[j][j] += stiffness
        k[i][j] -= stiffness
        k[j][i] -= stiffness
    if not all(math.isfinite(v) for row in k for v in row):
        _fail('NUMERICAL')
    def supplied(key, field, kind):
        items = data.get(key)
        if not isinstance(items, list) or len(items) > n:
            _fail(kind)
        result = {}
        for item in items:
            if not isinstance(item, dict):
                _fail(kind)
            node = item.get('node')
            if not isinstance(node, str) or node not in index or node in result:
                _fail(kind)
            result[node] = _number(item.get(field), kind)
        return result
    loads = supplied('loads', 'force', 'LOAD')
    fixed = supplied('displacements', 'value', 'BC')
    unseen = set(ids)
    while unseen:
        component = set()
        todo = [min(unseen)]
        while todo:
            node = todo.pop()
            if node not in component:
                component.add(node)
                todo.extend(adjacent[node] - component)
        unseen -= component
        if not component.intersection(fixed):
            _fail('SINGULAR')
    refs = data.get('source_refs', [])
    if not isinstance(refs, list) or len(refs) > 128 or any(not isinstance(v, str) or len(v) > 2048 for v in refs):
        _fail('SOURCE')
    f = [loads.get(key, 0.0) for key in ids]
    free = [index[key] for key in ids if key not in fixed]
    u = [fixed.get(key, 0.0) for key in ids]
    rhs = [f[i] - math.fsum(k[i][index[key]]*fixed[key] for key in sorted(fixed)) for i in free]
    reduced = [[k[i][j] for j in free] for i in free]
    for i, value in zip(free, _system(reduced, rhs)):
        u[i] = value
    internal = [math.fsum(k[i][j]*u[j] for j in range(n)) for i in range(n)]
    reactions = [internal[i] - f[i] if ids[i] in fixed else 0.0 for i in range(n)]
    result_elements = []
    for eid, left, right, length, young, area, stiffness in checked:
        delta = u[index[right]] - u[index[left]]
        strain = delta / length
        stress = young * strain
        result_elements.append({'id': eid, 'nodes': [left, right], 'length': length,
                                'strain': strain, 'stress': stress, 'axial_force': stress*area})
    energy = math.fsum(.5*stiffness*(u[index[right]]-u[index[left]])**2
                       for _, left, right, _, _, _, stiffness in checked)
    work = .5*math.fsum(u[i]*(f[i]+reactions[i]) for i in range(n))
    residual = max((abs(internal[i]-f[i]) for i in free), default=0.0)
    balance = math.fsum(f + reactions)
    scalars = u + reactions + [energy, work, residual, balance]
    scalars += [v for el in result_elements for name, v in el.items() if name in ('strain','stress','axial_force')]
    if not all(math.isfinite(v) for v in scalars):
        _fail('NUMERICAL')
    if residual > 1e-8 * max(1.0, *(abs(v) for v in f), *(abs(v) for v in internal)):
        _fail('NUMERICAL')
    return {'model': MODEL, 'units': dict(UNITS), 'solver': 'bounded_scaled_gaussian_elimination',
            'nodes': [{'id': key, 'displacement': u[i], 'reaction': reactions[i],
                       'restrained': key in fixed} for i, key in enumerate(ids)],
            'elements': result_elements, 'strain_energy': energy, 'external_work_half': work,
            'equilibrium_residual': residual, 'force_balance_residual': balance,
            'source_refs': list(refs), 'source_verified': False, 'safety_certified': False,
            'requires_engineer_review': True,
            'boundary': 'Supplied 1D linear-elastic axial bar only; no 3D FEA or safety certification.'}


def solve_axial_bar(data: dict) -> dict:
    """Public strict-error boundary, including overflow in derived quantities."""
    try:
        return _solve_axial_bar(data)
    except (OverflowError, ZeroDivisionError):
        _fail('NUMERICAL')
