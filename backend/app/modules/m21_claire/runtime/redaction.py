from __future__ import annotations
import hashlib, json, re
from typing import Any

PATTERNS = (
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgh[opsu]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:Bearer\s+)[A-Za-z0-9._~+/-]{16,}=*\b", re.IGNORECASE),
    re.compile(r"(?i)\b(password|passwd|api[_-]?key|access[_-]?token|secret)\s*[:=]\s*([^\s,;]{8,})"),
)
SENSITIVE_KEYS = re.compile(r"token|secret|password|api[_-]?key|authorization|cookie", re.IGNORECASE)


def _marker(value: str) -> str:
    return f"[REDACTED:{hashlib.sha256(value.encode()).hexdigest()[:16]}:{len(value)}]"


def scrub_text(text: str) -> str:
    result = text
    for i, pattern in enumerate(PATTERNS):
        if i == len(PATTERNS) - 1:
            result = pattern.sub(lambda m: f"{m.group(1)}={_marker(m.group(2))}", result)
        else:
            result = pattern.sub(lambda m: _marker(m.group(0)), result)
    return result


def redact(value: Any, key: str = "") -> Any:
    if SENSITIVE_KEYS.search(key):
        enc = json.dumps(value, sort_keys=True, default=str).encode()
        return {"redacted": True, "sha256": hashlib.sha256(enc).hexdigest(), "bytes": len(enc)}
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((redact(v) for v in value), key=repr)
    if isinstance(value, (bytes, bytearray)):
        return {"bytes_redacted": True, "sha256": hashlib.sha256(bytes(value)).hexdigest(), "bytes": len(value)}
    if isinstance(value, str):
        value = scrub_text(value)
        if len(value) > 20_000:
            enc = value.encode()
            return {"truncated": True, "sha256": hashlib.sha256(enc).hexdigest(), "bytes": len(enc), "preview": value[:1000]}
    return value
