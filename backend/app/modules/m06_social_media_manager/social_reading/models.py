"""Tenant-scoped knowledge records for people and their observed work."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SocialPersonRow(Base):
    """One person in the owner's network, deduplicated per platform+handle."""

    __tablename__ = "m06_social_people"
    __table_args__ = (UniqueConstraint("tenant_id", "platform", "handle", name="uq_m06_social_person"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    platform: Mapped[str] = mapped_column(String(40))
    handle: Mapped[str] = mapped_column(String(300))
    display_name: Mapped[str] = mapped_column(String(600), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    external_url: Mapped[str] = mapped_column(String(2000), default="")
    relation: Mapped[str] = mapped_column(String(40), default="follower")  # follower | following | connection
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SocialWorkRow(Base):
    """One observed piece of work: a post, launch, patent, article, release."""

    __tablename__ = "m06_social_work"
    __table_args__ = (UniqueConstraint("tenant_id", "platform", "external_id", name="uq_m06_social_work"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    platform: Mapped[str] = mapped_column(String(40))
    handle: Mapped[str] = mapped_column(String(300), index=True)
    external_id: Mapped[str] = mapped_column(String(600))
    kind: Mapped[str] = mapped_column(String(40), default="post")  # post | launch | patent | article | release
    text: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(2000), default="")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    idea_id: Mapped[str | None] = mapped_column(String(80), nullable=True)  # set when harvested into M19
    signal_score: Mapped[float] = mapped_column(Float, default=0.0)


class SocialReadRunRow(Base):
    """Audit of each read run: what was read, what came back, what blocked it."""

    __tablename__ = "m06_social_read_runs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    platform: Mapped[str] = mapped_column(String(40))
    operation: Mapped[str] = mapped_column(String(40))
    session_id: Mapped[str] = mapped_column(String(300), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="running")  # running | complete | blocked | failed
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
