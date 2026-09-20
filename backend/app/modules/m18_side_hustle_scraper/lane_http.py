"""HTTP transport with legal-collection behaviour baked in.

The production client uses urllib (stdlib). Tests inject FakeHttpClient, so no
collector ever touches the network during unit tests. Conditional requests
(ETag / If-Modified-Since) are first-class: freshness monitoring depends on
304 handling, and polite collection depends on not re-downloading unchanged
feeds.
"""
from __future__ import annotations

import gzip
import urllib.error
import urllib.request
from datetime import datetime
from typing import Callable, Mapping, Optional, Protocol

from .lane_models import FetchPolicy, HttpResponseRecord, utcnow


class HttpError(Exception):
    def __init__(self, url: str, status: Optional[int], reason: str, retry_after: Optional[float] = None):
        super().__init__(f"HTTP {status} for {url}: {reason}")
        self.url = url
        self.status = status
        self.reason = reason
        self.retry_after = retry_after


class HttpClient(Protocol):
    def fetch(
        self,
        url: str,
        *,
        policy: FetchPolicy,
        headers: Optional[Mapping[str, str]] = None,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
    ) -> HttpResponseRecord:
        ...


class UrllibHttpClient:
    """Production client: bounded size, gzip, redirects, conditional GET."""

    def __init__(self, clock: Callable[[], datetime] = utcnow):
        self._clock = clock

    def fetch(
        self,
        url: str,
        *,
        policy: FetchPolicy,
        headers: Optional[Mapping[str, str]] = None,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
    ) -> HttpResponseRecord:
        req_headers: dict[str, str] = {
            "User-Agent": policy.user_agent,
            "Accept": "application/json, application/atom+xml, application/rss+xml, text/xml, text/html;q=0.8, */*;q=0.5",
            "Accept-Encoding": "gzip",
        }
        if headers:
            req_headers.update(headers)
        if etag:
            req_headers["If-None-Match"] = etag
        if last_modified:
            req_headers["If-Modified-Since"] = last_modified

        class _RedirectLimiter(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, hdrs, newurl):  # noqa: N802 (stdlib signature)
                if getattr(req, "_redirect_count", 0) >= policy.max_redirects:
                    raise urllib.error.HTTPError(url, 508, "redirect limit exceeded", hdrs, fp)
                req._redirect_count = getattr(req, "_redirect_count", 0) + 1
                return super().redirect_request(req, fp, code, msg, hdrs, newurl)

        opener = urllib.request.build_opener(_RedirectLimiter())
        request = urllib.request.Request(url, headers=req_headers)
        try:
            with opener.open(request, timeout=policy.timeout_seconds) as resp:
                status = getattr(resp, "status", resp.getcode())
                raw = resp.read(policy.max_bytes + 1)
                truncated = len(raw) > policy.max_bytes
                raw = raw[: policy.max_bytes]
                if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                    raw = gzip.decompress(raw)
                final_url = resp.geturl() or url
                return HttpResponseRecord(
                    url=final_url,
                    status=status,
                    headers={k.lower(): v for k, v in resp.headers.items()},
                    body=raw,
                    fetched_at=self._clock(),
                    truncated=truncated,
                )
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                return HttpResponseRecord(
                    url=url,
                    status=304,
                    headers={k.lower(): v for k, v in (exc.headers or {}).items()},
                    body=b"",
                    fetched_at=self._clock(),
                    not_modified=True,
                )
            retry_after = None
            if exc.headers and exc.headers.get("Retry-After"):
                try:
                    retry_after = float(exc.headers["Retry-After"])
                except ValueError:
                    retry_after = None
            raise HttpError(url, exc.code, exc.reason or "http error", retry_after) from exc
        except urllib.error.URLError as exc:
            raise HttpError(url, None, str(exc.reason)) from exc


class FakeHttpClient:
    """Test double: maps URL -> queued responses, records every request."""

    def __init__(self, clock: Callable[[], datetime] = utcnow):
        self.routes: dict[str, list] = {}
        self.requests: list[dict] = []
        self._clock = clock

    def add(self, url: str, body: bytes | str = b"", status: int = 200, headers: Optional[Mapping[str, str]] = None) -> None:
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.routes.setdefault(url, []).append((status, dict(headers or {}), body))

    def add_error(self, url: str, error: Exception) -> None:
        self.routes.setdefault(url, []).append(error)

    def fetch(self, url, *, policy, headers=None, etag=None, last_modified=None) -> HttpResponseRecord:
        self.requests.append({"url": url, "headers": dict(headers or {}), "etag": etag, "last_modified": last_modified})
        queue = self.routes.get(url)
        if not queue:
            raise HttpError(url, 404, "no fake route registered")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        status, hdrs, body = item
        if etag and hdrs.get("etag") == etag:
            return HttpResponseRecord(url=url, status=304, headers=hdrs, body=b"", fetched_at=self._clock(), not_modified=True)
        return HttpResponseRecord(url=url, status=status, headers={k.lower(): v for k, v in hdrs.items()}, body=body,
                                fetched_at=self._clock(), not_modified=(status == 304))
