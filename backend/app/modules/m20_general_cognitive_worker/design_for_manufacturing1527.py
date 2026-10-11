"""Row 1527 Design for Manufacturing: rule checks over supplied process constraints.

Compares caller-supplied feature values with caller-supplied min/max process
constraints using exact decimal arithmetic (bounds are inclusive). A feature
lacking a constrained field is reported as missing, never as a pass. Units must
match exactly. It plans no process and makes no shop-floor claim.
"""
import unicodedata
from decimal import Decimal, InvalidOperation
from fractions import Fraction

MAX_CONSTRAINTS = 64
MAX_FEATURES = 64
MAX_VALUES = 32
MAX_TEXT = 128
MAX_MAGNITUDE = 10 ** 12

_TOP = frozenset(("process", "process_constraints", "features"))
_CONS = frozenset(("id", "field", "unit", "min", "max"))
_FEAT = frozenset(("id", "values"))
_VAL = frozenset(("value", "unit"))


def _fail(code):
    raise ValueError("DESMAN1527:" + code)




def _has_forbidden(value):
    return any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") for c in value)


MAX_KEYS = 64


def _extra(d, allowed):
    # key count is checked before any set construction or iteration
    if len(d) > MAX_KEYS:
        _fail("invalid_count:keys")
    for key in d:
        if type(key) is not str:
            _fail("unknown_key")
    return set(d) - allowed


def _text(value, field):
    if type(value) is not str or not 1 <= len(value) <= MAX_TEXT or not value.strip() or _has_forbidden(value):
        _fail("invalid_text:" + field)
    return value


def _num(value, field):
    if type(value) not in (int, float) or (type(value) is int and value.bit_length() > 64) or (type(value) is float and value != value) or abs(value) > MAX_MAGNITUDE:
        _fail("invalid_number:" + field)
    try:
        return Fraction(Decimal(str(value)))
    except InvalidOperation:
        _fail("invalid_number:" + field)


def _items(value, name, lo, hi, allowed):
    if type(value) is not list or not lo <= len(value) <= hi:
        _fail("invalid_count:" + name)
    for item in value:
        if type(item) is not dict:
            _fail("invalid_item:" + name)
        if _extra(item, allowed):
            _fail("unknown_key")
    return value


def _show(fr):
    """Exact decimal rendering of a Fraction whose denominator divides a power of ten (no decimal context used)."""
    sign = "-" if fr < 0 else ""
    num, den = abs(fr.numerator), fr.denominator
    k = 0
    while (10 ** k) % den:
        k += 1
    scaled = num * (10 ** k // den)
    whole, frac = divmod(scaled, 10 ** k)
    text = str(whole)
    if k:
        digits = str(frac).rjust(k, "0").rstrip("0")
        if digits:
            text += "." + digits
    return sign + text if (whole or frac) else "0"


def run(request):
    if type(request) is not dict:
        _fail("invalid_request")
    if _extra(request, _TOP):
        _fail("unknown_key")
    process = _text(request.get("process"), "process")
    cons = _items(request.get("process_constraints"), "process_constraints", 1, MAX_CONSTRAINTS, _CONS)
    feats = _items(request.get("features"), "features", 1, MAX_FEATURES, _FEAT)
    parsed, seen = [], set()
    for c in cons:
        cid = _text(c.get("id"), "id")
        if cid in seen:
            _fail("duplicate_id:process_constraints")
        seen.add(cid)
        field = _text(c.get("field"), "field")
        unit = _text(c.get("unit"), "unit")
        if "min" not in c and "max" not in c:
            _fail("constraint_needs_bound")
        lo = _num(c["min"], "min") if "min" in c else None
        hi = _num(c["max"], "max") if "max" in c else None
        if lo is not None and hi is not None and lo > hi:
            _fail("invalid_bounds")
        parsed.append((cid, field, unit, lo, hi))
    checks, fseen, violations, missing = [], set(), 0, 0
    for f in feats:
        fid = _text(f.get("id"), "id")
        if fid in fseen:
            _fail("duplicate_id:features")
        fseen.add(fid)
        values = f.get("values")
        if type(values) is not dict:
            _fail("invalid_item:values")
        if len(values) > MAX_VALUES:
            _fail("invalid_count:values")
        nums = {}
        for field, cell in values.items():
            _text(field, "field")
            if type(cell) is not dict:
                _fail("invalid_item:values")
            if _extra(cell, _VAL):
                _fail("unknown_key")
            nums[field] = (_num(cell.get("value"), "value"), _text(cell.get("unit"), "unit"))
        found, absent = [], []
        for cid, field, unit, lo, hi in parsed:
            if field not in nums:
                absent.append(cid)
                continue
            value, vunit = nums[field]
            if vunit != unit:
                _fail("unit_mismatch")
            if lo is not None and value < lo:
                found.append({"constraint_id": cid, "kind": "below_min", "value": _show(value), "bound": _show(lo),
                              "margin": _show(lo - value)})
            if hi is not None and value > hi:
                found.append({"constraint_id": cid, "kind": "above_max", "value": _show(value), "bound": _show(hi),
                              "margin": _show(value - hi)})
        violations += len(found)
        missing += len(absent)
        checks.append({"feature_id": fid, "violations": found, "missing_constraint_ids": absent})
    with_violations = sum(1 for c in checks if c["violations"])
    with_missing = sum(1 for c in checks if c["missing_constraint_ids"])
    with_findings = sum(1 for c in checks if c["violations"] or c["missing_constraint_ids"])
    return {"process": process, "feature_checks": checks, "process_planning_claimed": False,
            "disposition": "bookkeeping_only",
            "summary": {"feature_count": len(feats), "constraint_count": len(cons), "violation_count": violations,
                        "missing_count": missing, "features_with_violations_count": with_violations,
                        "features_with_missing_count": with_missing,
                        "features_without_findings_count": len(feats) - with_findings}}
