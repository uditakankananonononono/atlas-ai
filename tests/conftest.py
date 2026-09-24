"""Shared production-auth fixtures for mounted-surface tests."""
from __future__ import annotations

import base64
import json
import os
import time

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

# Tests never reach a public timestamp authority; tests that need timestamps
# inject a mocked TSA explicitly.
os.environ.setdefault("ATLAS_M10_TIMESTAMP_SCHEME", "off")

from app.auth import context as auth


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


@pytest.fixture
def oidc_auth_headers(monkeypatch: pytest.MonkeyPatch):
    """Issue real RS256 test identities through the production verifier path."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_numbers()
    verifier = auth.OIDCVerifier("https://issuer.test", "atlas")
    verifier._keys = {
        "test-key": {
            "kid": "test-key",
            "kty": "RSA",
            "n": _b64(public.n.to_bytes((public.n.bit_length() + 7) // 8, "big")),
            "e": _b64(public.e.to_bytes((public.e.bit_length() + 7) // 8, "big")),
        }
    }
    verifier._expires = time.monotonic() + 300
    monkeypatch.setattr(auth, "_production_verifier", lambda: verifier)

    def headers(tenant: str = "tenant-a", subject: str = "tester") -> dict[str, str]:
        now = int(time.time())
        header = _b64(json.dumps({"alg": "RS256", "kid": "test-key"}).encode())
        payload = _b64(json.dumps({
            "iss": "https://issuer.test",
            "aud": "atlas",
            "sub": subject,
            "atlas_tenant": tenant,
            "iat": now,
            "exp": now + 300,
        }).encode())
        signature = _b64(key.sign(f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256()))
        return {"Authorization": f"Bearer {header}.{payload}.{signature}"}

    return headers
