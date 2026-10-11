"""Row86 bounded adverse-selection rule flags over declared signals.

Supplied actor/attributes and a declared signal vocabulary are the only
input. The mechanism applies four deterministic rules and emits one flag
per firing rule, each with a stable rule id. No statistical inference, no
ML, no utility tables, no menus: a flag records that a declared pattern
matched a declared rule, nothing more. Everything not supplied is refused
with an "ADVERSE86:" prefixed ValueError.
"""
from __future__ import annotations

import re
from fractions import Fraction

MAX_SIGNALS = 32
MAX_ACTOR_SIGNALS = 32
MAX_SOURCE_REF = 200
MAX_NUM = 10 ** 12
MAX_DEN = 10 ** 6

INTERPRETATION = "declared signals only; no statistical inference, declared rule flags only"

LIMITS = [
    "Flags fire on the supplied actor attributes and declared signal vocabulary only; nothing is observed, inferred or claimed about any real person or population.",
    "A flag is a deterministic rule firing over the caller's declarations, not a determination that any actor is bad, risky, or should be priced, denied or excluded; every such decision stays with a human.",
    "No statistical inference: shares are exact ratios of declared counts compared against declared thresholds; no distributions, samples, confidence or significance are computed or implied.",
    "No utility tables, menus, or incentive/participation constraints: screening-menu analysis is a separate mechanism (row88) and this unit accepts none of its inputs.",
    "The protected-trait guard is a coarse id-token filter, not a proof that a flag set is non-discriminatory; legal and ethics review remain with a human. No counterpart is contacted, persuaded or deceived.",
]

RULE_IDS = ("ADVERSE86-R1", "ADVERSE86-R2", "ADVERSE86-R3", "ADVERSE86-R4")

_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_RAT = re.compile(r"^-?[0-9]{1,20}(?:/[0-9]{1,20})?$")
_PROTECTED = {"gender", "sex", "race", "religion", "age", "disability", "ethnicity", "nationality",
              "pregnancy", "orientation", "caste", "ancestry"}


def _fail(msg: str):
    raise ValueError(f"ADVERSE86: {msg}")


def _keys(d, allowed, label):
    if not isinstance(d, dict):
        _fail(f"{label} must be an object")
    for k in d:
        if k not in allowed:
            _fail(f"unknown key {k!r} in {label}")


def _src(v, label):
    if not isinstance(v, str) or not v.strip():
        _fail(f"{label} source_ref must be a non-blank string")
    if len(v) > MAX_SOURCE_REF:
        _fail(f"{label} source_ref exceeds {MAX_SOURCE_REF} characters")
    return v


def _id(v, label):
    if not isinstance(v, str) or not _ID.match(v):
        _fail(f"invalid id {v!r} in {label}")
    lowered = v.lower()
    for token in _PROTECTED:
        if re.search(rf"(^|[-_]){token}([-_]|$)", lowered) or lowered == token:
            _fail(f"id {v!r} in {label} names a protected trait")
    return v


def _rational(v, label):
    if isinstance(v, bool):
        _fail(f"{label} must be an integer or p/q string, not a boolean")
    if isinstance(v, int):
        if abs(v) > MAX_NUM:
            _fail(f"{label} numerator exceeds {MAX_NUM}")
        return Fraction(v, 1)
    if isinstance(v, str) and _RAT.match(v):
        num, _, den = v.partition("/")
        n, d = int(num), int(den) if den else 1
        if d == 0:
            _fail(f"{label} has a zero denominator")
        if abs(n) > MAX_NUM or d > MAX_DEN:
            _fail(f"{label} exceeds numeric bounds")
        return Fraction(n, d)
    _fail(f"{label} must be an integer or p/q string")


def _share_str(frac: Fraction | None) -> str | None:
    if frac is None:
        return None
    if frac.denominator == 1:
        return str(frac.numerator)
    return f"{frac.numerator}/{frac.denominator}"


def check_adverse_selection(data: dict) -> dict:
    """Grade one supplied actor against declared signals. Returns the flag
    set, exact shares and the limits. Refuses (ValueError, "ADVERSE86:") any
    input outside the declared surface."""
    _keys(data, {"source_ref", "signal_basis", "actor", "signals", "actor_signal_ids", "pool", "thresholds"}, "input")
    _src(data.get("source_ref"), "input")
    if data.get("signal_basis") != "declared_signals":
        _fail("signal_basis must be exactly 'declared_signals'")

    actor = data.get("actor")
    _keys(actor, {"id", "source_ref"}, "actor")
    actor_id = _id(actor.get("id"), "actor")
    _src(actor.get("source_ref"), "actor")

    signals = data.get("signals")
    if not isinstance(signals, list) or not signals:
        _fail("signals must be a non-empty list")
    if len(signals) > MAX_SIGNALS:
        _fail(f"signals exceeds {MAX_SIGNALS} entries")
    classes: dict[str, str] = {}
    for i, s in enumerate(signals):
        _keys(s, {"id", "class", "source_ref"}, f"signals[{i}]")
        sid = _id(s.get("id"), f"signals[{i}]")
        if sid in classes:
            _fail(f"duplicate signal id {sid!r}")
        if s.get("class") not in ("adverse", "favorable"):
            _fail(f"signals[{i}] class must be 'adverse' or 'favorable'")
        if "source_ref" in s:
            _src(s["source_ref"], f"signals[{i}]")
        classes[sid] = s["class"]

    present = data.get("actor_signal_ids")
    if not isinstance(present, list):
        _fail("actor_signal_ids must be a list")
    if len(present) > MAX_ACTOR_SIGNALS:
        _fail(f"actor_signal_ids exceeds {MAX_ACTOR_SIGNALS} entries")
    seen: set[str] = set()
    for sid in present:
        _id(sid, "actor_signal_ids")
        if sid not in classes:
            _fail(f"actor_signal_ids names unknown signal {sid!r}")
        if sid in seen:
            _fail(f"duplicate actor signal id {sid!r}")
        seen.add(sid)

    pool = data.get("pool")
    _keys(pool, {"adverse_share", "source_ref"}, "pool")
    pool_share = _rational(pool.get("adverse_share"), "pool adverse_share")
    if not 0 <= pool_share <= 1:
        _fail("pool adverse_share must be within [0, 1]")
    _src(pool.get("source_ref"), "pool")

    thresholds = data.get("thresholds")
    _keys(thresholds, {"concentration", "pool_gap_margin", "min_declared"}, "thresholds")
    concentration = _rational(thresholds.get("concentration"), "thresholds concentration")
    if not 0 <= concentration <= 1:
        _fail("thresholds concentration must be within [0, 1]")
    margin = _rational(thresholds.get("pool_gap_margin"), "thresholds pool_gap_margin")
    if not 0 <= margin <= 1:
        _fail("thresholds pool_gap_margin must be within [0, 1]")
    min_declared = thresholds.get("min_declared")
    if isinstance(min_declared, bool) or not isinstance(min_declared, int):
        _fail("thresholds min_declared must be an integer")
    if not 0 <= min_declared <= len(signals):
        _fail("thresholds min_declared must be within [0, len(signals)]")

    adverse_present = sum(1 for sid in present if classes[sid] == "adverse")
    favorable_present = len(present) - adverse_present
    share = Fraction(adverse_present, len(present)) if present else None

    flags: list[dict] = []
    if adverse_present > favorable_present:
        flags.append({"rule_id": "ADVERSE86-R1",
                      "detail": f"adverse majority: {adverse_present} adverse > {favorable_present} favorable declared present"})
    if share is not None and adverse_present >= 1 and share >= concentration:
        flags.append({"rule_id": "ADVERSE86-R2",
                      "detail": f"adverse concentration: share {_share_str(share)} >= declared threshold {_share_str(concentration)}"})
    if share is not None and share - pool_share >= margin:
        flags.append({"rule_id": "ADVERSE86-R3",
                      "detail": f"pool adverse gap: share {_share_str(share)} - pool {_share_str(pool_share)} >= declared margin {_share_str(margin)}"})
    if len(present) < min_declared:
        flags.append({"rule_id": "ADVERSE86-R4",
                      "detail": f"insufficient disclosure: {len(present)} declared < required minimum {min_declared}"})

    return {
        "actor_id": actor_id,
        "present_total": len(present),
        "adverse_present": adverse_present,
        "favorable_present": favorable_present,
        "adverse_share": _share_str(share),
        "pool_adverse_share": _share_str(pool_share),
        "flags": flags,
        "flags_total": len(flags),
        "ok": not flags,
        "interpretation": INTERPRETATION,
        "limits": list(LIMITS),
    }
