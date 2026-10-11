"""[Row 107] Nudge Design: exact checklist for a default-based choice nudge that keeps the person's choice intact.

Transparent, ethical-use framing. The caller declares the options, the default, whether opting out is easy, whether the
nudge is disclosed, whether alternatives are visible and how many steps opting out takes. This function runs four named
checks and, if the caller supplies uptake counts, reports the exact difference between them. It measures no behaviour,
predicts no change and gives no advice.
"""
from __future__ import annotations

from math import gcd

ROW = 107
CODE = "NUDGED107"
MIN_OPTIONS, MAX_OPTIONS = 2, 20
MAX_OPTION = 100
MAX_STEPS = 20
OK_STEPS = 2
MAX_COUNT = 10**9
LIMITS = (
    "Supplied declarations only; nothing here measures what people will choose.",
    "A default must not hide costs, obstruct exit or remove alternatives; all four checks must pass.",
    "Not a prediction of behaviour change and not advice; the uptake difference is the caller's supplied figures.",
)
_REQ = ("options", "default", "easy_opt_out", "transparent", "alternatives_visible", "opt_out_steps")
_OPT = ("baseline_uptake", "default_uptake")


class NudgeError(ValueError):
    pass


def _fail(msg):
    raise NudgeError(f"{CODE}: {msg}")


def _pair(v, name):
    if (not isinstance(v, list) or len(v) != 2 or type(v[0]) is not int or type(v[1]) is not int
            or not 1 <= v[1] <= MAX_COUNT or not 0 <= v[0] <= v[1]):
        _fail(f"{name} must be [successes, total] with 0 <= successes <= total <= {MAX_COUNT}")
    return v[0], v[1]


def review(data):
    if not isinstance(data, dict):
        _fail("input must be a mapping")
    for k in data:
        if k not in _REQ and k not in _OPT:
            _fail(f"unknown key {k!r}")
    for k in _REQ:
        if k not in data:
            _fail(f"{k} required")
    for k in ("easy_opt_out", "transparent", "alternatives_visible"):
        if type(data[k]) is not bool:
            _fail(f"{k} must be true or false")
    steps = data["opt_out_steps"]
    if type(steps) is not int or not 0 <= steps <= MAX_STEPS:
        _fail(f"opt_out_steps must be an integer from 0 to {MAX_STEPS}")
    options = data["options"]
    if not isinstance(options, list) or not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        _fail(f"options must be a list of {MIN_OPTIONS} to {MAX_OPTIONS} strings")
    for n, o in enumerate(options):
        if not isinstance(o, str) or not o.strip() or len(o) > MAX_OPTION:
            _fail(f"option {n} must be a non-empty string of at most {MAX_OPTION} characters")
    if len(set(options)) != len(options):
        _fail("duplicate option")
    if data["default"] not in options:
        _fail("default must be one of the options")
    diff = None
    if ("baseline_uptake" in data) != ("default_uptake" in data):
        _fail("baseline_uptake and default_uptake must be supplied together (both or neither)")
    if "baseline_uptake" in data:
        bs, bn = _pair(data["baseline_uptake"], "baseline_uptake")
        ds, dn = _pair(data["default_uptake"], "default_uptake")
        num, den = ds * bn - bs * dn, dn * bn
        g = gcd(abs(num), den)
        diff = f"{num // g}/{den // g}"
    failures = []
    if not data["easy_opt_out"]:
        failures.append("opt_out_not_easy")
    if not data["transparent"]:
        failures.append("not_transparent")
    if not data["alternatives_visible"]:
        failures.append("alternatives_hidden")
    if steps > OK_STEPS:
        failures.append("opt_out_steps_over_2")
    return {
        "row": ROW, "options": list(options), "default": data["default"], "failures": failures,
        "checks_passed": 4 - len(failures), "allowed": not failures, "supplied_uptake_difference": diff,
        "limits": list(LIMITS),
    }
