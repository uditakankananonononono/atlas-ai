from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, LargeBinary, String, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine

from .domain import ActionType, AuditEvent


class BrowserAuditRow(Base):
    __tablename__ = "m13_browser_audit_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    run_id: Mapped[str] = mapped_column(String(120), index=True)
    action: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConsumedApprovalRow(Base):
    __tablename__ = "m13_consumed_approvals"
    approval_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PreSubmitCaptureRow(Base):
    __tablename__ = "m13_pre_submit_captures"
    __table_args__ = (UniqueConstraint("tenant_id", "capture_sha256"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    session_id: Mapped[str] = mapped_column(String(300), index=True)
    capture_sha256: Mapped[str] = mapped_column(String(64), index=True)
    artifact: Mapped[dict[str, Any]] = mapped_column(JSON)
    dom_bytes: Mapped[bytes] = mapped_column(LargeBinary)
    screenshot_bytes: Mapped[bytes] = mapped_column(LargeBinary)
    persisted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SQLStore:
    def __init__(self, sessions: sessionmaker | None = None):
        if sessions is None:
            Base.metadata.create_all(engine)
            sessions = SessionLocal
        self.sessions = sessions

    async def append_audit(self, event: AuditEvent) -> None:
        with self.sessions.begin() as db:
            db.add(BrowserAuditRow(
                tenant_id=event.tenant_id,
                run_id=event.run_id,
                action=event.action.value,
                payload=event.payload,
                occurred_at=datetime.fromtimestamp(event.occurred_at, timezone.utc),
            ))

    async def was_consumed(self, approval_id: str) -> bool:
        with self.sessions() as db:
            return db.get(ConsumedApprovalRow, approval_id) is not None

    async def consume(self, approval_id: str, tenant_id: str) -> None:
        """Atomically claim an approval. The primary key closes concurrent replay races."""
        try:
            with self.sessions.begin() as db:
                db.add(ConsumedApprovalRow(
                    approval_id=approval_id,
                    tenant_id=tenant_id,
                    consumed_at=datetime.now(timezone.utc),
                ))
                db.flush()
        except IntegrityError as error:
            raise PermissionError("approval was already consumed") from error

    async def persist_capture(self, tenant_id: str, session_id: str, capture_sha256: str,
                              artifact: dict, dom_bytes: bytes, screenshot_bytes: bytes):
        try:
            with self.sessions.begin() as db:
                row = PreSubmitCaptureRow(tenant_id=tenant_id, session_id=session_id,
                    capture_sha256=capture_sha256, artifact=artifact, dom_bytes=dom_bytes,
                    screenshot_bytes=screenshot_bytes, persisted_at=datetime.now(timezone.utc))
                db.add(row);db.flush();return row
        except IntegrityError as error:
            raise ValueError("capture hash already persisted; immutable capture cannot be replaced") from error

    async def get_capture(self, tenant_id: str, capture_sha256: str):
        with self.sessions() as db:
            return db.scalar(select(PreSubmitCaptureRow).where(
                PreSubmitCaptureRow.tenant_id == tenant_id,
                PreSubmitCaptureRow.capture_sha256 == capture_sha256))

    async def audit_events(self, tenant_id: str, run_id: str, limit: int = 100) -> list[AuditEvent]:
        limit = max(1, min(limit, 1000))
        with self.sessions() as db:
            rows = db.scalars(
                select(BrowserAuditRow)
                .where(BrowserAuditRow.tenant_id == tenant_id, BrowserAuditRow.run_id == run_id)
                .order_by(BrowserAuditRow.id.desc())
                .limit(limit)
            ).all()
        return [AuditEvent(row.tenant_id, row.run_id, ActionType(row.action), row.payload, row.occurred_at.timestamp()) for row in rows]
