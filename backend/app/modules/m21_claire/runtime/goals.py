from __future__ import annotations
import json, secrets, uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from sqlalchemy import Integer, String, Text, create_engine, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

Clock = Callable[[], datetime]
TERMINAL = {"completed", "blocked", "failed", "exhausted", "not_accepted", "cancelled"}


class Base(DeclarativeBase):
    pass


class GoalRow(Base):
    __tablename__ = "claire_runtime_goals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(200), index=True)
    actor_id: Mapped[str] = mapped_column(String(200), index=True)
    purpose: Mapped[str] = mapped_column(Text)
    criteria: Mapped[str] = mapped_column(Text)
    max_steps: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    blocker: Mapped[str | None] = mapped_column(String(100), nullable=True)
    report: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdict: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))


@dataclass(frozen=True)
class Claim:
    goal_id: str
    tenant_id: str
    actor_id: str
    purpose: str
    criteria: list[dict[str, Any]]
    max_steps: int
    lease_token: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat()


class GoalStore:
    """Durable, tenant+actor-scoped goal/job store. Every read and write is keyed on both."""

    def __init__(self, url: str = "sqlite://", *, clock: Clock = _now, max_attempts: int = 3, lease_seconds: int = 120, create_schema: bool = False):
        kwargs: dict[str, Any] = {}
        if url == "sqlite://":
            kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
        self.engine = create_engine(url, **kwargs)
        if create_schema:  # production schema is owned by Alembic (20261008_m21_runtime_goals)
            Base.metadata.create_all(self.engine)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.clock, self.max_attempts, self.lease_seconds = clock, max_attempts, lease_seconds

    def close(self) -> None:
        self.engine.dispose()

    def create(self, tenant_id: str, actor_id: str, purpose: str, criteria: list[dict[str, Any]], max_steps: int) -> str:
        if not tenant_id or not actor_id:
            raise ValueError("tenant and actor are required")
        if not criteria:
            raise ValueError("at least one acceptance criterion is required")
        now = _iso(self.clock())
        gid = str(uuid.uuid4())
        with self._sessions.begin() as s:
            s.add(GoalRow(id=gid, tenant_id=tenant_id, actor_id=actor_id, purpose=purpose, criteria=json.dumps(criteria),
                          max_steps=max_steps, status="queued", attempts=0, created_at=now, updated_at=now))
        return gid

    def get(self, tenant_id: str, actor_id: str, goal_id: str) -> dict[str, Any] | None:
        with self._sessions() as s:
            row = s.scalars(select(GoalRow).where(GoalRow.id == goal_id, GoalRow.tenant_id == tenant_id,
                                                  GoalRow.actor_id == actor_id)).first()
            return None if row is None else self._view(row)

    def cancel(self, tenant_id: str, actor_id: str, goal_id: str) -> str:
        """Returns cancelled | not_found | not_cancellable (only queued goals can be cancelled in milestone 1)."""
        with self._sessions.begin() as s:
            res = s.execute(update(GoalRow).where(GoalRow.id == goal_id, GoalRow.tenant_id == tenant_id,
                            GoalRow.actor_id == actor_id, GoalRow.status == "queued")
                            .values(status="cancelled", updated_at=_iso(self.clock())))
            if res.rowcount == 1:
                return "cancelled"
            exists = s.scalars(select(GoalRow.id).where(GoalRow.id == goal_id, GoalRow.tenant_id == tenant_id,
                                                        GoalRow.actor_id == actor_id)).first()
        return "not_cancellable" if exists else "not_found"

    def claim(self, worker_id: str) -> Claim | None:
        now = self.clock()
        with self._sessions.begin() as s:
            # Expired leases that already used every attempt become failed, never retried again.
            s.execute(update(GoalRow).where(GoalRow.status == "running", GoalRow.lease_expires_at < _iso(now),
                      GoalRow.attempts >= self.max_attempts)
                      .values(status="failed", blocker="attempts_exhausted", lease_token=None, updated_at=_iso(now)))
            ids = s.scalars(select(GoalRow.id).where(
                (GoalRow.status == "queued") | ((GoalRow.status == "running") & (GoalRow.lease_expires_at < _iso(now))))
                .order_by(GoalRow.created_at).limit(5)).all()
            for gid in ids:
                token = secrets.token_hex(16)
                res = s.execute(update(GoalRow).where(GoalRow.id == gid, GoalRow.attempts < self.max_attempts,
                    (GoalRow.status == "queued") | ((GoalRow.status == "running") & (GoalRow.lease_expires_at < _iso(now))))
                    .values(status="running", attempts=GoalRow.attempts + 1, lease_owner=worker_id, lease_token=token,
                            lease_expires_at=_iso(now + timedelta(seconds=self.lease_seconds)), updated_at=_iso(now)))
                if res.rowcount == 1:
                    row = s.get(GoalRow, gid)
                    return Claim(gid, row.tenant_id, row.actor_id, row.purpose, json.loads(row.criteria), row.max_steps, token)
        return None

    def settle(self, claim: Claim, status: str, *, blocker: str | None, report: dict[str, Any], verdict: dict[str, Any] | None) -> bool:
        """Fenced: only the current lease token can settle. False means the lease was lost."""
        if status not in TERMINAL:
            raise ValueError("not a terminal status")
        with self._sessions.begin() as s:
            res = s.execute(update(GoalRow).where(GoalRow.id == claim.goal_id, GoalRow.lease_token == claim.lease_token,
                            GoalRow.status == "running")
                            .values(status=status, blocker=blocker, report=json.dumps(report), verdict=json.dumps(verdict),
                                    lease_token=None, lease_expires_at=None, updated_at=_iso(self.clock())))
            return res.rowcount == 1

    @staticmethod
    def _view(row: GoalRow) -> dict[str, Any]:
        return {"id": row.id, "purpose": row.purpose, "criteria": json.loads(row.criteria), "max_steps": row.max_steps,
                "status": row.status, "attempts": row.attempts, "blocker": row.blocker,
                "report": json.loads(row.report) if row.report else None,
                "verdict": json.loads(row.verdict) if row.verdict else None,
                "created_at": row.created_at, "updated_at": row.updated_at}
