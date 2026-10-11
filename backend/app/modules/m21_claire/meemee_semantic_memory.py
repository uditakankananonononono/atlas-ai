"""Offline semantic memory, ported from meemee `semantic_memory.py` (C4 meemee-merge).

Semantics preserved from meemee@50e7605: deterministic local feature-hashing
embeddings (blake2b, signed log-scaled counts, L2-normalized), overflow-safe
cosine similarity, and embedding-space binding. The MiniLM/ONNX path is NOT
ported (external weight download, non-hermetic); the hashing embedder needs no
network, model file or paid API, matching Atlas's free-first rule. Adds the
in-memory owner-scoped store Claire queries.
"""
from __future__ import annotations

import hashlib
import math
import re
import threading
import uuid
from collections import Counter
from itertools import pairwise
from typing import Any, Protocol

TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    dimensions: int
    space_id: str
    def embed(self, text: str) -> list[float]: ...


class HashingEmbedder:
    """Deterministic local feature-hashing embedding with no external service."""
    def __init__(self, dimensions: int = 256):
        if dimensions < 32:
            raise ValueError("dimensions must be at least 32")
        self.dimensions = dimensions
        self.space_id = f"lexical-hashing-blake2b-v1:{dimensions}"

    def embed(self, text: str) -> list[float]:
        values = [0.0] * self.dimensions
        tokens = TOKEN.findall(text.lower())
        features = tokens + [f"{a}_{b}" for a, b in pairwise(tokens)]
        for feature, count in Counter(features).items():
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self.dimensions
            sign = 1.0 if digest[0] & 1 else -1.0
            values[index] += sign * (1.0 + math.log(count))
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("cannot compare vectors of different dimensions")
    if not all(math.isfinite(v) for v in (*left, *right)):
        raise ValueError("vectors must be finite")
    # Scale before norms/products so finite large encoders do not overflow.
    left_scale = max((abs(v) for v in left), default=0.0)
    right_scale = max((abs(v) for v in right), default=0.0)
    if not left_scale or not right_scale:
        return 0.0
    a = [v / left_scale for v in left]
    b = [v / right_scale for v in right]
    score = sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))
    return max(-1.0, min(1.0, score))


class SemanticMemory:
    """Owner-scoped in-memory vector store bound to one embedding space."""

    def __init__(self, embedder: Embedder):
        self.embedder = embedder
        self.space_id = embedder.space_id
        self.lock = threading.RLock()
        self._rows: list[dict[str, Any]] = []

    def add(self, owner: str, text: str, metadata: dict[str, Any] | None = None) -> str:
        if not owner.strip() or not text.strip():
            raise ValueError("owner and text are required")
        ident = uuid.uuid4().hex
        vector = self.embedder.embed(text)
        with self.lock:
            self._rows.append({"id": ident, "owner": owner, "text": text,
                               "vector": vector, "metadata": dict(metadata or {})})
        return ident

    def add_with_vector(self, owner: str, text: str, vector: list[float], *, space_id: str) -> str:
        if space_id != self.space_id:
            raise ValueError(f"embedding space mismatch: store is {self.space_id}, got {space_id}")
        if len(vector) != self.embedder.dimensions:
            raise ValueError("vector has incorrect dimensions")
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in vector):
            raise ValueError("vector must contain finite numbers")
        if not owner.strip() or not text.strip():
            raise ValueError("owner and text are required")
        ident = uuid.uuid4().hex
        with self.lock:
            self._rows.append({"id": ident, "owner": owner, "text": text,
                               "vector": [float(v) for v in vector], "metadata": {}})
        return ident

    def search(self, owner: str, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        if limit < 1 or not query.strip():
            return []
        qv = self.embedder.embed(query)
        with self.lock:
            rows = [row for row in self._rows if row["owner"] == owner]
        scored = [(cosine(qv, row["vector"]), row) for row in rows]
        scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
        return [{"id": row["id"], "owner": row["owner"], "text": row["text"],
                 "metadata": dict(row["metadata"]), "score": round(score, 6)}
                for score, row in scored[:limit]]
