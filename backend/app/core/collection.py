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
    LICENSED_DATA = "licensed_data"

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


def execute_registered_source(source_id: int) -> dict[str, Any]:
    """Run one configured allow-listed collector and durably store deduplicated records."""
    import asyncio, hashlib, json
    from datetime import timedelta
    from app.collectors.registry import build_collector
    started = datetime.now(timezone.utc)
    with SessionLocal() as db:
        source = db.get(CollectionSourceRow, source_id)
        if source is None:
            raise LookupError(f"collection source not found: {source_id}")
        if not source.enabled:
            return {"source_id": source_id, "status": "disabled"}
        if source.throttle_until and source.throttle_until > started:
            return {"source_id": source_id, "status": "throttled", "until": source.throttle_until.isoformat()}
        config = dict(source.config or {})
        adapter_name = config.get("adapter")
        if not adapter_name:
            raise ValueError("collection source config requires registered adapter")
        collector = build_collector(adapter_name)
        run = CollectionRunRow(tenant_id=source.tenant_id, source_key=source.source_key, status="running", started_at=started)
        db.add(run); db.commit()
        try:
            batch = asyncio.run(collector.collect(config))
            asyncio.run(collector.close())
            created = 0
            for item in batch.items:
                digest = hashlib.sha256(json.dumps(item.payload, sort_keys=True, default=str).encode()).hexdigest()
                exists = db.scalar(select(CollectedRecordRow.id).where(CollectedRecordRow.tenant_id == source.tenant_id, CollectedRecordRow.content_hash == digest))
                if exists is None:
                    db.add(CollectedRecordRow(tenant_id=source.tenant_id, source_key=source.source_key, canonical_url=item.canonical_url, content_hash=digest, payload=item.payload)); created += 1
            finished=datetime.now(timezone.utc)
            run.status="completed"; run.requests=batch.requests; run.records_new=created
            run.estimated_cost_usd=round(batch.requests * source.cost_per_1000_requests_usd / 1000, 6)
            run.finished_at=finished; run.detail={**batch.detail,"cursor":batch.cursor}
            source.last_run_at=finished; source.next_run_at=finished + timedelta(seconds=source.cadence_seconds)
            db.commit()
            return {"source_id":source_id,"status":"completed","records_new":created,"requests":batch.requests,"cursor":batch.cursor}
        except Exception as exc:
            run.status="failed"; run.finished_at=datetime.now(timezone.utc); run.detail={"error":type(exc).__name__,"message":str(exc)[:500]}; db.commit(); raise
