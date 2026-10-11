"""Row 1529 Design for Sustainability: caller-supplied impact tallies per lifecycle stage.

Sums caller-supplied impact values per category with exact decimal arithmetic,
requires one unit per category, and reports per-stage shares as exact
fractions plus the stage(s) with the largest value. The functional unit and
system boundary must be stated. A comparative claim needs review; the unit
makes no LCA-certification claim and uses no characterisation factors.
"""
import unicodedata
from decimal import Decimal, InvalidOperation
from fractions import Fraction

MAX_STAGES = 32
MAX_CATEGORIES = 16
MAX_TEXT = 128
MAX_MAGNITUDE = 10 ** 12

_TOP = frozenset(("functional_unit", "system_boundary", "lifecycle_stages"))
_STAGE = frozenset(("id", "impacts"))
_CELL = frozenset(("value", "unit"))


def _fail(code):
    raise ValueError("DESSUS1529:" + code)


_BAD_CHARS = frozenset("\x7f\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff")


def _has_forbidden(value):
    return any(c in _BAD_CHARS or unicodedata.category(c) in ("Cc", "Zl", "Zp") for c in value)


MAX_KEYS = 64


def _extra(d, allowed):
    # key count is checked before any set construction or iteration
    if len(d) > MAX_KEYS:
        _fail("invalid_count:keys")
    return set(d) - allowed


def _text(value, field):
    if type(value) is not str or not 1 <= len(value) <= MAX_TEXT or not value.strip() or _has_forbidden(value):
        _fail("invalid_text:" + field)
    return value


def _num(value, field):
    if type(value) not in (int, float) or (type(value) is int and value.bit_length() > 64) or (type(value) is float and value != value) or abs(value) > MAX_MAGNITUDE:
        _fail("invalid_number:" + field)
    try:
        return Decimal(str(value))
    except InvalidOperation:
        _fail("invalid_number:" + field)


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


def _frac(f):
    return str(f.numerator) if f.denominator == 1 else "%d/%d" % (f.numerator, f.denominator)


def run(request):
    if type(request) is not dict:
        _fail("invalid_request")
    if _extra(request, _TOP):
        _fail("unknown_key")
    unit_text = _text(request.get("functional_unit"), "functional_unit")
    boundary = _text(request.get("system_boundary"), "system_boundary")
    stages = request.get("lifecycle_stages")
    if type(stages) is not list or not 1 <= len(stages) <= MAX_STAGES:
        _fail("invalid_count:lifecycle_stages")
    seen, units, values = set(), {}, {}
    for stage in stages:
        if type(stage) is not dict:
            _fail("invalid_item:lifecycle_stages")
        if _extra(stage, _STAGE):
            _fail("unknown_key")
        sid = _text(stage.get("id"), "id")
        if sid in seen:
            _fail("duplicate_id:lifecycle_stages")
        seen.add(sid)
        impacts = stage.get("impacts")
        if type(impacts) is not dict:
            _fail("invalid_item:impacts")
        if len(impacts) > MAX_CATEGORIES:
            _fail("invalid_count:impacts")
        for cat, cell in impacts.items():
            _text(cat, "category")
            if type(cell) is not dict:
                _fail("invalid_item:impacts")
            if _extra(cell, _CELL):
                _fail("unknown_key")
            value = _num(cell.get("value"), "value")
            unit = _text(cell.get("unit"), "unit")
            if units.setdefault(cat, unit) != unit:
                _fail("unit_mismatch")
            values.setdefault(cat, {})[sid] = Fraction(value)
    totals, shares, hotspots = {}, {}, {}
    for cat in sorted(values):
        total = sum(values[cat].values(), Fraction(0))
        totals[cat] = {"total": _show(total), "unit": units[cat]}
        if total == 0:
            shares[cat] = None
        else:
            shares[cat] = {sid: _frac(v / total) for sid, v in sorted(values[cat].items())}
        top = max(values[cat].values())
        hotspots[cat] = sorted(sid for sid, v in values[cat].items() if v == top)
    return {"functional_unit": unit_text, "system_boundary": boundary, "stage_count": len(stages),
            "impact_totals": totals, "shares": shares, "hotspots": hotspots,
            "comparative_claim_review_required": True, "lca_certification_claimed": False}
