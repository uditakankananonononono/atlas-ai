"""Row 408 content strategy: deterministic pillar/format/cadence/measurement
structure from caller-provided facts, with honesty guards.

Honesty rules enforced in code, not by prompt:

1. Pillars are caller-provided or derived from caller-provided topics via a
   disclosed template (basis marked). The engine never invents topics.
2. Formats per pillar come only from caller-provided content pieces matched
   by exact topic. A pillar with no provided format gets format_gap=True and
   a TO BE PROVIDED slot - never an invented format.
3. Measurement lists only metrics the caller's provided analytics or content
   pieces actually carry; unavailable metrics are named as gaps. Counts and
   rates are computed from provided rows only.
4. Cadence is caller-provided or a disclosed engine default, marked as such
   - it is not audience research.
5. No external effects: pure function over the input mapping.
"""

from __future__ import annotations

import re
from typing import Any

_MAX_PILLARS = 5
_TARGET_MIN_PILLARS = 3

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


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError, RuntimeError):
        return None


def build_content_strategy(inputs: dict[str, Any]) -> dict[str, Any]:
    """Deterministic content strategy.

    Identical input produces identical output, including ordering.
    """
    facts = inputs.get("facts") or {}
    notes: list[str] = []

    raw_pillars = facts.get("pillars") or facts.get("topics") or []
    provided_pillars = bool(facts.get("pillars"))
    pillars = _dedupe([_norm_str(p, "pillars") for p in raw_pillars])[:_MAX_PILLARS]
    pillar_basis = "caller-provided" if provided_pillars else (
        "derived from provided topics" if pillars else None
    )
    if not pillars:
        notes.append("no pillars or topics provided; nothing to structure")
    elif len(pillars) < _TARGET_MIN_PILLARS:
        notes.append(
            f"fewer than {_TARGET_MIN_PILLARS} pillars: only "
            f"{len(pillars)} provided"
        )

    # Provided content pieces drive per-pillar formats and measurement.
    raw_pieces = facts.get("content") or facts.get("pieces") or []
    pieces: list[dict[str, Any]] = []
    for raw in raw_pieces:
        if not isinstance(raw, dict):
            raise ValueError(
                f"content pieces must be mappings, got {type(raw).__name__}"
            )
        pieces.append(raw)

    def _piece_pillar(piece: dict[str, Any]) -> str | None:
        topic = piece.get("pillar") or piece.get("topic")
        return str(topic).strip() if topic else None

    pillar_entries: list[dict[str, Any]] = []
    for pillar in pillars:
        matched = [
            p for p in pieces
            if _piece_pillar(p) and _piece_pillar(p).lower() == pillar.lower()
        ]
        formats = _dedupe(
            [str(p["format"]) for p in matched if p.get("format")]
        )
        entry: dict[str, Any] = {
            "pillar": pillar,
            "formats": formats,
            "piece_count": len(matched),
            "basis": pillar_basis,
        }
        if not formats:
            entry["format_gap"] = True
            entry["format_slot"] = (
                f"TO BE PROVIDED: formats for pillar {pillar!r}"
            )
        pillar_entries.append(entry)

    all_formats = _dedupe(
        [str(p["format"]) for p in pieces if p.get("format")]
    )

    # Measurement: only metrics the provided data actually carries.
    analytics = facts.get("analytics") or {}
    if analytics and not isinstance(analytics, dict):
        raise ValueError("facts.analytics must be a mapping")
    analytics_metrics = sorted(analytics.keys())

    impressions = sum(_num(p.get("impressions")) or 0.0 for p in pieces)
    engagements = sum(_num(p.get("engagements")) or 0.0 for p in pieces)
    has_impressions = any(p.get("impressions") is not None for p in pieces)
    has_engagements = any(p.get("engagements") is not None for p in pieces)
    piece_metrics = [m for m, present in
                     (("impressions", has_impressions), ("engagements", has_engagements))
                     if present]
    available = _dedupe(analytics_metrics + piece_metrics)
    engagement_rate = (engagements / impressions) if impressions else None

    measurement = {
        "available_metrics": available,
        "observed": {
            "impressions": impressions if has_impressions else None,
            "engagements": engagements if has_engagements else None,
            "engagement_rate": engagement_rate,
        },
        "measurement_gaps": (
            [] if available
            else ["no analytics or per-piece metrics provided; success "
                  "criteria cannot be measured yet"]
        ),
        "basis": "only metrics present in the provided analytics or content "
                 "pieces are listed",
    }

    cadence = facts.get("cadence")
    if cadence:
        cadence_out = {"plan": cadence, "basis": "caller-provided"}
    elif pillars:
        cadence_out = {
            "plan": {"per_week": 3, "rotation": "one piece per pillar in "
                     "listed order, repeating"},
            "basis": "engine default, not audience data",
        }
    else:
        cadence_out = {"plan": None, "basis": "none: no pillars to schedule"}

    return {
        "pillars": pillar_entries,
        "formats": all_formats,
        "cadence": cadence_out,
        "measurement": measurement,
        "notes": notes + [
            "formats per pillar come only from caller-provided content "
            "pieces matched by exact topic; gaps are marked TO BE PROVIDED",
        ],
    }
