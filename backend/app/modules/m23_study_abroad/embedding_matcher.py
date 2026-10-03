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
    def __init__(self, base_url: str, model: str, timeout: float = 20.0):
        if not _loopback(base_url):
            raise ValueError("embedding server must be on loopback (local, free, private)")
        self.base_url, self.model, self.timeout = base_url.rstrip("/"), model, timeout

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        body = json.dumps({"model": self.model, "input": texts}).encode()
        req = urllib.request.Request(self.base_url + "/embeddings", data=body,
                                     headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310 loopback only
                data = json.load(r)["data"]
            vecs = [d["embedding"] for d in sorted(data, key=lambda d: d["index"])]
            return vecs if len(vecs) == len(texts) and all(vecs) else None
        except Exception:  # unreachable / malformed -> caller labels fallback
            return None

    def rank(self, query: str, docs: list[str]) -> list[float] | None:
        """Cosine score of each doc against query, or None when no real embedding was obtained."""
        if not docs:
            return []
        vecs = self.embed([query, *docs])
        if vecs is None:
            return None
        return [round(cosine(vecs[0], v), 4) for v in vecs[1:]]


def matcher_from_env(env: dict | None = None) -> LocalEmbeddingMatcher | None:
    e = os.environ if env is None else env
    url, model = e.get("INSTINCT_EMBED_URL"), e.get("INSTINCT_EMBED_MODEL")
    if not url or not model or not _loopback(url):
        return None
    return LocalEmbeddingMatcher(url, model)
