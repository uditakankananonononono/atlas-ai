"""Row 1545 Environmental Testing (ledger: requirement title only - "Environmental Testing", no description).

Bounded plan over caller-supplied environmental exposure declarations. Delta against
the existing mechanism _env(d, 'environmental') in engineering_1510_1559.py (read on
live main 98bbd4ec, line 223): existing is a passive echo of the declaration with
test_executed False and no validation; this unit validates a bounded multi-profile
declaration with ENV1545-tagged refusals and returns a labeled plan. Unlike row 1547
there is no existing formula to reuse: _env computes nothing, so this unit is
interface and aggregation bookkeeping only, and says so. No physical test,
conditioning execution, survivability, certification or release claim; the plan is
a plan, never a result.
"""

import math
import unicodedata

ROW = 1545
_P = "ENV1545: "
_KEYS = ("profiles", "specimen_count", "preconditioning", "measurements", "acceptance_criteria")
_PROFILE_KEYS = ("condition", "setpoint", "unit", "dwell_hours")
# bookkeeping unit conventions per condition, not standards compliance
_UNITS = {"temperature": ("celsius", "fahrenheit", "kelvin"),
          "humidity": ("percent_rh",),
          "pressure": ("kpa",),
          "salt_fog": ("percent",),
          "dust": ("g_per_m3",),
          "solar": ("w_per_m2",)}
# wide sanity bounds for supplied setpoints; bookkeeping only, not physical limits
_BOUNDS = {"temperature": (-273.15, 1000.0), "humidity": (0.0, 100.0),
           "pressure": (0.0, 10000.0), "salt_fog": (0.0, 100.0),
           "dust": (0.0, 1000.0), "solar": (0.0, 2000.0)}
_BAD_CATS = ("Cc", "Cf", "Zl", "Zp")  # Zs accepted; Cs surrogates stay a disclosed residual
_LIMITS = [
    "Plan over supplied declarations only; conditions, units and bounds are bookkeeping conventions, not test standards.",
    "No environmental conditioning is executed here and no specimen survivability, certification or release judgment is made or implied.",
    "Supplied preconditioning, measurements and acceptance criteria are bookkeeping only; they are never evaluated against the plan.",
]


def _unicode_clean(text, name):
    for ch in text:
        if unicodedata.category(ch) in _BAD_CATS:
            _fail(name + " carries a refused Unicode character")
    return text


class EnvError(ValueError):
    pass


def _fail(msg):
    raise EnvError(_P + msg)


def _number(value, name, lo, hi, positive):
    if type(value) not in (int, float):
        _fail(name + " must be a number")
    if type(value) is int:
        # exact ints are always finite; bound them before any float contact
        if value < lo or value > hi or (positive and value <= 0):
            _fail(name + " out of range")
        return value
    if not math.isfinite(value):
        _fail(name + " must be finite")
    if value < lo or value > hi or (positive and value <= 0):
        _fail(name + " out of range")
    return value


def _texts(value, name, lo, hi, cap):
    if type(value) is not list or not lo <= len(value) <= hi:
        _fail(name + " must be a list of %d to %d entries" % (lo, hi))
    for entry in value:
        if type(entry) is not str:
            _fail(name + " entries must be text")
        if len(entry) > cap:  # cap before strip, before Unicode
            _fail(name + " entries must be at most %d characters" % cap)
        if not entry.strip():
            _fail(name + " entries must be non-empty text")
        _unicode_clean(entry, name)
    return list(value)


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
    preconditioning = _texts(data["preconditioning"], "preconditioning", 0, 10, 64)
    measurements = _texts(data["measurements"], "measurements", 1, 20, 64)
    criteria = _texts(data["acceptance_criteria"], "acceptance_criteria", 0, 10, 64)
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
        condition = prof["condition"]
        if type(condition) is not str:
            _fail("unsupported condition")
        if len(condition) > 32:  # cap before the enum
            _fail("condition must be at most 32 characters")
        units = _UNITS.get(condition)
        if units is None:
            _fail("unsupported condition")
        _unicode_clean(condition, "condition")
        unit = prof["unit"]
        if type(unit) is not str:
            _fail("unsupported unit")
        if len(unit) > 32:  # cap before the enum
            _fail("unit must be at most 32 characters")
        if unit not in units:
            _fail("unsupported unit")
        _unicode_clean(unit, "unit")
        lo, hi = _BOUNDS[condition]
        setpoint = _number(prof["setpoint"], "setpoint", lo, hi, positive=False)
        dwell = _number(prof["dwell_hours"], "dwell_hours", 0, 100000, positive=True)
        out.append({"index": i, "condition": condition, "unit": unit,
                    "setpoint": setpoint, "dwell_hours": dwell})
    condition_counts = {}
    for p in out:
        condition_counts[p["condition"]] = condition_counts.get(p["condition"], 0) + 1
    return {"row": ROW, "test_type": "environmental", "plan": out,
            "profiles_supplied": len(out),
            "condition_counts": {k: condition_counts[k] for k in sorted(condition_counts)},
            "total_dwell_hours": math.fsum(p["dwell_hours"] for p in out),
            "max_dwell_hours": max(p["dwell_hours"] for p in out),
            "specimen_count": n,
            "preconditioning_declared": len(preconditioning),
            "measurements_declared": len(measurements),
            "acceptance_criteria_declared": len(criteria),
            "test_executed": False, "plan_only": True, "limits": list(_LIMITS)}
