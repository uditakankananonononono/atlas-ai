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

    def headers(tenant: str = "tenant-a", subject: str = "tester", roles: list[str] | None = None) -> dict[str, str]:
        now = int(time.time())
        header = _b64(json.dumps({"alg": "RS256", "kid": "test-key"}).encode())
        payload = _b64(json.dumps({
            "iss": "https://issuer.test",
            "aud": "atlas",
            "sub": subject,
            "roles": roles or [],
            "atlas_tenant": tenant,
            "iat": now,
            "exp": now + 300,
        }).encode())
        signature = _b64(key.sign(f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256()))
        return {"Authorization": f"Bearer {header}.{payload}.{signature}"}

    return headers


@pytest.fixture(autouse=True)
def explicit_local_auth_opt_in(monkeypatch):
    # Legacy local-only fixtures intentionally use insecure development auth.
    # Tests of deployment defaults remove this explicit opt-in.
    monkeypatch.setenv("ATLAS_DEV_NO_AUTH", "1")
    monkeypatch.setenv("ATLAS_ENV", "development")


def _check_bubblewrap_probe(probe):
    """Only exact known OS-capability refusals count as unavailable environment."""
    refusals = {
        "bwrap: Creating new namespace failed: Operation not permitted",
        "bwrap: Creating new namespace failed: Permission denied",
        "bwrap: No permissions to create new namespace, likely because the kernel does not allow non-privileged user namespaces. See <https://deb.li/bubblewrap> or <file:///usr/share/doc/bubblewrap/README.Debian.gz>.",
    }
    if probe.returncode != 0 and not probe.stdout and probe.stderr.strip() in refusals:
        pytest.skip(f"REAL ISOLATION UNVERIFIED: {probe.stderr.strip()}")
    assert probe.returncode == 0, f"bubblewrap probe failed: {probe.returncode}: {probe.stderr}"
    assert probe.stdout == "atlas-isolation-probe\n", repr(probe.stdout)
    assert not probe.stderr, probe.stderr


@pytest.fixture(scope="session")
def real_bubblewrap_environment():
    """Gate only explicit-bubblewrap acceptance tests on real namespace support."""
    import subprocess
    import tempfile
    from pathlib import Path
    from app.modules.m04_research_scientist.approved_sandbox import BubblewrapBackend
    backend = BubblewrapBackend()
    if backend.bwrap is None:
        pytest.skip("REAL ISOLATION UNVERIFIED: bubblewrap binary is absent")
    assert backend.available("python"), "bubblewrap Python interpreter/configuration is invalid"
    with tempfile.TemporaryDirectory(prefix="atlas-test-bwrap-probe-") as td:
        root = Path(td)
        inputs = root / "in"; inputs.mkdir()
        outputs = root / "out"; outputs.mkdir()
        (inputs / "analysis.py").write_text("print('atlas-isolation-probe')")
        # Missing binary, namespace refusal alone may skip. Other OSError and
        # timeout propagate as test errors; malformed commands must stay red.
        try:
            probe = subprocess.run(backend.command("python", inputs, outputs),
                                   capture_output=True, text=True, timeout=10)
        except FileNotFoundError as exc:
            if exc.filename == backend.bwrap:
                pytest.skip("REAL ISOLATION UNVERIFIED: bubblewrap binary disappeared")
            raise
        _check_bubblewrap_probe(probe)
