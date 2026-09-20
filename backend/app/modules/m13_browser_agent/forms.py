from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FieldDescriptor:
    selector: str
    label: str = ""
    name: str = ""
    placeholder: str = ""
    input_type: str = "text"
    required: bool = False


_TOKEN = re.compile(r"[a-z0-9]+")
_TYPE_HINTS = {
    "email": {"email", "mail"},
    "tel": {"phone", "mobile", "telephone", "tel"},
    "url": {"url", "website", "site"},
    "password": {"password", "passcode"},
}


def _tokens(value: str) -> set[str]:
    return set(_TOKEN.findall(value.lower()))


def match_fields(fields: list[FieldDescriptor], data: dict[str, str], threshold: float = .38) -> dict[str, str]:
    """Return conservative one-to-one matches; ties are intentionally left unfilled."""
    result: dict[str, str] = {}
    used: set[str] = set()
    for field in fields:
        if not field.selector:
            continue
        haystack = _tokens(" ".join((field.label, field.name, field.placeholder)))
        scored: list[tuple[float, str, str]] = []
        for key, value in data.items():
            if key in used:
                continue
            key_tokens = _tokens(key)
            score = len(haystack & key_tokens) / max(1, len(haystack | key_tokens))
            if _TYPE_HINTS.get(field.input_type, set()) & key_tokens:
                score += .6
            scored.append((score, key, value))
        scored.sort(reverse=True)
        if not scored or scored[0][0] < threshold:
            continue
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            continue
        _, key, value = scored[0]
        result[field.selector] = value
        used.add(key)
    return result
