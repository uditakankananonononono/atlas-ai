"""Semantic memory (spec 4.2.3): facts, concepts, documents and the
knowledge-graph edges that link them.

Facts carry provenance and confidence, and model knowledge decay (features
doc category 1: Knowledge Decay Modeling) so the GCW can schedule refreshes
of facts likely to be outdated.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .embeddings import DeterministicEmbedding, EmbeddingProvider, cosine_similarity
from .schemas import KnowledgeEdge, SemanticFact


class SemanticMemory:
    """Hybrid store: semantic similarity + structured graph links."""

    def __init__(self, embedder: EmbeddingProvider | None = None) -> None:
        self.embedder = embedder or DeterministicEmbedding()
        self._facts: dict[str, SemanticFact] = {}
        self._vectors: dict[str, list[float]] = {}
        self._edges: list[KnowledgeEdge] = []

    def store(self, fact: SemanticFact) -> SemanticFact:
        self._facts[fact.id] = fact
        self._vectors[fact.id] = self.embedder.embed(fact.content)
        return fact

    def remember(
        self,
        content: str,
        *,
        kind: str = "fact",
        provenance: dict | None = None,
        confidence: float = 1.0,
        decay_rate: float = 0.0,
    ) -> SemanticFact:
        return self.store(SemanticFact(
            content=content, kind=kind, provenance=provenance or {},
            confidence=confidence, decay_rate=decay_rate,
        ))

    def query(self, text: str, *, limit: int = 5, min_score: float = 0.0) -> list[tuple[SemanticFact, float]]:
        """Proactive lookup when the executive meets an unknown term."""
        if not text.strip():
            return []
        vector = self.embedder.embed(text)
        scored = [
            (self._facts[fid], cosine_similarity(vector, vec))
            for fid, vec in self._vectors.items()
        ]
        scored = [(f, s) for f, s in scored if s >= min_score]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]

    def link(self, from_id: str, relation: str, to_id: str, *, metadata: dict | None = None) -> KnowledgeEdge:
        if from_id not in self._facts and from_id not in {e.from_id for e in self._edges}:
            raise KeyError(f"unknown node: {from_id}")
        if to_id not in self._facts and to_id not in {e.to_id for e in self._edges}:
            raise KeyError(f"unknown node: {to_id}")
        edge = KnowledgeEdge(from_id=from_id, relation=relation, to_id=to_id, metadata=metadata or {})
        self._edges.append(edge)
        return edge

    def neighbors(self, node_id: str, *, relation: str | None = None) -> list[KnowledgeEdge]:
        return [
            e for e in self._edges
            if (e.from_id == node_id or e.to_id == node_id)
            and (relation is None or e.relation == relation)
        ]

    def freshness(self, fact_id: str, *, now: datetime | None = None) -> float:
        """Estimated current reliability of a fact under knowledge decay."""
        fact = self._facts[fact_id]
        if fact.decay_rate <= 0.0:
            return fact.confidence
        now = now or datetime.now(timezone.utc)
        age_days = max(0.0, (now - fact.last_confirmed_at).total_seconds() / 86400.0)
        return fact.confidence * (0.5 ** (fact.decay_rate * age_days / 30.0))

    def due_for_refresh(self, *, threshold: float = 0.5, now: datetime | None = None) -> list[SemanticFact]:
        """Facts whose freshness fell below threshold: schedule re-verification."""
        return [
            fact for fact in self._facts.values()
            if fact.decay_rate > 0.0 and self.freshness(fact.id, now=now) < threshold
        ]

    def confirm(self, fact_id: str, *, now: datetime | None = None) -> SemanticFact:
        fact = self._facts[fact_id]
        fact.last_confirmed_at = now or datetime.now(timezone.utc)
        return fact

    def get(self, fact_id: str) -> SemanticFact | None:
        return self._facts.get(fact_id)

    def __len__(self) -> int:
        return len(self._facts)
