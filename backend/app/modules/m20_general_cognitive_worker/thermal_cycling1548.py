"""Row 1548 Thermal Cycling (ledger: requirement title only - "Thermal Cycling", no description).

Bounded plan over one caller-supplied thermal-cycle declaration. Delta against the
existing mechanism _env(d, 'thermal_cycling') in engineering_1510_1559.py (read on
live main 98bbd4ec, line 223): existing is a passive echo of the declaration with
test_executed False and no validation; this unit validates a bounded declaration
with THERM1548-tagged refusals and returns a labeled plan. Unlike row 1547 there is
no existing formula to reuse: _env computes nothing. The cycle-time figure here is
simple arithmetic over the supplied numbers (dwells plus two ramp legs), labeled an
idealized estimate, not a simulation; it is new interface-level arithmetic and the
contract says so. No physical test, chamber execution, survivability, certification
or release claim; the plan is a plan, never a result.
"""

import math
import unicodedata

ROW = 1548
_P = "THERM1548: "
_KEYS = ("profile", "cycles", "specimen_count", "preconditioning", "measurements", "acceptance_criteria")
_PROFILE_KEYS = ("low_temperature_c", "high_temperature_c", "ramp_rate_c_per_min",
                 "dwell_low_min", "dwell_high_min")
_BAD_CATS = ("Cc", "Cf", "Zl", "Zp")  # Zs accepted; Cs surrogates stay a disclosed residual
_LIMITS = [
    "Plan over supplied declarations only; the cycle-time figure is idealized arithmetic (dwells plus two constant-rate ramp legs), not a chamber simulation or measured response.",
    "No thermal cycling is executed here and no specimen survivability, certification or release judgment is made or implied.",
    "Supplied preconditioning, measurements and acceptance criteria are bookkeeping only; they are never evaluated against the plan.",
]


def _unicode_clean(text, name):
    for ch in text:
        if unicodedata.category(ch) in _BAD_CATS:
            _fail(name + " carries a refused Unicode character")
    return text


class ThermError(ValueError):
    pass


def _fail(msg):
    raise ThermError(_P + msg)


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
    prof = data["profile"]
    if type(prof) is not dict:
        _fail("profile must be a mapping")
    if len(prof) > len(_PROFILE_KEYS):
        _fail("unknown profile key")
    if any(type(k) is not str for k in prof):
        _fail("profile keys must be text")
    for k in _PROFILE_KEYS:
        if k not in prof:
            _fail(k + " required")
    if len(prof) != len(_PROFILE_KEYS):
        _fail("unknown profile key")
    cycles = data["cycles"]
    if type(cycles) is not int or not 1 <= cycles <= 100000:
        _fail("cycles must be an integer from 1 to 100000")
    n = data["specimen_count"]
    if type(n) is not int or not 1 <= n <= 1000:
        _fail("specimen_count must be an integer from 1 to 1000")
    preconditioning = _texts(data["preconditioning"], "preconditioning", 0, 10, 64)
    measurements = _texts(data["measurements"], "measurements", 1, 20, 64)
    criteria = _texts(data["acceptance_criteria"], "acceptance_criteria", 0, 10, 64)
    low = _number(prof["low_temperature_c"], "low_temperature_c", -273.15, 1000.0, positive=False)
    high = _number(prof["high_temperature_c"], "high_temperature_c", -273.15, 1000.0, positive=False)
    if not low < high:
        _fail("low_temperature_c must be below high_temperature_c")
    ramp = _number(prof["ramp_rate_c_per_min"], "ramp_rate_c_per_min", 0, 1000.0, positive=True)
    dwell_low = _number(prof["dwell_low_min"], "dwell_low_min", 0.0, 100000.0, positive=False)
    dwell_high = _number(prof["dwell_high_min"], "dwell_high_min", 0.0, 100000.0, positive=False)
    swing = high - low
    per_cycle = dwell_low + dwell_high + 2 * swing / ramp
    if not math.isfinite(per_cycle):
        _fail("derived cycle time is not finite")
    total = per_cycle * cycles
    if not math.isfinite(total):
        _fail("derived total time is not finite")
    entry = {"low_temperature_c": low, "high_temperature_c": high,
             "temperature_swing_c": swing, "ramp_rate_c_per_min": ramp,
             "dwell_low_min": dwell_low, "dwell_high_min": dwell_high,
             "estimated_cycle_time_min": per_cycle}
    return {"row": ROW, "test_type": "thermal_cycling", "plan": [entry],
            "cycles": cycles,
            "estimated_cycle_time_min": per_cycle,
            "estimated_total_time_min": total,
            "specimen_count": n,
            "preconditioning_declared": len(preconditioning),
            "measurements_declared": len(measurements),
            "acceptance_criteria_declared": len(criteria),
            "test_executed": False, "plan_only": True, "limits": list(_LIMITS)}
