"""[Row 109] Libertarian Paternalism: exact welfare and regret bookkeeping for a default that keeps a costless exit.

The caller declares options, the default, three autonomy declarations, supplied expected utilities and supplied
population shares. The unit computes the expected welfare, the default's regret against the best option (all ties
listed) and whether the declarations allow deployment. It judges nothing about whether the utilities are right, never
decides for anyone, never sends or posts anything, measures no behaviour and gives no advice.
"""
from __future__ import annotations

import re
import unicodedata
from fractions import Fraction

ROW = 109
CODE = "LIBPAT109"
MIN_OPTIONS, MAX_OPTIONS = 2, 20
MAX_OPTION = 100
MAX_UTILITY = 10**12
MAX_NUMBER_TEXT = 20
LIMITS = (
    "Supplied declarations and numbers only; nothing here judges whether the utilities are right.",
    "Guidance must preserve a costless informed exit: easy opt-out, transparency and visible alternatives are all required.",
    "Not a prediction of choices and not advice; welfare and regret are arithmetic on the supplied figures.",
)
_KEYS = ("options", "default", "easy_opt_out", "transparent", "alternatives_visible",
         "expected_utilities", "population_shares")
_UTILITY_RE = re.compile(r"-?[0-9]{1,12}(\.[0-9]{1,6})?", re.ASCII)
_SHARE_RE = re.compile(r"[0-9](\.[0-9]{1,6})?", re.ASCII)
_BAD_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})


class LibertarianError(ValueError):
    pass


def _fail(msg):
    raise LibertarianError(f"{CODE}: {msg}")


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
    n = round(abs(f) * 10**6)
    sign = "-" if f < 0 and n else ""
    return f"{sign}{n // 10**6}.{n % 10**6:06d}"


def _frac(f):
    return f"{f.numerator}/{f.denominator}"


def _utility(v):
    if type(v) is int:
        if abs(v) > MAX_UTILITY:
            _fail("expected_utilities values are out of range")
        return Fraction(v)
    if type(v) is str and len(v) <= MAX_NUMBER_TEXT and _UTILITY_RE.fullmatch(v):
        return Fraction(v)
    _fail("expected_utilities values must be integers or plain decimal strings")


def _share(v):
    if type(v) is int and v in (0, 1):
        return Fraction(v)
    if type(v) is str and len(v) <= MAX_NUMBER_TEXT and _SHARE_RE.fullmatch(v):
        f = Fraction(v)
        if f <= 1:
            return f
    _fail("population_shares values must be plain decimals from 0 to 1")


def _per_option(value, field, options, parse):
    if type(value) is not dict:
        _fail(f"{field} must be a mapping")
    if len(value) != len(options):  # size before any key is read
        _fail(f"{field} must have exactly one entry per option")
    out = {}
    for k in value:
        if type(k) is not str or k not in options:
            _fail(f"{field} keys must be the options")
    for o in options:
        if o not in value:
            _fail(f"{field} keys must be the options")
        out[o] = parse(value[o])
    return out


def review(data):
    if type(data) is not dict:
        _fail("input must be a mapping")
    if len(data) > len(_KEYS):
        _fail("too many keys")
    for k in data:
        if type(k) is not str or k not in _KEYS:
            _fail("unknown key")
    for k in _KEYS:
        if k not in data:
            _fail(f"{k} required")
    for k in ("easy_opt_out", "transparent", "alternatives_visible"):
        if type(data[k]) is not bool:
            _fail(f"{k} must be true or false")
    options = data["options"]
    if type(options) is not list or not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        _fail(f"options must be a list of {MIN_OPTIONS} to {MAX_OPTIONS} strings")
    for o in options:
        _text(o, "options", MAX_OPTION)
    if len(set(options)) != len(options):
        _fail("options must be unique")
    default = data["default"]
    if type(default) is not str or default not in options:
        _fail("default must be one of the options")
    util = _per_option(data["expected_utilities"], "expected_utilities", options, _utility)
    share = _per_option(data["population_shares"], "population_shares", options, _share)
    if sum(share.values()) != 1:
        _fail("population_shares must sum to exactly 1")
    welfare = sum(share[o] * util[o] for o in options)
    best = max(util.values())
    regret = best - util[default]
    autonomy = data["easy_opt_out"] and data["transparent"] and data["alternatives_visible"]
    return {
        "row": ROW, "options": list(options), "default": default,
        "expected_population_welfare": _frac(welfare), "expected_population_welfare_decimal": _decimal6(welfare),
        "default_regret": _frac(regret), "default_regret_decimal": _decimal6(regret),
        "utility_maximizing_options": sorted(o for o in options if util[o] == best),
        "autonomy_preserved": autonomy, "deployment_allowed": autonomy and regret == 0,
        "limits": list(LIMITS),
    }
