"""P235 concepts batch 23 (concepts 221-230, units and everyday exact math) -
ten new small deterministic conversion concepts. 221-230 of the doc's 1000
(anchor P235|L184). All results exact Fractions; inputs bounded; ASCII-strict
time parsing; oracles pinned in tests.
"""
from __future__ import annotations

import re
from fractions import Fraction

from .p235_concepts_batch1 import check_int, make_fail

MAX_ABS = 1_000_000
MAX_SPEED = 10**9
MILE_MM = Fraction(1609344, 1000000)

_12H = re.compile(r"^(1[0-2]|[1-9]):([0-5][0-9]) (AM|PM|am|pm)$")
_24H = re.compile(r"^([01][0-9]|2[0-3]):([0-5][0-9])$")


def _check_number(fail, value, name, lo, hi):
    if type(value) is int:
        v = Fraction(value)
    elif type(value) is Fraction:
        v = value
    else:
        fail("bad_type:" + name)
    if v < lo or v > hi:
        fail("bad_value:" + name)
    return v


def celsius_to_fahrenheit_exact(celsius):
    fail = make_fail("celsius_to_fahrenheit_exact")
    c = _check_number(fail, celsius, "celsius", -MAX_ABS, MAX_ABS)
    return c * 9 / 5 + 32


def fahrenheit_to_celsius_exact(fahrenheit):
    fail = make_fail("fahrenheit_to_celsius_exact")
    f = _check_number(fail, fahrenheit, "fahrenheit", -MAX_ABS, MAX_ABS)
    return (f - 32) * 5 / 9


def km_to_miles_exact(km):
    fail = make_fail("km_to_miles_exact")
    k = _check_number(fail, km, "km", 0, MAX_ABS)
    return k / MILE_MM


def miles_to_km_exact(miles):
    fail = make_fail("miles_to_km_exact")
    m = _check_number(fail, miles, "miles", 0, MAX_ABS)
    return m * MILE_MM


def bmi_exact(weight_kg, height_m):
    fail = make_fail("bmi_exact")
    w = _check_number(fail, weight_kg, "weight_kg", 1, 1000)
    h = _check_number(fail, height_m, "height_m", Fraction(1, 100), 3)
    return w / (h * h)


def speed_mps_exact(distance_m, time_s):
    fail = make_fail("speed_mps_exact")
    check_int(fail, distance_m, "distance_m")
    check_int(fail, time_s, "time_s")
    if distance_m < 0 or distance_m > MAX_SPEED:
        fail("bad_value:distance_m")
    if time_s < 1 or time_s > MAX_SPEED:
        fail("bad_value:time_s")
    return Fraction(distance_m, time_s)


def degrees_to_pi_fraction(degrees):
    """Exact radians as a multiple of pi (pi itself is irrational)."""
    fail = make_fail("degrees_to_pi_fraction")
    d = _check_number(fail, degrees, "degrees", -MAX_ABS, MAX_ABS)
    return d / 180


def pi_fraction_to_degrees(numerator, denominator):
    fail = make_fail("pi_fraction_to_degrees")
    check_int(fail, numerator, "numerator")
    check_int(fail, denominator, "denominator")
    if abs(numerator) > MAX_ABS:
        fail("bad_value:numerator")
    if denominator < 1 or denominator > MAX_ABS:
        fail("bad_value:denominator")
    return Fraction(numerator * 180, denominator)


def _digits(fail, s, name):
    if not s.isascii():
        fail("bad_value:" + name)


def time_12h_to_24h(text):
    fail = make_fail("time_12h_to_24h")
    if type(text) is not str:
        fail("bad_type:text")
    _digits(fail, text, "text")
    m = _12H.fullmatch(text)
    if not m:
        fail("bad_format:text")
    hour = int(m.group(1))
    minute = int(m.group(2))
    pm = m.group(3).lower() == "pm"
    if pm:
        hour = hour % 12 + 12
    else:
        hour = hour % 12
    return "%02d:%02d" % (hour, minute)


def time_24h_to_12h(text):
    fail = make_fail("time_24h_to_12h")
    if type(text) is not str:
        fail("bad_type:text")
    _digits(fail, text, "text")
    m = _24H.fullmatch(text)
    if not m:
        fail("bad_format:text")
    hour = int(m.group(1))
    minute = m.group(2)
    suffix = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return "%d:%s %s" % (hour12, minute, suffix)
