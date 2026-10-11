"""S1.2 / c31.replicate_plan - capability-replication planner.

Source excerpt (verbatim): "replicate them and integrate into atlas";
"actually integrate it into themselves if its opensource of build it into
themselves if itsnt".

Per-capability build tickets (acceptance tests first) over a SUPPLIED
capability matrix. Open license => integrate; anything else => build
ourselves. Closed-source copying is refused. Stdlib only, offline,
deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "FLEET"
OPEN_LICENSES = ("mit", "apache", "bsd")
MAX_TOOLS = 4096


def plan(tools, copy_closed=False):
    """Emit one build ticket per (tool, capability) from supplied records."""
    # bool needs no separate guard: it is not a list/tuple, so the NOSOURCE
    # refusal covers it (pinned); a redundant isinstance(bool) was eliminated
    if not isinstance(tools, (list, tuple)):
        raise ValueError("FLEET_REFUSED_NOSOURCE")
    if not tools:
        raise ValueError("FLEET_REFUSED_NOSOURCE")
    if len(tools) > MAX_TOOLS:
        raise ValueError("FLEET_REFUSED_OVERSIZE")
    tickets = []
    for t in tools:
        if not isinstance(t, dict):
            raise ValueError("FLEET_REFUSED_BAD_TYPE:tool")
        name = policy.clean_text(t.get("name"), PREFIX, "name", 128)
        license_ = t.get("license", "unknown")
        if license_ not in OPEN_LICENSES + ("gpl", "proprietary", "unknown"):
            raise ValueError("FLEET_REFUSED_BAD_LICENSE:" + str(license_)[:64])
        if copy_closed and license_ not in OPEN_LICENSES:
            raise ValueError("FLEET_REFUSED_UNLICENSED")  # closed-source copying refused
        route = "integrate" if license_ in OPEN_LICENSES else "build_ourselves"
        caps = t.get("capabilities", [])
        if not isinstance(caps, (list, tuple)):
            raise ValueError("FLEET_REFUSED_BAD_TYPE:capabilities")
        for cap in sorted({policy.clean_text(c, PREFIX, "capability", 128) for c in caps}):
            tickets.append({"tool": name, "capability": cap, "route": route,
                            "acceptance_tests_first": True,
                            "ticket": "ticket: %s %s via %s (tests first)" % (route, cap, name)})
    tickets.sort(key=lambda r: (r["capability"], r["tool"]))
    return {"tickets": tickets, "ticket_count": len(tickets),
            "integrate_count": sum(1 for r in tickets if r["route"] == "integrate"),
            "build_ourselves_count": sum(1 for r in tickets if r["route"] == "build_ourselves"),
            "scope": policy.scope(
                ["per-capability build tickets, acceptance tests first",
                 "integrate vs build-ourselves routing by license"],
                ["copying closed-source behavior", "live integration"],
                "supplied capability matrix records")}


def report(tools):
    return plan(tools)
