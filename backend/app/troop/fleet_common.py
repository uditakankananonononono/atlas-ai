"""Shared checks for the S1 fleet units (tool scanner, replication planner, troop roster).

Stdlib only, no I/O. Refusals are ValueError. A policy refusal is a FleetRefusal whose message is
exactly its FLEET_REFUSED_* code; any other refusal reads "<unit>:<code>". Messages never contain
input text.
"""
from __future__ import annotations

import unicodedata

NOSOURCE = "FLEET_REFUSED_NOSOURCE"
UNLICENSED = "FLEET_REFUSED_UNLICENSED"
SPEND = "FLEET_REFUSED_SPEND"
FORBIDDEN_CATEGORIES = ("Cc", "Zl", "Zp")
TEXT_WHITESPACE = "\n\r\t"
MAX_DEPTH = 8
MAX_NODES = 200000
_LEAF = (str, int, bool, float, type(None))


class FleetRefusal(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def err(unit, code):
    return ValueError("%s:%s" % (unit, code))


def has_forbidden(value, allow_text_whitespace=False):
    for c in value:
        if allow_text_whitespace and c in TEXT_WHITESPACE:
            continue
        if unicodedata.category(c) in FORBIDDEN_CATEGORIES:
            return True
    return False


def scan(value, unit, field, depth=0, budget=None, text_ok=()):
    """Exact-type walk. Refuses subclasses, foreign objects and control characters.

    Strings under a dict key named in text_ok may keep \\n, \\r and \\t; everything else may not.
    """
    if budget is None:
        budget = [0]
    budget[0] += 1
    if budget[0] > MAX_NODES or depth > MAX_DEPTH:
        raise err(unit, "too_deep")
    t = type(value)
    if t is dict:
        for k, v in value.items():
            if type(k) is not str:
                raise err(unit, "bad_type:" + field)
            scan(k, unit, field, depth + 1, budget)
            if type(v) is str and k in text_ok:
                if has_forbidden(v, True):
                    raise err(unit, "control_chars:" + field)
            else:
                scan(v, unit, field, depth + 1, budget, text_ok)
    elif t is list:
        for v in value:
            scan(v, unit, field, depth + 1, budget, text_ok)
    elif t is str:
        if has_forbidden(value):
            raise err(unit, "control_chars:" + field)
    elif t not in _LEAF:
        raise err(unit, "bad_type:" + field)


def exact_keys(d, unit, field, allowed, required):
    if type(d) is not dict:
        raise err(unit, "bad_type:" + field)
    if any(k not in allowed for k in d):
        raise err(unit, "unknown_field:" + field)
    if any(k not in d for k in required):
        raise err(unit, "missing_field:" + field)
