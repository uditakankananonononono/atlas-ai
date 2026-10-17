"""Module 10 LTM seam: incoming emails embedded into the tenant long-term memory.

Spec (Module 10, Email Assistant): "Incoming emails are ingested, embedded,
and stored in the LTM."

The LTM is ``core.vector_store.memory_embeddings``: ``tenant_id`` + ``namespace``
scoped rows with a 1024-dim pgvector column. The table has no account column,
and M10 is multi-account, so the account scope travels in ``metadata_json``
(account_id, gmail_id, sha256, model_id) and every retrieval filters it in SQL
before any ranking limit - the same fail-closed account rule as the module's
context window. Deterministic row ids per (tenant, account, gmail message,
chunk) make Pub/Sub re-ingestion an upsert, matching the module's idempotent
(tenant, account, gmail_id) message uniqueness.

Embedding truth: this module never invents vectors. The store binds an
explicit 1024-dim provider with a stable model_id and refuses anything else at
construction and at runtime. A trained production provider (e.g. the m20
documented text-embedding-3-large / Ollama bindings) is integrator wiring;
the deterministic hashing fixture used in tests names itself as such.
"""
from __future__ import annotations

import hashlib
import os
import math
import re
import uuid
from typing import Any, Protocol

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.core.retrieval import SourceDocument, chunk_document
from app.core.vector_store import EMBEDDING_DIMENSIONS, MemoryEmbeddingRow

NAMESPACE = "m10-email-v1"

_LEXICAL_TERMS = re.compile(r"[a-z0-9]+")


class SyncEmbeddingProvider(Protocol):
    """m20-style synchronous provider contract."""

    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...


def _embed_snapshot(provider: SyncEmbeddingProvider, text: str) -> list[float]:
    """Validate and detach a supplied embedding (mirrors m20's embed_snapshot;
    kept local so the M10 seam does not import the m20 package closure)."""
    dimensions = provider.dimensions
    if type(dimensions) is not int or dimensions < 1:
        raise ValueError("embedding dimensions must be a positive integer")
    supplied = provider.embed(text)
    if not isinstance(supplied, (list, tuple)) or len(supplied) != dimensions:
        raise ValueError("embedding vector must match provider dimensions")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in supplied):
        raise ValueError("embedding components must be finite numbers, not bool")
    return list(supplied)


class SyncProviderEmbedder:
    """Adapt a synchronous m20-style provider to the async list shape the M10
    Embedder protocol and core.retrieval both use. Validates the provider at
    binding: exactly 1024 dimensions and a stable explicit model_id, matching
    the m20 pgvector binding rules."""

    def __init__(self, provider: SyncEmbeddingProvider) -> None:
        dimensions = getattr(provider, "dimensions", None)
        if dimensions != EMBEDDING_DIMENSIONS:
            raise ValueError("LTM embeddings require an explicit 1024D provider")
        model_id = getattr(provider, "model_id", None)
        if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 200:
            raise ValueError("LTM embeddings require a stable explicit model_id")
        self.provider = provider
        self.dimensions = dimensions
        self.model_id = model_id

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [_embed_snapshot(self.provider, text) for text in texts]


# Model output dimensions verified against app.core.embeddings: the OpenAI
# provider requests dimensions=1024 explicitly; bge-m3 emits 1024-dim vectors.
# A model outside this table has no proven 1024-dim binding and is refused
# rather than trusted on faith.
_VERIFIED_MODEL_DIMENSIONS = {
    "text-embedding-3-large": 1024,
    "bge-m3": 1024,
}

_PROVIDER_PREFIX = {
    "OpenAIEmbeddingProvider": "openai",
    "OllamaBGEEmbeddingProvider": "ollama",
}


class CoreProviderEmbedder:
    """Typed 1024D binding over an app.core.embeddings provider, exposing the
    dimensions/model_id contract EmailLtmStore pins at binding."""

    dimensions = EMBEDDING_DIMENSIONS

    def __init__(self, provider: Any, *, model_id: str) -> None:
        self.provider = provider
        self.model_id = model_id

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self.provider.embed(texts)


# M10-scoped embedding selection. Free-on-PC is the settled user constraint:
# the default binding is the local Ollama provider. The paid OpenAI provider
# activates ONLY through an explicit M10-scoped selection
# (ATLAS_M10_EMBEDDING_PROVIDER=openai) together with its credential - it is
# never inferred from a globally present OPENAI_API_KEY, which other modules
# may be using for their own purposes. The shared registry default in
# app.core.embeddings is unchanged; this is M10-local selection only.
M10_EMBEDDING_PROVIDER_ENV = "ATLAS_M10_EMBEDDING_PROVIDER"


def configured_email_ltm(
    tenant_id: str,
    session_factory: sessionmaker,
    *,
    provider_name: str | None = None,
) -> "EmailLtmStore":
    """Build the production LTM store from M10-scoped embedding configuration.

    Always binds a real provider or raises: there is no None/Null fallback
    that could hide a missing capability behind apparently-successful
    ingestion. Unsupported provider names, an explicit paid selection without
    its credential, and models with no verified 1024-dimension binding all
    raise at binding. Runtime unavailability of the configured backend (e.g.
    the local Ollama server is down) surfaces as EmbeddingError at the first
    embed, which fails the ingestion pass visibly so Pub/Sub retries - the
    truthful status path, never a silent skip. Construction itself makes no
    network calls."""
    from app.core.embeddings import (
        OllamaBGEEmbeddingProvider,
        OpenAIEmbeddingProvider,
    )

    selection = (provider_name or os.getenv(M10_EMBEDDING_PROVIDER_ENV, "ollama")).lower()
    if selection in {"ollama", "bge", "local"}:
        provider = OllamaBGEEmbeddingProvider()
    elif selection == "openai":
        provider = OpenAIEmbeddingProvider()
        if not provider.api_key:
            raise ValueError(
                "ATLAS_M10_EMBEDDING_PROVIDER=openai selected but OPENAI_API_KEY "
                "is not configured: the explicit paid selection requires its credential"
            )
    else:
        raise ValueError(
            f"email LTM embedding provider misconfigured: unsupported provider {selection!r}"
        )
    model = getattr(provider, "model", None)
    if _VERIFIED_MODEL_DIMENSIONS.get(model or "") != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"embedding model {model!r} has no verified 1024-dimension binding; "
            "extend the registry explicitly after verifying the model's output"
        )
    prefix = _PROVIDER_PREFIX.get(type(provider).__name__, type(provider).__name__)
    return EmailLtmStore(
        tenant_id=tenant_id,
        session_factory=session_factory,
        embedder=CoreProviderEmbedder(provider, model_id=f"{prefix}:{model}"),
    )


def _row_id(tenant_id: str, account_id: str, gmail_id: str, chunk_index: int) -> str:
    """Deterministic per (tenant, account, gmail message, chunk): re-ingestion
    upserts, and tenants/accounts can never collide on the same gmail id."""
    key = (
        f"{NAMESPACE}:{len(tenant_id)}:{tenant_id}"
        f":{len(account_id)}:{account_id}:{gmail_id}:{chunk_index}"
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


class EmailLtmStore:
    """Tenant + account scoped email storage and retrieval on memory_embeddings."""

    def __init__(
        self,
        *,
        tenant_id: str,
        session_factory: sessionmaker,
        embedder: Any,
        namespace: str = NAMESPACE,
    ) -> None:
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if embedder is None:
            raise ValueError(
                "LTM storage requires a configured 1024D embedding provider; "
                "absent provider means LTM storage is unavailable, never faked"
            )
        dimensions = getattr(embedder, "dimensions", None)
        if dimensions != EMBEDDING_DIMENSIONS:
            raise ValueError("LTM embeddings require an explicit 1024D provider")
        model_id = getattr(embedder, "model_id", None)
        if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 200:
            raise ValueError("LTM embeddings require a stable explicit model_id")
        self.tenant_id = tenant_id
        self.sessions = session_factory
        self.embedder = embedder
        self.model_id = model_id
        self.namespace = namespace

    def _embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError  # replaced by _embed_async; kept sync-free

    async def _embed_checked(self, texts: list[str]) -> list[list[float]]:
        if getattr(self.embedder, "model_id", None) != self.model_id:
            raise ValueError("embedding model changed during runtime; explicit reindex required")
        vectors = await self.embedder.embed(texts)
        if len(vectors) != len(texts):
            raise ValueError("embedding count mismatch")
        for vector in vectors:
            if (
                len(vector) != EMBEDDING_DIMENSIONS
                or not any(vector)
                or not all(math.isfinite(float(value)) for value in vector)
            ):
                raise ValueError("LTM storage requires a nonzero finite 1024D embedding")
        return vectors

    async def store_message(
        self,
        *,
        account_id: str,
        gmail_id: str,
        subject: str,
        body_text: str,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """Chunk, embed, and upsert one ingested email into the tenant LTM."""
        if not account_id or not account_id.strip():
            raise ValueError("account_id is required; LTM storage fails closed")
        if not gmail_id or not gmail_id.strip():
            raise ValueError("gmail_id is required; LTM storage fails closed")
        text = f"{subject}\n{body_text}"
        document = SourceDocument(
            source_id=gmail_id,
            title=subject,
            text=text,
            locator=f"gmail://messages/{gmail_id}",
            metadata={
                "account_id": account_id,
                "gmail_id": gmail_id,
                "thread_id": thread_id,
                "model_id": self.model_id,
                "message_sha256": hashlib.sha256(text.encode()).hexdigest(),
            },
        )
        chunks = chunk_document(document)
        vectors = await self._embed_checked([chunk["text"] for chunk in chunks])
        ids: list[str] = []
        with self.sessions.begin() as db:
            for chunk, vector in zip(chunks, vectors):
                row_id = _row_id(self.tenant_id, account_id, gmail_id, chunk["metadata"]["chunk_index"])
                ids.append(row_id)
                values = {
                    "tenant_id": self.tenant_id,
                    "namespace": self.namespace,
                    "text": chunk["text"],
                    "metadata_json": chunk["metadata"],
                    "embedding": vector,
                }
                row = db.get(MemoryEmbeddingRow, row_id)
                if row is None:
                    db.add(MemoryEmbeddingRow(id=row_id, **values))
                else:
                    if row.tenant_id != self.tenant_id:
                        raise PermissionError("cross-tenant chunk collision")
                    for key, value in values.items():
                        setattr(row, key, value)
        return {"chunks": len(chunks), "ids": ids}

    async def retrieve(
        self,
        *,
        account_id: str,
        query: str,
        limit: int = 8,
        candidates: int = 40,
    ) -> list[dict[str, Any]]:
        """Account-scoped semantic recall over this tenant's stored emails.

        The tenant, namespace, and account filters all apply in SQL before any
        ORDER BY/LIMIT, so a ranking cap can never leak or crowd out across
        accounts. Unknown account fails closed."""
        if not account_id or not account_id.strip():
            raise ValueError("account_id is required; LTM retrieval fails closed")
        if not query.strip() or not 1 <= limit <= 50 or candidates < limit:
            raise ValueError("invalid retrieval request")
        vector = (await self._embed_checked([query]))[0]
        filters = (
            MemoryEmbeddingRow.tenant_id == self.tenant_id,
            MemoryEmbeddingRow.namespace == self.namespace,
            MemoryEmbeddingRow.metadata_json["account_id"].as_string() == account_id,
        )
        with self.sessions() as db:
            dialect = db.get_bind().dialect.name
            statement = sa.select(MemoryEmbeddingRow).where(*filters)
            if dialect == "postgresql":
                statement = statement.order_by(
                    MemoryEmbeddingRow.embedding.cosine_distance(vector)
                ).limit(candidates)
            rows = list(db.scalars(statement))
        for row in rows:
            if row.metadata_json.get("model_id") != self.model_id:
                raise ValueError(
                    "stored email embeddings use a different model; explicit reindex required"
                )
        terms = set(_LEXICAL_TERMS.findall(query.lower()))

        def score(row: MemoryEmbeddingRow) -> tuple[float, float, float]:
            lexical = len(terms & set(_LEXICAL_TERMS.findall(row.text.lower()))) / max(1, len(terms))
            try:
                dense = 1 - float(row.embedding.cosine_distance(vector))
            except Exception:
                a = [float(value) for value in row.embedding]
                dot = sum(x * y for x, y in zip(a, vector))
                na = sum(x * x for x in a) ** 0.5
                nb = sum(x * x for x in vector) ** 0.5
                dense = dot / (na * nb) if na and nb else 0.0
            return 0.8 * dense + 0.2 * lexical, dense, lexical

        ranked = sorted(((score(row), row) for row in rows), key=lambda item: item[0][0], reverse=True)[:limit]
        return [
            {
                "id": row.id,
                "text": row.text,
                "score": round(scores[0], 6),
                "dense_score": round(scores[1], 6),
                "lexical_score": round(scores[2], 6),
                "citation": {
                    "source_id": row.metadata_json["source_id"],
                    "title": row.metadata_json["title"],
                    "locator": row.metadata_json["locator"],
                    "chunk_index": row.metadata_json["chunk_index"],
                    "sha256": row.metadata_json["sha256"],
                    "account_id": row.metadata_json["account_id"],
                    "gmail_id": row.metadata_json["gmail_id"],
                    "model_id": row.metadata_json["model_id"],
                },
            }
            for scores, row in ranked
        ]
