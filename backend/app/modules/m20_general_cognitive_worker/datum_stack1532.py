"""Bounded 1D datum-referenced signed interval chain, not full GD&T."""
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import math

MAX_ITEMS = 64
MAX_TEXT = 128
MAX_NUMBER_TEXT = 64
MAX_MAGNITUDE = 10**12
UNITS = frozenset(("mm", "cm", "m", "inch"))


def _fail(code):
    raise ValueError("GDT1532:" + code)


def _text(value, field):
    if type(value) is not str or not 1 <= len(value) <= MAX_TEXT or not value.strip():
        _fail("invalid_text:" + field)
    return value


def _number(value, field):
    if type(value) not in (str, int, float):
        _fail("invalid_number:" + field)
    if type(value) is float and not math.isfinite(value):
        _fail("invalid_number:" + field)
    # Reject huge ints before decimal conversion and its digit allocation.
    if type(value) is int and abs(value) > MAX_MAGNITUDE:
        _fail("number_bound:" + field)
    text = str(value)
    if not 1 <= len(text) <= MAX_NUMBER_TEXT or text.strip() != text:
        _fail("invalid_number:" + field)
    try:
        d = Decimal(text)
    except InvalidOperation:
        _fail("invalid_number:" + field)
    if not d.is_finite():
        _fail("invalid_number:" + field)
    if d.copy_abs() > MAX_MAGNITUDE or abs(d.as_tuple().exponent) > 18:
        _fail("number_bound:" + field)
    return Fraction(d)


def _rows(packet, name, required, minimum):
    rows = packet.get(name)
    if type(rows) is not list or not minimum <= len(rows) <= MAX_ITEMS:
        _fail("invalid_count:" + name)
    seen = set()
    for row in rows:
        if type(row) is not dict:
            _fail("invalid_record:" + name)
        if set(row) != required:
            _fail("invalid_fields:" + name)
        key = _text(row["id"], "id")
        if key in seen:
            _fail("duplicate_id:" + name)
        seen.add(key)
        _text(row["source_ref"], "source_ref")
        if row["unit"] != packet["unit"]:
            _fail("unit_mismatch:" + name)
    return sorted(rows, key=lambda row: row["id"])


def evaluate_stack(packet):
    """Return exact rational text, closed intervals and supplied source references.

    Contribution is sign * (datum offset + component local dimension).
    All fits constrain the same scalar; their intersection, not union, is used.
    No source authenticity, distribution, inspection or engineering release claim.
    """
    if type(packet) is not dict:
        _fail("invalid_packet")
    if set(packet) != {"geometry", "unit", "datums", "components", "fit_limits"}:
        _fail("unknown_fields:packet")
    if packet["geometry"] != "linear_1d":
        _fail("unsupported_geometry")
    if type(packet["unit"]) is not str or packet["unit"] not in UNITS:
        _fail("unsupported_unit")
    datums = _rows(packet, "datums", {"id", "offset", "unit", "source_ref"}, 1)
    components = _rows(packet, "components", {"id", "datum", "nominal", "lower", "upper", "sign", "unit", "source_ref"}, 1)
    fits = _rows(packet, "fit_limits", {"id", "lower", "upper", "unit", "source_ref"}, 0)
    offsets = {d["id"]: (_number(d["offset"], "offset"), d["source_ref"]) for d in datums}
    nominal = low = high = Fraction(0)
    trace = []
    for c in components:
        key = c["id"]
        datum = _text(c["datum"], "datum")
        if datum not in offsets:
            _fail("unknown_datum:" + key)
        sign = c["sign"]
        if type(sign) is not int or sign not in (-1, 1):
            _fail("invalid_sign:" + key)
        n, a, b = (_number(c[field], field) for field in ("nominal", "lower", "upper"))
        if a > b:
            _fail("inverted_interval:" + key)
        if not a <= n <= b:
            _fail("nominal_outside_interval:" + key)
        offset, datum_ref = offsets[datum]
        cn = sign * (offset + n)
        ca, cb = (offset + a, offset + b) if sign == 1 else (-(offset + b), -(offset + a))
        nominal += cn
        low += ca
        high += cb
        trace.append({"id": key, "source_ref": c["source_ref"], "datum": datum,
                      "datum_source_ref": datum_ref, "sign": sign,
                      "nominal_contribution": str(cn), "lower_contribution": str(ca), "upper_contribution": str(cb)})
    fit_trace = []
    for f in fits:
        a, b = (_number(f[field], field) for field in ("lower", "upper"))
        if a > b:
            _fail("inverted_interval:" + f["id"])
        fit_trace.append({"id": f["id"], "source_ref": f["source_ref"], "lower": str(a), "upper": str(b)})
    intersection = None
    status = "no_fit_limits_declared"
    if fit_trace:
        fa = max(Fraction(f["lower"]) for f in fit_trace)
        fb = min(Fraction(f["upper"]) for f in fit_trace)
        if fa > fb or high < fa or low > fb:
            status = "no_feasible_fit"
        elif fa <= low and high <= fb:
            status = "guaranteed_within_declared_limits"
        else:
            status = "not_guaranteed"
        if fa <= fb:
            intersection = {"lower": str(fa), "upper": str(fb)}
    return {"feature_id": 1532, "model": "signed_datum_linear_1d_closed_intervals", "unit": packet["unit"],
            "nominal": str(nominal), "lower": str(low), "upper": str(high),
            "source_trace": trace, "fit_trace": fit_trace, "fit_intersection": intersection, "fit_status": status,
            "sources_verified": False, "full_gdt_claimed": False, "physical_inspection_claimed": False,
            "release_authorized": False, "statistical_rss_performed": False}
