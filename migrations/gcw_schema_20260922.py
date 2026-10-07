"""Frozen pre-Oct7 GCW tables for the historical migration, not live models."""
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase

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
