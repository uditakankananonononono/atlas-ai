"""Durable persistence for the GCW (sql_repository pattern).

SQLAlchemy 2.0, JSON columns for plan/action payloads. SQLite in tests,
PostgreSQL in production via the shared ATLAS_DATABASE_URL - the integrator
passes an engine. No connection happens at import time.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .schemas import Episode, SemanticFact, Skill, TaskContext, TraceEntry


class Base(DeclarativeBase):
    pass


class TaskRow(Base):
    __tablename__ = "m20_tasks"

    id = sa.Column(sa.String, primary_key=True)
    tenant_id = sa.Column(sa.String, nullable=False, default="default", index=True)
    goal = sa.Column(sa.Text, nullable=False)
    state = sa.Column(sa.String, nullable=False)
    importance = sa.Column(sa.Integer, nullable=False, default=3)
    deadline = sa.Column(sa.DateTime(timezone=True), nullable=True)
    plan_json = sa.Column(sa.JSON, nullable=False, default=list)
    standup_notes_json = sa.Column(sa.JSON, nullable=False, default=list)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    updated_at = sa.Column(sa.DateTime(timezone=True), nullable=False)


class EpisodeRow(Base):
    __tablename__ = "m20_episodes"

    id = sa.Column(sa.String, primary_key=True)
    tenant_id = sa.Column(sa.String, nullable=False, default="default", index=True)
    task_id = sa.Column(sa.String, sa.ForeignKey("m20_tasks.id"), nullable=False, index=True)
    goal = sa.Column(sa.Text, nullable=False)
    outcome = sa.Column(sa.String, nullable=False)
    payload_json = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False)


class FactRow(Base):
    __tablename__ = "m20_semantic_facts"

    id = sa.Column(sa.String, primary_key=True)
    tenant_id = sa.Column(sa.String, nullable=False, default="default", index=True)
    content = sa.Column(sa.Text, nullable=False)
    kind = sa.Column(sa.String, nullable=False, default="fact")
    confidence = sa.Column(sa.Float, nullable=False, default=1.0)
    decay_rate = sa.Column(sa.Float, nullable=False, default=0.0)
    provenance_json = sa.Column(sa.JSON, nullable=False, default=dict)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    last_confirmed_at = sa.Column(sa.DateTime(timezone=True), nullable=False)


class SkillRow(Base):
    __tablename__ = "m20_skills"

    id = sa.Column(sa.String, primary_key=True)
    tenant_id = sa.Column(sa.String, nullable=False, default="default", index=True)
    name = sa.Column(sa.String, nullable=False, index=True)
    version = sa.Column(sa.Integer, nullable=False, default=1)
    status = sa.Column(sa.String, nullable=False)
    payload_json = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False)


class TraceRow(Base):
    __tablename__ = "m20_traces"

    id = sa.Column(sa.String, primary_key=True)
    tenant_id = sa.Column(sa.String, nullable=False, default="default", index=True)
    task_id = sa.Column(sa.String, nullable=True, index=True)
    phase = sa.Column(sa.String, nullable=False)
    detail = sa.Column(sa.Text, nullable=False)
    policy_basis = sa.Column(sa.String, nullable=False, default="")
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class GCWRepository:
    """CRUD over the GCW's durable rows. Engine injected; no work at import."""

    def __init__(self, engine: sa.engine.Engine, *, tenant_id: str = "default") -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        self.engine = engine
        self.tenant_id = tenant_id
        self._session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def _session(self) -> Session:
        return self._session_factory()

    # -- tasks -----------------------------------------------------------

    def save_task(self, context: TaskContext) -> TaskContext:
        with self._session() as session:
            row = session.get(TaskRow, context.id)
            if row is not None and row.tenant_id != self.tenant_id:
                raise PermissionError("task belongs to another tenant")
            if row is None:
                row = TaskRow(id=context.id, goal=context.goal, tenant_id=self.tenant_id,
                              created_at=_aware(context.created_at))
                session.add(row)
            row.goal = context.goal
            row.state = context.state.value
            row.importance = context.importance
            row.deadline = context.deadline
            row.plan_json = [n.model_dump(mode="json") for n in context.plan]
            row.standup_notes_json = list(context.standup_notes)
            row.updated_at = _aware(datetime.now(timezone.utc))
            session.commit()
        return context

    def load_task(self, task_id: str) -> TaskContext | None:
        from .schemas import PlanNode
        with self._session() as session:
            row = session.get(TaskRow, task_id)
            if row is None or row.tenant_id != self.tenant_id:
                return None
            context = TaskContext(
                id=row.id, goal=row.goal, importance=row.importance,
                deadline=_aware(row.deadline) if row.deadline else None,
            )
            from .schemas import TaskState
            context.state = TaskState(row.state)
            context.plan = [PlanNode(**n) for n in (row.plan_json or [])]
            context.standup_notes = list(row.standup_notes_json or [])
            context.created_at = _aware(row.created_at)
            context.updated_at = _aware(row.updated_at)
            return context

    def list_tasks(self, *, state: str | None = None) -> list[TaskContext]:
        with self._session() as session:
            query = session.query(TaskRow).filter(TaskRow.tenant_id == self.tenant_id)
            if state:
                query = query.filter(TaskRow.state == state)
            ids = [row.id for row in query.all()]
        return [ctx for ctx in (self.load_task(i) for i in ids) if ctx is not None]

    # -- episodes ----------------------------------------------------------

    def save_episode(self, episode: Episode) -> Episode:
        with self._session() as session:
            session.add(EpisodeRow(
                id=episode.id, tenant_id=self.tenant_id,
                task_id=episode.task_id, goal=episode.goal,
                outcome=episode.outcome.value,
                payload_json=episode.model_dump(mode="json"),
                created_at=_aware(episode.created_at),
            ))
            session.commit()
        return episode

    def list_episodes(self, *, task_id: str | None = None) -> list[Episode]:
        with self._session() as session:
            query = session.query(EpisodeRow).filter(EpisodeRow.tenant_id == self.tenant_id)
            if task_id:
                query = query.filter(EpisodeRow.task_id == task_id)
            return [Episode(**row.payload_json) for row in query.all()]

    # -- semantic facts ----------------------------------------------------

    def save_fact(self, fact: SemanticFact) -> SemanticFact:
        with self._session() as session:
            row = session.get(FactRow, fact.id)
            if row is not None and row.tenant_id != self.tenant_id:
                raise PermissionError("fact belongs to another tenant")
            if row is None:
                row = FactRow(id=fact.id, content=fact.content, tenant_id=self.tenant_id)
                session.add(row)
            row.content = fact.content
            row.kind = fact.kind
            row.confidence = fact.confidence
            row.decay_rate = fact.decay_rate
            row.provenance_json = fact.provenance
            row.created_at = _aware(fact.created_at)
            row.last_confirmed_at = _aware(fact.last_confirmed_at)
            session.commit()
        return fact

    def list_facts(self) -> list[SemanticFact]:
        with self._session() as session:
            return [
                SemanticFact(
                    id=row.id, content=row.content, kind=row.kind,
                    confidence=row.confidence, decay_rate=row.decay_rate,
                    provenance=row.provenance_json or {},
                    created_at=_aware(row.created_at),
                    last_confirmed_at=_aware(row.last_confirmed_at),
                )
                for row in session.query(FactRow).filter(FactRow.tenant_id == self.tenant_id).all()
            ]

    # -- skills ------------------------------------------------------------

    def save_skill(self, skill: Skill) -> Skill:
        with self._session() as session:
            row = session.get(SkillRow, skill.id)
            if row is not None and row.tenant_id != self.tenant_id:
                raise PermissionError("skill belongs to another tenant")
            if row is None:
                row = SkillRow(id=skill.id, name=skill.name, tenant_id=self.tenant_id)
                session.add(row)
            row.version = skill.version
            row.status = skill.status.value
            row.payload_json = skill.model_dump(mode="json")
            row.created_at = _aware(skill.created_at)
            session.commit()
        return skill

    def list_skills(self, *, status: str | None = None) -> list[Skill]:
        with self._session() as session:
            query = session.query(SkillRow).filter(SkillRow.tenant_id == self.tenant_id)
            if status:
                query = query.filter(SkillRow.status == status)
            return [Skill(**row.payload_json) for row in query.all()]

    # -- traces ------------------------------------------------------------

    def save_trace(self, trace: TraceEntry) -> TraceEntry:
        with self._session() as session:
            session.add(TraceRow(
                id=trace.id, tenant_id=self.tenant_id,
                task_id=trace.task_id, phase=trace.phase,
                detail=trace.detail, policy_basis=trace.policy_basis,
                created_at=_aware(trace.created_at),
            ))
            session.commit()
        return trace

    def list_traces(self, *, task_id: str | None = None) -> list[TraceEntry]:
        with self._session() as session:
            query = session.query(TraceRow).filter(TraceRow.tenant_id == self.tenant_id).order_by(TraceRow.created_at)
            if task_id:
                query = query.filter(TraceRow.task_id == task_id)
            return [
                TraceEntry(
                    id=row.id, task_id=row.task_id, phase=row.phase,
                    detail=row.detail, policy_basis=row.policy_basis,
                    created_at=_aware(row.created_at),
                )
                for row in query.all()
            ]


# -- runtime-depth tables (rows M20-04..M20-11, M20-28, M20-30) -------------

class ChunkRow(Base):
    __tablename__ = "m20_working_chunks"

    id = sa.Column(sa.String, primary_key=True)
    tenant_id = sa.Column(sa.String, nullable=False, default="default", index=True)
    partition = sa.Column(sa.String, nullable=False, default="", index=True)
    payload_json = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False)


class EdgeRow(Base):
    __tablename__ = "m20_knowledge_edges"

    id = sa.Column(sa.String, primary_key=True)
    tenant_id = sa.Column(sa.String, nullable=False, default="default", index=True)
    from_id = sa.Column(sa.String, nullable=False, index=True)
    to_id = sa.Column(sa.String, nullable=False, index=True)
    relation = sa.Column(sa.String, nullable=False)
    metadata_json = sa.Column(sa.JSON, nullable=False, default=dict)


class RetrospectiveRow(Base):
    __tablename__ = "m20_retrospectives"

    id = sa.Column(sa.String, primary_key=True)
    tenant_id = sa.Column(sa.String, nullable=False, default="default", index=True)
    task_id = sa.Column(sa.String, nullable=False, index=True)
    payload_json = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False)


class MethodRow(Base):
    __tablename__ = "m20_htn_methods"

    id = sa.Column(sa.String, primary_key=True)
    tenant_id = sa.Column(sa.String, nullable=False, default="default", index=True)
    name = sa.Column(sa.String, nullable=False, index=True)
    status = sa.Column(sa.String, nullable=False, default="active", index=True)
    payload_json = sa.Column(sa.JSON, nullable=False)


class ClaimRow(Base):
    __tablename__ = "m20_calibration_claims"

    id = sa.Column(sa.String, primary_key=True)
    tenant_id = sa.Column(sa.String, nullable=False, default="default", index=True)
    payload_json = sa.Column(sa.JSON, nullable=False)
    resolved = sa.Column(sa.Boolean, nullable=False, default=False, index=True)


def _repository_extension(cls):
    from .metacognition import Claim
    from .schemas import HTNMethod, KnowledgeEdge, MemoryChunk, Retrospective

    # -- working-memory chunks (M20-04) -------------------------------------

    def save_chunk(self, chunk, *, partition: str = ""):
        with self._session() as session:
            row = session.get(ChunkRow, chunk.id)
            if row is not None and row.tenant_id != self.tenant_id:
                raise PermissionError("chunk belongs to another tenant")
            if row is None:
                row = ChunkRow(id=chunk.id, tenant_id=self.tenant_id,
                               created_at=_aware(chunk.created_at))
                session.add(row)
            row.partition = partition
            row.payload_json = chunk.model_dump(mode="json")
            session.commit()
        return chunk

    def list_chunks(self, *, partition: str | None = None) -> list:
        with self._session() as session:
            query = session.query(ChunkRow).filter(ChunkRow.tenant_id == self.tenant_id)
            if partition is not None:
                query = query.filter(ChunkRow.partition == partition)
            return [MemoryChunk(**row.payload_json) for row in query.all()]

    def delete_chunk(self, chunk_id: str) -> bool:
        with self._session() as session:
            row = session.get(ChunkRow, chunk_id)
            if row is None or row.tenant_id != self.tenant_id:
                return False
            session.delete(row)
            session.commit()
            return True

    def clear_chunks(self, partition: str) -> int:
        with self._session() as session:
            rows = (session.query(ChunkRow)
                    .filter(ChunkRow.tenant_id == self.tenant_id,
                            ChunkRow.partition == partition).all())
            for row in rows:
                session.delete(row)
            session.commit()
            return len(rows)

    # -- knowledge edges (M20-07) --------------------------------------------

    def save_edge(self, edge):
        with self._session() as session:
            if session.get(EdgeRow, edge.id) is None:
                session.add(EdgeRow(
                    id=edge.id, tenant_id=self.tenant_id, from_id=edge.from_id,
                    to_id=edge.to_id, relation=edge.relation,
                    metadata_json=edge.metadata,
                ))
                session.commit()
        return edge

    def list_edges(self, *, node_id: str | None = None) -> list:
        with self._session() as session:
            query = session.query(EdgeRow).filter(EdgeRow.tenant_id == self.tenant_id)
            rows = query.all()
        edges = [
            KnowledgeEdge(id=r.id, from_id=r.from_id, relation=r.relation,
                          to_id=r.to_id, metadata=r.metadata_json or {})
            for r in rows
        ]
        if node_id is not None:
            edges = [e for e in edges if e.from_id == node_id or e.to_id == node_id]
        return edges

    # -- retrospectives (M20-28) ---------------------------------------------

    def save_retrospective(self, retro):
        with self._session() as session:
            if session.get(RetrospectiveRow, retro.id) is None:
                session.add(RetrospectiveRow(
                    id=retro.id, tenant_id=self.tenant_id, task_id=retro.task_id,
                    payload_json=retro.model_dump(mode="json"),
                    created_at=_aware(retro.created_at),
                ))
                session.commit()
        return retro

    def list_retrospectives(self, *, task_id: str | None = None) -> list:
        with self._session() as session:
            query = (session.query(RetrospectiveRow)
                     .filter(RetrospectiveRow.tenant_id == self.tenant_id))
            if task_id:
                query = query.filter(RetrospectiveRow.task_id == task_id)
            return [Retrospective(**row.payload_json) for row in query.all()]

    # -- HTN methods with review status (M20-10, M20-11) ---------------------

    def save_method(self, method, *, status: str = "active"):
        with self._session() as session:
            row = session.get(MethodRow, method.id)
            if row is not None and row.tenant_id != self.tenant_id:
                raise PermissionError("method belongs to another tenant")
            if row is None:
                row = MethodRow(id=method.id, tenant_id=self.tenant_id)
                session.add(row)
            row.name = method.name
            row.status = status
            payload = method.model_dump(mode="json")
            payload["review_status"] = status
            row.payload_json = payload
            session.commit()
        return method

    def list_methods(self, *, status: str | None = None) -> list:
        """Returns (method, review_status) pairs."""
        with self._session() as session:
            query = session.query(MethodRow).filter(MethodRow.tenant_id == self.tenant_id)
            if status:
                query = query.filter(MethodRow.status == status)
            return [
                (
                    HTNMethod(**{k: v for k, v in row.payload_json.items()
                                 if k != "review_status"}),
                    row.status,
                )
                for row in query.all()
            ]

    def set_method_status(self, method_id: str, status: str) -> bool:
        with self._session() as session:
            row = session.get(MethodRow, method_id)
            if row is None or row.tenant_id != self.tenant_id:
                return False
            row.status = status
            row.payload_json = {**row.payload_json, "review_status": status}
            session.commit()
            return True

    # -- calibration claims (M20-30) -----------------------------------------

    def save_claim(self, claim) -> None:
        with self._session() as session:
            row = session.get(ClaimRow, claim.id)
            if row is not None and row.tenant_id != self.tenant_id:
                raise PermissionError("claim belongs to another tenant")
            if row is None:
                row = ClaimRow(id=claim.id, tenant_id=self.tenant_id)
                session.add(row)
            row.resolved = claim.resolved
            row.payload_json = {
                "id": claim.id, "text": claim.text, "confidence": claim.confidence,
                "evidence_count": claim.evidence_count, "flagged": claim.flagged,
                "flag_reason": claim.flag_reason, "resolved": claim.resolved,
                "correct": claim.correct,
                "created_at": claim.created_at.isoformat(),
            }
            session.commit()

    def list_claims(self) -> list:
        from datetime import datetime as _dt
        with self._session() as session:
            rows = (session.query(ClaimRow)
                    .filter(ClaimRow.tenant_id == self.tenant_id).all())
        claims = []
        for row in rows:
            payload = dict(row.payload_json)
            payload["created_at"] = _dt.fromisoformat(payload["created_at"])
            claims.append(Claim(**payload))
        return claims

    for name, fn in {
        "save_chunk": save_chunk, "list_chunks": list_chunks,
        "delete_chunk": delete_chunk, "clear_chunks": clear_chunks,
        "save_edge": save_edge, "list_edges": list_edges,
        "save_retrospective": save_retrospective,
        "list_retrospectives": list_retrospectives,
        "save_method": save_method, "list_methods": list_methods,
        "set_method_status": set_method_status,
        "save_claim": save_claim, "list_claims": list_claims,
    }.items():
        setattr(cls, name, fn)
    return cls


GCWRepository = _repository_extension(GCWRepository)
