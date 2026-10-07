"""Episodic memory (spec 4.2.3): every task execution logged as an episode
and retrievable by similarity for analogical transfer.

Production storage is ChromaDB behind the same interface; this implementation
is the in-module store the integrator can swap or back with the shared vector
DB. Retrieval is embedding-similarity over goal + reflection text.
"""
from __future__ import annotations

from .embeddings import DeterministicEmbedding, EmbeddingProvider, cosine_similarity
from .schemas import ActionRecord, Episode, EpisodeOutcome


class EpisodicMemory:
    """Store and similarity-retrieve task episodes."""

    def __init__(self, embedder: EmbeddingProvider | None = None) -> None:
        self.embedder = embedder or DeterministicEmbedding()
        self._episodes: dict[str, Episode] = {}
        self._vectors: dict[str, list[float]] = {}

    def record(self, episode: Episode) -> Episode:
        episode = episode.model_copy(deep=True)
        if not episode.embedding_text:
            episode.embedding_text = self._embed_text(episode)
        vector = self.embedder.embed(episode.embedding_text)
        self._episodes[episode.id] = episode
        self._vectors[episode.id] = vector
        return episode.model_copy(deep=True)

    def log_execution(
        self,
        *,
        task_id: str,
        goal: str,
        start_state: str = "",
        actions: list[ActionRecord] | None = None,
        outcome: EpisodeOutcome = EpisodeOutcome.SUCCEEDED,
        reflection: str = "",
        tags: list[str] | None = None,
    ) -> Episode:
        episode = Episode(
            task_id=task_id, goal=goal, start_state=start_state,
            actions=actions or [], outcome=outcome, reflection=reflection,
            tags=tags or [],
        )
        return self.record(episode)

    def recall_similar(self, query: str, *, limit: int = 5, min_score: float = 0.0) -> list[tuple[Episode, float]]:
        """Analogical transfer: 'have I solved something like this before?'"""
        if not query.strip():
            return []
        vector = self.embedder.embed(query)
        scored = [
            (self._episodes[eid], cosine_similarity(vector, vec))
            for eid, vec in self._vectors.items()
        ]
        scored = [(ep, s) for ep, s in scored if s >= min_score]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [(ep.model_copy(deep=True),score) for ep,score in scored[:limit]]

    def for_task(self, task_id: str) -> list[Episode]:
        return [ep.model_copy(deep=True) for ep in self._episodes.values() if ep.task_id == task_id]

    def successful_patterns(self, *, min_actions: int = 2) -> list[Episode]:
        """Successful multi-step episodes: candidates for skill learning."""
        return [
            ep.model_copy(deep=True) for ep in self._episodes.values()
            if ep.outcome == EpisodeOutcome.SUCCEEDED and len(ep.actions) >= min_actions
            and all(action.succeeded for action in ep.actions)
        ]

    def get(self, episode_id: str) -> Episode | None:
        episode = self._episodes.get(episode_id)
        return episode.model_copy(deep=True) if episode is not None else None

    def __len__(self) -> int:
        return len(self._episodes)

    @staticmethod
    def _embed_text(episode: Episode) -> str:
        tools = " ".join(a.tool for a in episode.actions)
        return f"{episode.goal} {episode.reflection} {' '.join(episode.tags)} {tools}".strip()
