"""Corpus-trained distributional embeddings and text semantic ranking (1964/1965).

No downloads, pretrained claims, hashing, supplied vectors, or synonym table.
Learns positive pointwise mutual information from word contexts, then a truncated
SVD latent space. Meaning is limited to distributional evidence in this corpus.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

import numpy as np

# Absolute cosine tolerance, independent of NumPy/BLAS epsilon implementation.
SCORE_TIE_TOLERANCE = 1e-12

_MAX_DOCS = 2000
_MAX_TOKENS = 50000
_MAX_TEXT = 20000
_MAX_VOCAB = 512  # dense SVD memory/CPU guard for local PCs
_TOKEN = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in [{low},{high}]")
    return value


def _tokens(text):
    if not isinstance(text, str) or not text.strip() or len(text) > _MAX_TEXT:
        raise ValueError("text must be a nonempty string of at most 20000 characters")
    return _TOKEN.findall(unicodedata.normalize("NFKC", text).casefold())


def _normalized(rows):
    norms = np.linalg.norm(rows, axis=-1, keepdims=True)
    return np.divide(rows, norms, out=np.zeros_like(rows), where=norms > 0)


class CorpusEmbeddings:
    """Fitted word/context model with read-only vectors; fit() builds a new model."""

    def __init__(self, vocabulary, vectors, corpus_sha256, window, dimensions):
        # Constructor accepts only validated data through fit/from_dict below.
        self._vocabulary = tuple(vocabulary)
        self._lookup = {word: i for i, word in enumerate(vocabulary)}
        self._vectors = np.array(vectors, dtype=np.float64, copy=True)
        self._vectors.flags.writeable = False
        self._corpus_sha256 = corpus_sha256
        self._window = window
        self._dimensions = dimensions

    @classmethod
    def fit(cls, corpus, *, dimensions=32, window=2, min_count=1, max_vocab=512):
        _integer(dimensions, "dimensions", 1, 128)
        _integer(window, "window", 1, 10)
        _integer(min_count, "min_count", 1, _MAX_TOKENS)
        _integer(max_vocab, "max_vocab", 2, _MAX_VOCAB)
        if not isinstance(corpus, (list, tuple)) or not 1 <= len(corpus) <= _MAX_DOCS:
            raise ValueError("corpus must contain 1..2000 texts")
        documents = []
        total = 0
        for text in corpus:
            words = _tokens(text)
            total += len(words)
            if total > _MAX_TOKENS:
                raise ValueError("corpus exceeds 50000 tokens")
            documents.append(words)
        counts = Counter(word for doc in documents for word in doc)
        vocabulary = sorted(
            sorted((w for w in counts if counts[w] >= min_count),
                   key=lambda w: (-counts[w], w))[:max_vocab]
        )
        if len(vocabulary) < 2:
            raise ValueError("at least two retained words required")
        lookup = {word: i for i, word in enumerate(vocabulary)}
        cooccurrence = np.zeros((len(vocabulary), len(vocabulary)), dtype=np.float64)
        for words in documents:
            for i, word in enumerate(words):
                if word not in lookup:
                    continue
                for j in range(max(0, i - window), min(len(words), i + window + 1)):
                    other = words[j]
                    if j != i and other in lookup:
                        cooccurrence[lookup[word], lookup[other]] += 1.0 / abs(i - j)
        mass = float(cooccurrence.sum())
        if mass == 0:
            raise ValueError("corpus has no retained within-document context pairs")
        denominator = cooccurrence.sum(axis=1)[:, None] * cooccurrence.sum(axis=0)[None, :]
        ratio = np.divide(cooccurrence * mass, denominator,
                          out=np.zeros_like(cooccurrence), where=denominator > 0)
        ppmi = np.zeros_like(ratio)
        positive = ratio > 1
        ppmi[positive] = np.log(ratio[positive])
        u, singular, _ = np.linalg.svd(ppmi, full_matrices=False)
        rank = int(np.sum(singular > max(ppmi.shape) * np.finfo(float).eps * singular[0]))
        if rank == 0:
            raise ValueError("corpus contains no positive mutual information")
        width = min(dimensions, rank)
        vectors = u[:, :width] * np.sqrt(singular[:width])
        # Canonical signs make serialized output stable for a fixed SVD result.
        for col in range(width):
            pivot = int(np.argmax(np.abs(vectors[:, col])))
            if vectors[pivot, col] < 0:
                vectors[:, col] *= -1
        corpus_hash = hashlib.sha256(json.dumps(documents, ensure_ascii=False,
                                                  separators=(",", ":")).encode()).hexdigest()
        return cls(vocabulary, _normalized(vectors), corpus_hash, window, width)

    @property
    def dimensions(self):
        return self._dimensions

    @property
    def vocabulary(self):
        return self._vocabulary

    def encode(self, text):
        words = _tokens(text)
        known = [self._lookup[word] for word in words if word in self._lookup]
        vector = np.zeros(self.dimensions) if not known else _normalized(
            self._vectors[known].mean(axis=0))
        return {"vector": vector.tolist(), "known_tokens": len(known),
                "total_tokens": len(words), "out_of_vocabulary": sorted(set(words) - self._lookup.keys())}

    def word_similarity(self, first, second):
        a, b = self.encode(first), self.encode(second)
        if not a["known_tokens"] or not b["known_tokens"]:
            return None
        return float(np.clip(np.dot(a["vector"], b["vector"]), -1, 1))

    def to_dict(self):
        return {"format": "atlas.corpus_ppmi_svd.v1", "vocabulary": list(self.vocabulary),
                "vectors": self._vectors.tolist(), "dimensions": self.dimensions,
                "window": self._window, "corpus_sha256": self._corpus_sha256}

    @classmethod
    def from_dict(cls, state):
        if not isinstance(state, dict) or state.get("format") != "atlas.corpus_ppmi_svd.v1":
            raise ValueError("unsupported embedding format")
        dimensions = _integer(state.get("dimensions"), "dimensions", 1, 128)
        window = _integer(state.get("window"), "window", 1, 10)
        words = state.get("vocabulary")
        if (not isinstance(words, list) or not 2 <= len(words) <= _MAX_VOCAB
                or any(not isinstance(w, str) or len(w) > _MAX_TEXT
                       or _tokens(w) != [w] for w in words)
                or words != sorted(set(words))):
            raise ValueError("vocabulary must be sorted unique normalized words")
        digest = state.get("corpus_sha256")
        if not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
            raise ValueError("invalid corpus digest")
        rows = state.get("vectors")
        if (not isinstance(rows, list) or len(rows) != len(words)
                or any(not isinstance(row, list) or len(row) != dimensions for row in rows)
                or any(type(x) not in (float, int) or not -1.000001 <= x <= 1.000001
                       or not math.isfinite(x) for row in rows for x in row)):
            raise ValueError("vectors must be finite aligned normalized rows")
        vectors = np.array(rows, dtype=np.float64)
        norms = np.linalg.norm(vectors, axis=1)
        if not np.all((norms == 0) | np.isclose(norms, 1, rtol=1e-6, atol=1e-8)):
            raise ValueError("vectors must have unit or zero norm")
        return cls(words, vectors, digest, window, dimensions)


@dataclass(frozen=True)
class SemanticHit:
    id: str
    text: str
    score: float


def _rank_hits(hits):
    """Descending-score bands, lexicographic ids within each absolute-tie band.

    Each band includes scores <=1e-12 below its highest score (inclusive).
    Band anchors never move, so chained near-ties cannot merge distant scores.
    Raw scores remain unchanged; min_score filtering occurs before banding.
    """
    ordered = sorted(hits, key=lambda hit: (-hit.score, hit.id))
    ranked = []
    start = 0
    while start < len(ordered):
        anchor = ordered[start].score
        end = start + 1
        while end < len(ordered) and anchor - ordered[end].score <= SCORE_TIE_TOLERANCE:
            end += 1
        ranked.extend(sorted(ordered[start:end], key=lambda hit: hit.id))
        start = end
    return ranked


class CorpusSemanticSearch:
    """Text-to-text ranking in one fitted space. Unknown queries yield no hits.

    Scores are cosine similarities, not relevance probabilities. No fallback to
    string matching or artificial scores. The caller owns the corpus/documents.
    """

    def __init__(self, model, documents):
        if not isinstance(model, CorpusEmbeddings):
            raise ValueError("fitted CorpusEmbeddings model required")
        if not isinstance(documents, (list, tuple)) or not 1 <= len(documents) <= _MAX_DOCS:
            raise ValueError("documents must contain 1..2000 id/text objects")
        ids, entries, vectors = set(), [], []
        total = 0
        for document in documents:
            if not isinstance(document, dict):
                raise ValueError("document must be an object")
            identity = document.get("id")
            if not isinstance(identity, str) or not identity.strip() or len(identity) > 256 or identity in ids:
                raise ValueError("document ids must be nonempty, unique, at most 256 characters")
            encoded = model.encode(document.get("text"))
            total += encoded["total_tokens"]
            if total > _MAX_TOKENS:
                raise ValueError("indexed documents exceed 50000 tokens")
            ids.add(identity)
            entries.append((identity, document["text"]))
            vectors.append(encoded["vector"])
        self._model = model
        self._entries = tuple(entries)
        self._vectors = np.array(vectors, dtype=np.float64)
        self._vectors.flags.writeable = False

    def search(self, query, *, top_k=10, min_score=0.0):
        _integer(top_k, "top_k", 1, _MAX_DOCS)
        if type(min_score) not in (int, float) or not 0 <= min_score <= 1 or not math.isfinite(min_score):
            raise ValueError("min_score must be finite and in [0,1]")
        encoded = self._model.encode(query)
        if not encoded["known_tokens"]:
            return []
        scores = np.clip(self._vectors @ np.array(encoded["vector"]), -1, 1)
        hits = [SemanticHit(identity, text, float(score))
                for (identity, text), score in zip(self._entries, scores)
                if score > min_score]
        return _rank_hits(hits)[:top_k]


def run_corpus_semantics(method, data):
    """Opt-in dispatcher entry, deliberately separate from the legacy registry."""
    if method not in ("embeddings", "semantic_search") or not isinstance(data, dict):
        raise ValueError("method must be embeddings or semantic_search with object data")
    model = CorpusEmbeddings.fit(data.get("corpus"), dimensions=data.get("dimensions", 32),
                                window=data.get("window", 2), min_count=data.get("min_count", 1),
                                max_vocab=data.get("max_vocab", 512))
    if method == "embeddings":
        texts = data.get("texts")
        if not isinstance(texts, list) or not 1 <= len(texts) <= _MAX_DOCS:
            raise ValueError("texts must contain 1..2000 strings")
        encoded = [model.encode(text) for text in texts]
        if sum(item["total_tokens"] for item in encoded) > _MAX_TOKENS:
            raise ValueError("texts exceed 50000 tokens")
        result = {"embeddings": encoded}
    else:
        index = CorpusSemanticSearch(model, data.get("documents"))
        hits = index.search(data.get("query"), top_k=data.get("top_k", 10),
                            min_score=data.get("min_score", 0.0))
        coverage = model.encode(data.get("query"))
        result = {"hits": [hit.__dict__ for hit in hits],
                  "query_coverage": {key: value for key, value in coverage.items() if key != "vector"}}
    return {**result, "model": model.to_dict(), "algorithm": "corpus_ppmi_svd",
            "scope": "Corpus-trained distributional semantics only; no pretrained or general-language guarantee.",
            "status": "scoped_corpus_model", "external_calls": 0}
