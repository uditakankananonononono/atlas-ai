"""Row 1544 Accelerated Life Testing: Arrhenius stress-level bookkeeping over caller-supplied data.

For each caller-supplied stress level the unit computes the Arrhenius exponent
exactly (as a fraction, from a fixed Boltzmann constant) and the acceleration
factor as exp(exponent) in float, plus exact device-hours and totals.
It makes no life, MTTF, reliability or field claim; the failure mechanism
must be declared and its equivalence across stress levels is not validated.
"""
import math
import unicodedata
from decimal import Decimal, InvalidOperation
from fractions import Fraction

MAX_LEVELS = 32
MAX_TEXT = 128
MAX_KEYS = 64
MAX_EA_EV = 10
MAX_TEMP_K = 10000
MAX_HOURS = 10 ** 9
MAX_UNITS = 10 ** 6
MAX_EXPONENT = 700
BOLTZMANN_EV_PER_K = Fraction(8617333262, 10 ** 14)

_TOP = frozenset(("model", "failure_mechanism", "activation_energy_ev", "use_temperature_k", "stress_levels"))
_LEVEL = frozenset(("id", "temperature_k", "hours", "units_on_test", "failures"))


def _fail(code):
    raise ValueError("ACCLIF1544:" + code)


def _has_forbidden(value):
    return any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") for c in value)


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


def _positive(value, field, maximum):
    if type(value) not in (int, float) or (type(value) is int and value.bit_length() > 64) or (type(value) is float and value != value):
        _fail("invalid_number:" + field)
    if not 0 < value <= maximum:
        _fail("invalid_number:" + field)
    try:
        return Fraction(Decimal(str(value)))
    except InvalidOperation:
        _fail("invalid_number:" + field)


def _count(value, field, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        _fail("invalid_number:" + field)
    return value


def _show(fr):
    """Exact decimal rendering of a non-negative Fraction whose denominator divides a power of ten."""
    num, den = fr.numerator, fr.denominator
    k = 0
    while (10 ** k) % den:
        k += 1
    whole, frac = divmod(num * (10 ** k // den), 10 ** k)
    text = str(whole)
    if k:
        digits = str(frac).rjust(k, "0").rstrip("0")
        if digits:
            text += "." + digits
    return text


def _frac(f):
    return str(f.numerator) if f.denominator == 1 else "%d/%d" % (f.numerator, f.denominator)


def _model(value):
    # order: exact type str, then raw length cap, then the enum compare
    if type(value) is not str or len(value) > MAX_TEXT or value != "arrhenius":
        _fail("unsupported_model")


def run(request):
    if type(request) is not dict:
        _fail("invalid_request")
    if _extra(request, _TOP):
        _fail("unknown_key")
    _model(request.get("model"))
    mechanism = _text(request.get("failure_mechanism"), "failure_mechanism")
    ea = _positive(request.get("activation_energy_ev"), "activation_energy_ev", MAX_EA_EV)
    tuse = _positive(request.get("use_temperature_k"), "use_temperature_k", MAX_TEMP_K)
    levels = request.get("stress_levels")
    if type(levels) is not list or not 1 <= len(levels) <= MAX_LEVELS:
        _fail("invalid_count:stress_levels")
    seen, out, total_hours, total_fail, total_units = set(), [], Fraction(0), 0, 0
    for lv in levels:
        if type(lv) is not dict:
            _fail("invalid_item:stress_levels")
        if _extra(lv, _LEVEL):
            _fail("unknown_key")
        lid = _text(lv.get("id"), "id")
        if lid in seen:
            _fail("duplicate_id:stress_levels")
        seen.add(lid)
        temp = _positive(lv.get("temperature_k"), "temperature_k", MAX_TEMP_K)
        hours = _positive(lv.get("hours"), "hours", MAX_HOURS)
        units = _count(lv.get("units_on_test"), "units_on_test", 1, MAX_UNITS)
        fails = _count(lv.get("failures"), "failures", 0, MAX_UNITS)
        if fails > units:
            _fail("failures_exceed_units")
        x = ea / BOLTZMANN_EV_PER_K * (1 / tuse - 1 / temp)
        if abs(x) > MAX_EXPONENT:
            _fail("invalid_range:exponent")
        dh = hours * units
        total_hours += dh
        total_fail += fails
        total_units += units
        out.append({
            "id": lid,
            "temperature_k": _show(temp),
            "exponent": "-" + _frac(-x) if x < 0 else _frac(x),
            "acceleration_factor": math.exp(float(x)),
            "stress_relation": "above_use" if temp > tuse else ("below_use" if temp < tuse else "at_use"),
            "device_hours": _show(dh),
            "failures": fails,
            "units_on_test": units,
        })
    return {
        "status": "supplied_stress_bookkeeping_only",
        "model": "arrhenius",
        "failure_mechanism": mechanism,
        "mechanism_equivalence_validated": False,
        "levels": out,
        "totals": {"device_hours": _show(total_hours), "failures": total_fail, "units_on_test": total_units},
    }
