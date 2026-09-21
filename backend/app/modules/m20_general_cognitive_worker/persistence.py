"""Write-through durable stores: the GCW's memories, methods, retrospectives
and calibration history survive process restarts (rows M20-04..M20-11,
M20-28, M20-30).

Each class subclasses its in-memory counterpart and mirrors every mutation
into GCWRepository. ``load()`` rehydrates a fresh instance from the
repository - embeddings are recomputed at load so a swapped embedder never
invalidates stored rows. All rows are tenant-scoped by the repository.
"""
from __future__ import annotations

from .embeddings import EmbeddingProvider
from .episodic_memory import EpisodicMemory
from .htn_planner import HTNPlanner, PlannerModel
from .metacognition import CalibrationEngine
from .reflection import RetrospectiveEngine
from .schemas import (
    Episode, HTNMethod, KnowledgeEdge, MemoryChunk, Retrospective, SemanticFact, Skill,
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

    def put(self, chunk: MemoryChunk, *, active_goal: str = "", partition: str = "") -> MemoryChunk:
        result = super().put(chunk, active_goal=active_goal, partition=partition)
        self.repo.save_chunk(result, partition=partition or (chunk.context_id or ""))
        return result

    def remove(self, chunk_id: str) -> bool:
        existed = super().remove(chunk_id)
        if existed:
            self.repo.delete_chunk(chunk_id)
        return existed

    def clear_partition(self, partition: str) -> int:
        cleared = super().clear_partition(partition)
        self.repo.clear_chunks(partition)
        return cleared

    @classmethod
    def load(
        cls,
        repo: GCWRepository,
        *,
        capacity: int = 50,
        attention: AttentionController | None = None,
    ) -> "DurableWorkingMemory":
        memory = cls(repo, capacity=capacity, attention=attention)
        for chunk in repo.list_chunks():
            partition = chunk.context_id or ""
            WorkingMemory.put(memory, chunk, partition=partition)
        return memory


class DurableEpisodicMemory(EpisodicMemory):
    """Episodes mirrored into m20_episodes (row M20-06)."""

    def __init__(self, repo: GCWRepository, embedder: EmbeddingProvider | None = None) -> None:
        super().__init__(embedder=embedder)
        self.repo = repo

    def record(self, episode: Episode) -> Episode:
        result = super().record(episode)
        self.repo.save_episode(result)
        return result

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
        result = super().store(fact)
        self.repo.save_fact(result)
        return result

    def link(self, from_id: str, relation: str, to_id: str, *, metadata: dict | None = None) -> KnowledgeEdge:
        edge = super().link(from_id, relation, to_id, metadata=metadata)
        self.repo.save_edge(edge)
        return edge

    def confirm(self, fact_id: str, **kwargs) -> SemanticFact:
        fact = super().confirm(fact_id, **kwargs)
        self.repo.save_fact(fact)
        return fact

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

    def register(self, skill: Skill) -> Skill:
        result = super().register(skill)
        for existing in self._skills.values():
            self.repo.save_skill(existing)
        return result

    def activate(self, skill_id: str) -> Skill:
        skill = super().activate(skill_id)
        self.repo.save_skill(skill)
        return skill

    def propose_from_episodes(self, episodes, *, min_occurrences: int = 2) -> list[Skill]:
        proposals = super().propose_from_episodes(episodes, min_occurrences=min_occurrences)
        for skill in proposals:
            self.repo.save_skill(skill)
        return proposals

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

    def write(self, task_id: str, *, went_well, went_poorly, lessons) -> Retrospective:
        retro = super().write(task_id, went_well=went_well, went_poorly=went_poorly, lessons=lessons)
        self.repo.save_retrospective(retro)
        return retro

    @classmethod
    def load(cls, repo: GCWRepository, embedder: EmbeddingProvider | None = None) -> "DurableRetrospectiveEngine":
        engine = cls(repo, embedder=embedder)
        for retro in repo.list_retrospectives():
            RetrospectiveEngine.write(
                engine, retro.task_id, went_well=retro.went_well,
                went_poorly=retro.went_poorly, lessons=retro.lessons,
            )
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
        self._review_status[method.name] = status
        self.repo.save_method(method, status=status)
        return super().register_method(method)

    def _match_method(self, goal: str) -> HTNMethod | None:
        match = super()._match_method(goal)
        if match is not None and self.method_status(match.name) != "active":
            return None
        return match

    def decompose(self, goal: str, *, context: str = ""):
        known = set(self.methods)
        nodes = super().decompose(goal, context=context)
        if self.require_review:
            for name in set(self.methods) - known:
                method = self.methods[name]
                if name.startswith("learned:"):
                    # base decompose registered it as active; demote to
                    # proposed until a reviewer activates it (row M20-11)
                    self.register_method(method, status="proposed")
        return nodes

    def activate_method(self, name: str) -> bool:
        if name not in self.methods:
            return False
        self._review_status[name] = "active"
        self.repo.set_method_status(self.methods[name].id, "active")
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
        claim = super().assess_claim(text, confidence, evidence_count=evidence_count)
        self.repo.save_claim(claim)
        return claim

    def resolve(self, claim_id: str, correct: bool):
        claim = super().resolve(claim_id, correct)
        self.repo.save_claim(claim)
        return claim

    @classmethod
    def load(cls, repo: GCWRepository, **kwargs) -> "DurableCalibrationEngine":
        engine = cls(repo, **kwargs)
        for claim in repo.list_claims():
            engine.claims[claim.id] = claim
        return engine
