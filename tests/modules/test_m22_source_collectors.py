"""M22 source integrations: blogs, podcasts, git hosts, RSS/Atom feeds.

Fixtures preserve the exact field names of the live endpoints as verified on
2026-09-25 (DEV.to, WordPress.com Reader, HN Algolia, iTunes Search, GitLab,
Codeberg). Network is never touched: every collector takes an injected fetch.
"""
import io
import json
import os

import pytest

from app.modules.m22_tools_hub import sources
from app.modules.m22_tools_hub.collectors import default_collectors
from app.modules.m22_tools_hub.service import Service

DEVTO = json.dumps([{
    "type_of": "article", "id": 4689954, "title": "What Building a Fintech Ledger Taught Me",
    "description": "I built a double-entry payments ledger.", "slug": "fintech-ledger",
    "path": "/alice/fintech-ledger-1abc", "url": "https://dev.to/alice/fintech-ledger-1abc",
    "comments_count": 12, "public_reactions_count": 88, "published_at": "2026-09-19T09:00:00Z",
    "tag_list": ["kubernetes", "fintech"], "user": {"name": "Alice Example", "username": "alice"},
}]).encode()

WORDPRESS = json.dumps({
    "date_range": {"before": "2026-07-06 20:00:21", "after": "2026-07-06 20:00:21"},
    "posts": [{
        "ID": 26120, "site_ID": 235918711,
        "author": {"ID": 64223368, "name": "Amjad Izhar"},
        "URL": "https://amjadizhar4.wordpress.com/2026/07/07/kubernetes-guide/",
        "title": "Kubernetes: A Beginner&#8217;s Guide",
        "excerpt": "<p>This comprehensive guide introduces&nbsp;Kubernetes.</p>",
        "date": "2026-07-07T01:00:00+05:00",
        "discussion": {"comment_count": 3},
    }],
}).encode()

HACKERNEWS = json.dumps({
    "hits": [{
        "title": "Google Kubernetes Engine's third consecutive day of service disruption",
        "url": "https://status.cloud.google.com/incident/container-engine/18005",
        "points": 779, "author": "rlancer", "created_at": "2018-11-11T20:47:57Z",
        "num_comments": 407, "objectID": "18428497",
    }, {
        "title": "Ask HN: Who is hiring?", "url": None,
        "points": 10, "author": "whoishiring", "created_at": "2026-09-01T15:00:00Z",
        "num_comments": 500, "objectID": "99999999",
    }],
}).encode()

ITUNES = json.dumps({
    "resultCount": 1,
    "results": [{
        "wrapperType": "track", "kind": "podcast", "collectionId": 979020229,
        "artistName": "Michael Kennedy", "collectionName": "Talk Python To Me",
        "collectionViewUrl": "https://podcasts.apple.com/us/podcast/talk-python-to-me/id979020229",
        "feedUrl": "https://talkpython.fm/episodes/rss", "trackCount": 480,
        "genres": ["Technology", "Podcasts"],
    }],
}).encode()

GITLAB = json.dumps([{
    "id": 18899486, "description": "Kubernetes Operator for GitLab Server",
    "name": "GitLab Operator", "name_with_namespace": "GitLab.org / Cloud Native / GitLab Operator",
    "path": "gitlab-operator", "path_with_namespace": "gitlab-org/cloud-native/gitlab-operator",
    "created_at": "2020-05-20T17:22:13.221Z", "default_branch": "master",
    "topics": ["Canonical"], "web_url": "https://gitlab.com/gitlab-org/cloud-native/gitlab-operator",
    "star_count": 42, "forks_count": 7, "last_activity_at": "2026-09-01T10:00:00.000Z",
    "visibility": "public",
}]).encode()

CODEBERG = json.dumps({
    "ok": True,
    "data": [{
        "id": 392559, "name": "kube-tools", "full_name": "terminalnode/kube-tools",
        "html_url": "https://codeberg.org/terminalnode/kube-tools",
        "description": "Small Kubernetes helpers", "stars_count": 5, "forks_count": 1,
        "updated_at": "2026-09-10T12:00:00Z", "language": "Go", "archived": False,
    }],
}).encode()

MEDIUM_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0">
  <channel>
    <title>kubernetes - Medium</title>
    <item>
      <title>Kubernetes in 10 minutes</title>
      <link>https://medium.com/@alice/kubernetes-in-10-minutes-abc123</link>
      <dc:creator>Alice</dc:creator>
      <pubDate>Sat, 19 Sep 2026 09:00:00 GMT</pubDate>
      <description>&lt;p&gt;A hands-on tour of pods and services.&lt;/p&gt;</description>
      <content:encoded>&lt;p&gt;A hands-on tour of pods and services with yaml.&lt;/p&gt;</content:encoded>
    </item>
  </channel>
</rss>"""

PODCAST_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Example Show</title>
    <item>
      <title>Episode 1: Beginnings</title>
      <link>https://example.show/ep/1</link>
      <pubDate>Sat, 19 Sep 2026 09:00:00 GMT</pubDate>
      <description>Our first episode.</description>
      <enclosure url="https://cdn.example.show/ep1.mp3" length="123456" type="audio/mpeg"/>
    </item>
    <item>
      <title>Episode 2: More</title>
      <link>https://example.show/ep/2</link>
      <pubDate>Sat, 20 Sep 2026 09:00:00 GMT</pubDate>
      <description>Second episode.</description>
      <enclosure url="https://cdn.example.show/ep2.mp3" length="123457" type="audio/mpeg"/>
    </item>
  </channel>
</rss>"""

ATOM_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Blog</title>
  <entry>
    <title>Atom post one</title>
    <link rel="alternate" href="https://blog.example.com/post-1"/>
    <published>2026-09-18T09:00:00Z</published>
    <summary>First atom post.</summary>
  </entry>
</feed>"""


def fake_fetch(mapping):
    def fetch(url, headers=None):
        for prefix, body in mapping.items():
            if url.startswith(prefix):
                return body
        raise sources.SourceError(f"unexpected URL in test: {url}")
    return fetch


async def collect_all(collector, query="kubernetes"):
    return [x async for x in collector.collect(query)]


@pytest.mark.asyncio
@pytest.mark.parametrize("collector,mapping,expected_name", [
    (sources.JsonSourceCollector("devto", "blog", "https://dev.to/api/articles?tag={tag}&per_page=20&top=30", sources._parse_devto),
     {"https://dev.to/": DEVTO}, "What Building a Fintech Ledger Taught Me"),
    (sources.JsonSourceCollector("wordpress", "blog", "https://public-api.wordpress.com/rest/v1.2/read/search?q={query}&number=20", sources._parse_wordpress),
     {"https://public-api.wordpress.com/": WORDPRESS}, "Kubernetes: A Beginner’s Guide"),
    (sources.JsonSourceCollector("hackernews", "article", "https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage=20", sources._parse_hackernews),
     {"https://hn.algolia.com/": HACKERNEWS}, "Google Kubernetes Engine's third consecutive day of service disruption"),
    (sources.JsonSourceCollector("itunes", "podcast", "https://itunes.apple.com/search?media=podcast&term={query}&limit=20", sources._parse_itunes),
     {"https://itunes.apple.com/": ITUNES}, "Talk Python To Me"),
    (sources.JsonSourceCollector("gitlab", "repository", "https://gitlab.com/api/v4/projects?search={query}&per_page=20", sources._parse_gitlab),
     {"https://gitlab.com/": GITLAB}, "gitlab-org/cloud-native/gitlab-operator"),
    (sources.JsonSourceCollector("codeberg", "repository", "https://codeberg.org/api/v1/repos/search?q={query}&limit=20", sources._parse_codeberg),
     {"https://codeberg.org/": CODEBERG}, "terminalnode/kube-tools"),
])
async def test_json_sources_parse_real_shapes(collector, mapping, expected_name):
    collector.fetch = fake_fetch(mapping)
    items = await collect_all(collector)
    assert items and items[0]["name"] == expected_name
    for item in items:
        assert item["url"].startswith("https://")
        assert item["kind"] == collector.kind
        assert item["evidence"], "every candidate carries provenance evidence"
        assert item["permissions"] == []


@pytest.mark.asyncio
async def test_hackernews_fallback_url_for_self_posts():
    c = sources.JsonSourceCollector("hackernews", "article", "https://hn.algolia.com/?q={query}", sources._parse_hackernews)
    c.fetch = fake_fetch({"https://hn.algolia.com/": HACKERNEWS})
    items = await collect_all(c)
    assert items[1]["url"] == "https://news.ycombinator.com/item?id=99999999"


@pytest.mark.asyncio
async def test_medium_tag_feed_parses_rss():
    c = sources.MediumTagCollector()
    c.fetch = fake_fetch({"https://medium.com/": MEDIUM_RSS})
    items = await collect_all(c)
    assert [x["name"] for x in items] == ["Kubernetes in 10 minutes"]
    assert items[0]["kind"] == "blog"
    assert items[0]["url"] == "https://medium.com/@alice/kubernetes-in-10-minutes-abc123"
    assert "pods and services" in items[0]["summary"]
    assert "<" not in items[0]["summary"], "HTML is stripped from feed summaries"
    assert items[0]["evidence"][0]["source"] == "medium"


@pytest.mark.asyncio
async def test_medium_skips_unsluggable_query():
    c = sources.MediumTagCollector()
    assert await collect_all(c, query="!!!") == []


@pytest.mark.asyncio
async def test_feed_collector_podcast_rss_detects_episodes():
    c = sources.feed_collector("https://example.show/feed.xml", opener=lambda url: io.BytesIO(PODCAST_RSS))
    items = await collect_all(c)
    assert [x["name"] for x in items] == ["Episode 1: Beginnings", "Episode 2: More"]
    assert all(x["kind"] == "podcast-episode" for x in items)
    assert items[0]["evidence"][1]["enclosure_url"] == "https://cdn.example.show/ep1.mp3"


@pytest.mark.asyncio
async def test_feed_collector_atom():
    c = sources.feed_collector("https://blog.example.com/feed.xml", opener=lambda url: io.BytesIO(ATOM_FEED))
    items = await collect_all(c)
    assert items[0]["name"] == "Atom post one"
    assert items[0]["url"] == "https://blog.example.com/post-1"
    assert items[0]["kind"] == "blog"


def test_feed_collector_stops_after_max_items():
    body = b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>' + b"".join(
        b"<item><title>ep %d</title><link>https://x.test/%d</link></item>" % (i, i) for i in range(500)
    ) + b"</channel></rss>"
    c = sources.feed_collector("https://x.test/feed", max_items=20, opener=lambda url: io.BytesIO(body))
    import asyncio
    items = asyncio.run(collect_all(c))
    assert len(items) == 20


def test_feed_collector_rejects_non_https():
    with pytest.raises(sources.SourceError):
        sources.feed_collector("http://insecure.example.com/feed")


def test_parse_feed_rejects_malformed_xml():
    with pytest.raises(sources.SourceError):
        list(sources.parse_feed(b"<rss><channel><item><title>oops"))


def test_default_collectors_cover_blogs_podcasts_and_git():
    kinds = {}
    for c in default_collectors():
        kinds.setdefault(getattr(c, "kind", "?"), []).append(c.name)
    assert kinds.get("blog") and {"devto", "wordpress", "medium"} <= set(kinds["blog"])
    assert "itunes" in kinds.get("podcast", [])
    assert kinds.get("repository") and {"github", "gitlab", "codeberg"} <= set(kinds["repository"])
    assert "hackernews" in kinds.get("article", [])
    assert kinds.get("package") and {"pypi", "npm"} <= set(kinds["package"])


def test_podcast_index_is_optional_config(monkeypatch):
    monkeypatch.delenv("ATLAS_PODCASTINDEX_API_KEY", raising=False)
    monkeypatch.delenv("ATLAS_PODCASTINDEX_API_SECRET", raising=False)
    with pytest.raises(sources.SourceError):
        sources.PodcastIndexCollector()
    assert "podcastindex" not in [c.name for c in sources.default_source_collectors()]
    c = sources.PodcastIndexCollector(api_key="k", api_secret="s")
    assert c.name == "podcastindex"


@pytest.mark.asyncio
async def test_podcast_index_search_with_key():
    payload = json.dumps({"feeds": [{
        "title": "Example Pod", "url": "https://example.show/feed.xml", "link": "https://example.show",
        "description": "<p>A show</p>", "author": "Jane", "language": "en", "itunesId": 123,
        "lastUpdateTime": 1758000000,
    }]}).encode()
    seen = {}

    def fetch(url, headers):
        seen.update(headers)
        return payload

    c = sources.PodcastIndexCollector(api_key="k", api_secret="s", fetch=fetch)
    items = await collect_all(c)
    assert items[0]["name"] == "Example Pod"
    assert items[0]["kind"] == "podcast"
    assert items[0]["summary"] == "A show"
    assert {"X-Auth-Key", "X-Auth-Date", "Authorization"} <= seen.keys(), "signed per Podcast Index auth spec"


class FakeApprovals:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)
        return item


class FailingCollector:
    name = "broken"
    kind = "blog"

    async def collect(self, query):
        raise sources.SourceError("upstream 500")
        yield  # pragma: no cover


class WorkingCollector:
    name = "fine"
    kind = "repository"

    async def collect(self, query):
        yield {"name": "Good Repo", "url": "https://codeberg.org/a/b", "summary": "real",
               "kind": "repository", "security": 0.9, "fit": 0.8, "maintenance": 0.9,
               "novelty": 0.7, "evidence": [{"source": "codeberg"}]}


@pytest.mark.asyncio
async def test_discovery_tolerates_a_failing_source():
    s = Service(FakeApprovals(), [FailingCollector(), WorkingCollector()])
    items = await s.discover("kubernetes")
    assert [x.name for x in items] == ["Good Repo"]
    assert s.last_errors == {"broken": "upstream 500"}
    listing = {x["name"]: x for x in s.sources()}
    assert listing["broken"]["last_error"] == "upstream 500"
    assert listing["fine"]["last_error"] is None
    assert listing["fine"]["kind"] == "repository"


@pytest.mark.asyncio
async def test_kind_flows_from_raw_candidate_to_candidate():
    s = Service(FakeApprovals(), [WorkingCollector()])
    items = await s.discover("anything")
    assert items[0].kind == "repository"
