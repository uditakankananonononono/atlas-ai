from __future__ import annotations
import json, secrets, uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from sqlalchemy import Integer, String, Text, UniqueConstraint, create_engine, exists, insert, literal, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

Clock = Callable[[], datetime]
TERMINAL = {"completed", "blocked", "failed", "exhausted", "not_accepted", "cancelled", "awaiting_review"}


class _NoApproval(Exception):
    pass


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


class ApprovalRow(Base):
    """One single-use approval for one gate of one exact call (tenant+actor+goal+capability+payload digest)."""
    __tablename__ = "claire_runtime_approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(200), index=True)
    actor_id: Mapped[str] = mapped_column(String(200), index=True)
    goal_id: Mapped[str] = mapped_column(String(36), index=True)
    capability: Mapped[str] = mapped_column(String(100))
    gate: Mapped[str] = mapped_column(String(20))
    payload_digest: Mapped[str] = mapped_column(String(64))
    approver: Mapped[str] = mapped_column(String(200))
    expires_at: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[str] = mapped_column(String(40))
    consumed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class EffectRow(Base):
    """Journal of one exact non-read call (goal + tool + argument digest). Written BEFORE dispatch.
    States: intent (dispatching or crashed), unknown (ended without a recorded outcome), committed, failed (never ran),
    absent (owner or reconcile established that no effect happened)."""
    __tablename__ = "claire_runtime_effects"
    __table_args__ = (UniqueConstraint("goal_id", "idempotency_key", name="uq_claire_runtime_effects_goal_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(200), index=True)
    actor_id: Mapped[str] = mapped_column(String(200), index=True)
    goal_id: Mapped[str] = mapped_column(String(36), index=True)
    tool: Mapped[str] = mapped_column(String(100))
    idempotency_key: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20))
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    receipt_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))


PENDING = ("intent", "unknown")
RETRIABLE = ("failed", "absent")


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

    def renew(self, claim: Claim) -> bool:
        """Extend the lease. True only if this claim's token still owns a running, unexpired goal.
        False means the lease is lost (expired, replaced, settled or cancelled) and the caller must stop."""
        now = self.clock()
        with self._sessions.begin() as s:
            res = s.execute(update(GoalRow).where(GoalRow.id == claim.goal_id, GoalRow.lease_token == claim.lease_token,
                            GoalRow.status == "running", GoalRow.lease_expires_at >= _iso(now))
                            .values(lease_expires_at=_iso(now + timedelta(seconds=self.lease_seconds)), updated_at=_iso(now)))
            return res.rowcount == 1

    def settle(self, claim: Claim, status: str, *, blocker: str | None, report: dict[str, Any], verdict: dict[str, Any] | None) -> bool:
        """Fenced: only the current lease token, with an unexpired lease, can settle. False means the lease was lost."""
        if status not in TERMINAL:
            raise ValueError("not a terminal status")
        with self._sessions.begin() as s:
            res = s.execute(update(GoalRow).where(GoalRow.id == claim.goal_id, GoalRow.lease_token == claim.lease_token,
                            GoalRow.status == "running", GoalRow.lease_expires_at >= _iso(self.clock()))
                            .values(status=status, blocker=blocker, report=json.dumps(report), verdict=json.dumps(verdict),
                                    lease_token=None, lease_expires_at=None, updated_at=_iso(self.clock())))
            return res.rowcount == 1

    def requeue(self, tenant_id: str, actor_id: str, goal_id: str) -> str:
        """awaiting_review -> queued so the owner's new approvals can be used. Returns requeued | not_found | not_requeueable."""
        with self._sessions.begin() as s:
            res = s.execute(update(GoalRow).where(GoalRow.id == goal_id, GoalRow.tenant_id == tenant_id,
                            GoalRow.actor_id == actor_id, GoalRow.status == "awaiting_review", GoalRow.attempts < self.max_attempts)
                            .values(status="queued", blocker=None, updated_at=_iso(self.clock())))
            if res.rowcount == 1:
                return "requeued"
            exists = s.scalars(select(GoalRow.id).where(GoalRow.id == goal_id, GoalRow.tenant_id == tenant_id,
                                                        GoalRow.actor_id == actor_id)).first()
        return "not_requeueable" if exists else "not_found"

    # --- effect journal --------------------------------------------------------------------------
    def peek_effect(self, principal: Any, key: str) -> dict[str, Any] | None:
        with self._sessions.begin() as s:
            row = s.scalars(select(EffectRow).where(EffectRow.goal_id == principal.goal_id, EffectRow.idempotency_key == key,
                            EffectRow.tenant_id == principal.tenant_id, EffectRow.actor_id == principal.actor_id)).first()
            return None if row is None else self._effect_view(row, with_receipt=True)

    def _live_lease(self, principal: Any):
        """SQL condition: the goal row still carries THIS principal's token, is running and unexpired. It is embedded in the
        journal write statement itself, so the check and the write are one atomic statement (no check-then-write gap)."""
        return (GoalRow.id == principal.goal_id, GoalRow.tenant_id == principal.tenant_id, GoalRow.actor_id == principal.actor_id,
                GoalRow.lease_token == principal.lease_token, GoalRow.status == "running",
                GoalRow.lease_expires_at >= _iso(self.clock()))

    def begin_effect(self, principal: Any, tool: str, key: str, *, takeover_pending: bool,
                     gates: tuple[str, ...] = ()) -> tuple[str, str | None, str | None]:
        """Returns (status, effect_id, receipt_json): new | replay | pending | lease_lost | approval_required.
        'new' means the caller owns an intent row and may dispatch. ONE transaction: the fenced reservation and the consumption
        of the gate approvals (capability = tool, digest = key) commit together or not at all, so replay, pending, lease_lost and
        a missing approval never consume anything and never leave an intent behind."""
        if principal.lease_token is None:
            return ("lease_lost", None, None)
        try:
            return self._begin_effect(principal, tool, key, takeover_pending, gates)
        except _NoApproval:
            return ("approval_required", None, None)
        except IntegrityError:
            return ("pending", None, None)  # another handle inserted the same call first; this transaction rolled back

    def _begin_effect(self, principal: Any, tool: str, key: str, takeover_pending: bool, gates: tuple[str, ...]) -> tuple[str, str | None, str | None]:
        with self._sessions.begin() as s:
            row = s.scalars(select(EffectRow).where(EffectRow.goal_id == principal.goal_id, EffectRow.idempotency_key == key,
                                                    EffectRow.tenant_id == principal.tenant_id,
                                                    EffectRow.actor_id == principal.actor_id)).first()
            now = _iso(self.clock())
            if row is None:
                eid = str(uuid.uuid4())
                cols = ("id", "tenant_id", "actor_id", "goal_id", "tool", "idempotency_key", "state", "attempts", "created_at", "updated_at")
                vals = (eid, principal.tenant_id, principal.actor_id, principal.goal_id, tool, key, "intent", 1, now, now)
                src = select(*[literal(v) for v in vals]).where(exists(select(GoalRow.id).where(*self._live_lease(principal))))
                res = s.execute(insert(EffectRow).from_select(cols, src))  # no SAVEPOINT: pysqlite would commit it early
                if res.rowcount != 1:
                    return ("lease_lost", None, None)
                self._consume(s, principal, tool, key, gates)  # raises _NoApproval: the reservation above rolls back too
                return ("new", eid, None)
            if row.state == "committed":
                return ("replay", row.id, row.receipt_json)
            if row.state in RETRIABLE or (row.state in PENDING and takeover_pending):
                res = s.execute(update(EffectRow).where(EffectRow.id == row.id, EffectRow.state == row.state,
                                exists(select(GoalRow.id).where(*self._live_lease(principal))))
                                .values(state="intent", attempts=EffectRow.attempts + 1, updated_at=now))
                if res.rowcount == 1:
                    self._consume(s, principal, tool, key, gates)
                    return ("new", row.id, None)
                live = s.scalars(select(GoalRow.id).where(*self._live_lease(principal))).first()
                return ("lease_lost", None, None) if live is None else ("pending", row.id, None)
            return ("pending", row.id, None)

    def mark_effect(self, effect_id: str, state: str, receipt: dict[str, Any] | None = None) -> bool:
        """intent -> committed | failed | unknown. Records truth, so it is deliberately not lease-fenced."""
        if state not in ("committed", "failed", "unknown"):
            raise ValueError("bad effect state")
        with self._sessions.begin() as s:
            res = s.execute(update(EffectRow).where(EffectRow.id == effect_id, EffectRow.state == "intent")
                            .values(state=state, receipt_json=json.dumps(receipt) if receipt is not None else None,
                                    updated_at=_iso(self.clock())))
            return res.rowcount == 1

    def pending_effects(self, goal_id: str) -> list[dict[str, Any]]:
        with self._sessions.begin() as s:
            rows = s.scalars(select(EffectRow).where(EffectRow.goal_id == goal_id, EffectRow.state.in_(PENDING))
                             .order_by(EffectRow.created_at)).all()
            return [self._effect_view(r) for r in rows]

    def resolve_effect(self, goal_id: str, effect_id: str, outcome: str, *, receipt: dict[str, Any] | None = None,
                       tenant_id: str | None = None, actor_id: str | None = None, require_not_running: bool = False) -> str:
        """intent|unknown -> committed | absent. Returns resolved | not_found | not_pending | goal_running."""
        if outcome not in ("committed", "absent"):
            raise ValueError("bad outcome")
        with self._sessions.begin() as s:
            q = select(EffectRow).where(EffectRow.id == effect_id, EffectRow.goal_id == goal_id)
            if tenant_id is not None:
                q = q.where(EffectRow.tenant_id == tenant_id, EffectRow.actor_id == actor_id)
            row = s.scalars(q).first()
            if row is None:
                return "not_found"
            if require_not_running and s.scalars(select(GoalRow.status).where(GoalRow.id == goal_id)).first() == "running":
                return "goal_running"
            res = s.execute(update(EffectRow).where(EffectRow.id == effect_id, EffectRow.state.in_(PENDING))
                            .values(state=outcome, receipt_json=json.dumps(receipt) if outcome == "committed" and receipt is not None else None,
                                    updated_at=_iso(self.clock())))
            return "resolved" if res.rowcount == 1 else "not_pending"

    def list_effects(self, tenant_id: str, actor_id: str, goal_id: str) -> list[dict[str, Any]] | None:
        with self._sessions.begin() as s:
            if not s.scalars(select(GoalRow.id).where(GoalRow.id == goal_id, GoalRow.tenant_id == tenant_id, GoalRow.actor_id == actor_id)).first():
                return None
            rows = s.scalars(select(EffectRow).where(EffectRow.goal_id == goal_id, EffectRow.tenant_id == tenant_id,
                             EffectRow.actor_id == actor_id).order_by(EffectRow.created_at)).all()
            return [self._effect_view(r) for r in rows]

    @staticmethod
    def _effect_view(row: EffectRow, *, with_receipt: bool = False) -> dict[str, Any]:
        out = {"id": row.id, "tool": row.tool, "idempotency_key": row.idempotency_key, "state": row.state,
               "attempts": row.attempts, "created_at": row.created_at, "updated_at": row.updated_at}
        if with_receipt:
            out["receipt_json"] = row.receipt_json
        return out

    # --- approval ledger -------------------------------------------------------------------------
    def grant(self, tenant_id: str, actor_id: str, goal_id: str, capability: str, gate: str, digest: str,
              approver: str, ttl_seconds: int = 900) -> str:
        if gate not in {"payment", "comms"}:
            raise ValueError("unknown gate")
        if not (1 <= ttl_seconds <= 86400) or len(digest) != 64:
            raise ValueError("invalid approval")
        now = self.clock()
        with self._sessions.begin() as s:
            if not s.scalars(select(GoalRow.id).where(GoalRow.id == goal_id, GoalRow.tenant_id == tenant_id,
                                                      GoalRow.actor_id == actor_id)).first():
                raise KeyError(goal_id)
            aid = str(uuid.uuid4())
            s.add(ApprovalRow(id=aid, tenant_id=tenant_id, actor_id=actor_id, goal_id=goal_id, capability=capability, gate=gate,
                              payload_digest=digest, approver=approver, expires_at=_iso(now + timedelta(seconds=ttl_seconds)),
                              created_at=_iso(now)))
        return aid

    def _consume(self, s: Any, principal: Any, capability: str, digest: str, gates: tuple[str, ...]) -> None:
        """Inside the caller's transaction. Raises _NoApproval (the caller rolls back) unless every gate had its own approval."""
        now = _iso(self.clock())
        for gate in gates:
            res = s.execute(update(ApprovalRow).where(
                ApprovalRow.id == select(ApprovalRow.id).where(
                    ApprovalRow.tenant_id == principal.tenant_id, ApprovalRow.actor_id == principal.actor_id,
                    ApprovalRow.goal_id == principal.goal_id, ApprovalRow.capability == capability,
                    ApprovalRow.gate == gate, ApprovalRow.payload_digest == digest,
                    ApprovalRow.consumed_at.is_(None), ApprovalRow.expires_at > now).limit(1).scalar_subquery(),
                ApprovalRow.consumed_at.is_(None)).values(consumed_at=now))
            if res.rowcount != 1:
                raise _NoApproval

    def consume_all(self, principal: Any, capability: str, digest: str, gates: tuple[str, ...]) -> bool:
        """All-or-nothing: every gate needs its own unexpired, unconsumed, exactly-matching approval; consumed in one transaction."""
        try:
            with self._sessions.begin() as s:
                self._consume(s, principal, capability, digest, gates)
        except _NoApproval:
            return False
        return True

    @staticmethod
    def _view(row: GoalRow) -> dict[str, Any]:
        return {"id": row.id, "purpose": row.purpose, "criteria": json.loads(row.criteria), "max_steps": row.max_steps,
                "status": row.status, "attempts": row.attempts, "blocker": row.blocker,
                "report": json.loads(row.report) if row.report else None,
                "verdict": json.loads(row.verdict) if row.verdict else None,
                "created_at": row.created_at, "updated_at": row.updated_at}
