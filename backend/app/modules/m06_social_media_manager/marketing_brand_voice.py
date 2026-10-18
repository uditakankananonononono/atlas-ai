"""Row 405 brand voice: deterministic voice-attribute structure and
tone-by-context flex from caller-provided facts, with honesty guards.

Honesty rules enforced in code, not by prompt:

1. Voice attributes are caller-provided or derived from caller-provided
   brand values via a disclosed template (basis marked either way). The
   engine never invents brand values.
2. Do/don't examples appear only where the caller supplied them on the
   attribute record. Missing examples are explicit TO BE PROVIDED slots with
   example_gap=True - never a fabricated example in the brand's voice.
3. Tone-by-context guidance comes from a disclosed fixed context set and
   disclosed flex templates applied to the actual attributes; it is
   mechanical guidance, not copy.
4. No external effects: pure function over the input mapping.
"""

from __future__ import annotations

import re
from typing import Any

_MAX_ATTRIBUTES = 5
_TARGET_MIN_ATTRIBUTES = 3

# Disclosed fixed context set and flex templates. {attribute} is bound to the
# actual attribute name; the modifier per context is disclosed here.
_CONTEXT_FLEX: dict[str, str] = {
    "launch": "dial up energy and optimism; stay {attribute} but more celebratory",
    "support": "dial up patience and clarity; stay {attribute} but plainer and slower",
    "crisis": "dial down promotion; stay {attribute} but more direct and factual",
    "social": "stay {attribute} but lighter and more conversational",
}

_WHITESPACE = re.compile(r"\s+")


def _norm_str(value: Any, what: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{what} must be strings, got {type(value).__name__}")
    out = _WHITESPACE.sub(" ", value.strip())
    if not out:
        raise ValueError(f"{what} must be non-empty")
    return out


def _normalize_attributes(raw: list[Any]) -> list[dict[str, Any]]:
    attributes: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            attributes.append(
                {"name": _norm_str(item, "voice attributes"), "do": None,
                 "dont": None, "basis": "caller-provided"}
            )
        elif isinstance(item, dict):
            name = item.get("name") or item.get("attribute")
            attributes.append(
                {
                    "name": _norm_str(name, "voice attributes"),
                    "do": item.get("do"),
                    "dont": item.get("dont"),
                    "basis": "caller-provided",
                }
            )
        else:
            raise ValueError(
                f"voice attributes must be strings or mappings, got {type(item).__name__}"
            )
    return attributes


def build_brand_voice(inputs: dict[str, Any]) -> dict[str, Any]:
    """Deterministic brand-voice artifact.

    Identical input produces identical output, including ordering.
    """
    facts = inputs.get("facts") or {}
    notes: list[str] = []

    raw_attributes = facts.get("voice_attributes") or []
    if raw_attributes:
        attributes = _normalize_attributes(raw_attributes)[:_MAX_ATTRIBUTES]
    else:
        raw_values = facts.get("values") or facts.get("brand_values") or []
        seen: set[str] = set()
        attributes = []
        for raw in raw_values:
            name = _norm_str(raw, "brand values")
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            attributes.append(
                {"name": name, "do": None, "dont": None,
                 "basis": "derived from provided brand values"}
            )
            if len(attributes) >= _MAX_ATTRIBUTES:
                break
        if not attributes:
            notes.append(
                "no voice attributes or brand values provided; provide "
                "facts.voice_attributes or facts.values"
            )

    # Caller-provided tone overrides win per context; otherwise disclosed
    # mechanical flex per attribute.
    provided_tone = facts.get("tone_by_context") or {}
    if not isinstance(provided_tone, dict):
        raise ValueError("facts.tone_by_context must be a mapping")
    tone_by_context: dict[str, Any] = {}
    for context, template in _CONTEXT_FLEX.items():
        if context in provided_tone:
            tone_by_context[context] = {
                "guidance": provided_tone[context],
                "basis": "caller-provided",
            }
        else:
            tone_by_context[context] = {
                "guidance": [
                    template.format(attribute=a["name"]) for a in attributes
                ],
                "basis": "derived from disclosed flex template",
            }

    do_examples: list[str] = []
    dont_examples: list[str] = []
    for a in attributes:
        if a["do"]:
            do_examples.append(str(a["do"]))
        if a["dont"]:
            dont_examples.append(str(a["dont"]))
        a["example_gap"] = not (a["do"] and a["dont"])
        if a["example_gap"]:
            a["example_slot"] = (
                "TO BE PROVIDED: one do and one don't example for "
                f"{a['name']!r}"
            )

    coverage = (
        sum(1 for a in attributes if not a["example_gap"]) / len(attributes)
        if attributes
        else None
    )
    if 0 < len(attributes) < _TARGET_MIN_ATTRIBUTES:
        notes.append(
            f"fewer than {_TARGET_MIN_ATTRIBUTES} attributes: only "
            f"{len(attributes)} provided or derivable"
        )
    notes.append(
        "do/don't examples appear only where the caller supplied them; "
        "gaps are marked TO BE PROVIDED"
    )

    return {
        "voice_attributes": attributes,
        "tone_by_context": tone_by_context,
        "do_examples": do_examples,
        "dont_examples": dont_examples,
        "example_coverage": coverage,
        "notes": notes,
    }
