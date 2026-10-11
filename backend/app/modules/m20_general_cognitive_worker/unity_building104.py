"""[Row 104] Unity Building: exact check of shared purpose between two parties' declared goals, with conflicts kept visible.

Transparent, ethical-use framing. The caller supplies each party's goals and any goal pairs that conflict. This function
reports the shared goals, the goals held by only one side, the named conflicts and an exact alignment fraction. Shared
identity may not hide a conflict or a person's own choice. It checks no goal, predicts no cohesion and gives no advice.
"""
from __future__ import annotations

from math import gcd

ROW = 104
CODE = "UNITYB104"
MAX_GOALS = 50
MAX_CONFLICTS = 50
MAX_GOAL = 100
LIMITS = (
    "Supplied declarations only; goals are the callers' statements and are not checked here.",
    "Shared identity may not erase a conflict or a person's own choice; named conflicts stay named.",
    "Not a prediction of cohesion and not advice; invented common ground is never suggested.",
)
_KEYS = ("goals_a", "goals_b", "conflicts", "individual_choice_preserved", "disclosed")


class UnityError(ValueError):
    pass


def _fail(msg):
    raise UnityError(f"{CODE}: {msg}")


def _goal(v, what):
    if not isinstance(v, str) or not v.strip() or len(v) > MAX_GOAL:
        _fail(f"{what} must be a non-empty string of at most {MAX_GOAL} characters")
    return v.strip().lower()


def _goals(lst, name):
    if not isinstance(lst, list) or len(lst) > MAX_GOALS:
        _fail(f"{name} must be a list of at most {MAX_GOALS} goals")
    out = []
    for n, g in enumerate(lst):
        t = _goal(g, f"{name} goal {n}")
        if t in out:
            _fail(f"duplicate goal {t!r} in {name}")
        out.append(t)
    return set(out)


def _frac(a, b):
    if b == 0:
        return None
    g = gcd(a, b)
    return f"{a // g}/{b // g}"


def review(data):
    if not isinstance(data, dict):
        _fail("input must be a mapping")
    for k in data:
        if k not in _KEYS:
            _fail(f"unknown key {k!r}")
    for k in _KEYS:
        if k not in data:
            _fail(f"{k} required")
    for k in ("individual_choice_preserved", "disclosed"):
        if type(data[k]) is not bool:
            _fail(f"{k} must be true or false")
    a = _goals(data["goals_a"], "goals_a")
    b = _goals(data["goals_b"], "goals_b")
    raw = data["conflicts"]
    if not isinstance(raw, list) or len(raw) > MAX_CONFLICTS:
        _fail(f"conflicts must be a list of at most {MAX_CONFLICTS} pairs")
    pairs = []
    for n, p in enumerate(raw):
        if not isinstance(p, list) or len(p) != 2:
            _fail(f"conflict {n} must be a pair of goals")
        pa, pb = _goal(p[0], f"conflict {n} goal"), _goal(p[1], f"conflict {n} goal")
        if pa not in a or pb not in b:
            _fail(f"conflict {n} must pair a goal_a with a goal_b")
        if [pa, pb] in pairs:
            _fail(f"duplicate conflict {n}")
        pairs.append([pa, pb])
    shared = sorted(a & b)
    if not shared:
        claim = "none"
    elif pairs:
        claim = "shared_goal_with_named_conflicts"
    else:
        claim = "shared_goal"
    return {
        "row": ROW, "shared": shared, "only_a": sorted(a - b), "only_b": sorted(b - a), "conflicts": sorted(pairs),
        "conflict_count": len(pairs), "alignment": _frac(len(shared), len(a | b)), "identity_claim": claim,
        "allowed": claim != "none" and data["disclosed"] and data["individual_choice_preserved"], "limits": list(LIMITS),
    }
