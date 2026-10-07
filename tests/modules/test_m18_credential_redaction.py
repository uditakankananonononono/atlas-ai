"""Pin for M18 credential redaction in recorded collection failures.

Collector fetches need the real URL (the YouTube Data API key travels as
?key=), but CollectionError records are persisted and reported - "failures
are data". Every CollectionError, whoever constructed it, must not carry
credential query parameters. Establishes recording hygiene only; fetch
behavior is unchanged (the live request still uses the real URL).
"""
from urllib.parse import urlsplit
from app.modules.m18_side_hustle_scraper.lane_models import CollectionError

def test_collection_error_never_records_credential_query_params():
    err = CollectionError(
        source="youtube",
        url="https://www.googleapis.com/youtube/v3/search?part=snippet&key=SECRET-KEY-123&q=test",
        reason="boom",
        status=500,
    )
    assert "SECRET-KEY-123" not in err.url
    assert "REDACTED" in err.url
    assert "q=test" in err.url and "part=snippet" in err.url  # non-sensitive params survive

def test_collection_error_redacts_all_sensitive_key_names():
    for param in ("key", "api_key", "apikey", "token", "access_token", "KEY"):
        err = CollectionError(source="x", url=f"https://h.test/p?{param}=SECRET-XYZ&a=1", reason="r")
        assert "SECRET-XYZ" not in err.url, param

def test_urls_without_credentials_pass_through_unchanged():
    url = "https://hn.algolia.com/api/v1/search?query=side%20hustle&tags=story"
    assert CollectionError(source="hn", url=url, reason="r").url == url

def test_reason_text_is_scrubbed_for_embedded_credentials():
    # An arbitrary reason string (e.g. an upstream error embedding the failing
    # URL) is not trusted to be secret-free.
    err = CollectionError(
        source="youtube",
        url="https://h.test/p",
        reason="HTTP 500 for https://www.googleapis.com/youtube/v3/search?part=snippet&key=SECRET-KEY-123&q=x: boom",
    )
    assert "SECRET-KEY-123" not in err.reason
    assert "key=[REDACTED]" in err.reason

def test_userinfo_is_stripped_from_recorded_url():
    err = CollectionError(source="x", url="https://user:SECRET-PW@h.test/p?a=1", reason="r")
    assert "SECRET-PW" not in err.url
    assert "user" not in err.url.split("/")[2]  # no userinfo in netloc
    assert err.url.startswith("https://h.test/p")

def test_userinfo_in_reason_text_is_scrubbed():
    err = CollectionError(source="x", url="https://h.test", reason="auth failed for https://u:SECRET-PW@h.test/p")
    assert "SECRET-PW" not in err.reason
    assert "[REDACTED]@" in err.reason

def test_fragment_left_unchanged_characterization():
    # Characterization of the accepted limitation: fragments are not redacted.
    # Recorded request URLs do not carry OAuth-style fragment tokens today.
    url = "https://h.test/cb#token=FRAG-SECRET"
    assert CollectionError(source="x", url=url, reason="r").url == url

def test_ipv6_brackets_and_port_preserved_when_redacting():
    # Regression: rebuilding the netloc from urlsplit().hostname drops IPv6
    # brackets and .port can raise. The authority must survive verbatim.
    url = "https://u:SECRET-PW@[::1]:8080/p?key=SECRET-KEY&q=1"
    redacted = CollectionError(source="x", url=url, reason="r").url
    assert "SECRET" not in redacted
    assert "[::1]:8080" in redacted
    assert urlsplit(redacted).port == 8080  # re-parseable

def test_keyed_ipv6_url_keeps_brackets_without_userinfo():
    url = "https://[2001:db8::1]/p?KEY=SECRET-KEY&q=1"
    redacted = CollectionError(source="x", url=url, reason="r").url
    assert "SECRET-KEY" not in redacted
    assert "[2001:db8::1]" in redacted
    assert urlsplit(redacted).hostname == "2001:db8::1"

def test_username_only_userinfo_stripped():
    # Characterization: userinfo without a password is also stripped.
    err = CollectionError(source="x", url="https://user@h.test/p?a=1", reason="r")
    assert err.url == "https://h.test/p?a=1"
