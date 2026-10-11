"""S1.1 tool-landscape scanner (offline, stdlib only).

Source (v2 mega-spec, S1.1, relayed by the integrator; I did not see the spec itself):
"Has a whole troop of agents inspired but better than Cellcog, strawberry browser and similar tools maybe
search up yc companies and replicate them and integrate into atlas".
Scope as relayed: takes a supplied list of saved texts, extracts capabilities, license and price tier, and
returns a capability matrix and a gap list against Atlas capabilities.

It never fetches anything: a source_ref is only recorded, never opened, so no crawling and no robots question
arises. Every capability, license and price statement is what the supplied text says (vendor-stated). The
matrix covers only the pages supplied; that coverage is reported in the result. Not a claim about any tool.
"""
from __future__ import annotations

import re

from .fleet_common import (NOSOURCE, SPEND, UNLICENSED, FleetRefusal, err, exact_keys, has_forbidden,
                           scan)

UNIT = "S1.1"
FEATURE = "tool_landscape_scanner"
MAX_RECORDS = 200
MAX_TEXT = 100000
MAX_NAME = 100
MAX_REF = 500
MAX_ATLAS = 200
SOURCE_KINDS = ("yc_export", "github_repo", "product_page")
OPEN_PERMISSIVE, OPEN_COPYLEFT, CLOSED, UNKNOWN = "OPEN_PERMISSIVE", "OPEN_COPYLEFT", "CLOSED", "UNKNOWN"
FREE, FREEMIUM, PAID, PRICE_UNKNOWN = "FREE", "FREEMIUM", "PAID", "UNKNOWN"
CAPABILITY_VOCAB = (
    ("agent_teams", r"\bswarm\b|teams? of (?:\w+ )?agents|multi-?agent|multiplayer agent|troop"),
    ("browser_automation", r"\bbrowser\b"),
    ("email_inbox", r"\binbox\b|\be-?mail\b"),
    ("human_approval", r"\bapproval\b|human[s]? (?:fully )?in the loop"),
    ("memory", r"\bmemory\b"),
    ("parallel_execution", r"\bparallel\b"),
    ("planning", r"\bplan(?:s|ner|ning)?\b"),
    ("scheduled_routines", r"\broutines?\b|\bschedule[ds]?\b|\brecurring\b"),
    ("task_board", r"task board|shared canvas|visible steps?|step list"),
)
_CAPS = tuple((n, re.compile(p, re.I)) for n, p in CAPABILITY_VOCAB)
_PERMISSIVE = re.compile(r"\b(?:MIT|Apache[- ]2\.0|BSD(?:-[23]-Clause)?|ISC)\b")
_COPYLEFT = re.compile(r"\b(?:A?GPL(?:-?v?[23](?:\.0)?)?|LGPL|MPL-2\.0)\b")
_CLOSED = re.compile(r"\bproprietary\b|all rights reserved|closed[- ]source", re.I)
_FREE_PLAN = re.compile(r"free (?:plan|tier)|freemium", re.I)
_FREE_WORD = re.compile(r"\bfree\b", re.I)
_MONEY = re.compile(r"[$€£]\s?\d")
_REQ = ("records", "atlas_capabilities", "spend_usd", "require_open_license")
METHOD_LIMITS = (
    "Capabilities, licenses and prices are what the supplied text says (vendor-stated), found by fixed "
    "keyword patterns. Nothing was fetched, tested or used. The matrix covers only the pages supplied. A "
    "capability absent from a page is not shown absent from the product."
)


def _license(text):
    p, c, x = bool(_PERMISSIVE.search(text)), bool(_COPYLEFT.search(text)), bool(_CLOSED.search(text))
    if x and (p or c):
        return UNKNOWN, True
    if x:
        return CLOSED, False
    if p and not c:
        return OPEN_PERMISSIVE, False
    if c and not p:
        return OPEN_COPYLEFT, False
    if p and c:
        return UNKNOWN, True
    return UNKNOWN, False


def _price(text):
    money = bool(_MONEY.search(text))
    if _FREE_PLAN.search(text) and money:
        return FREEMIUM
    if money:
        return PAID
    if _FREE_WORD.search(text):
        return FREE
    return PRICE_UNKNOWN


def _record(i, r):
    exact_keys(r, UNIT, "records", ("name", "source_kind", "source_ref", "text"), ("name", "source_kind", "text"))
    name, kind, text, ref = r["name"], r["source_kind"], r["text"], r.get("source_ref", "")
    if type(name) is not str or not name.strip() or len(name) > MAX_NAME:
        raise err(UNIT, "bad_name")
    if kind not in SOURCE_KINDS or type(kind) is not str:
        raise err(UNIT, "bad_source_kind")
    if type(ref) is not str or len(ref) > MAX_REF:
        raise err(UNIT, "bad_source_ref")
    if type(text) is not str or len(text) > MAX_TEXT:
        raise err(UNIT, "bad_text")
    if not text.strip():
        raise FleetRefusal(NOSOURCE)
    return name, kind, ref, text


def scan_landscape(request):
    if type(request) is not dict:
        raise err(UNIT, "bad_type:request")
    exact_keys(request, UNIT, "request", _REQ, ("records", "atlas_capabilities"))
    recs, atlas = request["records"], request["atlas_capabilities"]
    if type(recs) is not list:
        raise err(UNIT, "bad_type:records")
    if type(atlas) is not list:
        raise err(UNIT, "bad_type:atlas_capabilities")
    spend = request.get("spend_usd", 0)
    req_open = request.get("require_open_license", False)
    scan({"a": atlas, "s": spend, "o": req_open}, UNIT, "request")
    scan(recs, UNIT, "records", text_ok=("text",))
    if type(spend) is not int or spend < 0:
        raise err(UNIT, "bad_spend")
    if spend != 0:
        raise FleetRefusal(SPEND)
    if type(req_open) is not bool:
        raise err(UNIT, "bad_type:require_open_license")
    if len(recs) > MAX_RECORDS:
        raise err(UNIT, "limit_exceeded:records")
    if len(atlas) > MAX_ATLAS:
        raise err(UNIT, "limit_exceeded:atlas_capabilities")
    if any(type(a) is not str or not a.strip() or len(a) > MAX_NAME for a in atlas):
        raise err(UNIT, "bad_atlas_capability")
    if len(set(atlas)) != len(atlas):
        raise err(UNIT, "duplicate_atlas_capability")
    seen, out = set(), []
    for i, r in enumerate(recs):
        name, kind, ref, text = _record(i, r)
        if name in seen:
            raise err(UNIT, "duplicate_name")
        seen.add(name)
        lic, conflict = _license(text)
        if req_open and lic not in (OPEN_PERMISSIVE, OPEN_COPYLEFT):
            raise FleetRefusal(UNLICENSED)
        caps = sorted(n for n, rx in _CAPS if rx.search(text))
        out.append({"name": name, "source_kind": kind, "source_ref": ref, "capabilities": caps,
                    "license": {"class": lic, "conflicting_statements": conflict},
                    "price_tier": _price(text), "basis": "vendor-stated"})
    out.sort(key=lambda x: x["name"])
    matrix = {}
    for o in out:
        for c in o["capabilities"]:
            matrix.setdefault(c, []).append(o["name"])
    matrix = {c: matrix[c] for c in sorted(matrix)}
    have = set(atlas)
    gaps = [{"capability": c, "providers": matrix[c]} for c in matrix if c not in have]
    return {"feature": FEATURE, "records": out, "matrix": matrix, "gaps": gaps,
            "coverage": {"pages_supplied": len(out), "scope": "supplied pages only"},
            "atlas_capabilities": sorted(atlas),
            "claims": {"fetched_anything": False, "capabilities_verified": False, "product_tested": False,
                       "universal_coverage": False},
            "method_limits": METHOD_LIMITS, "action": "none"}


def render(request):
    r = scan_landscape(request)
    lines = ["tool landscape: %d pages, %d capabilities, %d gaps"
             % (len(r["records"]), len(r["matrix"]), len(r["gaps"]))]
    lines += ["gap %s: %s" % (g["capability"], ",".join(g["providers"])) for g in r["gaps"]]
    return "\n".join(lines)
