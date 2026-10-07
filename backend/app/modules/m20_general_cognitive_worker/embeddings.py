"""Embedding providers for GCW memory retrieval (spec 4.2.3).

Production Atlas embeds with text-embedding-3-large or a local Ollama model;
those live behind the EmbeddingProvider protocol and are injected by the
integrator. The DeterministicEmbedding fallback below is dependency-free,
stable across runs, and good enough for offline tests and development.
No network at import or in the fallback.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol, runtime_checkable

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Minimal contract every embedding backend must satisfy."""

    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...


class DeterministicEmbedding:
    """Hashing-trick bag-of-words embedder. Deterministic, offline, free."""

    def __init__(self, dimensions: int = 256) -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be >= 8")
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        tokens = tokenize(text)
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    if any(type(value) not in (int, float) or not math.isfinite(value) for vector in (a, b) for value in vector):
        raise ValueError("finite numeric vector components required, not bool")
    scale_a = max(abs(value) for value in a)
    scale_b = max(abs(value) for value in b)
    if scale_a == 0 or scale_b == 0:
        return 0.0
    aa = [value / scale_a for value in a]
    bb = [value / scale_b for value in b]
    dot = math.fsum(x * y for x, y in zip(aa, bb))
    norm_a = math.sqrt(math.fsum(x * x for x in aa))
    norm_b = math.sqrt(math.fsum(y * y for y in bb))
    return max(-1.0, min(1.0, dot / norm_a / norm_b))
