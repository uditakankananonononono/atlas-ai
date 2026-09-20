"""Human Approval Center (Module 0) domain logic.

Every module that can perform an irreversible action (send, publish,
submit, delete, pay) proposes the action here first. The center persists
the request, enforces time limits, records an append-only audit trail,
notifies dashboard subscribers, and lets a calling worker block until a
human decision lands. Nothing in this module executes the action itself.

No FastAPI imports live here; the HTTP surface is routes.py. The service
constructor takes every dependency explicitly, so tests inject their own
database and clock.
"""
from __future__ import annotations

import queue
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import JSON, DateTime, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker
from uuid import uuid4

from app.core.database import Base, SessionLocal, engine
from app.core.models import ApprovalStatus
from app.modules.catalog import BY_ID
from app.modules.m00_approval_center.schemas import DEFAULT_USER_ID

TERMINAL_STATUSES = {ApprovalStatus.APPROVED, ApprovalStatus.DENIED, ApprovalStatus.EXPIRED}
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_WAIT_TIMEOUT_SECONDS = 3600.0


class ApprovalNotFoundError(KeyError):
    """Raised when an approval id does not exist."""


class ApprovalConflictError(RuntimeError):
    """Raised when a request can no longer change state (decided or expired)."""


def _aware(moment: datetime) -> datetime:
    """Treat naive datetimes coming back from SQLite as UTC."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


class ApprovalRequestRow(Base):
    """Spec data model: one row per gated action awaiting a human."""

    __tablename__ = "m00_approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True)
    module_id: Mapped[int]
    action_type: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)


class ApprovalEventRow(Base):
    """Append-only decision log. Rows are never updated or deleted."""

    __tablename__ = "m00_approval_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    approval_id: Mapped[str] = mapped_column(String(36), index=True)
    event: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _view(row: ApprovalRequestRow) -> dict[str, Any]:
    """Render a stored row as the plain dict the schemas and SDK return."""
    return {
        "id": row.id,
        "module_id": row.module_id,
        "action_type": row.action_type,
        "payload": row.payload,
        "user_id": row.user_id,
        "status": ApprovalStatus(row.status),
        "created_at": _aware(row.created_at),
        "expires_at": _aware(row.expires_at) if row.expires_at else None,
        "decided_at": _aware(row.decided_at) if row.decided_at else None,
        "approved_by": row.approved_by,
    }


class ApprovalBroadcaster:
    """In-process fan-out of approval events to dashboard subscribers.

    Each subscriber gets a thread-safe queue; publishers never block on a
    slow consumer. Cross-process fan-out (Redis Streams) is integrator
    work, documented in INTEGRATION.md.
    """

    def __init__(self, max_queue_size: int = 1000) -> None:
        self._max_queue_size = max_queue_size
        self._subscribers: set[queue.Queue] = set()
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        """Register a new subscriber and return its event queue."""
        subscriber: queue.Queue = queue.Queue(maxsize=self._max_queue_size)
        with self._lock:
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue) -> None:
        """Remove a subscriber; its queue stops receiving events."""
        with self._lock:
            self._subscribers.discard(subscriber)

    def publish(self, event: dict[str, Any]) -> None:
        """Push one event to every subscriber, dropping for full queues only."""
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(event)
            except queue.Full:
                continue


class Service:
    """The Approval Center state machine.

    Dependencies are injected: a SQLAlchemy session factory, an event
    broadcaster, and a clock (so tests control time). With no arguments it
    binds to the shared database engine and wall-clock UTC.
    """

    def __init__(
        self,
        session_factory: sessionmaker | None = None,
        broadcaster: ApprovalBroadcaster | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if session_factory is None:
            Base.metadata.create_all(engine)
            session_factory = SessionLocal
        self._sessions = session_factory
        self._broadcaster = broadcaster or ApprovalBroadcaster()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._callbacks: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
        self._callback_lock = threading.Lock()

    @property
    def broadcaster(self) -> ApprovalBroadcaster:
        return self._broadcaster

    def submit(
        self,
        *,
        module_id: int,
        action_type: str,
        payload: dict[str, Any],
        user_id: str = DEFAULT_USER_ID,
        ttl_seconds: int | None = None,
    ) -> dict[str, Any]:
        """Persist a new pending approval request and notify subscribers.

        Raises ValueError for an unknown module id so a misrouted gated
        action fails loudly instead of sitting in the queue forever.
        """
        if module_id not in BY_ID:
            raise ValueError(f"unknown module id: {module_id}")
        now = self._clock()
        expires_at = now + timedelta(seconds=ttl_seconds) if ttl_seconds else None
        row = ApprovalRequestRow(
            id=str(uuid4()),
            user_id=user_id,
            module_id=module_id,
            action_type=action_type,
            payload=payload,
            status=ApprovalStatus.PENDING.value,
            created_at=now,
            expires_at=expires_at,
        )
        with self._sessions.begin() as db:
            db.add(row)
            db.add(ApprovalEventRow(approval_id=row.id, event="created", actor=None, at=now))
        view = _view(row)
        self._broadcaster.publish({"type": "approval_request", "approval": _jsonable(view)})
        return view

    def get(self, approval_id: str) -> dict[str, Any]:
        """Return one request, applying expiry lazily. Raises ApprovalNotFoundError."""
        with self._sessions.begin() as db:
            row = self._fetch(db, approval_id)
            self._expire_if_overdue(db, row, self._clock())
            return _view(row)

    def list(
        self,
        *,
        status: ApprovalStatus | None = None,
        module_id: int | None = None,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List requests newest first, optionally filtered."""
        with self._sessions.begin() as db:
            statement = select(ApprovalRequestRow).order_by(ApprovalRequestRow.created_at.desc()).limit(limit)
            if status is not None:
                statement = statement.where(ApprovalRequestRow.status == status.value)
            if module_id is not None:
                statement = statement.where(ApprovalRequestRow.module_id == module_id)
            if user_id is not None:
                statement = statement.where(ApprovalRequestRow.user_id == user_id)
            rows = list(db.scalars(statement))
            now = self._clock()
            for row in rows:
                self._expire_if_overdue(db, row, now)
            return [_view(row) for row in rows]

    def decide(self, approval_id: str, decision: ApprovalStatus, decided_by: str) -> dict[str, Any]:
        """Record a human decision. Decisions are final; expiry wins races.

        Raises ApprovalNotFoundError for a missing id, ValueError for a
        decision that is not approved/denied, and ApprovalConflictError
        when the request is already decided or expired.
        """
        if decision not in {ApprovalStatus.APPROVED, ApprovalStatus.DENIED}:
            raise ValueError("decision must be approved or denied")
        now = self._clock()
        with self._sessions.begin() as db:
            row = self._fetch(db, approval_id)
            if self._expire_if_overdue(db, row, now):
                raise ApprovalConflictError("approval has expired")
            if row.status != ApprovalStatus.PENDING.value:
                raise ApprovalConflictError(f"approval already {row.status}")
            row.status = decision.value
            row.decided_at = now
            row.approved_by = decided_by
            db.add(ApprovalEventRow(approval_id=row.id, event=decision.value, actor=decided_by, at=now))
            view = _view(row)
        self._broadcaster.publish({"type": "approval_decision", "approval": _jsonable(view)})
        self._fire_callbacks(approval_id, view)
        return view

    def expire_overdue(self) -> list[str]:
        """Sweep every pending request past its deadline into expired.

        A Celery beat job should call this; see INTEGRATION.md.
        """
        now = self._clock()
        expired: list[str] = []
        with self._sessions.begin() as db:
            statement = select(ApprovalRequestRow).where(
                ApprovalRequestRow.status == ApprovalStatus.PENDING.value,
                ApprovalRequestRow.expires_at.is_not(None),
                ApprovalRequestRow.expires_at <= now,
            )
            for row in db.scalars(statement):
                self._expire(db, row, now)
                expired.append(row.id)
        for approval_id in expired:
            self._broadcaster.publish({"type": "approval_expired", "approval_id": approval_id})
            self._fire_callbacks(approval_id, self.get(approval_id))
        return expired

    def audit(self, approval_id: str) -> list[dict[str, Any]]:
        """Return the immutable event log for one request, oldest first."""
        with self._sessions() as db:
            statement = (
                select(ApprovalEventRow)
                .where(ApprovalEventRow.approval_id == approval_id)
                .order_by(ApprovalEventRow.id)
            )
            events = [
                {"event": row.event, "actor": row.actor, "at": _aware(row.at)}
                for row in db.scalars(statement)
            ]
        if not events:
            raise ApprovalNotFoundError(approval_id)
        return events

    def register_callback(self, approval_id: str, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register an in-process callback fired when the request resolves.

        Used by workers that proposed an action and hold the means to
        execute it. Callback exceptions never corrupt the recorded state.
        Cross-process callbacks need Redis Streams; see INTEGRATION.md.
        """
        with self._callback_lock:
            self._callbacks.setdefault(approval_id, []).append(callback)

    def wait_for_decision(
        self,
        approval_id: str,
        *,
        timeout_seconds: float = DEFAULT_WAIT_TIMEOUT_SECONDS,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> dict[str, Any]:
        """Block the calling worker until the request leaves pending.

        Returns the terminal view (approved, denied, or expired). Raises
        ApprovalNotFoundError for a missing id and TimeoutError if no
        resolution arrives within timeout_seconds.
        """
        deadline = time.monotonic() + timeout_seconds
        while True:
            view = self.get(approval_id)
            if view["status"] in TERMINAL_STATUSES:
                return view
            if time.monotonic() >= deadline:
                raise TimeoutError(f"no decision for approval {approval_id} within {timeout_seconds}s")
            time.sleep(poll_interval_seconds)

    def _fetch(self, db: Session, approval_id: str) -> ApprovalRequestRow:
        row = db.get(ApprovalRequestRow, approval_id)
        if row is None:
            raise ApprovalNotFoundError(approval_id)
        return row

    def _expire(self, db: Session, row: ApprovalRequestRow, now: datetime) -> None:
        row.status = ApprovalStatus.EXPIRED.value
        row.decided_at = now
        db.add(ApprovalEventRow(approval_id=row.id, event="expired", actor=None, at=now))

    def _expire_if_overdue(self, db: Session, row: ApprovalRequestRow, now: datetime) -> bool:
        """Expire a pending row whose deadline passed. Returns True if expired."""
        if row.status != ApprovalStatus.PENDING.value or row.expires_at is None:
            return False
        if _aware(row.expires_at) > now:
            return False
        self._expire(db, row, now)
        return True

    def _fire_callbacks(self, approval_id: str, view: dict[str, Any]) -> None:
        with self._callback_lock:
            callbacks = self._callbacks.pop(approval_id, [])
        for callback in callbacks:
            try:
                callback(view)
            except Exception:
                continue


def _jsonable(view: dict[str, Any]) -> dict[str, Any]:
    """Convert a view dict into JSON-serializable form for event payloads."""
    result = dict(view)
    result["status"] = view["status"].value if isinstance(view["status"], ApprovalStatus) else view["status"]
    for key in ("created_at", "expires_at", "decided_at"):
        if isinstance(result.get(key), datetime):
            result[key] = result[key].isoformat()
    return result


_default_service: Service | None = None
_default_lock = threading.Lock()


def default_service() -> Service:
    """Lazily build the process-wide service against the shared database."""
    global _default_service
    with _default_lock:
        if _default_service is None:
            _default_service = Service()
    return _default_service


def request_approval(
    *,
    module_id: int,
    action_type: str,
    payload: dict[str, Any],
    user_id: str = DEFAULT_USER_ID,
    ttl_seconds: int | None = None,
    wait: bool = False,
    timeout_seconds: float = DEFAULT_WAIT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """SDK entry point every other module calls before a gated external effect.

    Returns the pending request view. With wait=True it blocks the calling
    worker and returns the terminal view after the human decides (or the
    request expires), which is the spec's release-to-execution handoff.
    """
    service = default_service()
    view = service.submit(
        module_id=module_id,
        action_type=action_type,
        payload=payload,
        user_id=user_id,
        ttl_seconds=ttl_seconds,
    )
    if wait:
        return service.wait_for_decision(
            view["id"],
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
    return view

# ---- Durable policy and exact-effect gate extensions ----
import fnmatch
import hashlib
import json
from sqlalchemy import Boolean, Integer, UniqueConstraint


class ApprovalPolicyRow(Base):
    __tablename__ = "m00_approval_policies"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    module_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    action_pattern: Mapped[str] = mapped_column(String(200), default="*")
    effect: Mapped[str] = mapped_column(String(20))
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    conditions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    review_ttl_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApprovalIdempotencyRow(Base):
    __tablename__ = "m00_approval_idempotency"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    approval_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApprovalEffectRow(Base):
    __tablename__ = "m00_approval_effects"
    __table_args__ = (UniqueConstraint("approval_id"), UniqueConstraint("effect_id"))
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    approval_id: Mapped[str] = mapped_column(String(36), index=True)
    effect_id: Mapped[str] = mapped_column(String(200), index=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(120))
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _request_hash(*, module_id: int, action_type: str, payload: dict[str, Any], user_id: str) -> str:
    body = {"module_id": module_id, "action_type": action_type, "payload": payload, "user_id": user_id}
    return hashlib.sha256(_canonical(body).encode()).hexdigest()


def _condition_matches(conditions: dict[str, Any], context: dict[str, Any]) -> bool:
    """Exact values and value lists; dotted keys address nested context."""
    for dotted, wanted in conditions.items():
        current: Any = context
        for part in dotted.split("."):
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]
        if isinstance(wanted, list):
            if current not in wanted:
                return False
        elif current != wanted:
            return False
    return True


def _policy_view(row: ApprovalPolicyRow) -> dict[str, Any]:
    return {"id": row.id, "name": row.name, "module_id": row.module_id,
            "action_pattern": row.action_pattern, "effect": row.effect,
            "priority": row.priority, "enabled": row.enabled,
            "conditions": row.conditions, "review_ttl_seconds": row.review_ttl_seconds,
            "created_at": _aware(row.created_at), "updated_at": _aware(row.updated_at)}


def _install_extensions() -> None:
    """Attach extensions without changing the established Service API."""
    def upsert_policy(self: Service, *, policy_id: str, name: str, action_pattern: str,
                      effect: str, actor: str, module_id: int | None = None,
                      priority: int = 0, enabled: bool = True,
                      conditions: dict[str, Any] | None = None,
                      review_ttl_seconds: int = 3600) -> dict[str, Any]:
        if effect not in {"allow", "deny", "review"}:
            raise ValueError("effect must be allow, deny, or review")
        if review_ttl_seconds <= 0:
            raise ValueError("review_ttl_seconds must be positive")
        now = self._clock()
        with self._sessions.begin() as db:
            row = db.get(ApprovalPolicyRow, policy_id)
            event = "policy_updated" if row else "policy_created"
            if row is None:
                row = ApprovalPolicyRow(id=policy_id, created_at=now)
                db.add(row)
            row.name, row.module_id, row.action_pattern = name, module_id, action_pattern
            row.effect, row.priority, row.enabled = effect, priority, enabled
            row.conditions, row.review_ttl_seconds, row.updated_at = conditions or {}, review_ttl_seconds, now
            # Policy events use their policy id in the existing append-only audit table.
            db.add(ApprovalEventRow(approval_id=f"policy:{policy_id}", event=event, actor=actor, at=now))
            db.flush()
            return _policy_view(row)

    def list_policies(self: Service, *, enabled_only: bool = False) -> list[dict[str, Any]]:
        with self._sessions() as db:
            stmt = select(ApprovalPolicyRow).order_by(ApprovalPolicyRow.priority.desc(), ApprovalPolicyRow.id)
            if enabled_only:
                stmt = stmt.where(ApprovalPolicyRow.enabled.is_(True))
            return [_policy_view(row) for row in db.scalars(stmt)]

    def evaluate_policy(self: Service, *, module_id: int, action_type: str,
                        context: dict[str, Any] | None = None) -> tuple[str, dict[str, Any] | None]:
        matches = [p for p in self.list_policies(enabled_only=True)
                   if (p["module_id"] is None or p["module_id"] == module_id)
                   and fnmatch.fnmatchcase(action_type, p["action_pattern"])
                   and _condition_matches(p["conditions"], context or {})]
        if not matches:
            return "review", None  # fail closed for unknown external effects
        top_priority = matches[0]["priority"]
        severity = {"deny": 0, "review": 1, "allow": 2}
        top = sorted((p for p in matches if p["priority"] == top_priority),
                     key=lambda p: (severity[p["effect"]], p["id"]))
        return top[0]["effect"], top[0]

    def gate(self: Service, *, module_id: int, action_type: str, payload: dict[str, Any],
             user_id: str = DEFAULT_USER_ID, context: dict[str, Any] | None = None,
             idempotency_key: str | None = None) -> dict[str, Any]:
        effect, policy = self.evaluate_policy(module_id=module_id, action_type=action_type, context=context)
        if effect == "allow":
            return {"decision": "allow", "allowed": True, "reason": "allowed by policy",
                    "policy_id": policy["id"], "approval": None}
        if effect == "deny":
            return {"decision": "deny", "allowed": False, "reason": "denied by policy",
                    "policy_id": policy["id"], "approval": None}
        digest = _request_hash(module_id=module_id, action_type=action_type, payload=payload, user_id=user_id)
        if idempotency_key:
            with self._sessions() as db:
                idem = db.get(ApprovalIdempotencyRow, idempotency_key)
                if idem:
                    if idem.request_hash != digest:
                        raise ApprovalConflictError("idempotency key belongs to another request")
                    return {"decision": "review", "allowed": False, "reason": "existing review",
                            "policy_id": policy["id"] if policy else None, "approval": self.get(idem.approval_id)}
        approval = self.submit(module_id=module_id, action_type=action_type, payload=payload,
                               user_id=user_id,
                               ttl_seconds=policy["review_ttl_seconds"] if policy else None)
        if idempotency_key:
            with self._sessions.begin() as db:
                db.add(ApprovalIdempotencyRow(key=idempotency_key, request_hash=digest,
                                               approval_id=approval["id"], created_at=self._clock()))
        return {"decision": "review", "allowed": False, "reason": "human review required",
                "policy_id": policy["id"] if policy else None, "approval": approval}

    def consume_effect(self: Service, approval_id: str, *, module_id: int, action_type: str,
                       payload: dict[str, Any], user_id: str, effect_id: str,
                       actor: str) -> dict[str, Any]:
        """Atomically issue a one-shot permit bound to the exact reviewed request."""
        digest = _request_hash(module_id=module_id, action_type=action_type, payload=payload, user_id=user_id)
        now = self._clock()
        with self._sessions.begin() as db:
            row = self._fetch(db, approval_id)
            if self._expire_if_overdue(db, row, now):
                raise ApprovalConflictError("approval has expired")
            existing = db.scalar(select(ApprovalEffectRow).where(ApprovalEffectRow.approval_id == approval_id))
            if existing:
                if existing.effect_id == effect_id and existing.request_hash == digest:
                    return {"approval_id": approval_id, "effect_id": effect_id,
                            "allowed": True, "consumed_at": _aware(existing.consumed_at)}
                raise ApprovalConflictError("approval has already been consumed")
            if row.status != ApprovalStatus.APPROVED.value:
                raise ApprovalConflictError(f"approval is {row.status}, not approved")
            stored = _request_hash(module_id=row.module_id, action_type=row.action_type,
                                   payload=row.payload, user_id=row.user_id)
            if stored != digest:
                raise ApprovalConflictError("effect does not match approved request")
            if db.scalar(select(ApprovalEffectRow).where(ApprovalEffectRow.effect_id == effect_id)):
                raise ApprovalConflictError("effect id has already been used")
            db.add(ApprovalEffectRow(approval_id=approval_id, effect_id=effect_id,
                                     request_hash=digest, actor=actor, consumed_at=now))
            db.add(ApprovalEventRow(approval_id=approval_id, event="effect_consumed", actor=actor, at=now))
        return {"approval_id": approval_id, "effect_id": effect_id, "allowed": True, "consumed_at": now}

    Service.upsert_policy = upsert_policy
    Service.list_policies = list_policies
    Service.evaluate_policy = evaluate_policy
    Service.gate = gate
    Service.consume_effect = consume_effect


_install_extensions()
