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
    task_id = sa.Column(sa.String, sa.ForeignKey("m20_tasks.id"), nullable=False, index=True)
    goal = sa.Column(sa.Text, nullable=False)
    outcome = sa.Column(sa.String, nullable=False)
    payload_json = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False)


class FactRow(Base):
    __tablename__ = "m20_semantic_facts"

    id = sa.Column(sa.String, primary_key=True)
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
    name = sa.Column(sa.String, nullable=False, index=True)
    version = sa.Column(sa.Integer, nullable=False, default=1)
    status = sa.Column(sa.String, nullable=False)
    payload_json = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False)


class TraceRow(Base):
    __tablename__ = "m20_traces"

    id = sa.Column(sa.String, primary_key=True)
    task_id = sa.Column(sa.String, nullable=True, index=True)
    phase = sa.Column(sa.String, nullable=False)
    detail = sa.Column(sa.Text, nullable=False)
    policy_basis = sa.Column(sa.String, nullable=False, default="")
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class GCWRepository:
    """CRUD over the GCW's durable rows. Engine injected; no work at import."""

    def __init__(self, engine: sa.engine.Engine) -> None:
        self.engine = engine
        self._session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def _session(self) -> Session:
        return self._session_factory()

    # -- tasks -----------------------------------------------------------

    def save_task(self, context: TaskContext) -> TaskContext:
        with self._session() as session:
            row = session.get(TaskRow, context.id)
            if row is None:
                row = TaskRow(id=context.id, goal=context.goal,
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
            if row is None:
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
            query = session.query(TaskRow)
            if state:
                query = query.filter(TaskRow.state == state)
            ids = [row.id for row in query.all()]
        return [ctx for ctx in (self.load_task(i) for i in ids) if ctx is not None]

    # -- episodes ----------------------------------------------------------

    def save_episode(self, episode: Episode) -> Episode:
        with self._session() as session:
            session.add(EpisodeRow(
                id=episode.id, task_id=episode.task_id, goal=episode.goal,
                outcome=episode.outcome.value,
                payload_json=episode.model_dump(mode="json"),
                created_at=_aware(episode.created_at),
            ))
            session.commit()
        return episode

    def list_episodes(self, *, task_id: str | None = None) -> list[Episode]:
        with self._session() as session:
            query = session.query(EpisodeRow)
            if task_id:
                query = query.filter(EpisodeRow.task_id == task_id)
            return [Episode(**row.payload_json) for row in query.all()]

    # -- semantic facts ----------------------------------------------------

    def save_fact(self, fact: SemanticFact) -> SemanticFact:
        with self._session() as session:
            row = session.get(FactRow, fact.id)
            if row is None:
                row = FactRow(id=fact.id, content=fact.content)
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
                for row in session.query(FactRow).all()
            ]

    # -- skills ------------------------------------------------------------

    def save_skill(self, skill: Skill) -> Skill:
        with self._session() as session:
            row = session.get(SkillRow, skill.id)
            if row is None:
                row = SkillRow(id=skill.id, name=skill.name)
                session.add(row)
            row.version = skill.version
            row.status = skill.status.value
            row.payload_json = skill.model_dump(mode="json")
            row.created_at = _aware(skill.created_at)
            session.commit()
        return skill

    def list_skills(self, *, status: str | None = None) -> list[Skill]:
        with self._session() as session:
            query = session.query(SkillRow)
            if status:
                query = query.filter(SkillRow.status == status)
            return [Skill(**row.payload_json) for row in query.all()]

    # -- traces ------------------------------------------------------------

    def save_trace(self, trace: TraceEntry) -> TraceEntry:
        with self._session() as session:
            session.add(TraceRow(
                id=trace.id, task_id=trace.task_id, phase=trace.phase,
                detail=trace.detail, policy_basis=trace.policy_basis,
                created_at=_aware(trace.created_at),
            ))
            session.commit()
        return trace

    def list_traces(self, *, task_id: str | None = None) -> list[TraceEntry]:
        with self._session() as session:
            query = session.query(TraceRow).order_by(TraceRow.created_at)
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
