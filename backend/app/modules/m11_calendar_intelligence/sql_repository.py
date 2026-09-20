"""Tenant-scoped SQL storage for module 11, with append-only change rows."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CalendarSourceRow(Base):
    __tablename__ = "m11_calendar_sources"
    __table_args__ = (UniqueConstraint("tenant_id", "provider", "calendar_ref"),)
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    id: Mapped[str] = mapped_column(String(36), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    account_email: Mapped[str] = mapped_column(String(320))
    calendar_ref: Mapped[str] = mapped_column(Text)  # google calendar id or CalDAV URL
    encrypted_credentials: Mapped[str] = mapped_column(Text)
    sync_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    watch_channel_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    watch_channel_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    watch_resource_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    watch_expiration: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CalendarEventRow(Base):
    __tablename__ = "m11_calendar_events"
    __table_args__ = (UniqueConstraint("tenant_id", "source_id", "uid"),)
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    id: Mapped[str] = mapped_column(String(36), index=True)
    source_id: Mapped[str] = mapped_column(String(36), index=True)
    uid: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")
    start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SchedulingTaskRow(Base):
    __tablename__ = "m11_scheduling_tasks"
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    priority: Mapped[int] = mapped_column(Integer, default=3)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    prep_minutes: Mapped[int] = mapped_column(Integer, default=0)
    splittable: Mapped[bool] = mapped_column(Boolean, default=False)
    min_block_minutes: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SchedulingPrefsRow(Base):
    __tablename__ = "m11_scheduling_prefs"
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), unique=True)
    prefs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlanRow(Base):
    __tablename__ = "m11_plans"
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    id: Mapped[str] = mapped_column(String(36), index=True)
    week_start: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    approval_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlannedBlockRow(Base):
    __tablename__ = "m11_planned_blocks"
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    plan_id: Mapped[str] = mapped_column(String(36), index=True)
    task_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(10))
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(Text, nullable=True)


class CalendarEventLogRow(Base):
    """Append-only audit log for module 11 mutations."""

    __tablename__ = "m11_calendar_events_log"
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    event: Mapped[str] = mapped_column(String(60))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SqlCalendarRepository:
    def __init__(self, tenant_id: str, session_factory: sessionmaker = SessionLocal) -> None:
        self.tenant_id = tenant_id
        self.sessions = session_factory
        Base.metadata.create_all(engine)

    # -- sources ------------------------------------------------------------
    def save_source(self, *, source_id: str, provider: str, account_email: str,
                    calendar_ref: str, encrypted_credentials: str) -> None:
        with self.sessions.begin() as db:
            now = _utcnow()
            db.add(CalendarSourceRow(
                tenant_id=self.tenant_id, id=source_id, provider=provider,
                account_email=account_email, calendar_ref=calendar_ref,
                encrypted_credentials=encrypted_credentials, created_at=now, updated_at=now))
            self._log(db, "calendar_source", source_id, "source_registered",
                      {"provider": provider, "calendar_ref": calendar_ref})

    def get_source(self, source_id: str) -> CalendarSourceRow | None:
        with self.sessions() as db:
            return db.scalar(select(CalendarSourceRow).where(
                CalendarSourceRow.tenant_id == self.tenant_id, CalendarSourceRow.id == source_id))

    def get_source_by_channel(self, channel_id: str) -> CalendarSourceRow | None:
        with self.sessions() as db:
            return db.scalar(select(CalendarSourceRow).where(
                CalendarSourceRow.tenant_id == self.tenant_id,
                CalendarSourceRow.watch_channel_id == channel_id))

    def list_sources(self) -> list[CalendarSourceRow]:
        with self.sessions() as db:
            return list(db.scalars(select(CalendarSourceRow).where(
                CalendarSourceRow.tenant_id == self.tenant_id)))

    def update_watch(self, source_id: str, *, channel_id: str, channel_token: str,
                     resource_id: str, expiration: datetime | None) -> None:
        with self.sessions.begin() as db:
            row = self._source_in(db, source_id)
            if row is not None:
                row.watch_channel_id = channel_id
                row.watch_channel_token = channel_token
                row.watch_resource_id = resource_id
                row.watch_expiration = expiration
                row.updated_at = _utcnow()
                self._log(db, "calendar_source", source_id, "watch_registered",
                          {"channel_id": channel_id})

    def update_sync_token(self, source_id: str, sync_token: str) -> None:
        with self.sessions.begin() as db:
            row = self._source_in(db, source_id)
            if row is not None:
                row.sync_token = sync_token
                row.updated_at = _utcnow()

    def _source_in(self, db, source_id: str) -> CalendarSourceRow | None:
        return db.scalar(select(CalendarSourceRow).where(
            CalendarSourceRow.tenant_id == self.tenant_id, CalendarSourceRow.id == source_id))

    # -- events ---------------------------------------------------------------
    def upsert_event(self, *, event_id: str, source_id: str, uid: str, summary: str,
                     start: datetime | None, end: datetime | None,
                     location: str | None, status: str) -> str:
        """Insert or update by (tenant, source, uid). Returns 'created'/'updated'."""
        with self.sessions.begin() as db:
            row = db.scalar(select(CalendarEventRow).where(
                CalendarEventRow.tenant_id == self.tenant_id,
                CalendarEventRow.source_id == source_id, CalendarEventRow.uid == uid))
            if row is None:
                db.add(CalendarEventRow(
                    tenant_id=self.tenant_id, id=event_id, source_id=source_id, uid=uid,
                    summary=summary, start=start, end=end, location=location,
                    status=status, updated_at=_utcnow()))
                outcome = "created"
            else:
                row.summary = summary
                row.start = start
                row.end = end
                row.location = location
                row.status = status
                row.updated_at = _utcnow()
                outcome = "updated"
            self._log(db, "calendar_event", event_id if outcome == "created" else row.id,
                      f"event_{outcome}", {"uid": uid, "status": status})
            return outcome

    def list_events(self, start: datetime | None = None, end: datetime | None = None,
                    include_cancelled: bool = False, limit: int = 500) -> list[CalendarEventRow]:
        with self.sessions() as db:
            statement = select(CalendarEventRow).where(
                CalendarEventRow.tenant_id == self.tenant_id)
            if not include_cancelled:
                statement = statement.where(CalendarEventRow.status != "cancelled")
            if start is not None:
                statement = statement.where(CalendarEventRow.end > start)
            if end is not None:
                statement = statement.where(CalendarEventRow.start < end)
            return list(db.scalars(statement.order_by(CalendarEventRow.start).limit(limit)))

    # -- tasks ------------------------------------------------------------------
    def save_task(self, *, task_id: str, title: str, duration_minutes: int,
                  deadline: datetime, priority: int, location: str | None,
                  prep_minutes: int, splittable: bool, min_block_minutes: int) -> None:
        with self.sessions.begin() as db:
            db.add(SchedulingTaskRow(
                tenant_id=self.tenant_id, id=task_id, title=title,
                duration_minutes=duration_minutes, deadline=deadline, priority=priority,
                location=location, prep_minutes=prep_minutes, splittable=splittable,
                min_block_minutes=min_block_minutes, status="pending", created_at=_utcnow()))
            self._log(db, "scheduling_task", task_id, "task_created", {"title": title})

    def list_tasks(self, status: str = "pending") -> list[SchedulingTaskRow]:
        with self.sessions() as db:
            return list(db.scalars(select(SchedulingTaskRow).where(
                SchedulingTaskRow.tenant_id == self.tenant_id,
                SchedulingTaskRow.status == status)))

    def get_task(self, task_id: str) -> SchedulingTaskRow | None:
        with self.sessions() as db:
            return db.scalar(select(SchedulingTaskRow).where(
                SchedulingTaskRow.tenant_id == self.tenant_id, SchedulingTaskRow.id == task_id))

    def set_task_status(self, task_id: str, status: str) -> None:
        with self.sessions.begin() as db:
            row = db.scalar(select(SchedulingTaskRow).where(
                SchedulingTaskRow.tenant_id == self.tenant_id,
                SchedulingTaskRow.id == task_id))
            if row is not None:
                row.status = status

    # -- prefs ---------------------------------------------------------------------
    def get_prefs(self) -> dict[str, Any] | None:
        with self.sessions() as db:
            row = db.scalar(select(SchedulingPrefsRow).where(
                SchedulingPrefsRow.tenant_id == self.tenant_id))
            return dict(row.prefs) if row else None

    def save_prefs(self, prefs: dict[str, Any]) -> None:
        with self.sessions.begin() as db:
            row = db.scalar(select(SchedulingPrefsRow).where(
                SchedulingPrefsRow.tenant_id == self.tenant_id))
            if row is None:
                db.add(SchedulingPrefsRow(tenant_id=self.tenant_id, prefs=prefs,
                                          updated_at=_utcnow()))
            else:
                row.prefs = prefs
                row.updated_at = _utcnow()

    # -- plans -----------------------------------------------------------------------
    def save_plan(self, *, plan_id: str, week_start: str, status: str,
                  approval_id: str | None) -> None:
        with self.sessions.begin() as db:
            db.add(PlanRow(tenant_id=self.tenant_id, id=plan_id, week_start=week_start,
                           status=status, approval_id=approval_id, created_at=_utcnow()))

    def get_plan(self, plan_id: str) -> PlanRow | None:
        with self.sessions() as db:
            return db.scalar(select(PlanRow).where(
                PlanRow.tenant_id == self.tenant_id, PlanRow.id == plan_id))

    def set_plan_status(self, plan_id: str, status: str, approval_id: str | None = None) -> None:
        with self.sessions.begin() as db:
            row = db.scalar(select(PlanRow).where(
                PlanRow.tenant_id == self.tenant_id, PlanRow.id == plan_id))
            if row is not None:
                row.status = status
                if approval_id:
                    row.approval_id = approval_id
                self._log(db, "plan", plan_id, f"plan_{status}", {"approval_id": approval_id})

    def replace_plan_blocks(self, plan_id: str, blocks: list[dict[str, Any]]) -> None:
        with self.sessions.begin() as db:
            for old in db.scalars(select(PlannedBlockRow).where(
                    PlannedBlockRow.tenant_id == self.tenant_id,
                    PlannedBlockRow.plan_id == plan_id)):
                db.delete(old)
            for block in blocks:
                db.add(PlannedBlockRow(
                    tenant_id=self.tenant_id, plan_id=plan_id, task_id=block["task_id"],
                    kind=block["kind"], start=block["start"], end=block["end"],
                    location=block.get("location")))

    def plan_blocks(self, plan_id: str) -> list[PlannedBlockRow]:
        with self.sessions() as db:
            return list(db.scalars(select(PlannedBlockRow).where(
                PlannedBlockRow.tenant_id == self.tenant_id,
                PlannedBlockRow.plan_id == plan_id).order_by(PlannedBlockRow.start)))

    # -- audit ------------------------------------------------------------------------
    def _log(self, db, entity: str, entity_id: str, event: str, details: dict) -> None:
        db.add(CalendarEventLogRow(tenant_id=self.tenant_id, entity=entity,
                                   entity_id=entity_id, event=event, at=_utcnow(),
                                   details=details))
