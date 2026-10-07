"""Write-through durable stores: the GCW's memories, methods, retrospectives
and calibration history survive process restarts (rows M20-04..M20-11,
M20-28, M20-30).

Each class subclasses its in-memory counterpart and mirrors every mutation
into GCWRepository. ``load()`` rehydrates a fresh instance from the
repository - embeddings are recomputed at load so a swapped embedder never
invalidates stored rows. All rows are tenant-scoped by the repository.
"""
from __future__ import annotations

import hashlib
import json

from .embeddings import EmbeddingProvider, embed_snapshot
from .episodic_memory import EpisodicMemory
from .htn_planner import HTNPlanner, PlannerModel
from .metacognition import CalibrationEngine
from .reflection import RetrospectiveEngine
from .schemas import (
    Episode, HTNMethod, MethodSource, KnowledgeEdge, MemoryChunk, Retrospective, SemanticFact, Skill,
    SkillStatus,
)
from .semantic_memory import SemanticMemory
from .skill_library import SkillLibrary
from .sql_repository import GCWRepository
from .working_memory import AttentionController, WorkingMemory


class DurableWorkingMemory(WorkingMemory):
    """Working memory mirrored into m20_working_chunks (row M20-04)."""

    def __init__(self, repo: GCWRepository, **kwargs) -> None:
        super().__init__(**kwargs)
        self.repo = repo

    def _change(self, operation, *args, **kwargs):
        staged = WorkingMemory(capacity=self.capacity, attention=self.attention)
        staged._chunks = {cid:chunk.model_copy(deep=True) for cid,chunk in self._chunks.items()}
        staged._partitions = {partition:list(ids) for partition,ids in self._partitions.items()}
        result = getattr(staged, operation)(*args, **kwargs)
        changed = [chunk for cid,chunk in staged._chunks.items()
                   if cid not in self._chunks or chunk != self._chunks[cid]]
        removed = [cid for cid in self._chunks if cid not in staged._chunks]
        if changed or removed:
            self.repo.change_chunks(changed, removed)
        self._chunks, self._partitions = staged._chunks, staged._partitions
        return result

    def put(self, chunk: MemoryChunk, *, active_goal: str = "", partition: str = "") -> MemoryChunk:
        return self._change('put', chunk, active_goal=active_goal, partition=partition)

    def _remove(self, chunk_id: str) -> None:
        self._change('_remove', chunk_id)

    def clear_partition(self, partition: str) -> int:
        return self._change('clear_partition', partition)

    def refresh_attention(self, active_goal: str, *, partition: str | None = None) -> None:
        self._change('refresh_attention', active_goal, partition=partition)

    @classmethod
    def load(
        cls,
        repo: GCWRepository,
        *,
        capacity: int = 50,
        attention: AttentionController | None = None,
    ) -> "DurableWorkingMemory":
        memory = cls(repo, capacity=capacity, attention=attention)
        staged = WorkingMemory(capacity=capacity, attention=memory.attention)
        for chunk in repo.list_chunks():
            staged.put(chunk, partition=chunk.context_id or "")
        memory._chunks, memory._partitions = staged._chunks, staged._partitions
        return memory


class DurableEpisodicMemory(EpisodicMemory):
    """Episodes mirrored into m20_episodes (row M20-06)."""

    def __init__(self, repo: GCWRepository, embedder: EmbeddingProvider | None = None) -> None:
        super().__init__(embedder=embedder)
        self.repo = repo

    def record(self, episode: Episode) -> Episode:
        # Stage embedding before the write, publish to recall only after commit.
        result = episode.model_copy(deep=True)
        if not result.embedding_text:
            result.embedding_text = self._embed_text(result)
        vector = embed_snapshot(self.embedder, result.embedding_text)
        self.repo.save_episode(result)
        self._episodes[result.id] = result
        self._vectors[result.id] = vector
        return result.model_copy(deep=True)

    @classmethod
    def load(cls, repo: GCWRepository, embedder: EmbeddingProvider | None = None) -> "DurableEpisodicMemory":
        memory = cls(repo, embedder=embedder)
        for episode in repo.list_episodes():
            EpisodicMemory.record(memory, episode)
        return memory


class DurableSemanticMemory(SemanticMemory):
    """Facts and knowledge-graph edges mirrored (row M20-07)."""

    def __init__(self, repo: GCWRepository, embedder: EmbeddingProvider | None = None) -> None:
        super().__init__(embedder=embedder)
        self.repo = repo

    def store(self, fact: SemanticFact) -> SemanticFact:
        result = fact.model_copy(deep=True)
        vector = embed_snapshot(self.embedder, result.content)
        self.repo.save_fact(result)
        self._facts[result.id] = result
        self._vectors[result.id] = vector
        return result.model_copy(deep=True)

    def link(self, from_id: str, relation: str, to_id: str, *, metadata: dict | None = None) -> KnowledgeEdge:
        if from_id not in self._facts and from_id not in {e.from_id for e in self._edges}:
            raise KeyError(f"unknown node: {from_id}")
        if to_id not in self._facts and to_id not in {e.to_id for e in self._edges}:
            raise KeyError(f"unknown node: {to_id}")
        edge = KnowledgeEdge(from_id=from_id,relation=relation,to_id=to_id,metadata=metadata or {}).model_copy(deep=True)
        self.repo.save_edge(edge)
        self._edges.append(edge)
        return edge.model_copy(deep=True)

    def confirm(self, fact_id: str, **kwargs) -> SemanticFact:
        from datetime import datetime, timezone
        fact = self._facts[fact_id].model_copy(deep=True)
        fact.last_confirmed_at = kwargs.get('now') or datetime.now(timezone.utc)
        self.repo.save_fact(fact)
        self._facts[fact_id] = fact
        return fact.model_copy(deep=True)

    @classmethod
    def load(cls, repo: GCWRepository, embedder: EmbeddingProvider | None = None) -> "DurableSemanticMemory":
        memory = cls(repo, embedder=embedder)
        for fact in repo.list_facts():
            SemanticMemory.store(memory, fact)
        for edge in repo.list_edges():
            memory._edges.append(edge)
        return memory


class DurableSkillLibrary(SkillLibrary):
    """Skill registry mirrored into m20_skills (rows M20-08, M20-09)."""

    def __init__(self, repo: GCWRepository) -> None:
        super().__init__()
        self.repo = repo

    def _change(self, operation, *args, **kwargs):
        staged = SkillLibrary()
        staged._skills = {ident:skill.model_copy(deep=True) for ident,skill in self._skills.items()}
        result = getattr(staged, operation)(*args, **kwargs)
        changed = [skill for ident,skill in staged._skills.items()
                   if ident not in self._skills or skill != self._skills[ident]]
        if changed:
            self.repo.save_skills(changed)
        self._skills = staged._skills
        return result

    def register(self, skill: Skill) -> Skill:
        return self._change('register', skill)

    def activate(self, skill_id: str) -> Skill:
        return self._change('activate', skill_id)

    def retire(self, name: str) -> bool:
        return self._change('retire', name)

    def propose_from_episodes(self, episodes, *, min_occurrences: int = 2) -> list[Skill]:
        return self._change('propose_from_episodes', episodes, min_occurrences=min_occurrences)

    @classmethod
    def load(cls, repo: GCWRepository) -> "DurableSkillLibrary":
        library = cls(repo)
        for skill in repo.list_skills():
            library._skills[skill.id] = skill
        return library


class DurableRetrospectiveEngine(RetrospectiveEngine):
    """Retrospective artifacts mirrored into m20_retrospectives (row M20-28)."""

    def __init__(self, repo: GCWRepository, embedder: EmbeddingProvider | None = None) -> None:
        super().__init__(embedder=embedder)
        self.repo = repo

    def write(self, task_id: str, *, went_well, went_poorly, lessons, execution_report=None) -> Retrospective:
        retro = Retrospective(
            task_id=task_id, went_well=went_well, went_poorly=went_poorly,
            lessons=lessons, execution_report=execution_report or {},
        ).model_copy(deep=True)
        text = " ".join(retro.went_well + retro.went_poorly + retro.lessons)
        vector = embed_snapshot(self.embedder, text)
        self.repo.save_retrospective(retro)
        self._retros[retro.id] = retro
        self._vectors[retro.id] = vector
        return retro.model_copy(deep=True)

    @classmethod
    def load(cls, repo: GCWRepository, embedder: EmbeddingProvider | None = None) -> "DurableRetrospectiveEngine":
        engine = cls(repo, embedder=embedder)
        for retro in repo.list_retrospectives():
            engine._store_snapshot(retro)
        return engine


class DurableHTNPlanner(HTNPlanner):
    """Method library mirrored into m20_htn_methods with a review gate
    (rows M20-10, M20-11): with ``require_review`` on, methods learned from
    de-novo decompositions persist as *proposed* and cannot match goals
    until a reviewer activates them - no silent self-modification.
    """

    def __init__(self, repo: GCWRepository, model: PlannerModel | None = None, *, require_review: bool = False) -> None:
        super().__init__(model=model)
        self.repo = repo
        self.require_review = require_review
        self._review_status: dict[str, str] = {}

    def method_status(self, name: str) -> str:
        return self._review_status.get(name, "active")

    def register_method(self, method: HTNMethod, *, status: str = "active") -> HTNMethod:
        method = self._validated_method(method)
        existing = self.methods.get(method.name)
        if existing is not None:
            method = method.model_copy(deep=True, update={"id": existing.id})
        if self.require_review and method.source == MethodSource.LEARNED:
            status = "proposed"
        self.repo.save_method(method, status=status)
        self._review_status[method.name] = status
        return super().register_method(method)

    def _match_method(self, goal: str, *, context: str = "") -> HTNMethod | None:
        match = super()._match_method(goal, context=context)
        if match is not None and self.method_status(match.name) != "active":
            return None
        return match

    def decompose(self, goal: str, *, context: str = ""):
        matched = self._match_method(goal, context=context)
        if matched is None:
            return super().decompose(goal, context=context)
        staged = matched.model_copy(deep=True)
        nodes = self._instantiate(staged)
        staged.times_used += 1
        self.repo.save_method(staged, status=self.method_status(staged.name))
        self._methods[staged.name] = staged
        return nodes

    def record_outcome(self, method_name: str, succeeded: bool) -> None:
        method = self._methods.get(method_name)
        if method is None:
            return
        staged = HTNPlanner()
        staged._methods[method_name] = method.model_copy(deep=True)
        staged.record_outcome(method_name, succeeded)
        updated = staged._methods[method_name]
        self.repo.save_method(updated, status=self.method_status(method_name))
        self._methods[method_name] = updated

    @staticmethod
    def method_review_hash(method):
        payload=method.model_dump(mode="json")
        payload.pop("times_used", None)
        payload.pop("success_rate", None)
        payload.pop("outcomes_recorded", None)
        payload.pop("successes_recorded", None)
        return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

    def activate_method(self, name: str, *, expected_hash: str) -> bool:
        if name not in self.methods:
            return False
        if expected_hash != self.method_review_hash(self.methods[name]):
            raise PermissionError("method revision differs from reviewed hash")
        if not self.repo.set_method_status(self.methods[name].id, "active"):
            return False
        self._review_status[name] = "active"
        return True

    @classmethod
    def load(cls, repo: GCWRepository, model: PlannerModel | None = None, *, require_review: bool = False) -> "DurableHTNPlanner":
        planner = cls(repo, model=model, require_review=require_review)
        for method, status in repo.list_methods():
            HTNPlanner.register_method(planner, method)
            planner._review_status[method.name] = status
        return planner


class DurableCalibrationEngine(CalibrationEngine):
    """Calibration claims mirrored into m20_calibration_claims (row M20-30)."""

    def __init__(self, repo: GCWRepository, **kwargs) -> None:
        super().__init__(**kwargs)
        self.repo = repo

    def assess_claim(self, text, confidence, *, evidence_count: int = 0):
        staged = CalibrationEngine()
        claim = staged.assess_claim(text, confidence, evidence_count=evidence_count)
        self.repo.save_claim(claim)
        self._claims[claim.id] = staged._claims[claim.id]
        return claim

    def resolve(self, claim_id: str, correct: bool):
        from copy import deepcopy
        staged = CalibrationEngine()
        staged._claims[claim_id] = deepcopy(self._claims[claim_id])
        claim = staged.resolve(claim_id, correct)
        self.repo.save_claim(claim)
        self._claims[claim_id] = staged._claims[claim_id]
        return claim

    @classmethod
    def load(cls, repo: GCWRepository, **kwargs) -> "DurableCalibrationEngine":
        engine = cls(repo, **kwargs)
        for claim in repo.list_claims():
            engine._claims[claim.id] = claim
        return engine
