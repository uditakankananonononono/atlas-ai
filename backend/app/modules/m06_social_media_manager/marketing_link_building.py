"""Row 412 link building: deterministic angle and outreach-draft generation
for caller-provided prospects, with code-enforced honesty guards.

Honesty rules enforced in code, not by prompt:

1. Never invent prospects. Every target, angle, and draft is keyed to a
   caller-provided contact. No names, sites, emails, or outlets are
   generated; with no prospects, every list is empty.
2. No invented metrics. Authority, site, topic, and email fields appear only
   where the caller supplied them on the prospect record; otherwise null.
3. Angles come from a disclosed keyword-to-angle rule table matched against
   the prospect's caller-provided text. An unmatched prospect gets the
   generic angle with basis ``no rule matched`` - never a fabricated fit.
4. Drafts are DRAFT templates assembled from provided facts only. Every fact
   not provided is an explicit ``[TO BE PROVIDED: ...]`` slot, listed in the
   draft's ``requires`` field. Drafts are never sent: this engine is a pure
   function with no external effects.
"""

from __future__ import annotations

import re
from typing import Any

# Disclosed keyword-to-angle rule table, checked in order. The first needle
# found in the prospect's provided text (name/site/topic/notes) wins.
_ANGLE_RULES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "broken-link replacement",
        "point out a broken link on their page and offer a working replacement",
        "a working replacement for a dead link they host (caller supplies the replacement URL)",
        ("broken", "dead link", "404"),
    ),
    (
        "guest post",
        "original article written for their audience",
        "an original article pitched to their editorial guidelines",
        ("blog", "guest", "editorial", "contributor"),
    ),
    (
        "resource inclusion",
        "a relevant resource their page does not list",
        "a caller-supplied asset (guide, tool, or dataset) that fits their resource page",
        ("resource", "links page", "directory", "list"),
    ),
    (
        "expert review contribution",
        "expert input or a review unit for their comparison content",
        "hands-on data or a review unit they can cite",
        ("review", "comparison", "roundup", "vs"),
    ),
    (
        "data citation",
        "a citable dataset or study for their research content",
        "caller-supplied original data they can cite with attribution",
        ("data", "study", "research", "statistics", "report"),
    ),
    (
        "podcast guest pitch",
        "an interview guest with a defined expertise area",
        "a caller-supplied guest bio and topic outline",
        ("podcast", "interview", "episode"),
    ),
)

_DEFAULT_ANGLE = (
    "value-first introduction",
    "introduce the caller's relevant work and ask what would be useful to their audience",
    "TO BE PROVIDED",
)

_WHITESPACE = re.compile(r"\s+")


def _normalize_prospect(raw: Any) -> dict[str, Any]:
    """Accept a bare string (name/site label) or a mapping with provided
    fields. Nothing is inferred beyond what the caller supplied."""
    if isinstance(raw, str):
        name = _WHITESPACE.sub(" ", raw.strip())
        if not name:
            raise ValueError("prospect names must be non-empty")
        return {"name": name, "site": None, "topic": None, "notes": None,
                "authority": None, "email": None}
    if isinstance(raw, dict):
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("prospect mappings require a non-empty 'name'")
        return {
            "name": _WHITESPACE.sub(" ", name.strip()),
            "site": raw.get("site"),
            "topic": raw.get("topic"),
            "notes": raw.get("notes"),
            "authority": raw.get("authority"),
            "email": raw.get("email"),
        }
    raise ValueError(f"prospects must be strings or mappings, got {type(raw).__name__}")


def _match_angle(prospect: dict[str, Any]) -> tuple[str, str, str, str]:
    haystack = " ".join(
        str(prospect[k]) for k in ("name", "site", "topic", "notes") if prospect.get(k)
    ).lower()
    for angle_type, angle, value_exchange, needles in _ANGLE_RULES:
        for needle in needles:
            if needle in haystack:
                return angle_type, angle, value_exchange, f"matched keyword {needle!r}"
    return _DEFAULT_ANGLE[0], _DEFAULT_ANGLE[1], _DEFAULT_ANGLE[2], "no rule matched"


def _draft(prospect: dict[str, Any], angle_type: str, angle: str,
           value_exchange: str) -> dict[str, Any]:
    requires: list[str] = []
    first_name = prospect["name"].split(" ", 1)[0]  # name is normalized non-empty
    if value_exchange == "TO BE PROVIDED":
        requires.append("value exchange")
    asset_slot = "[TO BE PROVIDED: link or asset to share]"
    requires.append("link or asset to share")
    sender = "[TO BE PROVIDED: sender name]"
    requires.append("sender name")

    subject_bits = angle_type
    if prospect.get("site"):
        subject_bits += f" for {prospect['site']}"
    body = (
        f"Hi {first_name},\n\n"
        f"I'm reaching out about {prospect.get('site') or '[TO BE PROVIDED: their site/page]'}: "
        f"{angle}.\n\n"
        f"What I can offer: {value_exchange}.\n"
        f"Asset: {asset_slot}\n\n"
        f"If it's not a fit, no follow-up beyond one polite check-in.\n\n"
        f"Best,\n{sender}"
    )
    if not prospect.get("site"):
        requires.append("their site/page")

    return {
        "target": prospect["name"],
        "email": prospect.get("email"),  # only ever caller-provided
        "subject": subject_bits,
        "body": body,
        "status": "draft",
        "sent": False,
        "requires": sorted(set(requires)),
    }


def build_outreach(inputs: dict[str, Any]) -> dict[str, Any]:
    """Deterministic outreach plan over caller-provided prospects.

    Identical input produces identical output, including ordering (input
    order, deduplicated case-insensitively on the normalized name).
    """
    raw_contacts = inputs.get("contacts") or []

    prospects: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_contacts:
        p = _normalize_prospect(raw)
        key = p["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        prospects.append(p)

    targets = [
        {
            "name": p["name"],
            "site": p.get("site"),
            "topic": p.get("topic"),
            "authority": p.get("authority"),  # provided metrics only, else null
        }
        for p in prospects
    ]

    angles: list[dict[str, Any]] = []
    drafts: list[dict[str, Any]] = []
    for p in prospects:
        angle_type, angle, value_exchange, basis = _match_angle(p)
        angles.append(
            {
                "target": p["name"],
                "angle_type": angle_type,
                "angle": angle,
                "value_exchange": value_exchange,
                "basis": basis,
            }
        )
        drafts.append(_draft(p, angle_type, angle, value_exchange))

    return {
        "targets": targets,
        "angles": angles,
        "outreach_drafts": drafts,
        "prospect_count": len(prospects),
        "targets_note": (
            "Targets constrained to supplied prospects; this engine never "
            "invents contacts, sites, or email addresses."
        ),
        "follow_up_plan": {
            "max_followups": 2,
            "stop_on_decline": True,
            "basis": "engine defaults, not prospect-specific data",
        },
        "notes": [
            "angle_type comes from a disclosed keyword rule table matched on "
            "caller-provided prospect text; unmatched prospects get the "
            "generic angle with basis 'no rule matched'",
            "drafts are unsent templates; every missing fact is an explicit "
            "[TO BE PROVIDED: ...] slot listed in the draft's 'requires'",
            "authority/site/topic/email appear only where the caller "
            "provided them",
        ],
    }
