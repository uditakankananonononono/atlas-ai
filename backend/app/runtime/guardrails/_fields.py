"""Shared field validators for guardrail gate modules. Pure stdlib.

Every validator raises ValueError("<PREFIX>:<code>") so malformed input is
distinguishable from a guardrail verdict (GuardrailRefusal). Validators never
coerce: a bad type, blank text, control character or naive timestamp fails.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[A-Za-z0-9._/-]{1,64}$")


def make_fail(prefix):
    def fail(message):
        raise ValueError(f"{prefix}:{message}")
    return fail


def text(value, name, *, fail, max_len=256, allow_blank=False):
    if type(value) is not str:
        fail(f"bad_type:{name}")
    if not allow_blank and not value.strip():
        fail(f"empty_field:{name}")
    if len(value) > max_len:
        fail(f"text_too_long:{name}")
    if any(unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") for ch in value):
        fail(f"bad_chars:{name}")
    return value


def ident(value, name, *, fail):
    if type(value) is not str or not ID_RE.fullmatch(value):
        fail(f"bad_id:{name}")
    return value


def instant(value, name, *, fail):
    """Timezone-aware ISO text -> datetime in UTC. Naive input fails."""
    if type(value) is not str:
        fail(f"bad_type:{name}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail(f"bad_instant:{name}")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        fail(f"naive_instant:{name}")
    return parsed.astimezone(timezone.utc)


def iso(moment):
    return moment.isoformat()


def sha256_hex(value, name, *, fail):
    if type(value) is not str or not SHA256_RE.fullmatch(value):
        fail(f"bad_hash:{name}")
    return value


def payload_sha256(payload):
    """Canonical digest of an arbitrary JSON-able payload dict."""
    import hashlib
    import json
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
