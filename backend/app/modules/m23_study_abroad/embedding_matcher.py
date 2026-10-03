"""Local embedding matcher for essay-topic discovery (scoped, unaudited).

Calls a loopback-only OpenAI-compatible /v1/embeddings server (e.g. llama.cpp --embedding with a real
sentence-embedding GGUF) and ranks student evidence by cosine similarity to an essay prompt. There is no
hashing or token trick here: if no real embedding server answers, `rank` returns None and callers must label
the result as the token-overlap FALLBACK. Matching only orders the student's own evidence; it writes no prose.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
import urllib.request
from urllib.parse import urlparse

EMBEDDING = "embedding_local_model"
FALLBACK = "token_overlap_fallback"


def _loopback(url: str | None) -> bool:
    return bool(url) and (urlparse(url).hostname or "") in {"127.0.0.1", "localhost", "::1"}


def cosine(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


class LocalEmbeddingMatcher:
    def __init__(self, base_url: str, model: str, timeout: float = 10.0):
        if not _loopback(base_url):
            raise ValueError("embedding server must be on loopback (local, free, private)")
        self.base_url, self.model, self.timeout = base_url.rstrip("/"), model, timeout

    def _fetch(self, texts: list[str]) -> bytes:
        body = json.dumps({"model": self.model, "input": texts}).encode()
        req = urllib.request.Request(self.base_url + "/embeddings", data=body,
                                     headers={"content-type": "application/json"})

        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                raise OSError("embedding endpoint redirected; refusing to follow")
        # ProxyHandler({}) = no env proxies (HTTP_PROXY must never carry the prompt/evidence off-box)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        deadline = time.monotonic() + self.timeout
        with opener.open(req, timeout=self.timeout) as r:  # noqa: S310 loopback only
            buf = b""
            while chunk := r.read1(16384):
                buf += chunk
                if len(buf) > 8_000_000 or time.monotonic() > deadline:
                    raise OSError("embedding response too large or too slow")
        return buf

    @staticmethod
    def _valid(data, n: int) -> list[list[float]] | None:
        """Exactly n items, indices a permutation of 0..n-1, equal-length non-empty vectors of finite real numbers."""
        if not isinstance(data, list) or len(data) != n:
            return None
        by_index: dict[int, list] = {}
        for d in data:
            i, v = d.get("index") if isinstance(d, dict) else None, d.get("embedding") if isinstance(d, dict) else None
            if type(i) is not int or not 0 <= i < n or i in by_index or not isinstance(v, list) or not v:
                return None
            if any(type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 1e6 for x in v):
                return None
            by_index[i] = v
        vecs = [by_index[i] for i in range(n)]
        return vecs if len({len(v) for v in vecs}) == 1 else None

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        """Loopback only, no redirects, no env proxy; the whole call (connect, headers, body) is capped at
        self.timeout seconds by a worker thread. Anything malformed returns None so callers label the fallback."""
        box: dict = {}

        def work():
            try:
                box["raw"] = self._fetch(texts)
            except Exception:  # noqa: BLE001
                pass
        t = threading.Thread(target=work, daemon=True)
        t.start()
        t.join(self.timeout)
        if t.is_alive() or "raw" not in box:
            return None
        try:
            return self._valid(json.loads(box["raw"].decode()).get("data"), len(texts))
        except Exception:  # noqa: BLE001
            return None

    def rank(self, query: str, docs: list[str]) -> list[float] | None:
        """Cosine score of each doc against query, or None when no real, well-formed embedding was obtained."""
        if not docs:
            return []
        vecs = self.embed([query, *docs])
        if vecs is None:
            return None
        try:
            scores = [round(cosine(vecs[0], v), 4) for v in vecs[1:]]
        except Exception:  # noqa: BLE001
            return None
        return scores if all(math.isfinite(x) for x in scores) else None


def matcher_from_env(env: dict | None = None) -> LocalEmbeddingMatcher | None:
    e = os.environ if env is None else env
    url, model = e.get("INSTINCT_EMBED_URL"), e.get("INSTINCT_EMBED_MODEL")
    if not url or not model or not _loopback(url):
        return None
    return LocalEmbeddingMatcher(url, model)
