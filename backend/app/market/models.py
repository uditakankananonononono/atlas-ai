from datetime import datetime, timezone
from typing import Any
from sqlalchemy import JSON, BigInteger, DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class MarketObservationRow(Base):
    __tablename__ = "market_observations"
    __table_args__ = (UniqueConstraint("source", "external_id", "observed_at"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    external_id: Mapped[str] = mapped_column(String(300), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_url: Mapped[str] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class FactorValueRow(Base):
    __tablename__ = "market_factor_values"
    __table_args__ = (UniqueConstraint("tenant_id", "observation_id", "factor_key"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    observation_id: Mapped[int] = mapped_column(BigInteger, index=True)
    factor_key: Mapped[str] = mapped_column(String(500), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON)
