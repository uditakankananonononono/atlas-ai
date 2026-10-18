"""Row 420 social media strategy: deterministic per-platform roles, mix,
cadence, and KPIs from caller-provided facts, with honesty guards.

Honesty rules enforced in code, not by prompt:

1. Platforms come only from the caller. Roles are caller-provided or bound
   from a disclosed platform-archetype table keyed on the provided platform
   name (basis marked 'disclosed archetype ..., not account data'). Unknown
   platforms get an explicit TO BE PROVIDED role slot - never an invented
   read of an unknown platform.
2. Observed KPI numbers are computed only from caller-provided figures;
   absent figures are null. The measurable-KPI list per platform is a
   disclosed set of standard platform-analytics metrics, not pulled data.
3. Content mix and cadence are caller-provided or disclosed engine defaults,
   marked as such - they are not audience research.
4. No external effects: pure function over the input mapping.
"""

from __future__ import annotations

import re
from typing import Any

# Disclosed platform-archetype table: well-known platform name -> typical
# role and standard official-analytics metrics. This is a fixed lookup, not
# account data.
_ARCHETYPES: dict[str, dict[str, Any]] = {
    "linkedin": {
        "role": "B2B authority, hiring, and partnership reach",
        "metrics": ["impressions", "engagement_rate", "follower_growth",
                    "link_clicks"],
    },
    "instagram": {
        "role": "visual brand storytelling and community",
        "metrics": ["reach", "saves", "shares", "follower_growth"],
    },
    "x": {
        "role": "real-time commentary and support",
        "metrics": ["impressions", "replies", "reposts", "link_clicks"],
    },
    "twitter": {
        "role": "real-time commentary and support",
        "metrics": ["impressions", "replies", "reposts", "link_clicks"],
    },
    "tiktok": {
        "role": "short-form discovery and reach",
        "metrics": ["views", "completion_rate", "shares", "follower_growth"],
    },
    "youtube": {
        "role": "long-form education and search presence",
        "metrics": ["views", "watch_time", "subscribers", "ctr"],
    },
    "facebook": {
        "role": "community and local reach",
        "metrics": ["reach", "engagement_rate", "group_activity",
                    "link_clicks"],
    },
}

_DEFAULT_MIX = {"educate": 0.4, "engage": 0.3, "promote": 0.2, "entertain": 0.1}
_DEFAULT_CADENCE = {"posts_per_week": 3}

_WHITESPACE = re.compile(r"\s+")


def _norm_str(value: Any, what: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{what} must be strings, got {type(value).__name__}")
    out = _WHITESPACE.sub(" ", value.strip())
    if not out:
        raise ValueError(f"{what} must be non-empty")
    return out


def _num(facts: dict[str, Any], key: str) -> float | None:
    try:
        return float(facts[key])
    except (KeyError, TypeError, ValueError):
        return None


def _ratio(a: float | None, b: float | None) -> float | None:
    if a is None or not b:
        return None
    return a / b


def _normalize_platform(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        return {"name": _norm_str(raw, "platforms"), "role": None}
    if isinstance(raw, dict):
        name = raw.get("name") or raw.get("platform")
        role = raw.get("role")
        return {"name": _norm_str(name, "platforms"),
                "role": str(role).strip() if role else None}
    raise ValueError(f"platforms must be strings or mappings, got {type(raw).__name__}")


def build_social_strategy(inputs: dict[str, Any]) -> dict[str, Any]:
    """Deterministic social-media strategy.

    Identical input produces identical output, including ordering.
    """
    facts = inputs.get("facts") or {}
    notes: list[str] = []

    raw_platforms = facts.get("channels") or facts.get("platforms") or []
    platforms: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_platforms:
        p = _normalize_platform(raw)
        if p["name"].lower() in seen:
            continue
        seen.add(p["name"].lower())
        platforms.append(p)

    platform_roles: list[dict[str, Any]] = []
    for p in platforms:
        if p["role"]:
            platform_roles.append({"platform": p["name"], "role": p["role"],
                                   "basis": "caller-provided"})
            continue
        archetype = _ARCHETYPES.get(p["name"].lower())
        if archetype:
            platform_roles.append({
                "platform": p["name"],
                "role": archetype["role"],
                "basis": "disclosed archetype for platform name, not account data",
            })
        else:
            platform_roles.append({
                "platform": p["name"],
                "role": f"TO BE PROVIDED: role for platform {p['name']!r}",
                "basis": "no archetype: platform not in the disclosed table",
                "role_gap": True,
            })

    if facts.get("content_mix"):
        content_mix = {"mix": facts["content_mix"], "basis": "caller-provided"}
    elif platforms:
        content_mix = {"mix": dict(_DEFAULT_MIX),
                       "basis": "engine default, not audience data"}
    else:
        content_mix = {"mix": None, "basis": "none: no platforms provided"}

    if facts.get("cadence"):
        cadence = {"plan": facts["cadence"], "basis": "caller-provided"}
    elif platforms:
        cadence = {"plan": dict(_DEFAULT_CADENCE),
                   "basis": "engine default, not audience data"}
    else:
        cadence = {"plan": None, "basis": "none: no platforms provided"}

    measurable = {
        p["name"]: list(_ARCHETYPES[p["name"].lower()]["metrics"])
        if p["name"].lower() in _ARCHETYPES else []
        for p in platforms
    }
    kpis = {
        "measurable_per_platform": measurable,
        "observed": {
            "engagement_rate": _ratio(_num(facts, "engagements"), _num(facts, "impressions")),
            "conversion_rate": _ratio(_num(facts, "conversions"), _num(facts, "clicks")),
        },
        "basis": "measurable lists are disclosed standard platform-analytics "
                 "metrics; observed values are computed only from provided "
                 "figures and are null when absent",
    }

    if not platforms:
        notes.append("no platforms provided; provide facts.channels")

    return {
        "platform_roles": platform_roles,
        "content_mix": content_mix,
        "cadence": cadence,
        "kpis": kpis,
        "notes": notes,
    }
