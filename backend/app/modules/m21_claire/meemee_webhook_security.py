"""Webhook signature verification and SSRF-safe URL validation, ported from
meemee `webhook_verify.py` and `webhooks.py` (C4 meemee-merge).

Semantics preserved from meemee@50e7605: timestamped HMAC-SHA256 with a replay
tolerance window, and HTTPS-only webhook URLs without embedded credentials that
must resolve to globally routable addresses. Difference from meemee: the
test-only MEEMEE_WEBHOOK_ALLOW_PRIVATE_HOSTS override is NOT ported - Claire
refuses private resolution unconditionally. The resolver is injectable so the
guard stays hermetic under test.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import socket
import time
from collections.abc import Callable
from urllib.parse import urlparse


def compute_signature(secret: str, timestamp: str, body: bytes) -> str:
    return "sha256=" + hmac.new(
        secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()


def verify_signature(
    secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
    tolerance_seconds: int = 300,
    now: int | None = None,
) -> bool:
    """Verify a timestamped webhook signature and reject stale replay attempts."""
    if (tolerance_seconds < 0 or not isinstance(signature, str)
            or not signature.isascii() or not signature.startswith("sha256=")):
        return False
    try:
        observed = int(timestamp)
    except ValueError:
        return False
    current = int(time.time() if now is None else now)
    if abs(current - observed) > tolerance_seconds:
        return False
    return hmac.compare_digest(compute_signature(secret, timestamp, body), signature)


def _default_resolver(host: str, port: int) -> list[str]:
    return [str(info[4][0]) for info in socket.getaddrinfo(host, port)]


def validate_webhook_url(url: str, *, resolver: Callable[[str, int], list[str]] | None = None) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("webhook URL must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        # Reject rather than silently changing the caller's endpoint. HTTP
        # clients would turn userinfo into Basic auth and the URL can enter
        # metadata.
        raise ValueError("webhook URL must not contain credentials")
    resolve = resolver or _default_resolver
    for address in resolve(parsed.hostname, parsed.port or 443):
        if not ipaddress.ip_address(address.split("%", 1)[0]).is_global:
            raise ValueError("webhook URL resolves to a private or reserved address")
    return url
