"""Durable registry for application browser sessions.

Tenant-scoped like every other Module 13 artifact: a record is only ever
read through its owning tenant id. The SQL implementation stores the whole
session record as JSON (same pattern as the Module 2 competition rows); the
in-memory implementation serves tests and single-process development.
"""
from __future__ import annotations

from copy import deepcopy
from threading import RLock

from sqlalchemy import JSON, String, UniqueConstraint, or_, select, update
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine

from .application_flow import ApplicationSession, StaleSessionError


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

    def _guarded_update(self, record: ApplicationSession, extra: list | None = None) -> bool:
        """One conditional UPDATE: atomic on SQLite and PostgreSQL alike (no read-then-write window).

        Succeeds only while the stored revision still equals the copy's revision (a missing rev in a
        legacy row counts as 0). On success the stored and in-memory revision advance by one."""
        expected = record.rev
        rev_col = ApplicationSessionRow.data["rev"].as_integer()
        rev_ok = (rev_col == expected) if expected else or_(rev_col == 0, rev_col.is_(None))
        record.rev = expected + 1
        payload = record.to_dict()
        with self.sessions.begin() as db:
            result = db.execute(update(ApplicationSessionRow).where(
                ApplicationSessionRow.tenant_id == record.tenant_id,
                ApplicationSessionRow.session_id == record.session_id,
                rev_ok, *(extra or []),
            ).values(data=payload))
            ok = result.rowcount == 1
        if not ok:
            record.rev = expected
        return ok

    def save(self, record: ApplicationSession) -> ApplicationSession:
        if self._guarded_update(record):
            return record
        with self.sessions() as db:
            exists = db.scalar(select(ApplicationSessionRow.id).where(
                ApplicationSessionRow.tenant_id == record.tenant_id,
                ApplicationSessionRow.session_id == record.session_id))
        if exists is None:
            return self.create(record)
        raise StaleSessionError("session changed since it was read; write refused")

    def compare_and_save(self, record: ApplicationSession, expected_status: str, expected_attempt_id: str) -> bool:
        """Atomic claim: conditional UPDATE on revision + status + attempt owner. False writes nothing."""
        extra = [ApplicationSessionRow.data["status"].as_string() == expected_status]
        if expected_attempt_id:
            extra.append(ApplicationSessionRow.data["attempt_id"].as_string() == expected_attempt_id)
        else:
            extra.append(or_(ApplicationSessionRow.data["attempt_id"].as_string() == "",
                             ApplicationSessionRow.data["attempt_id"].as_string().is_(None)))
        return self._guarded_update(record, extra)


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
        with self._lock:
            current = self._rows.get((record.tenant_id, record.session_id))
            if current is not None and current.rev != record.rev:
                raise StaleSessionError("session changed since it was read; write refused")
            record.rev += 1
            self._rows[(record.tenant_id, record.session_id)] = deepcopy(record)
            return record

    def compare_and_save(self, record: ApplicationSession, expected_status: str, expected_attempt_id: str) -> bool:
        with self._lock:
            current = self._rows.get((record.tenant_id, record.session_id))
            if current is None or current.rev != record.rev or not _matches(current, expected_status, expected_attempt_id):
                return False
            record.rev += 1
            self._rows[(record.tenant_id, record.session_id)] = deepcopy(record)
            return True
