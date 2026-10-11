"""[Row 106] Priming Effects: descriptive difference of two supplied proportions, with disclosure gating.

The caller declares a context label, whether the context-setting is disclosed and, optionally, four counts: successes
and totals for an exposed and a control group. The unit reports the exact unadjusted difference of proportions and a
Wald interval with reliability flags. It claims no cause, no unconscious effect and no effectiveness, never decides how
to prime anyone, never sends or posts anything, measures no behaviour and gives no advice.
"""
from __future__ import annotations

import math
import unicodedata
from fractions import Fraction

ROW = 106
CODE = "PRIME106"
MAX_CONTEXT = 200
MAX_COUNT = 10**9
Z95 = 1.96
SMALL_CELL = 5
LIMITS = (
    "Supplied counts only; assignment, confounding and measurement are not verified.",
    "An unadjusted difference of proportions; no causal claim and no claim that anything is unconscious or effective.",
    "Context-setting must be disclosed; not persuasion and not advice.",
)
_REQ = ("context", "disclosed")
_COUNTS = ("exposed_successes", "exposed_total", "control_successes", "control_total")
_BAD_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})


class PrimingError(ValueError):
    pass


def _fail(msg):
    raise PrimingError(f"{CODE}: {msg}")


def _text(value, field, limit):
    if type(value) is not str:
        _fail(f"{field} must be a string")
    if len(value) > limit:
        _fail(f"{field} is longer than {limit} characters")
    if not value.strip():
        _fail(f"{field} must not be blank")
    for ch in value:
        if unicodedata.category(ch) in _BAD_CATEGORIES:
            _fail(f"{field} contains a control, format or separator character")
    return value


def _decimal6(f):
    n = round(abs(f) * 10**6)  # Fraction rounding: half to even, exact
    sign = "-" if f < 0 and n else ""
    return f"{sign}{n // 10**6}.{n % 10**6:06d}"


def _frac(f):
    return f"{f.numerator}/{f.denominator}"


def review(data):
    if type(data) is not dict:
        _fail("input must be a mapping")
    if len(data) > len(_REQ) + len(_COUNTS):
        _fail("too many keys")
    for k in data:
        if type(k) is not str or (k not in _REQ and k not in _COUNTS):
            _fail("unknown key")
    for k in _REQ:
        if k not in data:
            _fail(f"{k} required")
    context = _text(data["context"], "context", MAX_CONTEXT)
    if type(data["disclosed"]) is not bool:
        _fail("disclosed must be true or false")
    disclosed = data["disclosed"]
    present = [k for k in _COUNTS if k in data]
    if present and len(present) != len(_COUNTS):
        _fail("counts must be supplied as all four or none")
    effect = effect_dec = interval = None
    degenerate = small = False
    if present:
        for k in _COUNTS:
            v = data[k]
            if type(v) is not int or not 0 <= v <= MAX_COUNT:
                _fail(f"{k} must be an integer from 0 to {MAX_COUNT}")
        es, en, cs, cn = (data[k] for k in _COUNTS)
        if en < 1:
            _fail("exposed_total must be at least 1")
        if cn < 1:
            _fail("control_total must be at least 1")
        if es > en:
            _fail("exposed_successes must not exceed exposed_total")
        if cs > cn:
            _fail("control_successes must not exceed control_total")
        p1, p2 = Fraction(es, en), Fraction(cs, cn)
        diff = p1 - p2
        effect, effect_dec = _frac(diff), _decimal6(diff)
        small = min(es, en - es, cs, cn - cs) < SMALL_CELL
        if 0 < p1 < 1 and 0 < p2 < 1:
            se = math.sqrt(float(p1 * (1 - p1) / en + p2 * (1 - p2) / cn))
            d = float(diff)
            interval = [round(d - Z95 * se, 6), round(d + Z95 * se, 6)]
        else:
            degenerate = True
    return {
        "row": ROW, "context": context, "disclosed": disclosed,
        "effect": effect, "effect_decimal": effect_dec, "interval_95": interval,
        "degenerate_rate": degenerate, "small_sample": small, "interval_unreliable": degenerate or small,
        "causal_estimate_available": False, "descriptive_difference_available": bool(present),
        "covert_influence_blocked": not disclosed, "allowed": disclosed and bool(present),
        "limits": list(LIMITS),
    }
