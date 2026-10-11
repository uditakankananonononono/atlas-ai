"""S1.6 / c31.integrate - tool-finder integrator.

Source excerpt (verbatim): "find new ai tools and integrate them".

Score supplied alternative tools for a use case from their supplied metadata
(free, rating, privacy tier) and pick the best one. Integration means a
generated offline adapter stub with a deterministic sandbox-test plan - not
a live install. Any paid tool refuses spend. Stdlib only, offline,
deterministic. Payment refusal substitutes for X12.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "FLEET"
TIER_SCORE = {"good": 3, "caution": 2, "toxic": 0}
MAX_TOOLS = 256


def _parse(tool):
    if not isinstance(tool, dict):
        raise ValueError("FLEET_REFUSED_BAD_TYPE:tool")
    name = policy.clean_text(tool.get("name"), PREFIX, "tool_name", 64)
    if bool(tool.get("paid", False)):
        raise ValueError("FLEET_REFUSED_SPEND:" + name)
    rating = tool.get("rating")
    if isinstance(rating, bool) or not isinstance(rating, (int, float)) \
            or not 0.0 <= rating <= 5.0:
        raise ValueError("FLEET_REFUSED_BAD_TYPE:rating")
    tier = tool.get("privacy_tier")
    if tier not in TIER_SCORE:
        raise ValueError("FLEET_REFUSED_BAD_TYPE:privacy_tier")
    return {"name": name, "rating": rating, "privacy_tier": tier,
            "score": 3 + 2 * (rating / 5.0) + TIER_SCORE[tier]}  # free always true here


def select(use_case, tools):
    """Pick the best scored alternative for a supplied use case."""
    use_case = policy.clean_text(use_case, PREFIX, "use_case", 200)
    if isinstance(tools, bool) or not isinstance(tools, (list, tuple)) or not tools:
        raise ValueError("FLEET_REFUSED_BAD_TYPE:tools")
    if len(tools) > MAX_TOOLS:
        raise ValueError("FLEET_REFUSED_OVERSIZE")
    scored = [_parse(t) for t in tools]
    best = max(scored, key=lambda t: t["score"])
    ties = sorted(t["name"] for t in scored if t["score"] == best["score"])
    if len(ties) > 1:
        raise ValueError("FLEET_REFUSED_AMBIGUOUS:" + "|".join(ties))
    adapter = ("# adapter stub for %r (offline; not installed)\n"
               "def run(payload):\n"
               "    raise NotImplementedError(%r)"
               % (best["name"], "adapter for %s not installed" % best["name"]))
    sandbox = ["import adapter", "call adapter.run with a fixed sample payload",
               "expect NotImplementedError until a real implementation is reviewed"]
    return {"use_case": use_case, "picked": best["name"],
            "picked_score": best["score"],
            "ranked": sorted(scored, key=lambda t: (-t["score"], t["name"])),
            "adapter_stub": adapter, "sandbox_test_plan": sandbox,
            "scope": policy.scope(
                ["scored alternatives", "generated adapter stub", "sandbox test plan"],
                ["installing or calling any tool", "spend (refused)"],
                "supplied tool metadata")}


def report(use_case, tools):
    return select(use_case, tools)
