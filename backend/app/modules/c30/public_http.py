"""c30.public_http - shared bounded live-fetch helper for PUBLIC HTTPS sources.

Used by v2 units explicitly scoped to live public data (c37.live_watch, m01
competition_live). This helper is the ONLY network path those units may use,
and it is fail-closed on every axis:

- HTTPS only in production (allow_http exists SOLELY for hermetic tests and
  also relaxes the public-IP check; production callers never set it).
- Exact host allow-list; any other host, userinfo or non-default port refuses.
- Public-IP validation: the host's resolved addresses must ALL be globally
  routable (loopback/private/link-local/reserved/multicast refuse). DNS is
  validated at fetch time; a rebind between validation and connect is a
  named residual.
- Redirects are NEVER followed implicitly: urllib's redirect handler is
  disabled, every 3xx Location target is re-validated against the allow-list
  AND the public-IP check before it is contacted, and the chain is capped.
  An off-list redirect target refuses BEFORE any request to it is made.
- robots.txt is fail-CLOSED: only an explicit 404/410 (no robots file) means
  "no restrictions"; any other failure (401/403/429/5xx/DNS/timeout) DENIES
  the fetch. A disallow rule denies. Results are cached per host.
- Per-host minimum interval throttling; clock and sleeper are injectable.
- Conditional GET with a caller-visible ETag/Last-Modified cache; 304
  returns not_modified without a body.
- Response bodies are capped (read at most cap+1 bytes).

Stdlib only. No credentials, no cookies, no auth headers.
"""
from __future__ import annotations

import ipaddress
import socket
import time
import urllib.error
import urllib.request
import urllib.robotparser
from urllib.parse import urljoin, urlsplit

PREFIX = "HTTP"
MAX_BYTES = 2000000
MAX_REDIRECTS = 5
TIMEOUT_S = 20
USER_AGENT = "atlas-public-monitor/1.0 (public-data research; respectful)"
MIN_INTERVAL_S = 1.0
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})


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


def resolve_public(host, port, allow_http=False):
    """Resolve host and require EVERY returned address to be globally
    routable. Skipped only under the allow_http hermetic-test seam."""
    if allow_http:
        return []
    try:
        infos = socket.getaddrinfo(host, port or 443, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, OSError):
        _err("DNS", host)
    addrs = sorted({info[4][0] for info in infos})
    if not addrs:
        _err("DNS", host)
    for addr in addrs:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            _err("DNS", host)
        if not ip.is_global:
            _err("NONPUBLIC_IP", host)
    return addrs


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Disable implicit redirect following: every 3xx becomes an HTTPError
    so the caller can validate the target BEFORE contacting it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Fetcher:
    """Bounded polite fetcher over an explicit host allow-list."""

    def __init__(self, allowed_hosts, min_interval_s=MIN_INTERVAL_S, cache=None,
                 honor_robots=True, allow_http=False, clock=None, sleeper=None,
                 max_bytes=MAX_BYTES, timeout_s=TIMEOUT_S, max_redirects=MAX_REDIRECTS):
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
        self.max_redirects = int(max_redirects)
        self._last_hit = {}
        self._robots = {}
        self.fetches = 0
        self.bytes_read = 0
        self._opener = urllib.request.build_opener(_NoRedirect)

    # -- internals ---------------------------------------------------------

    def _throttle(self, host):
        last = self._last_hit.get(host)
        now = self.clock()
        if last is not None and now - last < self.min_interval:
            self.sleeper(self.min_interval - (now - last))
        self._last_hit[host] = self.clock()

    def _request(self, url, headers, redirects_left):
        """One validated GET; manual redirect handling. Every hop (initial
        URL and every Location target) is allow-list + public-IP validated
        BEFORE it is contacted."""
        _scheme, host, port = validate_url(url, self.allowed_hosts, self.allow_http)
        resolve_public(host, port, self.allow_http)
        req = urllib.request.Request(url, headers=headers)
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                status = getattr(resp, "status", 200)
                final_url = resp.geturl()
                # defense in depth: re-validate whatever the server reports
                validate_url(final_url, self.allowed_hosts, self.allow_http)
                body = resp.read(self.max_bytes + 1)
                if len(body) > self.max_bytes:
                    _err("TOO_LARGE")
                return {"url": final_url, "status": status, "body": body,
                        "etag": resp.headers.get("ETag"),
                        "last_modified": resp.headers.get("Last-Modified")}
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return {"url": url, "status": 304, "body": b"", "etag": None,
                        "last_modified": None}
            if e.code in _REDIRECT_CODES:
                if redirects_left <= 0:
                    _err("REDIRECTS")
                location = e.headers.get("Location")
                if not location:
                    _err("REDIRECT")
                target = urljoin(url, location)
                # validate the target BEFORE any request is made to it;
                # the recursive call performs the allow-list + IP checks
                validate_url(target, self.allowed_hosts, self.allow_http)
                return self._request(target, headers, redirects_left - 1)
            _err("STATUS:%d" % e.code)
        except urllib.error.URLError as e:
            _err("FETCH_FAILED", type(e.reason).__name__ if getattr(e, "reason", None) else "unknown")
        except (socket.timeout, TimeoutError, OSError):
            _err("FETCH_FAILED", "os-error")

    def _robots_allows(self, url):
        _scheme, host, _port = validate_url(url, self.allowed_hosts, self.allow_http)
        if host in self._robots:
            verdict = self._robots[host]
            return verdict.can_fetch(USER_AGENT, url) if verdict is not None else False
        netloc = urlsplit(url).netloc
        scheme = urlsplit(url).scheme
        robots_url = "%s://%s/robots.txt" % (scheme, netloc)
        try:
            result = self._request(robots_url, {"User-Agent": USER_AGENT},
                                   self.max_redirects)
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(result["body"].decode("utf-8", "replace").splitlines())
            self._robots[host] = rp
        except ValueError as e:
            code = str(e)
            if code in ("HTTP_REFUSED_STATUS:404", "HTTP_REFUSED_STATUS:410"):
                rp = urllib.robotparser.RobotFileParser()
                rp.parse([])  # explicit absence: no restrictions
                self._robots[host] = rp
            elif code.startswith(("HTTP_REFUSED_NONPUBLIC_IP", "HTTP_REFUSED_NONHTTPS",
                                  "HTTP_REFUSED_HOST_NOT_ALLOWED",
                                  "HTTP_REFUSED_CREDENTIALS_IN_URL",
                                  "HTTP_REFUSED_BAD_URL")):
                raise  # policy refusals are not robots failures: propagate
            else:
                # FAIL CLOSED: 401/403/429/5xx/DNS/timeout/parse failures all
                # deny; cache the denial for this fetcher's lifetime.
                self._robots[host] = None
                return False
        return self._robots[host].can_fetch(USER_AGENT, url)

    # -- public API --------------------------------------------------------

    def fetch(self, url, opener=None):
        """GET url; returns a bounded result dict. Refuses on any policy
        violation. `opener` is accepted for backward compatibility and
        ignored: redirects must never be followed implicitly, so the
        fetcher's own no-redirect opener is always used."""
        validate_url(url, self.allowed_hosts, self.allow_http)
        if self.honor_robots and not self._robots_allows(url):
            _err("ROBOTS")
        host = urlsplit(url).hostname
        self._throttle(host)
        headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        cached = self.cache.get(url)
        if cached:
            if cached.get("etag"):
                headers["If-None-Match"] = cached["etag"]
            if cached.get("last_modified"):
                headers["If-Modified-Since"] = cached["last_modified"]
        result = self._request(url, headers, self.max_redirects)
        if result["status"] == 304:
            return {"url": url, "status": 304, "not_modified": True, "body": b"",
                    "etag": cached.get("etag"), "last_modified": cached.get("last_modified")}
        self.fetches += 1
        self.bytes_read += len(result["body"])
        self.cache[url] = {"etag": result["etag"], "last_modified": result["last_modified"]}
        return {"url": result["url"], "status": result["status"], "not_modified": False,
                "body": result["body"], "etag": result["etag"],
                "last_modified": result["last_modified"]}
