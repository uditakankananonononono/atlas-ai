"""Live NLP stack for Opportunity Discovery (module 1).

This is the production path that replaces keyword/token scoring when the real
dependencies are present:

- spaCy named-entity recognition (``ATLAS_SPACY_MODEL``, default
  ``en_core_web_sm``) for entity tags,
- dateparser deadline normalization, anchored on deadline cue phrases and
  pinned to an explicit timezone (UTC unless the tenant says otherwise),
- embedding cosine similarity between opportunity and profile text.

Embedding backends, free first:

``fastembed`` (default)  in-process ONNX ``BAAI/bge-small-en-v1.5``; no server,
                         no key, no per-use cost. Weights download once from
                         Hugging Face and are cached (``ATLAS_FASTEMBED_CACHE``).
``ollama``               local Ollama server (``ATLAS_OLLAMA_URL``,
                         ``ATLAS_OLLAMA_EMBEDDING_MODEL``, default ``bge-m3``).
``openai``               bring-your-own-key; only used when explicitly chosen.
``token``                explicit opt-out: token-count cosine.

Honesty rules. Every stored opportunity records which engine produced its
match score and its deadline (``match_engine`` / ``deadline_engine``). The
token/regex path is only used when an optional dependency is missing, the
operator opted out, or the embedding backend failed for that item; the reason
is recorded instead of being hidden. ``describe()`` reports what is actually
loaded so the dashboard can show it.
"""
from __future__ import annotations

import math
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

TOKEN_ENGINE = "token-cosine"
REGEX_DEADLINE_ENGINE = "regex-formats"

#: spaCy labels that carry useful opportunity facets (host, place, event,
#: prize, eligible group). DATE/CARDINAL/etc. are handled by dateparser or
#: are noise as tags.
USEFUL_ENTITY_LABELS = frozenset({"ORG", "GPE", "LOC", "EVENT", "NORP", "PRODUCT", "WORK_OF_ART", "FAC", "MONEY"})
MAX_ENTITY_TAGS = 12

_DEADLINE_CUE_RE = re.compile(
    r"(deadline|due(?: date)?|apply by|apply before|applications? (?:close|closes|closing|due|open until)|"
    r"submissions? (?:close|closes|due)|submit by|register by|registration (?:closes|deadline)|closes on|last date|until)"
    r"\s*(?:is|on|:|-)?\s*",
    re.IGNORECASE,
)
_CUE_WINDOW = 60


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return 0.0 if not norm else dot / norm


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


class EmbeddingBackendError(RuntimeError):
    pass


_FASTEMBED_LOCK = threading.Lock()


@lru_cache(maxsize=4)
def _fastembed_model(model_name: str, cache_dir: str | None) -> Any:
    from fastembed import TextEmbedding  # optional dependency

    with _FASTEMBED_LOCK:
        return TextEmbedding(model_name=model_name, cache_dir=cache_dir)


class FastEmbedBackend:
    """Free in-process embeddings (ONNX Runtime, CPU)."""

    kind = "fastembed"

    def __init__(self, model: str | None = None, cache_dir: str | None = None) -> None:
        self.model = model or os.getenv("ATLAS_FASTEMBED_MODEL", "BAAI/bge-small-en-v1.5")
        self.cache_dir = cache_dir or os.getenv("ATLAS_FASTEMBED_CACHE") or None
        try:
            self._model = _fastembed_model(self.model, self.cache_dir)
        except ModuleNotFoundError as exc:
            raise EmbeddingBackendError("fastembed is not installed (pip install fastembed)") from exc
        except Exception as exc:  # download or ONNX load failure
            raise EmbeddingBackendError(f"fastembed model {self.model!r} could not load: {exc}") from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(x) for x in vector] for vector in self._model.embed(texts)]


class OllamaBackend:
    kind = "ollama"

    def __init__(self, base_url: str | None = None, model: str | None = None, client: httpx.Client | None = None) -> None:
        self.base_url = (base_url or os.getenv("ATLAS_OLLAMA_URL", "http://ollama:11434")).rstrip("/")
        self.model = model or os.getenv("ATLAS_OLLAMA_EMBEDDING_MODEL", "bge-m3")
        self._client = client

    def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._client or httpx.Client(timeout=300)
        try:
            response = client.post(f"{self.base_url}/api/embed", json={"model": self.model, "input": texts, "truncate": True})
        except httpx.HTTPError as exc:
            raise EmbeddingBackendError(f"Ollama unreachable at {self.base_url}: {exc.__class__.__name__}") from exc
        finally:
            if self._client is None:
                client.close()
        if response.is_error:
            raise EmbeddingBackendError(f"Ollama embeddings failed ({response.status_code})")
        return response.json()["embeddings"]


class OpenAIBackend:
    """Bring-your-own-key. Never selected by default."""

    kind = "openai"

    def __init__(self, api_key: str | None = None, model: str | None = None, client: httpx.Client | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise EmbeddingBackendError("OPENAI_API_KEY is not configured")
        self.model = model or os.getenv("ATLAS_OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
        self._client = client

    def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._client or httpx.Client(timeout=120)
        try:
            response = client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts, "dimensions": 1024},
            )
        except httpx.HTTPError as exc:
            raise EmbeddingBackendError(f"OpenAI embeddings unreachable: {exc.__class__.__name__}") from exc
        finally:
            if self._client is None:
                client.close()
        if response.is_error:
            raise EmbeddingBackendError(f"OpenAI embeddings failed ({response.status_code})")
        return [item["embedding"] for item in sorted(response.json()["data"], key=lambda item: item["index"])]


class LiveEmbeddingMatcher:
    """EmbeddingMatcher backed by a real embedding model.

    Similarity is cosine mapped to [0, 1]. Profile vectors are cached because a
    scan scores many opportunities against one profile.
    """

    def __init__(self, backend: Any) -> None:
        self.backend = backend
        self.engine = f"embedding:{backend.kind}:{backend.model}"
        self._profile_cache: dict[str, list[float]] = {}

    def _profile_vector(self, profile_text: str) -> list[float]:
        vector = self._profile_cache.get(profile_text)
        if vector is None:
            vector = self.backend.embed([profile_text])[0]
            if len(self._profile_cache) > 256:
                self._profile_cache.clear()
            self._profile_cache[profile_text] = vector
        return vector

    def similarity(self, opportunity_text: str, profile_text: str) -> float:
        profile_vector = self._profile_vector(profile_text)
        opportunity_vector = self.backend.embed([opportunity_text])[0]
        return _clamp01(_cosine(opportunity_vector, profile_vector))


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class LiveNormalizer:
    """spaCy entities plus dateparser deadlines.

    ``nlp`` is an already-loaded spaCy pipeline. Deadlines are only taken from
    text next to a deadline cue ("apply by", "applications close", ...), so a
    posting date or event date is not mistaken for the deadline. Past dates
    relative to ``now`` are ignored when a future candidate exists.
    """

    def __init__(self, nlp: Any, *, timezone_name: str = "UTC", now: Callable[[], datetime] | None = None) -> None:
        self.nlp = nlp
        self.model = getattr(nlp, "meta", {}).get("name", "spacy")
        try:
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone {timezone_name!r}") from exc
        self.timezone_name = timezone_name
        self._now = now or (lambda: datetime.now(timezone.utc))
        lang = getattr(nlp, "meta", {}).get("lang", "en")
        self.entity_engine = f"spacy:{lang}_{self.model}" if not str(self.model).startswith(lang) else f"spacy:{self.model}"
        self.deadline_engine = f"dateparser:{timezone_name}"

    def entities(self, text: str) -> list[str]:
        seen: dict[str, str] = {}
        for ent in self.nlp(text[:20000]).ents:
            value = " ".join(ent.text.split())
            if ent.label_ not in USEFUL_ENTITY_LABELS or len(value) < 2:
                continue
            key = f"{ent.label_.lower()}:{value}"
            seen.setdefault(key.lower(), key)
        return sorted(seen.values())[:MAX_ENTITY_TAGS]

    def deadline(self, text: str) -> datetime | None:
        import dateparser.search

        now = self._now()
        settings = {
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TIMEZONE": self.timezone_name,
            "TO_TIMEZONE": "UTC",
            "RELATIVE_BASE": now.astimezone(ZoneInfo(self.timezone_name)).replace(tzinfo=None),
        }
        candidates: list[datetime] = []
        for cue in _DEADLINE_CUE_RE.finditer(text):
            window = text[cue.end(): cue.end() + _CUE_WINDOW]
            window = re.split(r"[.;\n](?:\s|$)", window, maxsplit=1)[0]
            found = dateparser.search.search_dates(window, languages=["en"], settings=settings) or []
            for phrase, parsed in found:
                if not re.search(r"\d|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|tomorrow|week|month", phrase, re.I):
                    continue  # bare words like "now" or "on" are not deadlines
                candidates.append(parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc))
                break
        if not candidates:
            return None
        future = [c for c in candidates if c >= now]
        return min(future) if future else max(candidates)


# ---------------------------------------------------------------------------
# Stack assembly
# ---------------------------------------------------------------------------


@dataclass
class NlpStack:
    normalizer: LiveNormalizer | None
    matcher: LiveEmbeddingMatcher | None
    entity_engine: str
    deadline_engine: str
    match_engine: str
    degraded: dict[str, str] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        return {
            "entity_engine": self.entity_engine,
            "deadline_engine": self.deadline_engine,
            "match_engine": self.match_engine,
            "live": not self.degraded,
            "degraded": dict(self.degraded),
        }


def _load_spacy(model: str) -> Any:
    import spacy

    return spacy.load(model)


def build_nlp_stack(
    *,
    embedding_provider: str | None = None,
    spacy_model: str | None = None,
    timezone_name: str | None = None,
    spacy_loader: Callable[[str], Any] = _load_spacy,
    backend_factory: Callable[[str], Any] | None = None,
) -> NlpStack:
    """Assemble the live stack, recording any component that could not load."""

    degraded: dict[str, str] = {}
    provider = (embedding_provider or os.getenv("ATLAS_M01_EMBEDDING_PROVIDER", "fastembed")).lower()
    model_name = spacy_model or os.getenv("ATLAS_SPACY_MODEL", "en_core_web_sm")
    tz = timezone_name or os.getenv("ATLAS_M01_DEADLINE_TIMEZONE", "UTC")

    normalizer: LiveNormalizer | None = None
    try:
        import dateparser  # noqa: F401

        normalizer = LiveNormalizer(spacy_loader(model_name), timezone_name=tz)
    except ModuleNotFoundError as exc:
        degraded["normalizer"] = f"missing dependency: {exc.name}"
    except OSError:
        degraded["normalizer"] = f"spaCy model {model_name!r} is not installed (python -m spacy download {model_name})"
    except ValueError as exc:
        degraded["normalizer"] = str(exc)

    matcher: LiveEmbeddingMatcher | None = None
    if provider in {"token", "none", "off"}:
        degraded["matcher"] = "operator opted out of embeddings (ATLAS_M01_EMBEDDING_PROVIDER=token)"
    else:
        factory = backend_factory or _default_backend
        try:
            matcher = LiveEmbeddingMatcher(factory(provider))
        except EmbeddingBackendError as exc:
            degraded["matcher"] = str(exc)
        except ValueError as exc:
            degraded["matcher"] = str(exc)

    return NlpStack(
        normalizer=normalizer,
        matcher=matcher,
        entity_engine=normalizer.entity_engine if normalizer else "keyword-tags",
        deadline_engine=normalizer.deadline_engine if normalizer else REGEX_DEADLINE_ENGINE,
        match_engine=matcher.engine if matcher else TOKEN_ENGINE,
        degraded=degraded,
    )


def _default_backend(provider: str) -> Any:
    if provider == "fastembed":
        return FastEmbedBackend()
    if provider in {"ollama", "bge"}:
        return OllamaBackend()
    if provider == "openai":
        return OpenAIBackend()
    raise ValueError(f"unsupported embedding provider: {provider!r} (use fastembed, ollama, openai or token)")


_STACK: NlpStack | None = None
_STACK_LOCK = threading.Lock()


def default_stack() -> NlpStack:
    """Process-wide stack, loaded once (model loads are expensive)."""

    global _STACK
    if _STACK is None:
        with _STACK_LOCK:
            if _STACK is None:
                _STACK = build_nlp_stack()
    return _STACK


def reset_default_stack() -> None:
    global _STACK
    with _STACK_LOCK:
        _STACK = None
