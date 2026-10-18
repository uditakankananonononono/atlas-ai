"""Row 406 messaging framework: deterministic core-message/pillar structure
from caller-provided facts, with code-enforced honesty guards.

Honesty rules enforced in code, not by prompt:

1. Proof points come only from caller-provided facts (pillar proof_points or
   facts.proof_points). A pillar without provided proof gets an explicit
   TO BE PROVIDED slot and proof_gap=True - never a fabricated claim,
   statistic, or customer quote.
2. The core message and pillars are either caller-provided (marked
   basis='caller-provided') or derived from caller-provided product /
   audience / benefit facts via disclosed templates (marked
   basis='derived from disclosed template'). Missing inputs become explicit
   [TO BE PROVIDED: ...] slots.
3. Audience variants are generated only for caller-provided audience
   segments. The engine never invents segments.
4. No external effects: pure function over the input mapping.
"""

from __future__ import annotations

import re
from typing import Any

_MAX_PILLARS = 4
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


def _core_message(facts: dict[str, Any]) -> tuple[str, str]:
    """Provided core message wins; else derive from provided product /
    audience / benefit facts via a disclosed template with explicit slots."""
    provided = facts.get("core_message")
    if isinstance(provided, str) and provided.strip():
        return _WHITESPACE.sub(" ", provided.strip()), "caller-provided"

    product = facts.get("product")
    audience = facts.get("audience")
    benefit = facts.get("benefit")
    if product or audience or benefit:
        product_s = str(product).strip() if product else "[TO BE PROVIDED: product]"
        audience_s = str(audience).strip() if audience else "[TO BE PROVIDED: audience]"
        benefit_s = str(benefit).strip() if benefit else "[TO BE PROVIDED: primary benefit]"
        return (
            f"{product_s} helps {audience_s} {benefit_s}",
            "derived from disclosed template",
        )
    return "TO BE PROVIDED", "no inputs to derive from"


def _normalize_pillars(raw_pillars: list[Any]) -> tuple[list[dict[str, Any]], bool]:
    """Caller-provided pillars: strings or mappings with name/proof_points.
    Returns (pillars, any_had_provided_proof)."""
    pillars: list[dict[str, Any]] = []
    any_proof = False
    for raw in raw_pillars:
        if isinstance(raw, str):
            pillars.append({"name": _norm_str(raw, "pillars"),
                            "proof_points": [], "basis": "caller-provided"})
        elif isinstance(raw, dict):
            name = raw.get("name") or raw.get("pillar")
            proof = [str(p) for p in (raw.get("proof_points") or [])]
            any_proof = any_proof or bool(proof)
            pillars.append({"name": _norm_str(name, "pillars"),
                            "proof_points": proof, "basis": "caller-provided"})
        else:
            raise ValueError(
                f"pillars must be strings or mappings, got {type(raw).__name__}"
            )
    return pillars, any_proof


def build_messaging_framework(inputs: dict[str, Any]) -> dict[str, Any]:
    """Deterministic messaging framework.

    Identical input produces identical output, including ordering.
    """
    facts = inputs.get("facts") or {}

    core_message, core_basis = _core_message(facts)

    raw_pillars = facts.get("pillars") or []
    notes: list[str] = []
    if raw_pillars:
        pillars, _ = _normalize_pillars(raw_pillars)
        pillars = pillars[:_MAX_PILLARS]
    else:
        # Derive pillars from caller-provided benefits/differentiators.
        raw_benefits = facts.get("benefits") or facts.get("differentiators") or []
        benefits = _dedupe([_norm_str(b, "benefits") for b in raw_benefits])
        pillars = [
            {"name": benefit, "proof_points": [],
             "basis": "derived from provided benefits"}
            for benefit in benefits[:_MAX_PILLARS]
        ]
        if not pillars:
            notes.append(
                "no pillars or benefits provided; provide facts.pillars or "
                "facts.benefits to structure the framework"
            )

    # Attach caller-provided proof; explicit slots where missing.
    flat_provided = [str(p) for p in (facts.get("proof_points") or [])]
    all_proof: list[str] = list(flat_provided)
    for pillar in pillars:
        if pillar["proof_points"]:
            all_proof.extend(pillar["proof_points"])
        elif flat_provided:
            # Unassigned caller-provided proof points are offered, not
            # asserted to belong to this pillar.
            pillar["proof_points"] = []
            pillar["proof_gap"] = True
            pillar["proof_slot"] = (
                "TO BE PROVIDED: proof specific to this pillar "
                "(unassigned caller-provided proof points exist in "
                "proof_points)"
            )
        else:
            pillar["proof_gap"] = True
            pillar["proof_slot"] = "TO BE PROVIDED: proof for this pillar"

    # Audience variants: only for caller-provided segments.
    raw_segments = facts.get("audience_segments") or facts.get("audiences") or []
    segments = _dedupe([_norm_str(s, "audience segments") for s in raw_segments])
    provided_variants = facts.get("audience_variants") or []
    variant_by_segment: dict[str, str] = {}
    for v in provided_variants:
        if isinstance(v, dict) and v.get("segment") and v.get("variant"):
            variant_by_segment[str(v["segment"]).strip().lower()] = str(v["variant"])
    audience_variants = [
        {
            "segment": segment,
            "variant": variant_by_segment.get(
                segment.lower(), f"{core_message} - for {segment}"
            ),
            "basis": "caller-provided"
            if segment.lower() in variant_by_segment
            else "derived from disclosed template",
        }
        for segment in segments
    ]

    coverage = (
        sum(1 for p in pillars if not p.get("proof_gap")) / len(pillars)
        if pillars
        else None
    )
    if 0 < len(pillars) < _TARGET_MIN_PILLARS:
        notes.append(
            f"fewer than {_TARGET_MIN_PILLARS} pillars: only "
            f"{len(pillars)} provided or derivable"
        )
    notes.append(
        "proof points appear only where the caller supplied them; pillars "
        "without provided proof carry proof_gap=True and a TO BE PROVIDED slot"
    )

    return {
        "core_message": core_message,
        "core_message_basis": core_basis,
        "pillars": pillars,
        "proof_points": _dedupe(all_proof),
        "audience_variants": audience_variants,
        "proof_coverage": coverage,
        "notes": notes,
    }
