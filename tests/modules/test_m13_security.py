import socket

import pytest

from app.modules.m13_browser_agent.security import NavigationBlocked, validate_public_url, values_digest


@pytest.mark.parametrize("url", [
    "http://localhost/x",
    "http://127.0.0.1/x",
    "http://[::1]/x",
    "http://169.254.169.254/latest/meta-data",
    "ftp://example.com/file",
    "https://u:p@example.com",
])
def test_dangerous_destinations_are_blocked(url):
    with pytest.raises(NavigationBlocked):
        validate_public_url(url)


def test_dns_rebinding_style_mixed_resolution_is_blocked(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
    ])
    with pytest.raises(NavigationBlocked):
        validate_public_url("https://example.com")


def test_allowlist_is_exact_unless_suffix_explicit(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    with pytest.raises(NavigationBlocked):
        validate_public_url("https://evil-example.com", {"example.com"})
    assert validate_public_url("https://sub.example.com", {".example.com"}) == "https://sub.example.com/"


def test_digest_is_unambiguous_and_order_stable():
    assert values_digest({"a": "1", "b": "2"}) == values_digest({"b": "2", "a": "1"})
    assert values_digest({"a": "1\nb=2"}) != values_digest({"a": "1", "b": "2"})
