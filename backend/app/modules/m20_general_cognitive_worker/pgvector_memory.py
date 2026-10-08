"""Opt-in M20 semantic recall. SQL facts are authoritative, vectors are atomic."""
import math
import hashlib
import uuid

import sqlalchemy as sa

from app.core.vector_store import MemoryEmbeddingRow
from .embeddings import embed_snapshot
from .persistence import DurableSemanticMemory
from .schemas import SemanticFact
from .sql_repository import FactRow

NAMESPACE = 'm20-semantic-v1'


def vector_id(tenant_id, fact_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'{NAMESPACE}:{len(tenant_id)}:{tenant_id}:{fact_id}'))


def fingerprint(text):
    return hashlib.sha256(text.encode()).hexdigest()


class PgVectorSemanticMemory(DurableSemanticMemory):
    def __init__(self, repo, embedder):
        if repo.engine.dialect.name != 'postgresql':
            raise ValueError('pgvector semantic memory requires PostgreSQL')
        if embedder is None or embedder.dimensions != 1024:
            raise ValueError('pgvector semantic memory requires an explicit 1024D embedder')
        model_id = getattr(embedder, 'model_id', None)
        if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 200:
            raise ValueError('pgvector embedder requires a stable explicit model_id')
        self.model_id = model_id
        super().__init__(repo, embedder)
        # Fail at binding, never fall back after a deployment misconfiguration.
        with repo._session() as session:
            if not session.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')")):
                raise ValueError('pgvector extension is not installed')
            session.execute(sa.select(MemoryEmbeddingRow.id).limit(1))
        for fact in repo.list_facts():
            with repo._session() as session:
                row = session.get(MemoryEmbeddingRow, vector_id(repo.tenant_id, fact.id))
                if row is None or row.tenant_id != repo.tenant_id or row.namespace != NAMESPACE or (row.metadata_json.get('sha256') != fingerprint(fact.content) or row.metadata_json.get('model_id') != self.model_id):
                    raise ValueError('existing semantic facts require explicit pgvector reindex before binding')
            self._facts[fact.id] = fact
        self._edges = repo.list_edges()

    def _embed(self, text):
        if self.embedder.model_id != self.model_id:
            raise ValueError('embedding model changed during runtime; explicit reindex required')
        vector = embed_snapshot(self.embedder, text)
        if len(vector) != 1024 or not any(vector):
            raise ValueError('pgvector recall requires a nonzero finite 1024D embedding')
        return vector

    def store(self, fact):
        fact = fact.model_copy(deep=True)
        vector = self._embed(fact.content)
        self.repo.save_fact_with_embedding(fact, vector, self.model_id)
        self._facts[fact.id] = fact
        return fact.model_copy(deep=True)

    def query(self, text, *, limit=5, min_score=0.0):
        if not text.strip():
            return []
        if type(limit) is not int or not 1 <= limit <= 50 or type(min_score) not in (int, float) or not math.isfinite(min_score) or not -1 <= min_score <= 1:
            raise ValueError('invalid pgvector recall bounds')
        vector = self._embed(text)
        distance = MemoryEmbeddingRow.embedding.cosine_distance(vector)
        with self.repo._session() as session:
            # Authoritative fact content must match the indexed snapshot.
            stmt = sa.select(FactRow, MemoryEmbeddingRow.metadata_json, distance).join(
                MemoryEmbeddingRow,
                sa.and_(MemoryEmbeddingRow.metadata_json['fact_id'].as_string() == FactRow.id,
                        MemoryEmbeddingRow.tenant_id == FactRow.tenant_id)
            ).where(FactRow.tenant_id == self.repo.tenant_id,
                    MemoryEmbeddingRow.tenant_id == self.repo.tenant_id,
                    MemoryEmbeddingRow.namespace == NAMESPACE,
                    1-distance >= min_score).order_by(distance, FactRow.id).limit(limit)
            results = []
            for row, metadata, value in session.execute(stmt):
                if metadata.get('sha256') != fingerprint(row.content) or metadata.get('model_id') != self.model_id:
                    raise ValueError('semantic vector diverged from authoritative fact; explicit reindex required')
                fact = SemanticFact(id=row.id, content=row.content, kind=row.kind,
                                    confidence=row.confidence, decay_rate=row.decay_rate,
                                    provenance=row.provenance_json or {}, created_at=row.created_at,
                                    last_confirmed_at=row.last_confirmed_at)
                results.append((fact, 1-float(value)))
            return results
