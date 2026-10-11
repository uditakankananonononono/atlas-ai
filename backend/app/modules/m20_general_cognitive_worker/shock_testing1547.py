"""Row 1547 Shock Testing (ledger: requirement title only - "Shock Testing", no description).

Bounded plan over caller-supplied shock pulse declarations. Delta against the existing
mechanism _shock in engineering_1510_1559.py (read on live main a294723b, line 228):
existing computes one pulse's estimated delta velocity with three shape factors and an
untagged ValueError; this unit validates a bounded multi-profile declaration with
SHOCK1547-tagged refusals, keeps the same physical factors and formula per profile, and
returns a labeled plan. No physical test, solver execution, survivability, certification
or release claim; the plan is a plan, never a result.
"""

import math
import unicodedata

ROW = 1547
_P = "SHOCK1547: "
_KEYS = ("profiles", "specimen_count", "axes", "acceptance_criteria")
_PROFILE_KEYS = ("pulse_shape", "peak_acceleration_g", "duration_ms")
_SHAPES = {"half_sine": 2 / math.pi, "rectangular": 1.0, "terminal_peak_sawtooth": 0.5}
_AXES = ("x", "y", "z")
_BAD_CATS = ("Cc", "Cf", "Zl", "Zp")  # Zs accepted; Cs surrogates stay a disclosed residual
_LIMITS = [
    "Plan over supplied declarations only; the pulse model is the classical idealized shape-factor estimate, not a measured response.",
    "No test is executed here and no specimen survivability, certification or release judgment is made or implied.",
    "Supplied acceptance criteria are bookkeeping only; they are never evaluated against the estimate.",
]


def _unicode_clean(text, name):
    for ch in text:
        if unicodedata.category(ch) in _BAD_CATS:
            _fail(name + " carries a refused Unicode character")
    return text


class ShockError(ValueError):
    pass


def _fail(msg):
    raise ShockError(_P + msg)


def _positive_number(value, name, cap):
    if type(value) not in (int, float):
        _fail(name + " must be a number")
    if type(value) is int:
        # exact ints are always finite; bound them before any float contact
        if value <= 0 or value > cap:
            _fail(name + " must be greater than 0 and at most " + str(cap))
        return value
    if not math.isfinite(value):
        _fail(name + " must be finite")
    if value <= 0 or value > cap:
        _fail(name + " must be greater than 0 and at most " + str(cap))
    return value


def plan(data):
    if type(data) is not dict:
        _fail("input must be a mapping")
    if len(data) > len(_KEYS):
        _fail("unknown key")
    if any(type(k) is not str for k in data):
        _fail("keys must be text")
    for k in _KEYS:
        if k not in data:
            _fail(k + " required")
    if len(data) != len(_KEYS):
        _fail("unknown key")
    profiles = data["profiles"]
    if type(profiles) is not list:
        _fail("profiles must be a list")
    if not 1 <= len(profiles) <= 20:
        _fail("profiles must hold 1 to 20 items")
    n = data["specimen_count"]
    if type(n) is not int or not 1 <= n <= 1000:
        _fail("specimen_count must be an integer from 1 to 1000")
    axes = data["axes"]
    if type(axes) is not list or not 1 <= len(axes) <= 3:
        _fail("axes must be a list of 1 to 3 items")
    for a in axes:
        if type(a) is not str:
            _fail("axes entries must be text")
        if len(a) > 8:
            _fail("axes entries must be at most 8 characters")
        _unicode_clean(a, "axes")
        if a not in _AXES:
            _fail("axes entries must be x, y or z")
    if len(set(axes)) != len(axes):
        _fail("duplicate axis")
    criteria = data["acceptance_criteria"]
    if type(criteria) is not list or len(criteria) > 10:
        _fail("acceptance_criteria must be a list of at most 10 entries")
    for c in criteria:
        if type(c) is not str:
            _fail("acceptance_criteria entries must be text")
        if len(c) > 64:
            _fail("acceptance_criteria entries must be at most 64 characters")
        if not c.strip():
            _fail("acceptance_criteria entries must be non-empty text")
        _unicode_clean(c, "acceptance_criteria")
    out = []
    for i, prof in enumerate(profiles):
        if type(prof) is not dict:
            _fail("each profile must be a mapping")
        if len(prof) > len(_PROFILE_KEYS):
            _fail("unknown profile key")
        if any(type(k) is not str for k in prof):
            _fail("profile keys must be text")
        for k in _PROFILE_KEYS:
            if k not in prof:
                _fail(k + " required")
        if len(prof) != len(_PROFILE_KEYS):
            _fail("unknown profile key")
        shape = prof["pulse_shape"]
        if type(shape) is not str:
            _fail("unsupported pulse_shape")
        if len(shape) > 32:
            _fail("pulse_shape must be at most 32 characters")
        factor = _SHAPES.get(shape)
        if factor is None:
            _fail("unsupported pulse_shape")
        _unicode_clean(shape, "pulse_shape")
        peak = _positive_number(prof["peak_acceleration_g"], "peak_acceleration_g", 100000)
        duration = _positive_number(prof["duration_ms"], "duration_ms", 60000)
        out.append({"index": i, "pulse_shape": shape,
                    "peak_acceleration_g": peak, "duration_ms": duration,
                    "shape_factor": factor,
                    "estimated_delta_velocity_m_per_s": peak * 9.80665 * duration / 1000 * factor})
    shape_counts = {}
    for p in out:
        shape_counts[p["pulse_shape"]] = shape_counts.get(p["pulse_shape"], 0) + 1
    return {"row": ROW, "plan": out, "profiles_supplied": len(out),
            "max_estimated_delta_velocity_m_per_s": max(p["estimated_delta_velocity_m_per_s"] for p in out),
            "shape_counts": {k: shape_counts[k] for k in sorted(shape_counts)},
            "specimen_count": n, "axes": list(axes),
            "acceptance_criteria_declared": len(criteria),
            "test_executed": False, "plan_only": True, "limits": list(_LIMITS)}
