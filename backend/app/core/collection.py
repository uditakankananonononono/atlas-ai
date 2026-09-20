"""Distributed, cost-visible collection orchestration."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base, SessionLocal

class CollectorType(str, Enum):
    OFFICIAL_API = "official_api"
    RSS = "rss"
    PUBLIC_PAGE = "public_page"
    AUTHORIZED_SESSION = "authorized_session"
    WEBHOOK = "webhook"

class CollectionSourceRow(Base):
    __tablename__ = "collection_sources"
    __table_args__ = (UniqueConstraint("tenant_id", "source_key"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    source_key: Mapped[str] = mapped_column(String(300))
    collector_type: Mapped[str] = mapped_column(String(40), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=50, index=True)
    cadence_seconds: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    cost_per_1000_requests_usd: Mapped[float] = mapped_column(Float, default=0)
    daily_request_cap: Mapped[int] = mapped_column(Integer, default=3)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    throttle_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class CollectedRecordRow(Base):
    __tablename__ = "collected_records"
    __table_args__ = (UniqueConstraint("tenant_id", "content_hash"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    source_key: Mapped[str] = mapped_column(String(300), index=True)
    canonical_url: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class CollectionRunRow(Base):
    __tablename__ = "collection_runs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    source_key: Mapped[str] = mapped_column(String(300), index=True)
    status: Mapped[str] = mapped_column(String(30))
    requests: Mapped[int] = mapped_column(Integer, default=0)
    records_new: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

def due_source_ids(limit: int = 1000) -> list[int]:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        statement = select(CollectionSourceRow.id).where(
            CollectionSourceRow.enabled.is_(True), CollectionSourceRow.next_run_at <= now
        ).order_by(CollectionSourceRow.priority.desc(), CollectionSourceRow.next_run_at).limit(limit)
        return list(db.scalars(statement))

def estimate_daily_cost(source: CollectionSourceRow) -> float:
    requests = min(source.daily_request_cap, max(1, 86400 // source.cadence_seconds))
    return round(requests * source.cost_per_1000_requests_usd / 1000, 6)
