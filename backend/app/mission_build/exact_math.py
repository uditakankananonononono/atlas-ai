"""Exact, bounded polynomial arithmetic with independently replayable certificates.

No eval, no symbolic-string execution, and no claim of universal solving.
Coefficients are rational integers/strings, ascending by power.
"""
from fractions import Fraction
import re


def rational(value):
    if type(value) is int:
        result = Fraction(value)
    elif type(value) is str and re.fullmatch(r'[+-]?\d{1,40}(?:/\d{1,40})?', value):
        try:
            result = Fraction(value)
        except ZeroDivisionError as exc:
            raise ValueError('zero denominator') from exc
    else:
        raise ValueError('rational integer/string required')
    if max(abs(result.numerator), result.denominator).bit_length() > 128:
        raise ValueError('rational component limit')
    return result


def polynomial(values):
    if type(values) is not list or not 1 <= len(values) <= 33:
        raise ValueError('1..33 coefficients required')
    result = [rational(x) for x in values]
    while len(result) > 1 and result[-1] == 0:
        result.pop()
    return result


def evaluate(coefficients, x):
    value = Fraction(0)
    for coefficient in reversed(coefficients):
        value = value * x + coefficient
        if max(abs(value.numerator), value.denominator).bit_length() > 16384:
            raise ValueError('intermediate arithmetic limit')
    return value


def analyze(payload):
    p = polynomial(payload['coefficients'])
    x = rational(payload.get('at', 0))
    derivative = [p[i] * i for i in range(1, len(p))] or [Fraction(0)]
    integral = [Fraction(0)] + [c / (i + 1) for i, c in enumerate(p)]
    candidates = payload.get('root_candidates', [])
    if type(candidates) is not list or len(candidates) > 100:
        raise ValueError('at most 100 root candidates')
    roots = []
    for candidate in candidates:
        c = rational(candidate)
        residue = evaluate(p, c)
        roots.append({'candidate': str(c), 'residual': str(residue), 'is_root': residue == 0})
    bounds = payload.get('integrate_between')
    definite = None
    if bounds is not None:
        if type(bounds) is not list or len(bounds) != 2:
            raise ValueError('two integration bounds required')
        lo, hi = map(rational, bounds)
        definite = str(evaluate(integral, hi) - evaluate(integral, lo))
    return {'method': 'exact rational polynomial arithmetic', 'coefficients': list(map(str, p)),
            'at': str(x), 'value': str(evaluate(p, x)),
            'derivative': list(map(str, derivative)), 'antiderivative_zero_constant': list(map(str, integral)),
            'definite_integral': definite, 'root_checks': roots,
            'all_roots_found': False, 'universal_problem_solver': False}


def verify_certificate(payload, certificate):
    """Recompute every field from original problem; caller labels are not proof."""
    return type(certificate) is dict and certificate == analyze(payload)
