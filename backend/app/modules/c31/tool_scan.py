"""S1.1 / c31.tool_scan - tool-landscape scanner.

Source excerpt (verbatim): "Has a whole troop of agents inspired but better
than Cellcog, strawberry browser and similar tools maybe search up yc
companies and replicate them and integrate into atlas".

Capability matrix + gap list over SUPPLIED tool records (YC directory exports,
repo pages, product pages saved as text). No live crawling. Stdlib only,
offline, deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "FLEET"
MAX_TOOLS = 4096
LICENSES = ("mit", "apache", "bsd", "gpl", "proprietary", "unknown")
PRICE_TIERS = ("free", "freemium", "paid")


def scan(tools, atlas_modules=None, purchase=False):
    """Build a capability matrix from supplied tool records + gap list."""
    if purchase:
        policy.check("spend", PREFIX)  # paid tools are per-action approval
    if isinstance(tools, bool) or not isinstance(tools, (list, tuple)):
        raise ValueError("FLEET_REFUSED_NOSOURCE")
    if not tools:
        raise ValueError("FLEET_REFUSED_NOSOURCE")
    if len(tools) > MAX_TOOLS:
        raise ValueError("FLEET_REFUSED_OVERSIZE")
    matrix = []
    seen = set()
    for t in tools:
        if not isinstance(t, dict):
            raise ValueError("FLEET_REFUSED_BAD_TYPE:tool")
        name = policy.clean_text(t.get("name"), PREFIX, "name", 128)
        if name in seen:
            raise ValueError("FLEET_REFUSED_DUPLICATE:" + name)
        seen.add(name)
        license_ = t.get("license", "unknown")
        if license_ not in LICENSES:
            raise ValueError("FLEET_REFUSED_BAD_LICENSE:" + str(license_)[:64])
        tier = t.get("price_tier", "unknown")
        if tier not in PRICE_TIERS + ("unknown",):
            raise ValueError("FLEET_REFUSED_BAD_PRICE_TIER:" + str(tier)[:64])
        caps = t.get("capabilities", [])
        if not isinstance(caps, (list, tuple)):
            raise ValueError("FLEET_REFUSED_BAD_TYPE:capabilities")
        caps = sorted({policy.clean_text(c, PREFIX, "capability", 128) for c in caps})
        matrix.append({"name": name, "license": license_, "price_tier": tier,
                       "capabilities": caps})
    matrix.sort(key=lambda r: r["name"])
    covered = set()
    for r in matrix:
        covered.update(r["capabilities"])
    own = set()
    if atlas_modules is not None:
        if not isinstance(atlas_modules, (list, tuple)):
            raise ValueError("FLEET_REFUSED_BAD_TYPE:atlas_modules")
        own = {policy.clean_text(m, PREFIX, "atlas_module", 128) for m in atlas_modules}
    gaps = sorted(covered - own)
    return {"matrix": matrix, "tool_count": len(matrix),
            "capability_count": len(covered), "gap_list": gaps, "gap_count": len(gaps),
            "scope": policy.scope(
                ["capability matrix over supplied records", "computed gap list"],
                ["live crawling", "installing or buying any tool"],
                "supplied tool records")}


def report(tools, atlas_modules=None):
    return scan(tools, atlas_modules)
