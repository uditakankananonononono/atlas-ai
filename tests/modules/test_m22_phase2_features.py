"""M22 phase 2: 20 module features, each with focused tests. No network:
every fetch is injected; fixtures keep the live endpoint field names."""
import io
import json

import pytest

from app.modules.m22_tools_hub import sources
from app.modules.m22_tools_hub.collectors import _github, default_collectors
from app.modules.m22_tools_hub.service import Service


class FakeApprovals:
    def __init__(self): self.items = []
    def put(self, item): self.items.append(item); return item


def make_service(collectors=(), **kw):
    kw.setdefault("source_cooldown_seconds", 300)
    return Service(FakeApprovals(), list(collectors), **kw)


class StaticCollector:
    def __init__(self, name, kind, items, calls=None):
        self.name, self.kind, self.items = name, kind, items
        self.calls = calls if calls is not None else []

    async def collect(self, query):
        self.calls.append(query)
        for x in self.items:
            yield x


REPO_A = {"name": "repo-a", "url": "https://gitlab.com/a/repo-a", "summary": "A",
          "kind": "repository", "security": .9, "fit": .8, "maintenance": .9, "novelty": .7,
          "evidence": [{"source": "gitlab"}]}
BLOG_B = {"name": "blog-b", "url": "https://blog.example.com/b", "summary": "B",
          "kind": "blog", "security": .5, "fit": .5, "maintenance": .5, "novelty": .5,
          "evidence": [{"source": "devto"}]}


# 1. kind-filtered discovery -------------------------------------------------
@pytest.mark.asyncio
async def test_discover_filters_collectors_by_kind():
    repo = StaticCollector("gitlab", "repository", [REPO_A])
    blog = StaticCollector("devto", "blog", [BLOG_B])
    s = make_service([repo, blog])
    items = await s.discover("kubernetes", kinds=["repository"])
    assert [x.name for x in items] == ["repo-a"]
    assert blog.calls == [], "blog collector was not queried for a repository-only search"
    items = await s.discover("kubernetes")
    assert {x.name for x in items} == {"repo-a", "blog-b"}


# 2. per-source run stats ----------------------------------------------------
@pytest.mark.asyncio
async def test_source_stats_recorded():
    repo = StaticCollector("gitlab", "repository", [REPO_A])
    s = make_service([repo])
    await s.discover("x")
    stats = {x["name"]: x for x in s.sources()}["gitlab"]
    assert stats["runs"] == 1 and stats["failures"] == 0
    assert stats["candidates"] == 1 and stats["last_status"] == "ok"
    assert stats["last_latency_ms"] >= 0


# 3. failure cooldown --------------------------------------------------------
@pytest.mark.asyncio
async def test_failing_source_cools_down_and_is_skipped():
    calls = []

    class Flaky:
        name = "flaky"
        kind = "blog"

        async def collect(self, query):
            calls.append(query)
            raise sources.SourceError("boom")
            yield  # pragma: no cover - keeps this an async generator

    s = make_service([Flaky()], source_cooldown_seconds=3600)
    assert await s.discover("x") == []
    assert s.last_errors["flaky"] == "boom"
    assert await s.discover("x") == []
    assert len(calls) == 1, "second discovery skipped the cooling-down source"
    assert "cooldown" in s.last_errors["flaky"]


# 4. feed autodiscovery from HTML + path probing -----------------------------
def test_discover_feeds_from_link_tags():
    page = b'''<html><head>
      <link rel="alternate" type="application/rss+xml" title="RSS" href="/feed.xml">
      <link rel="stylesheet" href="/style.css">
    </head><body>hi</body></html>'''
    rss = b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'

    def fetch(url, **kw):
        return rss if url.endswith("/feed.xml") else page

    feeds = sources.discover_feeds("https://blog.example.com/", fetch=fetch)
    assert feeds == ["https://blog.example.com/feed.xml"]


def test_discover_feeds_probes_common_paths():
    rss = b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'

    def fetch(url, **kw):
        if url == "https://site.example.com":
            return b"<html><head></head></html>"
        if url == "https://site.example.com/feed":
            return rss
        raise sources.SourceError("404")

    assert sources.discover_feeds("https://site.example.com", fetch=fetch) == ["https://site.example.com/feed"]


def test_discover_feeds_ignores_self_referencing_links():
    """Blogger-style pages advertise <link type=atom href=//site/> pointing at the homepage."""
    rss = b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'

    def fetch(url, **kw):
        if url == "https://blog.example.com/":
            return b'<html><head><link href="//blog.example.com/" type="application/atom+xml" rel="alternate" title="feed"/></head></html>'
        if url == "https://blog.example.com/feed":
            return rss
        raise sources.SourceError("404")

    assert sources.discover_feeds("https://blog.example.com/", fetch=fetch) == ["https://blog.example.com/feed"]


def test_discover_feeds_rejects_non_https():
    with pytest.raises(sources.SourceError):
        sources.discover_feeds("http://insecure.example.com", fetch=lambda url, **kw: b"")


# 5 + 6. OPML import/export roundtrip ----------------------------------------
OPML = """<?xml version="1.0"?>
<opml version="2.0"><head><title>subs</title></head><body>
  <outline type="rss" text="Talk Python" xmlUrl="https://talkpython.fm/episodes/rss" htmlUrl="https://talkpython.fm"/>
  <outline type="rss" text="Blog" xmlUrl="https://blog.example.com/feed"/>
  <outline type="rss" text="Insecure" xmlUrl="http://old.example.com/feed"/>
</body></opml>"""


def test_opml_parse_and_collectors_skip_insecure():
    feeds = sources.parse_opml(OPML)
    assert len(feeds) == 3
    collectors = sources.collectors_from_opml(OPML)
    assert len(collectors) == 2, "the http feed is skipped, not imported"
    assert collectors[0].feed_url == "https://talkpython.fm/episodes/rss"


def test_opml_build_roundtrip():
    feeds = sources.parse_opml(OPML)[:2]
    doc = sources.feeds_to_opml(feeds)
    again = sources.parse_opml(doc)
    assert [f["feed_url"] for f in again] == [f["feed_url"] for f in feeds]


# 7. canonical dedup keys ----------------------------------------------------
def test_dedup_ignores_tracking_params_and_trailing_slash():
    class C:
        def __init__(self, name, url): self.name, self.url = name, url
    a = C("tool", "https://Example.com/x/?utm_source=news&id=1#frag")
    b = C("tool", "https://example.com/x?id=1")
    assert Service._key(a) == Service._key(b)


# 8. score explanation -------------------------------------------------------
def test_explain_contributions_sum_to_score():
    s = make_service([])
    c = s._normalize(dict(REPO_A), "gitlab")
    ex = c.explain()
    assert abs(sum(v["contribution"] for v in ex["contributions"].values()) - ex["score"]) < 1e-3
    assert ex["kind"] == "repository"


# 9. GitHub collector recency scoring ----------------------------------------
def test_github_maintenance_uses_recency():
    recent = {"items": [{"full_name": "a/b", "html_url": "https://github.com/a/b", "description": "",
                         "archived": False, "stargazers_count": 1, "pushed_at": "2026-09-20T00:00:00Z",
                         "updated_at": "2026-09-20T00:00:00Z", "license": None}]}
    stale = {"items": [{"full_name": "a/b", "html_url": "https://github.com/a/b", "description": "",
                        "archived": False, "stargazers_count": 1, "pushed_at": "2019-01-01T00:00:00Z",
                        "updated_at": "2019-01-01T00:00:00Z", "license": None}]}
    assert next(_github(recent))["maintenance"] > next(_github(stale))["maintenance"]


# 10. richer feed entry metadata ---------------------------------------------
def test_feed_entries_carry_guid_duration_and_enclosure_length():
    rss = b'''<?xml version="1.0"?><rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
    <channel><title>s</title><item><title>Ep</title><guid>urn:ep:1</guid>
    <link>https://x.test/1</link><pubDate>Sat, 19 Sep 2026 09:00:00 GMT</pubDate>
    <itunes:duration>00:31:12</itunes:duration>
    <enclosure url="https://x.test/1.mp3" length="22474701" type="audio/mpeg"/></item></channel></rss>'''
    (item,) = sources.parse_feed(rss)
    assert item["guid"] == "urn:ep:1" and item["published"]
    enc = next(e for e in item["evidence"] if "enclosure_url" in e)
    assert enc["enclosure_length"] == "22474701"
    assert any(e.get("duration") == "00:31:12" for e in item["evidence"])


# 11. iTunes episode search collector ----------------------------------------
@pytest.mark.asyncio
async def test_itunes_episode_collector():
    payload = json.dumps({"results": [{
        "collectionName": "Talk Python To Me", "trackName": "#450: Fun episode",
        "trackViewUrl": "https://podcasts.apple.com/us/podcast/id450",
        "episodeUrl": "https://cdn.x/ep450.mp3", "feedUrl": "https://talkpython.fm/episodes/rss",
        "releaseDate": "2026-09-20T07:00:00Z", "description": "Fun", "trackTimeMillis": 1872000,
    }]}).encode()
    c = sources.JsonSourceCollector("itunes-episodes", "podcast-episode",
                                    "https://itunes.apple.com/search?media=podcast&entity=podcastEpisode&term={query}&limit=20",
                                    sources._parse_itunes_episodes, fetch=lambda url: payload)
    items = [x async for x in c.collect("python")]
    assert items[0]["name"] == "#450: Fun episode"
    assert items[0]["kind"] == "podcast-episode"
    assert items[0]["evidence"][0]["show"] == "Talk Python To Me"


# 12. batch discovery ---------------------------------------------------------
@pytest.mark.asyncio
async def test_batch_discovery_merges_and_dedups():
    dup = dict(REPO_A)
    c1 = StaticCollector("gitlab", "repository", [REPO_A])
    c2 = StaticCollector("codeberg", "repository", [dup])
    s = make_service([c1, c2])
    result = await s.discover_many(["kubernetes", "docker"])
    assert len(result["per_query"]) == 2
    assert [x.name for x in result["merged"]] == ["repo-a"], "same repo across queries dedups"
    with pytest.raises(ValueError):
        await s.discover_many([f"q{i}" for i in range(21)])


# 13. custom scoring weights --------------------------------------------------
@pytest.mark.asyncio
async def test_custom_weights_change_ranking():
    secure_low_fit = {"name": "secure", "url": "https://x.test/s", "kind": "repository",
                      "security": 1.0, "fit": .1, "maintenance": .9, "novelty": .7,
                      "evidence": [{}, {}, {}]}
    fit_low_secure = {"name": "fit", "url": "https://x.test/f", "kind": "repository",
                      "security": .1, "fit": 1.0, "maintenance": .1, "novelty": .1, "evidence": []}
    s = make_service([StaticCollector("g", "repository", [secure_low_fit, fit_low_secure])])
    default = await s.discover("q")
    assert default[0].name == "secure"
    custom = await s.discover("q", weights={"fit": 1.0})
    assert custom[0].name == "fit"
    with pytest.raises(ValueError):
        await s.discover("q", weights={"bogus": 1.0})
    with pytest.raises(ValueError):
        await s.discover("q", weights={"fit": 0.0})


# 14. persistent runtime blocklist --------------------------------------------
@pytest.mark.asyncio
async def test_blocklist_runtime_add_persists_and_filters(tmp_path):
    s = make_service([StaticCollector("g", "repository", [REPO_A, dict(BLOG_B, url="https://spam.example.com/x", name="spammy")])],
                     state_path=str(tmp_path))
    items = await s.discover("q")
    assert {x.name for x in items} == {"repo-a", "spammy"}
    s.add_block("domains", "spam.example.com")
    s2 = make_service([StaticCollector("g", "repository", [REPO_A, dict(BLOG_B, url="https://spam.example.com/x", name="spammy")])],
                      state_path=str(tmp_path))
    items = await s2.discover("q")
    assert {x.name for x in items} == {"repo-a"}, "block survived a service restart via the state file"
    s2.remove_block("domains", "spam.example.com")
    assert "spam.example.com" not in s2.blocks()["domains"]


# 15. candidate export ---------------------------------------------------------
@pytest.mark.asyncio
async def test_export_json_csv_markdown():
    s = make_service([StaticCollector("g", "repository", [REPO_A])])
    await s.discover("q")
    assert json.loads(s.export_candidates("json"))[0]["name"] == "repo-a"
    assert "repo-a" in s.export_candidates("csv").splitlines()[1]
    assert "**repo-a**" in s.export_candidates("markdown")
    with pytest.raises(ValueError):
        s.export_candidates("yaml")


# 16. feed watcher with persistent cursors --------------------------------------
RSS_V1 = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>s</title>
<item><title>Ep 1</title><guid>g1</guid><link>https://x.test/1</link></item></channel></rss>'''
RSS_V2 = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>s</title>
<item><title>Ep 2</title><guid>g2</guid><link>https://x.test/2</link></item>
<item><title>Ep 1</title><guid>g1</guid><link>https://x.test/1</link></item></channel></rss>'''


@pytest.mark.asyncio
async def test_feed_watcher_returns_only_new_entries(tmp_path):
    w = sources.FeedWatcher(tmp_path / "watches.json")
    first = await w.poll("https://x.test/feed", opener=lambda url: io.BytesIO(RSS_V1))
    assert [e["name"] for e in first] == ["Ep 1"]
    w2 = sources.FeedWatcher(tmp_path / "watches.json")  # new instance, same state file
    second = await w2.poll("https://x.test/feed", opener=lambda url: io.BytesIO(RSS_V2))
    assert [e["name"] for e in second] == ["Ep 2"], "only the unseen episode comes back"
    third = await w2.poll("https://x.test/feed", opener=lambda url: io.BytesIO(RSS_V2))
    assert third == []


# 17. repository evidence refresh ------------------------------------------------
def test_refresh_repository_candidate_all_hosts():
    def fetch(url):
        if "api.github.com" in url:
            return json.dumps({"stargazers_count": 5, "forks_count": 1, "pushed_at": "2026-09-24T00:00:00Z",
                               "archived": False, "license": {"spdx_id": "MIT"}}).encode()
        if "gitlab.com" in url:
            assert "a%2Fb" in url, "gitlab project path is URL-encoded"
            return json.dumps({"star_count": 9, "forks_count": 2, "last_activity_at": "2026-09-24T00:00:00Z"}).encode()
        return json.dumps({"stars_count": 3, "forks_count": 0, "updated_at": "2026-09-24T00:00:00Z",
                           "archived": False, "language": "Go"}).encode()

    gh = sources.refresh_repository_candidate("a/b", "github", fetch=fetch)
    gl = sources.refresh_repository_candidate("a/b", "gitlab", fetch=fetch)
    cb = sources.refresh_repository_candidate("a/b", "codeberg", fetch=fetch)
    assert gh["evidence"]["license"] == "MIT" and gh["maintenance"] == 0.8
    assert gl["evidence"]["stars"] == 9
    assert cb["evidence"]["language"] == "Go"
    with pytest.raises(sources.SourceError):
        sources.refresh_repository_candidate("x", "pypi", fetch=fetch)


# 18. query history ---------------------------------------------------------------
@pytest.mark.asyncio
async def test_query_history_recorded():
    s = make_service([StaticCollector("g", "repository", [REPO_A])])
    await s.discover("alpha")
    await s.discover("beta", kinds=["repository"])
    assert [h["query"] for h in s.query_history] == ["alpha", "beta"]
    assert s.query_history[1]["kinds"] == ["repository"] and s.query_history[1]["count"] == 1


# 19. saved-query diffing ----------------------------------------------------------
@pytest.mark.asyncio
async def test_saved_query_diff_reports_changes():
    collector = StaticCollector("g", "repository", [REPO_A])
    s = make_service([collector])
    await s.discover("q")
    assert s.last_diffs["q"]["first_run"] is True
    collector.items = [dict(REPO_A, name="repo-b", url="https://gitlab.com/a/repo-b")]
    await s.discover("q")
    diff = s.last_diffs["q"]
    assert diff["added"] == ["repo-b"] and diff["removed"] == ["repo-a"]
    report = s.discovery_report("q")
    assert report["diff"]["added"] == ["repo-b"]
    assert {c["name"] for c in report["candidates"]} == {"repo-a", "repo-b"}


# 20. https-only enforcement --------------------------------------------------------
@pytest.mark.asyncio
async def test_insecure_candidate_urls_are_refused_by_default():
    insecure = dict(REPO_A, url="http://gitlab.com/a/repo-a", name="insecure")
    s = make_service([StaticCollector("g", "repository", [insecure])])
    assert await s.discover("q") == []
    s2 = make_service([StaticCollector("g", "repository", [insecure])], require_https=False)
    assert len(await s2.discover("q")) == 1
