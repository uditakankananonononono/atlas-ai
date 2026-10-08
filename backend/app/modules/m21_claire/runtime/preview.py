"""Bounded, deterministic preview of a refused call's STORED (already redacted) arguments, for the approving principal.
Pure function of the stored snapshot: no clock, no registry, no re-redaction over live state. The digest still binds the full payload;
the preview only lets the approver read what they sign, and says when it is partial."""
from __future__ import annotations
import json
import re
from typing import Any

from .redaction import scrub_text

_MARKER = re.compile(r"\[REDACTED:[0-9a-f]{16}:\d+\]")  # what scrub_text leaves behind in a string
MAX_DEPTH, MAX_ITEMS, MAX_STRING, MAX_BYTES, MAX_KEY = 4, 20, 300, 4096, 100


def _render(value: Any, depth: int, flags: dict[str, bool]) -> Any:
    if isinstance(value, dict):
        if value.get("redacted") is True or value.get("bytes_redacted") is True or value.get("truncated") is True:
            flags["contains_redactions"] = True
        if depth >= MAX_DEPTH:
            flags["truncated"] = True
            return {"omitted": "max_depth", "keys": len(value)}
        entries = sorted(((str(k), v) for k, v in value.items()),
                         key=lambda e: (e[0], json.dumps(e[1], sort_keys=True, default=str)))  # keeps every entry, even str(k) twins
        if len(entries) > MAX_ITEMS:
            flags["truncated"] = True
        out: dict[str, Any] = {}
        for raw, v in entries[:MAX_ITEMS]:
            shown = scrub_text(raw)[:MAX_KEY]  # keys are not redacted upstream
            if shown != raw:
                flags["truncated"] = True
                flags["key_altered"] = True        # a key was cut or scrubbed: the digest binds the real key
            n = 1
            while shown in out:                    # two distinct keys must never merge into one entry
                flags["truncated"] = True
                flags["key_altered"] = True
                n += 1
                shown = f"{shown[:MAX_KEY - 8]}~dup{n}"
            out[shown] = _render(v, depth + 1, flags)
        if len(entries) > MAX_ITEMS:
            marker = "...(more keys)"
            while marker in out:
                marker += "_"
            out[marker] = f"{len(entries) - MAX_ITEMS} more keys"
        return out
    if isinstance(value, (list, tuple)):
        if depth >= MAX_DEPTH:
            flags["truncated"] = True
            return {"omitted": "max_depth", "items": len(value)}
        out = [_render(v, depth + 1, flags) for v in value[:MAX_ITEMS]]
        if len(value) > MAX_ITEMS:
            flags["truncated"] = True
            out.append(f"... {len(value) - MAX_ITEMS} more items")
        return out
    if isinstance(value, str):
        if _MARKER.search(value):
            flags["contains_redactions"] = True      # a secret inside a string was replaced by a marker upstream
        if len(value) > MAX_STRING:
            flags["truncated"] = True
            return value[:MAX_STRING] + f"... [{len(value)} chars total]"
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    flags["truncated"] = True
    return {"omitted": "unsupported_type"}


def render_preview(arguments: Any) -> dict[str, Any] | None:
    """None when no arguments snapshot was stored. Otherwise {value, truncated, contains_redactions, key_altered, untrusted_model_content}."""
    if arguments is None:
        return None
    flags = {"truncated": False, "contains_redactions": False, "key_altered": False}
    value = _render(arguments, 0, flags)
    size = len(json.dumps(value, sort_keys=True, default=str).encode())
    if size > MAX_BYTES:
        value, flags["truncated"] = {"omitted": "preview_over_budget", "bytes": size}, True
    return {"value": value, "truncated": flags["truncated"], "contains_redactions": flags["contains_redactions"],
            "key_altered": flags["key_altered"],
            "untrusted_model_content": True}
