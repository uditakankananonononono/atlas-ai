"""Opt-in M20 semantic recall. SQL facts are authoritative, vectors are atomic."""
import struct
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
        self.query('binding validation', limit=1)

    def _embed(self, text):
        if self.embedder.model_id != self.model_id:
            raise ValueError('embedding model changed during runtime; explicit reindex required')
        vector = embed_snapshot(self.embedder, text)
        if len(vector) != 1024 or not any(vector):
            raise ValueError('pgvector recall requires a nonzero finite 1024D embedding')
        # pgvector stores float32. Stable unit normalization avoids finite
        # float64 overflow/underflow changing a nonzero vector into inf/zero.
        scale = max(abs(value) for value in vector)
        scaled = [value / scale for value in vector]
        norm = math.sqrt(math.fsum(value * value for value in scaled))
        normalized = [struct.unpack('f', struct.pack('f', value / norm))[0] for value in scaled]
        if not all(math.isfinite(value) for value in normalized) or not any(normalized):
            raise ValueError('embedding is not representable as a nonzero float32 vector')
        return normalized

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
            # Check the entire tenant namespace, including rows omitted by a
            # score/limit filter. Never allow extra/missing rows to rank facts.
            facts = session.scalars(sa.select(FactRow).where(FactRow.tenant_id == self.repo.tenant_id)).all()
            indexed = session.scalars(sa.select(MemoryEmbeddingRow).where(
                MemoryEmbeddingRow.tenant_id == self.repo.tenant_id,
                MemoryEmbeddingRow.namespace == NAMESPACE)).all()
            expected = {vector_id(self.repo.tenant_id, fact.id): fact for fact in facts}
            if set(expected) != {row.id for row in indexed}:
                raise ValueError('semantic vector identity set diverged; explicit reindex required')
            for indexed_row in indexed:
                fact = expected[indexed_row.id]
                metadata = indexed_row.metadata_json
                if metadata.get('fact_id') != fact.id or metadata.get('sha256') != fingerprint(fact.content) or metadata.get('model_id') != self.model_id:
                    raise ValueError('semantic vector diverged; explicit reindex required')
                if not any(indexed_row.embedding) or not all(math.isfinite(float(value)) for value in indexed_row.embedding):
                    raise ValueError('semantic vector is zero or nonfinite; explicit reindex required')
            # Authoritative fact content must match the indexed snapshot.
            stmt = sa.select(MemoryEmbeddingRow.id, MemoryEmbeddingRow.metadata_json, distance).where(
                MemoryEmbeddingRow.tenant_id == self.repo.tenant_id,
                MemoryEmbeddingRow.namespace == NAMESPACE,
                MemoryEmbeddingRow.id.in_(expected),
                1-distance >= min_score).order_by(distance, MemoryEmbeddingRow.id).limit(limit)
            results = []
            for ident, metadata, value in session.execute(stmt):
                row = expected[ident]
                if metadata.get('fact_id') != row.id or metadata.get('sha256') != fingerprint(row.content) or metadata.get('model_id') != self.model_id:
                    raise ValueError('semantic vector diverged from authoritative fact; explicit reindex required')
                fact = SemanticFact(id=row.id, content=row.content, kind=row.kind,
                                    confidence=row.confidence, decay_rate=row.decay_rate,
                                    provenance=row.provenance_json or {}, created_at=row.created_at,
                                    last_confirmed_at=row.last_confirmed_at)
                score = 1-float(value)
                if not math.isfinite(score):
                    raise ValueError('semantic recall produced a nonfinite score')
                results.append((fact, score))
            return results
