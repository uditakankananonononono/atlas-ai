"""Unit tests for Module 18 legal source collectors. No network: FakeHttpClient."""
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m18_side_hustle_scraper.lane_http import FakeHttpClient, HttpError
from app.modules.m18_side_hustle_scraper.lane_models import FetchPolicy, RightsClass, SourceKind
from app.modules.m18_side_hustle_scraper.lane_rate_limit import HostRateLimiter
from app.modules.m18_side_hustle_scraper.lane_robots import RobotsCache
from app.modules.m18_side_hustle_scraper.lane_sources import (
    DevToCollector,
    HackerNewsCollector,
    PublicWebCollector,
    RedditJsonCollector,
    RssFeedCollector,
    YouTubeDataCollector,
    ensure_legal_platform,
)

T0 = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


class Sleeps:
    def __init__(self, clock):
        self.clock = clock
        self.waits = []

    def __call__(self, seconds):
        self.waits.append(seconds)
        self.clock.advance(seconds)


def policy(**kw):
    base = dict(min_request_interval_seconds=2.0, max_retries=2, backoff_base_seconds=1.0)
    base.update(kw)
    return FetchPolicy(**base)


class RedditTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.sleeps = Sleeps(self.clock)
        self.http = FakeHttpClient(clock=self.clock)

    def test_parses_listing_with_provenance(self):
        payload = {"data": {"children": [
            {"data": {"title": "I made $400 tutoring", "selftext": "Started with 5 students...",
                      "permalink": "/r/sidehustle/comments/abc/i_made_400/", "score": 231,
                      "num_comments": 44, "created_utc": 1758000000, "author": "poster1",
                      "link_flair_text": "Story"}},
        ]}}
        self.http.add("https://www.reddit.com/r/sidehustle/search.json?q=tutoring&restrict_sr=1&sort=relevance&t=year&limit=10",
                      json.dumps(payload), headers={"etag": "W/\"x\""})
        c = RedditJsonCollector(self.http, policy=policy(), sleeper=self.sleeps, clock=self.clock,
                                subreddits=("sidehustle",))
        docs, errors = c.collect("tutoring", 10)
        self.assertEqual(errors, [])
        self.assertEqual(len(docs), 1)
        d = docs[0]
        self.assertEqual(d.url, "https://www.reddit.com/r/sidehustle/comments/abc/i_made_400/")
        self.assertEqual(d.rights, RightsClass.OFFICIAL_API)
        self.assertEqual(d.kind, SourceKind.REDDIT_JSON)
        self.assertEqual(d.engagement["score"], 231.0)
        self.assertEqual(d.engagement["comments"], 44.0)
        self.assertEqual(d.author, "poster1")
        self.assertTrue(d.content_hash)
        self.assertEqual(self.http.requests[0]["headers"], {})

    def test_rejects_browser_spoof_user_agent(self):
        with self.assertRaises(ValueError):
            RedditJsonCollector(self.http, policy=policy(user_agent="Mozilla/5.0 Chrome/120 Safari/537.36"))

    def test_error_becomes_collection_error_not_exception(self):
        self.http.add_error("https://www.reddit.com/r/sidehustle/search.json?q=x+y&restrict_sr=1&sort=relevance&t=year&limit=10",
                            HttpError("u", 403, "blocked"))
        c = RedditJsonCollector(self.http, policy=policy(), sleeper=self.sleeps, clock=self.clock,
                                subreddits=("sidehustle",))
        docs, errors = c.collect("x y", 10)
        self.assertEqual(docs, [])
        self.assertEqual(errors[0].status, 403)

    def test_retry_on_429_then_success(self):
        url = "https://hn.algolia.com/api/v1/search?query=tutoring&tags=story&hitsPerPage=10"
        self.http.add_error(url, HttpError(url, 429, "slow down", retry_after=5.0))
        self.http.add(url, json.dumps({"hits": []}))
        c = HackerNewsCollector(self.http, policy=policy(), sleeper=self.sleeps, clock=self.clock)
        docs, errors = c.collect("tutoring", 10)
        self.assertEqual(errors, [])
        self.assertEqual(len(self.http.requests), 2)
        self.assertTrue(any(w >= 5.0 for w in self.sleeps.waits))


class HackerNewsTests(unittest.TestCase):
    def test_parses_hits_and_thread_link(self):
        payload = {"hits": [{"objectID": "99", "title": "Ask HN: side projects that pay",
                             "url": "https://example.com/side", "story_text": "body",
                             "points": 120, "num_comments": 80, "created_at_i": 1758000000, "author": "hnuser"}]}
        clock = Clock()
        http = FakeHttpClient(clock=clock)
        http.add("https://hn.algolia.com/api/v1/search?query=side+projects&tags=story&hitsPerPage=10", json.dumps(payload))
        c = HackerNewsCollector(http, policy=policy(), clock=clock)
        docs, _ = c.collect("side projects", 10)
        self.assertEqual(docs[0].meta["thread"], "https://news.ycombinator.com/item?id=99")
        self.assertEqual(docs[0].engagement["score"], 120.0)


class DevToTests(unittest.TestCase):
    def test_parses_articles(self):
        payload = [{"url": "https://dev.to/a/post", "title": "Freelance sprint",
                    "description": "How I bill", "published_at": "2026-09-01T10:00:00Z",
                    "positive_reactions_count": 55, "comments_count": 3, "tag_list": ["career"],
                    "user": {"username": "dev1"}, "reading_time_minutes": 6}]
        http = FakeHttpClient()
        http.add("https://dev.to/api/articles?tag=freelance&per_page=10&state=rising", json.dumps(payload))
        docs, errors = DevToCollector(http, policy=policy()).collect("freelance clients", 10)
        self.assertEqual(errors, [])
        self.assertEqual(docs[0].author, "dev1")
        self.assertEqual(docs[0].engagement["score"], 55.0)
        self.assertIsNotNone(docs[0].published_at)


class YouTubeTests(unittest.TestCase):
    def test_requires_api_key(self):
        with self.assertRaises(ValueError):
            YouTubeDataCollector(FakeHttpClient(), api_key="")

    def test_search_plus_stats(self):
        search = {"items": [{"id": {"videoId": "v1"}, "snippet": {"title": "Print on demand 2026",
                             "description": "Full tutorial", "channelTitle": "Maker",
                             "publishedAt": "2026-08-15T09:00:00Z", "channelId": "ch1"}}]}
        vids = {"items": [{"id": "v1", "statistics": {"viewCount": "12000", "likeCount": "300", "commentCount": "45"},
                           "contentDetails": {"duration": "PT12M", "caption": "true"}}]}
        http = FakeHttpClient()
        http.add("https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&order=relevance&maxResults=5&q=print+on+demand&key=K",
                 json.dumps(search))
        http.add("https://www.googleapis.com/youtube/v3/videos?part=statistics,contentDetails&id=v1&key=K",
                 json.dumps(vids))
        docs, errors = YouTubeDataCollector(http, api_key="K", policy=policy()).collect("print on demand", 5)
        self.assertEqual(errors, [])
        d = docs[0]
        self.assertEqual(d.url, "https://www.youtube.com/watch?v=v1")
        self.assertEqual(d.engagement["views"], 12000.0)
        self.assertTrue(d.meta["captions_available"])
        self.assertIn("not collected", d.meta["transcript_note"])


RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Tutoring income report</title><link>https://blog.example.com/tutoring</link>
<description>I tutor math online, here are numbers.</description><pubDate>Sat, 19 Sep 2026 08:00:00 +0000</pubDate>
<guid>g1</guid></item>
<item><title>Unrelated recipe</title><link>https://blog.example.com/cake</link>
<description>chocolate</description></item></channel></rss>"""

ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Etsy shop month 3</title><link rel="alternate" href="https://shop.example.com/m3"/>
<summary>Revenue and lessons</summary><published>2026-09-10T07:00:00Z</published><id>e1</id>
<author><name>crafter</name></author></entry></feed>"""


class RssTests(unittest.TestCase):
    def test_rss2_query_filter_and_etag(self):
        http = FakeHttpClient()
        http.add("https://blog.example.com/feed.xml", RSS, headers={"etag": "\"v1\""})
        docs, errors = RssFeedCollector(http, feed_urls=("https://blog.example.com/feed.xml",),
                                        policy=policy()).collect("tutoring income", 10)
        self.assertEqual(errors, [])
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].url, "https://blog.example.com/tutoring")
        self.assertEqual(docs[0].rights, RightsClass.RSS_FEED)
        self.assertEqual(docs[0].etag, "\"v1\"")
        self.assertIsNotNone(docs[0].published_at)

    def test_atom_feed(self):
        http = FakeHttpClient()
        http.add("https://shop.example.com/atom.xml", ATOM)
        docs, _ = RssFeedCollector(http, feed_urls=("https://shop.example.com/atom.xml",),
                                   policy=policy()).collect("etsy", 10)
        self.assertEqual(docs[0].author, "crafter")
        self.assertEqual(docs[0].url, "https://shop.example.com/m3")

    def test_304_not_modified_yields_nothing(self):
        http = FakeHttpClient()
        http.add("https://blog.example.com/feed.xml", b"", status=304, headers={"etag": "\"v1\""})
        docs, _ = RssFeedCollector(http, feed_urls=("https://blog.example.com/feed.xml",),
                                   policy=policy()).collect("tutoring", 10)
        self.assertEqual(docs, [])


class PublicWebTests(unittest.TestCase):
    def test_robots_disallow_blocks_fetch(self):
        http = FakeHttpClient()
        http.add("https://site.example.com/robots.txt", "User-agent: *\nDisallow: /articles\n")
        robots = RobotsCache(http, policy())
        c = PublicWebCollector(http, robots=robots, policy=policy())
        doc, err = c.fetch_page("https://site.example.com/articles/side-hustle")
        self.assertIsNone(doc)
        self.assertEqual(err.reason, "robots_disallows")
        self.assertEqual(len(http.requests), 1)  # only robots.txt was fetched

    def test_allowed_page_excerpt_and_canonical(self):
        http = FakeHttpClient()
        http.add("https://site.example.com/robots.txt", "", status=404)
        body = ("<html><head><title>My hustle</title>"
                "<link rel=\"canonical\" href=\"https://site.example.com/canonical\"></head>"
                "<body><script>var x=1;</script><p>" + "step by step " * 400 + "</p></body></html>")
        http.add("https://site.example.com/page", body, headers={"etag": "\"p9\""})
        robots = RobotsCache(http, policy())
        c = PublicWebCollector(http, robots=robots, policy=policy())
        doc, err = c.fetch_page("https://site.example.com/page")
        self.assertIsNone(err)
        self.assertEqual(doc.url, "https://site.example.com/canonical")
        self.assertEqual(doc.rights, RightsClass.PUBLIC_PAGE)
        self.assertLessEqual(len(doc.text), 2000)
        self.assertNotIn("var x=1", doc.text)
        self.assertEqual(doc.etag, "\"p9\"")

    def test_domain_allowlist(self):
        http = FakeHttpClient()
        c = PublicWebCollector(http, robots=RobotsCache(http, policy()), policy=policy(),
                               allowed_domains=("good.example.com",))
        doc, err = c.fetch_page("https://evil.example.com/x")
        self.assertEqual(err.reason, "domain_not_allowed")

    def test_robots_unreachable_fails_closed(self):
        http = FakeHttpClient()
        http.add_error("https://down.example.com/robots.txt", HttpError("u", 500, "boom"))
        c = PublicWebCollector(http, robots=RobotsCache(http, policy()), policy=policy())
        doc, err = c.fetch_page("https://down.example.com/x")
        self.assertEqual(err.reason, "robots_unreachable_denied_fail_closed")


class RateLimitTests(unittest.TestCase):
    def test_human_speed_pacing_between_requests(self):
        clock = Clock()
        sleeps = Sleeps(clock)
        http = FakeHttpClient(clock=clock)
        url1 = "https://hn.algolia.com/api/v1/search?query=a&tags=story&hitsPerPage=1"
        http.add(url1, json.dumps({"hits": []}))
        http.add(url1, json.dumps({"hits": []}))
        limiter = HostRateLimiter(policy(), clock=clock)
        c = HackerNewsCollector(http, policy=policy(), limiter=limiter, sleeper=sleeps, clock=clock)
        c.collect("a", 1)
        clock.advance(0.5)
        c.collect("a", 1)
        self.assertTrue(any(abs(w - 1.5) < 1e-6 for w in sleeps.waits))

    def test_circuit_opens_after_repeated_failures(self):
        clock = Clock()
        sleeps = Sleeps(clock)
        http = FakeHttpClient(clock=clock)
        url = "https://hn.algolia.com/api/v1/search?query=a&tags=story&hitsPerPage=1"
        for _ in range(10):
            http.add_error(url, HttpError(url, 500, "broken"))
        limiter = HostRateLimiter(policy(), clock=clock, circuit_failure_threshold=3)
        c = HackerNewsCollector(http, policy=policy(), limiter=limiter, sleeper=sleeps, clock=clock)
        c.collect("a", 1)
        self.assertTrue(limiter.circuit_open("hn.algolia.com"))
        docs, errors = c.collect("a", 1)
        self.assertEqual(errors[0].reason, "circuit_open")


class ComplianceTests(unittest.TestCase):
    def test_prohibited_platforms_rejected_loudly(self):
        for platform in ("tiktok_unofficial", "instagram_login", "pinterest_scraper", "discord_selfbot"):
            with self.assertRaises(ValueError) as ctx:
                ensure_legal_platform(platform)
            self.assertIn("prohibited", str(ctx.exception))

    def test_non_http_url_rejected(self):
        from app.modules.m18_side_hustle_scraper.lane_models import RawDocument
        with self.assertRaises(ValueError):
            RawDocument(url="file:///etc/passwd", platform="x", kind=SourceKind.PUBLIC_WEB,
                        rights=RightsClass.PUBLIC_PAGE)


if __name__ == "__main__":
    unittest.main()
