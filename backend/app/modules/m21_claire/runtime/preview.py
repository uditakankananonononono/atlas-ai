"""Bounded, deterministic preview of a refused call's STORED (already redacted) arguments, for the approving principal.
Pure function of the stored snapshot: no clock, no registry, no re-redaction over live state. The digest still binds the full payload;
the preview only lets the approver read what they sign, and says when it is partial."""
from __future__ import annotations
import json
from typing import Any

from .redaction import scrub_text

MAX_DEPTH, MAX_ITEMS, MAX_STRING, MAX_BYTES = 4, 20, 300, 4096


def _render(value: Any, depth: int, flags: dict[str, bool]) -> Any:
    if isinstance(value, dict):
        if value.get("redacted") is True or value.get("bytes_redacted") is True or value.get("truncated") is True:
            flags["contains_redactions"] = True
        if depth >= MAX_DEPTH:
            flags["truncated"] = True
            return {"omitted": "max_depth", "keys": len(value)}
        value = {str(k): v for k, v in value.items()}
        keys = sorted(value)
        if len(keys) > MAX_ITEMS:
            flags["truncated"] = True
        out = {scrub_text(k)[:100]: _render(value[k], depth + 1, flags) for k in keys[:MAX_ITEMS]}  # keys are not redacted upstream
        if len(keys) > MAX_ITEMS:
            out["..."] = f"{len(keys) - MAX_ITEMS} more keys"
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
        if len(value) > MAX_STRING:
            flags["truncated"] = True
            return value[:MAX_STRING] + f"... [{len(value)} chars total]"
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    flags["truncated"] = True
    return {"omitted": "unsupported_type"}


def render_preview(arguments: Any) -> dict[str, Any] | None:
    """None when no arguments snapshot was stored. Otherwise {value, truncated, contains_redactions, untrusted_model_content}."""
    if arguments is None:
        return None
    flags = {"truncated": False, "contains_redactions": False}
    value = _render(arguments, 0, flags)
    size = len(json.dumps(value, sort_keys=True, default=str).encode())
    if size > MAX_BYTES:
        value, flags["truncated"] = {"omitted": "preview_over_budget", "bytes": size}, True
    return {"value": value, "truncated": flags["truncated"], "contains_redactions": flags["contains_redactions"],
            "untrusted_model_content": True}
