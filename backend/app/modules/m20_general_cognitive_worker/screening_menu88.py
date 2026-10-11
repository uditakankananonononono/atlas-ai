"""Row88 scoped screening-menu checker over a declared utility table.

Pure stdlib, exact rationals. For each caller-supplied menu and intended
type->option mapping it computes participation (IR) and incentive-compatibility
(IC) violations, ties and a deterministic feasible-menu selection. Utilities are
declared table values only: nothing is inferred about real people, no menu is
optimized, no welfare claim is made and no counterpart is contacted.
"""
from __future__ import annotations

import re
from fractions import Fraction
from typing import Any

MAX_TYPES = 16
MAX_OPTIONS = 16
MAX_MENUS = 64
MAX_SOURCE_REF = 200
MAX_NUM = 10 ** 12
MAX_DEN = 10 ** 6
OUTSIDE = "outside"

LIMITS = [
    "Checks only the supplied declared utility table, outside options and menus; the table is not validated against, inferred from or claimed about any real person or population.",
    "IR and IC are evaluated by exact pairwise comparison within each supplied menu; no menu is generated or optimized, and feasible_menu_ids is not a welfare, profit or fairness claim.",
    "Selection is the lexicographically smallest feasible menu id, a deterministic tie-breaker only.",
    "Ties count as acceptable weak IC/IR only when tie_policy explicitly declares it.",
    "The protected-trait guard is a coarse id-token filter, not a proof that a screen is non-discriminatory; legal and ethics review remain with a human. No counterpart is contacted, persuaded or deceived.",
]
INTERPRETATION = "declared table values only; not inferred from or claimed about real people"

_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_RAT = re.compile(r"-?[0-9]{1,20}(?:/[0-9]{1,20})?")
_PROTECTED = {"gender", "sex", "race", "religion", "age", "disability", "ethnicity", "nationality",
              "pregnancy", "orientation", "caste", "ancestry"}


def _fail(msg: str):
    raise ValueError(msg)


def _keys(d, allowed, label):
    for k in d:
        if k not in allowed:
            _fail(f"unknown key {k!r} in {label}")


def _src(v, label):
    pre = f"{label} " if label else ""
    if not isinstance(v, str) or not v.strip():
        _fail(f"{pre}source_ref must be a non-blank string")
    if len(v) > MAX_SOURCE_REF:
        _fail(f"{pre}source_ref exceeds {MAX_SOURCE_REF} characters")
    return v


def _id(v, label):
    if not isinstance(v, str) or not _ID.match(v):
        _fail(f"invalid id {v!r} in {label}")
    if v == OUTSIDE:
        _fail(f"reserved id {OUTSIDE!r} in {label}")
    for tok in re.split(r"[_-]", v.lower()):
        if tok in _PROTECTED:
            _fail(f"id {v!r} contains protected-trait term {tok!r}")
    return v


def _rat(v, label) -> Fraction:
    if type(v) is int:
        f = Fraction(v)
        den = 1
    elif isinstance(v, str) and _RAT.fullmatch(v) and v.isascii():
        n, _, dd = v.partition("/")
        den = int(dd) if dd else 1
        if den == 0:
            _fail(f"invalid rational {v!r} in {label}")
        f = Fraction(int(n), den)
        num = abs(int(n))
        if num > MAX_NUM or den > MAX_DEN:
            _fail(f"rational {v!r} in {label} exceeds bounds")
        return f
    else:
        _fail(f"invalid rational {v!r} in {label}")
    if abs(f) > MAX_NUM:
        _fail(f"rational {v!r} in {label} exceeds bounds")
    return f


def _list(v, label, nonempty, bound=None):
    if not isinstance(v, list) or (nonempty and not v):
        _fail(f"{label} must be a{' non-empty' if nonempty else ''} list")
    if bound is not None and len(v) > bound:
        _fail(f"{label} exceed {bound}")
    return v


def _objs(v, label):
    for x in v:
        if not isinstance(x, dict):
            _fail(f"{label} entries must be objects")


def _s(f: Fraction) -> str:
    return str(f)


def check_screening_menu(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        _fail("request must be an object")
    _keys(data, {"source_ref", "utility_basis", "tie_policy", "select", "types", "options",
                 "outside_options", "utilities", "menus"}, "request")
    top = _src(data.get("source_ref"), "")
    if data.get("utility_basis") != "declared_table":
        _fail("utility_basis must be 'declared_table'")
    tp = data.get("tie_policy")
    if not isinstance(tp, dict):
        _fail("tie_policy must be an object")
    _keys(tp, {"weak_ic", "weak_ir"}, "tie_policy")
    for k in ("weak_ic", "weak_ir"):
        if type(tp.get(k)) is not bool:
            _fail(f"tie_policy.{k} must be boolean")
    weak_ic, weak_ir = tp["weak_ic"], tp["weak_ir"]
    select = data.get("select", False)
    if type(select) is not bool:
        _fail("select must be boolean")

    trace = []
    tlist = _list(data.get("types"), "types", True, MAX_TYPES)
    _objs(tlist, "types")
    types = []
    for t in tlist:
        _keys(t, {"id", "source_ref"}, "types")
        tid = _id(t.get("id"), "types")
        if tid in types:
            _fail(f"duplicate type id {tid!r}")
        types.append(tid)
        trace.append({"kind": "type", "id": tid, "source_ref": _src(t.get("source_ref"), f"type {tid!r}")})
    olist = _list(data.get("options"), "options", True, MAX_OPTIONS)
    _objs(olist, "options")
    options = []
    for o in olist:
        _keys(o, {"id", "source_ref"}, "options")
        oid = _id(o.get("id"), "options")
        if oid in options:
            _fail(f"duplicate option id {oid!r}")
        options.append(oid)
        trace.append({"kind": "option", "id": oid, "source_ref": _src(o.get("source_ref"), f"option {oid!r}")})

    out: dict[str, Fraction] = {}
    xlist = _list(data.get("outside_options"), "outside_options", False)
    _objs(xlist, "outside_options")
    for x in xlist:
        _keys(x, {"type_id", "utility", "source_ref"}, "outside_options")
        tid = x.get("type_id")
        if tid not in types:
            _fail(f"unknown type id {tid!r} in outside_options")
        if tid in out:
            _fail(f"duplicate outside option for type {tid}")
        out[tid] = _rat(x.get("utility"), "outside_options")
        trace.append({"kind": "outside_option", "id": tid, "source_ref": _src(x.get("source_ref"), f"outside option {tid!r}")})
    for tid in sorted(types):
        if tid not in out:
            _fail(f"missing outside option for type {tid}")

    u: dict[tuple, Fraction] = {}
    ulist = _list(data.get("utilities"), "utilities", False)
    _objs(ulist, "utilities")
    for r in ulist:
        _keys(r, {"type_id", "option_id", "utility", "source_ref"}, "utilities")
        tid, oid = r.get("type_id"), r.get("option_id")
        if tid not in types:
            _fail(f"unknown type id {tid!r} in utilities")
        if oid not in options:
            _fail(f"unknown option id {oid!r} in utilities")
        if (tid, oid) in u:
            _fail(f"duplicate utility for {tid}/{oid}")
        u[(tid, oid)] = _rat(r.get("utility"), "utilities")
        trace.append({"kind": "utility", "id": f"{tid}/{oid}",
                      "source_ref": _src(r["source_ref"], f"utility {tid}/{oid}") if "source_ref" in r else top})
    for tid in sorted(types):
        for oid in sorted(options):
            if (tid, oid) not in u:
                _fail(f"missing utility for {tid}/{oid}")

    mlist = _list(data.get("menus"), "menus", True, MAX_MENUS)
    _objs(mlist, "menus")
    menus = {}
    for m in mlist:
        mid = m.get("id")
        _keys(m, {"id", "option_ids", "mapping", "source_ref"}, f"menu {mid!r}")
        mid = _id(mid, "menus")
        if mid in menus:
            _fail(f"duplicate menu id {mid!r}")
        mo = m.get("option_ids")
        if not isinstance(mo, list) or not mo:
            _fail(f"menu {mid!r} option_ids must be a non-empty list")
        for o in mo:
            if mo.count(o) > 1:
                _fail(f"menu {mid!r} has duplicate option {o!r}")
        for o in mo:
            if o not in options:
                _fail(f"menu {mid!r} has unknown option {o!r}")
        mp = m.get("mapping")
        if not isinstance(mp, list):
            _fail(f"menu {mid!r} mapping must be a list")
        mapping = {}
        for e in mp:
            if not isinstance(e, dict):
                _fail(f"menu {mid!r} mapping entries must be objects")
            _keys(e, {"type_id", "option_id"}, f"menu {mid!r} mapping")
            tid, oid = e.get("type_id"), e.get("option_id")
            if tid not in types:
                _fail(f"menu {mid!r} maps unknown type {tid!r}")
            if tid in mapping:
                _fail(f"menu {mid!r} has duplicate mapping for type {tid}")
            if oid != OUTSIDE and oid not in mo:
                _fail(f"menu {mid!r} maps type {tid} to {oid!r}, which is not in the menu")
            mapping[tid] = oid
        for tid in sorted(types):
            if tid not in mapping:
                _fail(f"menu {mid!r} missing mapping for type {tid}")
        menus[mid] = (sorted(mo), mapping)
        trace.append({"kind": "menu", "id": mid, "source_ref": _src(m.get("source_ref"), f"menu {mid!r}")})

    reports = []
    for mid in sorted(menus):
        mo, mapping = menus[mid]
        ir_v, ic_v, ties = [], [], []
        for tid in sorted(types):
            c = mapping[tid]
            uc = out[tid] if c == OUTSIDE else u[(tid, c)]
            if c != OUTSIDE:
                if uc == out[tid]:
                    ties.append({"kind": "ir", "type_id": tid, "chosen": c, "alternative": OUTSIDE,
                                 "utility": _s(uc), "accepted_as_weak": weak_ir})
                if uc < out[tid] or (uc == out[tid] and not weak_ir):
                    ir_v.append({"type_id": tid, "chosen": c, "chosen_utility": _s(uc),
                                 "outside_utility": _s(out[tid]), "shortfall": _s(out[tid] - uc)})
            for a in mo:
                if a == c:
                    continue
                ua = u[(tid, a)]
                if uc == ua:
                    ties.append({"kind": "ic", "type_id": tid, "chosen": c, "alternative": a,
                                 "utility": _s(uc), "accepted_as_weak": weak_ic})
                if uc < ua or (uc == ua and not weak_ic):
                    ic_v.append({"type_id": tid, "chosen": c, "deviation": a, "chosen_utility": _s(uc),
                                 "deviation_utility": _s(ua), "gain": _s(ua - uc)})
        ties.sort(key=lambda t: (t["type_id"], t["kind"], t["alternative"]))
        reports.append({"id": mid, "option_ids": mo,
                        "mapping": [{"type_id": t, "option_id": mapping[t]} for t in sorted(types)],
                        "feasible": not ir_v and not ic_v,
                        "ir_violations": ir_v, "ic_violations": ic_v, "ties": ties})
    feasible = [r["id"] for r in reports if r["feasible"]]
    trace.sort(key=lambda t: (t["kind"], t["id"]))
    return {
        "menus": reports,
        "feasible_menu_ids": feasible,
        "selected_menu_id": feasible[0] if (select and feasible) else None,
        "no_feasible_menu": not feasible,
        "tie_policy": {"weak_ic": weak_ic, "weak_ir": weak_ir},
        "source_trace": trace,
        "utility_interpretation": INTERPRETATION,
        "welfare_claim": False,
        "counterpart_contacted": False,
        "limits": list(LIMITS),
    }
