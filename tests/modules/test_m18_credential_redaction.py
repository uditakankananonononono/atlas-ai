"""Pin for M18 credential redaction in recorded collection failures.

Collector fetches need the real URL (the YouTube Data API key travels as
?key=), but CollectionError records are persisted and reported - "failures
are data". Every CollectionError, whoever constructed it, must not carry
credential query parameters. Establishes recording hygiene only; fetch
behavior is unchanged (the live request still uses the real URL).
"""
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
