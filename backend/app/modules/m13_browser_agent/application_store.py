"""Durable registry for application browser sessions.

Tenant-scoped like every other Module 13 artifact: a record is only ever
read through its owning tenant id. The SQL implementation stores the whole
session record as JSON (same pattern as the Module 2 competition rows); the
in-memory implementation serves tests and single-process development.
"""
from __future__ import annotations

from copy import deepcopy
from threading import RLock

from sqlalchemy import JSON, String, UniqueConstraint, select, update, func
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine

from .application_flow import ApplicationSession, SessionRevisionConflict


class ApplicationSessionRow(Base):
    __tablename__ = "m13_application_sessions"
    __table_args__ = (UniqueConstraint("tenant_id", "session_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    session_id: Mapped[str] = mapped_column(String(60), index=True)
    data: Mapped[dict] = mapped_column(JSON)


class SQLApplicationSessionStore:
    def __init__(self, session_factory: sessionmaker | None = None) -> None:
        if session_factory is None:
            Base.metadata.create_all(engine)
            session_factory = SessionLocal
        self.sessions = session_factory

    def create(self, record: ApplicationSession) -> ApplicationSession:
        with self.sessions.begin() as db:
            db.add(ApplicationSessionRow(
                tenant_id=record.tenant_id,
                session_id=record.session_id,
                data=record.to_dict(),
            ))
        return record

    def get(self, tenant_id: str, session_id: str) -> ApplicationSession | None:
        with self.sessions() as db:
            row = db.scalar(select(ApplicationSessionRow).where(
                ApplicationSessionRow.tenant_id == tenant_id,
                ApplicationSessionRow.session_id == session_id,
            ))
            return ApplicationSession.from_dict(row.data) if row else None

    def save(self, record: ApplicationSession) -> ApplicationSession:
        expected = record.revision
        data = record.to_dict()
        data["revision"] = expected + 1
        with self.sessions.begin() as db:
            claimed = db.execute(update(ApplicationSessionRow).where(
                ApplicationSessionRow.tenant_id == record.tenant_id,
                ApplicationSessionRow.session_id == record.session_id,
                func.coalesce(ApplicationSessionRow.data["revision"].as_integer(), 0) == expected,
            ).values(data=data))
            if claimed.rowcount != 1:
                raise SessionRevisionConflict("application session changed; reload before saving")
        record.revision = expected + 1
        return record


class InMemoryApplicationSessionStore:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], ApplicationSession] = {}
        self._lock = RLock()

    def create(self, record: ApplicationSession) -> ApplicationSession:
        with self._lock:
            if (record.tenant_id, record.session_id) in self._rows:
                raise SessionRevisionConflict("application session already exists")
            self._rows[(record.tenant_id, record.session_id)] = deepcopy(record)
            return deepcopy(record)

    def get(self, tenant_id: str, session_id: str) -> ApplicationSession | None:
        with self._lock:
            row = self._rows.get((tenant_id, session_id))
            return deepcopy(row) if row else None

    def save(self, record: ApplicationSession) -> ApplicationSession:
        with self._lock:
            existing = self._rows.get((record.tenant_id, record.session_id))
            if existing is None or existing.revision != record.revision:
                raise SessionRevisionConflict("application session changed; reload before saving")
            updated = deepcopy(record)
            updated.revision += 1
            self._rows[(record.tenant_id, record.session_id)] = updated
            record.revision = updated.revision
            return deepcopy(updated)
