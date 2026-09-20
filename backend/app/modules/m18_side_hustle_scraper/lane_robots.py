"""robots.txt enforcement for public-page collection.

PublicWebCollector asks this cache before every page fetch. Robots documents
are fetched through the same polite HttpClient and cached per origin. Fail
closed by default: if robots cannot be retrieved and the policy does not
explicitly allow proceeding, the page is skipped and the decision is recorded
as data.
"""
from __future__ import annotations

import urllib.robotparser
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Optional
from urllib.parse import urlsplit

from .lane_http import HttpClient, HttpError
from .lane_models import FetchPolicy, RobotsVerdict, utcnow


@dataclass
class _CacheEntry:
    parser: Optional[urllib.robotparser.RobotFileParser]
    fetched_at: datetime
    reachable: bool


class RobotsCache:
    def __init__(
        self,
        http: HttpClient,
        policy: FetchPolicy | None = None,
        *,
        clock: Callable[[], datetime] = utcnow,
    ):
        self.http = http
        self.policy = policy or FetchPolicy()
        self._clock = clock
        self._cache: Dict[str, _CacheEntry] = {}

    @staticmethod
    def robots_url_for(url: str) -> str:
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}/robots.txt"

    def _load(self, origin: str, robots_url: str) -> _CacheEntry:
        now = self._clock()
        cached = self._cache.get(origin)
        if cached and (now - cached.fetched_at).total_seconds() < self.policy.robots_ttl_seconds:
            return cached
        try:
            resp = self.http.fetch(robots_url, policy=self.policy)
            parser = urllib.robotparser.RobotFileParser(robots_url)
            if resp.status == 404:
                parser.parse([])  # no robots file: everything allowed
                entry = _CacheEntry(parser=parser, fetched_at=now, reachable=True)
            else:
                parser.parse(resp.text().splitlines())
                entry = _CacheEntry(parser=parser, fetched_at=now, reachable=True)
        except HttpError as exc:
            if exc.status == 404:
                parser = urllib.robotparser.RobotFileParser(robots_url)
                parser.parse([])
                entry = _CacheEntry(parser=parser, fetched_at=now, reachable=True)
            else:
                entry = _CacheEntry(parser=None, fetched_at=now, reachable=False)
        self._cache[origin] = entry
        return entry

    def check(self, url: str) -> RobotsVerdict:
        if not self.policy.respect_robots_txt:
            return RobotsVerdict(url=url, allowed=True, reason="robots_disabled_by_policy", robots_url="")
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        robots_url = self.robots_url_for(url)
        entry = self._load(origin, robots_url)
        if not entry.reachable or entry.parser is None:
            allowed = self.policy.allow_on_robots_error
            return RobotsVerdict(
                url=url,
                allowed=allowed,
                reason="robots_unreachable_" + ("allowed_by_policy" if allowed else "denied_fail_closed"),
                robots_url=robots_url,
            )
        allowed = entry.parser.can_fetch(self.policy.user_agent, url)
        return RobotsVerdict(
            url=url,
            allowed=allowed,
            reason="robots_allows" if allowed else "robots_disallows",
            robots_url=robots_url,
        )

    def crawl_delay(self, url: str) -> Optional[float]:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        entry = self._cache.get(origin)
        if entry and entry.parser:
            delay = entry.parser.crawl_delay(self.policy.user_agent)
            return float(delay) if delay is not None else None
        return None
