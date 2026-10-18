"""Row 417 public relations: deterministic narrative, announcement plan, and
DRAFT press release from caller-provided facts, with honesty guards.

Honesty rules enforced in code, not by prompt:

1. The narrative and press release are assembled only from caller-provided
   facts; every missing input is an explicit [TO BE PROVIDED: ...] slot,
   listed in ``requires``. The engine never invents quotes, dates, outlets,
   spokespeople, or contact details.
2. The press release is always status ``draft`` with review_required=True.
   It is never published or sent: this engine has no external effects.
3. Milestone ordering is deterministic (provided date string, then input
   order); milestones without dates keep an explicit slot rather than an
   invented date.
4. Risk notes are caller-provided plus a disclosed engine review checklist,
   marked as such - the checklist is review guidance, not a claim that any
   specific risk exists.
"""

from __future__ import annotations

import re
from typing import Any

_WHITESPACE = re.compile(r"\s+")

# Disclosed review checklist, always appended after caller-provided risks.
_REVIEW_CHECKLIST = [
    "verify every claim in the draft against a provided source before release",
    "confirm quote approval from the quoted person before release",
    "confirm dates and figures with the owning team before release",
]


def _norm_str(value: Any, what: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{what} must be strings, got {type(value).__name__}")
    out = _WHITESPACE.sub(" ", value.strip())
    if not out:
        raise ValueError(f"{what} must be non-empty")
    return out


def build_public_relations(inputs: dict[str, Any]) -> dict[str, Any]:
    """Deterministic public-relations artifact.

    Identical input produces identical output, including ordering.
    """
    facts = inputs.get("facts") or {}

    provided_narrative = facts.get("narrative")
    if isinstance(provided_narrative, str) and provided_narrative.strip():
        narrative = _WHITESPACE.sub(" ", provided_narrative.strip())
        narrative_basis = "caller-provided"
    elif facts.get("headline") or facts.get("why_it_matters"):
        headline = str(facts.get("headline") or "[TO BE PROVIDED: headline]")
        why = str(facts.get("why_it_matters") or "[TO BE PROVIDED: why it matters]")
        narrative = f"{headline} - {why}"
        narrative_basis = "derived from provided headline/why_it_matters"
    else:
        narrative = "TO BE PROVIDED"
        narrative_basis = "no inputs to derive from"

    raw_milestones = facts.get("milestones") or []
    milestones: list[dict[str, Any]] = []
    for i, raw in enumerate(raw_milestones):
        if isinstance(raw, str):
            milestones.append({"name": _norm_str(raw, "milestones"),
                               "date": None, "channel": None, "_i": i})
        elif isinstance(raw, dict):
            milestones.append({
                "name": _norm_str(raw.get("name") or raw.get("milestone"), "milestones"),
                "date": raw.get("date"),
                "channel": raw.get("channel"),
                "_i": i,
            })
        else:
            raise ValueError(
                f"milestones must be strings or mappings, got {type(raw).__name__}"
            )
    milestones.sort(key=lambda m: (str(m["date"] or "9999"), m["_i"]))
    announcement_plan = [
        {
            "name": m["name"],
            "date": m["date"] or "TO BE PROVIDED: date",
            "channel": m["channel"] or "TO BE PROVIDED: channel",
            "status": "planned",
        }
        for m in milestones
    ]

    requires: list[str] = []
    def slot(key: str) -> str:
        value = facts.get(key)
        if value:
            return str(value)
        requires.append(key)
        return f"[TO BE PROVIDED: {key}]"

    headline = slot("headline")
    body_facts = facts.get("body") or facts.get("summary")
    body = str(body_facts) if body_facts else "[TO BE PROVIDED: body]"
    if not body_facts:
        requires.append("body")
    quote = slot("quote")
    quote_source = slot("quote_source")
    contact = slot("contact")
    requires.append("sender/legal review")

    press_release_draft = {
        "status": "draft",
        "review_required": True,
        "published": False,
        "headline": headline,
        "body": (
            f"DRAFT - FOR REVIEW ONLY, NOT FOR RELEASE\n\n"
            f"{headline}\n\n"
            f"{body}\n\n"
            f"\"{quote}\", said {quote_source}.\n\n"
            f"Media contact: {contact}"
        ),
        "requires": sorted(set(requires)),
    }

    risks = [str(r) for r in (facts.get("risks") or [])]
    risk_notes = {
        "caller_provided": risks,
        "review_checklist": list(_REVIEW_CHECKLIST),
        "checklist_basis": "disclosed engine review checklist, not an "
                           "assertion that a specific risk exists",
    }

    readiness_inputs = ("headline", "quote", "body", "contact")
    readiness = (
        sum(1 for k in readiness_inputs if facts.get(k)) / len(readiness_inputs)
    )

    return {
        "narrative": narrative,
        "narrative_basis": narrative_basis,
        "announcement_plan": announcement_plan,
        "press_release_draft": press_release_draft,
        "risk_notes": risk_notes,
        "readiness": readiness,
        "notes": [
            "draft only: review_required=True, never published or sent",
            "quotes, dates, contacts, and figures appear only where the "
            "caller provided them; gaps are explicit TO BE PROVIDED slots",
        ],
    }
