"""[Row 103] Liking Enhancement: exact check of which rapport claims rest on commonalities both people confirmed.

Transparent, ethical-use framing. The caller lists commonalities (each marked as confirmed by both people or not) and the
similarities it wants to cite. This function reports which claims are supported, which are not, and the exact fractions
involved. An invented similarity is blocked. It checks no fact, predicts no liking and gives no advice.
"""
from __future__ import annotations

from math import gcd

ROW = 103
CODE = "LIKING103"
MAX_ITEMS = 50
MAX_TOPIC = 100
LIMITS = (
    "Supplied declarations only; whether a commonality is real is the caller's statement, not checked here.",
    "Only commonalities confirmed by both people may be cited; an invented similarity is blocked, never suggested.",
    "Not a prediction that anyone will like anyone and not advice; say nothing you cannot stand behind.",
)
_TOP = {"commonalities", "claimed", "disclosed"}
_COM = {"topic", "confirmed_by_both"}


class LikingError(ValueError):
    pass


def _fail(msg):
    raise LikingError(f"{CODE}: {msg}")


def _norm(v, what):
    if not isinstance(v, str) or not v.strip() or len(v) > MAX_TOPIC:
        _fail(f"{what} must be a non-empty string of at most {MAX_TOPIC} characters")
    return v.strip().lower()


def _frac(a, b):
    if b == 0:
        return None
    g = gcd(a, b)
    return f"{a // g}/{b // g}"


def review(data):
    if not isinstance(data, dict):
        _fail("input must be a mapping")
    for k in data:
        if k not in _TOP:
            _fail(f"unknown key {k!r}")
    coms = data.get("commonalities")
    if not isinstance(coms, list) or len(coms) > MAX_ITEMS:
        _fail(f"commonalities must be a list of at most {MAX_ITEMS} records")
    claimed = data.get("claimed")
    if not isinstance(claimed, list) or len(claimed) > MAX_ITEMS:
        _fail(f"claimed must be a list of at most {MAX_ITEMS} strings")
    if "disclosed" not in data:
        _fail("disclosed required")
    disclosed = data["disclosed"]
    if type(disclosed) is not bool:
        _fail("disclosed must be true or false")
    confirmed, unconfirmed, seen = set(), set(), set()
    for n, c in enumerate(coms):
        if not isinstance(c, dict):
            _fail(f"commonality {n} must be a mapping")
        for k in c:
            if k not in _COM:
                _fail(f"commonality {n} has unknown key {k!r}")
        topic = _norm(c.get("topic"), f"commonality {n} topic")
        flag = c.get("confirmed_by_both")
        if type(flag) is not bool:
            _fail(f"commonality {n} confirmed_by_both must be true or false")
        if topic in seen:
            _fail(f"duplicate commonality {topic!r}")
        seen.add(topic)
        (confirmed if flag else unconfirmed).add(topic)
    claims, cseen = [], set()
    for n, v in enumerate(claimed):
        t = _norm(v, f"claim {n}")
        if t in cseen:
            _fail(f"duplicate claim {t!r}")
        cseen.add(t)
        claims.append(t)
    supported = sorted(cseen & confirmed)
    unsupported = sorted(cseen - confirmed)
    usable = bool(claims) and not unsupported
    return {
        "row": ROW, "supported": supported, "unsupported": unsupported, "unconfirmed": sorted(unconfirmed),
        "precision": _frac(len(supported), len(claims)), "coverage": _frac(len(supported), len(confirmed)),
        "usable": usable, "allowed": usable and disclosed, "limits": list(LIMITS),
    }
