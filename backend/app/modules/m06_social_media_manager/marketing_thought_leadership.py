"""Row 416 thought leadership: deterministic theme proposal and outline
construction from caller-provided expertise areas, with code-enforced
honesty guards.

Honesty rules enforced in code, not by prompt:

1. Themes come only from caller-provided expertise areas (derived via a
   disclosed angle-template table) or from caller-provided themes verbatim.
   The engine never invents expertise areas.
2. Evidence appears only where the caller supplied it (facts.evidence map,
   keyed by area or theme). Missing evidence is an explicit
   ``TO BE PROVIDED`` slot with ``evidence_gap=True`` - never a fabricated
   statistic or quote.
3. Hooks and arguments are template scaffolds bound to the theme's source
   area, disclosed as such; they are starting structures, not finished
   articles.
4. Channels echo caller-provided channels only. No external effects: pure
   function over the input mapping.
"""

from __future__ import annotations

import re
from typing import Any

_MAX_THEMES = 5
_TARGET_MIN_THEMES = 3

# Disclosed angle-template table, cycled deterministically over the provided
# expertise areas in input order.
_ANGLE_TEMPLATES: tuple[dict[str, str], ...] = (
    {
        "title": "{area}: what practitioners get wrong",
        "hook": "Open with the most common {area} mistake you can disprove with evidence.",
        "argument": "Challenge a widely repeated {area} practice and show the caller-provided counter-evidence.",
    },
    {
        "title": "{area} playbook from real work",
        "hook": "Lead with the single most surprising number from the caller's own {area} work.",
        "argument": "Walk through the exact steps taken, with caller-provided results at each step.",
    },
    {
        "title": "{area}: myths vs measured reality",
        "hook": "List the three most repeated {area} claims, then measure each against provided data.",
        "argument": "Separate {area} folklore from what the caller-provided evidence actually shows.",
    },
    {
        "title": "{area} trends grounded in observed data",
        "hook": "Start from the most recent caller-provided {area} datapoint, not from predictions.",
        "argument": "Describe only trends visible in the caller-provided data; mark projections clearly as projections.",
    },
    {
        "title": "{area} mistakes that cost real money",
        "hook": "Quantify one expensive {area} failure using caller-provided figures.",
        "argument": "Break down the failure mode, the cost, and the fix, each backed by provided evidence.",
    },
)

_WHITESPACE = re.compile(r"\s+")


def _norm_str(value: Any, what: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{what} must be strings, got {type(value).__name__}")
    out = _WHITESPACE.sub(" ", value.strip())
    if not out:
        raise ValueError(f"{what} must be non-empty")
    return out


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _evidence_for(evidence_map: dict[str, Any], keys: list[str]) -> list[str]:
    """Caller-provided evidence for any of the given lookup keys (exact match
    on raw or normalized key), flattened in input order."""
    found: list[str] = []
    for key in keys:
        row = evidence_map.get(key)
        if row is None:
            row = evidence_map.get(_WHITESPACE.sub(" ", key.strip()))
        if isinstance(row, str):
            row = [row]
        if isinstance(row, list):
            found.extend(str(item) for item in row)
    return found


def build_thought_leadership(inputs: dict[str, Any]) -> dict[str, Any]:
    """Deterministic thought-leadership plan.

    Identical input produces identical output, including ordering.
    """
    facts = inputs.get("facts") or {}
    evidence_map = facts.get("evidence") or {}
    if not isinstance(evidence_map, dict):
        raise ValueError("facts.evidence must be a mapping of area/theme to evidence list")

    raw_themes = facts.get("themes") or []
    raw_areas = facts.get("expertise") or facts.get("expertise_areas") or []

    # (theme dict, hook, argument) triples keep the template binding explicit.
    themes: list[tuple[dict[str, Any], str, str]] = []
    if raw_themes:
        for raw in _dedupe([_norm_str(t, "themes") for t in raw_themes])[:_MAX_THEMES]:
            themes.append(
                (
                    {"title": raw, "source_area": None, "basis": "caller-provided"},
                    "TO BE PROVIDED: hook for caller-provided theme",
                    "TO BE PROVIDED: argument for caller-provided theme",
                )
            )
    else:
        areas = _dedupe([_norm_str(a, "expertise areas") for a in raw_areas])
        for i, area in enumerate(areas[:_MAX_THEMES]):
            template = _ANGLE_TEMPLATES[i % len(_ANGLE_TEMPLATES)]
            themes.append(
                (
                    {
                        "title": template["title"].format(area=area),
                        "source_area": area,
                        "basis": "derived from disclosed angle template",
                    },
                    template["hook"].format(area=area),
                    template["argument"].format(area=area),
                )
            )

    outlines: list[dict[str, Any]] = []
    for theme, hook, argument in themes:
        lookup_keys = [k for k in (theme["title"], theme["source_area"]) if k]
        evidence = _evidence_for(evidence_map, lookup_keys)
        gap = not evidence
        outlines.append(
            {
                "theme": theme["title"],
                "hook": hook,
                "argument": argument,
                "evidence_slots": evidence
                or [f"TO BE PROVIDED: evidence for {theme['title']!r}"],
                "evidence_gap": gap,
            }
        )

    channels = _dedupe([_norm_str(c, "channels") for c in (facts.get("channels") or [])])

    notes = [
        "themes are derived from caller-provided expertise areas via a "
        "disclosed angle-template table, or echo caller-provided themes; the "
        "engine never invents expertise areas",
        "evidence appears only where the caller supplied it; gaps are marked "
        "TO BE PROVIDED with evidence_gap=True",
        "hooks and arguments are disclosed template scaffolds, not finished copy",
    ]
    if 0 < len(themes) < _TARGET_MIN_THEMES:
        notes.append(
            f"fewer than {_TARGET_MIN_THEMES} themes proposed: only "
            f"{len(themes)} expertise area(s) provided"
        )
    if not themes:
        notes.append("no expertise areas or themes provided; nothing to outline")

    return {
        "themes": [theme for theme, _, _ in themes],
        "outlines": outlines,
        "channels": channels,
        "theme_count": len(themes),
        "notes": notes,
    }
