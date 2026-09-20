"""Thread-safe repository abstraction and in-memory implementation."""
from __future__ import annotations

from copy import deepcopy
from threading import RLock
from uuid import UUID

from .lane_models import Decision, Evidence, Experiment, FeasibilityTest, Idea


class NotFoundError(LookupError):
    pass


class ConflictError(RuntimeError):
    pass


class InMemoryIdeaRepository:
    """Deterministic repository for local use and tests.

    Production persistence can implement this same method surface without changing the
    domain service. Defensive copies prevent callers mutating committed state.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._ideas: dict[UUID, Idea] = {}
        self._evidence: dict[UUID, list[Evidence]] = {}
        self._tests: dict[UUID, list[FeasibilityTest]] = {}
        self._experiments: dict[UUID, list[Experiment]] = {}
        self._decisions: dict[UUID, list[Decision]] = {}

    def add_idea(self, idea: Idea) -> Idea:
        with self._lock:
            if idea.id in self._ideas:
                raise ConflictError(f"idea {idea.id} already exists")
            self._ideas[idea.id] = deepcopy(idea)
            return deepcopy(idea)

    def get_idea(self, idea_id: UUID) -> Idea:
        with self._lock:
            try:
                return deepcopy(self._ideas[idea_id])
            except KeyError as exc:
                raise NotFoundError(f"idea {idea_id} not found") from exc

    def save_idea(self, idea: Idea, expected_version: int) -> Idea:
        with self._lock:
            current = self._ideas.get(idea.id)
            if current is None:
                raise NotFoundError(f"idea {idea.id} not found")
            if current.version != expected_version:
                raise ConflictError(
                    f"idea version changed: expected {expected_version}, current {current.version}"
                )
            self._ideas[idea.id] = deepcopy(idea)
            return deepcopy(idea)

    def list_ideas(self) -> list[Idea]:
        with self._lock:
            return sorted((deepcopy(x) for x in self._ideas.values()), key=lambda x: x.created_at)

    def _append(self, store: dict[UUID, list], idea_id: UUID, item):
        self.get_idea(idea_id)
        with self._lock:
            store.setdefault(idea_id, []).append(deepcopy(item))
            return deepcopy(item)

    def _list(self, store: dict[UUID, list], idea_id: UUID) -> list:
        self.get_idea(idea_id)
        with self._lock:
            return deepcopy(store.get(idea_id, []))

    def add_evidence(self, item: Evidence) -> Evidence:
        return self._append(self._evidence, item.idea_id, item)

    def list_evidence(self, idea_id: UUID) -> list[Evidence]:
        return self._list(self._evidence, idea_id)

    def add_feasibility_test(self, item: FeasibilityTest) -> FeasibilityTest:
        return self._append(self._tests, item.idea_id, item)

    def list_feasibility_tests(self, idea_id: UUID) -> list[FeasibilityTest]:
        return self._list(self._tests, idea_id)

    def add_experiment(self, item: Experiment) -> Experiment:
        return self._append(self._experiments, item.idea_id, item)

    def list_experiments(self, idea_id: UUID) -> list[Experiment]:
        return self._list(self._experiments, idea_id)

    def save_experiment(self, item: Experiment) -> Experiment:
        self.get_idea(item.idea_id)
        with self._lock:
            items = self._experiments.get(item.idea_id, [])
            for index, current in enumerate(items):
                if current.id == item.id:
                    items[index] = deepcopy(item)
                    return deepcopy(item)
            raise NotFoundError(f"experiment {item.id} not found")

    def add_decision(self, item: Decision) -> Decision:
        return self._append(self._decisions, item.idea_id, item)

    def list_decisions(self, idea_id: UUID) -> list[Decision]:
        return self._list(self._decisions, idea_id)
