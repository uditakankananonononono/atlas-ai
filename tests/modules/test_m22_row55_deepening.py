"""Row 55 deepening: exact-value tests for the M22 blog, podcast and GitHub collectors. No network: injected fetch
and a patched urlopen only."""
import asyncio
import json

import pytest

from app.modules.m22_tools_hub import sources
from app.modules.m22_tools_hub.collectors import _github


def collect(collector, query="kubernetes"):
    async def go():
        return [x async for x in collector.collect(query)]
    return asyncio.run(go())


def recorder(payload):
    seen = []

    def fetch(url, headers=None):
        seen.append(url)
        return json.dumps(payload).encode()
    return fetch, seen


def devto(fetch):
    return sources.JsonSourceCollector("devto", "blog", "https://dev.to/api/articles?tag={tag}&per_page=20&top=30",
                                       sources._parse_devto, fetch=fetch)


def itunes(fetch):
    return sources.JsonSourceCollector("itunes", "podcast", "https://itunes.apple.com/search?media=podcast&term={query}&limit=20",
                                       sources._parse_itunes, fetch=fetch)


def test_url_uses_slugged_tag_for_devto_and_quoted_query_for_others():
    fetch, seen = recorder([])
    collect(devto(fetch), "Kubernetes & Go!")
    assert seen[-1] == "https://dev.to/api/articles?tag=kubernetesgo&per_page=20&top=30"
    fetch, seen = recorder({"results": []})
    collect(itunes(fetch), "a b&c")
    assert seen[-1] == "https://itunes.apple.com/search?media=podcast&term=a+b%26c&limit=20"


def test_tag_slug_is_capped_at_40_characters():
    assert sources._tag_slug("a" * 60) == "a" * 40


def test_non_json_body_raises_source_error():
    c = devto(lambda url, headers=None: b"<html>not json</html>")
    with pytest.raises(sources.SourceError):
        collect(c)


def test_devto_caps_at_20_and_cleans_the_summary():
    rows = [{"title": "t%d" % i, "url": "https://dev.to/x/%d" % i, "description": "<b>bold</b> " + "w " * 400}
            for i in range(25)]
    out = collect(devto(recorder(rows)[0]))
    assert len(out) == 20
    s = out[0]["summary"]
    assert "<b>" not in s and s.startswith("bold w")
    assert len(s) <= sources.MAX_SUMMARY_CHARS and s.endswith("…")


def test_wordpress_title_html_is_stripped():
    payload = {"posts": [{"title": "<em>Hello</em> &amp; welcome", "URL": "https://x.wordpress.com/p"}]}
    c = sources.JsonSourceCollector("wordpress", "blog", "https://public-api.wordpress.com/rest/v1.2/read/search?q={query}&number=20",
                                    sources._parse_wordpress, fetch=recorder(payload)[0])
    assert collect(c)[0]["name"] == "Hello & welcome"


def test_itunes_genres_url_artist_and_cap():
    rows = [{"collectionName": "Show %d" % i, "collectionViewUrl": "https://podcasts.apple.com/c/%d" % i,
             "trackViewUrl": "https://podcasts.apple.com/t/%d" % i, "genres": ["Podcasts", "Technology", "Education"],
             "artistName": None} for i in range(25)]
    out = collect(itunes(recorder({"results": rows})[0]))
    assert len(out) == 20
    first = out[0]
    assert first["url"] == "https://podcasts.apple.com/c/0"
    assert first["evidence"][0]["genres"] == ["Technology", "Education"]
    assert first["summary"] == "Podcast by unknown artist (Technology, Education)"


def test_recency_score_windows_and_missing_timestamp():
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    f = lambda d: sources._recency_score((now - timedelta(days=d)).isoformat())
    assert f(10) == 0.8 and f(181 + 0) == 0.5 and f(731) == 0.2
    assert sources._recency_score(None) == 0.5 and sources._recency_score("garbage") == 0.5


def test_http_get_enforces_the_byte_cap(monkeypatch):
    class Resp:
        def __init__(self, data): self.data = data
        def read(self, n): return self.data[:n]
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(sources, "urlopen", lambda req, timeout=None: Resp(b"x" * 50))
    with pytest.raises(sources.SourceError):
        sources.http_get("https://example.test/a", limit=10)
    assert sources.http_get("https://example.test/a", limit=10, truncate_ok=True) == b"x" * 10
    assert sources.http_get("https://example.test/a", limit=50) == b"x" * 50


def test_github_caps_at_20_and_uses_html_url():
    items = [{"full_name": "o/r%d" % i, "html_url": "https://github.com/o/r%d" % i, "url": "https://api.github.com/repos/o/r%d" % i,
              "description": "d", "pushed_at": "2026-09-01T00:00:00Z", "license": {"spdx_id": "MIT"}} for i in range(25)]
    out = list(_github({"items": items}))
    assert len(out) == 20
    assert out[0]["url"] == "https://github.com/o/r0" and out[0]["name"] == "o/r0"
