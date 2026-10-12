"""c30.public_http - shared bounded live-fetch helper for PUBLIC HTTPS sources.

Used by v2 units that are explicitly scoped to live public data (e.g.
c37.live_watch, m01 competition_live). This helper is the ONLY network path
those units may use, and it is fail-closed:

- HTTPS only in production (allow_http exists solely for hermetic tests).
- The caller supplies the exact allowed host set per call context; any other
  host, userinfo, non-default port or non-HTTPS scheme refuses.
- robots.txt is honored per host (cached); a disallow refuses the fetch.
- Per-host minimum interval throttling; the clock and sleeper are injectable
  so tests stay hermetic.
- Conditional GET with an ETag/Last-Modified cache supplied by the caller;
  304 responses return not_modified without a body.
- Response bodies are capped (MAX_BYTES) and read at most cap+1 bytes.

Stdlib only. No credentials, no cookies, no auth headers, no redirects to
off-list hosts (redirects are followed by urllib but the FINAL url is
re-validated against the allow-list before the body is accepted).
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
import urllib.robotparser
from urllib.parse import urlsplit

PREFIX = "HTTP"
MAX_BYTES = 2000000
TIMEOUT_S = 20
USER_AGENT = "atlas-public-monitor/1.0 (public-data research; respectful)"
MIN_INTERVAL_S = 1.0


def _err(code, detail=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, code, (":" + detail) if detail else ""))


def validate_url(url, allowed_hosts, allow_http=False):
    """Return (scheme, host, port) or refuse. Host matching is exact."""
    if not isinstance(url, str) or len(url) > 2048:
        _err("BAD_URL")
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        _err("BAD_URL")
    if parts.scheme != "https" and not (allow_http and parts.scheme == "http"):
        _err("NONHTTPS")
    if not host or host not in allowed_hosts:
        _err("HOST_NOT_ALLOWED")
    if parts.username or parts.password:
        _err("CREDENTIALS_IN_URL")
    if not allow_http and port not in (None, 443, 80):
        _err("BAD_URL")
    return parts.scheme, host, port


class Fetcher:
    """Bounded polite fetcher over an explicit host allow-list."""

    def __init__(self, allowed_hosts, min_interval_s=MIN_INTERVAL_S, cache=None,
                 honor_robots=True, allow_http=False, clock=None, sleeper=None,
                 max_bytes=MAX_BYTES, timeout_s=TIMEOUT_S):
        hosts = list(allowed_hosts) if isinstance(allowed_hosts, (list, tuple, set)) else None
        if not hosts or any(not isinstance(h, str) or not h for h in hosts):
            _err("HOSTS")
        self.allowed_hosts = frozenset(hosts)
        self.min_interval = float(min_interval_s)
        self.cache = cache if cache is not None else {}
        self.honor_robots = bool(honor_robots)
        self.allow_http = bool(allow_http)
        self.clock = clock or time.monotonic
        self.sleeper = sleeper or time.sleep
        self.max_bytes = int(max_bytes)
        self.timeout = int(timeout_s)
        self._last_hit = {}
        self._robots = {}
        self.fetches = 0
        self.bytes_read = 0

    def _throttle(self, host):
        last = self._last_hit.get(host)
        now = self.clock()
        if last is not None and now - last < self.min_interval:
            self.sleeper(self.min_interval - (now - last))
        self._last_hit[host] = self.clock()

    def _robots_allows(self, url, opener):
        scheme, host, _ = validate_url(url, self.allowed_hosts, self.allow_http)
        if host in self._robots:
            rp = self._robots[host]
        else:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = "%s://%s/robots.txt" % (scheme, urlsplit(url).netloc)
            try:
                req = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
                with opener.open(req, timeout=self.timeout) as resp:
                    body = resp.read(65536).decode("utf-8", "replace")
                rp.parse(body.splitlines())
            except Exception:
                rp.parse([])  # no robots.txt: allowed by convention
            self._robots[host] = rp
        return rp.can_fetch(USER_AGENT, url)

    def fetch(self, url, opener=None):
        """GET url; returns a bounded result dict. Refuses on policy violations."""
        validate_url(url, self.allowed_hosts, self.allow_http)
        opener = opener or urllib.request.build_opener()
        if self.honor_robots and not self._robots_allows(url, opener):
            _err("ROBOTS_DISALLOW")
        host = urlsplit(url).hostname
        self._throttle(host)
        headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        cached = self.cache.get(url)
        if cached:
            if cached.get("etag"):
                headers["If-None-Match"] = cached["etag"]
            if cached.get("last_modified"):
                headers["If-Modified-Since"] = cached["last_modified"]
        req = urllib.request.Request(url, headers=headers)
        try:
            with opener.open(req, timeout=self.timeout) as resp:
                status = getattr(resp, "status", 200)
                final_url = resp.geturl()
                validate_url(final_url, self.allowed_hosts, self.allow_http)
                body = resp.read(self.max_bytes + 1)
                if len(body) > self.max_bytes:
                    _err("TOO_LARGE")
                etag = resp.headers.get("ETag")
                last_mod = resp.headers.get("Last-Modified")
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return {"url": url, "status": 304, "not_modified": True, "body": b"",
                        "etag": cached.get("etag"), "last_modified": cached.get("last_modified")}
            _err("STATUS:%d" % e.code)
        except urllib.error.URLError as e:
            _err("FETCH_FAILED", type(e.reason).__name__ if getattr(e, "reason", None) else "unknown")
        self.fetches += 1
        self.bytes_read += len(body)
        self.cache[url] = {"etag": etag, "last_modified": last_mod}
        return {"url": final_url, "status": status, "not_modified": False, "body": body,
                "etag": etag, "last_modified": last_mod}
