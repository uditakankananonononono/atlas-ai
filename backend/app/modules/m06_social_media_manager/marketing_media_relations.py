"""Row 418 media relations: deterministic pitch drafting for caller-provided
outlets/journalists, with code-enforced honesty guards.

Honesty rules enforced in code, not by prompt:

1. Never invent journalists, outlets, or contact details. Every target and
   pitch is keyed to a caller-provided contact; email/outlet/beat appear
   only where the caller supplied them.
2. Tailoring is disclosed and mechanical: keyword overlap between the
   caller-provided story facts and the contact's caller-provided beat text.
   The engine has no external knowledge of any journalist or outlet; with no
   overlap the pitch says so (``no story-beat overlap``) instead of faking
   familiarity.
3. Story content comes only from caller-provided facts. Any missing fact is
   an explicit ``[TO BE PROVIDED: ...]`` slot, listed in the pitch's
   ``requires``.
4. No external effects. Pitches are status ``draft`` and never sent; this is
   a pure function over the input mapping.
"""

from __future__ import annotations

import re
from typing import Any

_WHITESPACE = re.compile(r"\s+")
_TOKEN = re.compile(r"[a-z0-9]+")

# Small disclosed stopword set for the overlap computation. Overlap is a
# tailoring signal, not a relevance score.
_STOPWORDS = frozenset(
    "the a an and or of to in for on with at by from is are was were be been "
    "this that these those it its as we you our your their they he she them "
    "his her".split()
)

_FOLLOW_UP_DEFAULTS = {
    "max_followups": 2,
    "spacing_days": 3,
    "stop_on_decline": True,
    "stop_on_response": True,
    "basis": "engine defaults, not outlet-specific knowledge",
}


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if len(t) >= 4 and t not in _STOPWORDS}


def _normalize_contact(raw: Any) -> dict[str, Any]:
    """Accept a bare string (name or 'name at outlet') or a mapping with
    provided fields. Nothing is inferred beyond what the caller supplied."""
    if isinstance(raw, str):
        name = _WHITESPACE.sub(" ", raw.strip())
        if not name:
            raise ValueError("contact names must be non-empty")
        return {"name": name, "outlet": None, "beat": None, "email": None}
    if isinstance(raw, dict):
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("contact mappings require a non-empty 'name'")
        return {
            "name": _WHITESPACE.sub(" ", name.strip()),
            "outlet": raw.get("outlet"),
            "beat": raw.get("beat"),
            "email": raw.get("email"),
        }
    raise ValueError(f"contacts must be strings or mappings, got {type(raw).__name__}")


def _story_facts(facts: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Caller-provided story fields; missing ones become explicit slots."""
    story = {
        "headline": facts.get("headline"),
        "summary": facts.get("summary"),
        "key_points": [str(p) for p in (facts.get("key_points") or [])],
        "why_now": facts.get("why_now"),
        "assets": [str(a) for a in (facts.get("assets") or [])],
    }
    missing = [k for k in ("headline", "summary", "why_now") if not story[k]]
    if not story["key_points"]:
        missing.append("key_points")
    return story, missing


def _pitch(contact: dict[str, Any], story: dict[str, Any],
           missing: list[str]) -> dict[str, Any]:
    requires = list(missing)
    requires.append("sender name")

    first_name = contact["name"].split(" ", 1)[0]
    outlet = contact.get("outlet") or "[TO BE PROVIDED: outlet]"
    if not contact.get("outlet"):
        requires.append("outlet")

    # Disclosed mechanical tailoring: token overlap between provided story
    # text and the contact's provided beat.
    story_text = " ".join(
        [str(story["headline"] or ""), str(story["summary"] or ""),
         " ".join(story["key_points"]), str(story["why_now"] or "")]
    )
    beat_tokens = _tokens(str(contact.get("beat") or ""))
    overlap = sorted(beat_tokens & _tokens(story_text)) if beat_tokens else []
    if overlap:
        fit_basis = f"keyword overlap with provided beat: {', '.join(overlap)}"
        fit_line = (
            f"I noticed your coverage touches {', '.join(overlap[:3])}, which "
            "is exactly where this story sits."
        )
    elif contact.get("beat"):
        fit_basis = "beat provided but no token overlap with provided story facts"
        fit_line = (
            f"Your stated beat ({contact['beat']}) looked adjacent to this "
            "story; flagging honestly that the overlap is loose."
        )
    else:
        fit_basis = "no story-beat overlap: no beat provided"
        fit_line = "I don't have your beat on file, so I'll keep this short."

    headline = story["headline"] or "[TO BE PROVIDED: story headline]"
    summary = story["summary"] or "[TO BE PROVIDED: story summary]"
    points = story["key_points"] or ["[TO BE PROVIDED: key point]"]
    why_now = story["why_now"] or "[TO BE PROVIDED: why this matters now]"
    assets = story["assets"] or ["[TO BE PROVIDED: interview/data/asset offer]"]
    if not story["assets"]:
        requires.append("interview/data/asset offer")

    body = (
        f"Hi {first_name},\n\n"
        f"Story for {outlet}: {headline}\n\n"
        f"{summary}\n\n"
        "Key points:\n" + "\n".join(f"- {p}" for p in points) + "\n\n"
        f"Why now: {why_now}\n\n"
        f"{fit_line}\n\n"
        f"I can offer: {', '.join(assets)}.\n\n"
        "If it's not a fit, one polite follow-up and I'll stop.\n\n"
        "Best,\n[TO BE PROVIDED: sender name]"
    )

    return {
        "target": contact["name"],
        "email": contact.get("email"),  # only ever caller-provided
        "subject": headline,
        "body": body,
        "status": "draft",
        "sent": False,
        "fit_basis": fit_basis,
        "requires": sorted(set(requires)),
    }


def build_media_relations(inputs: dict[str, Any]) -> dict[str, Any]:
    """Deterministic media-relations plan over caller-provided contacts.

    Identical input produces identical output, including ordering (input
    order, deduplicated case-insensitively on the normalized name).
    """
    facts = inputs.get("facts") or {}
    raw_contacts = inputs.get("contacts") or []

    contacts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_contacts:
        c = _normalize_contact(raw)
        key = c["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        contacts.append(c)

    story, missing = _story_facts(facts)

    targets = [
        {"name": c["name"], "outlet": c.get("outlet"), "beat": c.get("beat")}
        for c in contacts
    ]
    pitches = [_pitch(c, story, missing) for c in contacts]

    return {
        "targets": targets,
        "pitches": pitches,
        "follow_up_plan": dict(_FOLLOW_UP_DEFAULTS),
        "target_count": len(contacts),
        "targets_note": (
            "Targets constrained to supplied contacts; this engine never "
            "invents journalists, outlets, or contact details."
        ),
        "notes": [
            "fit_basis is mechanical keyword overlap between caller-provided "
            "story facts and the contact's caller-provided beat, not "
            "external knowledge of the journalist",
            "pitches are unsent drafts; every missing fact is an explicit "
            "[TO BE PROVIDED: ...] slot listed in 'requires'",
            "email/outlet/beat appear only where the caller provided them",
        ],
    }
