"""Small injectable JSON transport with bounded retries and response limits."""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class TransportError(RuntimeError):
    pass


_SENSITIVE_QUERY_KEYS = {"api_key", "apikey", "key", "token", "access_token"}


def safe_url(url: str) -> str:
    """Redact credentials before URLs reach exceptions or logs."""
    parts = urlsplit(url)
    query = [(key, "[REDACTED]" if key.lower() in _SENSITIVE_QUERY_KEYS else value) for key, value in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class JsonTransport(Protocol):
    def request(self, method: str, url: str, *, body: Mapping[str, Any] | None = None, headers: Mapping[str, str] | None = None) -> Any: ...


@dataclass(slots=True)
class UrllibJsonTransport:
    timeout_seconds: float = 20.0
    attempts: int = 3
    max_response_bytes: int = 10_000_000
    user_agent: str = "Atlas-OpportunityDiscovery/1.0"

    def request(self, method: str, url: str, *, body: Mapping[str, Any] | None = None, headers: Mapping[str, str] | None = None) -> Any:
        payload = None if body is None else json.dumps(body, separators=(",", ":")).encode()
        request_headers = {"Accept": "application/json", "User-Agent": self.user_agent, **(headers or {})}
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
        last: Exception | None = None
        for attempt in range(self.attempts):
            try:
                req = Request(url, data=payload, method=method, headers=request_headers)
                with urlopen(req, timeout=self.timeout_seconds) as response:
                    length = response.headers.get("Content-Length")
                    if length and int(length) > self.max_response_bytes:
                        raise TransportError("response exceeds configured limit")
                    raw = response.read(self.max_response_bytes + 1)
                    if len(raw) > self.max_response_bytes:
                        raise TransportError("response exceeds configured limit")
                    return json.loads(raw)
            except HTTPError as exc:
                last = exc
                if exc.code not in {429, 500, 502, 503, 504}:
                    break
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                last = exc
            if attempt + 1 < self.attempts:
                time.sleep(min(4.0, 0.25 * (2**attempt)) + random.random() * 0.1)
        raise TransportError(f"{method} {safe_url(url)} failed after {self.attempts} attempt(s)") from last
