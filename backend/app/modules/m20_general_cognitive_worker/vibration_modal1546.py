"""Bounded, supplied-input undamped modal analysis. No physical test execution."""
from __future__ import annotations
import math

_LIMIT = 1e12
_CONDITION_FLOOR = 1e-12


def _number(value, label):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and abs(value) <= _LIMIT
    except (OverflowError, TypeError):
        valid = False
    if not valid:
        raise ValueError(f'{label}: expected finite number with magnitude <= 1e12')
    return float(value)


def _text(value, label, bound):
    if not isinstance(value, str) or not value.strip() or len(value) > bound:
        raise ValueError(f'{label}: expected nonblank string of length 1..{bound}')
    return value


def _matrix(value, label, dimension=None):
    if type(value) is not list or len(value) not in (1, 2) or any(type(row) is not list or len(row) != len(value) for row in value):
        raise ValueError(f'{label}: expected 1 or 2 square rows')
    if dimension is not None and len(value) != dimension:
        raise ValueError(f'{label}: dimension differs from mass_matrix')
    out = [[_number(v, f'{label}[{i}][{j}]') for j, v in enumerate(row)] for i, row in enumerate(value)]
    if len(out) == 2 and out[0][1] != out[1][0]:
        raise ValueError(f'{label}: must be symmetric')
    scale = max(abs(x) for row in out for x in row)
    if scale < 1e-12:
        raise ValueError(f'{label}: must be positive definite and well conditioned')
    a = out[0][0] / scale
    if len(out) == 1:
        positive = a > 0
    else:
        b, c = out[0][1] / scale, out[1][1] / scale
        hi = (a + c + math.hypot(a - c, 2*b)) / 2
        lo = (a*c - b*b) / hi if hi > 0 else -1
        positive = lo > hi * _CONDITION_FLOOR
    if not positive:
        raise ValueError(f'{label}: must be positive definite and well conditioned')
    return out


def _mv(A, x):
    return [sum(a*b for a, b in zip(row, x)) for row in A]


def _modes(M, K):
    n = len(M)
    if n == 1:
        eigenpairs = [(K[0][0] / M[0][0], [1 / math.sqrt(M[0][0])])]
    else:
        # M = L L^T, then A = L^-1 K L^-T, phi = L^-T y.
        l00 = math.sqrt(M[0][0]); l10 = M[1][0] / l00
        l11 = math.sqrt(M[1][1] - l10*l10)
        inverse = [[1/l00, 0], [-l10/(l00*l11), 1/l11]]
        A = [[sum(inverse[i][u]*K[u][v]*inverse[j][v] for u in range(2) for v in range(2)) for j in range(2)] for i in range(2)]
        a, b, c = A[0][0], (A[0][1]+A[1][0])/2, A[1][1]
        hi = (a+c+math.hypot(a-c, 2*b))/2
        lo = (a*c-b*b)/hi
        if a == c and b == 0:
            ys = [[1.0, 0.0], [0.0, 1.0]]
        else:
            theta = math.atan2(2*b, a-c)/2
            ys = [[-math.sin(theta), math.cos(theta)], [math.cos(theta), math.sin(theta)]]
        eigenpairs = [(e, [sum(inverse[j][i]*y[j] for j in range(2)) for i in range(2)]) for e, y in zip([lo, hi], ys)]
    result = []
    for mode_id, (eigenvalue, x) in enumerate(eigenpairs, 1):
        if not math.isfinite(eigenvalue) or eigenvalue <= 0:
            raise ValueError('modal solve: positive finite eigenvalues required')
        norm = math.sqrt(sum(a*b for a, b in zip(x, _mv(M, x))))
        x = [v/norm for v in x]
        pivot = max(range(n), key=lambda i: abs(x[i]))
        # First component within 1e-12 of largest absolute value wins ties.
        pivot = next(i for i in range(n) if abs(x[i]) >= abs(x[pivot])*(1-1e-12))
        if x[pivot] < 0:
            x = [-v for v in x]
        kx, mx = _mv(K, x), _mv(M, x)
        residual = math.hypot(*(a-eigenvalue*b for a,b in zip(kx,mx)))
        relative = residual / (math.hypot(*kx)+abs(eigenvalue)*math.hypot(*mx))
        if not math.isfinite(relative) or relative > 1e-8:
            raise ValueError('modal solve: residual exceeds 1e-8')
        omega = math.sqrt(eigenvalue)
        result.append(dict(mode_id=mode_id, eigenvalue_rad2_s2=eigenvalue, omega_rad_s=omega,
                           frequency_hz=omega/(2*math.pi), shape=x, residual_norm=residual, relative_residual=relative))
    return result


def analyze_modal(data):
    """Solve one or two supplied SI DOFs and compare mode-indexed observations.

    Modes are ascending in frequency; observations sorted by mode_id. The function
    is pure, does not discover measurements and does not certify a structure.
    """
    if type(data) is not dict:
        raise ValueError('input: expected object')
    allowed = {'request_id','mass_matrix','stiffness_matrix','units','model','measurements','tolerance_hz'}
    extra = sorted(set(data)-allowed, key=str)
    if extra:
        raise ValueError('unsupported fields: '+','.join(map(str, extra)))
    request_id = _text(data.get('request_id'), 'request_id', 128)
    if data.get('model') != 'linear_undamped':
        raise ValueError('model: only linear_undamped supported')
    if data.get('units') != {'mass':'kg','stiffness':'N/m'}:
        raise ValueError('units: exactly mass=kg and stiffness=N/m required')
    M = _matrix(data.get('mass_matrix'), 'mass_matrix')
    K = _matrix(data.get('stiffness_matrix'), 'stiffness_matrix', len(M))
    observations = data.get('measurements', [])
    if type(observations) is not list or len(observations) > len(M):
        raise ValueError(f'measurements: expected at most {len(M)} records')
    if observations and 'tolerance_hz' not in data:
        raise ValueError('tolerance_hz: required for measurements')
    tolerance = None
    if 'tolerance_hz' in data:
        tolerance = _number(data['tolerance_hz'], 'tolerance_hz')
        if tolerance < 0:
            raise ValueError('tolerance_hz: must be nonnegative')
    records = []; ids = set()
    for observation in observations:
        if type(observation) is not dict or set(observation) != {'mode_id','frequency_hz','source_ref'}:
            raise ValueError('measurement: exactly mode_id,frequency_hz,source_ref required')
        mode_id = observation['mode_id']
        if type(mode_id) is not int or not 1 <= mode_id <= len(M) or mode_id in ids:
            raise ValueError(f'measurement mode_id: expected unique integer in 1..{len(M)}')
        ids.add(mode_id)
        frequency = _number(observation['frequency_hz'], 'measured frequency_hz')
        if frequency <= 0:
            raise ValueError('measured frequency_hz: must be positive')
        source = _text(observation['source_ref'], 'source_ref', 256)
        records.append((mode_id, frequency, source))
    modes = _modes(M, K)
    comparisons = []
    for mode_id, frequency, source in sorted(records):
        predicted = modes[mode_id-1]['frequency_hz']; difference = abs(frequency-predicted)
        comparisons.append(dict(mode_id=mode_id, supplied_frequency_hz=frequency, calculated_frequency_hz=predicted,
                                absolute_difference_hz=difference, tolerance_hz=tolerance,
                                within_tolerance=difference <= tolerance, source_ref=source))
    return dict(request_id=request_id, capability='Vibration Testing', ledger_row=1546,
                artifact_status='supplied_modal_calculation', model='linear_undamped', dof_count=len(M),
                modes=modes, comparisons=comparisons,
                comparison_status='supplied_measurements_compared' if comparisons else 'no_supplied_measurements',
                missing_measurement_mode_ids=sorted(set(range(1,len(M)+1))-ids),
                test_performed=False, structural_certification=False, source_authenticity_verified=False,
                units={'mass':'kg','stiffness':'N/m','frequency':'Hz'},
                normalization='phi^T M phi = 1; largest absolute component positive; first near-tie wins',
                boundary='Calculation over supplied matrices and observations, not a physical vibration test or structural certification.')
