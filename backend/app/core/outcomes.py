"""Provenance-first outcome data. Predictive training stays disabled until real labels exist."""
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class OutcomeEvidenceRow(Base):
    __tablename__ = "outcome_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    opportunity_id: Mapped[str] = mapped_column(String(200), index=True)
    source_type: Mapped[str] = mapped_column(String(40))  # official_page, official_api, youtube_api, atlas_outcome
    source_url: Mapped[str] = mapped_column(Text)
    source_record_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    features: Mapped[dict[str, Any]] = mapped_column(JSON)
    won: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class PredictionProvenanceRow(Base):
    __tablename__ = "prediction_provenance"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    opportunity_id: Mapped[str] = mapped_column(String(200), index=True)
    model_version: Mapped[str] = mapped_column(String(100))
    evidence_ids: Mapped[list[str]] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
