"""Durable registry for application browser sessions.

Tenant-scoped like every other Module 13 artifact: a record is only ever
read through its owning tenant id. The SQL implementation stores the whole
session record as JSON (same pattern as the Module 2 competition rows); the
in-memory implementation serves tests and single-process development.
"""
from __future__ import annotations

from copy import deepcopy
from threading import RLock

from sqlalchemy import JSON, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine

from .application_flow import ApplicationSession


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
        with self.sessions.begin() as db:
            row = db.scalar(select(ApplicationSessionRow).where(
                ApplicationSessionRow.tenant_id == record.tenant_id,
                ApplicationSessionRow.session_id == record.session_id,
            ))
            if row is None:
                db.add(ApplicationSessionRow(
                    tenant_id=record.tenant_id,
                    session_id=record.session_id,
                    data=record.to_dict(),
                ))
            else:
                row.data = record.to_dict()
        return record

    def compare_and_save(self, record: ApplicationSession, expected_status: str, expected_attempt_id: str) -> bool:
        """Write only if the persisted row still has the expected status and attempt owner.

        Row-locked read-modify-write inside one transaction (FOR UPDATE where the dialect supports
        it; SQLite serialises writers). Returns False, writing nothing, when the row has moved on."""
        with self.sessions.begin() as db:
            row = db.scalar(select(ApplicationSessionRow).where(
                ApplicationSessionRow.tenant_id == record.tenant_id,
                ApplicationSessionRow.session_id == record.session_id,
            ).with_for_update())
            if row is None or not _matches(ApplicationSession.from_dict(row.data), expected_status, expected_attempt_id):
                return False
            row.data = record.to_dict()
            return True


def _matches(current: ApplicationSession, expected_status: str, expected_attempt_id: str) -> bool:
    return current.status == expected_status and current.attempt_id == expected_attempt_id


class InMemoryApplicationSessionStore:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], ApplicationSession] = {}
        self._lock = RLock()

    def create(self, record: ApplicationSession) -> ApplicationSession:
        with self._lock:
            self._rows[(record.tenant_id, record.session_id)] = deepcopy(record)
            return deepcopy(record)

    def get(self, tenant_id: str, session_id: str) -> ApplicationSession | None:
        with self._lock:
            row = self._rows.get((tenant_id, session_id))
            return deepcopy(row) if row else None

    def save(self, record: ApplicationSession) -> ApplicationSession:
        return self.create(record)

    def compare_and_save(self, record: ApplicationSession, expected_status: str, expected_attempt_id: str) -> bool:
        with self._lock:
            current = self._rows.get((record.tenant_id, record.session_id))
            if current is None or not _matches(current, expected_status, expected_attempt_id):
                return False
            self._rows[(record.tenant_id, record.session_id)] = deepcopy(record)
            return True
