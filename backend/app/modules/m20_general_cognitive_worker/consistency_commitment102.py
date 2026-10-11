"""[Row 102] Consistency Commitment: exact review of a declared ladder of requests ("small yeses to large yeses").

Transparent, ethical-use framing. The caller declares an ordered ladder. This function checks, with integer arithmetic, that
no step jumps more than double the last accepted step, that every step was freely chosen with an exit available, that the
ladder stops after a decline, and that the whole ladder was disclosed first. It measures no person and predicts nothing.
"""
from __future__ import annotations

from math import gcd

ROW = 102
CODE = "CONSIS102"
MAX_STEPS = 50
MAX_ID = 100
MAX_SIZE = 10**6
MAX_RATIO_NUM, MAX_RATIO_DEN = 2, 1
LIMITS = (
    "Supplied declarations only; nothing here measures what a person actually feels or will do.",
    "A declined step ends the ladder. Earlier agreement is never a reason to continue.",
    "Not a prediction of compliance and not advice; disclose the whole ladder to the person before the first step.",
)
_TOP = {"steps", "ladder_disclosed"}
_STEP = {"id", "size", "freely_chosen", "accepted", "exit_available"}


class ConsistencyError(ValueError):
    pass


def _fail(msg):
    raise ConsistencyError(f"{CODE}: {msg}")


def _bool(v, name):
    if type(v) is not bool:
        _fail(f"{name} must be true or false")
    return v


def review(data):
    if not isinstance(data, dict):
        _fail("input must be a mapping")
    for k in data:
        if k not in _TOP:
            _fail(f"unknown key {k!r}")
    steps = data.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        _fail(f"steps must be a list of 1 to {MAX_STEPS} records")
    if "ladder_disclosed" not in data:
        _fail("ladder_disclosed required")
    disclosed = _bool(data["ladder_disclosed"], "ladder_disclosed")
    seen = set()
    out = []
    prior = None
    declined = False
    first = None
    for n, s in enumerate(steps):
        if not isinstance(s, dict):
            _fail(f"step {n} must be a mapping")
        for k in s:
            if k not in _STEP:
                _fail(f"step {n} has unknown key {k!r}")
        sid = s.get("id")
        if not isinstance(sid, str) or not sid.strip() or len(sid) > MAX_ID:
            _fail(f"step {n} id must be a non-empty string of at most {MAX_ID} characters")
        if sid in seen:
            _fail(f"duplicate step id {sid!r}")
        seen.add(sid)
        size = s.get("size")
        if type(size) is not int or not 1 <= size <= MAX_SIZE:
            _fail(f"step {n} size must be an integer from 1 to {MAX_SIZE}")
        freely = _bool(s.get("freely_chosen"), f"step {n} freely_chosen")
        accepted = _bool(s.get("accepted"), f"step {n} accepted")
        exit_ok = _bool(s.get("exit_available"), f"step {n} exit_available")
        v = []
        ratio = None
        if prior is not None:
            g = gcd(size, prior)
            ratio = f"{size // g}/{prior // g}"
            if size * MAX_RATIO_DEN > MAX_RATIO_NUM * prior:
                v.append("escalation_over_2x")
        if declined:
            v.insert(0, "continued_after_decline")
        if not freely:
            v.append("not_freely_chosen")
        if not exit_ok:
            v.append("no_exit_available")
        if v and first is None:
            first = {"index": n, "id": sid, "code": v[0]}
        out.append({"id": sid, "size": size, "ratio_to_prior_accepted": ratio, "violations": v})
        if accepted:
            prior = size
        else:
            declined = True
    if first is None and not disclosed:
        first = {"index": None, "id": None, "code": "ladder_not_disclosed"}
    return {"row": ROW, "steps": out, "allowed": first is None, "first_violation": first, "limits": list(LIMITS)}
