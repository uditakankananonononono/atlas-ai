"""Legal source collectors for Module 18.

Every collector here uses a legal channel only:
- Reddit public JSON listings (documented, requires an honest identifying UA)
- YouTube Data API v3 (official, key-injected)
- Hacker News via the official Algolia API
- dev.to public articles API
- published RSS/Atom feeds
- robots-permitted public pages (link + bounded excerpt)

Each collector is synchronous and side-effect free apart from HTTP through the
injected client; the FastAPI/Celery layer runs them in an executor. All pacing
goes through HostRateLimiter so collection stays at human speed and honors
Retry-After. Failures are returned as CollectionError records, never raised
past the collector boundary.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable, Iterable, Mapping, Optional, Protocol, Sequence
from urllib.parse import quote_plus, urlsplit

from .lane_http import HttpClient, HttpError
from .lane_models import (
    CollectionError,
    FetchPolicy,
    PROHIBITED_PLATFORMS,
    PUBLIC_PAGE_EXCERPT_CHARS,
    RawDocument,
    RightsClass,
    SourceKind,
    utcnow,
)
from .lane_rate_limit import HostRateLimiter
from .lane_robots import RobotsCache

Sleeper = Callable[[float], None]
Clock = Callable[[], datetime]


def _no_sleep(_seconds: float) -> None:
    return None


class Collector(Protocol):
    platform: str

    def collect(self, query: str, limit: int) -> tuple[list[RawDocument], list[CollectionError]]:
        ...


def ensure_legal_platform(platform: str) -> None:
    """Loud rejection for channels the compliance decision refuses."""
    if platform in PROHIBITED_PLATFORMS:
        raise ValueError(f"prohibited collection channel {platform!r}: {PROHIBITED_PLATFORMS[platform]}")


def _parse_dt(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    text = str(value).strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


class BaseCollector:
    platform: str = "base"

    def __init__(
        self,
        http: HttpClient,
        *,
        policy: FetchPolicy | None = None,
        limiter: HostRateLimiter | None = None,
        sleeper: Sleeper | None = None,
        clock: Clock = utcnow,
    ):
        self.http = http
        self.policy = policy or FetchPolicy()
        self.limiter = limiter or HostRateLimiter(self.policy, clock=clock)
        self.sleeper = sleeper or _no_sleep
        self.clock = clock

    def _get(self, url: str, *, headers: Optional[Mapping[str, str]] = None,
             etag: Optional[str] = None, last_modified: Optional[str] = None) -> tuple[Optional[Any], Optional[CollectionError]]:
        """One paced, retried GET. Returns (response, None) or (None, error)."""
        host = urlsplit(url).netloc
        for attempt in range(self.policy.max_retries + 1):
            if self.limiter.circuit_open(host):
                return None, CollectionError(source=self.platform, url=url, reason="circuit_open")
            wait = self.limiter.check(host)
            if wait > 0:
                self.sleeper(wait)
            self.limiter.record_request(host)
            try:
                resp = self.http.fetch(url, policy=self.policy, headers=headers, etag=etag, last_modified=last_modified)
                self.limiter.record_success(host)
                return resp, None
            except HttpError as exc:
                self.limiter.record_failure(host, (exc.reason, exc.status))
                if exc.retry_after is not None:
                    self.limiter.honor_retry_after(host, exc.retry_after)
                retriable = exc.status in (429, 500, 502, 503, 504) or exc.status is None
                if not retriable or attempt >= self.policy.max_retries:
                    return None, CollectionError(source=self.platform, url=url, reason=exc.reason, status=exc.status)
                backoff = min(self.policy.backoff_max_seconds, self.policy.backoff_base_seconds * (2 ** attempt))
                self.sleeper(max(backoff, exc.retry_after or 0.0))
        return None, CollectionError(source=self.platform, url=url, reason="retries_exhausted")


class RedditJsonCollector(BaseCollector):
    """Documented public JSON listings. Reddit's API rules require a unique,
    honest User-Agent; a browser-spoofing UA is rejected up front."""

    platform = "reddit"
    BASE = "https://www.reddit.com"
    _BROWSER_UA = re.compile(r"Mozilla/|Chrome/|Safari/", re.IGNORECASE)

    def __init__(self, *args: Any, subreddits: Sequence[str] = ("sidehustle", "Entrepreneur", "smallbusiness", "passive_income"), **kwargs: Any):
        super().__init__(*args, **kwargs)
        if self._BROWSER_UA.search(self.policy.user_agent):
            raise ValueError("reddit public API requires an identifying User-Agent, not a browser spoof")
        self.subreddits = tuple(subreddits)

    def collect(self, query: str, limit: int) -> tuple[list[RawDocument], list[CollectionError]]:
        docs: list[RawDocument] = []
        errors: list[CollectionError] = []
        per_sub = max(1, limit // max(1, len(self.subreddits)))
        for sub in self.subreddits:
            url = (f"{self.BASE}/r/{sub}/search.json?q={quote_plus(query)}"
                   f"&restrict_sr=1&sort=relevance&t=year&limit={min(per_sub, 100)}")
            resp, err = self._get(url)
            if err:
                errors.append(err)
                continue
            try:
                payload = json.loads(resp.text())
                children = payload["data"]["children"]
            except (ValueError, KeyError, TypeError) as exc:
                errors.append(CollectionError(source=self.platform, url=url, reason=f"malformed_payload:{exc}"))
                continue
            for child in children:
                data = child.get("data", {})
                permalink = data.get("permalink") or ""
                post_url = f"{self.BASE}{permalink}" if permalink else data.get("url", "")
                if not post_url:
                    continue
                docs.append(RawDocument(
                    url=post_url,
                    platform=self.platform,
                    kind=SourceKind.REDDIT_JSON,
                    rights=RightsClass.OFFICIAL_API,
                    title=(data.get("title") or "").strip(),
                    text=(data.get("selftext") or "").strip(),
                    author=data.get("author"),
                    published_at=_parse_dt(data.get("created_utc")),
                    retrieved_at=resp.fetched_at,
                    http_status=resp.status,
                    engagement={"score": float(data.get("score") or 0), "comments": float(data.get("num_comments") or 0)},
                    meta={"subreddit": sub, "flair": data.get("link_flair_text")},
                ))
        return docs[:limit], errors


class HackerNewsCollector(BaseCollector):
    """Official HN Algolia API - free, documented, no key."""

    platform = "hacker_news"
    SEARCH = "https://hn.algolia.com/api/v1/search"

    def collect(self, query: str, limit: int) -> tuple[list[RawDocument], list[CollectionError]]:
        url = f"{self.SEARCH}?query={quote_plus(query)}&tags=story&hitsPerPage={min(limit, 100)}"
        resp, err = self._get(url)
        if err:
            return [], [err]
        try:
            payload = json.loads(resp.text())
            hits = payload["hits"]
        except (ValueError, KeyError, TypeError) as exc:
            return [], [CollectionError(source=self.platform, url=url, reason=f"malformed_payload:{exc}")]
        docs: list[RawDocument] = []
        for hit in hits:
            story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            if not story_url.startswith("http"):
                continue
            docs.append(RawDocument(
                url=story_url,
                platform=self.platform,
                kind=SourceKind.HACKER_NEWS,
                rights=RightsClass.OFFICIAL_API,
                title=(hit.get("title") or "").strip(),
                text=(hit.get("story_text") or "").strip(),
                author=hit.get("author"),
                published_at=_parse_dt(hit.get("created_at_i")),
                retrieved_at=resp.fetched_at,
                http_status=resp.status,
                engagement={"score": float(hit.get("points") or 0), "comments": float(hit.get("num_comments") or 0)},
                meta={"hn_id": hit.get("objectID"), "thread": f"https://news.ycombinator.com/item?id={hit.get('objectID')}"},
            ))
        return docs, []


class DevToCollector(BaseCollector):
    """dev.to public articles API (documented, keyless read endpoints)."""

    platform = "dev_to"
    API = "https://dev.to/api/articles"

    def collect(self, query: str, limit: int) -> tuple[list[RawDocument], list[CollectionError]]:
        tag = re.sub(r"[^a-z0-9]", "", query.lower().split()[0]) if query.strip() else ""
        if not tag:
            return [], [CollectionError(source=self.platform, url=self.API, reason="empty_query")]
        url = f"{self.API}?tag={tag}&per_page={min(limit, 100)}&state=rising"
        resp, err = self._get(url)
        if err:
            return [], [err]
        try:
            articles = json.loads(resp.text())
            if not isinstance(articles, list):
                raise TypeError("expected list payload")
        except (ValueError, TypeError) as exc:
            return [], [CollectionError(source=self.platform, url=url, reason=f"malformed_payload:{exc}")]
        docs: list[RawDocument] = []
        for art in articles:
            art_url = art.get("url") or ""
            if not art_url.startswith("http"):
                continue
            docs.append(RawDocument(
                url=art_url,
                platform=self.platform,
                kind=SourceKind.DEV_TO,
                rights=RightsClass.OFFICIAL_API,
                title=(art.get("title") or "").strip(),
                text=(art.get("description") or "").strip(),
                author=(art.get("user") or {}).get("username"),
                published_at=_parse_dt(art.get("published_at")),
                retrieved_at=resp.fetched_at,
                http_status=resp.status,
                engagement={
                    "score": float(art.get("positive_reactions_count") or 0),
                    "comments": float(art.get("comments_count") or 0),
                },
                meta={"tags": art.get("tag_list") or [], "reading_time_minutes": art.get("reading_time_minutes")},
            ))
        return docs, []


class YouTubeDataCollector(BaseCollector):
    """Official YouTube Data API v3. Metadata, descriptions and statistics
    only. Caption *download* needs channel-owner OAuth, so transcripts are
    never scraped; caption availability is recorded as a flag instead."""

    platform = "youtube"
    SEARCH = "https://www.googleapis.com/youtube/v3/search"
    VIDEOS = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self, *args: Any, api_key: str, **kwargs: Any):
        if not api_key or not api_key.strip():
            raise ValueError("YouTubeDataCollector requires an official API key; scraping youtube.com is not supported")
        super().__init__(*args, **kwargs)
        self._api_key = api_key

    def collect(self, query: str, limit: int) -> tuple[list[RawDocument], list[CollectionError]]:
        errors: list[CollectionError] = []
        search_url = (f"{self.SEARCH}?part=snippet&type=video&order=relevance"
                      f"&maxResults={min(limit, 50)}&q={quote_plus(query)}&key={self._api_key}")
        resp, err = self._get(search_url)
        if err:
            return [], [err]
        try:
            items = json.loads(resp.text())["items"]
        except (ValueError, KeyError, TypeError) as exc:
            return [], [CollectionError(source=self.platform, url=search_url, reason=f"malformed_payload:{exc}")]
        ids = [((it.get("id") or {}).get("videoId")) for it in items]
        ids = [i for i in ids if i]
        stats: dict[str, Mapping[str, Any]] = {}
        details: dict[str, Mapping[str, Any]] = {}
        if ids:
            vids_url = (f"{self.VIDEOS}?part=statistics,contentDetails&id={','.join(ids)}&key={self._api_key}")
            vresp, verr = self._get(vids_url)
            if verr:
                errors.append(verr)
            else:
                try:
                    for v in json.loads(vresp.text()).get("items", []):
                        stats[v["id"]] = v.get("statistics", {})
                        details[v["id"]] = v.get("contentDetails", {})
                except (ValueError, KeyError, TypeError) as exc:
                    errors.append(CollectionError(source=self.platform, url=vids_url, reason=f"malformed_payload:{exc}"))
        docs: list[RawDocument] = []
        for it in items:
            vid = (it.get("id") or {}).get("videoId")
            snippet = it.get("snippet") or {}
            if not vid:
                continue
            st = stats.get(vid, {})
            docs.append(RawDocument(
                url=f"https://www.youtube.com/watch?v={vid}",
                platform=self.platform,
                kind=SourceKind.YOUTUBE_DATA_API,
                rights=RightsClass.OFFICIAL_API,
                title=(snippet.get("title") or "").strip(),
                text=(snippet.get("description") or "").strip(),
                author=snippet.get("channelTitle"),
                published_at=_parse_dt(snippet.get("publishedAt")),
                retrieved_at=resp.fetched_at,
                http_status=resp.status,
                engagement={
                    "views": float(st.get("viewCount") or 0),
                    "likes": float(st.get("likeCount") or 0),
                    "comments": float(st.get("commentCount") or 0),
                },
                meta={
                    "video_id": vid,
                    "channel_id": snippet.get("channelId"),
                    "duration": (details.get(vid) or {}).get("duration"),
                    "captions_available": bool((details.get(vid) or {}).get("caption") == "true"),
                    "transcript_note": "caption download requires channel-owner OAuth; not collected",
                },
            ))
        return docs, errors


class RssFeedCollector(BaseCollector):
    """Generic RSS 2.0 / Atom collector for feeds the user or registry names."""

    platform = "rss"

    def __init__(self, *args: Any, feed_urls: Sequence[str], **kwargs: Any):
        if not feed_urls:
            raise ValueError("RssFeedCollector requires at least one feed URL")
        super().__init__(*args, **kwargs)
        self.feed_urls = tuple(feed_urls)

    def collect(self, query: str, limit: int) -> tuple[list[RawDocument], list[CollectionError]]:
        docs: list[RawDocument] = []
        errors: list[CollectionError] = []
        terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
        for feed_url in self.feed_urls:
            resp, err = self._get(feed_url, headers={"Accept": "application/rss+xml, application/atom+xml, text/xml"})
            if err:
                errors.append(err)
                continue
            if resp.not_modified:
                continue
            try:
                root = ET.fromstring(resp.text())
            except ET.ParseError as exc:
                errors.append(CollectionError(source=self.platform, url=feed_url, reason=f"feed_parse:{exc}", status=resp.status))
                continue
            for entry in self._entries(root):
                text = entry["text"].lower()
                if terms and not any(t in text or t in entry["title"].lower() for t in terms):
                    continue
                docs.append(RawDocument(
                    url=entry["link"],
                    platform=self.platform,
                    kind=SourceKind.RSS,
                    rights=RightsClass.RSS_FEED,
                    title=entry["title"],
                    text=entry["text"],
                    author=entry.get("author"),
                    published_at=_parse_dt(entry.get("published")),
                    retrieved_at=resp.fetched_at,
                    etag=resp.headers.get("etag"),
                    last_modified=resp.headers.get("last-modified"),
                    http_status=resp.status,
                    meta={"feed_url": feed_url, "guid": entry.get("guid")},
                ))
        return docs[:limit], errors

    @staticmethod
    def _entries(root: ET.Element) -> Iterable[dict[str, Any]]:
        def text_of(elem: Optional[ET.Element]) -> str:
            if elem is None:
                return ""
            return "".join(elem.itertext()).strip()

        # RSS 2.0
        for item in root.iter("item"):
            link = text_of(item.find("link"))
            if not link:
                continue
            yield {
                "title": text_of(item.find("title")),
                "link": link,
                "text": text_of(item.find("description")),
                "author": text_of(item.find("author")) or text_of(item.find("{http://purl.org/dc/elements/1.1/}creator")),
                "published": text_of(item.find("pubDate")),
                "guid": text_of(item.find("guid")),
            }
        # Atom
        ns = "{http://www.w3.org/2005/Atom}"
        for entry in root.iter(f"{ns}entry"):
            link = ""
            for link_el in entry.findall(f"{ns}link"):
                if link_el.get("rel") in (None, "alternate") and link_el.get("href"):
                    link = link_el.get("href", "")
                    break
            if not link:
                continue
            author_el = entry.find(f"{ns}author/{ns}name")
            yield {
                "title": text_of(entry.find(f"{ns}title")),
                "link": link,
                "text": text_of(entry.find(f"{ns}summary")) or text_of(entry.find(f"{ns}content")),
                "author": text_of(author_el),
                "published": text_of(entry.find(f"{ns}published")) or text_of(entry.find(f"{ns}updated")),
                "guid": text_of(entry.find(f"{ns}id")),
            }


class _TextExtractor(HTMLParser):
    """Minimal visible-text extractor; skips script/style/noscript entirely."""

    SKIP = {"script", "style", "noscript", "template", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._chunks: list[str] = []
        self.canonical: Optional[str] = None
        self.title: str = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag in self.SKIP:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "link":
            attr = dict(attrs)
            if (attr.get("rel") or "").lower() == "canonical" and attr.get("href"):
                self.canonical = attr["href"]

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._skip_depth == 0 and not self._in_title:
            chunk = data.strip()
            if chunk:
                self._chunks.append(chunk)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._chunks)).strip()


class PublicWebCollector(BaseCollector):
    """Robots-enforced public page fetch. Stores link + bounded excerpt only."""

    platform = "public_web"

    def __init__(self, *args: Any, robots: RobotsCache, allowed_domains: Optional[Sequence[str]] = None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.robots = robots
        self.allowed_domains = {d.lower() for d in allowed_domains} if allowed_domains else None

    def fetch_page(self, url: str) -> tuple[Optional[RawDocument], Optional[CollectionError]]:
        host = urlsplit(url).netloc.lower()
        if self.allowed_domains is not None and not any(host == d or host.endswith("." + d) for d in self.allowed_domains):
            return None, CollectionError(source=self.platform, url=url, reason="domain_not_allowed")
        verdict = self.robots.check(url)
        if not verdict.allowed:
            return None, CollectionError(source=self.platform, url=url, reason=verdict.reason)
        delay = self.robots.crawl_delay(url)
        if delay:
            self.sleeper(max(0.0, delay - self.limiter.check(host)))
        resp, err = self._get(url)
        if err:
            return None, err
        extractor = _TextExtractor()
        try:
            extractor.feed(resp.text())
        except Exception as exc:  # malformed HTML should not kill a batch
            return None, CollectionError(source=self.platform, url=url, reason=f"html_parse:{exc}", status=resp.status)
        excerpt = extractor.text()[:PUBLIC_PAGE_EXCERPT_CHARS]
        return RawDocument(
            url=extractor.canonical or resp.url or url,
            platform=self.platform,
            kind=SourceKind.PUBLIC_WEB,
            rights=RightsClass.PUBLIC_PAGE,
            title=extractor.title.strip(),
            text=excerpt,
            retrieved_at=resp.fetched_at,
            etag=resp.headers.get("etag"),
            last_modified=resp.headers.get("last-modified"),
            http_status=resp.status,
            meta={"fetched_url": url, "robots": verdict.reason, "truncated_to_excerpt": True},
        ), None

    def collect(self, query: str, limit: int) -> tuple[list[RawDocument], list[CollectionError]]:
        # Public-web collection is URL-driven (URLs come from discovery elsewhere);
        # there is no legal generic "search the whole web" endpoint here.
        return [], [CollectionError(source=self.platform, url="", reason="url_driven_only_use_fetch_page")]

class PinterestApiCollector(BaseCollector):
    """Pinterest API v5 pin search. Requires an owner-supplied OAuth access token."""
    platform = "pinterest"
    SEARCH = "https://api.pinterest.com/v5/search/pins"
    def __init__(self, *args: Any, access_token: str, **kwargs: Any):
        if not access_token.strip(): raise ValueError("PinterestApiCollector requires an official API v5 access token")
        super().__init__(*args, **kwargs); self._token=access_token.strip()
    def collect(self, query: str, limit: int) -> tuple[list[RawDocument], list[CollectionError]]:
        url=f"{self.SEARCH}?query={quote_plus(query)}&page_size={min(limit,100)}"
        resp,err=self._get(url,headers={"Authorization":f"Bearer {self._token}"})
        if err:return [],[err]
        try:items=json.loads(resp.text()).get("items",[])
        except (ValueError,TypeError) as exc:return [],[CollectionError(source=self.platform,url=url,reason=f"malformed_payload:{exc}")]
        docs=[]
        for item in items[:limit]:
            pid=str(item.get("id","")).strip()
            if not pid:continue
            title=str(item.get("title") or item.get("description") or "Pinterest pin")
            docs.append(RawDocument(id=f"pinterest:{pid}",url=f"https://www.pinterest.com/pin/{pid}/",platform=self.platform,kind=SourceKind.PINTEREST_API,rights=RightsClass.OFFICIAL_API,title=title,text=" ".join(filter(None,[str(item.get("title",'')),str(item.get("description",'')),str(item.get("alt_text",''))])),author=str(item.get("board_owner",{}).get("username",'')) or None,retrieved_at=self.clock(),engagement={"saves":float(item.get("pin_metrics",{}).get("lifetime_metrics",{}).get("SAVE",0) or 0)},http_status=resp.status,meta={"official_api":"pinterest_v5"}))
        return docs,[]

class XApiCollector(BaseCollector):
    """X API v2 recent search. X read access is optional and commonly paid."""
    platform = "x"
    SEARCH = "https://api.x.com/2/tweets/search/recent"
    def __init__(self,*args:Any,bearer_token:str,**kwargs:Any):
        if not bearer_token.strip():raise ValueError("XApiCollector requires an official X API v2 bearer token")
        super().__init__(*args,**kwargs);self._token=bearer_token.strip()
    def collect(self,query:str,limit:int)->tuple[list[RawDocument],list[CollectionError]]:
        url=f"{self.SEARCH}?query={quote_plus(query + ' -is:retweet')}&max_results={max(10,min(limit,100))}&tweet.fields=created_at,public_metrics,author_id"
        resp,err=self._get(url,headers={"Authorization":f"Bearer {self._token}"})
        if err:return [],[err]
        try:items=json.loads(resp.text()).get("data",[])
        except (ValueError,TypeError) as exc:return [],[CollectionError(source=self.platform,url=url,reason=f"malformed_payload:{exc}")]
        docs=[]
        for item in items[:limit]:
            tid=str(item.get("id","")).strip();text=str(item.get("text","")).strip()
            if not tid or not text:continue
            metrics=item.get("public_metrics",{})
            docs.append(RawDocument(id=f"x:{tid}",url=f"https://x.com/i/web/status/{tid}",platform=self.platform,kind=SourceKind.X_API,rights=RightsClass.OFFICIAL_API,title=text[:160],text=text,author=str(item.get("author_id",'')) or None,published_at=_parse_dt(item.get("created_at")),retrieved_at=self.clock(),engagement={"likes":float(metrics.get("like_count",0)),"reposts":float(metrics.get("retweet_count",0)),"replies":float(metrics.get("reply_count",0))},http_status=resp.status,meta={"official_api":"x_v2"}))
        return docs,[]

class InstagramGraphCollector(BaseCollector):
    """Official Instagram oEmbed lookup for user-provided public post/Reel links only."""
    platform="instagram"
    OEMBED="https://graph.facebook.com/v22.0/instagram_oembed"
    URL_RE=re.compile(r"https://(?:www\.)?instagram\.com/(?:p|reel)/[^\s?#]+/?")
    def __init__(self,*args:Any,access_token:str,**kwargs:Any):
        if not access_token.strip():raise ValueError("InstagramGraphCollector requires a Meta Graph API access token")
        super().__init__(*args,**kwargs);self._token=access_token.strip()
    def collect(self,query:str,limit:int)->tuple[list[RawDocument],list[CollectionError]]:
        links=[]
        for link in self.URL_RE.findall(query):
            if link not in links:links.append(link)
        if not links:return [],[CollectionError(source=self.platform,url="",reason="user_provided_instagram_link_required")]
        docs=[];errors=[]
        for link in links[:limit]:
            url=f"{self.OEMBED}?url={quote_plus(link)}&access_token={quote_plus(self._token)}"
            resp,err=self._get(url)
            if err:errors.append(err);continue
            try:item=json.loads(resp.text())
            except (ValueError,TypeError) as exc:errors.append(CollectionError(source=self.platform,url=link,reason=f"malformed_payload:{exc}"));continue
            media_id=str(item.get("media_id") or sha256_text(link)[:20])
            text=str(item.get("title") or "Instagram post")
            docs.append(RawDocument(id=f"instagram:{media_id}",url=link,platform=self.platform,kind=SourceKind.INSTAGRAM_GRAPH_API,rights=RightsClass.OFFICIAL_API,title=text[:160],text=text,author=str(item.get("author_name",'')) or None,retrieved_at=self.clock(),http_status=resp.status,meta={"official_api":"instagram_oembed","user_provided_link":True}))
        return docs,errors
