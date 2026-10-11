"""S1.2 capability-replication planner (offline, stdlib only, proposals only).

Input is the supplied pages themselves (records and atlas_capabilities), not a scan result: the matrix, license and
price are re-derived here by calling the S1.1 scanner, so a forged or edited scan cannot be fed in.

Source (v2 mega-spec, S1.2, relayed by the integrator; I did not see the spec itself): same line as S1.1 plus
"replicate them and integrate into atlas", and "actually integrate it into themselves if its opensource of
build it into themselves if itsnt".
Scope as relayed: from the S1.1 matrix, one build ticket per gap, acceptance tests first, each labelled
"integrate (open source, license ok)" or "build ourselves". Refuses closed-source copying
(FLEET_REFUSED_UNLICENSED) and any paid tier (FLEET_REFUSED_SPEND).

It plans only. It builds, copies, installs and buys nothing, and every ticket stays PROPOSED.
"""
from __future__ import annotations

from .fleet_common import SPEND, UNLICENSED, FleetRefusal, err, exact_keys, scan
from .landscape import OPEN_COPYLEFT, OPEN_PERMISSIVE, PAID, scan_landscape

UNIT = "S1.2"
FEATURE = "capability_replication_planner"
INTEGRATE = "integrate (open source, license ok)"
BUILD = "build ourselves"
MAX_ADOPT = 100
_REQ = ("records", "atlas_capabilities", "adopt", "spend_usd")
_STEPS = ("write acceptance tests (red)", "implement or integrate", "run acceptance tests (green)",
          "audit review")
METHOD_LIMITS = (
    "Tickets are proposals from vendor-stated license and price text, re-derived from the supplied pages by "
    "the S1.1 scanner on every call. A license reading is not legal advice and may be wrong. Nothing is "
    "built, copied, installed or bought."
)


def _tests(cap):
    return [
        "given a supplied fixture input, the %s capability returns the documented output" % cap,
        "given empty or malformed input, the %s capability refuses with a stable code" % cap,
        "the %s capability is deterministic: the same input twice gives equal output" % cap,
    ]


def plan_replication(request):
    if type(request) is not dict:
        raise err(UNIT, "bad_type:request")
    exact_keys(request, UNIT, "request", _REQ, ("records", "atlas_capabilities"))
    scan(request, UNIT, "request", text_ok=("text",))
    spend = request.get("spend_usd", 0)
    adopt = request.get("adopt", [])
    if type(spend) is not int or spend < 0:
        raise err(UNIT, "bad_spend")
    if spend != 0:
        raise FleetRefusal(SPEND)
    if type(adopt) is not list:
        raise err(UNIT, "bad_type:adopt")
    if len(adopt) > MAX_ADOPT:
        raise err(UNIT, "limit_exceeded:adopt")
    if any(type(a) is not str for a in adopt):
        raise err(UNIT, "bad_type:adopt")
    if len(set(adopt)) != len(adopt):
        raise err(UNIT, "duplicate_adopt")
    sc = scan_landscape({"records": request["records"], "atlas_capabilities": request["atlas_capabilities"]})
    by = {r["name"]: r for r in sc["records"]}
    gaps = sc["gaps"]
    for name in sorted(adopt):
        if name not in by:
            raise err(UNIT, "unknown_adopt_name")
    for name in sorted(adopt):
        if by[name]["license"]["class"] != OPEN_PERMISSIVE:
            raise FleetRefusal(UNLICENSED)
    for name in sorted(adopt):
        if by[name]["price_tier"] == PAID:
            raise FleetRefusal(SPEND)
    tickets = []
    for g in gaps:
        cap, provs = g["capability"], g["providers"]
        ok = [p for p in provs if by[p]["license"]["class"] == OPEN_PERMISSIVE and by[p]["price_tier"] != PAID]
        if ok:
            pick = next((p for p in ok if p in adopt), ok[0])
            decision, source, reason = INTEGRATE, pick, "license_ok"
        else:
            classes = [by[p]["license"]["class"] for p in provs]
            decision, source = BUILD, None
            if OPEN_COPYLEFT in classes:
                reason = "copyleft_needs_human_review"
            elif OPEN_PERMISSIVE in classes:
                reason = "paid_tier_not_adopted"
            else:
                reason = "no_open_provider_license_ok"
        tickets.append({"ticket_id": "REP-" + cap, "capability": cap, "decision": decision,
                        "source_tool": source, "reason": reason, "acceptance_tests": _tests(cap),
                        "steps": list(_STEPS), "estimated_spend_usd": 0, "status": "PROPOSED",
                        "basis": "vendor-stated"})
    return {"feature": FEATURE, "tickets": tickets, "adopted": sorted(adopt),
            "counts": {"tickets": len(tickets),
                       "integrate": sum(1 for t in tickets if t["decision"] == INTEGRATE),
                       "build": sum(1 for t in tickets if t["decision"] == BUILD)},
            "claims": {"built_anything": False, "copied_code": False, "spent_money": False,
                       "license_verified": False},
            "method_limits": METHOD_LIMITS, "action": "none"}
