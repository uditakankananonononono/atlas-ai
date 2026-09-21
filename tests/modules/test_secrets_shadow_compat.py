"""Regression coverage for the repo-root secrets module shadowing stdlib."""
import secrets


def test_stdlib_compatibility_surface_is_secure_and_available():
    assert len(secrets.token_bytes(7)) == 7
    assert len(secrets.token_hex(7)) == 14
    assert "=" not in secrets.token_urlsafe(7)
    assert 0 <= secrets.randbelow(5) < 5
    assert secrets.compare_digest("atlas", "atlas")
    assert not secrets.compare_digest("atlas", "other")
