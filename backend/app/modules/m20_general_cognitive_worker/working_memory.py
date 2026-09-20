"""Working memory and attention buffer (spec 4.2.2).

Working memory is a capacity-bounded store of chunks (fact / goal /
hypothesis / question) with an attention controller that scores each chunk's
relevance to the active goal. Capacity defaults to ~50 chunks, mirroring the
spec's human-limit inspiration. Each concurrent task context gets its own
partition (spec 4.2.6) so parallel projects never share attention.

The production attention controller is a small LLM call; the default here is
a deterministic lexical scorer so the module works offline and in tests.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from .embeddings import tokenize
from .schemas import ChunkType, MemoryChunk

DEFAULT_CAPACITY = 50


@runtime_checkable
class AttentionController(Protocol):
    """Scores how relevant a chunk is to the active goal (0..1)."""

    def score(self, chunk: MemoryChunk, active_goal: str) -> float: ...


class HeuristicAttentionController:
    """Deterministic lexical-overlap attention scorer.

    Combines token overlap with the active goal, chunk salience, chunk
    confidence, and a mild recency bonus. Type priors keep goals and open
    questions in focus slightly longer than bare facts.
    """

    TYPE_PRIOR: dict[ChunkType, float] = {
        ChunkType.GOAL: 0.15,
        ChunkType.QUESTION: 0.12,
        ChunkType.HYPOTHESIS: 0.08,
        ChunkType.FACT: 0.05,
    }

    def score(self, chunk: MemoryChunk, active_goal: str) -> float:
        goal_tokens = set(tokenize(active_goal))
        chunk_tokens = set(tokenize(chunk.content))
        if goal_tokens and chunk_tokens:
            overlap = len(goal_tokens & chunk_tokens) / len(goal_tokens | chunk_tokens)
        else:
            overlap = 0.0
        age_seconds = max(
            0.0, (datetime.now(timezone.utc) - chunk.created_at).total_seconds()
        )
        recency = 1.0 / (1.0 + math.log1p(age_seconds))
        prior = self.TYPE_PRIOR.get(chunk.type, 0.05)
        raw = 0.45 * overlap + 0.25 * chunk.salience + 0.15 * chunk.confidence + 0.15 * recency + prior
        return max(0.0, min(1.0, raw))


class WorkingMemory:
    """Capacity-bounded chunk store with attention-based pruning."""

    def __init__(
        self,
        capacity: int = DEFAULT_CAPACITY,
        attention: AttentionController | None = None,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self.attention = attention or HeuristicAttentionController()
        self._chunks: dict[str, MemoryChunk] = {}
        self._partitions: dict[str, list[str]] = {}

    def put(
        self,
        chunk: MemoryChunk,
        *,
        active_goal: str = "",
        partition: str = "",
    ) -> MemoryChunk:
        chunk.attention_score = self.attention.score(chunk, active_goal)
        chunk.context_id = partition or None
        self._chunks[chunk.id] = chunk
        if partition:
            self._partitions.setdefault(partition, [])
            if chunk.id not in self._partitions[partition]:
                self._partitions[partition].append(chunk.id)
        self._enforce_capacity(partition or None, active_goal)
        return chunk

    def _enforce_capacity(self, partition: str | None, active_goal: str) -> None:
        ids = self._ids_for(partition)
        while len(ids) > self.capacity:
            for chunk_id in ids:
                chunk = self._chunks[chunk_id]
                chunk.attention_score = self.attention.score(chunk, active_goal)
            weakest = min(ids, key=lambda cid: self._chunks[cid].attention_score)
            self._remove(weakest)
            ids = self._ids_for(partition)

    def _ids_for(self, partition: str | None) -> list[str]:
        if partition is None:
            return list(self._chunks.keys())
        return [cid for cid in self._partitions.get(partition, []) if cid in self._chunks]

    def _remove(self, chunk_id: str) -> None:
        chunk = self._chunks.pop(chunk_id, None)
        if chunk and chunk.context_id and chunk.context_id in self._partitions:
            ids = self._partitions[chunk.context_id]
            if chunk_id in ids:
                ids.remove(chunk_id)

    def refresh_attention(self, active_goal: str, *, partition: str | None = None) -> None:
        for chunk_id in self._ids_for(partition):
            chunk = self._chunks[chunk_id]
            chunk.attention_score = self.attention.score(chunk, active_goal)

    def get(self, chunk_id: str) -> MemoryChunk | None:
        return self._chunks.get(chunk_id)

    def remove(self, chunk_id: str) -> bool:
        existed = chunk_id in self._chunks
        self._remove(chunk_id)
        return existed

    def clear_partition(self, partition: str) -> int:
        """Attention-residue management: wipe a context's chunks on switch."""
        ids = list(self._partitions.get(partition, []))
        for chunk_id in ids:
            self._remove(chunk_id)
        self._partitions.pop(partition, None)
        return len(ids)

    def focused(self, *, partition: str | None = None, limit: int | None = None) -> list[MemoryChunk]:
        ids = self._ids_for(partition)
        chunks = sorted(
            (self._chunks[cid] for cid in ids),
            key=lambda c: c.attention_score,
            reverse=True,
        )
        return chunks[:limit] if limit else chunks

    def context(self, *, partition: str | None = None, limit: int = 20) -> str:
        """Render the most-attended chunks as prompt-ready text."""
        lines = []
        for chunk in self.focused(partition=partition, limit=limit):
            lines.append(
                f"[{chunk.type.value} | conf={chunk.confidence:.2f}] {chunk.content}"
            )
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._chunks)
