"""Row 1525 Ergonomics: assessment-instrument context kept with supplied exposures.

Pure computation over caller-supplied exposures (with optional caller-declared
limits), anthropometric percentile data and controls. A supplied score is kept
only together with its named instrument, version and citation and a declared
scale; the unit never computes a score and has no scoring authority. Reading
the result needs a qualified reviewer. No ergonomic test was performed.
"""
import unicodedata
import decimal
from decimal import Decimal, InvalidOperation

MAX_EXPOSURES = 64
MAX_ANTHROPOMETRIC = 128
MAX_CONTROLS = 64
MAX_TEXT = 128
MAX_MAGNITUDE = 10 ** 12

_TOP = frozenset(("task", "exposures", "anthropometric", "controls", "assessment_instrument", "score"))
_EXPOSURE = frozenset(("id", "kind", "value", "unit", "limit", "duration_s"))
_ANTHRO = frozenset(("dimension", "percentile", "value", "unit"))
_CONTROL = frozenset(("id", "description"))
_INSTRUMENT = frozenset(("name", "version", "source_citation"))
_SCORE = frozenset(("value", "scale_min", "scale_max"))


def _fail(code):
    raise ValueError("ERGONO1525:" + code)


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
    if type(value) not in (int, float) or (type(value) is int and value.bit_length() > 64) or (type(value) is float and value != value):
        _fail("invalid_number:" + field)
    if abs(value) > MAX_MAGNITUDE:
        _fail("invalid_number:" + field)
    try:
        return Decimal(str(value))
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


def _show(d):
    text = format(d.normalize(), "f")
    return text


def _context():
    return decimal.Context(prec=64, rounding=decimal.ROUND_HALF_EVEN, Emin=-999999, Emax=999999, clamp=0, capitals=1,
                           flags=[], traps=[decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow, decimal.Underflow])


def run(request):
    # Fixed local Decimal context around all arithmetic, so output never depends on the caller's ambient context.
    try:
        with decimal.localcontext(_context()):
            return _run(request)
    except decimal.DecimalException:
        _fail("arithmetic")


def _run(request):
    if type(request) is not dict:
        _fail("invalid_request")
    if _extra(request, _TOP):
        _fail("unknown_key")
    task = _text(request.get("task"), "task")
    exposures = _items(request.get("exposures"), "exposures", 1, MAX_EXPOSURES, _EXPOSURE)
    anthro = _items(request.get("anthropometric", []), "anthropometric", 0, MAX_ANTHROPOMETRIC, _ANTHRO)
    controls = _items(request.get("controls", []), "controls", 0, MAX_CONTROLS, _CONTROL)
    instrument = request.get("assessment_instrument")
    score = request.get("score")
    if instrument is not None:
        if type(instrument) is not dict:
            _fail("invalid_item:assessment_instrument")
        if _extra(instrument, _INSTRUMENT):
            _fail("unknown_key")
    if score is not None:
        if type(score) is not dict:
            _fail("invalid_item:score")
        if _extra(score, _SCORE):
            _fail("unknown_key")
        if instrument is None:
            _fail("score_without_instrument")
    if instrument is not None:
        for field in ("name", "version", "source_citation"):
            _text(instrument.get(field), field)
    out_exposures, exceeding, unassessed, seen = [], [], [], set()
    for e in exposures:
        ident = _text(e.get("id"), "id")
        if ident in seen:
            _fail("duplicate_id:exposures")
        seen.add(ident)
        _text(e.get("kind"), "kind")
        value = _num(e.get("value"), "value")
        unit = _text(e.get("unit"), "unit")
        if "duration_s" in e:
            if type(e["duration_s"]) is not int or e["duration_s"] < 0 or e["duration_s"] > MAX_MAGNITUDE:
                _fail("invalid_number:duration_s")
        limit = e.get("limit")
        over = margin = None
        if "limit" in e:
            lim = _num(limit, "limit")
            over = value > lim
            margin = _show(lim - value)
            (exceeding if over else []).append(ident)
        else:
            unassessed.append(ident)
        out_exposures.append({"id": ident, "kind": e["kind"], "value": e["value"], "unit": unit,
                              "exceeds_supplied_limit": over, "margin": margin})
    dims = {}
    keyseen = set()
    for a in anthro:
        dim = _text(a.get("dimension"), "dimension")
        pct = a.get("percentile")
        if type(pct) is not int or not 1 <= pct <= 99:
            _fail("invalid_percentile")
        _num(a.get("value"), "value")
        unit = _text(a.get("unit"), "unit")
        if (dim, pct) in keyseen:
            _fail("duplicate_percentile")
        keyseen.add((dim, pct))
        if dim in dims and dims[dim]["unit"] != unit:
            _fail("unit_mismatch")
        dims.setdefault(dim, {"unit": unit, "percentiles": []})["percentiles"].append(pct)
    out_anthro = []
    for dim in sorted(dims):
        pcts = sorted(dims[dim]["percentiles"])
        out_anthro.append({"dimension": dim, "unit": dims[dim]["unit"], "percentiles": pcts,
                           "spans_p5_p95": pcts[0] <= 5 and pcts[-1] >= 95})
    cseen = set()
    for c in controls:
        ident = _text(c.get("id"), "id")
        if ident in cseen:
            _fail("duplicate_id:controls")
        cseen.add(ident)
        _text(c.get("description"), "description")
    supplied = None
    if score is not None:
        value, lo, hi = (_num(score.get(k), k) for k in ("value", "scale_min", "scale_max"))
        if lo > hi:
            _fail("invalid_scale")
        if not lo <= value <= hi:
            _fail("score_out_of_scale")
        supplied = {"value": score["value"], "scale_min": score["scale_min"], "scale_max": score["scale_max"]}
    return {"task": task, "exposures": out_exposures, "anthropometric": out_anthro,
            "controls": [{"id": c["id"], "description": c["description"]} for c in controls],
            "assessment_instrument": None if instrument is None else {k: instrument[k] for k in ("name", "version", "source_citation")},
            "supplied_score": supplied, "computed_score": None, "scoring_authority": False,
            "interpretation_requires_qualified_reviewer": True,
            "summary": {"exposure_count": len(exposures), "exceeding_ids": sorted(exceeding), "unassessed_ids": sorted(unassessed)}}
