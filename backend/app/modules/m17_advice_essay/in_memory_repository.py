"""Thread-safe in-memory repository for local development and unit tests."""

from __future__ import annotations

from collections.abc import Sequence
from threading import RLock
from uuid import UUID

from .schemas import AdviceSource, AdviceTip, EssayConcept, IdentityMaterial


class InMemoryModule17Repository:
    def __init__(self) -> None:
        self._lock = RLock()
        self._sources: dict[UUID, AdviceSource] = {}
        self._materials: dict[UUID, IdentityMaterial] = {}
        self._tips: dict[UUID, AdviceTip] = {}
        self._concepts: dict[UUID, EssayConcept] = {}

    def add_source(self, source: AdviceSource) -> AdviceSource:
        with self._lock:
            self._sources[source.id] = source.model_copy(deep=True)
            return source.model_copy(deep=True)

    def list_sources(self, owner_id: UUID) -> list[AdviceSource]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self._sources.values() if item.owner_id == owner_id]

    def add_material(self, material: IdentityMaterial) -> IdentityMaterial:
        with self._lock:
            self._materials[material.id] = material.model_copy(deep=True)
            return material.model_copy(deep=True)

    def list_materials(self, owner_id: UUID, ids: Sequence[UUID]) -> list[IdentityMaterial]:
        requested = set(ids)
        with self._lock:
            return [
                item.model_copy(deep=True)
                for item in self._materials.values()
                if item.owner_id == owner_id and item.id in requested and item.user_confirmed
            ]

    def add_tip(self, tip: AdviceTip) -> AdviceTip:
        with self._lock:
            self._tips[tip.id] = tip.model_copy(deep=True)
            return tip.model_copy(deep=True)

    def list_tips(self, owner_id: UUID) -> list[AdviceTip]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self._tips.values() if item.owner_id == owner_id]

    def add_concept(self, concept: EssayConcept) -> EssayConcept:
        with self._lock:
            self._concepts[concept.id] = concept.model_copy(deep=True)
            return concept.model_copy(deep=True)
